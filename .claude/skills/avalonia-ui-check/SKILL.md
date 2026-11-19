---
name: avalonia-ui-check
description: Собрать C#-версию AndroidManager (Avalonia), запустить её и снять/проверить окно скриншотом. Использовать при любой правке dotnet/AndroidManager или dotnet/AndroidManager.Core, когда нужно убедиться, что интерфейс действительно работает, а не только компилируется.
---

# Проверка UI C#-версии (Avalonia)

Рабочая папка: `E:\DOWNLOADS\CREATIVE\PYTHON\GitHub\ADB`.

## 1. Сборка

Перед сборкой всегда гасить запущенный exe, иначе MSB3021/MSB3027 и сборка врёт про «0 ошибок»:

```powershell
taskkill /f /im AndroidManager.exe 2>$null
& "C:\Program Files\dotnet\dotnet.exe" build dotnet/AndroidManager 2>&1 | Select-Object -Last 5
```

Норма — `0 Error(s)` и ~17 предупреждений (obsolete clipboard, CS8602). Рост числа предупреждений — сигнал.

## 2. Запуск

`dotnet run` в этой сессии зависает (блокирует инструмент). Запускать exe напрямую из bash с фоновым перенаправлением:

```bash
cd "/e/DOWNLOADS/CREATIVE/PYTHON/GitHub/ADB/dotnet/AndroidManager/bin/Debug/net10.0" && ./AndroidManager.exe > /tmp/am_out.log 2>&1 &
sleep 4; tasklist //fi "imagename eq AndroidManager.exe" | tail -1
```

Смотреть `/tmp/am_out.log`, если окно не появилось.

## 3. Скриншот окна

`PrintWindow` снимает содержимое окна, даже если оно перекрыто полноэкранной игрой или другим процессом (`CopyFromScreen` в этом случае даёт чужой экран).

```powershell
pwsh -File .claude/skills/avalonia-ui-check/scripts/capture.ps1 -Out dtest_shot.png
```

Скрипт печатает размеры окна; сам PNG читать инструментом Read.

## 4. Переключение вкладок

Кнопки сайдбара имеют `x:Name` (BtnHome, BtnCards, BtnApps, BtnProcs, BtnConsole, BtnLogs, BtnActions, BtnSettings) — Avalonia отдаёт их как AutomationId, и UIA их кликает:

```powershell
pwsh -File .claude/skills/avalonia-ui-check/scripts/click.ps1 -AutomationId BtnConsole
```

Кнопку внутри вкладки можно нажать по имени: `-Name "ps -A"`, `-Name "Выполнить"`.

## 5. Живой клик мышью

Avalonia **не принимает** синтетические `PostMessage(WM_LBUTTONDOWN/UP)` и `mouse_event` через `PostMessage` — сообщения теряются. Работает только реальная инъекция:

```powershell
pwsh -File .claude/skills/avalonia-ui-check/scripts/click.ps1 -Name "df" -RealMouse
```

`-RealMouse` двигает настоящий курсор, поэтому скрипт сохраняет и восстанавливает его позицию. Использовать умеренно — пользователь может играть/работать в этот момент.

## 6. Тесты ядра

```powershell
& "C:\Program Files\dotnet\dotnet.exe" run --project dotnet/AndroidManager.SelfCheck
```

`dotnet test` на этой машине падает (testhost — Access denied на OpenProcess), каноничный запуск — `AndroidManager.SelfCheck`.

## Ловушки, проверенные на практике

- `Button` гасит `PointerPressed`: обработчики на кнопке нужно вешать через `AddHandler(..., handledEventsToo: true)`, иначе драг не заведётся.
- Захват указателя (`e.Pointer.Capture`) на `PointerPressed` **ломает обычный клик** по кнопке — брать захват только после сдвига дальше порога.
- Прокрутка `ScrollViewer` сразу после смены `ItemsSource` считает по старому `Extent` — откладывать на `DispatcherPriority.Background`.
- `GetVisualAncestorsAndSelf` не существует; в этой версии — `GetSelfAndVisualAncestors`.
- Контекстные меню и попапы — отдельные окна, `PrintWindow` их не снимает; проверять через UIA (`AutomationElement.RootElement.FindAll` по имени пункта).
