# Разбиение `Android_manager.pyw` на модули — план

Документ описывает, как разложить один файл на пакеты, не сломав ни установщик, ни
сборку `Android-manager.exe`, ни уже установленные копии программы.

Все цифры получены разбором текущего файла (`ast`), ссылки на строки — по состоянию
на коммит `5760aba` (файл `Android_manager.pyw`, 4085 строк).

**Коротко:** файл на 4085 строк = установщик (≈480 строк) + `PROGRAM_SRC` — 3601 строка
программы, лежащая строковым литералом ради сборки exe. Разбиваем на пакеты
`android_manager/` (приложение: 9–12 модулей нижнего слоя + 4 виджета + 12 UI-миксинов)
и `installer/` (8 модулей). Ключевые решения: `App` (140 методов) разрезается **миксинами по
вкладкам**; `PROGRAM_SRC` заменяется генератором `_FILES` в `devtools/build_installer.py`,
а сборка — `PyInstaller --paths`; данные программы остаются рядом с exe. Проверено AST:
предлагаемое разбиение **ациклично**, все 56 верхнеуровневых имён раскладываются по модулям
без правок логики. Практический смысл — стоимость правки агентом: типичная задача падает
с ~54 000 до 5–9 тысяч токенов (§14).

> **Статус: выполнено (этапы 0–2, 5).** Файл разложен на пакеты `android_manager/`
> (30 модулей) и `installer/` (9 модулей); `PROGRAM_SRC` удалён, `App` собран из 11
> миксинов, установщик собирает exe через `--paths`. Перенос проверен
> `devtools/verify_extraction.py`: 115 символов и 140 методов совпадают по AST,
> `dir(App)` не изменился. Отличия от плана: добавлен `installer/errors.py`
> (устраняет цикл `service → build → service`), `ui/common.py` не понадобился
> (импорты генерировались автоматически), `version.py`/`keymap.py`/`startup.py`
> слиты, `app_dir()` считается от пакета (§8.1). Тесты добавлены (этап 4): `tests/` —
> 62 теста на разбор, утилиты, настройки и структурные проверки импортов.

---

## 1. Что есть сейчас

| Файл | Строк | Что это |
|------|-------|---------|
| `Android_manager.pyw` | **4085** | установщик + **вся программа в виде строки** |
| `tvdiag_report.py` | 513 | внешний скрипт диагностики (в `scripts/`) |
| `adb.py` | 41 | заглушка `adb.shell()` для запуска `tvdiag_report.py` без GUI |
| `scripts/adb.py` | 26 | копия заглушки, которую программа сама создаёт в папке `scripts/` |
| `_test_app_tab.py`, `_t1.py`, `_tab_progress.txt` | 43 / 15 / 7293 | отладочный мусор в корне |

Внутри `Android_manager.pyw` три слоя:

| Строки | Что |
|--------|-----|
| 1–106 | шапка установщика: `import`, `APP_EXE`, `VERSION`, `Tooltip`, `_python_exe` |
| **107–3709** | `PROGRAM_SRC = r'''…'''` — **3601 строка самой программы внутри строкового литерала** |
| 3712–4085 | установщик: скачивание adb/scrcpy, `build_program()` (PyInstaller), ярлыки, `InstallerWindow` |

Внутри `PROGRAM_SRC`:

| Строки | Содержимое | Строк |
|--------|-----------|-------|
| 140–235 | константы: `VERSION`, цвета `C`, `PALETTE`, регулярки, `BUILTIN_CMDS`, `LAYOUT` | 96 |
| 236–276 | пути: `app_dir`, `P`, `find_tool`, `BASE`, `ADB`, `SCRCPY` + создание папок при импорте | 41 |
| 277–417 | значения по умолчанию: раскладки пультов, `default_cards`, `DEFAULT_*` | 141 |
| 418–560 | `merge`, `slug`, `unique_*`, `read_text`, `migrate_settings`, `make_bundle`, `apply_bundle` | 143 |
| 561–600 | геометрия: `hit_button`, `flow_layout`, `fit_scale`, `remote_window_rect` | 40 |
| 602–785 | **парсинг** `adb`-вывода: `num`, `parse_card`, `parse_state_batch`, `parse_proc_*`, `mem_from_meminfo`, `parse_df_mb`, `parse_pkgs`, `split_target` | 184 |
| 786–831 | JSON/настройки + `run()` | 46 |
| 832–929 | `ScriptStop`, `ScriptAPI` — API для пользовательских скриптов | 98 |
| 930–1064 | виджеты: `round_rect`, `FlowFrame`, `ButtonPanel`, `ScrollFrame`, `Spark`, `Gauge` | 135 |
| 1065–1175 | `RemoteWindow` | 111 |
| **1177–3682** | **`class App(tk.Tk)` — 140 методов, 2506 строк** | |
| 3684–3709 | `main()` **дважды** и два `if __name__ == "__main__"` | 26 |

---

## 2. Что именно мешает (и что чинится попутно)

1. **`PROGRAM_SRC` — строка, а не код.** Нет подсветки, автодополнения, линтера, `grep` по
   символам, рефакторинга в IDE; любая правка — это правка внутри литерала (см. AGENTS.md:
   «не редактировать небрежно»). Это главная причина разбиения.
2. **Две копии `Tooltip`** — строки 61–103 (установщик) и 155–196 (программа). Побайтово
   одинаковые.
3. **Два `def main()`** (3684 и 3699) и два `if __name__ == "__main__"` (3695 и 3707):
   второй блок перекрывает первый; читателю не очевидно, какой работает.
4. **Установщик тащит текст программы** только затем, чтобы записать его в файл и скормить
   PyInstaller (строка 3834). Формат хранения и сборка связаны жёстко.
