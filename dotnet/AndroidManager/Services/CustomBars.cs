using AndroidManager.Core.Adb;
using AndroidManager.Core.Settings;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Interactivity;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Threading;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading.Tasks;

namespace AndroidManager.Services;

/// <summary>
/// Кастомные кнопки живут на своих вкладках, как в Python-версии:
/// console → Консоль, apps → Приложения, tools → Действия. Здесь — общий рендер, редактор и запуск.
/// </summary>
public static class CustomBars
{
    public const string PanelTools = "tools";
    public const string PanelApps = "apps";
    public const string PanelConsole = "console";

    public static readonly Dictionary<string, string> PanelTitles = new()
    {
        [PanelTools] = "Действия",
        [PanelApps] = "Приложения",
        [PanelConsole] = "Консоль",
    };

    /// <summary>Список кнопок панели, создаётся при необходимости.</summary>
    public static List<BarItem> Items(AppState ctx, string panel)
    {
        ctx.Settings.Bars ??= new();
        if (!ctx.Settings.Bars.TryGetValue(panel, out var list) || list is null)
            ctx.Settings.Bars[panel] = list = new();
        return list;
    }

    /// <summary>
    /// Кнопки панели плюс «+ Кнопка» в конце. ПКМ по кнопке — изменить/удалить/переставить.
    /// onChanged перерисовывает панель после правки.
    /// </summary>
    public static void Render(AppState ctx, string panel, Panel host, TopLevel? top, Action? onChanged, Action<BarItem>? onRun = null)
    {
        host.Children.Clear();
        var items = Items(ctx, panel);

        for (var idx = 0; idx < items.Count; idx++)
        {
            var item = items[idx];
            var i = idx;

            var btn = new Button
            {
                Content = item.Name,
                Margin = new Thickness(0, 0, 6, 6),
            };
            ToolTip.SetTip(btn, $"{item.Type}: {item.Cmd}");
            btn.Click += (_, _) =>
            {
                if (onRun is not null)
                    onRun(item);
                else
                    Run(ctx, item, top);
            };

            var menu = new ContextMenu();
            menu.Items.Add(new MenuItem { Header = "Изменить", Tag = i });
            menu.Items.Add(new MenuItem { Header = "Удалить", Tag = i });
            menu.Items.Add(new Separator());
            menu.Items.Add(new MenuItem { Header = "Сдвинуть влево", Tag = i });
            menu.Items.Add(new MenuItem { Header = "Сдвинуть вправо", Tag = i });

            void OnMenuItem(object? s, RoutedEventArgs e)
            {
                if (s is not MenuItem mi)
                    return;

                var id = (int)mi.Tag!;
                switch (mi.Header as string ?? "")
                {
                    case "Изменить": Edit(ctx, panel, id, top as Window, onChanged); break;
                    case "Удалить": Delete(ctx, panel, id, onChanged); break;
                    case "Сдвинуть влево": Move(ctx, panel, id, -1, onChanged); break;
                    case "Сдвинуть вправо": Move(ctx, panel, id, 1, onChanged); break;
                }
            }

            foreach (var mi in menu.Items.OfType<MenuItem>())
                mi.Click += OnMenuItem;

            btn.ContextMenu = menu;
            host.Children.Add(btn);
        }

        var add = new Button
        {
            Content = "+ Кнопка",
            Margin = new Thickness(0, 0, 6, 6),
            Classes = { "btn--ghost" },
        };
        ToolTip.SetTip(add, $"Создать свою кнопку на панели «{PanelTitles.GetValueOrDefault(panel, panel)}»");
        add.Click += (_, _) => Edit(ctx, panel, null, top as Window, onChanged);
        host.Children.Add(add);
    }

