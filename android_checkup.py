# -*- coding: utf-8 -*-
"""
ДИАГНОСТИКА ANDROID-УСТРОЙСТВА для Android manager.

Универсальная версия: работает на обычных Android-устройствах (телефоны,
планшеты, ТВ-приставки, ТВ-боксы). Всё, что есть только у фирменных приставок
(Amlogic GPU/HDMI/CEC, серверы провайдера), проверяется по возможности и
пропускается, если устройство таких путей не предоставляет.

Как добавить: вкладка «Скрипты» -> «Импорт .py» -> выбрать этот файл -> «Сохранить».
Затем запустите кнопку скрипта. Отчёт появится в окне «Результат».

Что делает: отправляет на устройство ОДНУ пакетную команду (adb shell), получает
сырые показания, разбирает их и печатает отчёт с предупреждениями.
На устройстве ничего не меняет и ничего не записывает.
"""

import datetime
import adb  # noqa: F401  -- предоставляется Android-manager при автономном запуске; локальная обёртка adb.py имитирует тот же интерфейс

# Команды, которые выполняются на устройстве. Каждая строка печатает "@@ключ=значение".
# Строки объединяются через "; " и уходят одним вызовом adb shell.
# Синтаксис — чистый POSIX sh: одинаково работает от Android 5 до Android 15.
COMMANDS = r'''
echo "@@model=$(getprop ro.product.model)"
echo "@@brand=$(getprop ro.product.brand)"
echo "@@manufacturer=$(getprop ro.product.manufacturer)"
echo "@@devname=$(getprop ro.product.device)"
echo "@@board=$(getprop ro.hardware)"
echo "@@soc=$(getprop ro.board.platform)"
echo "@@build=$(getprop ro.build.display.id)"
echo "@@buildtype=$(getprop ro.build.type)"
echo "@@tags=$(getprop ro.build.tags)"
echo "@@debuggable=$(getprop ro.debuggable)"
echo "@@serial=$(getprop ro.serialno)"
echo "@@android=$(getprop ro.build.version.release)"
echo "@@sdk=$(getprop ro.build.version.sdk)"
echo "@@patch=$(getprop ro.build.version.security_patch)"
echo "@@abi=$(getprop ro.product.cpu.abi)"
echo "@@selinux=$(getenforce 2>/dev/null)"
echo "@@rooted=$(id -u 2>/dev/null)"
echo "@@su=$(command -v su >/dev/null 2>&1 && echo yes || echo no)"
echo "@@date=$(date "+%d.%m.%Y %H:%M:%S")"
echo "@@tz=$(getprop persist.sys.timezone)"
echo "@@uptime=$(cut -d " " -f1 /proc/uptime)"
echo "@@btime=$(awk "/^btime/{print \$2}" /proc/stat)"
echo "@@memtotal=$(awk "/^MemTotal/{print \$2}" /proc/meminfo)"
echo "@@memavail=$(awk "/^MemAvailable/{print \$2}" /proc/meminfo)"
echo "@@swap=$(awk "/^SwapTotal/{print \$2}" /proc/meminfo)"
echo "@@cpupart=$(awk -F": *" "/^CPU part/{print \$2; exit}" /proc/cpuinfo)"
echo "@@cpuimpl=$(awk -F": *" "/^CPU implementer/{print \$2; exit}" /proc/cpuinfo)"
echo "@@cpuhw=$(awk -F": *" "/^Hardware|model name/{print \$2; exit}" /proc/cpuinfo)"
echo "@@cpucount=$(grep -c "^processor" /proc/cpuinfo)"
echo "@@online=$(cat /sys/devices/system/cpu/online 2>/dev/null)"
for p in /sys/devices/system/cpu/cpufreq/policy*; do [ -r "$p/scaling_cur_freq" ] && echo "@@cpu $(basename $p | sed "s/policy//") $(cat $p/scaling_cur_freq 2>/dev/null) $(cat $p/cpuinfo_min_freq 2>/dev/null) $(cat $p/cpuinfo_max_freq 2>/dev/null) $(cat $p/scaling_governor 2>/dev/null)"; done
echo "@@load=$(cat /proc/loadavg)"
for z in /sys/class/thermal/thermal_zone*; do [ -r "$z/type" ] && echo "@@tz $(cat $z/type 2>/dev/null) $(cat $z/temp 2>/dev/null)"; done
echo "@@gpucur=$(cat /sys/class/mpgpu/cur_freq 2>/dev/null || cat /sys/class/kgsl/kgsl-3d0/gpuclk 2>/dev/null || cat /sys/class/devfreq/kgsl-3d0/cur_freq 2>/dev/null)"
echo "@@gpumax=$(cat /sys/class/kgsl/kgsl-3d0/max_gpuclk 2>/dev/null || cat /sys/devices/system/cpu/cpufreq/policy0/cpuinfo_max_freq 2>/dev/null)"
echo "@@gpuutil=$(head -1 /sys/class/mpgpu/utilization 2>/dev/null || awk "{print \$1*100/(\$2+1)}" /sys/class/kgsl/kgsl-3d0/gpubusy 2>/dev/null)"
echo "@@gles=$(dumpsys SurfaceFlinger 2>/dev/null | grep -m1 "GLES:" | cut -c1-100)"
echo "@@renderer=$(dumpsys SurfaceFlinger 2>/dev/null | grep -m1 "GLES: " | cut -c1-110)"
echo "@@batlevel=$(dumpsys battery 2>/dev/null | awk "/level:/{print \$2}")"
echo "@@battemp=$(dumpsys battery 2>/dev/null | awk "/temperature:/{print \$2}")"
echo "@@batstat=$(dumpsys battery 2>/dev/null | awk "/status:/{print \$2}")"
echo "@@bathealth=$(dumpsys battery 2>/dev/null | awk "/health:/{print \$2}")"
echo "@@disp=$(wm size 2>/dev/null | tr "\n" " ")"
echo "@@density=$(wm density 2>/dev/null | tr "\n" " ")"
echo "@@refresh=$(dumpsys display 2>/dev/null | grep -m1 -o "fps=[0-9.]*" | cut -d= -f2)"
echo "@@hdmi=$(cat /sys/class/drm/*/status 2>/dev/null | grep -m1 connected)"
echo "@@hpd=$(cat /sys/class/amhdmitx/amhdmitx0/hpd_state 2>/dev/null || echo "")"
echo "@@vmode=$(cat /sys/class/amhdmitx/amhdmitx0/valid_mode 2>/dev/null || echo "")"
echo "@@mode=$(cat /sys/class/display/mode 2>/dev/null || echo "")"
echo "@@cec=$(settings get global hdmi_control_enabled 2>/dev/null)"
echo "@@autotime=$(settings get global auto_time 2>/dev/null)"
echo "@@vdec=$(dmesg 2>/dev/null | grep -c -E "wait resource timeout|decoder timeout|frame number gap error")"
echo "@@fserr=$(dmesg 2>/dev/null | grep -c -E "EXT4-fs error|F2FS-fs .*error|Remounting filesystem read-only|I/O error")"
echo "@@unclean=$(dmesg 2>/dev/null | grep -c -E "not cleanly shutdown|orphan inodes deleted")"
echo "@@therm=$(dmesg 2>/dev/null | grep -c -i -E "thermal.*trip|over.temp")"
echo "@@mmccrc=$(dmesg 2>/dev/null | grep -c -E "mmc[0-9].*CRC|meson-gx-mmc.*CRC")"
echo "@@lowmem=$(dmesg 2>/dev/null | grep -c -i -E "lowmemorykiller|Out of memory|oom-kill")"
echo "@@dmesgfirst=$(dmesg 2>/dev/null | head -1 | cut -c1-20)"
echo "@@logfirst=$(logcat -d 2>/dev/null | grep -v "beginning of" | head -1 | cut -c1-18)"
echo "@@anr=$(logcat -d -t 500 "*:E" 2>/dev/null | grep -c -E "ANR in|FATAL EXCEPTION|died")"
echo "@@abort=$(logcat -d -t 500 "*:E" 2>/dev/null | grep -c -E "Fatal signal 6|SIGABRT|assertion .* failed")"
echo "@@underrun=$(logcat -d -t 500 2>/dev/null | grep -c underrun)"
echo "@@reason=$(getprop sys.boot.reason)"
echo "@@reasonlast=$(getprop sys.boot.reason.last)"
echo "@@history=$(getprop persist.sys.boot.reason.history)"
echo "@@pstore=$(ls /sys/fs/pstore 2>/dev/null | grep -c .)"
echo "@@pstorepanic=$(grep -h -i -E "Kernel panic|Unable to handle" /sys/fs/pstore/* 2>/dev/null | head -1 | cut -c1-110)"
echo "@@freemb=$(df -k /data 2>/dev/null | awk "NR==2{print int(\$4/1024)}")"
echo "@@totmb=$(df -k /data 2>/dev/null | awk "NR==2{print int(\$2/1024)}")"
echo "@@cachefree=$(df -k /cache 2>/dev/null | awk "NR==2{print int(\$4/1024)}")"
echo "@@pkgs=$(pm list packages 2>/dev/null | grep -c .)"
echo "@@userpkgs=$(pm list packages -3 2>/dev/null | grep -c .)"
echo "@@gms=$(pm list packages 2>/dev/null | grep -c "com.google.android.gms")"
echo "@@iface=$(ip route get 8.8.8.8 2>/dev/null | awk "{for(i=1;i<=NF;i++) if(\$i==\"dev\"){print \$(i+1); exit}}")"
echo "@@gateway=$(ip route 2>/dev/null | awk "/^default/{print \$3; exit}"; ip route 2>/dev/null | awk "/via/{for(i=1;i<=NF;i++) if(\$i==\"via\"){print \$(i+1); exit}}")"
echo "@@ipaddr=$(ip -4 addr 2>/dev/null | grep -v 127.0.0.1 | grep -m1 "inet " | awk "{print \$2}")"
echo "@@rssi=$(dumpsys wifi 2>/dev/null | grep -m1 -o "RSSI: -*[0-9]*" | head -1)"
echo "@@ssid=$(dumpsys wifi 2>/dev/null | grep -m1 "mWifiInfo" | grep -o "SSID: [^,]*" | head -1 | cut -c7- | tr -d "\"" | sed "s/<unknown ssid>//")"
echo "@@dns1=$(getprop net.dns1)"
echo "@@dns2=$(getprop net.dns2)"
echo "@@bt=$(settings get global bluetooth_on 2>/dev/null)"
for c in /sys/class/net/*; do n=$(basename $c); [ "$n" = "lo" ] && continue; echo "@@nic $n $(cat $c/operstate 2>/dev/null) $(cat $c/speed 2>/dev/null) $(cat $c/statistics/rx_errors 2>/dev/null) $(cat $c/statistics/tx_errors 2>/dev/null) $(cat $c/statistics/rx_dropped 2>/dev/null) $(cat $c/carrier_changes 2>/dev/null)"; done
echo "@@ping gw $(cat /proc/net/route 2>/dev/null | awk "NR==2{print \$2}" | sed "s/\(..\)\(..\)\(..\)\(..\)/\4.\3.\2.\1/") $(ping -c 1 -W 2 1.1.1.1 2>/dev/null | grep -o "time=[0-9.]*" | cut -d= -f2)"
echo "@@ping dns 1.1.1.1 $(ping -c 1 -W 2 1.1.1.1 2>/dev/null | grep -o "time=[0-9.]*" | cut -d= -f2)"
echo "@@ping gstatic connectivitycheck.gstatic.com $(ping -c 1 -W 3 connectivitycheck.gstatic.com 2>/dev/null | grep -o "time=[0-9.]*" | cut -d= -f2)"
echo "@@ping google google.com $(ping -c 1 -W 3 google.com 2>/dev/null | grep -o "time=[0-9.]*" | cut -d= -f2)"
ps -A -o NAME,RSS 2>/dev/null | awk "NR>1 && \$2+0>0" | sort -k2 -nr | head -6 | awk "{print \"@@top \" \$1 \" \" \$2}"
'''

