using System;
using System.Runtime.InteropServices;
using System.Text.Json;

class Program
{
    const string Dll = @"C:\Program Files (x86)\Gigabyte\OSDSidekick\AORUS\RtHIDLib.dll";

    [DllImport(Dll, CallingConvention = CallingConvention.Cdecl)]
    static extern int Open_HID(ushort vendor_id, ushort product_id);

    [DllImport(Dll, CallingConvention = CallingConvention.Cdecl)]
    static extern void Close_HID();

    [DllImport(Dll, CallingConvention = CallingConvention.Cdecl)]
    static extern int HID_i2cread(uint dwRegAddr, byte byRegAddrLen, IntPtr pBuffer, byte byBufferLen, byte bySlaveAddr, byte bySpeed, uint dwTimeout);

    [DllImport(Dll, CallingConvention = CallingConvention.Cdecl)]
    static extern int HID_i2cwrite(IntPtr pBuffer, byte byBufferLen, byte bySlaveAddr, byte bySpeed);

    [DllImport(Dll, CallingConvention = CallingConvention.Cdecl)]
    static extern int Get_mutiHID(ushort vendor_id, ushort product_id);

    [DllImport(Dll, CallingConvention = CallingConvention.Cdecl)]
    static extern int Open_mutiHID(int index);

    static bool _opened = false;

