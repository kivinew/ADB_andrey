using AndroidManager.Core.Adb;
using Xunit;

namespace AndroidManager.Core.Tests;

public class AdbServerTests
{
    [Fact]
    public void EnsureStarted_skips_restart_when_adb_responds()
    {
        var calls = new List<string>();

        var ok = AdbServer.EnsureStarted(
            "adb",
            isResponsive: _ =>
            {
                calls.Add("check");
                return true;
            },
            killServer: _ =>
            {
                calls.Add("kill");
                return 0;
            },
            startServer: _ =>
            {
                calls.Add("start");
                return 0;
            });

        Assert.True(ok);
        Assert.Equal(new[] { "check" }, calls);
    }

    [Fact]
    public void EnsureStarted_kills_and_starts_when_adb_down()
    {
        var calls = new List<string>();
        var checks = 0;

        var ok = AdbServer.EnsureStarted(
            "adb",
            isResponsive: _ =>
            {
                checks++;
                calls.Add("check");
                // Первый check — до перезапуска — не отвечает, второй — отвечает.
                return checks > 1;
            },
            killServer: _ =>
            {
                calls.Add("kill");
                return 0;
            },
            startServer: _ =>
            {
                calls.Add("start");
                return 0;
            });

        Assert.True(ok);
        Assert.Equal(new[] { "check", "kill", "start", "check" }, calls);
    }

    [Fact]
    public void EnsureStarted_retries_restart_once_when_still_down()
    {
        var calls = new List<string>();
        var checks = 0;

        var ok = AdbServer.EnsureStarted(
            "adb",
            isResponsive: _ =>
            {
                checks++;
                calls.Add("check");
                // Всегда не отвечает.
                return false;
            },
            killServer: _ =>
            {
                calls.Add("kill");
                return 0;
            },
            startServer: _ =>
            {
                calls.Add("start");
                return 0;
            });

        Assert.False(ok);
        Assert.Equal(
            new[] { "check", "kill", "start", "check", "kill", "start", "check" },
            calls);
    }
}
