# -*- coding: utf-8 -*-
"""Windows에서 실제 화면(tkinter)을 띄워 주요 기능을 자동으로 점검합니다.
GitHub Actions(ci.yml)에서 실행:  python tests/smoke_test.py
"""
import os
import sys
import time
import faulthandler
faulthandler.enable()
import queue
import tempfile
import tkinter as tk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.argv = [sys.argv[0]]

try:
    import pymupdf as fitz  # noqa: E402
except ImportError:
    import fitz  # noqa: E402
import smartpdfeditor as S  # noqa: E402

TMP = tempfile.mkdtemp(prefix="spe_")
S.CONF_DIR = os.path.join(TMP, "conf")
S.CONF_FILE = os.path.join(S.CONF_DIR, "settings.json")
S.AD_CACHE = os.path.join(S.CONF_DIR, "ad_cache")
S.AD_URL = "https://127.0.0.1:9/none.json"   # 광고 서버는 점검에서 제외 (실패해도 조용히 넘어가야 함)
base_threads = 0
S.UPDATE_API = ""   # 새 버전 확인은 점검에서 실제로 하지 않음
stats_sent = []   # 사용 통계는 실제로 보내지 않고 기록만 (점검이 설치 수에 섞이지 않게)
S.stats_call = lambda url, method, body: stats_sent.append((url, method, body))

errors = []
step_name = ["시작"]


def step(name):
    step_name[0] = name
    print(f"· {name}", flush=True)


# 대화상자는 막지 않도록 자동 응답
def _fail(kind):
    return lambda *a, **k: errors.append(f"[{step_name[0]}] {kind}: {a}")


S.messagebox.showerror = _fail("showerror")
S.messagebox.showwarning = _fail("showwarning")
S.messagebox.showinfo = lambda *a, **k: print("   (info)", a[1] if len(a) > 1 else a)
S.messagebox.askyesno = lambda *a, **k: True
S.messagebox.askyesnocancel = lambda *a, **k: False
S.ask_text = lambda parent, title, prompt, initial="": initial   # 이름 입력창은 기본값 그대로


def make_pdf(path, rotate_second=True):
    d = fitz.open()
    p1 = d.new_page()
    p1.insert_text((72, 100), "Hello World", fontsize=14)
    p1.insert_text((72, 140), "Second line here", fontsize=12)
    p2 = d.new_page()
    p2.insert_text((72, 100), "Rotated page text", fontsize=14)
    if rotate_second:
        p2.set_rotation(90)
    p3 = d.new_page(width=842, height=595)
    p3.insert_text((72, 100), "Landscape page", fontsize=14)
    d.save(path)
    d.close()


def pump(sec=0.3):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.01)


SHOTS = os.path.join(ROOT, "screenshots")


def shot(name):
    """화면 모습 확인용 스크린샷 (Actions의 Artifacts에서 볼 수 있음)"""
    try:
        from PIL import ImageGrab
        pump(0.4)
        root.lift()
        x, y = root.winfo_rootx(), root.winfo_rooty()
        os.makedirs(SHOTS, exist_ok=True)
        ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height()), all_screens=True).save(
            os.path.join(SHOTS, name + ".png"))
    except Exception as ex:
        print("   (스크린샷 생략:", ex, ")")


def check(cond, msg):
    if not cond:
        errors.append(f"[{step_name[0]}] 실패: {msg}")
        print("   ✗", msg, flush=True)


pdf1 = os.path.join(TMP, "sample1.pdf")
pdf2 = os.path.join(TMP, "sample2.pdf")
make_pdf(pdf1)
make_pdf(pdf2, rotate_second=False)

root = tk.Tk()
root.report_callback_exception = lambda et, ev, tb: errors.append(
    f"[{step_name[0]}] 콜백 오류: {et.__name__}: {ev}")

step("프로그램 시작 + 파일 열기")
base_threads = S.threading.active_count()
app = S.App(root, [pdf1], listen=False)
root.geometry("1000x690+0+0")
root.deiconify()
root.lift()
pump(1.0)
check(len(app.tabs) == 1, "탭 1개")
check(app.doc is not None and len(app.doc) == 3, "3쪽 문서")
check(len(app.imgs) > 0, "화면에 쪽이 그려짐")
check(len(getattr(app, "_app_icons", [])) == 4, "프로그램 아이콘(제목줄·작업표시줄)")

step("메뉴와 도구가 한 줄 · 쪽 이동/확대는 아래 상태줄")
labels = [l_.cget("text") for l_, _ in app.menubar.items]
check(labels == ["파일", "편집", "보기", "도구", "페이지", "즐겨찾기", "설정", "도움말"], f"메뉴 {labels}")
check(app.menubar.master is app.bar, "메뉴가 도구줄과 같은 줄")
check(str(app._page_entry.winfo_toplevel()) == "." and app._page_entry.master.master is app.sbar, "쪽 번호 칸은 아래 상태줄")
check(int(app._page_entry.master.grid_info()["column"]) == 1, "상태줄 가운데부터 오른쪽")

step("보기 방식 / 맞춤")
for _, label, _ in S.VIEWS:
    app.view_var.set(label)
    app.on_view()
    pump(0.2)
    check(len(app.slots) > 0, f"{label} 배치")
