using AndroidManager.Core.Adb;
using AndroidManager.Core.Parsing;
using AndroidManager.Core.Settings;
using AndroidManager.Services;
using Avalonia.Controls;
using Avalonia.Input;
using System.Net;

namespace AndroidManager.Views;

public partial class ConnectionView : UserControl
{
    public AppState Ctx { get; set; } = null!;

    /// <summary>Список устройств изменился — главное окно должно его перечитать.</summary>
    public event Action? DevicesChanged;

    /// <summary>Пользователь выбрал устройство из списка.</summary>
    public event Action<string>? DeviceSelected;

    private bool _loading;

    public ConnectionView()
    {
        InitializeComponent();

        ConnectBtn.Click += (_, _) => _ = ToggleConnectionAsync();
        PairBtn.Click += (_, _) => _ = PairAsync();
        FavAddBtn.Click += (_, _) => AddFavorite();
        RefreshBtn.Click += (_, _) => DevicesChanged?.Invoke();

        HistoryBox.SelectionChanged += (_, _) => PickHistory();
        FavBox.SelectionChanged += (_, _) => PickFavorite();
        DeviceBox.SelectionChanged += (_, _) =>
        {
            if (DeviceBox.SelectedItem is string serial)
                DeviceSelected?.Invoke(serial);
        };

        DeviceBox.KeyDown += (_, e) =>
        {
            if (e.Key == Key.Enter)
            {
                var text = DeviceBox.Text?.Trim();
                if (text.Length > 0)
                    DeviceSelected?.Invoke(text);
            }
        };

        Loaded += (_, _) =>
        {
            LoadLists();
            UpdateConnectButton();
        };
    }

    private void LoadLists()
    {
        _loading = true;

        try
        {
            Ctx.Settings.History ??= new();
            Ctx.Settings.Favorites ??= new();

            HistoryBox.ItemsSource = Ctx.Settings.History.ToList();
            FavBox.ItemsSource = Ctx.Settings.Favorites.Select(f => f.Name).ToList();
            HostBox.Text = Ctx.Settings.Host;
            PortBox.Text = Ctx.Settings.Port;
        }
        finally
        {
            _loading = false;
        }
    }

    private void SaveHost()
    {
        if (_loading)
            return;

        Ctx.Settings.Host = HostBox.Text?.Trim() ?? "";
        Ctx.Settings.Port = PortBox.Text?.Trim() ?? "";
        Ctx.SaveSettings();
    }

    private void Remember(string target)
    {
        var history = Ctx.Settings.History;
        history.RemoveAll(h => h == target);
        history.Insert(0, target);

        if (history.Count > 10)
            history.RemoveRange(10, history.Count - 10);

        Ctx.SaveSettings();

        _loading = true;
        HistoryBox.ItemsSource = history.ToList();
        _loading = false;
    }

    private void PickHistory()
    {
        if (_loading || HistoryBox.SelectedItem is not string target)
            return;

        var (host, port) = TargetParser.SplitTarget(target, "5555");
        HostBox.Text = host;
        PortBox.Text = port;
        SaveHost();
    }

    private void PickFavorite()
    {
        if (_loading || FavBox.SelectedItem is not string name)
            return;

        var fav = Ctx.Settings.Favorites.FirstOrDefault(f => f.Name == name);
        if (fav is null)
            return;

        HostBox.Text = fav.Host;
        PortBox.Text = fav.Port;
        SaveHost();
    }

    private void AddFavorite()
    {
        var host = HostBox.Text?.Trim() ?? "";
        var port = PortBox.Text?.Trim() ?? "";

        if (host.Length == 0)
        {
            Ctx.Log("Введите адрес для избранного");
            return;
        }

        var name = $"{host}:{port}";
        Ctx.Settings.Favorites.RemoveAll(f => f.Name == name);
        Ctx.Settings.Favorites.Add(new Favorite { Name = name, Host = host, Port = port });
        Ctx.SaveSettings();

        _loading = true;
        FavBox.ItemsSource = Ctx.Settings.Favorites.Select(f => f.Name).ToList();
        _loading = false;

        Ctx.Log($"В избранное: {name}");
    }

    private void UpdateConnectButton()
    {
        var connected = !string.IsNullOrEmpty(Ctx.Serial);
        ConnectBtn.Content = connected ? "ОТКЛЮЧИТЬ" : "ПОДКЛЮЧИТЬ";
    }

    private async Task ToggleConnectionAsync()
    {
        if (!string.IsNullOrEmpty(Ctx.Serial) && Ctx.Serial.Contains(':'))
        {
            await DisconnectAsync();
            return;
        }

        await ConnectAsync();
    }

