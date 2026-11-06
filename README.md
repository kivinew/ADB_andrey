# Android Manager

Установщик и диагностика для Android TV-устройств (КЭС / Элтекс / Tanix и др.).

## Состав

| Файл | Назначение |
|------|------------|
| `install_kes_v9.py` | **Установщик** (один файл). Качает `adb` + `scrcpy`, собирает `Android-manager.exe` через PyInstaller, ставит в `%LOCALAPPDATA%\Android-manager`, создаёт ярлыки. Запуск: `python install_kes_v9.py` (GUI) или `--cli` (без окон). |
| `tvdiag_report.py` | **Диагностика ТВ** — отправляет на устройство **одну** пакетную `adb shell` команду, парсит вывод и печатает структурированный отчёт (CPU, память, GPU, HDMI/CEC, сеть, логи, перезагрузки). Работает внутри Android-manager (где `adb` — это `ScriptAPI`), для CLI замените `adb.shell(COMMANDS)` на `subprocess.run(["adb", "shell", ...])`. |
| `AGENTS.md` | Инструкции для ИИ-агентов (Hermes, Codex и др.) — как работать с репозиторием. |

## Быстрый старт

```bash
# Установка менеджера (Windows)
python install_kes_v9.py

# Диагностика устройства (нужен adb в PATH и подключенное устройство)
python tvdiag_report.py
```

## Возможности Android-manager

- **Вкладка «Приложения»**: список пакетов (пользовательские/системные/отключённые), запуск, остановка, очистка, удаление, установка APK.
- **Вкладка «Инструменты»**: состояние (модель, Android, uptime, память, CPU, GPU, температура, HDMI, сеть, DNS, ping провайдера), процессы (top по памяти/CPU), команды (getprop, pm, am, settings, logcat, dmesg, ping, свои).
- **Вкладка «Консоль»**: интерактивный `adb shell` с историей и подсказками.
- **Вкладка «Скрипты»**: пользовательские Python-скрипты с API `adb.shell()`, `adb.call()`, `adb.getprop()`, `adb.packages()`, `adb.install()`, `adb.push/pull()`, `adb.screenshot()`, `adb.reboot()` и др. Скрипты кладутся в `scripts/`.
- **Вкладка «Пульты»**: настраиваемые раскладки кнопок (стандартный, Tanix, Элтекс, свои), отправка keyevent/tap/swipe/text.
- **Вкладка «Настройки»**: IP/порт ADB, тема, шрифт, автообновление списка пакетов, таймауты.

## Требования

- Windows 10/11 (x64)
- Python 3.10+ (для запуска установщика)
- ADB/Scrcpy качаются автоматически при установке

## Структура после установки

```
%LOCALAPPDATA%\Android-manager\
├── Android-manager.exe
├── tools\
│   ├── adb\adb.exe
│   └── scrcpy\scrcpy.exe
├── scripts\          # ваши .py скрипты
├── apk\              # ваши .apk
├── programs\
├── screenshots\
├── files\
└── settings.json
```

## Лицензия

MIT — делайте что хотите, ссылка на автора приветствуется.