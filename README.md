# Android Manager

Установщик и диагностика для Android TV-устройств (Элтекс / Tanix и др.).

## Состав

| Файл | Назначение |
|------|------------|
| `Android_manager.pyw` | **Точка входа**: окно установки, `--cli` (без окна), `--run` (приложение), `--version`. |
| `android_manager/` | **Приложение** (Tkinter): вкладки, виджеты, разбор `adb`, настройки. |
| `installer/` | **Установщик**: скачивает `adb` и `scrcpy`, собирает `Android-manager.exe` через PyInstaller, ставит в `%USERPROFILE%\Android-manager`, создаёт ярлыки. |
| `android_checkup.py` | **Диагностика ТВ** — одна пакетная `adb shell` команда, разбор `@@key=value`, отчёт (CPU, память, GPU, HDMI/CEC, сеть, логи, перезагрузки). Кладётся в `scripts/`. |
| `adb.py` | Заглушка `adb.shell()` для запуска `android_checkup.py` без GUI (через `adb.exe`). |
| `devtools/` | `smoke_gui.py` (дымовой тест окна), `build_installer.py` (один файл для раздачи), `verify_extraction.py` (сверка переноса). |
| `PLAN_MODULES.md` | Как и зачем файл разбивался на модули (решения, риски, замеры токенов). |

## Быстрый старт

```bash
# Установка менеджера (Windows)
python Android_manager.pyw

# Запуск приложения из исходников
python Android_manager.pyw --run

# Диагностика устройства (нужен adb в PATH и подключенное устройство)
python android_checkup.py
```

Установщик одним файлом для раздачи собирается так:

```bash
python devtools/build_installer.py   # -> dist/Android_manager.pyw
```

## Возможности Android-manager

- **Вкладка «Приложения»**: список пакетов (пользовательские/системные/отключённые), запуск, остановка, очистка, удаление, установка APK.
- **Вкладка «Инструменты»**: состояние (модель, Android, uptime, память, CPU, GPU, температура, HDMI, сеть, DNS, ping провайдера), процессы (top по памяти/CPU), команды (getprop, pm, am, settings, logcat, dmesg, ping, свои).
- **Вкладка «Консоль»**: интерактивный `adb shell` с историей и подсказками, стриминг `logcat`/`top`.
- **Вкладка «Скрипты»**: пользовательские Python-скрипты с API `adb.shell()`, `adb.call()`, `adb.getprop()`, `adb.packages()`, `adb.install()`, `adb.push/pull()`, `adb.screenshot()`, `adb.reboot()`. Скрипты кладутся в `scripts/`.
- **Вкладка «Пульты»**: настраиваемые раскладки кнопок (стандартный, Tanix, Элтекс, свои), отправка keyevent/tap/swipe/text.
- **Вкладка «Настройки»**: IP/порт ADB, тема, шрифт, автообновление списка пакетов, таймауты.

## Требования

- Windows 10/11 (x64)
- Python 3.10+ (для запуска установщика из исходников)
- ADB/Scrcpy качаются автоматически при установке

## Структура после установки

```
%USERPROFILE%\Android-manager\
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

## Структура репозитория

```
Android_manager.pyw      точка входа (установщик)
android_manager/         приложение: config, paths, parsing, storage, widgets/, ui/
installer/               установщик: service, build, gui, packages, shortcuts
devtools/                служебные скрипты (не нужны для работы программы)
scripts/                 пользовательские скрипты (в git — только adb.py)
```

## Лицензия

MIT — делайте что хотите, ссылка на автора приветствуется.
