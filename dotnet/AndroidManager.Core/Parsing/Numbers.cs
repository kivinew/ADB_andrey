using System.Globalization;
using System.Text.RegularExpressions;

namespace AndroidManager.Core.Parsing;

/// <summary>Числа из вывода adb: терпимые к мусору, как int(float(x)) в Python.</summary>
public static class Num
{
    private static readonly Regex NumRe = new(@"-?\d+(?:\.\d+)?", RegexOptions.Compiled | RegexOptions.CultureInvariant);

    /// <summary>Первый проход по числу: "3.9" -> 3, "abc" -> <paramref name="fallback"/>.</summary>
    public static int Parse(string? text, int fallback = 0)
    {
        if (string.IsNullOrWhiteSpace(text))
            return fallback;

        if (double.TryParse(text.Trim(), NumberStyles.Float, CultureInfo.InvariantCulture, out var d))
        {
            if (double.IsNaN(d) || double.IsInfinity(d))
                return fallback;
            return (int)d;
        }

        return fallback;
    }

    /// <summary>Все числа из текста, включая отрицательные и дробные.</summary>
    public static List<double> CardNumbers(string text)
    {
        var result = new List<double>();
        foreach (Match m in NumRe.Matches(text))
            result.Add(double.Parse(m.Value, CultureInfo.InvariantCulture));

        return result;
    }

    /// <summary>Счётчики из строки /proc/stat. Пусто или мало полей — нули.</summary>
    public static CpuTimes CpuTotals(string line)
    {
        var parts = line.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
        var nums = new List<int>();
        for (var i = 1; i < parts.Length; i++)
            nums.Add(Parse(parts[i]));

        if (nums.Count < 5)
            return default;

        var total = 0;
        for (var i = 0; i < 8 && i < nums.Count; i++)
            total += nums[i];

        return new CpuTimes(total, nums[3] + nums[4]);
    }

    /// <summary>Деление с округлением к минус бесконечности — как // в Python.</summary>
    public static int FloorDiv(int value, int divisor)
        => (int)Math.Floor((double)value / divisor);
}

/// <summary>Пара счётчиков /proc/stat: сумма первых восьми полей и простой (idle + iowait).</summary>
public readonly record struct CpuTimes(int Total, int Idle);

/// <summary>Два замера /proc/stat с интервалом — из них считается загрузка CPU.</summary>
public readonly record struct CpuSnapshot(CpuTimes First, CpuTimes Second);