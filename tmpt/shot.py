import os, sys, time, base64, io
sys.path.insert(0, ".")
import smartpdfeditor as S, tkinter as tk
from PIL import ImageGrab
root = tk.Tk()
app = S.App(root, [], listen=False)
def grab(win, tag):
    win.update(); time.sleep(0.5); win.update()
    x, y, w, h = win.winfo_rootx(), win.winfo_rooty(), win.winfo_width(), win.winfo_height()
    im = ImageGrab.grab((x, y, x + w, y + h)).convert("RGB"); im.thumbnail((1000, 1000))
    b = io.BytesIO(); im.save(b, "JPEG", quality=75)
    enc = base64.b64encode(b.getvalue()).decode()
    for i in range(0, len(enc), 4000):
        print(tag + ":" + enc[i:i + 4000], flush=True)
def go():
    app.settings_dialog()
    dlg = app._settings_dlg[0]
    nb = [w for w in dlg.winfo_children() if w.winfo_class() == "TNotebook"][0]
    nb.select(1)
    grab(dlg, "IMG1")
    app._settings_dlg[2].set(S.THEMES["sky"]["name"])
    app._settings_dlg[1]["wall"].set(S.photo_wall_path("호수"))
    app._settings_dlg[3]()
    root.update(); time.sleep(0.5)
    grab(root, "IMG2")
    os._exit(0)
root.after(2500, go)
root.after(60000, lambda: os._exit(1))
root.mainloop()
