using AndroidManager.Core.Settings;
using Xunit;

namespace AndroidManager.Core.Tests;

public class SettingsTests
{
    [Fact]
    public void Default_cards_match_the_python_defaults()
    {
        var cards = Defaults.DefaultCards();

        Assert.Equal(6, cards.Count);

        var ram = cards[0];
        Assert.Equal("nums_pct", ram.Parse);
        Assert.Equal(1024.0, ram.Div);
        Assert.Equal(1, ram.A);
        Assert.Equal(0, ram.B);

        var parsed = ram.ToCard();
        Assert.Equal(1, parsed.Id);
        Assert.Equal("nums_pct", parsed.Parse);
        Assert.Equal(1024.0, parsed.Div.GetValueOrDefault());
        Assert.Equal(1, parsed.A.GetValueOrDefault());
        Assert.Equal(0, parsed.B.GetValueOrDefault());
    }

    [Fact]
    public void Default_card_ids_are_unique()
    {
        var ids = Defaults.DefaultCards().Select(c => c.Id).ToList();

        Assert.Equal(ids.Count, ids.Distinct().Count());
    }

    [Fact]
    public void Load_missing_file_gives_defaults()
    {
        var path = Path.Combine(Path.GetTempPath(), "android-manager-no-such-file.json");

        var (settings, error) = AppSettings.Load(path);

        Assert.Null(error);
        Assert.Equal("dark", settings.Theme);
        Assert.Equal(6, settings.Cards.Count);
    }

    [Fact]
    public void Save_and_load_round_trip()
    {
        // Пишем рядом со сборкой: в %TEMP% процессу может быть отказано на запись
        // (песочница, урезанные права), а тесту нужен настоящий файл на диске.
        var dir = Path.Combine(AppContext.BaseDirectory, "settings-tests-" + Guid.NewGuid().ToString("N"));
        var path = Path.Combine(dir, "settings.json");

        try
        {
            new AppSettings { Theme = "light", FontSize = 13, Host = "10.0.0.1", Port = "5556" }.Save(path);

            var (loaded, error) = AppSettings.Load(path);

            Assert.Null(error);
            Assert.Equal("light", loaded.Theme);
            Assert.Equal(13, loaded.FontSize);
            Assert.Equal("10.0.0.1", loaded.Host);
            Assert.Equal("5556", loaded.Port);
        }
        finally
        {
            // Уборка не должна подменять собой настоящую причину падения.
            try
            {
                if (Directory.Exists(dir))
                    Directory.Delete(dir, true);
            }
            catch
            {
            }
        }
    }
}