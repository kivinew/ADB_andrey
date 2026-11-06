# -*- coding: utf-8 -*-
"""
ДИАГНОСТИКА ТВ-ПРИСТАВКИ (замена tvdiag.sh) для Android manager.

Как добавить: вкладка «Скрипты» -> «Импорт .py» -> выбрать этот файл -> «Сохранить».
Затем нажмите кнопку «Диагностика ТВ» (название можно поменять в редакторе).
Отчёт появится в окне «Результат».

Что делает: отправляет на устройство ОДНУ пакетную команду (adb shell), получает
сырые показания, разбирает их и печатает отчёт с предупреждениями.
На устройстве ничего не меняет и ничего не записывает.
"""

import datetime
import adb  # noqa: F401  -- предоставляется Android-manager при автономном запуске; локальная обёртка adb.py имитирует тот же интерфейс

# Команды, которые выполняются на устройстве. Каждая строка печатает "@@ключ=значение".
# Строки объединяются через "; " и уходят одним вызовом adb shell.
COMMANDS = r'''
echo "@@model=$(getprop ro.product.model)"
echo "@@devname=$(getprop ro.product.device)"
echo "@@odm=$(getprop ro.product.odm.model)"
echo "@@board=$(getprop ro.hardware)"
echo "@@soc=$(getprop ro.board.platform)"
echo "@@build=$(getprop ro.build.display.id)"
echo "@@tags=$(getprop ro.build.tags)"
echo "@@serial=$(getprop ro.serialno)"
echo "@@android=$(getprop ro.build.version.release)"
echo "@@sdk=$(getprop ro.build.version.sdk)"
echo "@@patch=$(getprop ro.build.version.security_patch)"
echo "@@date=$(date "+%d.%m.%Y %H:%M:%S")"
echo "@@uptime=$(cut -d " " -f1 /proc/uptime)"
echo "@@btime=$(awk "/^btime/{print \$2}" /proc/stat)"
echo "@@memtotal=$(awk "/^MemTotal/{print \$2}" /proc/meminfo)"
echo "@@memavail=$(awk "/^MemAvailable/{print \$2}" /proc/meminfo)"
echo "@@cpupart=$(awk -F": *" "/^CPU part/{print \$2; exit}" /proc/cpuinfo)"
echo "@@cpuimpl=$(awk -F": *" "/^CPU implementer/{print \$2; exit}" /proc/cpuinfo)"
echo "@@cpucount=$(grep -c "^processor" /proc/cpuinfo)"
echo "@@online=$(cat /sys/devices/system/cpu/online 2>/dev/null)"
echo "@@cur0=$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq 2>/dev/null)"
echo "@@min0=$(cat /sys/devices/system/cpu/cpufreq/policy0/cpuinfo_min_freq 2>/dev/null)"
echo "@@max0=$(cat /sys/devices/system/cpu/cpufreq/policy0/cpuinfo_max_freq 2>/dev/null)"
echo "@@gov0=$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor 2>/dev/null)"
echo "@@steps0=$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_available_frequencies 2>/dev/null)"
echo "@@affected0=$(cat /sys/devices/system/cpu/cpufreq/policy0/affected_cpus 2>/dev/null)"
echo "@@load=$(cat /proc/loadavg)"
for z in /sys/class/thermal/thermal_zone*; do echo "@@tz $(cat $z/type 2>/dev/null) $(cat $z/temp 2>/dev/null)"; done
echo "@@gpuinfo=$(head -1 /sys/class/misc/mali0/device/gpuinfo 2>/dev/null)"
echo "@@gpucur=$(head -1 /sys/class/mpgpu/cur_freq 2>/dev/null)"
echo "@@gpuutil=$(head -1 /sys/class/mpgpu/utilization 2>/dev/null)"
echo "@@gpuerr=$(head -1 /sys/class/mpgpu/gpu_err 2>/dev/null)"
echo "@@gpumem=$(awk "/^mali0/{print \$NF; exit}" /sys/devices/platform/fe400000.bifrost/gpu_memory 2>/dev/null)"
echo "@@gles=$(dumpsys SurfaceFlinger 2>/dev/null | grep -m1 "GLES:" | cut -c1-100)"
echo "@@hpd=$(cat /sys/class/amhdmitx/amhdmitx0/hpd_state 2>/dev/null)"
echo "@@vmode=$(cat /sys/class/amhdmitx/amhdmitx0/valid_mode 2>/dev/null)"
echo "@@mode=$(cat /sys/class/display/mode 2>/dev/null)"
echo "@@natdisp=$(grep "\*" /sys/class/amhdmitx/amhdmitx0/disp_cap 2>/dev/null | tr -d "*\r ")"
echo "@@pa=$(cat /sys/class/cec/physical_addr 2>/dev/null)"
echo "@@edid=$(cat /sys/class/amhdmitx/amhdmitx0/rawedid 2>/dev/null | tr -d " \n\r")"
echo "@@cec=$(settings get global hdmi_control_enabled 2>/dev/null)"
echo "@@autotime=$(settings get global auto_time 2>/dev/null)"
echo "@@vdec=$(dmesg 2>/dev/null | grep -c -E "wait resource timeout|decoder timeout|frame number gap error")"
echo "@@fserr=$(dmesg 2>/dev/null | grep -c -E "EXT4-fs error|Remounting filesystem read-only|EXT4-fs.*I/O error")"
echo "@@unclean=$(dmesg 2>/dev/null | grep -c -E "not cleanly shutdown|orphan inodes deleted")"
echo "@@therm=$(dmesg 2>/dev/null | grep -c -i -E "thermal.*trip|over.temp")"
echo "@@mmccrc=$(dmesg 2>/dev/null | grep -c "meson-gx-mmc.*CRC")"
echo "@@dmesgfirst=$(dmesg 2>/dev/null | head -1 | cut -c1-20)"
echo "@@logfirst=$(logcat -d 2>/dev/null | head -1 | cut -c1-18)"
echo "@@anr=$(logcat -d -t 500 "*:E" 2>/dev/null | grep -c -E "ANR in|FATAL EXCEPTION|died")"
echo "@@abort=$(logcat -d -t 500 "*:E" 2>/dev/null | grep -c -E "Fatal signal 6|SIGABRT|assertion .* failed")"
echo "@@underrun=$(logcat -d -t 500 2>/dev/null | grep -c underrun)"
echo "@@cecfail=$(logcat -d -t 300 2>/dev/null | grep -c "Failed to send")"
echo "@@reason=$(getprop sys.boot.reason)"
echo "@@reasonlast=$(getprop sys.boot.reason.last)"
echo "@@history=$(getprop persist.sys.boot.reason.history)"
echo "@@pstore=$(ls /sys/fs/pstore 2>/dev/null | grep -c .)"
echo "@@pstorepanic=$(grep -h -i -E "Kernel panic|Unable to handle" /sys/fs/pstore/* 2>/dev/null | head -1 | cut -c1-110)"
echo "@@freemb=$(df -k /data 2>/dev/null | awk "NR==2{print int(\$4/1024)}")"
echo "@@totmb=$(df -k /data 2>/dev/null | awk "NR==2{print int(\$2/1024)}")"
echo "@@netif=$(ip route get 8.8.8.8 2>/dev/null | awk "{for(i=1;i<=NF;i++) if(\$i==\"dev\"){print \$(i+1); exit}}")"
echo "@@ethspd=$(cat /sys/class/net/eth0/speed 2>/dev/null)"
echo "@@ethdup=$(cat /sys/class/net/eth0/duplex 2>/dev/null)"
echo "@@ethrx=$(cat /sys/class/net/eth0/statistics/rx_errors 2>/dev/null)"
echo "@@ethtx=$(cat /sys/class/net/eth0/statistics/tx_errors 2>/dev/null)"
echo "@@ethdrop=$(cat /sys/class/net/eth0/statistics/rx_dropped 2>/dev/null)"
echo "@@ethchg=$(cat /sys/class/net/eth0/carrier_changes 2>/dev/null)"
echo "@@ethcar=$(cat /sys/class/net/eth0/carrier 2>/dev/null)"
echo "@@rssi=$(dumpsys wifi 2>/dev/null | grep -m1 "mWifiInfo" | grep -o "RSSI: -*[0-9]*" | head -1)"
echo "@@dns1=$(getprop net.dns1)"
echo "@@dns2=$(getprop net.dns2)"
for t in market:93.95.159.33 api:185.30.15.53 epg:93.95.152.11 cache1:93.95.158.1 cache2:93.95.158.2 acs:93.95.159.36; do echo "@@ping ${t%%:*} ${t#*:} $(ping -c 1 -W 1 ${t#*:} 2>/dev/null | grep -o "time=[0-9.]*" | cut -d= -f2)"; done
for h in android-market.eltex.local api-stb.example.com eltex.local iptv.example.com iptv-cache01.example.com iptv-cache02.example.com acs.example.com; do echo "@@dns $h $(ping -c 1 -W 2 $h 2>/dev/null | head -1)"; done
ps -A -o NAME,RSS 2>/dev/null | awk "NR>1 && \$2+0>0" | sort -k2 -nr | head -6 | awk "{print \"@@top \" \$1 \" \" \$2}"
'''

