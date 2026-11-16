namespace AndroidManager.Core.Adb;

/// <summary>adb с привязкой к устройству: <c>adb -s &lt;serial&gt; ...</c>.</summary>
public sealed class AdbClient
{
    private readonly string _adbPath;
    private readonly string? _serial;
    private readonly int _timeoutSeconds;

    public AdbClient(string adbPath, string? serial = null, int timeoutSeconds = 30)
    {
        _adbPath = adbPath;
        _serial = serial;
        _timeoutSeconds = timeoutSeconds;
    }

    public (int rc, string stdout, string stderr) Run(params string[] args)
        => AdbRunner.Run(Compose(args), _timeoutSeconds);

    public (int rc, string stdout, string stderr) Shell(string command, int timeoutSeconds = 120)
        => AdbRunner.Run(Compose(["shell", command]), timeoutSeconds);

    private string[] Compose(string[] args)
    {
        var full = new List<string>(args.Length + 3) { _adbPath };

        if (!string.IsNullOrEmpty(_serial))
        {
            full.Add("-s");
            full.Add(_serial);
        }

        full.AddRange(args);
        return full.ToArray();
    }
}