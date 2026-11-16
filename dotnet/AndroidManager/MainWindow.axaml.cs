using AndroidManager.Core.Adb;
using AndroidManager.Core.Devices;
using AndroidManager.Core.Parsing;
using AndroidManager.Core.Settings;
using AndroidManager.Services;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Media;
using Avalonia.Styling;
using Avalonia.Threading;

namespace AndroidManager;

public partial class MainWindow : Window
{
    private static readonly IBrush StatusOk = new SolidColorBrush(Color.Parse("#A6E3A1"));
    private static readonly IBrush StatusWarn = new SolidColorBrush(Color.Parse("#F9E2AF"));
    private static readonly IBrush StatusErr = new SolidColorBrush(Color.Parse("#F38BA8"));

    private readonly AppState _ctx;
    private bool _busy;

    public MainWindow()
    {
        InitializeComponent();

        var (settings, error) = AppSettings.Load();
        _ctx = new AppState(settings, AppSettings.DefaultPath);

        _ctx.Logged += text => Dispatcher.UIThread.Post(() => StatusLine.Text = text);
        _ctx.DevicesRefresh += () => Dispatcher.UIThread.Post(() => _ = RefreshDevicesAsync());

        if (error is not null)
            _ctx.Log($"Настройки не прочитаны, беру значения по умолчанию: {error}");

        ConnectionTab.Ctx = _ctx;
        ConsoleTab.Ctx = _ctx;
        AppsTab.Ctx = _ctx;
        CardsTab.Ctx = _ctx;
        SettingsTab.Ctx = _ctx;

        ConnectionTab.DevicesChanged += () => Dispatcher.UIThread.Post(() => _ = RefreshDevicesAsync());
        ConnectionTab.DeviceSelected += serial => OnDeviceSelected(serial);
        SettingsTab.SettingsChanged += ApplyThemeAndFont;

        // Sidebar навигация
        BtnHome.Click += (_, _) => ShowPage("home");
        BtnStrategies.Click += (_, _) => ShowPage("strategies");
        BtnSpeed.Click += (_, _) => ShowPage("speed");
        BtnCloud.Click += (_, _) => ShowPage("cloud");
        BtnTelegram.Click += (_, _) => ShowPage("telegram");
        BtnStats.Click += (_, _) => ShowPage("stats");
        BtnSettings.Click += (_, _) => ShowPage("settings");

        Closed += (_, _) => ConsoleTab.Shutdown();

        ApplyThemeAndFont();
        _ctx.Log($"Настройки: {_ctx.SettingsPath}");
        ShowPage("home");
        _ = RefreshDevicesAsync();
    }

    private void ShowPage(string page)
    {
        PanelConnection.IsVisible = page == "home";
        PanelConsole.IsVisible = page == "console";
        PanelApps.IsVisible = page == "apps";
        PanelCards.IsVisible = page == "cards";
        PanelSettings.IsVisible = page == "settings";

        SetActiveSidebar(page);
    }

    private void SetActiveSidebar(string page)
    {
        foreach (var btn in new[] { BtnHome, BtnStrategies, BtnSpeed, BtnCloud, BtnTelegram, BtnStats, BtnGithub, BtnSettings })
        {
            var classes = btn.Classes;
            if (classes.Contains("is-active"))
                classes.Remove("is-active");
        }

        var active = page switch
        {
            "home" => BtnHome,
            "strategies" => BtnStrategies,
            "speed" => BtnSpeed,
            "cloud" => BtnCloud,
            "telegram" => BtnTelegram,
            "stats" => BtnStats,
            "settings" => BtnSettings,
            _ => BtnHome
        };

        active.Classes.Add("is-active");
    }

    /// <summary>Тема и шрифт применяются сразу: это и есть смена оформления без перезапуска.</summary>
    private void ApplyThemeAndFont()
    {
        if (Application.Current is { } app)
            app.RequestedThemeVariant = _ctx.Settings.Theme == "light" ? ThemeVariant.Light : ThemeVariant.Dark;

        var font = new FontFamily(_ctx.Settings.FontFamily);
        var size = (double)_ctx.Settings.FontSize;

        StatusLine.FontFamily = font;
        StatusLine.FontSize = size;

        ConsoleTab.ApplyFont();
    }