CPU_PARTS = {
    "0xd01": "Cortex-A32", "0xd03": "Cortex-A53", "0xd04": "Cortex-A35", "0xd05": "Cortex-A55",
    "0xd07": "Cortex-A57", "0xd08": "Cortex-A72", "0xd09": "Cortex-A73", "0xd0a": "Cortex-A75",
    "0xd0b": "Cortex-A76", "0xd0d": "Cortex-A77", "0xd41": "Cortex-A78",
}

EXPECTED_DNS = {
    "android-market.eltex.local": "93.95.159.33", "api-stb.example.com": "185.30.15.53",
    "eltex.local": "93.95.152.11", "iptv.example.com": "93.95.152.11",
    "iptv-cache01.example.com": "93.95.158.1", "iptv-cache02.example.com": "93.95.158.2",
    "acs.example.com": "93.95.159.36",
}

REASON_WORDS = [
    ("thermal", "перегрев"), ("watchdog", "зависание"), ("wdog", "зависание"),
    ("panic", "паника ядра"), ("kernel", "паника ядра"), ("power", "проблема с питанием"),
    ("battery", "проблема с питанием"), ("ota", "после обновления"), ("update", "после обновления"),
    ("reboot", "обычная перезагрузка"), ("shutdown", "обычная перезагрузка"),
]