CPU_PARTS = {
    "0xd01": "Cortex-A32", "0xd03": "Cortex-A53", "0xd04": "Cortex-A35", "0xd05": "Cortex-A55",
    "0xd07": "Cortex-A57", "0xd08": "Cortex-A72", "0xd09": "Cortex-A73", "0xd0a": "Cortex-A75",
    "0xd0b": "Cortex-A76", "0xd0d": "Cortex-A77", "0xd41": "Cortex-A78", "0xd44": "Cortex-X1",
    "0xd46": "Cortex-A510", "0xd47": "Cortex-A710", "0xd48": "Cortex-X2",
}

REASON_WORDS = [
    ("thermal", "перегрев"), ("watchdog", "зависание"), ("wdog", "зависание"),
    ("panic", "паника ядра"), ("kernel", "паника ядра"), ("power", "проблема с питанием"),
    ("battery", "проблема с питанием"), ("ota", "после обновления"), ("update", "после обновления"),
    ("reboot", "обычная перезагрузка"), ("shutdown", "обычная перезагрузка"),
]

BAT_STATUS = {"1": "не заряжается", "2": "заряжается", "3": "разряжается", "4": "не заряжается",
              "5": "почти полная"}
BAT_HEALTH = {"1": "неизвестно", "2": "хорошо", "3": "перегрев", "4": "мёртвая",
              "5": "перегрев напряжения", "6": "сбой", "7": "холодная"}


