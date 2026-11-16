using AndroidManager.Core.Adb;
using AndroidManager.Core.Parsing;
using AndroidManager.Services;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Threading;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace AndroidManager.Views;

public partial class ProcsView : UserControl
{
    private const int RefreshIntervalMs = 3000;

    private readonly DispatcherTimer _autoTimer = new() { Interval = TimeSpan.FromMilliseconds(RefreshIntervalMs) };
    private List<ProcRow> _rows = new();
    private string _sortKey = "cpu";
    private bool _sortRev = true;
    private bool _busy;

    public AppState Ctx { get; set; } = null!;

    public ProcsView()
    {
        InitializeComponent();

        BtnSortCpu.Click += (_, _) => SetSort("cpu");
        BtnSortMem.Click += (_, _) => SetSort("mem");
        BtnSortName.Click += (_, _) => SetSort("name");
        BtnSortPid.Click += (_, _) => SetSort("pid");

        FilterBox.TextChanged += (_, _) => Fill();
        AutoCheck.IsCheckedChanged += (_, _) => _autoTimer.IsEnabled = AutoCheck.IsChecked == true;
        _autoTimer.Tick += (_, _) => { if (!string.IsNullOrEmpty(Ctx.Serial)) Refresh(); };

        BtnRefresh.Click += (_, _) => Refresh();
        BtnCopy.Click += (_, _) => CopySelected();
        BtnKill.Click += (_, _) => KillSelected();

        ProcList.SelectionChanged += (_, _) => { };
    }

    public void OnDeviceChanged()
    {
        _rows.Clear();
        ProcList.ItemsSource = null;
        ProcCount.Text = "Процессы не загружены";
        _autoTimer.IsEnabled = false;
    }

    private void SetSort(string key)
    {
        if (_sortKey == key)
            _sortRev = !_sortRev;
        else
        {
            _sortKey = key;
            _sortRev = key is "cpu" or "mem";
        }
        Fill();
    }

    public void Refresh()
    {
        if (_busy || string.IsNullOrEmpty(Ctx.Serial))
            return;

        _busy = true;
        ProcCount.Text = "Процессы загружаются...";

        _ = Task.Run(() =>
        {
            var client = new AdbClient(Ctx.AdbPath, Ctx.Serial, 90);
            var (_, stdout, _) = client.Shell(ProcParser.ProcCmd, 90);
            return ProcParser.ParseProcOutput(stdout);
        }).ContinueWith(t =>
        {
            _busy = false;
            if (t.IsFaulted || t.IsCanceled)
            {
                ProcCount.Text = $"Ошибка: {t.Exception?.InnerException?.Message ?? "отменено"}";
                return;
            }

            _rows = t.Result ?? new();
            Dispatcher.UIThread.Post(Fill);
        }, TaskScheduler.FromCurrentSynchronizationContext());
    }

    private void Fill()
    {
        var query = FilterBox.Text?.Trim().ToLowerInvariant() ?? "";
        var filtered = _rows.Where(r => string.IsNullOrEmpty(query) || r.Name.ToLowerInvariant().Contains(query)).ToList();

        var keyFunc = _sortKey switch
        {
            "mem" => (Func<ProcRow, object>)(r => r.Mem),
            "name" => (Func<ProcRow, object>)(r => r.Name.ToLowerInvariant()),
            "pid" => (Func<ProcRow, object>)(r =>
            {
                var p = int.TryParse(r.Pid, out var n) ? n : 0;
                return (double)p;
            }),
            _ => (Func<ProcRow, object>)(r => r.Cpu),
        };

        var sorted = _sortRev ? filtered.OrderByDescending(keyFunc).ToList() : filtered.OrderBy(keyFunc).ToList();

        ProcList.ItemsSource = null;
        ProcList.ItemsSource = sorted.Select(r => new
        {
            r.Pid,
            r.Name,
            Mem = $"{r.Mem:F1} МБ",
            Cpu = $"{r.Cpu:F1}%",
            r.State,
        }).ToList();

        ProcCount.Text = $"Процессов: {_rows.Count} (показано {sorted.Count})";
    }

    private void CopySelected()
    {
        var sel = ProcList.SelectedItems;
        if (sel == null || sel.Count == 0)
        {
            Ctx.Log("Выберите процессы в списке");
            return;
        }

        var lines = sel.Cast<dynamic>().Select(r => $"{r.Pid}\t{r.Name}\t{r.Mem}\tCPU {r.Cpu}");
        var text = string.Join("\n", lines);
        TopLevel.GetTopLevel(this)!.Clipboard.SetTextAsync(text);
        Ctx.Log($"Скопировано процессов: {sel.Count}");
    }

    private async void KillSelected()
    {
        var serial = Ctx.Serial;
        if (string.IsNullOrEmpty(serial))
        {
            Ctx.Log("Выберите процессы в списке");
            return;
        }

        var sel = ProcList.SelectedItems;
        if (sel == null || sel.Count == 0)
        {
            Ctx.Log("Выберите процессы в списке");
            return;
        }

        var pids = sel.Cast<dynamic>().Select(r => (string)r.Pid).ToList();
        var cmd = "kill -9 " + string.Join(" ", pids);

        try
        {
            var (rc, out_, err) = await Task.Run(() => new AdbClient(Ctx.AdbPath, serial, 30).Shell(cmd, 30));
            if (rc == 0)
                Ctx.Log($"Завершено процессов: {pids.Count}");
            else
                Ctx.Log($"Ошибка завершения: {err.Trim() ?? out_.Trim()}");
        }
        catch (Exception ex)
        {
            Ctx.Log($"Ошибка завершения: {ex.Message}");
        }

        Refresh();
    }
}