# -*- coding: utf-8 -*-
"""스마트PDF Editor 아이콘 만들기 (PIL). 결과는 smartpdfeditor.py 의 ICON_DATA 에 base64로 들어갑니다.
    python tools/make_icons.py > icons.txt
4배 크기로 그린 뒤 줄여서 테두리를 부드럽게(안티에일리어싱) 합니다.
"""
import io
import sys
import math
import base64
import json
from PIL import Image, ImageDraw

SZ = 20          # 최종 크기(px)
K = 4            # 확대 배율
N = SZ * K

ORANGE, BLUE, RED, YELLOW, PINK, GREEN = "#f6a53f", "#1e88e5", "#e53935", "#ffd54f", "#f48fb1", "#43a047"


def new():
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def P(*xy):            # 20px 좌표 → 확대 좌표
    return [v * K for v in xy]


def arrow_head(d, tip, angle, size, fill):
    a = math.radians(angle)
    l = (tip[0] - size * math.cos(a - 0.5), tip[1] - size * math.sin(a - 0.5))
    r = (tip[0] - size * math.cos(a + 0.5), tip[1] - size * math.sin(a + 0.5))
    d.polygon([tip, l, r], fill=fill)


def rr(d, box, r, **kw):
    d.rounded_rectangle(P(*box), radius=r * K, **kw)


