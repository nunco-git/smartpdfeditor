# -*- coding: utf-8 -*-
# smartpdfeditor — 스마트PDF Editor
# Copyright (C) 2026 스마트공 (smartgong.kr)
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation, version 3.
# This program is distributed WITHOUT ANY WARRANTY. See the LICENSE file for details.
# Source code: https://github.com/nunco-git/smartpdfeditor
#
# Uses PyMuPDF / MuPDF (AGPL-3.0, Copyright (C) Artifex Software, Inc.)
"""
스마트PDF Editor (스마트공 · smartgong.kr)
 - PDF 보기 (페이지 이동, 확대/축소)
 - 글자 위에 마우스를 올리면 강조 → 클릭하면 수정 창
 - 찾아 바꾸기 (전체 페이지)
 - 되돌리기, 다른 이름으로 저장
 - 파일 즐겨찾기 / 페이지 북마크 (폴더로 정리, 끌어서 이동)
 - 최근 파일, 마지막으로 본 페이지 기억
 - 설정 내보내기 / 가져오기 (JSON)
 - 페이지 회전(쪽별·여러 쪽), 원하는 쪽만 골라 새 PDF로 저장
 - 색칠(형광펜), 감추기(내용 삭제 후 검정/흰색 칠), 메모, 주석 지우기
 - 연속 스크롤 보기, 여러 쪽 나란히 보기(2~4쪽), 가로맞춤/세로맞춤
 - 여러 파일을 탭으로 (프로그램은 하나만 실행, 다시 열면 새 탭) / 새 창으로 열기
 - 도형 그리기 (사각형·원·선·화살표)
 - 파일 검색 (파일명·PDF 본문) → 결과를 사이드바 목록으로
 - 영역 캡쳐 (끌어서 선택 → 클립보드 복사 / PNG 저장)

필요: pip install pymupdf
exe:  smartpdfeditor_build.bat 실행 → smartpdfeditor.exe
"""
import os
import sys
import base64
import json
import datetime
import subprocess
import shutil
import webbrowser
import urllib.request
import urllib.parse
import contextlib
import socket
import threading
import queue
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser

try:
    import pymupdf as fitz  # PyMuPDF (새 이름)
except ImportError:
    try:
        import fitz  # PyMuPDF (예전 이름)
    except ImportError:
        fitz = None
if fitz is None:
    r = tk.Tk(); r.withdraw()
    messagebox.showerror("스마트PDF Editor", "PyMuPDF가 필요합니다.\n\n명령 프롬프트에서:\npip install pymupdf")
    sys.exit(1)

APP = "스마트PDF Editor"
HOME_URL = "https://smartgong.kr"
SOURCE_URL = "https://github.com/nunco-git/smartpdfeditor"
RELEASES_URL = SOURCE_URL + "/releases"
WIN_FONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
UNDO_MAX = 30
_APPDATA = os.environ.get("APPDATA") or os.path.expanduser("~")
CONF_DIR = os.path.join(_APPDATA, "smartpdfeditor")
CONF_FILE = os.path.join(CONF_DIR, "settings.json")
_OLD_CONF = os.path.join(_APPDATA, "PDF글자수정뷰어", "settings.json")   # 이전 이름의 설정 → 자동으로 옮김
if not os.path.exists(CONF_FILE) and os.path.exists(_OLD_CONF):
    try:
        os.makedirs(CONF_DIR, exist_ok=True)
        shutil.copy2(_OLD_CONF, CONF_FILE)
    except OSError:
        pass
APP_DIR = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
AD_W, AD_H = 250, 250     # 광고창 기본 크기 (사이드바 폭에 맞춘 정사각형 배너)
AD_FILES = ("ad.png", "ad.gif", "ad.jpg", "ad.jpeg")   # 실행파일 옆에 두면 이 광고가 우선 (시험용)
AD_LINK_FILE = "ad.txt"   # 첫 줄 = 광고 클릭 시 열 주소
AD_URL = "https://smartgong.kr/ads/smartpdfeditor.json"   # 인터넷 광고 설정
AD_CACHE = os.path.join(CONF_DIR, "ad_cache")            # 인터넷이 안 될 때 마지막 광고 사용
AD_REFRESH_MS = 3 * 60 * 60 * 1000                       # 3시간마다 새로 확인
APP_VER = "1.0.0"

# 스마트공 로고 (PNG, base64 내장)
LOGO_PNG = (
    "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"
)

HELP_TEXT = [
    ("스마트PDF Editor 사용방법", "h1"),
    ("PDF를 보면서 바로 글자를 고치고, 색칠·도형·메모·캡쳐까지 할 수 있는 프로그램입니다.\n", ""),
    ("■ 파일 열기", "h2"),
    ("· Ctrl+O 또는 [열기] — 여러 파일을 고르면 탭으로 각각 열립니다.\n"
     "· 탐색기에서 PDF를 더블클릭하면 이미 켜진 창의 새 탭으로 열립니다. (설정에서 '새 창'으로 변경 가능)\n"
     "· Ctrl+Tab 탭 이동 · Ctrl+W 탭 닫기 · 탭 우클릭 → 새 창으로 옮기기\n", ""),
    ("■ 보기", "h2"),
    ("· 마우스 휠로 위아래 연속 스크롤 (보기 메뉴: 휠 한 칸에 한 쪽씩), Ctrl+휠 확대/축소\n"
     "· 아래 상태줄 오른쪽 아이콘: ↔ 가로맞춤 · ↕ 세로맞춤 · 한 쪽씩 / 연속 / 2·3·4쪽 나란히\n"
     "· 👁 뷰어 모드: 끌어서 글자 선택 → Ctrl+C 복사, Ctrl+B 선택한 글자로 북마크, 우클릭 메뉴\n"
     "· 휠 버튼(가운데 버튼)으로 끌면 화면 이동\n", ""),
    ("■ 도구 (Esc = 글자수정으로 돌아가기)", "h2"),
    ("· ✎ 글자수정: 글자를 클릭 → 새 글자 입력 → Enter.  Ctrl+F 찾아 바꾸기\n"
     "· 🖍 색칠: 글자를 클릭하거나 영역을 끌어서 형광펜\n"
     "· ■ 감추기: 영역을 끌면 아래 내용을 지우고 검정/흰색으로 덮음 (개인정보 가리기)\n"
     "· ◻ 도형: 사각형·원·선·화살표를 끌어서 그리기 (Shift = 정사각형·정원)\n"
     "· 💬 메모: 클릭한 곳에 메모 붙이기\n"
     "· ⌫ 지우개: 색칠·도형·메모를 클릭해서 지우기\n"
     "· ✂ 캡쳐(Ctrl+Shift+C): 영역을 끌면 클립보드로 복사 → 한글·카톡 등에 Ctrl+V\n", ""),
    ("■ 페이지", "h2"),
    ("· ⟲ ⟳ 지금 쪽 회전 (Ctrl+L / Ctrl+R) · [여러 쪽 회전]\n"
     "· [원하는 쪽만 저장] (Ctrl+E): 예) 7, 2, 10-12 → 그 쪽들만 새 PDF로\n", ""),
    ("■ 왼쪽 사이드바 (F9로 숨기기)", "h2"),
    ("· 즐겨찾기(Ctrl+D) · 북마크(Ctrl+B) — 글자를 선택하고 추가하면 그 글자가 이름이 되고 그 위치로 이동\n"
     "· 파일 검색(Ctrl+Shift+F): 폴더 안 PDF를 파일명·본문으로 찾기 → 결과를 즐겨찾기/북마크로 저장\n", ""),
    ("■ 저장", "h2"),
    ("· Ctrl+S — 기본 이름은 '원본_수정.pdf' (원본은 그대로)\n"
     "· Ctrl+Z 되돌리기 (최근 30번)\n"
     "· [설정] → 설정 내보내기/가져오기로 즐겨찾기·북마크를 다른 PC로 옮기기\n", ""),
    ("더 많은 업무 도구는 smartgong.kr 에서 만나보세요.\n"
     "이 프로그램은 AGPL-3.0 오픈소스입니다 · 소스: github.com/nunco-git/smartpdfeditor", "foot"),
]
IPC_PORT = 48517          # 프로그램 하나만 실행: 두 번째 실행은 이 포트로 파일을 넘기고 종료
IPC_TOKEN = "PDFTE-1"
SEARCH_MAX = 3000
SHAPES = ("사각형", "원", "선", "화살표")
TOOLS = [("edit", "✎ 글자수정"), ("mark", "🖍 색칠"), ("hide", "■ 감추기"), ("shape", "◻ 도형"),
         ("memo", "💬 메모"), ("erase", "⌫ 지우개"), ("capture", "✂ 캡쳐")]
TOOL_LABEL = dict(TOOLS)
LIMIT_DEFAULTS = {"fav_max": 100, "bm_max": 200, "recent_max": 20}
MARGIN = 12      # 화면 가장자리 여백(px)
GAP = 12         # 쪽 사이 간격(px)
VIEWS = [("single", "한 쪽씩", 1), ("cont", "연속 스크롤", 1), ("cont2", "2쪽씩 나란히", 2),
         ("cont3", "3쪽씩 나란히", 3), ("cont4", "4쪽씩 나란히", 4)]
VIEW_LABEL = {k: t for k, t, _ in VIEWS}
VIEW_KEY = {t: k for k, t, _ in VIEWS}
VIEW_COLS = {k: c for k, _, c in VIEWS}
LASTPAGE_MAX = 300


# ───────────────────────── 설정 ─────────────────────────
def default_conf():
    return {"version": 1, "favorites": [], "bookmarks": [], "recent": [], "recent_time": {}, "last_page": {},
            "prefs": {"zoom": 1.3, "view": "cont", "fit": "width", "unit": "line", "autofit": True, "panel": True, "geometry": "1200x820"}}


def load_conf():
    conf = default_conf()
    try:
        with open(CONF_FILE, encoding="utf-8") as f:
            data = json.load(f)
        for k in conf:
            if k in data:
                if isinstance(conf[k], dict):
                    conf[k].update(data[k])
                else:
                    conf[k] = data[k]
    except (OSError, ValueError):
        pass
    return conf


def save_conf(conf):
    try:
        os.makedirs(CONF_DIR, exist_ok=True)
        tmp = CONF_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(conf, f, ensure_ascii=False, indent=1)
        os.replace(tmp, CONF_FILE)
    except OSError:
        pass


def remove_node(container, node):
    for i, x in enumerate(container):
        if x is node:
            del container[i]
            return True
    return False


def iter_items(nodes, parent=None):
    """폴더 안까지 모든 항목(폴더 제외)을 (항목, 담긴 목록)으로"""
    for n in nodes:
        if n.get("type") == "folder":
            yield from iter_items(n.get("children", []), n)
        else:
            yield n, nodes


def count_items(nodes):
    return sum(1 for _ in iter_items(nodes))


def contains_node(root, node):
    """root 폴더 안(하위 포함)에 node가 있는지"""
    for ch in root.get("children", []):
        if ch is node or (ch.get("type") == "folder" and contains_node(ch, node)):
            return True
    return False


# ───────────────── 폴더가 있는 목록 (즐겨찾기·북마크 공용) ─────────────────
class TreePanel(ttk.Frame):
    """data: 노드 리스트. 노드 = {"type":"folder","name","open","children"} 또는 항목
    on_add(): 새 항목 dict 반환(없으면 None) / on_activate(node): 더블클릭 / label(node): 표시 글자"""

    def __init__(self, master, data, on_add, on_activate, label, on_change, add_text):
        super().__init__(master)
        self.data, self.on_add, self.on_activate = data, on_add, on_activate
        self.label, self.on_change = label, on_change
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 3))
        ttk.Button(bar, text=add_text, command=self.add).pack(side="left")
        ttk.Button(bar, text="새 폴더", command=self.new_folder).pack(side="left", padx=2)
        ttk.Button(bar, text="이름", width=4, command=self.rename).pack(side="left")
        ttk.Button(bar, text="삭제", width=4, command=self.delete).pack(side="left", padx=2)
        self.tv = ttk.Treeview(self, show="tree", selectmode="browse")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv.pack(fill="both", expand=True)
        self.tv.tag_configure("missing", foreground="#999")
        self.map = {}
        self.drag = None
        self.tv.bind("<Double-1>", self._dbl)
        self.tv.bind("<Return>", self._dbl)
        self.tv.bind("<Delete>", lambda e: self.delete())
        self.tv.bind("<F2>", lambda e: self.rename())
        self.tv.bind("<ButtonPress-1>", self._press)
        self.tv.bind("<B1-Motion>", self._motion)
        self.tv.bind("<ButtonRelease-1>", self._release)
        self.tv.bind("<<TreeviewOpen>>", lambda e: self._set_open(True))
        self.tv.bind("<<TreeviewClose>>", lambda e: self._set_open(False))
        self.refresh()

    def refresh(self, select=None):
        self.tv.delete(*self.tv.get_children())
        self.map = {}
        sel_iid = None

        def put(parent, nodes):
            nonlocal sel_iid
            for n in nodes:
                if n.get("type") == "folder":
                    iid = self.tv.insert(parent, "end", text="📁 " + n.get("name", "폴더"), open=n.get("open", True))
                    self.map[iid] = (n, nodes)
                    put(iid, n.setdefault("children", []))
                else:
                    miss = n.get("path") and not os.path.exists(n["path"])
                    iid = self.tv.insert(parent, "end", text=self.label(n), tags=("missing",) if miss else ())
                    self.map[iid] = (n, nodes)
                if n is select:
                    sel_iid = iid
        put("", self.data)
        if sel_iid:
            self.tv.selection_set(sel_iid)
            self.tv.see(sel_iid)

    def selected(self):
        sel = self.tv.selection()
        return self.map.get(sel[0]) if sel else None

    def target_container(self):
        """선택한 폴더 안, 또는 선택 항목과 같은 폴더"""
        s = self.selected()
        if not s:
            return self.data
        node, cont = s
        return node["children"] if node.get("type") == "folder" else cont

    def changed(self, select=None):
        self.refresh(select)
        self.on_change()

    def add(self):
        node = self.on_add()
        if node:
            self.target_container().append(node)
            self.changed(node)

    def new_folder(self):
        name = ask_text(self, "새 폴더", "폴더 이름", "새 폴더")
        if name:
            node = {"type": "folder", "name": name, "open": True, "children": []}
            self.target_container().append(node)
            self.changed(node)

    def rename(self):
        s = self.selected()
        if not s:
            return
        node = s[0]
        name = ask_text(self, "이름 바꾸기", "새 이름", node.get("name", ""))
        if name:
            node["name"] = name
            self.changed(node)

    def delete(self):
        s = self.selected()
        if not s:
            return
        node, cont = s
        msg = f"'{node.get('name')}' 폴더와 안의 항목을 모두 삭제할까요?" if node.get("type") == "folder" \
            else f"'{node.get('name')}'을(를) 삭제할까요?"
        if messagebox.askyesno(APP, msg, parent=self):
            remove_node(cont, node)
            self.changed()

    def _set_open(self, val):
        iid = self.tv.focus()
        if iid in self.map:
            self.map[iid][0]["open"] = val
            self.on_change()

    def _dbl(self, e):
        s = self.selected()
        if s and s[0].get("type") != "folder":
            self.on_activate(s[0])
            return "break"

    # 끌어서 폴더로 이동
    def _press(self, e):
        iid = self.tv.identify_row(e.y)
        self.drag = (iid, e.y, False) if iid else None

    def _motion(self, e):
        if self.drag and abs(e.y - self.drag[1]) > 6:
            self.drag = (self.drag[0], self.drag[1], True)
            self.tv.configure(cursor="hand2")

    def _release(self, e):
        d, self.drag = self.drag, None
        self.tv.configure(cursor="")
        if not d or not d[2]:
            return
        src = self.map.get(d[0])
        if not src:
            return
        node, cont = src
        tgt_iid = self.tv.identify_row(e.y)
        if tgt_iid == d[0]:
            return
        if tgt_iid:
            tnode, tcont = self.map[tgt_iid]
            if node.get("type") == "folder" and (tnode is node or contains_node(node, tnode)):
                return  # 폴더를 자기 안으로 넣을 수 없음
            remove_node(cont, node)
            if tnode.get("type") == "folder":
                tnode.setdefault("children", []).append(node)
                tnode["open"] = True
            else:
                idx = next(i for i, x in enumerate(tcont) if x is tnode)
                tcont.insert(idx, node)
        else:  # 빈 곳에 놓으면 맨 위 단계 끝으로
            remove_node(cont, node)
            self.data.append(node)
        self.changed(node)


def ask_text(parent, title, prompt, initial=""):
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.transient(parent.winfo_toplevel())
    dlg.resizable(False, False)
    frm = ttk.Frame(dlg, padding=10)
    frm.pack()
    ttk.Label(frm, text=prompt).pack(anchor="w")
    v = tk.StringVar(value=initial)
    ent = ttk.Entry(frm, textvariable=v, width=40)
    ent.pack(pady=6)
    ent.focus_set()
    ent.select_range(0, "end")
    res = {"v": None}

    def ok(_=None):
        res["v"] = v.get().strip() or None
        dlg.destroy()
    b = ttk.Frame(frm)
    b.pack(fill="x")
    ttk.Button(b, text="취소", command=dlg.destroy).pack(side="right")
    ttk.Button(b, text="확인", command=ok).pack(side="right", padx=4)
    ent.bind("<Return>", ok)
    dlg.bind("<Escape>", lambda e: dlg.destroy())
    dlg.grab_set()
    dlg.wait_window()
    return res["v"]


# ───────────────────────── 글꼴 ─────────────────────────
_font_cache = {}

def get_font(bold):
    """(PDF 안 글꼴이름, 글꼴파일경로 또는 None, fitz.Font) 반환. 한글 지원 글꼴 우선."""
    key = bool(bold)
    if key in _font_cache:
        return _font_cache[key]
    names = ["malgunbd.ttf", "malgun.ttf"] if bold else ["malgun.ttf"]
    names += ["NanumGothicBold.ttf", "NanumGothic.ttf"] if bold else ["NanumGothic.ttf"]
    for n in names:
        p = os.path.join(WIN_FONTS, n)
        if os.path.exists(p):
            fname = "krb" if ("bd" in n.lower() or "Bold" in n) else "kr"
            res = (fname, p, fitz.Font(fontfile=p))
            _font_cache[key] = res
            return res
    # 윈도우 글꼴이 없으면 PyMuPDF 내장 한글(CJK) 글꼴
    res = ("korea", None, fitz.Font(ordering=3))
    _font_cache[key] = res
    return res