for fit in ("width", "height", "custom"):
    app.fit.set(fit)
    app.on_fit()
    pump(0.2)
app.view_var.set(S.VIEW_LABEL["cont"])
app.on_view()
app.fit.set("width")
app.on_fit()
pump(0.3)

step("휠 스크롤 (마우스 위치 기준)")
class Ev:  # noqa: E302
    pass
ev = Ev()
ev.x_root = app.cv.winfo_rootx() + app.cv.winfo_width() // 2
ev.y_root = app.cv.winfo_rooty() + app.cv.winfo_height() // 2
ev.delta, ev.state = -120, 0
top0 = app.cv.yview()[0]
if root.winfo_containing(ev.x_root, ev.y_root) is not app.cv:
    print("   (이 환경은 창 위치 확인이 안 되어 휠 신호를 직접 전달)")
    for _ in range(5):
        app.on_wheel(ev)
else:
    for _ in range(5):
        app.route_wheel(ev)
pump(0.2)
check(app.cv.yview()[0] > top0, "휠로 아래로 이동")
app.wheel_page.set(True)
pg0 = app.page_no
app._wheel_t = 0
app.wheel_step(1)
pump(0.2)
check(app.page_no != pg0 or pg0 == len(app.doc) - 1, "휠 한 칸 = 한 쪽")
app.wheel_page.set(False)
app.goto(0)
pump(0.2)

shot("1_viewer_mode")
step("아래 상태줄 보기 아이콘")
check(len(app.view_icons) == 5, "보기 방식 아이콘 5개")

step("뷰어 모드 글자 선택 → 북마크 이름")
app.app_mode.set("view")
app.set_app_mode()
w = app.words_for(0)
check(len(w) > 3, "단어 목록")
app.select_text(0, fitz.Point(70, 95), fitz.Point(200, 95))
check(app.sel and app.sel["text"].startswith("Hello"), f"선택 글자: {app.sel and app.sel['text']!r}")
check(len(app.cv.find_withtag("tsel")) > 0, "선택 표시")
shot("2_text_selected")
app.copy_selection()
check(root.clipboard_get().startswith("Hello"), "Ctrl+C 복사")
_ask = S.ask_text
S.ask_text = lambda *a, **k: errors.append("선택한 글자로 북마크할 때 이름 창이 뜸") or "x"
bm = app.new_bookmark()
S.ask_text = _ask
check(bm and bm["name"].startswith("Hello") and bm["page"] == 0 and "pos" in bm, f"북마크: {bm}")
app.select_text(0, fitz.Point(70, 95), fitz.Point(200, 140))
check("\n" in app.sel["text"], "여러 줄 선택")
n_hl = len(list(app.doc[0].annots()))
app.mark_selection()
check(len(list(app.doc[0].annots())) == n_hl + 1, "선택 글자 색칠")
app.do_undo()
app.clear_selection()
app.dirty = False
app.goto(0, 0.5)
pump(0.2)

step("좁은 창에서 도구줄 두 줄")
app.fit_toolbar()
pump(0.2)
in2 = str(app.toolarea.pack_info().get("in")) == str(app.bar2)
check(in2, "1000px 창에서는 도구 버튼이 둘째 줄로")
root.geometry("1900x690+0+0")
pump(0.3)
app.fit_toolbar()
pump(0.2)
if root.winfo_width() >= 1500:
    check(str(app.toolarea.pack_info().get("in")) == str(app.bar), "넓은 창에서는 한 줄")
else:
    print("   (이 화면은 넓은 창을 만들 수 없어 한 줄 확인은 생략)")
root.geometry("1000x690+0+0")
pump(0.3)
app.fit_toolbar()
pump(0.2)

step("뷰어 / 편집 모드")
app.app_mode.set("view")
app.set_app_mode()
check(app.toolbtns.winfo_manager() != "", "뷰어 모드에서도 도구 버튼 표시")
check(app.mode.get() == "", "뷰어 모드에서는 눌린 도구 없음")
check(app.optbox.winfo_manager() == "", "뷰어 모드에서 도구 옵션 숨김")
app.pick_tool("mark")
check(app.app_mode.get() == "edit" and app.mode.get() == "mark", "뷰어 모드에서 도구 누르면 편집 모드로")
app.app_mode.set("view")
app.set_app_mode()
app.app_mode.set("edit")
app.set_app_mode()
pump(0.2)
check(app.toolbtns.winfo_manager() != "", "편집 모드에서 도구 표시")
for k, _ in S.TOOLS:
    app.pick_tool(k)
    pump(0.05)
app.pick_tool("shape")
shot("3_edit_mode_shape_tool")
app.pick_tool("edit")

step("글자 수정 (한글)")
items = app.items_for(0)
it = next((i for i in items if "Hello" in i["text"]), None)
check(it is not None, "편집칸 찾기")
if it:
    app.page_no = 0
    app.push_undo()
    app.apply_edits(app.doc[0], [(it["rect"], it["origin"], it["size"], it["color"], False, "안녕 World 테스트")])
    app.dirty = True
    app.render()
    pump(0.2)
    txt = app.doc[0].get_text()
    check("안녕" in txt and "Hello" not in txt, f"수정 결과: {txt[:40]!r}")
    check("●" in app.tabbar.tab(app.tab.frame, "text"), "수정 표시(●)")

