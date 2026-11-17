using AndroidManager.Core.Adb;
using AndroidManager.Core.Settings;
using Avalonia.Controls;
using Avalonia.Threading;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading.Tasks;

namespace AndroidManager.Services;

/// <summary>
/// Кастомные кнопки: хранятся в settings.json по панелям и показываются на своих вкладках,
/// как в Python-версии (console → Консоль, apps → Приложения, tools → Действия).
/// </summary>
public static class CustomBars
{
    public const string PanelTools = "tools";
    public const string PanelApps = "apps";
    public const string PanelConsole = "console";

    /// <summary>Список кнопок панели, создаётся при необходимости.</summary>
    public static List<BarItem> Items(AppState ctx, string panel)
    {
        ctx.Settings.Bars ??= new();
        if (!ctx.Settings.Bars.TryGetValue(panel, out var list) || list is null)
            ctx.Settings.Bars[panel] = list = new();
        return list;
    }

    /// <summary>Раскладывает кнопки панели в контейнер вкладки. Возвращает количество.</summary>
    public static int Render(AppState ctx, string panel, Panel host, TopLevel? top)
    {
        host.Children.Clear();

        foreach (var item in Items(ctx, panel))
        {
            var btn = new Button
            {
                Content = item.Name,
                Margin = new Avalonia.Thickness(0, 0, 6, 6),
            };
            ToolTip.SetTip(btn, $"{item.Type}: {item.Cmd}");
            btn.Click += (_, _) => Run(ctx, item, top);
            host.Children.Add(btn);
        }

        return host.Children.Count;
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

        // {clipboard} и {serial} подставляются для shell-команд
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