@contextlib.contextmanager
def unrotated(page):
    """회전된 페이지도 회전 0 기준 좌표로 다루기 위해 잠시 회전을 풀었다가 되돌림"""
    rot = page.rotation
    if rot:
        page.set_rotation(0)
    try:
        yield page
    finally:
        if rot:
            page.set_rotation(rot)


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def parse_pages(text, n):
    """'1-3, 5, 9-7, 10-' → 0부터 시작하는 쪽 번호 목록 (입력 순서, 중복 제거)"""
    out = []
    for tok in text.replace(" ", ",").split(","):
        tok = tok.strip()
        if not tok:
            continue
        if "-" in tok or "~" in tok:
            a, b = tok.replace("~", "-").split("-", 1)
            a = int(a) if a.strip() else 1
            b = int(b) if b.strip() else n
            rng = range(a, b + 1) if a <= b else range(a, b - 1, -1)
        else:
            rng = [int(tok)]
        for p in rng:
            if not 1 <= p <= n:
                raise ValueError(f"{p}쪽은 없습니다 (전체 {n}쪽).")
            if p - 1 not in out:
                out.append(p - 1)
    if not out:
        raise ValueError("쪽 번호를 입력해주세요.")
    return out


def color_tuple(c):
    try:
        return fitz.sRGB_to_pdf(c)
    except Exception:
        return ((c >> 16 & 255) / 255, (c >> 8 & 255) / 255, (c & 255) / 255)


# ───────────────────────── 클립보드에 그림 넣기 (Windows) ─────────────────────────
def pixmap_to_dib(pix):
    """PyMuPDF Pixmap(RGB) → CF_DIB 바이트 (BITMAPINFOHEADER + 아래→위 BGR)"""
    import struct
    w, h, n = pix.width, pix.height, pix.n
    if n != 3 or pix.alpha:
        pix = fitz.Pixmap(fitz.csRGB, pix, 0)
        w, h = pix.width, pix.height
    stride = pix.stride
    src = pix.samples
    bgr = bytearray(len(src))
    bgr[0::3], bgr[1::3], bgr[2::3] = src[2::3], src[1::3], src[0::3]
    row = w * 3
    pad = (4 - row % 4) % 4
    out = bytearray()
    for y in range(h - 1, -1, -1):
        out += bgr[y * stride: y * stride + row]
        out += b"\0" * pad
    header = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(out), 2835, 2835, 0, 0)
    return header + bytes(out)


def copy_image_to_clipboard(pix):
    """성공하면 True. Windows 전용 (한글·워드·엑셀·그림판·카톡 등에 붙여넣기 가능)"""
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    k32.GlobalAlloc.restype = ctypes.c_void_p
    k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    k32.GlobalFree.argtypes = [ctypes.c_void_p]
    u32.SetClipboardData.restype = ctypes.c_void_p
    u32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    u32.OpenClipboard.argtypes = [ctypes.c_void_p]
    u32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    u32.RegisterClipboardFormatW.restype = wintypes.UINT

    def put(fmt, data):
        h = k32.GlobalAlloc(0x0002, len(data))   # GMEM_MOVEABLE
        if not h:
            return False
        ptr = k32.GlobalLock(h)
        ctypes.memmove(ptr, data, len(data))
        k32.GlobalUnlock(h)
        if not u32.SetClipboardData(fmt, h):
            k32.GlobalFree(h)
            return False
        return True

    for _ in range(10):          # 다른 프로그램이 잠깐 잡고 있을 수 있어 재시도
        if u32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        return False
    try:
        u32.EmptyClipboard()
        ok = put(8, pixmap_to_dib(pix))               # CF_DIB
        png_fmt = u32.RegisterClipboardFormatW("PNG")  # 오피스 등은 PNG 형식을 더 선명하게 받음
        if png_fmt:
            put(png_fmt, pix.tobytes("png"))
        return ok
    finally:
        u32.CloseClipboard()


# ───────────────────────── 인터넷 광고 받아오기 ─────────────────────────
def _http_get(url, limit, timeout=6):
    req = urllib.request.Request(url, headers={"User-Agent": f"smartpdfeditor/{APP_VER}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError("too large")
    return data


def fetch_ads():
    """smartgong.kr의 광고 설정(JSON)과 그림을 받아 반환. 백그라운드 스레드에서 실행.
    반환: {"interval": 초, "ads": [{"data": bytes, "link": str, "until": "YYYY-MM-DD"}]}  (광고 끔 → ads=[])"""
    conf = json.loads(_http_get(AD_URL, 200_000).decode("utf-8-sig"))
    out = {"interval": int(conf.get("interval", 30) or 30), "ads": []}
    if not conf.get("enabled", True):
        return out
    items = conf.get("ads") or ([conf] if conf.get("image") else [])
    for ad in items[:5]:
        if not isinstance(ad, dict) or not ad.get("image") or ad.get("enabled") is False:
            continue
        try:
            img = _http_get(urllib.parse.urljoin(AD_URL, ad["image"]), 3_000_000)
        except (OSError, ValueError):
            continue
        out["ads"].append({"data": img, "link": ad.get("link") or "", "until": ad.get("until") or ""})
    return out


def save_ad_cache(res):
    try:
        os.makedirs(AD_CACHE, exist_ok=True)
        for f in os.listdir(AD_CACHE):
            os.remove(os.path.join(AD_CACHE, f))
        meta = {"interval": res["interval"], "ads": []}
        for i, ad in enumerate(res["ads"]):
            fn = f"ad{i}.img"
            with open(os.path.join(AD_CACHE, fn), "wb") as f:
                f.write(ad["data"])
            meta["ads"].append({"file": fn, "link": ad["link"], "until": ad["until"]})
        with open(os.path.join(AD_CACHE, "ads.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
    except OSError:
        pass


def load_ad_cache():
    try:
        with open(os.path.join(AD_CACHE, "ads.json"), encoding="utf-8") as f:
            meta = json.load(f)
        ads = []
        for ad in meta.get("ads", []):
            with open(os.path.join(AD_CACHE, ad["file"]), "rb") as f:
                ads.append({"data": f.read(), "link": ad.get("link", ""), "until": ad.get("until", "")})
        return {"interval": meta.get("interval", 30), "ads": ads}
    except (OSError, ValueError, KeyError):
        return None


# ───────────────────────── 보기 방식 아이콘 (그림 파일 없이 직접 그림) ─────────────────────────
def make_view_icon(kind, fg="#444444", bg="#ffffff"):
    W, H = 26, 18
    img = tk.PhotoImage(width=W, height=H)

    def page(x0, y0, x1, y1):
        img.put(fg, to=(x0, y0, x1, y1))
        if x1 - x0 > 2 and y1 - y0 > 2:
            img.put(bg, to=(x0 + 1, y0 + 1, x1 - 1, y1 - 1))
            for yy in range(y0 + 3, y1 - 2, 3):   # 글줄 모양
                img.put("#9aa0a6", to=(x0 + 2, yy, x1 - 2, yy + 1))
    if kind == "single":
        page(8, 1, 19, 17)
    elif kind == "cont":
        page(8, 0, 19, 8)
        page(8, 10, 19, 18)
    else:
        n = {"cont2": 2, "cont3": 3, "cont4": 4}[kind]
        w = (W - 2 - (n - 1) * 2) // n
        x = (W - (n * w + (n - 1) * 2)) // 2
        for _ in range(n):
            page(x, 3, x + w, 16)
            x += w + 2
    return img


# ───────────────────────── 말풍선 도움말 ─────────────────────────
class Tooltip:
    def __init__(self, widget, text):
        self.w, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def show(self, e=None):
        if self.tip:
            return
        x = self.w.winfo_rootx() - 20
        y = self.w.winfo_rooty() + self.w.winfo_height() + 4
        self.tip = tk.Toplevel(self.w)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, bg="#ffffe0", relief="solid", bd=1, padx=6, pady=2,
                 font=("맑은 고딕", 9)).pack()

    def hide(self, e=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


# ───────────────────────── 탭 하나 = 문서 하나 ─────────────────────────
class DocTab:
    def __init__(self):
        self.doc = None
        self.path = None
        self.page_no = 0
        self.undo = []
        self._dirty = False
        self.items_cache = {}
        self.words_cache = {}
        self.annot_cache = {}
        self.mats = {}
        self.sizes = []
        self.slots = {}
        self.imgs = {}
        self._sizes_key = None
        self.frame = None        # 탭 막대의 탭 위젯

    @property
    def title(self):
        return os.path.basename(self.path) if self.path else "새 탭"


# ───────────────────────── 프로그램 하나만 실행 ─────────────────────────
def send_to_running(files):
    """이미 실행 중인 프로그램이 있으면 파일을 넘기고 True"""
    try:
        with socket.create_connection(("127.0.0.1", IPC_PORT), timeout=0.8) as c:
            c.sendall((json.dumps({"token": IPC_TOKEN, "files": files}) + "\n").encode("utf-8"))
            c.settimeout(2)
            return c.recv(8).startswith(b"OK")
    except OSError:
        return False


def start_ipc_server(q):
    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        srv.bind(("127.0.0.1", IPC_PORT))
        srv.listen(5)
    except OSError:
        return None

    def loop():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            try:
                conn.settimeout(3)
                buf = b""
                while not buf.endswith(b"\n") and len(buf) < 65536:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                msg = json.loads(buf.decode("utf-8"))
                if msg.get("token") == IPC_TOKEN:
                    q.put(list(msg.get("files", [])))
                    conn.sendall(b"OK")
            except (OSError, ValueError):
                pass
            finally:
                conn.close()
    threading.Thread(target=loop, daemon=True).start()
    return srv


def launch_new_window(paths=()):
    if getattr(sys, "frozen", False):
        args = [sys.executable]
    else:
        args = [sys.executable, os.path.abspath(__file__)]
    args += ["--new"] + [os.path.abspath(x) for x in paths]
    try:
        subprocess.Popen(args, close_fds=True)
    except OSError as ex:
        messagebox.showerror(APP, f"새 창을 열 수 없습니다:\n{ex}")


def open_folder(path):
    try:
        if sys.platform == "win32":
            if os.path.isfile(path):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            else:
                os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path if os.path.isdir(path) else os.path.dirname(path)])
    except Exception:
        pass


# ───────────────────────── 최근 본 파일 패널 ─────────────────────────
class RecentPanel(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 3))
        self.info = ttk.Label(bar, foreground="#666")
        self.info.pack(side="left")
        ttk.Button(bar, text="모두 지우기", command=app.clear_recent).pack(side="right")
        self.tv = ttk.Treeview(self, columns=("page", "time"), show="tree headings", selectmode="browse")
        self.tv.heading("#0", text="파일")
        self.tv.heading("page", text="쪽")
        self.tv.heading("time", text="열어본 때")
        self.tv.column("#0", width=120, stretch=True)
        self.tv.column("page", width=34, anchor="center", stretch=False)
        self.tv.column("time", width=78, anchor="center", stretch=False)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv.pack(fill="both", expand=True)
        self.tv.tag_configure("missing", foreground="#aaa")
        self.tv.bind("<Double-1>", self.activate)
        self.tv.bind("<Return>", self.activate)
        self.tv.bind("<Delete>", lambda e: self.remove())
        self.tv.bind("<Button-3>", self.popup)
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="열기 (새 탭)", command=self.activate)
        self.menu.add_command(label="새 창으로 열기", command=lambda: self.sel() and launch_new_window([self.sel()]))
        self.menu.add_command(label="즐겨찾기에 추가", command=self.add_fav)
        self.menu.add_command(label="파일 위치 열기", command=lambda: self.sel() and open_folder(self.sel()))
        self.menu.add_separator()
        self.menu.add_command(label="목록에서 지우기", command=self.remove)
        self.refresh()

    def refresh(self):
        self.tv.delete(*self.tv.get_children())
        conf = self.app.conf
        for p in conf["recent"]:
            t = conf.get("recent_time", {}).get(p, "")
            pg = conf["last_page"].get(p)
            self.tv.insert("", "end", iid=p, text="📄 " + os.path.basename(p),
                           values=("" if pg is None else pg + 1, t[5:] if len(t) > 5 else t),
                           tags=() if os.path.exists(p) else ("missing",))
        self.info.config(text=f"{len(conf['recent'])} / {self.app.limit('recent_max')}개")

    def sel(self):
        s = self.tv.selection()
        return s[0] if s else None

    def activate(self, e=None):
        p = self.sel()
        if p:
            self.app.open_path(p)
        return "break"

    def popup(self, e):
        iid = self.tv.identify_row(e.y)
        if iid:
            self.tv.selection_set(iid)
            self.menu.tk_popup(e.x_root, e.y_root)

    def add_fav(self):
        p = self.sel()
        if p and self.app.ensure_room("favorites"):
            self.app.conf["favorites"].append({"type": "file", "name": os.path.basename(p), "path": p,
                                               "added": time.time()})
            self.app.fav_panel.refresh()
            self.app.persist()
            self.app.status.set("즐겨찾기에 추가했습니다.")

    def remove(self):
        p = self.sel()
        if p and p in self.app.conf["recent"]:
            self.app.conf["recent"].remove(p)
            self.app.conf.get("recent_time", {}).pop(p, None)
            self.app.update_recent_menu()
            self.app.persist()


# ───────────────────────── 파일 검색 패널 ─────────────────────────
class SearchPanel(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        pr = app.conf["prefs"]
        self.folder = tk.StringVar(value=pr.get("search_folder") or os.path.expanduser("~"))
        self.query = tk.StringVar()
        self.sub = tk.BooleanVar(value=pr.get("search_sub", True))
        self.body = tk.BooleanVar(value=pr.get("search_body", False))
        self.info = tk.StringVar(value="폴더와 검색어를 넣고 Enter")
        self.running = False
        self.q = None
        self.map = {}
        self.dir_nodes = {}
        self.results = []      # [(path, [(page, snippet)])]
        self.words = []

        r1 = ttk.Frame(self)
        r1.pack(fill="x")
        ttk.Entry(r1, textvariable=self.folder).pack(side="left", fill="x", expand=True)
        ttk.Button(r1, text="…", width=3, command=self.pick_folder).pack(side="left", padx=(2, 0))
        r2 = ttk.Frame(self)
        r2.pack(fill="x", pady=3)
        qe = ttk.Entry(r2, textvariable=self.query)
        qe.pack(side="left", fill="x", expand=True)
        qe.bind("<Return>", lambda e: self.start())
        self.qe = qe
        self.btn = ttk.Button(r2, text="검색", width=5, command=self.toggle)
        self.btn.pack(side="left", padx=(2, 0))
        r3 = ttk.Frame(self)
        r3.pack(fill="x")
        ttk.Checkbutton(r3, text="하위 폴더", variable=self.sub).pack(side="left")
        ttk.Checkbutton(r3, text="PDF 본문도", variable=self.body).pack(side="left", padx=6)
        b = ttk.Button(r3, text="현재 폴더", command=self.use_current)
        b.pack(side="right")

        self.tv = ttk.Treeview(self, show="tree", selectmode="browse")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        bot = ttk.Frame(self)
        bot.pack(side="bottom", fill="x", pady=(3, 0))
        ttk.Label(bot, textvariable=self.info, foreground="#555").pack(side="left", fill="x", expand=True)
        mb = ttk.Menubutton(bot, text="목록 저장")
        m = tk.Menu(mb, tearoff=0)
        m.add_command(label="즐겨찾기 폴더로 저장", command=lambda: self.save_list("fav"))
        m.add_command(label="북마크 폴더로 저장 (찾은 쪽 포함)", command=lambda: self.save_list("bm"))
        m.add_command(label="목록 지우기", command=self.clear)
        mb["menu"] = m
        mb.pack(side="right")
        sb.pack(side="right", fill="y", pady=(4, 0))
        self.tv.pack(fill="both", expand=True, pady=(4, 0))
        self.tv.tag_configure("dir", foreground="#666")
        self.tv.tag_configure("hit", foreground="#1a5fb4")
        self.tv.bind("<Double-1>", self.activate)
        self.tv.bind("<Return>", self.activate)
        self.tv.bind("<Button-3>", self.popup)
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="열기 (새 탭)", command=lambda: self.activate())
        self.menu.add_command(label="새 창으로 열기", command=self.open_window)
        self.menu.add_command(label="즐겨찾기에 추가", command=self.add_fav)
        self.menu.add_command(label="파일 위치 열기", command=lambda: self.sel() and open_folder(self.sel()[0]))

    def pick_folder(self):
        d = filedialog.askdirectory(initialdir=self.folder.get() if os.path.isdir(self.folder.get()) else None)
        if d:
            self.folder.set(os.path.normpath(d))

    def use_current(self):
        if self.app.path:
            self.folder.set(os.path.dirname(self.app.path))

    def toggle(self):
        if self.running:
            self.running = False
        else:
            self.start()

    def clear(self):
        self.running = False
        self.tv.delete(*self.tv.get_children())
        self.map.clear()
        self.dir_nodes.clear()
        self.results = []
        self.info.set("")

    def start(self):
        folder = self.folder.get().strip()
        if not os.path.isdir(folder):
            messagebox.showwarning(APP, "검색할 폴더를 확인해주세요.", parent=self)
            return
        self.clear()
        self.words = self.query.get().lower().split()
        self.base = folder
        pr = self.app.conf["prefs"]
        pr.update(search_folder=folder, search_sub=self.sub.get(), search_body=self.body.get())
        self.running = True
        self.btn.config(text="중지")
        self.q = queue.Queue()
        self.scanned = 0
        sub = self.sub.get()
        run_flag = self

        def walk():
            try:
                for root, dirs, files in os.walk(folder):
                    if not run_flag.running:
                        break
                    dirs.sort()
                    for f in sorted(files):
                        if f.lower().endswith(".pdf"):
                            self.q.put(os.path.join(root, f))
                    if not sub:
                        dirs[:] = []
            finally:
                self.q.put(None)
        threading.Thread(target=walk, daemon=True).start()
        self.after(30, self.poll)

    def poll(self):
        """PDF 열기(PyMuPDF)는 화면과 같은 스레드에서 조금씩 처리"""
        if not self.running:
            self.finish("중지했습니다")
            return
        t0 = time.time()
        body = self.body.get()
        while time.time() - t0 < 0.06:
            try:
                path = self.q.get_nowait()
            except queue.Empty:
                break
            if path is None:
                self.finish("검색 완료")
                return
            self.scanned += 1
            name = os.path.basename(path).lower()
            if all(w in name for w in self.words):
                self.add(path, [])
            elif body and self.words:
                hits = self.search_body(path)
                if hits:
                    self.add(path, hits)
            if len(self.results) >= SEARCH_MAX:
                self.running = False
                self.finish(f"결과가 많아 {SEARCH_MAX}개에서 멈췄습니다")
                return
        self.info.set(f"검색 중… {self.scanned}개 확인 · {len(self.results)}개 찾음")
        self.after(10, self.poll)

    def search_body(self, path):
        hits = []
        try:
            with fitz.open(path) as d:
                if d.needs_pass:
                    return []
                for i in range(len(d)):
                    txt = d[i].get_text()
                    low = txt.lower()
                    if all(w in low for w in self.words):
                        k = low.find(self.words[0])
                        snip = " ".join(txt[max(0, k - 12):k + 40].split())
                        hits.append((i, snip))
                        if len(hits) >= 30:
                            break
        except Exception:
            return []
        return hits

    def finish(self, msg):
        self.running = False
        self.btn.config(text="검색")
        self.info.set(f"{msg} · {self.scanned}개 중 {len(self.results)}개")

    def add(self, path, hits):
        self.results.append((path, hits))
        d = os.path.dirname(path)
        if d not in self.dir_nodes:
            rel = os.path.relpath(d, self.base)
            label = os.path.basename(self.base) or self.base if rel == "." else rel
            self.dir_nodes[d] = self.tv.insert("", "end", text="📁 " + label, open=True, tags=("dir",))
            self.map[self.dir_nodes[d]] = (d, None)
        iid = self.tv.insert(self.dir_nodes[d], "end", text="📄 " + os.path.basename(path), open=False)
        self.map[iid] = (path, None)
        for pg, snip in hits:
            h = self.tv.insert(iid, "end", text=f"{pg + 1}쪽: {snip}", tags=("hit",))
            self.map[h] = (path, pg)
        if hits:
            self.tv.item(iid, text=f"📄 {os.path.basename(path)}  ({len(hits)})")

    def sel(self):
        s = self.tv.selection()
        return self.map.get(s[0]) if s else None

    def activate(self, e=None):
        v = self.sel()
        if not v:
            return
        path, pg = v
        if os.path.isdir(path):
            return
        self.app.open_file(path, pg)
        if pg is not None and self.words:
            self.app.status.set(f"{pg + 1}쪽에서 찾음: {' '.join(self.words)}")
        return "break"

    def popup(self, e):
        iid = self.tv.identify_row(e.y)
        if iid:
            self.tv.selection_set(iid)
            self.menu.tk_popup(e.x_root, e.y_root)

    def open_window(self):
        v = self.sel()
        if v and os.path.isfile(v[0]):
            launch_new_window([v[0]])

    def add_fav(self):
        v = self.sel()
        if v and os.path.isfile(v[0]) and self.app.ensure_room("favorites"):
            self.app.conf["favorites"].append({"type": "file", "name": os.path.basename(v[0]), "path": v[0],
                                               "added": time.time()})
            self.app.fav_panel.refresh()
            self.app.persist()
            self.app.status.set("즐겨찾기에 추가했습니다.")

    def save_list(self, kind):
        if not self.results:
            messagebox.showinfo(APP, "저장할 검색 결과가 없습니다.", parent=self)
            return
        key = "favorites" if kind == "fav" else "bookmarks"
        room = self.app.limit("fav_max" if kind == "fav" else "bm_max") - count_items(self.app.conf[key])
        need = len(self.results) if kind == "fav" else sum(max(1, len(h)) for _, h in self.results)
        if room <= 0:
            messagebox.showwarning(APP, f"{'즐겨찾기' if kind == 'fav' else '북마크'}가 이미 최대 개수입니다.\n"
                                        "[설정 → 환경설정]에서 개수를 늘리거나 항목을 지워주세요.", parent=self)
            return
        if need > room and not messagebox.askyesno(APP, f"최대 개수 때문에 {need}개 중 {room}개만 저장됩니다. 계속할까요?",
                                                   parent=self):
            return
        name = ask_text(self, "목록 저장", "폴더 이름", f"검색: {self.query.get().strip() or os.path.basename(self.base)}")
        if not name:
            return
        if kind == "fav":
            ch = [{"type": "file", "name": os.path.basename(p), "path": p, "added": time.time()}
                  for p, _ in self.results][:room]
            self.app.conf["favorites"].append({"type": "folder", "name": name, "open": True, "children": ch})
            self.app.fav_panel.refresh()
            self.app.side.select(self.app.fav_panel)
        else:
            ch = []
            for p, hits in self.results:
                base = os.path.splitext(os.path.basename(p))[0]
                if hits:
                    for pg, snip in hits:
                        ch.append({"type": "mark", "name": f"{base} - {pg + 1}쪽 {snip[:20]}", "path": p, "page": pg})
                else:
                    ch.append({"type": "mark", "name": f"{base} - 1쪽", "path": p, "page": 0})
            self.app.conf["bookmarks"].append({"type": "folder", "name": name, "open": True, "children": ch[:room]})
            self.app.bm_panel.refresh()
            self.app.side.select(self.app.bm_panel)
        self.app.persist()