step("되돌리기")
app.do_undo()
pump(0.2)
check("Hello" in app.doc[0].get_text(), "되돌린 뒤 원래 글자")

step("찾아 바꾸기 핵심 (회전된 쪽 포함)")
page = app.doc[1]
with S.unrotated(page):
    hits = page.search_for("Rotated")
check(len(hits) == 1, "회전된 쪽에서 찾기")

step("색칠 / 감추기 / 도형 / 지우개")
app.page_no = 0
r = app.items_for(0)[0]["rect"]
n0 = len(list(app.doc[0].annots()))
print("   - 색칠", flush=True)
app.do_area("mark", r)
check(len(list(app.doc[0].annots())) == n0 + 1, "색칠 주석 추가")
for kind in S.SHAPES:
    print("   - 도형", kind, flush=True)
    app.shape_kind.set(kind)
    app.do_shape(fitz.Point(100, 300), fitz.Point(200, 380))
check(len(list(app.doc[0].annots())) == n0 + 1 + len(S.SHAPES), f"도형 {len(S.SHAPES)}종 추가")
pg0 = app.doc[0]
kinds = [a.type[1] for a in pg0.annots()]
del pg0
check("Polygon" in kinds, f"삼각형 = 다각형 주석 {kinds}")
check(kinds.count("Circle") == 2, "원 + 타원")

step("편집해도 화면 전체를 지우지 않음 (번쩍임 없음)")
app.goto(0)
pump(0.3)
before_ids = app.cv.find_withtag("img0")
bg_ids = app.cv.find_withtag("bg")
app.page_no = 0
app.do_shape(fitz.Point(100, 450), fitz.Point(160, 500))
after_ids = app.cv.find_withtag("img0")
check(before_ids and before_ids == after_ids, f"쪽 그림은 그 자리에서 교체 {before_ids} → {after_ids}")
check(app.cv.find_withtag("bg") == bg_ids, "쪽 배경을 다시 만들지 않음")
app.do_undo()
app.page_no = 1
print("   - 회전된 쪽 색칠", flush=True)
app.do_area("mark", fitz.Rect(60, 80, 300, 110))   # 회전된 쪽
app.page_no = 0
second = next(i for i in app.items_for(0) if "Second" in i["text"])
print("   - 감추기", flush=True)
app.do_area("hide", second["rect"])
check("Second" not in app.doc[0].get_text(), "감추기 = 실제 삭제")
pg0 = app.doc[0]                      # 주석을 읽는 동안 쪽 객체를 붙잡아 둠 (PyMuPDF 규칙)
c = fitz.Rect(next(pg0.annots()).rect)
del pg0
app.page_no = 0
print("   - 지우개", flush=True)
app.erase_at(fitz.Point((c.x0 + c.x1) / 2, (c.y0 + c.y1) / 2))
check(len(list(app.doc[0].annots())) == n0 + len(S.SHAPES), "지우개로 하나 삭제")

step("메모를 오른쪽에 펼쳐 보기")
app.view_var.set(S.VIEW_LABEL["cont"])
app.on_view()
pg0 = app.doc[0]
pg0.add_text_annot((300, 300), "오른쪽에 보이는 메모입니다.\n두 번째 줄")
pg0.add_text_annot((420, 320), "두 번째 메모")
del pg0
app.render(goto=0)
pump(0.4)
check(app._memo_pages == {0}, f"메모 있는 쪽 {app._memo_pages}")
check(len(app.cv.find_withtag("memo0")) >= 2, "쪽 오른쪽에 메모 쪽지")
x, y, w, h = app.slots[0]
check(x + w + S.MEMO_W <= float(app.cv.cget("scrollregion").split()[2]) + 1, "메모 칸 자리 확보")
shot("5_memo_side")
app.memo_side.set(False)
app.render()
check(len(app.cv.find_withtag("memo")) == 0, "메모 펼쳐 보기 끄기")
app.memo_side.set(True)
app.render()

step("전체 쪽 회전")
before = [app.doc[i].rotation for i in range(len(app.doc))]
app.rotate_all(90)
after = [app.doc[i].rotation for i in range(len(app.doc))]
check(all((b + 90) % 360 == a for b, a in zip(before, after)), f"전체 회전 {before} → {after}")
app.do_undo()
check([app.doc[i].rotation for i in range(len(app.doc))] == before, "전체 회전 되돌리기")

step("이 파일에서 찾기 (Ctrl+F)")
app.focus_search("file")
sp = app.search_panel
check(sp.scope.get() == "file" and sp.folder_box.winfo_manager() == "", "기본은 이 파일에서")
sp.query.set("page")
sp.toggle()
end = time.time() + 15
while sp.running and time.time() < end:
    pump(0.05)
check(len(sp.hits) >= 2, f"찾은 곳 {len(sp.hits)}")
check(app.sel and app.sel["text"] == "page", "찾은 곳 표시")
i0 = sp.hit_idx
sp.step(1)
check(sp.hit_idx == (i0 + 1) % len(sp.hits), "다음 찾기")
sp.toggle()          # 같은 검색어로 다시 Enter → 다음
check(sp.hit_idx == (i0 + 2) % len(sp.hits), "Enter = 다음")
shot("7_find_in_file")
app.clear_selection()

