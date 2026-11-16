using AndroidManager.Core.Adb;
using AndroidManager.Core.Settings;
using AndroidManager.Services;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Interactivity;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Threading;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Threading.Tasks;

namespace AndroidManager.Views;

public partial class BarsView : UserControl
{
    private const string PanelTools = "tools";
    private const string PanelApps = "apps";
    private const string PanelScripts = "scripts";
    private const string PanelConsole = "console";

    private static readonly string[] PanelNames = { PanelTools, PanelApps, PanelScripts, PanelConsole };
    private static readonly string[] PanelTitles = { "Инструменты", "Приложения", "Скрипты", "Консоль" };

    private string _currentPanel = PanelTools;

    public AppState Ctx { get; set; } = null!;

    public BarsView()
    {
        InitializeComponent();

        for (var i = 0; i < PanelNames.Length; i++)
            BarBox.Items.Add(PanelTitles[i]);

        BarBox.SelectedIndex = 0;
        BarBox.SelectionChanged += (_, _) =>
        {
            if (Ctx is null) return;
            var idx = BarBox.SelectedIndex;
            if (idx < 0 || idx >= PanelNames.Length) return;
            _currentPanel = PanelNames[idx];
            Render();
        };

        BtnAdd.Click += (_, _) => EditButton(null);
    }

    public void RefreshBars()
    {
        Render();
    }

    /// <summary>Возвращает список кнопок панели, создавая его при необходимости.</summary>
    private List<BarItem> GetPanelItems()
    {
        if (Ctx is null || Ctx.Settings.Bars is null)
            return new();
        if (!Ctx.Settings.Bars.ContainsKey(_currentPanel))
            Ctx.Settings.Bars[_currentPanel] = new();
        return Ctx.Settings.Bars[_currentPanel];
    }

    private void Render()
    {
        ButtonPanel.Children.Clear();

        var items = GetPanelItems();

        foreach (var (item, idx) in items.Select((it, i) => (it, i)))
        {
            var btn = new Button
            {
                Content = item.Name,
                Width = 150,
                Height = 80,
                Margin = new Thickness(6),
                Tag = idx,
            };

            btn.Click += (_, _) => ExecuteButton(item);

            var menu = new ContextMenu();
            menu.Items.Add(new MenuItem { Header = "Изменить", Tag = idx });
            menu.Items.Add(new MenuItem { Header = "Удалить", Tag = idx });
            menu.Items.Add(new Separator());
            menu.Items.Add(new MenuItem { Header = "Сдвинуть влево", Tag = idx });
            menu.Items.Add(new MenuItem { Header = "Сдвинуть вправо", Tag = idx });

            void OnMenuItem(object s, RoutedEventArgs e)
            {
                if (s is not MenuItem mi) return;
                var id = (int)mi.Tag!;
                var header = mi.Header as string ?? "";
                switch (header)
                {
                    case "Изменить": EditButton(id); break;
                    case "Удалить": DeleteButton(id); break;
                    case "Сдвинуть влево": MoveButton(id, -1); break;
                    case "Сдвинуть вправо": MoveButton(id, 1); break;
                }
            }

            foreach (var mi in menu.Items.OfType<MenuItem>())
                mi.Click += OnMenuItem;

            btn.ContextMenu = menu;
            ButtonPanel.Children.Add(btn);
        }
    }

    private void ExecuteButton(BarItem item)
    {
        var type = item.Type ?? "shell";
        var cmd = item.Cmd;

        if (type == "pc")
        {
            _ = Task.Run(() => ExecutePcCommand(cmd, item.Name));
            return;
        }

        var serial = Ctx?.Serial;
        if (string.IsNullOrEmpty(serial))
        {
            Ctx?.Log("Сначала подключите устройство");
            return;
        }

        // Подставляем {clipboard} и {serial} для shell-команд
        string finalCmd;
        try
        {
            var clip = TopLevel.GetTopLevel(this)!.Clipboard.GetTextAsync().GetAwaiter().GetResult();
            finalCmd = cmd.Replace("{clipboard}", clip ?? "").Replace("{serial}", serial);
        }
        catch
        {
            finalCmd = cmd.Replace("{serial}", serial);
        }

        _ = Task.Run(() =>
        {
            var (rc, out_, err) = new AdbClient(Ctx.AdbPath, serial, 60).Shell(finalCmd, 60);
            var answer = (out_ + err).Trim();
            Dispatcher.UIThread.Post(() =>
            {
                if (answer.Length > 0)
                    Ctx.Log($"{item.Name}: {answer}");
                else if (rc == 0)
                    Ctx.Log($"{item.Name}: выполнено");
                else
                    Ctx.Log($"{item.Name}: ошибка rc={rc}");
            });
        });
    }

