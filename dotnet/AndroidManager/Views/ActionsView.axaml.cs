using AndroidManager.Core.Adb;
using AndroidManager.Core.Parsing;
using AndroidManager.Core.Settings;
using AndroidManager.Services;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Threading;
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
using System.Threading.Tasks;

namespace AndroidManager.Views;

public partial class ActionsView : UserControl
{
    private const string ScrcpyExeName = "scrcpy";
    private const string VysorPathSetting = "vysor_path";

    private static readonly string[] KeyNames =
    {
        "Домой (3)", "Назад (4)", "Меню (82)", "Поиск (84)", "Камера (27)",
        "Кач. вверх (24)", "Кач. вниз (25)", "Вкл/выкл (26)", "Отбой (6)", "Звонок (5)",
    };
    private static readonly int[] KeyCodes = { 3, 4, 82, 84, 27, 24, 25, 26, 26, 6 };

    public AppState Ctx { get; set; } = null!;

    public ActionsView()
    {
        InitializeComponent();

        ScCodec.SelectedIndex = 0;

        foreach (var kn in KeyNames)
        {
            var idx = Array.IndexOf(KeyNames, kn);
            KeyBox.Items.Add(new KeyItem { Name = kn, Code = KeyCodes[idx] });
        }
        KeyBox.SelectedIndex = 0;

        BtnScStart.Click += (_, _) => StartScrcpy();
        BtnVysorSelect.Click += (_, _) => SelectVysor();
        BtnVysorStart.Click += (_, _) => StartVysor();
        BtnScreenshot.Click += (_, _) => TakeScreenshot();
        BtnReboot.Click += (_, _) => Reboot("");
        BtnRebootRecovery.Click += (_, _) => Reboot("recovery");
        BtnRebootBootloader.Click += (_, _) => Reboot("bootloader");
        BtnKey.Click += (_, _) => SendKey();

        // ПКМ-меню для редактирования команд кнопок
        BtnScStart.ContextMenu = CreateButtonEditMenu("BtnScStart", "Запустить scrcpy", "scrcpy --video-codec h264");
        BtnVysorStart.ContextMenu = CreateButtonEditMenu("BtnVysorStart", "Запустить Vysor", "");
        BtnScreenshot.ContextMenu = CreateButtonEditMenu("BtnScreenshot", "Скриншот", "screencap -p /sdcard/screen.png && pull /sdcard/screen.png screenshots/screen_{date}.png");
        BtnReboot.ContextMenu = CreateButtonEditMenu("BtnReboot", "Перезагрузка", "reboot");
        BtnRebootRecovery.ContextMenu = CreateButtonEditMenu("BtnRebootRecovery", "Recovery", "reboot recovery");
        BtnRebootBootloader.ContextMenu = CreateButtonEditMenu("BtnRebootBootloader", "Bootloader", "reboot bootloader");
        BtnKey.ContextMenu = CreateButtonEditMenu("BtnKey", "Отправить клавишу", "input keyevent {code}");

        BtnScreenRefresh.Click += (_, _) => _ = RefreshScreenInfoAsync();
        BtnScreenApply.Click += (_, _) => _ = ApplyScreenAsync();
        BtnScreenResetSize.Click += (_, _) => _ = ResetScreenAsync(false);
        BtnScreenResetDpi.Click += (_, _) => _ = ResetScreenAsync(true);
        Preset720.Click += (_, _) => ResBox.Text = "1280x720";
        Preset1080.Click += (_, _) => ResBox.Text = "1920x1080";
        Preset2160.Click += (_, _) => ResBox.Text = "3840x2160";

        Loaded += (_, _) => { LoadVysorPath(); ReloadPrograms(); RefreshCustomBar(); _ = RefreshScreenInfoAsync(); };
    }