def reason_word(code):
    if not code:
        return "неизвестно"
    for key, word in REASON_WORDS:
        if key in code:
            return word
    return "другое"


def parse_output(raw):
    kv, tops, pings, dns, tzs, cpus, nics = {}, [], {}, {}, [], [], []
    for line in raw.splitlines():
        if not line.startswith("@@"):
            continue
        body = line[2:]
        parts = body.split(" ")
        if body.startswith("top "):
            if len(parts) >= 3:
                tops.append((parts[1], parts[2]))
        elif body.startswith("ping "):
            name = parts[1] if len(parts) > 1 else ""
            ip = parts[2] if len(parts) > 2 else ""
            ms = parts[3] if len(parts) > 3 else ""
            pings[name] = (ip, ms)
        elif body.startswith("dns "):
            host = parts[1]
            dns[host] = body
        elif body.startswith("tz "):
            if len(parts) >= 3:
                tzs.append((parts[1], parts[2]))
        elif body.startswith("cpu "):
            if len(parts) >= 6:
                cpus.append(parts[1:6])
        elif body.startswith("nic "):
            nics.append(parts[1:])
        else:
            key, _, value = body.partition("=")
            kv[key] = value
    return kv, tops, pings, dns, tzs, cpus, nics


def num(text, default=0):
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return default