    private static void ExecutePcCommand(string cmd, string name)
    {
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = "cmd.exe",
                Arguments = "/c " + cmd,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            };
            using var proc = Process.Start(psi);
            if (proc == null) return;
            proc.WaitForExit(30000);
        }
        catch (Exception ex)
        {
            // Логирование через Ctx невозможно из статического метода; игнорируем.
        }
    }

    private void EditButton(int? id)
    {
        var items = GetPanelItems();
        var editing = id.HasValue && id.Value >= 0 && id.Value < items.Count ? items[id.Value] : null;
        var isNew = editing == null;

        var win = new Window
        {
            Title = isNew ? "Новая кнопка" : "Изменить кнопку",
            Width = 600,
            Height = 400,
            CanResize = false,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
        };

        var nameBox = new TextBox { Text = editing?.Name ?? "Новая кнопка", Margin = new Thickness(0, 0, 0, 8) };
        var typeBox = new ComboBox
        {
            SelectedIndex = (editing?.Type == "pc" ? 1 : 0),
            Margin = new Thickness(0, 0, 0, 8),
        };
        typeBox.Items.Add("shell");
        typeBox.Items.Add("pc");
        var cmdBox = new TextBox { Text = editing?.Cmd ?? "", Margin = new Thickness(0, 0, 0, 8) };

        var hint = new TextBlock
        {
            Text = "shell: команда в shell устройства (adb shell ...)\npc: команда на ПК, {clipboard} и {serial} подставятся",
            Foreground = (IBrush)Avalonia.Application.Current.Resources["Muted"]!,
            TextWrapping = Avalonia.Media.TextWrapping.Wrap,
            Margin = new Thickness(0, 0, 0, 16),
        };

        var saveBtn = new Button { Content = "Сохранить", MinWidth = 100 };
        var cancelBtn = new Button { Content = "Отмена", MinWidth = 100 };
        var deleteBtn = new Button { Content = "Удалить", MinWidth = 100, IsVisible = !isNew };

        var btnBar = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8, HorizontalAlignment = Avalonia.Layout.HorizontalAlignment.Right };
        btnBar.Children.Add(cancelBtn);
        if (!isNew) btnBar.Children.Add(deleteBtn);
        btnBar.Children.Add(saveBtn);

        var root = new StackPanel { Spacing = 8, Margin = new Thickness(24) };
        root.Children.Add(new TextBlock { Text = "Название" });
        root.Children.Add(nameBox);
        root.Children.Add(new TextBlock { Text = "Тип" });
        root.Children.Add(typeBox);
        root.Children.Add(new TextBlock { Text = "Команда" });
        root.Children.Add(cmdBox);
        root.Children.Add(hint);
        root.Children.Add(btnBar);

        win.Content = root;

        saveBtn.Click += (_, _) =>
        {
            if (Ctx is null) { win.Close(); return; }

            var name = nameBox.Text?.Trim();
            var cmd = cmdBox.Text?.Trim() ?? "";
            var type = typeBox.SelectedItem as string ?? "shell";

            if (string.IsNullOrEmpty(name) || string.IsNullOrEmpty(cmd))
                return;

            var barItem = new BarItem { Name = name, Cmd = cmd, Type = type };
            var items = GetPanelItems();
            if (isNew)
                items.Add(barItem);
            else
                items[id!.Value] = barItem;

            Ctx.SaveSettings();
            Render();
            win.Close();
        };

        cancelBtn.Click += (_, _) => win.Close();

        deleteBtn.Click += (_, _) =>
        {
            if (Ctx is null) { win.Close(); return; }

            var items = GetPanelItems();
            items.RemoveAt(id!.Value);
            Ctx.SaveSettings();
            Render();
            win.Close();
        };

        win.ShowDialog(GetMainWindow());
    }

    private void DeleteButton(int id)
    {
        if (Ctx is null) return;
        GetPanelItems().RemoveAt(id);
        Ctx.SaveSettings();
        Render();
    }

    private static Window GetMainWindow()
    {
        if (Avalonia.Application.Current.ApplicationLifetime is Avalonia.Controls.ApplicationLifetimes.IClassicDesktopStyleApplicationLifetime lifetime)
            return lifetime.MainWindow!;
        throw new InvalidOperationException("No main window");
    }

    private void MoveButton(int id, int delta)
    {
        if (Ctx is null) return;
        var items = GetPanelItems();
        var j = id + delta;
        if (j < 0 || j >= items.Count) return;
        (items[id], items[j]) = (items[j], items[id]);
        Ctx.SaveSettings();
        Render();
    }
}