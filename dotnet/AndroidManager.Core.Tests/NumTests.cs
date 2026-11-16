using AndroidManager.Core.Parsing;
using Xunit;

namespace AndroidManager.Core.Tests;

public class NumTests
{
    [Fact]
    public void Parse_truncates_like_int_float()
    {
        Assert.Equal(42, Num.Parse("42"));
        Assert.Equal(7, Num.Parse(" 7 "));
        Assert.Equal(3, Num.Parse("3.9"));
        Assert.Equal(0, Num.Parse("abc"));
        Assert.Equal(0, Num.Parse(null));
        Assert.Equal(5, Num.Parse("", 5));
        Assert.Equal(5, Num.Parse(null, 5));
    }

    [Fact]
    public void CardNumbers_reads_numbers_from_text()
    {
        Assert.Equal(new[] { 1.0, 2.5, -3.0 }, Num.CardNumbers("1 2.5 -3"));
        Assert.Empty(Num.CardNumbers("нет чисел"));
    }

    [Fact]
    public void CpuTotals_sums_and_idle()
    {
        Assert.Equal(new CpuTimes(3600, 900), Num.CpuTotals("cpu 100 200 300 400 500 600 700 800 900"));
    }

    [Fact]
    public void CpuTotals_short_line()
    {
        Assert.Equal(new CpuTimes(0, 0), Num.CpuTotals("cpu 1 2"));
    }

    [Fact]
    public void FloorDiv_rounds_toward_negative_infinity()
    {
        Assert.Equal(-3, Num.FloorDiv(-5, 2));
        Assert.Equal(2, Num.FloorDiv(5, 2));
    }
}