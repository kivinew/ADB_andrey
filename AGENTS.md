# ADB — Android Manager

Менеджер Android TV-приставок через ADB: установщик (PyInstaller) + Tkinter-приложение.
Только stdlib и tkinter, без внешних зависимостей для запуска из исходников.

## Запуск и проверки

```bash
python Android_manager.pyw            # окно установщика
python Android_manager.pyw --cli      # установка без окна
python Android_manager.pyw --run      # запустить приложение из исходников
python -m android_manager             # то же, что --run
python Android_manager.pyw --version  # версия

python devtools/smoke_gui.py          # дымовой тест окна: открыть, обойти вкладки, закрыть
python devtools/smoke_gui.py --scripts  # + запуск скрипта через вкладку «Скрипты»
python devtools/build_installer.py    # собрать dist/Android_manager.pyw (установщик одним файлом)
python devtools/verify_extraction.py --baseline <git-ref>   # сверить пакеты с исходным файлом
python -m compileall -q android_manager installer
python -m unittest discover -s tests -v                     # 64 теста
```

## Где что лежит

| Задача | Файлы |
|---|---|
| Вкладка «Приложения» | `android_manager/ui/tab_apps.py` |
| «Инструменты»: пульт | `android_manager/ui/tab_tools.py`, `widgets/remote.py` |
| Показатели состояния | `android_manager/ui/cards.py`, `parsing.py` (`parse_card`, `build_state_batch`) |
| Процессы и top | `android_manager/ui/procs.py`, `parsing.py` (`parse_proc_stat`, `parse_proc_output`) |
| scrcpy / Vysor / скриншот / клавиши | `android_manager/ui/actions.py` |
| «Консоль», стриминг, автодополнение | `android_manager/ui/tab_console.py` |
| «Скрипты», API для скриптов | `android_manager/ui/tab_scripts.py`, `scriptapi.py`, `script_shim.py` |
| «Настройки», экспорт и импорт | `android_manager/ui/tab_settings.py`, `storage.py` |
| Подключение, устройства, пара | `android_manager/ui/connection.py` |
| Настраиваемые кнопки | `android_manager/ui/bars.py` |
| Общие диалоги и окна | `android_manager/ui/dialogs.py` |
| Каркас окна, стили, журнал | `android_manager/ui/app.py` |
| Установщик: шаги и ошибки | `installer/service.py`, `installer/errors.py` |
| Сборка exe (PyInstaller) | `installer/build.py` |
| Ярлыки, скачивание adb/scrcpy | `installer/shortcuts.py`, `installer/packages.py`, `installer/net.py` |
| Пути, версия, цвета, умолчания | `android_manager/paths.py`, `config.py`, `defaults.py` |
| Разбор вывода adb (чистые функции) | `android_manager/parsing.py` |
| Настройки, JSON, бандлы | `android_manager/storage.py` |

## Правила

- Слои: `ui` → `widgets` → `storage`/`scriptapi`/`proc` → `config`/`paths`/`parsing`/`util`.
  Импорт только вниз; циклам не место.
- Никаких `from x import *`. Миксины не импортируют друг друга — только `self`.
- `App` собирается в `ui/app.py` из 11 миксинов-вкладок; методы живут в своих файлах.
- Побочных эффектов при импорте нет: папки и `scripts/adb.py` создаёт `bootstrap()` из `__main__.py`.
- Данные программы (`settings.json`, `scripts/`, `apk/`, `programs/`, `screenshots/`, `files/`)
  лежат рядом с exe, а из исходников — в корне репозитория (`paths.BASE`).
- `dist/Android_manager.pyw` — генерируемый артефакт, в git не нужен.
- Русские строки — в интерфейсе; докстринги и комментарии короткие.
- `PROGRAM_SRC` больше нет: установщик собирает exe прямо из пакета (`PyInstaller --paths`).

Не читать: `dist/`, `__pycache__/`, `apk/`, `files/`, `programs/`, `screenshots/`.

## Тесты

```bash
python -m unittest discover -s tests -v
```

- `tests/test_parsing.py` — разбор вывода adb: `parse_card`, `parse_state_batch`,
  `parse_proc_stat`/`parse_proc_output`, память, `df`, пакеты, адреса;
- `tests/test_util.py` — имена, `slug`, `unique_path`, `flow_layout`, `hit_button`,
  геометрия пульта;
- `tests/test_storage.py` — миграция настроек, `make_bundle`/`apply_bundle`, JSON;
  работает во временной папке и не трогает файлы проекта;
- `tests/test_imports.py` — все модули импортируются, каждое глобальное имя имеет импорт
  (ловит `NameError` вроде пропавшего `import sys`), `paths.BASE`, запрет
  зависимости `android_manager` → `installer`.

Новую логику разбора кладите в `parsing.py`/`util.py` и покрывайте тестом: это дешевле,
чем проверять окно глазами.