    /// <summary>Окно создания и правки кнопки.</summary>
    public static void Edit(AppState ctx, string panel, int? id, Window? owner, Action? onChanged)
    {
        var items = Items(ctx, panel);
        var editing = id.HasValue && id.Value >= 0 && id.Value < items.Count ? items[id.Value] : null;
        var isNew = editing == null;

        var win = new Window
        {
            Title = isNew
                ? $"Новая кнопка · {PanelTitles.GetValueOrDefault(panel, panel)}"
                : $"Изменить кнопку · {PanelTitles.GetValueOrDefault(panel, panel)}",
            Width = 600,
            Height = 400,
            CanResize = false,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
        };

        var nameBox = new TextBox { Text = editing?.Name ?? "", Watermark = "Например: Очистить logcat", Margin = new Thickness(0, 0, 0, 8) };
        var typeBox = new ComboBox { SelectedIndex = editing?.Type == "pc" ? 1 : 0, Margin = new Thickness(0, 0, 0, 8) };
        typeBox.Items.Add("shell");
        typeBox.Items.Add("pc");
        var cmdBox = new TextBox { Text = editing?.Cmd ?? "", Margin = new Thickness(0, 0, 0, 8) };

        var error = new TextBlock
        {
            Text = "Заполните название и команду",
            Foreground = new SolidColorBrush(Color.Parse("#F38BA8")),
            IsVisible = false,
            Margin = new Thickness(0, 0, 0, 8),
        };

        var hint = new TextBlock
        {
            Text = "shell — команда на устройстве (adb shell …), доступны {serial} и {clipboard}\npc — команда на ПК (cmd /c …)",
            Foreground = (IBrush?)Application.Current?.Resources["Muted"] ?? Brushes.Gray,
            TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(0, 0, 0, 16),
        };

        var saveBtn = new Button { Content = "Сохранить", MinWidth = 100 };
        var cancelBtn = new Button { Content = "Отмена", MinWidth = 100 };
        var deleteBtn = new Button { Content = "Удалить", MinWidth = 100, IsVisible = !isNew };

        var btnBar = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8, HorizontalAlignment = HorizontalAlignment.Right };
        btnBar.Children.Add(cancelBtn);
        if (!isNew)
            btnBar.Children.Add(deleteBtn);
        btnBar.Children.Add(saveBtn);

        var root = new StackPanel { Spacing = 6, Margin = new Thickness(24) };
        root.Children.Add(new TextBlock { Text = "Название" });
        root.Children.Add(nameBox);
        root.Children.Add(new TextBlock { Text = "Тип" });
        root.Children.Add(typeBox);
        root.Children.Add(new TextBlock { Text = "Команда" });
        root.Children.Add(cmdBox);
        root.Children.Add(hint);
        root.Children.Add(error);
        root.Children.Add(btnBar);
        win.Content = root;

        saveBtn.Click += (_, _) =>
        {
            var name = nameBox.Text?.Trim() ?? "";
            var cmd = cmdBox.Text?.Trim() ?? "";
            var type = typeBox.SelectedItem as string ?? "shell";

            if (name.Length == 0 || cmd.Length == 0)
            {
                error.IsVisible = true;
                return;
            }

            var barItem = new BarItem { Name = name, Cmd = cmd, Type = type };
            if (isNew)
                items.Add(barItem);
            else
                items[id!.Value] = barItem;

            ctx.SaveSettings();
            onChanged?.Invoke();
            win.Close();
        };

        cancelBtn.Click += (_, _) => win.Close();
        deleteBtn.Click += (_, _) =>
        {
            items.RemoveAt(id!.Value);
            ctx.SaveSettings();
            onChanged?.Invoke();
            win.Close();
        };