    /// <summary>Перерисовывает кастомные кнопки панели «Действия».</summary>
    public void RefreshCustomBar()
    {
        if (Ctx is null)
            return;

        CustomBars.Render(Ctx, CustomBars.PanelTools, CustomBar, TopLevel.GetTopLevel(this), RefreshCustomBar);
    }

    private class KeyItem
    {
        public string Name { get; set; } = "";
        public int Code { get; set; }
        public override string ToString() => Name;
    }

    private class ProgramJson
    {
        [JsonPropertyName("name")] public string Name { get; set; } = "";
        [JsonPropertyName("file")] public string File { get; set; } = "";
        [JsonPropertyName("args")] public string Args { get; set; } = "";
    }

    public void RefreshActions()
    {
        ReloadPrograms();
    }

    private void LoadVysorPath()
    {
        if (Ctx.Settings.GetType().GetProperty(VysorPathSetting) is { } prop)
        {
            var path = prop.GetValue(Ctx.Settings) as string ?? "";
            VysorPathText.Text = string.IsNullOrEmpty(path) ? "не задан" : path;
        }
    }

    private void SelectVysor()
    {
        // File picker would be ideal; for now log that user should set path in settings.
        Ctx.Log("Путь к Vysor настраивается в разделе Настройки");
    }

    private void StartVysor()
    {
        var path = Ctx.Settings.VysorPath;
        if (string.IsNullOrEmpty(path) || !File.Exists(path))
        {
            Ctx.Log("Путь к Vysor не задан или файл не найден. Укажите в Настройках.");
            return;
        }

        try
        {
            // Если пользователь задал свою команду для Vysor — используем её
            if (!string.IsNullOrEmpty(Ctx.Settings.ButtonCommands.VysorCmd))
            {
                var customCmd = Ctx.Settings.ButtonCommands.VysorCmd
                    .Replace("{vysor}", path)
                    .Replace("{serial}", Ctx.Serial ?? "");

                Process.Start(new ProcessStartInfo
                {
                    FileName = "cmd.exe",
                    Arguments = $"/c {customCmd}",
                    UseShellExecute = false,
                    CreateNoWindow = true,
                });
                Ctx.Log($"Vysor (custom) запущен: {customCmd}");
            }
            else
            {
                Process.Start(new ProcessStartInfo
                {
                    FileName = path,
                    UseShellExecute = true,
                    CreateNoWindow = true,
                });
                Ctx.Log("Vysor запущен");
            }
        }
        catch (Exception ex)
        {
            Ctx.Log($"Не удалось запустить Vysor: {ex.Message}");
        }
    }

