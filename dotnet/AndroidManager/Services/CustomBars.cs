using AndroidManager.Core.Adb;
using AndroidManager.Core.Settings;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Controls.Primitives;
using Avalonia.Input;
using Avalonia.Interactivity;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Threading;
using Avalonia.VisualTree;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading.Tasks;

namespace AndroidManager.Services;

/// <summary>
/// Кастомные кнопки живут на своих вкладках, как в Python-версии:
/// console → Консоль, apps → Приложения, tools → Действия. Здесь — общий рендер, редактор и запуск.
/// </summary>
public static class CustomBars
{
    public const string PanelTools = "tools";
    public const string PanelApps = "apps";
    public const string PanelConsole = "console";
    public const string PanelConsoleQuick = "console_quick";

    public static readonly Dictionary<string, string> PanelTitles = new()
    {
        [PanelTools] = "Действия",
        [PanelApps] = "Приложения",
        [PanelConsole] = "Консоль",
        [PanelConsoleQuick] = "Быстрые команды консоли",
    };

    private sealed class DragState
    {
        public string Panel = "";
        public int Index;
        public Point Start;
        public bool Moved;
        public Button? Source;
    }

    // Последний отрисованный хост каждой панели: по нему ловим бросок и перерисовываем.
    private static readonly Dictionary<string, (Panel Host, Action Repaint, AppState Ctx)> _bars = new();
    private static readonly HashSet<Panel> _wired = new();
    private static DragState? _drag;
    private const double DragThreshold = 6;

    /// <summary>Список кнопок панели, создаётся при необходимости.</summary>
    public static List<BarItem> Items(AppState ctx, string panel)
    {
        ctx.Settings.Bars ??= new();
        if (!ctx.Settings.Bars.TryGetValue(panel, out var list) || list is null)
            ctx.Settings.Bars[panel] = list = new();
        return list;
    }

    /// <summary>
    /// Кнопки панели плюс «+ Кнопка» в конце. ПКМ по кнопке — изменить/удалить/переставить.
    /// onChanged перерисовывает панель после правки. showAdd=false — без «+ Кнопка»
    /// (быстрые команды консоли: там своя панель создания).
    /// </summary>
    public static void Render(AppState ctx, string panel, Panel host, TopLevel? top, Action? onChanged, Action<BarItem>? onRun = null, bool showAdd = true)
    {
        host.Children.Clear();
        var items = Items(ctx, panel);

        _bars[panel] = (host, () =>
        {
            if (onChanged is not null)
                onChanged();
            else
                Render(ctx, panel, host, top, null, onRun, showAdd);
        }, ctx);

        WireHost(host);

        for (var idx = 0; idx < items.Count; idx++)
        {
            var item = items[idx];
            var i = idx;

            // Тот же акцент, что у кнопки подключения; padding компактнее — кнопки идут в ряд.
            var btn = new Button
            {
                Content = item.Name,
                Margin = new Thickness(0, 0, 6, 6),
                Classes = { "btn--primary" },
                Padding = new Thickness(14, 6),
                FontSize = 12,
            };
            ToolTip.SetTip(btn, $"{item.Type}: {item.Cmd}\nПеретащите кнопку, чтобы переставить её");
            btn.Click += (_, _) =>
            {
                if (onRun is not null)
                    onRun(item);
                else
                    Run(ctx, item, top);
            };

            var menu = new ContextMenu();
            menu.Items.Add(new MenuItem { Header = "Изменить", Tag = i });
            menu.Items.Add(new MenuItem { Header = "Удалить", Tag = i });
            menu.Items.Add(new Separator());
            menu.Items.Add(new MenuItem { Header = "Сдвинуть влево", Tag = i });
            menu.Items.Add(new MenuItem { Header = "Сдвинуть вправо", Tag = i });

            void OnMenuItem(object? s, RoutedEventArgs e)
            {
                if (s is not MenuItem mi)
                    return;

                var id = (int)mi.Tag!;
                switch (mi.Header as string ?? "")
                {
                    case "Изменить": Edit(ctx, panel, id, top as Window, onChanged); break;
                    case "Удалить": Delete(ctx, panel, id, onChanged); break;
                    case "Сдвинуть влево": Move(ctx, panel, id, -1, onChanged); break;
                    case "Сдвинуть вправо": Move(ctx, panel, id, 1, onChanged); break;
                }
            }

            foreach (var mi in menu.Items.OfType<MenuItem>())
                mi.Click += OnMenuItem;

            btn.ContextMenu = menu;
            host.Children.Add(btn);
        }

        if (!showAdd)
            return;

        var add = new Button
        {
            Content = "+ Кнопка",
            Margin = new Thickness(0, 0, 6, 6),
            Classes = { "btn--ghost" },
            Padding = new Thickness(14, 6),
            FontSize = 12,
        };
        ToolTip.SetTip(add, $"Создать свою кнопку на панели «{PanelTitles.GetValueOrDefault(panel, panel)}»");
        add.Click += (_, _) => Edit(ctx, panel, null, top as Window, onChanged);
        host.Children.Add(add);
    }