5. **`--run` (4058–4070)** исполняет `exec(compile(PROGRAM_SRC, …), globals())` — из-за этого
   `PROGRAM_SRC` обязан оставаться строкой. После разбиения `--run` становится обычным импортом.
6. **Побочные эффекты при импорте**: `os.makedirs` ×5 и запись `scripts/adb.py` на строках
   251–261, а `App.__init__` (1184–1185) при каждом старте пишет `settings.json` на диск.
   Для тестов и для импорта «просто посмотреть» это ловушки.
7. **`BASE = app_dir()`** (243) считается от `__file__`. После переноса в пакет `__file__`
   окажется внутри пакета, и данные (`scripts/`, `apk/`, `settings.json`) уедут в подпапку. Это
   самая частая поломка при таком рефакторинге — учтено в §8.1.
8. **Заглушка `scripts/adb.py` записана как одна escaped-строка** (259) — 20 строк кода в одну
   строку с `\n`. Плюс её копия лежит в `scripts/adb.py`. Два источника правды.
9. **`sys.modules["adb"] = adb_module`** (3534) не восстанавливается: после первого запуска
   скрипта любой последующий `import adb` в процессе получает объект с чужим `serial`.
10. **`VERSION` в двух местах** (37 и 140) и «v1.5» в докстрингах; README знает
    `Android_manager.py`, а в репозитории `Android_manager.pyw`.
11. **`nul` в корне** ломает `grep`/`rg` по всему проекту (`rg: Incorrect function`), а
    `_tab_progress.txt` (245 КБ) — отладочный лог, случайно оказавшийся в репозитории.

---

## 3. Целевая структура

```
ADB/
├── Android_manager.pyw        # 40 строк: argparse → installer.gui / installer.cli / приложение
├── android_manager/           # ПРИЛОЖЕНИЕ (бывший PROGRAM_SRC)
│   ├── __init__.py            # __version__, публичный App
│   ├── __main__.py            # main(): bootstrap() + App().mainloop()
│   ├── version.py             # VERSION, APP_TITLE
│   ├── theme.py               # C, PALETTE, KEY_COL/ACC_COL/RED_COL, REMOTE_W/H, BUNDLE_FORMAT
│   ├── keymap.py              # LAYOUT, to_latin
│   ├── paths.py               # app_dir, BASE, P, SCRIPTS_DIR, SETTINGS_PATH, find_tool, ADB, SCRCPY
│   ├── startup.py             # bootstrap(): папки + заглушка adb.py + нормализация settings.json
│   ├── defaults.py            # раскладки пультов, default_cards, DEFAULT_* (значения по умолчанию)
│   ├── util.py                # merge, slug, unique_path, unique_name, read_text
│   ├── storage.py             # settings.json, JSON-файлы, bundle экспорт/импорт, файлы скриптов
│   ├── geom.py                # hit_button, flow_layout, fit_scale, remote_window_rect
│   ├── parsing.py             # разбор вывода adb (единственный кандидат на настоящие юнит-тесты)
│   ├── proc.py                # run() — запуск процессов (бывший ADB-раннер)
│   ├── scriptapi.py           # ScriptStop, ScriptAPI
│   ├── widgets/
│   │   ├── tooltip.py         # Tooltip, tooltip_btn   (единственная копия)
│   │   ├── frames.py          # FlowFrame, ButtonPanel, ScrollFrame
│   │   ├── canvas.py          # round_rect, Spark, Gauge
│   │   └── remote.py          # RemoteWindow
│   └── ui/                    # App, разложенный на миксины по вкладкам
│       ├── app.py             # App(tk.Tk) + ядро: init, стиль, _build, фон, лог, вкладка «Логи»
│       ├── connection.py      # подключение (adb connect/pair, история, избранное, устройства)
│       ├── bars.py            # настраиваемые кнопки (render_bar/bar_*/меню)
│       ├── dialogs.py         # show_text, popup, ask_fields, ask_multiline, show_result
│       ├── tab_apps.py        # «Приложения»
│       ├── tab_tools.py       # «Инструменты»: каркас + пульт
│       ├── cards.py           # показатели состояния
│       ├── procs.py           # процессы + автообновление
│       ├── actions.py         # scrcpy/vysor/программы/скриншот/клавиши
│       ├── tab_console.py     # «Консоль» + стриминг + автодополнение
│       ├── tab_scripts.py     # «Скрипты»
│       └── tab_settings.py    # «Настройки»
├── installer/                 # УСТАНОВЩИК (бывшие строки 1–106 и 3712–4085)
│   ├── __init__.py
│   ├── config.py              # APP_EXE, DEFAULT_PARENT, URL-ы, USER_DIRS, CSIDL_*, NO_WIN, PYTHON
│   ├── net.py                 # download(), scrcpy_download_url()
│   ├── packages.py            # find_dir_with, install_archive, install_tools, check_adb
│   ├── build.py               # build_program(): PyInstaller + app_src_root()
│   ├── shortcuts.py           # special_folder, make_shortcut, create_shortcuts
│   ├── service.py             # InstallError, resolve_install_dir, check_writable, check_environment, install()
│   ├── gui.py                 # InstallerWindow
│   └── cli.py                 # argparse: --cli / --run / --dir
├── devtools/                  # вместо _test_app_tab.py / _t1.py
│   ├── smoke_gui.py           # запуск окна на 2 сек, ловля исключений и зацикливания layout
│   ├── verify_extraction.py   # сверка «старый PROGRAM_SRC ↔ новый пакет» по AST
│   └── build_installer.py     # сборка одного файла dist/Android_manager.pyw
├── tests/                     # stdlib unittest, без зависимостей
│   ├── test_parsing.py
│   ├── test_storage.py
│   └── test_geom.py
├── scripts/  tvdiag_report.py  adb.py   # как сейчас
└── README.md  AGENTS.md  VERSIONS.md  PLAN_MODULES.md
```

