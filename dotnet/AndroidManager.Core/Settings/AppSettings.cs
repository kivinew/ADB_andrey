using AndroidManager.Core.Parsing;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace AndroidManager.Core.Settings;

/// <summary>Избранное устройство для быстрого выбора.</summary>
public sealed class Favorite
{
    public string Name { get; set; } = "";
    public string Host { get; set; } = "";
    public string Port { get; set; } = "5555";
}

/// <summary>Один показатель состояния: чем снимать, как разбирать, в чём показывать.</summary>
public sealed class CardSetting
{
    public int Id { get; set; }
    public string Title { get; set; } = "Показатель";
    public string Cmd { get; set; } = "";
    public string Parse { get; set; } = "number";
    public string Unit { get; set; } = "";
    public double Div { get; set; } = 1;
    public int A { get; set; }
    public int B { get; set; } = 1;
    public int Idx { get; set; }
    public double Max { get; set; }

    public Card ToCard() => new()
    {
        Id = Id,
        Cmd = Cmd,
        Parse = Parse,
        Unit = Unit,
        Div = Div,
        A = A,
        B = B,
        Idx = Idx,
        Max = Max,
    };
}

/// <summary>Одна кастомная кнопка на панели: имя, команда, тип (shell/pc).</summary>
public sealed class BarItem
{
    public string Name { get; set; } = "Кнопка";
    public string Cmd { get; set; } = "";
    public string Type { get; set; } = "shell";
}

/// <summary>Пользовательские команды для встроенных кнопок интерфейса (scrcpy, Vysor, скриншот, перезагрузка, клавиши).</summary>
public sealed class ButtonCommands
{
    public string ScrcpyCmd { get; set; } = "";
    public string VysorCmd { get; set; } = "";
    public string ScreenshotCmd { get; set; } = "";
    public string RebootCmd { get; set; } = "";
    public string KeyCmd { get; set; } = "";
}

/// <summary>Настройки приложения. Лежат в settings.json рядом с exe: у C#-версии своя
/// папка, с настройками Python-версии они не пересекаются.</summary>
public sealed class AppSettings
{
    public string PcIp { get; set; } = "";
    public string VysorPath { get; set; } = "";
    public string Theme { get; set; } = "dark";
    public string FontFamily { get; set; } = "Segoe UI";
    public int FontSize { get; set; } = 11;
    public int ConsoleFontSize { get; set; } = 12;
    public int ConsoleHistoryLimit { get; set; } = 500;
    public bool ConfirmDangerous { get; set; } = true;
    public int AutoRefreshPackages { get; set; } = 30;
    public string Host { get; set; } = "";
    public string Port { get; set; } = "5555";
    public List<string> History { get; set; } = new();
    public List<Favorite> Favorites { get; set; } = new();
    public List<CardSetting> Cards { get; set; } = Defaults.DefaultCards();

    /// <summary>Кастомные кнопки для панелей: tools, apps, scripts, console.</summary>
    public Dictionary<string, List<BarItem>> Bars { get; set; } = new()
    {
        ["tools"] = new(),
        ["apps"] = new(),
        ["scripts"] = new(),
        ["console"] = new(),
    };

    /// <summary>Пользовательские команды для встроенных кнопок (scrcpy, Vysor, скриншот, перезагрузка, клавиши).</summary>
    public ButtonCommands ButtonCommands { get; set; } = new();

    private static readonly JsonSerializerOptions Json = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        // Без этого кириллица уезжает в \uXXXX, и файл не читается глазами.
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    /// <summary>Рядом с exe, как в Python-версии: там это paths.BASE.</summary>
    public static string DefaultPath { get; } = Path.Combine(
        AppContext.BaseDirectory, "settings.json");

    /// <summary>Читает настройки. Битый или чужой файл — не беда: берём значения по умолчанию.</summary>
    public static (AppSettings Settings, string? Error) Load(string? path = null)
    {
        var file = path ?? DefaultPath;

        try
        {
            if (File.Exists(file))
            {
                var loaded = JsonSerializer.Deserialize<AppSettings>(File.ReadAllText(file), Json);
                if (loaded is not null)
                {
                    // Файл могли править руками: пустые и потерянные списки заменяем.
                    loaded.History ??= new();
                    loaded.Favorites ??= new();
                    loaded.Cards ??= new();
                    loaded.Bars ??= new()
                    {
                        ["tools"] = new(),
                        ["apps"] = new(),
                        ["scripts"] = new(),
                        ["console"] = new(),
                    };

                    loaded.ButtonCommands ??= new ButtonCommands();

                    if (loaded.Cards.Count == 0)
                        loaded.Cards = Defaults.DefaultCards();

                    return (loaded, null);
                }
            }
        }
        catch (Exception ex)
        {
            return (new AppSettings(), ex.Message);
        }

        return (new AppSettings(), null);
    }

    public void Save(string? path = null)
    {
        var file = path ?? DefaultPath;
        var dir = Path.GetDirectoryName(file);
        if (!string.IsNullOrEmpty(dir))
            Directory.CreateDirectory(dir);

        File.WriteAllText(file, JsonSerializer.Serialize(this, Json));
    }
}