step("본문 메모 (글상자) 붙이기·옮기기·고치기")
check(app.limit("recent_max") == 200, "최근 파일 기본 200개")
app.memo_style.set("box")
app.view_var.set(S.VIEW_LABEL["cont"])
app.on_view()
app.goto(0)
pump(0.3)
app.page_no = 0
_md = app.memo_dialog
app.memo_dialog = lambda initial="", existing=False: ("save", "본문에 보이는 메모\n두 번째 줄")
sx0, sy0, sw0, sh0 = app.slots[0]
app.memo_at(app.canvas_to_page(0, sx0 + 60, sy0 + 300), (sx0 + 60, sy0 + 300))
pg0 = app.doc[0]
ft = [(a.xref, fitz.Rect(a.rect), a.info.get("content")) for a in pg0.annots(types=[fitz.PDF_ANNOT_FREE_TEXT])]
txt0 = pg0.get_text()
del pg0
check(len(ft) == 1 and "본문에 보이는 메모" in ft[0][2], f"글상자 메모 {ft}")
check("본문에 보이는 메모" in txt0, "본문 글자로 들어감 (검색 가능)")
pg0 = app.doc[0]
subj = [a.info.get("subject", "") for a in pg0.annots(types=[fitz.PDF_ANNOT_FREE_TEXT])]
del pg0
anc = S.parse_anchor(subj[0]) if subj else None
want = app.canvas_to_page(0, sx0 + 60, sy0 + 300)
check(anc is not None and abs(anc.x - want.x) < 1 and abs(anc.y - want.y) < 1, f"원래 위치 기록 {subj}")
check(len(app.cv.find_withtag("memolink0")) >= 2, "원래 위치 점 + 연결선")
shot("9_memo_box")
if ft:
    xref, r0, _ = ft[0]
    app.move_memo(0, xref, r0, 80, 40)
    pg0 = app.doc[0]
    r1 = fitz.Rect(pg0.load_annot(xref).rect)
    del pg0
    check(abs((r1.x0 - r0.x0) - 80 / app.zoom) < 2 and abs((r1.y0 - r0.y0) - 40 / app.zoom) < 2, f"메모 옮기기 {r0} → {r1}")
    app.memo_dialog = lambda initial="", existing=False: ("save", "고친 메모 내용")
    app.memo_at(fitz.Point((r1.x0 + r1.x1) / 2, (r1.y0 + r1.y1) / 2))
    pg0 = app.doc[0]
    contents = [a.info.get("content") for a in pg0.annots(types=[fitz.PDF_ANNOT_FREE_TEXT])]
    del pg0
    check(contents == ["고친 메모 내용"], f"메모 고치기 {contents}")
    pg0 = app.doc[0]
    subj2 = [a.info.get("subject", "") for a in pg0.annots(types=[fitz.PDF_ANNOT_FREE_TEXT])]
    del pg0
    check(subj2 == subj, "옮기고 고쳐도 원래 위치 연결 유지")
    check(len(app.cv.find_withtag("memolink0")) >= 2, "옮긴 뒤에도 연결선")
    shot("9_memo_box_moved")
app.page_no = 1          # 회전된 쪽
sx1, sy1, _, _ = app.slots[1]
app.memo_dialog = lambda initial="", existing=False: ("save", "회전된 쪽 메모")
app.memo_at(app.canvas_to_page(1, sx1 + 40, sy1 + 40), (sx1 + 40, sy1 + 40))
pg1 = app.doc[1]
n1 = len(list(pg1.annots(types=[fitz.PDF_ANNOT_FREE_TEXT])))
del pg1
check(n1 == 1, "회전된 쪽에도 메모")
app.memo_dialog = _md
app.do_undo(); app.do_undo(); app.do_undo(); app.do_undo()

step("회전 / 쪽 범위")
rot = app.doc[2].rotation
app.rotate_pages([2], 90)
check(app.doc[2].rotation == (rot + 90) % 360, "회전")
check(S.parse_pages("3, 1-2", 3) == [2, 0, 1], "쪽 번호 해석")

step("캡쳐")
app.cap_preview.set(True)
app.capture(0, fitz.Rect(50, 50, 300, 200))
app.capture(1, None)
pump(0.3)

step("저장")
out = os.path.join(TMP, "edited.pdf")
app.doc.save(out)
check(os.path.getsize(out) > 0, "저장 파일")
app.dirty = False

step("탭 / 새 파일 / 최근 파일")
app.open_file(pdf2)
pump(0.3)
app.view_var.set(S.VIEW_LABEL["cont2"])
app.on_view()
shot("4_two_tabs_2pages")
check(len(app.tabs) == 2, "탭 2개")
app.open_file(pdf1)
check(len(app.tabs) == 2 and app.path == os.path.abspath(pdf1), "이미 열린 파일은 그 탭으로")
app.next_tab(1)
pump(0.2)
check(app.path == os.path.abspath(pdf2), "탭 이동")
check(os.path.abspath(pdf2) in app.conf["recent"], "최근 파일 기록")
check(len(app.recent_panel.tv.get_children()) >= 2, "최근 패널 목록")
step("탭 × 버튼으로 닫기")
st_ = S.ttk.Style(root)
check(any("tabclose" in n for n in st_.element_names()), "× 그림 요소")
pump(0.3)
spot = None
for yy in range(2, 30, 3):
    for xx in range(0, 600, 2):
        if "tabclose" in app.tabbar.identify(xx, yy):
            spot = (xx, yy)
            break
    if spot:
        break
