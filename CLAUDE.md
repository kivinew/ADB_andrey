# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Что это

Менеджер Android TV-приставок через ADB: установщик + Tkinter-приложение. Только stdlib
и tkinter — внешних зависимостей для запуска из исходников нет (PyInstaller нужен только
на шаге сборки exe). Интерфейс на русском.

## Команды

```bash
python Android_manager.pyw              # окно установщика
python Android_manager.pyw --cli        # установка без окна
python Android_manager.pyw --run        # запустить приложение из исходников
python -m android_manager               # то же, что --run
python Android_manager.pyw --version

python -m unittest discover -s tests -v                  # все тесты (72)
python -m unittest discover -s tests -p test_parsing.py  # один файл
python -m unittest discover -s tests -k parse_card       # один тест
python -m compileall -q android_manager installer        # проверка синтаксиса

python devtools/smoke_gui.py            # дымовой тест окна: собрать, обойти вкладки, закрыть
python devtools/smoke_gui.py --scripts  # + запустить скрипт через вкладку «Скрипты»
python devtools/build_installer.py      # -> dist/Android_manager.pyw (один файл для раздачи)
python devtools/verify_extraction.py --baseline <git-ref>   # сверить перенос по AST
```

C#-версия (папка `dotnet/`), если нужен GPU-рендеринг и неблокирующая консоль:

```bash
"/c/Program Files/dotnet/dotnet.exe" build dotnet/AndroidManager
"/c/Program Files/dotnet/dotnet.exe" run   dotnet/AndroidManager
"/c/Program Files/dotnet/dotnet.exe" run   dotnet/AndroidManager.SelfCheck   # 38 тестов ядра
```

GUI-тестов в `tests/` нет: окно проверяется только через `devtools/smoke_gui.py` (нужен
дисплей) или руками. Вся логика, доступная без окна, должна быть покрыта юнит-тестами.

## Архитектура

Два независимых пакета плюс точка входа:

- `Android_manager.pyw` → `installer/cli.py` — разбор флагов; окно установщика (`--cli`
  без окна, `--run` сразу запускает приложение).
- `installer/` — установка: скачивает adb/scrcpy (`net.py`, `packages.py`), собирает
  `Android-manager.exe` через PyInstaller **из пакета** (`build.py`, `--paths`), кладёт
  рядом, делает ярлыки (`shortcuts.py`). Цель по умолчанию — домашняя папка
  (`installer/config.py: DEFAULT_PARENT`).
- `android_manager/` — приложение. `App` в `ui/app.py` собирается из 11 миксинов-вкладок
  (`DialogsTab, ConnectionTab, BarsTab, AppsTab, ToolsTab, CardsTab, ProcsTab, ActionsTab,
  ConsoleTab, ScriptsTab, SettingsTab`) плюс `tk.Tk`; каждому миксину соответствует свой
  файл в `ui/`. Порядок миксинов задаёт порядок вкладок. Правка вкладки — правка её файла.

Ключевая идея разделения: **`parsing.py` — чистые функции над текстом вывода `adb`**
(`parse_card`, `build_state_batch`, `parse_state_batch`, `parse_proc_stat`,
`parse_proc_output`, `mem_from_meminfo`, `parse_df_mb`, `parse_pkgs`, `split_target`).
Новую логику разбора кладите туда (или в `util.py`) и покрывайте тестом — проверять окно
глазами дороже. `cards.py` определяет, какие показатели показывать и каким парсером.

Слои (импорт только вниз, циклов нет): `ui` → `widgets` → `storage`/`scriptapi`/`proc`
→ `config`/`paths`/`parsing`/`util`. `test_imports.py` проверяет, что `android_manager`
не импортирует `installer` (иначе exe потянет установщик целиком), что каждый модуль
импортируется и что все глобальные имена где-то объявлены (ловит потерянный `import sys`).

Данные программы: `paths.BASE` — папка рядом с exe при сборке, корень репозитория из
исходников. Там лежат `settings.json`, `scripts/`, `apk/`, `programs/`, `screenshots/`,
`files/`. `adb`/`scrcpy` ищутся сначала в `tools/<name>/`, затем в PATH (`paths.find_tool`).
`bootstrap()` из `__main__.py` создаёт эти папки и пишет `scripts/adb.py`; при импорте
побочных эффектов нет — тесты и импорт модулей ничего не создают.

Все обращения к устройству идут через `proc.run([ADB, "-s", serial, ...])`, который
возвращает `(rc, out, err)`, не бросает исключений и не открывает окно консоли. Тяжёлые
вызовы оборачиваются в `App.bg(job, done)`: поток выполняет `job`, результат кладётся в
`self.jobs`, а `_poll` (каждые 80 мс) вызывает `done` уже в главном потоке tkinter — из
`done` можно трогать виджеты. Прямые вызовы `run` в обработчиках блокируют UI.

`programs/` — описания внешних программ, по одному JSON на файл, читаются
`storage.load_json_folder`; кнопки для них строятся в `ui/actions.py`.

## Пользовательские скрипты