        if (owner is not null)
            win.ShowDialog(owner);
        else
            win.Show();
    }

    private static void Delete(AppState ctx, string panel, int id, Action? onChanged)
    {
        var items = Items(ctx, panel);
        if (id < 0 || id >= items.Count)
            return;

        items.RemoveAt(id);
        ctx.SaveSettings();
        onChanged?.Invoke();
    }

    private static void Move(AppState ctx, string panel, int id, int delta, Action? onChanged)
    {
        var items = Items(ctx, panel);
        var j = id + delta;
        if (id < 0 || id >= items.Count || j < 0 || j >= items.Count)
            return;

        (items[id], items[j]) = (items[j], items[id]);
        ctx.SaveSettings();
        onChanged?.Invoke();
    }

    /// <summary>Выполняет кнопку: shell-команда на устройстве или команда на ПК.</summary>
    public static void Run(AppState ctx, BarItem item, TopLevel? top)
    {
        var type = item.Type ?? "shell";
        var cmd = item.Cmd;

        if (type == "pc")
        {
            _ = Task.Run(() => ExecutePcCommand(ctx, cmd, item.Name));
            return;
        }

        var serial = ctx.Serial;
        if (string.IsNullOrEmpty(serial))
        {
            ctx.Log("Сначала подключите устройство");
            return;
        }

        string finalCmd;
        try
        {
            var clip = top?.Clipboard?.GetTextAsync().GetAwaiter().GetResult();
            finalCmd = cmd.Replace("{clipboard}", clip ?? "").Replace("{serial}", serial);
        }
        catch
        {
            finalCmd = cmd.Replace("{serial}", serial);
        }

        _ = Task.Run(() =>
        {
            var (rc, out_, err) = new AdbClient(ctx.AdbPath, serial, 60).Shell(finalCmd, 60);
            var answer = (out_ + err).Trim();
            Dispatcher.UIThread.Post(() =>
            {
                if (answer.Length > 0)
                    ctx.Log($"{item.Name}: {answer}");
                else if (rc == 0)
                    ctx.Log($"{item.Name}: выполнено");
                else
                    ctx.Log($"{item.Name}: ошибка rc={rc}");
            });
        });
    }

    /// <summary>Кнопка панели «Приложения» над выбранным списком: {pkg} подставляется на каждый пакет.</summary>
    public static void RunForPackages(AppState ctx, BarItem item, IReadOnlyList<string> packages, TopLevel? top)
    {
        var cmd = item.Cmd ?? "";
        var type = item.Type ?? "shell";

        if (!cmd.Contains("{pkg}"))
        {
            Run(ctx, item, top);
            return;
        }

        if (packages.Count == 0)
        {
            ctx.Log("Выберите хотя бы одно приложение");
            return;
        }

        var serial = ctx.Serial;
        if (type == "shell" && string.IsNullOrEmpty(serial))
        {
            ctx.Log("Сначала подключите устройство");
            return;
        }

        var clip = "";
        try
        {
            clip = top?.Clipboard?.GetTextAsync().GetAwaiter().GetResult() ?? "";
        }
        catch
        {
        }

        _ = Task.Run(() =>
        {
            var client = type == "shell" ? new AdbClient(ctx.AdbPath, serial!, 60) : null;

            foreach (var pkg in packages)
            {
                var finalCmd = cmd.Replace("{pkg}", pkg).Replace("{clipboard}", clip);

                if (client is null)
                {
                    ExecutePcCommand(ctx, finalCmd, $"{item.Name} · {pkg}");
                    continue;
                }

                var (rc, out_, err) = client.Shell(finalCmd.Replace("{serial}", serial!), 60);
                var answer = (out_ + err).Trim();
                var p = pkg;

                Dispatcher.UIThread.Post(() =>
                {
                    if (answer.Length > 0)
                        ctx.Log($"{item.Name} · {p}: {answer}");
                    else if (rc == 0)
                        ctx.Log($"{item.Name} · {p}: выполнено");
                    else
                        ctx.Log($"{item.Name} · {p}: ошибка rc={rc}");
                });
            }
        });
    }

    private static void ExecutePcCommand(AppState ctx, string cmd, string name)
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
            proc?.WaitForExit(30000);
            Dispatcher.UIThread.Post(() => ctx.Log($"{name}: выполнено на ПК"));
        }
        catch (Exception ex)
        {
            Dispatcher.UIThread.Post(() => ctx.Log($"{name}: ошибка на ПК — {ex.Message}"));
        }
    }
}