# ───────────────────────── 앱 ─────────────────────────
class App:
    def __init__(self, root, files=(), listen=True):
        self.root = root
        self.tabs = []
        self.tab = DocTab()      # 열린 파일이 없을 때의 빈 탭
        self.ipc_q = queue.Queue()
        self.ipc_srv = start_ipc_server(self.ipc_q) if listen else None
        root.title(APP)
        self.conf = load_conf()
        pr = self.conf["prefs"]
        try:
            root.geometry(pr.get("geometry", "1280x860"))
        except tk.TclError:
            root.geometry("1200x820")
        self.doc = None
        self.path = None
        self.page_no = 0
        self.zoom = float(pr.get("zoom", 1.3))
        self.items_cache = {}    # 쪽번호 → 편집 대상 (줄 또는 조각)
        self.annot_cache = {}    # 쪽번호 → [(rect, 종류, 내용)]
        self.mats = {}           # 쪽번호 → (회전행렬, 역회전행렬)
        self.sizes = []          # 쪽별 (폭, 높이) pt, 회전 반영
        self.slots = {}          # 쪽번호 → (x, y, w, h) 화면 위치
        self.imgs = {}           # 쪽번호 → PhotoImage (보이는 쪽만)
        self.view = pr.get("view", "cont") if pr.get("view") in VIEW_COLS else "cont"
        self.view_var = tk.StringVar(value=VIEW_LABEL[self.view])
        self.fit = tk.StringVar(value=pr.get("fit", "width"))   # custom / width / height
        self._vis_job = None
        self._cfg_job = None
        self._sizes_key = None
        self._last_size = (0, 0)
        self._sync_page = True
        self.undo = []
        self.dirty = False
        self.img = None
        self.unit = tk.StringVar(value=pr.get("unit", "line"))
        self.autofit = tk.BooleanVar(value=pr.get("autofit", True))
        self.panel_on = tk.BooleanVar(value=pr.get("panel", True))
        self.mode = tk.StringVar(value="edit")
        self.mark_color = pr.get("mark_color", "#ffe600")
        self.hide_fill = tk.StringVar(value=pr.get("hide_fill", "검정"))
        self.press = None
        self.dragging = False
        self.shape_kind = tk.StringVar(value=pr.get("shape_kind", "사각형"))
        self.shape_color = pr.get("shape_color", "#e53935")
        self.shape_width = tk.DoubleVar(value=pr.get("shape_width", 2.0))
        self.shape_fill = tk.StringVar(value=pr.get("shape_fill", "없음"))
        self.ext_open = tk.StringVar(value=pr.get("external_open", "tab"))
        self.cap_dpi = tk.StringVar(value=str(pr.get("cap_dpi", 200)))
        self.cap_preview = tk.BooleanVar(value=pr.get("cap_preview", True))
        self.app_mode = tk.StringVar(value=pr.get("start_mode", pr.get("app_mode", "view")))      # view / edit
        self.wheel_page = tk.BooleanVar(value=pr.get("wheel_page", False))  # 휠 한 칸 = 한 쪽
        self.panning = False
        self._wheel_t = 0
        self.sel = None          # 선택한 글자 {"page", "text", "rects", "y"}
        self.selecting = None

        self._build_ui()
        for f in files:
            self.open_file(f)
        self.on_mode(quiet=True)
        self.set_app_mode()
        self.root.after(200, self.poll_ipc)

    # ---------- UI ----------
    def _build_menu(self):
        mb = tk.Menu(self.root)

        fm = tk.Menu(mb, tearoff=0)
        fm.add_command(label="열기 (새 탭)...", accelerator="Ctrl+O", command=self.ask_open)
        fm.add_command(label="새 창으로 열기...", accelerator="Ctrl+Shift+O", command=self.ask_open_window)
        fm.add_command(label="새 창", accelerator="Ctrl+N", command=lambda: launch_new_window())
        self.recent_menu = tk.Menu(fm, tearoff=0)
        fm.add_cascade(label="최근 본 파일", menu=self.recent_menu)
        fm.add_separator()
        fm.add_command(label="저장...", accelerator="Ctrl+S", command=self.save)
        fm.add_command(label="원하는 쪽만 저장...", accelerator="Ctrl+E", command=self.extract_dialog)
        fm.add_separator()
        fm.add_command(label="탭 닫기", accelerator="Ctrl+W", command=lambda: self.close_tab(self.tab))
        fm.add_command(label="종료", command=self.on_close)
        mb.add_cascade(label="파일", menu=fm)

        em = tk.Menu(mb, tearoff=0)
        em.add_command(label="되돌리기", accelerator="Ctrl+Z", command=self.do_undo)
        em.add_command(label="찾아 바꾸기...", accelerator="Ctrl+F", command=self.find_replace)
        em.add_separator()
        em.add_command(label="글자 수정 단위", state="disabled")
        em.add_radiobutton(label="    줄 단위", value="line", variable=self.unit, command=self.reload_items)
        em.add_radiobutton(label="    조각 단위", value="span", variable=self.unit, command=self.reload_items)
        em.add_checkbutton(label="새 글자가 길면 글자 크기 줄이기", variable=self.autofit)
        mb.add_cascade(label="편집", menu=em)

        vm = tk.Menu(mb, tearoff=0)
        vm.add_radiobutton(label="뷰어 모드 (보기 전용)", value="view", variable=self.app_mode, accelerator="F4",
                           command=self.set_app_mode)
        vm.add_radiobutton(label="편집 모드", value="edit", variable=self.app_mode, accelerator="F4",
                           command=self.set_app_mode)
        vm.add_separator()
        for k, t, _ in VIEWS:
            vm.add_radiobutton(label=t, value=t, variable=self.view_var, command=self.on_view)
        vm.add_separator()
        vm.add_radiobutton(label="가로맞춤 (폭에 맞춤)", value="width", variable=self.fit, accelerator="Ctrl+1",
                           command=self.on_fit)
        vm.add_radiobutton(label="세로맞춤 (한 쪽 전체)", value="height", variable=self.fit, accelerator="Ctrl+2",
                           command=self.on_fit)
        vm.add_radiobutton(label="직접 배율", value="custom", variable=self.fit, command=self.on_fit)
        vm.add_command(label="확대", accelerator="Ctrl++", command=lambda: self.set_zoom(self.zoom * 1.2))
        vm.add_command(label="축소", accelerator="Ctrl+-", command=lambda: self.set_zoom(self.zoom / 1.2))
        vm.add_command(label="실제 크기 100%", accelerator="Ctrl+0", command=lambda: self.set_zoom(1.0))
        vm.add_separator()
        vm.add_checkbutton(label="마우스 휠 한 칸에 한 쪽씩 넘기기", variable=self.wheel_page,
                           command=lambda: self.conf["prefs"].update(wheel_page=self.wheel_page.get()))
        vm.add_checkbutton(label="옆 패널 보이기", accelerator="F9", variable=self.panel_on, command=self.apply_panel)
        mb.add_cascade(label="보기", menu=vm)

        tm = tk.Menu(mb, tearoff=0)
        for k, t in TOOLS:
            tm.add_radiobutton(label=t, value=k, variable=self.mode, command=self.on_mode,
                               accelerator={"edit": "Esc", "capture": "Ctrl+Shift+C"}.get(k, ""))
        tm.add_separator()
        cm = tk.Menu(tm, tearoff=0)
        for name, c in (("노랑", "#ffe600"), ("초록", "#7cf27c"), ("파랑", "#7fd3ff"), ("분홍", "#ff9ecb")):
            cm.add_command(label=name, command=lambda c=c: self.set_color(c))
        cm.add_command(label="다른 색...", command=self.pick_color)
        tm.add_cascade(label="색칠 색", menu=cm)
        hm = tk.Menu(tm, tearoff=0)
        for v in ("검정", "흰색"):
            hm.add_radiobutton(label=v, value=v, variable=self.hide_fill)
        tm.add_cascade(label="감추기 색", menu=hm)
        sm_ = tk.Menu(tm, tearoff=0)
        for k in SHAPES:
            sm_.add_radiobutton(label=k, value=k, variable=self.shape_kind, command=lambda: self.pick_tool("shape"))
        sm_.add_separator()
        sm_.add_command(label="채우기", state="disabled")
        for v in ("없음", "반투명", "채움"):
            sm_.add_radiobutton(label="    " + v, value=v, variable=self.shape_fill)
        sm_.add_separator()
        sm_.add_command(label="두께", state="disabled")
        for v in (1.0, 2.0, 3.0, 5.0, 8.0):
            sm_.add_radiobutton(label=f"    {v:g} pt", value=v, variable=self.shape_width)
        sm_.add_separator()
        sm_.add_command(label="선 색 고르기...", command=self.pick_shape_color)
        tm.add_cascade(label="도형", menu=sm_)
        km = tk.Menu(tm, tearoff=0)
        km.add_command(label="해상도", state="disabled")
        for v in ("96", "150", "200", "300", "600"):
            km.add_radiobutton(label=f"    {v} dpi", value=v, variable=self.cap_dpi)
        km.add_separator()
        km.add_checkbutton(label="캡쳐 후 미리보기 창 띄우기", variable=self.cap_preview)
        tm.add_cascade(label="캡쳐", menu=km)
        mb.add_cascade(label="도구", menu=tm)

        pm = tk.Menu(mb, tearoff=0)
        pm.add_command(label="이전 쪽", accelerator="PgUp", command=lambda: self.go(-1))
        pm.add_command(label="다음 쪽", accelerator="PgDn", command=lambda: self.go(1))
        pm.add_command(label="첫 쪽", accelerator="Home", command=lambda: self.goto(0))
        pm.add_command(label="마지막 쪽", accelerator="End",
                       command=lambda: self.doc and self.goto(len(self.doc) - 1))
        pm.add_command(label="쪽 번호로 이동", accelerator="Ctrl+G", command=self.focus_page)
        pm.add_separator()
        pm.add_command(label="이 쪽 오른쪽으로 회전", accelerator="Ctrl+R", command=lambda: self.rotate_pages([self.page_no], 90))
        pm.add_command(label="이 쪽 왼쪽으로 회전", accelerator="Ctrl+L", command=lambda: self.rotate_pages([self.page_no], -90))
        pm.add_command(label="여러 쪽 회전...", command=self.rotate_dialog)
        pm.add_separator()
        pm.add_command(label="원하는 쪽만 저장...", accelerator="Ctrl+E", command=self.extract_dialog)
        mb.add_cascade(label="페이지", menu=pm)

        bm = tk.Menu(mb, tearoff=0)
        bm.add_command(label="즐겨찾기에 추가", accelerator="Ctrl+D", command=self.add_favorite_now)
        bm.add_command(label="지금 쪽 북마크", accelerator="Ctrl+B", command=self.add_bookmark_now)
        bm.add_separator()
        bm.add_command(label="즐겨찾기 보기", command=lambda: self.show_side(self.fav_panel))
        bm.add_command(label="북마크 보기", command=lambda: self.show_side(self.bm_panel))
        bm.add_command(label="최근 본 파일 보기", command=lambda: self.show_side(self.recent_panel))
        bm.add_command(label="파일 검색", accelerator="Ctrl+Shift+F", command=self.focus_search)
        mb.add_cascade(label="즐겨찾기", menu=bm)

        sm = tk.Menu(mb, tearoff=0)
        sm.add_command(label="환경설정...", command=self.settings_dialog)
        sm.add_separator()
        sm.add_command(label="탐색기에서 PDF를 열면:", state="disabled")
        sm.add_radiobutton(label="    이 창의 새 탭으로 열기", value="tab", variable=self.ext_open, command=self.on_ext_open)
        sm.add_radiobutton(label="    새 창(프로그램)으로 열기", value="window", variable=self.ext_open, command=self.on_ext_open)
        sm.add_separator()
        sm.add_command(label="설정 내보내기...", command=self.export_conf)
        sm.add_command(label="설정 가져오기...", command=self.import_conf)
        sm.add_command(label="설정 폴더 열기", command=self.open_conf_dir)
        mb.add_cascade(label="설정", menu=sm)

        hm2 = tk.Menu(mb, tearoff=0)
        hm2.add_command(label="사용방법", accelerator="F1", command=self.show_help)
        hm2.add_command(label="smartgong.kr 바로가기", command=lambda: webbrowser.open(HOME_URL))
        hm2.add_command(label="새 버전 내려받기", command=lambda: webbrowser.open(RELEASES_URL))
        hm2.add_separator()
        hm2.add_command(label="정보 · 라이선스", command=self.show_about)
        mb.add_cascade(label="도움말", menu=hm2)
        self.root.config(menu=mb)

    def _build_ui(self):
        self._build_menu()
        bar = ttk.Frame(self.root, padding=(4, 3))
        bar.pack(fill="x")

        def btn(text, cmd, tip, width=None):
            b_ = ttk.Button(bar, text=text, command=cmd, width=width)
            b_.pack(side="left", padx=1)
            Tooltip(b_, tip)
            return b_

        def sep():
            ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=5)

        btn("열기", self.ask_open, "열기 (Ctrl+O)", 5)
        btn("저장", self.save, "저장 (Ctrl+S)", 5)
        btn("↶", self.do_undo, "되돌리기 (Ctrl+Z)", 3)
        sep()
        btn("◀", lambda: self.go(-1), "이전 쪽 (PgUp)", 3)
        self.page_var = tk.StringVar(value="0 / 0")
        e = ttk.Entry(bar, textvariable=self.page_var, width=9, justify="center")
        self._page_entry = e
        e.pack(side="left", padx=1)
        e.bind("<Return>", self.jump)
        btn("▶", lambda: self.go(1), "다음 쪽 (PgDn)", 3)
        sep()
        btn("－", lambda: self.set_zoom(self.zoom / 1.2), "축소 (Ctrl+-)", 3)
        self.zoom_lbl = ttk.Label(bar, text=f"{round(self.zoom * 100)}%", width=5, anchor="center")
        self.zoom_lbl.pack(side="left")
        btn("＋", lambda: self.set_zoom(self.zoom * 1.2), "확대 (Ctrl++)", 3)
        sep()
        btn("⟲", lambda: self.rotate_pages([self.page_no], -90), "이 쪽 왼쪽으로 회전 (Ctrl+L)", 3)
        btn("⟳", lambda: self.rotate_pages([self.page_no], 90), "이 쪽 오른쪽으로 회전 (Ctrl+R)", 3)
        btn("회전…", self.rotate_dialog, "여러 쪽 한꺼번에 회전", 5)

        # 편집 모드에서만 보이는 도구 버튼 + 도구별 옵션
        self.toolarea = ttk.Frame(bar)
        self.toolarea.pack(side="left", padx=(6, 0))
        self.toolbtns = ttk.Frame(self.toolarea)
        short = {"edit": "✎수정", "mark": "🖍색칠", "hide": "■감추기", "shape": "◻도형", "memo": "💬메모",
                 "erase": "⌫지우개", "capture": "✂캡쳐"}
        tips = {"edit": "글자 수정 — 글자를 클릭 (Esc)", "mark": "색칠 — 글자 클릭 또는 영역 끌기",
                "hide": "감추기 — 아래 내용을 지우고 덮기", "shape": "도형 — 사각형·원·선·화살표 (Shift: 정사각형·정원)",
                "memo": "메모 붙이기", "erase": "색칠·도형·메모 지우기", "capture": "영역 캡쳐 → 클립보드 (Ctrl+Shift+C)"}
        for k, _ in TOOLS:
            rb = ttk.Radiobutton(self.toolbtns, text=short[k], value=k, variable=self.mode, style="Toolbutton",
                                 command=self.on_mode)
            rb.pack(side="left", padx=0)
            Tooltip(rb, tips[k])
        self.optbox = ttk.Frame(self.toolarea)
        self.opt = {k: ttk.Frame(self.optbox) for k, _ in TOOLS}

        f = self.opt["mark"]
        self.swatch = tk.Label(f, width=2, bg=self.mark_color, relief="groove", cursor="hand2")
        self.swatch.pack(side="left", padx=(4, 2))
        self.swatch.bind("<Button-1>", lambda e: self.pick_color())
        Tooltip(self.swatch, "색 고르기")
        for c in ("#ffe600", "#7cf27c", "#7fd3ff", "#ff9ecb"):
            b_ = tk.Label(f, width=1, bg=c, relief="ridge", cursor="hand2")
            b_.pack(side="left", padx=1)
            b_.bind("<Button-1>", lambda e, c=c: self.set_color(c))

        f = self.opt["shape"]
        ttk.Combobox(f, textvariable=self.shape_kind, values=SHAPES, width=5, state="readonly").pack(side="left", padx=(4, 2))
        self.shape_swatch = tk.Label(f, width=2, bg=self.shape_color, relief="groove", cursor="hand2")
        self.shape_swatch.pack(side="left", padx=2)
        self.shape_swatch.bind("<Button-1>", lambda e: self.pick_shape_color())
        Tooltip(self.shape_swatch, "선 색 고르기")
        for c in ("#e53935", "#1e88e5", "#000000"):
            b_ = tk.Label(f, width=1, bg=c, relief="ridge", cursor="hand2")
            b_.pack(side="left", padx=1)
            b_.bind("<Button-1>", lambda e, c=c: self.set_shape_color(c))
        sp = ttk.Spinbox(f, from_=0.5, to=20, increment=0.5, textvariable=self.shape_width, width=3)
        sp.pack(side="left", padx=2)
        Tooltip(sp, "선 두께(pt) · 채우기는 [도구 → 도형]")

        # 아래 상태줄: 왼쪽 안내 글 / 오른쪽 맞춤·보기 방식 아이콘
        self.status = tk.StringVar(value="PDF를 열어주세요 (Ctrl+O).")
        sbar = ttk.Frame(self.root, padding=(4, 1))
        sbar.pack(side="bottom", fill="x")
        self.view_icons = {}
        for k, t, _ in reversed(VIEWS):
            self.view_icons[k] = make_view_icon(k)
            rb = ttk.Radiobutton(sbar, image=self.view_icons[k], value=t, variable=self.view_var,
                                 style="Toolbutton", command=self.on_view)
            rb.pack(side="right", padx=1)
            Tooltip(rb, t)
        ttk.Separator(sbar, orient="vertical").pack(side="right", fill="y", padx=6)
        for val, txt, tip in (("height", "↕", "세로맞춤 — 한 쪽 전체 (Ctrl+2)"), ("width", "↔", "가로맞춤 — 폭에 맞춤 (Ctrl+1)")):
            rb = ttk.Radiobutton(sbar, text=txt, value=val, variable=self.fit, style="Toolbutton", width=3,
                                 command=self.on_fit)
            rb.pack(side="right", padx=1)
            Tooltip(rb, tip)
        ttk.Label(sbar, textvariable=self.status, anchor="w").pack(side="left", fill="x", expand=True)

        # 우측: 로고(→ smartgong.kr) · 사용방법 · 뷰어/편집 모드
        try:
            self.logo_img = tk.PhotoImage(data="".join(LOGO_PNG))
            logo = tk.Label(bar, image=self.logo_img, cursor="hand2", bd=0)
        except tk.TclError:
            logo = tk.Label(bar, text="스마트공", fg="#2e7d32", font=("맑은 고딕", 12, "bold"), cursor="hand2")
        logo.pack(side="right", padx=(4, 2))
        logo.bind("<Button-1>", lambda e: webbrowser.open(HOME_URL))
        Tooltip(logo, "smartgong.kr 바로가기")
        hl = tk.Label(bar, text="사용방법", fg="#1565c0", cursor="hand2", font=("맑은 고딕", 9, "underline"))
        hl.pack(side="right", padx=(6, 4))
        hl.bind("<Button-1>", lambda e: self.show_help())
        for val, txt, tip in (("edit", "✎ 편집", "편집 모드: 글자 수정·색칠·도형 등 (F4)"),
                              ("view", "👁 뷰어", "뷰어 모드: 보기 전용, 끌어서 이동 (F4)")):
            rb = ttk.Radiobutton(bar, text=txt, value=val, variable=self.app_mode, style="Toolbutton",
                                 command=self.set_app_mode)
            rb.pack(side="right", padx=1)
            Tooltip(rb, tip)

        self.pw = ttk.PanedWindow(self.root, orient="horizontal")
        self.pw.pack(fill="both", expand=True)
        self.side_box = ttk.Frame(self.pw)
        self.side = ttk.Notebook(self.side_box, width=AD_W)
        self.fav_panel = TreePanel(self.side, self.conf["favorites"], self.new_favorite, self.open_favorite,
                                   lambda n: "📄 " + n.get("name", ""), self.persist, "＋ 현재 파일")
        self.bm_panel = TreePanel(self.side, self.conf["bookmarks"], self.new_bookmark, self.open_bookmark,
                                  lambda n: f"🔖 {n.get('name', '')}", self.persist, "＋ 현재 쪽")
        self.side.add(self.fav_panel, text="즐겨찾기")
        self.side.add(self.bm_panel, text="북마크")
        self.recent_panel = RecentPanel(self.side, self)
        self.side.add(self.recent_panel, text="최근")
        self.search_panel = SearchPanel(self.side, self)
        self.side.add(self.search_panel, text="검색")
        # 사이드바 하단 광고창: 광고가 있으면 250×250, 없으면 최소화
        self.ad_frame = tk.Frame(self.side_box, width=AD_W, height=AD_H, bg="#f3f3f3",
                                 highlightthickness=1, highlightbackground="#d6d6d6")
        self.ad_frame.pack(side="bottom", fill="x", pady=(4, 0))
        self.ad_frame.pack_propagate(False)
        self.ad_label = tk.Label(self.ad_frame, bg="#f3f3f3", bd=0)
        self.ad_label.pack(fill="both", expand=True)
        self.side.pack(side="top", fill="both", expand=True)
        self.ad_link = None
        self.load_ad()
        self.update_recent_menu()
        wrap = ttk.Frame(self.pw)
        self.pw.add(self.side_box, weight=0)
        self.pw.add(wrap, weight=1)
        if not self.panel_on.get():
            self.pw.forget(self.side_box)
        self.tabbar = ttk.Notebook(wrap)
        self.tabbar.pack(side="top", fill="x")
        self.tabbar.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        self.tabbar.bind("<Button-2>", self.on_tab_middle)
        self.tabbar.bind("<Button-3>", self.on_tab_menu)
        self.tab_menu = tk.Menu(self.root, tearoff=0)
        self.tab_menu.add_command(label="탭 닫기", command=lambda: self.close_tab(self._menu_tab))
        self.tab_menu.add_command(label="다른 탭 모두 닫기", command=lambda: self.close_others(self._menu_tab))
        self.tab_menu.add_separator()
        self.tab_menu.add_command(label="이 탭을 새 창으로 옮기기", command=lambda: self.move_to_window(self._menu_tab))
        self.tab_menu.add_command(label="파일 위치 열기",
                                  command=lambda: self._menu_tab.path and open_folder(self._menu_tab.path))
        self._menu_tab = None
        self.cv = tk.Canvas(wrap, bg="#5a5a5a", highlightthickness=0, yscrollincrement=20, xscrollincrement=20)
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.cv.yview)
        hs = ttk.Scrollbar(wrap, orient="horizontal", command=self.cv.xview)
        self.vs = vs

        def ys(a, b):
            vs.set(a, b)
            self.schedule_visible()

        def xs(a, b):
            hs.set(a, b)
            self.schedule_visible()
        self.cv.configure(yscrollcommand=ys, xscrollcommand=xs)
        vs.pack(side="right", fill="y")
        hs.pack(side="bottom", fill="x")
        self.cv.pack(fill="both", expand=True)


        self.cv.bind("<Motion>", self.on_move)
        self.cv.bind("<ButtonPress-2>", self.pan_start)
        self.cv.bind("<B2-Motion>", self.pan_move)
        self.cv.bind("<ButtonRelease-2>", self.pan_end)
        self.cv.bind("<Button-3>", self.on_context)
        self.root.bind("<Control-c>", self.copy_selection)
        self.cv.bind("<ButtonPress-1>", self.on_press)
        self.cv.bind("<B1-Motion>", self.on_drag)
        self.cv.bind("<ButtonRelease-1>", self.on_release)
        # 휠: 마우스가 올라간 곳을 스크롤 (Windows는 휠 신호가 '선택된 칸'으로 가서 화면이 안 넘어가던 문제)
        self.root.bind_all("<MouseWheel>", self.route_wheel)
        self.cv.bind("<Enter>", self.on_canvas_enter)
        self.cv.bind("<Button-4>", lambda e: self.wheel_step(-1, e))
        self.cv.bind("<Button-5>", lambda e: self.wheel_step(1, e))
        self.cv.bind("<Configure>", self.on_configure)
        r = self.root
        r.bind("<Control-o>", lambda e: self.ask_open())
        r.bind("<Control-O>", lambda e: self.ask_open_window())
        r.bind("<Control-n>", lambda e: launch_new_window())
        r.bind("<Control-w>", lambda e: self.close_tab(self.tab))
        r.bind("<Control-Tab>", lambda e: self.next_tab(1))
        r.bind("<Control-Shift-Tab>", lambda e: self.next_tab(-1))
        r.bind("<Control-F>", lambda e: self.focus_search())
        r.bind("<Control-C>", lambda e: self.pick_tool("edit" if self.mode.get() == "capture" else "capture"))
        r.bind("<Control-g>", lambda e: self.focus_page())
        r.bind("<F4>", lambda e: (self.app_mode.set("edit" if self.app_mode.get() == "view" else "view"),
                                  self.set_app_mode()))
        r.bind("<Control-s>", lambda e: self.save())
        r.bind("<Control-z>", lambda e: self.do_undo())
        r.bind("<Control-f>", lambda e: self.find_replace())
        def nav(f):   # 글자 입력칸에서는 Home/End/PgUp/PgDn을 쪽 이동에 쓰지 않음
            return lambda e: None if isinstance(e.widget, (tk.Entry, ttk.Entry, tk.Text, tk.Spinbox)) else f()
        r.bind("<Prior>", nav(lambda: self.go(-1)))
        r.bind("<Next>", nav(lambda: self.go(1)))
        r.bind("<Home>", nav(lambda: self.goto(0)))
        r.bind("<End>", nav(lambda: self.goto(len(self.doc) - 1) if self.doc else None))
        r.bind("<Control-Key-1>", lambda e: (self.fit.set("width"), self.on_fit()))
        r.bind("<Control-Key-2>", lambda e: (self.fit.set("height"), self.on_fit()))
        r.bind("<Control-Key-0>", lambda e: self.set_zoom(1.0))
        r.bind("<Control-plus>", lambda e: self.set_zoom(self.zoom * 1.2))
        r.bind("<Control-equal>", lambda e: self.set_zoom(self.zoom * 1.2))
        r.bind("<Control-minus>", lambda e: self.set_zoom(self.zoom / 1.2))
        r.bind("<Control-r>", lambda e: self.rotate_pages([self.page_no], 90))
        r.bind("<Control-l>", lambda e: self.rotate_pages([self.page_no], -90))
        r.bind("<Control-e>", lambda e: self.extract_dialog())
        r.bind("<Escape>", lambda e: self.app_mode.get() == "edit" and self.pick_tool("edit"))
        r.bind("<Control-d>", lambda e: self.add_favorite_now())
        r.bind("<Control-b>", lambda e: self.add_bookmark_now())
        r.bind("<F1>", lambda e: self.show_help())
        r.bind("<F9>", lambda e: (self.panel_on.set(not self.panel_on.get()), self.apply_panel()))
        r.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------- 파일 ----------
    def ask_open(self):
        ps = filedialog.askopenfilenames(filetypes=[("PDF", "*.pdf"), ("모든 파일", "*.*")])
        for p in ps:
            self.open_file(p)

    def ask_open_window(self):
        ps = filedialog.askopenfilenames(filetypes=[("PDF", "*.pdf"), ("모든 파일", "*.*")])
        if ps:
            launch_new_window(ps)

    def open_file(self, p, page=None):
        p = os.path.abspath(p)
        for t in self.tabs:   # 이미 열린 파일이면 그 탭으로
            if t.path and os.path.normcase(t.path) == os.path.normcase(p):
                self.switch_tab(t)
                if page is not None:
                    self.goto(page)
                return True
        try:
            doc = fitz.open(p)
            if doc.needs_pass:
                messagebox.showerror(APP, "암호가 걸린 PDF는 열 수 없습니다.")
                return False
        except Exception as ex:
            messagebox.showerror(APP, f"열 수 없습니다:\n{ex}")
            return False
        if page is None:
            page = self.conf["last_page"].get(p, 0)
        t = DocTab()
        t.doc, t.path = doc, p
        t.page_no = page if 0 <= page < len(doc) else 0
        t.frame = ttk.Frame(self.tabbar, height=1)
        self.tabs.append(t)
        self.tabbar.add(t.frame, text=" " + t.title + " ")
        self.add_recent(p)
        self.update_recent_menu()
        self.persist()
        self.switch_tab(t)
        return True

    # ---------- 광고창 · 사용방법 ----------
    def load_ad(self):
        """광고 순서: ① 실행파일 옆 ad.png (시험용)  ② smartgong.kr 인터넷 광고  ③ 마지막으로 받은 광고
        광고가 없으면 광고창 최소화"""
        self.ad_list, self.ad_idx, self.ad_job = [], 0, None
        path = next((os.path.join(APP_DIR, n) for n in AD_FILES if os.path.exists(os.path.join(APP_DIR, n))), None)
        if path:
            link = None
            try:
                with open(os.path.join(APP_DIR, AD_LINK_FILE), encoding="utf-8-sig") as f:
                    link = f.readline().strip() or None
            except OSError:
                pass
            try:
                with open(path, "rb") as f:
                    self.apply_ads({"interval": 30, "ads": [{"data": f.read(), "link": link or "", "until": ""}]})
            except OSError:
                self.set_ad(None)
            return
        cached = load_ad_cache()
        self.apply_ads(cached) if cached else self.set_ad(None)
        self.refresh_ads()

    def refresh_ads(self):
        q = queue.Queue()

        def work():
            try:
                q.put(("ok", fetch_ads()))
            except Exception:
                q.put(("fail", None))
        threading.Thread(target=work, daemon=True).start()

        def check():
            try:
                kind, res = q.get_nowait()
            except queue.Empty:
                self.root.after(500, check)
                return
            if kind == "ok":
                save_ad_cache(res)
                self.apply_ads(res)
            self.root.after(AD_REFRESH_MS, self.refresh_ads)
        self.root.after(500, check)

    def apply_ads(self, res):
        """받은 광고를 250×250에 맞춰 준비하고, 여러 개면 돌아가며 보여줌"""
        today = datetime.date.today().isoformat()
        prepared = []
        for ad in res.get("ads", []):
            if ad.get("until") and ad["until"] < today:      # 기간 지난 광고는 제외
                continue
            try:
                pix = fitz.Pixmap(ad["data"])
                if pix.alpha:
                    pix = fitz.Pixmap(pix, 0)
                k = min(AD_W / pix.width, AD_H / pix.height)
                if abs(k - 1) > 0.01:
                    pix = fitz.Pixmap(pix, max(1, int(pix.width * k)), max(1, int(pix.height * k)), None)
                prepared.append((pix.tobytes("png"), ad.get("link") or None))
            except Exception:
                continue
        if self.ad_job:
            self.root.after_cancel(self.ad_job)
            self.ad_job = None
        self.ad_list, self.ad_idx = prepared, 0
        self.ad_interval = max(5, int(res.get("interval", 30) or 30)) * 1000
        self.rotate_ad()

    def rotate_ad(self):
        self.ad_job = None
        if not self.ad_list:
            self.set_ad(None)
            return
        data, link = self.ad_list[self.ad_idx % len(self.ad_list)]
        self.set_ad(data, link)
        if len(self.ad_list) > 1:
            self.ad_idx += 1
            self.ad_job = self.root.after(self.ad_interval, self.rotate_ad)

    def set_ad(self, png_bytes=None, link=None):
        """광고 넣기/빼기. png_bytes=None 이면 광고 없음 → 최소화"""
        self.ad_link = link
        if png_bytes:
            self.ad_img = tk.PhotoImage(data=base64.b64encode(png_bytes))
            self.ad_label.config(image=self.ad_img, cursor="hand2" if link else "")
            self.ad_frame.config(height=AD_H, highlightthickness=1)
            self.ad_label.bind("<Button-1>", lambda e: self.ad_link and webbrowser.open(self.ad_link))
        else:
            self.ad_img = None
            self.ad_label.config(image="", cursor="")
            self.ad_label.unbind("<Button-1>")
            self.ad_frame.config(height=1, highlightthickness=0)   # 빈 광고창은 최소화

    def show_about(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("정보")
        dlg.transient(self.root)
        dlg.resizable(False, False)
        frm = ttk.Frame(dlg, padding=18)
        frm.pack()
        if getattr(self, "logo_img", None):
            tk.Label(frm, image=self.logo_img, bd=0).pack()
        ttk.Label(frm, text=APP, font=("맑은 고딕", 14, "bold")).pack(pady=(8, 0))
        try:
            mu = f"PyMuPDF {fitz.VersionBind} · MuPDF {fitz.VersionFitz}"
        except AttributeError:
            mu = "PyMuPDF"
        ttk.Label(frm, text=f"버전 {APP_VER}   ({mu})", foreground="#666").pack(pady=(2, 10))
        msg = ("이 프로그램은 GNU AGPL-3.0 라이선스의 자유 소프트웨어입니다.\n"
               "누구나 소스 코드를 받아 보고, 고치고, 다시 배포할 수 있으며\n"
               "다시 배포할 때에는 같은 라이선스로 소스를 공개해야 합니다.\n"
               "이 프로그램은 어떠한 보증도 없이 제공됩니다.\n\n"
               "PDF 처리에 PyMuPDF / MuPDF (AGPL-3.0, © Artifex Software, Inc.)를 사용합니다.\n"
               "'스마트공' 이름과 로고는 smartgong.kr의 것입니다.")
        ttk.Label(frm, text=msg, justify="center").pack()
        links = ttk.Frame(frm)
        links.pack(pady=(12, 0))
        for text, url in (("소스 코드", SOURCE_URL), ("새 버전", RELEASES_URL), ("라이선스 전문", SOURCE_URL + "/blob/main/LICENSE"),
                          ("smartgong.kr", HOME_URL)):
            l_ = tk.Label(links, text=text, fg="#1565c0", cursor="hand2", font=("맑은 고딕", 9, "underline"))
            l_.pack(side="left", padx=6)
            l_.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
        ttk.Button(frm, text="닫기", command=dlg.destroy).pack(pady=(14, 0))
        dlg.bind("<Escape>", lambda e: dlg.destroy())

    def show_help(self):
        if getattr(self, "_help", None) and self._help.winfo_exists():
            self._help.lift()
            return
        dlg = self._help = tk.Toplevel(self.root)
        dlg.title(f"{APP} 사용방법")
        dlg.transient(self.root)
        dlg.geometry("600x620")
        frm = ttk.Frame(dlg, padding=10)
        frm.pack(fill="both", expand=True)
        bot = ttk.Frame(frm)
        bot.pack(side="bottom", fill="x", pady=(8, 0))
        link = tk.Label(bot, text="smartgong.kr 바로가기", fg="#1565c0", cursor="hand2",
                        font=("맑은 고딕", 9, "underline"))
        link.pack(side="left")
        link.bind("<Button-1>", lambda e: webbrowser.open(HOME_URL))
        ttk.Button(bot, text="닫기", command=dlg.destroy).pack(side="right")
        txt = tk.Text(frm, wrap="word", font=("맑은 고딕", 10), relief="flat", bg="#fbfbfb",
                      padx=12, pady=10, spacing1=2, spacing3=2, cursor="arrow")
        sb = ttk.Scrollbar(frm, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(fill="both", expand=True)
        txt.tag_configure("h1", font=("맑은 고딕", 15, "bold"), foreground="#2e7d32", spacing3=6)
        txt.tag_configure("h2", font=("맑은 고딕", 11, "bold"), foreground="#1565c0", spacing1=10)
        txt.tag_configure("foot", foreground="#777", spacing1=14)
        for text, tag in HELP_TEXT:
            txt.insert("end", text + ("\n" if tag else ""), tag)
        txt.config(state="disabled")
        dlg.bind("<Escape>", lambda e: dlg.destroy())

    # ---------- 탭 ----------
    def switch_tab(self, t):
        self.sel = None
        if t is not self.tab:
            self.remember_page()
            self.cv.delete("all")
            self.imgs.clear()
        self.tab = t
        if t.frame is not None and self.tabbar.select() != str(t.frame):
            self.tabbar.select(t.frame)
        self.root.title(f"{t.title} - {APP}" if t.doc else APP)
        if t.doc:
            self.render(goto=t.page_no)
            self.reload_items()
        else:
            self.page_var.set("0 / 0")
            self.cv.configure(scrollregion=(0, 0, 0, 0))

    def on_tab_changed(self, e=None):
        sel = self.tabbar.select()
        for t in self.tabs:
            if str(t.frame) == sel:
                if t is not self.tab:
                    self.switch_tab(t)
                return

    def tab_at(self, e):
        try:
            i = self.tabbar.index(f"@{e.x},{e.y}")
        except tk.TclError:
            return None
        return self.tabs[i] if 0 <= i < len(self.tabs) else None

    def on_tab_middle(self, e):
        t = self.tab_at(e)
        if t:
            self.close_tab(t)

    def on_tab_menu(self, e):
        t = self.tab_at(e)
        if t:
            self._menu_tab = t
            self.tab_menu.tk_popup(e.x_root, e.y_root)

    def next_tab(self, step):
        if len(self.tabs) > 1 and self.tab in self.tabs:
            i = (self.tabs.index(self.tab) + step) % len(self.tabs)
            self.switch_tab(self.tabs[i])
        return "break"

    def update_tab_title(self, t):
        if t.frame is not None and t in self.tabs:
            self.tabbar.tab(t.frame, text=(" ● " if t._dirty else " ") + t.title + " ")

    def ask_save_tab(self, t):
        """닫기 전 확인. 계속해도 되면 True"""
        if not t._dirty:
            return True
        if t is not self.tab:
            self.switch_tab(t)
        ans = messagebox.askyesnocancel(APP, f"'{t.title}'의 수정 내용을 저장할까요?")
        if ans is None:
            return False
        if ans:
            return self.save()
        return True

    def close_tab(self, t):
        if t is None or t not in self.tabs:
            return
        if not self.ask_save_tab(t):
            return
        self.remember_page(t)
        i = self.tabs.index(t)
        self.tabs.remove(t)
        self.tabbar.forget(t.frame)
        try:
            t.doc.close()
        except Exception:
            pass
        if t is self.tab:
            self.tab = DocTab()
            if self.tabs:
                self.switch_tab(self.tabs[min(i, len(self.tabs) - 1)])
            else:
                self.cv.delete("all")
                self.switch_tab(self.tab)
                self.status.set("파일을 열어주세요 (Ctrl+O).")
        self.persist()

    def close_others(self, keep):
        for t in [x for x in self.tabs if x is not keep]:
            self.close_tab(t)

    def move_to_window(self, t):
        if not t or not t.path:
            return
        if t._dirty and not messagebox.askyesno(APP, "저장하지 않은 수정 내용은 새 창으로 옮겨지지 않습니다.\n"
                                                     "먼저 저장하려면 '아니요'를 누르세요.\n\n수정 내용을 버리고 옮길까요?"):
            return
        t._dirty = False
        path = t.path
        self.close_tab(t)
        launch_new_window([path])

    def on_ext_open(self):
        self.conf["prefs"]["external_open"] = self.ext_open.get()
        self.persist()

    def poll_ipc(self):
        """다른 실행에서 넘어온 파일을 새 탭으로"""
        try:
            while True:
                files = self.ipc_q.get_nowait()
                for f in files:
                    if os.path.exists(f):
                        self.open_file(f)
                self.bring_to_front()
        except queue.Empty:
            pass
        self.root.after(250, self.poll_ipc)

    def bring_to_front(self):
        r = self.root
        if r.state() == "iconic":
            r.deiconify()
        r.lift()
        r.attributes("-topmost", True)
        r.after(300, lambda: r.attributes("-topmost", False))
        r.focus_force()

    def focus_search(self):
        if not self.panel_on.get():
            self.panel_on.set(True)
            self.apply_panel()
        self.side.select(self.search_panel)
        self.search_panel.qe.focus_set()

    def save(self):
        if not self.doc:
            return False
        base, ext = os.path.splitext(self.path)
        p = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=os.path.basename(base) + "_수정.pdf",
                                         initialdir=os.path.dirname(self.path), filetypes=[("PDF", "*.pdf")])
        if not p:
            return False
        p = os.path.abspath(p)
        try:
            if os.path.abspath(p) == os.path.abspath(self.path):
                data = self.doc.tobytes(garbage=3, deflate=True)
                self.doc.close()
                with open(p, "wb") as f:
                    f.write(data)
                self.doc = fitz.open(p)
            else:
                self.doc.save(p, garbage=3, deflate=True)
                self.path = p          # 탭은 새로 저장한 파일을 가리킴
                self.root.title(f"{self.tab.title} - {APP}")
            self.dirty = False
            self.status.set(f"저장했습니다: {p}")
            return True
        except Exception as ex:
            messagebox.showerror(APP, f"저장 실패:\n{ex}")
            return False

    def on_close(self):
        for t in list(self.tabs):
            if not self.ask_save_tab(t):
                return
        for t in self.tabs:
            self.remember_page(t)
        pr = self.conf["prefs"]
        pr.update(zoom=round(self.zoom, 3), unit=self.unit.get(), autofit=self.autofit.get(),
                  panel=self.panel_on.get(), geometry=self.root.geometry(),
                  mark_color=self.mark_color, hide_fill=self.hide_fill.get(),
                  view=self.view, fit=self.fit.get(), shape_kind=self.shape_kind.get(),
                  shape_color=self.shape_color, shape_fill=self.shape_fill.get(),
                  external_open=self.ext_open.get(), search_sub=self.search_panel.sub.get(),
                  search_body=self.search_panel.body.get(), cap_preview=self.cap_preview.get(),
                  wheel_page=self.wheel_page.get(), app_mode=pr.get("start_mode", self.app_mode.get()))
        try:
            pr["cap_dpi"] = int(float(self.cap_dpi.get()))
        except ValueError:
            pass
        try:
            pr["shape_width"] = float(self.shape_width.get())
        except (tk.TclError, ValueError):
            pass
        save_conf(self.conf)
        if self.ipc_srv:
            try:
                self.ipc_srv.close()
            except OSError:
                pass
        self.root.destroy()

    # ---------- 설정·즐겨찾기·북마크 ----------
    def persist(self):
        save_conf(self.conf)

    def remember_page(self, t=None):
        t = t or self.tab
        if t.doc and t.path:
            lp = self.conf["last_page"]
            lp.pop(t.path, None)
            lp[t.path] = t.page_no
            while len(lp) > LASTPAGE_MAX:
                lp.pop(next(iter(lp)))

    def limit(self, key):
        try:
            return max(1, int(self.conf["prefs"].get(key, LIMIT_DEFAULTS[key])))
        except (TypeError, ValueError):
            return LIMIT_DEFAULTS[key]

    def add_recent(self, p):
        rec = [x for x in self.conf["recent"] if x != p]
        n = self.limit("recent_max")
        self.conf["recent"] = ([p] + rec)[:n]
        times = self.conf.setdefault("recent_time", {})
        times[p] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        for k in [k for k in times if k not in self.conf["recent"]]:
            del times[k]
        self.update_recent_menu()
        self.persist()

    def update_recent_menu(self):
        m = self.recent_menu
        m.delete(0, "end")
        if not self.conf["recent"]:
            m.add_command(label="(없음)", state="disabled")
        else:
            for i, p in enumerate(self.conf["recent"][:20]):
                m.add_command(label=f"{i + 1}. {os.path.basename(p)}   —  {os.path.dirname(p)}",
                              command=lambda p=p: self.open_path(p))
            m.add_separator()
            m.add_command(label="최근 본 파일 목록 보기", command=lambda: self.show_side(self.recent_panel))
            m.add_command(label="목록 지우기", command=self.clear_recent)
        if hasattr(self, "recent_panel"):
            self.recent_panel.refresh()

    def clear_recent(self):
        if self.conf["recent"] and not messagebox.askyesno(APP, "최근 본 파일 목록을 모두 지울까요?"):
            return
        self.conf["recent"] = []
        self.conf["recent_time"] = {}
        self.update_recent_menu()
        self.persist()

    def ensure_room(self, key):
        """즐겨찾기/북마크 최대 개수 확인. 꽉 찼으면 가장 오래된 항목을 지울지 물어봄"""
        lim = self.limit("fav_max" if key == "favorites" else "bm_max")
        items = list(iter_items(self.conf[key]))
        if len(items) < lim:
            return True
        name = "즐겨찾기" if key == "favorites" else "북마크"
        oldest, cont = min(items, key=lambda x: x[0].get("added", 0))
        if not messagebox.askyesno(APP, f"{name}는 최대 {lim}개까지 저장됩니다.\n\n"
                                        f"가장 오래된 '{oldest.get('name')}'을(를) 지우고 추가할까요?\n"
                                        "(최대 개수는 [설정 → 환경설정]에서 바꿀 수 있습니다)"):
            return False
        remove_node(cont, oldest)
        (self.fav_panel if key == "favorites" else self.bm_panel).refresh()
        return True

    def settings_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("환경설정")
        dlg.transient(self.root)
        dlg.resizable(False, False)
        frm = ttk.Frame(dlg, padding=14)
        frm.pack()
        vars_ = {}
        rows = (("fav_max", "즐겨찾기 최대 개수", 1000), ("bm_max", "북마크 최대 개수", 2000),
                ("recent_max", "최근 본 파일 개수", 200))
        ttk.Label(frm, text="저장 개수", font=("맑은 고딕", 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))
        for i, (k, label, mx) in enumerate(rows, 1):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=2)
            v = tk.IntVar(value=self.limit(k))
            ttk.Spinbox(frm, from_=1, to=mx, textvariable=v, width=7).grid(row=i, column=1, sticky="w", padx=8)
            cur = len(self.conf["recent"]) if k == "recent_max" else \
                count_items(self.conf["favorites" if k == "fav_max" else "bookmarks"])
            ttk.Label(frm, text=f"(지금 {cur}개)", foreground="#777").grid(row=i, column=2, sticky="w")
            vars_[k] = v
        ttk.Separator(frm).grid(row=5, column=0, columnspan=3, sticky="ew", pady=10)
        ttk.Label(frm, text="보기", font=("맑은 고딕", 10, "bold")).grid(row=6, column=0, sticky="w", pady=(0, 6))
        ttk.Checkbutton(frm, text="마우스 휠 한 칸에 한 쪽씩 넘기기", variable=self.wheel_page).grid(
            row=7, column=0, columnspan=3, sticky="w")
        start = tk.StringVar(value=self.app_mode.get())
        sf = ttk.Frame(frm)
        sf.grid(row=8, column=0, columnspan=3, sticky="w", pady=(4, 0))
        ttk.Label(sf, text="시작할 때:").pack(side="left")
        ttk.Radiobutton(sf, text="뷰어 모드", value="view", variable=start).pack(side="left", padx=6)
        ttk.Radiobutton(sf, text="편집 모드", value="edit", variable=start).pack(side="left")
        ef = ttk.Frame(frm)
        ef.grid(row=9, column=0, columnspan=3, sticky="w", pady=(4, 0))
        ttk.Label(ef, text="탐색기에서 PDF를 열면:").pack(side="left")
        ttk.Radiobutton(ef, text="새 탭", value="tab", variable=self.ext_open).pack(side="left", padx=6)
        ttk.Radiobutton(ef, text="새 창", value="window", variable=self.ext_open).pack(side="left")

        def ok():
            pr = self.conf["prefs"]
            try:
                for k, v in vars_.items():
                    pr[k] = max(1, int(v.get()))
            except (tk.TclError, ValueError):
                messagebox.showwarning(APP, "개수는 숫자로 입력해주세요.", parent=dlg)
                return
            n = pr["recent_max"]
            if len(self.conf["recent"]) > n:
                self.conf["recent"] = self.conf["recent"][:n]
            pr["wheel_page"] = self.wheel_page.get()
            pr["start_mode"] = start.get()
            pr["app_mode"] = start.get()
            self.on_ext_open()
            self.update_recent_menu()
            self.persist()
            dlg.destroy()
            over = [lbl for k, lbl, _ in rows[:2]
                    if count_items(self.conf["favorites" if k == "fav_max" else "bookmarks"]) > pr[k]]
            self.status.set("설정을 저장했습니다." + (f" ({', '.join(over)}보다 이미 많은 항목은 그대로 두고, "
                                                    "새로 추가할 때부터 적용합니다)" if over else ""))
        b = ttk.Frame(frm)
        b.grid(row=10, column=0, columnspan=3, sticky="e", pady=(14, 0))
        ttk.Button(b, text="취소", command=dlg.destroy).pack(side="right")
        ttk.Button(b, text="저장", command=ok).pack(side="right", padx=4)
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        dlg.grab_set()

    def show_side(self, panel):
        if not self.panel_on.get():
            self.panel_on.set(True)
            self.apply_panel()
        self.side.select(panel)

    def focus_page(self):
        self._page_entry.focus_set()
        self._page_entry.select_range(0, "end")

    def open_path(self, p, page=None):
        if not os.path.exists(p):
            messagebox.showwarning(APP, f"파일을 찾을 수 없습니다:\n{p}")
            return False
        return self.open_file(p, page)

    def apply_panel(self):
        if self.panel_on.get():
            if str(self.side_box) not in [str(x) for x in self.pw.panes()]:
                self.pw.insert(0, self.side_box, weight=0)
        elif str(self.side_box) in [str(x) for x in self.pw.panes()]:
            self.pw.forget(self.side_box)
        self.conf["prefs"]["panel"] = self.panel_on.get()
        self.persist()

    def new_favorite(self):
        if not self.ensure_room("favorites"):
            return None
        if not self.path:
            p = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf"), ("모든 파일", "*.*")])
            if not p:
                return None
            p = os.path.abspath(p)
        else:
            p = self.path
        return {"type": "file", "name": os.path.basename(p), "path": p, "added": time.time()}

    def open_favorite(self, node):
        self.open_path(node["path"])

    def new_bookmark(self):
        if not self.doc:
            messagebox.showinfo(APP, "먼저 PDF를 열어주세요.")
            return None
        if not self.ensure_room("bookmarks"):
            return None
        page, pos = self.page_no, None
        if self.sel and self.sel["text"].strip():   # 선택한 글자가 있으면 그 글자를 이름으로, 그 위치로
            default = " ".join(self.sel["text"].split())[:60]
            page, pos = self.sel["page"], round(self.sel["y"], 4)
        else:
            default = f"{os.path.splitext(os.path.basename(self.path))[0]} - {self.page_no + 1}쪽"
        name = ask_text(self.root, "북마크 추가", f"북마크 이름  ({page + 1}쪽)", default)
        if not name:
            return None
        node = {"type": "mark", "name": name, "path": self.path, "page": page, "added": time.time()}
        if pos:
            node["pos"] = pos
        return node

    def open_bookmark(self, node):
        pg = int(node.get("page", 0))
        if self.open_path(node["path"], pg) and node.get("pos"):
            self.root.update_idletasks()
            self.goto(pg, float(node["pos"]))

    def add_favorite_now(self):
        self.side.select(self.fav_panel)
        if not self.panel_on.get():
            self.panel_on.set(True); self.apply_panel()
        self.fav_panel.add()

    def add_bookmark_now(self):
        self.side.select(self.bm_panel)
        if not self.panel_on.get():
            self.panel_on.set(True); self.apply_panel()
        self.bm_panel.add()

    def export_conf(self):
        self.remember_page()
        p = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("설정 파일", "*.json")],
                                         initialfile=f"smartpdfeditor_설정_{datetime.date.today():%Y%m%d}.json")
        if not p:
            return
        try:
            out = dict(self.conf)
            out["exported"] = datetime.datetime.now().isoformat(timespec="seconds")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=1)
            self.status.set(f"설정을 내보냈습니다: {p}")
        except OSError as ex:
            messagebox.showerror(APP, f"내보내기 실패:\n{ex}")

    def import_conf(self):
        p = filedialog.askopenfilename(filetypes=[("설정 파일", "*.json")])
        if not p:
            return
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or not ({"favorites", "bookmarks"} & set(data)):
                raise ValueError("이 프로그램의 설정 파일이 아닙니다.")
        except (OSError, ValueError) as ex:
            messagebox.showerror(APP, f"가져오기 실패:\n{ex}")
            return
        ans = messagebox.askyesnocancel(APP, "가져온 설정을 어떻게 적용할까요?\n\n"
                                             "예: 지금 설정에 합치기 (가져온 항목은 '가져온 항목' 폴더에)\n"
                                             "아니요: 지금 설정을 지우고 덮어쓰기")
        if ans is None:
            return
        favs, bms = data.get("favorites", []), data.get("bookmarks", [])
        if ans:
            tag = f"가져온 항목 {datetime.date.today():%m-%d}"
            known = {n.get("path") for n in self.conf["favorites"] if n.get("type") == "file"}
            favs = [n for n in favs if n.get("type") == "folder" or n.get("path") not in known]
            if favs:
                self.conf["favorites"].append({"type": "folder", "name": tag, "open": True, "children": favs})
            if bms:
                self.conf["bookmarks"].append({"type": "folder", "name": tag, "open": True, "children": bms})
            self.conf["recent"] = (self.conf["recent"] + [x for x in data.get("recent", [])
                                                          if x not in self.conf["recent"]])[:self.limit("recent_max")]
            for k, v in data.get("last_page", {}).items():
                self.conf["last_page"].setdefault(k, v)
        else:
            self.conf["favorites"][:] = favs
            self.conf["bookmarks"][:] = bms
            self.conf["recent"] = data.get("recent", [])[:self.limit("recent_max")]
            self.conf["last_page"] = dict(data.get("last_page", {}))
            pr = data.get("prefs", {})
            if pr:
                self.unit.set(pr.get("unit", self.unit.get()))
                self.autofit.set(pr.get("autofit", self.autofit.get()))
                self.zoom = float(pr.get("zoom", self.zoom))
                if pr.get("view") in VIEW_COLS:
                    self.view = pr["view"]
                    self.view_var.set(VIEW_LABEL[self.view])
                if pr.get("fit") in ("custom", "width", "height"):
                    self.fit.set(pr["fit"])
                self.render(goto=self.page_no)
        self.fav_panel.data = self.conf["favorites"]
        self.bm_panel.data = self.conf["bookmarks"]
        self.fav_panel.refresh()
        self.bm_panel.refresh()
        self.update_recent_menu()
        self.persist()
        self.status.set("설정을 가져왔습니다.")

    def open_conf_dir(self):
        os.makedirs(CONF_DIR, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(CONF_DIR)
            else:
                subprocess.Popen(["xdg-open", CONF_DIR])
        except Exception:
            messagebox.showinfo(APP, CONF_DIR)

    # ---------- 화면 ----------
    # ---------- 화면 배치 ----------
    def cols(self):
        return VIEW_COLS[self.view]

    def page_list(self):
        if not self.doc:
            return []
        return [self.page_no] if self.view == "single" else list(range(len(self.doc)))

    def calc_zoom(self):
        fit = self.fit.get()
        if fit == "custom" or not self.doc:
            return self.zoom
        self.cv.update_idletasks()
        cw = max(100, self.cv.winfo_width())
        ch = max(100, self.cv.winfo_height())
        pages = self.page_list()
        cols = self.cols()
        if fit == "width":
            maxw = max(self.sizes[i][0] for i in pages)
            sb = 0 if self.view == "single" else 4
            z = (cw - 2 * MARGIN - (cols - 1) * GAP - sb) / (cols * maxw)
        else:
            maxh = max(self.sizes[i][1] for i in pages)
            z = (ch - 2 * MARGIN) / maxh
            # 여러 쪽이 가로로 넘치면 폭에도 맞춤
            if cols > 1:
                maxw = max(self.sizes[i][0] for i in pages)
                z = min(z, (cw - 2 * MARGIN - (cols - 1) * GAP) / (cols * maxw))
        return max(0.1, min(8.0, z))

    def layout(self):
        """쪽 위치 계산 (줄마다 가운데 정렬)"""
        self.slots = {}
        pages = self.page_list()
        cols = self.cols()
        z = self.zoom
        cw = max(100, self.cv.winfo_width())
        rows = [pages[i:i + cols] for i in range(0, len(pages), cols)]
        widths = [sum(self.sizes[p][0] * z for p in r) + GAP * (len(r) - 1) for r in rows]
        total_w = max([cw] + [w + 2 * MARGIN for w in widths])
        y = MARGIN
        for r, rw in zip(rows, widths):
            x = (total_w - rw) / 2
            rh = max(self.sizes[p][1] * z for p in r)
            for p in r:
                w, h = self.sizes[p][0] * z, self.sizes[p][1] * z
                self.slots[p] = (round(x), round(y), round(w), round(h))
                x += w + GAP
            y += rh + GAP
        total_h = y - GAP + MARGIN
        return total_w, total_h

    def render(self, goto=None):
        """전체 다시 그리기. goto: 이 쪽으로 이동 / None: 지금 스크롤 위치 유지"""
        self.cv.delete("all")
        self.imgs.clear()
        self.items_cache.clear()
        self.words_cache.clear()
        self.annot_cache.clear()
        self.mats.clear()
        if not self.doc:
            return
        yfrac, xfrac = self.cv.yview()[0], self.cv.xview()[0]
        self.page_no = min(self.page_no, len(self.doc) - 1)
        key = (id(self.doc), len(self.doc))
        if self._sizes_key != key:   # 쪽 크기는 파일이 바뀌거나 회전했을 때만 다시 계산
            self.sizes = [(r.width, r.height) for r in (self.doc[i].rect for i in range(len(self.doc)))]
            self._sizes_key = key
        self.zoom = self.calc_zoom()
        tw, th = self.layout()
        self.cv.configure(scrollregion=(0, 0, tw, th))
        for p, (x, y, w, h) in self.slots.items():
            self.cv.create_rectangle(x + 3, y + 3, x + w + 3, y + h + 3, fill="#3c3c3c", outline="", tags="bg")
            self.cv.create_rectangle(x, y, x + w, y + h, fill="white", outline="#888", tags="bg")
            self.cv.create_text(x + w / 2, y + h / 2, text=str(p + 1), fill="#bbb",
                                font=("맑은 고딕", max(8, min(40, int(h / 12)))), tags="bg")
        self.zoom_lbl.config(text=f"{round(self.zoom * 100)}%")
        if goto is not None:
            self._sync_page = False
            self.scroll_to(goto)
            self.page_no = goto
        else:
            self.cv.yview_moveto(yfrac)
            self.cv.xview_moveto(xfrac)
        self.update_page_label()
        self.update_visible()
        self.draw_selection()
        self._sync_page = True

    def scroll_to(self, p, frac=None):
        """p쪽으로 이동. frac: 쪽 안의 세로 위치(0~1, 회전 반영 전 좌표 기준)"""
        if p not in self.slots:
            return
        x, y, w, h = self.slots[p]
        sr = self.cv.cget("scrollregion").split()
        th = float(sr[3]) if len(sr) == 4 else 1
        top = y - MARGIN
        if frac:
            top = y + h * frac - self.cv.winfo_height() * 0.25
        self.cv.yview_moveto(max(0, top / th))

    def schedule_visible(self):
        if self._vis_job is None:
            self._vis_job = self.root.after(15, self.update_visible)

    def update_visible(self):
        """화면에 보이는 쪽만 그려 메모리·속도 절약"""
        self._vis_job = None
        if not self.doc or not self.slots:
            return
        ch = self.cv.winfo_height()
        top = self.cv.canvasy(0)
        bot = top + ch
        pad = ch * 0.6
        want = [p for p, (x, y, w, h) in self.slots.items() if y + h >= top - pad and y <= bot + pad]
        for p in list(self.imgs):
            if p not in want:
                self.cv.delete(f"img{p}")
                del self.imgs[p]
        for p in want:
            if p in self.imgs:
                continue
            x, y, w, h = self.slots[p]
            try:
                pix = self.doc[p].get_pixmap(matrix=fitz.Matrix(self.zoom, self.zoom), alpha=False)
                img = tk.PhotoImage(data=base64.b64encode(pix.tobytes("png")))
            except Exception:
                continue
            self.imgs[p] = img
            self.cv.create_image(x, y, image=img, anchor="nw", tags=("page", f"img{p}"))
        for tag in ("tsel", "hl"):
            if self.cv.find_withtag(tag):
                self.cv.tag_raise(tag)
        # 현재 쪽 = 화면 위쪽 1/3 지점에 걸친 쪽
        if self._sync_page and self.view != "single":
            mid = top + ch / 3
            best = None
            for p, (x, y, w, h) in self.slots.items():
                if y <= mid <= y + h + GAP:
                    best = p if best is None else min(best, p)
            if best is None and want:
                best = min(want)
            if best is not None and best != self.page_no:
                self.page_no = best
                self.update_page_label()

    def update_page_label(self):
        if self.doc:
            if self.root.focus_get() is not getattr(self, "_page_entry", None):
                self.page_var.set(f"{self.page_no + 1} / {len(self.doc)}")

    def on_configure(self, e):
        size = (e.width, e.height)
        if size == self._last_size:
            return
        self._last_size = size
        if self._cfg_job:
            self.root.after_cancel(self._cfg_job)
        self._cfg_job = self.root.after(150, self._relayout_keep_page)

    def _relayout_keep_page(self):
        self._cfg_job = None
        if self.doc:
            self.render(goto=self.page_no)

    def on_view(self):
        self.view = VIEW_KEY.get(self.view_var.get(), "cont")
        self.render(goto=self.page_no)
        self.conf["prefs"]["view"] = self.view

    def on_fit(self):
        self.render(goto=self.page_no)

    # ---------- 쪽 정보 (필요할 때 계산해서 저장) ----------
    def mat(self, p):
        if p not in self.mats:
            pg = self.doc[p]
            self.mats[p] = (pg.rotation_matrix, pg.derotation_matrix)
        return self.mats[p]

    def reload_items(self):
        """편집 단위가 바뀌면 다시 계산"""
        self.items_cache.clear()
        self.annot_cache.clear()
        if self.doc:
            n = len(self.items_for(self.page_no))
            self.status.set(f"{self.page_no + 1}쪽: {n}개 편집 대상 · 글자를 클릭하면 수정합니다." if n
                            else "이 쪽에서 글자를 찾지 못했습니다 (스캔 이미지 PDF일 수 있습니다).")

    def annots_for(self, p):
        if p not in self.annot_cache:
            page = self.doc[p]
            lst = []
            with unrotated(page):
                for a in page.annots() or []:
                    lst.append((fitz.Rect(a.rect), a.type[0], a.info.get("content", "")))
            self.annot_cache[p] = lst
        return self.annot_cache[p]

    def items_for(self, p):
        if p in self.items_cache:
            return self.items_cache[p]
        items = []
        page = self.doc[p]
        with unrotated(page):
            d = page.get_text("dict")
        for b in d.get("blocks", []):
            if b.get("type") != 0:
                continue
            for ln in b["lines"]:
                spans = [s for s in ln["spans"] if s["text"].strip()]
                if not spans:
                    continue
                if ln.get("dir", (1, 0)) != (1, 0) and abs(ln["dir"][1]) > 0.01:
                    continue  # 세로/회전 글자는 제외
                groups = [spans] if self.unit.get() == "line" else [[s] for s in spans]
                for g in groups:
                    rect = fitz.Rect(g[0]["bbox"])
                    for s_ in g[1:]:
                        rect |= fitz.Rect(s_["bbox"])
                    first = g[0]
                    items.append({
                        "rect": rect,
                        "text": first["text"] if len(g) == 1 else self._join_spans(g),
                        "size": first["size"],
                        "color": first["color"],
                        "bold": bool(first["flags"] & 16) or "bold" in first["font"].lower(),
                        "origin": fitz.Point(first["origin"]),
                        "font": first["font"],
                    })
        self.items_cache[p] = items
        return items

    @staticmethod
    def _join_spans(g):
        out = g[0]["text"]
        for prev, s in zip(g, g[1:]):
            gap = s["bbox"][0] - prev["bbox"][2]
            if gap > s["size"] * 0.25 and not out.endswith(" ") and not s["text"].startswith(" "):
                out += " "
            out += s["text"]
        return out

    # ---------- 좌표 변환 ----------
    def page_at(self, cx, cy):
        for p, (x, y, w, h) in self.slots.items():
            if x <= cx <= x + w and y <= cy <= y + h:
                return p
        return None

    def canvas_to_page(self, p, cx, cy):
        """화면 좌표 → p쪽의 회전 0 기준 PDF 좌표"""
        x, y, w, h = self.slots[p]
        return fitz.Point((cx - x) / self.zoom, (cy - y) / self.zoom) * self.mat(p)[1]

    def locate(self, e):
        cx, cy = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        p = self.page_at(cx, cy)
        if p is None:
            return None, None
        return p, self.canvas_to_page(p, cx, cy)

    def page_to_canvas_rect(self, p, r):
        x, y, w, h = self.slots[p]
        r = fitz.Rect(r) * self.mat(p)[0]
        z = self.zoom
        return x + r.x0 * z, y + r.y0 * z, x + r.x1 * z, y + r.y1 * z

    def hit_pt(self, p, pt):
        for it in self.items_for(p):
            if pt in it["rect"]:
                return it
        return None

    def annot_at(self, p, pt):
        found = None
        for rect, typ, content in self.annots_for(p):
            if pt in rect:
                found = (rect, typ, content)
        return found

    def pick_tool(self, tool):
        self.mode.set(tool)
        self.on_mode()

    def set_app_mode(self):
        m = self.app_mode.get()
        self.conf["prefs"]["app_mode"] = m
        self.cv.delete("hl")
        if m == "view":
            self.toolbtns.pack_forget()
            self.optbox.pack_forget()
            self.status.set("뷰어 모드: 끌어서 글자 선택 (Ctrl+C 복사 · Ctrl+B 북마크) · 휠 버튼으로 끌면 화면 이동 · "
                            "고치려면 [✎ 편집] (F4)")
        else:
            self.clear_selection()
            self.toolbtns.pack(side="left")
            self.optbox.pack(side="left")
            self.on_mode()

    def on_mode(self, quiet=False):
        if not quiet and self.app_mode.get() != "edit":   # 도구를 고르면 편집 모드로
            self.app_mode.set("edit")
            self.set_app_mode()
            return
        tips = {"edit": "글자를 클릭하면 수정합니다.",
                "mark": "글자를 클릭하거나 영역을 끌어서 색칠합니다.",
                "hide": "글자를 클릭하거나 영역을 끌어서 감춥니다. (아래 내용은 실제로 지워집니다)",
                "shape": "끌어서 도형을 그립니다. (Shift: 정사각형·정원·45° 선)",
                "capture": "캡쳐할 영역을 끌어서 선택하세요. 클릭하면 쪽 전체를 캡쳐합니다. (Ctrl+Shift+C)",
                "memo": "메모를 붙일 곳을 클릭하세요. 기존 메모를 클릭하면 수정/삭제합니다.",
                "erase": "지울 색칠·도형·메모를 클릭하세요."}
        m = self.mode.get()
        if not quiet:
            self.status.set(tips[m])
        self.cv.delete("hl")
        for k, f in self.opt.items():
            if k == m:
                f.pack(side="left")
            else:
                f.pack_forget()

    def on_move(self, e):
        self.cv.delete("hl")
        if not self.doc:
            return
        p, pt = self.locate(e)
        if p is None:
            self.cv.configure(cursor="")
            return
        mode = self.mode.get()
        an = self.annot_at(p, pt)
        if an and an[1] == fitz.PDF_ANNOT_TEXT and an[2]:
            self.status.set("💬 " + an[2].replace("\n", " ")[:120])
        if self.app_mode.get() == "view":   # 뷰어 모드: 편집칸 표시 없음, 글자 위에서는 글자 선택 커서
            if self.panning:
                self.cv.configure(cursor="fleur")
            else:
                self.cv.configure(cursor="xterm" if self.hit_pt(p, pt) else "arrow")
            return
        if mode == "erase":
            if an:
                x0, y0, x1, y1 = self.page_to_canvas_rect(p, an[0])
                self.cv.create_rectangle(x0 - 1, y0 - 1, x1 + 1, y1 + 1, outline="#e0002a", width=2, dash=(4, 2), tags="hl")
            self.cv.configure(cursor="X_cursor" if an else "")
            return
        if mode in ("memo", "shape", "capture"):
            self.cv.configure(cursor="pencil" if mode == "memo" else "crosshair")
            return
        it = self.hit_pt(p, pt)
        if it:
            x0, y0, x1, y1 = self.page_to_canvas_rect(p, it["rect"])
            color = {"edit": "#ff7a00", "mark": self.mark_color, "hide": "#333"}[mode]
            self.cv.create_rectangle(x0 - 1, y0 - 1, x1 + 1, y1 + 1, outline=color, width=2, tags="hl")
        self.cv.configure(cursor=("xterm" if it else "") if mode == "edit" else "crosshair")

    def on_press(self, e):
        self.cv.focus_set()
        if self.app_mode.get() == "view":   # 뷰어 모드: 쪽 위에서 끌면 글자 선택, 바깥에서 끌면 화면 이동
            self.press = None
            cx, cy = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
            p = self.page_at(cx, cy) if self.doc else None
            if p is None:
                self.pan_start(e)
            else:
                self.selecting = (p, self.canvas_to_page(p, cx, cy), False)
            return
        cx, cy = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        p = self.page_at(cx, cy)
        self.press = (cx, cy, p) if p is not None else None
        self.dragging = False

    def constrain(self, x0, y0, x1, y1, e):
        """Shift: 정사각형·정원 / 선은 45° 단위"""
        if not (getattr(e, "state", 0) & 0x1):
            return x1, y1
        dx, dy = x1 - x0, y1 - y0
        if self.mode.get() == "shape" and self.shape_kind.get() in ("선", "화살표"):
            if abs(dx) > 2 * abs(dy):
                return x1, y0
            if abs(dy) > 2 * abs(dx):
                return x0, y1
        d = min(abs(dx), abs(dy))
        return x0 + (d if dx >= 0 else -d), y0 + (d if dy >= 0 else -d)

    def clamp_to_page(self, p, x, y):
        sx, sy, sw, sh = self.slots[p]
        return min(max(x, sx), sx + sw), min(max(y, sy), sy + sh)

    def on_drag(self, e):
        if self.panning:
            self.pan_move(e)
            return
        if self.selecting:
            p, a, _ = self.selecting
            cx, cy = self.clamp_to_page(p, self.cv.canvasx(e.x), self.cv.canvasy(e.y))
            self.selecting = (p, a, True)
            self.select_text(p, a, self.canvas_to_page(p, cx, cy))
            return
        mode = self.mode.get()
        if not self.press or mode not in ("mark", "hide", "shape", "capture"):
            return
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        if abs(x - self.press[0]) + abs(y - self.press[1]) > 5:
            self.dragging = True
            self.cv.delete("sel")
            x0, y0, p = self.press
            if mode == "capture":
                x, y = self.clamp_to_page(p, x, y)
                self.cv.create_rectangle(x0, y0, x, y, outline="#e8001a", dash=(6, 3), width=2, tags="sel")
                self.cv.create_text(x + 4, y + 4, anchor="nw", fill="#e8001a", tags="sel",
                                    text=f"{abs(x - x0) / self.zoom * 25.4 / 72:.0f}×{abs(y - y0) / self.zoom * 25.4 / 72:.0f}mm")
                return
            if mode != "shape":
                self.cv.create_rectangle(x0, y0, x, y, outline="#1a73e8", dash=(4, 2), width=2, tags="sel")
                return
            x, y = self.clamp_to_page(p, *self.constrain(x0, y0, x, y, e))
            kind, col = self.shape_kind.get(), self.shape_color
            try:
                w = max(1, float(self.shape_width.get()) * self.zoom)
            except (tk.TclError, ValueError):
                w = 2
            fill = col if self.shape_fill.get() != "없음" else ""
            stip = "gray50" if self.shape_fill.get() == "반투명" else ""
            if kind == "사각형":
                self.cv.create_rectangle(x0, y0, x, y, outline=col, width=w, fill=fill, stipple=stip, tags="sel")
            elif kind == "원":
                self.cv.create_oval(x0, y0, x, y, outline=col, width=w, fill=fill, stipple=stip, tags="sel")
            else:
                self.cv.create_line(x0, y0, x, y, fill=col, width=w, tags="sel",
                                    arrow="last" if kind == "화살표" else "none",
                                    arrowshape=(4 * w + 6, 4 * w + 6, 1.5 * w + 2))

    def on_release(self, e):
        if self.panning:
            self.pan_end(e)
            return
        if self.selecting:
            p, a, moved = self.selecting
            self.selecting = None
            self.page_no = p
            self.update_page_label()
            if not moved:
                self.clear_selection()
            elif self.sel:
                t = self.sel["text"].replace("\n", " ")
                self.status.set(f"선택: \"{t[:40]}{'…' if len(t) > 40 else ''}\"  ·  Ctrl+C 복사 · Ctrl+B 북마크 · 우클릭 메뉴")
            return
        if not self.press or not self.doc:
            self.press = None
            return
        x0, y0, p = self.press
        self.press = None
        self.cv.delete("sel")
        mode = self.mode.get()
        x1, y1 = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        # 작업할 쪽 = 누른 쪽 (화면 이동 없이 현재 쪽으로 지정)
        self.page_no = p
        self.update_page_label()
        if mode == "capture":
            sx, sy, sw, sh = self.slots[p]
            if self.dragging:
                x1, y1 = self.clamp_to_page(p, x1, y1)
                r = fitz.Rect(x0 - sx, y0 - sy, x1 - sx, y1 - sy).normalize() / self.zoom
                if r.width < 3 or r.height < 3:
                    return
            else:
                r = None   # 쪽 전체
            self.capture(p, r)
            return
        if self.dragging and mode == "shape":
            x1, y1 = self.clamp_to_page(p, *self.constrain(x0, y0, x1, y1, e))
            self.do_shape(self.canvas_to_page(p, x0, y0), self.canvas_to_page(p, x1, y1))
            return
        if self.dragging and mode in ("mark", "hide"):
            x1, y1 = self.clamp_to_page(p, x1, y1)   # 끈 영역이 쪽 밖으로 나가면 쪽 안으로 자름
            r = fitz.Rect(self.canvas_to_page(p, x0, y0), self.canvas_to_page(p, x1, y1)).normalize()
            if r.width > 2 and r.height > 2:
                self.do_area(mode, r)
            return
        pt = self.canvas_to_page(p, x1, y1)
        if self.page_at(x1, y1) != p:
            return
        if mode == "edit":
            it = self.hit_pt(p, pt)
            if it:
                self.edit_dialog(it)
        elif mode in ("mark", "hide"):
            it = self.hit_pt(p, pt)
            if it:
                self.do_area(mode, it["rect"])
        elif mode == "memo":
            self.memo_at(pt)
        elif mode == "erase":
            self.erase_at(pt)

    # ---------- 글자 선택 (뷰어 모드) ----------
    def words_for(self, p):
        if p not in self.words_cache:
            page = self.doc[p]
            with unrotated(page):
                self.words_cache[p] = [w for w in page.get_text("words") if w[4].strip()]
        return self.words_cache[p]

    @staticmethod
    def _nearest_word(words, pt):
        best, bd = None, None
        for i, w in enumerate(words):
            r = fitz.Rect(w[:4])
            if pt in r:
                return i
            dx = max(r.x0 - pt.x, 0, pt.x - r.x1)
            dy = max(r.y0 - pt.y, 0, pt.y - r.y1)
            d = dx + dy * 3          # 같은 줄을 우선
            if bd is None or d < bd:
                best, bd = i, d
        return best

    def select_text(self, p, a, b):
        """a~b 사이 글자를 읽는 순서대로 선택"""
        words = self.words_for(p)
        if not words:
            self.clear_selection()
            return
        i, j = self._nearest_word(words, a), self._nearest_word(words, b)
        lo, hi = min(i, j), max(i, j)
        chosen = words[lo:hi + 1]
        parts, prev = [], None
        for w in chosen:
            key = (w[5], w[6])
            if prev is not None:
                parts.append(" " if key == prev else "\n")
            parts.append(w[4])
            prev = key
        page_h = self.doc[p].mediabox.height or 1
        self.sel = {"page": p, "text": "".join(parts), "rects": [fitz.Rect(w[:4]) for w in chosen],
                    "y": max(0.0, min(1.0, chosen[0][1] / page_h))}
        self.draw_selection()

    def draw_selection(self):
        self.cv.delete("tsel")
        if not self.sel or not self.doc or self.sel["page"] not in self.slots:
            return
        p = self.sel["page"]
        for r in self.sel["rects"]:
            x0, y0, x1, y1 = self.page_to_canvas_rect(p, r)
            self.cv.create_rectangle(x0, y0, x1, y1, fill="#2f7cf6", outline="", stipple="gray50", tags="tsel")

    def clear_selection(self):
        self.sel = None
        self.cv.delete("tsel")

    def copy_selection(self, e=None):
        try:
            cls = self.root.focus_get().winfo_class()
        except (AttributeError, KeyError, tk.TclError):
            cls = ""
        if cls in ("TEntry", "Entry", "Text", "TSpinbox", "Spinbox", "TCombobox"):
            return   # 입력칸에서는 원래 복사 동작
        if self.sel and self.sel["text"]:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.sel["text"])
            self.status.set(f"복사했습니다 ({len(self.sel['text'])}자)")

    def mark_selection(self):
        if not self.sel:
            return
        p = self.sel["page"]
        try:
            self.push_undo()
            page = self.doc[p]
            with unrotated(page):
                a = page.add_highlight_annot(self.sel["rects"])
                a.set_colors(stroke=hex2rgb(self.mark_color))
                a.update()
            self.dirty = True
            self.clear_selection()
            self.render()
            self.status.set("선택한 글자를 색칠했습니다.")
        except Exception as ex:
            messagebox.showerror(APP, f"색칠 실패:\n{ex}")

    def pan_start(self, e):
        self.panning = True
        self.cv.scan_mark(e.x, e.y)
        self.cv.configure(cursor="fleur")

    def pan_move(self, e):
        if self.panning:
            self.cv.scan_dragto(e.x, e.y, gain=1)

    def pan_end(self, e=None):
        self.panning = False
        self.cv.configure(cursor="")

    def on_context(self, e):
        if not self.doc:
            return
        cx, cy = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        p = self.page_at(cx, cy)
        if p is not None:
            self.page_no = p
            self.update_page_label()
        m = tk.Menu(self.root, tearoff=0)
        if self.sel:
            m.add_command(label="복사", accelerator="Ctrl+C", command=self.copy_selection)
            m.add_command(label="선택한 글자로 북마크 추가", accelerator="Ctrl+B", command=self.add_bookmark_now)
            m.add_command(label="선택한 글자 색칠", command=self.mark_selection)
            m.add_command(label="선택 해제", command=self.clear_selection)
            m.add_separator()
        m.add_command(label="이 쪽 북마크", command=lambda: (self.clear_selection(), self.add_bookmark_now()))
        m.add_command(label="즐겨찾기에 추가", accelerator="Ctrl+D", command=self.add_favorite_now)
        m.add_separator()
        m.add_command(label="이 쪽 왼쪽으로 회전", command=lambda: self.rotate_pages([self.page_no], -90))
        m.add_command(label="이 쪽 오른쪽으로 회전", command=lambda: self.rotate_pages([self.page_no], 90))
        m.add_command(label="이 쪽 캡쳐", command=lambda: self.capture(self.page_no, None))
        m.tk_popup(e.x_root, e.y_root)

    # ---------- 스크롤 · 쪽 이동 · 배율 ----------
    def on_canvas_enter(self, e):
        f = self.root.focus_get()   # 글자 입력 중이 아니면 화면에 포커스 (콤보상자가 휠에 바뀌는 것도 방지)
        try:
            cls = f.winfo_class() if f else ""
        except (KeyError, tk.TclError):
            cls = ""
        if cls not in ("TEntry", "Entry", "Text", "TSpinbox", "Spinbox"):
            self.cv.focus_set()

    def route_wheel(self, e):
        """휠 신호를 마우스 아래 칸으로 보냄"""
        try:
            w = self.root.winfo_containing(e.x_root, e.y_root)
        except (KeyError, tk.TclError):
            return
        if w is None:
            return
        if w is self.cv:
            self.on_wheel(e)
            return
        if w is self.root.focus_get() and w.winfo_class() in ("Text", "Treeview", "Listbox"):
            return   # 이미 자체적으로 스크롤됨
        while w is not None and not hasattr(w, "yview"):
            w = w.master
        if w is not None and w.winfo_class() in ("Text", "Treeview", "Listbox", "Canvas"):
            try:
                w.yview_scroll(-1 if e.delta > 0 else 1, "units") if abs(e.delta) < 120 else \
                    w.yview_scroll(int(-e.delta / 120 * 3), "units")
            except tk.TclError:
                pass

    def on_wheel(self, e):
        if e.state & 0x4:  # Ctrl+휠 = 확대/축소
            self.set_zoom(self.zoom * (1.1 if e.delta > 0 else 1 / 1.1))
            return
        if e.state & 0x1:  # Shift+휠 = 가로 스크롤
            self.cv.xview_scroll(int(-e.delta / 40), "units")
            return
        self.wheel_step(-1 if e.delta > 0 else 1, e, amount=max(1, abs(int(e.delta / 40))))

    def wheel_step(self, direction, e=None, amount=3):
        if e is not None and getattr(e, "state", 0) & 0x4:
            self.set_zoom(self.zoom * (1.1 if direction < 0 else 1 / 1.1))
            return
        if self.wheel_page.get():   # 휠 한 칸 = 한 쪽
            now = time.time()
            if now - self._wheel_t > 0.15:
                self._wheel_t = now
                self.go(direction)
            return
        top, bot = self.cv.yview()
        if self.view == "single":   # 한 쪽씩: 끝에 닿으면 다음/이전 쪽
            if direction > 0 and bot >= 0.999:
                self.go(1)
                return
            if direction < 0 and top <= 0.001 and self.page_no > 0:
                self.go(-1)
                self.cv.yview_moveto(1.0)
                return
        self.cv.yview_scroll(direction * amount, "units")

    def goto(self, p, frac=None):
        if not self.doc or not 0 <= p < len(self.doc):
            return
        if self.view == "single":
            self.page_no = p
            self.render(goto=p)
            if frac:
                self.scroll_to(p, frac)
        else:
            self._sync_page = False
            self.scroll_to(p, frac)
            self.page_no = p
            self.update_page_label()
            self.update_visible()
            self._sync_page = True

    def go(self, step):
        if self.doc:
            n = self.page_no + step * (1 if self.view == "single" else self.cols())
            if self.cols() > 1:
                n -= n % self.cols()
            self.goto(max(0, min(len(self.doc) - 1, n)))

    def jump(self, _=None):
        try:
            n = int(self.page_var.get().split("/")[0]) - 1
        except ValueError:
            return
        self.cv.focus_set()
        self.goto(n)
        self.update_page_label()

    def set_zoom(self, z):
        self.fit.set("custom")
        self.zoom = max(0.1, min(8.0, z))
        self.zoom_lbl.config(text=f"{round(self.zoom * 100)}%")
        if self.doc:
            self.render(goto=self.page_no)

    # ---------- 수정 ----------
    def push_undo(self):
        self.undo.append((self.doc.tobytes(), self.page_no))
        del self.undo[:-UNDO_MAX]

    def do_undo(self):
        if not self.undo:
            self.status.set("되돌릴 내용이 없습니다.")
            return
        data, pg = self.undo.pop()
        self._sizes_key = None
        self.doc = fitz.open("pdf", data)
        self.page_no = pg
        self.dirty = bool(self.undo)
        self.render(goto=pg if self.view == "single" else None)
        self.status.set("되돌렸습니다.")

    def apply_edits(self, page, edits):
        """edits: [(rect, origin, size, color, bold, new_text)] 를 한 페이지에 적용"""
        with unrotated(page):
            self._apply_edits(page, edits)

    def _apply_edits(self, page, edits):
        for rect, *_ in edits:
            r = fitz.Rect(rect)
            h = r.height
            r.y0 += h * 0.2   # 위/아래 줄을 지우지 않도록 살짝 줄여서 지움
            r.y1 -= h * 0.2
            page.add_redact_annot(r, fill=False)
        try:
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                                  graphics=fitz.PDF_REDACT_LINE_ART_NONE)  # 표 선·그림 보존
        except (TypeError, AttributeError):
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
        for rect, origin, size, color, bold, text in edits:
            if not text:
                continue
            fname, fpath, font = get_font(bold)
            w = font.text_length(text, fontsize=size)
            maxw = fitz.Rect(rect).width
            if self.autofit.get() and maxw > 0 and w > maxw * 1.02:
                size = max(4, size * maxw / w)
            kw = dict(fontsize=size, fontname=fname, color=color_tuple(color))
            if fpath:
                kw["fontfile"] = fpath
            page.insert_text(origin, text, **kw)

    def edit_dialog(self, it):
        dlg = tk.Toplevel(self.root)
        dlg.title("글자 수정")
        dlg.transient(self.root)
        dlg.grab_set()
        frm = ttk.Frame(dlg, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"원래: {it['text']}", wraplength=520, foreground="#666").pack(anchor="w")
        ttk.Label(frm, text=f"글꼴 {it['font']} · {it['size']:.1f}pt").pack(anchor="w", pady=(2, 6))
        var = tk.StringVar(value=it["text"])
        ent = ttk.Entry(frm, textvariable=var, width=70, font=("맑은 고딕", 11))
        ent.pack(fill="x")
        ent.focus_set()
        ent.select_range(0, "end")
        size_var = tk.DoubleVar(value=round(it["size"], 1))
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=8)
        ttk.Label(row, text="글자 크기").pack(side="left")
        ttk.Spinbox(row, from_=4, to=72, increment=0.5, textvariable=size_var, width=6).pack(side="left", padx=4)
        bold_var = tk.BooleanVar(value=it["bold"])
        ttk.Checkbutton(row, text="굵게", variable=bold_var).pack(side="left", padx=8)

        def ok(_=None):
            new = var.get()
            try:
                sz = float(size_var.get())
            except (tk.TclError, ValueError):
                sz = it["size"]
            dlg.destroy()
            if new == it["text"] and abs(sz - it["size"]) < 0.05 and bold_var.get() == it["bold"]:
                return
            try:
                self.push_undo()
                page = self.doc[self.page_no]
                self.apply_edits(page, [(it["rect"], it["origin"], sz, it["color"], bold_var.get(), new)])
                self.dirty = True
                self.render()
                self.status.set("수정했습니다. (Ctrl+Z 되돌리기, Ctrl+S 저장)")
            except Exception as ex:
                messagebox.showerror(APP, f"수정 실패:\n{ex}")

        btns = ttk.Frame(frm)
        btns.pack(fill="x")
        ttk.Button(btns, text="취소", command=dlg.destroy).pack(side="right")
        ttk.Button(btns, text="적용 (Enter)", command=ok).pack(side="right", padx=4)
        ent.bind("<Return>", ok)
        dlg.bind("<Escape>", lambda e: dlg.destroy())

    # ---------- 색칠 · 감추기 · 메모 ----------
    def set_color(self, c):
        self.mark_color = c
        self.swatch.config(bg=c)
        if self.mode.get() != "mark":
            self.mode.set("mark"); self.on_mode()

    def pick_color(self):
        c = colorchooser.askcolor(self.mark_color, title="색칠 색")[1]
        if c:
            self.set_color(c)

    def do_area(self, mode, rect):
        try:
            self.push_undo()
            page = self.doc[self.page_no]
            with unrotated(page):
                if mode == "mark":
                    self._mark(page, fitz.Rect(rect))
                else:
                    fill = (0, 0, 0) if self.hide_fill.get() == "검정" else (1, 1, 1)
                    page.add_redact_annot(fitz.Rect(rect), fill=fill)
                    try:
                        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)
                    except (TypeError, AttributeError):
                        page.apply_redactions()
            self.dirty = True
            self.render()
            self.status.set("색칠했습니다." if mode == "mark" else "감췄습니다. (Ctrl+Z로 되돌리기)")
        except Exception as ex:
            messagebox.showerror(APP, f"실패:\n{ex}")

    def _mark(self, page, rect):
        c = hex2rgb(self.mark_color)
        words = []
        for w in page.get_text("words"):
            wr = fitz.Rect(w[:4])
            inter = fitz.Rect(wr) & rect
            if not inter.is_empty and wr.get_area() > 0 and inter.get_area() >= wr.get_area() * 0.3:
                words.append(wr)
        if words:   # 글자가 있으면 형광펜
            a = page.add_highlight_annot(words)
            a.set_colors(stroke=c)
        else:       # 빈 곳이면 반투명 사각형
            a = page.add_rect_annot(rect)
            a.set_colors(stroke=c, fill=c)
            a.set_border(width=0)
            a.set_opacity(0.35)
        a.update()

    # ---------- 캡쳐 ----------
    def capture(self, p, rect):
        """rect: 화면에 보이는(회전 반영) 쪽 좌표 pt. None이면 쪽 전체"""
        try:
            dpi = max(36, min(1200, int(float(self.cap_dpi.get()))))
        except ValueError:
            dpi = 200
        page = self.doc[p]
        clip = (rect & page.rect) if rect else page.rect
        sc = dpi / 72
        if clip.width * sc * clip.height * sc > 120_000_000:   # 너무 큰 그림 방지
            sc = (120_000_000 / (clip.width * clip.height)) ** 0.5
            dpi = int(sc * 72)
        try:
            pix = page.get_pixmap(matrix=fitz.Matrix(sc, sc), clip=clip, alpha=False)
        except Exception as ex:
            messagebox.showerror(APP, f"캡쳐 실패:\n{ex}")
            return
        copied = copy_image_to_clipboard(pix)
        msg = (f"캡쳐했습니다 ({pix.width}×{pix.height}px, {dpi}dpi) — 클립보드에 복사됨, Ctrl+V로 붙여넣기"
               if copied else f"캡쳐했습니다 ({pix.width}×{pix.height}px). 클립보드 복사는 실패했습니다.")
        self.status.set(msg)
        if self.cap_preview.get() or not copied:
            self.capture_preview(pix, p, copied)

    def capture_preview(self, pix, p, copied):
        dlg = tk.Toplevel(self.root)
        dlg.title("캡쳐")
        dlg.transient(self.root)
        frm = ttk.Frame(dlg, padding=8)
        frm.pack(fill="both", expand=True)
        scale = min(1.0, 640 / pix.width, 480 / pix.height)
        prev = pix
        if scale < 1:
            try:
                prev = fitz.Pixmap(pix, max(1, int(pix.width * scale)), max(1, int(pix.height * scale)), None)
            except Exception:
                prev = pix
        img = tk.PhotoImage(data=base64.b64encode(prev.tobytes("png")))
        if prev is pix and scale < 1:
            img = img.subsample(int(1 / scale + 0.999))
        lbl = tk.Label(frm, image=img, bd=1, relief="solid", bg="white")
        lbl.image = img
        lbl.pack()
        ttk.Label(frm, text=f"{pix.width} × {pix.height} px" + ("  ·  클립보드에 복사됨" if copied else ""),
                  foreground="#555").pack(pady=(6, 4))
        b = ttk.Frame(frm)
        b.pack(fill="x")
        base = os.path.splitext(os.path.basename(self.path or "캡쳐"))[0]

        def save():
            fp = filedialog.asksaveasfilename(parent=dlg, defaultextension=".png",
                                              filetypes=[("PNG 그림", "*.png"), ("JPG 그림", "*.jpg")],
                                              initialdir=os.path.dirname(self.path) if self.path else None,
                                              initialfile=f"{base}_{p + 1}쪽_캡쳐_{datetime.datetime.now():%H%M%S}.png")
            if not fp:
                return
            try:
                if fp.lower().endswith((".jpg", ".jpeg")):
                    try:
                        pix.save(fp, jpg_quality=92)
                    except TypeError:
                        pix.save(fp)
                else:
                    pix.save(fp)
                self.status.set(f"저장했습니다: {fp}")
                dlg.destroy()
            except Exception as ex:
                messagebox.showerror(APP, f"저장 실패:\n{ex}", parent=dlg)

        def recopy():
            if copy_image_to_clipboard(pix):
                self.status.set("클립보드에 복사했습니다.")
                dlg.destroy()
            else:
                messagebox.showwarning(APP, "클립보드 복사에 실패했습니다.", parent=dlg)

        ttk.Button(b, text="닫기", command=dlg.destroy).pack(side="right")
        ttk.Button(b, text="그림 파일로 저장 (Ctrl+S)", command=save).pack(side="right", padx=4)
        ttk.Button(b, text="클립보드 복사", command=recopy).pack(side="right")
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        dlg.bind("<Control-s>", lambda e: save())
        dlg.focus_set()

    def set_shape_color(self, c):
        self.shape_color = c
        self.shape_swatch.config(bg=c)

    def pick_shape_color(self):
        c = colorchooser.askcolor(self.shape_color, title="도형 색")[1]
        if c:
            self.set_shape_color(c)

    def do_shape(self, a, b):
        kind = self.shape_kind.get()
        if kind in ("사각형", "원"):
            r = fitz.Rect(a, b).normalize()
            if r.width < 2 or r.height < 2:
                return
        elif abs(a.x - b.x) + abs(a.y - b.y) < 2:
            return
        try:
            w = max(0.5, float(self.shape_width.get()))
        except (tk.TclError, ValueError):
            w = 2.0
        col = hex2rgb(self.shape_color)
        fill = self.shape_fill.get()
        try:
            self.push_undo()
            page = self.doc[self.page_no]
            with unrotated(page):
                if kind == "사각형":
                    an = page.add_rect_annot(r)
                elif kind == "원":
                    an = page.add_circle_annot(r)
                else:
                    an = page.add_line_annot(a, b)
                if kind in ("사각형", "원") and fill != "없음":
                    an.set_colors(stroke=col, fill=col)
                    if fill == "반투명":
                        an.set_opacity(0.4)
                elif kind == "화살표":
                    an.set_colors(stroke=col, fill=col)
                    an.set_line_ends(fitz.PDF_ANNOT_LE_NONE, fitz.PDF_ANNOT_LE_CLOSED_ARROW)
                else:
                    an.set_colors(stroke=col)
                an.set_border(width=w)
                an.set_info(title="도형")
                an.update()
            self.dirty = True
            self.render()
            self.status.set(f"{kind}을(를) 그렸습니다. (지우개 도구로 지우기 / Ctrl+Z)")
        except Exception as ex:
            messagebox.showerror(APP, f"도형 그리기 실패:\n{ex}")

    def memo_dialog(self, initial="", existing=False):
        dlg = tk.Toplevel(self.root)
        dlg.title("메모 수정" if existing else "메모 추가")
        dlg.transient(self.root)
        frm = ttk.Frame(dlg, padding=10)
        frm.pack(fill="both", expand=True)
        txt = tk.Text(frm, width=50, height=8, font=("맑은 고딕", 10), wrap="word")
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", initial)
        txt.focus_set()
        res = {"v": None}

        def done(v):
            res["v"] = v
            dlg.destroy()
        b = ttk.Frame(frm)
        b.pack(fill="x", pady=(8, 0))
        ttk.Button(b, text="취소", command=dlg.destroy).pack(side="right")
        ttk.Button(b, text="저장 (Ctrl+Enter)", command=lambda: done(("save", txt.get("1.0", "end-1c")))).pack(side="right", padx=4)
        if existing:
            ttk.Button(b, text="메모 삭제", command=lambda: done(("delete", None))).pack(side="left")
        dlg.bind("<Control-Return>", lambda e: done(("save", txt.get("1.0", "end-1c"))))
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        dlg.grab_set()
        dlg.wait_window()
        return res["v"]

    def memo_at(self, pt):
        page = self.doc[self.page_no]
        xref, content = None, ""
        with unrotated(page):
            for a in page.annots(types=[fitz.PDF_ANNOT_TEXT]) or []:
                if pt in a.rect:
                    xref, content = a.xref, a.info.get("content", "")
        res = self.memo_dialog(content, existing=xref is not None)
        if not res:
            return
        action, text = res
        if action == "save" and not text.strip() and xref is None:
            return
        try:
            self.push_undo()
            page = self.doc[self.page_no]
            with unrotated(page):
                if xref is not None:
                    a = page.load_annot(xref)
                    if action == "delete" or not text.strip():
                        page.delete_annot(a)
                    else:
                        a.set_info(content=text)
                        a.update()
                else:
                    a = page.add_text_annot(pt, text, icon="Comment")
                    a.set_info(title="메모", content=text)
                    a.set_colors(stroke=(1, 0.82, 0))
                    a.update()
            self.dirty = True
            self.render()
            self.status.set("메모를 저장했습니다. 메모 위에 마우스를 올리면 내용이 보입니다.")
        except Exception as ex:
            messagebox.showerror(APP, f"메모 실패:\n{ex}")

    def erase_at(self, pt):
        page = self.doc[self.page_no]
        with unrotated(page):
            target = None
            for a in page.annots() or []:
                if pt in a.rect and a.type[0] != fitz.PDF_ANNOT_WIDGET:
                    target = a.xref
            if target is None:
                self.status.set("여기에는 지울 색칠·메모가 없습니다. (글자수정·감추기는 Ctrl+Z로 되돌리세요)")
                return
            self.push_undo()
            page.delete_annot(page.load_annot(target))
        self.dirty = True
        self.render()
        self.status.set("지웠습니다.")

    # ---------- 회전 · 쪽 골라 저장 ----------
    def rotate_pages(self, pages, delta):
        if not self.doc:
            return
        self.push_undo()
        for p in pages:
            pg = self.doc[p]
            pg.set_rotation((pg.rotation + delta) % 360)
        self._sizes_key = None
        self.dirty = True
        self.render()
        self.status.set(f"{len(pages)}쪽을 회전했습니다." if len(pages) > 1 else f"{pages[0] + 1}쪽을 회전했습니다.")

    def _pages_dialog(self, title, hint, extra=None):
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.transient(self.root)
        dlg.resizable(False, False)
        frm = ttk.Frame(dlg, padding=10)
        frm.pack()
        ttk.Label(frm, text=f"쪽 번호 (전체 {len(self.doc)}쪽)").pack(anchor="w")
        v = tk.StringVar(value=str(self.page_no + 1))
        ent = ttk.Entry(frm, textvariable=v, width=40)
        ent.pack(fill="x", pady=4)
        ent.focus_set()
        ent.select_range(0, "end")
        ttk.Label(frm, text=hint, foreground="#666").pack(anchor="w")
        if extra:
            extra(frm)
        res = {"v": None}

        def ok(_=None):
            try:
                res["v"] = parse_pages(v.get(), len(self.doc))
            except ValueError as ex:
                messagebox.showwarning(APP, str(ex) if "쪽" in str(ex) else "쪽 번호를 확인해주세요.", parent=dlg)
                return
            dlg.destroy()
        b = ttk.Frame(frm)
        b.pack(fill="x", pady=(8, 0))
        ttk.Button(b, text="취소", command=dlg.destroy).pack(side="right")
        ttk.Button(b, text="확인", command=ok).pack(side="right", padx=4)
        ent.bind("<Return>", ok)
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        dlg.grab_set()
        dlg.wait_window()
        return res["v"]

    def rotate_dialog(self):
        if not self.doc:
            return
        ang = tk.StringVar(value="오른쪽 90°")

        def extra(frm):
            f = ttk.Frame(frm)
            f.pack(anchor="w", pady=(6, 0))
            for t in ("오른쪽 90°", "왼쪽 90°", "180°"):
                ttk.Radiobutton(f, text=t, value=t, variable=ang).pack(side="left", padx=(0, 8))
        pages = self._pages_dialog("여러 쪽 회전", "예) 1-3, 5, 8-  (8- 는 8쪽부터 끝까지)", extra)
        if pages:
            self.rotate_pages(pages, {"오른쪽 90°": 90, "왼쪽 90°": -90, "180°": 180}[ang.get()])

    def extract_dialog(self):
        if not self.doc:
            return
        keep = tk.BooleanVar(value=True)

        def extra(frm):
            ttk.Checkbutton(frm, text="입력한 순서대로 저장 (끄면 쪽 번호 순)", variable=keep).pack(anchor="w", pady=(6, 0))
        pages = self._pages_dialog("원하는 쪽만 저장", "예) 7, 2, 10-12   → 이 쪽들만 새 PDF로 저장", extra)
        if not pages:
            return
        if not keep.get():
            pages = sorted(pages)
        base = os.path.splitext(os.path.basename(self.path))[0]
        p = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                                         initialdir=os.path.dirname(self.path), initialfile=f"{base}_발췌.pdf")
        if not p:
            return
        if os.path.abspath(p) == self.path:
            messagebox.showwarning(APP, "지금 열려 있는 파일과 다른 이름으로 저장해주세요.")
            return
        try:
            out = fitz.open()
            for i in pages:
                out.insert_pdf(self.doc, from_page=i, to_page=i)
            out.save(p, garbage=3, deflate=True)
            out.close()
            self.status.set(f"{len(pages)}쪽을 저장했습니다: {p}")
        except Exception as ex:
            messagebox.showerror(APP, f"저장 실패:\n{ex}")

    def find_replace(self):
        if not self.doc:
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("찾아 바꾸기")
        dlg.transient(self.root)
        frm = ttk.Frame(dlg, padding=10)
        frm.pack()
        ttk.Label(frm, text="찾을 글자").grid(row=0, column=0, sticky="w")
        ttk.Label(frm, text="바꿀 글자").grid(row=1, column=0, sticky="w", pady=4)
        fv, rv = tk.StringVar(), tk.StringVar()
        fe = ttk.Entry(frm, textvariable=fv, width=40)
        fe.grid(row=0, column=1)
        ttk.Entry(frm, textvariable=rv, width=40).grid(row=1, column=1, pady=4)
        scope = tk.StringVar(value="all")
        sf = ttk.Frame(frm)
        sf.grid(row=2, column=1, sticky="w")
        ttk.Radiobutton(sf, text="전체 페이지", value="all", variable=scope).pack(side="left")
        ttk.Radiobutton(sf, text="현재 페이지", value="cur", variable=scope).pack(side="left", padx=8)
        fe.focus_set()

        def run(_=None):
            old, new = fv.get(), rv.get()
            if not old:
                return
            pages = range(len(self.doc)) if scope.get() == "all" else [self.page_no]
            plan = {}
            for pn in pages:
                page = self.doc[pn]
                with unrotated(page):
                    hits = page.search_for(old)
                    spans = [s for b in page.get_text("dict")["blocks"] if b.get("type") == 0
                             for l in b["lines"] for s in l["spans"]] if hits else []
                if not hits:
                    continue
                edits = []
                for h in hits:
                    c = fitz.Point((h.x0 + h.x1) / 2, (h.y0 + h.y1) / 2)
                    sp = next((s for s in spans if c in fitz.Rect(s["bbox"])), None)
                    if not sp:
                        continue
                    bold = bool(sp["flags"] & 16) or "bold" in sp["font"].lower()
                    origin = fitz.Point(h.x0, sp["origin"][1])
                    edits.append((h, origin, sp["size"], sp["color"], bold, new))
                if edits:
                    plan[pn] = edits
            total = sum(len(v) for v in plan.values())
            if not total:
                messagebox.showinfo(APP, "찾는 글자가 없습니다.", parent=dlg)
                return
            if not messagebox.askyesno(APP, f"{len(plan)}개 페이지에서 {total}곳을 바꿉니다. 계속할까요?", parent=dlg):
                return
            try:
                self.push_undo()
                for pn, edits in plan.items():
                    self.apply_edits(self.doc[pn], edits)
                self.dirty = True
                dlg.destroy()
                self.render()
                self.status.set(f"{total}곳을 바꿨습니다.")
            except Exception as ex:
                messagebox.showerror(APP, f"바꾸기 실패:\n{ex}", parent=dlg)

        ttk.Button(frm, text="모두 바꾸기", command=run).grid(row=3, column=1, sticky="e", pady=(8, 0))
        dlg.bind("<Return>", run)
        dlg.bind("<Escape>", lambda e: dlg.destroy())