    /// <summary>
    /// Перетаскивание живёт на самой панели, а не на кнопке: нажатие не трогаем вовсе,
    /// иначе клик по кнопке перестаёт срабатывать. Указатель захватывается только
    /// после сдвига дальше порога — тогда кнопка отпускание уже не получает.
    /// </summary>
    private static void WireHost(Panel host)
    {
        if (!_wired.Add(host))
            return;

        host.AddHandler(InputElement.PointerPressedEvent, HostPressed, RoutingStrategies.Tunnel);
        host.AddHandler(InputElement.PointerMovedEvent, HostMoved, RoutingStrategies.Tunnel, handledEventsToo: true);
        host.AddHandler(InputElement.PointerReleasedEvent, HostReleased, RoutingStrategies.Tunnel, handledEventsToo: true);
    }

    private static (AppState Ctx, string Panel)? FindEntry(Panel host)
    {
        foreach (var (key, bar) in _bars)
        {
            if (ReferenceEquals(bar.Host, host))
                return (bar.Ctx, key);
        }

        return null;
    }

    private static void HostPressed(object? sender, PointerPressedEventArgs e)
    {
        if (sender is not Panel host || _drag is not null)
            return;

        if (!e.GetCurrentPoint(host).Properties.IsLeftButtonPressed)
            return;

        var entry = FindEntry(host);
        if (entry is null)
            return;

        var btn = (e.Source as Visual)?.GetSelfAndVisualAncestors().OfType<Button>()
            .FirstOrDefault(b => b.Parent == host);
        if (btn is null)
            return;

        var index = host.Children.IndexOf(btn);
        if (index < 0 || index >= Items(entry.Value.Ctx, entry.Value.Panel).Count)
            return;

        _drag = new DragState { Panel = entry.Value.Panel, Index = index, Start = e.GetPosition(host), Source = btn };
    }

    private static void HostMoved(object? sender, PointerEventArgs e)
    {
        if (_drag is null || _drag.Moved || sender is not Panel host)
            return;

        if (!e.GetCurrentPoint(host).Properties.IsLeftButtonPressed)
            return;

        if (DragDistance(e.GetPosition(host), _drag.Start) < DragThreshold)
            return;

        _drag.Moved = true;
        if (_drag.Source is not null)
            _drag.Source.Opacity = 0.55;

        e.Pointer.Capture(host);
    }

