using AndroidManager.Services;
using Avalonia.Controls;
using System.Globalization;

namespace AndroidManager.Views;

public partial class SettingsView : UserControl
{
    private bool _loading;

    public AppState Ctx { get; set; } = null!;

    /// <summary>Настройки сохранены — главное окно переприменяет тему и шрифт.</summary>
    public event Action? SettingsChanged;

    public SettingsView()
    {
        InitializeComponent();

        ThemeBox.ItemsSource = new[] { "Тёмная", "Светлая" };
        FontBox.ItemsSource = new[]
        {
            "Segoe UI", "Cascadia Mono", "Consolas", "Courier New", "Inter", "Arial",
        };

        Loaded += (_, _) => Load();
        SaveBtn.Click += (_, _) => Save();
    }

    private void Load()
    {
        _loading = true;

        try
        {
            var s = Ctx.Settings;

            ThemeBox.SelectedIndex = s.Theme == "light" ? 1 : 0;

            var fonts = FontBox.ItemsSource as string[] ?? Array.Empty<string>();
            var index = Array.IndexOf(fonts, s.FontFamily);
            FontBox.SelectedIndex = index >= 0 ? index : 0;

            FontSizeBox.Text = s.FontSize.ToString(CultureInfo.InvariantCulture);
            ConsoleFontBox.Text = s.ConsoleFontSize.ToString(CultureInfo.InvariantCulture);
            HistoryBox.Text = s.ConsoleHistoryLimit.ToString(CultureInfo.InvariantCulture);
            AutoRefreshBox.Text = s.AutoRefreshPackages.ToString(CultureInfo.InvariantCulture);

            ConfirmBox.IsChecked = s.ConfirmDangerous;
            PcIpBox.Text = s.PcIp;
            VysorBox.Text = s.VysorPath;
            PathLabel.Text = $"Файл настроек: {Ctx.SettingsPath}";
        }
        finally
        {
            _loading = false;
        }
    }

    private void Save()
    {
        if (_loading)
            return;

        var s = Ctx.Settings;

        s.Theme = ThemeBox.SelectedIndex == 1 ? "light" : "dark";
        s.FontFamily = (FontBox.SelectedItem as string) ?? "Segoe UI";
        s.FontSize = ReadInt(FontSizeBox, s.FontSize, 8, 20);
        s.ConsoleFontSize = ReadInt(ConsoleFontBox, s.ConsoleFontSize, 8, 20);
        s.ConsoleHistoryLimit = ReadInt(HistoryBox, s.ConsoleHistoryLimit, 50, 5000);
        s.AutoRefreshPackages = ReadInt(AutoRefreshBox, s.AutoRefreshPackages, 0, 300);
        s.ConfirmDangerous = ConfirmBox.IsChecked == true;
        s.PcIp = PcIpBox.Text?.Trim() ?? "";
        s.VysorPath = VysorBox.Text?.Trim() ?? "";

        Ctx.SaveSettings();
        Ctx.Log("Настройки сохранены");
        SettingsChanged?.Invoke();
    }

    private static int ReadInt(TextBox box, int fallback, int min, int max)
    {
        if (!int.TryParse(box.Text?.Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out var value))
            return fallback;

        return Math.Clamp(value, min, max);
    }
}