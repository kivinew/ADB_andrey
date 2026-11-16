namespace AndroidManager.Core.Parsing;

/// <summary>Разбор ответа build_state_batch: значения показателей и два замера CPU.</summary>
public static class StateBatchParser
{
    public static (Dictionary<string, string> Values, CpuSnapshot? Snapshot) Parse(string raw)
    {
        var vals = new Dictionary<string, string>(StringComparer.Ordinal);
        CpuTimes? s1 = null;
        CpuTimes? s2 = null;

        foreach (var line in raw.Split('\n'))
        {
            if (line.StartsWith("@@c", StringComparison.Ordinal))
            {
                var tail = line[3..];
                var sp = tail.IndexOf(' ');
                var head = sp < 0 ? tail : tail[..sp];
                var rest = sp < 0 ? "" : tail[(sp + 1)..].Trim();
                if (head.StartsWith("c", StringComparison.Ordinal))
                    head = head[1..];

                vals[head] = rest;
            }
            else if (line.StartsWith("@@S1 ", StringComparison.Ordinal))
                s1 = Num.CpuTotals(line[5..]);
            else if (line.StartsWith("@@S2 ", StringComparison.Ordinal))
                s2 = Num.CpuTotals(line[5..]);
        }

        CpuSnapshot? snap = s1.HasValue && s2.HasValue ? new CpuSnapshot(s1.Value, s2.Value) : null;
        return (vals, snap);
    }
}