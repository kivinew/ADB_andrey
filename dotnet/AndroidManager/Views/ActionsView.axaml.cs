using AndroidManager.Core.Adb;
using AndroidManager.Core.Parsing;
using AndroidManager.Core.Settings;
using AndroidManager.Services;
using Avalonia;
using Avalonia.Controls;
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

        Loaded += (_, _) => { LoadVysorPath(); ReloadPrograms(); };
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
            Process.Start(new ProcessStartInfo
            {
                FileName = path,
                UseShellExecute = true,
                CreateNoWindow = true,
            });
            Ctx.Log("Vysor запущен");
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

        var scrcpy = Paths.FindTool(ScrcpyExeName);
        var args = new List<string> { scrcpy, "-s", serial, "--video-codec", ScCodec.SelectedItem as string ?? "h264" };

        if (!string.IsNullOrWhiteSpace(ScMax.Text) && int.TryParse(ScMax.Text, out var ms) && ms > 0)
            args.AddRange(["--max-size", ScMax.Text]);
        if (!string.IsNullOrWhiteSpace(ScFps.Text) && int.TryParse(ScFps.Text, out var fps))
            args.AddRange(["--max-fps", ScFps.Text]);
        if (!string.IsNullOrWhiteSpace(ScBr.Text))
            args.AddRange(["--video-bit-rate", ScBr.Text]);
        if (ScTouch.IsChecked == true) args.Add("--show-touches");
        if (ScAwake.IsChecked == true) args.Add("--stay-awake");
        if (ScOff.IsChecked == true) args.Add("--turn-screen-off");

        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = args[0],
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            foreach (var a in args.Skip(1)) psi.ArgumentList.Add(a);
            // scrcpy ищет adb через переменную окружения ADB — передаём путь, как в Python-версии.
            psi.Environment["ADB"] = Ctx.AdbPath;
            var proc = Process.Start(psi);
            if (proc is null)
                throw new InvalidOperationException("scrcpy не запустился");
            Ctx.Log("scrcpy запущен");
        }
        catch (Win32Exception)
        {
            Ctx.Log($"scrcpy не найден по пути: {args[0]}. Установите scrcpy рядом с программой (tools/scrcpy/scrcpy.exe) или в PATH");
        }
        catch (Exception ex)
        {
            Ctx.Log($"Не удалось запустить scrcpy: {ex.Message}");
        }
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
            var (rc, _, err) = await Task.Run(() => new AdbClient(Ctx.AdbPath, serial, 30).Shell(cmd, 30));
            if (rc == 0)
                Ctx.Log($"Команда отправлена: {cmd}");
            else
                Ctx.Log($"Ошибка {cmd}: {err.Trim()}");
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
            var (rc, _, err) = new AdbClient(Ctx.AdbPath, serial, 15).Shell($"input keyevent {ki.Code}", 15);
            Dispatcher.UIThread.Post(() =>
            {
                if (rc == 0)
                    Ctx.Log($"Клавиша отправлена: {ki.Name}");
                else
                    Ctx.Log($"Ошибка клавиши: {err.Trim()}");
            });
        });
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