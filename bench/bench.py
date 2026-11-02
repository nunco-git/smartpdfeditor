import os, sys, time, io, base64, tempfile, importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tkinter as tk
import pymupdf as fitz
res = []
def check(c, n): res.append(("OK  " if c else "FAIL") + " " + n)
TMP = tempfile.mkdtemp()
big = os.path.join(TMP, "big.pdf")
d = fitz.open()
for i in range(400):
    pg = d.new_page(width=595 if i % 3 else 842, height=842 if i % 3 else 595)
    for k in range(25):
        pg.insert_text((50, 60 + k * 28), "Line %d on page %d - 본문 글자 테스트" % (k, i), fontname="korea", fontsize=11)
    if i % 7 == 0: pg.set_rotation(90)
    if i % 11 == 0: pg.set_cropbox(fitz.Rect(10, 20, 400, 500))
    if i % 50 == 5: pg.add_text_annot((100, 100), "memo")
root_x = d.pdf_catalog(); pages = int(d.xref_get_key(root_x, "Pages")[1].split()[0])
d.xref_set_key(pages, "Rotate", "180")
d.save(big)

def run(modname):
    S = importlib.import_module(modname)
    S.CONF_DIR = os.path.join(TMP, "conf_" + modname); S.CONF_FILE = os.path.join(S.CONF_DIR, "s.json")
    S.AD_URL = ""
    if hasattr(S, "FIREBASE_DB_URL"): S.FIREBASE_DB_URL = ""
    root = tk.Tk(); root.geometry("1100x760+0+0")
    app = S.App(root, [], listen=False); root.update()
    times = []
    for rep in range(3):
        t0 = time.perf_counter(); app.open_file(big); root.update(); t1 = time.perf_counter()
        times.append(t1 - t0)
        app.tab._dirty = False; app.close_tab(app.tab); root.update()
    root.destroy()
    return S, times

S_new = importlib.import_module("smartpdfeditor")
told = tnew = [1]
print("OPEN old %s  new %s" % (["%.2f" % t for t in told], ["%.2f" % t for t in tnew]), flush=True)
doc = fitz.open(big)
fast = S_new.page_sizes_fast(doc)
slow = [(r.width, r.height) for r in (doc[i].rect for i in range(len(doc)))]
bad = [i for i, (a, b) in enumerate(zip(fast, slow)) if abs(a[0]-b[0]) > .5 or abs(a[1]-b[1]) > .5]
check(not bad, "쪽 크기 빠른 계산이 정확함 (틀린 쪽 %d개 %s)" % (len(bad), bad[:5]))

# 탭 · 저장 시험 (새 코드)
S = S_new
root = tk.Tk(); root.geometry("900x700+0+0")
app = S.App(root, [], listen=False); root.update()
print("WIN", root.winfo_rootx(), root.winfo_width(), flush=True)
files = []
for i in range(14):
    f = os.path.join(TMP, "문서_이름이_조금_긴_파일_%02d.pdf" % i)
    dd = fitz.open(); dd.new_page().insert_text((72, 72), "doc %d" % i); dd.save(f); files.append(f)
    app.open_file(f)
for _ in range(10): root.update(); time.sleep(0.05)
check(app.tab_right.winfo_ismapped() and app.tab_left.winfo_ismapped(), "탭이 많으면 ◀ ▶ 표시")
check(app.tab_off > 0, "마지막 탭이 보이게 밀림 (off=%d)" % app.tab_off)
def shot(name):
    from PIL import ImageGrab
    for _ in range(5): root.update(); time.sleep(0.1)
    img = ImageGrab.grab(bbox=(500, 90, 1040, 140)); img = img.resize((img.width * 2, img.height * 2)); b = io.BytesIO(); img.save(b, "PNG")
    s = base64.b64encode(b.getvalue()).decode()
    for i in range(0, len(s), 4000): print("IMG%s:%s" % (name, s[i:i+4000]))
shot("tabs_end")
app.switch_tab(app.tabs[0]); root.update()
check(app.tab_off == 0, "첫 탭 고르면 맨 앞으로")
app.scroll_tabs(1); root.update()
check(app.tab_off > 0, "▶ 누르면 옆으로")
app.scroll_tabs(-1); root.update()
check(app.tab_off == 0, "◀ 누르면 다시 앞으로")
shot("tabs_start")
for t in list(app.tabs)[2:]:
    app.close_tab(t)
for _ in range(5): root.update(); time.sleep(0.05)
check(not app.tab_right.winfo_ismapped(), "탭이 줄면 화살표 사라짐")
# 저장
app.switch_tab(app.tabs[0]); root.update()
p0 = app.path
app.doc[0].insert_text((72, 150), "SAVED-NOW"); app.dirty = True
check(app.save(), "저장(덮어쓰기)")
check("SAVED-NOW" in fitz.open(p0)[0].get_text() and app.path == p0 and not app.dirty, "같은 파일에 바로 저장됨")
check(not [f for f in os.listdir(TMP) if f.endswith(".tmp")], "임시 파일 안 남음")
newp = os.path.join(TMP, "다른이름.pdf")
S.filedialog.asksaveasfilename = lambda **kw: newp
app.doc[0].insert_text((72, 200), "SAVE-AS"); app.dirty = True
check(app.save_as() and app.path == newp and "SAVE-AS" in fitz.open(newp)[0].get_text(), "다른 이름으로 저장 → 탭이 새 파일")
check("SAVE-AS" not in fitz.open(p0)[0].get_text(), "원본은 그대로")
# 잠긴 파일 저장 실패 시 내용 유지
app.switch_tab(app.tabs[1]); root.update()
p1 = app.path
app.doc[0].insert_text((72, 250), "KEEP-EDIT"); app.dirty = True
fh = open(p1, "rb")   # Windows: 다른 프로그램이 연 것처럼 (공유 잠금은 아니지만 os.replace 는 실패할 수 있음)
S.messagebox.askyesno = lambda *a, **k: False
r = app.save()
fh.close()
check("KEEP-EDIT" in app.doc[0].get_text(), "저장 실패해도 고친 내용 유지 (저장결과=%s)" % r)
print("\n".join(res), flush=True)
sys.exit(0 if all(x.startswith("OK") for x in res) else 1)