check(spot is not None, "탭에서 × 위치 찾기")
if spot:
    ev = Ev()
    ev.x, ev.y = spot
    idx = app.tabbar.index(f"@{spot[0]},{spot[1]}")
    app.tabs[idx]._dirty = False
    app.on_tab_press(ev)
    app.on_tab_release(ev)
    pump(0.2)
    check(len(app.tabs) == 1, "× 눌러서 탭 닫기")
else:
    app.close_tab(app.tab)

step("즐겨찾기 / 북마크 / 개수 제한")
app.conf["favorites"].append({"type": "file", "name": "a", "path": pdf1, "added": 1})
app.conf["prefs"]["fav_max"] = 1
check(app.ensure_room("favorites") is True and S.count_items(app.conf["favorites"]) == 0, "가장 오래된 항목 정리")
app.conf["prefs"]["fav_max"] = 100
node = app.new_favorite()
check(node and node["path"] == app.path, "즐겨찾기 항목")

step("즐겨찾기·북마크 × 버튼 / 오른쪽 클릭 메뉴")
fp = app.fav_panel
fp.data.extend([{"type": "file", "name": "지울 파일", "path": pdf1},
                {"type": "folder", "name": "빈 폴더", "children": []},
                {"type": "file", "name": "이름 바꿀 파일", "path": pdf2}])
fp.refresh()
app.side.select(fp)
pump(0.3)
n0 = len(fp.data)
iid = next(k for k, v in fp.map.items() if v[0]["name"] == "지울 파일")
fp.tv.see(iid)
pump(0.1)
bb = fp.tv.bbox(iid, "x")
check(bool(bb) and fp.tv.set(iid, "x") == "✕", "줄 끝 × 표시")
if bb:
    ev = Ev()
    ev.x, ev.y = bb[0] + bb[2] // 2, bb[1] + bb[3] // 2
    fp._press(ev)
    fp._release(ev)
    check(len(fp.data) == n0 - 1 and all(n.get("name") != "지울 파일" for n in fp.data), "× 눌러 바로 삭제")
iid = next(k for k, v in fp.map.items() if v[0]["name"] == "빈 폴더")
fp.delete(iid, ask=False)
check(all(n.get("name") != "빈 폴더" for n in fp.data), "빈 폴더 × 삭제")
iid = next(k for k, v in fp.map.items() if v[0]["name"] == "이름 바꿀 파일")
fp.tv.selection_set(iid)
_ask = S.ask_text
S.ask_text = lambda *a, **k: "바뀐 이름"
fp.rename()
S.ask_text = _ask
check(any(n.get("name") == "바뀐 이름" for n in fp.data), "이름 바꾸기")
check(hasattr(fp, "_context"), "오른쪽 클릭 메뉴")

step("여러 개 선택해서 한꺼번에 삭제")
fp.data[:] = [{"type": "file", "name": f"파일{i}", "path": pdf1} for i in range(4)] + \
    [{"type": "folder", "name": "묶음", "children": [{"type": "file", "name": "안쪽", "path": pdf2}]}]
fp.refresh()
by = {v[0]["name"]: k for k, v in fp.map.items()}
fp.tv.selection_set([by["파일0"], by["파일2"], by["묶음"], by["안쪽"]])
check(len(fp.selected_all()) == 3, "폴더 안 항목은 폴더와 함께 (중복 제외)")
fp.delete()
names = [n["name"] for n in fp.data]
check(names == ["파일1", "파일3"], f"여러 개 삭제 결과 {names}")
fp.select_all()
check(len(fp.tv.selection()) == 2, "Ctrl+A 전체 선택")
fp.delete()
check(fp.data == [], "전체 삭제")

step("즐겨찾기·북마크·최근 목록 검색")
fp.data[:] = [{"type": "file", "name": "예산 보고서", "path": "C:/문서/2026/예산.pdf"},
              {"type": "file", "name": "회의록", "path": "C:/문서/회의/1월.pdf"},
              {"type": "folder", "name": "계약", "children": [
                  {"type": "file", "name": "근로계약서", "path": "C:/계약/근로.pdf"},
                  {"type": "file", "name": "임대차", "path": "C:/계약/임대.pdf"}]}]
fp.refresh()
fp.filter.var.set("계약서")
pump(0.1)
names = [fp.map[i][0]["name"] for i in fp.map]
check(names == ["계약", "근로계약서"], f"폴더 안 항목 찾기 {names}")
fp.filter.var.set("문서 2026")
pump(0.1)
names = [fp.map[i][0]["name"] for i in fp.map]
check(names == ["예산 보고서"], f"경로로·여러 낱말 찾기 {names}")
check(fp.filter.count.cget("text") == "1개/4", f"찾은 개수 표시 {fp.filter.count.cget('text')}")
fp.filter.clear()
pump(0.1)
check(len(fp.map) == 5, "검색 지우면 전체")
bp = app.bm_panel
bp.scope_all.set(True)          # 이 점검은 모든 파일 북마크에서 찾기
bp.data[:] = [{"type": "mark", "name": "중요 표", "path": pdf1, "page": 11},
              {"type": "mark", "name": "결론", "path": pdf1, "page": 2}]
