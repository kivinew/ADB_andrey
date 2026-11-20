namespace AndroidManager.Core.Adb;

/// <summary>
/// Проверка и автоматический запуск ADB сервера при старте.
/// Если <c>adb version</c> не отвечает — убиваем и перезапускаем сервер, проверяем ещё раз.
/// </summary>
public static class AdbServer
{
    public const string BridgeMarker = "Android Debug Bridge";

    /// <summary>Жив ли adb-сервер: <c>adb version</c> отрабатывает и пишет bridge.</summary>
    public static bool IsResponsive(string adbPath, int timeoutSeconds = 5)
    {
        var (rc, stdout, _) = AdbRunner.Run(new[] { adbPath, "version" }, timeoutSeconds);
        return rc == 0 && stdout.Contains(BridgeMarker, StringComparison.Ordinal);
    }

    /// <summary>
    /// Убеждается, что ADB сервер запущен: при неработающем — kill + start + повторная проверка.
    /// </summary>
    public static bool EnsureStarted(
        string adbPath,
        Func<string, bool>? isResponsive = null,
        Func<string, int>? killServer = null,
        Func<string, int>? startServer = null)
    {
        var check = isResponsive ?? ((a) => IsResponsive(a));
        var kill = killServer ?? ((a) => AdbRunner.Run(new[] { a, "kill-server" }, 10).rc);
        var start = startServer ?? ((a) => AdbRunner.Run(new[] { a, "start-server" }, 10).rc);

        if (check(adbPath))
            return true;

        kill(adbPath);
        start(adbPath);

        if (check(adbPath))
            return true;

        kill(adbPath);
        start(adbPath);

        return check(adbPath);
    }

    public static Task<bool> EnsureStartedAsync(string adbPath, CancellationToken cancellationToken = default)
        => Task.Run(() => EnsureStarted(adbPath), cancellationToken);
}