Итого: 12 UI-модулей + 8 модулей установщика + 4 виджета + 12 модулей нижнего слоя
вместо одного файла на 4085 строк; самый большой — ~380 строк.

---

## 4. Куда переезжает каждая сущность

Строки — исходные, в `Android_manager.pyw`.

| Новый модуль | Строки источника | Что |
|---|---|---|
| `android_manager/version.py` | 140–141 | `VERSION`, `APP_TITLE` (единственный источник) |
| `android_manager/theme.py` | 142–151, 198, 278–280 | `BUNDLE_FORMAT`, `REMOTE_W/H`, `C`, `PALETTE`, `KEY_COL/ACC_COL/RED_COL` |
| `android_manager/keymap.py` | 226–233 | `LAYOUT`, `to_latin` |
| `android_manager/paths.py` | 237–247, 250, 263, 266–274 | `app_dir`, `P`, `BASE`, `SCRIPTS_DIR`, `SETTINGS_PATH`, `find_tool`, `ADB`, `SCRCPY` |
| `android_manager/startup.py` | 251–261, 1185 | создание папок, запись `scripts/adb.py`, `save_settings(load_settings())` |
| `android_manager/defaults.py` | 283–417 | `_btn`, `standard/tanix/eltex_layout`, `default_remotes`, `default_cards`, `DEFAULT_APPS_BAR`, `DEFAULT_CONSOLE_BAR`, `DEFAULT_SCRIPT_FILES`, `DEFAULT_SETTINGS` |
| `android_manager/util.py` | 418–441, 765 | `merge`, `slug`, `unique_path`, `unique_name`, `read_text` |
| `android_manager/storage.py` | 442–560, 786–820, 224 | `save_script_text`, `import_script_file`, `migrate_settings`, `make_bundle`, `apply_bundle`, `load/save_settings`, `write_json`, `load_json_folder`, `LEGACY_TOOL_NAMES` |
| `android_manager/geom.py` | 561–600 | `hit_button`, `flow_layout`, `fit_scale`, `remote_window_rect` |
| `android_manager/parsing.py` | 201–203, 602–785 | `IP_RE/CYR_RE/NUM_RE`, `num`, `cpu_totals`, `card_numbers`, `parse_card`, `build_state_batch`, `parse_state_batch`, `parse_proc_stat`, `parse_proc_output`, `mem_from_meminfo`, `parse_df_mb`, `split_target`, `parse_pkgs`, `detect_pc_ip`, `PROC_LINES`/`PROC_CMD` |
| `android_manager/proc.py` | 200, 821–830 | `NO_WIN`, `run()` |
| `android_manager/scriptapi.py` | 832–929 | `ScriptStop`, `ScriptAPI` |
| `android_manager/widgets/tooltip.py` | 154–196 (+ 61–103 убрать) | `Tooltip`, `tooltip_btn` |
| `android_manager/widgets/frames.py` | 937–1018 | `FlowFrame`, `ButtonPanel`, `ScrollFrame` |
| `android_manager/widgets/canvas.py` | 931–935, 1020–1064 | `round_rect`, `Spark`, `Gauge` |
| `android_manager/widgets/remote.py` | 1065–1174 | `RemoteWindow` |
| `android_manager/ui/app.py` | 1176–1433, 3633–3644, 3679–3682 | `App.__init__`, `bg`, `_poll`, `_drain_script`, `log`, `dev`, `_style`, `_ctrl_keys`, `_build`, `tab_logs`, `tab_about`, `on_close` |
| `android_manager/ui/connection.py` | 1434–1660 | `_fix_host/port`, `history/favorites_menu`, `pick_*`, `connect`, `disconnect`, `pair_dialog`, `refresh_devices`, `device_info`, `check_connection`, `load_caches` |
| `android_manager/ui/bars.py` | 1661–1846 | `render_bar`, `bar_menu/move/delete/edit_any/click/edit` |
| `android_manager/ui/dialogs.py` | 1271–1302, 1847–1906, 3646–3676 | `show_text`, `copy_text`, `popup`, `ask_multiline`, `run_popup_cmd`, `show_result`, `ask_fields` |
| `android_manager/ui/tab_apps.py` | 1907–2255 | вкладка «Приложения» (17 методов) |
| `android_manager/ui/tab_tools.py` | 2256–2545 | «Инструменты»: каркас + пульт (18) |
| `android_manager/ui/cards.py` | 2546–2765 | показатели состояния + `on_sub_tab`/`on_main_tab` (14) |
| `android_manager/ui/procs.py` | 2766–2912 | процессы, `_auto_tick`, `_set_show_touches` (10) |
| `android_manager/ui/actions.py` | 2913–3023 | `scrcpy_start`, `vysor_start`, программы, скриншот, `reboot`, `key` (7) |
| `android_manager/ui/tab_console.py` | 205–222, 3024–3423 | «Консоль», стриминг, автодополнение (19 методов); `BUILTIN_CMDS`, `SUBCMDS`, `PKG_CMDS`, `PKG_SUBS` — данные подсказок |
| `android_manager/ui/tab_scripts.py` | 3424–3568 | «Скрипты» (7) |
| `android_manager/ui/tab_settings.py` | 3569–3631 | «Настройки», экспорт/импорт (4) |
| `android_manager/__main__.py` | 3684–3696 | `main()` (дубль 3699–3709 удалить) |
| `installer/config.py` | 35–57 | `APP_EXE`, `DEFAULT_PARENT`, `PLATFORM_TOOLS_URL`, `SCRCPY_API`, `HEADERS`, `NO_WIN`, `PYTHON`, `USER_DIRS`, `CSIDL_*`; `VERSION`/`APP_TITLE` берутся из `android_manager.version` |
| `installer/net.py` | 3753–3770, 3798–3807 | `download`, `scrcpy_download_url` |
| `installer/packages.py` | 3773–3796, 3810–3826, 3902–3910 | `find_dir_with`, `install_archive`, `install_tools`, `check_adb` |
| `installer/build.py` | 3829–3858 | `build_program` → `--paths app_src_root()` + PyInstaller |
| `installer/shortcuts.py` | 3738–3742, 3873–3900 | `special_folder`, `make_shortcut`, `create_shortcuts` |
| `installer/service.py` | 3713–3735, 3745–3750, 3913–3932 | `InstallError`, `resolve_install_dir`, `check_writable`, `check_environment`, `install` |
| `installer/gui.py` | 3936–4056 | `InstallerWindow` |
| `installer/cli.py` | 4058–4080 | `main()` с `argparse` |
| `Android_manager.pyw` | — | 30–40 строк: `from installer.cli import main; main()` |

