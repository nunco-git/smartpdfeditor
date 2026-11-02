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
}
NEUTRAL = {"bg": "#f0f0f0", "fg": "#1f1f1f", "accent": "#cfe3fa", "field": "#ffffff"}   # 도구줄 아래(사이드바·상태줄)
THEME_DEFAULT = {"preset": "clip", "font_family": "맑은 고딕", "font_size": 9, "fg": "", "bg": "", "accent": "",
                 "canvas": "", "wall": ""}
FONT_FIRST = ("맑은 고딕", "Malgun Gothic", "나눔고딕", "NanumGothic", "나눔바른고딕", "굴림", "Gulim", "돋움",
              "Dotum", "바탕", "Batang", "Segoe UI", "Arial", "Tahoma")
AD_W, AD_H = 250, 250     # 광고창 기본 크기 (사이드바 폭에 맞춘 정사각형 배너)
AD_FILES = ("ad.png", "ad.gif", "ad.jpg", "ad.jpeg")   # 실행파일 옆에 두면 이 광고가 우선 (시험용)
AD_LINK_FILE = "ad.txt"   # 첫 줄 = 광고 클릭 시 열 주소
AD_URL = "https://smartgong.kr/ads/smartpdfeditor.json"   # 인터넷 광고 설정
# 사용 통계 — 설치된 컴퓨터 수만 셉니다. 보내는 것: 무작위 번호 + 프로그램 버전 (하루 한 번)
# 환경설정 → 일반 → 「사용 통계 보내지 않기」로 끌 수 있습니다.
FIREBASE_DB_URL = "https://smartexplorer-d569e-default-rtdb.asia-southeast1.firebasedatabase.app"
STATS_APP = "smartpdfeditor"


def stats_call(url, method, body):
    """Firebase REST 호출 한 번. 실패하면 예외 — 부르는 쪽에서 조용히 넘깁니다."""
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method=method,
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": f"smartpdfeditor/{APP_VER}"})
    with urllib.request.urlopen(req, timeout=8) as r:
        r.read()
AD_CACHE = os.path.join(CONF_DIR, "ad_cache")            # 인터넷이 안 될 때 마지막 광고 사용
AD_REFRESH_MS = 3 * 60 * 60 * 1000                       # 3시간마다 새로 확인
APP_VER = "1.0.4"

