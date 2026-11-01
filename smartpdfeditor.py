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
AD_CACHE = os.path.join(CONF_DIR, "ad_cache")            # 인터넷이 안 될 때 마지막 광고 사용
AD_REFRESH_MS = 3 * 60 * 60 * 1000                       # 3시간마다 새로 확인
APP_VER = "1.0.0"

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
     "· 🖍 색칠: 글자를 클릭하거나 영역을 끌어서 형광펜 — [색상표 ▾]에서 24가지 색 또는 직접 고르기\n"
     "· ■ 감추기: 영역을 끌면 아래 내용을 지우고 검정/흰색으로 덮음 (개인정보 가리기)\n"
     "· ◻ 도형: 사각형·원·선·화살표를 끌어서 그리기 (Shift = 정사각형·정원)\n"
     "· 💬 메모: 클릭한 곳에 메모 붙이기 → 쪽 오른쪽에 쪽지로 펼쳐 보임 (쪽지를 더블클릭하면 수정)\n"
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
    ("■ 화면 꾸미기", "h2"),
    ("· [설정 → 테마]: 스마트클립(주황) · 기본(회색) · 밝게 · 어둡게\n"
     "· [설정 → 환경설정 → 화면 꾸미기]: 글꼴·글자 크기·글자 색·바탕 색·강조 색·문서 배경 색·배경 그림\n", ""),
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


