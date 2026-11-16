using System.ComponentModel;
using System.Diagnostics;
using System.Text;

namespace AndroidManager.Core.Adb;

/// <summary>
/// Запуск внешних процессов (adb и прочие). Возвращает (rc, out, err) и не бросает:
/// отсутствующий файл — код <see cref="NotFound"/>, таймаут — <see cref="Timeout"/>.
/// </summary>
public static class AdbRunner
{
    public const int NotFound = -1;
    public const int Timeout = -2;

    public static (int rc, string stdout, string stderr) Run(
        string[] args, int timeoutSeconds = 30, string? input = null)
    {
        if (args.Length == 0)
            return (NotFound, "", "Пустой список аргументов");

        var psi = new ProcessStartInfo
        {
            FileName = args[0],
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            RedirectStandardInput = input is not null,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };

        // ArgumentList, а не склейка в строку: adb не приходится экранировать вручную.
        for (var i = 1; i < args.Length; i++)
            psi.ArgumentList.Add(args[i]);

        try
        {
            using var proc = Process.Start(psi);
            if (proc is null)
                return (NotFound, "", $"Не удалось запустить процесс: {args[0]}");

            // Читаем оба потока параллельно: если вычитывать stdout до stderr,
            // дочерний процесс, заполнивший буфер stderr, заблокируется.
            var stdoutTask = proc.StandardOutput.ReadToEndAsync();
            var stderrTask = proc.StandardError.ReadToEndAsync();

            if (input is not null)
            {
                proc.StandardInput.Write(input);
                proc.StandardInput.Close();
            }

            if (!proc.WaitForExit(timeoutSeconds * 1000))
            {
                // taskkill /T, а не Kill(): Kill не рвёт pipe, и читатель стрима висит.
                ProcessKill.KillTree(proc);

                return (Timeout, "", "Превышено время ожидания");
            }

            return (proc.ExitCode,
                stdoutTask.GetAwaiter().GetResult(),
                stderrTask.GetAwaiter().GetResult());
        }
        catch (Win32Exception)
        {
            return (NotFound, "", $"Не найден файл: {args[0]}");
        }
        catch (Exception ex)
        {
            return (NotFound, "", ex.Message);
        }
    }
}