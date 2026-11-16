namespace AndroidManager.Core.Settings;

/// <summary>Значения по умолчанию: показатели состояния и команды консоли.</summary>
public static class Defaults
{
    public static List<CardSetting> DefaultCards() => new()
    {
        new()
        {
            Id = 1, Title = "Оперативная память", Parse = "nums_pct", A = 1, B = 0, Div = 1024,
            Unit = "МБ", Max = 100,
            Cmd = "awk '/^MemTotal/{t=$2}/^MemAvailable/{a=$2}END{print t, t-a}' /proc/meminfo",
        },
        new()
        {
            Id = 2, Title = "Внутренняя память (/data)", Parse = "nums_pct", A = 0, B = 1, Div = 1024,
            Unit = "МБ", Max = 100,
            Cmd = "df -k /data | tail -1 | awk '{print $3, $2}'",
        },
        new()
        {
            Id = 3, Title = "Процессор (CPU)", Parse = "cpu", Unit = "%", Max = 100, Cmd = "",
        },
        new()
        {
            Id = 4, Title = "Видеопроцессор (GPU)", Parse = "number", Idx = 0, Div = 1, Unit = "%",
            Max = 100,
            Cmd = @"for f in /sys/class/mpgpu/utilization /sys/class/gpu/utilization /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage; do [ -r ""$f"" ] && cat ""$f"" && break; done 2>/dev/null || echo 0",
        },
        new()
        {
            Id = 5, Title = "Температура", Parse = "number", Idx = 0, Div = 1, Unit = "°C", Max = 100,
            Cmd = "dumpsys battery 2>/dev/null | grep temperature | sed 's/temperature: //'",
        },
        new()
        {
            Id = 6, Title = "Нагрузка CPU (1 мин)", Parse = "number", Idx = 0, Div = 100, Unit = "",
            Max = 100,
            Cmd = "cat /proc/loadavg 2>/dev/null | awk '{print $1*100}' || echo 0",
        },
    };

    /// <summary>Кнопки быстрого запуска под полем ввода консоли.</summary>
    public static string[] ConsoleBar { get; } =
    {
        "logcat -d -t 300",
        "dmesg | tail -200",
        "ps -A",
        "ip addr",
        "df",
    };

    /// <summary>Слова для подсказок: когда пользователь набирает команду с нуля.</summary>
    public static string[] ConsoleCommands { get; } =
    {
        "am", "cat", "cd", "chmod", "cp", "date", "df", "dmesg", "du", "echo", "find", "free",
        "getprop", "grep", "head", "id", "ifconfig", "input", "ip", "kill", "logcat", "ls", "mkdir",
        "monkey", "mount", "mv", "netstat", "ping", "pkill", "pm", "ps", "reboot", "rm", "sed",
        "setprop", "settings", "sh", "sleep", "sort", "stat", "tail", "top", "tr", "uniq", "uname",
        "uptime", "vmstat", "wc", "which", "wm",
    };
}