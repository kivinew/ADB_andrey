using AndroidManager.Core.Adb;
using AndroidManager.Core.Parsing;
using AndroidManager.Core.Settings;
using AndroidManager.Services;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Interactivity;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Threading;
using Avalonia.VisualTree;
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
    private CardItem? _selected;
    private bool _busy;

    public AppState Ctx { get; set; } = null!;

    public CardsView()
    {
        InitializeComponent();

        RefreshBtn.Click += (_, _) => _ = RefreshAsync();
        ResetBtn.Click += (_, _) => ResetCards();
        AddBtn.Click += (_, _) => EditCard(null);
        EditBtn.Click += (_, _) => EditCard(_selected);
        DeleteBtn.Click += (_, _) => DeleteCard(_selected);
        Cards.SelectionChanged += OnCardSelected;

        var cardMenu = new ContextMenu();
        var miEdit = new MenuItem { Header = "Изменить" };
        var miDelete = new MenuItem { Header = "Удалить" };
        cardMenu.Items.Add(miEdit);
        cardMenu.Items.Add(miDelete);
        Cards.ContextMenu = cardMenu;
        miEdit.Click += (_, _) => EditCard(_selected);
        miDelete.Click += (_, _) => DeleteCard(_selected);
        cardMenu.Opening += (_, e) =>
        {
            if (_selected is null)
                e.Cancel = true;
        };

        // ПКМ по карточке должна выбирать её до открытия меню, иначе правится чужая.
        Cards.AddHandler(InputElement.PointerPressedEvent, OnCardsPointerPressed, RoutingStrategies.Bubble, handledEventsToo: true);

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

    private void UpdateCommandButtons()
    {
        var has = _selected is not null;
        EditBtn.IsEnabled = has;
        DeleteBtn.IsEnabled = has;
    }

    private void SelectCard(CardItem item)
    {
        _selected = item;
        UpdateCommandButtons();
    }

    private void EditCard(CardItem? item)
    {
        var isNew = item is null;
        var setting = isNew ? new CardSetting { Id = NextId(), Parse = "number", Div = 1, Max = 100 }
            : Ctx.Settings.Cards.FirstOrDefault(c => c.Id.ToString() == item.Id) ?? new CardSetting();

        var win = new Window
        {
            Title = isNew ? "Новый виджет" : "Редактировать виджет",
            Width = 520,
            Height = 460,
            CanResize = false,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
        };

        var titleBox = new TextBox { Text = setting.Title, Margin = new Thickness(0, 0, 0, 8) };
        var cmdBox = new TextBox { Text = setting.Cmd, Margin = new Thickness(0, 0, 0, 8) };
        var parseBox = new ComboBox { SelectedIndex = ParseIndex(setting.Parse), Margin = new Thickness(0, 0, 0, 8) };
        parseBox.Items.Add("number");
        parseBox.Items.Add("nums_pct");
        parseBox.Items.Add("cpu");
        var unitBox = new TextBox { Text = setting.Unit, Margin = new Thickness(0, 0, 0, 8) };
        var divBox = new TextBox { Text = setting.Div == 1 ? "1" : setting.Div.ToString(), Margin = new Thickness(0, 0, 0, 8) };
        var maxBox = new TextBox { Text = setting.Max == 0 ? "100" : setting.Max.ToString(), Margin = new Thickness(0, 0, 0, 8) };
        var idxBox = new TextBox { Text = setting.Idx == 0 ? "0" : setting.Idx.ToString(), Margin = new Thickness(0, 0, 0, 8) };
        var aBox = new TextBox { Text = setting.A.ToString(), Margin = new Thickness(0, 0, 0, 8) };
        var bBox = new TextBox { Text = setting.B == 0 ? "1" : setting.B.ToString(), Margin = new Thickness(0, 0, 0, 8) };

        var hint = new TextBlock
        {
            Text = "number: одно число (Idx, Div, Max)\nnums_pct: процент A/B (A, B, Div)\ncpu: загрузка процессора (без команды)",
            Foreground = (IBrush)Avalonia.Application.Current.Resources["Muted"]!,
            TextWrapping = Avalonia.Media.TextWrapping.Wrap,
            Margin = new Thickness(0, 0, 0, 16),
        };

        var saveBtn = new Button { Content = "Сохранить", MinWidth = 100 };
        var cancelBtn = new Button { Content = "Отмена", MinWidth = 100 };

        var btnBar = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8, HorizontalAlignment = Avalonia.Layout.HorizontalAlignment.Right };
        btnBar.Children.Add(cancelBtn);
        btnBar.Children.Add(saveBtn);

        var root = new StackPanel { Spacing = 8, Margin = new Thickness(24) };
        root.Children.Add(new TextBlock { Text = "Название" });
        root.Children.Add(titleBox);
        root.Children.Add(new TextBlock { Text = "Тип показателя" });
        root.Children.Add(parseBox);
        root.Children.Add(new TextBlock { Text = "Команда (adb shell)" });
        root.Children.Add(cmdBox);
        root.Children.Add(new TextBlock { Text = "Единица измерения" });
        root.Children.Add(unitBox);
        root.Children.Add(new TextBlock { Text = "Делитель (Div)" });
        root.Children.Add(divBox);
        root.Children.Add(new TextBlock { Text = "Максимум (Max)" });
        root.Children.Add(maxBox);
        root.Children.Add(new TextBlock { Text = "Индекс (Idx)" });
        root.Children.Add(idxBox);
        root.Children.Add(new TextBlock { Text = "A (для nums_pct)" });
        root.Children.Add(aBox);
        root.Children.Add(new TextBlock { Text = "B (для nums_pct)" });
        root.Children.Add(bBox);
        root.Children.Add(hint);
        root.Children.Add(btnBar);

        var scroll = new ScrollViewer
        {
            Content = root,
            MaxHeight = 620,
        };

        win.Content = scroll;

        saveBtn.Click += (_, _) =>
        {
            setting.Title = titleBox.Text?.Trim() ?? "Виджет";
            setting.Cmd = cmdBox.Text?.Trim() ?? "";
            setting.Parse = parseBox.SelectedItem as string ?? "number";
            setting.Unit = unitBox.Text?.Trim() ?? "";
            setting.Div = double.TryParse(divBox.Text, out var d) ? d : 1;
            setting.Max = double.TryParse(maxBox.Text, out var m) ? m : 100;
            setting.Idx = int.TryParse(idxBox.Text, out var i) ? i : 0;
            setting.A = int.TryParse(aBox.Text, out var ai) ? ai : 0;
            setting.B = int.TryParse(bBox.Text, out var bi) ? bi : 1;

            if (isNew)
                Ctx.Settings.Cards.Add(setting);
            else
            {
                var idx = Ctx.Settings.Cards.FindIndex(c => c.Id == setting.Id);
                if (idx >= 0)
                    Ctx.Settings.Cards[idx] = setting;
            }

            Ctx.SaveSettings();
            Rebuild();
            win.Close();
        };

        cancelBtn.Click += (_, _) => win.Close();

        win.ShowDialog(GetMainWindow());
    }

    private void OnCardSelected(object? sender, SelectionChangedEventArgs e)
    {
        _selected = Cards.SelectedItem as CardItem;
        UpdateCommandButtons();
    }

    /// <summary>ПКМ по карточке выбирает её — меню «Изменить/Удалить» действует на неё.</summary>
    private void OnCardsPointerPressed(object? sender, PointerPressedEventArgs e)
    {
        if (!e.GetCurrentPoint(Cards).Properties.IsRightButtonPressed)
            return;

        var item = (e.Source as Visual)?.FindAncestorOfType<ListBoxItem>();
        if (item?.DataContext is CardItem card)
        {
            Cards.SelectedItem = card;
            SelectCard(card);
        }
        else
        {
            _selected = null;
            UpdateCommandButtons();
        }
    }

    private void DeleteCard(CardItem? item)
    {
        if (item is null) return;

        var setting = Ctx.Settings.Cards.FirstOrDefault(c => c.Id.ToString() == item.Id);
        if (setting is null) return;

        Ctx.Settings.Cards.Remove(setting);
        Ctx.SaveSettings();
        Rebuild();
        _selected = null;
        UpdateCommandButtons();
    }

    private static int NextId()
    {
        var max = 0;
        foreach (var c in Defaults.DefaultCards()) max = System.Math.Max(max, c.Id);
        return max + 1;
    }

    private static int ParseIndex(string parse) => parse switch
    {
        "number" => 0,
        "nums_pct" => 1,
        "cpu" => 2,
        _ => 0,
    };

    private Window GetMainWindow()
    {
        if (Avalonia.Application.Current.ApplicationLifetime is Avalonia.Controls.ApplicationLifetimes.IClassicDesktopStyleApplicationLifetime lifetime)
            return lifetime.MainWindow!;
        throw new InvalidOperationException("No main window");
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