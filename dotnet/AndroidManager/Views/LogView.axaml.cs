using AndroidManager.Services;
using Avalonia.Controls;
using Avalonia.Threading;
using System.Linq;

namespace AndroidManager.Views;

public partial class LogView : UserControl
{
    private AppState _ctx = null!;

    public LogView()
    {
        InitializeComponent();

        ClearBtn.Click += (_, _) => LogList.Items.Clear();
        CopyBtn.Click += (_, _) => CopyAll();
        TopBtn.Click += (_, _) => ScrollToTop();
        BottomBtn.Click += (_, _) => ScrollToBottom();

        Loaded += (_, _) =>
        {
            if (AutoScroll.IsChecked == true)
                ScrollToBottom();
        };
    }

    public void Attach(AppState ctx)
    {
        _ctx = ctx;
        _ctx.Logged += OnLogged;
    }

    private void OnLogged(string text)
    {
        // Метка времени как в Python-версии: [ЧЧ:ММ:СС]
        var stamp = DateTime.Now.ToString("HH:mm:ss");

        Dispatcher.UIThread.Post(() =>
        {
            LogList.Items.Add($"[{stamp}] {text}");
            if (AutoScroll.IsChecked == true)
                ScrollToBottom();
        });
    }

    private void ScrollToTop()
    {
        if (LogList.Items.Count > 0)
            LogList.ScrollIntoView(LogList.Items[0]);
    }

    private void ScrollToBottom()
    {
        if (LogList.Items.Count > 0)
            LogList.ScrollIntoView(LogList.Items[LogList.Items.Count - 1]);
    }

    private async void CopyAll()
    {
        var all = string.Join("\n", LogList.Items.OfType<string>());
        if (string.IsNullOrEmpty(all)) return;

        var top = TopLevel.GetTopLevel(this);
        if (top?.Clipboard is { } clip)
            await clip.SetTextAsync(all);
    }
}