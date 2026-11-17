using AndroidManager.Core.Adb;
using AndroidManager.Core.Settings;
using AndroidManager.Services;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Media;
using Avalonia.Threading;
using Avalonia.VisualTree;

namespace AndroidManager.Views;

public partial class ConsoleView : UserControl
{
    // Те же границы, что у Python-версии: буфер ограничен, старые строки выбрасываются.
    private const int MaxLines = 20000;
    private const int TrimTo = 15000;
    private const int DrainPerTick = 500;

    private readonly List<string> _lines = new();
    private readonly List<string> _history = new();
    private readonly DispatcherTimer _timer = new() { Interval = TimeSpan.FromMilliseconds(50) };

    private ScrollViewer? _scroll;
    private AdbStream? _stream;
    private int _historyPos;

    public AppState Ctx { get; set; } = null!;

    public ConsoleView()
    {
        InitializeComponent();

        RunBtn.Click += (_, _) => Run();
        StopBtn.Click += (_, _) => StopStream();
        ClearBtn.Click += (_, _) => Clear();
        CmdBox.KeyDown += OnKeyDown;

        // Быстрые команды: кнопка просто подставляет команду в поле и выполняет её.
        foreach (var command in Defaults.ConsoleBar)
        {
            var button = new Button { Content = command, Margin = new Thickness(0, 0, 6, 0) };
            button.Click += (_, _) => RunCommand(command);
            QuickBar.Children.Add(button);
        }

        _timer.Tick += (_, _) => Drain();
        Loaded += (_, _) => { ApplyFont(); RefreshCustomBar(); };
    }

    /// <summary>Перерисовывает кастомные кнопки панели «Консоль».</summary>
    public void RefreshCustomBar()
    {
        if (Ctx is null)
            return;

        var count = CustomBars.Render(Ctx, CustomBars.PanelConsole, CustomBar, TopLevel.GetTopLevel(this));
        CustomBar.IsVisible = count > 0;
    }

    /// <summary>Размер шрифта консоли. Вызывается при загрузке и после сохранения настроек.</summary>
    public void ApplyFont()
    {
        var size = Ctx?.Settings.ConsoleFontSize ?? 12;
        Output.FontSize = size;
        CmdBox.FontSize = size;
    }

    public void OnDeviceChanged()
    {
        if (_stream is null)
            return;

        StopStream();
        AppendLine($"[устройство: {Ctx?.Serial ?? "нет"}]");
    }

    private void Run()
    {
        RunCommand(CmdBox.Text ?? "");
        CmdBox.Text = "";
    }

    private void RunCommand(string command)
    {
        var cmd = command.Trim();
        var serial = Ctx?.Serial;

        if (cmd.Length == 0 || string.IsNullOrEmpty(serial))
            return;

        if (cmd == "clear")
        {
            Clear();
            return;
        }

        Remember(cmd);
        AppendLine($"$ {cmd}");

        if (IsStreaming(cmd))
        {
            StartStream(cmd, serial);
            return;
        }

        _ = RunOnceAsync(cmd, serial);
    }

    private async Task RunOnceAsync(string cmd, string serial)
    {
        var client = new AdbClient(Ctx.AdbPath, serial, 120);

        var text = await Task.Run(() =>
        {
            var (_, stdout, stderr) = client.Shell(cmd, 120);
            return stdout.TrimEnd().Length > 0 ? stdout.TrimEnd() : stderr.TrimEnd();
        });

        if (text.Length > 0)
            AppendText(text);
    }

    private void StartStream(string cmd, string serial)
    {
        StopStream();

        // logcat без флагов — прямой поток; всё остальное идёт через shell.
        var hasShellOps = cmd.IndexOfAny(new[] { '|', '>', '&', ';' }) >= 0;
        var args = cmd.StartsWith("logcat", StringComparison.Ordinal) && !hasShellOps
            ? Ctx.Args(cmd.Split(' ', StringSplitOptions.RemoveEmptyEntries))
            : Ctx.Args("shell", cmd);

        try
        {
            _stream = AdbStream.Start(args);
        }
        catch (Exception ex)
        {
            AppendLine($"[не удалось запустить поток: {ex.Message}]");
            return;
        }

        StopBtn.IsEnabled = true;
        if (!_timer.IsEnabled)
            _timer.Start();
    }

