# -*- coding: utf-8 -*-
"""smartpdfeditor.py 의 APP_VER 로 exe 버전 정보(version_info.txt)를 만듭니다.
Windows 파일 속성·'연결 프로그램' 목록에 '스마트PDF Editor' 이름과 버전이 표시됩니다.
    python tools/make_version_info.py
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(ROOT, "smartpdfeditor.py"), encoding="utf-8").read()
ver = re.search(r'^APP_VER = "([\d.]+)"', src, re.M).group(1)
nums = (ver.split(".") + ["0", "0", "0"])[:4]
tup = ", ".join(str(int(n)) for n in nums)

text = f"""# UTF-8 — PyInstaller --version-file 용 (tools/make_version_info.py 가 만듦)
VSVersionInfo(
  ffi=FixedFileInfo(filevers=({tup}), prodvers=({tup}), mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([
      StringTable('041204B0', [
        StringStruct('CompanyName', '스마트공 (smartgong.kr)'),
        StringStruct('FileDescription', '스마트PDF Editor'),
        StringStruct('FileVersion', '{ver}'),
        StringStruct('InternalName', 'smartpdfeditor'),
        StringStruct('LegalCopyright', 'Copyright (C) 2026 스마트공 · AGPL-3.0'),
        StringStruct('OriginalFilename', 'smartpdfeditor.exe'),
        StringStruct('ProductName', '스마트PDF Editor'),
        StringStruct('ProductVersion', '{ver}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1042, 1200])])
  ]
)
"""
out = os.path.join(ROOT, "version_info.txt")
with open(out, "w", encoding="utf-8") as f:
    f.write(text)
print("version_info.txt", ver)
