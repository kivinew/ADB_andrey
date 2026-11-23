# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Что это

Менеджер Android TV-приставок через ADB: установщик (PyInstaller) + Tkinter-приложение. Только stdlib и tkinter — внешних зависимостей для запуска из исходников нет (PyInstaller нужен только на шаге сборки exe). Интерфейс на русском, докстринги и комментарии короткие, на русском.

## Команды

```bash
python Android_manager.pyw            # окно установщика
python Android_manager.pyw --cli      # установка без окна
python Android_manager.pyw --run      # запустить приложение из исходников
python -m android_manager             # то же, что --run
python Android_manager.pyw --version  # версия

python -m unittest discover -s tests -v                  # все тесты (72)
python -m unittest discover -s tests -p test_parsing.py  # один файл
python -m unittest discover -s tests -k parse_card       # один тест по имени
python -m compileall -q android_manager installer        # проверка синтаксиса

python devtools/smoke_gui.py            # дымовой тест окна: собрать, обойти вкладки, закрыть (нужен дисплей)
python devtools/smoke_gui.py --scripts  # + запустить скрипт через вкладку «Скрипты»
python devtools/build_installer.py      # -> dist/Android_manager.pyw (один файл для раздачи)
python devtools/verify_extraction.py    # сверить перенос из Android_manager.pyw в пакеты по AST
python devtools/verify_extraction.py --baseline <git-ref>
python devtools/verify_extraction.py --baseline old.pyw
```

C#-версия (папка `dotnet/`), если нужен GPU-рендеринг и неблокирующая консоль:

```bash
"/c/Program Files/dotnet/dotnet.exe" build dotnet/AndroidManager
"/c/Program Files/dotnet/dotnet.exe" run   dotnet/AndroidManager                  # демо (окно)
"/c/Program Files/dotnet/dotnet.exe" run   dotnet/AndroidManager.SelfCheck        # 31 тест, текстовая сводка
dotnet test dotnet/AndroidManager.Core.Tests                                      # каноничный запуск (не работает на этой машине)
```

`testhost` на этой машине падает с `Access is denied` на `OpenProcess` процесса-родителя — поэтому тесты гоняет `AndroidManager.SelfCheck` (находит `[Fact]` рефлексией и вызывает сам). Тестовый проект остаётся каноничным — в нормальном окружении и в CI он идёт через `dotnet test`.

## Архитектура

Точка входа: `Android_manager.pyw` → `installer/cli.py` — разбор флагов (`--cli`, `--run`, `--version`).

Два независимых пакета:

- `installer/` — установка: скачивает adb/scrcpy (`net.py`, `packages.py`), собирает `Android-manager.exe` через PyInstaller **из пакета** (`build.py`, `--paths`), кладёт рядом, делает ярлыки (`shortcuts.py`). Сервисные шаги и ошибки — `service.py`, `errors.py`. Цель по умолчанию — домашняя папка (`installer/config.py: DEFAULT_PARENT`).
- `android_manager/` — приложение. `App` в `ui/app.py` собирается из 11 миксинов-вкладок (`DialogsTab, ConnectionTab, BarsTab, AppsTab, ToolsTab, CardsTab, ProcsTab, ActionsTab, ConsoleTab, ScriptsTab, SettingsTab`) плюс `tk.Tk`; порядок миксинов задаёт порядок вкладок. Правка вкладки — правка её файла.

Слои (импорт только вниз, циклов нет): `ui` → `widgets` → `storage`/`scriptapi`/`proc` → `config`/`paths`/`parsing`/`util`. Никаких `from x import *`. Миксины не импортируют друг друга — только `self`.

`test_imports.py` проверяет, что `android_manager` не импортирует `installer` (иначе exe потянет установщик целиком), что каждый модуль импортируется и что все глобальные имена где-то объявлены (ловит потерянный `import sys`).

Ключевая идея разделения: **`parsing.py` — чистые функции над текстом вывода `adb`** (`parse_card`, `build_state_batch`, `parse_state_batch`, `parse_proc_stat`, `parse_proc_output`, `mem_from_meminfo`, `parse_df_mb`, `parse_pkgs`, `split_target`). Новую логику разбора кладите туда (или в `util.py`) и покрывайте тестом — проверять окно глазами дороже.

