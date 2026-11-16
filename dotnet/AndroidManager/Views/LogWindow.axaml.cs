using AndroidManager.Services;
using Avalonia.Controls;
using Avalonia.Threading;

namespace AndroidManager.Views;

public partial class LogWindow : Window
{
    private readonly AppState _ctx;
    private bool _closing;

    public LogWindow()
    {
        InitializeComponent();
    }

    public LogWindow(AppState ctx) : this()
    {
        _ctx = ctx;

        ClearBtn.Click += (_, _) =>
        {
            LogList.Items.Clear();
        };

        CloseBtn.Click += (_, _) => Close();

        Closing += (_, _) =>
        {
            _closing = true;
            _ctx.Logged -= OnLogged;
        };

        // Подписываемся на новые логи и показываем существующие, если есть.
        _ctx.Logged += OnLogged;
    }

    private void OnLogged(string text)
    {
        if (_closing) return;

        Dispatcher.UIThread.Post(() =>
        {
            LogList.Items.Add(text);
            // Автоскролл вниз к последнему элементу.
            if (LogList.Items.Count > 0)
                LogList.ScrollIntoView(LogList.Items[LogList.Items.Count - 1]);
        });
    }
}