# ───────────────────────── 아이콘 (tools/make_icons.py 로 그린 PNG, base64 내장) ─────────────────────────
# light = 밝은 바탕용(진한 선), dark = 어두운 바탕용(밝은 선)
ICON_DATA = {
    "light": {
        "open": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAB4ElEQVR42s2UPWvUQRDGf7O7/3vJ5S6JGlNoJYithYWIkHwA29R+BW21OPIJ/A4iiIWFoIWV0QNtDHaWmkKDBIx54XK52//uY5FcopiEC0ZwYGBgZ5955pnZhf/dbBjo1Wz443RxLtvCQj7VimrjTpIf9tjVeivc8Y5aSqasrMZ44bqb8ZndfvNB7bYblakB6PnNqf6WX6u2KhAFCIIjbse1MuZb9Svd93y6ZEyvHg069zqZoV3doldK+j7YjBNlkkAGpFo9TMWoq3Zt6R0sjd7yMDYjADIzk/BlzBi61300e8EZ5WH0JKkxFtgp48PafGc5HD4JYYaVpagEuxjq4f6RlLKgESi/9TpmfA6HyurDvsCDjAZd0jFd5ppwRWu6vv727pnwG1BO+OnL+NYMpBLMhrjhON2SlKuN+mPXi08PEpWxooZrngfzEE6wfsrgfdNZfLl3axJywhpnwReQE0gjuXJW8N6l7f6PvnY6BzScxzVnQL8+yFE22bKNVQB1GjcefHUA68uLWL2VrNpMqEzCkmAkR0pAwipP9vfQdjbMNWcmaY65YtAHO4F+WZ7CiGtfVvYBJ67Px1g594Kt7fFYJg3HOwIauJCL3rpLqx83/vF/qLb7O6QF2e5IT9d+Akb68RwAWZn8AAAAAElFTkSuQmCC",
        "save": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACkklEQVR42rWUwWtcVRTGf9+5981MxmliLcFViQgVa1GQ2YgrF67cuTCEdinUhUt3boII0Y1/gK5cdNEm+AeUClXahYUOiEVBsLEl1raBTpuUTiZ5993jYiYxyUxiKXjgbg7nfu98v3veEbtj3o27nXC2DWfbbTqMRhvo0OGjb6Ddhs73y5ml2Wq00l08a+y6G3cSkr+6cPOVVR2dPf26hTNvHtGjfh4WAAatmlGLcHW5zxeX17xRxKosNy/dka6BC+SReTeEz3z598mtonbFaB5rtOpMPQ++aZggAP0EX11xTkyLUy828TpYIWKsf3584a+5lU91gUUP1r7bCSDPuZrTxNSx/Ph+v7/+KK11q7TWLdNat0zrD8vUfbCVfvj1Trr++2raWO+l3Oum1Ov2JeHGxwAsLf3rCJlTlY4UQTEjHOGA77gWSENkQiA8I6ncy3BHVHKgCOK5mihdhKFlE7w10+DEdEERdr+fwNFYQXeIJu49Tlxf2eRJmbFdd9872aQWxW/3tog2/sH3CGZ3GoW4+mefH5c32D9Heeg9mmgUoqp8pCbu/4IEG6WzVfnouA0M4jgmmKzp8A5N0Cudd15u8PZMnezssbzdpQluPUx8d6OHHSRoBinDVN34+v0XODph//mD3HyQuLbqtOxAhjBRCNNA3H2AgDEso8FkXQOuOoRh9gGraIcLmmAMZsb6etotocPGRu4O7nKq7e1xUIc+tCmo9mtb593lDBALv0iV5I3JenMiBCCYEWD0hGE+11o1q7dCUHUOgNemFZmdrZh3++MT/fTSwu25++nIh0u/KJx+o6k8hsl27sZq6T+v9Kriycb5M+Xxbz8brMDE/xuLHlj04P5054NFD8xf3jMp/wA5AC7ymd2FVAAAAABJRU5ErkJggg==",
        "undo": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACcklEQVR42s1Uv2tTURT+zn0vL2mqlg5m1dVEUXiD0j778uOVWihuZ3ARXIqC2EFwEh4P/wJF0L1L4Q4dFBxsqzGpEDBTbXCq4KCQRQvaNi/vvuuSaCxpUouD33ju4dzvnPOdD/jfQUfI04MSjUGPzGzkcjnRaDTibsz3fZHJZESj0RhMgZkNAKIfqyyz5TIfs+fm0sM67Ncy+b5PQRDETt4rEeGu1nqSiE7EWkeCqA6ip5W1l4sAVIdE/EdB27bTqdExd8RKb66sPP8EAE5h+kkqad1stcLPsVZlaPoI0uNElLes1Jl2u1X7Fu7NblSrXzt1NAAQMxvZbFavlis100zkoqhdA2jXsqzZKAwXCq7zOAiCuLcFxy15wjSekcaGCndmSqXSdhAEGoAm27YT9Xq9PemW7ltW4oEGYCUs7Hz/sVB9s/qo86loNpsEAJlMRksp1UWnYI+mU+9aYWtx/fXadWY2pJSquww4bsnLT1/RTr54zyl4N3oWRX0WaAHAhFt8eLngac/zxrojNKWUMQBQHG5Gob5WLa8tdR+llOoAUSgAgkDLZiJxZy+MzgJYZ2ZhdodZqVS+AFhiZqPZbFK5XI6GiF0TiTaAmAjJbtDslQsziwGsfmFra0sAUCpWlwxFQrX0BwCQUuq/OVPBzIZt2wkAOOc441PF6W0nX3zb0a7Yz3AYYiklACjHcU4KK/1CCAKpcL43yTysMbjuzCkY+kIcx0UQ5gGo3b1wqlYtv/d9X3S1KoZVc13XAKAVotvJkdSyJtwiQIY7rfO16qs6Mxv7hX9YhqedvOdOTFw9jt/WI/6JifZxpiNBHHQ5vfgJSI33JIoGXTAAAAAASUVORK5CYII=",
        "prev": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABnUlEQVR42sWUQUoDMRSGXzLjdERQREEURbyACqPCTBMz0xmtotts3XgCT1B6Abe6EDxA0aVudBEpVNSIV3DnQhBBcMbWxE0EF7ZMteKD7JIveX/+/wH8cyGz/gT8q8IGgmdnVwY6QXFOmAIATVjpcGhEX/lRNN0O2hHIObcAQBFChkkYnxRcdwshmLEARgEAKpVK/tYNDAghwySKG8n6pqal5KZYjOYMDHcjLgYARSkd11bhyHVdP03TBrTSjXq9/sQ5t2q12nsuDc3Nyl+OF5FdkG6/62fZ62UeWFufUUqnSJg8hMmapmGy63nJUKc2277QiKyVsgcRRmNaqzeF9J2UZ8+MMbtarequDff5imJY2mZJWUer65qweP/LR+EfQ30almmYPMblDV0M4708dmvrI8aYLYRoBYwtWJZz6vQ5o1mWHli6tSOEeDFndVeZ9DyvT0rZ9JfjRdtGx45TmHzL0husWlwIcW+26dxJkVI2OedW4+L8GprZUpamtwhh7x3jka6T8l1qgiCYCBibN0rjXo6sns1ElMfcPa0P9gSXpHPkmh4AAAAASUVORK5CYII=",
        "next": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABlElEQVR42s1UO0/CUBQ+ty1gYDBG2kSNJq6spANQetveBgJxrT/AV2Lioj9Awq+AmPjY2YzBOEGJhkFZ3XFwIHHxMQC3vS6WRZBHjfFbbnJPvnvOud/5DsB/Bz8mzn2d6NczFwoFzg+fAwCkaBrBJHMZN815AADLsviZWrYsixNFkWNIKIUjkRx0KVlZW3+4ub56xhgL7XbbHfUg+uleUZQoCKGLUGgu3+v1XqjTzTUbjft4PB5otVr9adseJEtppESyeZbWzU5CJfKk7Q/9S4+oYFI2cxssbWTeE6q+5Uco5BEVjRypuvmhmVmW0vXNYZVOkoHV63UOAMB1ockYvPGCAMDQKgBAp9NBk4gygCdAEuu7wUDwBCEEvX63vCxGD2KxGCsWi+7Uw5zSjG1sZhkmGaboZG8W9yCPkFSNY0wyTDOzLImNnXEK86MqkySJW5CWTsPh8KFD6atD+/t3du0MYyxUq1VnnPm/oVKpMGDuI6X9J5dR49aunWOMBdu2qa+lIMvyop9BHuEWf5tmUr//DT4BRbWLzZVelJYAAAAASUVORK5CYII=",
        "zoom_out": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADIklEQVR42p2Uz2ucRRjHv8/MvPvuHlpLNSip2SYhilhBJbquu5vM/koQi5DL3IQuaMSrePDXYXlBEfwTjIo/TrIiXhQMpdlhY70klET6HjysTZVVlJRWkGbfmfcdD3VxEzfS9DkNzMNnvs+P+XKMDlJK8UwmI8bHx3mpVKIwDHGH0WSH3Sil+NFQzX9h1epibr5cb85VFt4uVheey+fzmYM5I0sbhgVBkBQK8jEv7X/EBH/cGgMAEEIgjpNdE9uXv9cXvlBK8VarFY8CsiGYe1rKR7yMr0HuniiKGs7snez/Je7a2+vXAFzOpNOt4lz5XKvVig9TSgNgGIbU+/3aNuf8xI3d/pmtLX19KMcBwFy5/iUT/GzSdzOdzuovzWaTgiBI9ilUSvEgCJJf/7j+hO+nHraRfW0IhgEMACzFrxAgEhY/D8C12+3/qBTdbpcBiJ1LnrXWJv2bNz4vzFcrvu/VjDEJABD3mLPRzvra2kpBVn8guCUA75bL5URrvR84VLvvnKPNzU1TlJUSEXsLIAeAOBEssQ6AFSIYcuQfNmU2PT2dAIBz7DvheVQqLxSPZfz3Io+d5M4e584eE7Ankujm2VzumeOci4ccsYsAMKpkGgwmn1dpkb72GxFd7qydL4x6vShr76T81Ot94x5cmH/qpzAM6eD68MEPWF1tRRPZyR9T6fSr2dOTZ05Nnt7++cqVXQB4sla7e2bqgTeJ0RvWmC1K7NXPPv14e2xsjO/s7CT/v9iy2vCE+BAgZmNziYCYiB4VwvNMZDaJ6H4uxL2RiZYv6gsfSCmF1truUwgAWmunlOLffvP1pfH7sp9wj3rOYYaIOIi+sol5gZzrilTqnLXGCCGWJrJTvY5e25BSioNKb9sACrKyLGuLbq5Sj2Rt0ZVkfRkApJRin8JBhGHoADApJc/lcqSUIgC80WgAAF/X7Y2J7FSPc7aUJInhnC2dymZ767q9oZTidFRzG/SsJOvLXLD34ziOhOelouhWT9lRgVprOzs7663r8yuxNS8Jz0vF1v7pEtcdHjLuROmtnlZfzJfK8na88kiGjH/OfwNpW2BikqN9aQAAAABJRU5ErkJggg==",
        "zoom_in": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADRUlEQVR42p2UTWicVRSGz7k/86NIu2imdpJ8SSdgRS0qkRAnX3pnJjMRCkI2d1fsgI24tmBRF8NgNypuXfhT0riSz4UbZWzLdK6mkWKCpqWzEJw2XURECm2oyNzv/rhIqkmdSNOzunAOL895z+Wl0LtQSknT6TTLZrM0DENst9vwkFUjO3WklHR3UrV/xUql6bEjhXJtslg5PVGqvDw+Pp6+f6bnalvF6vW6y+fFczyVPEMYfd7EBhABKKVgrbsVW/P6D6r5pZSSRlFkewmSLWL+RSGe4emkAvT7tNbVR5M09V3zPHa7ugQA19KpVDQxWTgeRZHdiZQCABQKBcxkMuTun90mIiF3bunDP16+eHl//9DkcC537JJqzq9e/3VuIBh6lnJ+MugfOTs/f2a9VqsRpZTfRiilpPV63f32x+0XksnEU0abUysr6vZmv8J58t1/hl38BgIwR+wxAPCtVus/lKTT6RAAAO/dUWOM6/5154v8kVKxWHnpNKLPa93VYmr6vbwonVBK3dBxfBXAzWxu5np6uHmdpPcel5eXY0QfIpJ3PGDovQdE8iYivgIAgAgxAiZ3ujLJ5XJug5BcYpxjWKhMPJZOvp8gfg94/xHniQRxeoB5c3S0XN5DKXvSI1kEAOi5chRFDgDQ6r0XYq3XEf0HjUaj22g01gHhirWxstb+rpS6mzbuFKX0EY/sw1qtRjKZjO95ZSklPXcu0oPB8C+JVOpkMDT8dDYYvLqoWudv3rg+d+DAob25J0beBsS3TByvoDM3P5+fu9LX10dXV1fd/39sUapyxj4DQGKt+dl7cITAYcY4j3W8jIgDlLH9Otazi6r5qRCCKaXMNkIAAKWUl1LSb7/5+qfs48FZynHNez9CCBBA/Mq4+FX0vsMSiePGxDFjbGYwOLj2vbq4JIRg95M+cADkRXFWTE37yWJZi6lpH4ryLACAEIJtI7xX7XbbAwARQtCxsTGUUiIA0Gq1CgBAF1RraTA4uEYpmXHOxZSSmf4gWFtQrSUpJcXdhts9z0JRnqWMfGyt1YzzhNYbnpLdCiqlzOjoKF9QFz6xJn6NcZ6wxqx75ztbjwwPQ7rhaenEeFgQD5KVuwpk2Hz/DSDHdLTK0uZ2AAAAAElFTkSuQmCC",
        "rot_l": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADtElEQVR42o1UTWhcVRT+zr33zU+SqZPmx0yazFjIwiZFF4FWREmx0bpRKDihKl2IgiCCghY1FGYizcSK6KJLRaGoSKK1FBXBRdKNKaXB1jYFFWsmCZk0iZPM5CXz5r1373GRpPlrqB/cxYVzvnPu+c79CBuRYoEeMs19U2fA3i8T3YkLrakbgXCjwxgBRmKLjPQhDSLGDqDNV6bW1Khlh6OjFIomtLPw6uS7TV9sy+pniS4YYDuxWudiASLjVMwkQBxj11bSCn0e75t8CCTykIKkDP/mGHs410Vzqzm0tds7hB1piIuA8bj8hFXTVOnPz8B4jmvV7nkTejVIAFbRL8Y/mvnUXlx4P09UXBvTNsL6m2CkUgIsYuz6Z9jzf7CMk/dns4eIvRFiBBjiUUj1gnV//K0qxuNVfdmnx9+j+Y2dbpshUqCNFe+GxOnpblFZ3atLhUthQ0/9sVy7hDQYRKy2aMToAXekWEVy6UDu+uAr+fmFOqM1G4CDwaCsq6m5NvxOQyaRyZLVED+1PD2eQg+9jTaWADRtrZ5MJuXAwIBueXB/x8GDB4aOPNkJwwxBBM/38dXX33h/FvMNk8PDC/EPc6MkrCbXdvfmevbMgZnUTs+anZ2VjbEGffzF5/WKHGAAdO6774vzM6RAZDgzcVZVxzLSTD0G4DzSQ1LsRKiUYs/zpDFGua6rtNaqUCwqAxakXLMyIH0ZBiyYHwaA9lyExGZBWN2q7txURAgBIrpzNkkoqQwwMdZ51BZB/JHVhfVrG1gppQEYy7IYAO+KRIiINEyYwEw4nWsjQWDwGACMxNpZrewQEO8bj8KqzFCp8FeW6OPovvYK27bltd+vS2MMhBBwymV4rre7qgqwiRiZ7DG9VNSS5eBqV4bWCQtRiNJtEQj5jj2178CXbfmZ2JGz5eXFKBvDDLBSARUMV1z9dfDnN5pO/XM0UPfAOe/f8fMT3YmjSLLEAK2uTT9LdJFu7pt8Rt1Xf0E79iU3EDo2/XpF9m6CxXsnD4tw5Fsm9o1XfmTiRP0tpFc+BG12ENLx3rGXZXXzZ3op70CXPjBl7yeY23+HAiHpoXo/C3Fc7oq9ZBy7aEr5wxMnW65s/M+03ZZIx3vHnqNg5BMZ2d3EbhnantMAhIw2EsDQy4Vhv1R4berk3qtrOTv4IYBkv8RAl65L3aiqqKx9loXVCeO1gJmhgldg9I/jJ+oGAfBaLO6Jfpb3jEmx+B+OvXFrmZAeWiG+OcsA0NGapItt4J3cGgD+AzPCzxIkp2I7AAAAAElFTkSuQmCC",
        "rot_r": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADvElEQVR42oVUXWibZRR+zvt+X/PT/DW23VLadCpTWCerdMgila7iQFSGCCnDXxTFK/EHUbsOk+CswrxQEGHgD+iNJMLAK6cT2wsHre7KroqrbknTdS6tTdO/5Pu+9z1epClLbbsD79VzzvMenvOcQ9gpmAnJEdkz6yf0AGtX3TSZ2m91DGePgswj04NtLyHBAinStRLahomQhsAAqc1I+/v5Z6U7dJrLxaxvrdg1meqyAeIabmzZFRFjACrywUyzW/hiSq3dDaUZrMNkul9ha5khzEjZ29oJ0CUwC1C1y3rCRBUIJ/4M+PyhtwH5AvkCAUMHqrgE7PkZi6TZYDS1Ntpz+fsBXOpLQowCmwirnenoe9kmGJ7vzHDLPfY/uSl1vfghQZ9ngsVk9pjaGbE1hdlyHgGLCBIJ0ToJrteQmZAE3emda1wT/L30BA/plYWh7Ju7h3ccWoIFUuD/a5iBQIrU6nA20dASPeRcy53IHu8cjvUdiRfm5w9UKhUlABJSUrgpVIjc1f/pUiRpjabI2fwH1YYQScw0N/gaLrO287k3Il3tsVjojkD42hOPHzNNw4BmhiDC2R/OYWxs/PDUHxOj8XhcZjKZOicYSI5IAI70olcGm332XP5LEOmF22KGp8VVeu6Zp4IAeF0e/dvEhCwUCnI7FUTPrJ8AQDAfgAYTq3EAIMPSGiwWSyVDKWVYlmVorQ3btqVhGLwt4caQQQJgYkmVOk2INp4Qoq7476YHBBJsALyxIMaFSA9XCfkKCQJgdoH5Z+y9j4hIBfx+BYCFEARAG4bBjuMwmOkCkQ28iHoN1w0pWf6kVkoK2j4GotO+7l7Ylh0e++VX4Xa5oLWGEEIuLy8j1NruXSTiznf+eo09wb2wV47nBqNFcM2HcZbIkOoYzp4xb4k+ahWuPJY/ceuZe/sf/KiyttrtOJZDAJEQ5PL6i62zZ58ef/Ji2O1r+11bZQPasys3GCyCaz7cBwYz4dT119XqYq/hDX8efTdfOj/U/vJWwu/+eLWzwSp/Ta5GD5dXjk4PhhaQZgkiRfWuJ91xcuqg8IR/FG5fQJVmvyCtvzKxMFG2ygpi1+3CZT4E6XlLNobdamH6+dzQns+QZlm7TPXnax1oO3m52/AEP5HeYAwgqOJVBqClr1lSgwtq6d88V5ZezQ3t+eZGsq3vYTwtkRlQACh6qtAPIR+GUzlY9Y05Rdo+t7oy920htX/5htybRILFTXPSvOW20A73n5CG6LsIGp3MVDdjX0s1P3lYgWjLbfkPvcylffs3pMcAAAAASUVORK5CYII=",
        "rot_many": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADKElEQVR42rVUPWxbVRT+zrnv5TmpTXAqCyklbmkHkLNhI7ng1sZpJRBS1MUgBgZAqF0ZUECALAuhClrxI7FUYmKM2UrFUuo8xZQqJQxIWCIUSgNR0lCauKZx4vfuOQyVC3FLU4Z+09W95+c7P98F7haqhLI6m+7KNQdlZfxv9DilJjWaPqHu7d6px5VuDVYmVCry0Bs/P2Dj0QkCngObYVXbArkn5frKR7+X95zHpBo8S5buTI0AKHYc+6PgMJ9kdyAaXv/zc1WZY6IhGO9FHhj0ZPXyK/NvJT9Nn/jWpc1kyjw1OzuEVgvWWgriD7IbrMrC3uMvyOCuZ8KNlSMLEyM/de2TRy/FyYsd48h9L3dai8WFiZEadcvMZrMRE9n2hWHeLVYs6EaPCAyWjVVZ+v7Q9FzzYrb0ar+X+iDwh2cJhzMBACTfX/qR2ElosDHbbaYSxWIARgPbeRrW3WvUPlyfOrNzeur0Tsue6kh2DwCcq37Y9isU4nAm6A6GbOc9HojHORI90GWoudxTCTWdb8h2HqvX6yu5fPGQMc4+a60C+rwSvmM2F1Xk16uJoU8a1WqAyUnGDyVN9l16hKLbv9T1a7XNO0RkwnCAxsfHYyD6zKoMgeCB4JCCRSyI6J37l64UAGipWgUAzL+5q2Hay/v6QnrN6Z1rNCp2bW2NoViuT51+CYDmCmOPiurxs/6Z2hP5sTQRbbvpUCEBlH55neYBwLnDxphssTjsWXvZQvuYsD2fzzshEGEm6TFWqBIA9MpGPc/jdc9jAAhcVwqFggBQAKHv+yHdON+GACmI/pGMtZZU1WROnWqOZTJNAglct1mpVEQVAsC9G5V2SyZrm+t9iGntyYPnxZ+2UOzob7XP5gpjARGNimCxVCqZxeWrWwZUADQzM3Mtm88f6DeRlAThoIKPQvVtZtPUQJa+rn81BwCP7y+2DdGWDBUAzvn+BQAX0um02x8b/JiIGGEIGE7uLx4cDSUQA9q9lfr/DU6n0yaRSPBf7eBdNiYvEioUrKCQiAiE34wER3zfv3Lz97iX+M9mlEolk0qlbsneaDSoWq3KPWfWxd9DoF6g1daJGAAAAABJRU5ErkJggg==",
        "t_edit": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACWklEQVR42r2Uz0tUURTHv+fe+96bZxYORmCbQFq1UCgVM/WhI0TUos2jRWm0sX+g1m9e/0AFEfSDFkEtfNCiCJRopglbREkoBW3bRYFjpTNvZt69p4VmE8xoDtF3dRb3fjjf8z33Av9YVF8HQUDNDoZhCAAG/1vkeZ4qFArJsdHMlO1Yk9VqVQNQRCSYwQAnUiphtF6cLzy/xMxERNwMqFZXV9dtEvfajjMBEECA0RpEBCIBZVkoldb2AUA2myUAvNUMCQAfHRs74FpWdxwniVTolcK6VkuSBaPNZdu2heba8nwut7STUDbleV6fdHa9qVTj2Vcvcid2MkNVVwvf9xUA/WV5uR0AwLB835fpdFp0dXXpMAy3TVnU1QaAjqJIG2MMABCBoyjSzWDMIGYQB785qtX1YAYRbYbDHEBQCCNagwWCCFy82ttReTT+9Nu9kSEKYZgDoVqDhWblwXDalWrWduSA2M0D5YcjZ4Aw37BDImJmNgCZhrCbw2lXqTnbkQPllUqsHLkXLLqJwM0sK6WUALitIaxTzdmW7I9LtYrrWqkfxXjaPVu4OzPjyz8sR1G0nq7W77TW44ZlEQCyADZtqg1YuVZJuZazVkqm95yfv8N5T9FYlNDfpAkA+DCYjpdSsyl3vbNfsPZzhQ1YIdlqbcj3fREBAA4x0Wtr8Xr5cc9B0V8q1iptbY1h28r3fQkAgyPjh0+dPM7vb2SYn2R45f7oNAC8vXXE2uqlNJVjoefzd/P1yjPKffyUXOiYenk7n/dU38WFWks/+tDExP7J05nO+sSbXfgJBgoUJpe6qFIAAAAASUVORK5CYII=",
        "t_mark": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACj0lEQVR42s2UzUuVURDGnznnvPfe16ul1UqoKNpE2KoWiXn8jKxtdxV908JV/Qcvdxe0CGoRGYRQi8qFGEikaR1SDNy5khaVbYLSDMy8ej6mxatiZmZU0LMd5jdnnpkzwH8iKhQK8q9T/xRKAAQA1DU099bpxlMAkCSJWIz9nrTWahF2s+lIG9c3tXJ9U0uyquDGyFprZYxxdbrxXJTJ3rHWWgAiiiJpre2el7g4OjDwCUstrKckSYQxxtVqfUDI6Ia1zgNQzIwQAphQPS9EKUkSAgC1Ad9wsLl5qwj0EECeOQQALKUUIYTXKrijY/1mdqy/nwDwei8krbUsFosh6/m+knKX985TKgaAEOxJY8znxWnzui1rraUxxtU2NF5TKtNinXNEJBnwSkXSW98+bMxLrbXq6uryS3libd/SIRyqazqRUZnL1llHqW8+UpFydqFj+MXgraVhrcwVaw2hWDSuandbTS4nO7z3gQDJzEEpJZ1zI0NmsL1QKEhjjF/T9CUxg4gYzNXxpQt7Xg6N52vymQUPkAARAHxwJdo/MtL/cTE3/BTIrBUexxI7KthNjd9WFfL0lXuxezBcrspj5lxWEgV7rK/v8JPOzueZs2fhvkcZTwT+YbFnenbtj7flRzlAqAxk91AcrvZU8qt37vzU22d3N/I/wW/O5DA7fRmS4uB8Fgszx7g0XePmXMhujsTEZNXUzu2V18EsIdL1WOETIx8RSq6T9va8TYETx6vwRX3ClgwwH4ASI8zNeF6YA3KVkHEkEEtahUoVGNgUAe+/ttK+R0/VikoWNkTwDOQIoqxSgqoADmmSDWv3uBxLlz0FzpRZYL4Xcy4Pu2xEuvv0i/vBzFCCEMTkPznl3wBuCjHahO3s8AAAAABJRU5ErkJggg==",
        "t_hide": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABjElEQVR42sVUsWoUURQ95963y4wJCRpEyy22E8FmO2Gn1DqlXbDRzlphpt8P0F6w2P2I/IZGZJmIRLtlwYzJ7LxjkSwYETITEjzwiseDc+89554HXDP45yXf3w/ZFUiyLGtICjcBSiJJTafTdHG8eu0W0lVzCtBajCf1k4TV8a93L/aefc7z3ML68ejopJdsWybELQkixMsIBUVEmamZAkBRFNfvx4UuRqPRTheGn+7aaBoOBoPFbDZrAJAAbDweW3n47T3JJ5IiAGvJGUlSUqlYPy3L8kcAEOfz+Tatt2tmva5zSoC7366b+ADA9wAAJEViKemOJP0txWVdSoKZ1wAQzqqIBFMAOj9dEAH0YkR/TWgkKwlf3O1hjN34SJikyqz+ujaFADQcDu+GkDw6V4ZtcwF3VnV1WB4cfOwoVcs9XEdvMplsbO7ce+Me0tXpCmatHFaSJFwsl29fvXz+6UL0+v377uaPnbal4K2cphDN3TZvpR9uInr/+A/z3NClSgEUxdkeX2Hd/hN+A/M5omSsJQvEAAAAAElFTkSuQmCC",
        "t_shape": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADeklEQVR42r1UXWibZRR+zvne72sSkyWpS2j6v1YRqmxIkTm86MDihjgQJL1T2YXTC0UQeiFWvkbsOp2iVS9chXWidbLeyVBhw9oNBcsyxmDdxNHUZG3adHRma7J0+b73eNGfrfuJeuNz+z7v8z7nvOc8hBWIDU4ebTfwD2hPJh0CBP8X6Eg8bnSNjLjZJ7ZuDzFvXyiXGcR8B1O09hmGLrF8GTs5nhLbZkok9O001TI5yQBcrfXTHsvqFscRg0BrL2K5PgYjZCnMLJV/BZDCxATdzeFNJyKl2VLJUZpjbHoDCmoDm96A5XNDbHoDDmTnkqMdEilVKlndLJ4ZBHXd48lvGhu749L01vYCEylXM0OE0NWFyg5X4C+XTQFIABaApKNDCUDXLZ+liRF0rjkgkp/b2ghHxLi3wxVo0xQCRJb7JxKNCtlCMryhiEgrToda/ZHPzvmffJUWgQQgQiCSewqapmlIPG4glyOJRmUw3MlIUPm1l4ceXgjV42S47XtvMUcNH8yf1dr5KEN0aFkUAEjWCQqA6uPH8+ufGHFb+6ZeGg7EDrTkU1JbyH097duYZs27zOraocb357algVdgg5DALYKitSLW09se20EipYLl47qrM7r78Z4HvwnEBp+9+N3lT8b7qv1/nvmYsjgNoKdpf3a3CtYcbOifTmcS9X2wR9WaoBCpiGVx0XV/NIlQTRpVXj+uBOvQkk9h4Ld3N/osDy481Bnp2HNMbV74wfi0OzbUuDezk5T5dsSeG5hPRAuqPZl0AMBw6YuS1sfyjuMuMXOVe0Om7tvkPRF+5GhtIXvYlfLQJa5hnzOTHEuQs3jgFMEWdjl7yPLf3+Ut57YA9ItaXfTY+HgKQGr9DJxD4w420v76P8LjEz8B57GaC8lwu8YMQAYKEIir2Fr3yzbAvfH42joNToZ5pqWThnT5giV4joF3nn/xoGequdkZm5iXB7JQFxO0RH2pXdpYJFUsna8cGytD29CfeaFlUKRp36Xdt1Pq+jNbmgeuug17M8PLrkYVVRS1hdELadqf+9wIRvc4f819K3AOa0euGczPsDfwhohzSkr8VLoUzKMXUlkQQhAARNL43mwPsfEm+0I+ANBLi9C6/BVdnn09vW/zldWNoX+Vmivk+g/TXpaqR9kwFRVv/J56q2bu1vP/FsX2qLprn2W9qb8Bm+6CMgNmtUIAAAAASUVORK5CYII=",
        "t_memo": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACm0lEQVR42q2UT2tVVxTFf3vfe1/y4kue0UZB20ITEiqaIEJBaDF0UBwWStORg0Id9gM4E7+DM2dqoDwcCEKhAymlI1toQFRooWraJlpipWli3rt/zlkdJM8kmoSkdI/25Ky19lqcZbwyEsZexsBAbAW0Z7Du24v4BnwQWJdF028PUpgW29oRvFk3MSTjx98W7RJRwsyQdZd/psfe6E3jVc/S0yFIXbKdhHlimMJcvlSd3/f5ox8k3NQiYWjSivk/vq4df/Mj0iYQd3msQ2xT/jK7kMV8gqnZP1P7jKDpR4Oq1T+g1gxYYiSZYbuwswzEZCBkBxpDndnO8brxNAWgMFlGB6jnnUK3vrljnSLgvm2wlBWcnRzn8NFDTpDksQJIXxpiOIg0TTg1MUII2tZFA2KEgf6+1cXMLK6GmG62GZIkYfjE8M6RdCNbziFs9jt9lTqEwOy9h7tS+NaRA9QbfdsARgRGVQV+uvuQvKiw7Tw0KEto9o9TbzZAkqJpHbAmw0ljRD21jE8/ObOmztZv1NYpUwXh7kbMAFJdxCmsbR6eeGyP0jNQqgoZMYIEEnIX7hFhGzncTVRFEpZWsFrtdwCTcDNice2d97zRczPp7ztSrgT54H7z3hrRXN5pm+XLELU5GDdiOy+KxRdf1s89vqIWiXWLwQwtXR0+1MjiyU5ll3snxkbZ1yx5tpCF+fmqWupcUNAMVllqFhGiJ/Gw4nO95x//3MVYJ2yRALSmSPIb7/6lBx8H3TmjsjXyfOX68Pu7bZv1lKdWG2P52uGDJos8f+Jh7tlMHvyLxrlfZ/TtZMrCd69Hcx/ZpS0+f1dh+6uRD3X7mMrWyPd/T48PrilI916Sa+X6ojV6tLgxdkGtqWQj0f8y/6XB/wWKX0LP1tZMmgAAAABJRU5ErkJggg==",
        "t_erase": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACpElEQVR42t3UXUhTYRgH8Oc926DETc7UmLmzaU6F9Kjz7AQ5cZlbulxU4qjsIj+aJQV1UxBCh5YFKQOJrMvo2huLkBblbX5FRDZD+xK8KIr5EX7g3vM+XcjITEStq57rh98Lz/N/H4D/qQgAcP8Si9dfoorCAQCUlJTo8xwOAQDA7/drtmgtYxZR5MvK3cMHPN4pwW53AAC4XC7tljCxtJQvcDoHey+H8F3bA6xwV0XNRUXyplBFUTgCAEmiyBc4SwcfXupA7ArH8M4TOhK8j+51UM1aWDAYZIIo8jnG1PB15xG52pJPZ5cWtItqjBMSeSbtsCYMf5uoXTIk9r0ZGJj0+/2aSCSCf2xsGbvGDILAW1JM4VQ+WU7XJlLgiBaRgY5wMLO0wOUZ01hn2TE+N8UUNuTlyN3d3Wp8RL/FgQCwfFHkiW5buDPUIe8U0umF8xe1bcU+cAg2mJn/ATpOAxQZGHTb2Oj0V671RU90JPrFO97fP6QoCuFW5IwhJPFEtz186+YNuXyfi+Zm2bTtoXa4+qoXXk6+h6QEPcQYAwIEFlVKrHojTU7QGwljaQCAkUiEAAAQRCSSJKWU7fcMPXveh4gYo5QipRQREV9H3qLXewiHW+8h3n2K852P2HSoh9bX1KFZKjq9MhXxORK7fa/V4/XNfp6YQERU49hKtLLKh0NXutjC7ce0/mgdWooLA2sGPa6bhF2Oisrq6NjY+NroaIQ1nmygpw6fwAy5OLBuFuOvmMyZssfri46N/0JVVUVEZCqltKG5BdOyswNkI8GON6xGEZHNzc3TpuYWtGRsEFuNms2Zsrvq4NSHj58wFovRpjMtmJ6R1QwAIEmSblP/OI4akk2OGv/x74Gz59BstTWSrRyF1Wj27sI9tlyxdqNn6ydDKFuej+RW8wAAAABJRU5ErkJggg==",
        "t_capture": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADkklEQVR42q1Uz2tcVRT+vnvvzJskkx8moaGptDsXVSw4+TXTNBOKVfyBiPC6lmzcuVKCLnwZRCj4H+hOKApvU/zVGm2bZ8Y0aRqFINl0J2MtxSahk8SZee/e42JmaqOJIHhW98L57j3n+75zgP85CADV/NNHqvA+0kBPQ8T1GKN3Entr+PkXZ3/75qsPrOhPSfsqYb4E3LMC91hGqYm6cw4guoxyNefeG1paXTYA8ADex0Pp1Ct36w1L0gHQAmmEGxucBM8pLddFMC2wP9JhUilmBJgSQgAgRepdh5O/TE4+RQCoFMYiJVIwxh2n9XYGk4R3rE2Ora3tHdSWBFD4ttC11VlXds9zdWlcpnC0FrsjBgDEuVhIqcWp7ePLS3/sAwNqDsCTvk8/DB0AsgQHLFXbOZV8LhEw6dVaFACQ7O7SOpWN47QAFEBJi9/pYlGVAHc+DO1531cEpJVD8aEFIAU9nlKdylqa1ic/7CVJVYC4vwkA0eQniqIkl3u5M5utpsMw3H6oJIDgJKQESEVxMXZybxCIeZj8IsK5uTl+t1B+Vym+AZFOgJeUxLNRFN3/i5H9odo8SdA8A4Dv+5qkXI0W38lkMu8DeFyA/rTnzSQwFwEwCAI+ynMbz0O8KYVCoVulO26THHTOgaSCSKKMSTUayfjy4rWbvu/rMAztPyo8KJRSBkCHiDQfA+gEJABCsofiAEB8X0ux2BZIfN/X5XJ5GyKXPC+jBbAA4rSXNtba29mMWRERhk0b7cPz30ayWCwOOJX6hOQLJCGCn+PEztz4/upqEASqVCq5A4GVwujrAE/s9fRfeOLKlfrfk86cPTtGmC7a+mIURUmb5yYbkEp+ZEaBw0d7Bz5sOX10bfdMXn4fG+tpqcZHPtzfRRCofSMIoJIfWd8+PSGbuVyvaXluaztJGh3WUQIobPiUMBQC7lYul/oim5X+jg795vh4vLCwoKaDAEAJQFFJEOHOvGzuWLub0VrYqvAagKljN26mCMp/3YGV/Mh1Cic8x6G2suk+Y/Sv46OLFY7YbmPUjk1Wh5976a07819fcIoX4eQ17dTnotw5AP0ema+Ja6+vXCLgnlLGAIAh3t5J7GdG85nEwUHEiOBBuLHB04IpWjcPMg8kKwKOEcwIMErAAYSBqiXiZu8lcfUh4T+dOtV3whhxWssAgLu1mj26vr578D4MFFYuZ+9vNu8mndZ95fIWAPwJ52uqw6hG17YAAAAASUVORK5CYII=",
        "m_view": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADN0lEQVR42tVUTWhcVRT+zr33vZm8+QmhZtoGil04xQYCSmUmtZEXElHrQnHxWnBZC9ZNiyIItjJkIdKFIC5UBK1S0MUToSCY2tbOM1OFIKVKSMssXBgpOv0hJpN5M+/de4+bDgwBa93pWZ5zOOd8nO/7gP960N2KtVpN1Ot1MZgrlUochqEFwPe8JQgC+U/L/q5nc4JqtRrNzc1ZAJiand0lSe4zkLvAIMC2iFFf+Pbs5UEU/f7NA6kP47Hp2YMQ4riUagI2hYnXVomZyfVGRDYPkyTXGfhg4eK5twBoAAKAHRxIADA5+cSI4/H7jlIHUm2uiKT99tronpt/PvRSxQpRzK9caIwufdxJs1uOOVI8ba29nOreC99H0ZX+pQSAmBlEhKnpme+UcvZqy8d1c/ndlaM/lkWm+IV0MmWwhUnTNdbxkd9e3fL55MxTz7lk3yOAdNdWLl06/2utVhPk+76KokhP+bPv5PL5Y3HcgbHcFTDZP6pvoLu9injxlGES7D18QKl0Hdvqr0DGtxKWrusNeehsbPyUH3KqhUJBqyiKTBAE8vfWraVOHL9swVJw6ibeWKZ738Rr+vrPbufaOckA3O0TlnbsofbY1EfDzfAXozy7sdHuSRJyddXm5ufD26r/CJZYFNoypBCp41mRrGcpWT8ktz44NrT7yRREQo4+wJx0DMOe1apwDQTHsNDKJZnhXgIAfch2nz/z5ZDnPdvr9iCVA4e7WC1N4kbldZByALaw5GD46mmUrn4Ko3IwOoFSDpKk10qyTnl/tdpWURRZAFbBHO7F8V4hZV4nvRM95dazzTNDcuczo2lxxyEQFcnq04WlT5op0DYmLpOQb1pry8w4uDg/v3Z/oSBpkJyP+v4jjsx8xuCdFnySVO7DhW/OrAwy3w+CvLl5+3lBdEIIOdJLk6M/RBdPBUEgwzA0tJnxlUql6OaGTyopjoAIWusOA00wMUBjStFWIQR0quucxi82Go3moFpokxsI3Cn4vr/NCGc/ET0O5jIzExHdIKbzVqqvGhe+bvY1HYahuasD3RH+vTiV+Df2JXzfF6VSicfHxxkAlpeXqdVqUTQ9bTFgCP+v+As6h4YnlxejegAAAABJRU5ErkJggg==",
        "m_edit": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAB0ElEQVR42q3UP2gTURwH8O/vvXe9O70cXIcMDrq46aQeRFo44i7ikIDQ1UwOpZOLPOqWzUFcIqiDDjmcpGJEDFk6WIdCoZODuDiU2tjk0sT783MILS1depf+prf8Pnwf7/1+QMHSWgvWLHAexcx0dNZazIhNgZ3mu0t7zfc3AIDbbTkDRug/Zm/0bG1z8vzjaKcZ3pomnV6f8mBET7P+iwXPci93zOEDfzw2WKp0b5KkdWf57ldokDg7tpr13y54tmd0zNIvP7JexSmi1DCceeb0KoEY10KSZ8cWPVupzpwl/WhAsTR35YXSHznYvfLQXbnfYs2CHl3PVC7MlH40iGMhSVqGK6LJdsNdefOSu1pRlRIAUEUw25IiGsUNZ2mjxd2uomo1OeyjYljacJZ6Le4Giqq95HivOE/sFDgrdgLUGjNjR4/CDJICGa9X5g9+qk9FsWMJNWVcsTe/WWu2J/39v3EsC2AAIIIgUESr2c3bzp0nn83K9o/kwC2RNM38GACI4XBIAHDR5nv9fwaWP5j21m8lKMuPHf5DCoLATGG8njPleH+U9ijD1sb6l+/tdk3W62Gaey3VarVTM110cZ6YlCAIFACUy2UOwwLJAPwH/MgzUlKfkawAAAAASUVORK5CYII=",
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
    },
    "dark": {
        "open": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAB4ElEQVR42s2UPWvUQRDGf7O7/3vJ5S6JGlNoJYithYWIkHwA29R+BW21OPIJ/A4iiIWFoIWV0QNtDHaWmkKDBIx54XK52//uY5FcopiEC0ZwYGBgZ5955pnZhf/dbBjo1Wz443RxLtvCQj7VimrjTpIf9tjVeivc8Y5aSqasrMZ44bqb8ZndfvNB7bYblakB6PnNqf6WX6u2KhAFCIIjbse1MuZb9Svd93y6ZEyvHg069zqZoV3doldK+j7YjBNlkkAGpFo9TMWoq3Zt6R0sjd7yMDYjADIzk/BlzBi61300e8EZ5WH0JKkxFtgp48PafGc5HD4JYYaVpagEuxjq4f6RlLKgESi/9TpmfA6HyurDvsCDjAZd0jFd5ppwRWu6vv727pnwG1BO+OnL+NYMpBLMhrjhON2SlKuN+mPXi08PEpWxooZrngfzEE6wfsrgfdNZfLl3axJywhpnwReQE0gjuXJW8N6l7f6PvnY6BzScxzVnQL8+yFE22bKNVQB1GjcefHUA68uLWL2VrNpMqEzCkmAkR0pAwipP9vfQdjbMNWcmaY65YtAHO4F+WZ7CiGtfVvYBJ67Px1g594Kt7fFYJg3HOwIauJCL3rpLqx83/vF/qLb7O6QF2e5IT9d+Akb68RwAWZn8AAAAAElFTkSuQmCC",
        "save": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACkklEQVR42rWUwWtcVRTGf9+5981MxmliLcFViQgVa1GQ2YgrF67cuTCEdinUhUt3boII0Y1/gK5cdNEm+AeUClXahYUOiEVBsLEl1raBTpuUTiZ5993jYiYxyUxiKXjgbg7nfu98v3veEbtj3o27nXC2DWfbbTqMRhvo0OGjb6Ddhs73y5ml2Wq00l08a+y6G3cSkr+6cPOVVR2dPf26hTNvHtGjfh4WAAatmlGLcHW5zxeX17xRxKosNy/dka6BC+SReTeEz3z598mtonbFaB5rtOpMPQ++aZggAP0EX11xTkyLUy828TpYIWKsf3584a+5lU91gUUP1r7bCSDPuZrTxNSx/Ph+v7/+KK11q7TWLdNat0zrD8vUfbCVfvj1Trr++2raWO+l3Oum1Ov2JeHGxwAsLf3rCJlTlY4UQTEjHOGA77gWSENkQiA8I6ncy3BHVHKgCOK5mihdhKFlE7w10+DEdEERdr+fwNFYQXeIJu49Tlxf2eRJmbFdd9872aQWxW/3tog2/sH3CGZ3GoW4+mefH5c32D9Heeg9mmgUoqp8pCbu/4IEG6WzVfnouA0M4jgmmKzp8A5N0Cudd15u8PZMnezssbzdpQluPUx8d6OHHSRoBinDVN34+v0XODph//mD3HyQuLbqtOxAhjBRCNNA3H2AgDEso8FkXQOuOoRh9gGraIcLmmAMZsb6etotocPGRu4O7nKq7e1xUIc+tCmo9mtb593lDBALv0iV5I3JenMiBCCYEWD0hGE+11o1q7dCUHUOgNemFZmdrZh3++MT/fTSwu25++nIh0u/KJx+o6k8hsl27sZq6T+v9Kriycb5M+Xxbz8brMDE/xuLHlj04P5054NFD8xf3jMp/wA5AC7ymd2FVAAAAABJRU5ErkJggg==",
        "undo": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACC0lEQVR42s1UPW/TUBR913EyVHwoAwML6sDI1gUpAwi6sDGy8ge6IDEhZWJjgQGYqcTgH9ClgwckhCAsGRBqpiDiZ/t92U7iRomdw2IHN22DCwtnero697x73z3vMva/g+qQAKx4RIS/FgTQKETySswq8pYbxQE0CvKpqgC0AFwCsHVe5SXsSit5hUREtPSFud9q2k+kjjtEdCXLskyZ5KvFrLeHhwf7RJQDsIhoeUJ1NBpteaF6kKbpjTImdfwGAHSUjHgg3/NAPOe+fC109A0AlI4+fej326cqdRynAcDyQ/Ulnc1TL5BuIM1BDkDqeK/6DCV8X+4m4+lxnEw+R1HUBmCtRHu9XpMxxkKpn81zYJ4BADDicq+8vXhf23VduxzUcOjtLLIc3JfvqgNcHXxf7s7mGQKhngbSPK4Mis4YYIsxxn56wUupI2itr65aLxPCMLzOefholbTBUqUjuDB3F/kSSiWdE1Wuk13Xtf/kTwAUqKQDIBfC3Cvj1URyHMeqmngDLCLKf3ji9iRtWmmaff/dWE10u12rqKzJGGP9/rAdxePYC8RHxhid5YbaODryrsXJuDdNj2Ou1K3CCfUECzJxY7ans8XDUJlXOhrP4mQyHQ69ncr/ZnUFbcYY44F8AQBCRQsTTfYHg8HNcydbZ3VxY7a1Tu4Igctrm+ffsb6ZLrxgL7IHfwFRn6tg8+RGLgAAAABJRU5ErkJggg==",
        "prev": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABUElEQVR42sWUQUoDMRSGX2bqQhSlK1EQhR5AQXsGD+JBvIFbBVdewiO0C0cYii6rM+00YyaZTOyUIiX0d2ELUiu0qeJbZRG+5H/v/T/RfxYABoD9CXhVgAeAXQBeGIYbK0EBeNNzmsnbvCifuNYHTvIB+EREcWyqQhV3AKBNOZTSnEyAnhMsy01zAgueu+Jo9ucLy4yiaDdTRQMApDKNVqtV/frYUrAO53VtSg4AUptmHMdOMAaAJUmyL3Pz+j6yyHX/st1uby8qc/YCY4zB99e3fN/fsdaO7NiGtVrtDUCFiOC8Jr00Ox8MR7BjIBXqeip3qWF862NPnCndVwAgMn01bzeXgVaIiDiXp7kZSABQ2tw8CrHp7JQgCNaIiDodXtem7H5C+/dpWhw6B8V0TaIo2hVKP2hTjrmLU+a7Jt57SZJj5z7+FFm/lokryXStD3LhOG+6eQvOAAAAAElFTkSuQmCC",
        "next": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABUUlEQVR42s1UO07DQBB96yQI0VAghITgEBScgBtQ0PM9AAfgGqHiEEg0NCmRUGjdRUjG8dobO3FiexPHCY8Cu0FRCDYSTLXap3kzo/dmgP8eYhlI0gBAABBC8Fcr5+SVkoXr9o7CUXTf6XQ28/9aWcJaq9WqSxU8kuRgGD+/2vZBjtXLEAqSwnGcbc8fPJBkP4x9y3IOAaDdbjdKkRZv6fnNnFRZzidpqfFJGkWi9PxbkgwjHVu2OistVD6+AQCuCq77wzhJximlCk4Wdfpthdx/BgDMptnTfD6LNtbXIAT2V/Hyog4bAPDWdS/1JGM2J6XXb5Ks/XjkIkEq/zzWU0Y6pdsLrr6KtrJtAMBx/ZtYp0wmGbuuuiilcKGuo4I7kgxHydCW3ukqxl4GEnw39SS1dKyP93Z3XkjWhRCzSkfBNM2tSnu8aFsqXZplK/gn8QEZUgmiY4rdgwAAAABJRU5ErkJggg==",
        "zoom_out": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAClUlEQVR42p1Uv2sUQRR+bzdLkFxOo8EkEBG0sEkhBLRQEGOlIIhYiRCL3L8giKWIla0IaWzdwr/ARgRBvCSFBIJNyGV3Z2Zn9tft7V12b3efRe5CjLm7xNfMMG/me99775uHcIwREQKAtra2pgEALC4ulgBQIiLBaY2ItCE+fdT7saNgiFgCACRJdiNJ2/cN3TCoyH9sbW1+QcTO4TsnYra9bV1vJp31goikF5GrAspyomaro3Yd8QQAwBzFlIg0IkLG2EKz1Y7iZK9hOWJ5JwynfitV3WVsKYyTr0REO5azPKo0+4Am6UzIzSBq2hsb2+cAABCx3yAAAJBe+Dlpd1LPa18iIjwWtF9optTNoiTadfizQYEdx7+ctDsFE/7L3tuxf5rSk0ahET6Imq1yfm7mE2Py7vTF6XtK+SUAQLVa0eIo2pmdPb9qM/lL1+ARALwFgHJglwlxvCwJEbHLXXUbNXhFtH+gaToAat8AYBWQuoTaOIzSlpT+wywvyBbeLSIaJ6IpIURFCFHxfTorpZxUSlXDZitmrv9+UMrQKy42GnTG9YJIquD7oOBCem/SrFuEYXi1pwx9KEtHqMd5QRTFLdOy5LW+37KsC1GcvA6iVmEzuc65fDqQ4VFhW0w9b7XTIulkxIW3zoT66aog6xZETKi68iO+lxXEXW/lONADHSFiaZqmPj83/dHl9pW8KF/oht4xDAMMw/igXH8BqXxXmazMxHHcnZiYWOXcqyFiPpSpaZpDv5Vtu7U4SUn6URYne8S5VztR+kQ0Zpqm3t/3VwAAzr1anOz1QFOybV47CZlBwf4G9cI0zcuDmv6X1et1AwDA5m4tzYmCKI6YDJYO//v/Z+p6K42Gc2fkBDrtdO/v/wAMZw0y+9RlDAAAAABJRU5ErkJggg==",
        "zoom_in": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACrUlEQVR42p1UO2sUURQ+ZybjGhMfESEEI4iVRQohoKCCxk5BELESUYvsX1BEO7UQsbARwcbWKfwFaVIqeYAhENJEN5m9d567M3dmJzPZmc8iu4uPJBv9mnvhnPPd7zzuYdoBAJiItPn5eY2IaHJysiSikplB/woA2h42vV/8wJ9kzFwSESVJfj7JWtcN3TBQtL+srCzPMHP6q8++lK2tbZyLknShAOA3FIKmQl4AUZx663X7DhGR2U8pAA0ACyEmorgVqmSzVq/bD1ZXUSEiWhfuVFMlswDwY6P+oF9ptglN6MJ2lxthZC0urh0jInLdxlXHC54xb/u5QfNz0koz32+dAsA7knYLLTzvQlEC63V5r2sTtv+yAHqdFaJxOmmlhbCDJ53YgT/5eqOhgW+EUVyOj41+EsKdygq8YKKLrhvkSZq9ktKZHhsb+d4M4yWm4lYn/q/m9CSDuVKWYGbeYp0vD2j0FITLAEjT9EfE2n0iImJsgblC/WbLdYObebuAZfuXAFQAHJG2/7aVteF5yUnbxnAQBEebUayEE7zbNWUiKgFwmo7MNMMoOqBrr5k5Y+YIJb4ppWaXlr7ao6Mc5wUeDx6sHBo8oL3pNAR7qqzb3u12AYQqNtcs62zXXqs1j4cqed4I48IS7oKU7t3dFP412BvCexi3siJJc0jXXxS2N+94jXyrAITtzXlBKDfzAtLxp3ci7TWFmUvTNPXxsRMfHWmdaRflI13XW4ZhlIZhvPecYIJRvhk+PDyqlNoaGhr6IKVfZeb2nkpN09zzW1mWU1VJBjcIc5VsQkq/uq/0AQyYpql3792TiEhKv6qSzQ5pBsuS1f2I2e2x30n9Zpa1y15N/wtzc3MGEZElnWrWBhqhCoXbuNZZzP+HnlLHn67V6lf6bqB/3e7d+0+K0Bw+zO5T6wAAAABJRU5ErkJggg==",
        "rot_l": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADaElEQVR42oVUXWibVRh+3nO+L02bdM2yVE2WnxaHF63oRb0SpcWJeKMg2CKCFzJB3NVgCtoNvlTWxql0FwMvVBS8rAhD1BsvuiFYkQUntJMhYzHtki0paZOmyZfv57xeNFmTZekeOBeHc97nfXjeH0I7DBaYIxVL5S6C7V/XZxM/jhmrnv6IyUgD6fAOIznlgojRA9R5ZRoz1vRqf2CNvIGEa26/u/Fh9NuuqCWWmIECuom1fS4WIFLmQCEB4jBbVU3q3m/iqY2nQKIEKUjK/r9MVV3Jz9BmM4buV3uPcDIJcQVQNjde0I9Efc5WAco2LT109BTc5icB6BWnEv+88FV1Z/vjElGlZVMX4SPXwTAMARZhtpyLzM5PQz5RapTzUx6d0rCVx1LqWcXiTTkcOe1nPO9P/fdy9iPaalfa5SEMUHvGByF2/s6s5js879bLf/QreulGLbSLJBhErN1XI8YceHKZtdOD8EzEt94B6cOWWWMA7D90SDZqtb+j4SMLowsbpD929FztTtbAHL2PcZbAPXPaNDJLAMjmCpP8AOTublq/r2aDAIuR8/l/Ep8Vd8LG7VCrSKJnPxHJhuW4ACwADgAbgCOFqOTLugaQYna+k0MhvxzAcwCA5GUpDrCKQSSbhWs/ItinFABIoj+hwIL5aQCYyA+2K2SCwdqXaRyUpBOSGgATY59HdBaEnPeeIRvMtGcnu02jO05dEIGZlKJxEgQGZwAgHZ5gba+HgHgqG4DuW9Cd3X9vEi1WbhUGoh5NApDtopTioN8PgIjVQvYN7FZcyXK59dzWNkOAWz+hvEPOyJm1H8ZG6LfbxcolXSLg2A0GBHv7fZppq2tTT0SKiXO3XpOh2JS9mb20PpvIYJol5sjdH3YAsdTGK6NfWBxfLK14z+QSvayLzGeOjyyWtxIXtouxT+8+DmaCwaJzUpZYYobc+HzmhDwc+5prJVPA/kRj55egwE1T0+SO6T6pgLfgf/RtZVYrql46vn722NX2eabutURufD7zOvUNXpCDwShbDbjVTReAkIEIAQy3Vl5x6uWTubOj11oxPfYhgOklie9n3GFj1T/gC73KQn8Ryj4GZobWdxXK/Tn7wfAyAG79fXh/NT09EE3PHrKxO4aakLy8R3y9yAAwOTZNV8bBvbY1APwPdUivS3Yde2QAAAAASUVORK5CYII=",
        "rot_r": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADd0lEQVR42o1UTWhcVRT+zr3vTd68TGaSZyZ22mSS4EJoCq1MkRYKsYIblSJCgiuhoAsX4g+CxgRnBmpaSQXdKIo/oBuZCAVXIorJwi6E4KamYCNmfjJjM9NmMsl0kjfv3uPiTWoTJ6kHLnfxnfvxne+ecwgHBTMhNScTpS5CAmgULVpMH3MHprPnQOYT+YnDLyPJAmnSO09oHyZCBgLjpPYi/ZcK56XV/QlvVbOhRnVkMT3SBIh3cKOtKiLGOFTs8kqvJUKnlWo8AqUZrB0yrVfZ3WQIM7Zl9w0CdAPMAuSr3E2Y9AEn+Uc41NX9DiBfpFA4bOiwj0ugeWvFJWkGjJ6+zmal8DiAG6MpiHlgD6GvTMcvZntgBL83neijqlxcktXCBwEhrsIUrtvkhN0p5tYbnsOu9zRYxJBMir5F8G4PmQkp0MN2pbMh+AcZjJzy6muT+TcPTR/4aUkWSIP/6+EsBNKk7kxnk4Fo/JT+e2Uq/3b/dKF0a6zDto9v1moKAAUsm8DN8kKu57P3N+DOnyWvfWsAiCVXegdnyhtD75WuAyyuXss5xZsVl9tErrg66j9luZdOIDUnAUDaOCMjvSFm7yuAdGndNKQQNQAegGbrdrddTxGR3M8FkSh1EQAI5uPQYEn0KwA4HVoDEC1b/j0+Ge9LeLdykACYIGkb/zM+XYBAkg2A7w6IsRBLsE/IyyQIStMImH9p/FYiAKp1uNURmpnZT2d6iajZTqEGAMnyZ1WvKe15z4GIQyFAa3b8dobRuk0rYMjaFtsg4uFL2dfjlysfxy9mewAmMJMvdYwlZkkNTGevmL3xZ9Tq8rP5qeErfxbKH4a7Qie2GnUP0GSYHdRUqB6Jus8PT606FD1yXW03DOjgg7mJSBW804dH/RIws/qGqq+fIdv54tC7y7Xh/ugr7byzJouDfQ/EvpEBO8iNzXP5ie41ZFiCSNHuric9cGHppAg6PwkrFMbmzS8F8HWXJa9ZnqduazzkkfGkhvkW2Y6l1vIv5CaHPkeG5c5m2r2+WsDhC3+dMIKRj6QdOQ0QVLXIALQM9UoKdEBt3C7w9sZrucmhb+8la78PxzISs+MKAMVnymch5FPwtk+CiCDMJdLNH+/UK9+V08c278m9TyRZ3Dcnw22nhQ7Y/4QMxOjvoPnFWX8yjkb9/NRjCkRtp+UfE1KYZMudYDcAAAAASUVORK5CYII=",
        "rot_many": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADFElEQVR42rVUPWxbVRg95773/BPbtRtkLBXFSlIpQytgCBNSpYC6IaEyUCYGhFDZEEIQIYpM1aEChhQJhkjAwIJU2MoeMaRUSi0xIZEEQh2wn+3n3/di5/n53a9D45BYNQpDz3jv930657vnXOCkECEKYh47K6yZKIjC/8ZY07lbklxcFetR9zxOQjg+6xOA10g99+EfufB0cpnAa1DGGZHQBa3beq918+/C2Q3cEgOXGfIkBHPXd5fiicRtmvHkcK/xo4jeVOQ0jOgbaiod1e3qW6Wr+a8XV+9Z4wwVgOmy64KeR6efUk/PJ/WzN0uvO2H6pVjovv3n8szWqD5/4/5pRlOfq9ipNwdu5cV/lmfWOJK5u7sbi0QTP8Wn4vO9fi8kYAEKhmkgGTXaMeVcMuOzO9/fKcW/8meCnzeLxJXnAgDIf2b/TmVmJfCLJgCQlEqlkhLivNfdWyKDxr7vu3Nzc/sAYDutXxvDzNkQ2Ln8fL4/Yri4KlbxCgOGg09VMvuN+N5F84hcIcRLJKxqJpNt2Xb9krfnX3A9VyTUWUV5p9XxXg6GwV/Z6cyXBILiD9AoiBJ9/64OeiUZeGvH7EDA6Ha7rNfrKaH6zg/8aVKiJEwFpfyBD0V1vVxrLIEUefVhX+mj2d+Mfu1CZMj3D61SLpezds3ZaTab6Wazma7UnO2Rrey6s16pt14AgIrtrNtO65UDVcaBvsPHnehyAobjOGdExIQwoognRMQkGYOIHqsWiBAiHB8o6gAAoLXWAPRDMhiSHAKQRzOggDwSGZIAjJWVlU46ne4IoLPZoENSA9Ai2jpJCNQocq7r7kMg7773wUa13rxL8KlqPXan1mhtWJb1jBJW/t3ZZJgkRUS4sLDQrVbbF2PxqXO9fi+tqG5IqD9OJlMdz2vbudyTmwBQqTl9YnJiD40NALlcZhvAtsg9y67PfmFGo6rdbkNFInnbcc6HQ9GWac0Pw/C/Bx7NcrFYNLa2TqlUGt9GI9bVMAhEwqEiOYxFLAL4JRyY6wctGo8bnPxBizHBIgSgR2t67HgAbjCNk/XvqW8AAAAASUVORK5CYII=",
        "t_edit": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACNElEQVR42r2Tz2tTQRDHv7O7L+mTvNo0pf5AEAqeC2pykFZJ8F8QwZ859eRRz6/xLnoSRPFWDxEVBGmLlBDwqIgevAv1R5L25RfpS+zr+3poWtuaQBvEgWVnl5nPzuzMAP9YZEshKTvPPY1FQvxvkUKhYNLpdFBaWbkxMpK47nmrG6AYARUgpCAYjjmq0ax9OnZk/DZJERH2AxrHcTbTJCYjGhfHEgmIAnz/F4w2sCwFLUCjKeM7vqkvULZe9DzvpO3EJ5rVakCFycNO7EGt3vwQBht3nHhctfymd3R09PNA/1D5XjlLkj8r3vxBfdWW4rquIhkhqWGZWLfyFknd3dWBIyOpAaBc9s6T5I/y6tvuveptDyEhdP8EZgZtDxIisl0c0oWSHEI1GMxVImD1/uRI52XmTf3p9DnJISRdZQaD5cLa3FTc1mYhEtUp5TDlP5u+DOQK/SIkgLC7/oY9nIrbxixGojrl1zptE9VjoJqQzWnoObMGgBKRQz1hCbMYsXSyvbbesW1rqFltz9hXi0/y+Ut6b8ohABiDjwAyEkp183oWInd3w/z1zpBtRVtrwczwzXePWbhgJP08kP1UEwLgHuKdE5mFqIVk2w+2YbFrxS6sGOxq7D39KCR1Pp/XmHVlnow0TmVfR6WV9NthZ8g2PWH7bvRvVZ5ut2oMl26RL6bYmkvPAMD7R2esgSanVCplaz7LjfLXpfqrK1kAYME1g4yiAECl0jq+vPwlsbPi/Xx+A6+rKTEdcq7JAAAAAElFTkSuQmCC",
        "t_mark": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACfUlEQVR42s2Uv2sUQRTHv29n98zdJpdfRjgLyYGNRay01lJSCxbBn43YiH+BwcpSUEFjGsFGUggRglidgmBhZ2Onhzl292537za3ubu9ndl5FnfokaiJSsBXDcPM5735vu884H8IZqa1NRYHARb/VBUzGwDgB60Np+5fHO4bzEx/AzQBwK0HjzQzR+0OB81oeTThH8Nqbv1qXzG79SD1GqHqK+aGH72o1WqzwxeQuQ+YQUTKcfxTBbvwIG63MwBmlmVapikY+qgQIgFAAAaa/E43AKjVarO5sdwaGYadpikxM9u2bSRJ/3N3m86VSqUOACaiXwOHMEFE2srln9u2Xd6O44yIyDRN1syIO1tL5fJ0xMyCiHhfujmuf68vNbv1QHqNkL1GKJNU86bjXQeASqVi7qMJg0PVTed8J5Fc95vSa4TseL5KpGbH9VdGk46G+fMmGOprkxcmze0nSa+nsywTAHSxWBTtaOv9yuOHN4amzvaoDMTMxC9RaG1WPrb7zK7XUI7n6zCKddDc8lzXPTJq8p1BP2BnTLzKCxybYOl/WrUmrUutwk2VzC2ZQsdcLI5TK3QWSyvl19Ury7n56huFs6OotxkRdrs7Xi+fLMyNf9BKGyS7onf4gsbx2xx289fm5+jZXvoTAPCXy2PotG5BUF6r7BDSeJGTaCFLlLYsaajJ06FlpffBSgCad4oO2yIk6imdWK8OmmIEeZB5F1M5GH0NJDloI5cJqwfOz2QWRTOYyN8BBLBzwGgGihbQle8AVM2RTBJSW8gYGCMYhSkBmgZYAwxAMgYL7AZKDWBg7AEwLkigv4GesiG/CzG4T7TnZ4dpELQRHMg0/wZzLo40Ay8lVQAAAABJRU5ErkJggg==",
        "t_hide": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABjElEQVR42sVUsWoUURQ95963y4wJCRpEyy22E8FmO2Gn1DqlXbDRzlphpt8P0F6w2P2I/IZGZJmIRLtlwYzJ7LxjkSwYETITEjzwiseDc+89554HXDP45yXf3w/ZFUiyLGtICjcBSiJJTafTdHG8eu0W0lVzCtBajCf1k4TV8a93L/aefc7z3ML68ejopJdsWybELQkixMsIBUVEmamZAkBRFNfvx4UuRqPRTheGn+7aaBoOBoPFbDZrAJAAbDweW3n47T3JJ5IiAGvJGUlSUqlYPy3L8kcAEOfz+Tatt2tmva5zSoC7366b+ADA9wAAJEViKemOJP0txWVdSoKZ1wAQzqqIBFMAOj9dEAH0YkR/TWgkKwlf3O1hjN34SJikyqz+ujaFADQcDu+GkDw6V4ZtcwF3VnV1WB4cfOwoVcs9XEdvMplsbO7ce+Me0tXpCmatHFaSJFwsl29fvXz+6UL0+v377uaPnbal4K2cphDN3TZvpR9uInr/+A/z3NClSgEUxdkeX2Hd/hN+A/M5omSsJQvEAAAAAElFTkSuQmCC",
        "t_shape": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADeklEQVR42r1UXWibZRR+zvne72sSkyWpS2j6v1YRqmxIkTm86MDihjgQJL1T2YXTC0UQeiFWvkbsOp2iVS9chXWidbLeyVBhw9oNBcsyxmDdxNHUZG3adHRma7J0+b73eNGfrfuJeuNz+z7v8z7nvOc8hBWIDU4ebTfwD2hPJh0CBP8X6Eg8bnSNjLjZJ7ZuDzFvXyiXGcR8B1O09hmGLrF8GTs5nhLbZkok9O001TI5yQBcrfXTHsvqFscRg0BrL2K5PgYjZCnMLJV/BZDCxATdzeFNJyKl2VLJUZpjbHoDCmoDm96A5XNDbHoDDmTnkqMdEilVKlndLJ4ZBHXd48lvGhu749L01vYCEylXM0OE0NWFyg5X4C+XTQFIABaApKNDCUDXLZ+liRF0rjkgkp/b2ghHxLi3wxVo0xQCRJb7JxKNCtlCMryhiEgrToda/ZHPzvmffJUWgQQgQiCSewqapmlIPG4glyOJRmUw3MlIUPm1l4ceXgjV42S47XtvMUcNH8yf1dr5KEN0aFkUAEjWCQqA6uPH8+ufGHFb+6ZeGg7EDrTkU1JbyH097duYZs27zOraocb357algVdgg5DALYKitSLW09se20EipYLl47qrM7r78Z4HvwnEBp+9+N3lT8b7qv1/nvmYsjgNoKdpf3a3CtYcbOifTmcS9X2wR9WaoBCpiGVx0XV/NIlQTRpVXj+uBOvQkk9h4Ld3N/osDy481Bnp2HNMbV74wfi0OzbUuDezk5T5dsSeG5hPRAuqPZl0AMBw6YuS1sfyjuMuMXOVe0Om7tvkPRF+5GhtIXvYlfLQJa5hnzOTHEuQs3jgFMEWdjl7yPLf3+Ut57YA9ItaXfTY+HgKQGr9DJxD4w420v76P8LjEz8B57GaC8lwu8YMQAYKEIir2Fr3yzbAvfH42joNToZ5pqWThnT5giV4joF3nn/xoGequdkZm5iXB7JQFxO0RH2pXdpYJFUsna8cGytD29CfeaFlUKRp36Xdt1Pq+jNbmgeuug17M8PLrkYVVRS1hdELadqf+9wIRvc4f819K3AOa0euGczPsDfwhohzSkr8VLoUzKMXUlkQQhAARNL43mwPsfEm+0I+ANBLi9C6/BVdnn09vW/zldWNoX+Vmivk+g/TXpaqR9kwFRVv/J56q2bu1vP/FsX2qLprn2W9qb8Bm+6CMgNmtUIAAAAASUVORK5CYII=",
        "t_memo": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACm0lEQVR42q2UT2tVVxTFf3vfe1/y4kue0UZB20ITEiqaIEJBaDF0UBwWStORg0Id9gM4E7+DM2dqoDwcCEKhAymlI1toQFRooWraJlpipWli3rt/zlkdJM8kmoSkdI/25Ky19lqcZbwyEsZexsBAbAW0Z7Du24v4BnwQWJdF028PUpgW29oRvFk3MSTjx98W7RJRwsyQdZd/psfe6E3jVc/S0yFIXbKdhHlimMJcvlSd3/f5ox8k3NQiYWjSivk/vq4df/Mj0iYQd3msQ2xT/jK7kMV8gqnZP1P7jKDpR4Oq1T+g1gxYYiSZYbuwswzEZCBkBxpDndnO8brxNAWgMFlGB6jnnUK3vrljnSLgvm2wlBWcnRzn8NFDTpDksQJIXxpiOIg0TTg1MUII2tZFA2KEgf6+1cXMLK6GmG62GZIkYfjE8M6RdCNbziFs9jt9lTqEwOy9h7tS+NaRA9QbfdsARgRGVQV+uvuQvKiw7Tw0KEto9o9TbzZAkqJpHbAmw0ljRD21jE8/ObOmztZv1NYpUwXh7kbMAFJdxCmsbR6eeGyP0jNQqgoZMYIEEnIX7hFhGzncTVRFEpZWsFrtdwCTcDNice2d97zRczPp7ztSrgT54H7z3hrRXN5pm+XLELU5GDdiOy+KxRdf1s89vqIWiXWLwQwtXR0+1MjiyU5ll3snxkbZ1yx5tpCF+fmqWupcUNAMVllqFhGiJ/Gw4nO95x//3MVYJ2yRALSmSPIb7/6lBx8H3TmjsjXyfOX68Pu7bZv1lKdWG2P52uGDJos8f+Jh7tlMHvyLxrlfZ/TtZMrCd69Hcx/ZpS0+f1dh+6uRD3X7mMrWyPd/T48PrilI916Sa+X6ojV6tLgxdkGtqWQj0f8y/6XB/wWKX0LP1tZMmgAAAABJRU5ErkJggg==",
        "t_erase": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAACOUlEQVR42t3Uz08TQRQH8O+b3f6AFtJpBRWiIfHgFZMuB/4BwsmL/AMm5d/gH/HmzX8A92DixZhI449K4gFJWFpWKC07aQvttrPzPNBFBaoCnnynyczkk3kz7w3w3wQz09oai3+G/TQWN8UEAHw5PJzYqtXuAcALZutGmKeUbDRVWTVbgadUcbhmXwureJ5snHTfRa82uff8NSvVPto+Vs4olEZhRGQqrORMN+UWNnaczpvPGiQoOXfb6i7NB81UtPQgk9tgZpuI9EjwDFNKzhrh5j/VnM7bTU2ZtA0QzEnPpObuiHOoRUQRAIhLMc+TsyzcTHrMUVueFnbiNDVjIMbTItzZN2PuR1kILXf7+Nghoii+InEZNpOddPO5CYdSpPuPHVtPTYB6GhB0hva9A5Nefy9vtcOXu0otnBIsRFxnRGQqFU/OZHNuIZ9zAOiksGw5JdFbnoeenvyBMgO2RVE90OMikbeEuEtEDIAoLlrf9wupdHa9kJ8sAtAAzl5wwAZBPUB6/QPsRhuGiK1k0tDKonWYS5Tuj2WfxRmK+GFCogwJejg0frnbBAnIaYne8iP0ZYYt2za0smg1conVIWYRkblYwJ5fVK3OEZ9GxOci5Mg0a3V9snfEe91O6bcFHrfT9q7vjEANM+twEHE1CEp/1S3xhktQw8y61x9wtbpfulLrnUODIar7g4i96v4qAJTL5cRV+9gGgK+eXwxanUY4iLj2rf70Wp/CxZPuLlT9gyfDuT9+W98Bzcarw2SgurUAAAAASUVORK5CYII=",
        "t_capture": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADkElEQVR42q1US2gjVBQ9972XT9PpZ9rQ0g50VroYPwPTpjOppW3AUVAQEepa3AsulFkoxlkIAy5cuFNcikI2IjqfCnaGjnXa6ehQIV10p0mmNm2SNp8mzXvvuEgidWgFwbd7vHPuPe+eey/wPx8BgHL82aEyQp9poPeQ9L3G6Ip1a6MvvnTl0a3vP3LUX4m4VwXmO8A/T/jTYaUuNbz3gKDbKF/3/oPh5fv3DADsI/T5cDDwylbj0ImIB6AJHqbSaZmGXFaaiyTmCPeLeEwrJWECMxQQAAIiuupx7vfp6acFADJTk3cUOWWMHxMXqkStlZxz9syDB7XjvsUkFH6Y6i5GGsrVQr7BwxtCidWbfsgAAL1vUoT1ZqA0dm/54J/kpAIAPJUWvJ7yAESuwgPL5Q4mEx+3hNg+rWkAQER6urUO+INmkEC9XVsKwNtzcyqRSFgAIKkBeIgIAWAeCin4HNEbVCqimlZMO8lPNWvLBJoDANmKSABIJBI2m81GIpHRoIiUjrrJc62kGSVLTc/tKNA80X6SQlJt7xTe3y3u/5Hf3dstlMpfZLPZaPtNTiYDikmoI8E0AGxt7bxHkvndPf6ZL5AkH23lb5FJRVIdx5fjlIkINzY2evoHhzZDwWC00WgAgBIRG+7qChw0ahdHotFVklpE3FG+Okl1JBIxAulyznWCifdetNYA9amTeAoAOD+vOTvbcZwk9djYWInefRMd6NMAHMlmNBo11Wp1E7a+0q6hf5z/b4ZINpuN7hT3r5fKNZarDe5Var/lcvlYG6NOnOXMVOwNQM7WegeuPXnzZuNx0M5OaVJr3f3w4dpSIpGwnTqTEBEwE594U0FGR/oGPzZtm946bfSFcKHwCYAGARGAndYQkdUj6lV73oEPW+0I4O2I0s8U8/lPTRtULFl72OW8MAmF9LwwlaKI+LXx8QAXF7m5vq6fKBSat+fmFJNJAFcBzCom7yC3wELFuWpY65aCTDz2I4CZMz+vBgStqfovJxOfWBTKpZCX4Y4zwX5jdPZibCkjE67HGFVx9v7oCy+/k1u4fs0r+RKer2mvvqXylwEMhETidfrO+hq3hNSUMgYAjODdinVfGy0XrIcHaUjsp9JpeY6YEecXIBIH7AohkwIJE4gJ4AGBgapb+ivbtln+e1J+PX++/6wx9FpzEMBWve5G1terx+/DpMLKjVO7hdbdBIO6/+7dIgD8BdQH6xP7nt0QAAAAAElFTkSuQmCC",
        "m_view": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADHElEQVR42tVUS4gcVRS9972u6k/6M9Nx7PycMAk9C0FcKAFRkaALzUJwY7YmgmQhZCVZJNIhIogQEoSYVQgSUOlxocaNEOxGXIRZjFFICB1HZGY605+qrq5vV1VX1XFhGlozGrPTCw/e4rzDubxzDtH/egAIAKnpU6/XJQB+WKIHPvo7DP8FxETEzJwQEfVMc1GQ+mwUR4tRFLMquacI2Zydza9MbzHB0xZkRETU04eHh5b38yhMEI4jjCzd8C194No2IgCGabe1gfXuC7VaakL6J4UTsvX19dl8YebizEzh9YHp3ChIOvvVLUP7cFk9EBMXX90X/XD60KNeT3ePl2dLh0b+aMUy7Df37KncmCjlaWXdvv59sVB4xrCck7sC96PKFa5GIvfFtnyhSgAFI8/yR/Yx78z8Z7d/67xW2V76GERsD0cHdu8urwEQotlsSmZGRxucq8xtfy4Ix1IQTpvFkvf83sxPquRquHwp9pcvR2kRFRfmtn16c22AmZzyueN6Owq5TEWq+BpAemlpiZmIGIDo9odHslk17/q+VBnqqh6nD1+VJ8LeHdW89oEAEZVffCeJK0/w8SfdS28/pf5qBJwoEoGiKNK1zcvz8/ODFBGBiIhSWB6NA8iEhQdOSqkwk+b4aFDevyv3+MtjEAkqL0AmYSxT8ls74NtRLBRwEOWVgozSfkhERI1GIwVAbPa0LwFgMLThBTEA4OotD3vP21i4EGL/hQCVsw7OfGcDAMYJYJgOAKCnDbqahmKtVhM8+Z1223pEzSY306qa9zzvlOUmzWpFZg9+4s/9MqSjipRFQnTl+htKi0h1xsm4mstm389k0lXTMA/u3DnXBCBp2kd37/afthyvZZhOqBvme3c29MfE/X7Nd/r6W4bprLmeb29sdo9MknNfbomIrrdaRc0wL3pBhCACNnu6u76p/djuaCvtrt5x/TFiAPrQaqyubixuaeytYtR1nB1yTK8IQS8hTqpRErMU3GeW11JC+aZUyrQmypg5/qfQc71el/+iQHha2QOnVquJxh+VJe/VmLh3Tz0U0X9ufgdtGw1zJ+w01AAAAABJRU5ErkJggg==",
        "m_edit": "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABzklEQVR42q3Uv2uTQRgH8O9zd6/vm5IG3o4OdumknUpfHCqEiJs4OCgIWYo0iw7Sye3ULZuDOBihFqpISqlLxQz60qVLM3TyD3BQQtIm7ZvLD973zeMQW5UuyZs+0y3fD3fH3RdIOFprwZoFLmKYmc7WWosJsSFQL3643CxuLQAAl8tyAozQespu5+XOQf/V5069uLk43Onw+DQORvRi0Hq95DqZKxW7/cDr9SyWKm72o/h++smdb9AgMTr2fNB6v+SmXKtiT//wjLMWxjCxZaVnmOM5AjGubZIcHbvhppSqXHKkZwIKpX0op6aPZHA4u5JZvVtizYIezw/UWJgtPROEoZAkHSsjTP97IbO6/pZ9rShHEQCoJFjKkcJ0wkI6v19i31eUy0WnOUqGxYV0frfEflZRbjf6NysuEjsHTor9B/59Z8mxsztkBhGBWxozztWbX2ybEmEAIIgIeKZpjzklFx/u2KrnmfYgEQYA8H1fAcCvo/btbtDg4FO+01tfiHn7Frc3sisAwH5Wjfzhq9WqBQC1Wv0NM/PJyTGHXx9xd+36+NhptzGzU2s0PxrTfdc4jpZ/1s2wQcr3ktYSnwtOXJx/YMXMqpy0MAH8Bm2cRjgmtzzxAAAAAElFTkSuQmCC",
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
    },
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
        self._icons = {}         # (light/dark, 이름) → PhotoImage
        self.icon_users = []     # (위젯, 아이콘 이름, 영역 top/bottom/menu)
        self.memo_side = tk.BooleanVar(value=pr.get("memo_side", True))   # 메모를 오른쪽에 펼쳐 보기
        self._memo_pages = set()
        self.sel = None          # 선택한 글자 {"page", "text", "rects", "y"}
        self.selecting = None

        self._build_ui()
        for f in files:
            self.open_file(f)
        self.on_mode(quiet=True)
        self.apply_theme()
        self.set_app_mode()
        self.root.after(200, self.poll_ipc)

    # ---------- UI ----------
    def _build_menu(self):
        mb = tk.Menu(self.root)

        fm = tk.Menu(mb, tearoff=0)
        fm.add_command(label="열기 (새 탭)...", accelerator="Ctrl+O", command=self.ask_open,
                       image=self.menu_icon("open"), compound="left")
        fm.add_command(label="새 창으로 열기...", accelerator="Ctrl+Shift+O", command=self.ask_open_window)
        fm.add_command(label="새 창", accelerator="Ctrl+N", command=lambda: launch_new_window())
        self.recent_menu = tk.Menu(fm, tearoff=0)
        fm.add_cascade(label="최근 본 파일", menu=self.recent_menu)
        fm.add_separator()
        fm.add_command(label="저장...", accelerator="Ctrl+S", command=self.save,
                       image=self.menu_icon("save"), compound="left")
        fm.add_command(label="원하는 쪽만 저장...", accelerator="Ctrl+E", command=self.extract_dialog)
        fm.add_separator()
        fm.add_command(label="탭 닫기", accelerator="Ctrl+W", command=lambda: self.close_tab(self.tab))
        fm.add_command(label="종료", command=self.on_close)
        mb.add_cascade(label="파일", menu=fm)

        em = tk.Menu(mb, tearoff=0)
        em.add_command(label="되돌리기", accelerator="Ctrl+Z", command=self.do_undo,
                       image=self.menu_icon("undo"), compound="left")
        em.add_command(label="찾아 바꾸기...", accelerator="Ctrl+F", command=self.find_replace,
                       image=self.menu_icon("find"), compound="left")
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
        bm.add_command(label="파일 검색", accelerator="Ctrl+Shift+F", command=self.focus_search)
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
        self.root.config(menu=mb)

    def _build_ui(self):
        self._build_menu()
        self.topbox = ttk.Frame(self.root)       # 도구줄 1~2줄 (창이 좁으면 도구 버튼이 둘째 줄로)
        self.topbox.pack(fill="x")
        bar = self.bar = ttk.Frame(self.topbox, padding=(4, 3))
        bar.pack(fill="x")
        self.bar2 = ttk.Frame(self.topbox, padding=(4, 0, 4, 3))
        right = ttk.Frame(bar)          # 오른쪽 묶음을 먼저 배치 → 창이 좁아도 항상 보임
        right.pack(side="right")

        def btn(icon, cmd, tip, text=None):
            b_ = ttk.Button(bar, command=cmd, text=text or "", compound="left" if text else "image")
            self.set_icon(b_, icon, "top")
            b_.pack(side="left", padx=1)
            Tooltip(b_, tip)
            return b_

        def sep():
            ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=5)

        btn("open", self.ask_open, "열기 (Ctrl+O)", "열기")
        btn("save", self.save, "저장 (Ctrl+S)", "저장")
        btn("undo", self.do_undo, "되돌리기 (Ctrl+Z)")
        sep()
        btn("prev", lambda: self.go(-1), "이전 쪽 (PgUp)")
        self.page_var = tk.StringVar(value="0 / 0")
        e = ttk.Entry(bar, textvariable=self.page_var, width=9, justify="center")
        self._page_entry = e
        e.pack(side="left", padx=1)
        e.bind("<Return>", self.jump)
        btn("next", lambda: self.go(1), "다음 쪽 (PgDn)")
        sep()
        btn("zoom_out", lambda: self.set_zoom(self.zoom / 1.2), "축소 (Ctrl+-)")
        self.zoom_lbl = ttk.Label(bar, text=f"{round(self.zoom * 100)}%", width=5, anchor="center")
        self.zoom_lbl.pack(side="left")
        btn("zoom_in", lambda: self.set_zoom(self.zoom * 1.2), "확대 (Ctrl++)")
        sep()
        btn("rot_l", lambda: self.rotate_pages([self.page_no], -90), "이 쪽 왼쪽으로 회전 (Ctrl+L)")
        btn("rot_r", lambda: self.rotate_pages([self.page_no], 90), "이 쪽 오른쪽으로 회전 (Ctrl+R)")
        btn("rot_many", self.rotate_dialog, "여러 쪽 한꺼번에 회전")

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
        ttk.Combobox(f, textvariable=self.shape_kind, values=SHAPES, width=5, state="readonly").pack(side="left", padx=(4, 0))
        self.shape_swatch = color_opts(f, self.shape_color, ("#e53935", "#1e88e5", "#000000"),
                                       self.set_shape_color, "지금 선 색 (누르면 색상표)")
        sp = ttk.Spinbox(f, from_=0.5, to=20, increment=0.5, textvariable=self.shape_width, width=3)
        sp.pack(side="left", padx=2)
        Tooltip(sp, "선 두께(pt) · 채우기는 [도구 → 도형]")

        # 아래 상태줄: 왼쪽 안내 글 / 오른쪽 맞춤·보기 방식 아이콘
        self.status = tk.StringVar(value="PDF를 열어주세요 (Ctrl+O).")
        sbar = self.sbar = ttk.Frame(self.root, padding=(4, 1))
        sbar.pack(side="bottom", fill="x")
        self.view_icons = {}
        for k, t, _ in reversed(VIEWS):
            rb = ttk.Radiobutton(sbar, value=t, variable=self.view_var, style="Toolbutton", command=self.on_view)
            self.set_icon(rb, "v_" + k, "bottom")
            self.view_icons[k] = rb
            rb.pack(side="right", padx=1)
            Tooltip(rb, t)
        ttk.Separator(sbar, orient="vertical").pack(side="right", fill="y", padx=6)
        for val, ic, tip in (("height", "fit_h", "세로맞춤 — 한 쪽 전체 (Ctrl+2)"), ("width", "fit_w", "가로맞춤 — 폭에 맞춤 (Ctrl+1)")):
            rb = ttk.Radiobutton(sbar, value=val, variable=self.fit, style="Toolbutton", command=self.on_fit)
            self.set_icon(rb, ic, "bottom")
            rb.pack(side="right", padx=1)
            Tooltip(rb, tip)
        ttk.Label(sbar, textvariable=self.status, anchor="w").pack(side="left", fill="x", expand=True)

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
                  wheel_page=self.wheel_page.get(), app_mode=pr.get("start_mode", self.app_mode.get()),
                  memo_side=self.memo_side.get())
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
    def _is_dark(c):
        try:
            return sum(int(c[i:i + 2], 16) for i in (1, 3, 5)) < 384
        except (TypeError, ValueError, IndexError):
            return False

    def _style_set(self, st, pre, pal, size):
        """pre="" 이면 기본 스타일, "Top." 이면 도구줄 스타일"""
        bg, fg, ac, field = pal["bg"], pal["fg"], pal["accent"], pal["field"]
        dark = self._is_dark(bg)
        hover = ac if not dark else "#4a4a50"
        sel_fg = "#ffffff" if dark else fg
        st.configure(pre + "TFrame", background=bg)
        st.configure(pre + "TLabel", background=bg, foreground=fg)
        st.configure(pre + "TSeparator", background=bg)
        st.configure(pre + "TButton", background=field, foreground=fg, bordercolor=ac if pre else "#b9b9b9",
                     lightcolor=field, darkcolor=field, padding=(3, 1))
        st.map(pre + "TButton", background=[("active", hover)])
        st.configure(pre + "Toolbutton", background=bg, foreground=fg, padding=(3, 1))
        st.map(pre + "Toolbutton", background=[("selected", ac), ("active", hover)],
               foreground=[("selected", sel_fg)])
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
            fg_ = top["fg"] or "black"
            st.configure(".", font=(fam, size), foreground=fg_)
            st.configure("Treeview", rowheight=int(size * 2.3) + 2, foreground=fg_)
            base_bg = top_bg = st.lookup(".", "background") or "SystemButtonFace"
            self._top_dark = self._base_dark = False
        else:
            st.theme_use("clam")
            top["fg"] = top["fg"] or "#1f1f1f"
            top["accent"] = top["accent"] or "#cfe3fa"
            base = dict(top) if pr_.get("scope") == "all" else dict(NEUTRAL)   # 기본 색은 도구줄에만
            st.configure(".", font=(fam, size))
            self._style_set(st, "", base, size)
            self._style_set(st, "Top.", top, size)
            base_bg, top_bg = base["bg"], top["bg"]
            self._top_dark, self._base_dark = self._is_dark(top_bg), self._is_dark(base_bg)
        self.root.configure(bg=base_bg)
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
        self.cv.configure(bg=self.tcolor("canvas") or "#5a5a5a")
        self.root.after(50, self.fit_toolbar)     # 글꼴 크기가 바뀌면 도구줄 다시 맞춤
        if hasattr(self, "theme_var"):
            self.theme_var.set(self.theme.get("preset", "clip"))
        self.load_wall()
        if self.doc:
            self.render()
        else:
            self.place_wall()

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
            x, y = anchor.winfo_rootx(), anchor.winfo_rooty() + anchor.winfo_height() + 2
        except tk.TclError:
            x, y = self.root.winfo_pointerx(), self.root.winfo_pointery()
        pop.wm_geometry(f"+{x}+{y}")
        pop.bind("<Escape>", lambda e: pop.destroy())
        pop.bind("<FocusOut>", lambda e: pop.after(150, lambda: pop.winfo_exists() and
                                                    self.root.focus_get() is None and pop.destroy()))
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
        self._memo_pages = self.find_memo_pages() if self.memo_side.get() and self.cols() == 1 else set()
        self.zoom = self.calc_zoom()
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
            if p in self._memo_pages:
                self.draw_memos(p)
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

    def on_root_resize(self, e=None):
        if e is not None and e.widget is not self.root:
            return
        if self._fit_job:
            self.root.after_cancel(self._fit_job)
        self._fit_job = self.root.after(120, self.fit_toolbar)

    def fit_toolbar(self):
        """도구줄이 창 폭에 다 안 들어가면 도구 버튼을 둘째 줄로 (잘려서 안 보이는 일 없게)"""
        self._fit_job = None
        self.root.update_idletasks()
        W = self.root.winfo_width()
        if W < 100:
            return
        try:
            in_bar = str(self.toolarea.pack_info().get("in")) == str(self.bar)
        except tk.TclError:
            in_bar = False
        others = self.bar.winfo_reqwidth() - (self.toolarea.winfo_reqwidth() if in_bar else 0)
        widest_opt = max((f.winfo_reqwidth() for f in self.opt.values()), default=0)
        need = others + self.toolbtns.winfo_reqwidth() + widest_opt + 24
        if need > W and in_bar:
            self.toolarea.pack_forget()
            self.bar2.pack(fill="x")
            self.toolarea.pack(in_=self.bar2, side="left")
        elif need <= W and not in_bar:
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

    # ---------- 메모 오른쪽에 펼쳐 보기 ----------
    def find_memo_pages(self):
        out = set()
        for i in range(len(self.doc)):
            page = self.doc[i]
            if any(True for _ in page.annots(types=[fitz.PDF_ANNOT_TEXT]) or []):
                out.add(i)
        return out

    def draw_memos(self, p):
        """p쪽 메모를 쪽 오른쪽 칸에 노란 쪽지로 표시 (메모 아이콘과 점선으로 연결)"""
        self.cv.delete(f"memo{p}")
        x, y, w, h = self.slots[p]
        notes = [(r, c) for r, t, c in self.annots_for(p) if t == fitz.PDF_ANNOT_TEXT]
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
        m.add_command(label="북마크 추가", command=self.add_bookmark_now)
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
