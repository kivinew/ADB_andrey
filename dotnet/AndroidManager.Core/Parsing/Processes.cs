namespace AndroidManager.Core.Parsing;

/// <summary>Строка /proc/&lt;pid&gt;/stat: имя процесса, состояние, тики, RSS.</summary>
public readonly record struct ProcStat(string Pid, string Name, string State, int Ticks, int Rss);

/// <summary>Строка списка процессов для UI: память в МБ, загрузка в процентах.</summary>
public readonly record struct ProcRow(string Pid, string Name, string State, double Mem, double Cpu);

/// <summary>Разбор /proc/*/stat и замеров /proc/stat для расчёта загрузки процессов.</summary>
public static class ProcParser
{
    public const string ProcCmd =
        "echo \"@@S1 $(head -1 /proc/stat)\"; " +
        "for p in /proc/[0-9]*; do echo \"@@P $(cat $p/stat 2>/dev/null)\"; done; " +
        "sleep 1; " +
        "echo \"@@S2 $(head -1 /proc/stat)\"; " +
        "for p in /proc/[0-9]*; do echo \"@@Q $(cat $p/stat 2>/dev/null)\"; done";

    /// <summary>Разбор одной строки stat. Мусор и короткие строки — null.</summary>
    public static ProcStat? ParseProcStat(string text)
    {
        var lp = text.IndexOf('(');
        var rp = text.LastIndexOf(')');
        if (lp < 0 || rp < 0)
            return null;

        var pid = text[..lp].Trim();
        var name = lp + 1 <= rp ? text[(lp + 1)..rp] : "";
        var from = rp + 2;
        var rest = (from >= text.Length ? "" : text[from..])
            .Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);

        if (rest.Length < 22)
            return null;

        return new ProcStat(pid, name, rest[0],
            Num.Parse(rest[11]) + Num.Parse(rest[12]),
            Num.Parse(rest[21]));
    }

    /// <summary>Список процессов с памятью и загрузкой. Процессы без замера @@P получают 0%.</summary>
    public static List<ProcRow> ParseProcOutput(string raw)
    {
        CpuTimes? s1 = null;
        CpuTimes? s2 = null;
        var first = new Dictionary<string, ProcStat>(StringComparer.Ordinal);
        var second = new Dictionary<string, ProcStat>(StringComparer.Ordinal);

        foreach (var line in raw.Split('\n'))
        {
            if (line.StartsWith("@@S1 ", StringComparison.Ordinal))
                s1 = Num.CpuTotals(line[5..]);
            else if (line.StartsWith("@@S2 ", StringComparison.Ordinal))
                s2 = Num.CpuTotals(line[5..]);
            else if (line.StartsWith("@@P ", StringComparison.Ordinal))
            {
                if (ParseProcStat(line[4..]) is { } info)
                    first[info.Pid] = info;
            }
            else if (line.StartsWith("@@Q ", StringComparison.Ordinal))
            {
                if (ParseProcStat(line[4..]) is { } info)
                    second[info.Pid] = info;
            }
        }

        var dtotal = s1.HasValue && s2.HasValue ? s2.Value.Total - s1.Value.Total : 0;
        var rows = new List<ProcRow>();

        foreach (var (pid, cur) in second)
        {
            // Новый процесс: сравнивать не с чем, поэтому 0%, а не «тики минус ноль».
            var dp = first.TryGetValue(pid, out var old) ? cur.Ticks - old.Ticks : 0;
            var cpu = dtotal > 0 && dp >= 0 ? dp * 100.0 / dtotal : 0.0;
            rows.Add(new ProcRow(pid, cur.Name, cur.State, cur.Rss * 4 / 1024.0, cpu));
        }

        return rows;
    }
}