def temp_c(raw):
    t = num(raw, -1)
    if t <= 0:
        return None
    return t / 1000 if t > 1000 else float(t)


def mhz_from(raw):
    """Частота в Гц/кГц/МГц -> МГц."""
    v = num(raw, -1)
    if v < 0:
        return None
    if v >= 1000000:
        return v // 1000000
    if v >= 1000:
        return v // 1000
    return v


def parse_history(text):
    """История перезагрузок: 'причина[,подпричина],время' -> список (причина, время или None)."""
    items, cur = [], []
    for tok in text.split(","):
        if tok.isdigit() and len(tok) >= 5:
            items.append((",".join(cur) or "?", int(tok)))
            cur = []
        elif tok:
            cur.append(tok)
    if cur:
        items.append((",".join(cur), None))
    return items


def fmt_ts(ts):
    try:
        return datetime.datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M:%S")
    except (OverflowError, OSError, ValueError):
        return "?"


def or_na(value):
    """Пустая строка -> «н/д»."""
    text = (value or "").strip()
    return text if text else "н/д"


def build_report(raw):
    kv, tops, pings, dns, tzs, cpus, nics = parse_output(raw)
    R, W = [], []

    def head(title):
        R.append("")
        R.append(f"=== {title} ===")

    def row(text):
        R.append("  " + text)

    def warn(text):
        W.append(text)

    # ---------------- устройство
    head("УСТРОЙСТВО")
    row(f"Модель: {or_na(kv.get('model'))} | Устройство: {or_na(kv.get('devname'))}")
    row(f"Производитель: {or_na(kv.get('manufacturer'))} ({or_na(kv.get('brand'))})")
    row(f"Плата: {or_na(kv.get('board'))} | SoC: {or_na(kv.get('soc'))} | ABI: {or_na(kv.get('abi'))}")
    row(f"Серийный номер: {or_na(kv.get('serial'))}")
    row(f"Android {or_na(kv.get('android'))} (SDK {or_na(kv.get('sdk'))}) | "
        f"Патч безопасности: {or_na(kv.get('patch'))}")
    row(f"Сборка: {or_na(kv.get('build'))} | Тип: {or_na(kv.get('buildtype'))}")
    if "test-keys" in (kv.get("tags") or ""):
        row("Подпись: test-keys — неофициальная сборка")
        warn("Неофициальная прошивка (test-keys)")

    # ---------------- аптайм
    head("АПТАЙМ")
    up = num(kv.get("uptime"), 0)
    row(f"{up // 86400} д {up % 86400 // 3600} ч {up % 3600 // 60} мин | "
        f"Старт: {fmt_ts(num(kv.get('btime'), 0))}")
    if 0 < up < 300:
        warn("Устройство перезагрузилось меньше 5 минут назад")

    # ---------------- память
    head("ПАМЯТЬ")
    total = num(kv.get("memtotal")) // 1024
    avail = num(kv.get("memavail")) // 1024
    swap = num(kv.get("swap")) // 1024
    row(f"Всего: {total} МБ | Занято: {total - avail} МБ | Доступно: {avail} МБ")
    if swap:
        row(f"Подкачка (swap): {swap} МБ")
    if tops:
        row("Больше всего памяти (МБ):")
        for name, kb in tops:
            row(f"  {name[:40]}: {num(kb) // 1024}")
    if total and avail < 300:
        warn("Мало оперативной памяти: доступно меньше 300 МБ")
    if num(kv.get("lowmem")) > 0:
        warn(f"Срабатывал OOM/lowmemorykiller: {kv.get('lowmem')} раз")

    # ---------------- процессор
    head("ПРОЦЕССОР")
    part = (kv.get("cpupart") or "").strip()
    impl = (kv.get("cpuimpl") or "").strip()
    if part:
        row(f"Модель: {CPU_PARTS.get(part, 'неизвестно')} ({impl or '?'} / {part})")
    else:
        row(f"Модель: {or_na(kv.get('cpuhw'))}")
    row(f"SoC: {or_na(kv.get('soc'))}")
    cores = num(kv.get("cpucount"), 0)
    row(f"Ядер: {cores} | Онлайн CPU: {or_na(kv.get('online'))}")

    # Кластеры: у современных SoC их 2-3 (big.LITTLE), у старых — один.
    if cpus:
        for idx, cur, mn, mx, gov in cpus:
            cur_m, mn_m, mx_m = mhz_from(cur), mhz_from(mn), mhz_from(mx)
            row(f"Кластер CPU{idx}: текущая {cur_m or '?'} МГц | "
                f"диапазон {mn_m or '?'}..{mx_m or '?'} МГц | режим: {gov or 'н/д'}")
    else:
        row("Частоты CPU: н/д (нет /sys/devices/system/cpu/cpufreq)")

    load = (kv.get("load") or "").split()
    if len(load) >= 3:
        row(f"Нагрузка 1/5/15 мин: {load[0]} / {load[1]} / {load[2]}")
        if cores and float(load[0]) > cores:
            warn(f"Нагрузка CPU выше числа ядер ({load[0]} при {cores} ядрах)")

    # ---------------- температура
    head("ТЕМПЕРАТУРА")
    soc_t = gpu_t = bat_t = None
    named = []
    for ztype, zraw in tzs:
        t = temp_c(zraw)
        if t is None:
            continue
        named.append((ztype, t))
        low = ztype.lower()
        if soc_t is None and any(k in low for k in ("cpu", "soc", "tsens", "aoss", "ap")):
            soc_t = t
        if gpu_t is None and any(k in low for k in ("gpu", "mali", "kgsl")):
            gpu_t = t

    bat_raw = num(kv.get("battemp"), -1)
    # dumpsys battery отдаёт десятые доли градуса. На ТВ-приставках без
    # аккумулятора там лежит фиктивное 26 (=2.6 C), поэтому такие значения
    # отбрасываем: реальная рабочая температура всегда выше 15 C.
    if bat_raw > 150:
        bat_t = bat_raw / 10

    if soc_t is not None:
        row(f"SoC: {soc_t:.1f} C")
        if soc_t > 85:
            warn(f"Перегрев SoC: {soc_t:.1f} C, проверьте вентиляцию")
        elif soc_t > 75:
            warn(f"SoC горячий: {soc_t:.1f} C")
    else:
        row("SoC: н/д (нет датчиков thermal_zone)")
    if gpu_t is not None:
        row(f"GPU: {gpu_t:.1f} C")
        if gpu_t > 75:
            warn(f"GPU горячий: {gpu_t:.1f} C")
    if bat_t is not None:
        row(f"Батарея: {bat_t:.1f} C")
        if bat_t > 45:
            warn(f"Батарея горячая: {bat_t:.1f} C")

    # Полный список датчиков — только если их немного и они не дублируют сводку.
    extra = [(n, t) for n, t in named if n.lower() not in ("cpu", "soc", "gpu", "mali")]
    if extra:
        row("Датчики: " + ", ".join(f"{n}={t:.1f}C" for n, t in extra[:10]))

    # ---------------- графика
    head("ГРАФИКА")
    gcur = mhz_from(kv.get("gpucur"))
    if gcur is not None:
        row(f"Частота GPU: {gcur} МГц")
    util = num(kv.get("gpuutil"), -1)
    if util >= 0:
        row(f"Нагрузка GPU: {util} %")
        if util > 80:
            warn(f"Высокая нагрузка GPU: {util} %")
    if not gcur and util < 0:
        row("Частота/нагрузка GPU: н/д (нет драйверного sysfs)")

    renderer = (kv.get("renderer") or kv.get("gles") or "").strip()
    if renderer:
        row(f"Рендеринг: {renderer}")

    disp = (kv.get("disp") or "").replace("\n", " ").strip()
    dens = (kv.get("density") or "").replace("\n", " ").strip()
    if disp:
        row(f"Экран: {disp}")
    if dens:
        row(f"Плотность: {dens}")
    refresh = (kv.get("refresh") or "").strip()
    if refresh:
        row(f"Частота обновления: {refresh} Гц")

    # ---------------- HDMI (только на ТВ-приставках)
    hdmi = (kv.get("hdmi") or "").strip()
    hpd = (kv.get("hpd") or "").strip()
    if hdmi or hpd:
        head("HDMI / CEC")
        if hpd == "1" or hdmi == "connected":
            row("Внешний дисплей: подключён")
        elif hpd == "0" or hdmi == "disconnected":
            row("Внешний дисплей: не подключён")
        else:
            row(f"HDMI: {or_na(hdmi)}")
        cec = (kv.get("cec") or "").strip()
        if cec in ("0", "1"):
            row(f"CEC: {'включён' if cec == '1' else 'выключен'}")
        mode = (kv.get("mode") or "").strip()
        if mode:
            row(f"Режим вывода: {mode}")
            if "cvbs" in mode:
                warn("Вывод идёт по CVBS, а не по HDMI")

    # ---------------- питание
    head("ПИТАНИЕ")
    level = num(kv.get("batlevel"), -1)
    status = (kv.get("batstat") or "").strip()
    health = (kv.get("bathealth") or "").strip()
    if level >= 0:
        row(f"Заряд: {level} % | {BAT_STATUS.get(status, status or 'н/д')}")
        if health:
            row(f"Состояние батареи: {BAT_HEALTH.get(health, health)}")
            if health not in ("", "1", "2"):
                warn(f"Проблема с батареей: {BAT_HEALTH.get(health, health)}")
        if level <= 10 and status == "3":
            warn(f"Низкий заряд батареи: {level} %")
    else:
        row("Данных о заряде нет (нет батареи/датчика)")

    # ---------------- хранилище
    head("ХРАНИЛИЩЕ")
    free, tot = num(kv.get("freemb"), -1), num(kv.get("totmb"), -1)
    if free >= 0 and tot > 0:
        row(f"/data: свободно {free} МБ из {tot} МБ ({free * 100 // tot} %)")
        if free < 500:
            warn(f"Мало места на /data: {free} МБ")
        elif free * 100 // tot < 10:
            warn(f"Меньше 10 % свободного места на /data ({free} МБ)")
    else:
        row("/data: н/д")
    cache = num(kv.get("cachefree"), -1)
    if cache >= 0:
        row(f"/cache: свободно {cache} МБ")

    userpkgs = num(kv.get("userpkgs"), -1)
    allpkgs = num(kv.get("pkgs"), -1)
    if allpkgs >= 0:
        row(f"Приложений: {allpkgs} всего, {max(userpkgs, 0)} пользовательских")
    if num(kv.get("gms")) == 0:
        row("Google Services: не найдены")

    # ---------------- сеть
    head("СЕТЬ")
    iface = (kv.get("iface") or "").strip()
    row(f"Активный интерфейс: {iface or 'нет маршрута'}")
    row(f"IP-адрес: {or_na(kv.get('ipaddr'))} | Шлюз: {or_na(kv.get('gateway'))}")
    row(f"DNS: {or_na(kv.get('dns1'))} {kv.get('dns2') or ''}".rstrip())

    rssi_text = (kv.get("rssi") or "").strip()
    ssid = (kv.get("ssid") or "").strip()
    # Android отдаёт RSSI -127, когда Wi-Fi не подключён — это не «слабый сигнал».
    rssi = num(rssi_text.replace("RSSI:", "").strip(), 0)
    wifi_known = -126 <= rssi < 0

    if iface == "wlan0" or wifi_known:
        row(f"Wi-Fi: {ssid or 'н/д'} | {rssi_text or 'RSSI: н/д'}")
        if rssi < -70:
            warn(f"Слабый сигнал Wi-Fi: {rssi} dBm")
    elif rssi:
        row("Wi-Fi: не подключён")

    # Статистика интерфейсов: у телефонов это обычно wlan0/rmnet, у приставок eth0.
    for nic in nics:
        if len(nic) < 7:
            continue
        name, state, speed, rx, tx, drop, chg = (nic + [""] * 7)[:7]
        if name == iface:
            # operstate/carrier у вендорских ядер часто пусты: показываем только известное.
            bits = [f"Интерфейс {name}"]
            if state:
                bits.append(state)
            if num(speed) > 0:
                bits.append(f"{speed} Мбит/с")
            row(" | ".join(bits))
            rx_n, tx_n, drop_n = num(rx), num(tx), num(drop)
            if rx_n or tx_n or drop_n:
                row(f"Ошибки rx/tx: {rx_n}/{tx_n} | Отброшено: {drop_n}")
                if rx_n or tx_n:
                    warn(f"Ошибки на {name}: rx {rx_n}, tx {tx_n}")
            drops = num(chg) // 2
            if drops > 3:
                warn(f"Частые переподключения сети ({drops})")

    bt = (kv.get("bt") or "").strip()
    if bt in ("0", "1"):
        row(f"Bluetooth: {'включён' if bt == '1' else 'выключен'}")

    # ---------------- доступность
    head("ДОСТУПНОСТЬ СЕТИ")
    for name, title in (("dns", "1.1.1.1 (DNS)"), ("gstatic", "connectivitycheck.gstatic.com"),
                        ("google", "google.com")):
        ip, ms = pings.get(name, ("?", ""))
        if ms:
            row(f"{title:<32} OK   {ms} мс")
        else:
            row(f"{title:<32} НЕТ ОТВЕТА")
            warn(f"Нет связи: {title}")

    unresolved = [h for h in dns if not dns[h]]
    if unresolved:
        warn("DNS не разрешает имена")

    # ---------------- ядро
    head("ЯДРО / ДРАЙВЕРЫ")
    vdec = num(kv.get("vdec"))
    fserr = num(kv.get("fserr"))
    unclean = num(kv.get("unclean"))
    mmccrc = num(kv.get("mmccrc"))
    row(f"Сбои декодера видео: {vdec}")
    row(f"Ошибки файловой системы: {fserr}")
    row(f"CRC eMMC/MMC: {mmccrc}")
    if unclean > 0:
        row("Предыдущее выключение не штатное (ФС восстанавливалась)")
        warn("Предыдущее выключение не штатное: файловая система восстанавливалась")
    if vdec > 5:
        warn(f"Сбои декодера видео: {vdec}")
    if fserr > 0:
        warn(f"Ошибки файловой системы: {fserr}")
    if mmccrc > 0:
        warn(f"Ошибки CRC eMMC: {mmccrc}")
    if num(kv.get("therm")) > 0:
        warn(f"Термические события в ядре: {kv.get('therm')}")

    # ---------------- логи
    head("ЛОГИ")
    dmesg_first = kv.get("dmesgfirst", "")
    import re
    m = re.search(r"\[\s*([\d.]+)\]", dmesg_first)
    row(f"dmesg покрывает с {m.group(1) if m else '?'} с | logcat: с {kv.get('logfirst') or '?'}")
    anr, abort, under = num(kv.get("anr")), num(kv.get("abort")), num(kv.get("underrun"))
    row(f"Сбои приложений (ANR/FATAL): {anr}")
    row(f"Native abort: {abort}")
    row(f"Аудио underrun: {under}")
    if anr > 5:
        warn(f"Много ANR / FATAL EXCEPTION: {anr}")
    if abort > 0:
        warn(f"Падения приложений native abort: {abort}")
    if under > 5:
        warn(f"Аудио underrun: {under}")

    # ---------------- предыдущие выключения
    head("ПРЕДЫДУЩИЕ ВЫКЛЮЧЕНИЯ")
    row(f"Старт текущей сессии: {fmt_ts(num(kv.get('btime'), 0))}")
    cur = kv.get("reason", "")
    last = kv.get("reasonlast", "")
    row(f"Причина текущего включения: {reason_word(cur)}  [{cur or 'нет'}]")
    row(f"Причина предыдущего выключения: {reason_word(last)}  [{last or 'нет'}]")
    if "thermal" in last:
        warn("Предыдущее выключение: перегрев")
    history = kv.get("history", "")
    if history:
        row("История перезагрузок (время, причина):")
        for reason, ts in parse_history(history):
            row(f"  {fmt_ts(ts) if ts else '?'}  {reason}")
        row("(время верно только при включённом автовремени)")
        if "kernel_panic" in history:
            warn("В истории перезагрузок есть паника ядра")
        if "ext4" in history or "f2fs" in history:
            warn("В истории перезагрузок есть ошибка файловой системы")
    else:
        row("  история недоступна")
    pstore = num(kv.get("pstore"), 0)
    if pstore == 0:
        row("pstore: записей паники нет")
    else:
        row(f"pstore: записей {pstore}")
        if kv.get("pstorepanic"):
            row("  " + kv["pstorepanic"])
            warn("В pstore есть запись паники ядра")

    # ---------------- безопасность
    head("БЕЗОПАСНОСТЬ")
    row(f"SELinux: {or_na(kv.get('selinux'))}")
    if (kv.get("selinux") or "").strip().lower() == "permissive":
        warn("SELinux в режиме permissive")
    row(f"Тип сборки: {or_na(kv.get('buildtype'))} | debuggable: {or_na(kv.get('debuggable'))}")
    if (kv.get("debuggable") or "").strip() == "1":
        warn("Прошивка debuggable — снижена защита")
    su = (kv.get("su") or "").strip()
    uid = num(kv.get("rooted"), -1)
    if su == "yes" or uid == 0:
        row("Root: доступен (adb работает от root)")
        warn("На устройстве есть root-доступ")
    else:
        row("Root: не обнаружен")

    # ---------------- время
    head("ВРЕМЯ")
    row(f"На устройстве: {or_na(kv.get('date'))} | Автовремя: {or_na(kv.get('autotime'))} | "
        f"Часовой пояс: {or_na(kv.get('tz'))}")
    year = num((kv.get("date") or "")[-4:], 0)
    if year and year < 2025:
        warn(f"Неверные часы устройства ({year} год)")

    # ---------------- итог
    head("ПРЕДУПРЕЖДЕНИЯ")
    if W:
        for text in W:
            row("! " + text)
    else:
        row("нет")
    return R, W


def main():
    print("Диагностика устройства: запрашиваю показания...")
    raw = adb.shell(COMMANDS, timeout=180)
    report, warnings = build_report(raw)
    print("=" * 38)
    print(" Диагностика Android  " + datetime.datetime.now().strftime("%H:%M:%S") +
          f"  |  предупреждений: {len(warnings)}")
    print("=" * 38)
    print("\n".join(report).lstrip("\n"))


main()
