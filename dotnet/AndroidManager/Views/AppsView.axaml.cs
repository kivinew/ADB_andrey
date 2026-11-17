using AndroidManager.Core.Adb;
using AndroidManager.Core.Parsing;
using AndroidManager.Core.Settings;
using AndroidManager.Services;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Interactivity;
using Avalonia.VisualTree;

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

        var menu = new ContextMenu();
        menu.Opening += (_, _) => BuildContextMenu(menu);
        PkgList.ContextMenu = menu;

        // ПКМ по строке выбирает её до открытия меню, иначе действие уйдёт на чужие пакеты.
        PkgList.AddHandler(InputElement.PointerPressedEvent, OnPkgPointerPressed, RoutingStrategies.Bubble, handledEventsToo: true);
    }

    private List<string> SelectedPackages() => PkgList.SelectedItems?.Cast<string>().ToList() ?? new List<string>();

    /// <summary>ПКМ-меню как в Python: кнопки панели «Приложения», копирование и запуск одного пакета.</summary>
    private void BuildContextMenu(ContextMenu menu)
    {
        menu.Items.Clear();

        foreach (var item in CustomBars.Items(Ctx, CustomBars.PanelApps))
        {
            var bar = item;
            var mi = new MenuItem { Header = bar.Name };
            mi.Click += (_, _) => CustomBars.RunForPackages(Ctx, bar, SelectedPackages(), TopLevel.GetTopLevel(this));
            menu.Items.Add(mi);
        }

        menu.Items.Add(new Separator());

        var copy = new MenuItem { Header = "Копировать название пакета" };
        copy.Click += (_, _) => _ = CopyPackagesAsync();
        menu.Items.Add(copy);

        var selected = SelectedPackages();
        if (selected.Count == 1)
        {
            var pkg = selected[0];
            var add = new MenuItem { Header = $"Добавить кнопку: {pkg}" };
            add.Click += (_, _) => AddLaunchButton(pkg);
            menu.Items.Add(add);
        }
    }

    private void OnPkgPointerPressed(object? sender, PointerPressedEventArgs e)
    {
        if (!e.GetCurrentPoint(PkgList).Properties.IsRightButtonPressed)
            return;

        var item = (e.Source as Visual)?.FindAncestorOfType<ListBoxItem>();
        var pkg = item?.DataContext as string ?? item?.Content as string;
        if (pkg is null)
            return;

        var selected = SelectedPackages();
        if (selected.Contains(pkg))
            return;

        PkgList.SelectedItems?.Clear();
        PkgList.SelectedItems?.Add(pkg);
    }

    /// <summary>Создаёт кнопку запуска для конкретного пакета прямо из ПКМ-меню.</summary>
    private void AddLaunchButton(string pkg)
    {
        CustomBars.Items(Ctx, CustomBars.PanelApps).Add(new BarItem
        {
            Name = $"Запуск: {pkg}",
            Cmd = $"monkey -p {pkg} -c android.intent.category.LAUNCHER 1",
            Type = "shell",
        });

        Ctx.SaveSettings();
        RefreshCustomBar();
        Ctx.Log($"Добавлена кнопка запуска для {pkg}");
    }

    private async Task CopyPackagesAsync()
    {
        var selected = SelectedPackages();
        if (selected.Count == 0)
            return;

        var top = TopLevel.GetTopLevel(this);
        if (top?.Clipboard is { } clip)
            await clip.SetTextAsync(string.Join("\n", selected));
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

        CustomBars.Render(Ctx, CustomBars.PanelApps, CustomBar, TopLevel.GetTopLevel(this), RefreshCustomBar,
            item => CustomBars.RunForPackages(Ctx, item, SelectedPackages(), TopLevel.GetTopLevel(this)));
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