    private static void HostReleased(object? sender, PointerReleasedEventArgs e)
    {
        if (_drag is null || sender is not Panel host)
            return;

        var drag = _drag;
        _drag = null;

        if (!drag.Moved)
            return;

        if (drag.Source is not null)
            drag.Source.Opacity = 1;

        e.Pointer.Capture(null);

        var entry = FindEntry(host);
        var top = TopLevel.GetTopLevel(host);
        if (entry is null || top is null)
            return;

        var windowPoint = e.GetPosition(top);
        var hit = top.InputHitTest(windowPoint);

        if (FindDropTarget(hit, e, out var toPanel, out var toIndex))
            MoveTo(entry.Value.Ctx, drag.Panel, drag.Index, toPanel, toIndex);
        else if (TryDropOnHostArea(top, windowPoint, out var areaPanel))
            MoveTo(entry.Value.Ctx, drag.Panel, drag.Index, areaPanel, -1);
    }

    private static double DragDistance(Point a, Point b) => Math.Abs(a.X - b.X) + Math.Abs(a.Y - b.Y);

    /// <summary>Ищет панель под указателем и позицию вставки (-1 — в конец).</summary>
    private static bool FindDropTarget(IInputElement? hit, PointerReleasedEventArgs e, out string panel, out int index)
    {
        panel = "";
        index = -1;

        if (hit is not Visual v)
            return false;

        foreach (var anc in v.GetSelfAndVisualAncestors())
        {
            if (anc is not Panel p)
                continue;

            foreach (var (key, bar) in _bars)
            {
                if (!ReferenceEquals(bar.Host, p))
                    continue;

                panel = key;

                var target = v.GetSelfAndVisualAncestors().OfType<Button>().FirstOrDefault(b => b.Parent == p);
                if (target is null)
                    return true;

                // Правее середины кнопки — встать после неё.
                var bounds = target.Bounds;
                var pt = e.GetPosition(p);
                index = p.Children.IndexOf(target) + (pt.X > bounds.X + bounds.Width / 2 ? 1 : 0);
                return true;
            }
        }

        return false;
    }

    /// <summary>Точка внутри области панели (пустое место ряда) — бросок в конец.</summary>
    private static bool TryDropOnHostArea(TopLevel top, Point windowPoint, out string panel)
    {
        panel = "";

        foreach (var (key, bar) in _bars)
        {
            if (top.TranslatePoint(windowPoint, bar.Host) is not { } p)
                continue;

            if (p.X < 0 || p.Y < 0 || p.X > bar.Host.Bounds.Width || p.Y > bar.Host.Bounds.Height)
                continue;

            panel = key;
            return true;
        }

        return false;
    }

    /// <summary>Переносит кнопку между панелями (или внутри одной) и сохраняет настройки.</summary>
    private static void MoveTo(AppState ctx, string fromPanel, int fromIndex, string toPanel, int toIndex)
    {
        var from = Items(ctx, fromPanel);
        if (fromIndex < 0 || fromIndex >= from.Count)
            return;

        var to = Items(ctx, toPanel);
        var item = from[fromIndex];

        if (toIndex < 0)
            toIndex = to.Count;

        if (fromPanel == toPanel)
        {
            if (toIndex > fromIndex)
                toIndex--;
            toIndex = Math.Clamp(toIndex, 0, to.Count - 1);
            if (toIndex == fromIndex)
                return;
        }
        else
        {
            toIndex = Math.Clamp(toIndex, 0, to.Count);
        }

        from.RemoveAt(fromIndex);
        to.Insert(toIndex, item);
        ctx.SaveSettings();

        RepaintBar(fromPanel);
        if (toPanel != fromPanel)
            RepaintBar(toPanel);
    }

    private static void RepaintBar(string panel)
    {
        if (_bars.TryGetValue(panel, out var bar))
            bar.Repaint();
    }