Все обращения к устройству идут через `proc.run([ADB, "-s", serial, ...])`, который возвращает `(rc, out, err)`, не бросает исключений и не открывает окно консоли. Тяжёлые вызовы оборачиваются в `App.bg(job, done)`: поток выполняет `job`, результат кладётся в `self.jobs`, а `_poll` (каждые 80 мс) вызывает `done` уже в главном потоке tkinter — из `done` можно трогать виджеты. Прямые вызовы `run` в обработчиках блокируют UI.

`programs/` — описания внешних программ, по одному JSON на файл, читаются `storage.load_json_folder`; кнопки для них строятся в `ui/actions.py`.

## Пользовательские скрипты

Вкладка «Скрипты» исполняет произвольные `.py` из `scripts/` в пространстве имён, где уже определён объект `adb` (`ScriptAPI`), и одновременно подставляет модуль в `sys.modules`, чтобы работал и `import adb`. `AdbModule` в `scriptapi.py` делегирует все атрибуты живому `ScriptAPI`, иначе `import adb` дал бы только `shell`. Остановка пользователя — исключение `ScriptStop`. `scripts/adb.py` (шаблон — `script_shim.py`) нужен для запуска скриптов **вне** приложения: он берёт API из `__adb_api__` в globals и падает с понятной ошибкой, если скрипт запущен не через вкладку.

`android_checkup.py` — диагностика ТВ: одна большая `adb shell` команда, вывод которой разметан строками `@@key=value`. Запускается как обычный пользовательский скрипт (или из корня репозитория — тогда подхватывается `adb.py`). Списки серверов для пинга и DNS для проверки правятся в «Настройках» (`checkup_servers`, `checkup_dns` в `settings.json`).

## Настройки и экспорт

`settings.json` (в git не входит) мержится с `DEFAULT_SETTINGS` при загрузке, затем проходит `migrate_settings`. `make_bundle`/`apply_bundle` — экспорт/импорт: формат `android-tv-bundle`, тексты скриптов едут внутри бандла, при конфликте имён создаётся копия через `unique_path`, чужие элементы панелей и пультов добавляются, а не заменяют.

## Данные программы

`paths.BASE` — папка рядом с exe при сборке, корень репозитория из исходников. Там лежат `settings.json`, `scripts/`, `apk/`, `programs/`, `screenshots/`, `files/`. `adb`/`scrcpy` ищутся сначала в `tools/<name>/`, затем в PATH (`paths.find_tool`). `bootstrap()` из `__main__.py` создаёт эти папки и пишет `scripts/adb.py`; при импорте побочных эффектов нет — тесты и импорт модулей ничего не создают.

`dist/Android_manager.pyw` — генерируемый артефакт, не редактировать руками.

## Экономия контекста при чтении файлов

- Не читай файлы целиком, если нужна только часть. Сначала найди нужное через grep/glob (имя функции, класса, строки), затем читай диапазон через параметры `offset` и `limit`.
- Для файлов больше ~300 строк всегда используй `offset`/`limit`. Целиком читай только небольшие файлы или когда нужна общая структура.
- Не перечитывай файл, который уже есть в контексте и не менялся. После собственных правок не перечитывай файл целиком для проверки, достаточно прочитать изменённый фрагмент.
- Не читай логи, lock-файлы, сгенерированные и минифицированные файлы, `node_modules`, `dist`, `build`, дампы. Если нужно, используй `tail`/`head`/`grep` с ограничением вывода.
- Перед чтением нескольких файлов определи, какие из них действительно нужны для задачи.
- Если контекст сильно заполнен, предложи `/compact` или `/clear`, прежде чем продолжать.

## Правила

- Не коммитить данные пользователя: `settings.json`, `apk/`, `programs/`, `screenshots/`, `files/`, `scripts/*.py` (кроме `scripts/adb.py`), `dist/`.
- Не читать `dist/`, `__pycache__/`, `apk/`, `files/`, `programs/`, `screenshots/`.
- Докстринги и комментарии короткие, на русском.
- `PROGRAM_SRC` больше нет: установщик собирает exe прямо из пакета (`PyInstaller --paths`).

## C#-порт (dotnet/)

`dotnet/` — порт на C#/.NET 10 + Avalonia 11, живёт отдельно и не влияет на Python-версию.
`Android_manager.pyw` и `android_checkup.py` остаются на Python.

