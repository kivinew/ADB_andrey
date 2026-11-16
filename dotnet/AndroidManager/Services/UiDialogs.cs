using Avalonia;
using Avalonia.Controls;
using Avalonia.Layout;
using Avalonia.Media;

namespace AndroidManager.Services;

/// <summary>Пара для сопряжения по Wi-Fi.</summary>
public sealed record PairRequest(string Address, string Port, string Code);

/// <summary>Диалоги, которых нет в Avalonia из коробки.</summary>
public static class UiDialogs
{
    /// <summary>«Да / Нет». Закрытое окно — это «Нет».</summary>
    public static Task<bool> Confirm(Window? owner, string title, string message)
    {
        var tcs = new TaskCompletionSource<bool>();
        var root = new StackPanel { Margin = new Thickness(16), Spacing = 14 };

        root.Children.Add(new TextBlock
        {
            Text = message,
            TextWrapping = TextWrapping.Wrap,
        });

        var bar = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 8,
            HorizontalAlignment = HorizontalAlignment.Right,
        };

        var yes = new Button { Content = "Да", MinWidth = 90 };
        var no = new Button { Content = "Нет", MinWidth = 90 };
        bar.Children.Add(no);
        bar.Children.Add(yes);
        root.Children.Add(bar);

        var win = new Window
        {
            Title = title,
            Width = 440,
            SizeToContent = SizeToContent.Height,
            CanResize = false,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
            Content = root,
        };

        yes.Click += (_, _) =>
        {
            tcs.TrySetResult(true);
            win.Close();
        };

        no.Click += (_, _) =>
        {
            tcs.TrySetResult(false);
            win.Close();
        };

        win.Closed += (_, _) => tcs.TrySetResult(false);

        if (owner is null)
            win.Show();
        else
            win.ShowDialog(owner);

        return tcs.Task;
    }

    /// <summary>Три поля: адрес, порт сопряжения, код. Отмена — null.</summary>
    public static Task<PairRequest?> Pair(Window? owner)
    {
        var tcs = new TaskCompletionSource<PairRequest?>();
        var root = new StackPanel { Margin = new Thickness(16), Spacing = 8 };

        var address = Field(root, "Адрес", "192.168.1.10");
        var port = Field(root, "Порт сопряжения", "");
        var code = Field(root, "Код", "");

        var bar = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 8,
            HorizontalAlignment = HorizontalAlignment.Right,
        };

        var cancel = new Button { Content = "Отмена", MinWidth = 90 };
        var ok = new Button { Content = "Сопрячь", MinWidth = 90 };
        bar.Children.Add(cancel);
        bar.Children.Add(ok);
        root.Children.Add(bar);

        var win = new Window
        {
            Title = "Сопряжение",
            Width = 420,
            SizeToContent = SizeToContent.Height,
            CanResize = false,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
            Content = root,
        };

        ok.Click += (_, _) =>
        {
            tcs.TrySetResult(new PairRequest(address.Text?.Trim() ?? "", port.Text?.Trim() ?? "", code.Text?.Trim() ?? ""));
            win.Close();
        };

        cancel.Click += (_, _) =>
        {
            tcs.TrySetResult(null);
            win.Close();
        };

        win.Closed += (_, _) => tcs.TrySetResult(null);

        if (owner is null)
            win.Show();
        else
            win.ShowDialog(owner);

        return tcs.Task;
    }

    private static TextBox Field(Panel parent, string label, string hint)
    {
        parent.Children.Add(new TextBlock { Text = hint.Length == 0 ? label : $"{label} ({hint})" });

        var box = new TextBox
        {
            MinWidth = 260,
            HorizontalAlignment = HorizontalAlignment.Stretch,
        };

        parent.Children.Add(box);
        return box;
    }
}