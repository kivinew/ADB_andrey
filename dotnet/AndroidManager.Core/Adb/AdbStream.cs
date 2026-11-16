using System.Diagnostics;
using System.Text;
using System.Threading.Channels;

namespace AndroidManager.Core.Adb;

/// <summary>
/// Запущенный процесс с построчным выводом: строки читаются в фоне и падают в канал.
/// Если потребитель не успевает, старые строки отбрасываются — очередь не растёт.
/// </summary>
public sealed class AdbStream : IDisposable
{
    private const int QueueSize = 5000;

    private readonly Process _process;
    private readonly Channel<string> _channel;
    private readonly CancellationTokenSource _stop = new();
    private bool _disposed;

    public int Id => _process.Id;
    public ChannelReader<string> Lines => _channel.Reader;

    /// <summary>Чтение завершено: процесс закрыл поток или его погасили.</summary>
    public bool IsFinished => _channel.Reader.Completion.IsCompleted;

    private AdbStream(Process process, Channel<string> channel)
    {
        _process = process;
        _channel = channel;
    }

    /// <summary>Запуск процесса. <paramref name="args"/> — полная командная строка,
    /// включая путь к adb: <c>adb -s &lt;serial&gt; logcat</c>.</summary>
    public static AdbStream Start(string[] args)
    {
        if (args.Length == 0)
            throw new ArgumentException("Пустой список аргументов", nameof(args));

        var psi = new ProcessStartInfo
        {
            FileName = args[0],
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };

        for (var i = 1; i < args.Length; i++)
            psi.ArgumentList.Add(args[i]);

        var proc = Process.Start(psi)
            ?? throw new InvalidOperationException($"Не удалось запустить процесс: {args[0]}");

        var channel = Channel.CreateBounded<string>(new BoundedChannelOptions(QueueSize)
        {
            FullMode = BoundedChannelFullMode.DropOldest,
            SingleWriter = true,
            SingleReader = true,
        });

        var stream = new AdbStream(proc, channel);
        stream.Pump();
        return stream;
    }

    private void Pump()
    {
        _ = Task.Run(async () =>
        {
            try
            {
                while (!_stop.IsCancellationRequested)
                {
                    var line = await _process.StandardOutput.ReadLineAsync()
                        .WaitAsync(_stop.Token)
                        .ConfigureAwait(false);

                    if (line is null)
                        break;

                    _channel.Writer.TryWrite(line);
                }
            }
            catch (OperationCanceledException)
            {
            }
            catch
            {
                // adb закрыл поток или процесс исчез — просто завершаем чтение.
            }

            _channel.Writer.TryComplete();
        });
    }

    /// <summary>Остановка: сначала гасим дерево процессов, только потом закрываем канал.</summary>
    public void Stop()
    {
        ProcessKill.KillTree(_process);
        _channel.Writer.TryComplete();
    }

    public void Dispose()
    {
        if (_disposed)
            return;

        _disposed = true;
        Stop();

        try
        {
            _stop.Cancel();
        }
        catch
        {
            // Уже отменён.
        }

        _process.Dispose();
        _stop.Dispose();
    }
}