    static void Main(string[] args)
    {
        bool readOnly = Array.IndexOf(args, "--read-only") >= 0;
        ushort vid = 0x0BDA;
        ushort pid = 0x1100;
        Console.WriteLine(JsonSerializer.Serialize(new { ready = true, protocol = 2, read_only = readOnly, status_query = true }));
        string? line;
        while ((line = Console.ReadLine()) != null)
        {
            try
            {
                using var doc = JsonDocument.Parse(line);
                var root = doc.RootElement;
                string cmd = root.GetProperty("cmd").GetString() ?? "";
                if (readOnly && cmd != "open" && cmd != "close" && cmd != "quit" && cmd != "status_query" && cmd != "ddc_query")
                    throw new InvalidOperationException("command prohibited in read-only helper");
                if (cmd == "open")
                {
                    bool ok = Open_HID(vid, pid) > 0;
                    if (!ok)
                    {
                        int idx = Get_mutiHID(vid, pid);
                        if (idx > 0) ok = Open_mutiHID(0) == 0;
                    }
                    _opened = ok;
                    Console.WriteLine(JsonSerializer.Serialize(new { ok }));
                }
                else if (cmd == "close")
                {
                    if (_opened) { Close_HID(); _opened = false; }
                    Console.WriteLine(JsonSerializer.Serialize(new { ok = true }));
                }
                else if (cmd == "status_query" || cmd == "ddc_query")
                {
                    if (!_opened) throw new InvalidOperationException("HID device is not open");
                    byte selector = root.GetProperty("selector").GetByte();
                    bool standard = cmd == "ddc_query";
                    bool allowed = standard
                        ? selector == 0x10 || selector == 0x12 || selector == 0x6C || selector == 0x6E || selector == 0x70 || selector == 0xDF || selector == 0xE0
                        : selector == 0x02 || selector == 0x07 || selector == 0x38 || selector == 0x7F || selector == 0x80 || selector == 0x81 || selector == 0x82 || selector == 0x83;
                    if (!allowed)
                        throw new ArgumentException("selector is not an allowlisted status query");
                    byte[] frame = new byte[36];
                    frame[0] = 0x51; frame[1] = standard ? (byte)0x82 : (byte)0x83; frame[2] = 1;
                    frame[3] = standard ? selector : (byte)0xE0;
                    if (!standard) frame[4] = selector;
                    int checksumIndex = standard ? 4 : 5;
                    for (int k = 0; k < checksumIndex; k++) frame[checksumIndex] ^= frame[k];
                    byte[] reply = new byte[36];
                    IntPtr buf = Marshal.AllocHGlobal(36);
                    try
                    {
                        Marshal.Copy(frame, 0, buf, 36);
                        int writeStatus = HID_i2cwrite(buf, 36, 0x6E, 0);
                        if (writeStatus != 0) throw new InvalidOperationException($"status query send failed: {writeStatus}");
                        System.Threading.Thread.Sleep(150);
                        Marshal.Copy(reply, 0, buf, 36);
                        int readStatus = HID_i2cread(0x51, 1, buf, 36, 0x6E, 0, 100);
                        if (readStatus != 0) throw new InvalidOperationException($"status query receive failed: {readStatus}");
                        Marshal.Copy(buf, reply, 0, 36);
                        Console.WriteLine(JsonSerializer.Serialize(new { ok = true, result = 0, bytes = Array.ConvertAll(reply, b => (int)b), query = Array.ConvertAll(frame, b => (int)b) }));
                    }
                    finally { Marshal.FreeHGlobal(buf); }
                }
                else if (cmd == "i2c_write")
                {
                    if (!_opened) throw new InvalidOperationException("HID device is not open");
                    var bytes = root.GetProperty("bytes");
                    int n = bytes.GetArrayLength();
                    if (n < 1 || n > 128) throw new ArgumentException("write length must be 1..128");
                    byte[] arr = new byte[n];
                    int i = 0;
                    foreach (var b in bytes.EnumerateArray()) arr[i++] = b.GetByte();
                    byte slave = root.TryGetProperty("slave", out var s) ? s.GetByte() : (byte)0x6E;
                    byte speed = root.TryGetProperty("speed", out var sp) ? sp.GetByte() : (byte)0;
                    IntPtr buf = Marshal.AllocHGlobal(n);
                    try
                    {
                        Marshal.Copy(arr, 0, buf, n);
                        int res = HID_i2cwrite(buf, (byte)n, slave, speed);
                        Console.WriteLine(JsonSerializer.Serialize(new { ok = res == 0, result = res }));
                    }
                    finally { Marshal.FreeHGlobal(buf); }
                }
                else if (cmd == "i2c_read")
                {
                    if (!_opened) throw new InvalidOperationException("HID device is not open");
                    uint reg = root.GetProperty("reg").GetUInt32();
                    byte regLen = root.GetProperty("reg_len").GetByte();
                    int bufLen = root.GetProperty("buf_len").GetInt32();
                    if (bufLen < 1 || bufLen > 128 || regLen > 4) throw new ArgumentException("invalid read length");
                    byte slave = root.TryGetProperty("slave", out var s) ? s.GetByte() : (byte)0x6E;
                    byte speed = root.TryGetProperty("speed", out var sp) ? sp.GetByte() : (byte)0;
                    uint timeout = root.TryGetProperty("timeout", out var t) ? t.GetUInt32() : 100;
                    byte[] arr = new byte[bufLen];
                    IntPtr buf = Marshal.AllocHGlobal(bufLen);
                    try
                    {
                        Marshal.Copy(arr, 0, buf, bufLen);
                        int res = HID_i2cread(reg, regLen, buf, (byte)bufLen, slave, speed, timeout);
                        if (res == 0)
                        {
                            Marshal.Copy(buf, arr, 0, bufLen);
                            int[] intArr = Array.ConvertAll(arr, b => (int)b);
                            Console.WriteLine(JsonSerializer.Serialize(new { ok = true, result = res, bytes = intArr }));
                        }
                        else Console.WriteLine(JsonSerializer.Serialize(new { ok = false, result = res, error = "HID_i2cread failed" }));
                    }
                    finally { Marshal.FreeHGlobal(buf); }
                }
                else if (cmd == "quit")
                {
                    if (_opened) { Close_HID(); _opened = false; }
                    Console.WriteLine(JsonSerializer.Serialize(new { ok = true }));
                    return;
                }
                else
                {
                    Console.WriteLine(JsonSerializer.Serialize(new { ok = false, error = "unknown command" }));
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine(JsonSerializer.Serialize(new { ok = false, error = ex.Message }));
            }
        }
        if (_opened) { Close_HID(); _opened = false; }
    }
}