bp.refresh()
bp.filter.var.set("12쪽")
pump(0.1)
check([bp.map[i][0]["name"] for i in bp.map] == ["중요 표"], "북마크 쪽 번호로 찾기")

bp.filter.clear()
bp.scope_all.set(False)
rp = app.recent_panel
rp.refresh()
total = len(rp.tv.get_children())
rp.filter.var.set("sample2")
pump(0.1)
check(len(rp.tv.get_children()) == 1 and total >= 2, f"최근 파일 찾기 {total}→{len(rp.tv.get_children())}")
rp.filter.clear()
fp.data[:] = []
bp.data[:] = []
fp.refresh()
bp.refresh()
shot("8_favorites_x")

step("폴더에서 PDF 찾기 (본문)")
sp = app.search_panel
app.focus_search("folder")
check(sp.folder_box.winfo_manager() != "", "폴더 칸 표시")
sp.folder.set(TMP)
sp.query.set("Landscape")
sp.body.set(True)
sp.start()
end = time.time() + 30
while sp.running and time.time() < end:
    pump(0.1)
check(not sp.running, "검색 끝남")
check(len(sp.results) >= 2, f"검색 결과 {len(sp.results)}개")

step("설정 / 사용방법 / 정보 창")
root.event_generate("<Motion>", warp=True, x=300, y=200)
pump(0.1)
app.settings_dialog()
app.show_help()
app.show_about()
pump(0.4)
check(len(S.HELP_SECTIONS) >= 10, "사용방법 목차")
app._help_goto(4)
pump(0.3)
try:
    from PIL import ImageGrab
    hw = app._help
    hw.lift(); pump(0.4)
    x, y = hw.winfo_rootx(), hw.winfo_rooty()
    os.makedirs(SHOTS, exist_ok=True)
    ImageGrab.grab(bbox=(x, y, x + hw.winfo_width(), y + hw.winfo_height()), all_screens=True).save(
        os.path.join(SHOTS, "10_help.png"))
except Exception as ex:
    print("   (도움말 스크린샷 생략:", ex, ")")
pops = [w for w in root.winfo_children() if isinstance(w, S.Popup)]
check(len(pops) >= 3 and all(w.winfo_viewable() for w in pops), "팝업창 표시")
px, py = root.winfo_pointerx(), root.winfo_pointery()
near = [w for w in pops if abs(w.winfo_rootx() - px) < 400 and abs(w.winfo_rooty() - py) < 400]
check(len(near) >= 1, f"팝업이 마우스 근처에 ({px},{py})")
for w in root.winfo_children():
    if isinstance(w, tk.Toplevel):
        w.destroy()

step("색상표")
app.pick_tool("mark")
pump(0.2)
pop = app.palette_popup(app.swatch, app.set_color)
pump(0.2)
cells = [w for fr in pop.winfo_children() for w in fr.winfo_children() if w.cget("text") == ""]
check(len(cells) == 24, f"색상표 {len(cells)}색")
shot("6_palette")
pop.destroy()
app.set_color("#ce93d8")
check(app.swatch.cget("bg") == "#ce93d8", "색칠 색 바뀜")

step("아이콘")
check(len(app.icon_users) >= 25, f"아이콘 {len(app.icon_users)}개")
check(app.tool_rbs["mark"].cget("image") != "", "도구 아이콘")

step("화면 꾸미기 (테마 · 글꼴 · 배경 그림)")
app.view_var.set(S.VIEW_LABEL["cont"])
app.on_view()
app.app_mode.set("edit")
app.set_app_mode()
st = S.ttk.Style(root)
for key in S.THEMES:
    app.set_preset(key)
    pump(0.2)
    check(app.cv.cget("bg").lower() == S.THEMES[key]["canvas"], f"{key} 문서 배경 색")
    if key in ("clip", "light"):
        check(str(st.lookup("Top.TFrame", "background")).lower() == S.THEMES[key]["bg"], f"{key}: 도구줄에 테마 색")
        check(str(st.lookup("TFrame", "background")).lower() == S.NEUTRAL["bg"], f"{key}: 아래쪽은 기본 색")
    if key == "dark":
        check(str(st.lookup("TFrame", "background")).lower() == S.THEMES["dark"]["bg"], "어둡게: 전체 적용")
    shot(f"theme_{key}")
wall = os.path.join(TMP, "wall.png")
with open(wall, "wb") as f:
    f.write(__import__("base64").b64decode("".join(S.LOGO_PNG)))