    private void StopStream()
    {
        if (_stream is null)
            return;

        _stream.Dispose();
        _stream = null;
        StopBtn.IsEnabled = false;
        AppendLine("[остановлено пользователем]");
    }

    // Один заход в UI-поток на тик: до DrainPerTick строк за раз, одна перерисовка списка.
    private void Drain()
    {
        if (_stream is null)
        {
            _timer.Stop();
            return;
        }

        var added = 0;

        while (added < DrainPerTick && _stream.Lines.TryRead(out var line))
        {
            _lines.Add(line!);
            added++;
        }

        if (!_stream.IsFinished)
        {
            if (added > 0)
                Render();

            return;
        }

        // Поток закрыт: добираем остаток, иначе последние строки потерялись бы.
        while (_stream.Lines.TryRead(out var last))
            _lines.Add(last!);

        _lines.Add("[поток завершён]");
        Render();

        _stream.Dispose();
        _stream = null;
        StopBtn.IsEnabled = false;
        _timer.Stop();
    }

    private void AppendLine(string text)
    {
        _lines.Add(text);
        Render();
    }

    private void AppendText(string text)
    {
        foreach (var line in text.Split('\n'))
            _lines.Add(line.TrimEnd('\r'));

        Render();
    }

    private void Render()
    {
        if (_lines.Count > MaxLines)
            _lines.RemoveRange(0, _lines.Count - TrimTo);

        // Сброс источника — единственный способ уведомить список. Прокрутка смещением,
        // а не ScrollIntoView: тот реализует все элементы от 0 до конца.
        Output.ItemsSource = null;
        Output.ItemsSource = _lines;

        _scroll ??= Output.FindDescendantOfType<ScrollViewer>();
        if (_scroll is null)
            return;

        var max = _scroll.Extent.Height - _scroll.Viewport.Height;
        if (max > 0)
            _scroll.Offset = new Vector(0, max);
    }

    private void Clear()
    {
        _lines.Clear();
        Output.ItemsSource = null;
    }

    private void Remember(string cmd)
    {
        var limit = Math.Max(50, Ctx.Settings.ConsoleHistoryLimit);

        _history.Add(cmd);
        if (_history.Count > limit)
            _history.RemoveRange(0, _history.Count - limit);

        _historyPos = _history.Count;
    }

    private void MoveHistory(int delta)
    {
        if (_history.Count == 0)
            return;

        _historyPos = Math.Clamp(_historyPos + delta, 0, _history.Count);
        CmdBox.Text = _historyPos < _history.Count ? _history[_historyPos] : "";
        CmdBox.CaretIndex = CmdBox.Text.Length;
    }

    private void OnKeyDown(object? sender, KeyEventArgs e)
    {
        if (e.Key == Key.Return)
        {
            e.Handled = true;
            Run();
        }
        else if (e.Key == Key.Up)
        {
            e.Handled = true;
            MoveHistory(-1);
        }
        else if (e.Key == Key.Down)
        {
            e.Handled = true;
            MoveHistory(1);
        }
    }

    private static bool IsStreaming(string cmd)
    {
        foreach (var prefix in "dmesg -w top watch ping tail -f".Split(' '))
        {
            if (cmd.StartsWith(prefix, StringComparison.Ordinal))
                return true;
        }

        if (!cmd.StartsWith("logcat", StringComparison.Ordinal))
            return false;

        foreach (var part in cmd.Split(' ', StringSplitOptions.RemoveEmptyEntries))
        {
            if (part is "-d" or "-c" or "-t" or "--dump" or "--clear")
                return false;
        }

        return true;
    }

    public void Shutdown()
    {
        _timer.Stop();

        if (_stream is not null)
        {
            _stream.Dispose();
            _stream = null;
        }
    }
}