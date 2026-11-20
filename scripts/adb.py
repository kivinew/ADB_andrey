# -*- coding: utf-8 -*-
"""adb module for user scripts (C# Android-manager). Standalone API."""
import os
import subprocess
import time


def _adb_exe():
    here = os.path.dirname(os.path.abspath(__file__))
    local = os.path.join(os.path.dirname(here), 'tools', 'adb', 'adb.exe')
    if os.path.isfile(local):
        return local
    return 'adb'


def _serial():
    return os.environ.get('ANDROID_SERIAL') or ''


def _run(args, timeout=30):
    try:
        proc = subprocess.run([_adb_exe()] + args, capture_output=True, timeout=timeout,
                               stdin=subprocess.DEVNULL)
        return proc.returncode, proc.stdout.decode('utf-8', 'replace'), proc.stderr.decode('utf-8', 'replace')
    except Exception as exc:
        raise RuntimeError('adb failed: {}'.format(exc))


def shell(command, timeout=60):
    rc, out, err = _run(['-s', _serial(), 'shell', command], timeout=timeout)
    return ((out or '') + (err or '')).rstrip('\n')


def call(*args, timeout=120):
    rc, out, err = _run(['-s', _serial(), *args], timeout=timeout)
    return rc, out, err


def getprop(name):
    return shell('getprop {}'.format(name)).strip()


def packages(kind='all'):
    flags = {'all': [], 'user': ['-3'], 'system': ['-s'], 'disabled': ['-d']}.get(kind, [])
    rc, out, err = _run(['-s', _serial(), 'pm', 'list', 'packages', *flags], timeout=90)
    names = []
    for line in (out or '').splitlines():
        line = line.strip()
        if line.startswith('package:'):
            names.append(line.split('package:', 1)[1].strip())
    return names


def force_stop(pkg):
    return shell('am force-stop {}'.format(pkg))


def clear(pkg):
    return shell('pm clear {}'.format(pkg))


def disable(pkg):
    return shell('pm disable-user --user 0 {}'.format(pkg))


def enable(pkg):
    return shell('pm enable --user 0 {}'.format(pkg))


def uninstall(pkg):
    return shell('pm uninstall -k --user 0 {}'.format(pkg))


def launch(pkg):
    return shell('monkey -p {} -c android.intent.category.LAUNCHER 1'.format(pkg), timeout=30)


def install(apk_path):
    rc, out, err = _run(['-s', _serial(), 'install', '-r', apk_path], timeout=600)
    text = ((out or '') + (err or '')).strip()
    return 'Success' in text, text


def push(local_path, remote_path):
    rc, out, err = _run(['-s', _serial(), 'push', local_path, remote_path], timeout=600)
    if rc != 0:
        raise RuntimeError((out or '') + (err or ''))
    return (out or '').strip()


def pull(remote_path, local_path):
    rc, out, err = _run(['-s', _serial(), 'pull', remote_path, local_path], timeout=600)
    if rc != 0:
        raise RuntimeError((out or '') + (err or ''))
    return local_path


def screenshot(path):
    try:
        proc = subprocess.run([_adb_exe(), '-s', _serial(), 'exec-out', 'screencap', '-p'],
                               capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
    except Exception as exc:
        raise RuntimeError('adb failed: {}'.format(exc))
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError('screencap failed')
    with open(path, 'wb') as fh:
        fh.write(proc.stdout)
    return path


def reboot(mode=''):
    _run(['-s', _serial(), 'reboot'] + ([mode] if mode else []), timeout=15)


def sleep(seconds):
    end = time.time() + seconds
    while time.time() < end:
        time.sleep(min(0.2, max(0, end - time.time())))


def check():
    pass


stopped = False


__all__ = ['shell', 'call', 'getprop', 'packages', 'force_stop', 'clear', 'disable', 'enable', 'uninstall', 'launch', 'install', 'push', 'pull', 'screenshot', 'reboot', 'sleep', 'check']