app.settings_dialog()
dlg, tv, preset_name, ok, cancel = app._settings_dlg
preset_name.set(S.THEMES["clip"]["name"])
tv["font_family"].set("굴림")
tv["font_size"].set("11")
tv["canvas"].set("#336699")
tv["wall"].set(wall)
ok()
pump(0.4)
check(S.tkfont.nametofont("TkDefaultFont").cget("size") == 11, "글자 크기 적용")
check(app.cv.cget("bg").lower() == "#336699", "직접 고른 배경 색")
check(len(app.cv.find_withtag("wall")) == 1, "배경 그림 표시")
check(app.conf["prefs"]["theme"]["wall"] == wall, "테마 설정 저장")
shot("theme_custom_wall")
app.settings_dialog()
shot("settings_quick")
wp = S.wall_preset_path("하늘")
check(os.path.exists(wp) and os.path.getsize(wp) > 10000, "기본 배경 그림 꺼내기")
app._settings_dlg[1]["wall"].set(wp)
app._settings_dlg[3]()      # 저장
pump(0.4)
check(len(app.cv.find_withtag("wall")) == 1, "기본 배경 그림 표시")
shot("theme_builtin_wall")
app.settings_dialog()
app._settings_dlg[4]()      # 취소
app.theme.update(font_size=9, wall="", canvas="")
app.set_preset("clip")
pump(0.2)

step("프로그램 하나만 실행 (파일 넘기기)")
q = queue.Queue()
srv = S.start_ipc_server(q)
check(srv is not None, "대기 시작")
check(S.send_to_running([pdf1]), "파일 보내기")
check(q.get(timeout=3) == [pdf1], "파일 받기")
srv.close()

step("광고 처리")
logo = __import__("base64").b64decode("".join(S.LOGO_PNG))
app.apply_ads({"interval": 5, "ads": [{"data": logo, "link": "https://smartgong.kr", "until": ""},
                                      {"data": b"broken", "link": "", "until": ""},
                                      {"data": logo, "link": "", "until": "2000-01-01"}]})
check(len(app.ad_list) == 1, "깨진 그림·지난 광고 제외")
app.apply_ads({"interval": 5, "ads": []})
check(int(app.ad_frame.cget("height")) <= 1, "광고 없으면 최소화")

step("탭이 많을 때 ◀ ▶")
_many = []
for _i in range(12):
    _f = os.path.join(TMP, "긴_이름의_시험_문서_%02d.pdf" % _i)
    _d = fitz.open(); _d.new_page().insert_text((72, 72), "t%d" % _i); _d.save(_f); _many.append(_f)
    app.open_file(_f)
pump(0.6)
check(app.tab_right.winfo_ismapped(), "탭이 넘치면 화살표 표시")
check(app.tab_off > 0, "고른 탭이 보이게 밀림")
app.switch_tab(app.tabs[0]); pump(0.3)
check(app.tab_off == 0, "첫 탭으로 가면 맨 앞")
for _t in [t for t in app.tabs if t.path in _many]:
    _t._dirty = False
    app.close_tab(_t)
pump(0.4)
check(not app.tab_right.winfo_ismapped(), "탭이 줄면 화살표 숨김")

step("저장 · 다른 이름으로 저장")
_sp = os.path.join(TMP, "저장시험.pdf")
_d = fitz.open(); _d.new_page().insert_text((72, 72), "orig"); _d.save(_sp)
app.open_file(_sp); pump(0.3)
app.doc[0].insert_text((72, 120), "SAVED-NOW"); app.dirty = True
check(app.save() and "SAVED-NOW" in fitz.open(_sp)[0].get_text() and app.path == _sp, "Ctrl+S 바로 덮어쓰기")
_sp2 = os.path.join(TMP, "저장시험_새이름.pdf")
_ask = S.filedialog.asksaveasfilename
S.filedialog.asksaveasfilename = lambda **kw: _sp2
app.doc[0].insert_text((72, 160), "SAVE-AS"); app.dirty = True
check(app.save_as() and app.path == _sp2 and "SAVE-AS" in fitz.open(_sp2)[0].get_text()
      and "SAVE-AS" not in fitz.open(_sp)[0].get_text(), "다른 이름으로 저장 → 탭이 새 파일, 원본 그대로")
S.filedialog.asksaveasfilename = _ask
app.tab._dirty = False
app.close_tab(app.tab)
pump(0.2)

step("한글 입력 창 글꼴 맞추기")
probe = S.ttk.Entry(root, font=("맑은 고딕", 11))
probe.pack()
probe.focus_force()
pump(0.4)
res = S.ime_match_font(probe)
print("     IME 조합 창:", res if res else "IME 없음(영문 Windows) — 오류 없이 넘어감", flush=True)
check(res is None or res[1] > 8, "조합 창 글꼴 크기")
probe.destroy()

step("북마크는 파일마다 따로")
_fa = os.path.join(TMP, "북마크A.pdf"); _fb = os.path.join(TMP, "북마크B.pdf")
for _f in (_fa, _fb):
    _d = fitz.open(); _d.new_page(); _d.new_page(); _d.save(_f)