    /// <summary>Заготовки для нового окна кнопки: заполняют поля, дальше правятся руками.</summary>
    private static readonly (string Name, string Type, string Cmd, bool ShowWindow, bool KeepOpen, bool EchoOutput)[] Templates =
    {
        ("Пустая команда", "shell", "", false, true, true),
        ("Проверка интернета (ПК, окно)", "pc", "ping 8.8.8.8", true, true, false),
        ("Проверить доступность приставки (ПК)", "pc", "ping {serial}", true, true, false),
        ("Открыть папку загрузок (ПК)", "pc", "start \"\" \"%USERPROFILE%\\Downloads\"", false, true, false),
        ("Скриншот приставки на ПК", "pc", "adb -s {serial} exec-out screencap -p > \"%USERPROFILE%\\Desktop\\screen.png\"", false, true, true),
        ("Забрать файл с приставки (ПК)", "pc", "adb -s {serial} pull /sdcard/file.txt \"%USERPROFILE%\\Desktop\\\"", false, true, true),
        ("Список пакетов", "shell", "pm list packages -3", false, true, true),
        ("Очистить logcat", "shell", "logcat -c", false, true, true),
        ("Свободное место", "shell", "df -h /data", false, true, true),
        ("Перезагрузка", "shell", "reboot", false, true, true),
    };

    /// <summary>Окно создания и правки кнопки.</summary>
    public static void Edit(AppState ctx, string panel, int? id, Window? owner, Action? onChanged)
    {
        var items = Items(ctx, panel);
        var editing = id.HasValue && id.Value >= 0 && id.Value < items.Count ? items[id.Value] : null;
        var isNew = editing == null;

        var win = new Window
        {
            Title = isNew
                ? $"Новая кнопка · {PanelTitles.GetValueOrDefault(panel, panel)}"
                : $"Изменить кнопку · {PanelTitles.GetValueOrDefault(panel, panel)}",
            Width = 640,
            Height = 620,
            CanResize = false,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
            Background = (IBrush?)Application.Current?.Resources["Panel"] ?? Brushes.Black,
        };

        var scroll = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
        var root = new StackPanel { Spacing = 6, Margin = new Thickness(24) };
        scroll.Content = root;
        win.Content = scroll;

        var nameBox = new TextBox { Text = editing?.Name ?? "", Watermark = "Например: Очистить logcat", Margin = new Thickness(0, 0, 0, 8) };
        var typeBox = new ComboBox { Margin = new Thickness(0, 0, 0, 8), HorizontalAlignment = HorizontalAlignment.Stretch };
        // Сначала элементы, потом выбор: обратный порядок оставляет список пустым.
        typeBox.Items.Add("shell");
        typeBox.Items.Add("pc");
        typeBox.SelectedIndex = editing?.Type == "pc" ? 1 : 0;
        var cmdBox = new TextBox { Text = editing?.Cmd ?? "", Margin = new Thickness(0, 0, 0, 8) };

        var error = new TextBlock
        {
            Text = "Заполните название и команду",
            Foreground = new SolidColorBrush(Color.Parse("#F38BA8")),
            IsVisible = false,
            Margin = new Thickness(0, 0, 0, 8),
        };

        var hint = new TextBlock
        {
            FontSize = 11,
            Foreground = (IBrush?)Application.Current?.Resources["Muted"] ?? Brushes.Gray,
            TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(0, 0, 0, 8),
        };

        // Переключатели действуют только на pc-команды: у shell вывод всегда идёт в «Логи».
        var showWindowBox = new CheckBox { Content = "Открывать окно консоли", IsChecked = editing?.ShowWindow ?? false };
        var keepOpenBox = new CheckBox { Content = "Не закрывать окно после выполнения (cmd /k)", IsChecked = editing?.KeepOpen ?? true };
        var echoBox = new CheckBox { Content = "Писать вывод команды в «Логи»", IsChecked = editing?.EchoOutput ?? true };

        var pcOptions = new StackPanel { Spacing = 4, Margin = new Thickness(0, 0, 0, 8) };
        pcOptions.Children.Add(new TextBlock { Text = "ПАРАМЕТРЫ ЗАПУСКА НА ПК", FontSize = 10, FontWeight = FontWeight.Bold });
        pcOptions.Children.Add(showWindowBox);
        pcOptions.Children.Add(keepOpenBox);
        pcOptions.Children.Add(echoBox);

        void RefreshHints()
        {
            var pc = typeBox.SelectedItem as string == "pc";

            hint.Text = pc
                ? "pc — команда на ПК: запускается через cmd.exe.\n"
                  + "{serial} подставляется (адрес подключённого устройства), {clipboard} — нет.\n"
                  + "Чтобы увидеть работу команды (например, ping), включите окно консоли.\n"
                  + "Вывод попадает в «Логи» только при включённом переключателе ниже."
                : "shell — команда на устройстве: adb shell <команда>.\n"
                  + "{serial} — адрес подключённого устройства, {clipboard} — текст из буфера обмена.\n"
                  + "Вводимая команда без «adb shell» — префикс добавляется сам.\n"
                  + "На панели «Приложения» дополнительно работает {pkg} — один запуск на каждый выбранный пакет.";

            pcOptions.IsVisible = pc;
            keepOpenBox.IsVisible = pc && showWindowBox.IsChecked == true;

            var preview = cmdBox.Text?.Trim() ?? "";
            if (preview.Length == 0)
                return;

            var serial = ctx.Serial ?? "192.168.1.10:5555";
            var shown = preview.Replace("{serial}", serial).Replace("{clipboard}", "<буфер>");
            hint.Text += "\n\nБудет выполнено:\n" + (pc ? $"cmd.exe /{(keepOpenBox.IsChecked == true ? "k" : "c")} {shown}" : $"adb shell {shown}");
        }

        var saveBtn = new Button { Content = "Сохранить", MinWidth = 100 };
        var cancelBtn = new Button { Content = "Отмена", MinWidth = 100 };
        var deleteBtn = new Button { Content = "Удалить", MinWidth = 100, IsVisible = !isNew };

        var btnBar = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8, HorizontalAlignment = HorizontalAlignment.Right };
        btnBar.Children.Add(cancelBtn);
        if (!isNew)
            btnBar.Children.Add(deleteBtn);
        btnBar.Children.Add(saveBtn);