    private void StartScrcpy()
    {
        var serial = Ctx.Serial;
        if (string.IsNullOrEmpty(serial))
        {
            Ctx.Log("Сначала подключите устройство");
            return;
        }

        var scrcpyPath = FindScrcpyPath();
        if (string.IsNullOrEmpty(scrcpyPath))
        {
            var local = System.IO.Path.Combine(Paths.Base, "tools", ScrcpyExeName, ScrcpyExeName + ".exe");
            Ctx.Log($"scrcpy не найден. Положите scrcpy.exe в: {local} или добавьте в PATH. Текущая папка программы: {Paths.Base}");
            return;
        }

        // Ищем adb: сначала рядом с программой, потом в PATH. Без этого scrcpy не найдёт adb.
        var adbPath = FindAdbPath();
        Ctx.Log($"scrcpy: {scrcpyPath}");
        Ctx.Log($"adb: {adbPath}");

        var args = new List<string> { "-s", serial, "--video-codec", ScCodec.SelectedItem as string ?? "h264" };

        if (!string.IsNullOrWhiteSpace(ScMax.Text) && int.TryParse(ScMax.Text, out var ms) && ms > 0)
            args.AddRange(["--max-size", ScMax.Text]);
        if (!string.IsNullOrWhiteSpace(ScFps.Text) && int.TryParse(ScFps.Text, out var fps))
            args.AddRange(["--max-fps", ScFps.Text]);
        if (!string.IsNullOrWhiteSpace(ScBr.Text))
            args.AddRange(["--video-bit-rate", ScBr.Text]);
        if (ScTouch.IsChecked == true) args.Add("--show-touches");
        if (ScAwake.IsChecked == true) args.Add("--stay-awake");
        if (ScOff.IsChecked == true) args.Add("--turn-screen-off");

        // scrcpy-server — JAR-файл, который scrcpy отправляет на устройство.
        // Без него scrcpy падает: "scrcpy-server does not exist or is not a regular file".
        // Если его нет рядом со scrcpy.exe — пробуем скопировать из Android-manager.
        var serverPath = Path.Combine(Path.GetDirectoryName(scrcpyPath) ?? "", "scrcpy-server");
        if (!File.Exists(serverPath))
        {
            var candidates = new[]
            {
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Android-manager", "tools", "scrcpy", "scrcpy-server"),
                Path.Combine(Paths.Base, "..", "..", "..", "..", "..", "Android-manager", "tools", "scrcpy", "scrcpy-server"),
            };
            foreach (var c in candidates)
            {
                if (File.Exists(c))
                {
                    try { File.Copy(c, serverPath, true); Ctx.Log($"scrcpy-server скопирован из {c}"); }
                    catch (Exception ex) { Ctx.Log($"Не удалось скопировать scrcpy-server: {ex.Message}"); }
                    break;
                }
            }
        }

        var scrcpyDir = Path.GetDirectoryName(scrcpyPath) ?? "";

        try
        {
            // Если пользователь задал свою команду — используем её, иначе стандартную
            if (!string.IsNullOrEmpty(Ctx.Settings.ButtonCommands.ScrcpyCmd))
            {
                var customCmd = Ctx.Settings.ButtonCommands.ScrcpyCmd
                    .Replace("{serial}", serial)
                    .Replace("{scrcpy}", scrcpyPath)
                    .Replace("{adb}", adbPath);

                var psi = new ProcessStartInfo
                {
                    FileName = "cmd.exe",
                    Arguments = $"/c {customCmd}",
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                };
                psi.Environment["ADB"] = adbPath;
                psi.Environment["PATH"] = scrcpyDir + Path.PathSeparator + (psi.Environment["PATH"] ?? "");

                using var proc = Process.Start(psi);
                proc?.WaitForExit(30000);
                var output = proc?.StandardOutput.ReadToEnd() ?? "";
                var error = proc?.StandardError.ReadToEnd() ?? "";

                if (!string.IsNullOrEmpty(output.Trim()))
                    Ctx.Log($"scrcpy (custom): {output.Trim()}");
                if (!string.IsNullOrEmpty(error.Trim()))
                    Ctx.Log($"scrcpy (custom) error: {error.Trim()}");

                Ctx.Log("scrcpy (custom) запущен");
            }
            else
            {
                // Запускаем как GUI-процесс (как в Python-версии): без перехвата вывода.
                // scrcpy — оконное приложение, оно не завершается до закрытия окна.
                var psi = new ProcessStartInfo
                {
                    FileName = scrcpyPath,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                };
                foreach (var a in args) psi.ArgumentList.Add(a);
                // scrcpy ищет adb через переменную окружения ADB — передаём путь, как в Python-версии.
                psi.Environment["ADB"] = adbPath;
                psi.Environment["PATH"] = scrcpyDir + Path.PathSeparator + (psi.Environment["PATH"] ?? "");

                var proc = Process.Start(psi);
                if (proc is null)
                    throw new InvalidOperationException("scrcpy не запустился");

                // Отслеживаем выход: если scrcpy сразу упал — увидим код и сообщение.
                proc.EnableRaisingEvents = true;
                proc.Exited += (_, _) =>
                {
                    var code = proc.ExitCode;
                    Ctx.Log($"scrcpy завершился (код {code})");
                };

                Ctx.Log($"scrcpy запущен (PID {proc.Id})");
            }
        }
        catch (Exception ex)
        {
            Ctx.Log($"Не удалось запустить scrcpy: {ex.Message}");
        }
    }

