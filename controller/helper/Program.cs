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
        Console.WriteLine(JsonSerializer.Serialize(new { ready = true }));
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
                    bool ok = Open_HID(vid, pid) != 0;
                    if (!ok)
                    {
                        int idx = Get_mutiHID(vid, pid);
                        if (idx != 0) { Open_mutiHID(0); ok = true; }
                    }
                    if (ok) _opened = true;
                    Console.WriteLine(JsonSerializer.Serialize(new { ok }));
                }
                else if (cmd == "close")
                {
                    if (_opened) { Close_HID(); _opened = false; }
                    Console.WriteLine(JsonSerializer.Serialize(new { ok = true }));
                }
                else if (cmd == "i2c_write")
                {
                    var bytes = root.GetProperty("bytes");
                    int n = bytes.GetArrayLength();
                    IntPtr buf = Marshal.AllocHGlobal(n);
                    byte[] arr = new byte[n];
                    int i = 0;
                    foreach (var b in bytes.EnumerateArray()) arr[i++] = (byte)b.GetInt32();
                    Marshal.Copy(arr, 0, buf, n);
                    int slave = root.TryGetProperty("slave", out var s) ? s.GetInt32() : 0x6E;
                    int speed = root.TryGetProperty("speed", out var sp) ? sp.GetInt32() : 0;
                    int res = HID_i2cwrite(buf, (byte)n, (byte)slave, (byte)speed);
                    Marshal.FreeHGlobal(buf);
                    Console.WriteLine(JsonSerializer.Serialize(new { ok = true, result = res }));
                }
                else if (cmd == "i2c_read")
                {
                    int reg = root.GetProperty("reg").GetInt32();
                    int regLen = root.GetProperty("reg_len").GetInt32();
                    int bufLen = root.GetProperty("buf_len").GetInt32();
                    int slave = root.TryGetProperty("slave", out var s) ? s.GetInt32() : 0x6E;
                    int speed = root.TryGetProperty("speed", out var sp) ? sp.GetInt32() : 0;
                    int timeout = root.TryGetProperty("timeout", out var t) ? t.GetInt32() : 100;
                    IntPtr buf = Marshal.AllocHGlobal(bufLen);
                    int res = HID_i2cread((uint)reg, (byte)regLen, buf, (byte)bufLen, (byte)slave, (byte)speed, (uint)timeout);
                    byte[] arr = new byte[bufLen];
                    Marshal.Copy(buf, arr, 0, bufLen);
                    Marshal.FreeHGlobal(buf);
                    int[] intArr = Array.ConvertAll(arr, b => (int)b);
                    Console.WriteLine(JsonSerializer.Serialize(new { ok = true, result = res, bytes = intArr }));
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
    }
}