        root.Children.Add(new TextBlock { Text = "Название" });
        root.Children.Add(nameBox);
        root.Children.Add(new TextBlock { Text = "Тип" });
        root.Children.Add(typeBox);
        root.Children.Add(new TextBlock { Text = "Команда" });
        root.Children.Add(cmdBox);
        root.Children.Add(pcOptions);

        // Готовые заготовки: заполняют поля, дальше их можно править руками.
        if (isNew)
        {
            root.Children.Add(new TextBlock { Text = "ШАБЛОН", FontSize = 10, FontWeight = FontWeight.Bold, Margin = new Thickness(0, 8, 0, 2) });

            var templates = new StackPanel { Spacing = 4, Margin = new Thickness(0, 0, 0, 8) };
            var templateBox = new ComboBox
            {
                HorizontalAlignment = HorizontalAlignment.Stretch,
                PlaceholderText = "Выберите готовую заготовку",
            };
            foreach (var t in Templates)
                templateBox.Items.Add(new ComboBoxItem { Content = t.Name });

            templateBox.SelectionChanged += (_, _) =>
            {
                if (templateBox.SelectedIndex < 0)
                    return;

                var t = Templates[templateBox.SelectedIndex];
                nameBox.Text = t.Name;
                typeBox.SelectedItem = t.Type;
                cmdBox.Text = t.Cmd;
                showWindowBox.IsChecked = t.ShowWindow;
                keepOpenBox.IsChecked = t.KeepOpen;
                echoBox.IsChecked = t.EchoOutput;
                RefreshHints();
            };

            templates.Children.Add(templateBox);
            root.Children.Add(templates);
        }

        root.Children.Add(hint);
        root.Children.Add(error);
        root.Children.Add(btnBar);