# 문서별 값은 지금 탭(self.tab)에 저장 → 기존 코드의 self.doc, self.page_no 등이 그대로 탭 단위로 동작
for _n in ("doc", "path", "page_no", "undo", "items_cache", "words_cache", "annot_cache", "mats", "sizes", "slots", "imgs",
           "_sizes_key"):
    setattr(App, _n, property(lambda self, _n=_n: getattr(self.tab, _n),
                              lambda self, v, _n=_n: setattr(self.tab, _n, v)))


def _get_dirty(self):
    return self.tab._dirty


def _set_dirty(self, v):
    self.tab._dirty = bool(v)
    if hasattr(self, "tabbar"):
        self.update_tab_title(self.tab)


App.dirty = property(_get_dirty, _set_dirty)


def selftest():
    """실행파일 점검용: PDF 엔진이 제대로 들어갔는지 확인 (smartpdfeditor.exe --selftest → 종료코드 0)"""
    try:
        d = fitz.open()
        pg = d.new_page()
        pg.insert_text((72, 72), "selftest")
        get_font(False)
        ok = "selftest" in pg.get_text() and pg.get_pixmap().width > 0 and len(d.tobytes()) > 0
        sys.exit(0 if ok else 1)
    except Exception:
        sys.exit(2)


def main():
    args = sys.argv[1:]
    if "--selftest" in args:
        selftest()
    new_window = "--new" in args
    files = [os.path.abspath(a) for a in args if not a.startswith("--") and os.path.exists(a)]
    if not new_window and load_conf()["prefs"].get("external_open", "tab") == "tab":
        if send_to_running(files):   # 이미 실행 중 → 그 창의 새 탭으로 열고 끝
            return
    root = tk.Tk()
    App(root, files, listen=not new_window)
    root.mainloop()


if __name__ == "__main__":
    main()