---

## 5. Слои и правила импорта

Направление — **только сверху вниз**. Проверено разбором AST по фактическим ссылкам
между символами: **циклов 0**.

```
L3  android_manager/ui/*            (12 модулей: App и миксины)
L2  android_manager/widgets/*       (tkinter-виджеты)
L1  scriptapi, storage, proc, startup   (работа с внешним миром и файлами)
L0  version, theme, keymap, paths, defaults, util, geom, parsing   (без tkinter, почти без I/O)
```

Фактические рёбра (только межмодульные, остальное — внутри слоя):

```
ui.app           → defaults, geom, keymap, parsing, paths, proc, scriptapi, storage, util,
                   widgets.canvas, widgets.frames, widgets.remote, widgets.tooltip
widgets.remote   → geom, storage, widgets.canvas, widgets.frames, widgets.tooltip
widgets.frames   → geom
storage          → defaults, util
scriptapi        → parsing, proc
```

Правила, которые надо соблюдать при переносах:

- **L0 не импортирует `tkinter`** — это делает парсинг и настройки тестируемыми без окна.
- **Ни один миксин не импортирует другой миксин.** Взаимные вызовы — только через `self`
  (так они и написаны сейчас).
- **Никаких `from x import *`.** Каждый миксин явно импортирует нужное из `ui/common.py`
  (re-экспорт `tk`, `ttk`, `C`, `tooltip_btn`, `FlowFrame`, `P`, `ADB`, `save_settings`, …),
  чтобы не повторять 10 строк импортов в 12 файлах.
- **Модуль внутри пакета не должен называться `adb`** — это имя занято заглушкой для
  пользовательских скриптов (`sys.modules["adb"]`, `scripts/adb.py`). Поэтому раннер
  называется `proc.py`, а не `adb.py`.
- **`paths.py` не должен импортировать ничего из пакета**, кроме stdlib: его значения
  (`BASE`, `ADB`) вычисляются на импорте и нужны всем.

---

## 6. Как `App` перестаёт быть god-объектом

`App` — 140 методов / 2506 строк. Разносить их по классам-контроллерам сразу — большой
передел: методы обращаются к десяткам `self.*`-атрибутов, созданных в `__init__`.

**Решение: миксины по вкладкам** (на первом этапе — механический перенос, ноль правок логики):

```python
# android_manager/ui/app.py
import tkinter as tk
from .connection import ConnectionMixin
from .bars import BarsMixin
from .dialogs import DialogsMixin
from .tab_apps import AppsTab
from .tab_tools import ToolsTab
from .cards import CardsMixin
from .procs import ProcsMixin
from .actions import ActionsMixin
from .tab_console import ConsoleTab
from .tab_scripts import ScriptsTab
from .tab_settings import SettingsTab
from .common import C, ttk, scrolledtext, Tooltip, tooltip_btn, FlowFrame, ...

class App(AppsTab, ToolsTab, CardsMixin, ProcsMixin, ActionsMixin,
          ConsoleTab, ScriptsTab, SettingsTab,
          ConnectionMixin, BarsMixin, DialogsMixin, tk.Tk):
    def __init__(self):
        super().__init__()      # уходит в tk.Tk: у миксинов нет __init__
        ...

# android_manager/ui/tab_apps.py
class AppsTab:
    """Вкладка «Приложения». Требует self.nb, self.S, self.log, self.bg, ..."""
    def tab_apps(self, nb): ...
```

Почему так:

- перенос строк **дословный** — методы не меняются, `self.` остаётся `self.`;
- `tk.Tk` — последний в списке баз, MRO разрешается без сюрпризов;
- проверяемость: до и после сравниваются `sorted(dir(App))` и `App.__mro__` — набор
  методов обязан совпасть;
- дальше (необязательно, отдельным этапом) `cards`/`procs` можно превратить в настоящие
  классы с явными зависимостями — но уже без риска для остального.

Документируемый минимум: в докстринге каждого миксина перечислить нужные `self.*`
(они перечислены в `App.__init__`, строки 1184–1207). Это дешёвая замена «контракту» класса.

---

## 7. Упаковка: как сохранить «один файл» установщика

Сейчас: установщик = один `.pyw`; внутри него текст программы; `build_program()`
(3829–3858) пишет его в `work/src/Android-manager.py` и запускает PyInstaller.

После разбиения «программа» — дерево файлов. Варианты:

### Вариант A (рекомендуется) — генерируемый самораспаковывающийся установщик