def icons(S):
    """S = 선 색 (밝은 바탕용: 진한 회색 / 어두운 바탕용: 밝은 회색)"""
    W = int(1.6 * K)        # 기본 선 두께
    out = {}

    # 열기: 주황 폴더
    im, d = new()
    d.polygon(P(2, 6, 7.5, 6, 9, 7.5, 18, 7.5, 18, 16.5, 2, 16.5), fill=ORANGE)
    d.polygon(P(2, 6, 2, 4.5, 7, 4.5, 8.5, 6), fill=ORANGE)
    d.polygon(P(2, 16.5, 4.5, 10, 19.5, 10, 17.5, 16.5), fill="#fbc77a")
    out["open"] = im

    # 저장: 파란 디스켓
    im, d = new()
    rr(d, (2.5, 2.5, 17.5, 17.5), 2.2, fill=BLUE)
    d.rectangle(P(5.5, 2.5, 13.5, 7.5), fill="#bbdefb")
    d.rectangle(P(11, 3.4, 12.6, 6.6), fill=BLUE)
    rr(d, (5, 10.5, 15, 17.5), 1, fill="#ffffff")
    out["save"] = im

    # 다른 이름으로 저장: 디스켓 + 주황 연필
    im, d = new()
    rr(d, (1.5, 2.5, 14.5, 15.5), 2, fill=BLUE)
    d.rectangle(P(4, 2.5, 11, 6.8), fill="#bbdefb")
    d.rectangle(P(9, 3.3, 10.4, 6.1), fill=BLUE)
    rr(d, (4, 9.5, 12, 15.5), 0.8, fill="#ffffff")
    d.line(P(11.5, 17.5, 18, 11), fill="#ffffff", width=int(4.6 * K))
    d.line(P(11.5, 17.5, 18, 11), fill=ORANGE, width=int(2.6 * K))
    d.polygon(P(10.2, 18.8, 11, 16.2, 12.8, 18), fill=S)
    out["save_as"] = im

    # 되돌리기
    im, d = new()
    d.arc(P(4, 5, 17, 17), 200, 450, fill=S, width=W)
    arrow_head(d, P(3.2, 10.6), 105, 4.2 * K, S)
    out["undo"] = im

    # 이전 / 다음 쪽
    for name, pts in (("prev", (12.5, 4.5, 6.5, 10, 12.5, 15.5)), ("next", (7.5, 4.5, 13.5, 10, 7.5, 15.5))):
        im, d = new()
        d.line(P(*pts), fill=S, width=int(2.2 * K), joint="curve")
        out[name] = im

    # 축소 / 확대 (돋보기)
    for name, plus in (("zoom_out", False), ("zoom_in", True)):
        im, d = new()
        d.ellipse(P(2.5, 2.5, 13.5, 13.5), outline=S, width=W)
        d.line(P(12, 12, 17.5, 17.5), fill=S, width=int(2.6 * K))
        d.line(P(5.5, 8, 10.5, 8), fill=S, width=W)
        if plus:
            d.line(P(8, 5.5, 8, 10.5), fill=S, width=W)
        out[name] = im

    # 회전 (왼쪽 / 오른쪽): 가운데 쪽 + 시계 방향 화살표
    for name, flip in (("rot_l", True), ("rot_r", False)):
        im, d = new()
        rr(d, (7, 6.5, 13, 13.5), 0.8, fill="#ffffff", outline=S, width=int(1.1 * K))
        d.arc(P(2.5, 2.5, 17.5, 17.5), 20, 290, fill=BLUE, width=int(1.9 * K))
        t = math.radians(318)                     # 시계 방향 끝에 화살촉
        tip = (K * (10 + 7.5 * math.cos(t)), K * (10 + 7.5 * math.sin(t)))
        arrow_head(d, tip, 318 + 90, 5.2 * K, BLUE)
        if flip:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        out[name] = im

    # 여러 쪽 회전
    im, d = new()
    rr(d, (3, 5, 10, 14), 0.8, outline=S, width=int(1.2 * K))
    rr(d, (6, 7.5, 13, 16.5), 0.8, outline=S, width=int(1.2 * K), fill=None)
    d.arc(P(8, 2, 19, 13), 220, 360, fill=BLUE, width=W)
    arrow_head(d, P(18.8, 8.3), 95, 3.6 * K, BLUE)
    out["rot_many"] = im

    # 전체 쪽 회전: 겹친 쪽 3장 + 둥근 화살표
    im, d = new()
    for i, (x, y) in enumerate(((5.5, 4.5), (7.2, 6.2), (8.9, 7.9))):
        rr(d, (x, y, x + 5.6, y + 7.4), 0.6, fill="#ffffff", outline=S, width=int(1.0 * K))
    d.arc(P(1.5, 1.5, 18.5, 18.5), 20, 290, fill=BLUE, width=int(1.8 * K))
    t = math.radians(318)
    tip = (K * (10 + 8.5 * math.cos(t)), K * (10 + 8.5 * math.sin(t)))
    arrow_head(d, tip, 318 + 90, 5.0 * K, BLUE)
    out["rot_all"] = im

    # 도구: 글자 수정 (T + 연필)
    im, d = new()
    d.line(P(2.5, 4, 10.5, 4), fill=S, width=int(2 * K))
    d.line(P(6.5, 4, 6.5, 14), fill=S, width=int(2 * K))
    d.polygon(P(10, 16.5, 16.5, 10, 18.5, 12, 12, 18.5, 9.5, 19), fill=S)
    d.polygon(P(11.2, 16.8, 16.5, 11.5, 17.2, 12.2, 11.9, 17.5), fill=ORANGE)
    d.polygon(P(9.5, 19, 10, 16.5, 12, 18.5), fill=S)
    out["t_edit"] = im

    # 색칠 (형광펜)
    im, d = new()
    d.rectangle(P(2, 15.5, 18, 18.5), fill=YELLOW)
    d.polygon(P(6, 12.5, 13.5, 3, 17, 5.8, 9.5, 15.3), fill=S)
    d.polygon(P(6, 12.5, 9.5, 15.3, 7.2, 16.6, 4.6, 14.5), fill="#fbc02d")
    out["t_mark"] = im

    # 감추기 (글줄 위 검정 막대)
    im, d = new()
    for y in (4, 9.5, 15):
        d.line(P(3, y, 17, y), fill="#9aa0a6", width=int(1.4 * K))
    rr(d, (2, 7, 18, 12), 1, fill="#202124")
    out["t_hide"] = im

    # 도형 (사각형 + 원)
    im, d = new()
    d.rectangle(P(2.5, 2.5, 12, 12), outline=RED, width=W)
    d.ellipse(P(8, 8, 18, 18), outline=BLUE, width=W)
    out["t_shape"] = im

    # 메모 (말풍선)
    im, d = new()
    rr(d, (2, 3, 18, 14), 2.5, fill=YELLOW, outline="#f9a825", width=int(1.2 * K))
    d.polygon(P(5.5, 13.5, 5, 18, 10, 13.5), fill=YELLOW)
    d.line(P(5.5, 13.5, 5, 18, 10, 13.8), fill="#f9a825", width=int(1.2 * K))
    for y in (6.5, 10):
        d.line(P(5, y, 15, y), fill="#8d6e00", width=int(1.1 * K))
    out["t_memo"] = im

    # 지우개
    im, d = new()
    d.polygon(P(3, 13, 11, 5, 17, 11, 9, 19), fill=PINK)
    d.polygon(P(3, 13, 7, 9, 13, 15, 9, 19), fill="#ffffff", outline=None)
    d.line(P(3, 13, 11, 5, 17, 11, 9, 19, 3, 13), fill=S, width=int(1.2 * K), joint="curve")
    d.line(P(7, 9, 13, 15), fill=S, width=int(1.2 * K))
    out["t_erase"] = im

    # 캡쳐 (점선 영역 + 모서리)
    im, d = new()
    for x0, y0, dx, dy in ((2, 2, 1, 1), (18, 2, -1, 1), (2, 18, 1, -1), (18, 18, -1, -1)):
        d.line(P(x0, y0 + 4.5 * dy, x0, y0, x0 + 4.5 * dx, y0), fill=RED, width=int(1.9 * K))
    for x in range(8, 13, 2):
        d.line(P(x, 2, x + 1, 2), fill=RED, width=int(1.3 * K))
        d.line(P(x, 18, x + 1, 18), fill=RED, width=int(1.3 * K))
    d.ellipse(P(7, 7, 13, 13), fill=S)
    out["t_capture"] = im

    # 뷰어 모드 (눈)
    im, d = new()
    d.chord(P(1.5, 4.5, 18.5, 19), 200, 340, outline=S, width=W)
    d.chord(P(1.5, 1, 18.5, 15.5), 20, 160, outline=S, width=W)
    d.ellipse(P(7, 6.5, 13, 12.5), fill=BLUE)
    d.ellipse(P(8.8, 8.3, 11.2, 10.7), fill="#0d3c61")
    out["m_view"] = im

    # 편집 모드 (연필)
    im, d = new()
    d.polygon(P(3, 14.5, 13.5, 4, 16, 6.5, 5.5, 17), fill=S)
    d.polygon(P(4.6, 14.6, 13.6, 5.6, 14.4, 6.4, 5.4, 15.4), fill=ORANGE)
    d.polygon(P(13.5, 4, 15, 2.5, 17.5, 5, 16, 6.5), fill=PINK)
    d.polygon(P(3, 14.5, 5.5, 17, 2.2, 17.8), fill=S)
    out["m_edit"] = im

    # 가로맞춤 / 세로맞춤
    im, d = new()
    d.line(P(2, 4, 2, 16), fill=S, width=W)
    d.line(P(18, 4, 18, 16), fill=S, width=W)
    d.line(P(5, 10, 15, 10), fill=BLUE, width=W)
    arrow_head(d, P(4.2, 10), 180, 3.4 * K, BLUE)
    arrow_head(d, P(15.8, 10), 0, 3.4 * K, BLUE)
    out["fit_w"] = im
    out["fit_h"] = im.rotate(90)

    # 보기 방식 (쪽 모양)
    def page(d, x0, y0, x1, y1):
        rr(d, (x0, y0, x1, y1), 0.8, fill="#ffffff", outline=S, width=int(1.1 * K))
        y = y0 + 2.2
        while y < y1 - 1.5:
            d.line(P(x0 + 1.6, y, x1 - 1.6, y), fill="#9aa0a6", width=int(0.8 * K))
            y += 2.2
    im, d = new()
    page(d, 5, 2, 15, 18)
    out["v_single"] = im
    im, d = new()
    page(d, 5, 0.5, 15, 9)
    page(d, 5, 11, 15, 19.5)
    out["v_cont"] = im
    for n in (2, 3, 4):
        im, d = new()
        w = (19 - (n - 1) * 1.2) / n
        x = 0.5
        for _ in range(n):
            page(d, x, 4, x + w, 16)
            x += w + 1.2
        out[f"v_cont{n}"] = im

    # 메뉴용: 찾기, 북마크, 즐겨찾기(별), 설정(톱니), 도움말
    im, d = new()
    d.ellipse(P(2.5, 2.5, 13.5, 13.5), outline=S, width=W)
    d.line(P(12, 12, 17.5, 17.5), fill=S, width=int(2.6 * K))
    out["find"] = im
    im, d = new()
    d.polygon(P(5, 2, 15, 2, 15, 18, 10, 13.5, 5, 18), fill=RED)
    out["bookmark"] = im
    im, d = new()
    pts = []
    for i in range(10):
        a = math.radians(-90 + i * 36)
        r = 8.5 if i % 2 == 0 else 3.6
        pts += [10 + r * math.cos(a), 10.5 + r * math.sin(a)]
    d.polygon(P(*pts), fill=ORANGE)
    out["star"] = im
    im, d = new()
    for i in range(8):
        a = math.radians(i * 45)
        d.line(P(10 + 5 * math.cos(a), 10 + 5 * math.sin(a), 10 + 8.3 * math.cos(a), 10 + 8.3 * math.sin(a)),
               fill=S, width=int(2.6 * K))
    d.ellipse(P(4, 4, 16, 16), fill=S)
    d.ellipse(P(7.3, 7.3, 12.7, 12.7), fill=(0, 0, 0, 0))
    out["gear"] = im
    im, d = new()
    d.ellipse(P(1.5, 1.5, 18.5, 18.5), fill=BLUE)
    d.arc(P(6.5, 4.5, 13.5, 11), 180, 400, fill="#ffffff", width=int(1.9 * K))
    d.line(P(10, 10.6, 10, 12.4), fill="#ffffff", width=int(1.9 * K))
    d.ellipse(P(9, 14, 11, 16), fill="#ffffff")
    out["help"] = im
    im, d = new()
    d.polygon(P(4, 2, 13, 2, 16.5, 5.5, 16.5, 18, 4, 18), fill="#ffffff", outline=S)
    d.line(P(4, 2, 13, 2, 16.5, 5.5, 16.5, 18, 4, 18, 4, 2), fill=S, width=int(1.2 * K))
    d.text((7.2 * K, 7.5 * K), "PDF", fill=RED)
    out["pdf"] = im
    im, d = new()
    d.line(P(10, 3, 10, 17), fill=S, width=int(2 * K))
    d.line(P(3, 10, 17, 10), fill=S, width=int(2 * K))
    out["plus"] = im
    return out