    private string FindAdbPath()
    {
        var local = System.IO.Path.Combine(Paths.Base, "tools", "adb", "adb.exe");
        if (File.Exists(local))
            return local;

        // Ищем в PATH
        var pathEnv = Environment.GetEnvironmentVariable("PATH");
        if (pathEnv != null)
        {
            foreach (var dir in pathEnv.Split(Path.PathSeparator))
            {
                if (string.IsNullOrEmpty(dir)) continue;
                var candidate = System.IO.Path.Combine(dir, "adb.exe");
                if (File.Exists(candidate))
                    return candidate;
            }
        }

        return "adb";
    }

    private string? FindScrcpyPath()
    {
        // 1) Рядом с программой: tools/scrcpy/scrcpy.exe (туда копирует установщик)
        var local = System.IO.Path.Combine(Paths.Base, "tools", ScrcpyExeName, ScrcpyExeName + ".exe");
        if (File.Exists(local))
            return local;

        // 2) Ищем в PATH, как Python shutil.which — на случай, если scrcpy установлен глобально
        var pathEnv = Environment.GetEnvironmentVariable("PATH");
        if (pathEnv != null)
        {
            foreach (var dir in pathEnv.Split(Path.PathSeparator))
            {
                if (string.IsNullOrEmpty(dir)) continue;
                var candidate = System.IO.Path.Combine(dir, ScrcpyExeName + ".exe");
                if (File.Exists(candidate))
                    return candidate;
            }
        }

        return null;
    }

    private async void TakeScreenshot()
    {
        var serial = Ctx.Serial;
        if (string.IsNullOrEmpty(serial))
        {
            Ctx.Log("Сначала подключите устройство");
            return;
        }

        var dir = Path.Combine(Paths.Base, "screenshots");
        Directory.CreateDirectory(dir);
        var path = Path.Combine(dir, $"screen_{DateTime.Now:yyyyMMdd_HHmmss}.png");

        try
        {
            // Если пользователь задал свою команду — используем её
            if (!string.IsNullOrEmpty(Ctx.Settings.ButtonCommands.ScreenshotCmd))
            {
                var customCmd = Ctx.Settings.ButtonCommands.ScreenshotCmd
                    .Replace("{serial}", serial)
                    .Replace("{path}", path)
                    .Replace("{dir}", dir)
                    .Replace("{date}", DateTime.Now.ToString("yyyyMMdd_HHmmss"));

                var client = new AdbClient(Ctx.AdbPath, serial, 30);
                var (rc, output, err) = client.Shell(customCmd, 30);

                if (rc == 0 && !string.IsNullOrEmpty(output.Trim()))
                    Ctx.Log($"Скриншот (custom): {output.Trim()}");
                else if (rc != 0)
                    Ctx.Log($"Ошибка скриншота (custom): {err.Trim()}");

                // Пытаемся скопировать результат, если указан путь
                if (customCmd.Contains("screencap") && !customCmd.Contains("screenshots/"))
                {
                    var (rc2, _, err2) = client.Run("pull", "/sdcard/screen_tmp.png", path);
                    if (rc2 == 0)
                        Ctx.Log($"Скриншот: {path}");
                    else if (rc2 != 0 && !string.IsNullOrEmpty(err2.Trim()))
                        Ctx.Log($"Ошибка pull: {err2.Trim()}");
                }
            }
            else
            {
                // Сначала делаем screencap на устройство, потом подтягиваем pull
                var client = new AdbClient(Ctx.AdbPath, serial, 30);
                var (rc1, _, err1) = client.Shell($"screencap -p /sdcard/screen_tmp.png", 30);
                if (rc1 != 0)
                {
                    Ctx.Log($"Ошибка screencap: {err1.Trim()}");
                    return;
                }

                var (rc2, _, err2) = client.Run("pull", "/sdcard/screen_tmp.png", path);
                if (rc2 == 0)
                    Ctx.Log($"Скриншот: {path}");
                else
                    Ctx.Log($"Ошибка pull: {err2.Trim()}");
            }
        }
        catch (Exception ex)
        {
            Ctx.Log($"Ошибка скриншота: {ex.Message}");
        }
    }

