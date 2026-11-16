using AndroidManager.Core.Parsing;
using Xunit;

namespace AndroidManager.Core.Tests;

public class BatchTests
{
    [Fact]
    public void BuildStateBatch_skips_cpu_and_empty()
    {
        var cards = new[]
        {
            new Card { Id = 1, Cmd = "cat /proc/loadavg" },
            new Card { Id = 2, Cmd = "" },
            new Card { Id = 3, Cmd = "cat /proc/uptime", Parse = "cpu" },
        };

        var cmd = CardParser.BuildStateBatch(cards);

        Assert.Contains("@@c1", cmd);
        Assert.Contains("loadavg", cmd);
        Assert.DoesNotContain("@@c2", cmd);
        Assert.DoesNotContain("@@c3", cmd);
        Assert.Contains("echo \"@@S1 $(head -1 /proc/stat)\"", cmd);
        Assert.Contains("sleep 1", cmd);
    }

    [Fact]
    public void ParseStateBatch_values_and_snapshot()
    {
        var raw = string.Join("\n", new[]
        {
            "@@c12 55", "@@c7 3.5",
            "@@S1 cpu 1 2 3 4 5",
            "@@S2 cpu 2 3 4 5 6",
        });

        var (vals, snap) = StateBatchParser.Parse(raw);

        Assert.Equal(2, vals.Count);
        Assert.Equal("55", vals["12"]);
        Assert.Equal("3.5", vals["7"]);
        Assert.Equal(new CpuSnapshot(new CpuTimes(15, 9), new CpuTimes(20, 11)), snap);
    }

    [Fact]
    public void ParseStateBatch_without_snapshot()
    {
        var (vals, snap) = StateBatchParser.Parse("@@c1 1");

        Assert.Equal("1", vals["1"]);
        Assert.Null(snap);
    }
}