        typeBox.SelectionChanged += (_, _) => RefreshHints();
        cmdBox.TextChanged += (_, _) => RefreshHints();
        showWindowBox.IsCheckedChanged += (_, _) => RefreshHints();
        keepOpenBox.IsCheckedChanged += (_, _) => RefreshHints();
        RefreshHints();

        saveBtn.Click += (_, _) =>
        {
            var name = nameBox.Text?.Trim() ?? "";
            var cmd = cmdBox.Text?.Trim() ?? "";
            var type = typeBox.SelectedItem as string ?? "shell";

            if (name.Length == 0 || cmd.Length == 0)
            {
                error.IsVisible = true;
                return;
            }

            var barItem = new BarItem
            {
                Name = name,
                Cmd = cmd,
                Type = type,
                ShowWindow = showWindowBox.IsChecked == true,
                KeepOpen = keepOpenBox.IsChecked != false,
                EchoOutput = echoBox.IsChecked != false,
            };
            if (isNew)
                items.Add(barItem);
            else
                items[id!.Value] = barItem;

            ctx.SaveSettings();
            onChanged?.Invoke();
            win.Close();
        };

        cancelBtn.Click += (_, _) => win.Close();
        deleteBtn.Click += (_, _) =>
        {
            items.RemoveAt(id!.Value);
            ctx.SaveSettings();
            onChanged?.Invoke();
            win.Close();
        };

