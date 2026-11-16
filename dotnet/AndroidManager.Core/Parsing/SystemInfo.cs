namespace AndroidManager.Core.Parsing;

/// <summary>Память, диски и пакеты из вывода shell-команд.</summary>
public static class SystemInfoParser
{
    /// <summary>MemTotal и MemAvailable из /proc/meminfo, в МБ.</summary>
    public static (int Total, int Available) MemFromMeminfo(string text)
    {
        var vals = new Dictionary<string, int>(StringComparer.Ordinal);

        foreach (var line in text.Split('\n'))
        {
            var parts = line.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length >= 2 && parts[0].EndsWith(':'))
                vals[parts[0][..^1]] = Num.Parse(parts[1]);
        }

        vals.TryGetValue("MemTotal", out var total);
        vals.TryGetValue("MemAvailable", out var available);
        return (Num.FloorDiv(total, 1024), Num.FloorDiv(available, 1024));
    }

    /// <summary>Строка df: занято и всего, в МБ. Мало полей — null.</summary>
    public static (int Used, int Size)? ParseDfMb(string line)
    {
        var f = line.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
        if (f.Length >= 4)
            return (Num.FloorDiv(Num.Parse(f[2]), 1024), Num.FloorDiv(Num.Parse(f[1]), 1024));

        return null;
    }

    /// <summary>Пакеты из вывода pm list packages.</summary>
    public static List<string> ParsePkgs(string text)
    {
        const string prefix = "package:";
        var result = new List<string>();

        foreach (var line in text.Split('\n'))
        {
            var t = line.Trim();
            if (t.StartsWith(prefix, StringComparison.Ordinal))
                result.Add(t[prefix.Length..]);
        }

        return result;
    }
}