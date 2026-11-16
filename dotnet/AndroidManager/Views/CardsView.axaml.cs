using AndroidManager.Core.Adb;
using AndroidManager.Core.Parsing;
using AndroidManager.Core.Settings;
using AndroidManager.Services;
using Avalonia.Controls;
using Avalonia.Media;
using Avalonia.Threading;
using System.ComponentModel;

namespace AndroidManager.Views;

/// <summary>Показатель на экране: заголовок, значение, точки для графика.</summary>
public sealed class CardItem : INotifyPropertyChanged
{
    private string _value = "-";
    private List<double> _points = new();

    public string Id { get; init; } = "";
    public string Title { get; init; } = "";
    public Card Card { get; init; } = null!;
    public double Max { get; init; }
    public IBrush Color { get; init; } = Brushes.Transparent;

    public IList<double> Points => _points;

    public string Value
    {
        get => _value;
        set
        {
            if (_value == value)
                return;

            _value = value;
            Changed(nameof(Value));
        }
    }

    /// <summary>Новая точка. Список подменяется целиком, иначе график не узнает об изменении.</summary>
    public void Push(double? percent)
    {
        var next = new List<double>(_points) { percent ?? 0 };

        if (next.Count > 60)
            next.RemoveRange(0, next.Count - 60);

        _points = next;
        Changed(nameof(Points));
    }

    /// <summary>Сброс: другое устройство — старые замеры показывать нельзя.</summary>
    public void Reset()
    {
        _points = new();
        Value = "-";
        Changed(nameof(Points));
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    private void Changed(string name) => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
}

public partial class CardsView : UserControl
{
    private static readonly string[] Palette =
    {
        "#89B4FA", "#CBA6F7", "#A6E3A1", "#FAB387", "#F38BA8", "#89DCEB", "#F9E2AF", "#7F849C",
    };

    private readonly DispatcherTimer _auto = new() { Interval = TimeSpan.FromSeconds(3) };

    private List<CardItem> _items = new();
    private bool _busy;

    public AppState Ctx { get; set; } = null!;

    public CardsView()
    {
        InitializeComponent();

        RefreshBtn.Click += (_, _) => _ = RefreshAsync();
        ResetBtn.Click += (_, _) => ResetCards();
        AutoBox.IsCheckedChanged += (_, _) =>
        {
            if (AutoBox.IsChecked == true)
                _auto.Start();
            else
                _auto.Stop();
        };

        _auto.Tick += (_, _) => _ = RefreshAsync();
        Loaded += (_, _) =>
        {
            Rebuild();

            if (AutoBox.IsChecked == true)
                _auto.Start();
        };
    }

    public void OnDeviceChanged()
    {
        foreach (var item in _items)
            item.Reset();
    }

    private void Rebuild()
    {
        _items = Ctx.Settings.Cards
            .Select((card, i) => new CardItem
            {
                Id = card.Id.ToString(),
                Title = card.Title,
                Card = card.ToCard(),
                Max = card.Max,
                Color = new SolidColorBrush(Color.Parse(Palette[i % Palette.Length])),
            })
            .ToList();

        Cards.ItemsSource = _items;
    }

    private void ResetCards()
    {
        Ctx.Settings.Cards = Defaults.DefaultCards();
        Ctx.SaveSettings();
        Rebuild();
        Ctx.Log("Показатели возвращены к стандартным");
        _ = RefreshAsync();
    }

    private async Task RefreshAsync()
    {
        var serial = Ctx.Serial ?? "";

        if (_busy || string.IsNullOrEmpty(serial) || _items.Count == 0)
            return;

        _busy = true;

        try
        {
            var cards = Ctx.Settings.Cards;
            var batch = CardParser.BuildStateBatch(cards.Select(c => c.ToCard()));

            var (values, snapshot) = await Task.Run(() =>
            {
                var (_, stdout, _) = new AdbClient(Ctx.AdbPath, serial, 60).Shell(batch, 60);
                return StateBatchParser.Parse(stdout);
            });

            foreach (var item in _items)
            {
                var raw = values.TryGetValue(item.Id, out var text) ? text : "";
                var (percent, shown) = CardParser.Parse(item.Card, raw, snapshot);

                item.Value = shown;
                item.Push(percent);
            }
        }
        catch (Exception ex)
        {
            Ctx.Log($"Состояние: {ex.Message}");
        }
        finally
        {
            _busy = false;
        }
    }
}