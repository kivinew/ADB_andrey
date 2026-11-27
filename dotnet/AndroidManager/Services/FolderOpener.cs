using System.Diagnostics;
using System.Runtime.InteropServices;

namespace AndroidManager.Services;

/// <summary>
/// Открывает папку в файловом менеджере ОС. Единая точка для вкладок «Приложения» и «Скрипты».
/// </summary>
internal static class FolderOpener
{
    // Тот же вызов, что делает Python-версия (os.startfile): ShellExecuteW(NULL, "open", путь, ..., SW_SHOWNORMAL).
    [DllImport("shell32.dll", CharSet = CharSet.Unicode, EntryPoint = "ShellExecuteW")]
    private static extern IntPtr ShellExecuteW(IntPtr hwnd, string? operation, string file,
        string? parameters, string? directory, int showCmd);

    private const int SW_SHOWNORMAL = 1;

    /// <returns>true, если запуск не вызвал исключения (окно открывает сама оболочка).</returns>
    public static bool Open(string path, Action<string>? log = null)
    {
        string dir;
        try
        {
            dir = Path.GetFullPath(path);
            Directory.CreateDirectory(dir);
        }
        catch (Exception ex)
        {
            log?.Invoke($"Не удалось подготовить папку «{path}»: {ex.Message}");
            return false;
        }

        log?.Invoke($"Открытие папки: {dir}");

        if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
        {
            // 1) Прямой ShellExecuteW — в точности как os.startfile в Python-версии.
            if (TryShellExecuteW(log, dir))
                return true;

            // 2) ShellExecute через Process.Start по пути папки.
            if (TryStart(log, "Process.Start ShellExecute (путь папки)",
                    new ProcessStartInfo { FileName = dir, UseShellExecute = true }))
                return true;

            // 3) Последний вариант: explorer.exe как дочерний процесс (на некоторых системах падает с 0xc0000142).
            return TryStart(log, "Process.Start ShellExecute (explorer.exe)",
                new ProcessStartInfo { FileName = "explorer.exe", Arguments = $"\"{dir}\"", UseShellExecute = true });
        }

        return TryStart(log, RuntimeInformation.IsOSPlatform(OSPlatform.OSX) ? "open" : "xdg-open",
            new ProcessStartInfo
            {
                FileName = RuntimeInformation.IsOSPlatform(OSPlatform.OSX) ? "open" : "xdg-open",
                Arguments = $"\"{dir}\"",
                UseShellExecute = false,
            });
    }

    private static bool TryShellExecuteW(Action<string>? log, string dir)
    {
        try
        {
            // Результат > 32 — успех; иначе это код ошибки ShellExecute (2 — не найден, 5 — отказано в доступе и т.д.).
            var code = ShellExecuteW(IntPtr.Zero, "open", dir, null, null, SW_SHOWNORMAL).ToInt64();
            log?.Invoke(code > 32 ? "ShellExecuteW: OK" : $"ShellExecuteW: ошибка, код {code}");
            return code > 32;
        }
        catch (Exception ex)
        {
            log?.Invoke($"ShellExecuteW: исключение {ex.GetType().Name}: {ex.Message}");
            return false;
        }
    }

    private static bool TryStart(Action<string>? log, string method, ProcessStartInfo psi)
    {
        try
        {
            // Для ShellExecute Process.Start часто возвращает null (проводник уже запущен) — это не ошибка.
            using var _ = Process.Start(psi);
            log?.Invoke($"{method}: OK");
            return true;
        }
        catch (Exception ex)
        {
            var code = ex is System.ComponentModel.Win32Exception w ? $" (Win32 {w.NativeErrorCode}, 0x{w.NativeErrorCode:X})" : "";
            log?.Invoke($"{method}: ошибка {ex.GetType().Name}: {ex.Message}{code}");
            return false;
        }
    }
}