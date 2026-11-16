using System.Diagnostics;

namespace AndroidManager.Core.Adb;

/// <summary>
/// Гашение дерева процессов. На Windows <see cref="Process.Kill()"/> не рвёт pipe, и
/// читатель остаётся висеть в чтении до закрытия adb — отсюда зависание на десятки секунд
/// после «Стоп». taskkill /T убивает дерево и закрывает трубу.
/// </summary>
public static class ProcessKill
{
    public static void KillTree(Process? proc)
    {
        if (proc is null)
            return;

        try
        {
            if (proc.HasExited)
                return;
        }
        catch
        {
            return;
        }

        try
        {
            if (OperatingSystem.IsWindows())
            {
                var psi = new ProcessStartInfo("taskkill", $"/F /T /PID {proc.Id}")
                {
                    UseShellExecute = false,
                    CreateNoWindow = true,
                };

                using var killer = Process.Start(psi);
                killer?.WaitForExit(10_000);
            }
            else
            {
                proc.Kill(entireProcessTree: true);
            }
        }
        catch
        {
            // Процесс мог умереть между проверкой и запуском taskkill.
        }
    }
}