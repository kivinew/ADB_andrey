$ErrorActionPreference = 'Continue'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName UIAutomationClient

$proc = Get-Process AndroidManager -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $proc) { Write-Host 'NO APP'; exit 1 }
$h = $proc.MainWindowHandle

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class W {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; }
}
"@
$r = New-Object W+RECT
[W]::GetWindowRect($h, [ref]$r)
Write-Host ("rect {0} {1} {2} {3}" -f $r.L,$r.T,$r.R,$r.B)
mkdir -p /d/am_test 2>$null | Out-Null
$bmp = New-Object System.Drawing.Bitmap ($r.R-$r.L), ($r.B-$r.T)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.L,$r.T,0,0,$bmp.Size)
$bmp.Save($args[0])
Write-Host ("saved {0}" -f $args[0])