def tab_close(S, hot):
    """탭 닫기 × (16px). hot=True 이면 빨간 동그라미 위 흰 ×"""
    n = 16 * K
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    col = S
    if hot:
        d.ellipse((1.5 * K, 1.5 * K, 14.5 * K, 14.5 * K), fill="#e53935")
        col = "#ffffff"
    w = int(1.7 * K)
    d.line((5 * K, 5 * K, 11 * K, 11 * K), fill=col, width=w)
    d.line((11 * K, 5 * K, 5 * K, 11 * K), fill=col, width=w)
    return im


def encode(im, size=SZ):
    small = im.resize((size, size), Image.LANCZOS)
    b = io.BytesIO()
    small.save(b, "PNG", optimize=True)
    return base64.b64encode(b.getvalue()).decode()


def build():
    light = {k: encode(v) for k, v in icons("#3c4043").items()}   # 밝은 바탕용
    dark = {k: encode(v) for k, v in icons("#e8eaed").items()}    # 어두운 바탕용
    for var, S in ((light, "#5f6368"), (dark, "#bdc1c6")):
        var["tab_x"] = encode(tab_close(S, False), 16)
        var["tab_x_hot"] = encode(tab_close(S, True), 16)
    return {"light": light, "dark": dark}


if __name__ == "__main__":
    data = build()
    if "--preview" in sys.argv:
        names = list(data["light"])
        sheet = Image.new("RGBA", (len(names) * 34 + 10, 110), "#fff6e8")
        dsheet = Image.new("RGBA", sheet.size, "#2b2b2e")
        for i, n in enumerate(names):
            for var, sh in (("light", sheet), ("dark", dsheet)):
                im = Image.open(io.BytesIO(base64.b64decode(data[var][n]))).convert("RGBA")
                if im.size != (SZ, SZ):
                    im2 = Image.new("RGBA", (SZ, SZ))
                    im2.paste(im, ((SZ - im.width) // 2, (SZ - im.height) // 2))
                    im = im2
                sh.alpha_composite(im, (10 + i * 34, 10))
                sh.alpha_composite(im.resize((40, 40), Image.NEAREST), (5 + i * 34, 50)) if False else None
        out = Image.new("RGBA", (sheet.width, 220))
        out.paste(sheet, (0, 0))
        out.paste(dsheet, (0, 110))
        out = out.resize((out.width * 2, out.height * 2), Image.NEAREST)
        out.save(sys.argv[-1])
        print(names)
    else:
        print(json.dumps(data))