    private async void Reboot(string mode)
    {
        var serial = Ctx.Serial;
        if (string.IsNullOrEmpty(serial))
        {
            Ctx.Log("Сначала подключите устройство");
            return;
        }

        var cmd = string.IsNullOrEmpty(mode) ? "reboot" : $"reboot {mode}";

        try
        {
            // Если пользователь задал свою команду для перезагрузки — используем её
            if (!string.IsNullOrEmpty(Ctx.Settings.ButtonCommands.RebootCmd) && string.IsNullOrEmpty(mode))
            {
                var customCmd = Ctx.Settings.ButtonCommands.RebootCmd.Replace("{serial}", serial);
                var (rc, _, err) = await Task.Run(() => new AdbClient(Ctx.AdbPath, serial, 30).Shell(customCmd, 30));
                if (rc == 0)
                    Ctx.Log($"Команда отправлена (custom): {customCmd}");
                else
                    Ctx.Log($"Ошибка {customCmd}: {err.Trim()}");
            }
            else
            {
                var (rc, _, err) = await Task.Run(() => new AdbClient(Ctx.AdbPath, serial, 30).Shell(cmd, 30));
                if (rc == 0)
                    Ctx.Log($"Команда отправлена: {cmd}");
                else
                    Ctx.Log($"Ошибка {cmd}: {err.Trim()}");
            }
        }
        catch (Exception ex)
        {
            Ctx.Log($"Ошибка {cmd}: {ex.Message}");
        }
    }

    private void SendKey()
    {
        var serial = Ctx.Serial;
        if (string.IsNullOrEmpty(serial))
        {
            Ctx.Log("Сначала подключите устройство");
            return;
        }

        if (KeyBox.SelectedItem is not KeyItem ki) return;

        _ = Task.Run(() =>
        {
            // Если пользователь задал свою команду для клавиш — используем её
            if (!string.IsNullOrEmpty(Ctx.Settings.ButtonCommands.KeyCmd))
            {
                var customCmd = Ctx.Settings.ButtonCommands.KeyCmd
                    .Replace("{serial}", serial)
                    .Replace("{code}", ki.Code.ToString());

                var (rc, _, err) = new AdbClient(Ctx.AdbPath, serial, 15).Shell(customCmd, 15);
                Dispatcher.UIThread.Post(() =>
                {
                    if (rc == 0)
                        Ctx.Log($"Клавиша отправлена (custom): {ki.Name}");
                    else
                        Ctx.Log($"Ошибка клавиши (custom): {err.Trim()}");
                });
            }
            else
            {
                var (rc, _, err) = new AdbClient(Ctx.AdbPath, serial, 15).Shell($"input keyevent {ki.Code}", 15);
                Dispatcher.UIThread.Post(() =>
                {
                    if (rc == 0)
                        Ctx.Log($"Клавиша отправлена: {ki.Name}");
                    else
                        Ctx.Log($"Ошибка клавиши: {err.Trim()}");
                });
            }
        });
    }

    /// <summary>Создаёт контекстное меню (ПКМ) для кнопок интерфейса: Редактировать / Удалить.</summary>
    private ContextMenu CreateButtonEditMenu(string buttonId, string displayName, string defaultCmd)
    {
        var menu = new ContextMenu();
        var editItem = new MenuItem { Header = "Редактировать" };
        var deleteItem = new MenuItem { Header = "Удалить" };

        editItem.Click += (_, _) => EditButtonCommand(buttonId, displayName, defaultCmd);
        deleteItem.Click += (_, _) => DeleteButton(buttonId);

        menu.Items.Add(editItem);
        menu.Items.Add(deleteItem);
        return menu;
    }