app.conf["bookmarks"].append({"type": "mark", "name": "A의 북마크", "path": _fa, "page": 1})
app.conf["bookmarks"].append({"type": "mark", "name": "B의 북마크", "path": _fb, "page": 0})
app.open_file(_fa); pump(0.3)
_names = [app.bm_panel.tv.item(i, "text") for i in app.bm_panel.tv.get_children()]
check(any("A의" in n for n in _names) and not any("B의" in n for n in _names), "A 파일엔 A 북마크만")
app.open_file(_fb); pump(0.3)
_names = [app.bm_panel.tv.item(i, "text") for i in app.bm_panel.tv.get_children()]
check(any("B의" in n for n in _names) and not any("A의" in n for n in _names), "B 탭으로 바꾸면 B 북마크만")
app.bm_panel.scope_all.set(True); app.bm_panel.refresh()
_names = [app.bm_panel.tv.item(i, "text") for i in app.bm_panel.tv.get_children()]
check(any("A의" in n for n in _names) and any("B의" in n for n in _names), "'모든 파일' 체크하면 전체")
app.bm_panel.scope_all.set(False); app.bm_panel.refresh()
for _t in [t for t in app.tabs if t.path in (_fa, _fb)]:
    _t._dirty = False
    app.close_tab(_t)
app.conf["bookmarks"][:] = [n for n in app.conf["bookmarks"] if n.get("path") not in (_fa, _fb)]
app.bm_panel.refresh(); pump(0.2)

step("인쇄 (Microsoft Print to PDF)")
_api = S._print_lib()
_hdc = _api["gdi"].CreateDCW("WINSPOOL", "Microsoft Print to PDF", None, None)
if _hdc:
    _out = os.path.join(TMP, "인쇄결과.pdf")
    S.print_pages(_hdc, app.doc, list(range(len(app.doc))), title="점검", output=_out)
    _api["gdi"].DeleteDC(_hdc)
    for _ in range(40):
        if os.path.exists(_out) and os.path.getsize(_out) > 1000:
            break
        time.sleep(0.25)
    check(os.path.exists(_out) and len(fitz.open(_out)) == len(app.doc), "모든 쪽 인쇄됨")
else:
    print("     (이 PC에는 Microsoft Print to PDF 가 없어 건너뜀)", flush=True)

step("바로가기 만들기")
_scd = os.path.join(TMP, "바로가기시험")
os.makedirs(_scd, exist_ok=True)
S.make_shortcut(_scd)
check(os.path.exists(os.path.join(_scd, S.SHORTCUT_NAME)), "바로가기(.lnk) 만들어짐")
app.refresh_shortcut_btn(); pump(0.3)
check(app.sc_btn.winfo_ismapped() == (not (S.has_desktop_shortcut() and S.is_pinned_to_taskbar())), "바로가기 버튼 표시/숨김")

step("업데이트 필요 버튼")
app.update_info = {"version": "99.0.0", "date": "2099-01-01", "notes": "### 99.0.0 에서 바뀐 점\n- 시험"}
app.show_update_btn(); pump(0.3)
check(app.upd_btn.winfo_ismapped() and "99.0.0" in app.upd_btn.cget("text"), "새 버전이면 버튼 보임")
app.show_update(); pump(0.3)
_ups = [w for w in root.winfo_children() if isinstance(w, S.tk.Toplevel) and w.title() == "새 버전"]
check(bool(_ups), "버튼 누르면 새 버전 창")
for _w in _ups:
    _w.destroy()
app.update_info = None
app.show_update_btn(); pump(0.2)
check(not app.upd_btn.winfo_ismapped(), "최신이면 버튼 숨김")
check(S.ver_tuple("1.0.10") > S.ver_tuple("1.0.9") and S.ver_tuple("v1.1") > S.ver_tuple("1.0.9"), "버전 비교")

step("사용 통계")
def wait_for(cond, sec=5):
    end = time.time() + sec
    while time.time() < end and not cond():
        pump(0.05)
    return cond()
wait_for(lambda: S.threading.active_count() <= base_threads, 3)
app.conf["prefs"].pop("last_ping", None)
app.conf["prefs"]["no_stats"] = False
stats_sent.clear()
app.send_stats()
today = __import__("datetime").date.today().isoformat()
wait_for(lambda: app.conf["prefs"].get("last_ping") == today)
iid = app.conf["prefs"].get("install_id", "")
check(len(iid) == 32, "무작위 번호 만들기")
print("     보낸 것:", [(u.split("/apps/")[-1], m, b) for u, m, b in stats_sent], flush=True)
check(len(stats_sent) == 2 and "/apps/smartpdfeditor/installs/" + iid in stats_sent[0][0], "설치 기록 보내기")
check(bool(stats_sent) and set(stats_sent[0][2]) <= {"v", "last", "first"}
      and stats_sent[0][2]["v"] == S.APP_VER, "번호·버전만 보냄")
check(app.conf["prefs"].get("last_ping") == today, "오늘 보냄 기록")
n = len(stats_sent)
app.send_stats()
pump(0.5)
check(len(stats_sent) == n, "하루 한 번만")
app.conf["prefs"].pop("last_ping", None)
app.conf["prefs"]["no_stats"] = True
stats_sent.clear()
app.send_stats()
pump(0.5)
check(not stats_sent, "보내지 않기 설정")

step("종료")
for t in app.tabs:
    t._dirty = False
app.on_close()
check(os.path.exists(S.CONF_FILE), "설정 저장")

print()
if errors:
    print("점검 실패:")
    for e in errors:
        print("  ", e)
    sys.exit(1)
print("SMOKE OK — 모든 점검 통과")