    private async Task ConnectAsync()
    {
        var host = HostBox.Text?.Trim() ?? "";
        var port = PortBox.Text?.Trim() ?? "";

        if (host.Length == 0)
        {
            Ctx.Log("Введите IP или URL, например 192.168.1.10");
            return;
        }

        if (!int.TryParse(port, out var portNumber) || portNumber is < 1 or > 65535)
        {
            Ctx.Log($"Некорректный порт: «{port}». Введите число от 1 до 65535");
            return;
        }

        ConnectBtn.IsEnabled = false;
        var target = $"{host}:{port}";

        try
        {
            Ctx.Log($"adb путь: {Ctx.AdbPath}");

            // Разрешаем имя хоста в IP, как в Python-версии (adb connect не всегда справляется с DNS-именами).
            var ip = host;
            try
            {
                if (!IPAddress.TryParse(host, out var _))
                {
                    var entry = Dns.GetHostEntry(host);
                    ip = entry.AddressList[0].ToString();
                }
            }
            catch
            {
                // Если не удалось разрешить — оставляем как есть, adb сам сообщит об ошибке.
            }

            target = $"{ip}:{port}";
            Ctx.Log($"Подключение к {target}...");

            var (rc, stdout, stderr) = await Task.Run(() =>
                new AdbClient(Ctx.AdbPath, null, 20).Run("connect", target));

            var answer = (stdout + stderr).Trim();
            Ctx.Log($"adb connect rc={rc}, out={answer}");

            if (rc == AdbRunner.NotFound)
            {
                Ctx.Log($"adb не найден по пути: {Ctx.AdbPath}");
                return;
            }

            if (rc != 0 || answer.Contains("cannot", StringComparison.OrdinalIgnoreCase)
                || answer.Contains("failed", StringComparison.OrdinalIgnoreCase)
                || answer.Contains("unable", StringComparison.OrdinalIgnoreCase))
                return;

            Remember(target);
            DevicesChanged?.Invoke();
        }
        catch (Exception ex)
        {
            Ctx.Log($"Не удалось подключиться: {ex.Message}");
        }
        finally
        {
            ConnectBtn.IsEnabled = true;
            UpdateConnectButton();
        }
    }

    private async Task DisconnectAsync()
    {
        var serial = Ctx.Serial;

        if (string.IsNullOrEmpty(serial) || !serial.Contains(':'))
        {
            Ctx.Log("Отключать можно только сетевое подключение (IP:порт)");
            return;
        }

        var (rc, stdout, stderr) = await Task.Run(() =>
            new AdbClient(Ctx.AdbPath, null, 15).Run("disconnect", serial));

        if (rc == AdbRunner.NotFound)
        {
            Ctx.Log($"adb не найден по пути: {Ctx.AdbPath}");
            return;
        }

        var answer = (stdout + stderr).Trim();
        Ctx.Log(answer.Length == 0 ? "Отключено" : answer);
        DevicesChanged?.Invoke();
        UpdateConnectButton();
    }

    private async Task PairAsync()
    {
        var request = await UiDialogs.Pair(TopLevel.GetTopLevel(this) as Window);

        if (request is null || request.Address.Length == 0 || request.Code.Length == 0)
            return;

        var target = $"{request.Address}:{request.Port}";

        var (rc, stdout, stderr) = await Task.Run(() =>
            new AdbClient(Ctx.AdbPath, null, 60).Run("pair", target, request.Code));

        if (rc == AdbRunner.NotFound)
        {
            Ctx.Log($"adb не найден по пути: {Ctx.AdbPath}");
            return;
        }

        var answer = (stdout + stderr).Trim();
        Ctx.Log(answer.Length == 0 ? "Сопряжение выполнено" : answer);
    }

    /// <summary>Обновить список устройств в выпадающем списке.</summary>
    public void SetDevices(List<string> devices, List<string> unauthorized)
    {
        DeviceBox.ItemsSource = devices;

        if (devices.Count == 0)
        {
            DeviceBox.SelectedIndex = -1;
            ShowNoDevice();
        }
        else
        {
            var keep = devices[0];
            DeviceBox.SelectedItem = keep;
        }

        UpdateConnectButton();

        if (unauthorized.Count > 0)
            Ctx.Log("Подтвердите отладку на экране устройства: " + string.Join(", ", unauthorized));
    }

    /// <summary>Программно выбрать устройство.</summary>
    public void SelectDevice(string serial)
    {
        DeviceBox.SelectedItem = serial;
        UpdateConnectButton();
    }

    public void ShowDevice(string model, string release, string sdk, int totalMb, int availableMb)
    {
        InfoTitle.Text = $"{model} · Android {release} (SDK {sdk})";
        InfoText.Text = $"Оперативная память: {totalMb - availableMb} из {totalMb} МБ занято";
    }

    public void ShowNoDevice()
    {
        InfoTitle.Text = "Устройство не выбрано";
        InfoText.Text = "Выберите устройство в списке сверху или подключитесь по IP:порт.";
        UpdateConnectButton();
    }
}