def reason_word(code):
    if not code:
        return "неизвестно"
    for key, word in REASON_WORDS:
        if key in code:
            return word
    return "другое"


def parse_output(raw):
    kv, tops, pings, dns, tzs = {}, [], {}, {}, []
    for line in raw.splitlines():
        if not line.startswith("@@"):
            continue
        body = line[2:]
        parts = body.split(" ")
        if body.startswith("top "):
            if len(parts) >= 3:
                tops.append((parts[1], parts[2]))
        elif body.startswith("ping "):
            name = parts[1]
            ip = parts[2] if len(parts) > 2 else ""
            ms = parts[3] if len(parts) > 3 else ""
            pings[name] = (ip, ms)
        elif body.startswith("dns "):
            host = parts[1]
            dns[host] = body
        elif body.startswith("tz "):
            if len(parts) >= 3:
                tzs.append((parts[1], parts[2]))
        else:
            key, _, value = body.partition("=")
            kv[key] = value
    return kv, tops, pings, dns, tzs


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
    """Частота в Гц/кГц/МГц -> МГц (как в tvdiag)."""
    v = num(raw, -1)
    if v < 0:
        return None
    if v >= 1000000:
        return v // 1000000
    if v >= 1000:
        return v // 1000
    return v


def edid_model(hexs):
    i = hexs.find("000000fc00")
    if i < 0:
        return ""
    body = hexs[i + 10:i + 10 + 26]
    out = []
    for j in range(0, len(body) - 1, 2):
        b = int(body[j:j + 2], 16)
        if b in (0x0A, 0x00):
            break
        if b == 0x20 and not out:
            continue
        out.append(chr(b))
    return "".join(out).rstrip()


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