**Два репозитория.** `dotnet/` — это вложенный git-репозиторий со своим `origin`:
`kivinew/AndroidManager-CSharp` (ветка `main`), тогда как корень проекта пушится в
`kivinew/ADB_andrey` (ветка `master`). При этом файлы `dotnet/` отслеживает **и** корневой
репозиторий — так получилось исторически, и это не вложенный submodule. Следствия:

- `git status` в корне не покажет изменения внутри `dotnet/`, если они уже закоммичены во вложенном репозитории (и наоборот) — состояние надо смотреть в обоих.
- Правка файла в `dotnet/` требует коммита в **обоих** репозиториях, иначе копии разъедутся: `git -C dotnet commit` + `git -C dotnet push origin main` и `git commit` в корне + `git push origin master`.
- `auto_commit.ps1` (Task Scheduler, ежедневно в 02:00) делает это автоматически для обоих — отсюда коммиты `Auto-commit: <дата>` в истории.
- Перед коммитом в корень проверять, что `dotnet/` не остался с незакоммиченным изменением: иначе корневой коммит зафиксирует версию, отсутствующую во вложенном репозитории.

- `AndroidManager.Core` — логика без UI, по смыслу повторяет `android_manager`: `Parsing/` (те же чистые функции над выводом adb), `Adb/` (`AdbRunner`, `AdbClient`, `AdbStream`, `ProcessKill`, `AdbServer`), `Devices/`, `Settings/` (`AppSettings`, `Defaults`). `AdbServer.EnsureStarted` при старте проверяет `adb version`, а при молчании делает `kill-server` + `start-server` с повтором — поэтому «пустой список устройств» сначала стоит искать там, а не в `Devices/`.
- `AndroidManager` — оболочка Avalonia: `MainWindow` держит выбор устройства в шапке (он нужен всем вкладкам), вкладки в `Views/` — Подключение, Система (класс `CardsView`), Приложения, Процессы, Консоль, Логи, Действия, Скрипты, Настройки. `Controls/Sparkline` рисует графики на GPU. `Services/` — `AppState` (общее состояние), `UiDialogs` (Подтверждение/Сопряжение), `CustomBars` (кастомные кнопки панелей, редактор с шаблонами и перетаскивание между рядами).
- `AndroidManager.Core.Tests` — xUnit. `dotnet test` на этой машине не работает (testhost падает на `OpenProcess` Access Denied), поэтому тесты запускаются своим раннером: `AndroidManager.SelfCheck`, который находит методы `Fact` и вызывает их сам. Новый тест — просто метод с `[Fact]` в `AndroidManager.Core.Tests`.

Настройки C#-версии — `settings.json` рядом с exe: у неё своя папка, с Python-версией и её настройками они не пересекаются. Ключи в файле snake_case, как у Python-версии, чтобы файлы было видно глазами рядом.

Ловушки переноса с Python: `//` — это flooring, а не усечение (есть `Num.FloorDiv`); новый процесс в `parse_proc_output` получает `dp = 0`, а не «тики минус ноль»; `f"{x:.0f}"` — это не `"{x}"`, иначе в русской локали выйдет «2,5» вместо «2».

Вкладка «Скрипты» (`Views/ScriptsView.axaml.cs`) исполняет скрипты **внешним процессом**, а не внутри приложения: `.py` — `python -c "import runpy…"` с предварительной подстановкой модуля `adb` в `sys.modules`, `.ps1` — `powershell -NoProfile -ExecutionPolicy Bypass -File`, `.sh`/`.bat`/`.cmd` — аналогично своему интерпретатору. Путь к `adb`-шиму (`scripts/adb.py`) создаёт сама вкладка; подключённое устройство приходит в процесс через переменную окружения `ANDROID_SERIAL`, поэтому скрипт не знает про UI и работает при любом состоянии `AppState`. Ограничение подхода: встроенный в приложение ADB-клиент скрипту недоступен — только внешний `adb` из PATH.

Ловушки сборки: перед `dotnet build` закрывать запущенный exe (`taskkill //f //im AndroidManager.exe`), иначе MSB3021/3027. Ошибка XAML оставляет битый инкрементальный кэш — лечится `dotnet build --no-incremental`.