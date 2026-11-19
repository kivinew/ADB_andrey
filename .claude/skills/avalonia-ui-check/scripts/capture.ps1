param(
    [string]$Out = "dtest_shot.png",
    [string]$ProcessName = "AndroidManager"
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class UiCapture {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; }
}
"@

$proc = Get-Process $ProcessName -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $proc -or $proc.MainWindowHandle -eq 0) {
    Write-Host "NO WINDOW ($ProcessName)"
    exit 1
}

$h = $proc.MainWindowHandle
$r = New-Object UiCapture+RECT
[UiCapture]::GetWindowRect($h, [ref]$r) | Out-Null

$w = $r.R - $r.L
$hh = $r.B - $r.T
if ($w -le 0 -or $hh -le 0) {
    Write-Host "BAD RECT ($w x $hh)"
    exit 1
}

$bmp = New-Object System.Drawing.Bitmap $w, $hh
$g = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $g.GetHdc()
# 2 = PW_RENDERFULLCONTENT: снимает содержимое GPU-окна, даже перекрытого
[UiCapture]::PrintWindow($h, $hdc, 2) | Out-Null
$g.ReleaseHdc($hdc)
$g.Dispose()

$path = [System.IO.Path]::GetFullPath($Out)
$bmp.Save($path)
$bmp.Dispose()

Write-Host ("saved {0} ({1}x{2})" -f $path, $w, $hh)