    private void EditButtonCommand(string buttonId, string displayName, string defaultCmd)
    {
        var currentCmd = GetButtonCommand(buttonId, defaultCmd);

        var win = new Window
        {
            Title = $"Редактировать кнопку: {displayName}",
            Width = 500,
            Height = 300,
            CanResize = false,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
        };

        var cmdBox = new TextBox
        {
            Text = currentCmd,
            Margin = new Thickness(24, 8, 24, 8),
            Height = 80,
            TextWrapping = TextWrapping.Wrap,
            AcceptsReturn = true,
        };

        var hint = new TextBlock
        {
            Text = "shell — команда на устройстве (adb shell ...)\npc — команда на ПК\nДоступно: {serial}, {ip}, {port}",
            FontSize = 10,
            Foreground = new SolidColorBrush(Color.Parse("#7B84A0")),
            TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(24, 0, 24, 8),
        };

        var saveBtn = new Button { Content = "Сохранить", MinWidth = 100 };
        var cancelBtn = new Button { Content = "Отмена", MinWidth = 100 };

        var btnBar = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 8,
            HorizontalAlignment = HorizontalAlignment.Right,
            Margin = new Thickness(24, 0, 24, 16),
        };
        btnBar.Children.Add(cancelBtn);
        btnBar.Children.Add(saveBtn);

        var root = new StackPanel { Spacing = 6, Margin = new Thickness(24) };
        root.Children.Add(new TextBlock { Text = "Команда" });
        root.Children.Add(cmdBox);
        root.Children.Add(hint);
        root.Children.Add(btnBar);
        win.Content = root;

        saveBtn.Click += (_, _) =>
        {
            var newCmd = cmdBox.Text?.Trim() ?? "";
            SaveButtonCommand(buttonId, newCmd);
            win.Close();
            Ctx.Log($"Команда кнопки «{displayName}» изменена");
        };

        cancelBtn.Click += (_, _) => win.Close();