Вкладка «Скрипты» исполняет произвольные `.py` из `scripts/` в пространстве имён, где уже
определён объект `adb` (`ScriptAPI`), и одновременно подставляет модуль в `sys.modules`,
чтобы работал и `import adb`. `AdbModule` в `scriptapi.py` делегирует все атрибуты живому
`ScriptAPI`, иначе `import adb` дал бы только `shell`. Остановка пользователя — исключение
`ScriptStop`. `scripts/adb.py` (шаблон — `script_shim.py`) нужен для запуска скриптов
**вне** приложения: он берёт API из `__adb_api__` в globals и падает с понятной ошибкой,
если скрипт запущен не через вкладку.

`android_checkup.py` — диагностика ТВ: одна большая `adb shell` команда, вывод которой
размечен строками `@@key=value`. Запускается как обычный пользовательский скрипт (или из
корня репозитория — тогда подхватывается `adb.py`). Списки серверов для пинга и DNS для
проверки правятся в «Настройках» (`checkup_servers`, `checkup_dns` в `settings.json`).

## Настройки и экспорт

`settings.json` (в git не входит) мержится с `DEFAULT_SETTINGS` при загрузке, затем
проходит `migrate_settings`. `make_bundle`/`apply_bundle` — экспорт/импорт: формат
`android-tv-bundle`, тексты скриптов едут внутри бандла, при конфликте имён создаётся
копия через `unique_path`, чужие элементы панелей и пультов добавляются, а не заменяют.

## C#-порт (`dotnet/`)

Порт идёт отдельным деревом; Python-приложение остаётся рабочим и служит эталоном. Цель
порта — GPU-рендеринг, виртуализация списков и живая смена тем/шрифтов, а не скорость:
исходные зависания были архитектурными и уже исправлены в Python.

- `dotnet/AndroidManager/` — демо Avalonia (.NET 10): тема, шрифт, неблокируемый поток.
  Это стенд для проверки подходов, а не будущий интерфейс.
- `dotnet/AndroidManager.Core/` — `Adb/` (обёртка над `adb`, `(rc, out, err)` без
  исключений, таймаут = -2, нет файла = -1) и `Parsing/` (перенос `parsing.py` один в один).
- `dotnet/AndroidManager.Core.Tests/` — 31 тест, порт `tests/test_parsing.py`.
- `dotnet/AndroidManager.SelfCheck/` — консольный раннер тех же `[Fact]`.

```bash
dotnet run --project dotnet/AndroidManager                  # демо (окно)
dotnet run --project dotnet/AndroidManager.SelfCheck        # 31 тест, текстовая сводка
dotnet test dotnet/AndroidManager.Core.Tests                # каноничный запуск
```

`testhost` на этой машине падает с `Access is denied` на `OpenProcess` процесса-родителя —
и с AnyCPU, и с `PlatformTarget=x64`, до запуска любого теста. Поэтому здесь тесты гоняет
`AndroidManager.SelfCheck`: он находит те же `[Fact]` рефлексией и вызывает их. Тестовый
проект остаётся каноничным — в нормальном окружении и в CI он идёт через `dotnet test`.

Ловушки переноса с Python: `//` — это flooring, а не усечение (есть `Num.FloorDiv`);
новый процесс в `parse_proc_output` получает `dp = 0`, а не «тики минус ноль»; `f"{x:.0f}"` —
это не `"{x}"`, иначе в русской локали выйдет «2,5» вместо «2».

Открытый вопрос: вкладка «Скрипты» исполняет Python через `import adb`. Для C#-версии это
Roslyn (ломает совместимость), Python.NET (Python остаётся в проекте) или внешний процесс.

## C#-порт (dotnet/)

`dotnet/` — порт на C#/.NET 10 + Avalonia 11, живёт отдельно и не влияет на Python-версию.
`Android_manager.pyw` и `android_checkup.py` остаются на Python.

- `AndroidManager.Core` — логика без UI, по смыслу повторяет `android_manager`: `Parsing/`
  (те же чистые функции над выводом adb), `Adb/` (`AdbRunner`, `AdbClient`, `AdbStream`,
  `ProcessKill`), `Devices/`, `Settings/` (`AppSettings`, `Defaults`).
- `AndroidManager` — оболочка Avalonia: `MainWindow` держит выбор устройства в шапке (он нужен
  всем вкладкам), пять вкладок в `Views/` — Подключение, Консоль, Приложения, Карточки,
  Настройки. `Controls/Sparkline` рисует графики на GPU. `Services/` — `AppState` (общее
  состояние) и `UiDialogs` (Подтверждение/Сопряжение).
- `AndroidManager.Core.Tests` — xUnit. `dotnet test` на этой машине не работает (testhost падает
  на `OpenProcess` Access Denied), поэтому тесты запускаются своим раннером:
  `AndroidManager.SelfCheck`, который находит методы `Fact` и вызывает их сам. Новый тест —
  просто метод с `[Fact]` в `AndroidManager.Core.Tests`.

Настройки C#-версии — `settings.json` рядом с exe: у неё своя папка, с Python-версией и её
настройками они не пересекаются. Ключи в файле snake_case, как у Python-версии, чтобы файлы
было видно глазами рядом.

## Правила

- Не коммитить данные пользователя: `settings.json`, `apk/`, `programs/`, `screenshots/`,
  `files/`, `scripts/*.py` (кроме `scripts/adb.py`), `dist/`.
- Не читать `dist/`, `__pycache__/`, `apk/`, `files/`, `programs/`, `screenshots/`.
- `dist/Android_manager.pyw` — генерируемый артефакт, не редактировать руками.
- Докстринги и комментарии короткие, на русском.