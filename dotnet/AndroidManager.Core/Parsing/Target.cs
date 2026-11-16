using System.Net;
using System.Net.Sockets;

namespace AndroidManager.Core.Parsing;

/// <summary>Адрес подключения и определение IP этого ПК.</summary>
public static class TargetParser
{
    /// <summary>Вытаскивает порт из "host:port", если порт — число. Пробелы убираются.</summary>
    public static (string Host, string Port) SplitTarget(string host, string port)
    {
        var h = host.Trim().Replace(" ", "");

        var idx = h.LastIndexOf(':');
        if (idx >= 0)
        {
            var tail = h[(idx + 1)..];
            if (tail.Length > 0 && tail.All(char.IsDigit))
            {
                h = h[..idx];
                port = tail;
            }
        }

        return (h, port);
    }

    /// <summary>IP этого ПК в локальной сети: UDP-сокет к 8.8.8.8 без отправки пакетов.</summary>
    public static string DetectPcIp()
    {
        try
        {
            using var s = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, ProtocolType.Udp);
            s.Connect("8.8.8.8", 80);
            return s.LocalEndPoint is IPEndPoint ep ? ep.Address.ToString() : "127.0.0.1";
        }
        catch (Exception)
        {
            return "127.0.0.1";
        }
    }
}