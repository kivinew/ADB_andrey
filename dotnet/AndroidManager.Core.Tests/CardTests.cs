using AndroidManager.Core.Parsing;
using Xunit;

namespace AndroidManager.Core.Tests;

public class CardTests
{
    [Fact]
    public void NumberCard_computes_percent_from_max()
    {
        var (pct, text) = CardParser.Parse(
            new Card { Parse = "number", Idx = 1, Max = 100, Unit = "%" }, "a 42 b 84");

        Assert.Equal(84.0, pct!.Value, 6);
        Assert.Equal("84.0 %", text);
    }

    [Fact]
    public void NumberCard_without_max_has_no_percent()
    {
        var (pct, text) = CardParser.Parse(
            new Card { Parse = "number", Idx = 0, Unit = "МБ" }, "512");

        Assert.Null(pct);
        Assert.Equal("512.0 МБ", text);
    }

    [Fact]
    public void Div_scales_value()
    {
        var (pct, text) = CardParser.Parse(
            new Card { Parse = "number", Idx = 0, Div = 1024, Unit = "МБ" }, "2048");

        Assert.Equal("2.0 МБ", text);
        Assert.Null(pct);
    }

    [Fact]
    public void Missing_number_is_not_available()
    {
        var (pct, text) = CardParser.Parse(new Card { Parse = "number" }, "нет данных");

        Assert.Null(pct);
        Assert.Equal("н/д", text);
    }

    [Fact]
    public void NumsPct_computes_ratio()
    {
        var (pct, text) = CardParser.Parse(
            new Card { Parse = "nums_pct", A = 0, B = 1, Div = 1024, Unit = "МБ" }, "2048 4096");

        Assert.Equal(50.0, pct!.Value, 6);
        Assert.Equal("2 из 4 МБ (50%)", text);
    }

    [Fact]
    public void NumsPct_bad_index()
    {
        var (pct, text) = CardParser.Parse(
            new Card { Parse = "nums_pct", A = 0, B = 5 }, "1 2");

        Assert.Null(pct);
        Assert.Equal("н/д", text);
    }

    [Fact]
    public void NumsPct_zero_base()
    {
        var (pct, text) = CardParser.Parse(
            new Card { Parse = "nums_pct", A = 0, B = 1 }, "0 0");

        Assert.Null(pct);
        Assert.Equal("н/д", text);
    }

    [Fact]
    public void CpuCard_requires_snapshot()
    {
        var (pct, text) = CardParser.Parse(new Card { Parse = "cpu" }, "");

        Assert.Null(pct);
        Assert.Equal("н/д", text);
    }

    [Fact]
    public void CpuCard_percent_from_snapshots()
    {
        var snap = new CpuSnapshot(new CpuTimes(1000, 400), new CpuTimes(2000, 600));
        var (pct, text) = CardParser.Parse(new Card { Parse = "cpu" }, "", snap);

        Assert.Equal(80.0, pct!.Value, 6);
        Assert.Equal("80%", text);
    }

    [Fact]
    public void CpuCard_zero_delta()
    {
        var snap = new CpuSnapshot(new CpuTimes(1000, 400), new CpuTimes(1000, 400));
        var (pct, text) = CardParser.Parse(new Card { Parse = "cpu" }, "", snap);

        Assert.Null(pct);
        Assert.Equal("н/д", text);
    }
}