- Источник правды — пакеты `installer/` и `android_manager/` в репозитории.
- `devtools/build_installer.py` собирает `dist/Android_manager.pyw`: карта
  `_FILES = {"android_manager/__init__.py": "...", ...}` + лончер на ~20 строк, который
  1) распаковывает карту в `%TEMP%\android_manager-src-<VERSION>\`,
  2) делает `sys.path.insert(0, tmp)`,
  3) вызывает `from installer.cli import main; main()`.
- Пользователю — один файл и двойной клик, как сейчас; внутри — нормальные модули, включая
  общий `widgets/tooltip.py`, который импортирует и установщик.
- Минусы: артефакт ~250 КБ генерируется (коммитить не нужно), распаковка ~200 КБ на старте
  (доли секунды), временная папка требует уборки (`atexit`/`shutil.rmtree(ignore_errors=True)`).

`build_program()` после этого не пишет исходники сам, а указывает PyInstaller, где лежит пакет:

```python
def build_program(log, work):
    src_dir = os.path.join(work, "src")
    os.makedirs(src_dir, exist_ok=True)
    entry = os.path.join(src_dir, APP_EXE + ".py")
    with open(entry, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("from android_manager.__main__ import main\nmain()\n")
    root = app_src_root()                       # папка, содержащая android_manager/
    if not os.path.isdir(os.path.join(root, "android_manager")):
        raise InstallError("Не найдены исходники программы")
    cmd = [PYTHON, "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed",
           "--name", APP_EXE, "--paths", root,
           "--distpath", os.path.join(work, "dist"),
           "--workpath", os.path.join(work, "build"),
           "--specpath", src_dir, entry]
```

где `app_src_root()` — в репозитории корень проекта, в собранном установщике — распакованная
временная папка. `--add-data` не нужен: данных-файлов у программы нет.

Проверить `--paths` один раз живой сборкой. Если PyInstaller не соберёт пакет — страховочный
вариант: `shutil.copytree(root/"android_manager", src_dir/"android_manager")` и сборка без
`--paths` (тогда копирование становится явным шагом `build_program`).

### Вариант A' — тот же генератор, но артефакт в корне репозитория

`devtools/build_installer.py` пишет `Android_manager.pyw` в корень, файл коммитится.
Плюс: после рефакторинга репозиторий по-прежнему «один файл», привычка не меняется.
Минус: каждая правка кода тянет дифф на 250 КБ генерируемого файла; легко забыть пересобрать
(ложится тестом «сгенерированный файл совпадает с пакетами», §10.6).

Если важнее нулевые изменения в процессе — это A'. Если важнее чистый git — A.

### Вариант B — zipapp

`python -m zipapp src -m installer.cli:main -o Android_manager.pyz`. Один файл, но запускать
надо `python Android_manager.pyz`, а PyInstaller-сборке придётся читать членов архива из
`sys.argv[0]`. Больше магии — меньше выгоды.

### Вариант C — папка вместо файла

Распространять `ADB-installer/` с `Android_manager.pyw` + пакетами. Проще в поддержке,
но ломает обещание README и привычку «скинуть коллеге один файл».

**Итого: A** (A' — если процесс важнее чистоты git). Вариант C работает бесплатно в режиме
разработки: `python Android_manager.pyw` из репозитория запускает установщик сразу, потому что
`app_src_root()` указывает на корень проекта.

И `--run`:

```python
if args.run:                      # было: exec(compile(PROGRAM_SRC, ...), globals())
    from android_manager.__main__ import main as run_app
    run_app()
    return
```

---

## 8. Тонкие места (проверить руками при переносе)

1. **`BASE` / `app_dir()`.** Сейчас `dirname(__file__)`; в пакете это стало бы
   `<install>/android_manager`. Правильно:

```python
def app_dir():
    if getattr(sys, "frozen", False):            # собранный exe
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # корень репозитория
```

   Проверка: после запуска из репозитория `settings.json` появляется в корне, а не в
   `android_manager/`; у собранного exe — рядом с `Android-manager.exe`.

2. **Побочные эффекты импорта → `startup.bootstrap()`.** Ни `makedirs`, ни записи
   `scripts/adb.py`, ни `save_settings` на уровне модулей. Вызов — из `__main__.main()`
   (и из `installer` перед `--run`). Иначе `import android_manager.parsing` в тестах создаст
   папки и файлы в текущем каталоге.

3. **Заглушка `adb.py`.** Строку 259 развернуть в нормальный текст в
   `android_manager/script_shim.py` (`ADB_SHIM_SRC = '''…'''`), писать её из `bootstrap()`.
   Файл `scripts/adb.py` в репозитории — либо удалить (пусть генерируется), либо оставить
   как эталон и сравнивать.

4. **`sys.modules["adb"]`.** Сохранять/восстанавливать:

```python
prev = sys.modules.get("adb")
sys.modules["adb"] = adb_module
try:
    exec(compile(code, path, "exec"), namespace)
finally:
    if prev is None: sys.modules.pop("adb", None)
    else:            sys.modules["adb"] = prev
```

5. **`VERSION`** — только `android_manager/version.py`; установщик импортирует его
   (`from android_manager.version import VERSION, APP_TITLE`) — модуль без зависимостей.
   Заодно поправить докстринги «v1.5» → 1.7/1.8.

6. **`Tooltip`** — одна копия в `widgets/tooltip.py`. Установщик импортирует её оттуда же:
   в варианте A пакеты уже распакованы в `sys.path`, в варианте C лежат рядом; дубль не нужен.
   Если когда-нибудь понадобится установщик без пакета — лучше 42 строки продублировать
   осознанно, чем тащить полпакета.

7. **Порядок определений.** `default_cards()` вызывает `_btn`; `migrate_settings` — `merge`;
   при переносе сохранять порядок «снизу вверх» (`defaults` → `storage` → `ui`), иначе
   получите `ImportError` на импорте, а не при вызове.

8. **`PROC_CMD`** (строка 694) — константа, собранная из `PROC_LINES`; если разложить их в
   разные модули, сборка команды сломается. Оба — в `parsing.py`.

9. **Точка входа `.pyw`.** Оставить расширение `.pyw` (запуск без консоли двойным кликом);
   внутри — `try/except` вокруг `main()` с `input("Нажмите Enter…")`, как сейчас в 3684–3692,
   но один раз.

10. **`--cli`** после разбиения: `print` вместо GUI-лога, `install()` — без tkinter.
    `installer.service` не должен импортировать `tkinter`, иначе `--cli` получит лишнюю
    зависимость (на Windows она есть, но чистота полезна).

---

## 9. Этапы (каждый — рабочий коммит)

### Этап 0. Зафиксировать базу (30 мин)

- `git add -A && git commit` — сейчас `Android_manager.pyw` вообще не в git
  (`D Android_manager.py` + `?? Android_manager.pyw`). Рефакторинг без базовой точки — рулетка.
- Удалить/игнорировать: `nul`, `_tab_progress.txt`, `_t1.py`, `__pycache__/`,
  `settings.json`, `android_tv_export.json` (это пользовательские данные, не исходники).
- Прогнать вручную и записать, как выглядит «всё работает»: `python Android_manager.pyw`
  (окно установщика), `python Android_manager.pyw --run` (окно программы, обход вкладок),
  «Диагностика ТВ» на живом устройстве.

Проверка: `git status` чистый; приложение стартует.

### Этап 1. Механическая экстракция в пакеты — 4–6 часов

Один заход в ветке `refactor/modules` по таблице §4:

- создать `android_manager/**` (L0 + виджеты + `ui/app.py` пока целым `App`) и `installer/**`;
- перенести код **дословно**, без правок логики;
- удалить `PROGRAM_SRC` (107–3709), добавить `android_manager/__main__.py`;
- `installer.build`: `--paths app_src_root()` + точка входа (§7), `--run` — обычный импорт;
- `Android_manager.pyw` → 30–40 строк;
- заглушку `adb.py` (259) развернуть в `script_shim.py`, заменить запись на импорт константы.

Почему одним заходом: пока литерал существует, код пришлось бы держать в двух местах.
Зато перенос механический, и его проверяет `verify_extraction.py` (§10.1) — она сравнивает
AST каждого бывшего символа.

Проверки: `python -m compileall android_manager installer`;
`python -c "import android_manager.ui.app"`; `python Android_manager.pyw --run`;
`devtools/smoke_gui.py`; `verify_extraction.py` — 0 расхождений.

### Этап 2. Разрезать `App` на миксины — 4–6 часов

- 12 файлов `ui/*`, `class App(...)` через множественное наследование (§6);
- `ui/common.py` с re-экспортами;
- в докстринг каждого миксина — список нужных `self.*`.

Проверки: `sorted(dir(App))` и `App.__mro__` совпадают с базой; smoke-тест обходит все вкладки
(`nb.select(i)` в цикле), переключает подвкладки «Инструментов», открывает/закрывает пульт,
запускает пустой скрипт, экспортирует/импортирует bundle.

### Этап 3. Чистка после переноса — 2 часа

- удалить дубль `Tooltip`, дубль `main()`, второй `VERSION`;
- `bootstrap()` и `app_dir()` по §8.1–8.2;
- восстановление `sys.modules["adb"]` (§8.4);
- `ruff`/`pyflakes` (если поставить) — убрать «unused import» после разбиения.

### Этап 4. Тесты и devtools — 3 часа

- `tests/test_parsing.py`: `parse_proc_stat`, `parse_proc_output`, `parse_state_batch`,
  `mem_from_meminfo`, `parse_df_mb`, `parse_pkgs`, `split_target`, `cpu_totals`, `num`;
- `tests/test_storage.py`: `merge`, `migrate_settings`, `make_bundle`/`apply_bundle` на временной папке;
- `tests/test_geom.py`: `flow_layout`, `hit_button`, `fit_scale`, `remote_window_rect`;
- `devtools/smoke_gui.py` вместо `_test_app_tab.py` (тот парсит маркер `PROGRAM_SRC = r'''`
  и после этапа 1 не работает);
- `devtools/verify_extraction.py`, `devtools/build_installer.py`.

Проверка: `python -m unittest discover -s tests -v`.

### Этап 5. Сборка и приёмка — 2 часа

- `python devtools/build_installer.py` → `dist/Android_manager.pyw`;
- запустить его в пустой папке → ярлыки, `tools/`, exe;
- запустить собранный `Android-manager.exe`: вкладки, пульт, скрипт `tvdiag_report.py`,
  `settings.json` — рядом с exe;
- переустановка поверх (сохранение пользовательских данных) — критичный сценарий.

### Этап 6. Документация — 1 час

- README: таблица файлов, структура репозитория, «как запустить из исходников»,
  откуда брать установщик для распространения;
- AGENTS.md: новый layout, слои, запрет `import *`, `python -m unittest`, где точка входа,
  что `PROGRAM_SRC` больше нет, **карта «задача → файл»** и список «не читать» (§14.2);
- VERSIONS.md: запись v1.8 «модульная структура»;
- `PLAN_MODULES.md` → `ARCHITECTURE.md` (или удалить, когда сделано).

Итого: ~2 рабочих дня аккуратной работы, из них ~70 % — механический перенос.

---

## 10. Автоматические сверки (страховка от «потеряли строку»)

### 10.1. `devtools/verify_extraction.py`

Сравнивает старый `PROGRAM_SRC` (из git-версии файла) с новым пакетом:

```python
# псевдокод
old = ast.parse(program_src_from_git())          # 56 уникальных верхнеуровневых имён
new = {name: node for path in package_files()    # символы ищутся по всем модулям пакета
       for node in ast.parse(path.read_text()).body
       if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
for name in old_names:
    assert name in new, name
    assert ast.unparse(old[name]) == ast.unparse(new[name]), name
# константы: ast.literal_eval для VERSION, C, PALETTE, DEFAULT_SETTINGS, BUILTIN_CMDS …
```

Дословный перенос даёт `ast.unparse`-равенство; если оно упало — сравните, что именно
изменилось (нормализация кавычек/пробелов `unparse` одинакова с обеих сторон, так что
расхождение означает реальную правку).

### 10.2. Совпадение интерфейса `App`

```python
old = set(dir(App_baseline)); new = set(dir(App_new))
assert old - new == set(), old - new     # ничего не потеряли
assert new - old == set()                # и не приобрели случайного
```

### 10.3. `devtools/smoke_gui.py`

Текущий `_test_app_tab.py` уже умеет главное — детектировать зацикливание
`after_idle`/`relayout` и логировать шаги. Переписать его на нормальный импорт
(без чтения `PROGRAM_SRC`), добавить проход по всем вкладкам и закрытие пульта.

### 10.4. Тесты парсинга (обязательный минимум)

`parse_proc_stat`, `parse_proc_output`, `parse_state_batch`, `mem_from_meminfo`,
`parse_df_mb`, `parse_pkgs`, `split_target`, `cpu_totals`, `num` — это чистые функции от
строк; это единственные места, где ошибка не видна глазом и не ловится запуском GUI.
Именно на них сейчас нет ни одного теста (см. AGENTS.md, Pitfalls).

### 10.5. Приёмка установщика

`python Android_manager.pyw --cli --dir %TEMP%\am_test` в отдельной папке; проверки:
`tools/adb/adb.exe`, `tools/scrcpy/scrcpy.exe`, `Android-manager.exe`, 5 пользовательских
папок, ярлыки на рабочем столе/в «Пуск», `settings.json` рядом с exe после первого запуска.

### 10.6. Сверка сгенерированного установщика с пакетами

Если выбран вариант A' (артефакт коммитится), тест «сгенерированный файл актуален»:

```python
files = {f.relative_to(ROOT).as_posix(): f.read_text(encoding="utf-8")
         for d in PACKAGE_DIRS for f in (ROOT / d).rglob("*.py")}
gen = read_embedded_files(ROOT / "Android_manager.pyw")      # ast.literal_eval по _FILES
assert files == gen, sorted(set(files) ^ set(gen))
```

Для варианта A тот же тест запускается в `devtools/build_installer.py` перед записью артефакта.

---

## 11. Что ещё поправить по дороге

| Место | Проблема | Что сделать |
|---|---|---|
| 3534 | `sys.modules["adb"]` не восстанавливается | `try/finally`, §8.4 |
| 259 | заглушка в одну escaped-строку | `script_shim.py`, §8.3 |
| 1184–1185 | запись `settings.json` на каждом старте | перенести в `bootstrap()`, писать только при изменении |
| 3684/3699 | два `main()` | оставить один |
| 61–103 vs 155–196 | два `Tooltip` | один в `widgets/tooltip.py` |
| 37/140 | `VERSION` в двух местах | `version.py` |
| 1218 | `if not os.path.isfile(ADB)` — проверка на старте | в `startup.bootstrap()` → warning в лог |
| `nul` | ломает `rg` по проекту | удалить, добавить в `.gitignore` |
| `_tab_progress.txt` | 245 КБ лога в репозитории | удалить, `devtools/` пишет логи в `%TEMP%` |
| `settings.json`, `android_tv_export.json` | пользовательские данные в корне | в `.gitignore`, оставить только пример `settings.example.json` |

---

## 12. Риски

| Риск | Вероятность | Как снижаем |
|---|---|---|
| `BASE` уедет в подпапку пакета → данные «теряются» | высокая, если не заметить | §8.1 + приёмка этапа 5 (settings.json рядом с exe) |
| Побочные эффекты импорта создадут папки в тестах | высокая | `bootstrap()`, §8.2 |
| PyInstaller не найдёт пакет | низкая | `--paths app_src_root()`, fallback — `copytree` в `src/`; тестовая сборка на этапе 5 |
| Миксины ломают MRO / теряют метод | средняя | сверка `dir(App)` и `__mro__`, smoke-тест |
| Дубль `PROC_CMD`/`PROC_LINES` рассинхронизируется | средняя | оба в `parsing.py` |
| Пользовательские скрипты (`tvdiag_report.py`, `import adb`) сломаются | низкая | `sys.modules` фикс + приёмка на реальном скрипте |
| Генератор `dist/Android_manager.pyw` разъедется с пакетом | средняя | генерация перед релизом + сверка §10.6 |
| Из репозитория исчезает «один файл, который ставит программу» | средняя | вариант A': артефакт коммитится; вариант A — README объясняет, что брать из `dist/` |
| Нет тестов → регрессии не видны | **высокая сейчас** | этап 4; этапы 1–3 — только перенос без правок логики |

---

## 13. Порядок, если делать «прямо сейчас» (короткая версия)

1. Коммит текущего состояния, чистка мусора.
2. Ветка `refactor/modules`: механический перенос всего в `android_manager/**` +
   `installer/**`, `Android_manager.pyw` → лончер, `PROGRAM_SRC` → генератор `_FILES`,
   сборка через `--paths`.
3. Миксины по вкладкам + `ui/common.py`.
4. Чистка: `bootstrap()`, `app_dir()`, дубли, `sys.modules["adb"]`.
5. `unittest` на парсинг, `verify_extraction.py`, `smoke_gui.py`.
6. `devtools/build_installer.py`, установка в пустую папку, переустановка поверх.
7. README/AGENTS/VERSIONS.

Промежуточное состояние после п. 2 уже даёт главное: код программы — нормальные `.py`
файлы, которые видят IDE, линтер, git-diff и `grep`.

---

## 14. Экономия токенов при работе с ИИ (зачем это всё)

Цель разбиения — не красота, а стоимость правки агентом. Измерено по текущему файлу
(≈3,2 байта на токен для смеси русского текста и Python; русский текст дороже английского
примерно в полтора раза):

| Что | Строк | Байт | ≈ токенов |
|---|---|---|---|
| Весь `Android_manager.pyw` | 4085 | 173 188 | **54 000** |
| `PROGRAM_SRC` (программа) | 3601 | 154 263 | 48 000 |
| Установщик (1–106 + 3712–4085) | 480 | 18 878 | 5 900 |
| Будущий UI-модуль (вкладка) | 110–400 | 5–17 КБ | 1 500–5 200 |
| `App.__init__` — контракт атрибутов | 60 | — | ~900 |
| L0-блок (парсинг+настройки+умолчания) | 691 | 25 КБ | 7 800 (по модулям 1,5–2,5k) |

Стоимость типовой задачи «найти и поправить»:

| Задача | Сейчас | После разбиения |
|---|---|---|
| Правка установщика | ~54k (файл целиком) | ~6k |
| Правка вкладки, агент читает файл целиком (обычный режим) | ~54k | ~5k |
| Правка вкладки аккуратным срезом по `offset` | ~9k | ~7k |
| Кросс-задача («почему не обновляются показатели») | 20k+ (поиск по 139 методам) | ~9k (cards + parsing + ядро) |

Выигрыш даёт не число файлов, а два свойства: **модуль, который можно прочитать целиком**
(≤400 строк), и **карта**, по которой не нужно искать.

### 14.1. Где предел: «больше модулей» ≠ «дешевле»

- Каждый модуль платит шапкой (`import` + docstring) ≈ 0,5–0,8k токенов при каждом чтении.
- Файл <80 строк почти всегда читают вместе с соседом — платите дважды.
- Сквозная правка (новый `self.x`, смена сигнатуры хелпера) при 12 модулях — 3 правки,
  при 30 — 8: больше вызовов `edit`, и каждый несёт контекст.
- Каждый лишний файл — ещё один шаг навигации: `glob`/`grep`/`read` в сессии агента.

Правило: **модуль = наименьшая единица, которую правдоподобная задача трогает целиком**.
Для этого проекта это «вкладка», «семейство парсеров», «набор виджетов»: 200–400 строк,
2–5k токенов. Поэтому 12 UI-модулей — на месте; `parsing.py` (184 строки) и `widgets/*`
дробить не надо; `tab_console.py` (400 строк) стоит делить, только если появится спрос на
отдельные правки стриминга и автодополнения.

Ориентир по числу файлов: **25–35 модулей на проект такого размера**; 50+ почти наверняка
ухудшит и стоимость, и качество правок. Счётчик вторичен: важно, чтобы большинство модулей
попадало в 150–400 строк, а короткими оставались только константы и тонкие адаптеры.

Практическое следствие для плана выше: три модуля из §3 меньше 80 строк и их стоит слить —
`version.py` → `config.py` (там же `APP_TITLE`, `VERSION`, `BUNDLE_FORMAT`), `keymap.py` →
`util.py` (`to_latin` — текстовая утилита), а `bootstrap()` — прямо в `__main__.py`
(10 строк, вызывается один раз). Тогда нижний слой — 9 модулей, всего ~31 файл кода.

Не стоит дробить:
- `parsing.py` (184 строки) — парсеры вызываются вместе, тесты пишутся на весь модуль;
- `widgets/frames.py`, `widgets/canvas.py` — наборы из 2–3 классов по 40–120 строк;
- `cards.py` (241) и `tab_console.py` (400) — пока живут как целое; делить, только если
  появится реальный поток задач на «только стриминг» или «только автодополнение».

### 14.2. Что даёт больше, чем дальнейшее дробление

1. **Карта в `AGENTS.md`** — она автоматически попадает в контекст каждой сессии: таблица
   «задача → файл(ы)» на 20–30 строк и список «не читать» (`dist/`, `__pycache__/`,
   `_tab_progress.txt`). ~1,5k токенов один раз, экономия 2–4 поисковых шага на задачу.
   Подробная версия — в `ARCHITECTURE.md`, но агент её не читает, пока не попросят.
2. **Docstring модуля**: назначение, от чего зависит, какие `self.*` нужны. Убирает чтение
   `App.__init__` и соседних вкладок «на всякий случай».
3. **Тесты**: прогон + 10 строк ошибки дешевле, чем рассуждение по 300 строкам кода.
   Это единственный способ проверять парсинг, не читая парсер.
4. **Убрать литерал `PROGRAM_SRC`** — это 48k токенов, которые сегодня попадают в контекст
   при любой правке установщика, плюс запрет `'''` внутри строки, из-за которого правка
   внутри литерала требует лишних перечитываний.
5. **Не коммитить `dist/Android_manager.pyw`** (~250 КБ ≈ 80k токенов): `.gitignore` +
   явный запрет в `AGENTS.md`, иначе следующий агент однажды прочитает сгенерированный файл.
6. **Короткие служебные комментарии.** Русский текст ≈2–2,5 символа на токен против ~4 у
   английского: UI-строки обязаны остаться русскими, но докстринги и комментарии лучше
   писать короче. Это 10–15 % объёма, не главное, но бесплатно.

### 14.3. Итог

- Разбивать — да: **~54k → 5–9k токенов** на типовую правку (в 6–10 раз), потому что
  пропадает необходимость тащить 48k-литерал и появляется «файл = функция».
- Дробить «ещё мельче» — нет: после 200–400 строк на модуль выигрыш исчезает, а навигация
  и сквозные правки дорожают.
- Основной остаточный выигрыш — не в структуре, а в процессе: карта в `AGENTS.md`,
  docstring с контрактом, тесты как дешёвая обратная связь, отсутствие гигантских
  сгенерированных файлов в репозитории.
