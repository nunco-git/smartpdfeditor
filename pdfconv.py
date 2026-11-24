# -*- coding: utf-8 -*-
"""스마트PDF Editor - 용량 줄이기 / 워드·엑셀·한글 변환 / 스캔본 글자 인식(OCR)

외부 라이브러리는 PyMuPDF(fitz)만 사용합니다. docx / xlsx / hwpx 는 직접 만든 XML을 zip으로 묶어 저장합니다.
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from xml.sax.saxutils import escape as _esc

try:
    import fitz
except Exception:                      # pragma: no cover
    import pymupdf as fitz

IS_WIN = sys.platform.startswith("win")
_NOWIN = {"creationflags": 0x08000000} if IS_WIN else {}


class Cancelled(Exception):
    pass


def _tick(progress, cur, total, msg=""):
    if progress:
        progress(cur, total, msg)        # progress 가 Cancelled 를 던질 수 있음


def _x(s):
    """XML 에 넣을 수 있게 정리 (제어문자 제거 + 이스케이프)"""
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]", "", s or "")
    return _esc(s)


# ──────────────────────────────────────────────────────────────
# 1. PDF 용량 줄이기
# ──────────────────────────────────────────────────────────────
SHRINK_LEVELS = {
    # 이름: (이 해상도보다 크면 줄임, 줄일 해상도, JPEG 품질, 설명)
    "조금 줄이기 (화질 거의 그대로)": (220, 170, 85),
    "많이 줄이기 (보통 화질)": (160, 130, 70),
    "최대로 줄이기 (화질 낮음)": (110, 96, 50),
}


def _shrink_images_fallback(doc, thr, target, quality, pages=None):
    """rewrite_images 가 없는 구버전 PyMuPDF 용: 그림을 하나씩 줄여서 교체"""
    done = set()
    for pi, page in enumerate(doc):
        if pages is not None and pi not in pages:
            continue
        for img in page.get_images(full=True):
            xref = img[0]
            if xref in done:
                continue
            done.add(xref)
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.alpha or img[1]:           # 투명/마스크 그림은 건드리지 않음
                    continue
                if pix.colorspace and pix.colorspace.n not in (1, 3):
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                rects = page.get_image_rects(xref)
                if not rects:
                    continue
                w_in = max(r.width for r in rects) / 72.0
                dpi = pix.width / w_in if w_in > 0 else 0
                if dpi <= thr:
                    continue
                f = target / dpi
                small = fitz.Pixmap(pix, max(1, int(pix.width * f)), max(1, int(pix.height * f)), None)
                data = small.tobytes("jpeg", jpg_quality=quality)
                page.replace_image(xref, stream=data)
            except Exception:
                continue


def shrink_pdf(src_bytes, dst, level, progress=None, pages=None):
    """src_bytes(PDF 내용) 을 줄여서 dst 에 저장. (줄이기 전 크기, 줄인 뒤 크기) 반환"""
    thr, target, q = SHRINK_LEVELS[level]
    doc = fitz.open("pdf", src_bytes)
    before = len(src_bytes)
    try:
        if doc.needs_pass:
            raise ValueError("암호가 걸린 PDF 입니다.")
        _tick(progress, 0, 3, "그림 줄이는 중...")
        if pages is None and hasattr(doc, "rewrite_images"):
            doc.rewrite_images(dpi_threshold=thr, dpi_target=target, quality=q,
                               lossy=True, lossless=True, bitonal=True, color=True, gray=True)
        else:
            _shrink_images_fallback(doc, thr, target, q, None if pages is None else set(pages))
        _tick(progress, 1, 3, "불필요한 데이터 정리 중...")
        try:
            doc.subset_fonts()                  # fontTools 가 있을 때만 동작
        except Exception:
            pass
        _tick(progress, 2, 3, "저장 중...")
        tmp = dst + ".tmp"
        try:
            doc.save(tmp, garbage=4, deflate=True, deflate_images=True, deflate_fonts=True,
                     clean=True, use_objstms=1)
        except TypeError:
            doc.save(tmp, garbage=4, deflate=True, clean=True)
        after = os.path.getsize(tmp)
        os.replace(tmp, dst)
    finally:
        doc.close()
    _tick(progress, 3, 3, "완료")
    return before, after


# ──────────────────────────────────────────────────────────────
# 2. 글자 인식(OCR)
# ──────────────────────────────────────────────────────────────
def _tess_candidates():
    here = os.path.dirname(os.path.abspath(getattr(sys, "frozen", False) and sys.executable or __file__))
    c = []
    p = shutil.which("tesseract")
    if p:
        c.append(p)
    c.append(os.path.join(here, "tesseract", "tesseract.exe"))
    if IS_WIN:
        for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            b = os.environ.get(env)
            if b:
                c.append(os.path.join(b, "Tesseract-OCR", "tesseract.exe"))
                c.append(os.path.join(b, "Programs", "Tesseract-OCR", "tesseract.exe"))
    return [x for x in c if x and os.path.exists(x)]


def _tess_env(exe):
    env = os.environ.copy()
    td = os.path.join(os.path.dirname(exe), "tessdata")
    if os.path.isdir(td) and "TESSDATA_PREFIX" not in env:
        env["TESSDATA_PREFIX"] = td
    return env


def _tess_langs(exe):
    try:
        r = subprocess.run([exe, "--list-langs"], capture_output=True, timeout=30,
                           env=_tess_env(exe), **_NOWIN)
        out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
        return {ln.strip() for ln in out.splitlines()[1:] if ln.strip() and " " not in ln.strip()}
    except Exception:
        return set()


def ocr_engine():
    """(엔진, 설명, 보조값) 반환. 엔진: 'tesseract' | 'winrt' | None"""
    for exe in _tess_candidates():
        langs = _tess_langs(exe)
        if "kor" in langs:
            return "tesseract", "Tesseract (한글+영어)", (exe, "kor+eng" if "eng" in langs else "kor")
    if IS_WIN:
        return "winrt", "Windows 기본 글자 인식", None
    for exe in _tess_candidates():
        langs = _tess_langs(exe)
        if langs:
            use = [l for l in ("eng",) if l in langs]
            if use:
                return "tesseract", "Tesseract (영어만 — 한글 언어 데이터 없음)", (exe, "+".join(use))
    return None, ("글자 인식 엔진을 찾지 못했습니다.\n"
                  "· Windows 10/11 이면 '설정 → 시간 및 언어 → 언어 및 지역'에서 한국어 언어 팩을 설치하세요.\n"
                  "· 또는 Tesseract-OCR(한글 데이터 포함)을 설치하세요."), None


_PS_OCR = r'''
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq "AsTask" -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq "IAsyncOperation`1" })[0]
function Await($op, $type) {
  $t = $asTask.MakeGenericMethod($type).Invoke($null, @($op)); $t.Wait(-1) | Out-Null; $t.Result }
$engine = $null
foreach ($tag in @("ko", "ko-KR")) {
  try { $lang = New-Object Windows.Globalization.Language($tag)
        if ([Windows.Media.Ocr.OcrEngine]::IsLanguageSupported($lang)) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang); break } } catch {}
}
if (-not $engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
if (-not $engine) { [Console]::Error.WriteLine("NOENGINE"); exit 3 }
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($args[0])) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$dec = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bmp = Await ($dec.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$res = Await ($engine.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
$i = 0
foreach ($line in $res.Lines) {
  foreach ($w in $line.Words) {
    $r = $w.BoundingRect
    "{0}`t{1}`t{2}`t{3}`t{4}`t{5}" -f $i, [int]$r.X, [int]$r.Y, [int]$r.Width, [int]$r.Height, ($w.Text -replace "`t", " ")
  }
  $i++
}
'''


def _ocr_words_tesseract(png, exe, lang):
    r = subprocess.run([exe, png, "stdout", "-l", lang, "--psm", "4", "tsv"], capture_output=True,
                       timeout=300, env=_tess_env(exe), **_NOWIN)
    if r.returncode != 0:
        raise RuntimeError("Tesseract 오류: " + (r.stderr or b"").decode("utf-8", "replace")[:300])
    rows = []
    for ln in (r.stdout or b"").decode("utf-8", "replace").splitlines()[1:]:
        p = ln.split("\t")
        if len(p) < 12 or p[0] != "5":
            continue
        txt = p[11].strip()
        if not txt:
            continue
        try:
            if float(p[10]) < 0:
                continue
            key = (int(p[2]), int(p[3]), int(p[4]))
            rows.append((key, int(p[6]), int(p[7]), int(p[8]), int(p[9]), txt))
        except ValueError:
            continue
    return rows


def _ocr_words_winrt(png):
    ps1 = os.path.join(tempfile.gettempdir(), "spe_winocr.ps1")
    with open(ps1, "w", encoding="utf-8-sig") as f:
        f.write(_PS_OCR)
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1, png],
                       capture_output=True, timeout=300, **_NOWIN)
    if r.returncode == 3:
        raise RuntimeError("Windows 글자 인식 엔진이 없습니다. 설정 → 시간 및 언어에서 한국어 언어 팩을 설치해주세요.")
    if r.returncode != 0:
        raise RuntimeError("Windows 글자 인식 오류: " + (r.stderr or b"").decode("utf-8", "replace")[:300])
    rows = []
    for ln in (r.stdout or b"").decode("utf-8", "replace").splitlines():
        p = ln.rstrip("\r").split("\t")
        if len(p) < 6 or not p[5].strip():
            continue
        try:
            rows.append(((int(p[0]),), int(p[1]), int(p[2]), int(p[3]), int(p[4]), p[5].strip()))
        except ValueError:
            continue
    return rows


def ocr_lines(page, engine, aux, dpi=300):
    """한 쪽을 글자 인식. 줄 목록 [{'bbox':(x0,y0,x1,y1), 'text':str, 'words':[(x0,y0,x1,y1,text)]}] (PDF 좌표, 단위 pt).
    좌표는 '쪽을 눈으로 본 방향(회전 반영)' 기준입니다."""
    r = page.rect
    scale = dpi / 72.0
    if engine == "winrt":
        scale = min(scale, 2500.0 / max(r.width, r.height))
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csGRAY, alpha=False)
    fd, png = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        pix.save(png)
        rows = _ocr_words_tesseract(png, *aux) if engine == "tesseract" else _ocr_words_winrt(png)
    finally:
        try:
            os.remove(png)
        except OSError:
            pass
    k = 1.0 / scale
    lines = {}
    order = []
    for key, x, y, w, h, t in rows:
        if key not in lines:
            lines[key] = []
            order.append(key)
        lines[key].append((x * k, y * k, (x + w) * k, (y + h) * k, t))
    out = []
    for key in order:
        ws = sorted(lines[key], key=lambda a: a[0])
        out.append({"bbox": (min(a[0] for a in ws), min(a[1] for a in ws),
                             max(a[2] for a in ws), max(a[3] for a in ws)),
                    "text": " ".join(a[4] for a in ws), "words": ws})
    out.sort(key=lambda L: (round(L["bbox"][1] / 4), L["bbox"][0]))
    return out


def page_needs_ocr(page):
    """글자가 거의 없고 그림이 있는 쪽 = 스캔본으로 판단"""
    try:
        if len(page.get_text("text").strip()) >= 8:
            return False
        return bool(page.get_images()) or bool(page.get_drawings())
    except Exception:
        return False


def _add_invisible_text(page, lines):
    """보이지 않는 글자 층을 얹어서 검색·복사·선택이 되게 함"""
    n = 0
    inv = page.derotation_matrix
    for L in lines:
        for (x0, y0, x1, y1, t) in L["words"]:
            h = y1 - y0
            w = x1 - x0
            if h <= 0 or w <= 0:
                continue
            font = "korea" if any(ord(c) > 0x2FF for c in t) else "helv"
            fs = max(2.0, h * 0.82)
            try:
                tl = fitz.get_text_length(t, fontname=font, fontsize=fs)
                if tl > 0:
                    fs = max(2.0, min(fs * 2, fs * w / tl))
                p = fitz.Point(x0, y1 - h * 0.2) * inv
                page.insert_text(p, t + " ", fontname=font, fontsize=fs, render_mode=3,
                                 rotate=page.rotation)
                n += 1
            except Exception:
                continue
    return n


def make_searchable(src_bytes, dst, dpi=300, progress=None, redo=False):
    """스캔본 PDF 에 글자 층을 얹어 검색 가능한 PDF 로 저장. (인식한 쪽 수, 글자 수) 반환"""
    engine, desc, aux = ocr_engine()
    if not engine:
        raise RuntimeError(desc)
    doc = fitz.open("pdf", src_bytes)
    try:
        if doc.needs_pass:
            raise ValueError("암호가 걸린 PDF 입니다.")
        total = len(doc)
        todo = [i for i in range(total) if redo or page_needs_ocr(doc[i])]
        if not todo:
            raise RuntimeError("글자 인식이 필요한 쪽(글자 없이 그림만 있는 쪽)이 없습니다.")
        words = 0
        for n, i in enumerate(todo):
            _tick(progress, n, len(todo) + 1, f"{i + 1}쪽 글자 인식 중... ({n + 1}/{len(todo)})")
            words += _add_invisible_text(doc[i], ocr_lines(doc[i], engine, aux, dpi))
        _tick(progress, len(todo), len(todo) + 1, "저장 중...")
        tmp = dst + ".tmp"
        doc.save(tmp, garbage=3, deflate=True)
        os.replace(tmp, dst)
    finally:
        doc.close()
    _tick(progress, 1, 1, "완료")
    return len(todo), words


# ──────────────────────────────────────────────────────────────
# 3. PDF → 중간 구조
#    page = {"w","h","blocks":[ {"t":"p","text","size","bold"} | {"t":"tbl","rows":[[str]]} | {"t":"img","data","ext","w","h"} ]}
# ──────────────────────────────────────────────────────────────
def _overlap(a, b):
    r = fitz.Rect(a) & fitz.Rect(b)
    if r.is_empty:
        return 0.0
    ar = fitz.Rect(a).get_area()
    return r.get_area() / ar if ar else 0.0


def _clean(s):
    return re.sub(r"[ \t ]+", " ", (s or "").replace("\r", "")).strip()


def _image_bytes(doc, xref):
    try:
        info = doc.extract_image(xref)
        ext = (info.get("ext") or "").lower()
        if ext in ("png", "jpg", "jpeg"):
            return info["image"], "jpg" if ext == "jpeg" else ext
        pix = fitz.Pixmap(doc, xref)
        if pix.colorspace is None or pix.colorspace.n > 3 or pix.alpha:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        return pix.tobytes("png"), "png"
    except Exception:
        return None, None


def _lines_to_paras(lines):
    """OCR 줄들을 문단으로 묶기"""
    paras, cur, prev = [], [], None
    for L in lines:
        h = max(1.0, L["bbox"][3] - L["bbox"][1])
        if prev is not None:
            gap = L["bbox"][1] - prev["bbox"][3]
            if gap > h * 0.9 or abs(L["bbox"][0] - prev["bbox"][0]) > h * 6:
                paras.append(cur)
                cur = []
        cur.append(L)
        prev = L
    if cur:
        paras.append(cur)
    out = []
    for p in paras:
        size = sum(l["bbox"][3] - l["bbox"][1] for l in p) / len(p) * 0.85
        out.append({"t": "p", "text": " ".join(l["text"] for l in p), "size": round(size * 2) / 2, "bold": False})
    return out


def _merge_wrapped(blocks):
    """줄바꿈으로 갈라진 같은 문단(글자 크기·왼쪽 정렬이 같고 바로 아래 이어지는 줄)을 하나로 합침"""
    right = max([b["bbox"][2] for b in blocks if b["t"] == "p" and "bbox" in b] or [0])
    out = []
    for b in blocks:
        p = out[-1] if out else None
        if (p and p["t"] == "p" and b["t"] == "p" and "bbox" in p and "bbox" in b
                and abs(p["size"] - b["size"]) < 0.6 and p["bold"] == b["bold"]
                and 0 <= b["bbox"][1] - p["bbox"][3] < p["size"] * 0.6
                and abs(p["bbox"][0] - b["bbox"][0]) < p["size"] * 1.5
                and p["bbox"][2] >= right - p["size"] * 3):
            p["text"] += " " + b["text"]
            p["bbox"] = (p["bbox"][0], p["bbox"][1], max(p["bbox"][2], b["bbox"][2]), b["bbox"][3])
        else:
            out.append(b)
    return out


def extract_pages(src_bytes, pages=None, use_ocr=True, want_images=True, progress=None):
    doc = fitz.open("pdf", src_bytes)
    res = []
    notes = []
    eng = None
    if use_ocr:
        eng = ocr_engine()
    try:
        if doc.needs_pass:
            raise ValueError("암호가 걸린 PDF 입니다.")
        idx = list(pages) if pages is not None else list(range(len(doc)))
        for n, i in enumerate(idx):
            _tick(progress, n, len(idx), f"{i + 1}쪽 읽는 중... ({n + 1}/{len(idx)})")
            page = doc[i]
            pr = page.rect
            blocks = []
            tables = []
            try:
                tf = page.find_tables()
                tables = [t for t in tf.tables if t.row_count >= 1 and t.col_count >= 2]
            except Exception:
                tables = []
            tb_rects = [fitz.Rect(t.bbox) for t in tables]
            items = []                                   # (y0, x0, block)
            for t in tables:
                try:
                    rows = [[_clean(c) for c in row] for row in t.extract()]
                except Exception:
                    continue
                if rows and any(any(c for c in r) for r in rows):
                    items.append((t.bbox[1], t.bbox[0], {"t": "tbl", "rows": rows}))
            d = page.get_text("dict", flags=fitz.TEXT_PRESERVE_IMAGES | fitz.TEXT_PRESERVE_WHITESPACE
                              if want_images else fitz.TEXT_PRESERVE_WHITESPACE)
            has_text = False
            for b in d.get("blocks", []):
                bb = b["bbox"]
                if b.get("type") == 0:
                    if any(_overlap(bb, tr) > 0.5 for tr in tb_rects):
                        continue
                    txt, sizes, bolds, nspan = [], [], 0, 0
                    for ln in b.get("lines", []):
                        s = "".join(sp["text"] for sp in ln.get("spans", []))
                        if s.strip():
                            txt.append(_clean(s))
                        for sp in ln.get("spans", []):
                            if sp["text"].strip():
                                sizes.append(sp["size"])
                                nspan += 1
                                if (sp["flags"] & 16) or "bold" in sp["font"].lower():
                                    bolds += 1
                    text = " ".join(txt).strip()
                    if not text:
                        continue
                    has_text = True
                    items.append((bb[1], bb[0], {"t": "p", "text": text, "bbox": tuple(bb),
                                                 "size": round(max(sizes) * 2) / 2 if sizes else 10,
                                                 "bold": nspan > 0 and bolds * 2 >= nspan}))
                elif b.get("type") == 1 and want_images:
                    w, h = bb[2] - bb[0], bb[3] - bb[1]
                    if w < 12 or h < 12:
                        continue
                    items.append((bb[1], bb[0], {"t": "img", "raw": b.get("image"), "ext": b.get("ext"),
                                                 "w": w, "h": h, "area": w * h / max(1, pr.get_area())}))
            items.sort(key=lambda a: (round(a[0] / 3), a[1]))
            blocks = _merge_wrapped([x[2] for x in items])
            # 글자가 있는 쪽의 쪽 전체 크기 그림 = 스캔 배경 → 제외 (글자와 겹쳐 중복되므로)
            if has_text or tables:
                blocks = [bk for bk in blocks if not (bk["t"] == "img" and bk["area"] > 0.8)]
            # 스캔본: 글자 인식 또는 쪽 그림으로 대체
            if not has_text and not tables:
                done = False
                if eng and eng[0]:
                    try:
                        lines = ocr_lines(page, eng[0], eng[2], 300)
                        paras = _lines_to_paras(lines)
                        if paras:
                            blocks = paras
                            done = True
                            notes.append(f"{i + 1}쪽: 스캔본이라 글자 인식 결과로 변환했습니다 (표·그림 위치는 유지되지 않음)")
                    except Exception as ex:
                        notes.append(f"{i + 1}쪽: 글자 인식 실패 ({ex})")
                if not done and want_images:
                    pix = page.get_pixmap(dpi=130)
                    blocks = [{"t": "img", "raw": pix.tobytes("jpg", jpg_quality=80), "ext": "jpg",
                               "w": pr.width, "h": pr.height, "area": 1.0}]
                    notes.append(f"{i + 1}쪽: 글자가 없는 스캔본이라 그림으로 넣었습니다")
            for bk in blocks:
                if bk["t"] == "img":
                    raw, ext = bk.pop("raw", None), bk.pop("ext", None)
                    if raw and ext in ("png", "jpg", "jpeg"):
                        bk["data"], bk["ext"] = raw, "jpg" if ext == "jpeg" else ext
                    elif raw:
                        try:
                            bk["data"], bk["ext"] = fitz.Pixmap(raw).tobytes("png"), "png"
                        except Exception:
                            bk["data"] = None
                    else:
                        bk["data"] = None
            blocks = [bk for bk in blocks if bk["t"] != "img" or bk.get("data")]
            res.append({"w": pr.width, "h": pr.height, "no": i + 1, "blocks": blocks})
    finally:
        doc.close()
    _tick(progress, 1, 1, "저장 중...")
    return res, notes


# ──────────────────────────────────────────────────────────────
# 4. 저장: 워드(docx)
# ──────────────────────────────────────────────────────────────
_W_NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
         'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
         'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
         'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
         'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')


def _col_weights(rows):
    n = max(len(r) for r in rows)
    ws = []
    for c in range(n):
        m = max((len(r[c]) if c < len(r) else 0) for r in rows)
        ws.append(min(30, max(4, m)))
    return ws


def save_docx(pages, dst):
    CONTENT_W = 9638                      # twips (A4, 여백 2cm)
    body, media = [], []
    rid = 0
    for pi, pg in enumerate(pages):
        if pi:
            body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        for bk in pg["blocks"]:
            if bk["t"] == "p":
                sz = int(max(6, min(40, bk["size"])) * 2)
                rpr = f'<w:rFonts w:eastAsia="맑은 고딕" w:ascii="맑은 고딕" w:hAnsi="맑은 고딕"/>{"<w:b/>" if bk["bold"] else ""}<w:sz w:val="{sz}"/>'
                body.append(f'<w:p><w:pPr><w:spacing w:after="80"/></w:pPr><w:r><w:rPr>{rpr}</w:rPr>'
                            f'<w:t xml:space="preserve">{_x(bk["text"])}</w:t></w:r></w:p>')
            elif bk["t"] == "tbl":
                rows = bk["rows"]
                ws = _col_weights(rows)
                tot = float(sum(ws))
                grid = [int(CONTENT_W * w / tot) for w in ws]
                x = ['<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders>']
                for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
                    x.append(f'<w:{side} w:val="single" w:sz="4" w:space="0" w:color="000000"/>')
                x.append('</w:tblBorders><w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>')
                x += [f'<w:gridCol w:w="{g}"/>' for g in grid]
                x.append('</w:tblGrid>')
                for r in rows:
                    x.append('<w:tr>')
                    for c in range(len(ws)):
                        t = r[c] if c < len(r) else ""
                        x.append(f'<w:tc><w:tcPr><w:tcW w:w="{grid[c]}" w:type="dxa"/></w:tcPr><w:p><w:r><w:rPr>'
                                 f'<w:rFonts w:eastAsia="맑은 고딕"/><w:sz w:val="18"/></w:rPr>'
                                 f'<w:t xml:space="preserve">{_x(t)}</w:t></w:r></w:p></w:tc>')
                    x.append('</w:tr>')
                x.append('</w:tbl><w:p/>')
                body.append("".join(x))
            elif bk["t"] == "img":
                rid += 1
                name = f"image{rid}.{bk['ext']}"
                media.append((name, bk["data"]))
                cw = 481.0                                    # 본문 폭(pt)
                w, h = bk["w"], bk["h"]
                if w > cw:
                    h, w = h * cw / w, cw
                ph = 700.0
                if h > ph:
                    w, h = w * ph / h, ph
                cx, cy = int(w * 12700), int(h * 12700)
                body.append(
                    f'<w:p><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
                    f'<wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{rid}" name="그림 {rid}"/>'
                    f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                    f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{rid}" name="{name}"/><pic:cNvPicPr/></pic:nvPicPr>'
                    f'<pic:blipFill><a:blip r:embed="rIdImg{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
                    f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
                    f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
                    f'</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')
    doc_xml = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {_W_NS}><w:body>'
               + "".join(body) +
               '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" '
               'w:left="1134" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr></w:body></w:document>')
    exts = {e for _, d in media for e in [_.rsplit(".", 1)[1]]}
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          + ('<Default Extension="png" ContentType="image/png"/>' if "png" in exts else "")
          + ('<Default Extension="jpg" ContentType="image/jpeg"/>' if "jpg" in exts else "")
          + '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
          '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
          '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>')
    drels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             '<Relationship Id="rIdSt" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>']
    for n, (name, _d) in enumerate(media, 1):
        drels.append(f'<Relationship Id="rIdImg{n}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{name}"/>')
    drels.append('</Relationships>')
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr>'
              '<w:rFonts w:ascii="맑은 고딕" w:eastAsia="맑은 고딕" w:hAnsi="맑은 고딕"/><w:sz w:val="20"/><w:lang w:eastAsia="ko-KR"/>'
              '</w:rPr></w:rPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style></w:styles>')
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc_xml)
        z.writestr("word/styles.xml", styles)
        z.writestr("word/_rels/document.xml.rels", "".join(drels))
        for name, data in media:
            z.writestr("word/media/" + name, data)


# ──────────────────────────────────────────────────────────────
# 5. 저장: 엑셀(xlsx)
# ──────────────────────────────────────────────────────────────
_NUM = re.compile(r"^-?(0|[1-9]\d{0,2}(,\d{3})+|[1-9]\d{0,14})(\.\d+)?$|^-?0\.\d+$")


def _col_letter(n):
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _cell(ref, text, style):
    if _NUM.match(text or "") and len(text) < 17:
        return f'<c r="{ref}" s="{style}"><v>{text.replace(",", "")}</v></c>'
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{_x(text)}</t></is></c>'


def save_xlsx(pages, dst, split=False, gap=True):
    """split=False: 모든 쪽을 시트 1개에 차례로 / True: 쪽마다 시트 1개"""
    sheets = []
    groups = [[pg] for pg in pages] if split else [pages]
    for grp in groups:
        rows_xml, r, widths = [], 1, {}
        for pg in grp:
          if rows_xml and not split and gap:
            r += 1                                     # 쪽 사이 빈 줄
          for bk in pg["blocks"]:
              if bk["t"] == "p":
                  st = 2 if bk["bold"] else 0
                  rows_xml.append(f'<row r="{r}">{_cell("A%d" % r, bk["text"], st)}</row>')
                  r += 1
              elif bk["t"] == "tbl":
                  for row in bk["rows"]:
                      cells = []
                      for c, t in enumerate(row):
                          cells.append(_cell(f"{_col_letter(c)}{r}", t, 1))
                          widths[c] = max(widths.get(c, 6), min(60, sum(2 if ord(ch) > 0x2FF else 1 for ch in t) + 2))
                      rows_xml.append(f'<row r="{r}">{"".join(cells)}</row>')
                      r += 1
                  r += 1
        if not rows_xml:
            rows_xml.append('<row r="1"><c r="A1" t="inlineStr"><is><t>(이 쪽에는 가져올 글자나 표가 없습니다)</t></is></c></row>')
        cols = "".join(f'<col min="{c + 1}" max="{c + 1}" width="{w}" customWidth="1"/>' for c, w in sorted(widths.items()))
        sheets.append(('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                       + (f"<cols>{cols}</cols>" if cols else "") +
                       f'<sheetData>{"".join(rows_xml)}</sheetData></worksheet>', f'{grp[0]["no"]}쪽' if split else "변환결과"))
    wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>']
    wr = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>']
    for n, (_xml, name) in enumerate(sheets, 1):
        wb.append(f'<sheet name="{_x(name)}" sheetId="{n}" r:id="rId{n}"/>')
        wr.append(f'<Relationship Id="rId{n}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{n}.xml"/>')
        ct.append(f'<Override PartName="/xl/worksheets/sheet{n}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    wb.append('</sheets></workbook>')
    wr.append(f'<Relationship Id="rIdSt" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
    ct.append('</Types>')
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<fonts count="2"><font><sz val="10"/><name val="맑은 고딕"/></font><font><b/><sz val="10"/><name val="맑은 고딕"/></font></fonts>'
              '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
              '<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border>'
              '<border><left style="thin"><color auto="1"/></left><right style="thin"><color auto="1"/></right>'
              '<top style="thin"><color auto="1"/></top><bottom style="thin"><color auto="1"/></bottom><diagonal/></border></borders>'
              '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
              '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
              '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>'
              '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "".join(ct))
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", "".join(wb))
        z.writestr("xl/_rels/workbook.xml.rels", "".join(wr))
        z.writestr("xl/styles.xml", styles)
        for n, (xml, _name) in enumerate(sheets, 1):
            z.writestr(f"xl/worksheets/sheet{n}.xml", xml)


# ──────────────────────────────────────────────────────────────
# 6. 저장: 한글(hwpx)
# ──────────────────────────────────────────────────────────────
_HNS = ('xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
        'xmlns:hp10="http://www.hancom.co.kr/hwpml/2016/paragraph" xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
        'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
        'xmlns:hhs="http://www.hancom.co.kr/hwpml/2011/history" xmlns:hm="http://www.hancom.co.kr/hwpml/2011/master-page" '
        'xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf" xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:opf="http://www.idpf.org/2007/opf/" xmlns:ooxmlchart="http://www.hancom.co.kr/hwpml/2016/ooxmlchart" '
        'xmlns:hwpunitchar="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar" xmlns:epub="http://www.idpf.org/2007/ops" '
        'xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0"')
_FONT = "맑은 고딕"
_TEXT_W = 48190                       # A4 가로 59528 - 좌우 여백 5669*2


def _hwpx_header(charprs):
    def fontface(lang):
        return (f'<hh:fontface lang="{lang}" fontCnt="1"><hh:font id="0" face="{_FONT}" type="TTF" isEmbedded="0"/></hh:fontface>')
    bf = []
    for i, solid in ((1, False), (2, True)):
        t = "SOLID" if solid else "NONE"
        bf.append(f'<hh:borderFill id="{i}" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
                  '<hh:slash type="NONE" Crooked="0" isCounter="0"/><hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
                  f'<hh:leftBorder type="{t}" width="0.12 mm" color="#000000"/><hh:rightBorder type="{t}" width="0.12 mm" color="#000000"/>'
                  f'<hh:topBorder type="{t}" width="0.12 mm" color="#000000"/><hh:bottomBorder type="{t}" width="0.12 mm" color="#000000"/>'
                  '<hh:diagonal type="NONE" width="0.1 mm" color="#000000"/></hh:borderFill>')
    cps = []
    for cid, (height, bold) in enumerate(charprs):
        cps.append(f'<hh:charPr id="{cid}" height="{height}" textColor="#000000" shadeColor="none" useFontSpace="0" useKerning="0" '
                   'symMark="NONE" borderFillIDRef="1"><hh:fontRef hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
                   '<hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
                   '<hh:spacing hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
                   '<hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
                   '<hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
                   + ('<hh:bold/>' if bold else '') +
                   '<hh:underline type="NONE" shape="SOLID" color="#000000"/><hh:strikeout shape="NONE" color="#000000"/>'
                   '<hh:outline type="NONE"/><hh:shadow type="NONE" color="#C0C0C0" offsetX="10" offsetY="10"/></hh:charPr>')
    para = ('<hh:paraPr id="0" tabPrIDRef="0" condense="0" fontLineHeight="0" snapToGrid="1" suppressLineNumbers="0" checked="0">'
            '<hh:align horizontal="LEFT" vertical="BASELINE"/><hh:heading type="NONE" idRef="0" level="0"/>'
            '<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="KEEP_WORD" widowOrphan="0" keepWithNext="0" keepLines="0" '
            'pageBreakBefore="0" lineWrap="BREAK"/><hh:autoSpacing eAsianEng="0" eAsianNum="0"/>'
            '<hh:margin><hc:intent value="0" unit="HWPUNIT"/><hc:left value="0" unit="HWPUNIT"/><hc:right value="0" unit="HWPUNIT"/>'
            '<hc:prev value="0" unit="HWPUNIT"/><hc:next value="300" unit="HWPUNIT"/></hh:margin>'
            '<hh:lineSpacing type="PERCENT" value="150" unit="HWPUNIT"/>'
            '<hh:border borderFillIDRef="1" offsetLeft="0" offsetRight="0" offsetTop="0" offsetBottom="0" connect="0" ignoreMargin="0"/></hh:paraPr>')
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hh:head {_HNS} version="1.5" secCnt="1">'
            '<hh:beginNum page="1" footnote="1" endnote="1" pic="1" tbl="1" equation="1"/><hh:refList>'
            '<hh:fontfaces itemCnt="7">' + "".join(fontface(l) for l in ("HANGUL", "LATIN", "HANJA", "JAPANESE", "OTHER", "SYMBOL", "USER")) + '</hh:fontfaces>'
            f'<hh:borderFills itemCnt="2">{"".join(bf)}</hh:borderFills>'
            f'<hh:charProperties itemCnt="{len(charprs)}">{"".join(cps)}</hh:charProperties>'
            '<hh:tabProperties itemCnt="1"><hh:tabPr id="0" autoTabLeft="0" autoTabRight="0"/></hh:tabProperties>'
            f'<hh:paraProperties itemCnt="1">{para}</hh:paraProperties>'
            '<hh:styles itemCnt="1"><hh:style id="0" type="PARA" name="바탕글" engName="Normal" paraPrIDRef="0" charPrIDRef="0" '
            'nextStyleIDRef="0" langID="1042" lockForm="0"/></hh:styles></hh:refList>'
            '<hh:compatibleDocument targetProgram="HWP201X"><hh:layoutCompatibility/></hh:compatibleDocument>'
            '<hh:docOption><hh:linkinfo path="" pageInherit="0" footnoteInherit="0"/></hh:docOption>'
            '<hh:trackchageConfig flags="56"/></hh:head>')


_SECPR = ('<hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134" tabStop="8000" tabStopVal="4000" tabStopUnit="HWPUNIT" '
          'outlineShapeIDRef="0" memoShapeIDRef="0" textVerticalWidthHead="0" masterPageCnt="0">'
          '<hp:grid lineGrid="0" charGrid="0" wonggojiFormat="0"/><hp:startNum pageStartsOn="BOTH" page="0" pic="0" tbl="0" equation="0"/>'
          '<hp:visibility hideFirstHeader="0" hideFirstFooter="0" hideFirstMasterPage="0" border="SHOW_ALL" fill="SHOW_ALL" '
          'hideFirstPageNum="0" hideFirstEmptyLine="0" showLineNumber="0"/>'
          '<hp:lineNumberShape restartType="0" countBy="0" distance="0" startNumber="0"/>'
          '<hp:pagePr landscape="WIDELY" width="59528" height="84186" gutterType="LEFT_ONLY">'
          '<hp:margin header="4252" footer="4252" gutter="0" left="5669" right="5669" top="5669" bottom="5669"/></hp:pagePr>'
          '<hp:footNotePr><hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>'
          '<hp:noteLine length="-1" type="SOLID" width="0.12 mm" color="#000000"/><hp:noteSpacing betweenNotes="283" belowLine="567" aboveLine="850"/>'
          '<hp:numbering type="CONTINUOUS" newNum="1"/><hp:placement place="EACH_COLUMN" beneathText="0"/></hp:footNotePr>'
          '<hp:endNotePr><hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>'
          '<hp:noteLine length="14692344" type="SOLID" width="0.12 mm" color="#000000"/><hp:noteSpacing betweenNotes="0" belowLine="567" aboveLine="850"/>'
          '<hp:numbering type="CONTINUOUS" newNum="1"/><hp:placement place="END_OF_DOCUMENT" beneathText="0"/></hp:endNotePr>'
          '<hp:pageBorderFill type="BOTH" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">'
          '<hp:offset left="1417" right="1417" top="1417" bottom="1417"/></hp:pageBorderFill>'
          '<hp:pageBorderFill type="EVEN" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">'
          '<hp:offset left="1417" right="1417" top="1417" bottom="1417"/></hp:pageBorderFill>'
          '<hp:pageBorderFill type="ODD" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">'
          '<hp:offset left="1417" right="1417" top="1417" bottom="1417"/></hp:pageBorderFill></hp:secPr>')


def _hwpx_pic(bid, n, w, h):
    """w,h: HWPUNIT"""
    iid = 1700000000 + n
    return (f'<hp:run charPrIDRef="0"><hp:pic id="{iid}" zOrder="{n}" numberingType="PICTURE" textWrap="TOP_AND_BOTTOM" '
            f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" href="" groupLevel="0" instid="{iid}" reverse="0">'
            f'<hp:offset x="0" y="0"/><hp:orgSz width="{w}" height="{h}"/><hp:curSz width="{w}" height="{h}"/>'
            '<hp:flip horizontal="0" vertical="0"/>'
            f'<hp:rotationInfo angle="0" centerX="{w // 2}" centerY="{h // 2}" rotateimage="1"/>'
            '<hp:renderingInfo><hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
            '<hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/><hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/></hp:renderingInfo>'
            f'<hc:img binaryItemIDRef="{bid}" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/>'
            f'<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="{w}" y="0"/><hc:pt2 x="{w}" y="{h}"/><hc:pt3 x="0" y="{h}"/></hp:imgRect>'
            f'<hp:imgClip left="0" right="{w}" top="0" bottom="{h}"/><hp:inMargin left="0" right="0" top="0" bottom="0"/>'
            f'<hp:imgDim dimwidth="{w}" dimheight="{h}"/><hp:effects/>'
            f'<hp:sz width="{w}" widthRelTo="ABSOLUTE" height="{h}" heightRelTo="ABSOLUTE" protect="0"/>'
            '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '
            'horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
            '<hp:outMargin left="0" right="0" top="0" bottom="0"/></hp:pic></hp:run>')


def save_hwpx(pages, dst, title=""):
    media = []                                # (id, 파일명, 바이트, ext)
    charprs = [(1000, False)]                 # (높이 1/100pt, 굵게)
    cp_idx = {(1000, False): 0}

    def cp(size, bold):
        h = int(max(6, min(40, size)) * 100)
        h = (h // 50) * 50
        k = (h, bool(bold))
        if k not in cp_idx:
            cp_idx[k] = len(charprs)
            charprs.append(k)
        return cp_idx[k]

    paras = []
    first = [True]

    def para(inner, page_break=False):
        pre = ""
        if first[0]:
            pre = f'<hp:run charPrIDRef="0">{_SECPR}</hp:run>'
            first[0] = False
        paras.append(f'<hp:p id="{2147483648 + len(paras)}" paraPrIDRef="0" styleIDRef="0" pageBreak="{1 if page_break else 0}" '
                     f'columnBreak="0" merged="0">{pre}{inner}</hp:p>')

    for pi, pg in enumerate(pages):
        pb = pi > 0
        wrote = False
        for bk in pg["blocks"]:
            if bk["t"] == "p":
                para(f'<hp:run charPrIDRef="{cp(bk["size"], bk["bold"])}"><hp:t>{_x(bk["text"])}</hp:t></hp:run>', pb and not wrote)
                wrote = True
            elif bk["t"] == "img":
                n = len(media) + 1
                bid = f"image{n}"
                w, h = bk["w"] * 100.0, bk["h"] * 100.0
                if w > _TEXT_W:
                    h, w = h * _TEXT_W / w, float(_TEXT_W)
                if h > 70000:
                    w, h = w * 70000 / h, 70000.0
                media.append((bid, f"{bid}.{bk['ext']}", bk["data"], bk["ext"]))
                para(_hwpx_pic(bid, n, max(100, int(w)), max(100, int(h))), pb and not wrote)
                wrote = True
            elif bk["t"] == "tbl":
                rows = bk["rows"]
                ws = _col_weights(rows)
                tot = float(sum(ws))
                grid = [max(1500, int(_TEXT_W * w / tot)) for w in ws]
                scale = _TEXT_W / float(sum(grid))
                grid = [int(g * scale) for g in grid]
                rh = 2200
                tid = 1000000 + len(paras)
                x = [f'<hp:run charPrIDRef="0"><hp:tbl id="{tid}" zOrder="{len(paras)}" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
                     f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="0" rowCnt="{len(rows)}" '
                     f'colCnt="{len(ws)}" cellSpacing="0" borderFillIDRef="2" noAdjust="0">'
                     f'<hp:sz width="{sum(grid)}" widthRelTo="ABSOLUTE" height="{rh * len(rows)}" heightRelTo="ABSOLUTE" protect="0"/>'
                     '<hp:pos treatAsChar="0" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '
                     'horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
                     '<hp:outMargin left="0" right="0" top="0" bottom="283"/><hp:inMargin left="141" right="141" top="141" bottom="141"/>']
                small = cp(9, False)
                for ri, r in enumerate(rows):
                    x.append("<hp:tr>")
                    for c in range(len(ws)):
                        t = r[c] if c < len(r) else ""
                        run = f'<hp:run charPrIDRef="{small}"><hp:t>{_x(t)}</hp:t></hp:run>' if t else f'<hp:run charPrIDRef="{small}"/>'
                        x.append('<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="0" borderFillIDRef="2">'
                                 '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" '
                                 'linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
                                 f'<hp:p id="2147483648" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">{run}</hp:p></hp:subList>'
                                 f'<hp:cellAddr colAddr="{c}" rowAddr="{ri}"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
                                 f'<hp:cellSz width="{grid[c]}" height="{rh}"/><hp:cellMargin left="141" right="141" top="141" bottom="141"/></hp:tc>')
                    x.append("</hp:tr>")
                x.append("</hp:tbl></hp:run>")
                para("".join(x), pb and not wrote)
                wrote = True
        if pb and not wrote:
            para('<hp:run charPrIDRef="0"/>', True)
    if not paras:
        para('<hp:run charPrIDRef="0"/>')
    section = f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_HNS}>' + "".join(paras) + '</hs:sec>'
    header = _hwpx_header(charprs)
    hpf = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><opf:package {_HNS} version="" unique-identifier="" id="">'
           f'<opf:metadata><opf:title>{_x(title)}</opf:title><opf:language>ko</opf:language></opf:metadata>'
           '<opf:manifest><opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>'
           '<opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/>'
           '<opf:item id="settings" href="settings.xml" media-type="application/xml"/>'
           + "".join(f'<opf:item id="{i}" href="BinData/{fn}" media-type="image/{"jpg" if e == "jpg" else "png"}" isEmbeded="1"/>'
                     for i, fn, _d, e in media) + '</opf:manifest>'
           '<opf:spine><opf:itemref idref="header" linear="yes"/><opf:itemref idref="section0" linear="yes"/></opf:spine></opf:package>')
    container = ('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><ocf:container xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container" '
                 'xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf"><ocf:rootfiles>'
                 '<ocf:rootfile full-path="Contents/content.hpf" media-type="application/hwpml-package+xml"/>'
                 '</ocf:rootfiles></ocf:container>')
    version = ('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hv:HCFVersion xmlns:hv="http://www.hancom.co.kr/hwpml/2011/version" '
               'tagetApplication="WORDPROCESSOR" major="5" minor="1" micro="1" buildNumber="0" os="1" xmlVersion="1.5" '
               'application="Hancom Office Hangul" appVersion="12, 0, 0, 4547 WIN32LEWindows_10"/>')
    settings = ('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><ha:HWPApplicationSetting '
                'xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0">'
                '<ha:CaretPosition listIDRef="0" paraIDRef="0" pos="0"/></ha:HWPApplicationSetting>')
    with zipfile.ZipFile(dst, "w") as z:
        z.writestr("mimetype", "application/hwp+zip", compress_type=zipfile.ZIP_STORED)
        for name, data in (("version.xml", version), ("settings.xml", settings), ("META-INF/container.xml", container),
                           ("META-INF/manifest.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><odf:manifest xmlns:odf="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"/>'),
                           ("Contents/content.hpf", hpf), ("Contents/header.xml", header), ("Contents/section0.xml", section)):
            z.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
        for _i, fn, data, _e in media:
            z.writestr("BinData/" + fn, data, compress_type=zipfile.ZIP_STORED)
        z.writestr("Preview/PrvText.txt", "\n".join(b["text"] for p in pages for b in p["blocks"] if b["t"] == "p")[:1000],
                   compress_type=zipfile.ZIP_DEFLATED)


# ──────────────────────────────────────────────────────────────
def render_pages(src_bytes, outdir, base, pages, fmt="png", dpi=200, progress=None):
    """쪽을 그림 파일로 저장. 저장한 파일 경로 목록 반환 (이름: 기본이름_001.png)"""
    doc = fitz.open("pdf", src_bytes)
    outs = []
    try:
        if doc.needs_pass:
            raise ValueError("암호가 걸린 PDF 입니다.")
        idx = list(pages) if pages is not None else list(range(len(doc)))
        width = max(3, len(str(len(doc))))
        for n, i in enumerate(idx):
            _tick(progress, n, len(idx), f"{i + 1}쪽 저장 중... ({n + 1}/{len(idx)})")
            pix = doc[i].get_pixmap(dpi=dpi, alpha=False)
            p = os.path.join(outdir, f"{base}_{i + 1:0{width}d}.{'jpg' if fmt == 'jpg' else 'png'}")
            if fmt == "jpg":
                pix.save(p, jpg_quality=92)
            else:
                pix.save(p)
            outs.append(p)
    finally:
        doc.close()
    _tick(progress, 1, 1, "완료")
    return outs


def convert(src_bytes, dst, fmt, pages=None, use_ocr=True, progress=None, title="", split_sheets=False, page_gap=True):
    """fmt: 'docx' | 'xlsx' | 'hwpx'. (변환한 쪽 수, 알림 목록) 반환"""
    pg, notes = extract_pages(src_bytes, pages, use_ocr=use_ocr, want_images=(fmt != "xlsx"), progress=progress)
    if fmt == "docx":
        save_docx(pg, dst)
    elif fmt == "xlsx":
        save_xlsx(pg, dst, split_sheets, page_gap)
    elif fmt == "hwpx":
        save_hwpx(pg, dst, title)
    else:
        raise ValueError(fmt)
    ntbl = sum(1 for p in pg for b in p["blocks"] if b["t"] == "tbl")
    return len(pg), ntbl, notes
