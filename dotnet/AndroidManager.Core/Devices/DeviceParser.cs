namespace AndroidManager.Core.Devices;

/// <summary>Разбор <c>adb devices -l</c>: подключённые и неавторизованные.</summary>
public static class DeviceParser
{
    public static (List<string> Devices, List<string> Unauthorized) Parse(string output)
    {
        var devices = new List<string>();
        var unauthorized = new List<string>();

        foreach (var raw in output.Split('\n'))
        {
            var line = raw.Trim();
            if (line.Length == 0 || line.StartsWith("List of devices", StringComparison.Ordinal))
                continue;

            var parts = line.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length < 2)
                continue;

            if (parts[1] == "device")
                devices.Add(parts[0]);
            else if (parts[1] == "unauthorized")
                unauthorized.Add(parts[0]);
        }

        return (devices, unauthorized);
    }
}