    private void SetStatus(string text, IBrush color)
    {
        StatusLine.Text = text;
        StatusLine.Foreground = color;
    }

    public void OnDeviceSelected(string? serial)
    {
        if ((_ctx.Serial ?? "") == (serial ?? ""))
            return;

        _ctx.Serial = serial;

        ConsoleTab.OnDeviceChanged();
        AppsTab.OnDeviceChanged();
        CardsTab.OnDeviceChanged();

        if (string.IsNullOrEmpty(serial))
        {
            SetStatus("Не подключено", StatusErr);
            ConnectionTab.ShowNoDevice();
            return;
        }

        SetStatus($"Подключено: {serial}", StatusOk);
        _ = LoadDeviceInfoAsync();
    }

    /// <summary>Список устройств. Держим выбранным то же устройство, что и раньше.</summary>
    private async Task RefreshDevicesAsync()
    {
        if (_busy)
            return;

        _busy = true;
        var previous = _ctx.Serial;

        try
        {
            var (_, stdout, stderr) = await Task.Run(() =>
                new AdbClient(_ctx.AdbPath, null, 15).Run("devices", "-l"));

            var (devices, unauthorized) = DeviceParser.Parse(stdout);
            ConnectionTab.SetDevices(devices, unauthorized);

            if (devices.Count == 0)
            {
                OnDeviceSelected(null);
            }
            else
            {
                var keep = !string.IsNullOrEmpty(previous) && devices.Contains(previous) ? previous : devices[0];
                ConnectionTab.SelectDevice(keep);
                OnDeviceSelected(keep);
            }

            if (stderr.Trim().Length > 0 && devices.Count == 0)
                _ctx.Log(stderr.Trim());
        }
        catch (Exception ex)
        {
            _ctx.Log($"Не удалось обновить список устройств: {ex.Message}");
            SetStatus("adb недоступен", StatusErr);
        }
        finally
        {
            _busy = false;
        }
    }

    /// <summary>Модель, версия Android и память — одной командой, как в Python-версии.</summary>
    private async Task LoadDeviceInfoAsync()
    {
        var serial = _ctx.Serial;
        if (string.IsNullOrEmpty(serial))
            return;

        const string cmd =
            "echo M=$(getprop ro.product.model); " +
            "echo R=$(getprop ro.build.version.release); " +
            "echo S=$(getprop ro.build.version.sdk); " +
            "echo T=$(grep MemTotal /proc/meminfo | tr -s ' ' | cut -d' ' -f2); " +
            "echo A=$(grep MemAvailable /proc/meminfo | tr -s ' ' | cut -d' ' -f2)";

        var (_, stdout, _) = await Task.Run(() => new AdbClient(_ctx.AdbPath, serial, 20).Shell(cmd, 20));

        var values = new Dictionary<string, string>(StringComparer.Ordinal);

        foreach (var line in stdout.Split('\n'))
        {
            var idx = line.IndexOf('=');
            if (idx > 0)
                values[line[..idx].Trim()] = line[(idx + 1)..].Trim();
        }

        if (values.Count == 0)
        {
            SetStatus($"Подключено: {serial} (нет ответа)", StatusWarn);
            ConnectionTab.ShowNoDevice();
            return;
        }

        values.TryGetValue("M", out var model);
        values.TryGetValue("R", out var release);
        values.TryGetValue("S", out var sdk);

        var total = Num.FloorDiv(Num.Parse(values.GetValueOrDefault("T")), 1024);
        var free = Num.FloorDiv(Num.Parse(values.GetValueOrDefault("A")), 1024);

        SetStatus($"{model} · Android {release} (SDK {sdk}) · RAM {total - free} из {total} МБ", StatusOk);
        ConnectionTab.ShowDevice(model ?? "?", release ?? "?", sdk ?? "?", total, free);
    }
}