# 스마트공 로고 (PNG, base64 내장)
LOGO_PNG = (
    "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"
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
        "Ctrl+Shift+S — 다른 이름으로 저장. 원본을 남기고 싶으면 이것으로 새 이름을 정하세요. 저장한 뒤 탭은 새 파일을 가리킵니다.",
        "Ctrl+Z — 되돌리기 (최근 30번까지). 저장하지 않은 탭 이름 앞에는 ● 표시가 붙습니다.",
    ]),
    ("화면 구성", "m_view", [
        "위 도구줄 — 열기·저장·되돌리기 | 쪽 이동 | 확대·축소 | 회전 | 편집 도구 | 오른쪽: 뷰어/편집 전환 · 사용방법 · 스마트공",
        "왼쪽 사이드바 (F9로 숨기기) — 즐겨찾기 · 북마크 · 최근 · 검색, 맨 아래 광고 칸(광고가 없으면 접힘)",
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
        "여러 파일을 탭으로 엽니다. 탭 이름의 × 또는 휠 버튼 클릭 · Ctrl+W 로 닫기",
        ("키", "Ctrl+Tab", "다음 탭"),
        ("키", "Ctrl+N  ·  Ctrl+Shift+O", "새 창  ·  새 창으로 열기"),
        "탭을 오른쪽 클릭: 다른 탭 모두 닫기 · 이 탭을 새 창으로 옮기기 · 파일 위치 열기",
    ]),
    ("즐겨찾기·북마크·최근", "star", [
        ("키", "Ctrl+D", "지금 파일을 즐겨찾기에 추가"),
        ("키", "Ctrl+B", "북마크 추가 — 글자를 선택해 두면 묻지 않고 그 글자 이름으로, 그 위치로 바로 추가"),
        "더블클릭하면 열기(북마크는 그 쪽·그 위치로). 폴더를 만들고 끌어서 정리합니다.",
        "줄 끝 × 로 바로 삭제 · 오른쪽 클릭: 열기 · 이름 바꾸기(F2) · 삭제 · 새 폴더",
        "Ctrl·Shift+클릭으로 여러 개 골라 Delete로 한꺼번에 삭제, Ctrl+A 전체 선택",
        "목록 위 🔍 칸에 입력하면 이름·경로(북마크는 쪽 번호도)로 바로 걸러 보입니다. Esc로 지우기",
        "[최근] 탭: 최근 본 파일 200개 · 마지막으로 본 쪽 · 열어본 시각 — 🔍 칸으로 파일 이름·날짜 찾기",
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

    def __init__(self, master, on_change, hint="이름·경로로 찾기"):
        super().__init__(master)
        self.var = tk.StringVar()
        ttk.Label(self, text="🔍").pack(side="left", padx=(0, 2))
        self.entry = ttk.Entry(self, textvariable=self.var)
        self.entry.pack(side="left", fill="x", expand=True)
        self.count = ttk.Label(self, foreground="#666")
        self.count.pack(side="left", padx=(4, 0))
        self.clear_btn = ttk.Button(self, text="✕", width=2, command=self.clear)
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

    def __init__(self, master, data, on_add, on_activate, label, on_change, add_text):
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
        self.filter = FilterBox(self, lambda: self.refresh())
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
                    if searching and not inner and not flt.match(n.get("name")):
                        self.tv.delete(iid)          # 맞는 것이 없는 폴더는 숨김
                        del self.map[iid]
                        continue
                    shown += max(inner, 1)
                else:
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
        put("", self.data)
        if flt:
            flt.show_count(found, count_items(self.data))
        if sel_iid:
            self.tv.selection_set(sel_iid)
            self.tv.see(sel_iid)

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


# ───────────────────────── 아이콘 (tools/make_icons.py 로 그린 PNG, base64 내장) ─────────────────────────
# light = 밝은 바탕용(진한 선), dark = 어두운 바탕용(밝은 선)
ICON_DATA = {
    "light": {
        "open": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAB4ElEQVR42s2UPWvUQRDGf7O7/3vJ5S6JGlNoJYithYWIkHwA29R+BW21OPIJ/A4iiIWFoIWV0QNtDHaWmkKDBIx54XK52//uY5FcopiEC0ZwYGBgZ5955pnZhf/dbBjo1Wz443RxLtvCQj7VimrjTpIf9tjVeivc8Y5aSqasrMZ44bqb8ZndfvNB7bYblakB6PnNqf6WX6u2KhAFCIIjbse1MuZb9Svd93y6ZEyvHg069zqZoV3doldK+j7YjBNlkkAGpFo9TMWoq3Zt6R0sjd7yMDYjADIzk/BlzBi61300e8EZ5WH0JKkxFtgp48PafGc5HD4JYYaVpagEuxjq4f6RlLKgESi/9TpmfA6HyurDvsCDjAZd0jFd5ppwRWu6vv727pnwG1BO+OnL+NYMpBLMhrjhON2SlKuN+mPXi08PEpWxooZrngfzEE6wfsrgfdNZfLl3axJywhpnwReQE0gjuXJW8N6l7f6PvnY6BzScxzVnQL8+yFE22bKNVQB1GjcefHUA68uLWL2VrNpMqEzCkmAkR0pAwipP9vfQdjbMNWcmaY65YtAHO4F+WZ7CiGtfVvYBJ67Px1g594Kt7fFYJg3HOwIauJCL3rpLqx83/vF/qLb7O6QF2e5IT9d+Akb68RwAWZn8AAAAAElFTkSuQmCC",
        "save": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACkklEQVR42rWUwWtcVRTGf9+5981MxmliLcFViQgVa1GQ2YgrF67cuTCEdinUhUt3boII0Y1/gK5cdNEm+AeUClXahYUOiEVBsLEl1raBTpuUTiZ5993jYiYxyUxiKXjgbg7nfu98v3veEbtj3o27nXC2DWfbbTqMRhvo0OGjb6Ddhs73y5ml2Wq00l08a+y6G3cSkr+6cPOVVR2dPf26hTNvHtGjfh4WAAatmlGLcHW5zxeX17xRxKosNy/dka6BC+SReTeEz3z598mtonbFaB5rtOpMPQ++aZggAP0EX11xTkyLUy828TpYIWKsf3584a+5lU91gUUP1r7bCSDPuZrTxNSx/Ph+v7/+KK11q7TWLdNat0zrD8vUfbCVfvj1Trr++2raWO+l3Oum1Ov2JeHGxwAsLf3rCJlTlY4UQTEjHOGA77gWSENkQiA8I6ncy3BHVHKgCOK5mihdhKFlE7w10+DEdEERdr+fwNFYQXeIJu49Tlxf2eRJmbFdd9872aQWxW/3tog2/sH3CGZ3GoW4+mefH5c32D9Heeg9mmgUoqp8pCbu/4IEG6WzVfnouA0M4jgmmKzp8A5N0Cudd15u8PZMnezssbzdpQluPUx8d6OHHSRoBinDVN34+v0XODph//mD3HyQuLbqtOxAhjBRCNNA3H2AgDEso8FkXQOuOoRh9gGraIcLmmAMZsb6etotocPGRu4O7nKq7e1xUIc+tCmo9mtb593lDBALv0iV5I3JenMiBCCYEWD0hGE+11o1q7dCUHUOgNemFZmdrZh3++MT/fTSwu25++nIh0u/KJx+o6k8hsl27sZq6T+v9Kriycb5M+Xxbz8brMDE/xuLHlj04P5054NFD8xf3jMp/wA5AC7ymd2FVAAAAABJRU5ErkJggg==",
        "save_as": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADU0lEQVR42pWUT2hcVRTGf+feOzP5PzOxIRKigmizUYrMwiCRgQoW0Vq6MFREcJG2IUG6cOE/JIogCEVFEKzRnVA62dSFgmCtpVjUGEFEm4WJEWtbU9NJ0kwymffuPS7eRCc1UXrgPO57vPNxvnO/7wgbMaam0DNlDxUKbBUF4PDUFFMA+UJgUDzbhqpwo7FNjWNszCASdozN7Ozqumnw9QdbbGtKJAZMAAx0pA0YeOnjBf1+ISWtVM7OipxCVRDRRkABlduOXuyLffrLfD7X+fajjo4miANYgaqHN88ou+8UzswEvpit0u4CUWXpwG8v9J6gpLaRvgNRjS4MurZcZ7w8X10q73AhI8QBnIFKpHz+wzw3uzbCaky8Uo01l8uo6Chwgh/RzZQBxKj6SBFxzohLGUFIAJ2BppQh4wwigoCgQUQk2nqGf5NPhrFSUwSIFYyAD8qRgSy9OcdPf9SwZmNSyH8CGgNrUeDVz65irvu1yQk+wPJ6oNkJqv+wPLYXe+hl1Xo/DR0CCvy+FBMFkPp7ohAFhJSFbFoalKNGRKLDW3UoApFXHt/VQl9XCtXkW1KYnMtrgQ+/q+CT+YqIhGuqD7TBaUQU1QTQAN5Dvtny1iN5Mm57nU/PR5y9bLi6uL6sqgeILh2PJsffT5uWg4qIaaTrBFYjJQ4Q+USLG1nz4AOknZhLVxZ4ds8tRVZnj6+efMqnyueG1k+NvANqXR1N6w+MJFJppAwQ6rc+f60mI/d380r/hezqyWGI1mxl8c9a60NPjgBll8xPMyCKqte6R68HNIIJ3svwQDf7umeofjSqRGui60txa/GZNL1PnAM+SFRlzWkNsdiWbCbbbC1gjcFCYwYRa9nf8zO1T0cJUTUBG3jasXPoW+BhEfnFMqam/GL7bGdxeHoldtl7e+zcrTk75wNzRpgD5oBfQXpl+bypfHJE8VXR6mIC1ndwEtgjIouqajeu5H/X11dfTx179/n9kZbuW18ZvzvS6fdUVb9R1fyGJjdXlNQ+VlKrqqYxS6VSWkQoFHa91r97r5ae61edGVdVnWwAs//28qD4icSlm9abqkZvTEw0ZxZX7vBrC0c77tp3D7cPddRplutu8Te0nIvFomu0m1453741TfgLa1qdanHi1QcAAAAASUVORK5CYII=",
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
        "iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAKwUlEQVR4Xr1ae3BcVR3+zrmvfeXVNCHQRtoihfKogAVBoAFFBeQP"
        "ZQyMiA9GZIAO6gDKOC2kGVAGRVqnDigUQVqsNJWOaAccsY8M1BaoTItYoQNNK7TFtDYhu3v37r33HOd3zt1kk2yyjwDf9M5u9m7P"
        "/b2fC0wAubbTkF3gE93/qCAlGNEy0fPMsTckwCC7GGPdId2T6z47xxPBWQgxSwBxiA+ZdA76l2Oc75NG+CpjvXuAnlB2dXF0d0sG"
        "InEErPgP4pYx/YX0qgs/bzvmrSKUFztxwwYf9dUPH0LCc8OAG+gVAR6IXbN5gxJoEY2EYaroBn2w4+FPmqfX1y+3bXYzfZJzQwgp"
        "SRsjnDMDYFNgSAZj5FgSjDNmxGL0LMDPi99YrlzErtuSK2ZCUaGI7+nkOPo2d1Op9fEG+4vZAU+ZEBgj2UfURi9+BpqnWsDA7CTA"
        "uHpwGUgppTLaRINtuGl/42HDu2Ib2vOdnT2CrEUzsLbTYFf1hOlVCx9KNjk3Zge8PGPMHnc4PVD44MeeA5ZqK/fw0pAhwn2bgCAH"
        "GDag6SsLKWU+0ejY2aPequTXe79RoFl5OBHvrl54cSxhbnTdIADYOOdWShB52OcthnHC5WUfOBlE35Pwtq4ERAAYVsVMAPDjSdPy"
        "suEV5BObujpMjs5TlB4F2BKASRH5wiiQuv2MkrwinqRGJlTLFQyBH3cKnPNvArgFhHltThVASskRShkIcSeZ/UXYIpQJuWs6ZkHK"
        "PZDMiKxytIcyA9IbgDnvatjn3K79mRy5FggXSL8MxFIQh/bDe2EFILxqzEkanEKlODX21d7dinUpcHYsbpmhdpiJwwtJfKy0qtJG"
        "ZO/cAHJD4G3Hw7nwVoA7FWtCShnaCZMFPjuXaNe6k3I2DEaUlwkLJXgjhlRYreQqMhUyH2LimBlwFt5RFRNEBuNyNpGunVUiVr01"
        "EK8McnAfwsOvgylnnIB/yhkiAEscA956ivI4BaWJQfBj2uB03Alvy91AWKE5cU2zZoCzsgF5FDTtCt7mOyAO/B2wUpNHEzIfM4bY"
        "lT3g8WmAn9aMcBPI9oO3TIfTsQRe7z0qVGsfm4QsqWkuES4rABEfMWGedCXCRCtgxkckWwRlmIxDCh8s2QaWnAlYCcCmREiRzIfK"
        "zBSdZsyF/enFyG/5EWAlK0l0NTJAiEoJ8+Sr1FU1lITJb6J8aTTo4FY3U4fX8llaoTYNRI6jfMA9AjHwNhiZwiiVM1Vu8KYTwey6"
        "EZWNi/mRmZCJEVOhP7npjMEUGIh8YNMPIN59cbwPEKH5IRhzLodzyXLtHyUTViGyFcqt6orE2hmIfMBoW6DqGmbFx6idQQZZGG1n"
        "Vm1d1aB2BiJJWWfdrK6yqLBcqBaTMiBEobCQlAEhhIAIqZanjFywXfK8SdQ+yX06gXNDdVG1oiQD6mAGJOOWPldlWRNIJgGD/kvt"
        "ivugUaonhsEY/FBg/ba9OHA0C07chHnwHavBW3aqKMGiRENaKZYg47pRoc91tB0jXRUeGcIQaGv/OC676rtw4iml4VoUMV6UUsK0"
        "DDzy/G48++p7iFPPEVlL4B2B8F8B0Rb4gGUDTky/p89ECPg+YNtALKH/pu6C7hXOsCxdQRCf2TTQ9+bL+N49T1cVOosxigGi0zI4"
        "BjMedu47jKYkg2kyqCaBMSy67ym0tc+FaVnoP9iH9Y/fg53btuP6O+7G/E9dCsu2cXD/HvzxiXvxxq6XMK2lDouW/h7T246HYZjg"
        "3MSqFd/HS5ueQ7LOQDwVYtf2ZzE0eBj1jS3lKsmSKNlJkLQ4Y9TMK0emKwgFTlvwOQwNHsGaB3+GRKoRt//0zzAtoP2E+WhqmYl1"
        "K5ehvqkFdz3Yi5mz5yKbcTH/nEtx+NB+rH98Of6y7hc4sG83OA8QBr4KCMSYIBXWiMpaId34IwwDvL7jeTxy32N4csWtSNY1oWl6"
        "HJ6bQf/BvXhm9aO464YL4OdzuOzqW+BmAggR4h8v/glrHvoV/vDoChzoe0uZHtm8PrdMFCuDihkgB8t7Ls4493IsWbEUt9zdg3f2"
        "/hOH3knDjsWVJFvaLIQBx7t9u9E28ySlnczQAK6+8V48/ep+3L9mK5y4rXxisr6pGlQcD8kHwiCPaa3tOG3Bedi+cS02/O5+5ahM"
        "VZsCbsZXDtowrQ2HD/Wpe8Tczm3PYtvGDTB4VpmNjjbVVfATYUIGxqYW8oNEqgl/Xf9LrLjzLjRNB2JJqKhCxBumhWR9M6742nVo"
        "OXYWHn/gJsWMbcfw5msv4JlVv0VzC+BQ1V2EqSQxwoSJjByY4r+SVjTZorcUsxunW2hsthCKENzw4Xku2uecjl9veAOWHcPah5fg"
        "5S3PIVUfA7XZ8UQ9mpot1DWa8PNelB8onHIISghTwCgGiMBQSNTFLbTUx/Ha/jTqYqAxpVL4khvORub9IzBMH5m0jhyUmJ9Ytgjr"
        "Vi5WzUv/oT4c7feRSAFuJocfXjsP7w/0K0azaX84H5B20oPAvDNORKqhWTGqTLFKZsZnYilhMI7rL5mHJzbvwZGhnEo69IDcwDuw"
        "49MwY1b9MCFkAoHvIUvUSIn6xlY0t9oQoYCERC47hHiiDqn6aTrbRuoUgmHu6R/Ddbcth2nakFRjGRXHlGGMY4AIygcC7c0pLP7K"
        "mXA9GtQZkPlBWCd3qrmQpIna8FxIJ7mRqKILvwJIqqS/4s8KYdmynehrUpcgNaCkD6iQGZBtMlgmjU04ZMhgGlw5q3ad2ivIAvRI"
        "UETEV2s8GhNHoaiyKgiTXpUU1UWxU0/mqFlHPj15SV0KdI5hRe1m7ag4DxTZxEhYAkPw76cgj74JGLFqhrTDsOZ/Gyx1nBZMDUrV"
        "DAg9Zq8FRst8iFiTnu9UbAY0AyS7NwGnQT+2WgqkpjkabEEH56qgn8hbP6GuqaNKDpimORot8j4K9uXLqmJHixqT//RCDO6N5vzV"
        "OSI1RcacS8GcxiLtVXCG9se+YQZYwF7xskFoMMajnFVaHOS4YzYq0u2HzBwEDKfiYVQBZARG4AEUTZU8SIQUTifWBgMzfDeAFHy7"
        "YkDKLs5Y91vp1R1bkwnjgmw2EEz3i0XQ+wCZeS/abYW6zWKAeeKX9UB2eN5YCaLZJPXZlMrVvo1KVAPS/R9k6IGp9dNobdBoPRYz"
        "uecFO+5/q/dftMfmm5du1hmEsR9TRmKMjV9aUZq3khAHtiPc9zcdQqkWUM0+13NRMxa90vtyV/RdmmirzEznWZC5o/B3rYymfONB"
        "tHGTMSnxk+5uiM3o0Mvfwp4ss2rhY4km51ull3wUOWgYK2HMPB8sdezIuLB4XF0xikbclKkDD+LgS5BD7+rh71hTpSVfg21nBvPr"
        "Utf2dg4v+RQDhTVr5r+Wa2NDvN76THYwH+ihQrE5adVLPxOp/YOCtnlGmhuzuSSzoYcmGmzTy/hbHY4v4PWLsljaLYfXrAUm6IP9"
        "Pz833jrDechxzG9SZHJzIR1CzIxgqovuiaDWVcUWzMwELbpNBi8XPDWU9r/Tcv3WoXGL7uGoULTGzzzZ8SXT4rfJUJ7vJGj/VGWc"
        "niokkHepaGTbwjBclrimd22xoAvHj6NKJfSuLsa6u5UovJ6LT4WQCyDkbCEQr2wtXTsoonADOYD3wWA7nM6NuxTh9MuZpVBmU9Hp"
        "6uc2pXbGHzFIoJP93Ob/+ee5r+ItDUMAAAAASUVORK5CYII="
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
        self.filter = FilterBox(self, lambda: self.refresh(), "파일 이름·경로로 찾기")
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
        hm2.add_command(label="새 버전 내려받기", command=lambda: webbrowser.open(RELEASES_URL))
        hm2.add_separator()
        hm2.add_command(label="정보 · 라이선스", command=self.show_about)
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

        self.root.bind("<Configure>", self.on_root_resize, add="+")
        self.assign_top_styles(self.topbox)

        self.pw = ttk.PanedWindow(self.root, orient="horizontal")
        self.pw.pack(fill="both", expand=True)
        self.side_box = ttk.Frame(self.pw)
        self.side = ttk.Notebook(self.side_box, width=AD_W)
        self.fav_panel = TreePanel(self.side, self.conf["favorites"], self.new_favorite, self.open_favorite,
                                   lambda n: "📄 " + n.get("name", ""), self.persist, "＋ 현재 파일")
        self.bm_panel = TreePanel(self.side, self.conf["bookmarks"], self.new_bookmark, self.open_bookmark,
                                  lambda n: f"🔖 {n.get('name', '')}", self.persist, "＋ 북마크 추가")
        self.fav_panel.app = self.bm_panel.app = self
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
        r.bind("<Control-F>", lambda e: self.focus_search("folder"))
        r.bind("<Control-h>", lambda e: self.find_replace())
        r.bind("<F3>", lambda e: self.search_panel.step(1))
        r.bind("<Shift-F3>", lambda e: self.search_panel.step(-1))
        r.bind("<Control-C>", lambda e: self.pick_tool("edit" if self.mode.get() == "capture" else "capture"))
        r.bind("<Control-g>", lambda e: self.focus_page())
        r.bind("<F4>", lambda e: (self.app_mode.set("edit" if self.app_mode.get() == "view" else "view"),
                                  self.set_app_mode()))
        r.bind("<Control-s>", lambda e: self.save())
        r.bind("<Control-S>", lambda e: self.save_as())            # Ctrl+Shift+S
        r.bind("<Control-z>", lambda e: self.do_undo())
        r.bind("<Control-f>", lambda e: self.focus_search("file"))
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
        self.path = p          # 탭은 새로 저장한 파일을 가리킴
        self.dirty = False
        self.update_tab_title(self.tab)
        self.root.title(f"{self.tab.title} - {APP}")
        self.add_recent(p)
        self.update_recent_menu()
        self.persist()
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
        ttk.Label(tf, text="※ 색을 직접 고르면 테마 색보다 우선합니다. [테마 색으로]를 누르면 직접 고른 색을 지웁니다.",
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