def build_report(raw):
    kv, tops, pings, dns, tzs = parse_output(raw)
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
    row(f"Модель: {kv.get('model') or 'н/д'} | Устройство: {kv.get('devname') or 'н/д'}")
    row(f"Плата: {kv.get('board') or 'н/д'} | SoC: {kv.get('soc') or 'н/д'} | ODM: {kv.get('odm') or 'н/д'}")
    row(f"Серийный номер: {kv.get('serial') or 'н/д'}")
    row(f"Android {kv.get('android') or '?'} (SDK {kv.get('sdk') or '?'}) | Патч безопасности: {kv.get('patch') or 'н/д'}")
    row(f"Сборка: {kv.get('build') or 'н/д'}")
    if "test-keys" in kv.get("tags", ""):
        row("test-keys: неофициальная прошивка")

    # ---------------- аптайм
    head("АПТАЙМ")
    up = num(kv.get("uptime"), 0)
    row(f"{up // 86400} д {up % 86400 // 3600} ч {up % 3600 // 60} мин | Старт: {fmt_ts(num(kv.get('btime'), 0))}")

    # ---------------- память
    head("ПАМЯТЬ")
    total = num(kv.get("memtotal")) // 1024
    avail = num(kv.get("memavail")) // 1024
    row(f"Всего: {total} МБ | Занято: {total - avail} МБ | Доступно: {avail} МБ")
    if tops:
        row("Больше всего памяти (МБ):")
        for name, kb in tops:
            row(f"  {name[:40]}: {num(kb) // 1024}")
    if total and avail < 300:
        warn("Мало оперативной памяти: доступно меньше 300 МБ")

    # ---------------- процессор
    head("ПРОЦЕССОР")
    part = kv.get("cpupart", "").strip()
    impl = kv.get("cpuimpl", "").strip()
    row(f"Модель: {CPU_PARTS.get(part, 'неизвестно')} ({impl or '?'} / {part or '?'})")
    row(f"SoC: {kv.get('soc') or 'н/д'}")
    cores = num(kv.get("cpucount"), 0)
    row(f"Ядер: {cores} | Онлайн CPU: {kv.get('online') or 'н/д'}")
    cur0 = mhz_from(kv.get("cur0"))
    row(f"Текущая частота (cpu0): {cur0 if cur0 is not None else 'н/д'} МГц")
    mn, mx = mhz_from(kv.get("min0")), mhz_from(kv.get("max0"))
    row(f"Кластер CPU {kv.get('affected0') or '?'}: текущая {cur0 or '?'} МГц | "
        f"диапазон {mn or '?'}..{mx or '?'} МГц | режим: {kv.get('gov0') or 'н/д'}")
    steps = [str(mhz_from(s)) for s in kv.get("steps0", "").split() if mhz_from(s) is not None]
    if steps:
        row("Ступени частот, МГц: " + " ".join(steps))
    load = kv.get("load", "").split()
    if len(load) >= 3:
        row(f"Нагрузка 1/5/15 мин: {load[0]} / {load[1]} / {load[2]}")
        if cores and float(load[0]) > cores:
            warn(f"Нагрузка CPU выше числа ядер ({load[0]} при {cores} ядрах)")

    # ---------------- температура
    head("ТЕМПЕРАТУРА")
    soc_t, gpu_t = None, None
    for ztype, zraw in tzs:
        t = temp_c(zraw)
        if t is None:
            continue
        low = ztype.lower()
        if soc_t is None and any(k in low for k in ("cpu", "soc", "tsens", "aoss")):
            soc_t = t
        if gpu_t is None and any(k in low for k in ("gpu", "mali")):
            gpu_t = t
    row(f"SoC: {soc_t:.1f} C" if soc_t is not None else "SoC: н/д")
    if soc_t is not None:
        if soc_t > 85:
            warn(f"Перегрев SoC: {soc_t:.1f} C, проверьте вентиляцию")
        elif soc_t > 75:
            warn(f"SoC горячий: {soc_t:.1f} C")

    # ---------------- GPU
    head("ГРАФИЧЕСКИЙ ПРОЦЕССОР (GPU)")
    row(f"GPU: {kv.get('gpuinfo') or 'н/д'}")
    gcur = mhz_from(kv.get("gpucur"))
    row(f"Частота: {gcur if gcur is not None else 'н/д'} МГц")
    util = num(kv.get("gpuutil"), -1)
    row(f"Нагрузка GPU: {util if util >= 0 else 'н/д'} %")
    gerr = num(kv.get("gpuerr"), -1)
    row(f"Ошибки GPU (gpu_err): {gerr if gerr >= 0 else 'н/д'}")
    pages = num(kv.get("gpumem"), -1)
    if pages >= 0:
        row(f"Память GPU: {pages * 4 // 1024} МБ")
    if kv.get("gles"):
        row(f"OpenGL ES: {kv['gles']}")
    if util > 80:
        warn(f"Нагрузка GPU {util} %")
    if gerr > 0:
        warn(f"Ошибки GPU: {gerr}")
    if gpu_t is not None and gpu_t > 75:
        warn(f"GPU горячий: {gpu_t:.1f} C")

    # ---------------- HDMI / CEC
    head("HDMI / CEC")
    cec = kv.get("cec", "").strip()
    row(f"Состояние CEC: {'включён' if cec == '1' else 'выключен'}")
    if kv.get("hpd", "").strip() == "1":
        row("ТВ подключён: да")
        model = edid_model(kv.get("edid", "").replace(" ", ""))
        row(f"Модель ТВ: {model or 'н/д'}")
        if model[:3] in ("AAA", "XXX") or model.startswith("Digital"):
            warn("Модель ТВ не определена (заглушка EDID): переподключите ТВ по HDMI")
        row(f"Родной режим: {kv.get('natdisp') or 'н/д'} | Режим вывода: {kv.get('mode') or 'н/д'}")
        edid = kv.get("edid", "").strip().lower()
        if edid and not edid.startswith("00ffffffffffff00"):
            warn("EDID повреждён: проверьте кабель HDMI и DDC")
        elif kv.get("vmode", "").strip() == "1":
            row("HDMI работает")
        if "cvbs" in kv.get("mode", ""):
            warn("Вывод идёт по CVBS, а не по HDMI")
        pa = kv.get("pa", "").strip()
        if pa and pa[0] != "f":
            row(f"Порт HDMI на ТВ: HDMI {pa[0]}")
        else:
            row("Порт HDMI на ТВ: не определён")
        if num(kv.get("cecfail"), 0) > 3:
            warn(f"ТВ не отвечает по CEC ({kv.get('cecfail')} ошибок)")
    else:
        row("ТВ не подключён или выключен")
        row(f"Режим вывода: {kv.get('mode') or 'н/д'}")

    # ---------------- ядро
    head("ЯДРО / ДРАЙВЕРЫ")
    vdec = num(kv.get("vdec"))
    fserr = num(kv.get("fserr"))
    unclean = num(kv.get("unclean"))
    mmccrc = num(kv.get("mmccrc"))
    row(f"Декодер видео: сбои: {vdec}")
    row(f"Ошибки файловой системы (ext4): {fserr}")
    if unclean > 0:
        row("Предыдущее выключение не штатное (файловая система восстанавливалась)")
        warn("Предыдущее выключение не штатное: файловая система восстанавливалась")
    row(f"eMMC CRC: {mmccrc}")
    if vdec > 5:
        warn(f"Сбои декодера видео: {vdec}")
    if fserr > 0:
        warn(f"Ошибки файловой системы ext4: {fserr}")
    if mmccrc > 0:
        warn(f"Ошибки CRC eMMC: {mmccrc}")
    if num(kv.get("therm")) > 0:
        warn(f"Термические события в ядре: {kv.get('therm')}")

    # ---------------- хранилище
    head("ХРАНИЛИЩЕ (/data)")
    free, tot = num(kv.get("freemb"), -1), num(kv.get("totmb"), -1)
    if free >= 0 and tot > 0:
        row(f"Свободно: {free} МБ из {tot} МБ")
        if free < 500:
            warn(f"Мало места на /data: {free} МБ")
    else:
        row("Свободно: н/д")

    # ---------------- сеть
    head("СЕТЬ")
    iface = kv.get("netif", "").strip()
    row(f"Интерфейс: {iface or 'нет маршрута'}")
    if iface == "eth0":
        spd = kv.get("ethspd", "?") or "?"
        dup = kv.get("ethdup", "?") or "?"
        rx, tx = num(kv.get("ethrx")), num(kv.get("ethtx"))
        drop = num(kv.get("ethdrop"))
        chg = num(kv.get("ethchg"))
        carrier = kv.get("ethcar", "").strip()
        drops = (chg + 1) // 2 if carrier == "0" else chg // 2
        row(f"Тип: Ethernet | Скорость: {spd} Мбит/с | Дуплекс: {dup}")
        row(f"Ошибки rx/tx: {rx}/{tx} | Отброшено пакетов (rx): {drop}")
        row(f"Падения линка (с загрузки): {drops} | Линк сейчас: {'есть' if carrier == '1' else 'НЕТ'}")
        if dup == "half":
            warn("Ethernet работает в полудуплексе: проверьте кабель и порт")
        if rx or tx:
            warn(f"Ошибки Ethernet: rx {rx}, tx {tx}")
        if carrier != "1":
            warn("Нет линка Ethernet")
    elif iface == "wlan0":
        rssi_text = kv.get("rssi", "")
        row(f"Тип: Wi-Fi | {rssi_text or 'RSSI: н/д'}")
        rssi = num(rssi_text.replace("RSSI:", "").strip(), 0) if rssi_text else 0
        if rssi and rssi < -70:
            warn(f"Слабый Wi-Fi: {rssi} dBm")
    else:
        warn("Нет маршрута в сеть")

    # ---------------- серверы провайдера
    head("СЕРВЕРЫ ПРОВАЙДЕРА (ping по IP)")
    for name in ("market", "api", "epg", "cache1", "cache2", "acs"):
        ip, ms = pings.get(name, ("?", ""))
        if ms:
            row(f"{name:<8} {ip:<15} OK   {ms} мс")
        else:
            row(f"{name:<8} {ip:<15} НЕТ ОТВЕТА")
            warn(f"Нет связи с сервером {name} ({ip})")

    # ---------------- DNS
    head("DNS")
    row(f"DNS-серверы: {kv.get('dns1') or 'н/д'} {kv.get('dns2') or ''}".rstrip())
    import re
    for host, expected in EXPECTED_DNS.items():
        line = dns.get(host, "")
        m = re.search(r"\((\d+\.\d+\.\d+\.\d+)\)", line)
        if not m:
            row(f"{host:<30} -> НЕ РАЗРЕШАЕТСЯ")
            warn(f"DNS не разрешает имя: {host}")
        elif m.group(1) == expected:
            row(f"{host:<30} -> {m.group(1)}  OK")
        else:
            row(f"{host:<30} -> {m.group(1)}  (ожидался {expected})")
            warn(f"DNS вернул неверный IP для {host}")

    # ---------------- время
    head("ВРЕМЯ")
    row(f"Время на устройстве: {kv.get('date') or 'н/д'} | Автовремя: {kv.get('autotime') or 'н/д'}")
    year = num((kv.get("date") or "")[-4:], 0)
    if year and year < 2025:
        warn(f"Неверные часы устройства ({year} год)")

    # ---------------- логи
    head("ПОКРЫТИЕ ЛОГОВ")
    dmesg_first = kv.get("dmesgfirst", "")
    m = re.search(r"\[\s*([\d.]+)\]", dmesg_first)
    row(f"dmesg покрывает с {m.group(1) if m else '?'} с")
    row(f"logcat покрывает с {kv.get('logfirst') or '?'}")

    head("ОШИБКИ В ЖУРНАЛЕ (последние записи)")
    anr, abort, under = num(kv.get("anr")), num(kv.get("abort")), num(kv.get("underrun"))
    row(f"Записей о сбоях (ANR / FATAL): {anr}")
    row(f"Падения приложений (native abort): {abort}")
    row(f"Аудио underrun: {under}")
    if anr > 5:
        warn(f"Много ANR / FATAL EXCEPTION: {anr}")
    if abort > 0:
        warn(f"Падения приложений native abort: {abort}")
    if under > 5:
        warn(f"Аудио underrun: {under}")

    # ---------------- предыдущие выключения
    head("ПРЕДЫДУЩИЕ ВЫКЛЮЧЕНИЯ")
    row(f"Включение (старт текущей сессии): {fmt_ts(num(kv.get('btime'), 0))}")
    cur = kv.get("reason", "")
    last = kv.get("reasonlast", "")
    row(f"Причина текущего включения: {reason_word(cur)}  [{cur or 'нет'}]")
    row(f"Причина предыдущего выключения: {reason_word(last)}  [{last or 'нет'}]")
    if "thermal" in last:
        warn("Предыдущее выключение: перегрев")
    history = kv.get("history", "")
    row("История перезагрузок (время, причина):")
    if history:
        for reason, ts in parse_history(history):
            when = fmt_ts(ts) if ts else "?"
            row(f"  {when}  {reason}")
        row("(время записи верно только при включённом автовремени)")
        if "kernel_panic" in history:
            warn("В истории перезагрузок есть паника ядра")
        if "ext4" in history:
            warn("В истории перезагрузок есть ошибка файловой системы ext4")
    else:
        row("  нет")
    pstore = num(kv.get("pstore"), 0)
    if pstore == 0:
        row("Записи паники ядра (pstore): записей нет")
    else:
        row(f"Записи паники ядра (pstore): есть ({pstore})")
        if kv.get("pstorepanic"):
            row("  " + kv["pstorepanic"])
            warn("В pstore есть запись паники ядра")

    # ---------------- итог
    head("ПРЕДУПРЕЖДЕНИЯ")
    if W:
        for text in W:
            row("! " + text)
    else:
        row("нет")
    return R, W


def main():
    print("Диагностика ТВ: запрашиваю показания у устройства...")
    raw = adb.shell(COMMANDS, timeout=180)
    report, warnings = build_report(raw)
    print("=" * 38)
    print(" Диагностика ТВ  " + datetime.datetime.now().strftime("%H:%M:%S") +
          f"  |  предупреждений: {len(warnings)}")
    print("=" * 38)
    print("\n".join(report).lstrip("\n"))


main()
