using System.Globalization;

namespace AndroidManager.Core.Parsing;

/// <summary>Описание показателя: чем снимать, как разбирать, в чём показывать.</summary>
public sealed class Card
{
    public int Id { get; init; }
    public string? Cmd { get; init; }
    public string? Parse { get; init; }
    public string? Unit { get; init; }

    /// <summary>Делитель для отображения. 0 и отсутствие — единица.</summary>
    public double? Div { get; init; }

    /// <summary>Индексы чисел для parse = "nums_pct".</summary>
    public int? A { get; init; }
    public int? B { get; init; }

    /// <summary>Индекс числа для parse = "number".</summary>
    public int? Idx { get; init; }

    /// <summary>Верхняя граница для процента на графике. 0 и отсутствие — без процента.</summary>
    public double? Max { get; init; }
}

/// <summary>Разбор ответов показателей.</summary>
public static class CardParser
{
    private static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

    /// <summary>Разбор ответа показателя. Возвращает (процент для графика или null, текст для показа).</summary>
    public static (double? Percent, string Text) Parse(Card card, string text, CpuSnapshot? snap = null)
    {
        var unit = card.Unit ?? "";
        var div = card.Div.GetValueOrDefault(1);
        if (div == 0)
            div = 1;

        var parse = card.Parse ?? "number";

        if (parse == "cpu")
        {
            if (snap is null)
                return (null, "н/д");

            var (s1, s2) = snap.Value;
            var dt = s2.Total - s1.Total;
            if (dt <= 0)
                return (null, "н/д");

            var busy = (dt - (s2.Idle - s1.Idle)) * 100.0 / dt;
            return (busy, $"{busy.ToString("0", Inv)}%");
        }

        var nums = Num.CardNumbers(text);
        if (nums.Count == 0)
            return (null, "н/д");

        if (parse == "nums_pct")
        {
            var aI = card.A.GetValueOrDefault(0);
            var bI = card.B.GetValueOrDefault(1);
            if (Math.Max(aI, bI) >= nums.Count || Math.Min(aI, bI) < 0)
                return (null, "н/д");

            var a = nums[aI];
            var b = nums[bI];
            if (b <= 0)
                return (null, "н/д");

            var pct = a * 100.0 / b;
            var text1 = $"{(a / div).ToString("0", Inv)} из {(b / div).ToString("0", Inv)} {unit} ({pct.ToString("0", Inv)}%)";
            return (pct, text1);
        }

        var i = card.Idx.GetValueOrDefault(0);
        if (i < 0 || i >= nums.Count)
            return (null, "н/д");

        var v = nums[i] / div;
        var mx = card.Max.GetValueOrDefault(0);
        double? pctOut = mx != 0 ? v * 100.0 / mx : null;
        var result = $"{v.ToString("0.0", Inv)} {unit}".TrimEnd();
        return (pctOut, result);
    }

    /// <summary>Одна команда для всех показателей. Каждый ответ печатается строкой @@c&lt;id&gt; ....</summary>
    public static string BuildStateBatch(IEnumerable<Card> cards)
    {
        var parts = new List<string>();

        foreach (var c in cards)
        {
            if (c.Parse == "cpu")
                continue;

            var cmd = c.Cmd?.Trim();
            if (string.IsNullOrEmpty(cmd))
                continue;

            // tr "\n" " " — именно обратный слэш с n: команда уходит в sh как есть.
            parts.Add($"echo \"@@c{c.Id} $({cmd} 2>/dev/null | tr \"\\n\" \" \")\"");
        }

        parts.Add("echo \"@@S1 $(head -1 /proc/stat)\"");
        parts.Add("sleep 1");
        parts.Add("echo \"@@S2 $(head -1 /proc/stat)\"");

        return string.Join("; ", parts);
    }
}