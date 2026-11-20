using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using AndroidManager.Services;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Platform.Storage;
using Avalonia.Threading;

namespace AndroidManager.Views;

public partial class ScriptsView : UserControl
{
    private sealed class ScriptEntry
    {
        public string Name { get; set; } = "";
        public string FileName { get; set; } = "";
    }

    public AppState? Ctx { get; set; }

    private readonly List<ScriptEntry> _scripts = new();
    private Process? _running;

    private const string AdbShimFileName = "adb.py";

    private const string AdbShimSource = @"# -*- coding: utf-8 -*-
# adb module for user scripts (C# Android-manager).
# Provides shell(command, timeout=60) -> str.
# Usage:
#     import adb
#     output = adb.shell('logcat -d -t 100')
import os
import subprocess


def _adb_exe():
    here = os.path.dirname(os.path.abspath(__file__))
    local = os.path.join(os.path.dirname(here), 'tools', 'adb', 'adb.exe')
    if os.path.isfile(local):
        return local
    return 'adb'


def shell(command, timeout=60):
    exe = _adb_exe()
    args = [exe]
    serial = os.environ.get('ANDROID_SERIAL') or ''
    if serial:
        args += ['-s', serial]
    args += ['shell', command]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        raise RuntimeError('adb shell failed: {}'.format(exc))
    return ((proc.stdout or '') + (proc.stderr or '')).rstrip('\n')


__all__ = ['shell'];
";

    public ScriptsView()
    {
        InitializeComponent();

        EnsureAdbShim();

        AddBtn.Click += async (_, _) => await AddScriptAsync();
        StopBtn.Click += (_, _) => StopScript();
        OpenFolderBtn.Click += (_, _) => OpenScriptsFolder();
        CopyBtn.Click += async (_, _) => await CopyOutputAsync();
        ClearBtn.Click += (_, _) => OutputBox.Text = "";

        Loaded += (_, _) => LoadScripts();
    }

    private void EnsureAdbShim()
    {
        var path = Path.Combine(ScriptsDir, AdbShimFileName);
        if (File.Exists(path))
            return;

        try
        {
            File.WriteAllText(path, AdbShimSource);
        }
        catch (Exception ex)
        {
            AppendOutput($"[ошибка записи adb.py] {ex.Message}");
        }
    }

    private string ScriptsDir
    {
        get
        {
            var baseDir = Ctx is not null
                ? Path.GetDirectoryName(Ctx.SettingsPath) ?? AppContext.BaseDirectory
                : AppContext.BaseDirectory;
            var dir = Path.Combine(baseDir, "scripts");
            Directory.CreateDirectory(dir);
            return dir;
        }
    }

    private string IndexPath => Path.Combine(ScriptsDir, "scripts.json");

    private void LoadScripts()
    {
        _scripts.Clear();
        try
        {
            if (File.Exists(IndexPath))
            {
                var json = File.ReadAllText(IndexPath);
                var items = JsonSerializer.Deserialize<List<ScriptEntry>>(json);
                if (items is not null)
                    _scripts.AddRange(items);
            }
        }
        catch (Exception ex)
        {
            AppendOutput($"[ошибка чтения scripts.json] {ex.Message}");
        }

        RenderScripts();
    }

    private void SaveScripts()
    {
        try
        {
            var json = JsonSerializer.Serialize(_scripts, new JsonSerializerOptions { WriteIndented = true });
            File.WriteAllText(IndexPath, json);
        }
        catch (Exception ex)
        {
            AppendOutput($"[ошибка сохранения scripts.json] {ex.Message}");
        }
    }

    private void RenderScripts()
    {
        ScriptsBar.Children.Clear();
        EmptyHint.IsVisible = _scripts.Count == 0;

        foreach (var entry in _scripts.ToList())
        {
            var btn = new Button
            {
                Content = entry.Name,
                Margin = new Thickness(0, 0, 8, 8)
            };
            btn.Classes.Add("btn--ghost");

            var menu = new ContextMenu();
            var runItem = new MenuItem { Header = "Запустить" };
            runItem.Click += (_, _) => _ = RunScriptAsync(entry);
            var delItem = new MenuItem { Header = "Удалить" };
            delItem.Click += (_, _) =>
            {
                _scripts.Remove(entry);
                SaveScripts();
                RenderScripts();
            };
            menu.Items.Add(runItem);
            menu.Items.Add(delItem);
            btn.ContextMenu = menu;

            btn.Click += (_, _) => _ = RunScriptAsync(entry);
            ScriptsBar.Children.Add(btn);
        }
    }

