using AndroidManager.Core.Adb;
using AndroidManager.Core.Parsing;
using AndroidManager.Services;
using Avalonia.Controls;

namespace AndroidManager.Views;

public partial class AppsView : UserControl
{
    private List<string> _packages = new();

    public AppState Ctx { get; set; } = null!;

    public AppsView()
    {
        InitializeComponent();

        ScopeBox.ItemsSource = new[] { "Все", "Пользовательские", "Системные" };
        ScopeBox.SelectedIndex = 0;

        RefreshBtn.Click += (_, _) => _ = RefreshAsync();
        FilterBox.TextChanged += (_, _) => ApplyFilter();
        Loaded += (_, _) => RefreshCustomBar();

        RunBtn.Click += (_, _) => _ = ActAsync("monkey -p {pkg} -c android.intent.category.LAUNCHER 1", null);
        StopBtn.Click += (_, _) => _ = ActAsync("am force-stop {pkg}", null);
        ClearBtn.Click += (_, _) => _ = ActAsync("pm clear {pkg}", "Очистить данные и кэш");
        DisableBtn.Click += (_, _) => _ = ActAsync("pm disable-user --user 0 {pkg}", "Отключить");
        EnableBtn.Click += (_, _) => _ = ActAsync("pm enable --user 0 {pkg}", null);
        UninstallBtn.Click += (_, _) => _ = ActAsync("pm uninstall -k --user 0 {pkg}", "Удалить");
    }

    public void OnDeviceChanged()
    {
        _packages = new();
        PkgList.ItemsSource = null;
        CountLabel.Text = "Приложения не загружены";
    }

    /// <summary>Перерисовывает кастомные кнопки панели «Приложения».</summary>
    public void RefreshCustomBar()
    {
        if (Ctx is null)
            return;

        var count = CustomBars.Render(Ctx, CustomBars.PanelApps, CustomBar, TopLevel.GetTopLevel(this));
        CustomBar.IsVisible = count > 0;
    }

    private async Task RefreshAsync()
    {
        var serial = Ctx.Serial ?? "";

        if (string.IsNullOrEmpty(serial))
        {
            CountLabel.Text = "Сначала подключите устройство";
            return;
        }

        RefreshBtn.IsEnabled = false;

        try
        {
            var scope = ScopeBox.SelectedIndex switch
            {
                1 => "-3",
                2 => "-s",
                _ => "",
            };

            var args = scope.Length == 0
                ? new[] { "shell", "pm", "list", "packages" }
                : new[] { "shell", "pm", "list", "packages", scope };

            var (_, stdout, stderr) = await Task.Run(() => new AdbClient(Ctx.AdbPath, serial, 60).Run(args));

            _packages = SystemInfoParser.ParsePkgs(stdout);

            if (_packages.Count == 0)
                CountLabel.Text = stderr.Trim().Length > 0 ? stderr.Trim() : "Приложения не найдены";
            else
                ApplyFilter();
        }
        catch (Exception ex)
        {
            Ctx.Log($"Не удалось получить список приложений: {ex.Message}");
        }
        finally
        {
            RefreshBtn.IsEnabled = true;
        }
    }

    private void ApplyFilter()
    {
        var query = FilterBox.Text?.Trim() ?? "";
        var filtered = query.Length == 0
            ? _packages
            : _packages.FindAll(p => p.Contains(query, StringComparison.OrdinalIgnoreCase));

        PkgList.ItemsSource = filtered;

        CountLabel.Text = filtered.Count == _packages.Count
            ? $"Пакетов: {_packages.Count}"
            : $"Показано {filtered.Count} из {_packages.Count}";
    }

    private async Task ActAsync(string template, string? question)
    {
        var selected = PkgList.SelectedItems?.Cast<string>().ToList() ?? new List<string>();

        if (selected.Count == 0)
        {
            Ctx.Log("Выберите хотя бы одно приложение");
            return;
        }

        if (question is not null && Ctx.Settings.ConfirmDangerous)
        {
            var confirmed = await UiDialogs.Confirm(
                TopLevel.GetTopLevel(this) as Window,
                question,
                $"{question} у {selected.Count} приложений?");

            if (!confirmed)
                return;
        }

        foreach (var pkg in selected)
        {
            var command = template.Replace("{pkg}", pkg, StringComparison.Ordinal);

            var (_, stdout, stderr) = await Task.Run(() =>
                new AdbClient(Ctx.AdbPath, Ctx.Serial, 60).Shell(command, 60));

            var answer = (stdout + stderr).Trim();

            if (answer.Length > 0)
                Ctx.Log($"{pkg}: {answer}");
        }
    }
}