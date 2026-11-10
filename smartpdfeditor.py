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
import uuid
import queue
import re
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from tkinter import font as tkfont

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
UPDATE_API = "https://api.github.com/repos/nunco-git/smartpdfeditor/releases/latest"   # 새 버전 확인 (비우면 안 함)
DOWNLOAD_URL = "https://smartgong.kr/download/smart-pdf-editor"                       # 항상 최신 버전 exe
UPDATE_CHECK_HOURS = 3
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
# 화면 테마. "clip" = 스마트클립 아이콘 색(주황 #F6A53F · 갈색 #5C3D00 · 크림)
THEMES = {
    "clip":  {"name": "스마트클립 (주황)", "bg": "#fff6e8", "fg": "#3e2a00", "accent": "#f6a53f",
              "field": "#fffdf9", "canvas": "#5a5a5a", "shadow": "#3c3c3c", "link": "#b4610a", "scope": "top"},
    "gray":  {"name": "기본 (회색)", "bg": "", "fg": "", "accent": "", "field": "",
              "canvas": "#5a5a5a", "shadow": "#3c3c3c", "link": "#1565c0"},
    "light": {"name": "밝게", "bg": "#f7f9fc", "fg": "#1f2933", "accent": "#7fb2f0",
              "field": "#ffffff", "canvas": "#dfe5ec", "shadow": "#b8c2cc", "link": "#1565c0", "scope": "top"},
    "dark":  {"name": "어둡게", "bg": "#2b2b2e", "fg": "#e8e8e8", "accent": "#c9822b",
              "field": "#3a3a3e", "canvas": "#1e1e20", "shadow": "#000000", "link": "#f6a53f", "scope": "all"},
    "beige": {"name": "따뜻한 베이지", "bg": "#f5ecdc", "fg": "#3b2f20", "accent": "#d9a05b",
              "field": "#fffaf1", "canvas": "#8a7c6a", "shadow": "#5c5040", "link": "#a85d12", "scope": "top"},
    "sky":   {"name": "하늘색", "bg": "#e3f0fb", "fg": "#16324f", "accent": "#7fb2f0",
              "field": "#ffffff", "canvas": "#6f8396", "shadow": "#4a5a6a", "link": "#1d5fae", "scope": "top"},
    "green": {"name": "초록", "bg": "#e6f2e8", "fg": "#1f3a26", "accent": "#7cc492",
              "field": "#ffffff", "canvas": "#6b7d6f", "shadow": "#4a584d", "link": "#23773f", "scope": "top"},
    "pink":  {"name": "분홍", "bg": "#fbeaf0", "fg": "#4a2333", "accent": "#ec9ab8",
              "field": "#fffafc", "canvas": "#85707a", "shadow": "#5d4b54", "link": "#b03a6a", "scope": "top"},
    "purple": {"name": "보라", "bg": "#efeafa", "fg": "#2e2346", "accent": "#a993ea",
               "field": "#ffffff", "canvas": "#6f6a80", "shadow": "#4d4960", "link": "#5b3fb8", "scope": "top"},
    "navy":  {"name": "짙은 남색", "bg": "#1f2a3c", "fg": "#e6ecf5", "accent": "#4c8dff",
              "field": "#2a3850", "canvas": "#141b27", "shadow": "#000000", "link": "#8ab4ff", "scope": "all"},
}
NEUTRAL = {"bg": "#f0f0f0", "fg": "#1f1f1f", "accent": "#cfe3fa", "field": "#ffffff"}   # 도구줄 아래(사이드바·상태줄)
THEME_DEFAULT = {"preset": "clip", "font_family": "맑은 고딕", "font_size": 9, "fg": "", "bg": "", "accent": "",
                 "canvas": "", "wall": ""}
FONT_FIRST = ("맑은 고딕", "Malgun Gothic", "나눔고딕", "NanumGothic", "나눔바른고딕", "굴림", "Gulim", "돋움",
              "Dotum", "바탕", "Batang", "Segoe UI", "Arial", "Tahoma")
AD_W, AD_H = 250, 250     # 광고창 기본 크기 (사이드바 폭에 맞춘 정사각형 배너)
AD_FILES = ("ad.png", "ad.gif", "ad.jpg", "ad.jpeg")   # 실행파일 옆에 두면 이 광고가 우선 (시험용)
AD_LINK_FILE = "ad.txt"   # 첫 줄 = 광고 클릭 시 열 주소
CONTACT_EMAIL = "smartgongmaster@gmail.com"   # 오류·개선 제안 받는 주소
AD_URL = "https://smartgong.kr/ads/smartpdfeditor.json"   # 인터넷 광고 설정
# 사용 통계 — 설치된 컴퓨터 수만 셉니다. 보내는 것: 무작위 번호 + 프로그램 버전 (하루 한 번)
# 환경설정 → 일반 → 「사용 통계 보내지 않기」로 끌 수 있습니다.
FIREBASE_DB_URL = "https://smartexplorer-d569e-default-rtdb.asia-southeast1.firebasedatabase.app"
STATS_APP = "smartpdfeditor"


# ───────────── 인터넷 연결 (파이썬 방식 → 안 되면 윈도우 방식) ─────────────
# 회사·기관 PC는 프록시(자동 구성 스크립트)나 보안 프로그램의 인증서 때문에 파이썬 방식(urllib)이
# "urlopen error"로 실패하는 일이 많음. 그때는 인터넷 익스플로러·엣지와 같은 윈도우 설정(WinINet)으로 다시 시도.
_WININET_ERRORS = {
    12002: "응답 시간 초과", 12007: "인터넷 주소를 찾지 못함(DNS)", 12029: "서버에 연결할 수 없음(방화벽·차단)",
    12030: "연결이 끊어짐", 12031: "연결이 초기화됨", 12037: "보안 인증서 날짜 문제", 12038: "보안 인증서 이름 문제",
    12044: "클라이언트 인증서 필요", 12045: "신뢰할 수 없는 보안 인증서", 12057: "인증서 해지 확인 실패",
    12157: "보안 연결(SSL) 실패", 12175: "보안 인증서 오류",
}


class NetHTTPError(Exception):
    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.code = code


def _wininet_request(url, method, headers, data, limit, timeout):
    import ctypes
    from ctypes import wintypes
    from urllib.parse import urlsplit
    wi = ctypes.WinDLL("wininet", use_last_error=True)
    H = ctypes.c_void_p
    wi.InternetOpenW.restype = H
    wi.InternetOpenW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    wi.InternetConnectW.restype = H
    wi.InternetConnectW.argtypes = [H, wintypes.LPCWSTR, wintypes.WORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                    wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]
    wi.HttpOpenRequestW.restype = H
    wi.HttpOpenRequestW.argtypes = [H, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                    ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t]
    wi.HttpSendRequestW.restype = wintypes.BOOL
    wi.HttpSendRequestW.argtypes = [H, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    wi.HttpQueryInfoW.restype = wintypes.BOOL
    wi.HttpQueryInfoW.argtypes = [H, wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD),
                                  ctypes.POINTER(wintypes.DWORD)]
    wi.InternetReadFile.restype = wintypes.BOOL
    wi.InternetReadFile.argtypes = [H, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    wi.InternetSetOptionW.restype = wintypes.BOOL
    wi.InternetSetOptionW.argtypes = [H, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    wi.InternetCloseHandle.argtypes = [H]

    def fail(what):
        code = ctypes.get_last_error()
        raise OSError(f"{what}: {_WININET_ERRORS.get(code, '윈도우 오류')} ({code})")

    headers = dict(headers or {})
    ua = headers.pop("User-Agent", "Mozilla/5.0")
    sp = urlsplit(url)
    https = sp.scheme == "https"
    path = (sp.path or "/") + ("?" + sp.query if sp.query else "")
    handles = []
    try:
        h = wi.InternetOpenW(ua, 0, None, None, 0)          # 0 = 윈도우 인터넷 설정(프록시 포함) 그대로
        if not h:
            fail("인터넷 시작 실패")
        handles.append(h)
        ms = wintypes.DWORD(int(timeout * 1000))
        for opt in (2, 5, 6):                               # 연결·보내기·받기 시간 제한
            wi.InternetSetOptionW(h, opt, ctypes.byref(ms), 4)
        c = wi.InternetConnectW(h, sp.hostname, sp.port or (443 if https else 80), None, None, 3, 0, 0)
        if not c:
            fail("연결 실패")
        handles.append(c)
        flags = 0x80000000 | 0x04000000 | 0x00000200 | (0x00800000 if https else 0)   # 새로 받기·캐시 안 씀·창 없음·SSL
        r = wi.HttpOpenRequestW(c, method, path, None, None, None, flags, 0)
        if not r:
            fail("요청 실패")
        handles.append(r)
        hdr = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
        body = data or b""
        buf = ctypes.create_string_buffer(body, len(body)) if body else None
        if not wi.HttpSendRequestW(r, hdr or None, len(hdr), buf, len(body)):
            fail("보내기 실패")
        status, n = wintypes.DWORD(0), wintypes.DWORD(4)
        if wi.HttpQueryInfoW(r, 19 | 0x20000000, ctypes.byref(status), ctypes.byref(n), None) and status.value >= 400:
            raise NetHTTPError(status.value)
        out = bytearray()
        chunk = ctypes.create_string_buffer(65536)
        got = wintypes.DWORD(0)
        while len(out) <= limit:
            if not wi.InternetReadFile(r, chunk, 65536, ctypes.byref(got)):
                fail("받기 실패")
            if got.value == 0:
                break
            out += chunk.raw[:got.value]
        return bytes(out)
    finally:
        for x in reversed(handles):
            wi.InternetCloseHandle(x)


def net_request(url, method="GET", headers=None, data=None, limit=2 * 1024 * 1024, timeout=10):
    """인터넷에서 받기(또는 보내기) → 받은 내용(bytes). 서버가 오류(4xx·5xx)를 주면 NetHTTPError"""
    import urllib.request
    import urllib.error
    try:
        req = urllib.request.Request(url, data=data, method=method, headers=dict(headers or {}))
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(limit + 1)
    except urllib.error.HTTPError as e:
        raise NetHTTPError(e.code)
    except Exception as e1:
        if sys.platform != "win32":
            raise
        try:
            return _wininet_request(url, method, headers, data, limit, timeout)
        except NetHTTPError:
            raise
        except Exception as e2:
            raise OSError(f"{e2}  [기본 방식: {str(e1)[:80]}]")


def net_error_text(e):
    """사용자에게 보여 줄 짧은 설명"""
    if isinstance(e, NetHTTPError):
        if e.code == 403:
            return "확인 횟수 제한(잠시 뒤 다시 시도)"
        if e.code == 404:
            return "릴리스를 찾지 못함"
        return f"서버 오류 (HTTP {e.code})"
    return str(e)[:220]


def stats_call(url, method, body):
    """Firebase REST 호출 한 번. 실패하면 예외 — 부르는 쪽에서 조용히 넘깁니다."""
    net_request(url, method, {"Content-Type": "application/json", "User-Agent": f"smartpdfeditor/{APP_VER}"},
                json.dumps(body).encode("utf-8"), limit=4096, timeout=8)
AD_CACHE = os.path.join(CONF_DIR, "ad_cache")            # 인터넷이 안 될 때 마지막 광고 사용
AD_REFRESH_MS = 3 * 60 * 60 * 1000                       # 3시간마다 새로 확인
APP_VER = "1.0.18"

# 스마트공 로고 (PNG, base64 내장)
LOGO_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAGkAAAAcCAYAAABibZFIAAAVqUlEQVR42oWaaYxk13Xff+fe915VV3V39fSs5PRwE8VF3CQuIGXa"
    "cWTJiiLA8pIYEuIYTmIoCeIgXhIgCBDlg4F8SGJng5MASfhBUGJAgIVIijcZkQMJVCiJNikpEknJorjNDGfr6bWq3nv33nPy4b6q"
    "rm4O4wYKr7qq3n33nvV//ufIc5dbY+Hv0D9Hv5CDq73tD9/6Y7vRAhhmYKLzh9r8uz9nycV9dnuZ3yUy+xhB8j7lrff/Ocv//89j"
    "lp8zv954Bcs7mH9ipPnvBHforItLzj/ubizmB+t+JQsPNOxga7O9yCFZ3Fj8Jt2bfBUO3pvNhOjpOY9z+XvX3W9H1nzbhwDSHYzu"
    "qpaPoUA0I5mSJHHweAGxGypEug/FDit+JlLj4PAiR4QgM4XQSWxxzSxTwyhkgO/WTgZKs7Bm9yQ5OKBJXrWQBRs+vG17O5t+i9SE"
    "ToNinRIObGhuzViWFIYTodU9LtZvsJu2qVNLQnGUeApE3NwXrLvSKV8RBCEZJMmHjaYoUIinkoqeL1nxA9bLFZbdAOZGcNhPDilE"
    "7ODENvN/WbhycJ4bRAV5W4s9OPP18EWatImXgpXyQfpyG4mw8HM3X8QWokshnQzyegc2s6iyRWUdWKDc+Fuhs4juiEL3aJlHBRHB"
    "SNS6y1a4yE7c5lp7iathk+24zW5oaZKiOMBjVqAmKB6jQPD4osegXGalGLFSrHK8HDGQZVbKIWsypPKOxAC3aJlz1d9oy3LkjIKg"
    "2IJKsnR0rtyZ3WVPOSwOEZm7ueDYS8/wjeu/xH56lVODx3h39R/nz/ayhFnCiN0Sgi6E/2LRTuaKsoNw58jhQw4ZimFmnbDlUJ6a"
    "ufOh0LoQW0QENaPn17h3+Une1f2o1gnbYYtx2qfWhmA1rQVCMtQME6GQkspXFJQ4Kem7PkO/xHKxxKofgHmkM4pkEEyJFg959YEf"
    "CCZ22PIWQ7oZRoXgFvIdc1s/pO3uPreQXxIR1ZhlJA0vjj/FldpY8o9yx9I/ZegeoLUW2GQnfJlSNhgUT2KWFiJRfkSR99P5hi0G"
    "PUMMVA7Ha8OBE0AxBDXFkcPc7DozMcUQkwWbmCVyQVWpLS1YXo8T5VlOV3n52R7UbC5gLy4/2iBazkGKklSZpgTEQxFbOvM7CEf2"
    "thDJFvZu6nBun0Y/x1bzEmoFraacR0xJZqhmGKAoUROpMybF4ehx0/Bhzg4+SCHHuFB/hT/b+Q6tLPHQ6GOc6v0IaoraS7w6/efs"
    "tH9Cz93GfatPYXY2u8ViuDvipYcTamc5OocfnmP1n7K684dI3EF7p9gafYS98p05NGh3g0nn6dJhkiwuT6TiGpImczFlqxMUh4rQ"
    "mificG6ZgkEWr8CmtHw3tNTmuMNV3Cq+U70DMZwJU3FMjLmBzOK6WjaO/LK5p2PggZ6HtZ7gZkKWwNX2t3hz/EnqCE2CaEJQIaoQ"
    "FZIJJoKaENVI2p3DBKPghd0/5kTv9/iRM/+YvjuNj2e4bflO7ln5eUR6XA2/y6v7/4795s9wPlFVFSLLc//RRdjyjSuHIbi+FURl"
    "e7GS1fYlbnn9l6nGL2Cuj0hDM/ohXrnpXzIuzuEsYuLeklANoWLKLfV/YXn/81gyzBwBRy099qXPnh+w41bY9utctxXq4iTnlv4C"
    "J+R2rrvAH8RtxtFTp5KYSj7cL7mvdLSaPe8Nc3yxdlxrIEWhDUYTISShbY0mCU0w2gBt931MQkzZ6z96e+Kv3aZ4cShTfrD/MS5N"
    "vknQJVoVgjqSeqIJyYSEgAmGI2k2hITDgKSOqDBlwntP/i3eu/53iZYQPEjgpd1P8d3xU3gZM3QjTvce5J7Vf0Iht2Km89RhhyD4"
    "If+RQxAcBSEiRcX65v+g2v42RgkSMeeodr/N8NgL7I9ug9iAuCNLKUqP9fA0y9ufA50iVpDME6iYOs/Ul4zpsceAHe2xz5DrUZg2"
    "Fxj1b+Z8Suy1Qh09TXRcb+Gyg3sKoXDG2OCPJo5rLaQA005BKUJM0Aah7a4hGCEYMQopgSmkBJ/+nueBVfjh08puqBiVP8Gmu0Y0"
    "zUAFj4hDTTHnMtRXBQoKcRlpaqJNkaCGScEkRLbb6yiByo1odZenN/89//f677LkPbcMH+Jdo49yc+9DqBUdcMgFiZjNS58i56PF"
    "gqvLBvM8FYluwLHx8yxf+iw6nWZ0IGC+wKUdRltfYGvww7TSw2nEzM2T7wy4+voNSIbFgqQFDQVTCiYijIuCffrs+RX2WWFfhkxs"
    "GTVoq0QwoQmOSetoo6NuHW0/5wOnoAjXaiNGqFuoQ/aarUYI0QjRqFshRsuKikYMoMkwFSwqd6/DemW0KeemE9XPU67eSa27aHJd"
    "EQsiSyAQU0AoiUSStRiOabzOl6/9d6ZWo1Zmz4+CWsJQktZsNpsMyzu4e/kRHl3/6wz9GVrNXpbzYpPzvR2kg2Je6FmH7NSweY2W"
    "wFcMwiVOff9fUO68hMkgm6vvijRfsHrlM9xc3cprZ34F0wgkRHzGDzOcqYa1CVOI6mhxNP44bXGK4IdEt0yjBQ19Aj2C9iisxExI"
    "KjTJ0yQhxqyoqLNiNguvDkZohToIdcjJ9qM3Kcs+e1NMlmur2OWkLo9gRkhwz5py24rRKDjJ6Xq9+sAh6O4ELk+/wqXpnxI00C/W"
    "uXX5x1kpNjCDyB5fvPwZag2YeiZWEK0AcxiJ0q3xgVO/TKs1tw3uZT9ss9W+gNmUsriCszVKHsJwcx28PQTHch4qlhhMzrPxwq8w"
    "vPpH3c0t4hyYB1PElGSeY5c+idN9zt/0D2llANYeABIBSwatoeaIXXJt1j5EPXo/zlqWiby58yXaaLRa0lpBSYmQk3UdPG3wxOio"
    "W0FVKFzOoaowaYXYeVAdBA9cnBh9gaj5NwmZe0+GakLCWKngxHIOnSGCc+DMiDbJkcUMpGAavsuzl3+di/WLKCXBEo+d2OSR438f"
    "M6O1PabimGoO52MTkhuAFF2hnxgVG7y8+xV+Z/O3GZZTVC9SyTa94iqVO81tg0+wUj6GWY118L+YhTaDzosEEUHEc+L85zn9/X9N"
    "tfk0uArzDnEKPisIq3Jxh4d6m2NvfpIibXLt2M+yM3wcXcx+ChYkoyA1zDlScZbY38ClRMmUVvu0IRKoaLWi7zxmENTRBE8bC5rW"
    "E6Lj0lR4tYZb+prrrBZCBwyaLhd9dkdokxAjJM3epMmRIpmuMANz4OB728avPWAc7yvRZqVrMSerHBXjdIWxBgp3FuhTt1tM2n28"
    "GMkcPbfGI+sf5Nmtp9mJY945eICHRk9SSA+1RCEVu/ESX9r5NK/vP8vJsmDoW5Z9pPQNK+Uytw1zHWlHIfisLlMnFHHKaO8lTj3z"
    "j6h2nsPZGPUl4hVRRZwRh/cy3fgJll/5zxAjIgUWC8yElct/wOD607Sjh7m88Wtsc64j08BaQzuO0ZwhGhFThJakiZB6NLGgpUeI"
    "PcxViAgxZSXlvCRoEL58TXhmU7h/1fFzG5FpA7FDbUEhJMOb0BcjSfaYhKBimBfM5ZM7gVaNN6ewF+GMCCEptV2lTWMMQwFPyVZ9"
    "mak6psnAEo169rXhSv0aUXOWv2/5fdzaf5igib5fYuBXeHP6GsvVKit+xNAf49G1D7Ps1zhdrXOmv8bZpTOsVjcxDacp5DgQkXmJ"
    "IQue5DxLu69w7uufYPDK/0Rsgjqw0uViNkXEJeJNT/D6g7/J7tpj3Fyd5uT3/1VGdd4DLoOENKYfnmFj9+MMzvwCF07/Ys5JsauO"
    "1TKxqh2r1pX5IfVoVQlWEVNBTDmvqQp1cNRBaKMQAzRJaBUmDTwycrQR2gAxQNBcrp3uGd4gFdp58KzGOGAaVGG1Bx+73Ti3rDRa"
    "can5HM9f+y324w4xZfit4jHzBIOkJckEJyt85/pX+db1r5PEkXBEHDHlkN6a0YrSJOWmpXN8/PZfZaP/Th5Y+SD3Lf8YgsNLRnMa"
    "HZWQQYYsUv2zYtYUej2Ov/x5lr/5aVLlwXkoHRYN3wbS0hLjWz/CxXf/OuPhnZBaLt7y92gHt3P65d+gmvwAjS3GENUCtRLShOWt"
    "r1Kt/yTJyiw9c5Ash02TOYIxhGA9ohpRK2Iq0ZiTbhszIGiDJ4aspJTyjftRQKFtsxelJATLxenfvjNxspcBg3S51onN35vkYjYJ"
    "jFymwLyH7+/8IVv1FkkqkgrRHAnBtFOCGaoQuyI8SWbdA0o0pTWhNQgIIQoB4XuT8zy9+WV+buNukkUcJUbeW857ocMDB+TvYQiu"
    "mjmvegerQaslJNa4aUCWoD59P5v3/x2uveMXiL4PqcnUTmy4fOzHmTz4Lk6ff4rBpS9Q1ldQhFSOwGqaY+tEN4AYUBUsGTLvKWin"
    "pMwFBu3RJCNYRUglQT1mSohZCTFlmJ2S4EwpTHjypHL3cmIaBa+G5lOzPYXffFEonSwQqIZzOec6b4iDohDGCe5fMT6+EThZGmvV"
    "fbzCdxiHGhNPMiV2fFwwB1R4V2CSQ3wyo9bIlJagRqtCY0KjjtagMRj11rl7eG9HB1lGzovsjh1hv49CcHFCagLX7/gIo5c+Q/n6"
    "C7Di2X/XX2Xv9MPs3f5h9k4+BM0ULM0LVhFBLLHbO8f0jk+wvPZ+hjvfYNi8xqB5g73hXVw587MEv5zzTzIkE14417UjugpbTUha"
    "5UNaRZ1KWi2yMSQhxmyVloQ6wgdOKU+cMJ44ma343qHyzCXHamF4yR46DVC7jgg2w5wgLjeKnAnShVwR+Mp1+ItrnrPHI3eNPsbA"
    "n2U/bWWEZQVVMcCsoPBTttvzbLbXmKYWNegXq5zon6HHTdTJESQyTQ3TGFAnpGScGtzMo+tPEJPOiV4W6d4jDS2VA/BfYIaJx4fI"
    "/qn38OqHnqJ36Tl0eJLprT/KZOkUliKu3secP6Rx6Xgxpy3JhK3j72P7+PtYipsstReY9s4xleUuGWS8nAGfp7WCJCXiHEXyqIPW"
    "ejRqNNqjSRVBK9QyKmubfFgMQoC7luEv3Wxst9AT42/cqoxr4cVtY5zAu/xIJ+C8dmy9dTLoCvUuP4kID68YG32jjkolI+5d+xnM"
    "lNJ59uJ5Xtl9msvTl8GN2QtX2Wp2maQGFY/320zDPk62KGTIHSv38J6Vx7m5f5Y6Bbx4DGEcp7h59/RGxK/NaTixg6ZrMePZVTyi"
    "ib2zT7B/6xOYgmtqynYvM9/eL/R5Z0HzoH+EKJb2ESDIgHrpPkQDkgKpKDAVtKODGt9jYj3CtecJybFdHOOK9tluhForpqmi0T6N"
    "9TDzOS9ER0q5TCAJdRL2wmwrwl0rxj97IHFxAo12cX2BRpz132yxfdJdC4GzPeNEBSEBkqjjGBHhpZ3f5+vXPsVuuM5ue53WBNUK"
    "lQJ1ntaEaTKmMdESMSsYFsdZqY7z0XO/yKOrP8pe3MNLgVugzOygB3q4bX6kDW7McpIJnsD6K59ndOELZPowZZjsLUOl2QsHrsgS"
    "EN/978EVmPMkKQmuonZ96uoYzepD2OgJ1BxBC1oqGpaY+AE7W29weU+5WJ7lgruZfVujtj7T1GOSekxiMWcJYlA0dg0xVQTriBTh"
    "2V3h5WkubgvJXqQ5F+d2RupqVxNUc9LPrEOWljfhuQi3rxrvPQ2FQSEDttvv8n+uPsVWfRXoUboTOBOUitHSSYbVOtMUuDC5Coxx"
    "CsFgJ7a82bzGf3jlP/EP3jHgPcuP0mo718S8ITRrjSy0d2ZXW2z6oQrlEse//d84879+CSna3Ft3YEXna4XLJ3dFp5AScyX4MuN5"
    "KRBfoUWP4PuEYpVUrlFXa4zH15BqAytHBCtoXMnUDdljhW1G7Ngy26HPvi+pqZhaRa0V+6EiUs042o4MzQ3m7JWZzP+T68JvvOww"
    "yfFcXL4mk6wchRgz6kspw3ntiFVTw5JAAo8QEvzqg8pP3q6YtLw2/hqX9y/QK9dpk9Jq5NETf5knT/1NSreK77pqSRNXww/4ty//"
    "G85PrxCtQqXHy+OrPL/1Le4bPLg4fnOoebrYLhfpgMNRCK7O4cOE3pVvQdMSXQ9HQo357IKaA3WIywrBF4grQQvMZ6UlqYixR8uA"
    "Rpao/YD9tMpW22fYTpkeezd+eI52us3ECvZkiV1ZZksH7MgSu9pj2yrGVjG2kqgl71gWhkUmSDVlZIgZ2sFuB3zhgtDU2atc7rZ3"
    "Ht8x+NHwqaOlFFzqqKHUeVPKL4ehrfClV40f24C1XqLRliAVJE+boI6R9d47cJQ5H+MwNZwopT8Jssq+bZLMo+ZprGWiATPFiUdN"
    "jzSADs0LHfGoxUEUVdSVxKVTuGAY9UGa8Z0ndVQdDpzLSsKXWNG9dxXmE9FBW5XUGpkIbCNMl06yUqyyM7yJdOfHYe+VXJa5ZVZY"
    "QRkykFVOMWRsS9RakigZlI7HTxo9lwlQYm7soWSEmLJV3j8y/vfrjjYZzmeaLNtWPrSqkGIX4nJB0xF+naWmzlW7zx48bvS9AhWn"
    "+nejDJmqoJQk7/j06/+Ve0bPMarOkcTTJKit4bndb/OD8SVUCrDcd3JSsdG/mdKVtBo5PPRzo0kzu/EgiuaGEZvv/GmK/Qv0rr3Y"
    "tWQFKTzMXt5nbfmu0C1mIS8rKbmK4Hu0fkDyK1CM6JXH6I/uord0DE01O8cfw514FMxYwugDZxZ55oVhPueUkHJX9N41xanj2ji3"
    "rdf7wsZQSaZ86KyxXzuuTHIpkQt46xj4g9wzv6aFQYROP9K14k/0hZ++S6m80WrgdO8+Hj/5V/jjq59lHBOlDIgiPLPzPFGfozVH"
    "rTAxwVwfkx4GjGMNmvipsx/kh9YeJ2rsyCU5PJ6wMIM0nxnpRutm9SMiyNcv7BsY6irKVFPtv4mp5RwkkhXj/MHQyawwnI1dOde1"
    "I6TD94JZboWblCQpwFInEz3cvjg8YNX1sOQtc3fJ4KuXhG9dyazwgyeUR84YfZ8doe+NkOTISNONpiKPNDc7pDqzjV6RjSLNR7o8"
    "Tdrl5ck3+cbWl3hm61l2NSGupFGhSUZjmVEI3awfSXl47V4+fOr9PDF6lPVinaBtrguPzPTp246CdlFgNjzztfN7dqiodCWHxipZ"
    "gInzBNdpeR5DZ0+zbq7B5p16urGug7kHm43ozRG82Q2GK2YwWXNCLT2MQ+5hLVWW2w9d7NbOCmfDMwezdIuKtyMTpYeDjMPQbu/S"
    "DTR21R2Fq9gJV3ijfo3tsM31sMVOO6GxSJI8vbHk+oyqEWt+xB2DDTb6G7QpoaQ8T3cEbs/OP5PnYcPM7RSVPMgjX3tjb0E0Nhfi"
    "3CFnupC3MVCO6Ojg1HlSaKZ/OZhQvVGz/i0zlwtjTQpdgpZugigHCpGD6bhDg5rceErVju75SI0ixg2SupHM8FJQuhKzQKuRROrC"
    "0Wxo2FFKQUFBFKVNIVNQCyNvarlD9HZj14tXtYNT/D+ipqhACDx3PgAAAABJRU5ErkJggg=="
)

# 사용방법 (도움말 창: 왼쪽 목차 → 오른쪽 내용)
# 항목: "글"            → 점(•) 줄
#       ("키", 단축키, 설명) → 단축키 표 한 줄
#       ("소", 글)        → 작은 제목
#       ("주", 글)        → 알아두기(회색)
HELP_SECTIONS = [
    ("PDF 연결하기", "pdf", [
        "PDF 파일을 더블클릭했을 때 스마트PDF Editor로 열리게 하는 방법입니다. (처음 한 번만 하면 됩니다)",
        ("주", "먼저 smartpdfeditor.exe 를 계속 둘 폴더(예: 문서 폴더)에 옮겨 두세요. 연결한 뒤에 exe를 옮기면 연결이 끊어집니다."),
        ("소", "방법 1 — PDF 파일에서 바로 (가장 쉬움)"),
        "① 아무 PDF 파일이나 마우스 오른쪽 클릭 → [연결 프로그램] → [다른 앱 선택]",
        "② 목록에 '스마트PDF Editor'가 있으면 고르고, 없으면 맨 아래 [PC에서 앱 선택] (Windows 10: [이 PC에서 다른 앱 찾기])",
        "③ smartpdfeditor.exe 를 찾아 [열기]",
        "④ Windows 11: [항상] 클릭  /  Windows 10: '항상 이 앱을 사용하여 .pdf 파일 열기' 체크 → [확인]",
        ("소", "방법 2 — Windows 설정에서"),
        "[시작] → [설정] → [앱] → [기본 앱] → 위쪽 검색칸에 .pdf 입력",
        "→ 지금 연결된 앱(예: Microsoft Edge)을 누르고 → 스마트PDF Editor 선택 (목록에 없으면 [PC에서 앱 선택]으로 exe 지정)",
        ("주", "Windows 업데이트 뒤에 Edge로 되돌아가면 위 방법으로 다시 연결하세요."),
        ("주", "연결한 뒤 탐색기에서 PDF를 열면, 이미 켜진 창의 새 탭으로 열립니다. (환경설정에서 '새 창'으로 바꿀 수 있음)"),
    ]),
    ("시작하기", "open", [
        ("소", "파일 열기"),
        "[열기] 또는 Ctrl+O — 여러 파일을 한꺼번에 고르면 탭으로 각각 열립니다.",
        "탐색기에서 PDF를 더블클릭하면 이미 켜진 창의 새 탭으로 열립니다. (설정에서 '새 창'으로 바꿀 수 있음)",
        "PDF 파일을 smartpdfeditor.exe 아이콘 위로 끌어다 놓아도 열립니다.",
        "다시 열면 마지막으로 보던 쪽에서 이어집니다.",
        ("소", "저장 · 되돌리기"),
        "Ctrl+S — 지금 파일에 바로 저장합니다. (덮어쓰기)",
        "Ctrl+P — 인쇄. Windows 인쇄 창에서 프린터·쪽 범위·매수를 고릅니다. 고친 글자·메모·색칠도 화면에 보이는 그대로 인쇄되고, 가로 쪽은 돌려서 종이에 맞춥니다.",
        "Ctrl+Shift+S — 다른 이름으로 저장. 원본을 남기고 싶으면 이것으로 새 이름을 정하세요. 저장한 뒤 탭은 새 파일을 가리킵니다.",
        "Ctrl+Z — 되돌리기 (최근 30번까지). 저장하지 않은 탭 이름 앞에는 ● 표시가 붙습니다.",
    ]),
    ("화면 구성", "m_view", [
        "위 도구줄 — 열기·저장·되돌리기 | 쪽 이동 | 확대·축소 | 회전 | 편집 도구 | 오른쪽: 뷰어/편집 전환 · 사용방법 · 스마트공",
        "왼쪽 사이드바 (F9로 숨기기) — 즐겨찾기 · 북마크 · 검색 · 최근, 맨 아래 광고 칸(광고가 없으면 접힘)",
        "아래 상태줄 — 왼쪽: 지금 할 수 있는 일 안내 / 오른쪽: 맞춤(↔ ↕)과 보기 방식 아이콘",
        "창이 좁으면 도구 버튼이 둘째 줄로 내려가서 잘리지 않습니다.",
        "모든 대화상자는 누른 메뉴·버튼 가까이에 뜹니다.",
    ]),
    ("보기 · 쪽 이동", "v_cont", [
        ("소", "보기 방식 (아래 상태줄 오른쪽 아이콘)"),
        "한 쪽씩 · 연속 스크롤 · 2쪽 · 3쪽 · 4쪽 나란히",
        ("소", "맞춤 · 확대"),
        ("키", "Ctrl+1  /  Ctrl+2", "가로맞춤(폭에 맞춤)  /  세로맞춤(한 쪽 전체)"),
        ("키", "Ctrl+휠  ·  Ctrl + / -", "확대 · 축소"),
        ("키", "Ctrl+0", "실제 크기 100%"),
        ("소", "쪽 이동"),
        ("키", "마우스 휠", "위아래로 이어서 스크롤 ([보기] 메뉴에서 '휠 한 칸에 한 쪽씩'도 가능)"),
        ("키", "PgUp / PgDn · Home / End", "이전·다음 쪽 · 첫 쪽·마지막 쪽"),
        ("키", "Ctrl+G", "쪽 번호 입력해서 이동"),
        ("키", "휠 버튼(가운데) 끌기 · Shift+휠", "화면 이리저리 옮기기 · 가로 스크롤"),
    ]),
    ("뷰어 모드 / 편집 모드", "m_edit", [
        "오른쪽 위 [뷰어] [편집] 버튼 또는 F4로 바꿉니다. 시작할 때의 모드는 [설정 → 환경설정]에서 정합니다.",
        ("소", "👁 뷰어 모드 — 편하게 읽기"),
        "글자 위를 끌면 선택됩니다 → Ctrl+C 복사 · Ctrl+B 그 글자로 북마크 · Ctrl+F 그 글자 찾기",
        "오른쪽 클릭 메뉴: 복사 · 북마크 추가 · 선택한 글자 색칠 · 쪽 회전 · 쪽 캡쳐",
        ("소", "✎ 편집 모드 — 고치기"),
        "위 도구줄의 도구(수정·색칠·감추기·도형·메모·지우개·캡쳐)를 골라 씁니다.",
        "뷰어 모드에서 도구 버튼을 누르면 자동으로 편집 모드가 됩니다. Esc = 글자 수정 도구로.",
    ]),
    ("편집 도구", "t_edit", [
        ("소", "수정 — 글자 고치기"),
        "글자를 클릭 → 새 글자 입력 → Enter. 글자 크기·굵게도 바꿀 수 있습니다.",
        "[편집] 메뉴: 줄 단위/조각 단위, 새 글자가 길면 글자 크기 줄이기.  Ctrl+H 찾아 바꾸기",
        ("소", "색칠 — 형광펜"),
        "글자를 클릭하거나 영역을 끌어서 칠합니다.",
        "색: 빠른 색 4가지 · [색상표 ▾] 24가지 · '다른 색 직접 고르기'",
        ("소", "감추기 — 개인정보 가리기"),
        "영역을 끌면 아래 글자·그림을 실제로 지우고 검정(또는 흰색)으로 덮습니다. 복사·검색해도 안 나옵니다.",
        ("소", "도형"),
        "사각형 · 원(항상 정원) · 타원 · 삼각형 · 선 · 화살표 — 끌어서 그리기 (Shift: 정사각형·45° 선)",
        "선 색 · 두께 · 채우기(없음/반투명/채움)는 도구줄 옆과 [도구 → 도형]에서 고릅니다.",
        ("소", "메모"),
        "누른 곳에 주황 점이 찍히고, 그 옆에 노란 글상자로 내용이 붙어 점선으로 이어집니다.",
        "상자를 끌어 옮겨도 원래 위치와의 연결은 유지됩니다. 상자를 클릭하면 고치기·삭제.",
        "메모 내용은 본문에 보이고 검색도 됩니다. [도구 → 메모]에서 '아이콘 + 오른쪽 쪽지' 방식도 고를 수 있습니다.",
        ("소", "지우개"),
        "색칠·도형·메모를 클릭하면 지워집니다. (글자 수정·감추기는 Ctrl+Z로 되돌리기)",
        ("소", "캡쳐 (Ctrl+Shift+C)"),
        "영역을 끌면 그 부분이, 그냥 클릭하면 쪽 전체가 클립보드로 복사됩니다 → 한글·카톡 등에서 Ctrl+V",
        "미리보기 창에서 그림 파일(PNG/JPG)로 저장. 해상도는 [도구 → 캡쳐]에서 (기본 200dpi).",
    ]),
    ("쪽(페이지) 다루기", "rot_r", [
        ("키", "Ctrl+L  /  Ctrl+R", "지금 쪽 왼쪽 / 오른쪽으로 회전"),
        ("키", "도구줄 겹친 쪽 아이콘", "여러 쪽 골라서 회전 · 전체 쪽 회전 ([페이지] 메뉴: 왼쪽·180°)"),
        ("키", "Ctrl+E", "원하는 쪽만 새 PDF로 저장 — 예) 7, 2, 10-12  /  8- (8쪽부터 끝까지)"),
    ]),
    ("찾기", "find", [
        ("키", "Ctrl+F", "이 파일에서 찾기 — 찾은 곳 목록이 나오고 첫 곳으로 이동해 파랗게 표시"),
        ("키", "Enter · F3  /  Shift+F3", "다음 찾은 곳  /  이전 찾은 곳"),
        ("키", "Ctrl+Shift+F", "폴더에서 PDF 찾기 — 파일 이름·본문으로, 하위 폴더까지"),
        ("키", "Ctrl+H", "찾아 바꾸기"),
        "폴더 검색 결과는 [목록 저장]으로 즐겨찾기·북마크 폴더에 넣어 둘 수 있습니다.",
    ]),
    ("탭 · 새 창", "plus", [
        "탭이 많아 다 보이지 않으면 탭 막대 양옆에 ◀ ▶ 가 생깁니다. 눌러서(또는 탭 위에서 마우스 휠) 옆으로 넘기고, ▾ 를 누르면 열린 탭 목록에서 바로 고를 수 있습니다.",
        "여러 파일을 탭으로 엽니다. 탭 이름의 × 또는 휠 버튼 클릭 · Ctrl+W 로 닫기",
        ("키", "Ctrl+Tab", "다음 탭"),
        ("키", "Ctrl+N  ·  Ctrl+Shift+O", "새 창  ·  새 창으로 열기"),
        "탭을 오른쪽 클릭: 다른 탭 모두 닫기 · 이 탭을 새 창으로 옮기기 · 파일 위치 열기",
    ]),
    ("즐겨찾기·북마크·최근", "star", [
        ("키", "Ctrl+D", "지금 파일을 즐겨찾기에 추가"),
        ("키", "Ctrl+B", "북마크 추가 — 글자를 선택해 두면 묻지 않고 그 글자 이름으로, 그 위치로 바로 추가"),
        "더블클릭하면 열기(북마크는 그 쪽·그 위치로). 폴더를 만들고 끌어서 정리합니다.",
        "북마크는 파일마다 따로 — 북마크 탭에는 지금 보고 있는 파일의 북마크만 보이고, 다른 탭(파일)을 고르면 그 파일 것으로 바뀝니다. 위쪽 '모든 파일'을 체크하면 전체가 보입니다.",
        "줄 끝 × 로 바로 삭제 · 오른쪽 클릭: 열기 · 이름 바꾸기(F2) · 삭제 · 새 폴더",
        "Ctrl·Shift+클릭으로 여러 개 골라 Delete로 한꺼번에 삭제, Ctrl+A 전체 선택",
        "목록 위 🔍 칸(즐겨찾기 검색 · 북마크 검색 · 최근파일 검색)에 입력하면 이름·경로(북마크는 쪽 번호도)로 바로 걸러 보입니다. Esc로 지우기",
        "[최근] 탭(맨 오른쪽): 최근 본 파일 200개 · 마지막으로 본 쪽 · 열어본 시각 — 🔍 칸으로 파일 이름·날짜 찾기",
        ("주", "모두 자동으로 저장됩니다: %APPDATA%\\smartpdfeditor\\settings.json  (파일은 경로만 기억하므로 옮기면 회색으로 표시)"),
    ]),
    ("설정·화면 꾸미기", "gear", [
        ("소", "[설정 → 테마]"),
        "스마트클립(주황) · 기본(회색) · 밝게 · 어둡게 — 색은 위 도구줄에만 (어둡게는 화면 전체)",
        ("소", "[설정 → 환경설정]"),
        "일반: 즐겨찾기·북마크·최근 파일 개수, 휠 한 칸에 한 쪽, 시작 모드, 탐색기에서 열 때 새 탭/새 창",
        "화면 꾸미기: 글꼴 · 글자 크기 · 글자/바탕/강조/문서 배경 색 · 배경 그림 ([미리 보기]로 확인)",
        ("소", "다른 PC로 옮기기"),
        "[설정 → 설정 내보내기]로 json 파일을 만들고, 새 PC에서 [설정 가져오기] (합치기 또는 덮어쓰기)",
    ]),
    ("단축키 한눈에", "help", [
        ("키", "Ctrl+O · Ctrl+S · Ctrl+Z", "열기 · 저장 · 되돌리기"),
        ("키", "Ctrl+W · Ctrl+Tab · Ctrl+N", "탭 닫기 · 다음 탭 · 새 창"),
        ("키", "F4 · F9 · F1", "뷰어/편집 전환 · 사이드바 · 사용방법"),
        ("키", "Ctrl+F · F3 · Ctrl+H", "찾기 · 다음 찾기 · 찾아 바꾸기"),
        ("키", "Ctrl+Shift+F", "폴더에서 PDF 찾기"),
        ("키", "Ctrl+C · Ctrl+Shift+C", "선택한 글자 복사 · 캡쳐 도구"),
        ("키", "Ctrl+D · Ctrl+B", "즐겨찾기 · 북마크 추가"),
        ("키", "Ctrl+L · Ctrl+R · Ctrl+E", "왼쪽 회전 · 오른쪽 회전 · 원하는 쪽만 저장"),
        ("키", "Ctrl+1 · Ctrl+2 · Ctrl+0", "가로맞춤 · 세로맞춤 · 100%"),
        ("키", "PgUp · PgDn · Home · End · Ctrl+G", "쪽 이동"),
        ("키", "Esc", "글자 수정 도구로 · 창 닫기"),
    ]),
    ("알아두기", "pdf", [
        "스캔한(그림으로 된) PDF는 글자 정보가 없어 글자 수정·찾기가 되지 않습니다.",
        "수정한 글자는 맑은 고딕으로 다시 써집니다(원래 글꼴과 모양이 조금 다를 수 있음).",
        "감추기로 지운 내용은 저장하면 되살릴 수 없습니다. 원본은 따로 남겨 두세요.",
        "메모의 주황 점·점선은 이 프로그램에서만 보입니다(다른 뷰어에서는 노란 메모 상자만).",
        "이 프로그램은 AGPL-3.0 오픈소스입니다 — 소스: github.com/nunco-git/smartpdfeditor  ([도움말 → 정보])",
        "설치 수 통계로 하루 한 번 무작위 번호와 버전만 보냅니다 — 끄기: [환경설정 → 일반 → 사용 통계 보내지 않기]",
        "더 많은 업무 도구는 smartgong.kr 에서 만나보세요.",
    ]),
]
IPC_PORT = 48517          # 프로그램 하나만 실행: 두 번째 실행은 이 포트로 파일을 넘기고 종료
IPC_TOKEN = "PDFTE-1"
SEARCH_MAX = 3000
SHAPES = ("사각형", "원", "타원", "삼각형", "선", "화살표")
BOX_SHAPES = ("사각형", "원", "타원", "삼각형")      # 영역을 끌어서 그리는 도형
TOOLS = [("edit", "✎ 글자수정"), ("mark", "🖍 색칠"), ("hide", "■ 감추기"), ("shape", "◻ 도형"),
         ("memo", "💬 메모"), ("erase", "⌫ 지우개"), ("capture", "✂ 캡쳐")]
TOOL_LABEL = dict(TOOLS)
LIMIT_DEFAULTS = {"fav_max": 100, "bm_max": 200, "recent_max": 200}
MEMO_FILL = (1, 0.97, 0.77)        # 본문 메모 상자 바탕 (연한 노랑)
MEMO_TEXT = (0.24, 0.16, 0.0)      # 본문 메모 글자 (진한 갈색)
MEMO_FS = 10                       # 본문 메모 글자 크기(pt)
MEMO_BOX_W = 180                   # 본문 메모 상자 폭(pt)
ANCHOR_TAG = "memo-anchor:"        # 메모를 붙인 원래 위치를 주석의 subject 에 기록


def parse_anchor(subject):
    """'memo-anchor:x,y' → fitz.Point (없으면 None)"""
    if subject and subject.startswith(ANCHOR_TAG):
        try:
            x, y = (float(v) for v in subject[len(ANCHOR_TAG):].split(","))
            return fitz.Point(x, y)
        except ValueError:
            return None
    return None
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
class FilterBox(ttk.Frame):
    """목록 위 검색칸: 입력하는 대로 이름·경로로 걸러 보임 (Esc = 지우기)"""

    def __init__(self, master, on_change, hint="이름·경로로 찾기", title="검색"):
        super().__init__(master)
        self.var = tk.StringVar()
        top = ttk.Frame(self)                              # 무엇을 찾는 칸인지 이름을 보여 줌
        top.pack(fill="x")
        lbl = ttk.Label(top, text="🔍 " + title, cursor="xterm")
        lbl.pack(side="left")
        self.count = ttk.Label(top, foreground="#666")
        self.count.pack(side="right")
        row = ttk.Frame(self)
        row.pack(fill="x", pady=(1, 0))
        self.entry = ttk.Entry(row, textvariable=self.var)
        self.entry.pack(side="left", fill="x", expand=True)
        lbl.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.clear_btn = ttk.Button(row, text="✕", width=2, command=self.clear)
        self.clear_btn.pack(side="left", padx=(2, 0))
        Tooltip(self.entry, hint + " (여러 낱말은 띄어 쓰면 모두 들어간 것만, Esc 지우기)")
        Tooltip(self.clear_btn, "검색 지우기")
        self.entry.bind("<Escape>", lambda e: (self.clear(), "break")[1])
        self.var.trace_add("write", lambda *a: on_change())

    def words(self):
        return self.var.get().lower().split()

    def match(self, *texts):
        w = self.words()
        if not w:
            return True
        hay = " ".join(t or "" for t in texts).lower()
        return all(x in hay for x in w)

    def clear(self):
        self.var.set("")

    def show_count(self, n, total=None):
        if self.words():
            self.count.config(text=f"{n}개" + (f"/{total}" if total is not None else ""))
        else:
            self.count.config(text="")


class TreePanel(ttk.Frame):
    """data: 노드 리스트. 노드 = {"type":"folder","name","open","children"} 또는 항목
    on_add(): 새 항목 dict 반환(없으면 None) / on_activate(node): 더블클릭 / label(node): 표시 글자"""

    def __init__(self, master, data, on_add, on_activate, label, on_change, add_text, search_title="검색"):
        super().__init__(master)
        self.data, self.on_add, self.on_activate = data, on_add, on_activate
        self.label, self.on_change = label, on_change
        self.add_text = add_text
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 3))
        ttk.Button(bar, text=add_text, command=self.add).pack(side="left")
        ttk.Button(bar, text="새 폴더", command=self.new_folder).pack(side="left", padx=2)
        ttk.Button(bar, text="이름", width=4, command=self.rename).pack(side="left")
        db = ttk.Button(bar, text="삭제", width=4, command=self.delete)
        db.pack(side="left", padx=2)
        Tooltip(db, "선택한 항목 삭제 (Ctrl·Shift+클릭으로 여러 개 선택, Ctrl+A 전체 선택)")
        self.scope = None                       # 파일별 보기: 함수() → 지금 파일 경로 (북마크 탭에서 씀)
        self.scope_all = tk.BooleanVar(value=False)
        self.scope_bar = ttk.Frame(self)
        self.scope_lbl = ttk.Label(self.scope_bar, text="", foreground="#5f6368")
        self.scope_lbl.pack(side="left", fill="x", expand=True)
        ttk.Checkbutton(self.scope_bar, text="모든 파일", variable=self.scope_all,
                        command=lambda: self.refresh()).pack(side="right")
        self.filter = FilterBox(self, lambda: self.refresh(), title=search_title)
        self.filter.pack(fill="x", pady=(0, 3))
        self.tv = ttk.Treeview(self, show="tree", selectmode="extended", columns=("x",))
        self.tv.column("#0", stretch=True, width=180)
        self.tv.column("x", width=24, minwidth=24, stretch=False, anchor="center")   # 줄 끝 × (삭제)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv.pack(fill="both", expand=True)
        self.tv.tag_configure("missing", foreground="#999")
        self.map = {}
        self.drag = None
        self._xdown = None
        self._xhot = None
        self.tv.bind("<Motion>", self._hover)
        self.tv.bind("<Leave>", lambda e: self._hover(None))
        self.tv.bind("<Button-3>", self._context)
        self.tv.bind("<Control-a>", self.select_all)
        self.tv.bind("<<TreeviewSelect>>", self._sel_info)
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
        flt = getattr(self, "filter", None)
        searching = bool(flt and flt.words())
        found = 0
        cur = self.scope_path()
        in_scope = 0

        def mine(n):
            return cur is None or (n.get("path") and os.path.normcase(n["path"]) == cur)

        def put(parent, nodes):
            """넣은(검색에 맞는) 항목 수를 돌려줌. 검색 중에는 맞는 항목과 그 폴더만 보임"""
            nonlocal sel_iid, found
            shown = 0
            for n in nodes:
                if n.get("type") == "folder":
                    iid = self.tv.insert(parent, "end", text="📁 " + n.get("name", "폴더"),
                                         open=True if searching else n.get("open", True), values=("✕",))
                    self.map[iid] = (n, nodes)
                    inner = put(iid, n.setdefault("children", []))
                    if (searching and not inner and not flt.match(n.get("name"))) or \
                            (cur is not None and not inner and not mine(n)):
                        self.tv.delete(iid)          # 맞는 것이 없는 폴더(다른 파일 폴더)는 숨김
                        del self.map[iid]
                        continue
                    shown += max(inner, 1)
                else:
                    if not mine(n):                  # 다른 파일의 북마크는 숨김
                        continue
                    nonlocal_count[0] += 1
                    if searching and not flt.match(n.get("name"), n.get("path"),
                                                   f"{int(n.get('page', -1)) + 1}쪽" if "page" in n else ""):
                        continue
                    miss = n.get("path") and not os.path.exists(n["path"])
                    iid = self.tv.insert(parent, "end", text=self.label(n), tags=("missing",) if miss else (),
                                         values=("✕",))
                    self.map[iid] = (n, nodes)
                    shown += 1
                    found += 1
                if n is select:
                    sel_iid = iid
            return shown
        nonlocal_count = [0]
        put("", self.data)
        in_scope = nonlocal_count[0]
        if flt:
            flt.show_count(found, in_scope if cur is not None else count_items(self.data))
        self._scope_info(cur, in_scope)
        if sel_iid:
            self.tv.selection_set(sel_iid)
            self.tv.see(sel_iid)

    def scope_path(self):
        """파일별 보기 중이면 지금 파일 경로(normcase), 아니면 None"""
        if self.scope is None or self.scope_all.get():
            return None
        p = self.scope()
        return os.path.normcase(os.path.abspath(p)) if p else None

    def _scope_info(self, cur, n):
        if self.scope is None:
            return
        if not self.scope_bar.winfo_ismapped():
            self.scope_bar.pack(fill="x", pady=(0, 3), before=self.filter)
        p = self.scope()
        if self.scope_all.get() or not p:
            self.scope_lbl.config(text=f"모든 파일의 북마크 {count_items(self.data)}개")
        else:
            name = os.path.basename(p)
            self.scope_lbl.config(text=f"📄 {name[:28] + '…' if len(name) > 29 else name} · {n}개")

    def selected(self):
        sel = self.tv.selection()
        return self.map.get(sel[0]) if sel else None

    def selected_all(self):
        """선택한 항목 전부 [(항목, 담긴 목록)] — 선택한 폴더 안에 든 항목은 폴더와 함께 지워지므로 뺌"""
        picked = [self.map[i] for i in self.tv.selection() if i in self.map]
        folders = [n for n, _ in picked if n.get("type") == "folder"]
        return [(n, c) for n, c in picked if not any(f is not n and contains_node(f, n) for f in folders)]

    def select_all(self, e=None):
        def walk(parent):
            for i in self.tv.get_children(parent):
                yield i
                yield from walk(i)
        self.tv.selection_set(list(walk("")))
        return "break"

    def _sel_info(self, e=None):
        n = len(self.tv.selection())
        if n > 1:
            app = getattr(self, "app", None)
            if app:
                app.status.set(f"{n}개 선택됨 — Delete 또는 [삭제]로 한꺼번에 지우기")

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
            if self.scope_path() is not None:      # 파일별 보기에서 만든 폴더는 그 파일에 딸림
                node["path"] = self.scope()
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

    def delete(self, iid=None, ask=True):
        if iid is None and len(self.tv.selection()) > 1:     # 여러 개 한꺼번에
            items = self.selected_all()
            if not items:
                return
            n_items = sum(count_items(n.get("children", [])) + (0 if n.get("type") == "folder" else 1)
                          for n, _ in items)
            n_folders = sum(1 for n, _ in items if n.get("type") == "folder")
            what = f"항목 {n_items}개" + (f" (폴더 {n_folders}개 포함)" if n_folders else "")
            if ask and not messagebox.askyesno(APP, f"선택한 {what}를 모두 삭제할까요?", parent=self):
                return
            for n, c in items:
                remove_node(c, n)
            self.changed()
            app = getattr(self, "app", None)
            if app:
                app.status.set(f"{what}를 삭제했습니다.")
            return
        s = self.map.get(iid) if iid else self.selected()
        if not s:
            return
        node, cont = s
        is_folder = node.get("type") == "folder"
        if is_folder and node.get("children"):
            msg = f"'{node.get('name')}' 폴더와 안의 항목 {count_items(node['children'])}개를 모두 삭제할까요?"
        else:
            msg = f"'{node.get('name')}'을(를) 삭제할까요?"
        # × 버튼으로 지울 때는 항목은 바로, 내용 있는 폴더만 확인
        if (ask or (is_folder and node.get("children"))) and not messagebox.askyesno(APP, msg, parent=self):
            return
        remove_node(cont, node)
        self.changed()

    # 줄 끝 × 버튼
    def _hover(self, e):
        row = None
        if e is not None and self.tv.identify_column(e.x) == "#1":
            row = self.tv.identify_row(e.y) or None
        if row == self._xhot:
            return
        if self._xhot and self.tv.exists(self._xhot):
            self.tv.set(self._xhot, "x", "✕")
        self._xhot = row
        if row:
            self.tv.set(row, "x", "✖")
        self.tv.configure(cursor="hand2" if row else "")

    def _context(self, e):
        """오른쪽 클릭 메뉴: 열기 · 이름 바꾸기 · 삭제 · 새 폴더"""
        row = self.tv.identify_row(e.y)
        m = tk.Menu(self, tearoff=0)
        many = row and row in self.tv.selection() and len(self.tv.selection()) > 1
        if many:                        # 여러 개 선택한 채로 오른쪽 클릭
            m.add_command(label=f"선택한 {len(self.tv.selection())}개 삭제", accelerator="Del", command=self.delete)
            m.add_command(label="전체 선택", accelerator="Ctrl+A", command=self.select_all)
            m.add_separator()
            m.add_command(label="새 폴더", command=self.new_folder)
            m.tk_popup(e.x_root, e.y_root)
            return
        if row:
            self.tv.selection_set(row)
            self.tv.focus(row)
            node = self.map[row][0]
            if node.get("type") != "folder":
                m.add_command(label="열기", command=lambda: self.on_activate(node))
            m.add_command(label="이름 바꾸기", accelerator="F2", command=self.rename)
            m.add_command(label="삭제", accelerator="Del", command=self.delete)
            m.add_command(label="전체 선택", accelerator="Ctrl+A", command=self.select_all)
            m.add_separator()
            if node.get("type") != "folder" and node.get("path"):
                m.add_command(label="파일 위치 열기", command=lambda: open_folder(node["path"]))
                m.add_command(label="새 창으로 열기", command=lambda: launch_new_window([node["path"]]))
                m.add_separator()
        else:
            self.tv.selection_set(())
            m.add_command(label=self.add_text.replace("＋", "").strip(), command=self.add)
        m.add_command(label="새 폴더", command=self.new_folder)
        m.tk_popup(e.x_root, e.y_root)

    def _set_open(self, val):
        if getattr(self, "filter", None) and self.filter.words():
            return              # 검색 중에 펼친 상태는 저장하지 않음
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
        if iid and self.tv.identify_column(e.x) == "#1":    # × 누름
            self._xdown = iid
            self.drag = None
            return "break"
        self._xdown = None
        multi_key = e.state & 0x5 if hasattr(e, "state") else 0     # Ctrl·Shift 누른 채 클릭 = 여러 개 선택
        self.drag = (iid, e.y, False) if iid and not multi_key else None

    def _motion(self, e):
        if self.drag and abs(e.y - self.drag[1]) > 6:
            self.drag = (self.drag[0], self.drag[1], True)
            self.tv.configure(cursor="hand2")

    def _release(self, e):
        if self._xdown:
            iid, self._xdown = self._xdown, None
            if self.tv.identify_row(e.y) == iid and self.tv.identify_column(e.x) == "#1":
                self._xhot = None
                self.delete(iid, ask=False)
            return "break"
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


class MenuBar(ttk.Frame):
    """도구 버튼과 같은 줄에 놓는 메뉴줄 (Windows 기본 메뉴줄 옆에는 버튼을 둘 수 없어서 직접 만듦)"""

    def __init__(self, master):
        super().__init__(master)
        self.items = []          # (라벨, 메뉴)
        self.colors = ("SystemButtonFace", "black", "#cce4f7")
        self._open = None

    def add_cascade(self, label, menu, **kw):
        l_ = tk.Label(self, text=label, padx=7, pady=3, cursor="hand2", bd=0)
        l_.pack(side="left")
        l_.bind("<Button-1>", lambda e: self.post(l_, menu))
        l_.bind("<Enter>", lambda e: self._hover(l_, True))
        l_.bind("<Leave>", lambda e: self._hover(l_, False))
        self.items.append((l_, menu))
        self.recolor(*self.colors)

    def post(self, lbl, menu):
        self._hover(lbl, True)
        try:
            menu.tk_popup(lbl.winfo_rootx(), lbl.winfo_rooty() + lbl.winfo_height())
        finally:
            menu.grab_release()
            self._hover(lbl, False)

    def _hover(self, lbl, on):
        bg, fg, hot = self.colors
        try:
            lbl.configure(bg=hot if on else bg)
        except tk.TclError:
            pass

    def recolor(self, bg, fg, hot):
        self.colors = (bg, fg, hot)
        for l_, _ in self.items:
            try:
                l_.configure(bg=bg, fg=fg, activebackground=hot)
            except tk.TclError:
                pass


class Popup(tk.Toplevel):
    """모든 대화상자: 누른 메뉴·버튼(마우스) 가까이에 뜸"""

    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self.withdraw()                       # 자리 잡기 전에는 숨김 (깜빡임 방지)
        self._want_grab = False
        try:
            self._px, self._py = self.winfo_pointerx(), self.winfo_pointery()
        except tk.TclError:
            self._px = self._py = 100
        self.after_idle(self._place)

    def _place(self):
        if not self.winfo_exists():
            return
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        size = getattr(self, "size_hint", None)       # 크기를 정해 둔 창 (사용방법 등)
        if size:
            sw_, sh_ = self.winfo_screenwidth(), self.winfo_screenheight()
            w, h = min(size[0], sw_ - 20), min(size[1], sh_ - 90)
            self.geometry(f"{w}x{h}")
        try:   # geometry("600x620")처럼 크기를 정해 둔 창
            gw, gh = (int(v) for v in self.geometry().split("+")[0].split("x"))
            if gw > 1 and gh > 1:
                w, h = max(w, gw), max(h, gh)
        except ValueError:
            pass
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = min(max(0, self._px - 40), max(0, sw - w - 8))
        y = min(max(0, self._py + 14), max(0, sh - h - 70))
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.lift()
        if self._want_grab:
            self.after(30, self._do_grab)

    def _do_grab(self):
        try:
            if self.winfo_exists():
                super().grab_set()
        except tk.TclError:
            pass

    def grab_set(self):
        if self.winfo_viewable():
            return super().grab_set()
        self._want_grab = True                # 보이기 시작하면 잡음


def ask_text(parent, title, prompt, initial=""):
    dlg = Popup(parent)
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


def ver_tuple(v):
    nums = re.findall(r"\d+", str(v))[:4]
    return tuple(int(n) for n in nums) + (0,) * (4 - len(nums))


def page_sizes_fast(doc):
    """모든 쪽의 (너비, 높이). 쪽을 하나하나 열지 않고 PDF 정보만 읽어서 큰 파일도 바로 열림"""
    out = []
    for i in range(len(doc)):
        try:
            r = doc.page_cropbox(i)
            rot = 0
            x = doc.page_xref(i)
            for _ in range(20):                     # 회전 값은 위쪽(Parent)에서 물려받을 수 있음
                t, v = doc.xref_get_key(x, "Rotate")
                if t != "null":
                    rot = int(float(v)) % 360
                    break
                t, v = doc.xref_get_key(x, "Parent")
                if t != "xref":
                    break
                x = int(v.split()[0])
            w, h = abs(r.width), abs(r.height)
            out.append((h, w) if rot in (90, 270) else (w, h))
        except Exception:
            r = doc[i].rect
            out.append((r.width, r.height))
    return out


def page_photo(page, zoom):
    """쪽 그림 → tk 그림. PNG로 압축하지 않고 PPM 그대로 넘겨 빠름"""
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    if pix.n != 3:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    return tk.PhotoImage(data=pix.tobytes("ppm"))


# ───────────────────────── 인쇄 (Windows) ─────────────────────────
_print_api = {}


def _print_lib():
    if "pd" in _print_api:
        return _print_api
    import ctypes
    from ctypes import wintypes as wt

    class PRINTDLGW(ctypes.Structure):
        _fields_ = [("lStructSize", wt.DWORD), ("hwndOwner", wt.HWND), ("hDevMode", ctypes.c_void_p),
                    ("hDevNames", ctypes.c_void_p), ("hDC", ctypes.c_void_p), ("Flags", wt.DWORD),
                    ("nFromPage", wt.WORD), ("nToPage", wt.WORD), ("nMinPage", wt.WORD), ("nMaxPage", wt.WORD),
                    ("nCopies", wt.WORD), ("hInstance", ctypes.c_void_p), ("lCustData", ctypes.c_ssize_t),
                    ("lpfnPrintHook", ctypes.c_void_p), ("lpfnSetupHook", ctypes.c_void_p),
                    ("lpPrintTemplateName", ctypes.c_wchar_p), ("lpSetupTemplateName", ctypes.c_wchar_p),
                    ("hPrintTemplate", ctypes.c_void_p), ("hSetupTemplate", ctypes.c_void_p)]

    class DOCINFOW(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_int), ("lpszDocName", ctypes.c_wchar_p), ("lpszOutput", ctypes.c_wchar_p),
                    ("lpszDatatype", ctypes.c_wchar_p), ("fwType", wt.DWORD)]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                    ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                    ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", ctypes.c_long), ("biYPelsPerMeter", ctypes.c_long),
                    ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]

    gdi, cd, k32 = ctypes.windll.gdi32, ctypes.windll.comdlg32, ctypes.windll.kernel32
    gdi.StartDocW.argtypes = [ctypes.c_void_p, ctypes.POINTER(DOCINFOW)]
    for f in ("StartPage", "EndPage", "EndDoc", "AbortDoc", "DeleteDC"):
        getattr(gdi, f).argtypes = [ctypes.c_void_p]
    gdi.GetDeviceCaps.argtypes = [ctypes.c_void_p, ctypes.c_int]
    gdi.StretchDIBits.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                                  ctypes.POINTER(BITMAPINFOHEADER), ctypes.c_uint, wt.DWORD]
    gdi.SetStretchBltMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
    gdi.CreateDCW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p]
    gdi.CreateDCW.restype = ctypes.c_void_p
    cd.PrintDlgW.argtypes = [ctypes.POINTER(PRINTDLGW)]
    k32.GlobalFree.argtypes = [ctypes.c_void_p]
    _print_api.update(pd=PRINTDLGW, di=DOCINFOW, bih=BITMAPINFOHEADER, gdi=gdi, cd=cd, k32=k32, ct=ctypes)
    return _print_api


def ask_printer(owner_hwnd, n_pages, cur_page):
    """Windows 인쇄 창 (프린터·쪽 범위·매수). → (프린터 DC, [쪽 번호들]) 또는 None"""
    api = _print_lib()
    ct = api["ct"]
    pd = api["pd"]()
    pd.lStructSize = ct.sizeof(api["pd"])
    pd.hwndOwner = owner_hwnd
    pd.Flags = 0x100 | 0x4 | 0x40000            # RETURNDC | NOSELECTION | USEDEVMODECOPIESANDCOLLATE
    pd.nMinPage, pd.nMaxPage = 1, max(1, n_pages)
    pd.nFromPage = pd.nToPage = cur_page + 1
    pd.nCopies = 1
    ok = api["cd"].PrintDlgW(ct.byref(pd))
    for h in (pd.hDevMode, pd.hDevNames):
        if h:
            api["k32"].GlobalFree(h)
    if not ok or not pd.hDC:
        return None
    if pd.Flags & 0x2:                            # PD_PAGENUMS: 쪽 지정
        a, b = sorted((pd.nFromPage, pd.nToPage))
        pages = list(range(max(1, a) - 1, min(n_pages, b)))
    else:
        pages = list(range(n_pages))
    return pd.hDC, pages


def print_pages(hdc, doc, pages, title="스마트PDF Editor", output=None, progress=None):
    """프린터 DC에 쪽들을 그림 (고친 내용·메모·색칠 포함). 쪽은 종이에 맞게 줄이고, 가로 쪽은 돌려서 크게"""
    api = _print_lib()
    ct, gdi = api["ct"], api["gdi"]
    di = api["di"]()
    di.cbSize = ct.sizeof(api["di"])
    di.lpszDocName = title
    di.lpszOutput = output
    if gdi.StartDocW(hdc, ct.byref(di)) <= 0:
        raise OSError("인쇄를 시작하지 못했습니다 (프린터 확인)")
    try:
        pw, ph = gdi.GetDeviceCaps(hdc, 8), gdi.GetDeviceCaps(hdc, 10)          # 인쇄 가능 영역(픽셀)
        dpx, dpy = gdi.GetDeviceCaps(hdc, 88), gdi.GetDeviceCaps(hdc, 90)       # 인치당 점
        dpi = max(72, min(300, dpx, dpy))         # 그림 해상도 (최대 300dpi)
        gdi.SetStretchBltMode(hdc, 4)             # HALFTONE
        for n, pno in enumerate(pages):
            if progress:
                progress(n, len(pages))
            page = doc[pno]
            r = page.rect
            rotate = (r.width > r.height) != (pw > ph)        # 가로 쪽을 세로 종이에: 돌려서 크게
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            if rotate:
                mat = mat.prerotate(90)
            pix = page.get_pixmap(matrix=mat, alpha=False)    # 흰 바탕
            if pix.n != 3:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            rgb = pix.samples
            buf = bytearray(pix.width * pix.height * 4)          # RGB → BGRX (윈도우 그림 순서, 32비트)
            buf[0::4], buf[1::4], buf[2::4] = rgb[2::3], rgb[1::3], rgb[0::3]
            bih = api["bih"]()
            bih.biSize = ct.sizeof(api["bih"])
            bih.biWidth, bih.biHeight = pix.width, -pix.height   # 위에서 아래로
            bih.biPlanes, bih.biBitCount, bih.biCompression = 1, 32, 0
            # 종이(인쇄 가능 영역)에 비율 그대로 맞추고 가운데에
            iw = pix.width * dpx / dpi
            ih = pix.height * dpy / dpi
            k = min(pw / iw, ph / ih)
            dw, dh = int(iw * k), int(ih * k)
            x0, y0 = (pw - dw) // 2, (ph - dh) // 2
            if gdi.StartPage(hdc) <= 0:
                raise OSError("쪽 인쇄를 시작하지 못했습니다")
            cbuf = (ct.c_char * len(buf)).from_buffer(buf)
            gdi.StretchDIBits(hdc, x0, y0, dw, dh, 0, 0, pix.width, pix.height, cbuf, ct.byref(bih), 0, 0x00CC0020)
            gdi.EndPage(hdc)
        gdi.EndDoc(hdc)
    except Exception:
        gdi.AbortDoc(hdc)
        raise


# ───────────────────────── 바로가기 (바탕화면·작업표시줄) ─────────────────────────
SHORTCUT_NAME = "스마트PDF Editor.lnk"


def desktop_dir():
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf) == 0 and buf.value:   # 원드라이브 바탕화면 포함
            return buf.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Desktop")


def has_desktop_shortcut():
    try:
        return os.path.exists(os.path.join(desktop_dir(), SHORTCUT_NAME))
    except Exception:
        return False


def is_pinned_to_taskbar():
    """작업표시줄에 고정돼 있는지 (고정한 바로가기 중 이 프로그램을 가리키는 것이 있는지)"""
    d = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar")
    exe = os.path.basename(sys.executable if getattr(sys, "frozen", False) else "smartpdfeditor.exe").lower()
    try:
        for n in os.listdir(d):
            if not n.lower().endswith(".lnk"):
                continue
            if os.path.splitext(n)[0].lower() in ("스마트pdf editor", "smartpdfeditor"):
                return True
            with open(os.path.join(d, n), "rb") as f:
                data = f.read(65536).lower()
            if exe.encode("utf-16-le") in data or exe.encode("latin-1", "ignore") in data:
                return True
    except OSError:
        pass
    return False


def create_lnk(lnk_path, target, args="", workdir="", icon="", desc=""):
    """윈도우 바로가기(.lnk) 만들기 — PowerShell 없이 Windows 기능(IShellLink)을 직접 씀"""
    import ctypes
    ole32 = ctypes.windll.ole32

    class GUID(ctypes.Structure):
        _fields_ = [("a", ctypes.c_uint32), ("b", ctypes.c_uint16), ("c", ctypes.c_uint16), ("d", ctypes.c_ubyte * 8)]

    def guid(t):
        g = GUID()
        ole32.CLSIDFromString(ctypes.c_wchar_p(t), ctypes.byref(g))
        return g

    def vcall(ptr, i, argtypes, *a):
        vt = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        return ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)(vt[i])(ptr, *a)

    ole32.CoInitialize(None)
    ole32.CoCreateInstance.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p,
                                       ctypes.POINTER(ctypes.c_void_p)]
    psl, ppf = ctypes.c_void_p(), ctypes.c_void_p()
    hr = ole32.CoCreateInstance(ctypes.byref(guid("{00021401-0000-0000-C000-000000000046}")), None, 1,
                                ctypes.byref(guid("{000214F9-0000-0000-C000-000000000046}")), ctypes.byref(psl))
    if hr != 0 or not psl:
        raise OSError(f"바로가기 기능을 쓸 수 없습니다 ({hr & 0xFFFFFFFF:#x})")
    W = ctypes.c_wchar_p
    try:
        vcall(psl.value, 20, [W], target)                     # SetPath
        vcall(psl.value, 11, [W], args or "")                 # SetArguments
        vcall(psl.value, 9, [W], workdir or "")               # SetWorkingDirectory
        vcall(psl.value, 7, [W], desc or "")                  # SetDescription
        vcall(psl.value, 17, [W, ctypes.c_int], icon or target, 0)   # SetIconLocation
        hr = vcall(psl.value, 0, [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
                   ctypes.byref(guid("{0000010B-0000-0000-C000-000000000046}")), ctypes.byref(ppf))
        if hr != 0 or not ppf:
            raise OSError("바로가기를 저장할 수 없습니다")
        hr = vcall(ppf.value, 6, [W, ctypes.c_int], lnk_path, 1)    # IPersistFile::Save
        if hr != 0:
            raise OSError(f"바로가기를 저장할 수 없습니다 ({hr & 0xFFFFFFFF:#x}): {lnk_path}")
    finally:
        for p in (ppf, psl):
            if p:
                vcall(p.value, 2, [])


def make_shortcut(folder):
    """folder 에 '스마트PDF Editor' 바로가기 만들기"""
    if getattr(sys, "frozen", False):
        target, args, workdir = sys.executable, "", os.path.dirname(sys.executable)
    else:
        py = sys.executable
        pyw = os.path.join(os.path.dirname(py), "pythonw.exe")
        target = pyw if os.path.exists(pyw) else py
        args, workdir = f'"{os.path.abspath(__file__)}"', os.path.dirname(os.path.abspath(__file__))
    os.makedirs(folder, exist_ok=True)
    create_lnk(os.path.join(folder, SHORTCUT_NAME), target, args, workdir, target, "스마트PDF Editor (스마트공 시리즈)")


# ───────────────────────── 한글 입력(IME) ─────────────────────────
_ime = {}

def _ime_api():
    if "imm" not in _ime:
        import ctypes
        from ctypes import wintypes

        class LOGFONTW(ctypes.Structure):
            _fields_ = [("lfHeight", wintypes.LONG), ("lfWidth", wintypes.LONG),
                        ("lfEscapement", wintypes.LONG), ("lfOrientation", wintypes.LONG),
                        ("lfWeight", wintypes.LONG), ("lfItalic", wintypes.BYTE),
                        ("lfUnderline", wintypes.BYTE), ("lfStrikeOut", wintypes.BYTE),
                        ("lfCharSet", wintypes.BYTE), ("lfOutPrecision", wintypes.BYTE),
                        ("lfClipPrecision", wintypes.BYTE), ("lfQuality", wintypes.BYTE),
                        ("lfPitchAndFamily", wintypes.BYTE), ("lfFaceName", ctypes.c_wchar * 32)]
        u32, imm = ctypes.windll.user32, ctypes.windll.imm32
        u32.GetFocus.restype = ctypes.c_void_p
        imm.ImmGetContext.restype = ctypes.c_void_p
        imm.ImmGetContext.argtypes = [ctypes.c_void_p]
        imm.ImmReleaseContext.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        imm.ImmSetCompositionFontW.argtypes = [ctypes.c_void_p, ctypes.POINTER(LOGFONTW)]
        imm.ImmGetCompositionFontW.argtypes = [ctypes.c_void_p, ctypes.POINTER(LOGFONTW)]
        _ime.update(imm=imm, u32=u32, LOGFONTW=LOGFONTW, ctypes=ctypes)
    return _ime


def ime_match_font(widget):
    """한글을 조합하는 동안 뜨는 작은 입력 창(IME 조합 창)의 글꼴·크기를 입력칸과 똑같이 맞춤.
    맞추지 않으면 Windows 기본 글꼴로 크게 보였다가 글자가 완성되면 칸으로 옮겨져 어색하게 보임.
    성공하면 맞춘 (글꼴, 픽셀 높이), 아니면 None"""
    if sys.platform != "win32":
        return None
    try:
        api = _ime_api()
        hwnd = api["u32"].GetFocus()
        if not hwnd:
            return None
        try:
            spec = widget.cget("font")
        except tk.TclError:
            spec = ""
        f = tkfont.Font(root=widget, font=spec or "TkTextFont")
        act = f.actual()
        size = act["size"]
        px = -size if size < 0 else max(8, round(size * widget.winfo_fpixels("1i") / 72))
        himc = api["imm"].ImmGetContext(hwnd)
        if not himc:
            return None
        try:
            lf = api["LOGFONTW"]()
            lf.lfHeight = -px
            lf.lfWeight = 700 if act.get("weight") == "bold" else 400
            lf.lfCharSet = 129                      # HANGUL_CHARSET
            lf.lfQuality = 5                        # CLEARTYPE_QUALITY
            lf.lfFaceName = act["family"][:31]
            api["imm"].ImmSetCompositionFontW(himc, api["ctypes"].byref(lf))
        finally:
            api["imm"].ImmReleaseContext(hwnd, himc)
        return act["family"], px
    except Exception:
        return None


def install_ime_fix(root):
    """모든 입력칸에서 포커스를 받을 때 IME 조합 창 글꼴을 맞춤"""
    if sys.platform != "win32":
        return
    def on_focus(e):
        w = e.widget
        try:
            w.after_idle(lambda: ime_match_font(w))
        except tk.TclError:
            pass
    for cls in ("TEntry", "Entry", "Text", "TSpinbox", "TCombobox", "Spinbox"):
        root.bind_class(cls, "<FocusIn>", on_focus, add="+")


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
    data = net_request(url, headers={"User-Agent": f"smartpdfeditor/{APP_VER}"}, limit=limit, timeout=timeout)
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


# ───────────────────────── 아이콘 (tools/make_icons.py 로 그린 PNG, base64 내장) ─────────────────────────
# light = 밝은 바탕용(진한 선), dark = 어두운 바탕용(밝은 선)
ICON_DATA = {
    "light": {
        "open": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAB4ElEQVR42s2UPWvUQRDGf7O7/3vJ5S6JGlNoJYithYWIkHwA29R+BW21OPIJ/A4iiIWFoIWV0QNtDHaWmkKDBIx54XK52//uY5FcopiEC0ZwYGBgZ5955pnZhf/dbBjo1Wz443RxLtvCQj7VimrjTpIf9tjVeivc8Y5aSqasrMZ44bqb8ZndfvNB7bYblakB6PnNqf6WX6u2KhAFCIIjbse1MuZb9Svd93y6ZEyvHg069zqZoV3doldK+j7YjBNlkkAGpFo9TMWoq3Zt6R0sjd7yMDYjADIzk/BlzBi61300e8EZ5WH0JKkxFtgp48PafGc5HD4JYYaVpagEuxjq4f6RlLKgESi/9TpmfA6HyurDvsCDjAZd0jFd5ppwRWu6vv727pnwG1BO+OnL+NYMpBLMhrjhON2SlKuN+mPXi08PEpWxooZrngfzEE6wfsrgfdNZfLl3axJywhpnwReQE0gjuXJW8N6l7f6PvnY6BzScxzVnQL8+yFE22bKNVQB1GjcefHUA68uLWL2VrNpMqEzCkmAkR0pAwipP9vfQdjbMNWcmaY65YtAHO4F+WZ7CiGtfVvYBJ67Px1g594Kt7fFYJg3HOwIauJCL3rpLqx83/vF/qLb7O6QF2e5IT9d+Akb68RwAWZn8AAAAAElFTkSuQmCC",
        "save": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACkklEQVR42rWUwWtcVRTGf9+5981MxmliLcFViQgVa1GQ2YgrF67cuTCEdinUhUt3boII0Y1/gK5cdNEm+AeUClXahYUOiEVBsLEl1raBTpuUTiZ5993jYiYxyUxiKXjgbg7nfu98v3veEbtj3o27nXC2DWfbbTqMRhvo0OGjb6Ddhs73y5ml2Wq00l08a+y6G3cSkr+6cPOVVR2dPf26hTNvHtGjfh4WAAatmlGLcHW5zxeX17xRxKosNy/dka6BC+SReTeEz3z598mtonbFaB5rtOpMPQ++aZggAP0EX11xTkyLUy828TpYIWKsf3584a+5lU91gUUP1r7bCSDPuZrTxNSx/Ph+v7/+KK11q7TWLdNat0zrD8vUfbCVfvj1Trr++2raWO+l3Oum1Ov2JeHGxwAsLf3rCJlTlY4UQTEjHOGA77gWSENkQiA8I6ncy3BHVHKgCOK5mihdhKFlE7w10+DEdEERdr+fwNFYQXeIJu49Tlxf2eRJmbFdd9872aQWxW/3tog2/sH3CGZ3GoW4+mefH5c32D9Heeg9mmgUoqp8pCbu/4IEG6WzVfnouA0M4jgmmKzp8A5N0Cudd15u8PZMnezssbzdpQluPUx8d6OHHSRoBinDVN34+v0XODph//mD3HyQuLbqtOxAhjBRCNNA3H2AgDEso8FkXQOuOoRh9gGraIcLmmAMZsb6etotocPGRu4O7nKq7e1xUIc+tCmo9mtb593lDBALv0iV5I3JenMiBCCYEWD0hGE+11o1q7dCUHUOgNemFZmdrZh3++MT/fTSwu25++nIh0u/KJx+o6k8hsl27sZq6T+v9Kriycb5M+Xxbz8brMDE/xuLHlj04P5054NFD8xf3jMp/wA5AC7ymd2FVAAAAABJRU5ErkJggg==",
        "save_as": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADU0lEQVR42pWUT2hcVRTGf+feOzP5PzOxIRKigmizUYrMwiCRgQoW0Vq6MFREcJG2IUG6cOE/JIogCEVFEKzRnVA62dSFgmCtpVjUGEFEm4WJEWtbU9NJ0kwymffuPS7eRCc1UXrgPO57vPNxvnO/7wgbMaam0DNlDxUKbBUF4PDUFFMA+UJgUDzbhqpwo7FNjWNszCASdozN7Ozqumnw9QdbbGtKJAZMAAx0pA0YeOnjBf1+ISWtVM7OipxCVRDRRkABlduOXuyLffrLfD7X+fajjo4miANYgaqHN88ou+8UzswEvpit0u4CUWXpwG8v9J6gpLaRvgNRjS4MurZcZ7w8X10q73AhI8QBnIFKpHz+wzw3uzbCaky8Uo01l8uo6Chwgh/RzZQBxKj6SBFxzohLGUFIAJ2BppQh4wwigoCgQUQk2nqGf5NPhrFSUwSIFYyAD8qRgSy9OcdPf9SwZmNSyH8CGgNrUeDVz65irvu1yQk+wPJ6oNkJqv+wPLYXe+hl1Xo/DR0CCvy+FBMFkPp7ohAFhJSFbFoalKNGRKLDW3UoApFXHt/VQl9XCtXkW1KYnMtrgQ+/q+CT+YqIhGuqD7TBaUQU1QTQAN5Dvtny1iN5Mm57nU/PR5y9bLi6uL6sqgeILh2PJsffT5uWg4qIaaTrBFYjJQ4Q+USLG1nz4AOknZhLVxZ4ds8tRVZnj6+efMqnyueG1k+NvANqXR1N6w+MJFJppAwQ6rc+f60mI/d380r/hezqyWGI1mxl8c9a60NPjgBll8xPMyCKqte6R68HNIIJ3svwQDf7umeofjSqRGui60txa/GZNL1PnAM+SFRlzWkNsdiWbCbbbC1gjcFCYwYRa9nf8zO1T0cJUTUBG3jasXPoW+BhEfnFMqam/GL7bGdxeHoldtl7e+zcrTk75wNzRpgD5oBfQXpl+bypfHJE8VXR6mIC1ndwEtgjIouqajeu5H/X11dfTx179/n9kZbuW18ZvzvS6fdUVb9R1fyGJjdXlNQ+VlKrqqYxS6VSWkQoFHa91r97r5ae61edGVdVnWwAs//28qD4icSlm9abqkZvTEw0ZxZX7vBrC0c77tp3D7cPddRplutu8Te0nIvFomu0m1453741TfgLa1qdanHi1QcAAAAASUVORK5CYII=",
        "print": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADNUlEQVR42rVUz2tcVRT+zr33zS+bZIq4EImgLRKjLViwDmMkgYYidiEIgy6qWZQuK4rgSjpkExH9B/wbIriqBJW002hJxLT4K5J2IZFImjHTZmby3syb9+79XLyZMQ0TXYgHLhzuOee73/lxD/DfRP71oitqZmZmeBdA/hCH9fX1cHl5ufVPgAIAhUIhYzJHvoiiznNRFDkRUSD7HiQoIsjmcrvK4uz161/fKZfLanZ21gGAOfAAR0dHs79tbhXef+/dzPFjx0A6iKjESEJEEAQB5j76OL99d/sJAHfW1tb6xMwgxtZa/5nx8fT402McVBbnrBMRiW0cHbSrnlIqlRQADg0NRQKoTqcjAISkdIP6p9VqCwDlHC0AVqvVnu1vhvPz83Z6enqkVqsdFREJggDNvT3QOYh6MGV/zwdJGK1HJs6dO1q5cuX+/hRVqVSSrT/vfSJKnadzmmQ+l8uJ0RqDciYI3w/gnGsorSyIFeWiNyuVSs0AcH9Ua+ezmcw7YRhCJAn3/YTFYaJFQ2k1zJhI5zIvt9v8EMBF033yKeesBeBIGgCitT50lBkCagzwJjTDz2MbNSIR4fF+DUWkA4gmQOlm2GM6CFA0AJ9wWxR0KKJEw0ln0NgkMQIEQYAodoPTVUB2Mwu3QdAAku4WtgdIsntFCxGJrdMnTzyLRx8eSuaqy5ZM1Horxg8//YLYxk4ASxIgsn1ArfVVkh94npcWEbQbTVy69Dbaj4zDbzsYnfw+QYI4NtLBxbdeR223oTzPS2ljYG38ZQ9QLV39arH40tQbXsq74JyklEKx7re8zzaa2N714ZmkQbF1uB8KLr+omNIiURTf9Iyuh+3WtW+uLc7tn7C+Ui6XU6deKO6s3vqRt+7S3dgI+d1mxG9/j3h7x5Ikw1ZgX3n1NXfi1OnCwfr2msLJyUkzNTXlVldvD2sl3k696T79ucqte03JegrNEDg96mHubB5+EDiQRgmGy+WyWllZ8RYWFsKB66tYLB4RL/trPj/y2EMpgeo2RADEDggi1x/8TtR+/kal8v3+9SUDtg0nzpx5MmrHj9d9n6R+wCdjAGMMcql0Y2lp8Sb+b/kLqXCOmnfIMLkAAAAASUVORK5CYII=",
        "undo": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACcklEQVR42s1Uv2tTURT+zn0vL2mqlg5m1dVEUXiD0j778uOVWihuZ3ARXIqC2EFwEh4P/wJF0L1L4Q4dFBxsqzGpEDBTbXCq4KCQRQvaNi/vvuuSaCxpUouD33ju4dzvnPOdD/jfQUfI04MSjUGPzGzkcjnRaDTibsz3fZHJZESj0RhMgZkNAKIfqyyz5TIfs+fm0sM67Ncy+b5PQRDETt4rEeGu1nqSiE7EWkeCqA6ip5W1l4sAVIdE/EdB27bTqdExd8RKb66sPP8EAE5h+kkqad1stcLPsVZlaPoI0uNElLes1Jl2u1X7Fu7NblSrXzt1NAAQMxvZbFavlis100zkoqhdA2jXsqzZKAwXCq7zOAiCuLcFxy15wjSekcaGCndmSqXSdhAEGoAm27YT9Xq9PemW7ltW4oEGYCUs7Hz/sVB9s/qo86loNpsEAJlMRksp1UWnYI+mU+9aYWtx/fXadWY2pJSquww4bsnLT1/RTr54zyl4N3oWRX0WaAHAhFt8eLngac/zxrojNKWUMQBQHG5Gob5WLa8tdR+llOoAUSgAgkDLZiJxZy+MzgJYZ2ZhdodZqVS+AFhiZqPZbFK5XI6GiF0TiTaAmAjJbtDslQsziwGsfmFra0sAUCpWlwxFQrX0BwCQUuq/OVPBzIZt2wkAOOc441PF6W0nX3zb0a7Yz3AYYiklACjHcU4KK/1CCAKpcL43yTysMbjuzCkY+kIcx0UQ5gGo3b1wqlYtv/d9X3S1KoZVc13XAKAVotvJkdSyJtwiQIY7rfO16qs6Mxv7hX9YhqedvOdOTFw9jt/WI/6JifZxpiNBHHQ5vfgJSI33JIoGXTAAAAAASUVORK5CYII=",
        "prev": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABnUlEQVR42sWUQUoDMRSGXzLjdERQREEURbyACqPCTBMz0xmtotts3XgCT1B6Abe6EDxA0aVudBEpVNSIV3DnQhBBcMbWxE0EF7ZMteKD7JIveX/+/wH8cyGz/gT8q8IGgmdnVwY6QXFOmAIATVjpcGhEX/lRNN0O2hHIObcAQBFChkkYnxRcdwshmLEARgEAKpVK/tYNDAghwySKG8n6pqal5KZYjOYMDHcjLgYARSkd11bhyHVdP03TBrTSjXq9/sQ5t2q12nsuDc3Nyl+OF5FdkG6/62fZ62UeWFufUUqnSJg8hMmapmGy63nJUKc2277QiKyVsgcRRmNaqzeF9J2UZ8+MMbtarequDff5imJY2mZJWUer65qweP/LR+EfQ30almmYPMblDV0M4708dmvrI8aYLYRoBYwtWJZz6vQ5o1mWHli6tSOEeDFndVeZ9DyvT0rZ9JfjRdtGx45TmHzL0husWlwIcW+26dxJkVI2OedW4+L8GprZUpamtwhh7x3jka6T8l1qgiCYCBibN0rjXo6sns1ElMfcPa0P9gSXpHPkmh4AAAAASUVORK5CYII=",
        "next": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABlElEQVR42s1UO0/CUBQ+ty1gYDBG2kSNJq6spANQetveBgJxrT/AV2Lioj9Awq+AmPjY2YzBOEGJhkFZ3XFwIHHxMQC3vS6WRZBHjfFbbnJPvnvOud/5DsB/Bz8mzn2d6NczFwoFzg+fAwCkaBrBJHMZN815AADLsviZWrYsixNFkWNIKIUjkRx0KVlZW3+4ub56xhgL7XbbHfUg+uleUZQoCKGLUGgu3+v1XqjTzTUbjft4PB5otVr9adseJEtppESyeZbWzU5CJfKk7Q/9S4+oYFI2cxssbWTeE6q+5Uco5BEVjRypuvmhmVmW0vXNYZVOkoHV63UOAMB1ockYvPGCAMDQKgBAp9NBk4gygCdAEuu7wUDwBCEEvX63vCxGD2KxGCsWi+7Uw5zSjG1sZhkmGaboZG8W9yCPkFSNY0wyTDOzLImNnXEK86MqkySJW5CWTsPh8KFD6atD+/t3du0MYyxUq1VnnPm/oVKpMGDuI6X9J5dR49aunWOMBdu2qa+lIMvyop9BHuEWf5tmUr//DT4BRbWLzZVelJYAAAAASUVORK5CYII=",
        "zoom_out": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADIklEQVR42p2Uz2ucRRjHv8/MvPvuHlpLNSip2SYhilhBJbquu5vM/koQi5DL3IQuaMSrePDXYXlBEfwTjIo/TrIiXhQMpdlhY70klET6HjysTZVVlJRWkGbfmfcdD3VxEzfS9DkNzMNnvs+P+XKMDlJK8UwmI8bHx3mpVKIwDHGH0WSH3Sil+NFQzX9h1epibr5cb85VFt4uVheey+fzmYM5I0sbhgVBkBQK8jEv7X/EBH/cGgMAEEIgjpNdE9uXv9cXvlBK8VarFY8CsiGYe1rKR7yMr0HuniiKGs7snez/Je7a2+vXAFzOpNOt4lz5XKvVig9TSgNgGIbU+/3aNuf8xI3d/pmtLX19KMcBwFy5/iUT/GzSdzOdzuovzWaTgiBI9ilUSvEgCJJf/7j+hO+nHraRfW0IhgEMACzFrxAgEhY/D8C12+3/qBTdbpcBiJ1LnrXWJv2bNz4vzFcrvu/VjDEJABD3mLPRzvra2kpBVn8guCUA75bL5URrvR84VLvvnKPNzU1TlJUSEXsLIAeAOBEssQ6AFSIYcuQfNmU2PT2dAIBz7DvheVQqLxSPZfz3Io+d5M4e584eE7Ankujm2VzumeOci4ccsYsAMKpkGgwmn1dpkb72GxFd7qydL4x6vShr76T81Ot94x5cmH/qpzAM6eD68MEPWF1tRRPZyR9T6fSr2dOTZ05Nnt7++cqVXQB4sla7e2bqgTeJ0RvWmC1K7NXPPv14e2xsjO/s7CT/v9iy2vCE+BAgZmNziYCYiB4VwvNMZDaJ6H4uxL2RiZYv6gsfSCmF1truUwgAWmunlOLffvP1pfH7sp9wj3rOYYaIOIi+sol5gZzrilTqnLXGCCGWJrJTvY5e25BSioNKb9sACrKyLGuLbq5Sj2Rt0ZVkfRkApJRin8JBhGHoADApJc/lcqSUIgC80WgAAF/X7Y2J7FSPc7aUJInhnC2dymZ767q9oZTidFRzG/SsJOvLXLD34ziOhOelouhWT9lRgVprOzs7663r8yuxNS8Jz0vF1v7pEtcdHjLuROmtnlZfzJfK8na88kiGjH/OfwNpW2BikqN9aQAAAABJRU5ErkJggg==",
        "zoom_in": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADRUlEQVR42p2UTWicVRSGz7k/86NIu2imdpJ8SSdgRS0qkRAnX3pnJjMRCkI2d1fsgI24tmBRF8NgNypuXfhT0riSz4UbZWzLdK6mkWKCpqWzEJw2XURECm2oyNzv/rhIqkmdSNOzunAOL895z+Wl0LtQSknT6TTLZrM0DENst9vwkFUjO3WklHR3UrV/xUql6bEjhXJtslg5PVGqvDw+Pp6+f6bnalvF6vW6y+fFczyVPEMYfd7EBhABKKVgrbsVW/P6D6r5pZSSRlFkewmSLWL+RSGe4emkAvT7tNbVR5M09V3zPHa7ugQA19KpVDQxWTgeRZHdiZQCABQKBcxkMuTun90mIiF3bunDP16+eHl//9DkcC537JJqzq9e/3VuIBh6lnJ+MugfOTs/f2a9VqsRpZTfRiilpPV63f32x+0XksnEU0abUysr6vZmv8J58t1/hl38BgIwR+wxAPCtVus/lKTT6RAAAO/dUWOM6/5154v8kVKxWHnpNKLPa93VYmr6vbwonVBK3dBxfBXAzWxu5np6uHmdpPcel5eXY0QfIpJ3PGDovQdE8iYivgIAgAgxAiZ3ujLJ5XJug5BcYpxjWKhMPJZOvp8gfg94/xHniQRxeoB5c3S0XN5DKXvSI1kEAOi5chRFDgDQ6r0XYq3XEf0HjUaj22g01gHhirWxstb+rpS6mzbuFKX0EY/sw1qtRjKZjO95ZSklPXcu0oPB8C+JVOpkMDT8dDYYvLqoWudv3rg+d+DAob25J0beBsS3TByvoDM3P5+fu9LX10dXV1fd/39sUapyxj4DQGKt+dl7cITAYcY4j3W8jIgDlLH9Otazi6r5qRCCKaXMNkIAAKWUl1LSb7/5+qfs48FZynHNez9CCBBA/Mq4+FX0vsMSiePGxDFjbGYwOLj2vbq4JIRg95M+cADkRXFWTE37yWJZi6lpH4ryLACAEIJtI7xX7XbbAwARQtCxsTGUUiIA0Gq1CgBAF1RraTA4uEYpmXHOxZSSmf4gWFtQrSUpJcXdhts9z0JRnqWMfGyt1YzzhNYbnpLdCiqlzOjoKF9QFz6xJn6NcZ6wxqx75ztbjwwPQ7rhaenEeFgQD5KVuwpk2Hz/DSDHdLTK0uZ2AAAAAElFTkSuQmCC",
        "rot_l": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADtElEQVR42o1UTWhcVRT+zr33zU+SqZPmx0yazFjIwiZFF4FWREmx0bpRKDihKl2IgiCCghY1FGYizcSK6KJLRaGoSKK1FBXBRdKNKaXB1jYFFWsmCZk0iZPM5CXz5r1373GRpPlrqB/cxYVzvnPu+c79CBuRYoEeMs19U2fA3i8T3YkLrakbgXCjwxgBRmKLjPQhDSLGDqDNV6bW1Khlh6OjFIomtLPw6uS7TV9sy+pniS4YYDuxWudiASLjVMwkQBxj11bSCn0e75t8CCTykIKkDP/mGHs410Vzqzm0tds7hB1piIuA8bj8hFXTVOnPz8B4jmvV7nkTejVIAFbRL8Y/mvnUXlx4P09UXBvTNsL6m2CkUgIsYuz6Z9jzf7CMk/dns4eIvRFiBBjiUUj1gnV//K0qxuNVfdmnx9+j+Y2dbpshUqCNFe+GxOnpblFZ3atLhUthQ0/9sVy7hDQYRKy2aMToAXekWEVy6UDu+uAr+fmFOqM1G4CDwaCsq6m5NvxOQyaRyZLVED+1PD2eQg+9jTaWADRtrZ5MJuXAwIBueXB/x8GDB4aOPNkJwwxBBM/38dXX33h/FvMNk8PDC/EPc6MkrCbXdvfmevbMgZnUTs+anZ2VjbEGffzF5/WKHGAAdO6774vzM6RAZDgzcVZVxzLSTD0G4DzSQ1LsRKiUYs/zpDFGua6rtNaqUCwqAxakXLMyIH0ZBiyYHwaA9lyExGZBWN2q7txURAgBIrpzNkkoqQwwMdZ51BZB/JHVhfVrG1gppQEYy7IYAO+KRIiINEyYwEw4nWsjQWDwGACMxNpZrewQEO8bj8KqzFCp8FeW6OPovvYK27bltd+vS2MMhBBwymV4rre7qgqwiRiZ7DG9VNSS5eBqV4bWCQtRiNJtEQj5jj2178CXbfmZ2JGz5eXFKBvDDLBSARUMV1z9dfDnN5pO/XM0UPfAOe/f8fMT3YmjSLLEAK2uTT9LdJFu7pt8Rt1Xf0E79iU3EDo2/XpF9m6CxXsnD4tw5Fsm9o1XfmTiRP0tpFc+BG12ENLx3rGXZXXzZ3op70CXPjBl7yeY23+HAiHpoXo/C3Fc7oq9ZBy7aEr5wxMnW65s/M+03ZZIx3vHnqNg5BMZ2d3EbhnantMAhIw2EsDQy4Vhv1R4berk3qtrOTv4IYBkv8RAl65L3aiqqKx9loXVCeO1gJmhgldg9I/jJ+oGAfBaLO6Jfpb3jEmx+B+OvXFrmZAeWiG+OcsA0NGapItt4J3cGgD+AzPCzxIkp2I7AAAAAElFTkSuQmCC",
        "rot_r": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADvElEQVR42oVUXWibZRR+zvt+X/PT/DW23VLadCpTWCerdMgila7iQFSGCCnDXxTFK/EHUbsOk+CswrxQEGHgD+iNJMLAK6cT2wsHre7KroqrbknTdS6tTdO/5Pu+9z1epClLbbsD79VzzvMenvOcQ9gpmAnJEdkz6yf0AGtX3TSZ2m91DGePgswj04NtLyHBAinStRLahomQhsAAqc1I+/v5Z6U7dJrLxaxvrdg1meqyAeIabmzZFRFjACrywUyzW/hiSq3dDaUZrMNkul9ha5khzEjZ29oJ0CUwC1C1y3rCRBUIJ/4M+PyhtwH5AvkCAUMHqrgE7PkZi6TZYDS1Ntpz+fsBXOpLQowCmwirnenoe9kmGJ7vzHDLPfY/uSl1vfghQZ9ngsVk9pjaGbE1hdlyHgGLCBIJ0ToJrteQmZAE3emda1wT/L30BA/plYWh7Ju7h3ccWoIFUuD/a5iBQIrU6nA20dASPeRcy53IHu8cjvUdiRfm5w9UKhUlABJSUrgpVIjc1f/pUiRpjabI2fwH1YYQScw0N/gaLrO287k3Il3tsVjojkD42hOPHzNNw4BmhiDC2R/OYWxs/PDUHxOj8XhcZjKZOicYSI5IAI70olcGm332XP5LEOmF22KGp8VVeu6Zp4IAeF0e/dvEhCwUCnI7FUTPrJ8AQDAfgAYTq3EAIMPSGiwWSyVDKWVYlmVorQ3btqVhGLwt4caQQQJgYkmVOk2INp4Qoq7476YHBBJsALyxIMaFSA9XCfkKCQJgdoH5Z+y9j4hIBfx+BYCFEARAG4bBjuMwmOkCkQ28iHoN1w0pWf6kVkoK2j4GotO+7l7Ylh0e++VX4Xa5oLWGEEIuLy8j1NruXSTiznf+eo09wb2wV47nBqNFcM2HcZbIkOoYzp4xb4k+ahWuPJY/ceuZe/sf/KiyttrtOJZDAJEQ5PL6i62zZ58ef/Ji2O1r+11bZQPasys3GCyCaz7cBwYz4dT119XqYq/hDX8efTdfOj/U/vJWwu/+eLWzwSp/Ta5GD5dXjk4PhhaQZgkiRfWuJ91xcuqg8IR/FG5fQJVmvyCtvzKxMFG2ygpi1+3CZT4E6XlLNobdamH6+dzQns+QZlm7TPXnax1oO3m52/AEP5HeYAwgqOJVBqClr1lSgwtq6d88V5ZezQ3t+eZGsq3vYTwtkRlQACh6qtAPIR+GUzlY9Y05Rdo+t7oy920htX/5htybRILFTXPSvOW20A73n5CG6LsIGp3MVDdjX0s1P3lYgWjLbfkPvcylffs3pMcAAAAASUVORK5CYII=",
        "rot_many": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADKElEQVR42rVUPWxbVRT+zrnv5TmpTXAqCyklbmkHkLNhI7ng1sZpJRBS1MUgBgZAqF0ZUECALAuhClrxI7FUYmKM2UrFUuo8xZQqJQxIWCIUSgNR0lCauKZx4vfuOQyVC3FLU4Z+09W95+c7P98F7haqhLI6m+7KNQdlZfxv9DilJjWaPqHu7d6px5VuDVYmVCry0Bs/P2Dj0QkCngObYVXbArkn5frKR7+X95zHpBo8S5buTI0AKHYc+6PgMJ9kdyAaXv/zc1WZY6IhGO9FHhj0ZPXyK/NvJT9Nn/jWpc1kyjw1OzuEVgvWWgriD7IbrMrC3uMvyOCuZ8KNlSMLEyM/de2TRy/FyYsd48h9L3dai8WFiZEadcvMZrMRE9n2hWHeLVYs6EaPCAyWjVVZ+v7Q9FzzYrb0ar+X+iDwh2cJhzMBACTfX/qR2ElosDHbbaYSxWIARgPbeRrW3WvUPlyfOrNzeur0Tsue6kh2DwCcq37Y9isU4nAm6A6GbOc9HojHORI90GWoudxTCTWdb8h2HqvX6yu5fPGQMc4+a60C+rwSvmM2F1Xk16uJoU8a1WqAyUnGDyVN9l16hKLbv9T1a7XNO0RkwnCAxsfHYyD6zKoMgeCB4JCCRSyI6J37l64UAGipWgUAzL+5q2Hay/v6QnrN6Z1rNCp2bW2NoViuT51+CYDmCmOPiurxs/6Z2hP5sTQRbbvpUCEBlH55neYBwLnDxphssTjsWXvZQvuYsD2fzzshEGEm6TFWqBIA9MpGPc/jdc9jAAhcVwqFggBQAKHv+yHdON+GACmI/pGMtZZU1WROnWqOZTJNAglct1mpVEQVAsC9G5V2SyZrm+t9iGntyYPnxZ+2UOzob7XP5gpjARGNimCxVCqZxeWrWwZUADQzM3Mtm88f6DeRlAThoIKPQvVtZtPUQJa+rn81BwCP7y+2DdGWDBUAzvn+BQAX0um02x8b/JiIGGEIGE7uLx4cDSUQA9q9lfr/DU6n0yaRSPBf7eBdNiYvEioUrKCQiAiE34wER3zfv3Lz97iX+M9mlEolk0qlbsneaDSoWq3KPWfWxd9DoF6g1daJGAAAAABJRU5ErkJggg==",
        "rot_all": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAESElEQVR42n1UW2xUVRRd+9wz75a+ZgRKO6XlEaWmmloSlIItGF9RfnTqLx8mhkT8EF8xNsOgpVCkSI34+NBUQciQmGCqftgXGALBTkobS6wplGlh+hjHjmXodObee7Yf02Jrwf1zPvY+66yz194LuFv4WcDPAvcI78Gblatbbl8tbrxxEAAe97Ocz8kl1cGghjoyAaCkaWIFC0sVGbMPQdphmslrgsU0iD4nIVYx+GGA6Syg5q/TYjDWUEdmof/qeovDcYikZYe2zH0nzQyAAZVKAmCYyXhcJNOl4UBpHMwEon+pzoMVN4Z3kj3vKEv7MmiWoCFxRpagbyoGdlyPVWkqmQvGX5COF4TFvoNJVANow2kIAKZcBLZvaKfIWv6VTEQgL7acS1w62YvklFuXtqfWFRYae/oHP6sD0nMUjq9qGq+QytQAAL7Mtwl+FgiAi/aPrpGO7H5Tc45kn/Z1PvuId9fG6u0gISCI0PbjT7hwqb92sO9899rdR21DW14z5nu9MASugABiwTisOXMc9lLrS7HLbb9veXIHF+TlzHZ1dBihnh59YiyiZ9nRXF3zxIltqQGFOjLhC2r/nQYCgLUNEY9us4whnbgYfre0etWaB/Z91LS/vrv7rFFWViofLN8ABpiI6EDTh+rq4JV1Hs/To6HQF0ZGpoUMAaSkelRb5taY1UmACUyCCMjKzsLGqkq0d3ah9evj9O3JU8rhcOjlFZUhu2uoFQD7/f5FDCUyT1SAGSTEAEAMWs/MDCJC9M8YIpExvL+3Hnl5+cJms8rfBq7k7np1t/duQy8WngRWAKCUgtVqVVJKBgC73Q6Px4P8/Dy4XC44nU5mRgoAulEjEGRtESAxwiBixaIYYFq5sgjfnfle9PSEyON2m8wKuq6DOdMu0zRpvv9nA7WL1M4A6to5lUwQgOcA4nxv+ac9v4a2RWOx4eFwWEvOzjIzQyk1tzEMJk0AoJLG4Rpvc3TbBj9bASYBX1AbeW/FdTMx1SsceT5vY7is/dQnkYG+UJfL6Wpt+fjYL/F4fMbtdhuapukAjJzcXIPZVCDBTLZWYq0jnX8rByBI+HwAEdPBG2+SxdYO3dYKYCsBfK7z54ZNm15sTqdvz3zZ+g0sFitAhOjkBFx6bLLoyHS9Jcvl1aM364f2FEXh75K0cPWKGkYOW+8rft2cmvwBmHk5/FbpOAF4bPPmV8bHJ916KqHzbCKVtbKswHzmUHV69fZadWviwsjM4FagRmEveM5tmBCEQB2Z3gOjx2R+0S7j72gcptFssGqL1K/rhRC4P5Uo0E9jsx5VbwgptvD0xHk2Us+PvOONZ9aEmJYYa4BU8YGxOiEtR7TsgkLWdajEZEZBRy6E0wUzHoVp6IHR2T8+QKDWmLeupX4IAH6/QCCglh+67LKjcCsztkMZlRAaSIhrrMxu5lTn6NslkTnJ74DdOxYM6v/X8BJC/wBZYfeRwH5nEAAAAABJRU5ErkJggg==",
        "t_edit": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACf0lEQVR42r2US2hTQRSG/5m5Nw910agUqoLShfigVltbkhp6yaORWmlBmE3RutGIIuhC17cjbsSNuK2C4ELwoiAoNIipkbppEB+FgiCCUDcR0k2tyb13Zlz0QYSmtkH8YeAsDh9nzn/OAf6xSG1s2zaplyiEAACF/y1iWZZRKBT8Y72pkUDQPOO6rgRgEEKo1tCA9hkzqJLy42Th1TWtNSGE6HpAY35+fvGbRLcHgsE0QAACKClBCAEhFIZpYmHhZzMAjI6OEgB6rR4SADqWSOwOm2ZrpeL7zEA7o+Ydz/ffKamuBwIBKrVXnsznP23ElBVZlnWUBTcXq25l/O3rfP9GemjUxJRzbgCQpXJ5CwBAw+Scs0gkQltaWqQQ4q8u05pYAZCO40illAIAQqAdx5FrwJZbRlcDNjLDeukpwKYNA23bpgD00JDVdCSeeXE4lugBhLJtm9JGYEIINTwQj3wtmbm+vezEzibjWUcskRRC6FWBhBCttVYAUavBLg7HI8VSOHchRrovdf+qSLDtzCCtALRRz33DMKjnVTfVwm4IoQYG4pGXn8O5K73oGtznVs89CYVmy9XsTHHiHuec/QF0HGfRXSnfSymTSrO5muOg2uLxyOxcOHd7EF3RXW515HEo+L3sZmeKE2OWZRmO4/jrdZMciGa2tkX7pp7fTGv9tLcyfCqj93Qkzi8twkphrB6Ec85mDh6kNucIh8OBquuN3zpJov373erZR6Hgmy8q++1Dfmz5uKzLUc45A4BkMtnRkziu715N68unM7q5LZUFgM7OTnOt1asrT+KQydSP+1N02pP+w9J0/sFSZV5DF70nnd7RlUptqxmguvP7G+snAjaMCTBQAAAAAElFTkSuQmCC",
        "t_mark": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACj0lEQVR42s2UzUuVURDGnznnvPfe16ul1UqoKNpE2KoWiXn8jKxtdxV908JV/Qcvdxe0CGoRGYRQi8qFGEikaR1SDNy5khaVbYLSDMy8ej6mxatiZmZU0LMd5jdnnpkzwH8iKhQK8q9T/xRKAAQA1DU099bpxlMAkCSJWIz9nrTWahF2s+lIG9c3tXJ9U0uyquDGyFprZYxxdbrxXJTJ3rHWWgAiiiJpre2el7g4OjDwCUstrKckSYQxxtVqfUDI6Ia1zgNQzIwQAphQPS9EKUkSAgC1Ad9wsLl5qwj0EECeOQQALKUUIYTXKrijY/1mdqy/nwDwei8krbUsFosh6/m+knKX985TKgaAEOxJY8znxWnzui1rraUxxtU2NF5TKtNinXNEJBnwSkXSW98+bMxLrbXq6uryS3libd/SIRyqazqRUZnL1llHqW8+UpFydqFj+MXgraVhrcwVaw2hWDSuandbTS4nO7z3gQDJzEEpJZ1zI0NmsL1QKEhjjF/T9CUxg4gYzNXxpQt7Xg6N52vymQUPkAARAHxwJdo/MtL/cTE3/BTIrBUexxI7KthNjd9WFfL0lXuxezBcrspj5lxWEgV7rK/v8JPOzueZs2fhvkcZTwT+YbFnenbtj7flRzlAqAxk91AcrvZU8qt37vzU22d3N/I/wW/O5DA7fRmS4uB8Fgszx7g0XePmXMhujsTEZNXUzu2V18EsIdL1WOETIx8RSq6T9va8TYETx6vwRX3ClgwwH4ASI8zNeF6YA3KVkHEkEEtahUoVGNgUAe+/ttK+R0/VikoWNkTwDOQIoqxSgqoADmmSDWv3uBxLlz0FzpRZYL4Xcy4Pu2xEuvv0i/vBzFCCEMTkPznl3wBuCjHahO3s8AAAAABJRU5ErkJggg==",
        "t_hide": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABjElEQVR42sVUsWoUURQ95963y4wJCRpEyy22E8FmO2Gn1DqlXbDRzlphpt8P0F6w2P2I/IZGZJmIRLtlwYzJ7LxjkSwYETITEjzwiseDc+89554HXDP45yXf3w/ZFUiyLGtICjcBSiJJTafTdHG8eu0W0lVzCtBajCf1k4TV8a93L/aefc7z3ML68ejopJdsWybELQkixMsIBUVEmamZAkBRFNfvx4UuRqPRTheGn+7aaBoOBoPFbDZrAJAAbDweW3n47T3JJ5IiAGvJGUlSUqlYPy3L8kcAEOfz+Tatt2tmva5zSoC7366b+ADA9wAAJEViKemOJP0txWVdSoKZ1wAQzqqIBFMAOj9dEAH0YkR/TWgkKwlf3O1hjN34SJikyqz+ujaFADQcDu+GkDw6V4ZtcwF3VnV1WB4cfOwoVcs9XEdvMplsbO7ce+Me0tXpCmatHFaSJFwsl29fvXz+6UL0+v377uaPnbal4K2cphDN3TZvpR9uInr/+A/z3NClSgEUxdkeX2Hd/hN+A/M5omSsJQvEAAAAAElFTkSuQmCC",
        "t_shape": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADeklEQVR42r1UXWibZRR+zvne72sSkyWpS2j6v1YRqmxIkTm86MDihjgQJL1T2YXTC0UQeiFWvkbsOp2iVS9chXWidbLeyVBhw9oNBcsyxmDdxNHUZG3adHRma7J0+b73eNGfrfuJeuNz+z7v8z7nvOc8hBWIDU4ebTfwD2hPJh0CBP8X6Eg8bnSNjLjZJ7ZuDzFvXyiXGcR8B1O09hmGLrF8GTs5nhLbZkok9O001TI5yQBcrfXTHsvqFscRg0BrL2K5PgYjZCnMLJV/BZDCxATdzeFNJyKl2VLJUZpjbHoDCmoDm96A5XNDbHoDDmTnkqMdEilVKlndLJ4ZBHXd48lvGhu749L01vYCEylXM0OE0NWFyg5X4C+XTQFIABaApKNDCUDXLZ+liRF0rjkgkp/b2ghHxLi3wxVo0xQCRJb7JxKNCtlCMryhiEgrToda/ZHPzvmffJUWgQQgQiCSewqapmlIPG4glyOJRmUw3MlIUPm1l4ceXgjV42S47XtvMUcNH8yf1dr5KEN0aFkUAEjWCQqA6uPH8+ufGHFb+6ZeGg7EDrTkU1JbyH097duYZs27zOraocb357algVdgg5DALYKitSLW09se20EipYLl47qrM7r78Z4HvwnEBp+9+N3lT8b7qv1/nvmYsjgNoKdpf3a3CtYcbOifTmcS9X2wR9WaoBCpiGVx0XV/NIlQTRpVXj+uBOvQkk9h4Ld3N/osDy481Bnp2HNMbV74wfi0OzbUuDezk5T5dsSeG5hPRAuqPZl0AMBw6YuS1sfyjuMuMXOVe0Om7tvkPRF+5GhtIXvYlfLQJa5hnzOTHEuQs3jgFMEWdjl7yPLf3+Ut57YA9ItaXfTY+HgKQGr9DJxD4w420v76P8LjEz8B57GaC8lwu8YMQAYKEIir2Fr3yzbAvfH42joNToZ5pqWThnT5giV4joF3nn/xoGequdkZm5iXB7JQFxO0RH2pXdpYJFUsna8cGytD29CfeaFlUKRp36Xdt1Pq+jNbmgeuug17M8PLrkYVVRS1hdELadqf+9wIRvc4f819K3AOa0euGczPsDfwhohzSkr8VLoUzKMXUlkQQhAARNL43mwPsfEm+0I+ANBLi9C6/BVdnn09vW/zldWNoX+Vmivk+g/TXpaqR9kwFRVv/J56q2bu1vP/FsX2qLprn2W9qb8Bm+6CMgNmtUIAAAAASUVORK5CYII=",
        "t_memo": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACm0lEQVR42q2UT2tVVxTFf3vfe1/y4kue0UZB20ITEiqaIEJBaDF0UBwWStORg0Id9gM4E7+DM2dqoDwcCEKhAymlI1toQFRooWraJlpipWli3rt/zlkdJM8kmoSkdI/25Ky19lqcZbwyEsZexsBAbAW0Z7Du24v4BnwQWJdF028PUpgW29oRvFk3MSTjx98W7RJRwsyQdZd/psfe6E3jVc/S0yFIXbKdhHlimMJcvlSd3/f5ox8k3NQiYWjSivk/vq4df/Mj0iYQd3msQ2xT/jK7kMV8gqnZP1P7jKDpR4Oq1T+g1gxYYiSZYbuwswzEZCBkBxpDndnO8brxNAWgMFlGB6jnnUK3vrljnSLgvm2wlBWcnRzn8NFDTpDksQJIXxpiOIg0TTg1MUII2tZFA2KEgf6+1cXMLK6GmG62GZIkYfjE8M6RdCNbziFs9jt9lTqEwOy9h7tS+NaRA9QbfdsARgRGVQV+uvuQvKiw7Tw0KEto9o9TbzZAkqJpHbAmw0ljRD21jE8/ObOmztZv1NYpUwXh7kbMAFJdxCmsbR6eeGyP0jNQqgoZMYIEEnIX7hFhGzncTVRFEpZWsFrtdwCTcDNice2d97zRczPp7ztSrgT54H7z3hrRXN5pm+XLELU5GDdiOy+KxRdf1s89vqIWiXWLwQwtXR0+1MjiyU5ll3snxkbZ1yx5tpCF+fmqWupcUNAMVllqFhGiJ/Gw4nO95x//3MVYJ2yRALSmSPIb7/6lBx8H3TmjsjXyfOX68Pu7bZv1lKdWG2P52uGDJos8f+Jh7tlMHvyLxrlfZ/TtZMrCd69Hcx/ZpS0+f1dh+6uRD3X7mMrWyPd/T48PrilI916Sa+X6ojV6tLgxdkGtqWQj0f8y/6XB/wWKX0LP1tZMmgAAAABJRU5ErkJggg==",
        "t_erase": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACpElEQVR42t3UXUhTYRgH8Oc926DETc7UmLmzaU6F9Kjz7AQ5cZlbulxU4qjsIj+aJQV1UxBCh5YFKQOJrMvo2huLkBblbX5FRDZD+xK8KIr5EX7g3vM+XcjITEStq57rh98Lz/N/H4D/qQgAcP8Si9dfoorCAQCUlJTo8xwOAQDA7/drtmgtYxZR5MvK3cMHPN4pwW53AAC4XC7tljCxtJQvcDoHey+H8F3bA6xwV0XNRUXyplBFUTgCAEmiyBc4SwcfXupA7ArH8M4TOhK8j+51UM1aWDAYZIIo8jnG1PB15xG52pJPZ5cWtItqjBMSeSbtsCYMf5uoXTIk9r0ZGJj0+/2aSCSCf2xsGbvGDILAW1JM4VQ+WU7XJlLgiBaRgY5wMLO0wOUZ01hn2TE+N8UUNuTlyN3d3Wp8RL/FgQCwfFHkiW5buDPUIe8U0umF8xe1bcU+cAg2mJn/ATpOAxQZGHTb2Oj0V671RU90JPrFO97fP6QoCuFW5IwhJPFEtz186+YNuXyfi+Zm2bTtoXa4+qoXXk6+h6QEPcQYAwIEFlVKrHojTU7QGwljaQCAkUiEAAAQRCSSJKWU7fcMPXveh4gYo5QipRQREV9H3qLXewiHW+8h3n2K852P2HSoh9bX1KFZKjq9MhXxORK7fa/V4/XNfp6YQERU49hKtLLKh0NXutjC7ce0/mgdWooLA2sGPa6bhF2Oisrq6NjY+NroaIQ1nmygpw6fwAy5OLBuFuOvmMyZssfri46N/0JVVUVEZCqltKG5BdOyswNkI8GON6xGEZHNzc3TpuYWtGRsEFuNms2Zsrvq4NSHj58wFovRpjMtmJ6R1QwAIEmSblP/OI4akk2OGv/x74Gz59BstTWSrRyF1Wj27sI9tlyxdqNn6ydDKFuej+RW8wAAAABJRU5ErkJggg==",
        "t_capture": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADkklEQVR42q1Uz2tcVRT+vnvvzJskkx8moaGptDsXVSw4+TXTNBOKVfyBiPC6lmzcuVKCLnwZRCj4H+hOKApvU/zVGm2bZ8Y0aRqFINl0J2MtxSahk8SZee/e42JmaqOJIHhW98L57j3n+75zgP85CADV/NNHqvA+0kBPQ8T1GKN3Entr+PkXZ3/75qsPrOhPSfsqYb4E3LMC91hGqYm6cw4guoxyNefeG1paXTYA8ADex0Pp1Ct36w1L0gHQAmmEGxucBM8pLddFMC2wP9JhUilmBJgSQgAgRepdh5O/TE4+RQCoFMYiJVIwxh2n9XYGk4R3rE2Ora3tHdSWBFD4ttC11VlXds9zdWlcpnC0FrsjBgDEuVhIqcWp7ePLS3/sAwNqDsCTvk8/DB0AsgQHLFXbOZV8LhEw6dVaFACQ7O7SOpWN47QAFEBJi9/pYlGVAHc+DO1531cEpJVD8aEFIAU9nlKdylqa1ic/7CVJVYC4vwkA0eQniqIkl3u5M5utpsMw3H6oJIDgJKQESEVxMXZybxCIeZj8IsK5uTl+t1B+Vym+AZFOgJeUxLNRFN3/i5H9odo8SdA8A4Dv+5qkXI0W38lkMu8DeFyA/rTnzSQwFwEwCAI+ynMbz0O8KYVCoVulO26THHTOgaSCSKKMSTUayfjy4rWbvu/rMAztPyo8KJRSBkCHiDQfA+gEJABCsofiAEB8X0ux2BZIfN/X5XJ5GyKXPC+jBbAA4rSXNtba29mMWRERhk0b7cPz30ayWCwOOJX6hOQLJCGCn+PEztz4/upqEASqVCq5A4GVwujrAE/s9fRfeOLKlfrfk86cPTtGmC7a+mIURUmb5yYbkEp+ZEaBw0d7Bz5sOX10bfdMXn4fG+tpqcZHPtzfRRCofSMIoJIfWd8+PSGbuVyvaXluaztJGh3WUQIobPiUMBQC7lYul/oim5X+jg795vh4vLCwoKaDAEAJQFFJEOHOvGzuWLub0VrYqvAagKljN26mCMp/3YGV/Mh1Cic8x6G2suk+Y/Sv46OLFY7YbmPUjk1Wh5976a07819fcIoX4eQ17dTnotw5AP0ema+Ja6+vXCLgnlLGAIAh3t5J7GdG85nEwUHEiOBBuLHB04IpWjcPMg8kKwKOEcwIMErAAYSBqiXiZu8lcfUh4T+dOtV3whhxWssAgLu1mj26vr578D4MFFYuZ+9vNu8mndZ95fIWAPwJ52uqw6hG17YAAAAASUVORK5CYII=",
        "m_view": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADN0lEQVR42tVUTWhcVRT+zr33vZm8+QmhZtoGil04xQYCSmUmtZEXElHrQnHxWnBZC9ZNiyIItjJkIdKFIC5UBK1S0MUToSCY2tbOM1OFIKVKSMssXBgpOv0hJpN5M+/de4+bDgwBa93pWZ5zOOd8nO/7gP960N2KtVpN1Ot1MZgrlUochqEFwPe8JQgC+U/L/q5nc4JqtRrNzc1ZAJiand0lSe4zkLvAIMC2iFFf+Pbs5UEU/f7NA6kP47Hp2YMQ4riUagI2hYnXVomZyfVGRDYPkyTXGfhg4eK5twBoAAKAHRxIADA5+cSI4/H7jlIHUm2uiKT99tronpt/PvRSxQpRzK9caIwufdxJs1uOOVI8ba29nOreC99H0ZX+pQSAmBlEhKnpme+UcvZqy8d1c/ndlaM/lkWm+IV0MmWwhUnTNdbxkd9e3fL55MxTz7lk3yOAdNdWLl06/2utVhPk+76KokhP+bPv5PL5Y3HcgbHcFTDZP6pvoLu9injxlGES7D18QKl0Hdvqr0DGtxKWrusNeehsbPyUH3KqhUJBqyiKTBAE8vfWraVOHL9swVJw6ibeWKZ738Rr+vrPbufaOckA3O0TlnbsofbY1EfDzfAXozy7sdHuSRJyddXm5ufD26r/CJZYFNoypBCp41mRrGcpWT8ktz44NrT7yRREQo4+wJx0DMOe1apwDQTHsNDKJZnhXgIAfch2nz/z5ZDnPdvr9iCVA4e7WC1N4kbldZByALaw5GD46mmUrn4Ko3IwOoFSDpKk10qyTnl/tdpWURRZAFbBHO7F8V4hZV4nvRM95dazzTNDcuczo2lxxyEQFcnq04WlT5op0DYmLpOQb1pry8w4uDg/v3Z/oSBpkJyP+v4jjsx8xuCdFnySVO7DhW/OrAwy3w+CvLl5+3lBdEIIOdJLk6M/RBdPBUEgwzA0tJnxlUql6OaGTyopjoAIWusOA00wMUBjStFWIQR0quucxi82Go3moFpokxsI3Cn4vr/NCGc/ET0O5jIzExHdIKbzVqqvGhe+bvY1HYahuasD3RH+vTiV+Df2JXzfF6VSicfHxxkAlpeXqdVqUTQ9bTFgCP+v+As6h4YnlxejegAAAABJRU5ErkJggg==",
        "m_edit": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABwklEQVR42tXUz2sTQRQH8O/M7Jrt2ksq7sFbwR6kh2JprYToNBi3hT0Iyh4UqaD9gdh/wNMSUDE3i0cvguAhi0iLiikLS8CT9iD00msrvSkGGk266eT1kKwoCCabXpzTwDw+vPfm8YCEx/M8Th5xHMUhIvbr7nn9oTGwXXx56nvx1TgAUKkkEmMMAFUpHa28/Vx/+u5ntehPtN/a5fNeesYLhdZ1J5uem7tVrlNrzGDcMEyzvPdk7RIKIPKI826xQgfbqg6UdXNn8v6HF81v9R8qZRwfUkqdZmCEUZ91hQHA3RvZ9Jlzlz8+XraJ1qajm9cy6s7V27S/8nr+95J7w+7ZRKsXo4dLOXVeztJ4dmqhE6f1hY1lZiiXzy0AQOiF/WP5Dial/J+xeCYd52gwBgC2bQ+dzeTbo5EQE3GplrVvfPmqrcsRbeqB02g+ei9EafMYP2lGi0EQPpNSapVK5eCfmcWBF6bzDrh4M6g168MnkPq0q/NBES2GYfcYAGi1Wo0BQAt0xUzp2GvQwMYukASLe8eklCnF9edCiAaUqugCm0EQbLiuK3zfVz2vJdd1xV9mKNHi/GM7xL9oWRYlygzAIRX1DUBdlwRrAAAAAElFTkSuQmCC",
        "fit_w": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACFklEQVR42sWUu2tUQRTGf2fuLJsnMRELWcmCwc4uFgsuXI3kT9gljWBlkTJgFXSzaSQQax+VdhIr2zRyi5QpFUQiynZGkUDcNXfuzLG4S7LrJkQCkg8ODJzzzfnOYwb+E6Rr58U/BXEcD1Wr1cmzZqlUKsNxHF8AxAB4iZakMLQzPz8/0lPCvwixAHZobMmL3YnjeNQAiMiIiEymaXrWPoyKyJRzLlcIeFXVvpANjUCPSaCS+/rgVdUDWABVFRHJyQ01sAJ18QBxQ20vM2lKRh2PquzWVwwkXX7epr5g55zQlABQXv9+L2t3tpJH8qk3prTaumZHhm9+FXn5AdK/9R9dKMLB1HU/vf72jjHRMsbeNoWD19OPWztIlKtXr4qZEVtcKD/5cTe099ZaD2c2MUbQwIDCwvBPVY2uaAgV8BhbWNDgodsNVDAmQv0BGHtLDAkimyIidCdgjnqtFL+9j1oPpl5Fu18uh7SzqKmrdtpmfL9oJ/aLdqLTNuOaumpwvxdBL7aWr66iAfU+DJYMwCWobUSf127sAU9PWJGtrjE7e7+wvf3C9TrNQPibuqfRMDTeWRpqUJU+a2juU5WxsY967FBERFX1UDbNpkIzy8+DiwgEmkAcc8jvTsUAaKBorTXOuTO9FA0UbRTZLMvylyLBPA/BzZVKpXaPilORJInP+frMuWyuXC7/+m8/mKnVatE58k/GH8qK3UzlCg3LAAAAAElFTkSuQmCC",
        "fit_h": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACAklEQVR42rWUzW7TQBSFz52xHTu1VATIErRJF0gsgugKCSEMlpD8AkjuikV5BTYsURb8/4gXqNiwire8QIQEG1agLmABTZvSUvoTGtQ4sT2XRWWaAk4aqh7pLuZI883VmZlL2C/yPG8sjmPCgXQSExOFnTAM08wRGQgAXNc9lpK+IAvFljCsLWFYrb760b8mw9rUrai1/G3jKgAEQSABQOs/L0mSSEp+TgSTec9nIgEQESsFgAGAiBlgEooaAFCpVBhHob+y8jzvd9fL09fleHdefS/dugJpXqaPLx6P7UBZn1+xbdsMAPV6Pc26Hq47LACgfG/p9dSzLZ58ytZuBpx7aSIXVmOJKqnJB82bojjugpDIeGUWABDm78sHzkAFNZZE6QeOo5ecxBqn/B4AEECNDgTx2jxo6fbUO46jT1AJFnun3w5LSRwoRyFMgHAcG/bhgSNqOLBKCkpFAGMTJ34eAsjknAOXHjYukG6ehZAoG18v/T+wBhHOUMosz5Nu3hDSYJI0PezZ0CAvCFiEIaXlu4tvoMmLSkvt5vZcdzeKavY7eOSfeerJtlt6tD6b30N+h+T7frHX6+33F+qJ04Ba8zzjT4DjOJ2B87ATqxWWRlsJfa/O+J3Va36330tJa5Nutpur697geagX7ivFFhEzZ0PgHykxEyvFpEH7cqTz8Bf0hd3jDtxeQAAAAABJRU5ErkJggg==",
        "v_single": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACN0lEQVR42rVUTWtTQRQ9d2ZemrzEPFsaaRoNxo9QUj9QXGRRQRD8PYLgNmQh6EL0P+jGP+AP6EoXuhGyMBWKoq0B0+TZJH1v5s110TRtvkxEvTCb4d5zz7nnzgB/FzR6IackCs/zvCAI4gDGj+fFz2Yy5Pu+/l0HAoByuRxX8dTrpcXFG1KSZYY4TmMQEevIoPOz0+qG3XtvNzfrlUpFVKtVCwBqpAHXarXE7Tt3y08eP4oHoQYRDXXUxmDlTAZPnz0//eLlqwKAeq1WGySNAsL3fRZSdhwnttDpBSxOIBIBWkdIJFwrpaQw7IWj9WOAnufBGCOWl5cofy4HMNNJlpG1WIjFyBgjlFI0E7DdbiPmONje/oyvuw0oKcHcd0oAvYMAN69dgeM4MMZgLoah1ihevojrV9en7ovWGkopzM3wY/3Tv2VYOJ/HemkNYB5yOoosYjHnzxg6SmH3ewPNlg8pxPHaECEIQhQvFaCUmp+htRanUim4rgsCDfaaQNDGIOm6sNZOKp9wM3gTOJwdMcBHiIzBQKfEREAiQrfbRcvfH5EMhIFGKpUcmutMQGZGKpmEm3BxqHigGcYYuIkEmBkTPJlsihCSm3st/NhrQQqBI5GCCAdBCEcpEBEbY3gmYDqdJmO0LK0VbX+Uk7RFzOxIKdUsQMpms7rT6+3ff/DQG/3gqG+UECTqW1tYzeVazcY3lEolnvbjEgC+tbFxYefLTr4TBCyZxxkqhdWVrP/h3Zv3+N/xC6N+8nrW1ltlAAAAAElFTkSuQmCC",
        "v_cont": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAC2UlEQVR42pVUTU8TURQ9971506EUqnwpEkGUYAIoYkwkRqNR/AlE4s5f0rAwJiYGF+ie6Maw0pCYiCt2RIyJJgVlocWg8t0pbaYzffOuCygUaAXv8s55d84759xH2FvEzLh24/bQ8tpqr+/nWTBoLwJMZFFjU91qd2fH6NjYmA+Adz+XQgFua2s7du5818/7Q/ditm1vY3dhzAxmxrvJ9/gw8/Hm/OyXqcHBQTk+Ph4CgLWPIVKpFPVd6Q8GBgbC30srLIWg4u8FEby8j8uXeszXb9/k6zdvD5w/0IjH4/ADn2prquXJpkZmMBHtMjShgVKKPM8TjmNxzj1koOu6UJaFldU1rKe/QwqxqwkRfD9AZ0c7lFLQWuNIDI0xqInFEI1GQaAdCQmEgtaojkZhjCl3vExnS3g2zGDDYAKKIjIxmA3MljFc6m7FgcxMUlpSa23W0xkWJQIWr9zY0BAqpRSYDzWFmpubC+mMmx199jxuK7UnNEU641qL5Owczra1pD+t/0JXV1fZHO5k8cr162cXU4stm9ksg3lfsIkdx6FTLSeyn2dmPqHMgEol8e8KyzX3bwr6+/sdWVX9tu543WVLCsPMovTKBLDWITZz2Q0v492dnp6aTyQSYnh42JTTkJPJZNWNW3euPn700PGDAkpDTQAKWuNkUyOejDytffHyVTuA+WQySRVdzmQyLKTMKWVHcp6/z2WgUAhRVRU1UkoKAi84UrC11qKhoY5aT7cAvHf1QmMQsW3SWgvLsujQga7rwlYKP34sYPHPMiwpwduhEAJbj8PFnv9bPT8I0HHuDHovdFe0OAgCWNYRVs91XUQiEfNnadX8Xp5jKQQVKZIg5PM++i72GMdxkM8fgWFrays8z4st/FwQggTCbTN2fDYh5uZmxcZGGvX1cZFzlyoHO5FIiImJCRmprh3RBX3VGGOYIEoxAuCQGRHbXok56sHk5ORK6Wb+BRGWUUWCZpR+AAAAAElFTkSuQmCC",
        "v_cont2": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACfElEQVR42rWUTU8TURSG33PnTJkpLUylfIoNIEtjjBpcSAL+CBZuNBrjVoz+DmP8EWxYGsWdJiYqCFgqLIhG3RkZbMemnYZy7z0uKGprVUjwJDd38yTnyfkCjjio5f9TyGE4OmBydWDBY+PjXQAyAILGv/+CXC6X2afHxsa6/8XRxOTU5e5014Ok7ymlqMnWilitjYqi0r1dq5cy6WDO8z0oItXCyU69TuVyeY6/bocXrl+9kp2emkYcx3DY2YOMhed1IIpKuDV7Z2I7KuLmtRs9k5MXEce137gw3MLs7buXeFeb2HVdYWajjXHQkDTGQDlsfM93RCQ2xsSuy8JuQmtT4SZOOTbp+8rCVhgCRQQaHc3R8FA/OU4js7VgTtDbjXUSgRIRRUR0cuQEDQ/2NXGOw5Rfi0gEikkpGGOwvFJAuB2C2W1k1ggyATx2oBRBKQVtDJZWCwjDFi4I4JAFKQKLtWBmTJw73XYOCusbsFZgrYXLjImz7bnVN3mIFTApBa01lg5guKv14Qx36nVwozbGWiRct61hK8eOg/xa4aehMQab7z6gFEVg5h/dS6fTMNo01XDz/UeUSqVmLpWCNmbPkGAFAFKpTgCCX7uXTPoIazGsFSFrhQCkU52A2CbO931UKmWIiLAx4nqeZ48P9hugv3WvbbVaJRGwFnJ9z7NDA30GA32te23L3yKIwOXebPbLo4Un6vXySgIi2B/Yxn1RO/U6Ep5b7Mv2fH74eEG9eLXYAbRwBFWLa0h63hafP3Pq/tPnLxeLxaLTbhyCIMBg70h+dfFZqVqpfgrDsO3VSQUpjA8PF/BfDuzMzIzzN2h+ft4CkANyRxvfATanV0LRpNg6AAAAAElFTkSuQmCC",
        "v_cont3": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADkUlEQVR42q2VzU9cVRjGn3PuOXPvndC588VnZ0YIFGGkGIzUtjbpgmUTTRNn4T9ATNwYTRq3/APGj42JcesGt8buaotN20AdKBKRQgqlrRQVBmbunTtzzzmviymGNlai6bN5k/d5T85v8z4v8ILFnqmHRUd4z33Djvjsv3itfnpgIAEgBSAJz0vlcjn3YMIrFFp9IOl5hRRQslpOyfI872+v0JoDO3Xu/LvescTncdfh3OJQkUK1VquGJnqTK7yXTiffl0IYxhiiSPHdSqUM1XgHwv42k06PWRY32hjWaDbZ/v7+N+gfKn765Vdf06931+jWXJkePtqiDy99TO09hbOnzp67/MO1GVpcWqaFxSVa37hPF966WE0kEv0X3r5YXV65S+WFRVpeWaVrP16n18bPLPFI6UBKSUJIFUWK3LirhWWZWs2PABbEYjFinCuljXFdlyzL8vcbDS0s4UspKdLGMG7puOuSgakJEDhjYL29edbVmWVx12WRUtx1XaZ0qw4P9jNjDKvX60xrzW3HYUopns2kWT53HJxxzC/sMiJwwTiH1hq3y3dwf/Mh3nh9DDEpUa8HiMkYKpU9XL1+C2HYwMjwCQgh0AhDSCmxvrGJjQePkE1nwJkG4wyCjIEQAuNjoxgfGwUANKMIrhtHM2oik07h5MgrAIAgCKCUgu04iKIIgwN9GB0pAgB+Ks+DDEEwzqGUwuxzCP/c2cWVmRv/SLiyeu/fCUeGBuG6zlOEqaSHV0dPQmmNsF5/irDvpTyKQy+DcwvzC4cItdZYWb2HrcfbGB5qUdTrAaSQqPk+5hd/QbPZQD7XDcviaIQhhBDY2v4df+xU4CUSUPoJIYMhAGhriyPdTCImJYwxkDJGhjRZloWkdwxR5EBwC8aAbADGENm2jXQqibjrolbdAxGR0Jqk4zimp6tT93R1MgAaAHdsWyilRSaVMr2FnDnYVSKyYNvcGGMVcsfNk0Cg/b0KiCBFezb7+LvvL/PZudsxMgTOOV9dW0NHd3bXtp3dTz77gtt2jB/svR/4fl/PicAPfP+Djy5lAIAxIAjqiDvONpucnJRXZm6c2dnZsQCQEIK1d3RUfy7Pzk1MTGTWH2yNVioVACDHcVi+O7d58+bV1dOnzw9s/vYgH4YhAWBtyTYM5HJ38D8i6uiALZUOIqmlYrFIU1NTBgArlUr8sDc9PU0ADABeKpXYM5550RcAfwFBDLR1GDH1SgAAAABJRU5ErkJggg==",
        "v_cont4": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADS0lEQVR42q3U3W8VRRjH8d88O7M7u+ecnj1tTxEsTTkcY9XGGIMovsS/ohf6TxhF441J/wODMRpMiHrVm96ZCNUbVCzUE1oJiQ0REioopKf0haZvu7PzPF60hdY23Ni5mcxnLuabJ9kFDnip/+wAIP/X1D6PqH0epycE7T53NpsdqFZrjUajun1TazSqQLXW19dX27bGllV3WG9vb4zqY1Mn33z7nWpH5TMbRshypx6uLL0LD6RpOhJFEXvvzdLS4qeOi1atko5E1npfFGZx6eEXnOOsLYfjlY5y2eWOlpeXR3B8YPDM51+eldn2A3fum2/l+LODp595/sXTX537Wmb+ultcGr8sJ0+99V3juRc+eWS/XpYTr70xVj/S9/p7H3wkd/6+Jxd//kVefvXUH9qzW9OBlnKl4qIwDFxRbBghGG3ExomLrSURWfPer2mtxcaJs/GmZVnuiBQnSeJtZLUIVog9SOtAJTZU3rMKiBQLFJFSh+qdSimlREAiQkSkDtU7FSmlBEJaa8Us1FWrqiAgxcxERhOyLMfc/BKIFDwzKCA4V+DGrdtwRQEiBSKCc27TXAFShMI5ECnM3L2HLMsRBARyBSOOLepdKZgFARHYM6LQYKB5DKExYBYwM8IwxEDzGKLQgIWht+76jx5BHFt4zyCjCevrG3sKs3yzJt+qICLkeY4bt24jy92ewvX1jceF1kZ7CsMnFIb7FFobbRYGmpDnDssra7tnWBT4534bxY4ZFlvmit0znJ2bR547BAFBC0OUUgiN3iwMSACGgkISWwAAs4hiJQCQxHbr+xIxoRFmQRSFUAoQEdHee1MqxWyj0BtjmFkZZo8ktlxLO3ypVGIR6EIKE8fxI/PMmpk1ESHtqPhKuUzes9H17u7Z8z/8SJNT10oP5ufR2VV9AADfXxijiVYr2chyhNYs9HTX75+/MEatVivZyDJEkV18+ujhxT9v3sT7H34cra6uIonjtj7x0uCZi1euTCy0F3RPT48fHGiOA8Dk1O932u12kKYpDtf7r0399tPi6srqzNzcHJXTFM3ep65PXJqcB9MrE1evdpRtLM3+3usH9T/dDUNDQ8E2jI6O+n2MAch+Njw8TNPT02qHHez6Fxieyv70Czu5AAAAAElFTkSuQmCC",
        "find": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADCklEQVR42p1U32tjRRg938zcm+RFZbEoXRu3dVlwWVDJEmOb7qRpWooi9mXehA24FV9FEPXlckH/CX/hj8eIKKjEsmxzabUQWpYt7H3wIVKRKKsuS1mhuTN3xocmmNZUtvs9Dcw3Z8453+HjGF2klOK5XE6Mj4/zcrlMcRzjPitgx90opfjJoIJ/warVxeKlSi2YnVt4d6a68GKpVMod7RkpbRgsDEM7PS2f9rKZj5ngzxitAQBCCKSp/Uun5rXN6NoXSineaDTSUYBsCMw9J+UFL5eJQO7hJEnqTu+f6v0tHtzf780DuJnLZhszs5XLjUYjPY4pDQDjOKburds7nPOH9u/eebLdbu8dbZ6t1L5kgr9ge+7s+vrqr0EQUBiG9hBDpRQPw9D+9sedi5mMf97o9M12u723tLSU6X9IhULBA0CG0tcJEJalLwNwrVbrPyxZp9NhAOCcfV5rbT1mvgZAzWYzAeAAuO3tbR0EAW2ure1qndwA3EsAUKlU7EgP+9ozzjkCYPpAo6dI1CNC5rh7NjU1ZQ8Ysh883ycD72JfphjOX6vVYsXi0gOMiwsObBMARkmmwWBKJZUV2du/E9HN9bWr08NBHkRkRs6/52f8t3ranVu49OzPcRzT0fjwwcPV1UYykT/zk5/NvpF//Mz5idOTO83mN3/GcexKpcVTU+eeeJsYvWO0vkHW/PL5Z5/sjI2N8d3dXfv/wZbVuifERwAxk+rrBKRE9JQQnqcTvU1Ej3EhHkl0svJjdO1DKaWIosgcYggAURQ5pRT//rtvr48/mv+Ue9R1DmeJiIPoK2P1K+RcR/j+ZWO0FkIsT+Qnu+vR2paUUhxles8LYFrOrcj5RTc7V0vk/KIry9oKAEgpxSGGg4rj2AFgUkpeLBZJKUUAeL1eBwC+EbW2JvKTXc7ZsrVWc86WT+fz3Y2otaWU4nTS5TbwrCxrK1yw99M0TYTn+Uly4Ck7KWAURaZQKHgb0dUPUqNfFZ7np8bsOes6w0PG/TA98LR6pVSuyHvZlSdayOif/wFjgFdXbr6rfgAAAABJRU5ErkJggg==",
        "bookmark": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABhklEQVR42u3UQUsbQRQH8P+bmbUGk2bxXGrBD+AhBUMvS6HgyeNe/DL9OC3sp1hSSDApLeQasfRQKGItNE10d+b9eyiKmo3RKJ58x3nMb968NwzwwCHXFwjISav1XOpe5m36DSBGjBgYS577yzl3GRKA35KtZnRmvrriWexBVh0aEQp7an6QuwA6TFMrWRaugOdhgooA65GRBlihAVAAzgiMZ3Q95+Y0oixJelZXCEJL0kDA24GEiPyHZE6fpbp4mIee8hP4SCABErNPZClQAQogVkSU1HuBJHXViBBgUI4bzholw1JgILlijI1E/gDcU9g3gRw1nLMA/J1AAr5urRjBr2Pv373oDj6+7PWGo4LtM9V+M7IrYc71Z8C1ohYgiAP156QodzZ7n/eZJI5parf7/eNTM92Z+NBZjyJDVV0I/nVlXcjOUTl9vdH/MmCaWslzL1kWCJiNT8OTvPvq7VFRfFCiuXDs39vt2mGSrAIA09RWtOOiiINWq3n+WSyE398wsJuAf2mirqcXBVyhAAAAAElFTkSuQmCC",
        "star": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACr0lEQVR42s2UO09UURSF1z5n3+HemZFJNJjQi4XxUWBIUOFipKCzAhOvxsRY+Aes1EyMiZXWamJjAIshFkYSYwIZZgqMWJMY8Rf4KJzBuXDPY1sACjIO2rmrU5z1ncdeewF/USIgERD+uxKBAoDW9PBga2roAgBIZVx30qiOxIVYbYKvetAtAoDxI9JJQp3+DQDwsj9Km8WPzKrXW3c4TOorUoaiO/DtdAwAAhAq4ztvuwyNmRn7va84kY90LymS1PjzIniAV2OBVPbZHfsnZjwBsmfnWlPD78KQTzonyIxfLlyqHd3zyTI50G2DYmytXbVCwkwaznsQ+pRWD50TiIACJjLGXVdEH6CVslYckxAzF9ms1ujyUoOlDIXSQetWmyfCUtddWA8xHpRjQIB03W2cTIB1gnwUPAIB4gRhqAFWWG9mt7l0cF7KUDuenE7Ho1rTM2bqaa05Q0SafnOCAF5EXD7UgbXy2Tm5GCW1uV22kWrMUVKbS50/bbwsFfJBAJG27S/kg8B4WUqdPx0ltTmpxrwLSGdrVqoxl5L6SqORjWbGz3aFTCLifrHEdYVMmfGzjUY2WkrqK1KNmc7WbFtjb0F7ri02s8wqrUEbHHGbYNEalGVW9VxbbP4O22VsERAR5NvTcwcCNh+Vom7vgSjSCkRIWxZawTkvTWODQ6Ur81+3NO1Hb2bD3Dltjkc5LrIi1RVq1Urt/bRlbnKgbI6VjnJczGlzfLumPbDnEwGAEwxhf469x/tszY8VkvqNfFK/Z6ycyZy8wf4ce6J4u6Y9cGTESzVm0jRmvq0/Cb5nA1Gy8FrKMUs15sLFhbcvni8MrX1duw9ILI/7A4yM+I6j9vnJqX2t6eHBn/+6La4q29bNqeFjXyYHuv8hC8vqDylNe2Xirqr8hUDK7bP0B4hHVcva6aoXAAAAAElFTkSuQmCC",
        "gear": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADa0lEQVR42r1Uz2ucZRB+Zt73223SWL2YHoQqBBG24qngQjZ+u/k2skWkB9m7XnLwIK2F9KDyESiK4qlFBRHyB6yXgsY95NfWBFMkCB72IJibxKJGohvN7vfOjIf9YYwRTzrHeed9mJnneQb4H4IBcJqmDAAzlcozlbnLb0yXq9eLxeLYoIbq9brDoOZ40D+h1uv1HAD5/sf9N8fPTix0Oh0543A+hHAAAK1WK/QrUwYW9RRgIwAolZOl6Xj26vChVJ5dmH32claqJHtzc3NnR/lKMl8qlWMASI91SsNEu92mvR/2P8rlci9KCBAJ80r8i2O6CcOUmSmz+0pVP4bJbz7K3RLRAzN7YXNjZS1NU1pcXFQ/RC4UCra3sfm1iEBUlZ3/0BFB1aAqMpjikvfukhkjCyFE3j8YJEwBWG232wwAbrAP6nQ67t4XW1uPXHj0O+f9c6KqaqbOMTM7ZmYCEYJIUNUQRVGUZdm1rY219+I49svLyzJkFAB0Z2cn6y+BfqZB3jF7VVnNVK5kqldMZdUxexAN/z3+V4IGO3w6jh8bi8amsiwTIrvN7C4SEVS19fn6SuU4ezOV6jozl0UEZnaobBdz584ddO/f725vb//OAODhX3LOrTDTOoifFBElIlLRdwBQrVbL12q1PIB+jghmpkQ05pTv8eHRNy43/nIf62SY/avyB+I1AM5H0flcPo8sCw+PAAPCkojcVTUhwgfOuSfMzNjxAoDPms1md2QjxwtmBiIiANrr9d4GcBREWqc6ZbpcvR55924WQnDM3kxXBXSrLwl7hYgTUQ3eeR8k+2RrY+35k74dejPXH0S7ZgDMVFQDs0si5jsR8x1ml4hqgJkQAab4EgBqtVp+6Gse+JYbjUavVEnmoyh3O0gIPopykfdeRBBC0BCCiIh553wURfksC+K9e70UJ9eazWaWHu+wUCgYAILRtyJyEHnvJQuvZln2PhHtE5ERERFxN4TwaQhZyszO+ygC4al6vf73IzM0eKlUjkuVZH6002r1wnQ52avM1XozleTmSI9x9WqpnCwNCKchHyeQ/zxFcRz7yclJ293dnTjzwEM/TUxMuMPOr29tbqy9FsdxvtVqHZ0mqRM6XFSkKdfbbWo0GgLAisViD6AbvW5vHNC7AKxcLvdardbItv/puf8DnfGu5qU4jakAAAAASUVORK5CYII=",
        "help": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADx0lEQVR42oWUTWhcVRTHf+fcNzPJTCZJbY01nbZUKeJH8atuhEqkInSjq4QWiqIu6kZBWqvExTiiDbZUC7qwLqSioE4VxEUVqQj1s9Rau9AKYjVJg630K85M5uO9e4+LmYbUpPiH9xb3Pn73vHv+/wMLqWhK0ZQryUwYLruFtqJ5K2VzjIgHKOw+u8yZ3WXBr0EVlWjc4nBkXOQE4Od+e0myEGzwhZM3RN35MSzcF2WyeY0iQAjBk8xUPOqOSByXxkcHP6NoSknCfGAHVhibeFTTPa9qlO6VZoVaM/GN2MyAdITkM86RzmFmWFzfM/HM4FMMlx37hwOIyVzY8h2nHnbZvn3WqkFIkmrL3I0DaVl/fYaejHLojwaHJ1ukHd6JoD1XO//P33snRguPt6EjXtolY6t2TK32qfQxwbo0tLjYFH1sbY5dG/ovu5V3j9XY9ulFuhxmSKLZRSlfPb9xcrTwAcUvI+UXBMS8yi5NZ7OEONRi1TsH0+za0M/ktOeJTy6w6f1zfDfRZPPtOTbflmO6iTgxZ62ZgMqem163HkpDXtkvfuXOM0sRWW+NijlwjThw73UZphuB7QcusvdwlQO/1nnkw/O0PGy8NYsTMEQtbph25ZfWan/dA2Jt2wR/t3Tnc1af9gni+rqEfT/WeO/4DNVWYNVVEfXYKPQ60g6mG4FgnY4KJhpZMO4HDkQAJtyiGhHABBCBemzUWkZK4exMoB4bfbXA0akWbx+tAdY2iSGERDC7edbYhsxLhQpECs0EHrojx7Jex2vfVnjwnbOoQD6jeJsTHkGBziswgYX2af9RIzG2rsuzbV2evowQrH3YHJChDjEmZyuMTA/FjWosItHlkYWuSHjlqwpLe5RGAk4WyDUGuINt4HDZ/d4cOLlCpo5rpmdtaFY9IrPBdwpv/VBFBDJO6E61q+zATF1KfL3SUKcH2788PAwlCWbynGGgarSThnWejzYv4acnr6XQ52gm7aa19y2R7n7FJzvHt19zum3sEfGUzU2OLvvcmpU9LrckQvBgwQxSCqsXp1jZ7+jtNELMzCzEUW5xylfPfT/w55kXKZry/JCX2asto4yIXzE29YbmFm2xZg180zc9Nph30t+t/Hwmtq4ITFzksv0kjco3po0HTm1dfqHtokvD4dLkKZpQklB4+fQmddGYRumV6iKarYQkGNlMhJkRWvWqEXZP/vbxS7y5JcZMELH58xCgWFRKpbD46RP57MCSISEMifk1Ig5DxwPydfD1L6aeXX5qtssd2JVVNsf/qWyuE6zL9C/CKdGyAmfarAAAAABJRU5ErkJggg==",
        "pdf": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACI0lEQVR42q1UPW8TQRB9s3s+wC6M4wTHUpAw+Igt5DgEIlEgXZVIkaC8Lr+E5mQk6ihFfkEKhK52kdItEkFxkA1pDCiFbYHBXXy+vaFwDvztGBjpSXurmXc77+0O8Pchxm1S/8fW7m7k/ORko9lsybHJRCylFNF49PNZuVyzLEs6jqNGCE3T1Eqlkvf4ydMXmczqq6XFOBgADf4PzAwhBarVauv0Q3nnvFZ7G9QOJJqmqQHA7XvGy9dvHMXMHWZWE9D9+OmMt3aetZZXUpsAYFmWnKSD77quACC63a7wfX8ESilt9b6hDvb3Yrncg6PlldSm4zjKtm0xVliiXptCiB6IerhcSymhlJKGkfYP9vdi+XzuKJtdNwqFAtu2LcRML4l6CNYApJTwPE8YRlrl13Kx+s9vdwFwpVIhbRoXdzoAM7jrgm6EgU4HFIn87gAAua7Lwmc3qJlMKCTc02N4X79Au5OCajQgEwlc23gEMPdLRP3Xb3LLBJCuI5TJggCQFJAL8ZkKTT6hUtBzawAR/HYb+vpDIJCcaOCUVyPsKxTRaHCz/xg0z3scR9rv8r8RXpFoPsI5YkRD3/cvPVFTC4M8HjJHG5omHA6HPQCerutTCaWUAOCHQiHheR6PJYzFbl5/d/xeu+hcaMwMQZMVYWaAgHq9gWQyqbW/NwYGLAHg7e3n6WarYbVabQnBBH+WAwKJpcX2rYXoYbFY/DE8sP9L/AITY+9MX8gEcwAAAABJRU5ErkJggg==",
        "plus": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABw0lEQVR42r1UzWoUQRD+qrpnZl1GdHNY2LcIBnMw6uyuv3jysq+Rm+dmX8CXyHEeQFEDdgQv/hA9zM2rC4KsIZuFmXR3eUhG4yKbISwp6ENXfVRRX9VXQDOj03f51qhqlmWpT9NIzWaH1lq3DMvLgsYYBgBHeieuwrfAvAkAo9FIXSjhmTauEXNHRKLzsNyQGiciQkSyooTSeMr0P84WCoY3b9+9SpLWvbI8Gtzv9/cmk4nq9Xq+Bo3HYwEgjae8lQ1fJknrkfPl5t7u7ocmCytZlqWO9A4TpSIigJAIiAgCwQ1Wai14/wmEae0PIqKVJuerZ++t3TfGsK4zz+fz5MrV60+jKIbIv9w7dwzvPaI43mD6y4qIQEca5cz3AOwXRUG67r3dbh8EcVtVBQ2c7G4IzMwhSKDncRxvHLtym4Av3pNSSrxzgHYaLfJfASDP89CMw/7wRRK3Hvvy6Ka19uMyrD77WVRAp9Ph6XQavv/4ebLQWqenGAXgz5TzPA91p2givdv94evhwydyZzC4uxLpARREJKxSKW2tNS9SdJHzRQDkVvZgPYn1Wqjmn621v2r/pRxY1QRkjOFut8tFUZyL/Q23HrwDKmB1lgAAAABJRU5ErkJggg==",
        "tab_x": "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAABiklEQVR42s1ST08acRCd+e2KbFk5NOEzVDciqB/Ab+Dtd6p/utCiXnroFxj2rlET3YiQkk0vfgz2SjBkPRCPakLpRQ8tRtNdfuNFDEFM5GJ8p8nLvMmbNwPwTsE4zBCRYH7OvwgiEqPqV0Hm8x/7wiUiHQBgxd7IfM5tfnpseXKiDegQANC27VRMN86zmYXb/b2d+qXvq9Vcbt6IJ5qsouugeVqTUmqtVouHBwARiXa7fa9PxrummTycnp27yKazUdxIBGEUVb3K0Q8iEq7rKhi28hQfMyIif8lvrgPigRBCMbNXLbvfiUg4jsMAwP3+Z+EUi0UEALj7H9YRUZ+IxZK9KKoDAHQ6HW1QPHIFx3HU+tetxQ+GEYRRr9QLwwMzOfVrZnau/bNSahCR8H2fR4bo12pgX12lUI8FitWJV3G/Bc3GmZVO/zbNZNlKZzr7u9uNwRAHV2BA5G63e6MiXq4eH64BABYKhQmvUirf/vtbYMV/AAAsy+Kx/mL8R5JSG76QlFIbe9Cb4AEjy6ac7ASyVAAAAABJRU5ErkJggg==",
        "tab_x_hot": "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAACzElEQVR42nWTTWxUdRTFf/f//79XOv2aMgikJn7EHRJtCTZFFoSVaxePvamJwZ0JhpiYvA6GLQtDTIxCDPIRmLAhYtGwaKJUArJpS01cmHTEIInTdL5n3rz3vy6mSMFwVveem3s25xx4BhpFlufgShRZBdnKPbXEYIrgHx3aM+zT0cNCNukwZPhyN7M3X7p9+y8ABRHQpwQ0iqyUStnfb7/1fmhM0SIToQgIZKp0lUaCP3OtnX38wb17vcciAqBxbKRY9H/O7P9iexgcbXQSetZkqCoA1oppt20+CKg5e0vrnXd2Ly21AIxGkZVi0Zdnpme3h8HRjU43zfJ5T5JYMcZJEDitVq19fa9WX3m1l/f+YDq07TRAKYqMnVtd5cNDe4bx4XyW9gY0n5ddl68akoTuL4tor0f4xpvs/PaiaK1m1xcW0vGRkX2ViV3XZ364+cAJ6MNu7vCwM/m6WE+lYutff8nYseNou0WyssLO85doXf+O2unPkdFRxHtVlSPAXQeghn2hESFVlYEB6mfPoO02Y8eOgyrN0mU2Tn6GDA6iIJmqYHQKwACIyhM7jUGcI7l/vz/nciS/raKdDgQBqPb9o//jNk1cy1TBGNFmk3ByihfOXaB5tUSyvMz43AkkCGmc+wZTKKgTPKrl/wTEd76vZ0OJTVOnhYLu+OqstG/Ms3EiRpMEGQjJf/IpIkLt4nlsoWAkSa8AWI0iO/LjQv2jFyd2jIfhgVaSpL2VZdu4dAFxDhkbo7u4iG80SNfX06HymqsauZOpnTs1O+tFQYgRVpGHD6Z/Kjh74FG1mplcThERVBFrNavVGA1Dlw4OVpqk0y///OsfGsdGHmebOJbK/PywOj21zQWzRpVsM4hGwFpHI00Xa93We6/dXfpd+7R/0oUtBfnn4PRM6vVdhSkLKkgZY66tdXo39vd7YAT8/+qqILpp7fPw7P1fjOxQoW5mTJ4AAAAASUVORK5CYII=",
    },
    "dark": {
        "open": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAB4ElEQVR42s2UPWvUQRDGf7O7/3vJ5S6JGlNoJYithYWIkHwA29R+BW21OPIJ/A4iiIWFoIWV0QNtDHaWmkKDBIx54XK52//uY5FcopiEC0ZwYGBgZ5955pnZhf/dbBjo1Wz443RxLtvCQj7VimrjTpIf9tjVeivc8Y5aSqasrMZ44bqb8ZndfvNB7bYblakB6PnNqf6WX6u2KhAFCIIjbse1MuZb9Svd93y6ZEyvHg069zqZoV3doldK+j7YjBNlkkAGpFo9TMWoq3Zt6R0sjd7yMDYjADIzk/BlzBi61300e8EZ5WH0JKkxFtgp48PafGc5HD4JYYaVpagEuxjq4f6RlLKgESi/9TpmfA6HyurDvsCDjAZd0jFd5ppwRWu6vv727pnwG1BO+OnL+NYMpBLMhrjhON2SlKuN+mPXi08PEpWxooZrngfzEE6wfsrgfdNZfLl3axJywhpnwReQE0gjuXJW8N6l7f6PvnY6BzScxzVnQL8+yFE22bKNVQB1GjcefHUA68uLWL2VrNpMqEzCkmAkR0pAwipP9vfQdjbMNWcmaY65YtAHO4F+WZ7CiGtfVvYBJ67Px1g594Kt7fFYJg3HOwIauJCL3rpLqx83/vF/qLb7O6QF2e5IT9d+Akb68RwAWZn8AAAAAElFTkSuQmCC",
        "save": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACkklEQVR42rWUwWtcVRTGf9+5981MxmliLcFViQgVa1GQ2YgrF67cuTCEdinUhUt3boII0Y1/gK5cdNEm+AeUClXahYUOiEVBsLEl1raBTpuUTiZ5993jYiYxyUxiKXjgbg7nfu98v3veEbtj3o27nXC2DWfbbTqMRhvo0OGjb6Ddhs73y5ml2Wq00l08a+y6G3cSkr+6cPOVVR2dPf26hTNvHtGjfh4WAAatmlGLcHW5zxeX17xRxKosNy/dka6BC+SReTeEz3z598mtonbFaB5rtOpMPQ++aZggAP0EX11xTkyLUy828TpYIWKsf3584a+5lU91gUUP1r7bCSDPuZrTxNSx/Ph+v7/+KK11q7TWLdNat0zrD8vUfbCVfvj1Trr++2raWO+l3Oum1Ov2JeHGxwAsLf3rCJlTlY4UQTEjHOGA77gWSENkQiA8I6ncy3BHVHKgCOK5mihdhKFlE7w10+DEdEERdr+fwNFYQXeIJu49Tlxf2eRJmbFdd9872aQWxW/3tog2/sH3CGZ3GoW4+mefH5c32D9Heeg9mmgUoqp8pCbu/4IEG6WzVfnouA0M4jgmmKzp8A5N0Cudd15u8PZMnezssbzdpQluPUx8d6OHHSRoBinDVN34+v0XODph//mD3HyQuLbqtOxAhjBRCNNA3H2AgDEso8FkXQOuOoRh9gGraIcLmmAMZsb6etotocPGRu4O7nKq7e1xUIc+tCmo9mtb593lDBALv0iV5I3JenMiBCCYEWD0hGE+11o1q7dCUHUOgNemFZmdrZh3++MT/fTSwu25++nIh0u/KJx+o6k8hsl27sZq6T+v9Kriycb5M+Xxbz8brMDE/xuLHlj04P5054NFD8xf3jMp/wA5AC7ymd2FVAAAAABJRU5ErkJggg==",
        "save_as": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADSUlEQVR42pWUT2hcVRTGf+feOzPJ5M/MxIZIiIoLm1URmYUuIgEFi/gPF4aKCC76JySIiAtBkVEKgiAoiotquxCE0qyq4KJgHUuwC2OEItaIZJyaaDVtOkmamczMe+8eF29GpyGp9MB53Pd45+N83/3OEdpRUJMfnreH83l2ijxwZH6eeYBc3jMhEbuGqnCrsUuNo1AwiPg9hcW9g4O3TbzzSNr2JERCwHjAQH/SgIE3vlzVC6sJ6aE6WxI5i6ogop2AAip3vfvnaBglv83lsgMfPOno74LQgxWoR/DeOeWhe4Rzi55vSnX6nCeorh9Yem3kFDNqO+k7ENVgecL1ZgfCjZX6emWP8ykh9OAMVAPl6x9XuN314msh4WY91Gw2paLTwCl+Qm+kDCBGNQoUEeeMuIQRhBjQGehKGFLOICIICOpFRIKdNfyXfCzGZlMRIFQwApFXXhrLMJJ1XPy7iTVtpZCbAhoDW4Hn6FfXMNt+7XJC5GGj4el2gup/LI89gT38pmqrn44OAQX+WA8JPEjrPXaIAkLCQiYpHc5RIyLBkZ06FIEgUp69N83oYALV+FtcGJ8rW57PfqgSxfqKiPjrqg/3QhERRTUGNEAUQa7b8v7jOVJud58vrATM/mW4ttbYUNUDBJdPBnOfHE+a9CFFxHTSdQK1QAk9BFHsxXY2I4g8JJ2Yy1dWeXX/HePUSidrp1+IEpXzBxtnpz4Cta6Fpq0HRmKrdFIG8K1bX7nelKkHh3jrgeVM7fQkBFu2una12fPo81NAxcX6aQpEUY20NaPbAY1gfBTJ5NgQTw0tUv98Wgm2RBvrYc/4K0lGnjsPnIhdZU1RfSg2nUlluq0FrDFY6EwvxlqeHl6keWYaH9RjsLEXHXsPfg88JiK/WQpqKq/3lQbGJxc2Q5e5f9iW78zacuQpG6EMlIFLICN69YKpnXlZJaqL1tdisNFDc8B+EVlTVdu+kv9dX/VmdCz49YugdmJfY/P4vkAXPlZV/U5Vc21P3lgxo/aZGbWqarZlUkRY/r30tqpqdfao6sUPVVXnOsBsx/q62Q6NO19aWupKdmc+TdvGJbv2y33pu8f6WzQrrWnxt7Sci8Wi6xw3vfJz38404R96UqOleUak7gAAAABJRU5ErkJggg==",
        "print": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAC7UlEQVR42rVUv29bVRg9577rZ7/YsZ04dqpQkEAoWYoqJEBVF4SQKv6DglQmxP/AwAYT6p/A1o1sDAxdaKbAUpYuyGJprSSqG8f1j/f8/N69h8GW6zomDIgrfcu9V+c73/mODvAfjiSu3tl/+GgAVPv9/lqger2O4+PjlGSy+sbVbs+eHZfC4sEvpaj0fhzHHoBZ7RcEAWyh0I+nyZ03W622JEPSX2JIUk+f9iPQ3aqUo9JmOVpq+YpDnuUw1tYnL9K3AbSXiZl1mkga01DG0BtSrxdkrXWTSeqNUbaq4zKgIanxOMsAGMw+ri3Jk6SR5EhqdjcDtkvjur96vdoGoy1Mx5QEkJC0bmmQBE/WJG2RvFjgSDKHh4f8+JNP7xdL0b1JkgSS6sYYXmkZCBAHhdA6Cb+n8fDLvb29cwLAWbd3b3dn60H3vA+ScM7h38AsLWQEI4NGo4rnLy5+3G1uf21me+N+7uGcc1me57oKzMujXKjgqHOEL37+XJ1hJ8+m3jmfv7tYiqQpgGAmJa8clSScHBpRAzea7zGyEQUEFKevLWVVfElwArCGb+xj3GzexAe7HyLJYuTeIQgCLQAlFUlqbgNKCsLQolYK1vka41QYTVIkSjxJRxLe++gVQ2N+zXP3bb1eLzrnEI/HKEUbOOp4pE4wnBE1ILyEj66HCG0OG24YQ4ZR0WJA83BhG5K+c/r87uZm5askSUMjfzssbxa+eTjCy4mDnTvISeiOPX74rKaD6pS90fRxpRy9nEzSR7vNre8W4SCJc8fjyROFO63zk+3t7cYfp5lyJxoSmRda5QAHTQvA+1GScxxf3L62c+23S/E1188C8H+enFQNSoVRmvv7RwP1JznDgBhOhVvXQ3x/pwbvvSdgnWNVkmm324X9/f10NW0cAGgwSH0jGtY2CtWf7taAYC4gAXkgnjoYY4z3DjSmR9JLyi7l4fLoZ2f9d2qN2lun3a6WfWkXAVvBYDgcvNFqPcb/ff4GmP2RnCi8qXcAAAAASUVORK5CYII=",
        "undo": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACC0lEQVR42s1UPW/TUBR913EyVHwoAwML6sDI1gUpAwi6sDGy8ge6IDEhZWJjgQGYqcTgH9ClgwckhCAsGRBqpiDiZ/t92U7iRomdw2IHN22DCwtnero697x73z3vMva/g+qQAKx4RIS/FgTQKETySswq8pYbxQE0CvKpqgC0AFwCsHVe5SXsSit5hUREtPSFud9q2k+kjjtEdCXLskyZ5KvFrLeHhwf7RJQDsIhoeUJ1NBpteaF6kKbpjTImdfwGAHSUjHgg3/NAPOe+fC109A0AlI4+fej326cqdRynAcDyQ/Ulnc1TL5BuIM1BDkDqeK/6DCV8X+4m4+lxnEw+R1HUBmCtRHu9XpMxxkKpn81zYJ4BADDicq+8vXhf23VduxzUcOjtLLIc3JfvqgNcHXxf7s7mGQKhngbSPK4Mis4YYIsxxn56wUupI2itr65aLxPCMLzOefholbTBUqUjuDB3F/kSSiWdE1Wuk13Xtf/kTwAUqKQDIBfC3Cvj1URyHMeqmngDLCLKf3ji9iRtWmmaff/dWE10u12rqKzJGGP9/rAdxePYC8RHxhid5YbaODryrsXJuDdNj2Ou1K3CCfUECzJxY7ans8XDUJlXOhrP4mQyHQ69ncr/ZnUFbcYY44F8AQBCRQsTTfYHg8HNcydbZ3VxY7a1Tu4Igctrm+ffsb6ZLrxgL7IHfwFRn6tg8+RGLgAAAABJRU5ErkJggg==",
        "prev": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABUElEQVR42sWUQUoDMRSGX2bqQhSlK1EQhR5AQXsGD+JBvIFbBVdewiO0C0cYii6rM+00YyaZTOyUIiX0d2ELUiu0qeJbZRG+5H/v/T/RfxYABoD9CXhVgAeAXQBeGIYbK0EBeNNzmsnbvCifuNYHTvIB+EREcWyqQhV3AKBNOZTSnEyAnhMsy01zAgueu+Jo9ucLy4yiaDdTRQMApDKNVqtV/frYUrAO53VtSg4AUptmHMdOMAaAJUmyL3Pz+j6yyHX/st1uby8qc/YCY4zB99e3fN/fsdaO7NiGtVrtDUCFiOC8Jr00Ox8MR7BjIBXqeip3qWF862NPnCndVwAgMn01bzeXgVaIiDiXp7kZSABQ2tw8CrHp7JQgCNaIiDodXtem7H5C+/dpWhw6B8V0TaIo2hVKP2hTjrmLU+a7Jt57SZJj5z7+FFm/lokryXStD3LhOG+6eQvOAAAAAElFTkSuQmCC",
        "next": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABUUlEQVR42s1UO07DQBB96yQI0VAghITgEBScgBtQ0PM9AAfgGqHiEEg0NCmRUGjdRUjG8dobO3FiexPHCY8Cu0FRCDYSTLXap3kzo/dmgP8eYhlI0gBAABBC8Fcr5+SVkoXr9o7CUXTf6XQ28/9aWcJaq9WqSxU8kuRgGD+/2vZBjtXLEAqSwnGcbc8fPJBkP4x9y3IOAaDdbjdKkRZv6fnNnFRZzidpqfFJGkWi9PxbkgwjHVu2OistVD6+AQCuCq77wzhJximlCk4Wdfpthdx/BgDMptnTfD6LNtbXIAT2V/Hyog4bAPDWdS/1JGM2J6XXb5Ks/XjkIkEq/zzWU0Y6pdsLrr6KtrJtAMBx/ZtYp0wmGbuuuiilcKGuo4I7kgxHydCW3ukqxl4GEnw39SS1dKyP93Z3XkjWhRCzSkfBNM2tSnu8aFsqXZplK/gn8QEZUgmiY4rdgwAAAABJRU5ErkJggg==",
        "zoom_out": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAClUlEQVR42p1Uv2sUQRR+bzdLkFxOo8EkEBG0sEkhBLRQEGOlIIhYiRCL3L8giKWIla0IaWzdwr/ARgRBvCSFBIJNyGV3Z2Zn9tft7V12b3efRe5CjLm7xNfMMG/me99775uHcIwREQKAtra2pgEALC4ulgBQIiLBaY2ItCE+fdT7saNgiFgCACRJdiNJ2/cN3TCoyH9sbW1+QcTO4TsnYra9bV1vJp31goikF5GrAspyomaro3Yd8QQAwBzFlIg0IkLG2EKz1Y7iZK9hOWJ5JwynfitV3WVsKYyTr0REO5azPKo0+4Am6UzIzSBq2hsb2+cAABCx3yAAAJBe+Dlpd1LPa18iIjwWtF9optTNoiTadfizQYEdx7+ctDsFE/7L3tuxf5rSk0ahET6Imq1yfm7mE2Py7vTF6XtK+SUAQLVa0eIo2pmdPb9qM/lL1+ARALwFgHJglwlxvCwJEbHLXXUbNXhFtH+gaToAat8AYBWQuoTaOIzSlpT+wywvyBbeLSIaJ6IpIURFCFHxfTorpZxUSlXDZitmrv9+UMrQKy42GnTG9YJIquD7oOBCem/SrFuEYXi1pwx9KEtHqMd5QRTFLdOy5LW+37KsC1GcvA6iVmEzuc65fDqQ4VFhW0w9b7XTIulkxIW3zoT66aog6xZETKi68iO+lxXEXW/lONADHSFiaZqmPj83/dHl9pW8KF/oht4xDAMMw/igXH8BqXxXmazMxHHcnZiYWOXcqyFiPpSpaZpDv5Vtu7U4SUn6URYne8S5VztR+kQ0Zpqm3t/3VwAAzr1anOz1QFOybV47CZlBwf4G9cI0zcuDmv6X1et1AwDA5m4tzYmCKI6YDJYO//v/Z+p6K42Gc2fkBDrtdO/v/wAMZw0y+9RlDAAAAABJRU5ErkJggg==",
        "zoom_in": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACrUlEQVR42p1UO2sUURQ+ZybjGhMfESEEI4iVRQohoKCCxk5BELESUYvsX1BEO7UQsbARwcbWKfwFaVIqeYAhENJEN5m9d567M3dmJzPZmc8iu4uPJBv9mnvhnPPd7zzuYdoBAJiItPn5eY2IaHJysiSikplB/woA2h42vV/8wJ9kzFwSESVJfj7JWtcN3TBQtL+srCzPMHP6q8++lK2tbZyLknShAOA3FIKmQl4AUZx663X7DhGR2U8pAA0ACyEmorgVqmSzVq/bD1ZXUSEiWhfuVFMlswDwY6P+oF9ptglN6MJ2lxthZC0urh0jInLdxlXHC54xb/u5QfNz0koz32+dAsA7knYLLTzvQlEC63V5r2sTtv+yAHqdFaJxOmmlhbCDJ53YgT/5eqOhgW+EUVyOj41+EsKdygq8YKKLrhvkSZq9ktKZHhsb+d4M4yWm4lYn/q/m9CSDuVKWYGbeYp0vD2j0FITLAEjT9EfE2n0iImJsgblC/WbLdYObebuAZfuXAFQAHJG2/7aVteF5yUnbxnAQBEebUayEE7zbNWUiKgFwmo7MNMMoOqBrr5k5Y+YIJb4ppWaXlr7ao6Mc5wUeDx6sHBo8oL3pNAR7qqzb3u12AYQqNtcs62zXXqs1j4cqed4I48IS7oKU7t3dFP412BvCexi3siJJc0jXXxS2N+94jXyrAITtzXlBKDfzAtLxp3ci7TWFmUvTNPXxsRMfHWmdaRflI13XW4ZhlIZhvPecYIJRvhk+PDyqlNoaGhr6IKVfZeb2nkpN09zzW1mWU1VJBjcIc5VsQkq/uq/0AQyYpql3792TiEhKv6qSzQ5pBsuS1f2I2e2x30n9Zpa1y15N/wtzc3MGEZElnWrWBhqhCoXbuNZZzP+HnlLHn67V6lf6bqB/3e7d+0+K0Bw+zO5T6wAAAABJRU5ErkJggg==",
        "rot_l": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADaElEQVR42oVUXWibVRh+3nO+L02bdM2yVE2WnxaHF63oRb0SpcWJeKMg2CKCFzJB3NVgCtoNvlTWxql0FwMvVBS8rAhD1BsvuiFYkQUntJMhYzHtki0paZOmyZfv57xeNFmTZekeOBeHc97nfXjeH0I7DBaYIxVL5S6C7V/XZxM/jhmrnv6IyUgD6fAOIznlgojRA9R5ZRoz1vRqf2CNvIGEa26/u/Fh9NuuqCWWmIECuom1fS4WIFLmQCEB4jBbVU3q3m/iqY2nQKIEKUjK/r9MVV3Jz9BmM4buV3uPcDIJcQVQNjde0I9Efc5WAco2LT109BTc5icB6BWnEv+88FV1Z/vjElGlZVMX4SPXwTAMARZhtpyLzM5PQz5RapTzUx6d0rCVx1LqWcXiTTkcOe1nPO9P/fdy9iPaalfa5SEMUHvGByF2/s6s5js879bLf/QreulGLbSLJBhErN1XI8YceHKZtdOD8EzEt94B6cOWWWMA7D90SDZqtb+j4SMLowsbpD929FztTtbAHL2PcZbAPXPaNDJLAMjmCpP8AOTublq/r2aDAIuR8/l/Ep8Vd8LG7VCrSKJnPxHJhuW4ACwADgAbgCOFqOTLugaQYna+k0MhvxzAcwCA5GUpDrCKQSSbhWs/ItinFABIoj+hwIL5aQCYyA+2K2SCwdqXaRyUpBOSGgATY59HdBaEnPeeIRvMtGcnu02jO05dEIGZlKJxEgQGZwAgHZ5gba+HgHgqG4DuW9Cd3X9vEi1WbhUGoh5NApDtopTioN8PgIjVQvYN7FZcyXK59dzWNkOAWz+hvEPOyJm1H8ZG6LfbxcolXSLg2A0GBHv7fZppq2tTT0SKiXO3XpOh2JS9mb20PpvIYJol5sjdH3YAsdTGK6NfWBxfLK14z+QSvayLzGeOjyyWtxIXtouxT+8+DmaCwaJzUpZYYobc+HzmhDwc+5prJVPA/kRj55egwE1T0+SO6T6pgLfgf/RtZVYrql46vn722NX2eabutURufD7zOvUNXpCDwShbDbjVTReAkIEIAQy3Vl5x6uWTubOj11oxPfYhgOklie9n3GFj1T/gC73KQn8Ryj4GZobWdxXK/Tn7wfAyAG79fXh/NT09EE3PHrKxO4aakLy8R3y9yAAwOTZNV8bBvbY1APwPdUivS3Yde2QAAAAASUVORK5CYII=",
        "rot_r": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADd0lEQVR42o1UTWhcVRT+zr3vTd68TGaSZyZ22mSS4EJoCq1MkRYKsYIblSJCgiuhoAsX4g+CxgRnBmpaSQXdKIo/oBuZCAVXIorJwi6E4KamYCNmfjJjM9NmMsl0kjfv3uPiTWoTJ6kHLnfxnfvxne+ecwgHBTMhNScTpS5CAmgULVpMH3MHprPnQOYT+YnDLyPJAmnSO09oHyZCBgLjpPYi/ZcK56XV/QlvVbOhRnVkMT3SBIh3cKOtKiLGOFTs8kqvJUKnlWo8AqUZrB0yrVfZ3WQIM7Zl9w0CdAPMAuSr3E2Y9AEn+Uc41NX9DiBfpFA4bOiwj0ugeWvFJWkGjJ6+zmal8DiAG6MpiHlgD6GvTMcvZntgBL83neijqlxcktXCBwEhrsIUrtvkhN0p5tYbnsOu9zRYxJBMir5F8G4PmQkp0MN2pbMh+AcZjJzy6muT+TcPTR/4aUkWSIP/6+EsBNKk7kxnk4Fo/JT+e2Uq/3b/dKF0a6zDto9v1moKAAUsm8DN8kKu57P3N+DOnyWvfWsAiCVXegdnyhtD75WuAyyuXss5xZsVl9tErrg66j9luZdOIDUnAUDaOCMjvSFm7yuAdGndNKQQNQAegGbrdrddTxGR3M8FkSh1EQAI5uPQYEn0KwA4HVoDEC1b/j0+Ge9LeLdykACYIGkb/zM+XYBAkg2A7w6IsRBLsE/IyyQIStMImH9p/FYiAKp1uNURmpnZT2d6iajZTqEGAMnyZ1WvKe15z4GIQyFAa3b8dobRuk0rYMjaFtsg4uFL2dfjlysfxy9mewAmMJMvdYwlZkkNTGevmL3xZ9Tq8rP5qeErfxbKH4a7Qie2GnUP0GSYHdRUqB6Jus8PT606FD1yXW03DOjgg7mJSBW804dH/RIws/qGqq+fIdv54tC7y7Xh/ugr7byzJouDfQ/EvpEBO8iNzXP5ie41ZFiCSNHuric9cGHppAg6PwkrFMbmzS8F8HWXJa9ZnqduazzkkfGkhvkW2Y6l1vIv5CaHPkeG5c5m2r2+WsDhC3+dMIKRj6QdOQ0QVLXIALQM9UoKdEBt3C7w9sZrucmhb+8la78PxzISs+MKAMVnymch5FPwtk+CiCDMJdLNH+/UK9+V08c278m9TyRZ3Dcnw22nhQ7Y/4QMxOjvoPnFWX8yjkb9/NRjCkRtp+UfE1KYZMudYDcAAAAASUVORK5CYII=",
        "rot_many": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADFElEQVR42rVUPWxbVRg95773/BPbtRtkLBXFSlIpQytgCBNSpYC6IaEyUCYGhFDZEEIQIYpM1aEChhQJhkjAwIJU2MoeMaRUSi0xIZEEQh2wn+3n3/di5/n53a9D45BYNQpDz3jv930657vnXOCkECEKYh47K6yZKIjC/8ZY07lbklxcFetR9zxOQjg+6xOA10g99+EfufB0cpnAa1DGGZHQBa3beq918+/C2Q3cEgOXGfIkBHPXd5fiicRtmvHkcK/xo4jeVOQ0jOgbaiod1e3qW6Wr+a8XV+9Z4wwVgOmy64KeR6efUk/PJ/WzN0uvO2H6pVjovv3n8szWqD5/4/5pRlOfq9ipNwdu5cV/lmfWOJK5u7sbi0QTP8Wn4vO9fi8kYAEKhmkgGTXaMeVcMuOzO9/fKcW/8meCnzeLxJXnAgDIf2b/TmVmJfCLJgCQlEqlkhLivNfdWyKDxr7vu3Nzc/sAYDutXxvDzNkQ2Ln8fL4/Yri4KlbxCgOGg09VMvuN+N5F84hcIcRLJKxqJpNt2Xb9krfnX3A9VyTUWUV5p9XxXg6GwV/Z6cyXBILiD9AoiBJ9/64OeiUZeGvH7EDA6Ha7rNfrKaH6zg/8aVKiJEwFpfyBD0V1vVxrLIEUefVhX+mj2d+Mfu1CZMj3D61SLpezds3ZaTab6Wazma7UnO2Rrey6s16pt14AgIrtrNtO65UDVcaBvsPHnehyAobjOGdExIQwoognRMQkGYOIHqsWiBAiHB8o6gAAoLXWAPRDMhiSHAKQRzOggDwSGZIAjJWVlU46ne4IoLPZoENSA9Ai2jpJCNQocq7r7kMg7773wUa13rxL8KlqPXan1mhtWJb1jBJW/t3ZZJgkRUS4sLDQrVbbF2PxqXO9fi+tqG5IqD9OJlMdz2vbudyTmwBQqTl9YnJiD40NALlcZhvAtsg9y67PfmFGo6rdbkNFInnbcc6HQ9GWac0Pw/C/Bx7NcrFYNLa2TqlUGt9GI9bVMAhEwqEiOYxFLAL4JRyY6wctGo8bnPxBizHBIgSgR2t67HgAbjCNk/XvqW8AAAAASUVORK5CYII=",
        "rot_all": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAD2klEQVR42nVUS2xbVRA9M+/ZL44T1+TXKE0cklZAWRQo3VQtJSkLNrQb5LDtAoFYVUL8iqicVE2TNjSoXRRYoSwQkrtCCmUF/UBhVQUW0AjR5uN8HDt2nI/97PfevcMiuPk4OZu7mLlHZ+bMDLATYsKICWMXRC7PHn76ev5R28DMZQB4NSZmOWZWZMfjBnpIAUD7lYVmYd8R8oovwKyCUvZjFl4B0dfEvE8gLwJCdwFd/k5bycRAD6mOS4+eMazaIWHjtBGqexJWChANaMcGRKDsXI5tp2OqryMHEQLRhtQyWfvAzBnHF7y2VlQhx3Xj9mzie6TkTyiRxoPGkYCJMARZmIE32Vd1WoiPAxjFTTAARVvILk6cUTVN3+z1F3H2Je/e6Wfx4x7LKCitTcMKePDVfEVETlnDvivJQ6byjKlzrWNlhesGQKj10vSB/deXC8He+fHfHiZvyA54mEh3AcC1W/9Y0bgYOxnG+BsEkLDgKgdCgfy8/dbRiDmuNKRYLBUzS8tebnnVXczm3MagNbyQyn57rGlF3+whFY2LgVischoO9M81tn+e9vYPJn4FgInZ9AURkUw25y6v5sW2S5Iv2FpEJJnKqGQy1ykiPhGhSoUASqY+aoQaDMOk7yBCojUDABHB8pkolkoo2EVazOY0EdxQOPggmcqMEJGIbJ1XEwAEOAQR+CzrLxCJJBaknKC1wFMa4VANeB0mgHBW68jOPdz0MoneFNNEJGWlzAzmJ2KECCUA6L0DxiaDTAAgwRSIxHF0GyDEnAIALrmetiy/AiocpfJSXOgmr0IhucY9ba+RXSy9AZBkV/jLtaJ3Uis1EaiyDK21bC9NCzFEqHMo0RUZTp98PiZ+QIgRjRvTnzVPqrWlMQ6Eo5GBqc6XDzbO1QZ8t5lpJF90fgFQYGYPgAvAA+AxkQaRKDFHSIyfnLrVPQCBEY0CREImf0g+y4BhjYgIGQQ0NzX03xp78LoWBP9vjw+ABcBsCXOq+tPJ876G5og4hfP/ng2lEbttbFm91v7pq/6mtvfVUuoHoPD29EcdSZOA9GLmXdOyGnTJdmv9Usp5gfp3RvPH72fD3X5n6ffJtfETQJdGL8qDKYQ4GD2kIoOJG2Zd63vecjoHpYc98UbnzrWOAQCem6nHqepjgaDzwVP1ja/4S5n72rVPTX8Sya1bRdsmPSaMPtJtg/M9bPq+MGrrW8R1gUIGRAAHwuDqKqhcFlo5fROj4xdxt9vbOAzb7yEAxGKMvj69d+iPYBVaTojgNWjvMNgAMT8Wre6IlH5OfNw+t17cBtnu2OWSVOZU7vJ/oMr9SMTF0XkAAAAASUVORK5CYII=",
        "t_edit": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACJUlEQVR42r2TvW/TQBjG3/fsFAExiZOqfCxIlWBtQYgBIUQQEwsDM6hL+QtgzsSAxNA/oSuGDkggVCGUIUwhfEViIAMQkrRN7NhOHNcOuH4YsFHUNFISIU46+Xx+7+e753mO6B83jgcAePj9wGLmkP5340KhIOdyuaBlGHfS6ext0+zsEVhmgiBigCk4llREz7E/nTy+cA8AMzPGAWVFUf4cE7Q0J9H1+WyWWBB53k+SJZkSCUESE/UcXhiSaSyQ4z+apnn6sKIuOpYVQNBSSkmu2V3nXRjs3VdUVbieY57IZCoz6aBv6RcAYEc3X067VsSDfD4vAMwBkCghJyPnEwCk6Cmm3hkAiYio3TavAMB2u/Mqmhdj6jnqf7/Ls8Zjn9sAIJg5FDPCBDPj24dC2h7gxfdW9xIzhwCEmBEW1ipFNXnm6maq9/GGKvvPti3vGhGNFRpEFEZ9FFZ8rh49e3lTbWxcdIsP/CNKap7DX4sjgY9N0XUrF8WmGINi4WuVimr4KAVfnsLduOXvug7qHW+ViEjTNGlEaCIiy7LSAHKtlrU87HKtZqtGH6Xw/RrcJzd913XRtILVqEae2E0A/MNGxuijFJYfwV9f9r1ODfUeJoNFEEnTNAmAqFarh7aM/pvw7UN46+d8z/g6OezAoDeb570A8D8/xmCngrqLu0RE5TISM92clmGt2M5u2x7gdcMKVqbe2X6TdN091Wh0s8PxGbfmN0qCdRE0aHR6AAAAAElFTkSuQmCC",
        "t_mark": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACfUlEQVR42s2Uv2sUQRTHv29n98zdJpdfRjgLyYGNRay01lJSCxbBn43YiH+BwcpSUEFjGsFGUggRglidgmBhZ2Onhzl292537za3ubu9ndl5FnfokaiJSsBXDcPM5735vu884H8IZqa1NRYHARb/VBUzGwDgB60Np+5fHO4bzEx/AzQBwK0HjzQzR+0OB81oeTThH8Nqbv1qXzG79SD1GqHqK+aGH72o1WqzwxeQuQ+YQUTKcfxTBbvwIG63MwBmlmVapikY+qgQIgFAAAaa/E43AKjVarO5sdwaGYadpikxM9u2bSRJ/3N3m86VSqUOACaiXwOHMEFE2srln9u2Xd6O44yIyDRN1syIO1tL5fJ0xMyCiHhfujmuf68vNbv1QHqNkL1GKJNU86bjXQeASqVi7qMJg0PVTed8J5Fc95vSa4TseL5KpGbH9VdGk46G+fMmGOprkxcmze0nSa+nsywTAHSxWBTtaOv9yuOHN4amzvaoDMTMxC9RaG1WPrb7zK7XUI7n6zCKddDc8lzXPTJq8p1BP2BnTLzKCxybYOl/WrUmrUutwk2VzC2ZQsdcLI5TK3QWSyvl19Ury7n56huFs6OotxkRdrs7Xi+fLMyNf9BKGyS7onf4gsbx2xx289fm5+jZXvoTAPCXy2PotG5BUF6r7BDSeJGTaCFLlLYsaajJ06FlpffBSgCad4oO2yIk6imdWK8OmmIEeZB5F1M5GH0NJDloI5cJqwfOz2QWRTOYyN8BBLBzwGgGihbQle8AVM2RTBJSW8gYGCMYhSkBmgZYAwxAMgYL7AZKDWBg7AEwLkigv4GesiG/CzG4T7TnZ4dpELQRHMg0/wZzLo40Ay8lVQAAAABJRU5ErkJggg==",
        "t_hide": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABjElEQVR42sVUsWoUURQ95963y4wJCRpEyy22E8FmO2Gn1DqlXbDRzlphpt8P0F6w2P2I/IZGZJmIRLtlwYzJ7LxjkSwYETITEjzwiseDc+89554HXDP45yXf3w/ZFUiyLGtICjcBSiJJTafTdHG8eu0W0lVzCtBajCf1k4TV8a93L/aefc7z3ML68ejopJdsWybELQkixMsIBUVEmamZAkBRFNfvx4UuRqPRTheGn+7aaBoOBoPFbDZrAJAAbDweW3n47T3JJ5IiAGvJGUlSUqlYPy3L8kcAEOfz+Tatt2tmva5zSoC7366b+ADA9wAAJEViKemOJP0txWVdSoKZ1wAQzqqIBFMAOj9dEAH0YkR/TWgkKwlf3O1hjN34SJikyqz+ujaFADQcDu+GkDw6V4ZtcwF3VnV1WB4cfOwoVcs9XEdvMplsbO7ce+Me0tXpCmatHFaSJFwsl29fvXz+6UL0+v377uaPnbal4K2cphDN3TZvpR9uInr/+A/z3NClSgEUxdkeX2Hd/hN+A/M5omSsJQvEAAAAAElFTkSuQmCC",
        "t_shape": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADeklEQVR42r1UXWibZRR+zvne72sSkyWpS2j6v1YRqmxIkTm86MDihjgQJL1T2YXTC0UQeiFWvkbsOp2iVS9chXWidbLeyVBhw9oNBcsyxmDdxNHUZG3adHRma7J0+b73eNGfrfuJeuNz+z7v8z7nvOc8hBWIDU4ebTfwD2hPJh0CBP8X6Eg8bnSNjLjZJ7ZuDzFvXyiXGcR8B1O09hmGLrF8GTs5nhLbZkok9O001TI5yQBcrfXTHsvqFscRg0BrL2K5PgYjZCnMLJV/BZDCxATdzeFNJyKl2VLJUZpjbHoDCmoDm96A5XNDbHoDDmTnkqMdEilVKlndLJ4ZBHXd48lvGhu749L01vYCEylXM0OE0NWFyg5X4C+XTQFIABaApKNDCUDXLZ+liRF0rjkgkp/b2ghHxLi3wxVo0xQCRJb7JxKNCtlCMryhiEgrToda/ZHPzvmffJUWgQQgQiCSewqapmlIPG4glyOJRmUw3MlIUPm1l4ceXgjV42S47XtvMUcNH8yf1dr5KEN0aFkUAEjWCQqA6uPH8+ufGHFb+6ZeGg7EDrTkU1JbyH097duYZs27zOraocb357algVdgg5DALYKitSLW09se20EipYLl47qrM7r78Z4HvwnEBp+9+N3lT8b7qv1/nvmYsjgNoKdpf3a3CtYcbOifTmcS9X2wR9WaoBCpiGVx0XV/NIlQTRpVXj+uBOvQkk9h4Ld3N/osDy481Bnp2HNMbV74wfi0OzbUuDezk5T5dsSeG5hPRAuqPZl0AMBw6YuS1sfyjuMuMXOVe0Om7tvkPRF+5GhtIXvYlfLQJa5hnzOTHEuQs3jgFMEWdjl7yPLf3+Ut57YA9ItaXfTY+HgKQGr9DJxD4w420v76P8LjEz8B57GaC8lwu8YMQAYKEIir2Fr3yzbAvfH42joNToZ5pqWThnT5giV4joF3nn/xoGequdkZm5iXB7JQFxO0RH2pXdpYJFUsna8cGytD29CfeaFlUKRp36Xdt1Pq+jNbmgeuug17M8PLrkYVVRS1hdELadqf+9wIRvc4f819K3AOa0euGczPsDfwhohzSkr8VLoUzKMXUlkQQhAARNL43mwPsfEm+0I+ANBLi9C6/BVdnn09vW/zldWNoX+Vmivk+g/TXpaqR9kwFRVv/J56q2bu1vP/FsX2qLprn2W9qb8Bm+6CMgNmtUIAAAAASUVORK5CYII=",
        "t_memo": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACm0lEQVR42q2UT2tVVxTFf3vfe1/y4kue0UZB20ITEiqaIEJBaDF0UBwWStORg0Id9gM4E7+DM2dqoDwcCEKhAymlI1toQFRooWraJlpipWli3rt/zlkdJM8kmoSkdI/25Ky19lqcZbwyEsZexsBAbAW0Z7Du24v4BnwQWJdF028PUpgW29oRvFk3MSTjx98W7RJRwsyQdZd/psfe6E3jVc/S0yFIXbKdhHlimMJcvlSd3/f5ox8k3NQiYWjSivk/vq4df/Mj0iYQd3msQ2xT/jK7kMV8gqnZP1P7jKDpR4Oq1T+g1gxYYiSZYbuwswzEZCBkBxpDndnO8brxNAWgMFlGB6jnnUK3vrljnSLgvm2wlBWcnRzn8NFDTpDksQJIXxpiOIg0TTg1MUII2tZFA2KEgf6+1cXMLK6GmG62GZIkYfjE8M6RdCNbziFs9jt9lTqEwOy9h7tS+NaRA9QbfdsARgRGVQV+uvuQvKiw7Tw0KEto9o9TbzZAkqJpHbAmw0ljRD21jE8/ObOmztZv1NYpUwXh7kbMAFJdxCmsbR6eeGyP0jNQqgoZMYIEEnIX7hFhGzncTVRFEpZWsFrtdwCTcDNice2d97zRczPp7ztSrgT54H7z3hrRXN5pm+XLELU5GDdiOy+KxRdf1s89vqIWiXWLwQwtXR0+1MjiyU5ll3snxkbZ1yx5tpCF+fmqWupcUNAMVllqFhGiJ/Gw4nO95x//3MVYJ2yRALSmSPIb7/6lBx8H3TmjsjXyfOX68Pu7bZv1lKdWG2P52uGDJos8f+Jh7tlMHvyLxrlfZ/TtZMrCd69Hcx/ZpS0+f1dh+6uRD3X7mMrWyPd/T48PrilI916Sa+X6ojV6tLgxdkGtqWQj0f8y/6XB/wWKX0LP1tZMmgAAAABJRU5ErkJggg==",
        "t_erase": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACOUlEQVR42t3Uz08TQRQH8O+b3f6AFtJpBRWiIfHgFZMuB/4BwsmL/AMm5d/gH/HmzX8A92DixZhI449K4gFJWFpWKC07aQvttrPzPNBFBaoCnnynyczkk3kz7w3w3wQz09oai3+G/TQWN8UEAHw5PJzYqtXuAcALZutGmKeUbDRVWTVbgadUcbhmXwureJ5snHTfRa82uff8NSvVPto+Vs4olEZhRGQqrORMN+UWNnaczpvPGiQoOXfb6i7NB81UtPQgk9tgZpuI9EjwDFNKzhrh5j/VnM7bTU2ZtA0QzEnPpObuiHOoRUQRAIhLMc+TsyzcTHrMUVueFnbiNDVjIMbTItzZN2PuR1kILXf7+Nghoii+InEZNpOddPO5CYdSpPuPHVtPTYB6GhB0hva9A5Nefy9vtcOXu0otnBIsRFxnRGQqFU/OZHNuIZ9zAOiksGw5JdFbnoeenvyBMgO2RVE90OMikbeEuEtEDIAoLlrf9wupdHa9kJ8sAtAAzl5wwAZBPUB6/QPsRhuGiK1k0tDKonWYS5Tuj2WfxRmK+GFCogwJejg0frnbBAnIaYne8iP0ZYYt2za0smg1conVIWYRkblYwJ5fVK3OEZ9GxOci5Mg0a3V9snfEe91O6bcFHrfT9q7vjEANM+twEHE1CEp/1S3xhktQw8y61x9wtbpfulLrnUODIar7g4i96v4qAJTL5cRV+9gGgK+eXwxanUY4iLj2rf70Wp/CxZPuLlT9gyfDuT9+W98Bzcarw2SgurUAAAAASUVORK5CYII=",
        "t_capture": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADkElEQVR42q1US2gjVBQ9972XT9PpZ9rQ0g50VroYPwPTpjOppW3AUVAQEepa3AsulFkoxlkIAy5cuFNcikI2IjqfCnaGjnXa6ehQIV10p0mmNm2SNp8mzXvvuEgidWgFwbd7vHPuPe+eey/wPx8BgHL82aEyQp9poPeQ9L3G6Ip1a6MvvnTl0a3vP3LUX4m4VwXmO8A/T/jTYaUuNbz3gKDbKF/3/oPh5fv3DADsI/T5cDDwylbj0ImIB6AJHqbSaZmGXFaaiyTmCPeLeEwrJWECMxQQAAIiuupx7vfp6acFADJTk3cUOWWMHxMXqkStlZxz9syDB7XjvsUkFH6Y6i5GGsrVQr7BwxtCidWbfsgAAL1vUoT1ZqA0dm/54J/kpAIAPJUWvJ7yAESuwgPL5Q4mEx+3hNg+rWkAQER6urUO+INmkEC9XVsKwNtzcyqRSFgAIKkBeIgIAWAeCin4HNEbVCqimlZMO8lPNWvLBJoDANmKSABIJBI2m81GIpHRoIiUjrrJc62kGSVLTc/tKNA80X6SQlJt7xTe3y3u/5Hf3dstlMpfZLPZaPtNTiYDikmoI8E0AGxt7bxHkvndPf6ZL5AkH23lb5FJRVIdx5fjlIkINzY2evoHhzZDwWC00WgAgBIRG+7qChw0ahdHotFVklpE3FG+Okl1JBIxAulyznWCifdetNYA9amTeAoAOD+vOTvbcZwk9djYWInefRMd6NMAHMlmNBo11Wp1E7a+0q6hf5z/b4ZINpuN7hT3r5fKNZarDe5Var/lcvlYG6NOnOXMVOwNQM7WegeuPXnzZuNx0M5OaVJr3f3w4dpSIpGwnTqTEBEwE594U0FGR/oGPzZtm946bfSFcKHwCYAGARGAndYQkdUj6lV73oEPW+0I4O2I0s8U8/lPTRtULFl72OW8MAmF9LwwlaKI+LXx8QAXF7m5vq6fKBSat+fmFJNJAFcBzCom7yC3wELFuWpY65aCTDz2I4CZMz+vBgStqfovJxOfWBTKpZCX4Y4zwX5jdPZibCkjE67HGFVx9v7oCy+/k1u4fs0r+RKer2mvvqXylwEMhETidfrO+hq3hNSUMgYAjODdinVfGy0XrIcHaUjsp9JpeY6YEecXIBIH7AohkwIJE4gJ4AGBgapb+ivbtln+e1J+PX++/6wx9FpzEMBWve5G1terx+/DpMLKjVO7hdbdBIO6/+7dIgD8BdQH6xP7nt0QAAAAAElFTkSuQmCC",
        "m_view": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADHElEQVR42tVUS4gcVRS9972u6k/6M9Nx7PycMAk9C0FcKAFRkaALzUJwY7YmgmQhZCVZJNIhIogQEoSYVQgSUOlxocaNEOxGXIRZjFFICB1HZGY605+qrq5vV1VX1XFhGlozGrPTCw/e4rzDubxzDtH/egAIAKnpU6/XJQB+WKIHPvo7DP8FxETEzJwQEfVMc1GQ+mwUR4tRFLMquacI2Zydza9MbzHB0xZkRETU04eHh5b38yhMEI4jjCzd8C194No2IgCGabe1gfXuC7VaakL6J4UTsvX19dl8YebizEzh9YHp3ChIOvvVLUP7cFk9EBMXX90X/XD60KNeT3ePl2dLh0b+aMUy7Df37KncmCjlaWXdvv59sVB4xrCck7sC96PKFa5GIvfFtnyhSgAFI8/yR/Yx78z8Z7d/67xW2V76GERsD0cHdu8urwEQotlsSmZGRxucq8xtfy4Ix1IQTpvFkvf83sxPquRquHwp9pcvR2kRFRfmtn16c22AmZzyueN6Owq5TEWq+BpAemlpiZmIGIDo9odHslk17/q+VBnqqh6nD1+VJ8LeHdW89oEAEZVffCeJK0/w8SfdS28/pf5qBJwoEoGiKNK1zcvz8/ODFBGBiIhSWB6NA8iEhQdOSqkwk+b4aFDevyv3+MtjEAkqL0AmYSxT8ls74NtRLBRwEOWVgozSfkhERI1GIwVAbPa0LwFgMLThBTEA4OotD3vP21i4EGL/hQCVsw7OfGcDAMYJYJgOAKCnDbqahmKtVhM8+Z1223pEzSY306qa9zzvlOUmzWpFZg9+4s/9MqSjipRFQnTl+htKi0h1xsm4mstm389k0lXTMA/u3DnXBCBp2kd37/afthyvZZhOqBvme3c29MfE/X7Nd/r6W4bprLmeb29sdo9MknNfbomIrrdaRc0wL3pBhCACNnu6u76p/djuaCvtrt5x/TFiAPrQaqyubixuaeytYtR1nB1yTK8IQS8hTqpRErMU3GeW11JC+aZUyrQmypg5/qfQc71el/+iQHha2QOnVquJxh+VJe/VmLh3Tz0U0X9ufgdtGw1zJ+w01AAAAABJRU5ErkJggg==",
        "m_edit": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABhklEQVR42t3Uu0oDQRQG4H82F29BjXZ2gpdCbCRpfAWxTWEnmN432DqPoDaWsiJYiJDGCJEIkkKilYWywcRNsnExZk2ycfJbmIiFgrtJ5akGZviYOf9wAI+lqqpClQoGUSTF11pVlX4xBQAqieMZK3G0AgDUNF9vX3GLCSE6XN4Ih4LidHRs9KKSOIyIWEz2ni/cYnouHR4PLSUnz2+iTcuib3jIarXbsdD2+hlUCMUtFppdTY5NFKPl6HRbDgVlwBecIuWcgCCWDsWfe6bnTsJmg1fyPkl7Z9Ex9UvZeKyzltC2PsP5Q+I/YrsLjnWtyXqrw0K1GgcAplJ+j9i8Y11r8vWdNApGF+MgsEK8e+5/YLmBYAIQyOdvp8xX2R8mhABJJZ/JjBSfG5fv5Rvae4veMABIdf/QU7m8Zrc6NB4f3qp3aVl3yIJhuMMAIJvNBgCgVDF3SbJmO6w1ScML1usfyeFSxTqwG81903rZLBb1CABo38aSW9T3W+r9Dk8/Sb/nmwH4AOujnVTZMYxHAAAAAElFTkSuQmCC",
        "fit_w": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACD0lEQVR42sVUQWsTURD+ZvbFdbcbahUEbbGoCN6bg2BBi7/BkIvgucceehG7piJS0LNXvUn7D3qRHHrrVRAkhKRiNrtpNmJJmt28HQ/daNJWiSniwFzefDPzfe/NPOBfmIiQiND/yh+rw/lqtT0zaZdarWaFYXhBRIgB4GsjWLEdKnueZw8kjElEAcA521npxbrs+/6UAgAmspVSM0mfaUKJU4ZhXESSMgSg4ziWEdCmGMBpTIWOYkMngNZaawBQ6RkREQkAuMLPACBPGgDuuaKGk0tF6iMPDRHa+ogBIUodI+AWM6FISbEIzL9qPu53ujulNfo8jJld37ulbOtulehtAYiO8/9VkAi3o0hffvHlgW3ZT8BqiTO999de7pVBxpF00SLgm6TMwvzr/UeWPtz4tDq7LQmI6FhBAgCthRM1h0TuCDRYZQqSaGCAFgKzAdE9gNX9fiIlANsg/LxrHhoB+KZpeE+vvuOgciWJussSxYvdDmcPTDV9YKrpboezEsWLSXy4DMilyurceiouOSl5YA83jcpG7psAb34zJDupY3dXMrkcxcNBPgHfyus1EYb7QcEVhgiNuJvGRGhhAXJqy3ojKPrNtm40Gs4km1IP9p97fjMOgiDLacB0HIdbrRZNtihkWpataPDW9TC8HoTfl0RGN2CcbwsAPK99ox4Ef50/vrmuy2epftb8P9oPc0APNxN6OHwAAAAASUVORK5CYII=",
        "fit_h": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAB+UlEQVR42rWUwWpTURCG/39OEm9iilbTLKQmRdBN0U1cKK0rfYV0o0h9CpeXurAWqYjP0FX6DgoKutGN4sYsJGms4WItttJec+8548LckqAxSUsHzmaY881/Zs4M0WOqyiAITooIMZIVUChgj6RNPKkERFKbzeZpLzdRh8iktbEC6ILZjYH20Fw2F0r7W3gLwAtVNSRtqjcfyVDVPRUxXhwTkK5y68SBFKgjRCEAHFQopGUjeSCOw/6qlaoeqH5Wr5u5nYvu7svWjY4zc7crvx7PTs24C+E7rVQqiSJLckR1vgoAlB5uvCo/2dbpVc12sw5smgyE1dRgiW76Ueue5E7Ng4hN9HURALA++N5g4AJctaaGtB80Ctc0jlJq9T0AoAo3PhDU4CO4cb/8VqPwE1yMZufcm2FVkpHqKOIBxBls5Y8OHNOGA5fo4FwIKL7j7M8jAJXFWej5lcZVpr1LEINSZvP64YE1yPoCraq5zLR3R0xGaXhl2LfBPyaFyanW1ABAaXnjdXll015b1azv++KrShJzqEJP+l/mpx60FseeZVVlu42cSNDnLxb3YmDGBUGQ6fcXAWD/v/sw4+UbJ7L5iU4nAvmHu7WdBbALSXsHS8o5h/2OxY+d3ZsAng/chwCXoyjOWmsVcOzvXd/EaRRHRAqfj3Uf/gY1Pex9soovCAAAAABJRU5ErkJggg==",
        "v_single": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACHklEQVR42rWU227aQBCG/1nWHA3rQAS4DglQVepletcn6CP3FXJXcZGqrSLlhFolAVVAY6i9651ecBCYIJDajuSbPfzzef6dAf4imJnSa3LHQQGg0uv1AHip3RHa5+f4cnEREdEsfZfS2fr9fl7mih9VpfzOaGMZLJaHGAARMRgw1o6m8exDq16/YmZBRHaLkIj48vK+0HzlvDc6zg+GPyFlZiN/kiSoHilUVcV7/jHtALhaB9v6ZWtHTHQUhuE0NxgOWUpJzLxMCG0M8vmsdV2XhLXx3hoqpWCMFo36MR3XqiBBm4VnQAginbCAlPtNGY/HUF4Nt/ff8fnrN+RzWVg73xOCEMUx3r55jW7nDMYYHEQYxTG67Ra67dbOJxPpBFJKHEx4fdv/t4Tt0xO0Ah9CpEo4ryG0sYcTuqqKx6cBbu76yGYdrLsca42zVoBmo3EYIaBgEwvXLeEk8CEzGTAWgiAk1qLsurCWX2wzuadZwWAsAAHiFe2ueFFQEGE6neHxaQgnK1eCRAStNRxHolgsHiaoFGCZUSoV4fsNyIzAChCExCZwS6V5kkNNKVeqPJ5McH1ztzAFG6Z0zlrwCwWGMbxX0PM80sZkAr9pA7/J642/FkmkE4ccZ+u+SA/MMAw1mJ8BiFmkM1GciPXvd2yENuxoYyAsj9Ym2+Y8XAoSET88jLqqpk4HgwETpYaDMXA9D9PJr0kQ1D/hf8cfHroaupib9skAAAAASUVORK5CYII=",
        "v_cont": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACkElEQVR42o1Uy1LbQBDsWa0sgWULDBhs5AdOKMIpVblwyy2/QOXDcswX8AP5CiqHkMQUqXLABRjswhgbY620OzkAiZ/Bc9xR93ZrppcwVMxMAHB11fyYTPlv2+02CyEIo8Wu65DWcavfu/tULpdDImKM1zNZrVZbajRvuvxCGWY+u7h+/4S1nnnkOHG3K2gpk1C10zP9o3rCjpMgYx4FCCEQhiF2d7ZNqRhYRoUT+IkD3weUUlQqBFaQzzHRuGWGEIIizcJyXH6RsNPpwPMzuLpuoXZaRyJhg/kRR0RQUYRSYRMb6+uI4xgvEgI+jDbwvCSCzRykZYHxRAiCNgYpz4MxPA089ezRF4B/XmnKB8yQ8mXLQnRJWhmrc3dnTuvnbNuSxi1XSkXteUnbaP3/oTAzVavVaBCqXpDP+UE+N8MARLcfwhbW7bCjCS/MTETEjUajspjObDYvL3nCr5ScSqVI9Qe9IMh+Hb+JZklgZmt/f39q7+DgAESkp/VoPCn1et21ncUv6XTqXRxFhgExCniMWWxMu68ePhSy2RNmFkRkJv4hEfHR0dnCRt7eiyPlNls3kNIaodNaI7PsI+On072L/haAk2FhE1My5paJlu/v7/tOs9ViKUenHMUxXDdhPM8jYYyaI3o+4jgS69lVWl3JgATR+IYKQRRpFpCS5oqev7SC32fn+F49huskYMzzjhJCpfBm+xUqW6X5ouf7PkKlUCkXUCkXZi0BwkhDSom5FKb9FVM7rZufx7/Yceyh54sQhgq7O69NsRAgHgzmU6gi5ZWKBZFdW4MQ9DcGBAIzw7alsISAveCKmYRExMwsDg8Pe/li8nN/EO499B8M0+QeSktCs25a7H572l/z3P8DXbBc8+sBruQAAAAASUVORK5CYII=",
        "v_cont2": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACQ0lEQVR42rXUzU5TQRQH8P85M7f1pi29VRaEr6srEzBN3EhABMGn8Gl4Axc+BG9hTPwMrgzGxDQh0RDE1oQCLbXcO3OOi9LSFoQu8Kxubn6Z+c/JmQFuuAgAVJWuREQ6srsOdWtjY4OvM6pKBACVSmWs3c4aXxBtNhq9DfKFgt4rlSiKojoA7OzsFE9OLF/mbnOJ4jiq096v2vNcLv+SodxtQbe8qoRhyIf1oxek8qlQHNt0aQoAPOTUsqVGq7lpSWmhmA/Hf+zuQVVBndC976iQA6CPUi8Is8Gd79Vqt189x8yYnZ5E86SxZkFoOS9aPzzySZKYfpgJAh/PTBkQtZhNC4AeHh+75DSxQ06mJidYgaYVUbaGqTx/n0QHj0ydFpCqsogwACrPXXQMEDOTKrFlZjhRvHm3hSRJQMRnOwsymQzWV5ZARGDT+f/6/RbS04tudXkRTAQrIrBMWF9ZumocIF4AAM+e/NuJKvoSfhwp4au3H0ZL+HR5AaLnc6N9M9SfcO3xRccAmOk8oRfFl6/fkKZuYBystXhYnh9IuH2JC6xF+cFcJyEAJQJKxSKc9wPQGHPWHFHxqgBQiopwbtBZY3qvglWVgIkknp32wzcFgAAgJbJEGgCQeGbaD9+UMwdRBJZBVQW43U4zxIPree85F2YB1QPLZh8At/4k2e7xe1MgwuGtDAhaI1UNdvd/LwZBYJxzA9A5h4nxcdRqPz/fjeN6tXaw6r1nNzwvziEfRWBJtvG/HlhzjRMi0lHcjSf8CwpbSaL2qLdwAAAAAElFTkSuQmCC",
        "v_cont3": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADVElEQVR42q2V324bRRSHf+fMrL12HHu9dupAk7gGVCiNSitBShW1KkitxH1veAMk3oaH4KLwBFwiKlUICVSiVkSIqG0qyHptb/xnd+2dmcNFQ4ogoRLq3H6amU8zmm+AVzwIAESE/gWI5L/YqXNOAqct9DImIqSJSHZ3d+t5XlbWDqXX69HD8TgnogwAHidJc7g3EiBB7/Jl+uYrjInI3r0r6vZt1Pf2fhIEAUJuEhGN6Nkf0adLS7UvCMIEAiCwTia2yLcLK5+FzfDzLM8dE6CU5slk+uM8V3fKvv263li+Yoxx1jnSrGmSTr9kErraqFXaSTIKo34/tNaEQX2pO83zLrH6QGtuxoO4FQ8GLU9zU2m1NcdhqLXaKopFM4qi1vjwMKwtlZsk8hGDkBrrJEkOzUEUSZbl1jo461zBzOl8PpfhcGT68cDNF3Nhopl1zjLzbDZLJerHbjhKrHVOBJhq54S1Ytp8922yVkgpJidgz/PIGMN+uUxX3tskESGtFGVZwhXfJ2MMd1ba1A6bYCYoZhIh1swM4wTf3fse4+kUF985jzfOdZGlBVphFWmW49t79yEi2L76PrT2kAwiNFbX8Hj/GX7eeYTl5RpubH8IJoJ2zkEz4eb1a8fXbyxQqXpYLAq0gjo+uXXzmPXjEYJGA0WxQG9jDb2NtWPmRPA3w/snGs7S0w33nuyfbnhjewvWCpRiWPfCMAzquPXxdYgItFKIB8mxYXf9LNZeWz06Q3phaJ1g5+EvmKUZzm2sYbXTQZYWaAYVzOcLPNh5BBHB5oXzUEohGRyi3jmLqB/jt70nqFYruHTxwnNDAEIEBI06Kr6Piu9DnEB7WkScMDNaYQARgdIKMi/E932IOPHLZbRbTZRKpeMqaBHnMZHrrq/Zo1hYY8HlEmtjnS552r3Z67q/3v9kkqpKpcLGGHVmJXRBoy4A5PmlwNMMOhCA87wogQDFio21IKtGrDACwLNszkSEql+CCGaSUYoqzQC00nwBAKj6JRAkIhHxnv7ev+Z5njLGSK1Wo/FkOum+vvLD/v5+q9HqXIrjGFprabfbNB5GTzudzq8HBwdv1cMz63EcC4yhWhCA3eLBS1v5fwOr/pk2InJH3eNTGJ+wqXvVPwD+BPSa3lgkL0NBAAAAAElFTkSuQmCC",
        "v_cont4": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACt0lEQVR42q3V3WokRRQH8P85VdXdySQ9PU4ifgzbKyLLSsxVjIqI+Bj6MnkDwQvBJ8iLyCqEXEgMkQ1E3aDRZDbp9GamMz3VdY4XvROySUDQ1FXxo6r4Ux+ngHtuBACqSldApP/LrsNswE0DgI2NDb5pd80lANjf30/j+HUzHJ7K2tq7JQBsbx90o8hy90EXeZYVAHBwcNAdj1+1Hw4P595O0wRliTzPC/rz75Mv04XFb4IK4shRWbz4CgC6vXSzrr0kc4k7L8qvSWVrsZtuTqc+xHHszs+Lb52h74xLnhjmBRDxaDTeZCbz0UInWa4vq14SuaVGdFVAq0nklsqy6MeWe4CuB5X1udj1y/K8n0SmB6IPR5NJnqWdvKpG/cVO0iOiLywRqnraaFVNPAAjIhNj2i15cTHyABhEFWCq1i5aA1XM7BuBVJeXYeq9JWBkmyZwHFl6mA8IABljSKQ9tJXH7xEAUlUWEW7t0ZWBiFSV38kfCAAKqszWWkymDX7e/QUAECSAuT3Q73/cnl0HsJnZ1pV578FM2NndQz31MEywTdMgiSw+WHkMADBsIC8jfvbJ+uw6QMJtc85BRLG68v7LMIp/Sbh13wnX/lvCqQ/47dkftxLu7u3fSri79/RWwl9/P4T3TZtQRJSZkC7MAwCYWWdPKcu6bUdEoaqvGKDOWhVRLHbmQUxQhVpVcdaw9PuvBQCioq6RBgBk8NabrRFZFXWtvdGaqmVmCxCWl5cCABZRxww6FoDHVd0BwMbQc2PoOQC+GF/OA2Conlk2f103UhQUTOG9x6RuYgBMpCekqu5oWHwcEVk1GpZ7vScAMCwuPq3r2mRZhrOTo58e5nlxfHL2eR0CZ1mG8vR4ZzAYnD47Gq5FzqbWWo1Ydu6lnt5VYM21IhluGgBpX9mdxtcWlvv+AfAPdqKmOcUeajoAAAAASUVORK5CYII=",
        "find": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACgUlEQVR42p1UTWsTURS9dyZjar/QIIpFEQRddSFUFNwI3elGEFe6qIvmLyhuXQrdC27cOgvBfTcuxIppwUWhdFOaZL7fZDKZzCSTzMxx4STUNEk/Dgzz4L573plzzzymMQDARCRtb29LREQrKysZEWXMDDorAEhTavJJ/YVRMmbOiIjCsPcgjKMniqwoSJNfe3u7m8zcObrnVMoODur3WmFnJwXguD5s4aGXAK12R9R06wURkXqSUgASADYMY7nVjvwg7FbrurV22Gxe3hdisWYYq80g/A4Ah3V97SRr/hGqkA3L2fX8lra1tb84bp/jNr+2o07sutFNADyWdGC0IcTDFEBVM18REe0DxbyJASgAWNcbt8KokxpW413eWxjlG0ZDAj/1PD8rFvgbAL5D1GNm5E+fiHhpqXTot8I/EuNZ3n9sOEPJYC4mScpXoyiZljeWOAZTcVJdykNLMuhHqXSJ9dnZ+3mwCyO2SEKIxYszxWWAf44KOprDDADXarQJqdm6IF/4wMyPiKivqqpMRMTMKRGR5bhvF2aKs5QlG/lAMPUP0C3xPMkAvx1+qdftu4N6tVot+UHnvee3U81wdkzTeTlpKMeCXTfE63YUp2GnB9NydwxL/LaF1+ungGGJimj4ZreXwrTd9XGkQw+YOVNVVb5x/cpn29RuJ2n2RlbkjqIopCjKR2E3lhnZxvzC/LUgCPpzc3OfTNMtM3MyVenAt0nQNLschDGcht8Lwi5M0y2f6vMBFFRVlQfrwZuIyDTdchB2c9IYmmaWTyNm0mH/k7rNOE6yoafnQqVSUYiINNMuxwng+YFvON5qnt/zYajUdterVf3xiTfQWW/3wfovEVHq6STJ+1QAAAAASUVORK5CYII=",
        "bookmark": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABhklEQVR42u3UQUsbQRQH8P+bmbUGk2bxXGrBD+AhBUMvS6HgyeNe/DL9OC3sp1hSSDApLeQasfRQKGItNE10d+b9eyiKmo3RKJ58x3nMb968NwzwwCHXFwjISav1XOpe5m36DSBGjBgYS577yzl3GRKA35KtZnRmvrriWexBVh0aEQp7an6QuwA6TFMrWRaugOdhgooA65GRBlihAVAAzgiMZ3Q95+Y0oixJelZXCEJL0kDA24GEiPyHZE6fpbp4mIee8hP4SCABErNPZClQAQogVkSU1HuBJHXViBBgUI4bzholw1JgILlijI1E/gDcU9g3gRw1nLMA/J1AAr5urRjBr2Pv373oDj6+7PWGo4LtM9V+M7IrYc71Z8C1ohYgiAP156QodzZ7n/eZJI5parf7/eNTM92Z+NBZjyJDVV0I/nVlXcjOUTl9vdH/MmCaWslzL1kWCJiNT8OTvPvq7VFRfFCiuXDs39vt2mGSrAIA09RWtOOiiINWq3n+WSyE398wsJuAf2mirqcXBVyhAAAAAElFTkSuQmCC",
        "star": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACr0lEQVR42s2UO09UURSF1z5n3+HemZFJNJjQi4XxUWBIUOFipKCzAhOvxsRY+Aes1EyMiZXWamJjAIshFkYSYwIZZgqMWJMY8Rf4KJzBuXDPY1sACjIO2rmrU5z1ncdeewF/USIgERD+uxKBAoDW9PBga2roAgBIZVx30qiOxIVYbYKvetAtAoDxI9JJQp3+DQDwsj9Km8WPzKrXW3c4TOorUoaiO/DtdAwAAhAq4ztvuwyNmRn7va84kY90LymS1PjzIniAV2OBVPbZHfsnZjwBsmfnWlPD78KQTzonyIxfLlyqHd3zyTI50G2DYmytXbVCwkwaznsQ+pRWD50TiIACJjLGXVdEH6CVslYckxAzF9ms1ujyUoOlDIXSQetWmyfCUtddWA8xHpRjQIB03W2cTIB1gnwUPAIB4gRhqAFWWG9mt7l0cF7KUDuenE7Ho1rTM2bqaa05Q0SafnOCAF5EXD7UgbXy2Tm5GCW1uV22kWrMUVKbS50/bbwsFfJBAJG27S/kg8B4WUqdPx0ltTmpxrwLSGdrVqoxl5L6SqORjWbGz3aFTCLifrHEdYVMmfGzjUY2WkrqK1KNmc7WbFtjb0F7ri02s8wqrUEbHHGbYNEalGVW9VxbbP4O22VsERAR5NvTcwcCNh+Vom7vgSjSCkRIWxZawTkvTWODQ6Ur81+3NO1Hb2bD3Dltjkc5LrIi1RVq1Urt/bRlbnKgbI6VjnJczGlzfLumPbDnEwGAEwxhf469x/tszY8VkvqNfFK/Z6ycyZy8wf4ce6J4u6Y9cGTESzVm0jRmvq0/Cb5nA1Gy8FrKMUs15sLFhbcvni8MrX1duw9ILI/7A4yM+I6j9vnJqX2t6eHBn/+6La4q29bNqeFjXyYHuv8hC8vqDylNe2Xirqr8hUDK7bP0B4hHVcva6aoXAAAAAElFTkSuQmCC",
        "gear": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADUElEQVR42rVUPYskVRQ999Wr/mJqesQZN1NBxESMNnYdJhR2A/+Agk5gNLiwG8kwIsJupoGiCPMHzERMZmzdTMw0axgGGux+XdVV3fXRXd1V9e41sEt7e1cw2QsvOdx37nv3nnuAZx0iouoDAL4fvVmJfGyC8O5gMGivc0hEnDpnM54AiIiJiAFoEXFY4W0H+ASCB0qpTq/X0wAcIrJExNukaqMiAYAJonPjT06IqCAiK9aGFqhAFDiOszw8PKyIqDJBeDwY+re2SXX9MABk/PDbF/afezed5/D9cA4gcZuND2bTxAFw0NnZ+3k8Dr9jyKK72/1iuVzGxgTvAPhJRBQRsd5sHyC/p/MlilXButH4xnVdFEWBoigsASTCN73u7k1mRpIklbe7210Vq1eI6PKxr5+enioRcQHA+OH7cZaX4yAsR+NJmWS5ZIuVZIuVxOlChiYojR+u5stS/jSTk3XL9GM9PDs7YyIqAYBFpo7jKGZBu93WRVFcZklyJ0uSO2VZXnY6Hc3MigA4il5dD7J6bLKj0fTlspSjUTB9y4yDP2bJnON0weNJ1NtWwXgS9ZL5UsZBJMYPs+Fw+JKI7NWSUgCgNN7TGheuo3rK0a/nec6O1mRZHooI9fv9Zr/fb4oIWZaHSikwM4tIm3Tj19Ki32h7H25OeVPY/3sHiMjp7u3dcB0ARAf/EHKF86rCo9KyJeavWq3Wa7aqxFF0j4h+BLDa+PI9YQYREQCeRtGD/f39JTP/8tSyJpjeXRRWhiYoZ8lcJlF8YUxw25jg9iSKL2bJXEbjSZnlhZgg/H77vq43BYBLRIWt7IqthVKKF4tF5XneUavVOqrbkWVZRURWKaXZ2t/WeBNASURMa8AhImuC8Ljb3fs6ieNqZ2dHExHSNAUz89/Ch/I8j5RykKaJbbVanOeL+zcOnv+89gH17yyEYPlqmeex53k6TZOP4ln8pdtwIyISpRQ1m81VlqY/zGazU621s7vTdgF6Y726T9oWAAyG/i0Thsc1HkXRiyaIRqW1RRDGn9a4P5memCA83zaXp5LW6yQiztXVVdf4YSUiYvzgMxGh6+vr1n9pSW974ZqUAFgiksFgUIBw3wIdhjwiIhGRoi6+9s5nF38BggA7/6nEIaQAAAAASUVORK5CYII=",
        "help": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADx0lEQVR42oWUTWhcVRTHf+fcNzPJTCZJbY01nbZUKeJH8atuhEqkInSjq4QWiqIu6kZBWqvExTiiDbZUC7qwLqSioE4VxEUVqQj1s9Rau9AKYjVJg630K85M5uO9e4+LmYbUpPiH9xb3Pn73vHv+/wMLqWhK0ZQryUwYLruFtqJ5K2VzjIgHKOw+u8yZ3WXBr0EVlWjc4nBkXOQE4Od+e0myEGzwhZM3RN35MSzcF2WyeY0iQAjBk8xUPOqOSByXxkcHP6NoSknCfGAHVhibeFTTPa9qlO6VZoVaM/GN2MyAdITkM86RzmFmWFzfM/HM4FMMlx37hwOIyVzY8h2nHnbZvn3WqkFIkmrL3I0DaVl/fYaejHLojwaHJ1ukHd6JoD1XO//P33snRguPt6EjXtolY6t2TK32qfQxwbo0tLjYFH1sbY5dG/ovu5V3j9XY9ulFuhxmSKLZRSlfPb9xcrTwAcUvI+UXBMS8yi5NZ7OEONRi1TsH0+za0M/ktOeJTy6w6f1zfDfRZPPtOTbflmO6iTgxZ62ZgMqem163HkpDXtkvfuXOM0sRWW+NijlwjThw73UZphuB7QcusvdwlQO/1nnkw/O0PGy8NYsTMEQtbph25ZfWan/dA2Jt2wR/t3Tnc1af9gni+rqEfT/WeO/4DNVWYNVVEfXYKPQ60g6mG4FgnY4KJhpZMO4HDkQAJtyiGhHABBCBemzUWkZK4exMoB4bfbXA0akWbx+tAdY2iSGERDC7edbYhsxLhQpECs0EHrojx7Jex2vfVnjwnbOoQD6jeJsTHkGBziswgYX2af9RIzG2rsuzbV2evowQrH3YHJChDjEmZyuMTA/FjWosItHlkYWuSHjlqwpLe5RGAk4WyDUGuINt4HDZ/d4cOLlCpo5rpmdtaFY9IrPBdwpv/VBFBDJO6E61q+zATF1KfL3SUKcH2788PAwlCWbynGGgarSThnWejzYv4acnr6XQ52gm7aa19y2R7n7FJzvHt19zum3sEfGUzU2OLvvcmpU9LrckQvBgwQxSCqsXp1jZ7+jtNELMzCzEUW5xylfPfT/w55kXKZry/JCX2asto4yIXzE29YbmFm2xZg180zc9Nph30t+t/Hwmtq4ITFzksv0kjco3po0HTm1dfqHtokvD4dLkKZpQklB4+fQmddGYRumV6iKarYQkGNlMhJkRWvWqEXZP/vbxS7y5JcZMELH58xCgWFRKpbD46RP57MCSISEMifk1Ig5DxwPydfD1L6aeXX5qtssd2JVVNsf/qWyuE6zL9C/CKdGyAmfarAAAAABJRU5ErkJggg==",
        "pdf": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABmUlEQVR42q2UzW7TQBSFvztjO6FOHNwuugUkJFiAoBW8Au/Eu/Ae9BlgBesIcJWWIFiYkrb+mbks6oIdrMRFPdLVyNeez+eesQz/KVU1ff2gfXF6qrEdnR24orB1P0TTNDWL5eKziHxSVSsiru/BAGDx9ftrVdWLy1KLyv1Tl2WtXlXzs9WP+Tx72d7b67B2bgz48Sis1++15JPJzq6qvp1nJ69E5F3baScHA77pbaoAcLNpnO7dTY6y7OSFiLjrTM3AE+iuYAE/m8bpJJkeHR9/e9hEbIYBRbrrn4FwSTJJK60eiIgCEmw0VhSgilYlcmcHigKJ486rqqpWEVP2Hkord8BQfvxAnX0huHcft1xi9/cZHRxejd64FRERkLbtHl21JYoIHz1GALEGu7u3NZ2NI0dPnoIIPs+Jnj2H68i7WQ4HIgKqmNns7ylvgA37bBroNmfDgQNBNwPeQLcODNZ/T0Dd1BB5wChoL9AYM256wVBHo9ASmTBYBzqA0EZv8tXFz/Nf59Z7L9vMRdEYYySv69X7luPb1W+5NbnD5IzrbwAAAABJRU5ErkJggg==",
        "plus": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABaUlEQVR42s1Vy07CUBScaW9ZSBMsLvgPNfyDH6M7f8Of4CP8CuNjwc4toZAUDBBE773jgpa0DQZQYpxkMunJybnTc+5pgT0giZKIf4s0TWNJiSSzKzfY8aoBAHiaHoDX0Sjr5vHwRwULEGgBSEhGv3K4cQrYtUBHKbg2ib2mHNR7ViaAQgkAJCvxErm1IElfoyXpAdk8Y5HHP2t5m1ZQEkkqTdPY0/SMMbG3Vh4gBIIQofNGo9FerT4eQE5yx4KgZtzkcr687XSSJ0kBCrv9fv8se5tLkryqyKYzDYZjrWw17nIdDEZXxXViqX9mlGXdiJF5txYGgKMLQoXeyd+1k9bFdDK7IfHsnAvDMHQWFnF8CrdavCRJMt17PYfj7F6SxoPx5aFTDmuMCgUARCbOnxu1vG+n7MoEUKjyA305XqIOvdg+53E2heQJgIDkzq+N2b3GAD2vAbSNwWPJ8d+Ae/4Cin2urNk2fAHmbSAciMvc8AAAAABJRU5ErkJggg==",
        "tab_x": "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAABRElEQVR42s2Sv0rDYBTFz20qiIFWi6n0CRxFzOIiFOe6O1WQivgSfQfRTRB0ywOUgiZp/jSh4RMcOujirIKo1NYG2l4HLcSQInUQ73i+e+4998cH/MtiZkrQUkn6xKpWq6moeaoE9Xo9Nzaappn+1PQV3Q2W4wmjW4iZqWbbylxm8daw/QMiGhWLxUHtorG6oCjXGA634z6K3wmATLe1n1fyR48P9zvh4F3k5pV2PwxPN9bVXQBERKMfARqWV7aaQcfxr14dXxxGuHxbmgSHAKDXeQuYOS3Lcibs9wMAKJVKEgCONqfj5IloZBjOmpzNil63e/z88tRaKhTOLy1vVlXVE2ZOJZ4QhWh7out44mz8ptt+pX1zx4bT3AMATdOkiQw0TZOMZmtzPFQIMQMAuulW9Ia/9at/MbXhKyLFtakH/Ul9AHSIrU/XRy5wAAAAAElFTkSuQmCC",
        "tab_x_hot": "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAACzElEQVR42nWTTWxUdRTFf/f//79XOv2aMgikJn7EHRJtCTZFFoSVaxePvamJwZ0JhpiYvA6GLQtDTIxCDPIRmLAhYtGwaKJUArJpS01cmHTEIInTdL5n3rz3vy6mSMFwVveem3s25xx4BhpFlufgShRZBdnKPbXEYIrgHx3aM+zT0cNCNukwZPhyN7M3X7p9+y8ABRHQpwQ0iqyUStnfb7/1fmhM0SIToQgIZKp0lUaCP3OtnX38wb17vcciAqBxbKRY9H/O7P9iexgcbXQSetZkqCoA1oppt20+CKg5e0vrnXd2Ly21AIxGkZVi0Zdnpme3h8HRjU43zfJ5T5JYMcZJEDitVq19fa9WX3m1l/f+YDq07TRAKYqMnVtd5cNDe4bx4XyW9gY0n5ddl68akoTuL4tor0f4xpvs/PaiaK1m1xcW0vGRkX2ViV3XZ364+cAJ6MNu7vCwM/m6WE+lYutff8nYseNou0WyssLO85doXf+O2unPkdFRxHtVlSPAXQeghn2hESFVlYEB6mfPoO02Y8eOgyrN0mU2Tn6GDA6iIJmqYHQKwACIyhM7jUGcI7l/vz/nciS/raKdDgQBqPb9o//jNk1cy1TBGNFmk3ByihfOXaB5tUSyvMz43AkkCGmc+wZTKKgTPKrl/wTEd76vZ0OJTVOnhYLu+OqstG/Ms3EiRpMEGQjJf/IpIkLt4nlsoWAkSa8AWI0iO/LjQv2jFyd2jIfhgVaSpL2VZdu4dAFxDhkbo7u4iG80SNfX06HymqsauZOpnTs1O+tFQYgRVpGHD6Z/Kjh74FG1mplcThERVBFrNavVGA1Dlw4OVpqk0y///OsfGsdGHmebOJbK/PywOj21zQWzRpVsM4hGwFpHI00Xa93We6/dXfpd+7R/0oUtBfnn4PRM6vVdhSkLKkgZY66tdXo39vd7YAT8/+qqILpp7fPw7P1fjOxQoW5mTJ4AAAAASUVORK5CYII=",
    },
}

# 프로그램 아이콘 (스마트클립 색: 주황 바탕 · 흰 문서 · 갈색 PDF 띠) — 창 제목줄·작업표시줄용
APP_ICON_PNG = {
    256: (
        "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"
        "/wPreL5CUHz8+wAAAABJRU5ErkJggg=="
    ),
    48: (
        "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"
    ),
    32: (
        "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"
        "mZr59/8BJ/oEQA5Jw7MAAAAASUVORK5CYII="
    ),
    16: (
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAClklEQVR4XnWT3WtUVxTFf3vfc2duZiampU0i+OBASCRgAym0YhtN"
        "waCC9MknLfkniiiC9bHQlP4DfWuD/4AvLfgBTdqnShUp5CH44AeKkYbEzMydufeec+TMTabJgwsO94O9OGutvbd4j4jgd27NLyRx"
        "dLrotSpFnomiDKARxA1UnK8YybLCrQ5dXrnT54aineXT3zfq8XVcAbVRqDTA+5IfSvIO7LyEOAHnQKDVtkvDi39ck3R57kxSr95N"
        "213va6OuduFXqA7/f3tAtkFv9SbFs3+Qah3B69BQJO00P2+c6AKI9y63Wh0xB8lBhUAkVE98g4jBvniAN7UCH/7KgiKiSKgKSVjw"
        "rpTfP+xaGYbkGJVT3yEfT0PREUQFLzpIKtRrCEu09L3/RAlexyAeR+pj9LMq48OUQUFslG7awXa2MXFC3kupJnXyvNcXWU1qQQ7Y"
        "oiTswgQJ3nl+vL1GclgYe3GDV8/XmZj+jH8f3KM5Ocv21hbd1gbfLv2OaITveyuhRhWbOx4/2WJ04gTNqU85NnOK1ttNJo+fZGpm"
        "jvbbNzz++y7drEcUbO61eGABKBzk1nP/9s/YouCTz8/y38Zznq4/ZO3Rnwfbug8mc46hJObi3BHSl3/x0ViTWuMDRj4cZ3vzNVkv"
        "ZfaLrzk6MUUtSchtPghwoCBEcvnLJn5kAjn/y3tvK+HLru+FiIgLqeykOaYuVHfnICTvw3so7s+EQ00MYvDhW3CBq65w98GLMbH6"
        "bNtq3rGqkRWR/lNVrUaRVRNbXGFdumnVGMF7VfH3dpdp/odGw1zt97g+Xi7T3hjvR9EtlyqKaLeynxqLq1dkb53TW1+dMxWdL9JW"
        "xeZZcHAAwU0UG2+SQ7m1xUpyaeW3wH0HhLQZVUBlb5wAAAAASUVORK5CYII="
    ),
}

# 색상표 (색칠·도형 색)
PALETTE = [
    ["#ffe600", "#ffd54f", "#ffab40", "#ff9ecb", "#f48fb1", "#ce93d8", "#b39ddb", "#90caf9"],
    ["#7fd3ff", "#80deea", "#80cbc4", "#a5d6a7", "#7cf27c", "#c5e1a5", "#e6ee9c", "#fff59d"],
    ["#e53935", "#fb8c00", "#fdd835", "#43a047", "#1e88e5", "#3949ab", "#8e24aa", "#000000"],
]
MEMO_W = 230      # 오른쪽 메모 칸 폭(px)


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
        self.filter = FilterBox(self, lambda: self.refresh(), "파일 이름·경로로 찾기", "최근파일 검색")
        self.filter.pack(fill="x", pady=(0, 3))
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
        n = 0
        for p in conf["recent"]:
            t = conf.get("recent_time", {}).get(p, "")
            if not self.filter.match(os.path.basename(p), p, t):
                continue
            n += 1
            pg = conf["last_page"].get(p)
            self.tv.insert("", "end", iid=p, text="📄 " + os.path.basename(p),
                           values=("" if pg is None else pg + 1, t[5:] if len(t) > 5 else t),
                           tags=() if os.path.exists(p) else ("missing",))
        self.info.config(text=f"{len(conf['recent'])} / {self.app.limit('recent_max')}개")
        self.filter.show_count(n, len(conf["recent"]))

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
        self.info = tk.StringVar(value="검색어를 넣고 Enter (다시 Enter·F3 = 다음)")
        self.scope = tk.StringVar(value="file")      # 기본: 지금 보는 파일에서 찾기
        self.hits = []          # 현재 파일 결과 [(path, page, rect, snippet)]
        self.hit_idx = -1
        self._last_q = None
        self._last_path = None
        self.running = False
        self.q = None
        self.map = {}
        self.dir_nodes = {}
        self.results = []      # [(path, [(page, snippet)])]
        self.words = []

        r0 = ttk.Frame(self)
        r0.pack(fill="x", pady=(0, 3))
        ttk.Radiobutton(r0, text="이 파일에서", value="file", variable=self.scope, style="Toolbutton",
                        command=self.on_scope).pack(side="left", expand=True, fill="x")
        ttk.Radiobutton(r0, text="폴더에서 PDF 찾기", value="folder", variable=self.scope, style="Toolbutton",
                        command=self.on_scope).pack(side="left", expand=True, fill="x")
        self.r0 = r0
        self.folder_box = ttk.Frame(self)
        r1 = ttk.Frame(self.folder_box)
        r1.pack(fill="x")
        ttk.Entry(r1, textvariable=self.folder).pack(side="left", fill="x", expand=True)
        ttk.Button(r1, text="…", width=3, command=self.pick_folder).pack(side="left", padx=(2, 0))
        r2 = ttk.Frame(self)
        r2.pack(fill="x", pady=3)
        qe = ttk.Entry(r2, textvariable=self.query)
        qe.pack(side="left", fill="x", expand=True)
        qe.bind("<Return>", lambda e: self.toggle() if not self.running else None)
        self.qe = qe
        self.btn = ttk.Button(r2, text="찾기", width=5, command=self.toggle)
        self.btn.pack(side="left", padx=(2, 0))
        self.r2 = r2
        self.nav = ttk.Frame(self)
        ttk.Button(self.nav, text="▲ 이전", command=lambda: self.step(-1)).pack(side="left", expand=True, fill="x")
        ttk.Button(self.nav, text="▼ 다음 (F3)", command=lambda: self.step(1)).pack(side="left", expand=True, fill="x")
        r3 = ttk.Frame(self.folder_box)
        r3.pack(fill="x", pady=(3, 0))
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
        self.on_scope()

    def on_scope(self):
        """이 파일에서 / 폴더에서 바꾸기"""
        self.running = False
        if self.scope.get() == "folder":
            self.nav.pack_forget()
            self.folder_box.pack(fill="x", after=self.r0)
            self.info.set("폴더와 검색어를 넣고 Enter")
        else:
            self.folder_box.pack_forget()
            self.nav.pack(fill="x", after=self.r2)
            self.info.set("검색어를 넣고 Enter (다시 Enter·F3 = 다음)")
        self.clear()

    # ---------- 이 파일에서 찾기 ----------
    def start_file(self):
        q = self.query.get().strip()
        if not q or not self.app.doc:
            if not self.app.doc:
                self.info.set("먼저 PDF를 열어주세요.")
            return
        if q == self._last_q and self.hits and self._last_path == self.app.path:
            self.step(1)          # 같은 검색어로 다시 Enter → 다음
            return
        self.clear()
        self._last_q, self._last_path = q, self.app.path
        self.running = True
        self.btn.config(text="중지")
        self._fp = 0
        self.after(10, self.poll_file)

    def poll_file(self):
        app, q = self.app, self._last_q
        doc = app.doc
        if not self.running or doc is None or app.path != self._last_path:
            self.finish_file("중지했습니다")
            return
        t0 = time.time()
        while self._fp < len(doc) and time.time() - t0 < 0.05:
            p = self._fp
            self._fp += 1
            page = doc[p]
            with unrotated(page):
                rects = page.search_for(q)
                pw = page.rect.width
                for r in rects:
                    line = page.get_textbox(fitz.Rect(0, r.y0 - 1, pw, r.y1 + 1)) or q
                    snip = " ".join(line.split())[:60]
                    self.add_hit(app.path, p, fitz.Rect(r), snip)
        if self._fp < len(doc):
            self.info.set(f"찾는 중… {self._fp}/{len(doc)}쪽 · {len(self.hits)}곳")
            self.after(5, self.poll_file)
            return
        self.finish_file("")

    def add_hit(self, path, p, rect, snip):
        if len(self.hits) >= SEARCH_MAX:
            return
        if not self.results or self.results[-1][0] != path:
            self.results.append((path, []))
        if not self.results[-1][1] or self.results[-1][1][-1][0] != p:
            self.results[-1][1].append((p, snip))
        self.hits.append((path, p, rect, snip))
        iid = self.tv.insert("", "end", text=f"{p + 1}쪽:  {snip}", tags=("hit",))
        self.map[iid] = (path, p, len(self.hits) - 1)

    def finish_file(self, msg):
        self.running = False
        self.btn.config(text="찾기")
        n_pages = len({h[1] for h in self.hits})
        if self.hits:
            self.info.set(msg or f"{n_pages}쪽에서 {len(self.hits)}곳 찾음")
            if self.hit_idx < 0:
                self.step(1)
        else:
            self.info.set(msg or "찾는 글자가 없습니다.")

    def step(self, d):
        """다음/이전 찾은 곳으로"""
        if not self.hits:
            if self.scope.get() == "file" and self.query.get().strip():
                self.start_file()
            return
        self.hit_idx = (self.hit_idx + d) % len(self.hits)
        self.go_hit(self.hit_idx)

    def go_hit(self, i):
        path, p, rect, snip = self.hits[i]
        if self.app.path != path and not self.app.open_path(path):
            return
        self.app.show_hit(p, rect, self._last_q or "")
        iid = next((k for k, v in self.map.items() if len(v) == 3 and v[2] == i), None)
        if iid:
            self.tv.selection_set(iid)
            self.tv.see(iid)
        self.info.set(f"{i + 1} / {len(self.hits)}  ·  {p + 1}쪽")

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
        elif self.scope.get() == "file":
            self.start_file()
        else:
            self.start()

    def clear(self):
        self.running = False
        self.tv.delete(*self.tv.get_children())
        self.map.clear()
        self.dir_nodes.clear()
        self.results = []
        self.hits = []
        self.hit_idx = -1
        self._last_q = None

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
        self.btn.config(text="찾기")
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
        v = self.map.get(s[0]) if s else None
        return v

    def activate(self, e=None):
        v = self.sel()
        if not v:
            return
        if len(v) == 3:                 # 이 파일에서 찾은 곳
            self.hit_idx = v[2]
            self.go_hit(v[2])
            return "break"
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
            g = pr.get("geometry", "1280x860")
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight() - 110   # 작업표시줄·제목줄 여유
            try:   # 화면보다 크면 화면에 맞춤 (아래 상태줄이 가려지지 않게)
                gw, gh = (int(v) for v in g.split("+")[0].split("x"))
            except ValueError:
                gw, gh = 1280, 860
            if gw > sw or gh > sh:
                g = f"{min(gw, sw)}x{min(gh, sh)}+0+0"
            root.geometry(g)
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
        self.theme = dict(THEME_DEFAULT, **(pr.get("theme") or {}))
        self.themed_labels = []  # 테마 색을 따라야 하는 tk 라벨들
        self._wall_src = None    # 배경 그림 원본
        self._wall_key = None
        self._wall_img = None
        self._last_tool = "edit"
        if pr.get("recent_max") == 20 and not pr.get("_recent200"):    # 예전 기본값(20) → 200
            pr["recent_max"] = 200
        pr["_recent200"] = True
        self.memo_style = tk.StringVar(value=pr.get("memo_style", "box"))   # box=본문에 글상자 / note=아이콘+쪽지
        self.memo_drag = None
        self._icons = {}         # (light/dark, 이름) → PhotoImage
        self.icon_users = []     # (위젯, 아이콘 이름, 영역 top/bottom/menu)
        self.memo_side = tk.BooleanVar(value=pr.get("memo_side", True))   # 메모를 오른쪽에 펼쳐 보기
        self._memo_pages = set()
        self.sel = None          # 선택한 글자 {"page", "text", "rects", "y"}
        self.selecting = None

        self.set_app_icon()
        install_ime_fix(self.root)
        self._build_ui()
        for f in files:
            self.open_file(f)
        self.on_mode(quiet=True)
        self.apply_theme()
        self.set_app_mode()
        self.root.after(200, self.poll_ipc)
        self.root.after(3000, self.send_stats)
        saved = self.conf["prefs"].get("update_avail")
        self.update_info = saved if isinstance(saved, dict) and \
            ver_tuple(saved.get("version", "0")) > ver_tuple(APP_VER) else None
        self.root.after_idle(self.show_update_btn)
        self.root.after(4000, lambda: self.check_update(force=True))   # 켤 때마다 확인

    # ---------- 새 버전 확인 ----------
    def check_update(self, force=False):
        """깃허브 최신 릴리스 번호 확인 (켤 때, 그 뒤 3시간마다). 새 버전이면 [업데이트 필요] 버튼 표시"""
        pr = self.conf["prefs"]
        if not UPDATE_API:
            return
        if not force and time.time() - pr.get("update_checked", 0) < UPDATE_CHECK_HOURS * 3600 - 60:
            self.root.after(3600 * 1000, self.check_update)
            return
        box = {}

        def work():
            try:
                rel = json.loads(net_request(UPDATE_API, headers={"User-Agent": f"smartpdfeditor/{APP_VER}",
                                                                  "Accept": "application/vnd.github+json"},
                                             limit=1024 * 1024).decode("utf-8"))
                tag = str(rel.get("tag_name", "")).lstrip("vV")
                if tag and not rel.get("draft") and not rel.get("prerelease"):
                    box["info"] = ({"version": tag, "date": str(rel.get("published_at") or "")[:10],
                                    "notes": str(rel.get("body") or "")[:3000]}
                                   if ver_tuple(tag) > ver_tuple(APP_VER) else None)
            except Exception:
                pass
            box["done"] = True
        threading.Thread(target=work, daemon=True).start()

        def wait(n=0):
            if not box.get("done") and n < 60:
                self.root.after(500, lambda: wait(n + 1))
                return
            if "info" in box:
                pr["update_checked"] = time.time()
                pr["update_avail"] = box["info"]
                self.update_info = box["info"]
                self.show_update_btn()
        self.root.after(500, wait)
        if not force:
            self.root.after(UPDATE_CHECK_HOURS * 3600 * 1000, self.check_update)

    def show_update_btn(self):
        info = getattr(self, "update_info", None)
        try:
            if info:
                self.upd_btn.configure(text=f"업데이트 필요 (v{info['version']})")
                if not self.upd_btn.winfo_ismapped():
                    self.upd_btn.pack(side="right", padx=(6, 2), after=self._help_link)
            else:
                self.upd_btn.pack_forget()
        except tk.TclError:
            pass

    def show_update(self):
        info = getattr(self, "update_info", None)
        if not info:
            return
        dlg = Popup(self.root)
        dlg.title("새 버전")
        dlg.transient(self.root)
        f = ttk.Frame(dlg, padding=16)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text=f"{APP} 새 버전 v{info['version']}", font=("맑은 고딕", 13, "bold")).pack(anchor="w")
        ttk.Label(f, text=f"지금 쓰는 버전: v{APP_VER}" + (f"   ·   나온 날: {info['date']}" if info.get("date") else ""),
                  foreground="#777").pack(anchor="w", pady=(2, 8))
        notes = info.get("notes") or ""
        i = notes.find("### ")
        if i >= 0:
            notes = notes[i:]
        if notes:
            tx = tk.Text(f, height=12, width=72, wrap="word", font=("맑은 고딕", 10), relief="solid", bd=1)
            tx.insert("1.0", notes)
            tx.configure(state="disabled")
            tx.pack(fill="both", expand=True)
        ttk.Label(f, text="받은 smartpdfeditor.exe 를 지금 쓰는 파일 자리에 바꿔 넣고 다시 실행하세요.\n"
                          "(설정·즐겨찾기·북마크는 그대로 이어집니다)", foreground="#b0412b",
                  justify="left").pack(anchor="w", pady=(8, 0))
        bf = ttk.Frame(f)
        bf.pack(fill="x", pady=(10, 0))
        ttk.Button(bf, text="나중에", command=dlg.destroy).pack(side="right")
        ttk.Button(bf, text="새 버전 내려받기", command=lambda: (webbrowser.open(DOWNLOAD_URL), dlg.destroy())).pack(
            side="right", padx=4)
        dlg.bind("<Escape>", lambda e: dlg.destroy())

    # ---------- 사용 통계 ----------
    def send_stats(self):
        """하루 한 번, 무작위 번호와 버전만 보냅니다. 끄기: 환경설정 → 일반"""
        pr = self.conf["prefs"]
        if not FIREBASE_DB_URL or pr.get("no_stats"):
            return
        new = False
        iid = pr.get("install_id")
        if not (isinstance(iid, str) and len(iid) == 32):
            iid = pr["install_id"] = uuid.uuid4().hex
            new = True
            save_conf(self.conf)
        today = datetime.date.today().isoformat()
        if not new and pr.get("last_ping") == today:
            return
        base = f"{FIREBASE_DB_URL}/apps/{STATS_APP}"
        rec = {"v": APP_VER, "last": {".sv": "timestamp"}}
        if new or not pr.get("stats_first"):
            rec["first"] = {".sv": "timestamp"}   # 처음 한 번만 (규칙상 한 번 쓰면 못 바꿈)

        def work():
            try:
                stats_call(f"{base}/installs/{iid}.json", "PATCH", rec)
            except Exception:
                return
            pr["stats_first"] = True   # 딕셔너리 값 하나만 바꿈 — 저장은 종료할 때
            try:
                stats_call(f"{base}/daily/{today}/{iid}.json", "PUT", True)
            except Exception:
                return
            pr["last_ping"] = today   # 딕셔너리 값 하나만 바꿈 — 저장은 종료할 때
        threading.Thread(target=work, daemon=True).start()

    # ---------- UI ----------
    def _build_menu(self):
        mb = self.menubar

        fm = tk.Menu(mb, tearoff=0)
        fm.add_command(label="열기 (새 탭)...", accelerator="Ctrl+O", command=self.ask_open,
                       image=self.menu_icon("open"), compound="left")
        fm.add_command(label="새 창으로 열기...", accelerator="Ctrl+Shift+O", command=self.ask_open_window)
        fm.add_command(label="새 창", accelerator="Ctrl+N", command=lambda: launch_new_window())
        self.recent_menu = tk.Menu(fm, tearoff=0)
        fm.add_cascade(label="최근 본 파일", menu=self.recent_menu)
        fm.add_separator()
        fm.add_command(label="저장", accelerator="Ctrl+S", command=self.save,
                       image=self.menu_icon("save"), compound="left")
        fm.add_command(label="다른 이름으로 저장...", accelerator="Ctrl+Shift+S", command=self.save_as,
                       image=self.menu_icon("save_as"), compound="left")
        fm.add_command(label="인쇄...", accelerator="Ctrl+P", command=self.print_doc,
                       image=self.menu_icon("print"), compound="left")
        fm.add_command(label="원하는 쪽만 저장...", accelerator="Ctrl+E", command=self.extract_dialog)
        fm.add_separator()
        fm.add_command(label="탭 닫기", accelerator="Ctrl+W", command=lambda: self.close_tab(self.tab))
        fm.add_command(label="종료", command=self.on_close)
        mb.add_cascade(label="파일", menu=fm)

        em = tk.Menu(mb, tearoff=0)
        em.add_command(label="되돌리기", accelerator="Ctrl+Z", command=self.do_undo,
                       image=self.menu_icon("undo"), compound="left")
        em.add_command(label="이 파일에서 찾기", accelerator="Ctrl+F", command=lambda: self.focus_search("file"),
                       image=self.menu_icon("find"), compound="left")
        em.add_command(label="다음 찾기", accelerator="F3", command=lambda: self.search_panel.step(1))
        em.add_command(label="찾아 바꾸기...", accelerator="Ctrl+H", command=self.find_replace)
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
        vm.add_checkbutton(label="메모를 오른쪽에 펼쳐 보기", variable=self.memo_side,
                           command=lambda: (self.conf["prefs"].update(memo_side=self.memo_side.get()),
                                            self.render()))
        vm.add_checkbutton(label="마우스 휠 한 칸에 한 쪽씩 넘기기", variable=self.wheel_page,
                           command=lambda: self.conf["prefs"].update(wheel_page=self.wheel_page.get()))
        vm.add_checkbutton(label="옆 패널 보이기", accelerator="F9", variable=self.panel_on, command=self.apply_panel)
        mb.add_cascade(label="보기", menu=vm)

        tm = tk.Menu(mb, tearoff=0)
        for k, t in TOOLS:
            tm.add_radiobutton(label=t[2:], value=k, variable=self.mode, command=self.on_mode,
                               image=self.menu_icon("t_" + k), compound="left",
                               accelerator={"edit": "Esc", "capture": "Ctrl+Shift+C"}.get(k, ""))
        tm.add_separator()
        cm = tk.Menu(tm, tearoff=0)
        for name, c in (("노랑", "#ffe600"), ("초록", "#7cf27c"), ("파랑", "#7fd3ff"), ("분홍", "#ff9ecb")):
            cm.add_command(label=name, command=lambda c=c: self.set_color(c))
        cm.add_command(label="색상표에서 고르기...", command=lambda: self.palette_popup(self.swatch, self.set_color))
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
        mm = tk.Menu(tm, tearoff=0)
        mm.add_radiobutton(label="본문에 글상자로 붙이기 (내용이 바로 보임)", value="box", variable=self.memo_style,
                           command=lambda: self.conf["prefs"].update(memo_style="box"))
        mm.add_radiobutton(label="아이콘 + 오른쪽 쪽지", value="note", variable=self.memo_style,
                           command=lambda: self.conf["prefs"].update(memo_style="note"))
        tm.add_cascade(label="메모", menu=mm)
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
        pm.add_command(label="이 쪽 오른쪽으로 회전", accelerator="Ctrl+R", command=lambda: self.rotate_pages([self.page_no], 90),
                       image=self.menu_icon("rot_r"), compound="left")
        pm.add_command(label="이 쪽 왼쪽으로 회전", accelerator="Ctrl+L", command=lambda: self.rotate_pages([self.page_no], -90),
                       image=self.menu_icon("rot_l"), compound="left")
        pm.add_command(label="여러 쪽 회전...", command=self.rotate_dialog, image=self.menu_icon("rot_many"),
                       compound="left")
        pm.add_command(label="전체 쪽 오른쪽으로 회전", command=lambda: self.rotate_all(90),
                       image=self.menu_icon("rot_all"), compound="left")
        pm.add_command(label="전체 쪽 왼쪽으로 회전", command=lambda: self.rotate_all(-90))
        pm.add_command(label="전체 쪽 180° 회전", command=lambda: self.rotate_all(180))
        pm.add_separator()
        pm.add_command(label="원하는 쪽만 저장...", accelerator="Ctrl+E", command=self.extract_dialog)
        mb.add_cascade(label="페이지", menu=pm)

        bm = tk.Menu(mb, tearoff=0)
        bm.add_command(label="즐겨찾기에 추가", accelerator="Ctrl+D", command=self.add_favorite_now,
                       image=self.menu_icon("star"), compound="left")
        bm.add_command(label="북마크 추가", accelerator="Ctrl+B", command=self.add_bookmark_now,
                       image=self.menu_icon("bookmark"), compound="left")
        bm.add_separator()
        bm.add_command(label="즐겨찾기 보기", command=lambda: self.show_side(self.fav_panel))
        bm.add_command(label="북마크 보기", command=lambda: self.show_side(self.bm_panel))
        bm.add_command(label="최근 본 파일 보기", command=lambda: self.show_side(self.recent_panel))
        bm.add_command(label="폴더에서 PDF 찾기", accelerator="Ctrl+Shift+F", command=lambda: self.focus_search("folder"))
        mb.add_cascade(label="즐겨찾기", menu=bm)

        sm = tk.Menu(mb, tearoff=0)
        sm.add_command(label="환경설정...", command=self.settings_dialog, image=self.menu_icon("gear"), compound="left")
        thm = tk.Menu(sm, tearoff=0)
        self.theme_var = tk.StringVar()
        for k, v in THEMES.items():
            thm.add_radiobutton(label=v["name"], value=k, variable=self.theme_var,
                                command=lambda k=k: self.set_preset(k))
        sm.add_cascade(label="테마", menu=thm)
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
        hm2.add_command(label="사용방법", accelerator="F1", command=self.show_help, image=self.menu_icon("help"),
                        compound="left")
        hm2.add_command(label="smartgong.kr 바로가기", command=lambda: webbrowser.open(HOME_URL))
        hm2.add_command(label="새 버전 내려받기", command=lambda: webbrowser.open(DOWNLOAD_URL))
        hm2.add_separator()
        hm2.add_command(label="바로가기 만들기 (바탕화면·작업표시줄)…", command=self.shortcut_menu_at_pointer)
        hm2.add_command(label="정보 · 라이선스", command=self.show_about)
        hm2.add_separator()
        hm2.add_command(label=f"오류 · 개선 제안: {CONTACT_EMAIL}  (주소 복사)", command=self.copy_contact)
        mb.add_cascade(label="도움말", menu=hm2)

    def _build_ui(self):
        self.topbox = ttk.Frame(self.root)       # 도구줄 1~2줄 (창이 좁으면 도구 버튼이 둘째 줄로)
        self.topbox.pack(fill="x")
        bar = self.bar = ttk.Frame(self.topbox, padding=(4, 3))
        bar.pack(fill="x")
        self.bar2 = ttk.Frame(self.topbox, padding=(4, 0, 4, 3))
        right = ttk.Frame(bar)          # 오른쪽 묶음을 먼저 배치 → 창이 좁아도 항상 보임
        right.pack(side="right")
        self.menubar = MenuBar(bar)     # 파일·편집·보기… 메뉴 → 같은 줄에 도구 버튼이 이어짐
        self.menubar.pack(side="left")
        self._build_menu()

        self.labeled = []               # 좁으면 아이콘만 보이게 줄일 버튼들
        self._compact = False

        def btn(icon, cmd, tip, text=None):
            b_ = ttk.Button(bar, command=cmd, text=text or "", compound="left" if text else "image", width=-1)
            self.set_icon(b_, icon, "top")
            b_.pack(side="left", padx=1)
            Tooltip(b_, tip)
            if text:
                self.labeled.append(b_)
            return b_

        def sep():
            ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=5)

        sep()
        btn("open", self.ask_open, "열기 (Ctrl+O)", "열기")
        btn("save", self.save, "저장 — 지금 파일에 바로 저장 (Ctrl+S)", "저장")
        btn("save_as", self.save_as, "다른 이름으로 저장 (Ctrl+Shift+S)")
        btn("print", self.print_doc, "인쇄 (Ctrl+P) — 고친 내용·메모·색칠까지 그대로", "인쇄")
        btn("undo", self.do_undo, "되돌리기 (Ctrl+Z)")
        sep()
        btn("rot_l", lambda: self.rotate_pages([self.page_no], -90), "이 쪽 왼쪽으로 회전 (Ctrl+L)")
        btn("rot_r", lambda: self.rotate_pages([self.page_no], 90), "이 쪽 오른쪽으로 회전 (Ctrl+R)")
        btn("rot_many", self.rotate_dialog, "여러 쪽 골라서 회전")
        btn("rot_all", lambda: self.rotate_all(90), "전체 쪽 오른쪽으로 회전 (메뉴 [페이지]에 왼쪽 회전)")

        # 도구 버튼 (뷰어·편집 모드 모두 표시) + 도구별 옵션(편집 모드)
        self.toolarea = ttk.Frame(self.topbox)
        self.toolarea.pack(in_=bar, side="left", padx=(6, 0))
        self._fit_job = None
        self.toolbtns = ttk.Frame(self.toolarea)
        short = {"edit": "수정", "mark": "색칠", "hide": "감추기", "shape": "도형", "memo": "메모",
                 "erase": "지우개", "capture": "캡쳐"}
        tips = {"edit": "글자 수정 — 글자를 클릭 (Esc)", "mark": "색칠 — 글자 클릭 또는 영역 끌기",
                "hide": "감추기 — 아래 내용을 지우고 덮기", "shape": "도형 — 사각형·원·선·화살표 (Shift: 정사각형·정원)",
                "memo": "메모 붙이기 (오른쪽에 펼쳐 보임)", "erase": "색칠·도형·메모 지우기",
                "capture": "영역 캡쳐 → 클립보드 (Ctrl+Shift+C)"}
        self.tool_rbs = {}
        for k, _ in TOOLS:
            rb = ttk.Radiobutton(self.toolbtns, text=short[k], value=k, variable=self.mode, style="Toolbutton",
                                 compound="left", command=self.on_mode)
            self.set_icon(rb, "t_" + k, "top")
            rb.pack(side="left", padx=0)
            Tooltip(rb, tips[k])
            self.tool_rbs[k] = rb
            self.labeled.append(rb)
        self.optbox = ttk.Frame(self.toolarea)
        self.opt = {k: ttk.Frame(self.optbox) for k, _ in TOOLS}

        def color_opts(f, current, quick, setter, tip):
            sw = tk.Label(f, width=2, bg=current, relief="groove", cursor="hand2")
            sw.pack(side="left", padx=(6, 2))
            Tooltip(sw, tip)
            for c in quick:
                b_ = tk.Label(f, width=1, bg=c, relief="ridge", cursor="hand2")
                b_.pack(side="left", padx=1)
                b_.bind("<Button-1>", lambda e, c=c: setter(c))
            more = ttk.Button(f, text="색상표 ▾", width=7)
            more.pack(side="left", padx=(3, 0))
            more.configure(command=lambda: self.palette_popup(more, setter))
            sw.bind("<Button-1>", lambda e: self.palette_popup(sw, setter))
            Tooltip(more, "색상표에서 고르기")
            return sw

        self.swatch = color_opts(self.opt["mark"], self.mark_color, ("#ffe600", "#7cf27c", "#7fd3ff", "#ff9ecb"),
                                 self.set_color, "지금 색칠 색 (누르면 색상표)")
        f = self.opt["shape"]
        ttk.Combobox(f, textvariable=self.shape_kind, values=SHAPES, width=6, state="readonly").pack(side="left", padx=(4, 0))
        self.shape_swatch = color_opts(f, self.shape_color, ("#e53935", "#1e88e5", "#000000"),
                                       self.set_shape_color, "지금 선 색 (누르면 색상표)")
        sp = ttk.Spinbox(f, from_=0.5, to=20, increment=0.5, textvariable=self.shape_width, width=3)
        sp.pack(side="left", padx=2)
        Tooltip(sp, "선 두께(pt) · 채우기는 [도구 → 도형]")

        # 아래 상태줄: 왼쪽 안내 글 / 오른쪽 맞춤·보기 방식 아이콘
        self.status = tk.StringVar(value="PDF를 열어주세요 (Ctrl+O).")
        sbar = self.sbar = ttk.Frame(self.root, padding=(4, 1))
        sbar.pack(side="bottom", fill="x")
        sbar.columnconfigure(0, weight=1, uniform="half")      # 왼쪽 절반: 안내 글
        sbar.columnconfigure(1, weight=1, uniform="half")      # 오른쪽 절반: 가운데부터 쪽 이동·확대·보기
        ttk.Label(sbar, textvariable=self.status, anchor="w").grid(row=0, column=0, sticky="ew", padx=(2, 8))
        nav = ttk.Frame(sbar)
        nav.grid(row=0, column=1, sticky="w")

        def sbtn(icon, cmd, tip):
            b_ = ttk.Button(nav, command=cmd, compound="image", width=-1)
            self.set_icon(b_, icon, "bottom")
            b_.pack(side="left", padx=1)
            Tooltip(b_, tip)

        def ssep():
            ttk.Separator(nav, orient="vertical").pack(side="left", fill="y", padx=6)
        sbtn("prev", lambda: self.go(-1), "이전 쪽 (PgUp)")
        self.page_var = tk.StringVar(value="0 / 0")
        e = ttk.Entry(nav, textvariable=self.page_var, width=9, justify="center")
        self._page_entry = e
        e.pack(side="left", padx=1)
        e.bind("<Return>", self.jump)
        Tooltip(e, "쪽 번호를 넣고 Enter (Ctrl+G)")
        sbtn("next", lambda: self.go(1), "다음 쪽 (PgDn)")
        ssep()
        sbtn("zoom_out", lambda: self.set_zoom(self.zoom / 1.2), "축소 (Ctrl+-)")
        self.zoom_lbl = ttk.Label(nav, text=f"{round(self.zoom * 100)}%", width=5, anchor="center")
        self.zoom_lbl.pack(side="left")
        sbtn("zoom_in", lambda: self.set_zoom(self.zoom * 1.2), "확대 (Ctrl++)")
        ssep()
        for val, ic, tip in (("width", "fit_w", "가로맞춤 — 폭에 맞춤 (Ctrl+1)"), ("height", "fit_h", "세로맞춤 — 한 쪽 전체 (Ctrl+2)")):
            rb = ttk.Radiobutton(nav, value=val, variable=self.fit, style="Toolbutton", command=self.on_fit)
            self.set_icon(rb, ic, "bottom")
            rb.pack(side="left", padx=1)
            Tooltip(rb, tip)
        ssep()
        self.view_icons = {}
        for k, t, _ in VIEWS:
            rb = ttk.Radiobutton(nav, value=t, variable=self.view_var, style="Toolbutton", command=self.on_view)
            self.set_icon(rb, "v_" + k, "bottom")
            self.view_icons[k] = rb
            rb.pack(side="left", padx=1)
            Tooltip(rb, t)

        # 우측: 로고(→ smartgong.kr) · 사용방법 · 뷰어/편집 모드
        try:
            self.logo_img = tk.PhotoImage(data="".join(LOGO_PNG))
            logo = tk.Label(right, image=self.logo_img, cursor="hand2", bd=0)
        except tk.TclError:
            logo = tk.Label(right, text="스마트공", fg="#2e7d32", font=("맑은 고딕", 12, "bold"), cursor="hand2")
        logo.pack(side="right", padx=(4, 2))
        self.themed_labels.append((logo, False))
        logo.bind("<Button-1>", lambda e: webbrowser.open(HOME_URL))
        Tooltip(logo, "smartgong.kr 바로가기")
        hl = tk.Label(right, text="사용방법", fg="#1565c0", cursor="hand2", font=("맑은 고딕", 9, "underline"))
        hl.pack(side="right", padx=(6, 4))
        self._help_link = hl
        # 새 버전이 있을 때만 나타나는 [업데이트 필요] 버튼
        self.upd_btn = tk.Button(right, text="업데이트 필요", command=self.show_update, bg="#e8590c", fg="white",
                                 activebackground="#c44a07", activeforeground="white", relief="flat", bd=0,
                                 padx=8, pady=1, cursor="hand2", font=("맑은 고딕", 9, "bold"))
        Tooltip(self.upd_btn, "새 버전이 나왔습니다 — 눌러서 내려받기")
        self.themed_labels.append((hl, True))
        hl.bind("<Button-1>", lambda e: self.show_help())
        for val, ic, txt, tip in (("edit", "m_edit", "편집", "편집 모드: 글자 수정·색칠·도형 등 (F4)"),
                                  ("view", "m_view", "뷰어", "뷰어 모드: 보기 전용, 끌어서 글자 선택 (F4)")):
            rb = ttk.Radiobutton(right, text=txt, value=val, variable=self.app_mode, style="Toolbutton",
                                 compound="left", command=self.set_app_mode)
            self.set_icon(rb, ic, "top")
            self.labeled.append(rb)
            rb.pack(side="right", padx=1)
            Tooltip(rb, tip)
        # 바로가기(바탕화면·작업표시줄) — 둘 다 만들어 두면 숨김
        self.sc_btn = ttk.Button(right, text="📌 바로가기", style="Toolbutton", command=self.shortcut_menu)
        Tooltip(self.sc_btn, "바탕화면·작업표시줄에 바로가기 만들기 (만들고 나면 이 버튼은 사라집니다)")
        self.root.after(1500, self.refresh_shortcut_btn)

        self.root.bind("<Configure>", self.on_root_resize, add="+")
        self.assign_top_styles(self.topbox)

        self.pw = ttk.PanedWindow(self.root, orient="horizontal")
        self.pw.pack(fill="both", expand=True)
        self.side_box = ttk.Frame(self.pw)
        self.side = ttk.Notebook(self.side_box, width=AD_W)
        self.fav_panel = TreePanel(self.side, self.conf["favorites"], self.new_favorite, self.open_favorite,
                                   lambda n: "📄 " + n.get("name", ""), self.persist, "＋ 현재 파일", "즐겨찾기 검색")
        self.bm_panel = TreePanel(self.side, self.conf["bookmarks"], self.new_bookmark, self.open_bookmark,
                                  lambda n: f"🔖 {n.get('name', '')}", self.persist, "＋ 북마크 추가", "북마크 검색")
        self.fav_panel.app = self.bm_panel.app = self
        self.bm_panel.scope = lambda: self.path if self.doc else None    # 북마크는 지금 파일 것만 보임
        self.bm_panel.refresh()
        self.side.add(self.fav_panel, text="즐겨찾기")
        self.side.add(self.bm_panel, text="북마크")
        self.recent_panel = RecentPanel(self.side, self)
        self.search_panel = SearchPanel(self.side, self)
        self.side.add(self.search_panel, text="검색")
        self.side.add(self.recent_panel, text="최근")        # 맨 오른쪽
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
        self._close_themes = set()
        self.ensure_tab_close(ttk.Style(self.root))
        # 탭이 많으면 탭 막대를 옆으로 밀어서 봄: [◀] 탭들 [▶] [▾ 목록]
        th = ttk.Frame(wrap)
        th.pack(side="top", fill="x")
        th.columnconfigure(1, weight=1)
        self.tab_left = ttk.Button(th, text="◀", width=2, style="Toolbutton", command=lambda: self.scroll_tabs(-1))
        self.tab_right = ttk.Button(th, text="▶", width=2, style="Toolbutton", command=lambda: self.scroll_tabs(1))
        self.tab_more = ttk.Button(th, text="▾", width=2, style="Toolbutton", command=self.show_tab_list)
        Tooltip(self.tab_left, "앞쪽 탭 보기 (탭 위에서 마우스 휠도 됨)")
        Tooltip(self.tab_right, "뒤쪽 탭 보기")
        Tooltip(self.tab_more, "열린 탭 목록에서 고르기")
        self.tab_view = ttk.Frame(th, height=1)
        self.tab_view.grid(row=0, column=1, sticky="ew")
        self.tab_off = 0
        self._tab_spans = None
        self._fit_job = None
        self.tabbar = ttk.Notebook(self.tab_view, style="Closable.TNotebook")
        self._pressed_tab = None
        self.tabbar.bind("<ButtonPress-1>", self.on_tab_press, add="+")
        self.tabbar.bind("<ButtonRelease-1>", self.on_tab_release, add="+")
        self.tabbar.place(x=0, y=0)
        self.tab_view.bind("<Configure>", lambda e: self.fit_tabs_later())
        self.tabbar.bind("<MouseWheel>", self.on_tab_wheel)
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
        self.page_scroll_style(ttk.Style(self.root))
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.vscroll_cmd, style="Page.Vertical.TScrollbar")
        hs = ttk.Scrollbar(wrap, orient="horizontal", command=self.cv.xview, style="Page.Horizontal.TScrollbar")
        self.vs = vs

        def ys(a, b):
            self.set_vscroll(a, b)
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
        r.bind("<Control-F>", lambda e: (self.focus_search("folder"), "break")[1])
        r.bind("<Control-h>", lambda e: self.find_replace())
        r.bind("<F3>", lambda e: self.search_panel.step(1))
        r.bind("<Shift-F3>", lambda e: self.search_panel.step(-1))
        r.bind("<Control-C>", lambda e: self.pick_tool("edit" if self.mode.get() == "capture" else "capture"))
        r.bind("<Control-g>", lambda e: self.focus_page())
        r.bind("<F4>", lambda e: (self.app_mode.set("edit" if self.app_mode.get() == "view" else "view"),
                                  self.set_app_mode()))
        r.bind("<Control-s>", lambda e: self.save())
        r.bind("<Control-S>", lambda e: self.save_as())            # Ctrl+Shift+S
        r.bind("<Control-p>", lambda e: self.print_doc())
        r.bind("<Control-z>", lambda e: self.do_undo())
        r.bind("<Control-f>", lambda e: (self.focus_search("file"), "break")[1])   # 지금 PDF 파일에서 찾기
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
        self.fit_tabs_later()
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
        dlg = Popup(self.root)
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
               "'스마트공' 이름과 로고는 smartgong.kr의 것입니다.\n\n"
               "설치 수를 세기 위해 하루 한 번 무작위 번호와 프로그램 버전만 보냅니다.\n"
               "파일 이름·내용 등 다른 정보는 보내지 않으며, 환경설정 → 일반에서 끌 수 있습니다.")
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

    def copy_contact(self, parent=None):
        """오류·개선 제안 메일 주소를 클립보드에 복사"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(CONTACT_EMAIL)
        except tk.TclError:
            pass
        messagebox.showinfo(APP, f"메일 주소를 복사했습니다.\n\n{CONTACT_EMAIL}\n\n"
                                 "메일 받는 사람 칸에 붙여넣어(Ctrl+V) 오류나 개선할 점을 보내 주세요.",
                            parent=parent or self.root)

    def show_help(self, section=None):
        """사용방법: 왼쪽 목차를 누르면 오른쪽 내용이 그 부분으로 이동"""
        if getattr(self, "_help", None) and self._help.winfo_exists():
            self._help.lift()
            if section is not None:
                self._help_goto(section)
            return
        dlg = self._help = Popup(self.root)
        dlg.title(f"{APP} 사용방법")
        dlg.transient(self.root)
        dlg.size_hint = (860, 660)          # 화면보다 크면 화면에 맞춰 줄어듦
        dlg.minsize(560, 400)
        fam = self.theme.get("font_family") or "맑은 고딕"
        try:
            fs = max(9, int(self.theme.get("font_size") or 9) + 1)
        except (TypeError, ValueError):
            fs = 10
        acc = "#f6a53f"

        head = tk.Frame(dlg, bg="#fff6e8")
        head.pack(fill="x")
        if getattr(self, "logo_img", None):
            tk.Label(head, image=self.logo_img, bg="#fff6e8").pack(side="left", padx=(12, 8), pady=8)
        tk.Label(head, text=f"{APP} 사용방법", bg="#fff6e8", fg="#3e2a00",
                 font=(fam, fs + 5, "bold")).pack(side="left", pady=8)
        tk.Label(head, text=f"버전 {APP_VER}", bg="#fff6e8", fg="#8a6d3b", font=(fam, fs - 1)).pack(
            side="left", padx=8, pady=(14, 8))
        tk.Frame(dlg, bg=acc, height=3).pack(fill="x")
        cf = tk.Frame(dlg, bg="#fffdf7")
        cf.pack(fill="x")
        tk.Label(cf, text="✉  사용하다가 오류나 개선할 점이 있으면", bg="#fffdf7", fg="#3e2a00",
                 font=(fam, fs)).pack(side="left", padx=(14, 4), pady=6)
        ml = tk.Label(cf, text=CONTACT_EMAIL, bg="#fffdf7", fg="#1565c0", cursor="hand2",
                      font=(fam, fs, "bold", "underline"))
        ml.pack(side="left", pady=6)
        ml.bind("<Button-1>", lambda e: self.copy_contact(parent=dlg))
        tk.Label(cf, text="으로 알려 주세요. (누르면 주소 복사)", bg="#fffdf7", fg="#3e2a00",
                 font=(fam, fs)).pack(side="left", padx=4, pady=6)
        tk.Frame(dlg, bg="#eadfcd", height=1).pack(fill="x")

        bot = ttk.Frame(dlg, padding=(10, 6))
        bot.pack(side="bottom", fill="x")
        for text, url in (("smartgong.kr", HOME_URL), ("소스 코드", SOURCE_URL), ("새 버전", RELEASES_URL)):
            l_ = tk.Label(bot, text=text, fg="#1565c0", cursor="hand2", font=(fam, fs - 1, "underline"))
            l_.pack(side="left", padx=(0, 12))
            l_.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
        ttk.Button(bot, text="닫기", command=dlg.destroy).pack(side="right")

        body = ttk.PanedWindow(dlg, orient="horizontal")
        body.pack(fill="both", expand=True)
        # 왼쪽 목차
        toc = tk.Listbox(body, activestyle="none", exportselection=False, bd=0, highlightthickness=0,
                         font=(fam, fs), bg="#faf7f2", fg="#3e2a00", selectbackground="#fcd9a6",
                         selectforeground="#3e2a00", width=24)
        for i, (title, icon, _) in enumerate(HELP_SECTIONS):
            toc.insert("end", f"  {i + 1:>2}.  {title}")
        body.add(toc, weight=0)
        # 오른쪽 내용
        right = ttk.Frame(body)
        body.add(right, weight=1)
        txt = tk.Text(right, wrap="word", font=(fam, fs), relief="flat", bg="#ffffff", fg="#2b2b2b",
                      padx=18, pady=12, spacing1=3, spacing3=3, cursor="arrow", tabs=("190p",))
        sb = ttk.Scrollbar(right, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(fill="both", expand=True)
        txt.tag_configure("h2", font=(fam, fs + 3, "bold"), foreground="#b4610a", spacing1=14, spacing3=6)
        txt.tag_configure("sub", font=(fam, fs, "bold"), foreground="#3e2a00", spacing1=8, lmargin1=4)
        txt.tag_configure("bullet", lmargin1=10, lmargin2=26)
        txt.tag_configure("dot", foreground=acc)
        txt.tag_configure("key", font=(fam, fs - 1, "bold"), foreground="#1f4e8c", background="#eef3fb",
                          lmargin1=10, lmargin2=200)
        txt.tag_configure("keydesc", lmargin1=10, lmargin2=200)
        txt.tag_configure("note", foreground="#777777", lmargin1=10, lmargin2=10, spacing1=8,
                          font=(fam, fs - 1))
        txt.tag_configure("rule", font=(fam, 4), background="#f1e4cf")
        self._help_icons = []
        for i, (title, icon, items) in enumerate(HELP_SECTIONS):
            txt.mark_set(f"sec{i}", "end-1c")
            txt.mark_gravity(f"sec{i}", "left")
            if i:
                txt.insert("end", " \n", "rule")
            try:
                img = self.icon(icon, "menu")
                if img:
                    txt.image_create("end", image=img, padx=4)
                    self._help_icons.append(img)
            except tk.TclError:
                pass
            txt.insert("end", f" {title}\n", "h2")
            for it in items:
                if isinstance(it, str):
                    txt.insert("end", "•  ", ("bullet", "dot"))
                    txt.insert("end", it + "\n", "bullet")
                elif it[0] == "소":
                    txt.insert("end", it[1] + "\n", "sub")
                elif it[0] == "키":
                    txt.insert("end", f" {it[1]} ", "key")
                    txt.insert("end", "\t" + it[2] + "\n", "keydesc")
                elif it[0] == "주":
                    txt.insert("end", "※ " + it[1] + "\n", "note")
        txt.insert("end", "\n" * 8)
        txt.config(state="disabled")

        def goto(i):
            txt.yview(f"sec{i}")
            toc.selection_clear(0, "end")
            toc.selection_set(i)
            toc.see(i)
        self._help_goto = goto
        toc.bind("<<ListboxSelect>>", lambda e: toc.curselection() and txt.yview(f"sec{toc.curselection()[0]}"))

        def sync(*_):      # 내용을 스크롤하면 목차도 따라 표시
            top = txt.index("@0,0")
            cur = 0
            for i in range(len(HELP_SECTIONS)):
                if txt.compare(f"sec{i}", "<=", top):
                    cur = i
            if toc.curselection() != (cur,):
                toc.selection_clear(0, "end")
                toc.selection_set(cur)
        txt.configure(yscrollcommand=lambda a_, b_: (sb.set(a_, b_), sync()))
        goto(section or 0)
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        self._help_text = txt

    # ---------- 탭 ----------
    def switch_tab(self, t):
        self.sel = None
        if t is not self.tab:
            self.remember_page()
            self.cv.delete("all")
            self.imgs.clear()
        self.tab = t
        try:
            self.bm_panel.refresh()                 # 북마크 탭: 고른 파일의 북마크만
        except (AttributeError, tk.TclError):
            pass
        if t.frame is not None and self.tabbar.select() != str(t.frame):
            self.tabbar.select(t.frame)
        self.fit_tabs_later()
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

    # ── 탭이 많을 때 옆으로 밀기 ──
    def fit_tabs_later(self):
        if self._fit_job is None:
            self._fit_job = self.root.after_idle(self.fit_tabs)

    def _tab_spans_now(self):
        """탭마다 (왼쪽 x, 오른쪽 x) — 탭 막대를 훑어서 구함"""
        nb = self.tabbar
        n = len(self.tabs)
        if not n:
            return []
        y = max(2, nb.winfo_reqheight() // 2)
        spans = [None] * n
        for x in range(0, nb.winfo_width() + 1, 2):
            try:
                i = nb.index(f"@{x},{y}")
            except tk.TclError:
                continue
            if 0 <= i < n:
                a = spans[i]
                spans[i] = (x, x) if a is None else (a[0], x)
        return spans

    def fit_tabs(self):
        self._fit_job = None
        nb, view = self.tabbar, self.tab_view
        try:
            nb.update_idletasks()
            rw, rh = nb.winfo_reqwidth(), nb.winfo_reqheight()
            if int(view.cget("height")) != rh:
                view.configure(height=rh)
            vw = view.winfo_width()
        except tk.TclError:
            return
        if vw <= 1:
            return
        over = len(self.tabs) > 1 and rw > vw
        for w, col in ((self.tab_left, 0), (self.tab_right, 2), (self.tab_more, 3)):
            if over and not w.winfo_ismapped():
                w.grid(row=0, column=col, sticky="ns")
            elif not over and w.winfo_ismapped():
                w.grid_remove()
        if over:                                  # 화살표가 생기면 탭 보이는 폭이 줄어듦
            view.update_idletasks()
            vw = max(1, view.winfo_width())
        if not over:
            self.tab_off = 0
            nb.place(x=0, y=0, width=max(rw, vw), height=rh)
            return
        nb.place(x=-self.tab_off, y=0, width=rw, height=rh)
        nb.update_idletasks()
        self._tab_spans = self._tab_spans_now()
        if self.tab in self.tabs:                         # 고른 탭이 보이게
            sp = self._tab_spans[self.tabs.index(self.tab)]
            if sp:
                if sp[0] < self.tab_off:
                    self.tab_off = sp[0]
                elif sp[1] > self.tab_off + vw:
                    self.tab_off = sp[1] - vw + 2
        self.tab_off = max(0, min(self.tab_off, rw - vw))
        nb.place(x=-self.tab_off, y=0, width=rw, height=rh)
        self.tab_left.state(["!disabled"] if self.tab_off > 0 else ["disabled"])
        self.tab_right.state(["!disabled"] if self.tab_off < rw - vw else ["disabled"])

    def scroll_tabs(self, d):
        """◀ ▶: 가려진 탭 하나만큼 옆으로"""
        vw = self.tab_view.winfo_width()
        rw = self.tabbar.winfo_reqwidth()
        spans = [sp for sp in (self._tab_spans or []) if sp]
        off = self.tab_off
        if d > 0:
            nxt = [sp for sp in spans if sp[1] > off + vw + 1]
            off = (nxt[0][1] - vw + 2) if nxt else rw - vw
        else:
            prv = [sp for sp in spans if sp[0] < off - 1]
            off = prv[-1][0] if prv else 0
        self.tab_off = max(0, min(off, max(0, rw - vw)))
        self.tabbar.place(x=-self.tab_off)
        self.tab_left.state(["!disabled"] if self.tab_off > 0 else ["disabled"])
        self.tab_right.state(["!disabled"] if self.tab_off < rw - vw else ["disabled"])

    def on_tab_wheel(self, e):
        if self.tab_right.winfo_ismapped():
            self.scroll_tabs(-1 if e.delta > 0 else 1)
        return "break"

    def show_tab_list(self):
        m = tk.Menu(self.root, tearoff=0)
        for t in self.tabs:
            m.add_radiobutton(label=("● " if t._dirty else "") + t.title, value=1 if t is self.tab else 0,
                              variable=tk.IntVar(value=1), command=lambda t=t: self.switch_tab(t))
        b = self.tab_more
        m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

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
            self.fit_tabs_later()

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
        self.fit_tabs_later()
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

    def focus_search(self, scope="file"):
        if not self.panel_on.get():
            self.panel_on.set(True)
            self.apply_panel()
        self.side.select(self.search_panel)
        sp = self.search_panel
        sp.scope.set(scope)
        sp.on_scope()
        if scope == "file" and self.sel and self.sel["text"].strip() and len(self.sel["text"]) < 60:
            sp.query.set(" ".join(self.sel["text"].split()))   # 선택한 글자로 바로 찾기
        sp.qe.focus_set()
        sp.qe.select_range(0, "end")

    def show_hit(self, p, rect, text=""):
        """찾은 곳으로 이동하고 파랗게 표시"""
        h = self.doc[p].mediabox.height or 1
        frac = max(0.0, min(1.0, rect.y0 / h))
        self.goto(p, frac)
        self.sel = {"page": p, "text": text, "rects": [fitz.Rect(rect)], "y": frac}
        self.draw_selection()

    def save(self):
        """지금 파일에 바로 덮어쓰기 (Ctrl+S). 저장할 수 없는 곳이면 다른 이름으로 저장"""
        if not self.doc:
            return False
        if not self.path:
            return self.save_as()
        p = self.path
        tmp = os.path.join(os.path.dirname(p), f".~{os.path.basename(p)}.{os.getpid()}.tmp")
        try:
            data = self.doc.tobytes(garbage=3, deflate=True)   # 감춘 글자 등이 파일에 남지 않게 통째로 다시 씀
            with open(tmp, "wb") as f:                          # 임시 파일에 다 쓴 뒤 바꿔치기 → 도중에 실패해도 원본 안전
                f.write(data)
            self.doc.close()
            try:
                os.replace(tmp, p)
            except OSError:
                self.doc = fitz.open(stream=data, filetype="pdf")   # 고친 내용은 그대로 유지
                raise
            self.doc = fitz.open(p)
        except Exception as ex:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            if messagebox.askyesno(APP, f"이 파일에 저장하지 못했습니다:\n{ex}\n\n"
                                        "(다른 프로그램에서 열려 있거나 읽기 전용일 수 있습니다)\n"
                                        "다른 이름으로 저장할까요?"):
                return self.save_as()
            return False
        self.dirty = False
        self.status.set(f"저장했습니다: {p}")
        return True

    # ---------- 바로가기 ----------
    def refresh_shortcut_btn(self):
        if sys.platform != "win32":
            return
        try:
            done = has_desktop_shortcut() and is_pinned_to_taskbar()
            if done:
                self.sc_btn.pack_forget()
            elif not self.sc_btn.winfo_ismapped():
                self.sc_btn.pack(side="right", padx=(1, 6))
        except tk.TclError:
            pass

    def shortcut_menu_at_pointer(self):
        if not self.sc_btn.winfo_ismapped():      # 버튼이 숨겨졌으면 마우스 위치에 메뉴
            m = tk.Menu(self.root, tearoff=0)
            m.add_command(label="🖥 바탕화면에 바로가기 만들기", command=self.make_desktop_shortcut)
            m.add_command(label="📌 작업표시줄에 고정하기…", command=self.pin_taskbar)
            try:
                m.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
            finally:
                m.grab_release()
        else:
            self.shortcut_menu()

    def shortcut_menu(self):
        m = tk.Menu(self.root, tearoff=0)
        desk, task = has_desktop_shortcut(), is_pinned_to_taskbar()
        m.add_command(label="🖥 바탕화면에 바로가기 만들기" + ("  (만들어 둠)" if desk else ""),
                      command=self.make_desktop_shortcut, state="disabled" if desk else "normal")
        m.add_command(label="📌 작업표시줄에 고정하기…" + ("  (고정됨)" if task else ""),
                      command=self.pin_taskbar, state="disabled" if task else "normal")
        b = self.sc_btn
        try:
            m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())
        finally:
            m.grab_release()

    def make_desktop_shortcut(self):
        try:
            make_shortcut(desktop_dir())
            self.status.set("바탕화면에 '스마트PDF Editor' 바로가기를 만들었습니다.")
        except Exception as ex:
            messagebox.showerror(APP, f"바로가기를 만들 수 없습니다:\n{ex}")
        self.root.after(800, self.refresh_shortcut_btn)

    def pin_taskbar(self):
        try:          # 시작 메뉴에도 넣어 두면 검색·고정이 쉬움
            make_shortcut(os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"))
        except Exception:
            pass
        messagebox.showinfo(APP, "작업표시줄 고정은 Windows 보안 정책상 프로그램이 스스로 할 수 없어서, 한 번만 직접 해 주세요.\n\n"
                                 "① 화면 아래 작업표시줄에 있는 스마트PDF Editor 아이콘을 마우스 오른쪽 클릭\n"
                                 "② [작업 표시줄에 고정] 클릭\n\n"
                                 "(시작 메뉴에도 넣어 두었습니다. 시작 메뉴에서 오른쪽 클릭 → [작업 표시줄에 고정]으로도 됩니다.)")
        self._watch_pin(40)

    def _watch_pin(self, n):
        if is_pinned_to_taskbar():
            self.status.set("작업표시줄에 고정됐습니다.")
            self.refresh_shortcut_btn()
        elif n > 0:
            self.root.after(1500, lambda: self._watch_pin(n - 1))

    def print_doc(self):
        """인쇄 (Ctrl+P): Windows 인쇄 창에서 프린터·쪽 범위·매수를 고르면 지금 보이는 그대로(고친 내용 포함) 인쇄"""
        if not self.doc:
            messagebox.showinfo(APP, "먼저 PDF를 열어주세요.")
            return
        if sys.platform != "win32":
            messagebox.showinfo(APP, "인쇄는 Windows에서만 됩니다.")
            return
        try:
            got = ask_printer(int(self.root.wm_frame(), 16), len(self.doc), self.page_no)
        except Exception as ex:
            messagebox.showerror(APP, f"인쇄 창을 열 수 없습니다:\n{ex}")
            return
        if not got:
            return
        hdc, pages = got
        api = _print_lib()
        self.root.configure(cursor="watch")

        def prog(i, n):
            self.status.set(f"인쇄 중… {i + 1} / {n}쪽")
            self.root.update_idletasks()
        try:
            print_pages(hdc, self.doc, pages, title=self.tab.title, progress=prog)
            self.status.set(f"인쇄를 보냈습니다: {len(pages)}쪽")
        except Exception as ex:
            messagebox.showerror(APP, f"인쇄하지 못했습니다:\n{ex}")
        finally:
            api["gdi"].DeleteDC(hdc)
            self.root.configure(cursor="")

    def save_as(self):
        """다른 이름으로 저장 (Ctrl+Shift+S) — 저장한 뒤에는 탭이 새 파일을 가리킴"""
        if not self.doc:
            return False
        base = self.path or "새 문서.pdf"
        p = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=os.path.basename(base),
                                         initialdir=os.path.dirname(base) or None, filetypes=[("PDF", "*.pdf")],
                                         title="다른 이름으로 저장")
        if not p:
            return False
        p = os.path.abspath(p)
        if self.path and os.path.normcase(p) == os.path.normcase(os.path.abspath(self.path)):
            return self.save()
        for t in self.tabs:
            if t is not self.tab and t.path and os.path.normcase(t.path) == os.path.normcase(p):
                messagebox.showwarning(APP, "그 파일은 다른 탭에서 열려 있습니다. 그 탭을 닫은 뒤 다시 해 주세요.")
                return False
        try:
            self.doc.save(p, garbage=3, deflate=True)
        except Exception as ex:
            messagebox.showerror(APP, f"저장 실패:\n{ex}")
            return False
        self.remember_page()
        old = self.path
        if old:                # 북마크도 새 파일로 따라가게 복사 (원래 파일 북마크는 그대로)
            def copy_marks(nodes):
                for n in list(nodes):
                    if n.get("type") == "folder":
                        copy_marks(n.get("children", []))
                    elif n.get("path") and os.path.normcase(n["path"]) == os.path.normcase(old):
                        nodes.append(dict(n, path=p))
            copy_marks(self.conf["bookmarks"])
        self.path = p          # 탭은 새로 저장한 파일을 가리킴
        self.dirty = False
        self.update_tab_title(self.tab)
        self.root.title(f"{self.tab.title} - {APP}")
        self.add_recent(p)
        self.update_recent_menu()
        self.persist()
        self.bm_panel.refresh()
        self.status.set(f"저장했습니다: {p}")
        return True

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
                  wheel_page=self.wheel_page.get(), app_mode=pr.get("start_mode", self.app_mode.get()),
                  memo_side=self.memo_side.get(), memo_style=self.memo_style.get())
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
            for i, p in enumerate(self.conf["recent"][:30]):
                m.add_command(label=f"{i + 1}. {os.path.basename(p)}   —  {os.path.dirname(p)}",
                              command=lambda p=p: self.open_path(p))
            m.add_separator()
            m.add_command(label=f"최근 본 파일 목록 보기 (전체 {len(self.conf['recent'])}개)",
                          command=lambda: self.show_side(self.recent_panel))
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
        dlg = Popup(self.root)
        dlg.title("환경설정")
        dlg.transient(self.root)
        dlg.resizable(False, False)
        nb = ttk.Notebook(dlg)
        nb.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        # ── 일반
        frm = ttk.Frame(nb, padding=14)
        nb.add(frm, text="일반")
        vars_ = {}
        rows = (("fav_max", "즐겨찾기 최대 개수", 1000), ("bm_max", "북마크 최대 개수", 2000),
                ("recent_max", "최근 본 파일 개수", 200))
        ttk.Label(frm, text="저장 개수", font=(self.theme.get("font_family"), 10, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 6))
        for i, (k, label, mx) in enumerate(rows, 1):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=2)
            v = tk.IntVar(value=self.limit(k))
            ttk.Spinbox(frm, from_=1, to=mx, textvariable=v, width=7).grid(row=i, column=1, sticky="w", padx=8)
            cur = len(self.conf["recent"]) if k == "recent_max" else \
                count_items(self.conf["favorites" if k == "fav_max" else "bookmarks"])
            ttk.Label(frm, text=f"(지금 {cur}개)").grid(row=i, column=2, sticky="w")
            vars_[k] = v
        ttk.Separator(frm).grid(row=5, column=0, columnspan=3, sticky="ew", pady=10)
        ttk.Checkbutton(frm, text="마우스 휠 한 칸에 한 쪽씩 넘기기", variable=self.wheel_page).grid(
            row=6, column=0, columnspan=3, sticky="w")
        no_stats = tk.BooleanVar(value=bool(self.conf["prefs"].get("no_stats", False)))
        ttk.Checkbutton(frm, text="사용 통계 보내지 않기 (보내는 것: 무작위 번호와 버전뿐)",
                        variable=no_stats).grid(row=9, column=0, columnspan=3, sticky="w", pady=(6, 0))
        start = tk.StringVar(value=self.conf["prefs"].get("start_mode", self.app_mode.get()))
        sf = ttk.Frame(frm)
        sf.grid(row=7, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Label(sf, text="시작할 때:").pack(side="left")
        ttk.Radiobutton(sf, text="뷰어 모드", value="view", variable=start).pack(side="left", padx=6)
        ttk.Radiobutton(sf, text="편집 모드", value="edit", variable=start).pack(side="left")
        ef = ttk.Frame(frm)
        ef.grid(row=8, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Label(ef, text="탐색기에서 PDF를 열면:").pack(side="left")
        ttk.Radiobutton(ef, text="새 탭", value="tab", variable=self.ext_open).pack(side="left", padx=6)
        ttk.Radiobutton(ef, text="새 창", value="window", variable=self.ext_open).pack(side="left")

        # ── 화면 꾸미기
        old_theme = dict(self.theme)
        tf = ttk.Frame(nb, padding=14)
        nb.add(tf, text="화면 꾸미기")
        tv = {k: tk.StringVar(value=str(self.theme.get(k, ""))) for k in THEME_DEFAULT}
        names = {v["name"]: k for k, v in THEMES.items()}
        preset_name = tk.StringVar(value=THEMES.get(self.theme.get("preset"), THEMES["clip"])["name"])

        r = 0
        ttk.Label(tf, text="테마").grid(row=r, column=0, sticky="w", pady=3)
        pc = ttk.Combobox(tf, textvariable=preset_name, values=list(names), state="readonly", width=18)
        pc.grid(row=r, column=1, columnspan=2, sticky="w", padx=8)
        r += 1
        # 빠른 선택: 테마 버튼 + 기본 배경 그림 (누르면 바로 미리 보기)
        ttk.Label(tf, text="빠른 선택").grid(row=r, column=0, sticky="nw", pady=3)
        qf = ttk.Frame(tf)
        qf.grid(row=r, column=1, columnspan=2, sticky="w", padx=8, pady=3)

        def quick_theme(name):
            preset_name.set(name)
            reset_colors()
            preview()
        for i, (k, v) in enumerate(THEMES.items()):
            ttk.Button(qf, text=v["name"], command=lambda n=v["name"]: quick_theme(n)).grid(
                row=i // 4, column=i % 4, padx=1, pady=1, sticky="ew")
        r += 1
        ttk.Label(tf, text="배경 그림 고르기").grid(row=r, column=0, sticky="nw", pady=3)
        gf = ttk.Frame(tf)
        gf.grid(row=r, column=1, columnspan=2, sticky="w", padx=8, pady=3)
        dlg._thumbs = []

        def quick_wall(name, photo=False):
            try:
                tv["wall"].set((photo_wall_path(name) if photo else wall_preset_path(name)) if name else "")
            except Exception as e:
                messagebox.showerror(APP, f"배경 그림을 만들지 못했습니다.\n{e}", parent=dlg)
                return
            show_wall()
            preview()
        for name, _ in WALL_PRESETS:
            try:
                th = wall_thumb(name)
            except Exception:
                continue
            dlg._thumbs.append(th)
            lb = tk.Label(gf, image=th, text=name, compound="top", cursor="hand2", relief="solid", bd=1,
                          font=("맑은 고딕", 8), padx=1, pady=1)
            lb.pack(side="left", padx=2)
            lb.bind("<Button-1>", lambda e, n=name: quick_wall(n))
        nb_ = tk.Label(gf, text="없음", width=6, height=3, cursor="hand2", relief="solid", bd=1, font=("맑은 고딕", 8))
        nb_.pack(side="left", padx=2)
        nb_.bind("<Button-1>", lambda e: quick_wall(None))
        r += 1
        if PHOTO_WALLS:                                   # 실제 풍경 사진
            ttk.Label(tf, text="배경 사진 고르기").grid(row=r, column=0, sticky="nw", pady=3)
            phf = ttk.Frame(tf)
            phf.grid(row=r, column=1, columnspan=2, sticky="w", padx=8, pady=3)
            for i, (name, _, _) in enumerate(PHOTO_WALLS):
                try:
                    th = photo_wall_thumb(name)
                except Exception:
                    continue
                dlg._thumbs.append(th)
                lb = tk.Label(phf, image=th, text=name, compound="top", cursor="hand2", relief="solid", bd=1,
                              font=("맑은 고딕", 8), padx=1, pady=1)
                lb.grid(row=i // 6, column=i % 6, padx=2, pady=2)
                lb.bind("<Button-1>", lambda e, n=name: quick_wall(n, photo=True))
            r += 1
        fams = sorted({f for f in tkfont.families(self.root) if not f.startswith("@")})
        first = [f for f in FONT_FIRST if f in fams]
        ttk.Label(tf, text="글꼴").grid(row=r, column=0, sticky="w", pady=3)
        ttk.Combobox(tf, textvariable=tv["font_family"], values=first + [f for f in fams if f not in first],
                     width=18).grid(row=r, column=1, columnspan=2, sticky="w", padx=8)
        r += 1
        ttk.Label(tf, text="글자 크기").grid(row=r, column=0, sticky="w", pady=3)
        ttk.Spinbox(tf, from_=7, to=20, textvariable=tv["font_size"], width=5).grid(row=r, column=1, sticky="w", padx=8)
        r += 1
        swatches = {}

        def color_row(key, label, tip):
            nonlocal r
            ttk.Label(tf, text=label).grid(row=r, column=0, sticky="w", pady=3)
            sw = tk.Label(tf, width=4, relief="groove", cursor="hand2")
            sw.grid(row=r, column=1, sticky="w", padx=8)
            swatches[key] = sw
            ttk.Label(tf, text=tip, foreground="#888").grid(row=r, column=2, sticky="w")

            def pick(e=None):
                c = colorchooser.askcolor(tv[key].get() or self.tcolor(key) or "#ffffff", parent=dlg)[1]
                if c:
                    tv[key].set(c)
                    refresh_sw()
            sw.bind("<Button-1>", pick)
            r += 1
        color_row("fg", "글자 색", "누르면 색 고르기")
        color_row("bg", "바탕 색", "도구줄·사이드바")
        color_row("accent", "강조 색", "눌린 버튼·선택")
        color_row("canvas", "문서 배경 색", "쪽 뒤 배경")

        def refresh_sw():
            pr_ = THEMES[names[preset_name.get()]]
            for k, sw in swatches.items():
                c = tv[k].get() or pr_.get(k) or "#f0f0f0"
                sw.configure(bg=c)

        ttk.Label(tf, text="배경 그림").grid(row=r, column=0, sticky="w", pady=3)
        wf = ttk.Frame(tf)
        wf.grid(row=r, column=1, columnspan=2, sticky="w", padx=8)
        wall_lbl = ttk.Label(wf, width=22)
        wall_lbl.pack(side="left")

        def show_wall():
            w = tv["wall"].get()
            wall_lbl.config(text=os.path.basename(w) if w else "(없음)")

        def pick_wall():
            fp = filedialog.askopenfilename(parent=dlg, filetypes=[("그림", "*.png *.jpg *.jpeg *.gif *.bmp")])
            if fp:
                tv["wall"].set(fp)
                show_wall()
        ttk.Button(wf, text="찾아보기", command=pick_wall).pack(side="left", padx=2)
        ttk.Button(wf, text="지우기", command=lambda: (tv["wall"].set(""), show_wall())).pack(side="left")
        r += 1
        ttk.Label(tf, text="※ 배경 그림은 PDF를 열지 않았을 때와 쪽 뒤 빈 곳에 보입니다. "
                           "색을 직접 고르면 테마 색보다 우선합니다. [테마 색으로]를 누르면 직접 고른 색을 지웁니다.",
                  foreground="#888", wraplength=380).grid(row=r, column=0, columnspan=3, sticky="w", pady=(8, 0))
        r += 1

        def reset_colors():
            for k in ("fg", "bg", "accent", "canvas"):
                tv[k].set("")
            refresh_sw()

        def collect():
            th = {k: v.get().strip() for k, v in tv.items()}
            th["preset"] = names[preset_name.get()]
            try:
                th["font_size"] = max(7, min(20, int(float(th["font_size"] or 9))))
            except ValueError:
                th["font_size"] = 9
            return th

        def preview():
            self.theme = collect()
            self.apply_theme()

        tb = ttk.Frame(tf)
        tb.grid(row=r, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Button(tb, text="테마 색으로", command=reset_colors).pack(side="left")
        ttk.Button(tb, text="미리 보기", command=preview).pack(side="left", padx=4)
        pc.bind("<<ComboboxSelected>>", lambda e: (reset_colors(), preview()))
        refresh_sw()
        show_wall()

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
            pr["no_stats"] = no_stats.get()
            pr["start_mode"] = start.get()
            pr["app_mode"] = start.get()
            self.theme = collect()
            pr["theme"] = dict(self.theme)
            self.apply_theme()
            self.on_ext_open()
            self.update_recent_menu()
            self.persist()
            dlg.destroy()
            over = [lbl for k, lbl, _ in rows[:2]
                    if count_items(self.conf["favorites" if k == "fav_max" else "bookmarks"]) > pr[k]]
            self.status.set("설정을 저장했습니다." + (f" ({', '.join(over)}보다 이미 많은 항목은 그대로 두고, "
                                                    "새로 추가할 때부터 적용합니다)" if over else ""))

        def cancel():
            if self.theme != old_theme:      # 미리 보기 했던 것 되돌림
                self.theme = old_theme
                self.apply_theme()
            dlg.destroy()
        b = ttk.Frame(dlg, padding=(10, 8))
        b.pack(fill="x")
        ttk.Button(b, text="취소", command=cancel).pack(side="right")
        ttk.Button(b, text="저장", command=ok).pack(side="right", padx=4)
        dlg.protocol("WM_DELETE_WINDOW", cancel)
        dlg.bind("<Escape>", lambda e: cancel())
        dlg.grab_set()
        self._settings_dlg = (dlg, tv, preset_name, ok, cancel)   # 자동 점검용

    # ---------- 화면 꾸미기 (테마 · 글꼴 · 배경) ----------
    def tcolor(self, key):
        """현재 테마 색. 사용자가 직접 고른 색이 우선"""
        if key in ("fg", "bg", "accent", "canvas") and self.theme.get(key):
            return self.theme[key]
        return THEMES.get(self.theme.get("preset"), THEMES["clip"]).get(key) or ""

    def preset(self):
        return THEMES.get(self.theme.get("preset"), THEMES["clip"])

    def assign_top_styles(self, w):
        """도구줄 위젯에 Top.* 스타일을 붙임 (테마 색은 도구줄에만)"""
        cls = w.winfo_class()
        m = {"TFrame": "Top.TFrame", "TButton": "Top.TButton", "TLabel": "Top.TLabel",
             "TSeparator": "Top.TSeparator", "TRadiobutton": "Top.Toolbutton"}
        if cls in m:
            try:
                w.configure(style=m[cls])
            except tk.TclError:
                pass
        for ch in w.winfo_children():
            self.assign_top_styles(ch)

    @staticmethod
    def _tint(c, k):
        """색 c를 흰색 쪽으로 k만큼 섞음 (0=그대로, 1=흰색)"""
        try:
            r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
        except (TypeError, ValueError, IndexError):
            return c
        return "#%02x%02x%02x" % tuple(round(v + (255 - v) * k) for v in (r, g, b))

    @staticmethod
    def _is_dark(c):
        try:
            return sum(int(c[i:i + 2], 16) for i in (1, 3, 5)) < 384
        except (TypeError, ValueError, IndexError):
            return False

    def _style_set(self, st, pre, pal, size):
        """pre="" 이면 기본 스타일, "Top." 이면 도구줄 스타일"""
        bg, fg, ac, field = pal["bg"], pal["fg"], pal["accent"], pal["field"]
        dark = self._is_dark(bg)
        hover = self._tint(ac, 0.7) if not dark else "#4a4a50"
        sel_bg = self._tint(ac, 0.45) if not dark else ac      # 눌린 버튼: 연한 강조색 (아이콘이 묻히지 않게)
        sel_fg = "#ffffff" if dark else fg
        st.configure(pre + "TFrame", background=bg)
        st.configure(pre + "TLabel", background=bg, foreground=fg)
        st.configure(pre + "TSeparator", background=bg)
        st.configure(pre + "TButton", background=field, foreground=fg, bordercolor=ac if pre else "#b9b9b9",
                     lightcolor=field, darkcolor=field, padding=(3, 1))
        st.map(pre + "TButton", background=[("active", hover)])
        st.configure(pre + "Toolbutton", background=bg, foreground=fg, padding=(3, 1))
        st.map(pre + "Toolbutton", background=[("selected", sel_bg), ("active", hover)],
               foreground=[("selected", sel_fg)])
        st.configure(pre + "Toolbutton", bordercolor=ac)
        if not pre:
            st.configure(".", background=bg, foreground=fg, fieldbackground=field, bordercolor="#b9b9b9",
                         lightcolor=bg, darkcolor=bg, troughcolor=bg, selectbackground=ac, selectforeground=fg,
                         insertcolor=fg)
            st.configure("TNotebook", background=bg, bordercolor="#b9b9b9")
            st.configure("TNotebook.Tab", background=bg, padding=(6, 2))
            st.map("TNotebook.Tab", background=[("selected", field)], expand=[("selected", (1, 1, 1, 0))])
            st.configure("Treeview", background=field, fieldbackground=field, foreground=fg,
                         rowheight=int(size * 2.3) + 2)
            st.map("Treeview", background=[("selected", ac)], foreground=[("selected", sel_fg)])
            st.configure("Treeview.Heading", background=bg, foreground=fg)
            for w in ("TEntry", "TSpinbox", "TCombobox"):
                st.configure(w, fieldbackground=field, foreground=fg, background=bg, arrowcolor=fg)
            st.map("TCombobox", fieldbackground=[("readonly", field)])
            for sb_ in ("TScrollbar", "Vertical.TScrollbar", "Horizontal.TScrollbar"):
                st.configure(sb_, background=field, troughcolor=bg, bordercolor=bg, arrowcolor=fg,
                             lightcolor=field, darkcolor=field)
            st.map("TScrollbar", background=[("active", hover)])
            st.configure("TCheckbutton", background=bg, foreground=fg)
            st.configure("TRadiobutton", background=bg, foreground=fg)

    def apply_theme(self):
        st = ttk.Style(self.root)
        if not hasattr(self, "_native_theme"):
            self._native_theme = st.theme_use()
        fam = self.theme.get("font_family") or "맑은 고딕"
        try:
            size = max(7, min(20, int(self.theme.get("font_size") or 9)))
        except (TypeError, ValueError):
            size = 9
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkTooltipFont"):
            try:
                tkfont.nametofont(name).configure(family=fam, size=size)
            except tk.TclError:
                pass
        pr_ = self.preset()
        top = {"bg": self.tcolor("bg"), "fg": self.tcolor("fg"), "accent": self.tcolor("accent"),
               "field": pr_.get("field") or "#ffffff"}
        if not top["bg"]:      # 기본(회색): Windows 기본 모양 그대로
            st.theme_use(self._native_theme)
            self.ensure_tab_close(st)
            fg_ = top["fg"] or "black"
            st.configure(".", font=(fam, size), foreground=fg_)
            st.configure("Treeview", rowheight=int(size * 2.3) + 2, foreground=fg_)
            base_bg = top_bg = st.lookup(".", "background") or "SystemButtonFace"
            self._top_dark = self._base_dark = False
        else:
            st.theme_use("clam")
            self.ensure_tab_close(st)
            top["fg"] = top["fg"] or "#1f1f1f"
            top["accent"] = top["accent"] or "#cfe3fa"
            base = dict(top) if pr_.get("scope") == "all" else dict(NEUTRAL)   # 기본 색은 도구줄에만
            st.configure(".", font=(fam, size))
            self._style_set(st, "", base, size)
            self._style_set(st, "Top.", top, size)
            base_bg, top_bg = base["bg"], top["bg"]
            self._top_dark, self._base_dark = self._is_dark(top_bg), self._is_dark(base_bg)
        self.page_scroll_style(st)
        self.root.configure(bg=base_bg)
        top_fg = (self.tcolor("fg") or "black") if self.tcolor("bg") else "black"
        hot = self._tint(self.tcolor("accent"), 0.55) if self.tcolor("accent") else "#cce4f7"
        if self._top_dark:
            hot = "#4a4a50"
        self.menubar.recolor(top_bg, top_fg, hot)
        for w, is_link in self.themed_labels:
            try:
                w.configure(bg=top_bg)
                if is_link:
                    w.configure(fg=self.tcolor("link") or "#1565c0", font=(fam, size, "underline"))
            except tk.TclError:
                pass
        try:
            self.ad_frame.configure(bg=base_bg)
            self.ad_label.configure(bg=base_bg)
        except (AttributeError, tk.TclError):
            pass
        self.refresh_icons()
        self.ensure_tab_close(st, force_layout=True)
        self.cv.configure(bg=self.tcolor("canvas") or "#5a5a5a")
        self.root.after(50, self.fit_toolbar)     # 글꼴 크기가 바뀌면 도구줄 다시 맞춤
        if hasattr(self, "theme_var"):
            self.theme_var.set(self.theme.get("preset", "clip"))
        self.load_wall()
        if self.doc:
            self.render()
        else:
            self.place_wall()

    # ---------- 프로그램 아이콘 ----------
    def set_app_icon(self):
        """제목줄·작업표시줄 아이콘 (Tk 기본 깃털 모양 대신). 모든 창에 적용"""
        try:
            self._app_icons = [tk.PhotoImage(data="".join(APP_ICON_PNG[z])) for z in (256, 48, 32, 16)]
            self.root.iconphoto(True, *self._app_icons)
        except (tk.TclError, KeyError):
            pass

    # ---------- 탭 닫기(×) 버튼 ----------
    def page_scroll_style(self, st):
        """쪽 화면 오른쪽(아래) 스크롤 막대: 지금 위치가 잘 보이게 진한 색 손잡이.
        Windows 기본 모양은 색을 못 바꾸므로 색을 바꿀 수 있는 모양(clam)을 빌려 씀"""
        theme = st.theme_use()
        done = getattr(self, "_page_sb_themes", None)
        if done is None:
            done = self._page_sb_themes = set()
        if theme not in done:
            for o in ("Vertical", "Horizontal"):
                for el in ("trough", "thumb"):
                    try:
                        st.element_create(f"Page.{o}.Scrollbar.{el}", "from", "clam")
                    except tk.TclError:
                        pass
            st.layout("Page.Vertical.TScrollbar", [("Page.Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
                ("Page.Vertical.Scrollbar.thumb", {"sticky": "nswe", "unit": 1})]})])
            st.layout("Page.Horizontal.TScrollbar", [("Page.Horizontal.Scrollbar.trough", {"sticky": "we", "children": [
                ("Page.Horizontal.Scrollbar.thumb", {"sticky": "nswe", "unit": 1})]})])
            done.add(theme)
        dark = getattr(self, "_base_dark", False)
        thumb, hot, trough, arrow = (("#b8bcc2", "#e0e3e7", "#2b2b2e", "#b8bcc2") if dark
                                     else ("#5f6368", "#3c4043", "#e6e6e6", "#5f6368"))
        for o in ("Vertical", "Horizontal"):
            name = f"Page.{o}.TScrollbar"
            st.configure(name, background=thumb, troughcolor=trough, bordercolor=trough, lightcolor=thumb,
                         darkcolor=thumb, arrowcolor=arrow, gripcount=0, arrowsize=16, relief="flat")
            st.map(name, background=[("pressed", hot), ("active", hot)],
                   lightcolor=[("pressed", hot), ("active", hot)], darkcolor=[("pressed", hot), ("active", hot)])

    def ensure_tab_close(self, st, force_layout=False):
        """탭 이름 오른쪽에 × 그림을 넣은 탭 모양 (ttk 테마마다 한 번 만듦)"""
        theme = st.theme_use()
        if theme not in self._close_themes:
            for var in ("light", "dark"):
                n, h = (self._icon_var_img(var, "tab_x"), self._icon_var_img(var, "tab_x_hot"))
                try:
                    st.element_create(f"tabclose_{var}", "image", n, ("active", "pressed", "!disabled", h),
                                      ("active", "!disabled", h), border=4, sticky="")
                except tk.TclError:
                    pass
            self._close_themes.add(theme)
            force_layout = True
        if force_layout:
            var = "dark" if getattr(self, "_base_dark", False) else "light"
            st.layout("Closable.TNotebook", [("Notebook.client", {"sticky": "nswe"})])
            st.layout("Closable.TNotebook.Tab", [
                ("Notebook.tab", {"sticky": "nswe", "children": [
                    ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
                        ("Notebook.focus", {"side": "top", "sticky": "nswe", "children": [
                            ("Notebook.label", {"side": "left", "sticky": ""}),
                            (f"tabclose_{var}", {"side": "left", "sticky": ""}),
                        ]})]})]})])
            if hasattr(self, "tabbar"):
                self.tabbar.configure(style="Closable.TNotebook")

    def _icon_var_img(self, var, name):
        key = (var, name)
        if key not in self._icons:
            self._icons[key] = tk.PhotoImage(data=ICON_DATA[var][name])
        return self._icons[key]

    def on_tab_press(self, e):
        try:
            elem = self.tabbar.identify(e.x, e.y)
        except tk.TclError:
            return
        if "tabclose" in elem:
            self._pressed_tab = self.tabbar.index(f"@{e.x},{e.y}")
            self.tabbar.state(["pressed"])
            return "break"           # 탭이 바뀌지 않게

    def on_tab_release(self, e):
        if self._pressed_tab is None:
            return
        idx, self._pressed_tab = self._pressed_tab, None
        self.tabbar.state(["!pressed"])
        try:
            elem = self.tabbar.identify(e.x, e.y)
            same = self.tabbar.index(f"@{e.x},{e.y}") == idx
        except tk.TclError:
            return
        if "tabclose" in elem and same and idx < len(self.tabs):
            self.close_tab(self.tabs[idx])

    # ---------- 아이콘 ----------
    def icon(self, name, area="top"):
        dark = getattr(self, "_top_dark" if area == "top" else "_base_dark", False) if area != "menu" else False
        var = "dark" if dark else "light"
        key = (var, name)
        if key not in self._icons:
            data = ICON_DATA[var].get(name) or ICON_DATA["light"].get(name)
            self._icons[key] = tk.PhotoImage(data=data) if data else ""
        return self._icons[key]

    def set_icon(self, widget, name, area="top"):
        widget.configure(image=self.icon(name, area))
        self.icon_users.append((widget, name, area))

    def refresh_icons(self):
        for w, name, area in self.icon_users:
            try:
                w.configure(image=self.icon(name, area))
            except tk.TclError:
                pass

    def menu_icon(self, name):
        return self.icon(name, "menu")

    # ---------- 색상표 ----------
    def palette_popup(self, anchor, setter):
        if getattr(self, "_palette", None) and self._palette.winfo_exists():
            self._palette.destroy()
        pop = self._palette = tk.Toplevel(self.root)
        pop.wm_overrideredirect(True)
        pop.configure(bg="#9e9e9e")
        inner = tk.Frame(pop, bg="#ffffff", padx=6, pady=6)
        inner.pack(padx=1, pady=1)

        def choose(c):
            pop.destroy()
            if c:
                setter(c)
        for r, row in enumerate(PALETTE):
            for c_, col in enumerate(row):
                l_ = tk.Label(inner, bg=col, width=2, height=1, relief="raised", bd=1, cursor="hand2")
                l_.grid(row=r, column=c_, padx=2, pady=2)
                l_.bind("<Button-1>", lambda e, col=col: choose(col))
                l_.bind("<Enter>", lambda e, w=l_: w.configure(relief="sunken"))
                l_.bind("<Leave>", lambda e, w=l_: w.configure(relief="raised"))
        more = tk.Label(inner, text="다른 색 직접 고르기…", bg="#ffffff", fg="#1565c0", cursor="hand2")
        more.grid(row=len(PALETTE), column=0, columnspan=8, sticky="w", pady=(4, 0))

        def custom(e=None):
            pop.destroy()
            c = colorchooser.askcolor(title="색 고르기")[1]
            if c:
                setter(c)
        more.bind("<Button-1>", custom)
        try:
            if not anchor.winfo_viewable():
                raise tk.TclError
            x, y = anchor.winfo_rootx(), anchor.winfo_rooty() + anchor.winfo_height() + 2
        except tk.TclError:   # 버튼이 안 보일 때(메뉴에서 연 경우 등)는 마우스 위치에
            x, y = self.root.winfo_pointerx(), self.root.winfo_pointery()
        pop.wm_geometry(f"+{x}+{y}")
        pop.bind("<Escape>", lambda e: pop.destroy())
        def maybe_close():   # 색상표 바깥을 누르면 닫힘
            if not pop.winfo_exists():
                return
            f = self.root.focus_get()
            if f is None or not str(f).startswith(str(pop)):
                pop.destroy()
        pop.bind("<FocusOut>", lambda e: pop.after(150, maybe_close))
        pop.focus_force()
        return pop

    def set_preset(self, key):
        """메뉴에서 테마 바로 바꾸기 (직접 고른 색은 지움, 글꼴·배경 그림은 유지)"""
        self.theme.update(preset=key, fg="", bg="", accent="", canvas="")
        self.conf["prefs"]["theme"] = dict(self.theme)
        self.apply_theme()
        self.persist()

    def load_wall(self):
        path = self.theme.get("wall") or ""
        self._wall_src, self._wall_key, self._wall_img = None, None, None
        self.cv.delete("wall")
        if path and os.path.exists(path):
            try:
                pix = fitz.Pixmap(path)
                if pix.alpha:
                    pix = fitz.Pixmap(pix, 0)            # 투명 부분 없애기
                if pix.n != 3:
                    pix = fitz.Pixmap(fitz.csRGB, pix)   # 흑백·CMYK → RGB
                self._wall_src = pix
            except Exception:
                self.status.set("배경 그림을 열 수 없습니다.")

    def place_wall(self):
        """배경 그림을 화면 크기에 꽉 차게, 스크롤해도 제자리에"""
        if self._wall_src is None:
            return
        cw, ch = max(50, self.cv.winfo_width()), max(50, self.cv.winfo_height())
        if self._wall_key != (cw, ch):
            src = self._wall_src
            k = max(cw / src.width, ch / src.height)
            try:
                pix = fitz.Pixmap(src, max(1, int(src.width * k)), max(1, int(src.height * k)), None)
                self._wall_img = tk.PhotoImage(data=base64.b64encode(pix.tobytes("png")))
            except Exception:
                self._wall_src = None
                return
            self._wall_key = (cw, ch)
            self.cv.delete("wall")
        cx, cy = self.cv.canvasx(cw / 2), self.cv.canvasy(ch / 2)
        if self.cv.find_withtag("wall"):
            self.cv.coords("wall", cx, cy)
        else:
            self.cv.create_image(cx, cy, image=self._wall_img, anchor="center", tags="wall")
        self.cv.tag_lower("wall")

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
        if self.sel and self.sel["text"].strip():   # 선택한 글자가 있으면 묻지 않고 바로 그 글자로 추가
            name = " ".join(self.sel["text"].split())[:60]
            page, pos = self.sel["page"], round(self.sel["y"], 4)
            self.status.set(f"북마크에 추가했습니다: {name}  ({page + 1}쪽)")
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
        memo = MEMO_W if self._memo_pages and cols == 1 else 0   # 오른쪽 메모 칸만큼 빼고 맞춤
        if fit == "width":
            maxw = max(self.sizes[i][0] for i in pages)
            sb = 0 if self.view == "single" else 4
            z = (cw - 2 * MARGIN - (cols - 1) * GAP - sb - memo) / (cols * maxw)
        else:
            maxh = max(self.sizes[i][1] for i in pages)
            z = (ch - 2 * MARGIN) / maxh
            if memo:
                z = min(z, (cw - 2 * MARGIN - memo) / max(self.sizes[i][0] for i in pages))
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
        memo = MEMO_W if self._memo_pages and cols == 1 else 0
        widths = [sum(self.sizes[p][0] * z for p in r) + GAP * (len(r) - 1) + memo for r in rows]
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

    # ---------- 오른쪽 스크롤바: 문서 전체에서의 위치 ----------
    def _single_scroll(self):
        """'한 쪽씩' 보기는 화면에 한 쪽만 그려서, 스크롤바를 그대로 쓰면 그 쪽 안의 위치만 보임
        → 전체 쪽수 기준(쪽 번호 + 쪽 안 위치)으로 환산해서 보여줌"""
        return self.view == "single" and bool(self.doc) and len(self.doc) > 1

    def set_vscroll(self, a, b):
        a, b = float(a), float(b)
        if not self._single_scroll():
            self.vs.set(a, b)
            return
        n = len(self.doc)
        v = max(0.0, min(1.0, b - a))
        L = max(v / n, 0.04)                      # 손잡이가 너무 작아지지 않게
        room = 1 - v / n
        pos = (self.page_no + a) / n              # 0 ~ (1 - v/n)
        f0 = pos * (1 - L) / room if room > 1e-9 else 0.0
        f0 = max(0.0, min(1 - L, f0))
        self.vs.set(f0, f0 + L)

    def update_vscroll(self):
        a, b = self.cv.yview()
        self.set_vscroll(a, b)

    def vscroll_cmd(self, *args):
        """스크롤바를 끌거나 누를 때 (args: 'moveto', 위치 / 'scroll', 칸수, 단위)"""
        if not args:
            return
        if not self._single_scroll():
            self.cv.yview(*args)
            return
        if args[0] == "moveto":
            n = len(self.doc)
            a, b = self.cv.yview()
            v = max(0.0, min(1.0, b - a))
            L = max(v / n, 0.04)
            room = 1 - v / n
            pos = float(args[1]) * room / (1 - L) if L < 1 else 0.0
            t = max(0.0, min(n - v, pos * n))     # 쪽 번호 + 쪽 안 위치
            p = max(0, min(n - 1, int(t)))
            within = max(0.0, min(1 - v, t - p))
            if p != self.page_no:
                self.page_no = p
                self.render(goto=p)
            self.cv.yview_moveto(within)
            self.update_page_label()
        elif args[0] == "scroll":
            amount, what = int(args[1]), args[2]
            if what == "pages":                   # 빈 곳 누르기 = 한 화면씩, 끝에 닿으면 다음/이전 쪽
                top, bot = self.cv.yview()
                if amount > 0 and bot >= 0.999:
                    self.go(1)
                    return
                if amount < 0 and top <= 0.001 and self.page_no > 0:
                    self.go(-1)
                    self.cv.yview_moveto(1.0)
                    return
            self.cv.yview(*args)

    def render(self, goto=None):
        """전체 다시 그리기. goto: 이 쪽으로 이동 / None: 지금 스크롤 위치 유지
        계산을 모두 끝낸 뒤에 화면을 지우고 바로 다시 그려서 번쩍임이 없게 함"""
        if not self.doc:
            self.cv.delete("all")
            self.imgs.clear()
            return
        yfrac, xfrac = self.cv.yview()[0], self.cv.xview()[0]
        self.page_no = min(self.page_no, len(self.doc) - 1)
        key = (id(self.doc), len(self.doc))
        if self._sizes_key != key:   # 쪽 크기는 파일이 바뀌거나 회전했을 때만 다시 계산
            self.sizes = page_sizes_fast(self.doc)
            self._sizes_key = key
        self._memo_pages = self.find_memo_pages() if self.memo_side.get() and self.cols() == 1 else set()
        self.zoom = self.calc_zoom()          # (화면 크기를 읽느라 화면이 한 번 갱신됨 → 지우기 전에)
        self.cv.delete("all")
        self.imgs.clear()
        self.items_cache.clear()
        self.words_cache.clear()
        self.annot_cache.clear()
        self.mats.clear()
        tw, th = self.layout()
        self.cv.configure(scrollregion=(0, 0, tw, th))
        for p, (x, y, w, h) in self.slots.items():
            self.cv.create_rectangle(x + 3, y + 3, x + w + 3, y + h + 3, fill=self.tcolor("shadow"), outline="",
                                     tags="bg")
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
        self.update_vscroll()
        self.update_visible()
        self.draw_selection()
        self._sync_page = True

    def refresh_pages(self, pages):
        """고친 쪽만 그림을 바꿔 끼움 (화면 전체를 지우지 않아 번쩍임 없음)"""
        if not self.doc:
            return
        new_memo = self.find_memo_pages() if self.memo_side.get() and self.cols() == 1 else set()
        if bool(new_memo) != bool(self._memo_pages):   # 메모 칸이 생기거나 없어지면 배치가 바뀜
            self.render()
            return
        self._memo_pages = new_memo
        for p in set(pages):
            for c in (self.items_cache, self.words_cache, self.annot_cache):
                c.pop(p, None)
            if p not in self.imgs or p not in self.slots:
                continue
            try:
                img = page_photo(self.doc[p], self.zoom)
            except Exception:
                continue
            self.cv.itemconfigure(f"img{p}", image=img)     # 같은 자리에서 그림만 교체
            self.imgs[p] = img
            self.cv.delete(f"memo{p}")
            if p in self._memo_pages:
                self.draw_memos(p)
            self.draw_links(p)
        self.cv.delete("hl")
        self.draw_selection()

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
                self.cv.delete(f"memo{p}")
                self.cv.delete(f"memolink{p}")
                del self.imgs[p]
        for p in want:
            if p in self.imgs:
                continue
            x, y, w, h = self.slots[p]
            try:
                page = self.doc[p]
                r = page.rect
                if p < len(self.sizes) and (abs(r.width - self.sizes[p][0]) > 0.5
                                            or abs(r.height - self.sizes[p][1]) > 0.5):
                    self.sizes[p] = (r.width, r.height)   # 빠르게 잰 크기가 틀렸으면 (드문 경우) 바로잡고 다시 배치
                    self.root.after_idle(self.render)
                img = page_photo(page, self.zoom)
            except Exception:
                continue
            self.imgs[p] = img
            self.cv.create_image(x, y, image=img, anchor="nw", tags=("page", f"img{p}"))
            if p in self._memo_pages:
                self.draw_memos(p)
            self.draw_links(p)
        for tag in ("tsel", "hl"):
            if self.cv.find_withtag(tag):
                self.cv.tag_raise(tag)
        self.place_wall()
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
                    lst.append((fitz.Rect(a.rect), a.type[0], a.info.get("content", ""), a.xref,
                                parse_anchor(a.info.get("subject", ""))))
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
        for rect, typ, content, _x, _a in self.annots_for(p):
            if pt in rect:
                found = (rect, typ, content, _x, _a)
        return found

    def on_root_resize(self, e=None):
        if e is not None and e.widget is not self.root:
            return
        if self._fit_job:
            self.root.after_cancel(self._fit_job)
        self._fit_job = self.root.after(120, self.fit_toolbar)

    def set_compact(self, on):
        """좁은 창: 버튼 글자를 숨기고 아이콘만 (이름은 말풍선으로)"""
        if on == self._compact:
            return
        self._compact = on
        for w in self.labeled:
            try:
                w.configure(compound="image" if on else "left")
            except tk.TclError:
                pass

    def fit_toolbar(self):
        """한 줄에 다 들어가게: ① 글자+아이콘 한 줄 → ② 아이콘만 한 줄 → ③ 도구 버튼을 둘째 줄로"""
        self._fit_job = None
        W = self.root.winfo_width()
        if W < 100:
            return

        def need():
            self.root.update_idletasks()
            try:
                in_bar = str(self.toolarea.pack_info().get("in")) == str(self.bar)
            except tk.TclError:
                in_bar = False
            others = self.bar.winfo_reqwidth() - (self.toolarea.winfo_reqwidth() if in_bar else 0)
            widest_opt = max((f.winfo_reqwidth() for f in self.opt.values()), default=0)
            return others + self.toolbtns.winfo_reqwidth() + widest_opt + 24, in_bar

        self.set_compact(False)
        n, in_bar = need()
        one_row = n <= W
        if not one_row:
            self.set_compact(True)
            n, in_bar = need()
            one_row = n <= W
            if not one_row:
                self.set_compact(False)      # 두 줄일 때는 자리가 넉넉하니 글자도 보이게
        if not one_row and in_bar:
            self.toolarea.pack_forget()
            self.bar2.pack(fill="x")
            self.toolarea.pack(in_=self.bar2, side="left")
        elif one_row and not in_bar:
            self.toolarea.pack_forget()
            self.bar2.pack_forget()
            self.toolarea.pack(in_=self.bar, side="left", padx=(6, 0))

    def pick_tool(self, tool):
        self.mode.set(tool)
        self.on_mode()

    def set_app_mode(self):
        m = self.app_mode.get()
        self.conf["prefs"]["app_mode"] = m
        self.cv.delete("hl")
        if self.toolbtns.winfo_manager() == "":
            self.toolbtns.pack(side="left")      # 도구 버튼은 뷰어·편집 모드 모두 표시
        if m == "view":
            if self.mode.get() in TOOL_LABEL:
                self._last_tool = self.mode.get()
            self.mode.set("")                    # 뷰어 모드에서는 눌린 도구 없음
            self.optbox.pack_forget()
            self.status.set("뷰어 모드: 끌어서 글자 선택 (Ctrl+C 복사 · Ctrl+B 북마크) · 휠 버튼으로 끌면 화면 이동 · "
                            "고치려면 [✎ 편집] (F4)")
        else:
            self.clear_selection()
            if self.mode.get() not in TOOL_LABEL:
                self.mode.set(self._last_tool)
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
        if m not in TOOL_LABEL:
            return
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
        if an and an[1] in (fitz.PDF_ANNOT_TEXT, fitz.PDF_ANNOT_FREE_TEXT) and an[2]:
            self.status.set("💬 " + an[2].replace("\n", " ")[:120])
        if (self.app_mode.get() == "edit" and mode in ("memo", "edit") and an
                and an[1] == fitz.PDF_ANNOT_FREE_TEXT):      # 본문 메모: 끌어서 옮기기 / 클릭해서 고치기
            x0, y0, x1, y1 = self.page_to_canvas_rect(p, an[0])
            self.cv.create_rectangle(x0 - 2, y0 - 2, x1 + 2, y1 + 2, outline="#f6a53f", width=2, dash=(4, 2),
                                     tags="hl")
            self.cv.configure(cursor="fleur")
            self.status.set("메모: 끌어서 옮기기 · 클릭해서 고치기 · 💬 " + (an[2] or "").replace("\n", " ")[:80])
            return
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
        self.memo_drag = None
        if p is not None and self.mode.get() in ("memo", "edit"):
            an = self.annot_at(p, self.canvas_to_page(p, cx, cy))
            if an and an[1] == fitz.PDF_ANNOT_FREE_TEXT:     # 본문 메모를 잡음
                self.memo_drag = [p, an[0], an[3], cx, cy, False, an[4]]
                self.press = None
                return
        self.press = (cx, cy, p) if p is not None else None
        self.dragging = False

    def constrain(self, x0, y0, x1, y1, e):
        """Shift: 정사각형·정삼각형 꼴 / 선은 45° 단위.  '원'은 항상 정원"""
        always = self.mode.get() == "shape" and self.shape_kind.get() == "원"
        if not always and not (getattr(e, "state", 0) & 0x1):
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
        if self.memo_drag:
            p, rect, xref, sx, sy, _, anchor = self.memo_drag
            cx, cy = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
            if abs(cx - sx) + abs(cy - sy) > 4:
                self.memo_drag[5] = True
                x0, y0, x1, y1 = self.page_to_canvas_rect(p, rect)
                dx, dy = self.memo_shift(p, x0, y0, x1, y1, cx - sx, cy - sy)
                self.cv.delete("sel")
                self.cv.create_rectangle(x0 + dx, y0 + dy, x1 + dx, y1 + dy, outline="#f6a53f", width=2,
                                         dash=(5, 3), fill="#fff6c8", stipple="gray50", tags="sel")
                if anchor is not None:      # 원래 위치와 연결선 미리 보기
                    self.draw_link_line(p, anchor, (x0 + dx, y0 + dy, x1 + dx, y1 + dy), tags="sel")
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
            elif kind in ("원", "타원"):
                self.cv.create_oval(x0, y0, x, y, outline=col, width=w, fill=fill, stipple=stip, tags="sel")
            elif kind == "삼각형":
                self.cv.create_polygon(*self.triangle_pts(x0, y0, x, y), outline=col, width=w, fill=fill,
                                       stipple=stip, tags="sel")
            else:
                self.cv.create_line(x0, y0, x, y, fill=col, width=w, tags="sel",
                                    arrow="last" if kind == "화살표" else "none",
                                    arrowshape=(4 * w + 6, 4 * w + 6, 1.5 * w + 2))

    def on_release(self, e):
        if self.panning:
            self.pan_end(e)
            return
        if self.memo_drag:
            p, rect, xref, sx, sy, moved, _anchor = self.memo_drag
            self.memo_drag = None
            self.cv.delete("sel")
            self.page_no = p
            if moved:
                cx, cy = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
                self.move_memo(p, xref, rect, cx - sx, cy - sy)
            else:
                self.memo_at(fitz.Point((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2))
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
            pts = None
            if self.shape_kind.get() == "삼각형":   # 화면에서 본 모양 그대로 (회전된 쪽도 꼭짓점이 위로)
                c = self.triangle_pts(x0, y0, x1, y1)
                pts = [self.canvas_to_page(p, c[i], c[i + 1]) for i in (0, 2, 4)]
            self.do_shape(self.canvas_to_page(p, x0, y0), self.canvas_to_page(p, x1, y1), pts)
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
            self.memo_at(pt, (x1, y1))
        elif mode == "erase":
            self.erase_at(pt)

    # ---------- 메모 오른쪽에 펼쳐 보기 ----------
    def find_memo_pages(self):
        out = set()
        doc = self.doc
        for i in range(len(doc)):
            try:       # 주석(/Annots)이 없는 쪽은 열어 보지 않음 → 큰 파일도 빨리 열림
                if doc.xref_get_key(doc.page_xref(i), "Annots")[0] == "null":
                    continue
            except Exception:
                pass
            page = doc[i]
            if any(True for _ in page.annots(types=[fitz.PDF_ANNOT_TEXT]) or []):
                out.add(i)
        return out

    def draw_memos(self, p):
        """p쪽 메모를 쪽 오른쪽 칸에 노란 쪽지로 표시 (메모 아이콘과 점선으로 연결)"""
        self.cv.delete(f"memo{p}")
        x, y, w, h = self.slots[p]
        notes = [(r, c) for r, t, c, _x, _a in self.annots_for(p) if t == fitz.PDF_ANNOT_TEXT]
        notes.sort(key=lambda n: (n[0].y0, n[0].x0))
        fam = self.theme.get("font_family") or "맑은 고딕"
        try:
            fs = max(8, int(self.theme.get("font_size") or 9))
        except (TypeError, ValueError):
            fs = 9
        bx = x + w + 14
        last = y
        for i, (r, content) in enumerate(notes):
            ix0, iy0, ix1, iy1 = self.page_to_canvas_rect(p, r)
            cx, cy = (ix0 + ix1) / 2, (iy0 + iy1) / 2
            top = max(iy0 - 4, last + 8)
            tag = (f"memo{p}", "memo", f"memo{p}_{i}")
            t = self.cv.create_text(bx + 10, top + 8, anchor="nw", width=MEMO_W - 44, tags=tag,
                                    text=(content or "(빈 메모)")[:600], fill="#3e2a00", font=(fam, fs))
            x0, y0, x1, y1 = self.cv.bbox(t)
            box = self.cv.create_rectangle(bx, top, bx + MEMO_W - 24, y1 + 8, fill="#fff8c4", outline="#f9a825",
                                           width=1, tags=tag)
            self.cv.create_rectangle(bx, top, bx + 4, y1 + 8, fill="#f6a53f", outline="", tags=tag)
            self.cv.tag_lower(box, t)
            self.cv.create_line(cx, cy, bx, top + 12, fill="#f9a825", dash=(3, 2), tags=tag)
            self.cv.tag_bind(f"memo{p}_{i}", "<Double-Button-1>",
                             lambda e, p=p, r=r: self.edit_memo_from_side(p, r))
            last = y1 + 8
        for tag in ("tsel", "hl"):
            if self.cv.find_withtag(tag):
                self.cv.tag_raise(tag)

    def edit_memo_from_side(self, p, r):
        self.page_no = p
        self.memo_at(fitz.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2))

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
            self.refresh_pages([p])
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
        m.add_command(label="북마크 추가", command=self.add_bookmark_now)
        m.add_command(label="즐겨찾기에 추가", accelerator="Ctrl+D", command=self.add_favorite_now)
        m.add_separator()
        m.add_command(label="이 쪽 왼쪽으로 회전", command=lambda: self.rotate_pages([self.page_no], -90))
        m.add_command(label="이 쪽 오른쪽으로 회전", command=lambda: self.rotate_pages([self.page_no], 90))
        m.add_command(label="전체 쪽 오른쪽으로 회전", command=lambda: self.rotate_all(90))
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
        dlg = Popup(self.root)
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
                self.refresh_pages([self.page_no])
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
            self.refresh_pages([self.page_no])
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
        dlg = Popup(self.root)
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

    @staticmethod
    def triangle_pts(x0, y0, x1, y1):
        """끈 영역 안의 이등변삼각형 (꼭짓점 위) → [x, y, x, y, x, y]"""
        l, r_, t, b = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
        return [(l + r_) / 2, t, l, b, r_, b]

    def do_shape(self, a, b, pts=None):
        kind = self.shape_kind.get()
        if kind in BOX_SHAPES:
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
                elif kind in ("원", "타원"):
                    an = page.add_circle_annot(r)
                elif kind == "삼각형":
                    if not pts:
                        pts = [fitz.Point((r.x0 + r.x1) / 2, r.y0), fitz.Point(r.x0, r.y1), fitz.Point(r.x1, r.y1)]
                    an = page.add_polygon_annot(pts)
                else:
                    an = page.add_line_annot(a, b)
                if kind in BOX_SHAPES and fill != "없음":
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
            self.refresh_pages([self.page_no])
            self.status.set(f"{kind}을(를) 그렸습니다. (지우개 도구로 지우기 / Ctrl+Z)")
        except Exception as ex:
            messagebox.showerror(APP, f"도형 그리기 실패:\n{ex}")

    def memo_dialog(self, initial="", existing=False):
        dlg = Popup(self.root)
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

    def memo_at(self, pt, cxy=None):
        """메모 만들기/고치기. 본문 글상자(기본) 또는 아이콘+쪽지"""
        p = self.page_no
        page = self.doc[p]
        hit = None
        with unrotated(page):
            for a in page.annots(types=[fitz.PDF_ANNOT_TEXT, fitz.PDF_ANNOT_FREE_TEXT]) or []:
                if pt in a.rect:
                    hit = (a.xref, a.type[0], a.info.get("content", ""), fitz.Rect(a.rect),
                           parse_anchor(a.info.get("subject", "")))
        res = self.memo_dialog(hit[2] if hit else "", existing=hit is not None)
        if not res:
            return
        action, text = res
        if action == "save" and not text.strip() and hit is None:
            return
        box = (hit[1] == fitz.PDF_ANNOT_FREE_TEXT) if hit else (self.memo_style.get() == "box")
        try:
            self.push_undo()
            page = self.doc[p]
            if hit and (action == "delete" or not text.strip()):
                with unrotated(page):
                    page.delete_annot(page.load_annot(hit[0]))
                msg = "메모를 지웠습니다."
            elif box:
                if hit:            # 고치기: 같은 자리(왼쪽 위 기준)에 새 크기로, 원래 위치 연결은 그대로
                    x0, y0, _, _ = self.page_to_canvas_rect(p, hit[3])
                    anchor = hit[4]
                    with unrotated(page):
                        page.delete_annot(page.load_annot(hit[0]))
                    self.create_memo_box(p, x0, y0, text, anchor, place_near=False)
                else:              # 새 메모: 누른 곳 = 원래 위치(표시 점), 상자는 그 옆에
                    if cxy is None:
                        x0, y0, _, _ = self.page_to_canvas_rect(p, fitz.Rect(pt, pt))
                    else:
                        x0, y0 = cxy
                    self.create_memo_box(p, x0, y0, text, fitz.Point(pt))
                msg = "메모를 붙였습니다. 상자를 끌어 옮겨도 원래 위치와 선으로 이어집니다. 클릭하면 고치기."
            else:
                with unrotated(page):
                    if hit:
                        a = page.load_annot(hit[0])
                        a.set_info(content=text)
                        a.update()
                    else:
                        a = page.add_text_annot(pt, text, icon="Comment")
                        a.set_info(title="메모", content=text)
                        a.set_colors(stroke=(1, 0.82, 0))
                        a.update()
                msg = "메모를 저장했습니다. 오른쪽 쪽지 또는 마우스를 올리면 내용이 보입니다."
            self.dirty = True
            self.refresh_pages([p])
            self.status.set(msg)
        except Exception as ex:
            messagebox.showerror(APP, f"메모 실패:\n{ex}")

    @staticmethod
    def memo_box_height(text, fs=MEMO_FS, width=MEMO_BOX_W):
        """글 길이로 상자 높이(pt) 어림"""
        per_line = max(6, int((width - 6) / (fs * 1.02)))
        n = 0
        for line in (text or " ").split("\n"):
            wide = sum(1.0 if ord(ch) > 0x2E80 else 0.55 for ch in line)    # 한글은 넓게, 영문·숫자는 좁게
            n += max(1, -(-int(wide) // per_line))
        return n * fs * 1.45 + 8

    def memo_shift(self, p, x0, y0, x1, y1, dx, dy):
        """메모 상자가 쪽 밖으로 나가지 않게 이동량 조정"""
        sx, sy, sw, sh = self.slots[p]
        dx = min(max(dx, sx - x0), sx + sw - x1)
        dy = min(max(dy, sy - y0), sy + sh - y1)
        return dx, dy

    def create_memo_box(self, p, cx, cy, text, anchor=None, place_near=True):
        """본문 메모 글상자 (회전된 쪽에서도 화면 기준으로 가로 상자)
        place_near=True: (cx, cy)=원래 위치 → 상자는 그 오른쪽 위에 (모자라면 왼쪽)
        anchor: 원래 위치(쪽 좌표) — 상자와 선으로 이어 표시"""
        page = self.doc[p]
        rot = page.rotation
        z = self.zoom
        w, h = MEMO_BOX_W * z, self.memo_box_height(text) * z
        sx, sy, sw, sh = self.slots[p]
        if place_near:
            gap = 26
            bx = cx + gap
            if bx + w > sx + sw:             # 오른쪽이 모자라면 왼쪽에
                bx = cx - gap - w
            cx, cy = bx, cy - h - gap / 2 if cy - h - gap / 2 >= sy else cy + gap / 2
        cx = min(max(cx, sx), sx + sw - w)
        cy = min(max(cy, sy), sy + sh - h)
        r = fitz.Rect(self.canvas_to_page(p, cx, cy), self.canvas_to_page(p, cx + w, cy + h)).normalize()
        with unrotated(page):
            an = page.add_freetext_annot(r, text, fontsize=MEMO_FS, text_color=MEMO_TEXT, fill_color=MEMO_FILL,
                                         rotate=rot)
            an.set_border(width=0.8)
            info = {"title": "메모"}
            if anchor is not None:
                info["subject"] = f"{ANCHOR_TAG}{anchor.x:.2f},{anchor.y:.2f}"
            an.set_info(**info)
            an.update()

    def draw_link_line(self, p, anchor, box, tags):
        """원래 위치(점) → 메모 상자 가장 가까운 테두리까지 점선"""
        ax0, ay0, _, _ = self.page_to_canvas_rect(p, fitz.Rect(anchor, anchor))
        x0, y0, x1, y1 = box
        ex, ey = min(max(ax0, x0), x1), min(max(ay0, y0), y1)
        if abs(ex - ax0) + abs(ey - ay0) > 3:
            self.cv.create_line(ax0, ay0, ex, ey, fill="#f6a53f", width=2, dash=(5, 3), tags=tags)
        r = 5
        self.cv.create_oval(ax0 - r, ay0 - r, ax0 + r, ay0 + r, fill="#f6a53f", outline="#ffffff", width=2,
                            tags=tags)

    def draw_links(self, p):
        """p쪽 본문 메모마다 원래 붙인 위치를 점으로 표시하고 상자와 이음"""
        self.cv.delete(f"memolink{p}")
        if p not in self.slots:
            return
        for rect, typ, content, xref, anchor in self.annots_for(p):
            if typ == fitz.PDF_ANNOT_FREE_TEXT and anchor is not None:
                self.draw_link_line(p, anchor, self.page_to_canvas_rect(p, rect), ("memolink", f"memolink{p}"))
        for tag in ("tsel", "hl"):
            if self.cv.find_withtag(tag):
                self.cv.tag_raise(tag)

    def move_memo(self, p, xref, rect, dx, dy):
        x0, y0, x1, y1 = self.page_to_canvas_rect(p, rect)
        dx, dy = self.memo_shift(p, x0, y0, x1, y1, dx, dy)
        if abs(dx) + abs(dy) < 1:
            return
        r = fitz.Rect(self.canvas_to_page(p, x0 + dx, y0 + dy), self.canvas_to_page(p, x1 + dx, y1 + dy)).normalize()
        try:
            self.push_undo()
            page = self.doc[p]
            with unrotated(page):
                an = page.load_annot(xref)
                an.set_rect(r)
                an.update()
            self.dirty = True
            self.refresh_pages([p])
            self.status.set("메모를 옮겼습니다. (Ctrl+Z 되돌리기)")
        except Exception as ex:
            messagebox.showerror(APP, f"메모 옮기기 실패:\n{ex}")

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
        self.refresh_pages([self.page_no])
        self.status.set("지웠습니다.")

    # ---------- 회전 · 쪽 골라 저장 ----------
    def rotate_all(self, delta):
        if self.doc:
            self.rotate_pages(list(range(len(self.doc))), delta)
            self.status.set(f"전체 {len(self.doc)}쪽을 회전했습니다. (Ctrl+Z 되돌리기)")

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
        dlg = Popup(self.root)
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
        dlg = Popup(self.root)
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
                self.refresh_pages(list(plan))
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


WALL_PRESETS = [
    ('하늘', '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wgARCAPoBkADASIAAhEBAxEB/8QAGQABAQEBAQEAAAAAAAAAAAAAAAECAwQG/8QAGAEBAQEBAQAAAAAAAAAAAAAAAAECAwX/2gAMAwEAAhADEAAAAftR6/kgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFBUsURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFBRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRGhloZaGWoRRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABRFRFEURoubRFEURRGhloRoZasuG6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lmpM2amZZczNjLOssprMlmoAAURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFploRURaRas01K3NZ1red41dTWd0ZFLFEWACWWQgRZZJZpmG2BtiG2FmmBqZlm85lamZc3LNlyWQliVUURQVEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURoRSxpEaGWqYbLlumLqyy61m521nTTWdKsqkoAAEWDOs2SWWSM2Ems2ZVpgm5mG5lWpkmplVkJZFiFRYiURRFEUFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFKVEtpm6suW7Li7Li7Rh0GLtLm6sudasudWyy1KVKAAAAlElWYmpZjO82YzrO8SM2WRZYlVCVABABYlEURRFEURQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKosLdSy3WdZu7Lluy4u0uLsYukuboZukS0pUoAAAAAACUTOpZjPTNnLPTG8c87zrOZZrIhYAUACAAAAAAAUSgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALKNNTTTWa1dZ1LbnUtsubRGhFSxQAKSgAAAAAAAlElGc7zZjHTG888dMaxiazrMWWAAAAAAAAAAAUAAAAAAAAqxRFEWmWkZaGWhloRRGhloZaGWoZahFVAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACyrrWdZut53jerNZ1auaKsUAAAAAAAAAAAAAAJYSazZnG86zzzvGs4zvO85WXIAAAAAAAAAAAQKRRFEWrFEtLGkRoZapi6LlqxhsYbGGxi6GWxi6q4bRidIYbWc24YalmZpWZomVEUkURYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWyrrWNS73z3je9Y1nW7jUtubLUFSgAAAKAAAACCFQVBYhUCJZM3Os5zrOs5zZrOVlkCAAAAAAAAAAaUsVLGhm0RoRqy5uqYurLltLi7GG7GGy4bGGxhunO7GGxltLhsYbHNtZznSHOdJZznTOs4m5ZmbhloZahFEmlmWhlRFgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAoXWbLvXPUvTXO510uLnW7hLtkbZRpC25GkFQUAABBYhZCVlVZGpJZpmGpmWWSWMprMllkllgAAAAAAAAAAHRq51hsZbLlqxi6q5urGbpLGrLlqy5aGWxloZaGWkZaGWhFq5aGWhloZm4Zm5ZiblmM9JZznSWc21nNsYbVzbJhuGG4Zm5ZlqEmpUUkURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEUoRdZG7iy7uLLu4su7zsu2KauEu2RtlG2S7ZGmbFZVWRZJZqZlmpkamVmmYaZlmpIWRYhZBUURSRRFEURRFEURRFEURR3u3LrhsZbRi6q4uhGrLm2yxRFpFEURRFEURSxRFRFEURRFVFJlRnO1nNuGG5ZhsYbJzbVzdIc3SWc50lYmyc5uWZalmVEVUURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFACxFsS6Zpq4G2Uurimrirq4sbYsu2KaZRpmVpmGpJZZJZWVlZFQWARYAlVFEURRFEURRFEURRFEURRFHsacO2bbLloRRFpFEVAKAAAAAAAAAAAAAABFWZahFEmhloZmxhpZidIYnSWc50lnOdM2c50zZiblmVlgAAAAAAAAAAAAAAAAAAAAAAAAAAAAACygALUFRGkGmbLpkaZGmRqSFRYgBZAAAAAAAAAAAAAAAAAAAe6xw70FEoAAAAAAAAAAAAAAAAAAAAAAAAAEURSZVWZuGJuWc89M6zzm86zmalmVWRRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEUAAqwVEUAhYUAlJFEURRFEURRFEURRFEURRFEURRFEURRFEUeu4vHttmmrmy0SgAAAAAAAAAAAAAAAAAAAAAAAAAAAJRM6lmJvGs4zvOs4mprMlVFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEUdri897ubLu41Lq5stEoAAAABRFEURRFEAAAAAAURRFEURRFEURRFEAAAiWTNzrMxrOszOpZJVkURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRq5surmy7uNZ1u41Lq5stRFCgAAAVBUFQWAAAIVKAALBUFQVLABBUVUFgACJYlIzYjNyzc6iFkFgAAAAAAAAAAAAAAABRFEVEWrloZaGWoRSRVRYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAUS2wa1iy7uLLu4su2Uu2UaZLpmlQaZpURUFQVARVZJWVauEbZGkLpmlRFQVBSFQVBUFSVUhqSWWSJYzZcpqJZZAAgAAAAAAAAAKKRRFEURaZaEURpLFploRpGWhhuVlqGWoSaWZUQAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAUoFSlubLpmy6uKaZstQW5GmRq5RtkumRpkVkVlZUiaZVpkaZsumRtlGrirpkaZGmRpkaZGpIakJWVWQlklWJZYWQEURRFEURRFEURRFEoFEqyxaZaEaGWrLhsZaGbpGWquWqZaRlqrhuGWhhuWYbhibWYmlmZqEmpZFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURQURRKALUsLBUFQVBbkauUumaVBUFkFkWVBYFQVBbkaRLpkaQVBUFQVBWRUFkWWAIBSUkURRFEURRFEURRFBSyrEtsubaZtsubaZasuLoZaphtGWixoRaZaRm0SaGWhlqVmbhhuWYm82Ym5ZhqWSalkURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURQVLFEURRFEUAAAAAVBUFQAAJRFEUAAAAVBUFQVBUAAACURRFEURRFEURRFEURRKpFpGkstsstsubpEaLFpm1EUsURoRRFEVBRFEURRJRFVmaGc7lmM7lzibzqZmlmVEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEUFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURQqylsstsstsstRKqxUS0RSxRFAAAAAAAAAAEUmZqVnO5ZjO5c4m86mVWRRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURQAAAAAAAAAAAAAAAAAAAAAAAAKRRFEURSxSRRFgAAAAAAAAKTU1LKsrS5qrLKqlSgAAAAAAAAAAAAAAAAJRmalmc7zc4m86mZqWQWAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFLFEURRFEURRFEURRFEURRFEURRFEURRFEURQLEUFEURpGWi5aGWhlVkURYRRFEUQABRFEoKFsudasstSy2xFCgFEURRFEURRFEURRFEURRFEURYAASWWSWWZllzJZqSVUURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFBURRFEURRFEURRFEURRFEURRFEURRFEURRKBQVKWxm2rloRbGWi5aGWomWhlpWGhlqEmlmVEURRFEURaRUqqLLKssqylEooAAAAAAAAAAAAAAgCFiIhYzZZIakFklEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFBRFEURRFEURRFEURRFEURRFEURRFEURRFEoKss0spbLFssURbGWhloZahFVloZahlomWpWWhloZaGWhloZtEURaRUSirKKSrKBAAAAAAAAAAUAIWAIIlliWEiWJSWWJVkURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEUAoAAAAAAAAAAAAAAAAAACywpLasqktssopFEVEURRFVFEUSURRJomWhloZtEURRFEURRFEoooEABRBUFQVBUFQVBUFgCFQWRYIIlliWIAlgAUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABRAAAAAAAAAAAAAAAAAAAADWbLq5stubGkLpLLUoEAAAAAAAAAAAAAAAAAAAAAIUQEJUVblGmRpkVBUVUBBUIRViBFiAFgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAC1KW5pbmy25sWyrbLKEAAAAAAAAAAAAAAAAAAAAAQlQlgllQVBUFQVBUFQWIVCWFIAgACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFLFEURRFEURRFEURRFEURRFEURRFEURRFEUSgKAUS2yy6EtEAoAAAAAAAAAAAAAAAAAAIllJcohZBUWIBUFQABQAAEABFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFFAAAAAAAAAAAAAAAAAAAAAAABRLbLLbLLRAKAAAAAAAAAAAAAAAAAAIglIliWWJYBYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABRKAAAAAAAAAAAAAAAAAAAAAAABbEWyrbEtSwACgAgAAAAKAAAAAACCFRRAhYgiWUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEUAVLLUGkS0AAAAhUFSgCwVBUFQVBUAABAQgUggVFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEUAAAAAAAAAAAAAAAAAAAAAAAAAAAtEAVBUFQVAAABUFQVBRAABFVBYAACWAWAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFSxRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFAAAAAAAAAAAAAAAAAAAAEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURQURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEUFSxRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAUQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEUUKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAVEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFAKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB/8QAHxAAAwADAQACAwAAAAAAAAAAAAERECBwUDCAkLDg/9oACAEBAAEFAv1rM0nOoQmJmEIQhCEIQms5PCYm8IQhCYhCYhMQmIQmIQhORwnyQnN5pCE+w69J8UQvSY+KoXosfE0IQvSfFELo6F0dC6Qhfd2EJrNJtPybPpD6Q/4WR//EAB8RAQEAAgMBAAMBAAAAAAAAABEAAWAQQFAwIHCQsP/aAAgBAwEBPwH+cpERERERERERERGnERERERERERERERERGlkREREREfQiI0rFiOxmzpOLHZzZ0nFjrs6Xix1WZnrERERER52J6TMz9yIiIiIiIiIiIiI8xmZ+LMzMz0SIiIiIiI/I4IiPNZmZmZmZmZmfIzsmbOx5s6fjpuo4+jwzMzrrMzM6YRERGvERER9s/rPHWz2jgiIiIjVSIiI5IiIiIiNPIiIjokREeU/RnpERHVIiOCPHZ/B9g/jgcERHB/knf//EAB0RAQEBAAMBAQEBAAAAAAAAABEAAUBQYDAQkLD/2gAIAQIBAT8B/kUzMzM+VZmZmZmZmZmZmZ8czMzMzMzMzMzMzMzPjGZmZmZmfozNm+K223eRlnidt5OWeJ23jkWeK23ikRx2ZmZmZnrd4hHAZmZmZmZmZmZmZnrSIj4ERERHBZmZmZmZn8ZmZmZmesIiIiIiIiIiIjp8s68iIiOvyz0eWeO23hEeR35kREREeOZmfqREeNZmZmfOMzMz7PLPR5ZzWZmZ8FnEZmZmZmZmZmZ8g/j+PCeqIiI+JERHBZmeMzMzM9SfhEdwz/HFnzTM/wCPr//EABQQAQAAAAAAAAAAAAAAAAAAAOD/2gAIAQEABj8CQ1H/xAAgEAEBAQABBQEBAQEAAAAAAAAAEQEQIEBQYHAwkLDA/9oACAEBAAE/If8AD8iIiIiIiIiJ8pnbRERPmERERERERERERERERERERERERPkUREREREREREREREThEThERERERET45EREREREREREToE4RP0ABEROERERE+LxERERE5JwiIiJ1gToE5JyToE6QiI3G4ifFczjMZiInJERERERE5IiIiIiIiIiIiIiIiNxuNxuNxrfieMxmMxmMIidAiIiIiIiIiIiIiJ0REREREREbjcbjcbjW/EsZjMZjMZiIiIiIiIiIiInbREbjcbjcbjW/EcxmMxhmMxERERE8JuNxuNxhuNb8PxnDDMZjMZnjNbya1vw/GMYYYzPG63k1rfh2M6QxnjN1rdbw1rfh+M5MZ4zdbrdbrda1vxDGcmMZ4iq3VbrdbrdbrW+JicxE6ZxOZ6vjOTGM8PW63W63W63W63W+LiIiIiIiIiIier4xnJjN8Lut1ut1ut1uq3V7ucRERERERERERERERERERERERE4nqeMZrNZrNZq+BrdbrdbrdbrdVV7qIiIiIiIiIiIiIiIiIiIiIiIiIiInqmMZrNZrNVV72qrdbrdbrd4vcxEREROgREThEThERE4RERERERERERG43EbiJ6jjGazWazVVVVVX9aqqqqqqqq3W63W6q95GYzERERERERERERERERERERERERERG43G43G43PU84zVVVVVVVVV4vFVVVVVVVVVVVut1ut73GYzGYzGYiIiIiIiIiIiIiIiIiIiIiIiIiI3G43G43G56nVVVVVVVVVVVVVVVVVVVVVVVVVXvcYxjMZiIiIicTpnc7jcbjcbjW+q1VVVVVVVVVVVVVVVVVVVVVXi99jGMYxnh9bjeGta31aqqqqqqqqqqqqqvTVVV8DjGMYxniNbw1rfXaqqqqqqvjsYxjGM8PrW8Na34rnGMZrNYzw+ta1rfjGazWazWMZ4Tdbrda1rfjOMYxjPBVW63W61rW/GsYxjO/qqqt1ut1vxOInM6MYxjGd1VVVVVVu8b8ezGMYxjOxqqqqqqqqqqqqvxqIiIzGYzGM7Sqqqqqqqqqqr8YiIiIiMxmMznP13neaqqqqqqqr8WiIiIiIiIiInZ61rW9FVfjURERERERERETidnrWt4345EREREREREROZ2e8a1rWt+N4zGYzERERERERETtta1rWt+NYxmMxmIicRERO81rWta3zkRERE9WxjMZjMZiIng9a1rW+eies4xjGeH1rWta3x8T9IiInq2MYxjGeG1rWta3xsRERE6YiIiIiInE9SxjGMYzw28a1rfBTqiIiIiIiIiIiIiIiIiIiIiepYxjPE61re6iJ1xERERERERERERERERERERERERERPwiejYxjOb3tXq3Wta3wcREREREREROIiIiInMRE4iIiIiInp+MYqqvFVVXsqq9FVVVV76IiIiIiIiIiIiIiIiIiIiIidcRERG4iIiIiIiIiIno9VV/Cr+d6aqqvg4iIiIiIiJxERE7qJxERERERERET0eqqqqqqqqrxVVVVV5qqqqqqqr4CIiIiIiIiJ4GIiIiIiIiIiIiIiem1V/Gr1Xw0RERERETw0REROIiIiIiIiJ6PVXoqqqqqqqr0XxMRETycREREREROJ6XVVVXirxVVV9oiJzG59Fic7jW/RIjW41vwGr6FrWtb9F1rW/AavOb6BrW878Ezz+ta34JnOed3jW/Bs5vm7zvwjN6L5e9G78KvTVVV7Gqqqqr296b46IiIiIiex3rq/tV/Wr4ScxOYiIiIiIiIiIiIiIiInttXz0RERE6J0RERERERE6Z8jnEREREREREREROInMRE6JxERET1yqqqvZVVVVVVVV8JOqIid9vx6cROIiJzO9nx+dERPok8TvO/Rdbxv0bW+6T9Z3GeP33WJ+MTuM8jvxfPI77xOIid3nyKdlET0LfcJ2M/CIiIiIiInymfpPp8/KIiJ/fjf545/y1n/2gAMAwEAAgADAAAAEAQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQfvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjscccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccQgggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggssssssssssssssssssssssssssssssssssssssssssssssssstv/cccdffssssssssssssssssssssssssssssssssssssssssssjTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTQRz/8pDDDANQWuBTTQfBlRFjwTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTfvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvtF6Ha+Dc97wqJa6NDHIK3I84FL+PvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABJdcSk3F1C89yO3J4Pr3qpZiz5boCpQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQWn9zCSa2Ts4QTYLocTjjmIZaj4lyB+CQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQc8888888888888888888888888888888888hXIKplWsgQQQUcxjiggggjjkwTWmlJ2s888888888888888888888888888888888zTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTXcN8shcss88888wwwwwwwwww9pfYi5ODTTTTTTTTTTTTTTTTTTTSQQQQQRTTTTTTTTccccccccccccccccccccccccccccccccccZ+9NRahzzzzzzzzzzzzzzwwm0guDP5RMcccccccccccf/AP8A/wD/APrIwAz0gAzL/HHHHHEMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMNbuMR4EpKcsMMMMM8888uMqhla80QPcYMMMMMMcpzClfqAwwwxSeDcEwHth9hWQcMMMwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwz+wOhRUqlbLPPP4Jb332WVWxweDSewwwwwwwwyevRhdSAb67+fIyfnCVMQwTfdcwwwIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIJNfcZjIEW7UIJ6XpnHGXbo0QeOyMIIIIIIIIeSOTf8AqtQuOOOXFitSyidWx1EEQsDC/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8AaLcw5jfvUnP2F4bzzkncKw6u/wD/AP8A/wD/AP8A/wD/AB4wKIlYnHX332zq5/8A/wD72pAjXg+1/wDzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzyxkOpUadCwzieSoMMeuRszzzzzzzzzzzzygQjv05Jv33330008/8A/wDzz1Sgi66FPAQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQUTwoEMEsEMBjzzz+wQQQQQQQQQQQQQU1ECJCtvfvvvv/wD/AP8A/wDvPWmvH7ERKMEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABxOe0r1X7777+0U3nHY7Z1WkKI7wADDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDzjAdtiCQ3h/DDb7GLpXWkamv1yndq9jDD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/ADc2Cb0Q8au6dgAAA2V6OpYrWYbY7LI1f/8A/wDHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHQa39qSdUY6KFXIAAABCnnrk5pT0GLqFHHHHHE00000000000000000000000000000000000000000000000000000000000001h1krFGaG6bcVIwwwwwwxg2KX50Z7yw00000000888888888888888888888888888888888888888888888888888888888888883AUE4q3EZ44iAAAAAAABBoYR64c88888888888MMMMMMc0gBzjLLLI8EEEfYA0MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMOw+p9MrAAAAAAAAAAAAAABTV27SUMMMMMMMMMMP/ALzz6HkWH5kKyy2vVoCWpmtYb6zz3/8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/APfNq+JoMIBBBAAAAABEIAUig9jLj/8A/wD/AP8A/wD/AP8A/wAX7K5VKGlaXsb77iB0LKKn7oV1bLb5nH/f/wC+++++++++++++++++++++++++++1jJFiG1HysANBxhNUbo6VmdqJi/wDvvvvvvvvvvifVC/ARWWjsRTTz/wArLDBYX10Kn4D0XZUdSkMMMMMMMMMMMMMMMMMMMMMMMMMMNJaU33Epm7RdUVs2n03pmaVbrmiIMMMMMMMMMMOJVOq1upTkHHHHHDDLLLLCGhmaToO2aHwr6HrDDDDDDDDDDDDDDDDDDDDDDDDDDDACXJo1amilpnOWYMGm7pK2NDDDDDDDDDDDDDBWrI7kHc445zzzzzzzzzzw46HUx7JK3ZGEXbK8444444444444444444444444444472kHQx5Vpb29al4H32w4444444444444446YUJzzzzzzzzzzzzzzzzzzzzzzww476v3Yo6ULnHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHEFCw4IZyhHHHHHHHHHHHHHHHHHHHHG5W3Tzzzzzzzzzzzzzzzzzzzzzzzzzzzx5yXnljDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD7Lm3TzzzzzDHHHDzzzzzzDHHHHHHHDzzg011JIIIIIIIIIIIIIIIIIIII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ERERERET04iIiIiIiJzms1ms1nERE7N1utcN4n4nGM4Z1VVVVVutN1v4eeMZjM4Z57qqvC+A003W7+IiIiMxmMxmM89brd8wN1V/DxPIGGYzE6Na1uqqqv4jMZjMYZ4giJ063GGt/GZjMZjMRETu3G43G+rERERERERET5GMYZjPS1vDe2IiIiIiInCdIBERERERERERERERERERERERERERGMYzfSrda1rURERERERERERhniCJ0gGmkRERE+DjNZrNZqqq83xqqqt1ut3uieAwzgiIiIiIiIiNxuN8QRET4GM1mqq8KqqqqrdVeSr3zxCJzERETznETxCckRPgVVXkqrwqq3VVVX0IicRE9GJxERE4bjcbjc+HVVVVVVfpxEbjcbjfj32azWe/rWt/AVms1nRETpiIiInlrW+rERPkZrGazVX06q+NVut1reIiIiIiIiIiIicRETiIiIiIiIiIiIiIiIiIiIiIiIiIzjGazVVVVVVVVVVVVVVVVVVW63Wtb1xERERERERERET49VVVVVVVVVVVVVVVVVVXtnEREREThPEJwiJ8i8VVVVVV8aqqqqqqq9sREREREREREREbjcbifNqr11VX0IjMZiIiIiIieMRG43G5+NzGYiIicxERERERONxuNxv2J0zqxmMROaqqqqqqqqq8a1vG+/EREREREREREREROIiIiIiInEREROMxnOcREREREREROda1reIiIiIiIiIiIiIiIiIiIietGYiIiIiIiIiIiIjM5xjPRrda362YxERERERERERERE5z0a3VVfr4xnTERERERERPO9NVVbq/DiIiIiIiIiIiIic4xfaqqqqqqq+cRERERERERERERERERERERPaz2N/GYz19bxVVV/C4z07zv1IiIiIiIiIiIiIiIicYzsqqq+N8YiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIie5VXmrzeiqv5Oqq+FVeaq/n4iJ9uIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIifxbERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERP71//xAAeEQEBAQACAwEBAQAAAAAAAAAAEQEQQCAwUGCAcP/aAAgBAgEBPxD+9Kqqqqqqqqqqqqqqqqqq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iIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiJ9NiIiIiJquoH+H+H+PQA+PTvi8Xj0349cGkRuJ+l5zEROsDw4eHWBhhnQ+ehu70/0003saabicRP0nETWYwzgzseHDxePHOj/Hp/wZ2M7Hi8GdvN4cng8HhyeDTXXe1va3sb2tdd7G9jTScbn6RzEZjKYYYY4445zMfDn8ej+DDDDDOxna8PVJI3tb2NNNN7Wu80003G43P0fOMzgzORxxxwwxxzteLx42t4vHmwxxzn+PqEE8eOuuuu9vUquGG5xufo/MY6AezwY52s7Xh0HxZxy8fRAM64EROsDXTTTXXs9Llhhufo7GYzGOqtccc9AOjk8Ef0jkiIiInE7JzO3ERERG4013qDVlhuNb9GiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiMzrKfwxxjpCIiIiIiIiIiepERERuNzrCiww3G4iIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiJ9GxmMMMdRQZiJ2RET14iInVERE6dzjWWWGOjbjc+jREREREREREREREREREREREREREREREREREREREREREREREZjGGWeQzwZiMxERERERERERPaROjevPDWoiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIifST+TDDH4Z4Yz4WqrdbvBri2021w34qIiIiIiIn1fGcM9Byxnwu8brdbvUBW2+G+8nZOydk7J2TsnZOydk7J2TsnZERE7J2TsnZOydk7IiIidk7J29WIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiInGegmzmYiIiIiIiIiIiIiIiIiInTuq3Wm8DeogWmm8xERERERERERERERERERERERETkidAiInCcInCInERERERET6NjOXTTbbTNZvR+fe1ut1ut9EAqGm63W+0iIiIiInZE7J2TsnZOydkROFKZyvDj4PDj4cNdKaRERE+n4zhptppvgzVVeir6lVVVVVV5rdbrd9ABV3gabrda32MROJ2ThHg8OkPB4PB4PB4PB4PBnaxxx8Xi8Xj0/4vF48NdddNNxpG4jc+m4zWm+qoMM1VXuq8VV6aqrzVVVVVVW63W+gARdNNN1uq3fZxmIwwzsZ6AH4dH8efHHHHHHHHx6P4vFrrrrrrppppuNzjc64iIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiJxjGmumgwwzCs1V4q+hV4qqqqqr3Vutw03qAButN1utbzEREREREREREZjDDDHHHHHOxhnDKU+g7xxxwxzt5/Hp/x59dddd5rvE003G4iIifSMZrTXSQ44YYYY5wZqqqqqqqryQj+0f2j+0f2n+2uumm9JQ003W63Vb7TMZjMZyDHHO1jnHnr/8A+xztZ0fHJHHXXXXTXeirDkNxuN6YiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIjOMZrTN4MMMMccMMM1/bDOReF5NNNNN6wGmmu9EDWt1ut1r88flERERERERERERGYzGOoEcccc5/jxv0v/ACzt9gAANNdd66oG43ERE+k5xms1hhhhjjnewxxxzqx8uTXXXXe9vV/rpprrppput1eL7bGMMMschhhhmOgThEROEREREREREREREREbjc6gKwy3ON/n6b+eM1ms1hhhhhhjhhm2OdX+uu7ab6LB10003Wm63W+5jOTLLDDDMZjMRE7J2RERERERERE9OIiNxuMcWWGWOTfp94qqrDDDDDDDOf5vNP8AfHXXTTeRVVegaabrdXi+7z0DGM/jjMZiIidk7J2TsnZOydk7IiIiInXERE43GtZZYZ5Nb9R/PN5rNZrN9QAG6qqqr3Xuqrq9O+7xnDTbTTTTNZxnGe93eNb/AD6BbW/VrzVVVXsvZey9l7Kqqvp/57/GcM1prkNNM1jPfXit1ut1tttvk1v1er1VVVeqqqqqqq/AZxms1m9IFpppjPb1VVe6qrdbrd6AtttcN/n9K4xjTTfRsZ6166qqqqqt1utN6AGmuTf0nmcZjGM6vYz1aqqqqvde691VVVutNNNN6AGm61vVERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERE1NVyROERmMMMsssMZxERE6t3iqqqvdVVeG9zTTTTTTeButN1rWo1ERP0NETtxERERGYzGZwYZYZ6TP46N/jo1utbrdbreg7/t5dYGuuummmm63W7zv6KiczUROydk4YYYZ0AMsMxnGdW87/LWtbrdbrTesbppvBppppput1vG/onMTiIjMRE5MMMMMMexyGYzGOM9LeGt47rdaab6IA003W6qt43f0VOIzGYwzgwwzoHHHHDDHDMZjM4z0ta3G9SN1ut1vc8nkqqqr3Veb+iozEZnZmMMMMM7WdrOPxePDDOxnaxwwzGGYjM9XcbjcYYY4a03V4qr2Xn/AD9IZjMYYYYY4YYYZ0fmGGGYzGGZxPYYbjDLDPJv8t3mqqr7KIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIzGYzGOgDDHHDOsBhhhETiIiIiIiIiJzrDDDLLDDcRqIiIiIiIiIiIiIiJ9/zGGOgDDDDMZ0BCYnZETmJ7Dc43GGGWWWGGt/n3ERERERERERERERERERERERE9ABEREREREREREREREREREREREREREREREREREREREREREREREREREREREZjMYY6YDDDDMREROyIiIntI1uMMMssMNxuIiIiIiIiIiIiIiInsIiIiIiIiJzO3ERNTeSampqcRE+n4xhhlhhmMxmJxE99rWOGWWWGPhIiduiIiJyRERERERHhyeDwREbiJxuJ9Lz+fRKZ/DPgtb6BTf5b8DERERE7InoAIiJ6gAI03G43ET6ZnSG2mmM1m+9qqqt1pu9Na1v8+6iIicIjMROGe6AAYANNNNNI3G4jcRERE+iYxnDTTTNZrNZqqq+1qqqqqt1ut1uttcmtb7oRERE4YZwYYZw51gPB4PB4cfF4dX/F49P72NNNNNNNIiIiJyRET57GMY0000zWawqqqqqr13svZe3TW6qqvJVbrdbvBprk1uNz28RERERGGGGGGGGGdCZyJ6IBE4eHDwTk000000003OyIiIiJxERET5vGMZrTTTDDDDNZ0gqqqqq9VVW6000qryaaa6abrdbrd41vvAeHJhhhhhjhnswAAEREROGmmmm8HTTTTeDw9IARERPms4xjNZrNZrDDDO5VVVVeTNVemq3Wm63W63W46Q3W63W63W63Wt433KOsDDDDDDMYYZyImInZOydkRERERE6ojcbjTTcaaab6QAaabjcRE43E+ZzjGazWawwwwwzrAYYVhnWA3W600003pBvBput1V+DP44YYYYYZiIiIiIiIiIiIiIiIiIiNxG4000003r/6bwaaa6bwaTURERERERERERERERERERERERERERERERERERERETeM4xms1ms1mqqqqqwwwqqqqqtNN1ut1urwq6qrxvnjeYiIiIiIiIiIiIiIiInpADDDMRERPYxEREROicRuNN6QTpDTTTTTTTTTcbjcT5vOKqqvddZwYVVYYYYZ3K6BXDTdbrdabrdVe6qq/DAiIiIidURERPZzonEROyIicm8jTTTTTTTcabjc435urzVVe6qq8MMM5F5LyaaabrdVeiqq/AxE4iInRE+AicxERE5iI3OzTTTcbjeBuNxuNzjfnqqr0VVVVVVVVVVVeKvw+c5zERE+GiIiIicxE4jcaabjc4MMNxuN+i1V5q9NVeKvxecZxny0RERuNxppjgww3ERERERERERERERERERERERERERERERERERERERERERERERERE5/D8Pw/D8Pw/zmIiIiIiIiIiIiIiIiIiIiIiIiIiIiMMM1WbxnzMRuNxisMMMNxrc+/ZrNZrNZrPnNxuNYYZYa1qIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIwwzWbwZrNZvzW8b/HRdby377ms1ms1mtM1jPV/xERER/nrf4iIiIiIiIiIj/OrWt6Q1vERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERWazWmazWmazeL6l6t32F9W9VVut1putNNa1vwkRERERERERE+mZrNZrTNZrDNZqqqqqqvqVVVe6qvdVX0aq+jVVW63Wm63Wm63jW+8iIiJ2TiInMREROYicRPpWazWbwZrNZrDNVVVVVVVV6aqqqqqqqqqqqr6dVVVVbrTdbrd4N1ut33MRE9GIiIiIiIiIiIidE+kYzWazWGazWarOCEcLi4zVVVVVVVVVz0AEM1VVVVVXuvde691VVVVVcabrdbrdabrdbrfdRE4nZERMROyIiJ6YARERET6TnGMjGazWazVVVVcVVZrC4vdVXuvDSt1VXFXFVVVm8IXF7r3VVVVXuvdc5N1W63W7jdbrda3jW+0iJwmJwhM/pOEIeDw6BHDDPTABppDTcRuYjcT6RnFZrNVms1VVVVVVmqqqqqrdVVV/jhVVVVVVVVVVVVVVVVVbrdbrdXjfaxERERFdQPBEThET1AAabjcbjcabjcajc+kZxOqqqr3VVVVVVVut1W73Xrq91VVVVVVVVVVVVVu87xPaxGYnCM4MM9IAK5M4JyROkIicNzs0000003G43E+k1emqqqqqvWBVVV66qqq+qABVVVXmr7WcRmMxhmMxEThnIiIiIiIiIiJzERERuNxuNxuNxhucb9CiIiIiIj8vy/P9eh+X59D8pz+X5fl+X5fn+uj8vz63+Py/PR+U1ERERERERERERERGYjDMYYRhh4cInCJ2REREROIiJ0xETiNxuNxpuNxuNxG4iIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIntqqqqqq+tVVVVVVVVVVfdTjMZjDMZjMYYYZiIiIidkREREREROuIjcRuI3G43G43G43P0pOIzGYzGYzGGYzGYzEREROyIiIiezjcbjcbjDcbjDcan6RzjMZjMZjMZjMRmcRET3+41uMMNxhucb+kM4xjMZjMZjMZnEZnwm41rDDca3PoERERERERERERERERERERERERERERERERE4TExM/pMRERMTP6TExCJ2RERERERERERmMxGYzGGYjMYzE+G1uNxhuNxuNxuflERERERERERERERERERERERERERERERERERERERERPjYjMRE5IiIiInJEREREREREREREZjGcMYzjGdERERERERERERERERERERETo1rW8N/njcbnz0REREREREREREREREREREREREREREREREREROydk7J2TsnZERERETmIiIiIicTjGP4c5xjOjPg9a1vDf56YiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIifFZxmcRmIiIiJwnQIiIidkRERERERERE4nGcM/lnGcZvwW7zW63W63W61rW/aM4ziMxhE7IiJ2TsnZOydk7IiIidAiJ2RERERE7J2RGYzOM4xnGM4z3153W63W63W603ed+fiIiIiIiIiIiIiIiIiIiIiIiIiIiMxNZjMYZjMRERE7IiInZEThERE1E5PB4PB4dYERGYicZxjOM97u87rW63W63W61reNqIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiJ8VmMYzGYzGYzE4RETmIiJwiIiIiIiIiIiInZOyIiInGYzOc99rd43W63W63VX7bjMYxmcZnMRE6IiIicxE4TUTsnZOydk1NTVdIRNTURE5zPcVV6N1W63W63W63eN3jd+hREREREREREREREREREREREREREREYxjGMZ1xERETpiInpRET0YnoVeaqqqqqqvRVVVVutbrdbrefxxERERERERERERERERERERERERERERERERERERERERERET4zGMZrNZq8ZvOelET3k6d3iqqqqqqqqqqqqqqq3VbrdbvN+25zjNYzWarNZvGexiIiIiIiIiIiInTE6d43V66q9FVVVVVVVut1vOz7hnGMZxjNYxn88Z8ZrWt5q+hVVe3NXnej8fdsZvFZrGc58VvG8NbvFVVVVVVVVXmqvH552/d7xm8YxjGM+K3nWtbxVVVVVVVXpqrz+fvF4zeMYxjGfFbrWta1vFVVVVVVVemqv06IiIiIiIiIiIiIiIiIiIiIiIiIiIiIicZxjGMYz4nd53WtbxvrxERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERETiMZ0M+G3o3jWpxERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERPk8YxjOL8FVXi8brW87+lM4zeM1mqvFVVVVXrqqqr1VVVV5q8Vu8brd537HERERERERERERERERERERERERERERERERETjN4rN5q9NVemqvrVV5rdXi87xERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERET5bOMZq+jVVVVemqqqqr01ur0bvN/TOc50Xv1/6vfqvfmqqqqqqrz/AL6O/p3/AD2tVVVVVVX0P8/UNX4Sqv8A33ERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERP+kYiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIn/pDERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERE/ZMRERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERET/xZiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIif8ASP8A/9k='),
    ('노을', '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wgARCAPoBkADASIAAhEBAxEB/8QAGgABAQADAQEAAAAAAAAAAAAAAAECAwQFBv/EABoBAQEBAQEBAQAAAAAAAAAAAAABAgMEBQb/2gAMAwEAAhADEAAAAfqVfD/VRRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAVSRRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAUIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAUkURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABQgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABVkURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFUkURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFUkURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFJFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURQUkURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFBRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURQCAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAUIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAUIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABRQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABSRRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFpFEURRFEURRFEUYsoRRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURQURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEogApFEURRFEURRFEURYAJRFEUsURRFEURRFEURRFEURRFEURRFEURRFEURRFBSRRFEURRFEURRFEURRFEURRFE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TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffQggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww8cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccfPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPMcccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccTDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQTDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDM8888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888wgggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggv8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/ADzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzwggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwzDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDMcccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccdeQQAAAAAANecccccccccccccccccccccccccMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMIRy0/vvvvvsxy08cMMMMMMMMMMMMMMMMMMMMMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAArji5igXfAAPLSRmhznigAAAAAAAAAAAAAAAAAAAM888888888888888888888888888888888888888888888888888888888884xg7VJcp/8ALL4vJuxUMZPPPPPPPPPPPPPPPPPPPPM4444444444444444444444444444444444444444444444444444444444r+/6GiZli9L/wDqXklaSZ4f/GOOOOOOOOOOOOOOOOOOPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPe0VT2UaehavCCfmRImg6roYuNPPPPPPPPPPPPPPPPPxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxLWbI+YkaMm7OwwOTaIuYEqMnqDxxxxxxxxxxxxxxxxxwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwlxkDpVvIWIK7HMMK3UMqM6hXTYxRwwwwwwwwwwwwwwwwCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCOTQUuAD1KFRqW/8A61qaNoAzHqIKzggggggggggggggggvfffffffffffffffffffffffffffffffffffffffffffffffffffffffTYIvIiQhOGq4gAAAEl5sQWvf/EkhXfffffffffffffffcsssssssssssssssssssssssssssssssssssssssssssssssssssssspiaGIkQgRR4DecMMMNTUGSUctUrlBWsssssssssssssssgQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQiugHL7OxYHbPPPPPPHJUGRyCzgJhggQQQQQQQQQQQQQQTjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjsUGY6AamIG3Pvv8A/wD/APvrJ0LEscMrcMRjjjjjjjjjjjjjjjzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzy/uwcUNheV3vv/wD/AP8A/wD/AP8Arq5Wc8sS93hjzzzzzzzzzzzzzzTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTcEWNp7EJr/owwwwwwww0/nmoHO8hpcDTTTTTTTTTTTTTTQgggggggggggggggggggggggggggggggggggggggggggggggggggggh22gPBIv31owwwwwwwwww06r+wjNBBpywgggggggggggggscccccccccccccccccccccccccccccccccccccccccccccccccccccYUBdy870/3gwQQwwwwwwwQ7v4/wDMfsmBnHHHHHHHHHHHHHHPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPN2KPcL4P34EEMMMMMMMMEFZ0PYrppK3PPPPPPPPPPPPPPPLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLKxloo7wD/wMEEEEEEEEEEPT0DDwaaVzLLLLLLLLLLLLLLL33333333333333333333333333333333333333333333333333333321wP775b9YMMMMMMMMMMMOr8r774Ox3333333333333330MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMN53RRVfosMMMMMMMMMMe7uqji24MMMMMMMMMMMMMMMMPDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDAHt5JVGj8MMMMMMMMMN9SEmK/cnDDDDDDDDDDDDDDDDAMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMNfJT9BEK3y0EEMMMMEF3x0KmTenKsMMMMMMMMMMMMMMMP3zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzDHnz79/0057y280MwIEF36b1QNZDHXzzzzzzzzzzzzzzzzy/+0gg8000000000000000000000000000000000000000000kNU+5/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wDvfOu96QEQuONNNNNNNNNNNNNNNNNN/wD/AP8A/wDz/LAgAwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwxg0XDP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/APjH6QAwwwwwwwwwwwwwwwwww/8A/wD/AP8A/wD/AP8A+57vjXDDDDDDDDDDDDDDDDDDDDDDDHrexz7/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AMc5y6wwwwwwwwwwwwww/wD/AP8A/wD/AP8A/wD/AP8A/wD/AN153PrjvLLLLLLLLLLb3HIy97//AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/APfNe0z8+yyyyyyy/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AK/zzzzzw83/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/tt+7vv/AP8A/wD/AL67v/bv/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP3T/PPPPP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8Avrda/wC++++++++++++++++++u/63+//AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AD7s9v8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8Arf4+777777777777777777777777777747/7P7//AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD77764/wC72/8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wDvb87/AO+++++++++++++++++++++++++++++++++++++Pe72//wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A++++++++++v+326//wD/AP8A/wD/AP8A/wD/ALbf67/777777777777777777777777777777777777777777777774/57fbr/8A/wD/AP8A/wD/AP8A7+27+++++++++++++++u+/8A/wD/AP8A/wD+777777777777777777777777777777777777777777777777777777777777777/AP8A/wD/APf+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++/8QAJhEBAQEAAQMEAgIDAQAAAAAAABEBEDFAQSAhMFBgYYCxUXCRkP/aAAgBAwEBPxD8kqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqv+yaqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqv8Laqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqv8Laqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqv8Laqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqv+yaqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqr66qqqqqqqqqqqqqqqqq/f1VVVVVVVVVX8Uqqqqqqqqqqqr21VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVeKqqqqqqqqqqq8VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVXiqqqq8KqrwqqqqvFVVVVVVVVVVVV+6vFVVVuqqqqqqs1ms1VVeL2VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVW63W63W63VVVVVVms1ms1ms1VVVVVVVVVVVVV+6vFbrdbrdbqqqqqqqs1ms1ms1eL+FXiq3W63W63VVVVVVVZrNZrNZrNXi9jVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV4qt1ut1ut1uqvrqs1ms1ms1mqvFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVXnW63W63W63V4vrvFZrNZrNZrNZzVVVVVVVVVX7i8brdbrdbrdb8uM1ms1ms1m8X8J1ut1rW+q/DjGMYzsqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqrxW63Wta1vF+G8YxjGMZq8VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVXmta1vY4xjGc1VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV9Gta1reN+POMYxjGM5qqqqqqqqq/cXnW8a358YxjGcX8J1rWtb82MYxjGdlVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVfTreN+fOMZ6aqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqvGta3jexxjGcVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV9Gta3jfmxjPRVVVVVVVVVVfvda358Yz8OvZZ672W5udcVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV0DGaGb+GebWY8mZdd3h/V/b9X9v1f23Txw/t1vj3W78G4dNxg8OrZvqz11VVVVVVVVVVeOpY0dPZp5Mfh1TPq+jY0/p/k1mLoGdn1TOEaeqPA145ubntvfdQxq6ezB1PDNye2qqqqqqqqqqqqqqqqqqqqqrPfo8M8rWLr7uhZ3u5m9XhmvprF093UCqqqqqqqqqqqq/Hh7Nx4Zj5MHT3dUzuMzd6OhGnrsY+uvBMx0Z9N0M19PZr5PBV1TO+6plavDfHuvAMfT3dS03Nzr8ea3pjoxm3h5OsPU8EzHRn2HUMNfiMBi6bjcvDcvJus65325m9W6dcevbbb9D/AIzDpnYRNVyQhCEIQjkpN77duuP0P+fYbbaarhCdnEcKTe/mcKTfoorhM7+OFJ30RwpO5m8ITPp5iOE3v4jkpN+WarhCZ9jMRwpNT5Im9kiYmJiYmJiYmffxMTExMTExM/8AF7//xAAlEQEBAQABAgcAAgMAAAAAAAARAAFBEDEgMEBQUWBhcKAhcYD/2gAIAQIBAT8Q/wCkCIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIj+1KREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREfZSIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiI88iIiIiIiIiIiIiIj+JDwEdSPrh1IiIjqdD6gdDqREREREREREdTofTDoRERERERHQiIiIiPpx0OhHUiIiOpHQ+nHgI8B5J5J6EiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIjyjyTyiIiIiIiIiIj3o8B6U9EREREREREREREREREREREREREREREREREREREecREecRERERERERHvB60j+VyIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIj2AiIiIiIiIj3k8k8k+t75OfXCIiIiOu/Tz1p/F54DzT6meI6HhOh4j0mf5913czvftbQ+L/SfigpSl0DpOeA8ZHo8y5sws+WWbWbm9tiIiIiIiIiIiIiIiIiIiIiIiIiIiItw77blb8MtrdufRu5OzVmebNuehEdSIiIiIiIiIiI8eZc2YWZ5s05l9i3Dm3PGW6drdb3312Yc2a5s072ac+uzdztZlZ88s072bdt9TuPNvFbvjLdubd3e/s2aztZhZnnLN7Nze3rs3c7WZ82VmOcs1s25u8REREREWmd7ceejvBluuMt35t3d7+4ZlzZjZ8ss5rPns25sNiIiIj0+aWZc37373737373737W63n37NZzftfvfvfvfvfv/RN//8QALxABAQEAAQIDBgcBAQEBAQEAABEBECExIFFhQVBxkdHxQGBwgaGx8DCQweGAsP/aAAgBAQABPxD9SIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIn6kxERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERP/ABZiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIn/izERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERE/8WYiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiJ/wCLMRERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERET9SYiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIn/izERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERP/wCkYiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiJ/4sxERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERP1JiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIif+LMRERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERE/UmIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiJ+gsRERERERERE96xEREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREfEiIiIiIiIiIiIiPiRERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERE8URERERERETxxERERERERERERERERERERERERERERERP0DicxE8cRE4ifpbPDE8MRET0RERPRERPDE8M91xERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERmYmIiJxERMTERERERERERMTEROYiI3MRERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERPDE4ROIiInCIiIiJwiIicROETwxERERERERERERERERERERERERET88REZmoicRERERN4REREROE1E9ERuI3E4iNzURP0dzwZnMRGYnEZicRERERERE4jcTiIjcTnc8G5+jeZ4cziMziMziMxERERERERERG4nG43ONznc8O57miIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiJzmIzEZiMxmYzGYzMZiM4JieiIiIiInomJjSNxuY3G43MbjcbiNzEbnMRERERERERERERERERERERERE/OkRGYjMREZjMZjMZiIzE3hEREREREThNbiNxuNxuNxuNxuI3EbiInuSIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIjOc4zjGYxmMxmMxmcZjMRmIiJ4YiIiNxuI3G41uNzjcbnG8bzqIiIiIiIiIiIiIiIiIiIiIifnPM4icYiIzGYzGYzGYjMZiIiImJ6IieiIiImNxuI3G43G43G4iI3nc43PccRERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERmIjOIjMZjMZjMZjMYZjMZiMMxERERERERuNI3G43G43G43G43G43ERvERuIiIiIiIiIiIiIiIiIiIiIifnaMxmMxmcZjMZjMZjMZjMZiIiJ44iIjcbjcbjcbjcbjcRuNxuNxE/RnGcYxjMZjMZjM4zGZxmMziInERE5icRucbjcRuNxuNxuNxreNbxvuOIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIic4iZxmIzGYzGYzGYzGYjMZjMTiIiIiIiInEbjcbiNxuNxuNxuNxuI3GpiNzmIiIiIiIiIiIiIiIiIiIiJ+cYmozOMxjMZjMZjMZjMZjGYzE4iJ/ziNziNxucbjcbjcbjcbjca3ONRNT9EM4znGIzOMxmMxmMzjMZnGYzPFERETxbjc43G5xuNxuNxucbjca3nf0QzOvgxmMzjM4zGYzOMxjMZnGYzPBP+cTmNzjcbjW41uNbnG5xuNxvg3Px8RERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERmInGYzOMxmMxmMxmMxmMxmcZjOZzEREREROZ4NxrcbjcbjcbjcbjcbjW4nERuIiIiIiIiIiIiIiIiIiIifm/PDjMYxmcYxmMZxnizP+u54t41rcbjWtzjW5+iuM78RjGcYxmMZnGM4z8HvG87xrW41vG8a3ONb2/Q+IzGYjGYxmMxjMYzOMxmcZnGZ+DnG5xuNzjca3GtxuNxuNxG4iJ+hsRGcZnTjM4zGMzjOM8E/C7ng1rWtxuNzjc43ONRET9C878Z35zsxjGMYxnGM4xn4fW87xvGtbxvG873439C88OMYzGcYxjGcZ44iIiIiIiInj3jWta3jW41vi38dERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERGcxGMxmcZjGMYxnOc4if94jed41reNa1ucbjcaic6iIiIiIiIiIiIiIiIiIifm7E8Od2M7s7M4zjOM4zjPwu+DeN43jWtb2bzvEb+hud+M4zvxnGMYxnOd+M/D7343jWtb2b3a1vGt539DcxGZ1TjMZjGYxjGMYzjOM/D7xvGtbxrWtajc4jcRP0LzjO/OduMZ2YzsxnGM4zjO34ne3O861rW+HeN/QvO/hxjGMZxnfjPBnf8Tvg3vxre7Wtb3a3txvO/joiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiJxicYzjGMYxnGeDPxO8bxvGta1reNbxG8RERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERETmMzqnGYxjGM4zwZ+J3jeN41rW8bnG43E53ERERERERERERERERERET84RnixnZndnGeDO/wCJ3wb341rW8b3bzqe4IiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiInhxjPBjOM8Gfid8G92tbxvGtbnG9+YiIiIiIiIiIiIiIiIiIifnCIzGZxmJzjOM5z8Vre3h1vMbnGoiN/RDOcZzjOMZxnGfh943jW8a3nW87+iOeDGeDGcYzwZ+H3jeNbxvO8b3b4N9wRERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERE8ERnGM4zjGc5+I1vOt43jW8dOJ4IiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiJxGcZn/HOM/C7xv/DW5xqcRERERERERERERERERERERET86ZxnhxnGbx05zfwe74d3jW87xs439Fc5znOM4zwZ+G3neN43jeN90RERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERGYiMzmMZxnOfht8Gt53jWpzqI3ERERERERERERERERERERERPzp/mP8A63WzueZj55kdxd36c/hxgz/hgxETu7S5EdNz1fhsZxcub01vcu6tnp0yP8fptPmbmXp3PzxmNGwTRbu+Xf8A63w7xPDvG+6MmZ5uXLjN+W9vzVk2wXd3ZmZ5uqv7F/WjdafPaLvzzM4wbMs8jpu3mb8IztS3q9+HXddFf2L+lW81nvo3N/b8Nm3CYYZmeXdp9zN29Ob+eN1r8bJFmZ69mvKidRPxtrVjfafJM/fdz+m1Nb3LurZ6dMjEbb21t39s3mr4d3wbrfBvMRPcuQxXtpNz9291N3J2vy2sTLM3q2ML6dM+T9mMr+cjZyxks0jp23d6fy2uZbN3LF8uiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiNzLW6Zjpe3d3N/fpz+DO5Nddz1fhma37Z66Zua3M+NZ3GzNvTm/nmY2Gq99Lu/v7k1uwZN1anl0ewWLX8eqMBsc9vu/Lcz+G7drMnees9ms8/Vp9bZVu7692NLkmXcWp59ON8G8TwRvhiIiIiIiIiIiIiIiIiIiIiIif8Nju7uTtflTOy7N6t1mF9OmfJ+zGV/ORv5YyWaR07bu9P5bnMtm7li+XT8q7uWN0zHS9u7ub+/Tn8GzM45t7z0vtzPT1Z3GSRbnx7mdzbbmbYvn194ewwOpr4xitPM9ux89zdScyMi63bfPe+fwl5jTq3eoeWTr/GJNvegYz1zvndt8HVGoie8tnu7uTtflTKy7N6t1mF9OmfJ+xCV/GyI2dWGdn0u9L8NZNsFzc25uef5LybYLu7szM83U19i/59UfsQlPytdnf361+PUyubbczbF8+vvrJ2puO463t2dzf26E+HQ2bnfMnees9mb6+rU6yyrd317sbXNsu5lqefRu++t7uWTd21PLoh5hoZT97k3d+Os2Zz3b2npfZm+nq7O/t1r/JEv70BGeud8/IfwYR183d39+lPj0P3ISv5SMnnZm3pzfzxjUaL30u7+/5DkQ5kNIZ6ZtzE3MzIut23z3vn8Nzatzq3G6T0678m7xczZ3vyjffkCHMhpDPTNuYg5lZF1u2+e98/hk532yMzqO97/wAOhr7Vfx6K3jbBc3NubnmiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiPgYhr4VkTrZKdvX2bvT+WNyY67nq/DKyNa3q9306tbW9+ZmG81kkmdPyZvdyybu2p5dEPMNDKfvcm7vx1smQuqq78Nkz99buWcFmkdO27vT+WlzLZu5Yvl0RERERERERERERERERERERE/FYjBe0G5+7V7mbt6c388brW7OdM3ur8drNzvtkZnUd73/h0dfar+PRWTbBc3Nubnn7v+DiGvhWZOtkp29fZu9P5YXJjruer8MrE1rer3fTq3G1vfmZhvTJJM6flbV7u7k7X5VjOy7N6t1mF9OmfJ+zCF/GyNnLOCzSOnbd3p/LW5ls3csXy6e+8ZgvbVm5++NfuZu3pzfzxutbsZ0ze6vx2v2IAv42RgtnvnmfLNz+WfcMxcuc35b1z3L8DANfCsqdbJTt6+zd6b82FyI67nq/DM1h61vV7vp1bjd3rzMw3pkkmdPzBr9/dydr8qx3VvboT4dDHjPa/dsb+25v9tjZtzqY3SenXfk1+fmbO9+Ub78xmC9tWbn741+/u5O1+VY7q3t0J8Ohjxntfu2N/bc3+2zaQ6M0zN+N6sVg7vtyPnuZjW5Zl3FqefRERERERERERERERG/dMxdmd35Z11j9TZVm569mPMgdBPwlrXrPY/dsZ+2Zn98HN27zMTZlvzzLjC5NtzVi+fX81a3Ysm6tTy6Oqp7Vfx6oxWxz2+78tzP4ZssodWRm78J0a3azpm8zPjsafXOXqs306t1n3ObqZcM+e5Mf6z/6ybYLhtzc80RERERERET3dm2CYYZmeXdp9zN29Ob+eN1p8bJFmZ69m/8AW5cuXLly5cuXLlz/AB+m/wAfpugt1Sv59FajYe+tm/tu+55/XO12KTY+m1/vp9sz6vtmfVnlnndj/H2P8fY/x9j/AB9j/H2P8fY/x9jJZct9szH2zPq3Jvxtz6P99P8AfTNcze554ZtyPPNv5B0uybd1Yvn0aff3cna/Ksf4/Tf4/TbU05k3W7vr02fmi5cuXLly5cubM2vLdjc83a30zTNnW769G+Sed2tMZm3nmP8AfD74UBut9u7+F3bseebGY7m9jz0/3wzHMynrua7g5nnlNyb8bc+izMp59P7UBmN9ub+j9AZjPbutyb+11/pstm2+y5jZnTb67Uyb8HPqt5tze+Xp7lzDMzMsztmaYa3OPLcM29bnp0b5e9vtzFmZTz6f2zc3M3Nzc3tufopQGYz27rcm/tdf6Zs63fXo32d7PbuJNynl0/pu7u7u7u7vfd930Bus9uazJn73X+2betz06N8ve325izMp59P7Zubmbm5ub23Pfkzpxns3GTOu302Nyb8bc+jukSzN6/kyTdr5df6Zs63fXo32d7PbuJNynl0/pu7u7u7u7vfd980Bus9uazJn73X+2betz06N8ve325izMp59P7Zubmbm5ub23PffsJSTeuM8ne32brdnS76dW5M/e6f2zc3M3Nzc3tufkKf1ztdjIuegzPqy65v6bu//ABMm/Bz6p/TO12/kPdux55sdxxmSYe1GdO+r1TOvW+zcX+md5t997t2PPNjuOMyTDLpm/rub/wDGRd9BufRsza8s2++sy7+3t/pYzHlbJmt8k87tSblPLp/X5N9hKSb1xi7ZPZ017WM9uXEnu+2Wb8vfkvMuZ2y9Fy78XPoy6Zv67m//ABkXfQbn0bM2vLNvvDMu/t7f6WMx5WyZrfJPO7VnKzN8skbt2PPdv5Vv9c7zYmdOM9m4yZ12+mxuTfjbn0Se77ZZvy9+S8y5nbL0XLvxc+jNTLjd9s//AA0xuZee43Jn73T+1/pnebfcmzNry3Y3PN2t9M0zZ1u+vRvknndqzlZm+WSN27Hnu38v3+ud5sTOnGezcZM67fTY3Jvxtz6LMynn0/tQGY325vvyMFnszTMczL6eeY7s88suNm9NnptXLvxc+ikyPrsZubmbm5ub23Pw0/rna7G5N/a6/wBNx3cp65mP8fY7M88tupk34OfVbzbm98vT815hmZmWZ2zNMNbnHluGbetz06Mxcusz2z/8PtmfVm+ZtZ6bpWC32Zj8NQGYz27r7Ybnm7W+maZs63fXo3yTzu1sXPQZn1bru73PLXuDJmV5Zsblz9/b/b/fD/fDMczKeu5r7Zv1fbN+r7Zv1fbN+r7Zv1fbN+r7Zv1fbN+r7Zv1fbN+r7Zv1TJvwc+r/fD/AHw++FAbrfbu/nndux55sffD74ZjmZfTzzH++Gxd9BufR9s36vtm/V9s36vtm/V9s36vtm/V9s36vtm/V9s36vtm/VpjM288x/vh98PvhP6Z2u3/APxaP//Z'),
    ('숲', '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wgARCAPoBkADASIAAhEBAxEB/8QAGgABAQEBAQEBAAAAAAAAAAAAAAECAwQFB//EABcBAQEBAQAAAAAAAAAAAAAAAAABAgP/2gAMAwEAAhADEAAAAf1FHDhUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBast1LLQtBAZmomJqWTWdFsstACgAAAkBmWWRFlQVBUFQVBUFQUsKq2yyrKoHBGsVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFudRdZ0urLNLEVBYEmpWc6zckqaubNUAAAAACWEzZcxBUVUFQVBUFQVBqzUWyzVQtQVBxF5gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAANSrrWdTVsLUFQVBYEzrLObFmrmy6SqAAAAIJcozc2AgAAAAACyl1nTWhKCgAcBeYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAChdTU1aLRKAAAllTOss5llmrjUauatsLUFQVAgjNyIlyAAAAAAAsprWbNasqgAAecXAAAAAAAAAAAAAAAAAAAAAAAAAAAABQUS0smhlYkWAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACyls1LdStUQAAAABnOs2ZllyuabuLLq5q1BUFSFkiWRYgAAAAAAALBrWNS7ua1pLAAHnRrFQVBUFQVBUFQVBUFQVBUFQUBRFEAIVBUFQVBUFQVBUFQWyirKqrKCUSaiZmspCVUFQVBUFQVBUFQVBUFQVKACFQVBUFQVBUFQVBUFQVBUFQVBUFQVBbnRrWdS6ss0AAAAAITOs2ZljMJWmaauLGmS7mRqSJqSVUFQVBUFQVBUFQVBUGrim9c9S7uKumatZHEOYAAAAAAAAAAACtLLauWqYbGJuGZqJlYAgAAAAAAFs0tqtAAAATO8pmaykCAAAAAAAAAKqy0RouWoZaiZWAIAAAAAAAAAAAAABbNLdTTVLKAAAAAlgzYmc7zZmaygIAAAAAAAAAAAAAAABbku7gbZLpkYDIAAAAAAAAAAFs0rSqpKURRJRM7hjO83OViAAAAAALKas01SygAAAQGc6zc5WIAAAAAAABbNKtqlssUsmiYm4Ym83OFiAAAAAAAAAAAAALKutTS2k1QAEFQVBUFQJYTOpZmajOZYAgAAAAAAAAAAAAAAAAFQVBAAAAAAAAAAAWyl1NNWyyrC1BUFQAmZrKYms2QIAAAABbmm9Y01qxLUFQVBUAhM6xZCMgAAAAAAWyrd52rUs0BUFgJRnO4nOazcyWIAAAAAAAAAAABbKu9Z1NauatQVAAAAAAgSWJJZZM6yiCAAAAAAAAAAAAAAAAAAAQAAAAAAAAACwas0utZ1NUKAAAAAzrKZzrNzmWIAAAABbmm9Y1NauatAAAAiEzc3MliAAAAAALBrWdLvWdTVCgAAASahjO8M5lzcgAAAAAAAAAAAW5p01z1NdGKukLbmlQVBURRQQllSWJCJM6zZJYgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAF3jS71nU0CgAAAAJYmc6ymZZcgAAAAAXWNLu5sukqgAEDNyjKXIAAAAAAAGt43LrWdNAoAAAAGcbwznOs3IAAAAAAAAAAAAFuabvOy7YG7iru4q7ZpUFQtSggzYiIklzZAgAAAAAAAAAAAAAAAAAAEAAAAAAAAAABd41LvWNNaAEAAAAM2VnNyzIWAAAAAALBu4su7irtimpIakiJCIUAAAAAAABrfPcvS501RKAAAAllZxrLOc2XIAAAAAAAAAAAAAACwW5G9c9S7uKukLUGkFiFgjNyM2MwUAAAAAAAAAAAAAAAAAAARJUFQVBUFQVBUFQVBUF1ir03y21u5stAAAASFyzZM3LJCVBUFQVBUFQVBUGmaumRpkVkVCVBUFQVBUFQVBUFQa1ir11z01u5s1UFQVBUCM2TLLKQlQlQVBUFQVBUFQVBUFQVBUFQVBUFQW5q7uKu2aumaVBUhUhcspYiVCVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVAQVBUFQVBUFQVBUFQVBUG9c9L01z01tmy1BSFQIylwzYiM1BUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFuab1z011vPUu0qgoAiTOsWZzrLMQlQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFuaurmmrirpkakhZCIiVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQQAAAAAAAAAAAFuaa1z0vS86u7hLtgamZZrMiXKJYAAAAAAAAAAAAAAAAAAAAAAAAFuab3z010ubLpC1BYEzqJjHTFzmWIAAAAAAAAAAAAAAAAAABUGkFQVAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALBbkbYppkuoEUklEAAAAAAAAAAAAAAAAAAAAAAAAABrWNrvWNTWkFQAJYZzvCZzrNyAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAgAAAAAAAAAAAACwts0LbLGquZsYnTJibzZlcoCAAAAAAAAAAAAAAAAAAAAAALC63jUu9Z01UFQVBYExrKZzc3IIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABBAAAAAAAAAAAAAFrStNtTSqKsUSUmJuHLPTLOJrKAgAAAAAAAAAAAAApFKUSahFJAAALBrWNL01z21pC0AhYhMawzIiAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAs0t3na61K1QoAACUmMdMpyzvLOQgAAAAAAAAAAAFNLLaZuquLoYbHOdImJqGViAAW5q71z0vS4q7ZGpIXLKMoiCAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEFQVBUFQVBUFQVBUFQVBUF1nS73jbWtQtQtQVBUFQMbynPG8M5IzUFQVBUFQVBUFQVBUFSiqt00s0qlKBFGZuJjPTKc5vKZIlQVBq4q7vOnRgu5mJqSFkJUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQAAAAAAAAAAAAAXWavTfPo1qyqCgAAAM3KYxvDOZYyAAAAAAAAAAs0XU21dTSgoAAAEmoYx0yzzmspAgACwVBUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAoKRSxoZUSaiRYAQAAAAAAAAAAAAFudG+nLbXTWa1QAAACDGsJnFyzIIAAAAAAAAABdTS63NNWyqAAAAAlGc7ynPPTCZUkuhmdIYm8kliAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAUoWrLQUsUSahJomJqElJkAAAAAAAAAAAACwb3z0vbXLbW0stQVBYCMjDFyyjKAAAAAAAAAAspreNrvWdtBKAAAAAAllZzuSYtqS225aHPPTKc5vDMlgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABSjU0qirEVFVBUFhEmpWZqJhDNQVBUFQVBUFQVBUFQVBUFSl1nS73z3NbuNNaZpUhYyXDDNwzc2QlQVBUFQVBUFQVBUFQW5q76c9r01jU1UW1BUFQVBUFQVEJRKCwVAzrKYx053OZcpUJUFQVKABAlVBUFQVBUFQVBUFQVBUFQVKApURRFlAhBUFQVBUFQVBUFQVBUFQUqqotqy2rFElEEAAKUUZmkecXAAAAAAAAAAAAQrStTS2yrbC6QVAzcpnOsJJYyFAAAAAAAAAALLGt89tddY01QoAAAAAAhZCaZpQoDNiZ57wziWMhQQqkaq5uquJ0hibiZmoQIFAAAAAAAACwNLLRGiyaGWoZm4mZqJABQAAAAAAACrDTTS2rLSyglEmoSWIKSqKKURR4w5gAAAAAAAAAALKXU0urK1QAAAJYZzvCZljMAAAAAAAAAAAsGt89L13y21u5q0KAAAAIM3KJmJ01y0dGatSFyykxcsyCAU0NNNTV0uWi5aGJ0ics9cpzm8pkIAAAAAAAoK0pSqAAAEUZzvKZWJAAAAAAAALKXU0t000C1BUFQWAlEUKpKKAB40OVQVBUFQVBUFQVBUFQVBbnRreNtaSqAAAABM6ymJcskFQVBUFQVBUFQVBUFQVBdYp03y012vPTW0FCgACJZIMMM3Mib1y0dbyL1mIbzmJcolQVKa3na3c00sqgoCUmc7hzx0wziWMkFQVBUFQVBSiqtsqrBUFQUAACWGc7ymViEFQVBUFQVBUFudG9Z21qytAAAAAAKFSgAAHiQ5VBUFQVBUFQVBUFQVBUF1mrveNNasqgAAAATOspjOsswiVBUFQVBUFQVBUFQVBUFQa1ir03x0va8tNdGKumaVkamYlzMoyyzYhbkauRqQWQVCVBdTS66Z23aLULUFQVBYJnHTCcs7wzCM1BUFQVBUq3WdFqqCgALKCgqxRFGc7iYz0ymJvKQBCVBUFQVBrWNLveNtasNVBUFQVBUFsFBUFQVBUHiDkAAAAAAAAAAAsq73z2urKtQtQVBUFiDNymc3LIIAAAAAAAAAAAABbkvS86dLzL1cy9JiJuZhZIlggAAAAAAF3ja9N423oKAAAABMbynPn05s5DIAAACyrqzS0KAKAKoKoAACUZmic5uJzmspAgAAAF1jS9N89tasLULUFQVBUqLKtAAAAB4Q5AAAAAAAAAAALEa3z1b01z01tmlQtQVAjKMsoiTIUAAAAAAAAAAAAAAsRUtVJLqQVFgAAAAAAAAGt89r13z23qyqEAAACDGsWYxrDMhMhQAAFssutZ1bUqggS0tLKqwVBUFQVBYEmomMdMpzmokCAAAW5svTfLdvS5rVAAAAsFSrUFAAAB4ROQAAAAAAAAAAAFuab1zq9bzq7ZLpkamYmszJZIlggAAAAAAAAAAAAACylKsaGWoSWEWIAAAAAAAAsGtYq9t8ejXS5rWkFQVBUFjIxcM5xcsoIAAAsGrmrvWatsFQWwtspUqggAAAACWLM6ymM7wzJYgAACwb1z0vXXLS9LitaQVBUFkhq8ydLjS25q1BUFQeJDlUFQVBUFQVBUFQVBUFQVBUFuaauKu2BtmG5mFSJUFQVBUFQVBUFQVBUFQVBUFQVBSitKtqxoZm4Ym4c5vLMIVBUFQVBUFQVBUFuab6ctL21y21u5LpC1BYiJMjDDLKM1BQAAAW5pvWNLQtSiyrbKAAAAAAAASWGMdMM4IlQVBUFQW5prXPS9NctL0vOrtgamYmpnJtgnXXLa9LjTWkFAB4UOdQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFSjU0XU01aKABM7ymM9MJhYhBUFQVBUFQVBUFQXWR03yq9tcdNdXOm2IbmcmsTLNyiACktplouWhlomaF1mrpKtSludFSqAAAAAAAAlhjG8M5liEFQVBUFQVBq5G2RtgupImpIW5G9c9HXXLTXW86vRirpkeNDlUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUq61jZvWNNaSgACITG8JnNiEJUFQVBUFQVBUFQVBq4q7vOnRzq7YhuZiakhQWyi2rLQCgRRlSQFuaaQurmmrmrUFQVBUFQVBUFQXNyZxrDMiJUJUFQVBUFQVBUFQVBUFQW5G7ir0vKr1vKnRzLyEwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAsGtY1b01jTWkoAAiEzcJIkgIAAAAAAAAAABUFQAAWzVrU0qirBUFQVABFiQhbkbuKu9c9GkqgAAAAACDNwkxcsoSAAAAAAAAAAAAAAVBbkaZEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABdYp01z010uLbpBUhcpEyjMggAAAAAAAAAAAAAACqXU0qqoKAAAAAlhJrKSXKW5HTXLS9Nc9W7Zq0AQAAFQhM6iYz0Sc50iYm4YaiQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAF1im9c6u2KumBZIiCAAAAAAAAAAAAAAAANSmtZ01QAoAAAAACWJnOspIJbkdNc9L01y01u4q6QVBUFShbWWqYbHOdYcs9sycJ1wzzWIAAAAAAAAAAAAAAQlQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFuS6ZGmRUFQlQVBUFQVBUFQVBUFQVBUFQVBUFQa1jS7udNVBUFQVBUFQVBUFgZzrKSIlQluS9Lzq9Nch1vKr0mBu89HTWNtWqqlAJRM6Rz59sJxx15sZIlQlQVBUFQVBUFQVBUFQVBUEQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQa3jS7udNAAAAAAAACEzrCSIlQlQVBpku2Btmm98+q76Y23bLaAAABM6kcuXfkzyzrLBCVBUFQVBUFQVBUFQVBUFQQQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAsGtYtvS5q6uatQVBUFQVBUFQIgxcsyCBAAAAFubb068uzXTWdN0AAAACWGOfXkzyxvmxBIAAAAAAAAAAABEFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBSktq5bGJuGViEFQVBUFQVBUFQVBUFQXWKdNc9W7uatQVBUFQVBUFQIyMsyEJUFQUoUsmoLB168et121jTdAAAAAlhnnvkzz57xMRCVBUFQVBUFQVBUFQVBUFQRBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFs0XToudb1dc3UvHPfCcc9cTPOayhBUFQVBUFQVBUFQVBbmm7ir01z0u2bVRLUFQVBUWWSQyyiIhBUFspdTarauc9Icmspvpx6L33y6XekqgAAAIyTlrkxnFxMEosoWkUuWomVgQVBUFQVBUFQEJUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQUKWmWhlYCFQlQVBUFQVBUFQVBUFQVKut56LrpOl20qxSzO4nLn35s8MdeUzkiVCVBUFQVBUFQVBUFQW5q7vPR0vPS7ZLpBqQVIakyazIlzIlQVCVBdZq9N421uy2s6zGMbwzN86ejp5+t12vPbVuatQVASFw5szlecyyjNs0NNKaq5aGJ0yc50wmZYhCVBUFQVBUEQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVKWzStXS5u6uJ1hyz2ynKbymZYhBUFQVBUFQVBUFQVBdZ0dOvLq313jd3QAATn0wceXbjMYzYwQVBUFQVBUFQVBUFQVBq4prXOr0vMdLzL0cxuZibmBZCWQVBUFQauadOnHbXW89LqTI53KS50m+nLa9tctNdbytvVzLtiJvOMGucxM3EjNSprWejV1NLQoCUZx0wnPO8MyIlQVBUFQVAAlEAAAAAAAAAAAAAAAAAAABbKa3OjV201LSxRnPSJxx2wnHPTmzIIAAAAAAAABdY0de3Ds323z3d0AAEzcJz5dOMxnNyyAAAAAAAAAURRAVBbkaZGmRpkVAAAAAAsG9c6dNci9JiGpBrU6K3dLhrKmMp1cR2zyJ0xiJrMiWBdZ0b3jo1qytAAAM6ymMdOaYlyyAAAAB0dDXOdcpynTCZEAAAAAAAAAC0Wxm6VmbhlrJFkAAAXeOldOmOjetQ1UFQWBMdMJx59ebPOWTIAAAAAAAADWR168Olvo6cOjfVmtVBUyXneTOeWubEhIAAAAAAArVS60uHSnJ1i8p1ynNqJkQAAAAAAAAAAsFQVBdY2devLrd9LNNZx05py575MpJM6kFQAAXWNnTfPpdbSqCgAJcpnGsJiJMgAAAAe26XpjPXJx59+TPLOszJCVBUFQVBUFQVKqqNXVsuquWxhsc89cnKdMpiazIQlSrrpy629unLo1tI1WYmmRtims3Jjl05M4zczNQlQVBUFQVBUFQVBULrfOnfp5ul16defTXZyHTOMG+UwyyzM1BUJUFQVBUFSrbNjd3dTWtLlsuZsc89YcMd8M8c9MTOSFQlQVBUFQVBUFQVBUFQVBdY0vbr5ut16LxrXTnMJOdwykSVCUqy2mW6Y1ba6Z0urKtQtQWIlyyTncMyJJUJUFQVBUH0xe0liY5deScsaxMQIAAAAABbNF3NtXS3SqSipRJqJjPTKcsdcSc5rLKwb6ctr36cul3qSKkiaYJu4q7mYOWucznNjIAAAAAAAAACwa1zp1vGr2cS9c4iamSWAAAAAAA1nZrpnq1ek3dqKAAlGcdMpx5ejkzxzvEzAgAAAAAAAAAACwb1yq9rxHXOIazCAWtLN3a51vVvO9C83WGLoRSyWIkFkylzMSMspYIAAAAB9Jheu8zI5XlMzFywQVBUFQVBUFSmt56Lred3VsLUFQVBUCUY59cScsdMM5Ca6c+i9d51d3NwIklQW5GszKMMpEJUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQa6Y6L06463erK0sFQVBUCUY5dubPDl25TGCJUFQVBUFQVBUFQVBUFQVBUFQVBUF1Nrek6q23dy0AoAEmomcdMGMa5zLMyzrMiWQVBUFQVBUFQexxNdc84axMpZCVCVBUFQVBUFudLvrz6Nb1LdVBUFQVBUFQMbxJz59eTOUqb68uzXTS3WM7wZJM1BYgzcEzcskJUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFSrvry6r26c+l6aCgAAAATG8Jx49uUxziM1CVBUFQVBUFQVBUFQVBUFQVBUFudrrpnq1rpN3aqoAAACUZzvKcuPo4zPHO8MxCVCVBUFQVBUFQVgu2BqRJUFQVBUFQVBUGtY1b16curW9Zt1UFQVBUFQVAzrMY5dOTGUJ17+fu121nV3nn1wnOakmVJJYZxrCTKJUSVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBbmnTrx63Xfpy63erDVQVBUFQVBMb5pz49OMxnNzMVBUoUQBBUFQVBUFQVBUFQVBUGt4629O3Pq3rebdVC1BUFQVBUFgY5dubPDl25TGIkzUFQVBUFQVBUEAAAAAAAAABdY0devHpddbmtUAAAAADNyY575M5RM9O3n63Xq6efq3vOlvPPXMnOdMpjG+aYxcTKCAAAAAAAAAAAAAAAAAAAAAAALBvrx2vp6+ftd9LnV0CgAACJOeuUmOWubEyTKylrSy6W4z0xJmWIAAAAAAAAAspvry63Xbrz6N6st0AAAAAABOfTCcePbjMcpczAAAAAAAEQlQVBUFQVBUFQVBUF1ir16cOi99c93ekoAAAAIMXmmeeucySJvfKnp6+Xpd+rXm212nMaxMI5ucyyjJCVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQa3zq9+3l63Xp3w6N9GatFAEFzMSON5MzDMwQlsq73ja7F1nG8JiXMyQlQVBUFQVBUFQVBbmr07cOzXfry6Xe0t0AAAAAABM6xJy49uDHPNzMEJUFQVBUFQVBAAAAAAAAAALBrfPS9unDbXe89XWkFQVBUCTKObnIyyzYIsG9cqvbXCr3cR1xiGsyJYIAAAAAAAAAAAAAAAAAAAAAAAAAsG98qvp6eXo16defd12vKr0c4dM4wm8Ywl5zMzZDIFuab3y012cy6wyjKMgAAAAAAAALB07cOrXp6cet6dEqgAAAAACDGuac+PTjMYzcsggAAAAAEQVBUFQVBUFQVBUFQVBbmm98dL3359td7x1b1cx0cxvOMxvGcs3EiWQlQVBUFuRpkakFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFShaSaGVguRvXOr21wq+i+enecYvbPKJvOYlkJUFQVBq4ptgupCEFQVBUFQVBUFQVBUFQb68dr6e3m7XfbXPbdRVQVBUFQVBUkTnrkzjjrlMSIzUFQVBUFQVBUBEVBUFQVBUFQVBUFQVBUFuRu86dbyW9rxq9ZyJ0ziG8ySVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFs0XTd1mdIcp0wmCSVBUGmRpkakFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQXWKd+3l63Xq6efrd9LjTVQVBUFQVIXLmjjeMxOdzMkJUFQVBUFQVBUEQVBUFQVBUFQVBUFQVBUFQVBbkaZGmRqSgpLaZaGZqEAQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFSmt89r06c+ltli4575pnNkyQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFuRvfLR6O3k6XXr1593fdz0urimpBWYamMJrnnlM3nMzKIlQVBUFQVBUFQVBAgAAAAAAAAAAAAAAALa2TW+lvO9tNcHoHlz6sHmz35zPJrKQIAAAAAAAAAAAAAAAAAAAAAAAAAsGtc9L16cNL2nNbebMiIgIAAAAAAAAAAAAAAAAAAAAAAABULvXKno35t2+rXl016b56vonAds8cp1xzymsZkzZACAAAAAAAAQAAAAAAAAAAAAAAAFs2t6zvdOt6N5urblRjPSHDj6uUz5efo4zHOWMgAAAAAAAAAAAAAAAAAAAAAAAAALBq4LtgakIAAAAAAAAAAAAAAAAAAAAAAAAAAAsFuRu8y9byHVyHSYhuZJYAAAAAAAAAAERFQVBUFQVBUFQVBUFQVBUFQVBUprrz729e/PvemqXdzMpqYzJ0cx0whz4engzwx05zERJUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQRCVBUFQVBUFQVBUFQVBUFQVBUF1mr19Hn9N137cut62XFTDElmYmrgm7guuW+acuXTlMSJJUJUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUBBUFQVBUFQVBUFQVBUFQVBUFQXWNL29Hm9F16uvHrejGuZnFyhCVBUQ565pjlvmzETNQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBUFQVBAAAAAAAAAAAAAAANB09Jd+nqXpOYYwMhIAgZ5icuZM5CAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAf/8QAIRABAQEAAwADAQEBAQEAAAAAAQARMEBQIGBwEAKgkMD/2gAIAQEAAQUC/wDvXD9Yf+lk/wCOJ/OToP5uR0H84Og/nBzs/nB+rv8A7w79W23/AKIn9IZ/OSOZn83IjmZ/NyI5mZ/NiOgz+bEc7M/mxEczM/c8sss+gERzMz+bkczP3AiOBn3SOVmfuBHCz6hHCRyM/Us7xEcLM+6RxrP3EiOFmfo222/UDieyRHCzP0Lbbbbbbfp5HEz2CI4WZ9sj57bbbb1X2iI4mZ65EcLM+2R8GeY7WWWeWRyM9gjhZ62WWWWeCRHwZnlORnos+QRyM9kYbfjss+6R8Ge09JnyCORntbbbbbbbb1DyiG222We09JmfHI5Ge3tttttvTIjkZ7+2228WfzLPAZnwGfkRyM+mRysz5OWWeGzPROg/Ij3yI5mfGI8bZnpHQZ+JHvkc7M+IRHMz1Ntttl6RHRfgRHvERzsz4ZEdBnp7bb1COiz/AEiPeIjnZnwyI6DM+QR0Wf6RHvERzsz4REdJmfHI6LP9Ij3iI52Z8IiOkzPjkdFn+kRxPqkRzMz4RHTZnxyOiz8CI+bM+qRHKzPhER02Z8cjoM/Ehht+TPrERHIzPhER02ZnxzoM/IYbbbbbbZfYIYeNlnwyI6bM+QRzvBttttttvtDDDbwbLL4hEdNmfXeTbfd222222222223xiI6TM/ge2222222+QRHSZnzNttt/u222/UNtttt8kiOizM+btttttttv38iOgzPo7b+BEMPOyz96I+L6xDDyrLL97I+DPrkMNtvBtssvtZZZZZZZ7p8H2dhttttttttttlt9oLLLLLLLJJ9zbbfc222222222232SCCCz45JJP3vbbbbbbfaIIIOBmSfzov8xxMzP5wX+b/MfHfkzP5wX+Y5Wfzgv8x/WeFn84L/ADH9Z4Wfzgv8x/XiZ/OC/wA3+f68TP4x/8QAHxEAAgIDAQEAAwAAAAAAAAAAAREAQCAwUGBwEICg/9oACAEDAQE/Af4LX/HiP04cfn36Bxx1D9AH0px/D3H+ji+hDQfODQfODQe0oouQewIOIMzyFQGR4jj7IyPCcceo5qK4dgyOtRUh+TWNQZna444496oCOOubZ3vWMzQeKiionqi2KTjqjgCDQaQ0ngDgCDQaQ0mG6fwIL4gzMNEQajwAY47wzNIQajwXHHecccccdMQajWeL47jjjqjSYfNDSfOAx5O6ooou8444447oEWBHgHeEGR86NB84PSCDyf8A/8QAFBEBAAAAAAAAAAAAAAAAAAAAwP/aAAgBAgEBPwFE5//EABQQAQAAAAAAAAAAAAAAAAAAAOD/2gAIAQEABj8CQ1H/xAAdEAEBAQADAQEBAQAAAAAAAAABABEQMEAgUGBw/9oACAEBAAE/If8ADiPtnyvlP8UOt8j5D/FTrfg8DPjP8TI7Xk8DPhI/xQjsZ5PA+Ij/ABQjsZ8TPiI/xMiOxmeD8Ij/ABIiO1mfAz4yP8SIjtZ8L5CI/wAQIjuZ+t6d85H+IER3Mz97bbbbb6j/ABAjwM/j7bzv4eeo/jSI8DPTttvu2222325ZZ8ZZ5Tg62fTlllln4ZEeJ4fx9tttt9RwHU8PhI7Hh8hxln1lnD7yPI/wxHYz4SO1nyEdTPuIjzP8GRHYzPgI7WfGR1sz7SI/mCI7mfAR2s+IiOxmfYRHnf4EiO5me8jtZ8JEdrM+wiPO/wAAREdzM+A7XxER3Mz7Bhttttt8T/AERHczM9xHYz4iI7mZ9o22222229j8P8AREdzM+E6nh8REdzM+7bbbbbbeN7398iI7mZ8W287ztts+MiO5mffvO22w2/e9D/AER3Mz4tttttttttt8hEdrMz+PvYz/AAJEdzM+XbbbfQRHYzP452v8ERHcz+iRHYzP6b/CEMPYss/pDDHUzM/k7b97/EDD07LL+oQwx1Mz+btv8YNttvxtssv6xDEdLM/m7bb/ABe2222222222/rkR0sz/d7bbbbbb+0RHUzP+B5Z+sRHUzP+AZZZZZZJ+oRHUzP98Fllllllkkz+kRHUzP8AeEFln1kkk/pkdTM/3ZER0PCT+kRHQzP92REdbM/gZZZZZZ2jDb9bLL/dkRHYzM+0LLLLLLLLLOwYbbbbbZZf7wiI7GZn1kFln3lkkk9W2222222/3hER2MzM+kgg60mSerbeNt/vjgR2sz6SI7WZn/CyI7ng+giI7mZ/wsiO5mfQRHezM/4WRHYzM+ciI8DM8ZZZZZZ/ggww9iyyz5yI8LM8ZZzkkz/gREMdSyyz6CI8T0sz/RvvIiOhZZZ9JEetmf5DOMs8Oe0iI6Flll9REetmZ/j8s8ee0jg+Nt5Zn1kR496GZnqznP3zgP0SI62fWcD1sz05ZZZZZZZZ+2RB+iRHYz6yIjw7bb9sz9hBBZZZZZZZJJ+0RH6JEdjM+sYYY7mWW22G2222WWWfoiCPtkkn8N8pEfokRHYzPrIYY7lllthhhtttlll+iII6WSSfwnh8REfpER2szPrIYYexZZZ52222237IiOtmZ/CfGRH6REdzM+wYYYbfvbZZZZfrbbegiI7GZnuPIz4SI/SI7mZ9wwww2222222yyyy+EiO14M9pHne8iP0iI7mffsNttttttttstvhI4Hazwe09CcPaRH6ZHazP4O22222222+M5DtZ4PYRHoSZ7CI/TIjsWfxNttttt8hHA7WeD2EelmewiI/TIjqWZ/dI4Ha8j2HrZnsIj9Qi3oWWf3zgR2MzPYR62ewiI/U222222222X8bLLLPQQw9rKZ7T1sz2EMNvRtttsP4+2222222222/hh9J6Bhh61llnuPWzPaMMNttttttttttsMP5O2222/iEdDPmIYYelZZZe4j1sz3bDbbbbbbbbbbbDDDH8cRHQzPmIYYbbeNttlllmfAepmZ79ttttttt+CGGG3+NIjoZnz7DDbbbbbbLLbb+WzM+HbbbfsYYYbbbbbf4ciI6GZnz7bbbbw222238xmfbsNtttv8SERHSzPq2222389mfftttttv8AEEdTM/iH5DMz+Dtv8SREdDMz+GR49ttht8LMz/WEQ9CzP4h5thhh8DM8Z/WEPG/G8LM/hER4n52GGPBlllllln9UMNttttstv4hHjZn4GGGHuyyyyyySST+q22222238UjyM/Oww229uc5ZJJJJP+JkeRn7G22222223k6ckkhJP+JEeRno22222222IiOphCf8AEiPIz1bbbbbHIdbPI/4gR5GZnp237B2PI/4iR42Z7jyAP+IER4mZ7jkO55H/ABAiPEzPcch2vwn+xyyyyyz1jD4WWevPg8gD/XkEHwGJJ6x8S9QWWWSeIPwH+uIIILLLLJJJJ9JDHcyz0ERBZZJPBKUdjKU/eWWWf0hwEIPlJIcH0bDDbxtv1tvGyy29BERyzPClDD1LKUpfkssssssn+iOQ+3kfRttttttttttttttttttvQchyzNsMpQw9CyylLbyRFnzkzP7wQWWcMskk9J8A+34D6ttttttttttttt6yIYt4ZnglKGG222222WXgUs8kRH2zP7oQQQWWWWSSSeg60/CfZttttttttvcMMNtsss8ERENttttv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DCWUsAAAADCcXDDDDDDDDDDDD0J/SgQw4DIAKfXXDDDDDDDDDDDDDDDDDDAAAAAAAAAAACyL777777+oEAAAABDjfrPOpI0AAAAAABAOnzzzzyhdEAAAAAAAAAAABDEt/LYkETiRI+SAAAAAAAAAAAAAAAAAAAAAAAAAAAAABCLzX/8A/wD/ANmsgAAAAADQLItcPsAAAAAAABStHb7775DtkAAAAAAAAAAAAADCCWq/b5DRtZOAAAAAAAAAAAAAAAAAAAAMMMMMMMMMMO6qPPPPO8nOsMMMMMMNNpOO6MMMMMMMMMMdX777762soMMMMMMMMMMMMMMMMPoJgjGSZZIMMMMMMMMMMMMMMMMMMMM888888888899+hr/frdzc88888888888888888888888tp/P76/WM888888888888888888/rOoBbvc88888888888888888888//AP8A/wD/AP8A/wD/AP8A/wAukGar319//wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A+Rf/APS7Vf8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD99POO/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AMssssssssssssooWfFKWesssssssssssssssssssssssssmDjz/APeZXLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLHHHHHHHHHHHHHGSkd98YwTHHHHHHHHHHHHHHHHHHHHHHGSbI001tpXHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHPPPPPPPPPPPPPdJq8iA+rrbPPPPPPPPPPPPPPv4JbvvPOdspTPcLe7PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP/AP8A/wD/AP8A/wD/AP8A/wD/AKGEc888JT7/AP8A/wD/AP8A/wD/AP8A/wD/AGh+r68zt/8A9rrINff/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD+JSXzzzyxD7f/AP8A/wD/AP8A/wD/AP72CtQN41Bj/wD/AMo8JeJ//wD/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E6ysENNNNNNNNNNNcW4ryDhGkNNNNNNNNNN4b7WzT2GaesNNmWRCT2ZrqOKuB+eqveP2mKNNNNNN88888888888888888888884EG+XzJR8888888888hGIxxxQ2Z88888888888JoFmO1I5c888Ru7jSoDT9AhEyMRa/CCSWtd88888MY4wwwwwwwwwwww04wwwwwF8C2+z6EYwwwwwwwwwp6g3/wC7ZxcMMMMMMMPMMPAIFfQIMMMMMMAZbZHK/iim3dcIe+sssl4JcMMMMHBYesssssssssuEoVRNsssvX5jjno6Ossssssssspkc0vph/esssssstqAEdPKOssssssssssokguxG47Ekgssm2V/vvt6Ksssssr8gGv8A/wD/AP8A/wD620cVpUoW/wCuCxp839zHv/8A/wD/AP8A/wD/APomAO9GJvv/AP8A/wD+i9G1zyvS/v8A/wD/AP8A/wD/AP8A/wD/AOiFvYHv8osyIcQglQCNv/8A/wD/AAuwDssMMMMMgxhKYkgZUtYxwCMDcPQ8cMMMMMMMMMIY2/l6UMMMMMMOw6gkokj0DssMMMMMMMMMMMTh72dkpgRVTWGWMZ9kMMMMMPUDgTDDDDDHc2TTTTTefkADVBFjrnyLTDDDDDDDDDDDHfbTDDDDDDDIUCrjjjukX7DDDDDDDDDDDDDPfTPCyAzjjt0EtwTTDDDDDM+tCAQQQQQXJNDDDDDDFxSDtYIw1xAQQQQQQQQQQQQQQQQQQQQQQQUAVMsssssqGiAQQQQQQQQQQQQQQSFsOAAAAEJVqAAQQQQQQfLEwwwwwwwxGIAAAAAAMjTCJXSu+8HAwwwwwwwwwwwwwwwwwwwwwww0eYAAAAANDFwz8yywwwwwwwwwx+R7TDDDDDDPSSwwwwwww8sssssssssu5V888888+pK8B8d8wfussssssssssssssssssssssspp2+cMMMIfqGokpF/8ssssssssshB+MMMMMMMECL8ssssssvfffffffffbH8O88888xdxD0Dm8pgvffffffffffffffffffffffffZ7fjwQSS3L/cN1PJvfffffffffvpyAAAAAAAJoAvffffffccccccccccYcdwBTzyaTpEcTPs0kEccccccccccccccccccccccccccVW/Ypl6HgcQfhumcccccccccdd1gwwwwwwx76wMccccccTTTTTTTTTTTefOuBSXs3DTTXbTXTTTTTTTTTTTTTTTTTTTTTTTTScWYbcEg1joPTTXaXMbTTTTTTTTTXYcajTTTTTTuTpTTTTTTTQgggggggggggg31aGXV4wgggggggggggggggggggggggggggggg9/PYaw8160wwgggggwgggggggggggtzYevvPPphB0gwggggggjjjjjjjjjjjjjnrnrmuoy3yjjjjjjjjjjjjjjjjjjjjjjjjjjjmgsc3Gzjjjjjjjjjjjjjjjjjjjjjjjju5VGK0/wC2frY44444447PPPPPPPPPPPPPPPPZNFaPQ+LvPPPPPPPPPPPPPPPPPPPPPPPPONq/h4LPPPPPPPPPPPPPPPPPPPPPPPPNJ9kzJp/j+rPPPPPPPPPDDDDDDDDDDDDDDDEDmJ0mB+9nDDDDDDDDDDDDDDDDDDDDDDDDDDETzHHDDDDDDDDDDDDDDDDDDDDDDDDDCGHzOuYFHDDDDDDDDDAIIIIIIIIIIIIIIJbstB3fddQAoIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIL/AP8A/wD/AP8A/wD/AP8A/wD/AP8A5q/sejLdEDHv/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wAMMMMMMMMMMMMMMMpeO8gABJZysMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMP777777777777776OAL90MIMF7/wC+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++/8QAHBEBAQEAAwEBAQAAAAAAAAAAAQARECAwQFBg/9oACAEDAQE/EP4Yjo8Hi+RH8Sdng7s+JH8SR2eDuz4n8UEdngbey+R+Hlln4hHG2228PGw287Lb5DHx5Z6hZxkkn4R1zlnnbbbbfMhttttttttttttttt5yyyyznbbbbbeCOrPG222222285ZZZzttttttttttttvBHgzztttttttttttttttttttvqQdUnxOzM+JBBZZJJ8BHgzPx7bb6EHdJ8Du+JB2ST2I8WZn8AiO74HZnxI7vsQw22+L+AR3Z8Bh6rL4kd2fbbeGw2229GfwCO7PiNtttsvkR2Zn4Nthht423hn8Ah7rPltttvmQ9mWfjHnbeF/CGG3ostv0jDbbbwz8m222222/hbDDbbbLb9Www9Gfm2238XbbbfuI6s/vBBZZZJP0kdWf3Qgg6JJ8OWWdiG3jeFn90I7JPvlllllnUYbbZZf3SOMssssmfUILLLLLJJOu222/vEcbbbbwz6hEdkn9LLLPhIY7LL6EeDJZZZZ+YWdM+EYeqyz6EeKWWWSSflBZ2yT3I43hZZfYeeWTP0Z8AQQWdcsstttttttttttt4IOdtll422222222223gY4yyyyzneNtmZt5yyyznbbbbbbbeuWWdNttttttt5CDxyz2O77DD4LbDbbLLyQWWWWSSeQfEQfQR3Z9hh7LLLDyL0CDqkk+AWd8k8SPLbbfUjuz7DDDbbbLMXnbehHdnueSSWdyPqGOzPwD0G2+JHd8BHmknYiPpGHqsv3kd2exHbbbbbeGTuMfUMNttsvxZZ6ku6z2O+WWWWWcM9iHrtsPybbbbb8JZZZJPmMNvOyy29iPVnuMNttstsMP45HG8vmMMcG2y285ZZZwerPhttttvAww22/iEdX0222223nLOcs9mfLeo2/jBHV+MPHYfJn4Ntt/EGG3jZZfiPF42GHwbLLP1dhtttt+EjyeNhht7ZZZMT9XbbfjI8meNhhtthjskn8SR5M9Ntt4HcT/EEeT3OB4H9nLLPUjxZ65ZHA8D+uQRwMT1GHtvC9SyzgYezKecss/Cyz3ELOMkk9Rh67Lb0IiZhlD02WXBBZZZJ95BwyST0OB0eD6bbbbbbbb1IbZZeCG222YxeAg6JP2kEFllkknmSi222eD77bb4DbbbBBxvIzeCOrwfAT0yyzsR1fUobeNll5ZyJZ7nAnhvUjs98sh5hBZZJJ1HG22+wYhwMfEEEFllkxPdRGL0yyyOqy+R8CCDqknJFstttsp9Nt4bb4EIOqQn23htvARDgyzh42WXvssp8CONttt4SeCJ43hZfpId0n4iEHGWcsstviYtvciO7PInoz+CPB+AhB3YT47b4kR3Z5ElnDP4Q8H4CHiPkER3eSlwlky/Upd1LkLJPmHg/GMPdZeB4DgWWX6hlDbzsspeCOGflHg/GMMPVZZeRjkb9gxDkMYvQbZfRSttttttttng/IMQbbZZm/i7HKZvbfUZQ99lL5ttttt/DCyT61D3WU/RtvOWWfcRw/WPATbbbZZi/WEQ4WJ9ow2y/YMQ5jWLb9RwEzjOBPt237dttt4bbb9YhwttvAn+dEstttsv8AODiTPRZf56Z6M/xn/8QAHhEBAQACAgMBAQAAAAAAAAAAEQABEDBgIEBQcID/2gAIAQIBAT8Q6S6d588WOqZ4M8GOHPTSI1j089KfLHrMz0fMzM6x2THgREcxETMzMzMzMzOmZmZmZmZnTt8GZmZmZmZmZmZmZmZmZmZnkZmZmZmZmZmZn0GZnbOnhfF42Z0zp5mzyPQs9Lxz44c7IiNY9M+zn93f66Z0+6z0Mj9kZ+Y+bpmZmZmZmZ5GZmZmZn0GZmZmZmZmZmZmZmZmZmZmZmZmZmZ/HGetMzM/bZmZmZmZnjZmZmZmZ8WZmeJ4mZmZnjZmZmZ5n+Y2Zn+O2ZmZmf1t6S/xcz+dkRER04/kp7Pj52PUdPwnoL8J9Zn72fceFnbMzM8uOBmZmZmZmZmZmZmZnWODNnTMzMzMzMzM6xyMzMzP43ix0RmZ7Ez77MzM+Ty4sfEewszPQzyz1xmZ06fdI0e+z7zMzM9gfgYsbZ1nruLHlnruLG2ev4sdT//EACQQAQEBAAEEAwEAAwEBAAAAAAARARAgMEBhITFQcUFRYHCB/9oACAEBAAE/EP8AwzGcmM51vJvOMYzt70N+/CxjDGcZzVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVWMYZjOM53jW4w1jPtjPpiqqqqqqrxvDW6qqqqqqqqqqxjDMZ8c1V/8ADMYwxnXuNxhr4Zwz6728m+BjGGM/8QzkzGM69a1jjH07+8m/ffzhhn/iWcmMXFVVVXw3k1jTN+O9u8N3wM5M7FVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVWcmM+uzrXDdZrNZq9ut1ppuqqqqqqqqqqs5M3/xHGGOGM7Ovpw0zdaZqs3s7rdbrdbrfAzkxn/h+MMMMzjOxrfrpGazWazVXprdbrdaa8PTTGf8L/8AHy+f9c7/AMJjGOGF7d5N35bqs1ms1WaqqrdVut1put3wc1pppmqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqs5jMREbjcRvFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVnDHgjW/fGazWGazVX2vtVbrTdbrdVVVVVVVVVVVWazWmmb+JERPSIni4zGYzGYzEREbjcbjcb/wABjOGPCDWs1ms1m8M6Qbrdbrdb4WMZrTNZqqqr5fzxERERE8XGMxmMxOnW43Gtb43ynviInE9vn8HGcmd3W8mt4qquqq+1XV9q3fFzWazWGFXhV8zMZiInCI3Ea3wcYzGGZ0X0/wDnO43G43G+LnGYiIiNzjfwMYZ77W/XDDca3mqvQKvkVms1ms84GYzGYwwwiI003G43G54GcMxhnZ1hhv34mYzGYzGdAabjcbjc87OGGGM7utaw3GPxc1d84GMMzgzE5/8AvEbjcYbnDe/nDDOzvLeG+FjDMYYRERGmm4w3zcYZZjO/rWsNxrfxKqr7VfIxmMMMzmJxE43G4ww1vdz7Z99Bna3k368HGYwwzGYnRG43GGG43y84YYYzpqqqqqqrWt+mt4a38mqqqqqqqqqqqqqqsYwxyxcVVVXxxrDHDVVVVVVVVWazeTGKqqqqrW8Ps3W6qqqqqqqqqsYwwzGcROInGsMMNaqqqqqqqqqqqqqqqqrN6FjPro3t61rWtjWt1VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVWcMcM7et4Za1VVVVVVVYzmzta3h9m8VVVVVVVVXjGGGGM4qqq8a1j4YYaqqqqqqqqqqqqqqqqrOTXFVVXs3jWta1vDWqqqqqqqqqqqqqqqqqqqqqqqqqq+NjH25M7m9A3uYzW+GKqqqqqt1rXDdb3s5cMZ2t4YfdrfJzWmmmbxVVVXs61vGt4a38iqqqqqqqqqqqqqrOkKqqqqqqqt6BqqqqqqqqrNZrTNZ2d1utN1uqqqqqqqqqrOhYzta3oWqqqqqqqqqqqqqqqqs1m8hhnQFXmqqrzrWt1rd4bvw1VVVVVVVVVVVVVVVVVVVVVVVVVXxs/CQM1ppms1VVVVW63Wmm6vfzeh5xVVVVVXjejb5WazeDDORhhhmqqqqqqtaa1rTfpu/u59+KC3vZrNaZrNXprdabrTfAzoefXc19+bfLzWazoDDDDNYXFxVXFVW63eNa3hv5FVVVVVVVVVVVVVWb8tNNcM7m8NtN1VVVVVVVVWazWawwq7wuq00003V1VVVVVVVVVVm8Nts1na1utt8N1VVVVVVVVVVVVVVVVVVdXeFVmmGcDCr7X2vtWbwrdbqt1ut1r5bqqqqqqqqqqqqqqqqqqqqqqqqqqvj5rTbTN7e63Wmmm9/NZrDDOgNNNNN3ws+2m22fTO1rTbbTfv8LNZrNZrC9FVV43W6003f38aaaYzs7xuttcN8Gs1m9A03VXxM+222u1vGm22/iYzWmazeKvRW63W601v7+NNNs1m9nW63Wmm+HV6avi4020zWdnd+Gmmm/jZrNZrNVVVVbrdabrfyqqqqqqqqqqqqqqqrNa5DNZqqqqrdbrd5DTdVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVms3ktM1m9etNttfLdVVVVVVVVVVVVVVVVVVVVVVVVZqs1hhmqqq3Wm63W63VVVVVVVVVVVVVVVVVVVVVVVVVVVXyMZrN5DNVVVVVp7ODdbv6Oa1yGmazenda3m+zfv8fNZrNZq++S+1brdbv8AwmazWbwYYYVVxpvIN1ur+lmtcGmmazeKrd43hlhv5GazVXoFbrd/4bNZrDDOD+n9Iaaaabv6ua022xVXneWGG/lVVVV/PqqqqqqqqqqqqqqqqqquMMM6Qbrd43iqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqrN5dM1VVV53oG6qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq+dVXWbr5TU1FNIn6edCxnVv0366Hv/d4zGYzGGcnTeBuNz9HOH24YqqqqreH34b/3WMZnBhnQGm8DDGt/QzWmmmb2N1pttu/87VVVVVVVVVVVVVVVVVVWMxjgwwzE4iN5BhuNVVVVVVVVVVVVVVVVVVVVVdfL5fL5fKqqqqqrNY20zWazp3W603w3VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVXzMZjLDDHERETjDc4stxvmxmIiIiI3E68Y000zWaqq3W60003W/9xjDLDDOxrcYZYb5eMxmMxmmdAabmtxuNx89WazeQwzVX2rdbyDdbv8A3GcMssM7WsMs8N8nGMzgwwzg/jhpppuNxvXms3kM6A3kG63W/wDcZ0tna3pbfIxmMcGGGYiIjcabyDDc681msM9mcGm+zTTdX/uc/LZmMxjkMxmc/CPjiNzgxwYbnXms1nBeGm63f+7zwK3o++PmMMsMxmc3FVXxzuMMMMN7FVVX/lYnEROInVVVVVVVVVVVVVVVVVVZrTfy2xna1rbTbdVVVVVVVVVVVVVVZwyywzubGGWW9iqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqvGcREREbicbxVVVVVVVVVVVVVVVVVVWa022xmqqqqqqt1rbbTVVVVVVVVVVVVVXjGWWWd3WGGeERmIjcRucVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVeMZjMZiIiIjcbjcbnG+ZjNbbaZ2tabbabvi5wyzwzvawywjDORppuNxv/JYxmMxmMziIiJxG43G43iqqqqqqqqqqqqqqqqqrN6Cs1ms3qrdbvNfM03VVVVVVVVVVVVVVnQ8VVVVVVVVVW8MMek9MMMz0npvpwY4a1VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVeMYxmM4qqqqvOtxv8AG+ZmtN8WmbxVVed3oK03fGx9ubPA1huIzGYiNxuMssN/4/GMxmMxmdzcbjDc8zGcNtNM3p3W70Fabvj59vtzZ4GtxEZjOdbjDLDfzIiInmxmMMxhhmIidmIjcaVVVVVVVVVVVVVVVVVVZ0DTNZqqqt3pKN1dVVVVVVVVVVVVVVVmtNtMVVVVVVVVVV5idW9D+yqqqqrr5fPP/wBfL5VVVVVVVVVVVVVVVVV88fKaiImvnj5VVVVVVVVVVVVVVVXyxmMxmmGYzERGt42q+ecREbnmMYwwzOGazWbybrdababtb5GNtts3wN1u8M1end4b4/ZvVGYzGeiI/huInkTjM9MxE9InpG43PTcTyMMzgzGYzE53ONbxOcxmIiInl4wwwzGcVVX2rW+YY202zv63W6rNZrOjd4b4799WYzGGGc/XTTTcbniZnGYzGYzERPSI3G43G5xviYwxwZjMTr3G5zGYzGZxERPKxhhhmMzpq8a1hhrfIxpttrjO5rdbreDDNZq8brdbbbb0YzOgDDOXppvINxueFmIzGYzGYiIiI3G43G43ON8LGYwwwzE7GtxuIzGYxmInRVVVVVVVVVVVVVVVVms6RVVVVVVvQNVVVVVVVVVVVVVVVVZvRRpmqqqqqqqqtdEc4mcjegBpuqrGMMcGGYiIjcY5LLWqqqqqqqqqrGMZjGYziqqqq8a3OG41qqqqqqqqqqqs4ZYYzVVVVVVejGZzVVV8nPDAb9+TjXNaZq9rdbvYIA5x70QN3oxhniwzOInE5xyWGt7+YzGYxmdqcbjDcY8HOGWGd6Mn4OdCxn12t6Q3yMZrXRRm9ndbvQVpWawwzj003W70YwyywzOzuMMssN7uMxmMxmdjM6Jqe0bjDcbjcbnezoeM7mc5n4GdCxna1vQN8nNZvSAYZq81Wm9II3VVms3oG6vTnHLLDO1uMMsvt3MYwzGdjOiJxG43GGG43G93Oj4xVVVVVVeM4zs1VVVVVVVVVVVVVVVZrTTNYqqqqqqrd4aabrdVVVVVVVVVVVVVVVVVms3pFc6Qab0lTdVVVVVVVVVWcc8MVVVVVVVu9Jbqqqqqqqs5MYqqq8ZxmMzn4fD443G43G4w3GqqqqqqqrNb5s7mfTOKqqqqq+Tn2000zWdrdbrbbfMzWazgY57s9+fXfdrvE03fA+z7+APry72s+2cMZ1ZxnGdncbjc4NxhudvOO+OKqqqqqrxn4uNNs1m9mt1ptpvm1ms1hhntz/20003W74GPt4A+nRd7WdAzpzjOMzubjc4MMN7WNtts7ufiZrTTTNZ2N1u8Wm63fPrNVSlKVwq+DjTbTTO638NNt3tZyZxenNYzOM7m5www1vZzWm2mmb2qrO3VVVVVVVVVVVVVVVVWazWmmmaqqqq3W7waabqqqqqqqqqqqqqqqqqqqqqvnn5fK8VVVVVVVVVVVVVWbw200ze3utNNNtVVVVVWM4YxnFVnGMZxVVVVVVVXjWGGGt1VVVVWazW22mbWb26zV/DzWa00wzVVVVu8hput3z8xERERG54mfbG2m/jhnZ1rTbfDezjOTPpnTnGeBrcZZa3s5rTbbTNZvVeLi4zWazWb+Fms1msMMM4P64abwN1ut3z8xmMxmazg03Tcbjcb4ea1zWazezut1vg203s4xnDPpnOcYxjO/reOeG9nNZrXIYZrNVfaq3Wmn9M4Gazfw6zWGGGdBaaaaXz8YzODMREbnBuNb4ebGb0VZrNVVVVbrd6CtN3tYzfhjTGLxnRiqqqqqqqqqrdb0Ld7VZvQBhnQGmmu8OcwzWav4dVekNN1u/g5jDDMZiJiNxuMMNxvh5rXRRms1cXi4rd6Sjd64ic59NNM3nOM+mcZ9eDvQN7eazWcDHPZ/fH+2+zXXeDOgRpVVfw6qr+HjDDDM4iJxuMMsNzxM1roAwwvJvQG003mIiIiIiMZwzjOMYz78LfBDNZrDORTTTTdVmtdBGGaqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqvGdKxVVekbxVVVVVVVVVVVVWazkOOc/Xea6abvOYzGYzERERuJxjNZvRjNZ4W/XLrhVVVVVVVVVZq9IVuqqs3pBcc/4kM8BC3xM1msMMc6N1000q8YzGYzERERG43E4zWazVZrNYqqqqqqqqqqqq3W22263v1VVerGazgY45/wATmdKZ1b9N6FvjZrNZrNK4U/pW6rGMxmMxmMzrjcbicZrNZrNZrNZ4WtttN8zNZrDDH+39v7/4bGc+MVVVWt6Fu+RVVVXoxmMMxmMziInERONxuN4rNZrNZrNZvg6bbabvm1V4f0qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq0000zV6N1utNNtN1VVVVVVVVVVVVVVVVVVVVWM4YZxna3jWt1eGGcDDNXu1utNt8N5qqqqqqqqqqqqqqqqqqqqqr/w+a01wZrNVVVu8Gmm7+DjMYYziqqqqqqrxrWtVms6AGazVVVVVVVXjd5MNzhuNzW5/wBRmtcGawzV9q03eDTTfwM4YYZ4TW6rNZyDTNZvb1rcrTTfVrrppuNzz6qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqrNZvIZ0BvA03W6qqqqqqqqqqqqqqqqqqqqqs5MYqqqqqqqqqq3oF1Wb0gGazeKqr0YidJ67zXRuNXVVVVVVVVVVVVVVVVVVV/wCJzWbGGGcjTTdbv4WffJnhb0mM1nIMMM1VVVVmsZjMR/CI/hvSXsNz/pqqqqqq/hZ9s5M8LeXftv3zms3gwxzqAzWMMxmInpERuN6RNhv/AE9VVX3+JjOTPC3l1vRms1hhhnv0fDXHDDOxuMchlvmVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVms1ppiqqqqqqqqqqq1pput1VVVZq++H9cmGugZxVVVVeWWGOOqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqs34aaZrN8LTTbTdVVVVXhC4rN4f48mdreGGX3bqqqqqqqqqqqqqqqqqr/ANpms1ppms1VVVVVVVVVVutNNN1u9vOks4qqqqqq1vDP3w+zf/Ds1pppmqqqqqqqqqqt1pppu9zOj/Vnc19X+fJv3/1/zxE1NRr58jNaaaZqqqqqqqqqqrdaaabvX89X3bbfVneNNtN+/wDrsZnphh/L+Wmm56b4+azeQzWaqqqqqqqqrda4NN1u9WM/jM4Ruca+W22maqqqqqqqt1ptv7abv/WYzGORzg3oCbjW+LWazeDNZqr2qrdbvBut3qxnBnBvA3GNNtM347etfDTbTTd5zGImInG/9FjHRbnN3ovYb42azWuDTNXO1cbrXBput3pz74ZY5G8LDcb5jbO1rfNbbvGMZjMYfxybjcb36qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq+Xz0fK6qqqqqqqqqqqqqqqqrOGOgDMRG50EY4aqqqqqqqqqqqqqqzWcgwzWcFVV9rw03W8g03VVVVm9PZjc6Fm9JxV6t1eoMt1jGYxrDClNNMa3GrqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqrGZrMZiNxuN4qqqqqqqqqqqqqqqqzjlhlnTrLLPHdVVVVVVVVVVVVVVVhhhhjnWA0010000qqqqzW2mmlbrTbfzwl0rlVVVur1Gtpaz+cMMMMxEbjTDHDVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVYzOQxzi13mG41VVVVVVVVVVVVVVm8MfLLHCqqrxhhljhVVVVVVVVVVVVVVVZrNZ7MM9mezOh99m+zfZpvs3W6qqqqrNab4tP6bvtpttWvl8nQbnt0hvQc9vFpusYZYYZnTuMMstaqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqsZnBflc9eOu9FDcaqqqqqqqqqqqqqsffjj64Z2x+zVVVVVVVVVVVVVVVVms1WGcEP6Rw003W63VVVVVVm/LN6CMN5lrjHyxw1wZ7s9+ffdvt0l2m6xjLLLMZnTuNxlllq6qqqqqqr5fL5/KxjPQRhERvQIy3xcb+W/lv64a69cNfbf218t8mqzfar75P6X2rd9r3M1mvZy9fbwVjosi8f6f1x09r2PZw6bvUedjent++3PSek9NziqqqqqqqqqqqqqqqqqqqqqqqqqrOOHoZZjOjWGXoY46qqqqqqqqqqqqrN+W31cxms3p3Wnwc1puqqqqqqqqqqrzEROaqqqqqqqqqqqqqqqs1hnP3i0xyWO8MGv9P7abwNdN1VZrfPmqqqqqvQtN1VVVVVVeTTTcaqqqqqqqqqqqqqrz8IiI+OKqqqqvJhhEYqqq41j4YY5KqqqqqqqqqqqqrXSVZqqqt3pqNKqqqqqqqqq8ZGYwwzg0003OKqqqqqqqqqqqqqqqoR/tH++Fzj92fhnIjD/Llbz99kKqqrN+G2vltm9nTbf223VVVVVVVfw/hvJsNzxMxmMM6A0003E6sfZhn6ZZ0VedZZ++H28XHzdP5mqrd6jy3v5jM6Bc5Gm+nQhueZjTbf00rTf2203e1j7tcdM69aaa4b9923nmOG+DjGN5DHG2uumnBua3pz7ffo+cVeSq3ef78N+/ErT3PY9nBnu/tvu9vF7Htbf7bvfxjW3R7jj/Leivs0b5eN9F/9dG2/lu9PyiJqazNY3n0zerdbrTTbd7kRuMsM819r7X2vtfa+19r7X2vtfa+19r7X2xjHIYYZiI3G9ALEbxfa+2a2222zW+zTeXhnBpttpur7X2vtfa+19r7X2vtfa+19r7X2vtfa+19r7X2zeg728veb+7j03V9r7X2vtfa+19r7X2vtfa+19s6k5hmIjcb0h7LVX2vtfa+19r7X2vtfa+19r7X2vtfa+19r7X2vtfa+19r7ZrXZQom6vtffGMzWGObY5thjhnN9r7X2vtut6EW6vtfa+19r7X2vtfa+19r76IROibvyqqqqqqqqrEMXmsYzGYiYmIjcYc1hrVZrWNttK3eHeRhmUc17msbqqqqqqqqqqqqqqrDCP+XsZ7v7f233exX/AC03VVVVVVVVVZwxeLDgxnHw+Hw+ONzODLpAqqqqqqqqqqqqqqqqrN4I/wCXs477PZwbqqxmKdCmMcJ/0xwzHw1q4uK3HQ1puqqqqqqqvOtPo19tNN77HNZjMZ1a1uMfHBhhvGNNt/DXw3eDdaVWGF98hqteRmsM6D0003fAZ6KsdncZ5LHz5jNYZw6abvOYx0Xehhnr1YiNxrdabzWjTd7tVutclqtd7GGOLDGdnW4zwZ+eWffT2mm63VVmq3kW2vKq8Kq+FzwY+GWdncbjPFllvl1eFXnGOodMIiJ6T0iMNzjqdQobvge9OW3VVVVVVVVV5cMs4qqqqqrxvDHLus45YZWmm707rd6CN1VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVWb88+eOKqqqqqq3jnolVVVVVVVVVVVVVVVVVVVVVnDF6BMc1VVV41jk20abpulVVVVVVVVXn3pxFVVVVVVVVXpHFVVVVVVVu9K6zhlj4T4fF9m6qqrdabbbqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqzel8VVVVVVVepVVVVVVVVVVVVVVVVVVVVVXhjms/DEZ2rwz8M8uvlVVVVVVVVVVeTT28huqqqqqqqqqzjhjjnd3jjhr7M/LDHw3Geu1pttqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqryf4+A/rw+/DdVVVVVVVVVVVVVVVVVVVVYzzXwMdzeM81hj5aqqqqqqqqqrz66brdVVVVVVVVVeh/Tvt+uuH/F9G4z8MtxuPhPfGttNN1VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV5NNfXDO6+jXNu/Kqq6+XyuqqqqqqqqqqqqqqqvDHB9TDPrvYZ+OSxwqqqqqqqqqryUurqqqqqqqqqqrTfy202qqqqqqqqrdaaabrTf039NfDGOLRuNxPTWm22m6qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqtNfLTbbNVVVVVVVWm2m227qqxlRG5rXyqqqqqqqqqqqqqs45+mGOFVVVVVVVVVvDLHNdVVVVVVVVVVVVVVVVVVVVVVVmttNNKqqqqqqqq3W2vtppr5fNyWmscGmm5w2003VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVWa3zGmb291vi+x8jXyqsYzGYjcbjVVVVVVVVVVVVVVm+VJe78qqqqqqqqqvi5rbTTTN7u620018rzPte1hvy3ODcZaaaard/RzflqdEGmaqqqqqq3ekK3ecZ4MN4GGt8TOkcVVVVVVVVVV6B/lx38PPtprg2zVVVVVVVVutNcW2s1qcPu5rPduG7jWdEnzN/Tzek80qqqqqt3pnNVvGM45YbjLL7t8TH+PQc1VVVVVVVVVVvSG/iZrbktM1VVVVVVW70Qa1u8ZrTOD2ve9vHX2vc9nHu63f081pw+7m8M1eitjh9vRNu7zjTbbTdbbb+W+JmttNNs8DWmmm/lv4mb0g2Gaqqqqqt6Rturzms6AmG8ku03f1c3qCLHOZrvTZLtN3nN+Wuaw3lWm74mmvlpr6bZvgbrX200238XXJ+/jzDNXpuNxyft5jd6c1hjnu/pvs33ab7N39a8h7nv48f9s9+EN9mP+3ve97l2m705rXBmf8Abfdjwbrd8TTfzwaaZvf3Wm+LX2237/Fxm9R6Z0g3qPxu9i9Aq/pxEROc3pEcc9+O+7ffoV3W71YzWGcGmm74ufbfMaa7+t8xtr8fNZu49jV7HsZ7P64/209nB7mrRur+/jM1nBpua3nNZpjnuzSv9q/23Tdf7a7purvYuqvCrvj6+XydD2b3b1Apu+BVVVVVVVVVVVVVVVVWawxzTDORppvB03VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVWa+TDODTHphqqvUCuGlVVVVVVVVVVVVVVVVVVVVVVVVVm9VqZvb3W6lnRvpuqqqqqqqqqq+VmqzWGe/H+m+zXfdpuqv7+MZZ6AZZa3pqqq/kZrXD7nu5y+2b11ut33zPue/i3V/LqqvJVVURERE/azkwx8Iwzyb+lm8j7nu5zNVeiq3eU9z3cem7+fVXnGYzGGceumm5+zmtfLTTStNNNN39LNZvQP7eP2M90f7X2/p/Tfdr7nve17Oc3fCqqqqqqqqqqqqqqqqqqqqqqrGZXobb/jgz1fy31el6GmMNbqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqzWuiX69C2m6qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqzgy5f3Paxzi13i+7of2m6qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqxhfk/WzP+n8t9Xpevgiy3iqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqzegD+ugTdVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVWayOGP+Xtexntyaex7Htezh03VVVVVVVVVVVVV/Bxiq836eDPXhueW9HBNlufr5rNM49dN39is1msY57ML/wBr/wBt032aa7pu/rZnUBeE43WsdBkmZrf16q+1X9uqvtdUpS7/ALX2v6+PvwfTw5jPhutNd527WOQw39i+1X96+1VVVffk1VVVVVVVVVVVVVVVVVVV6H6H0M/HDd6BNf8A745zOWeG6qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq+fnDDLL6q1Oe00usM4N3oO/+aZx++Prza6AN1VVmq18Nv8uO/wDi1VVVVVVVVVVVVVVVVVVVWb8tt/TfHXw20003VVWavIbbbqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqzW/lv5bbabab+W63dVVVut8W226qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq+fnH7N/TX10L7vt17ba4b/wCLf//Z'),
    ('바다', '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wgARCAPoBkADASIAAhEBAxEB/8QAGgABAQEBAQEBAAAAAAAAAAAAAAEDAgQFB//EABkBAQEBAAMAAAAAAAAAAAAAAAABAgMEBf/aAAwDAQACEAMQAAAB/SR2fNAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAiCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAILAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAhKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoIKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAISoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqAgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgIsqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgIKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACISoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCoKgqCo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CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD8888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888NNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwzww00w04MAxxxxxxwF80w44wyw7wwwwwwwwwwwwwwwwwwwwy00www00tIRxxxxxxgd44w0w44/wwwwwwwwwwwwwwwwwwww/yww0f988888888888888888888888889vP8Av7zzzjjjjjjzv/37n/fPPPPPPPPPPPPPPPPPPPPPPPPPfv7/AP8AfvOOOOOOPP8Az37/AL3zzzzPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPOH3Hfn73bnHHHHHHHHHHHHHHHHHHHHHHHHHLvfHfnvPDBHDDDDGH3HfvvfbLHHHHHHHHHHHHHHHHHHHHHHHHHLH/X/ALx9xwRwwwwxNNNNNNNNPeeu+u+eiBOBBBBACEQ+ueeuv8sNNNNNNNNNNNNNNNNNNNNNNNff8P8ArnnsQgAgQQQAhEPrnnrvrrDTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTDDDDDDDDDDDDDDDDDDDDwjCBRACHffffffTCSyRQgCzjDDDDDDDDDDDDDDDDDDDDDDDDDDDDChzAiABDVPfffffSDRACABAyzDDDDTDDDDDATASTVYc80coggAAAAAAAAAAAAAAAAAAAAAEocsgUbiADQRTDDDDDCDQRSFycYcs0YgAAAAAAAAAAAAAAAAAAAAAIksogAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADjjjigjiRigRDzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzyQRQjiBQlTjjjqRiBTQgSRDzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzjjjjjjjjjjjvfPDDLYAARARQgBDjjjjiwCQQQQAATLDHfLDjjjjjjjjjjjjjjjjjjjjj/PDbDCAQQQSQQQBzjjjiwARQQQAQEDXTTTTTTTTTTTTTTTTTTTTTTTTTXj3PffbTzzTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTDzPfffbj7TTTTTTTTTc888888888888888888888888888+ddtucvs88888/s+vsu+vc88888888888888888888888888888888888889Ntcvstus8888+MssssssssssssssuP/AHjv+DCDDFNPLLLLLLLLLLLLLLLLLLLODDANHjz3f3jDLLLLLLLLLLLLLLXTTbjzhDEPDAHLLLLLLLLLLLI72xzw888889+xzw24888888888888888888888888888888888888888888/1ww3w88888/w9zx248888888888888888888888/HHHHHHHHHHHHHHzLrrL7HrHHHHrHr7HXvfDHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHX/PjL7LH7HHHH7H7LXfHPHHE8880c88ct88/48w888888888888888888308+88888I8cc88888888888888888888g88I8u8989/w888888888888888888299502zw44444444444444444444444444444444444444446y+x12/8Avyyyyy/+fN/M/MvOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO005004wwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww659y959888880805003wwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwSySyhCy6y9zwwwwwwwwwwwwwwwwwwwwwwwww76y2yiyyiRywwwwwwwwwwwwwwwwwwwRSyiCa6y2ywwwwwwwwwwwwwwwwwwwNNNNNNNNNNNNNNNM+f8Aj/nSijgQQQQQRSijifjvr/rDTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTX37rvnXxSRSQQQQQQwTjDDDDDDDDDDDDDSSSRAiQgggiQhgTQCSDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDySRBARgAgghgBBASScMMNuPPNKEAAIEsMMMMMMMMMMMMMMMMM4AEAANPOPPMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMtPOPPIAEEQY8MMMMMMMMMMMMMMMMAgokMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMIgkggsfsfsdcOcMMMOcOddetfogsQksMMMMMMMMMMMMMMMMMMMMMMMMMMMCzzzzzzyzxixCwgwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwxSDxhizzzzzzzxhiyxCQwwwwwwwwwwwww8ssssssssssssoEQgYQeefde8sssssssssssssssssssssssssssssssss/effdQUQQcE8ssssssssssssssssAYQUQfdfefMsssvPPPPPPPPPPPPPPPPPPPPPPLHDPHFOOfdOsPvPPPPPPPPPMP+uPPIXbDTL/ADzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz8yxy8MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMNDJLHHHHHGHKOAMMMMMMs4ccoUoEEEUoMcoo4sMMMMMMMMMMMMMMMMMMMMMMMMMMMMNvPvPDPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPH/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lKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpf8A0mlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSl/wDSaUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKX/ANJpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSl/wDSaUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKX/ANJpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpf8A0mlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKX/ANJpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpf8A0mlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSl/wDSaUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpf8A0mlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSlKUpSl/wD6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'),
    ('밤하늘', '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KIoiiKIoiiKIojRwNOWiKIoiiKIoiiKIoiiKIoiiKIoiiKAAAAAAAAAAAAAAB7UeK9Dz6AAA+vkANOYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAANPD5AAAAAAAAAAAAAAAAD7+Ohz7cQAURehyURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFE6fHQ5KIoiiKIoiiaswiiKIoiiKIoiiKIoiiKIoiiKIoiiKIoiiKIoiiKIoiiKIoKJ0+BFE68x05URRFEURRFEURRFEURRFEURRFEURRFEURRHfiRRFEURRH6DHL5arIoiiac4iiKIoiiKIonfiIoiiKI05yKIoiiKIoiiKIoiiKIoiiKIoiiKIoiiKIoiiKIoiiKIoiiKIoiiKIoiiKIoiiKIo69L2l85VkURRFEURRFEURRFEURRFEURRFBRFEURRFEURRNWYRf0kv5pVkURRFGrJRFEURRFEURRFEURRFEURRFEURRFEURRFEasxFEURRFEURRFEURRFEURRFEURRF1mNRFEURRFEURRFEURRFEdPgiiKIoiiKIoiiKIoiiKIoiiKIoiiKIoiiKIoiiKIoiiKIoiiKIoi/Zzen5qxSRRFEUdOXbkRQURRFEURRFEURRFEURffl/PqsiiKIoiiKIoiiKIoiiKIoiiKIoiiaswiiKIojdiIoiiKIoiiKIoiiKIoiiKIoiiKIv6mX8qqyKIoiiKIoiiKIoiiKIo++dEURRFEURRFEURRFGnLRFEURRFEURRFEURRHQc1EURRFEURRFEURRFEURRFEURRFEURQCgAAAADWZAAAAAAAAAAAAAAAAAD148h15UAAAAABuwgAA/T/mEBQAAA9SPLFAAAAAAAAHqefHMUAAAAAAAAAfXyAAAAAAAAAAAAAAAAAAAAAAAAAD6Pl34AACzucAAAAAAAAFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRNOcTZkEURRFEURRFEURRFEURRFEURRFEURRFEURRozURRFEURRFEURRFEURRFEURR19nwURVRRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFBRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURQURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEUFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABSxRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEURRFEUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAf/xAAsEAACAQIFBAICAgIDAAAAAAACAwQBBRMwQFBgEhQgcBARAIAGFSMkISWw/9oACAEBAAEFAua4TMHLQ1iGkVSLgr0NRzXFZg+TJDmR9nhFHGUfT16ZEc3L2+1wH3GVOithy9coyU1pk1u2RwUepSzD5DClyIb5DmyH8FjPwOMSEOjny0yjdl82gIrLl/IVQE3DihVqVfWbTSUbVowP0DiAlkjgY06ikKJD98UBNa0CU3bCEgLhllgf2U5wYbtnx29r5uoii8mMsWvKn0W+iRAUhzJDuSw47Jcm4wnQJGjfgbSlzE8QkXGOyzeTVsUzckNY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fffffffffffffffffffffffffffffffffffffffa/fff/bfffffffffffffffffd/fffffffffff/ffffffffffffffffffffffR/ffffffffffffffT/fffffffffffffffffe/ffX/AH3333333332/wB99999999999999999999999999799BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBDBDDBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBDBBBBBBBBBBBBBRBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBzzzzzzzzzzzzzzzzzz37zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz/zzzzzzzTz3zzzzzzzzzzzzzzzzzzzDjDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDBDDXDDDDDDDDDDDDDDDFDDDDDDDDDTDDDDDDDDDDDDDDDDDDDDDDDDDDDDDyyyyyyyyyyyyyyyyyyyyyyyyyzy2yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyxyy2yyyyyyyyyyy2yyy5e/8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AK2//wD/AP8A/wDv/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AO//AP8A/wD/APP/AP8A/wD/AP8Axxxxxxxxxxxxxxxxxxxxxxxxx9xxxxxx1iRxxxxhxxxxxxxxxxxxxxxxxxxxxxxxxRxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AH3/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP1//wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/APf/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP7/AP8A/wD/AK1f/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/f8A/wD/AP8A/wD/AP8A/wD/AP8A/j8MMMMMMMMMiMMMMMMMMMMMMMMMMMMMMMEMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMGGMMMMMMMMMMMMMMMMMMMQMMMMMMMMMMMMsMMMMMMMMMMMMMMMMMMMMMMMMOAMMMMMcsMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMNMMMMMMQMMMMMsMMMMMMMMMMMMMPHHHHHHHHHHPHHHHHHHHHHHHHHHHHHPPHGDHHGNPHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHLzHHHHHHHHHHHHHHHHHHHHHHHHHFbHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHLHHFLHHHHHHHHGHXHHHHHHHHHHHHHHHHHHFHHHHHHHHHHHHHHHHHHHE0000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000Y000033333333333333333333333333n3333333333333333333333333333333333333333333333313333333333333333333333333jKFvLLLLLLLLLLLbLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLbLLLLLLLLLLLLLLLLLLLLLLLLLLLL33331/wB999999999v9999999/wDfffffffffffffffffffffffffffffffffV/ffffff/fffV/ff/ffffffffffffffffffffffffQAAAAAAAAAAAKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEACwAAAAAAAAAMMMMMMMMMMMMMMMIEMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMOMMMMMMMMMMOMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMAgggggggggggggggggggiAggggggggggggggggggiQggggggggggggggggggggggggggggggggggggggggggggggggggggggggggsssssssssssssssssssssssssssssssssssssssssuMsssssssssutssskMssssssssssssssssssssssssssssssssssssspMssgQQQQQQQQQQgQQQQQQQQQQQQQQQQQQQQQQQQQQQQUYgQQQQQQQQQQUAQQgQQSAQQQQQQQQQQQQUpgQQQRywQQQQQQQQQQQQQQSgQTTTTTTTTTTTXzTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTXzTTTTTTTTTTTTTTTTTTTTTTTTTTTTzTTTTTTTTTTTTTTTffa/fffffffffffffffffffffffffffvffffffffffbffffffffffffffffffffffffffffeffffffffffffffffffffffffffffTzzzzzzzzjzzzzzzzzzzzzzzzzzzzz3TzzzzzTzzzzzxTzzzzzzzzzzzzzzzzzzzzzzzzzz3TzzzzzzzzzzzzTzTzzzzzzzzzzzz8ssssssssssssssssssssssssssssssssssssssssssssssssssssso8sssssssssss8sssssk88s8stssssssssssssssssssssgggggggggggggggggggggggggggiwgggggggggghwgggggggggggggggggggggggggggggggwgggggggwggggggggghwggwggggggggggggggggggggggggggggggggggggggggggggkAgggggggggggggggggggggggggggggggggggiQgggggggggggggggggggggggAAAAAAAAAAAAAAAAAAAMQAAAAAAAAgAAAAAAAAAAAAAEogAAAACAAAAEgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAAAggggggggggggqAggggggggggggghAgkAgggggggggggggggggggggggggAgggghiCQiAgggggggggggggggggggggAgggggggggnPvvvvvvvvnPvnPvOvvvvvvvvtPvrPvvvkfvvPvvvvvvvvvvvvvvvvvvvn/AL777777777777777777777777777777777777777777777777774/77757z7T77777777777777777777T/AO++++99++8++++++++++++++++++w++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++R++++++++++++++++++++++++++++++d++++++++++++++++++++++++++++++AAAAAAAAAAAAAACAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKAAAAAAOABiAGAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAATAgwAAAAAAAAAAAAAAAAAAAAAwAAAAAAAAAAAAATAAAAAAAAAAAAAAAAAAAMMMMMMMMMMMMMMMMMMMMMMMMMMMcMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMAAAAAAAAAAAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAjAQAAAAAnAUAAAAA88888888888888888888888888888888888888888888888888888oU8888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAwwwwwwwww5wwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwxwwwwwwwwwwwwwwwwhwwwwwwwwwwwwwwwwwwwwwwwwwwxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxwxxxxxxwwwwwwwwwwwwwwwwwwiwwwwwwwwwwwwwwwwwwwwwxwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww88888888888888888888888888888s88888888888888888888888888888888888888888888888888888888v8888888888888QAAAAAwAAAAAAAAAAAAAAAAAAAAAAAAAAEIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAwwww4www0wwwwwwwwwwwwwwwwwwwwwwwwwwIkwwwww0wwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwQwkwwwwwwwwwAAAAAAAATAAAAAAAAAAIAAAAAAAAAAAAAAXAQAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIgAAAAAAAAAAAAAAAAPPPPPPPPPPPPPPLNPPPNPNPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP9PPPPPPPPPPPPPPPPZNP/wCf/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD+n/8A/wD/AP8At/8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wDGHHHHHHHHHHHHHHHHHHHHHHHnHHHHDHHHHHHHHHHHHHHnHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHLHHHHHHHHHHHHHHHHHHHHHHGHLHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHnHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHXDHHHHHHHHHHHHHHHHbHHHHHHHHHHHHHHHHGHHHHnHHHHHHHHHHHHHHHbHHHHHHHHHHHFHHHHHHHHHFHHHHHHHHHH3HHHHHHHHHHHHHHHHHEwwwwwwgwwwwwwwwwwwwwwwww4Qwwwwwwwwx8wwwwowwwwwwwww4wwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwxgwwwwwwwz333333333333333333333333333333333333333333333333333333333333133333333333331/333333333333333333333333PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888/7777777777777777777777777777777777777777777777777777777777777777777777777777777777777777777777777777zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz/xAAjEQEBAQABBAIDAQEBAAAAAAARAAFAECFQYDBwIDFBgFGQ/9oACAEDAQE/EPdux9E79rno+68M9BzOhwDg9+JmdTgbm5br418Rmn5/zxO/vt/gnMfXsx8Puvs2aeOzTmfvw2b+D9I7h7TmPTM/7HyHnzjszMzMzMzMzMzMzMz0ZmZmZmZmZmZmZmZmZmZmZmbdyZmZnozMzkz0ZmZmZmZmZmZmZmZmeAelbm58bMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzPRmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZ4u8Tsey7hwH1R+R7H57ufz5+3JIiIiIiI6ERERERERERERERERERERERERERER0IiIiIiIiIiIiIiIiIiIiIiIiIiIiIiZs3P7MzMzMzMzMzMzMzMzMzZ32ZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmIiIiIs7ZERERERERERERER0IiIiIiIiIiIiIiIiIiIiIiIiIiOhERERERERERERERERERMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzM9GZnozMzMzMzMzMzMzERERERERERERERERERERERERERERERERERERERERERERERERERERHQiIiIiIiI6ERER4jNPC7h4zse35m77I+C3DyW8Lscjd3fK9jnZp+W5uabbrxj0Xsc90PY809Jzw+H99ezHyb5vdemafl2P8QZjj66+EfEvgu3w9jk5pxt3t9JZp9vZpys34HxLz87+hP0qdny3Y5OZ6ruHBzHw2Y+mY78DvXN3Px7/Q7v6/8cf/xAAkEQEBAQACAQQCAwEBAAAAAAARAAEhUEAQIDAxQWBRYXCAkf/aAAgBAgEBPxD925f8JzrX0ZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZ7rflcT9HzDw93M/Qdbn1nRj4mv48PNbMP1Xcffy9C/Bic/8E7p0K9Qx4m7mdPmZn12Cefvj7znHt46nczZ5Dy+M6bcfZmcvvPU8U8v7/V81x/ad0530364s/v5OO/4uPF4iIiIiIiIiIiIiIiItMiIiIiIiIiIiIiIiIiIiIiIizOOYiIiPQiIsz+Yj0IiIiIiIiIiIiIiIiP1rNzfr9vIiIiIiIiIiIiLc4szjmIiIiIiIiIiIiI1/qIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiI6rNzcc+PPbmZnT69bmH18gX1zc32Y3M5+fn9/1OPM0Ynycd0RERERatzYiIiIiIiIiIiIiIyIiI9CIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiPQiIiIiIiIiO3PG3H9fzX68Y/PXbmb99KnWOv9fDx8/Fx7uPaZ1hERERERERERERERERERERbuZ97ERERERERERERERERERERERERERERER6EREehERERERERER5u6eu5m/fRZr2Wc58u4+3l8jMZ9dry/10gzWZmZ9eM4n6Li7/AB8GZmeOF/PnkREREREREWRERERERERERERERERERERERERERERHoRERHoWODYIt4iIiIiIiIiIiIiIiIiIjqtx9fz0mtz6zrzr93M++zzOXyDow/PpuOHuN5PHpvvOXtN/qz65/wbeuzrtG5n8+a9fu5n34O5m9IdTmHV7rMYceGe7DBvjBu6/f6Fz4+9zuN3N38fFmvPs3Hod0xs1x7bX8eJu5n38h8X17cPvtc9N8LcYN+NffvHwa/j4d06jPP0Y2a4/oJy/rhnc/wPnen/8ADyNxtG5ntzpHrM3Nxz28vyAeFuPszc3nPA3Gbmb+f0zQfgzMzjPgG4zTfieTps9d7Ezej3G7m/7CREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREf8W//EAC4QAQEBAAECBAQHAQADAQEAABEAASExQVBRYGEwQHGBECBwkbHB8KGA4fGw0f/aAAgBAQABPxD1r/i4Ic81yTn4jfwxzrp9Nzc3c3Nc3N3Nzc200p1mtrum87u7ru76G+8QgLrtE3jTfPPWv+Lgh3yXBOPz+yCiR4mYmM3lp2PCMDyBnuc/kx1uOZro2/AYK/A4azDN3MN3kzp8vgaJofl2ZunHT28QEZG492mYjN0gY3XHbN3MO9Ni240PLAOZuPOZrmfPcO9eCtDc3NNzONwuHevFWhmZmO7vGYeG/Zzuh99bz4w56/M/xqWHcwDjsd9Q7ZsOI6rA3DjNNzTczeuZuNuo/OumcZxmZmZmYMzMzMzMzM9DfwLJXczid0d49MIdRm3Nzf5zc65ubmm5uZ+QiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiLSAR4fUBm5ud3HO7oqREi/s211G5PssGt3gAVd2+moIG3QwOEERERERERERERERERERERERERERERERERERERERERERERERERERERERERYbCcmjWYEb2zGZmdszMiIj9MPbkXr7z51T3Dvzn+LNn/X+gP8AwD9tFt23JxMcHTl29CbWYfbBbunOmZj33czO9lcAnrueW5/Gm503M3NzPHOH2tBWDu5mO7nO6XD7WirBzdzTc3nNPDdy0j9UbhvObm5ubm+jfYxiP73Oujh5E33jwoHRFHN75ueEf74A4vYE9n4Guf8AigbNc3Rw/wCauvheHJQN3De+n9mPXcO5rdPhYyzTMDBvXHM3zzPHty8j9U5pnObm5m5uSR/BzrpnGcZmZmZmYZmZmZmZmZ6m0DR4dZrQ8sxu6O8cZumXfXFyGOOZucA3M112N35P/BD3/gHuPhP2j0S9Bomc4b7+kN2K3SC6c509eM81+cWyuQXMw4ZuObm/Tc8TUNGOddO/G5ububmubm7m5ubbx8Tw6DAzDrpmZzu713d/RQtlcAuZh03dMzM+mZ4AzzBevmAcOh0wXMPR4REREX2q0y9Bomc4b72Ed5o2znMtzM41fXnTG5RERF/8Hw/+wO0REREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREQiZ4up3c3Gg0Y4MzgIiIiIiIiIiIiIiIiIiIiIiIiIie/jXejRokcGszNRvBIiIiIiIiIiIiIiIiIiIiIiIiI8UwRkNNNscEDyBPyf88Ec3uIe78/y/wwncwXIx0zqXL/DAd3FcrDTej6Ke5efQdTww55jdLuq/Ls9Ml3+A7rrD9zPmBaZ56n7cGbt119/ziaaAu+JGHOD68vLfg8uB9p4zjAO7y5axEREREREREREREREREREREREREREREREREREREREREREREREREREREREREREDVLQzBnAHbzc1moREREREREREREREREREREREREREREREREREREREREREREREREREREReYz4ffxvGo9nhywiIiIiIiItihcKsbmbrMbo7mPvkRERERERERHow7QN6TTTeBonAXG7PaBvSY6ZwtQ4Q4zPVmfA7fexTBgGw8ucNcab2bmNWszN3dHe+76Q2nIR3Rgc7u7uZmZ1sIZHEdNpbhxuOtNzc65uZ/URm8twR4S/uIzeW4CcL8PaNnIc/EDN0zN49+PE3DfpDGMy3Qw8vIzNfoaRERERERERERERERERERERERERERERERERY/jni8t1B4RsfzzxeW6CcKRERERERERbjkI7pwOc3NzNzc6WIMjiOmwsw53TGO7u9d3dIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiPDum9XdndMzunIxMOLdd6u7OabnZeRoYdH9Tf9RsjnmOSc+E/xDevZ3ndhN59FZdtbvG+HTOjlN74zrueN8rH1a4Bwt4x6yuu4x83Rhu6Zm7p2zfmf9RsjvkOCces8b3t5ga/yY5z2Ib4FnYXoe0NrrH9l8QX0JPGOj7nLjD4nKx9WOQcDecekrrucfN0aZuObuadt39K+3u79mbyd25848+sz5f+YUJ72o89xnrz/ZP3X9j5n8PoCeMdH3OXGHoji07gdhnPVnqc+DM8M44I6dc9Azd0vI3jhxp6Qz/Mtbu5PgumZy7nLdzN8JxV188XM+8gw+pvRokn7Hwbu4m8MY5ccYekNZoOzVrdCM7brc3O+bufkwniv3RnVLNzc3vxzqGePsdInmX7mf2buZzgLOWjvMVjjdxu5mnZ0899Abl5H6ozDOd3d3MzMss1DXDotDcOuObvObnXNz0myPmO9GjBg5cZuYLeR8L/AFbTl9j3OvzxEREREREREREREWSChZpuzAW/913cQREREREREREREREREREREREREXuc9OZnksLu9svc56c3PNaHN75ERERZgeA1PHlut3e9wiIiIti8j9U5pnObm5m5uWaahjh0WBmHXTMznd3ru7EREREREREREREREREREREREREREREREREREREREREREREREREREREREOj9+1u6nhrz3WGbgCIiIiIiIiIiIiIiIiIiIiIiIiIj9IdY1yfGirnDdMdWc48SDPRx1nU94hG5vJzrPByIiIiIiIiLdAbRdnMW4mnHvzOREREREREREREREREREREREREREREREREREREREREREREREREREWPbfq9vQe59P3oiIiLH1j914S+IiIiIiIiIsf4mYfc9zpEREX3NkwdTiLnPG5mxERERERERERERERERERERERERERNGD/Ov43Nxzc3jc3c3jbZMPYaWu7u7zu7vLEREREREREREREREREREREREREfIeR29nsZz10aYdGmab6q1ufzy4XY6e73z0GT+TsR7GAc9jnyn2bsDffW8+MOfya3GVtAa03pm7mmZ3Xlv4+Z09nsbz0w6YMOm476S/wB83bv3HXj1nmoYHl7dz9nO6a8Hz2AdNow4zd1uJv343HWt9Ubtgm6Yuv5zc65uaG5uZ8j9URORz8Fxx1678rz5wwncwXIx0znS6nFjV0DM3jdwIZnpfpBiMuLTrMyt7YMZ2zMzOnqM9GXl4wZwB283NZr8W6ZLdzFvUfvzmrMA615wHrPdc01ozpju7xzu9f0U0Bmo3mNBMd7jc4d7G/jsELLMYddDMOmO7nO5nXcyFe/udfxubhubnG5ubjm/oWEinZm6/jMzru7mY7uZvin2c7offW8+MOev4tlJpWbmmOcc3c+8RF2PgQFppubnOjm5rnk5uRI/CjMz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iIiIiIiIiIiIiIiIiLcxLd33M2MHOmmjeTTjelsFirvMbq0Y69jODPfSIiIiIiIiIiybbxQ1uu4HL/uriyIiIiIiIiIiIiIiIiIiIiIiIiIiIi6kG/hFYDeNOmxERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERER6d/2zs/6/0B8Lqgb+FVot5067+Izupc5bruJv343HWn6OuGCVv5gHDodMFzD00YSD4Gst00GjOumbvlm2ZOwNzDOx/rdx6bg3fif7SZy+x7nXxvS9lvN2Zv7/AF4Oo8EL+LXOo3c3Gg03HBmcH6RaWepNAZmszpm7ib3M8vnx9EfDv0zqM5CNzdM58Zxsl03bww4N7G72eefFxZ3gwz23NecNzc9tzc21e9zGe75Zn867vXd3d3fw5zG4HY7xnPC63LgzNz8mABeSCbxbmJn8cnhg+hJYx0fc5cYfLf4lG4vYE9n5T/A9HN7qHZfzZHuG7vzhLm5r38+Qz8nLazm063EDe26zc3vm5vzYOifh26b1WcAGZmucfBRYLhsdMzneM3ft+bKsK/MmdQN3d3O/PG5qZ4UWtb4O1xPItzGYrNN9aNQSk043O4ZuOby3HWtO63fwwkNp6I1hvTdzNNzsPPPkfqSWMdH3OXGvyHMSt1zTTc3rmbxudPJzeNEL5it3dM4zne36M6s2yzGHXQzDpju5zuZ13Ii7/wCdfxubhubnG5ubjm/BIbXALmYdN3TMzPpmfjrQpz3bcz9zOmbphqeH5eJ99m8gZOXI+Lj/AKjNUP3ftd/zfRwJycfBc89emeuO3AAStNNzc50c3Nc8nNwSH4UZmYM8sxmcu8c7uu/H37bxS1mOYHD/AJg68K8tM84y8AM3TNzn25+M/LNgEDObbvR1m+O5vhw0Om5113neMzMzd3dMzM3d3MzdsYsDEdFobh1xzd5zc65ufoTpx7hXjczdZjdHcx98+Q4TZo1zENzJgYdHl4duLhge3WB5aA3N543NNuRjb9puh3dKG7uuuxmeOERERERERERERERERERERERERERERERERERERERERERERERERERFhZ633uUwYBsPLnDc3HT1m5nVrMzd3R3h3YiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIjwj2x/dGOMZmcZmcZ6i7Ct7ZzOB2uoveoX25kwdTojvPXd301/uI7/AJwX017+YijXOszOM3evxsbzdZpaZjM53d3gy1vN1mFpus3nNzeDfhKkS0M0ZwB383dbj9DH/DY7gP8Apez1fj9WhIZz8Fxx167+HKWfbsYHkHRzoXKWfZtYnkDVzifJ++0avG73sN3eXUe/zGN5uswtcxuc5uby5a3m6zS13W7zu7vLvziR5lcDoRvY3ezz/UhTbRg7dZ8j0Zis0306xcf3NzPO2n9ueebjm6staO7ju9C3TOnO7vvv6IkREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREW+woyAF9zNO45onERERERERERERERERERERERERERERERERER89wFW4Owd3Mx3c53S4CrcXYObuabm85p8p91up50Pp/oniGwNl1mGMzTBnL6c5hmPibrnl+BFoN5x6b8no2Xz2LyFm48j8uA3XNzP0+qcN6L1zLmJmd+7uJzphjvU+FrQirvMbmGLHXHfOHfbcrMszHczA0N6aYc5Ned6/k2ON7dWs0acdsxu7vbM3fhkREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREskXHYabnOcbufe3L42Whru7u9d3e8REk/8AC3I3P7zy3M3DczYiIiIiI/JibGdm4zLHBq+vO5mdz5H/ANJnafo5dePS+WnOv1NMwznd3dMzLbTnX4mm4bzm5uG5v6j7Bo8Ot1geW63NDeeNzTbINHh1mMDyzGZi7xzu67/4G+5RoI5jMzk3ne36vkREREREREREREREREREREREREREREREREREREREREREREWpb4HHHP8Am/TddMbpERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERHg/ueTOZvmtBud8vc8mc3fJYTM7Z86z9uNxgzyx0M77u9/TufybPIZun7S6P8AKOH1ksVmDvGO7nW4fWS1W4Ocabm9PASIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIt5nC3VjGmDOXfjnMMzhERERERERERERERERERERERERERERERERER8maTS55umdQNDRuaM59P52R7l4dGbtx09l+YnaomnkHdddw4zTuekSIiIiIiIiIiIjSa3PJ03qBiYMzFnERERERERERERERERERERERERERERERERERERERERERERERERERERERFsOHrOrmbcTT9+YCIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiI/Sn7uFJehmI7zrvv8kCvfy+kzcMZua5vXptwNlXA0d9Du49XBnXwZq/ZsO/mLcTczj35+I/b6fbOZwO11F71DwvN5NnlIzD9pdH64BEREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREREX1tRkfsLOHGsREREREREfFzvU0Py6M3Tjp7eHif+3wn7EXs+ssTOsFxedN3p28l5fOc7IXzFZmY7xnO51uVkL5qtzcc43nN6fp77/tBc75E1vLqPf4OALuFFt0YHL/ALru4+HcceNJZg6Zju5zvFxx40luDjmm5vOceDfY6m+Oo0R333fX2z4MOYPON/c3pu446XpkXAmzoaY7wgvHIczZXAmzoY45wiPHAM3PVupWwb3Oxh0Zu5nu9/Yz5ciIi3zqxxhsZ06f5Z0EIiIiIiIiIiIiIiIiIiIiIiLIenXGGVvDp/hvUQiIiIiIiIiIiIvYTEQY4xmZxmZ0iIiIiIsQxgdNzzzf5w3N5zc3M3MfNPlgd3XTDMPLMzMztF1AN/COwG8adNiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiItop7JwekZrrT9nIBERP2UtuYO7/Xvu5mO7mREREREREREREfB/3X+y8j3+D1xgrM5EN1Dst5zzx8UzuRsEzc1oGv8AA6PxdSDfwrtFvOnXfiN+hw2OmZzvGbv29Qa3bNO7Zu4bhx23N3Nzvm78mRERERERERERbjuZ1zTkzkzgs4cdUiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiL7XgftR5F5c9yIi/gMYOxqPHcbERERERETvocdhpuc5xu594iIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIi07PxSNmOZg4f8wdWRERERERERERERERERERERHg+2o8O4PGbv7O9M3HTU+Nkd28/Dcz+zdzHc0xZC9lnO8bhuNbnXM3Tz3r8f/JxY6dhE4+S3PDdVLWOs5M+3XTM3c9GdlaPeQd113DjNO/orArEdlY0zpu5meb2Xnv5Purpk6HtPLDOfW2rZLdzFvUfvzm45gHWvOAdZ7rmmtGdMd3eOd3r4F3B2LyhdMOO7xn4f6u1xc9Fe/TwDMMQb6IY0cGcDcaYOcnBMd56Fp1EzODNzDOmfpJ3BWLyBddGObxv6EdwVm8wXXRpucfG9ihQRxGZnBnGdvGuS5LscJvA3jTp+gHelZuwN0w6ZnHojkuS7XIbwt506/k/qzxffAeEb+7PF9sE4U8b+z4oLrsRzjHfLPjf1RoGXudTnpUiz/wCdfxmZju7vGZm7pmWPNtsxp00NzHXHN3nNzrm+kfaM5guDguOenX4SgsOm4GJHC6GgwHNwPDXSZsewgZuYAfOZAEgbuzUbm5p28uNW+juxQ/Cjc3Rnlutzg3njc027iABK0x3d3nR3d6+RmeAERERERERERbV4WNDrczG4m/fnNdbmkRERERFqInglrMcwOH/MHVkRERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERExBeDHN3TDd0zN36ZsRHyWCTGY35Huzu9B9I8RaJ5i/Les23c3jNPpxpjN8BNZXDhMNbuGjOH043TNfl37xo6HsuHJ1PH/AHx2OMzyGF3e2XsnmAd1vmDvLXc+E5BeTHNzTTNxzdz6bv5CIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIvtYRS+2t58a8xERERERERERERERERERERERERERERERERERERERERERfuijoey4cPUiIiIiIiIiIiIizs4w0BkZ3XTv8Z0EIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIj5bXxDhrdG+yGcNM8zXwt0xaXPezToOOxMcxzwHAw/ZNCY8szp39Ag5f6YTuYLkY6Z1Ll/pgO7iuVhpvR8FIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiLpy1ue9umchjtDHdMiIiIsR7WmtXfL8XPkdUwiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiLV5dp1buYbpx2zM3d3tmbsREREREREREfG37bxS1mOYHD/mDrwTekZeEM4LvcWNzeDnFza3+LWL5A03nE+fzxM3jmHB1M5LOXPR+S+kh8s+znzdThv20N1t8lwE4fldbjKegNab0zdzTM7ry3xXBM/Sxjm9SzTenG5vluWhe+zu572x/ozyzMMz8zK7rNyNz+88tzNw3M31B/wCnt3S9z3OnH4dH+azOQdZiHdbzvnvhPlfQc9u5+znTd014PmwaxyA3dubhuYdN69Ln8zADNwa3obuc9eLOu/8A4yH/2Q=='),
    ('종이', '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wgARCAPoBkADASIAAhEBAxEB/8QAFgABAQEAAAAAAAAAAAAAAAAAAAEH/8QAFgEBAQEAAAAAAAAAAAAAAAAAAAED/9oADAMBAAIQAxAAAAHVhhoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAASgAAAAAAEoAASgAAAlgsCygAAACUAIFlBKEoAAlhUpKBKAEolAEoSygCUAJQSgAAAAAhQAEoBKCUAEoAAAAAAAAAAAIUAAhQEFIUAAAhQIoAAIUCWFABKAAEoCFAIUACUCRRSWFSgAAAAABKEsBQAAQJVAAAIUhQABBLQhQAAAJQABKCUABCUJVAAAAAABAEpUqFAAAAAEJVACFSkqFEABUoIsBQAhRCVQQFJQJCgFEsBUoACQpQAEoEpKAgUAASkBQAhQAEFgVBYFQAVBYFQWBYFgVBYFQVAsFQAVBUFgVAAsRUUBUFQVBYFQLBUFgWBUFQWEVFVBUCwLBYFQVBYCwALBUFQVAsACwVABUFgAWBURYUsFQWBUFQWBUFQVBUFgVBUFgAVELFVBUFgLBUFQVBYFQLBYFQLBYFgVBUCwBAUAAAAAAAEBQQFBAAUAEBQQFAAABAUAAAAAAAEBQQAAFBAAAUAAAAEBQQFAABAAUEABQAAQFBAAUEBQQAFAABAUEABQAAAAAAAAAAAQAAAAFABAUEBQQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAASgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEsACwLAsoShBSBQlEAqApLAspLBUBYLBYFQLKAQFiksCwUgWAAFiiAspAAFCAAsAACoWKRQAgKgoQoQLKQAFgKgAqBRKCURYWBYoiksFgUEUQoQAAVAKEFgWAsCoLKSwAAAFCWAFgFgWFlgKEoIWAUQpFgBYAACwAAALAABUAFQWBYCwWBYAFQALABYFgAAVAAsACwVBUFgLAABYAACwLAAAABUFQAAAALAsACwWBYCwAWAABUAFQAWAAAABYFgAAAVABUFQWBUFgALAAsAACwLAsACwLAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABKEoAAAAIUAhQAAAoIAASgAAAAAAAAKIUICiJQEoSgAhUoSgAi0IShKCFAAAAAAASgAhQAAAoIAASgAAhQAAAAAEoAAAAAAASghQApKgi0iUAAKCAoISgAAKCAAASwWBUFQAtQlIVAsCwVC0iVBYCwWABUFgVBUCwAVBYCwWBUAFgVAsFgVBUCwVABUFILBUFQVBYFgWBUCoVAsFgAVBUAFgLBUFihC2CAVBYFQAVBUFgAAWBUFQVBUFQCksFlhYAFgLAAsFQVBUFgVCglQVBUCwAVBUBYAKgAAWFgAAAWAAAAAAAAAAAAAAAAAAAAAAABYAAAAAAAAAABYAAAAFEABUAAABYAAAAAWAAAAAAAAAAAWAFgAACkAAAAAAAAAAsAAAACwAAAAAoAAAQFAAAAAABAUAAAAAAEBQAAAAQAFAAAABAUAAAAAAAAAAAAAAAAEBQAAAAQFAAAAAAABAUAAAEBQAAQFAAAABAAUAEBQAAAAAAAQFAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAApAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgKCAAoAICgAAgAKCAAAAAAAAAAAAAAoIAAAAAAAACggAKCAAAAoAIACggAAAKAACAAAoAIACggAKACAAAAAAoIACggKCAAoIAAAACggAKACAAAAAoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAogAAWAAAsFgAWAAAWABYWAAAWAAFgCkKIAAAApAWBZYVAsAFgAAWWBYCiAsFgACkWAogLAAsBQQCkABUAAApALAWABYWAAKQAAAABRFgAKQAACykAAAKQFgFEAABYpALKQAApLKQAFiiAKJYKgsAACoCkWCwAWWFlgAoQFgAALBYFgAWWFgAVKRYALKQFgLAWABYAACkAsCoAVAAAWAAFlgWAABYCkAABYFgCkABYAFiiAABYpACkAAAAAKSwLAAKQoikKQApAFhYACoAFgAABYAAAACwAAAALAAAAAAAAABUAAAACwAAAAAAAAWAABUAAAAAAAFgAWBUACwAAAAAAAALAABYAFgALAAAsAACwAAWAAsAFgAWAABYAACwAAAAAALAsCwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJQAigAEoAAJQAAAAAAAIVKJQASkoSgBKhQAASgAAlAAAhQECoUACUAAJQAAAAAAAAAAAAlAAhQSgAAAAIUBKSygABKACFBKBKECgSiUAAAAAAASoUABKEoAAAIKAAAhQSgAAIUAEoACFAIUCUECgAAAAIUCWFAAAIUEKCCgSgAAAhQJRKAhQEolAAAAAAAhZQBKACKAJQBKEqFABKAAAEoACFBKACUAAAEoSgAhQCFAAIUCUEoBKAAACWFAAAAQLBUFQVBYFQVBYFQVBUFQWBYCwVBUFQWBUCwVBYCwVBUFQVBUFQVABYFQAVBYFQWAsFQVBYFQVBUFQVAsFQVBYFQVBYFgVBUFgVBUCwLBUFgLBUFQVBUFgVBUFQVAsFQLBUFgLBUFgVBUFgVBUFQVBYFQVBUCwAVBYFQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABBUogWAsFRFRVlhSFQVBUFQAUhYFQVBSFQLBUFgUhUFQWBUFQVKIFQWAsFQWBUFIUhYpLBUFgWBUFlhUAFIUhUAFlBBUFlhSFQVBUCwLAsoSiBUFQVBUpLAsFQWBUFIWBUFQVBUogWBUAFgLKIoShBUoQLBUpAVAsFQVBYFQAACkAKQpAAACkABYAAAAApAAAAWAAAAAAUQFQLAAAspAAAAAFgsCwAFgAAABYpAAAWKSwAAAWAsACwAAACkWAAAAAAApAAALAWAACwAWAAKIAFgACkqAAAAogAAACxKgAAAAAsApAAAAALBYAApLAAAAAABYAAApLAKSyiAABYAAAABYALAABYACwWKQAFgFgAAAsFgWWAAAApALAWFgAWAKQAAAAAogFgABUAAAAApFgsApCiBYAAACwFgAAsAAAAAAAAUEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABQQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFBAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAhQEFAAAAAAAAAAAAAAAAAIUAABKAEoAAAAAAAIUAAAAhSFAAAAAQUAABKCFASgAAAAhQAEoIVKCFAAASgAAAAAAhUoAAAAAAIUAAAAAAABKAAAACFABKhSCgAAAAShKAAEoAAAAlCUSgAAAAAABFAEoJRKAAhQAAAJQlhZQASgAEoJQIUEoAEFlAAAAAEoAJQASghUoAAIUBKAIFAShKEoAIUAAEoCFAABKAAAAhQAJQASkoCFlAAACKSgAAiiUAAAASgAAAlAAhQJQAAAlACUAJQSgABKAJQIKAEUAJYUAAhSFAAASgAAEoAAJRKEsoAASggoEoIUhUpKBKAJQBKhUFSgEoJQAAQKhQJQBKAAAEoAJQAAAAABAAAAAAAAAAWAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgLAWAAChALAKIAAABYLKQpAAACkAsApFgAAspCkWAAABYAKhUAACwAAAFgKSykBZYFhYABYALAsFgCkAAsFlgAWFgFgAqAFgFgKRYAAAAKgWAApKgsCwWAqFgAAAALAAAABYAFgCkAAsAAACwLAsAAFgAAWABYAAAAAAFgAWAAsCwAAAAAAVAAAAAAAAAAAAsAAAAAAAAAAAAAAFgAWAAAAAAsAFgLAAAABYAACwAAAAAAAAAWAAAAAsAACwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAoIAAAAAAAAAAACggAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKCAAAAAoIAAAAACggAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQFABKCBQAAQFBAAAUEAAAAABQASggAAUAEAABQAAQAAAAFBAAUEAAAAABQAAAAAAQFABAUEABQAQFABAUAEBQAAQFABKFgShYAEAABQQAAAFBAUEBQQFCLQgEooCUEqAoASBaSghZRKAhQCJZRKKCCLQAhKSgAAAAASiUSgSgAKAACJQCygCSigAJSEoCpQCAACLUFAQWUSgSoSqAlIACggKBKAAIItSghZQlEqJQpLIFAoiWUCLQkooBCKhQoACUggooiUCUJUEoABKCUEFAAlAAAhQAAAJQAQUAAhQAAEoAABKhSFAIWUAAACFIVKAJQAASgAABKAAAACFABKhQACCgAIWUEoASgAABBQCFAIKAAABBQAJYUAhQJQBFi0IAAAAABKAi0IQtQVBYFQVBUFgVBUFQVBUFQWBUFQVBUFQVBUFQVBUFQVBYCwLBUFQLBUFQLAsFQVBUFQVBUFgVBUFQVBUFQVBUFgVBUFQLBUFQVBUFQVBUFgVBUFQVBUFQLAAsFQVBUFQVBUFQVAsCwVBUFQVBUFQVBUFQWBYFQVBUFgVAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAAAoIAAAAAAAAAAAAAAAAAAAAACggAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKCAAAAAAAAAAAAAAAAAAAAAAAAAAoIAAACggAAAAKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB//8QAFBABAAAAAAAAAAAAAAAAAAAA4P/aAAgBAQABBQJDUf/EABQRAQAAAAAAAAAAAAAAAAAAAMD/2gAIAQMBAT8BROf/xAAUEQEAAAAAAAAAAAAAAAAAAADA/9oACAECAQE/AUTn/8QAFBABAAAAAAAAAAAAAAAAAAAA4P/aAAgBAQAGPwJDUf/EABQQAQAAAAAAAAAAAAAAAAAAAOD/2gAIAQEAAT8hQ1H/2gAMAwEAAgADAAAAEPPPPPPPPPPPPPOPPPOPPLPOPHPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPOPPPPPPPPPPOPPPPPPPPPPPPPPPPPPPPPPPPPPPPNPPPPPPPPPPPPPPPNPPPPPPPLPPPPPPPPPPNPPPPOPPPPPPPPPPPPPPPPPPPPPPPPNPPPPPNLPPNPPPPPPPPPPPPPPPPPPPPPPOOMMNOMPOOOPOMGMFONNPPNNONMPNMMOPMMPPPMMOOONONPNMNNNPNNMPOMNOOONOPONPMENMPMNMPMFMNEMOMMMMOPNPNLFPMNNMIEMMMAMEMGJAEEEMMIEGMEIEIMEAEMIMIEAEAIMICAEEMMIEMEIAIEIAEAEMAAENNAIIMMEIAAAEMAEMEMEAIIEMEMIEEAIIEIEAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAIAAIAAAFLKAAAAEAHECCAAFCICACEAIKAEAECAAAAABAACAIEACAAAAAAAAAAABAABADBAAABAGAABAFAAIAAIBABAAEBgFCAAAAAACCgAAAhAAABBAAAiBAAAAEAAIEAAkkAAAAAAAgoJAAAAAAkABCJAggIGgABAkAgEBogCgIABoAAICIBMAAIgABAADHDHDPDHDHHHDHDDLDPDDHDPLjPDDDHDLDHHDDHjDDLLHDDHLPLDDDLPLDPDHPHDnLDHDDHDDDDHDDHPDrDDFLDBDHDLHDLHHDDLPvPPPPPPPPvPvPvvPPvPuPPPPvPLPPPPPPvPnvvPvvvPPPPPvPvPPNvvPvvPPPvPvvPvPvvPPPvPvvPPPPPPPPPPPPvvvvvPPvPvMssssksssssskssosqqssssstskossssssstssssksssspsossssssssssssksssssusssksosssssstskssksssksssskssssssgwQQQQQQwwQQQQwQQQQQQQQQQQQQwwwQQQQQYwSQQQQQQQQwwSQQQQwQQQQQQQwQQQQQQQQUQQQQQQQQQQQQQQQWQRwQQUwQQQQQbPLLKCDBskvJurKrDtLHjKAPGrrhNPPGHqPPMHPLvvpGMgnpoujKPPHJPJMIEtnGmLHgsuDPPjODHHrJqLPPPMFPHNNlOCBHMuNPnefbfefbffTfTXXbXXfTfbfXXffTfbfbTTXbffXefbZffffTTfffebbebXXbfXffTfTfXffffVXfffTfTTXTXfbfbffbbbebbfffffXfffdffffffffffffeffffffffXfffffffffffffffffffffffffdffXefffffbXffffffffdfXfffffdffffffffffffffffdeecfdcdeedfcddecccfffcccfcaeceeddeedcdcVaadYVdfVcfcdefeecfceeedccdccefcfcddffceccccdcecdccdYfecWfYccQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQUQQQQQQQQQQQQQQQQQQQQQQQQUQQQQQQQQQQQQQQQYQQQQQQQQQUQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQSSQQQQRQRQQQQAQQSQQQQQQQQQBAQBQSSQRSSQRASSRQQQQQQQSQRQQQQAQQSQQRQQQQQQSQQQQQQQSRQQCVBQQQAYASQQQAQQQbXTTfDRTbbTBTXbXfTXTTbfTXbXTfXTbXTTbTfTRbTTTXXXTZTbXfTTfXbTWTHfTXTfTTXffXTTTTTebVXfXbfbTTTXTPTTTbfTTdfZffdXfffXfffffffffffffffffffffffXffffffffffdffffcffTfffdfffffXffffffffffdfXffeffffffffffbffffbfffffPPPPvPPPPPPPvPPPPPPPvPPLPPvrPPPPPvPPPPPPPPPPPPPPPPPvPPPPPvPPPPPPPPvPPHPvPPPvOPPPPvvPPvPPPNPPPPvPPPPPvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvtvvvvuvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvnvvvvvvvvvvvvs8s04kg8koowyg00ww44w84w8800oww484w0w8gw8mw0xwss44g8844skg04wsk88g00go8448w8s44k8o44kww408k44gk48440gggggggkgggggggggggggggggggggggggggggigggggggggkgggggoggggggggggggkggggggggggggggggggggggggkgggggggggAAAAAAAAIAAAAAAAAAAAAAAACAAAAAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAACCAAAAAAAAABAAAAAAAAAAAAAAAAAAAPOHPPHPPLHPHPPNPNHPPNPPHOOHPPPOPHFDLPHPPFNOHLHPONOHLPLMDOPPDPPOPLNPNHPOPPPPPMNPOPPPKPPPOPHMPPPGPKPPOKPPGHOFJLPPJONLPFFPIPHPPLHHPFHPCNPKPHLNPNPPOPLJPDPPNPPFNPPNOPPPHHOPPHPGHPPGPOPPPPPOLLPOOGOPOPNHPJPNPOMEPNOMLPONOLMPOPMPMPNAOONOIMMNNPNMPEMOCMPONPPOENFANLPNMMPOPMIOOHMEPJOMJNOJMMGPKPGPENPEOOLNPMOOPIIJMAAHFLDDFFFGBPGCJOKCKIJLJCHAFNDKEKGJCMHBNKANCGFMPJPHNPDJGHHJLAPDEDBLCEEOEDHPEFJKJHPAMPEEJFANAHLLNHMJDMBFEJKFAAPINJOOHALHOAJDFGLAHPBFBGDLNCGDGAAGDBCMNHHEIIEJONBGAIPJLLHLCLOBDLBEEDLNOHIDGKHFIDILCLLDJKPGMAEAGAAIAAEAAAAAAABCEACIIAJAAAIAAEAABADJAAEAAEAAAAAAAAAAAAEABAIAAAABACKAACABAICDICEAAAAAAAJAACCAAABIAABAIQQBQAYQBQBQEDYQQQABAVAQQRAOBYCAAARAEIRQSEAAQQQQBEAYQGQUQIJAQYQQAYARQYAUAAQCCABQRQABAECAIAAAFAAAACbTTTXTTXTTTTVXbTTTXTbTXbTTTTTTTfXTfTXTXbTTXTTTTTbTTXTTXXTTXTTbbTXbTTTTXTTTTbTbTXbTXTTXTTTTXTTTbfTXTffffffffffffffffffffffffffefffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffZccdcddeYfceefXdcdcedefeccdcdcQdcedcecceccdWfccdcecceYcecefccceececYcfdedYccccYccefdcccdcfbdcccdccdeQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQYQQQQQQQQQQQQQQQUQQQQQSQQQQQQQQQQQQQYQSYQQQQQQQQQUQQQQQQQQQQQQQQRQQQQQQQQQQQSQQQQQYQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQRQQQQQQQQQQQQQQQQQQQQQQQQUQQQQQQQQQQQQQQQTSXXbTzVRTTTTfRXTTRTbTXRTTXTTSXTXbTXTRRWbTXXTVTfRRTfUTTVRTTTbbaSXTTTSbbTXTRXTTTSXXTfXaWSTSTbSfTbTTXTffefeefffeffXffffeffffXfffffcfTbffafffffdbbfdffffWfffWbfffXbfbfffedffffffefffbdffbfXfeXfXfeZfffeXfffe5//wD/AP8A7+//AP8A/wD73/8Au/8A/wD/AP8A/f8A/wDu/ut//wDf/wD/AP8A3/v/AP3/AO9v/wDf3/8A/wC99f8A/wD+/wC/d/8Af7//AP8A/wD7f3//AD//AP8A/wC97++33/8A/wDv3/8A7w+y74ww0X03w53yw597x/7x4580z6z/AN/c/vf+sfs8/wD3TDPLvT3P33bTDh/bnXT3nfLz/Dnzj/PvHr3Xn/zXXvXnB/8Ay4289/y382729257789y958x57089187992x+89047+/0xx112/x360/6002765y7+88w809198x/wA//vv+s/tv9vd8dfte/tu9Psv/AD3rfLvLzTj3jPjDTjzTDTTDTzzzjTjnTzj7zLzzzjTzjHTTjTXnzTzjzvDDTLnj7DjTT3Dzb3LnTjD7jDDjjznrzjjzTDnjjTjTjzT7TjDzHDDnHjDDDDLLDDLDDDDTTjDDDDDDDzDjTjDHDDDDTXTDLDDjTHDjDPTDDDDDjDTDLHLDDHDLDfDLLLDHDDDjHDDDjDDDHDDTDLjHTDDDbjDDbTDDDDjDDDTDHDTDDDTDTDTLDDLDTHjDzDXDDHHDDDLDDDjDDTjrDDLHjLHHLjLDTDnPLDjTDDPnDTDjDDDjDTDDDDDD/wD/AP8A/wD/AP8A/wD3/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/APf/AP8A/wD/AH//AP8A/wD/AP8A/wD/AP8A3/8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A9/8A/wD/AP8A/wD/AP8A/wDf/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD9/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wDPPPPPPPPPPPPPPPPPPfPPPPPPPPPPPPPfPPPPPPPPPPPNPPPPvPPPPPPPPPPPPfPPPPPPPPPPPPPPPPPPPPPPPPPPOPPPPPPPPPssMMMMMOMMMMMMMMMMMMMMMMMMsMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMcMOMMMMMMMOMMMMMMMMMMMMMMMMMMMMMNMMMMMcMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMNMMMMMMMMMMMMMMMMMMMsMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMN+/f8A/j/v7f8A/wD/AHr7/wD/APv+/vf/APr73/8A/wDf+c//APv/AP8A/fuv9fd//f8Avvf7/wD71/8Ad/f+f9/fvf8A/wD/AOff/ue+9+d//wD/AP7/AP8A/wD3/wB/v/8At999vtv9/d//AHf3f/fff/3fXf7b/f8A/wD9/N9/99//APff/fb/AP8A/wD/AP3/AP8A/wD3/wB9f9d9/wDffb/3b/fff3//AG/3/wB99999/f8A/wD/ANt//t/9155p59173x9z5x59x55xV7z9551x9/8Add98ce88+eYcfeedf8deddddd3ccefcfdf8AX3n/AN9/51955x11z5195xx995xx99Zx95xx51RR5pQtl9FhRRNJ59JoVd9BZJp1JBN5NVJxxVZd9Zhth5RF1BBpxt9ZFARVFpdMddRpJFAdt5R5RF9pxx5NJxxNJ5Z5t5ZJ5JttN9pvB9mL591fVfTrVv8A+57/ANX16d+MFEd/8V03ftM9ME8MGud8/ctmmVGFXU911fWusEWdE3N33PF33Nk0Yn7XX8NuU9/e8n93uU8EQEGABAkAAMAgRCAQAVGAEQAEmEEEEEElGEkEAAAFECAGAABEkBAEEEQwAxCAkgBEEAEACAAEQgRBCUAsEAVEQGAA2UAABEWAUFFMsMONM8MNMMMcMMMNMM8MMcMMMsMMOccMdMMMMccsNMMMsMMMsMMMMcMOcMMeMMdMsMsMMM8McMeMMMM8MNcMcNMPYMMMMMMOMYM445444544444454444444444445664464466444444544444444544464444444544444467644444444q6444444444554445477777777767677777777777777777777777777777777777777777777577777777777775777757777777777777777777777777/AP8A/v8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AL//ALv/AP8A/wD/AP8A/wD/AP8A/wDv/wD/AP8A/wDb/wD/AP8A/wD/AP8A/wD/AP8A/wD/AL//AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AO//AP8A/wC//wD/AP8AKDCSCLCCCCCCCGDCCCCCCCCCDCCCCCCCCDCDCCCDCCCDCCCCDCDCCCCCCCDCCDCCCCCCDCDDDCCCCCDCDCDCCDCCCCCCCCSDDCDDDCCCCHCCCCCCCLDDDCCCiDCCCCDCCCDCCCCD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'),
]


try:
    from photo_walls import PHOTO_WALLS        # 기본 배경 사진 (퍼블릭 도메인)
except Exception:
    PHOTO_WALLS = []


def photo_wall_path(name):
    d = os.path.join(CONF_DIR, "backgrounds")
    os.makedirs(d, exist_ok=True)
    i = [n for n, _, _ in PHOTO_WALLS].index(name)
    path = os.path.join(d, f"photo_{i + 1}.jpg")
    if not os.path.exists(path):
        with open(path + ".part", "wb") as f:
            f.write(base64.b64decode(PHOTO_WALLS[i][2]))
        os.replace(path + ".part", path)
    return path


def photo_wall_thumb(name, w=72, h=45):
    pix = fitz.Pixmap(base64.b64decode(next(d for n, _, d in PHOTO_WALLS if n == name)))
    pix = fitz.Pixmap(pix, w, h, None)
    return tk.PhotoImage(data=base64.b64encode(pix.tobytes("png")))


def wall_preset_path(name):
    """기본 배경 그림을 설정 폴더에 꺼내 두고 그 경로를 돌려줌"""
    d = os.path.join(CONF_DIR, "backgrounds")
    os.makedirs(d, exist_ok=True)
    i = [n for n, _ in WALL_PRESETS].index(name)
    path = os.path.join(d, f"bg_{i + 1}.jpg")
    if not os.path.exists(path):
        with open(path + ".part", "wb") as f:
            f.write(base64.b64decode(WALL_PRESETS[i][1]))
        os.replace(path + ".part", path)
    return path


def wall_thumb(name, w=72, h=45):
    """빠른 선택용 작은 그림 (tk.PhotoImage)"""
    data = base64.b64decode(dict(WALL_PRESETS)[name])
    pix = fitz.Pixmap(data)
    pix = fitz.Pixmap(pix, w, h, None)
    return tk.PhotoImage(data=base64.b64encode(pix.tobytes("png")))


def main():
    if sys.platform == "win32":
        try:   # 작업표시줄에서 python 이 아닌 '스마트PDF Editor' 로 따로 묶이고 아이콘이 보이게
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("smartgong.smartpdfeditor")
        except Exception:
            pass
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
