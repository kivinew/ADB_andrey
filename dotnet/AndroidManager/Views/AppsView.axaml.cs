using AndroidManager.Core.Adb;
using AndroidManager.Core.Parsing;
using AndroidManager.Core.Settings;
using AndroidManager.Services;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Interactivity;
using Avalonia.Platform.Storage;
using Avalonia.VisualTree;
using System.Diagnostics;

namespace AndroidManager.Views;

public partial class AppsView : UserControl
{
    private List<string> _packages = new();

    // Папка apk рядом с exe — та же схема, что в Python-версии (paths.BASE/apk).
    private static string ApkDir => Path.Combine(AppContext.BaseDirectory, "apk");

    public AppState Ctx { get; set; } = null!;

    public AppsView()
    {
        InitializeComponent();

        ScopeBox.ItemsSource = new[] { "Все", "Пользовательские", "Системные" };
        ScopeBox.SelectedIndex = 0;

        RefreshBtn.Click += (_, _) => _ = RefreshAsync();
        FilterBox.TextChanged += (_, _) => ApplyFilter();
        Loaded += (_, _) => { RefreshCustomBar(); ReloadApks(); };

        AddApkBtn.Click += (_, _) => _ = AddApkAsync();
        InstallApkBtn.Click += (_, _) => _ = InstallApkAsync();
        OpenApkFolderBtn.Click += (_, _) => OpenApkFolder();

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

    /// <summary>Перечитывает папку apk: только *.apk, по алфавиту.</summary>
    private void ReloadApks()
    {
        var current = ApkBox.SelectedItem as string;

        Directory.CreateDirectory(ApkDir);
        var files = Directory.GetFiles(ApkDir, "*.apk", SearchOption.TopDirectoryOnly)
            .Select(Path.GetFileName)
            .OrderBy(n => n, StringComparer.OrdinalIgnoreCase)
            .ToList();

        ApkBox.ItemsSource = files;
        InstallApkBtn.IsEnabled = files.Count > 0;

        if (current is not null && files.Contains(current))
            ApkBox.SelectedItem = current;
        else if (files.Count > 0)
            ApkBox.SelectedIndex = 0;
    }

    /// <summary>Выбор APK в проводнике и копирование в папку apk.</summary>
    private async Task AddApkAsync()
    {
        var top = TopLevel.GetTopLevel(this);
        if (top is null)
            return;

        var files = await top.StorageProvider.OpenFilePickerAsync(new FilePickerOpenOptions
        {
            Title = "Выберите APK для добавления",
            AllowMultiple = true,
            FileTypeFilter =
            [
                new FilePickerFileType("Android-приложения") { Patterns = ["*.apk"] },
            ],
        });

        foreach (var file in files)
        {
            var src = file.TryGetLocalPath();
            if (src is null)
                continue;

            var name = Path.GetFileName(src);
            var dst = Path.Combine(ApkDir, name);

            try
            {
                Directory.CreateDirectory(ApkDir);

                // Не перезаписываем молча: у второго файла добавляем «(2)».
                var target = dst;
                var n = 2;
                while (File.Exists(target) && !(src == target))
                {
                    target = Path.Combine(ApkDir,
                        $"{Path.GetFileNameWithoutExtension(name)} ({n++}){Path.GetExtension(name)}");
                }

                File.Copy(src, target, overwrite: false);
                Ctx.Log($"APK добавлен в папку apk: {Path.GetFileName(target)}");
                ApkBox.SelectedItem = Path.GetFileName(target);
            }
            catch (Exception ex)
            {
                Ctx.Log($"Не удалось скопировать {name}: {ex.Message}");
            }
        }

        ReloadApks();
    }

    /// <summary>Установка выбранного APK: adb install -r.</summary>
    private async Task InstallApkAsync()
    {
        var name = ApkBox.SelectedItem as string;
        var serial = Ctx.Serial;

        if (string.IsNullOrEmpty(serial))
        {
            Ctx.Log("Сначала подключите устройство");
            return;
        }

        if (string.IsNullOrEmpty(name))
        {
            Ctx.Log("Выберите APK");
            return;
        }

        var path = Path.Combine(ApkDir, name);
        if (!File.Exists(path))
        {
            Ctx.Log($"APK не найден: {path}");
            ReloadApks();
            return;
        }

        Ctx.Log($"Установка {name}...");
        InstallApkBtn.IsEnabled = false;

        try
        {
            // -r — переустановить с сохранением данных; -d — разрешить понижение версии.
            var (rc, stdout, stderr) = await Task.Run(() =>
                new AdbClient(Ctx.AdbPath, serial, 300).Run(["install", "-r", path]));

            var answer = (stdout + stderr).Trim();
            Ctx.Log(answer.Length > 0 ? answer : $"Установка {name}: код {rc}");

            if (rc == 0 && answer.Contains("Success", StringComparison.Ordinal))
            {
                Ctx.Log($"Установлено: {name}");
                await RefreshAsync();
            }
            else
            {
                Ctx.Log($"Не удалось установить {name}");
            }
        }
        catch (Exception ex)
        {
            Ctx.Log($"Ошибка установки {name}: {ex.Message}");
        }
        finally
        {
            InstallApkBtn.IsEnabled = true;
        }
    }

    private void OpenApkFolder()
    {
        try
        {
            Directory.CreateDirectory(ApkDir);

            // explorer.exe с аргументами и UseShellExecute=true работает из GUI-процесса.
            // FileName = path с UseShellExecute=true — не открывает окно.
            Process.Start(new ProcessStartInfo
            {
                FileName = "explorer.exe",
                Arguments = ApkDir,
                UseShellExecute = true,
            });
        }
        catch (Exception ex)
        {
            Ctx.Log($"Не удалось открыть папку apk: {ex.Message}");
        }
    }

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
            Ctx.Log($"Пакетов: {_packages.Count}");

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

        Ctx.Log($"Выполняется: {template} — приложений {selected.Count}...");
        var done = 0;

        foreach (var pkg in selected)
        {
            var command = template.Replace("{pkg}", pkg, StringComparison.Ordinal);

            var (_, stdout, stderr) = await Task.Run(() =>
                new AdbClient(Ctx.AdbPath, Ctx.Serial, 60).Shell(command, 60));

            var answer = (stdout + stderr).Trim();

            if (answer.Length > 0)
                Ctx.Log($"{pkg}: {answer}");

            done++;
        }

        if (selected.Count > 1)
            Ctx.Log($"Готово: обработка {done} приложений");
    }
}