        if (owner is not null)
            win.ShowDialog(owner);
        else
            win.Show();
    }

    private static void Delete(AppState ctx, string panel, int id, Action? onChanged)
    {
        var items = Items(ctx, panel);
        if (id < 0 || id >= items.Count)
            return;

        items.RemoveAt(id);
        ctx.SaveSettings();
        onChanged?.Invoke();
    }

    private static void Move(AppState ctx, string panel, int id, int delta, Action? onChanged)
    {
        var items = Items(ctx, panel);
        var j = id + delta;
        if (id < 0 || id >= items.Count || j < 0 || j >= items.Count)
            return;

        (items[id], items[j]) = (items[j], items[id]);
        ctx.SaveSettings();
        onChanged?.Invoke();
    }

    /// <summary>Выполняет кнопку: shell-команда на устройстве или команда на ПК.</summary>
    public static void Run(AppState ctx, BarItem item, TopLevel? top)
    {
        var type = item.Type ?? "shell";
        var cmd = item.Cmd;

        if (type == "pc")
        {
            _ = Task.Run(() => ExecutePcCommand(ctx, cmd, item.Name, item));
            return;
        }

        var serial = ctx.Serial;
        if (string.IsNullOrEmpty(serial))
        {
            ctx.Log("Сначала подключите устройство");
            return;
        }

        string finalCmd;
        try
        {
            var clip = top?.Clipboard?.GetTextAsync().GetAwaiter().GetResult();
            finalCmd = cmd.Replace("{clipboard}", clip ?? "").Replace("{serial}", serial);
        }
        catch
        {
            finalCmd = cmd.Replace("{serial}", serial);
        }

        _ = Task.Run(() =>
        {
            var (rc, out_, err) = new AdbClient(ctx.AdbPath, serial, 60).Shell(finalCmd, 60);
            var answer = (out_ + err).Trim();
            Dispatcher.UIThread.Post(() =>
            {
                if (answer.Length > 0)
                    ctx.Log($"{item.Name}: {answer}");
                else if (rc == 0)
                    ctx.Log($"{item.Name}: выполнено");
                else
                    ctx.Log($"{item.Name}: ошибка rc={rc}");
            });
        });
    }

    /// <summary>Кнопка панели «Приложения» над выбранным списком: {pkg} подставляется на каждый пакет.</summary>
    public static void RunForPackages(AppState ctx, BarItem item, IReadOnlyList<string> packages, TopLevel? top)
    {
        var cmd = item.Cmd ?? "";
        var type = item.Type ?? "shell";

        if (!cmd.Contains("{pkg}"))
        {
            Run(ctx, item, top);
            return;
        }

        if (packages.Count == 0)
        {
            ctx.Log("Выберите хотя бы одно приложение");
            return;
        }

        var serial = ctx.Serial;
        if (type == "shell" && string.IsNullOrEmpty(serial))
        {
            ctx.Log("Сначала подключите устройство");
            return;
        }

        var clip = "";
        try
        {
            clip = top?.Clipboard?.GetTextAsync().GetAwaiter().GetResult() ?? "";
        }
        catch
        {
        }

        _ = Task.Run(() =>
        {
            var client = type == "shell" ? new AdbClient(ctx.AdbPath, serial!, 60) : null;

            foreach (var pkg in packages)
            {
                var finalCmd = cmd.Replace("{pkg}", pkg).Replace("{clipboard}", clip);

                if (client is null)
                {
                    ExecutePcCommand(ctx, finalCmd, $"{item.Name} · {pkg}", item);
                    continue;
                }

                var (rc, out_, err) = client.Shell(finalCmd.Replace("{serial}", serial!), 60);
                var answer = (out_ + err).Trim();
                var p = pkg;

                Dispatcher.UIThread.Post(() =>
                {
                    if (answer.Length > 0)
                        ctx.Log($"{item.Name} · {p}: {answer}");
                    else if (rc == 0)
                        ctx.Log($"{item.Name} · {p}: выполнено");
                    else
                        ctx.Log($"{item.Name} · {p}: ошибка rc={rc}");
                });
            }
        });
    }

    /// <summary>Команда на ПК. Окно консоли, /k и вывод в «Логи» задаются параметрами кнопки.</summary>
    private static void ExecutePcCommand(AppState ctx, string cmd, string name, BarItem? item = null)
    {
        var showWindow = item?.ShowWindow == true;
        var keepOpen = item?.KeepOpen != false;
        var echo = item?.EchoOutput != false;

        // Подстановки: serial есть только при подключённом устройстве.
        var finalCmd = cmd.Replace("{serial}", ctx.Serial ?? "");

        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = "cmd.exe",
                Arguments = $"/{(keepOpen && showWindow ? "k" : "c")} {finalCmd}",
                UseShellExecute = showWindow,
                // Видимое окно и перенаправление вывода несовместимы.
                CreateNoWindow = !showWindow,
                RedirectStandardOutput = !showWindow && echo,
                RedirectStandardError = !showWindow && echo,
            };

            using var proc = Process.Start(psi);
            if (proc is null)
                return;

            if (echo && !showWindow)
            {
                var stdout = proc.StandardOutput.ReadToEnd().TrimEnd();
                var stderr = proc.StandardError.ReadToEnd().TrimEnd();
                var rc = proc.WaitForExit(120000) ? proc.ExitCode : -1;

                if (stdout.Length > 0 || stderr.Length > 0)
                {
                    // Многострочный вывод панель логов не любит — берём хвост.
                    var text = (stdout + (stderr.Length > 0 ? "\n" + stderr : "")).Trim();
                    var lines = text.Split('\n');
                    if (lines.Length > 20)
                        text = "…\n" + string.Join('\n', lines[^20..]);

                    Dispatcher.UIThread.Post(() => ctx.Log($"{name}:\n{text}"));
                }

                Dispatcher.UIThread.Post(() => ctx.Log($"{name}: завершено, код {rc}"));
                return;
            }

            proc.WaitForExit(30000);
            Dispatcher.UIThread.Post(() => ctx.Log($"{name}: выполнено на ПК"));
        }
        catch (Exception ex)
        {
            Dispatcher.UIThread.Post(() => ctx.Log($"{name}: ошибка на ПК — {ex.Message}"));
        }
    }
}
