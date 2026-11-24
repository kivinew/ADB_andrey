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
# Standalone API: shell, call, getprop, packages, install, push/pull, screenshot, reboot.
import os
import subprocess
import time


def _adb_exe():
    here = os.path.dirname(os.path.abspath(__file__))
    local = os.path.join(os.path.dirname(here), 'tools', 'adb', 'adb.exe')
    if os.path.isfile(local):
        return local
    return 'adb'


def _serial():
    return os.environ.get('ANDROID_SERIAL') or ''


def _run(args, timeout=30):
    try:
        proc = subprocess.run([_adb_exe()] + args, capture_output=True, timeout=timeout,
                               stdin=subprocess.DEVNULL)
        return proc.returncode, proc.stdout.decode('utf-8', 'replace'), proc.stderr.decode('utf-8', 'replace')
    except Exception as exc:
        raise RuntimeError('adb failed: {}'.format(exc))


def shell(command, timeout=60):
    rc, out, err = _run(['-s', _serial(), 'shell', command], timeout=timeout)
    return ((out or '') + (err or '')).rstrip('\n')


def call(*args, timeout=120):
    rc, out, err = _run(['-s', _serial(), *args], timeout=timeout)
    return rc, out, err


def getprop(name):
    return shell('getprop {}'.format(name)).strip()


def packages(kind='all'):
    flags = {'all': [], 'user': ['-3'], 'system': ['-s'], 'disabled': ['-d']}.get(kind, [])
    rc, out, err = _run(['-s', _serial(), 'pm', 'list', 'packages', *flags], timeout=90)
    names = []
    for line in (out or '').splitlines():
        line = line.strip()
        if line.startswith('package:'):
            names.append(line.split('package:', 1)[1].strip())
    return names


def force_stop(pkg):
    return shell('am force-stop {}'.format(pkg))


def clear(pkg):
    return shell('pm clear {}'.format(pkg))


def disable(pkg):
    return shell('pm disable-user --user 0 {}'.format(pkg))


def enable(pkg):
    return shell('pm enable --user 0 {}'.format(pkg))


def uninstall(pkg):
    return shell('pm uninstall -k --user 0 {}'.format(pkg))


def launch(pkg):
    return shell('monkey -p {} -c android.intent.category.LAUNCHER 1'.format(pkg), timeout=30)


def install(apk_path):
    rc, out, err = _run(['-s', _serial(), 'install', '-r', apk_path], timeout=600)
    text = ((out or '') + (err or '')).strip()
    return 'Success' in text, text


def push(local_path, remote_path):
    rc, out, err = _run(['-s', _serial(), 'push', local_path, remote_path], timeout=600)
    if rc != 0:
        raise RuntimeError((out or '') + (err or ''))
    return (out or '').strip()


def pull(remote_path, local_path):
    rc, out, err = _run(['-s', _serial(), 'pull', remote_path, local_path], timeout=600)
    if rc != 0:
        raise RuntimeError((out or '') + (err or ''))
    return local_path


def screenshot(path):
    try:
        proc = subprocess.run([_adb_exe(), '-s', _serial(), 'exec-out', 'screencap', '-p'],
                               capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
    except Exception as exc:
        raise RuntimeError('adb failed: {}'.format(exc))
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError('screencap failed')
    with open(path, 'wb') as fh:
        fh.write(proc.stdout)
    return path


def reboot(mode=''):
    _run(['-s', _serial(), 'reboot'] + ([mode] if mode else []), timeout=15)


def sleep(seconds):
    end = time.time() + seconds
    while time.time() < end:
        time.sleep(min(0.2, max(0, end - time.time())))


def check():
    pass


stopped = False


__all__ = ['shell', 'call', 'getprop', 'packages', 'force_stop', 'clear', 'disable', 'enable', 'uninstall', 'launch', 'install', 'push', 'pull', 'screenshot', 'reboot', 'sleep', 'check'];
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
            Ctx?.Log($"Скрипт «{entry.Name}»: файл не найден — {path}");
            return;
        }

        var (exe, args) = BuildCommand(path);
        AppendOutput($">>> {entry.Name} ({entry.FileName})");
        Ctx?.Log($"Запуск скрипта «{entry.Name}» ({entry.FileName})");

        var psi = new ProcessStartInfo
        {
            FileName = exe,
            WorkingDirectory = ScriptsDir,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };
        foreach (var a in args)
            psi.ArgumentList.Add(a);

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
            Ctx?.Log($"Скрипт «{entry.Name}»: завершён, код {proc.ExitCode}");
        }
        catch (Exception ex)
        {
            AppendOutput($"[ошибка запуска] {ex.Message}");
            Ctx?.Log($"Скрипт «{entry.Name}»: ошибка запуска — {ex.Message}");
        }
        finally
        {
            _running?.Dispose();
            _running = null;
            StopBtn.IsEnabled = false;
        }
    }

    private static (string exe, List<string> args) BuildCommand(string path)
    {
        var ext = Path.GetExtension(path).ToLowerInvariant();
        var args = new List<string>();
        return ext switch
        {
            ".py" => (RuntimeInformation.IsOSPlatform(OSPlatform.Windows) ? "python" : "python3", new List<string> { "-c", "import runpy, sys; m = __import__('adb'); sys.modules['adb'] = m; p = sys.argv[1]; sys.argv[0] = p; runpy.run_path(p, run_name='__main__', init_globals={'adb': m})", path }),
            ".ps1" => (RuntimeInformation.IsOSPlatform(OSPlatform.Windows) ? "powershell" : "pwsh", new List<string> { "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path }),
            ".bat" or ".cmd" => ("cmd.exe", new List<string> { "/c", path }),
            ".sh" => ("bash", new List<string> { path }),
            _ => (path, new List<string>())
        };
    }

    public void StopScript()
    {
        try
        {
            if (_running is not null && !_running.HasExited)
            {
                Ctx?.Log("Остановка скрипта...");
                _running.Kill(entireProcessTree: true);
                AppendOutput("[скрипт остановлен]");
            }
            else
            {
                AppendOutput("[скрипт не выполняется]");
            }
        }
        catch (Exception ex)
        {
            AppendOutput($"[ошибка остановки] {ex.Message}");
            Ctx?.Log($"Остановка скрипта: ошибка — {ex.Message}");
        }
    }

    private void OpenScriptsFolder()
    {
        try
        {
            var dir = ScriptsDir;
            if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
            {
                AppendOutput($"[отладка] Открытие папки скриптов: {dir}");

                // explorer.exe с UseShellExecute=false и явным WorkingDirectory — работает из WinExe.
                var psi = new ProcessStartInfo
                {
                    FileName = "explorer.exe",
                    Arguments = dir,
                    UseShellExecute = false,
                    CreateNoWindow = false,
                    WindowStyle = ProcessWindowStyle.Normal,
                    WorkingDirectory = Environment.GetFolderPath(Environment.SpecialFolder.System),
                };
                var proc = Process.Start(psi);
                AppendOutput($"[отладка] explorer.exe вернул: {proc?.Id ?? -1}, HasExited: {proc?.HasExited}");
            }
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