        if (TopLevel.GetTopLevel(this) is Window owner)
            win.ShowDialog(owner);
        else
            win.Show();
    }

    private string GetButtonCommand(string buttonId, string defaultCmd)
    {
        return buttonId switch
        {
            "BtnScStart" => Ctx.Settings.ButtonCommands.ScrcpyCmd ?? defaultCmd,
            "BtnVysorStart" => Ctx.Settings.ButtonCommands.VysorCmd ?? defaultCmd,
            "BtnScreenshot" => Ctx.Settings.ButtonCommands.ScreenshotCmd ?? defaultCmd,
            "BtnReboot" => Ctx.Settings.ButtonCommands.RebootCmd ?? defaultCmd,
            "BtnKey" => Ctx.Settings.ButtonCommands.KeyCmd ?? defaultCmd,
            _ => defaultCmd,
        };
    }

    private void SaveButtonCommand(string buttonId, string cmd)
    {
        switch (buttonId)
        {
            case "BtnScStart": Ctx.Settings.ButtonCommands.ScrcpyCmd = cmd; break;
            case "BtnVysorStart": Ctx.Settings.ButtonCommands.VysorCmd = cmd; break;
            case "BtnScreenshot": Ctx.Settings.ButtonCommands.ScreenshotCmd = cmd; break;
            case "BtnReboot": Ctx.Settings.ButtonCommands.RebootCmd = cmd; break;
            case "BtnKey": Ctx.Settings.ButtonCommands.KeyCmd = cmd; break;
        }
        Ctx.SaveSettings();
    }

    private void DeleteButton(string buttonId)
    {
        // Сброс к дефолтной команде
        SaveButtonCommand(buttonId, "");
        Ctx.Log("Команда кнопки сброшена к дефолтной");
    }

    /// <summary>Смена устройства: сбрасываем показания экрана и перечитываем.</summary>
    public void OnDeviceChanged()
    {
        ScreenInfo.Text = "—";
        ResBox.Text = "";
        DpiBox.Text = "";
        _ = RefreshScreenInfoAsync();
    }

    /// <summary>Читает физическое и текущее (override) разрешение и плотность через wm.</summary>
    private async Task RefreshScreenInfoAsync()
    {
        var serial = Ctx?.Serial;
        if (string.IsNullOrEmpty(serial))
        {
            ScreenInfo.Text = "Устройство не подключено";
            return;
        }

        try
        {
            var (rcS, sizeOut, _) = await Task.Run(() => new AdbClient(Ctx.AdbPath, serial, 15).Shell("wm size", 15));
            var (rcD, densOut, _) = await Task.Run(() => new AdbClient(Ctx.AdbPath, serial, 15).Shell("wm density", 15));

            if (rcS != 0 && rcD != 0)
            {
                ScreenInfo.Text = "Не удалось прочитать параметры экрана";
                return;
            }

            string? physSize = null, ovrSize = null, physDpi = null, ovrDpi = null;

            foreach (var raw in sizeOut.Split('\n'))
            {
                var line = raw.Trim();
                if (line.StartsWith("Physical size:", StringComparison.Ordinal))
                    physSize = line["Physical size:".Length..].Trim();
                else if (line.StartsWith("Override size:", StringComparison.Ordinal))
                    ovrSize = line["Override size:".Length..].Trim();
            }

            foreach (var raw in densOut.Split('\n'))
            {
                var line = raw.Trim();
                if (line.StartsWith("Physical density:", StringComparison.Ordinal))
                    physDpi = line["Physical density:".Length..].Trim();
                else if (line.StartsWith("Override density:", StringComparison.Ordinal))
                    ovrDpi = line["Override density:".Length..].Trim();
            }

            var effSize = ovrSize ?? physSize;
            var effDpi = ovrDpi ?? physDpi;

            var text = $"Физически: {physSize ?? "?"} · DPI {physDpi ?? "?"}";
            if (ovrSize != null || ovrDpi != null)
                text += $"\nТекущее: {effSize ?? "?"} · DPI {effDpi ?? "?"}";

            ScreenInfo.Text = text;

            // Подставляем текущие значения в поля, если пользователь их не заполнил.
            if (string.IsNullOrWhiteSpace(ResBox.Text) && effSize != null)
                ResBox.Text = effSize;
            if (string.IsNullOrWhiteSpace(DpiBox.Text) && effDpi != null)
                DpiBox.Text = effDpi;
        }
        catch (Exception ex)
        {
            ScreenInfo.Text = $"Ошибка чтения: {ex.Message}";
        }
    }

    /// <summary>Применяет разрешение (WxH) и/или DPI через wm size / wm density.</summary>
    private async Task ApplyScreenAsync()
    {
        var serial = Ctx?.Serial;
        if (string.IsNullOrEmpty(serial))
        {
            Ctx?.Log("Сначала подключите устройство");
            return;
        }

        var res = ResBox.Text?.Trim() ?? "";
        var dpi = DpiBox.Text?.Trim() ?? "";
        var validRes = Regex.IsMatch(res, @"^\d{3,5}x\d{3,5}$");
        var validDpi = Regex.IsMatch(dpi, @"^\d{2,4}$");

        if (!validRes && !validDpi)
        {
            Ctx.Log("Укажите разрешение вида 1920x1080 и/или DPI числом (например 320)");
            return;
        }

        if (Ctx.Settings.ConfirmDangerous)
        {
            var parts = new List<string>();
            if (validRes) parts.Add($"разрешение {res}");
            if (validDpi) parts.Add($"DPI {dpi}");
            var ok = await UiDialogs.Confirm(TopLevel.GetTopLevel(this) as Window,
                "Изменить экран",
                $"Применить {string.Join(" и ", parts)}? Неверные значения могут сделать экран нечитаемым — сбросить можно кнопками «Сбросить».");
            if (!ok) return;
        }

        var client = new AdbClient(Ctx.AdbPath, serial, 20);

        if (validRes)
        {
            var (rc, _, err) = await Task.Run(() => client.Shell($"wm size {res}", 20));
            Ctx.Log(rc == 0 ? $"Разрешение задано: {res}" : $"Ошибка разрешения: {err.Trim()}");
        }

        if (validDpi)
        {
            var (rc, _, err) = await Task.Run(() => client.Shell($"wm density {dpi}", 20));
            Ctx.Log(rc == 0 ? $"DPI задан: {dpi}" : $"Ошибка DPI: {err.Trim()}");
        }

        await RefreshScreenInfoAsync();
    }

    /// <summary>Сбрасывает разрешение или DPI к заводским (wm ... reset).</summary>
    private async Task ResetScreenAsync(bool density)
    {
        var serial = Ctx?.Serial;
        if (string.IsNullOrEmpty(serial))
        {
            Ctx?.Log("Сначала подключите устройство");
            return;
        }

        var client = new AdbClient(Ctx.AdbPath, serial, 20);
        var cmd = density ? "wm density reset" : "wm size reset";
        var (rc, _, err) = await Task.Run(() => client.Shell(cmd, 20));

        Ctx.Log(rc == 0
            ? (density ? "DPI сброшен к заводскому" : "Разрешение сброшено к заводскому")
            : $"Ошибка сброса: {err.Trim()}");

        await RefreshScreenInfoAsync();
    }

    private void ReloadPrograms()
    {
        ProgramPanel.Children.Clear();

        var programsDir = Path.Combine(Paths.Base, "programs");
        if (!Directory.Exists(programsDir))
            return;

        foreach (var file in Directory.GetFiles(programsDir, "*.json"))
        {
            try
            {
                var json = File.ReadAllText(file);
                var prog = JsonSerializer.Deserialize<ProgramJson>(json, new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
                if (prog == null) continue;

                var btn = new Button
                {
                    Content = prog.Name,
                    Width = 140,
                    Height = 40,
                    Margin = new Thickness(4),
                    Tag = prog,
                };
                btn.Click += (_, _) => RunProgram(prog);
                ProgramPanel.Children.Add(btn);
            }
            catch
            {
                // Пропускаем битые JSON
            }
        }
    }

    private void RunProgram(ProgramJson prog)
    {
        var serial = Ctx.Serial ?? "";
        var (ip, port) = SplitTarget(serial, "5555");

        var args = prog.Args;
        args = args.Replace("{serial}", serial).Replace("{ip}", ip).Replace("{port}", port);

        var progPath = Path.Combine(Paths.Base, "programs", prog.File);
        if (!File.Exists(progPath))
        {
            Ctx.Log($"Файл программы не найден: {prog.File}");
            return;
        }

        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = progPath,
                ArgumentList = { args },
                UseShellExecute = false,
                CreateNoWindow = true,
            });
            Ctx.Log($"Запущено: {prog.Name}");
        }
        catch (Exception ex)
        {
            Ctx.Log($"Не удалось запустить: {ex.Message}");
        }
    }

    private static (string Ip, string Port) SplitTarget(string host, string defaultPort)
    {
        var h = host.Trim().Replace(" ", "");
        var port = defaultPort;

        var idx = h.LastIndexOf(':');
        if (idx >= 0)
        {
            var tail = h[(idx + 1)..];
            if (tail.Length > 0 && tail.All(char.IsDigit))
            {
                h = h[..idx];
                port = tail;
            }
        }

        return (h, port);
    }
}