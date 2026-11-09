import sys, os, time, faulthandler
import tkinter

def log(s):
    with open("_tab_progress.txt", "a", encoding="utf-8") as fh:
        fh.write(str(s) + "\n"); fh.flush()

src = open("Android_manager.pyw", encoding="utf-8").read()
marker = "PROGRAM_SRC = r'''"
mstart = src.index(marker) + len(marker)
cend = src.index("'''", mstart)
code = src[mstart:cend]
g = {"__name__": "android_manager_test", "__file__": "Android_manager.pyw"}
sys.argv = ["Android_manager.pyw", "3"]
import tkinter as tk
from tkinter import ttk
orig_ai = tkinter.Misc.after_idle
count = [0]
def ai(self, func, *a):
    try:
        n = getattr(func, "__name__", str(func))
    except Exception:
        n = "?"
    if n == "relayout":
        count[0] += 1
        log("AFTER_IDLE relayout #%d" % count[0])
        if count[0] > 25:
            log("LOOP_DETECTED after_idle relayout x%d" % count[0])
    return orig_ai(self, func, *a)
tkinter.Misc.after_idle = ai
exec(compile(code, "Android_manager.pyw", "exec"), g)
App = g["App"]
app = App()
app.update()
log("TOOLS ok")
app.nb.select(3)
log("SELECTED")
t = time.time()
app.update()
log("UPDATE_DONE %.2f" % (time.time() - t))
log("DONE_OK")
app.after(1500, app.destroy)
app.mainloop()
