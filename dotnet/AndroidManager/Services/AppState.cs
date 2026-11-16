using AndroidManager.Core.Adb;
using AndroidManager.Core.Settings;

namespace AndroidManager.Services;

/// <summary>Папки программы. Рядом с exe лежат tools/, scripts/, apk/ — как в Python-версии.</summary>
public static class Paths
{
    // Полное имя не нужно: AppContext — системный класс, своего с таким именем больше нет.
    public static string Base { get; } = AppContext.BaseDirectory;

    /// <summary>Сначала tools/&lt;name&gt;/&lt;name&gt;.exe, затем PATH (тогда просто имя).</summary>
    public static string FindTool(string name)
    {
        var local = System.IO.Path.Combine(Base, "tools", name, name + ".exe");
        return File.Exists(local) ? local : name;
    }
}

/// <summary>Общее состояние оболочки: настройки, adb, выбранное устройство, журнал.</summary>
public sealed class AppState
{
    public AppSettings Settings { get; set; }
    public string AdbPath { get; }
    public string? Serial { get; set; }
    public string SettingsPath { get; }

    /// <summary>Последняя строка журнала — она же строка состояния внизу окна.</summary>
    public event Action<string>? Logged;

    /// <summary>Просьба перечитать список устройств: её слушает главное окно.</summary>
    public event Action? DevicesRefresh;

    public AppState(AppSettings settings, string settingsPath)
    {
        Settings = settings;
        SettingsPath = settingsPath;
        AdbPath = Paths.FindTool("adb");
    }

    public void Log(string text) => Logged?.Invoke(text);

    public void RequestDevicesRefresh() => DevicesRefresh?.Invoke();

    /// <summary>adb с текущим устройством. Можно вызывать из фонового потока.</summary>
    public AdbClient Client(int timeoutSeconds = 30) => new(AdbPath, Serial, timeoutSeconds);

    /// <summary>Полная командная строка: adb -s &lt;serial&gt; ...</summary>
    public string[] Args(params string[] args)
    {
        var full = new List<string>(args.Length + 3) { AdbPath };

        if (!string.IsNullOrEmpty(Serial))
        {
            full.Add("-s");
            full.Add(Serial);
        }

        full.AddRange(args);
        return full.ToArray();
    }

    /// <summary>Сохраняет настройки: вызывается после каждого изменения, чтобы падение не стёрло их.</summary>
    public void SaveSettings()
    {
        try
        {
            Settings.Save(SettingsPath);
        }
        catch (Exception ex)
        {
            Log($"Не удалось сохранить настройки: {ex.Message}");
        }
    }
}