    private async Task AddScriptAsync()
    {
        var top = TopLevel.GetTopLevel(this);
        if (top is null) return;

        var files = await top.StorageProvider.OpenFilePickerAsync(new FilePickerOpenOptions
        {
            Title = "Выберите скрипт",
            AllowMultiple = false,
            FileTypeFilter = new[]
            {
                new FilePickerFileType("Скрипты") { Patterns = new[] { "*.py", "*.ps1", "*.sh", "*.bat", "*.cmd" } },
                FilePickerFileTypes.All
            }
        });

        if (files.Count == 0) return;
        var srcPath = files[0].TryGetLocalPath();
        if (string.IsNullOrEmpty(srcPath) || !File.Exists(srcPath)) return;

        var fileName = Path.GetFileName(srcPath);
        var destPath = Path.Combine(ScriptsDir, fileName);
        File.Copy(srcPath, destPath, overwrite: true);

        var name = Path.GetFileNameWithoutExtension(fileName);
        _scripts.Add(new ScriptEntry { Name = name, FileName = fileName });
        SaveScripts();
        RenderScripts();
        Ctx?.Log($"Скрипт добавлен: {fileName}");
    }

    private async Task RunScriptAsync(ScriptEntry entry)
    {
        if (_running is not null)
        {
            AppendOutput("[уже выполняется другой скрипт — сначала остановите его]");
            return;
        }

        var path = Path.Combine(ScriptsDir, entry.FileName);
        if (!File.Exists(path))
        {
            AppendOutput($"[файл не найден] {path}");
            return;
        }

        var (exe, args) = BuildCommand(path);
        AppendOutput($">>> {entry.Name} ({entry.FileName})");

        var psi = new ProcessStartInfo
        {
            FileName = exe,
            Arguments = args,
            WorkingDirectory = ScriptsDir,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };

        var serial = Ctx?.Serial;
        if (!string.IsNullOrEmpty(serial))
            psi.Environment["ANDROID_SERIAL"] = serial;

        try
        {
            var proc = new Process { StartInfo = psi, EnableRaisingEvents = true };
            _running = proc;
            StopBtn.IsEnabled = true;

            proc.OutputDataReceived += (_, e) =>
            {
                if (e.Data is not null)
                    Dispatcher.UIThread.Post(() => AppendOutput(e.Data));
            };
            proc.ErrorDataReceived += (_, e) =>
            {
                if (e.Data is not null)
                    Dispatcher.UIThread.Post(() => AppendOutput($"[stderr] {e.Data}"));
            };

            proc.Start();
            proc.BeginOutputReadLine();
            proc.BeginErrorReadLine();

            await proc.WaitForExitAsync();
            AppendOutput($"[завершено с кодом {proc.ExitCode}]");
        }
        catch (Exception ex)
        {
            AppendOutput($"[ошибка запуска] {ex.Message}");
        }
        finally
        {
            _running?.Dispose();
            _running = null;
            StopBtn.IsEnabled = false;
        }
    }

    private static (string exe, string args) BuildCommand(string path)
    {
        var ext = Path.GetExtension(path).ToLowerInvariant();
        var q = $"\"{path}\"";
        return ext switch
        {
            ".py" => (RuntimeInformation.IsOSPlatform(OSPlatform.Windows) ? "python" : "python3", q),
            ".ps1" => (RuntimeInformation.IsOSPlatform(OSPlatform.Windows) ? "powershell" : "pwsh", $"-NoProfile -ExecutionPolicy Bypass -File {q}"),
            ".bat" or ".cmd" => ("cmd.exe", $"/c {q}"),
            ".sh" => ("bash", q),
            _ => (path, "")
        };
    }

    public void StopScript()
    {
        try
        {
            if (_running is not null && !_running.HasExited)
            {
                _running.Kill(entireProcessTree: true);
                AppendOutput("[скрипт остановлен]");
            }
        }
        catch (Exception ex)
        {
            AppendOutput($"[ошибка остановки] {ex.Message}");
        }
    }

    private void OpenScriptsFolder()
    {
        try
        {
            var dir = ScriptsDir;
            if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
                Process.Start(new ProcessStartInfo("explorer.exe", $"\"{dir}\"") { UseShellExecute = true });
            else if (RuntimeInformation.IsOSPlatform(OSPlatform.OSX))
                Process.Start("open", dir);
            else
                Process.Start("xdg-open", dir);
        }
        catch (Exception ex)
        {
            AppendOutput($"[ошибка] {ex.Message}");
        }
    }

    private async Task CopyOutputAsync()
    {
        var top = TopLevel.GetTopLevel(this);
        if (top?.Clipboard is not null)
            await top.Clipboard.SetTextAsync(OutputBox.Text ?? "");
    }

    private void AppendOutput(string line)
    {
        OutputBox.Text = string.IsNullOrEmpty(OutputBox.Text)
            ? line
            : $"{OutputBox.Text}{Environment.NewLine}{line}";
        OutputBox.CaretIndex = OutputBox.Text.Length;
    }
}
