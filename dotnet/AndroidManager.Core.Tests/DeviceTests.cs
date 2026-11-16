using AndroidManager.Core.Devices;
using Xunit;

namespace AndroidManager.Core.Tests;

public class DeviceTests
{
    [Fact]
    public void Parse_reads_device_and_unauthorized()
    {
        var text =
            "List of devices attached\n" +
            "192.168.1.5:5555\tdevice product:x\n" +
            "10.0.0.2:5555\tunauthorized usb:1\n";

        var (devices, unauthorized) = DeviceParser.Parse(text);

        Assert.Equal(new[] { "192.168.1.5:5555" }, devices);
        Assert.Equal(new[] { "10.0.0.2:5555" }, unauthorized);
    }

    [Fact]
    public void Parse_empty_output()
    {
        var (devices, unauthorized) = DeviceParser.Parse("");

        Assert.Empty(devices);
        Assert.Empty(unauthorized);
    }

    [Fact]
    public void Parse_skips_garbage_and_other_states()
    {
        var text = "List of devices attached\nabc\n192.168.1.5:5555 offline\n";

        var (devices, unauthorized) = DeviceParser.Parse(text);

        Assert.Empty(devices);
        Assert.Empty(unauthorized);
    }
}