param(
    [string]$AutomationId,
    [string]$Name,
    [switch]$RealMouse,
    [string]$ProcessName = "AndroidManager"
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$proc = Get-Process $ProcessName -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $proc -or $proc.MainWindowHandle -eq 0) {
    Write-Host "NO WINDOW ($ProcessName)"
    exit 1
}

$h = $proc.MainWindowHandle
$root = [System.Windows.Automation.AutomationElement]::FromHandle($h)

$el = $null
if ($AutomationId) {
    $c = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::AutomationIdProperty, $AutomationId)
    $el = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $c)
}
elseif ($Name) {
    $c = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::NameProperty, $Name)
    $el = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $c)
}
else {
    Write-Host "Specify -AutomationId or -Name"
    exit 2
}

if (-not $el) {
    Write-Host "NOT FOUND"
    exit 3
}

if (-not $RealMouse) {
    # UIA Invoke — не двигает курсор; работает для кнопок, но не для drag/ПКМ
    $el.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    Write-Host ("invoked {0}" -f ($AutomationId ?? $Name))
    exit 0
}

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class UiMouse {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetCursorPos(out PT p);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, int dx, int dy, int d, IntPtr e);
  [StructLayout(LayoutKind.Sequential)] public struct PT { public int X,Y; }
}
"@

$rect = $el.Current.BoundingRectangle
$old = New-Object UiMouse+PT
[UiMouse]::GetCursorPos([ref]$old) | Out-Null

try {
    [UiMouse]::SetForegroundWindow($h) | Out-Null
    Start-Sleep -Milliseconds 300
    [UiMouse]::SetCursorPos([int]($rect.X + $rect.Width / 2), [int]($rect.Y + $rect.Height / 2)) | Out-Null
    Start-Sleep -Milliseconds 200
    [UiMouse]::mouse_event(0x0002, 0, 0, 0, [IntPtr]::Zero)   # LEFTDOWN
    Start-Sleep -Milliseconds 80
    [UiMouse]::mouse_event(0x0004, 0, 0, 0, [IntPtr]::Zero)   # LEFTUP
    Start-Sleep -Milliseconds 400
}
finally {
    [UiMouse]::SetCursorPos($old.X, $old.Y) | Out-Null
}

Write-Host ("clicked {0} at {1},{2}" -f ($AutomationId ?? $Name), $rect.X, $rect.Y)
