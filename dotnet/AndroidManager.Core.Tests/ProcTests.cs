using System.Globalization;
using AndroidManager.Core.Parsing;
using Xunit;

namespace AndroidManager.Core.Tests;

public class ProcTests
{
    /// <summary>Строка /proc/&lt;pid&gt;/stat нужной формы: rest[11]+rest[12] — тики, rest[21] — RSS.</summary>
    private static string StatLine(string pid, string name, int utime = 0, int stime = 0, int rss = 0)
    {
        var fields = Enumerable.Repeat("0", 22).ToArray();
        fields[0] = "S";
        fields[11] = utime.ToString(CultureInfo.InvariantCulture);
        fields[12] = stime.ToString(CultureInfo.InvariantCulture);
        fields[21] = rss.ToString(CultureInfo.InvariantCulture);
        return $"{pid} ({name}) {string.Join(" ", fields)}";
    }

    [Fact]
    public void ParseProcStat_reads_fields()
    {
        var info = ProcParser.ParseProcStat(StatLine("1234", "my app", utime: 11, stime: 12, rss: 22));

        Assert.Equal(new ProcStat("1234", "my app", "S", 23, 22), info);
    }

    [Fact]
    public void ParseProcStat_garbage()
    {
        Assert.Null(ProcParser.ParseProcStat("мусор"));
        Assert.Null(ProcParser.ParseProcStat("1234 (name) S 1 2"));
    }

    [Fact]
    public void ParseProcOutput_cpu_and_mem()
    {
        var s1 = "cpu 100 0 100 800 100";
        var s2 = "cpu 200 0 200 900 100";

        var raw = string.Join("\n", new[]
        {
            "@@S1 " + s1,
            "@@P " + StatLine("77", "app", utime: 10, stime: 10, rss: 256),
            "@@S2 " + s2,
            "@@Q " + StatLine("77", "app", utime: 20, stime: 20, rss: 256),
        });

        var row = Assert.Single(ProcParser.ParseProcOutput(raw));

        Assert.Equal("77", row.Pid);
        Assert.Equal("app", row.Name);
        Assert.Equal("S", row.State);
        Assert.Equal(1.0, row.Mem, 6);
        Assert.Equal(20 * 100.0 / 300, row.Cpu, 6);
    }

    [Fact]
    public void ParseProcOutput_new_process_has_zero_cpu()
    {
        var raw = "@@Q " + StatLine("5", "new", rss: 512);

        var row = Assert.Single(ProcParser.ParseProcOutput(raw));

        Assert.Equal(0.0, row.Cpu, 6);
        Assert.Equal(2.0, row.Mem, 6);
    }
}