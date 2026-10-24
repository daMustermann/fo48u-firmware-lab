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

    static void Main()
    {
        ushort vid = 0x0BDA;
        ushort pid = 0x1100;
        Console.WriteLine(JsonSerializer.Serialize(new { ready = true, protocol = 2 }));
        string? line;
        while ((line = Console.ReadLine()) != null)
        {
            try
            {
                using var doc = JsonDocument.Parse(line);
                var root = doc.RootElement;
                string cmd = root.GetProperty("cmd").GetString() ?? "";
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
