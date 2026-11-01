import base64, ctypes, io, subprocess, sys, time
from ctypes import wintypes
from PIL import ImageGrab, Image
exe = sys.argv[1]
p = subprocess.Popen([exe, "--new"])
u32 = ctypes.windll.user32
found = []
def cb(hwnd, lp):
    n = u32.GetWindowTextLengthW(hwnd)
    if n and u32.IsWindowVisible(hwnd):
        buf = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(hwnd, buf, n + 1)
        if "스마트PDF Editor" in buf.value:
            found.append(hwnd)
    return True
for _ in range(40):
    time.sleep(1)
    found.clear()
    u32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    if found:
        break
time.sleep(3)
print("windows:", len(found))
if found:
    r = wintypes.RECT()
    u32.GetWindowRect(found[0], ctypes.byref(r))
    title = ImageGrab.grab(bbox=(max(0, r.left), max(0, r.top), max(0, r.left) + 520, max(0, r.top) + 60))
    b = io.BytesIO(); title.save(b, "PNG"); print("IMG title.png", base64.b64encode(b.getvalue()).decode())
sw, sh = ImageGrab.grab().size
task = ImageGrab.grab(bbox=(0, sh - 60, sw, sh))
b = io.BytesIO(); task.save(b, "PNG"); print("IMG taskbar.png", base64.b64encode(b.getvalue()).decode())
p.kill()
