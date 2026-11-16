using AndroidManager.Core.Parsing;
using Xunit;

namespace AndroidManager.Core.Tests;

public class SystemInfoTests
{
    [Fact]
    public void MemFromMeminfo_reads_total_and_available()
    {
        var text = "MemTotal:       2048000 kB\nMemFree: 10 kB\nMemAvailable: 1024000 kB\n";

        Assert.Equal((2000, 1000), SystemInfoParser.MemFromMeminfo(text));
    }

    [Fact]
    public void MemFromMeminfo_empty()
    {
        Assert.Equal((0, 0), SystemInfoParser.MemFromMeminfo(""));
    }

    [Fact]
    public void ParseDfMb_reads_used_and_size()
    {
        var df = SystemInfoParser.ParseDfMb("/dev/block 40960 20480 20480 50% /data");

        Assert.True(df.HasValue);
        Assert.Equal(20, df.Value.Used);
        Assert.Equal(40, df.Value.Size);
    }

    [Fact]
    public void ParseDfMb_too_few_fields()
    {
        Assert.Null(SystemInfoParser.ParseDfMb("мало полей"));
    }

    [Fact]
    public void ParsePkgs_extracts_names()
    {
        var text = "package:com.a\n  package:com.b  \nnot a package\n";

        Assert.Equal(new[] { "com.a", "com.b" }, SystemInfoParser.ParsePkgs(text));
    }

    [Fact]
    public void SplitTarget_host_with_port()
    {
        Assert.Equal(("192.168.1.5", "5555"), TargetParser.SplitTarget("192.168.1.5:5555", "5555"));
        Assert.Equal(("10.0.0.1", "5556"), TargetParser.SplitTarget(" 10.0.0.1:5556 ", "5555"));
    }

    [Fact]
    public void SplitTarget_keeps_non_numeric_port()
    {
        Assert.Equal(("host:abc", "1234"), TargetParser.SplitTarget("host:abc", "1234"));
    }

    [Fact]
    public void SplitTarget_without_port()
    {
        Assert.Equal(("192.168.1.5", "5555"), TargetParser.SplitTarget("192.168.1.5", "5555"));
        Assert.Equal(("", "5555"), TargetParser.SplitTarget("", "5555"));
    }

    [Fact]
    public void DetectPcIp_is_ipv4()
    {
        Assert.Matches(@"^\d{1,3}(\.\d{1,3}){3}$", TargetParser.DetectPcIp());
    }
}