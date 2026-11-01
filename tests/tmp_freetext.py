import base64, io, sys
import pymupdf as fitz
print("ver", fitz.VersionBind)
d = fitz.open()
pg = d.new_page(width=420, height=300)
pg.insert_text((20, 30), "FreeText test", fontsize=12)
res = {}
def tryit(name, fn):
    try:
        fn()
        res[name] = "ok"
    except Exception as ex:
        res[name] = f"ERR {ex}"
tryit("rich", lambda: pg.add_freetext_annot(fitz.Rect(20, 50, 200, 120), "한글 메모 테스트 ABC\n둘째 줄",
                                           fontsize=11, fill_color=(1, 0.97, 0.75), border_color=(0.98, 0.65, 0.15),
                                           richtext=True))
tryit("rich_style", lambda: pg.add_freetext_annot(fitz.Rect(220, 50, 400, 120), "<p>스타일 한글 <b>굵게</b></p>",
                                                 fontsize=11, fill_color=(1, 0.97, 0.75), richtext=True,
                                                 style="font-family: sans-serif; color: #3e2a00;"))
tryit("plain", lambda: pg.add_freetext_annot(fitz.Rect(20, 150, 200, 220), "plain 한글", fontsize=11,
                                            fill_color=(1, 0.97, 0.75)))
print(res)
for a in pg.annots():
    print(a.type, a.rect, repr(a.info.get("content")))
# move test
a = pg.first_annot
r = a.rect
a.set_rect(fitz.Rect(r.x0 + 10, r.y0 + 120, r.x1 + 10, r.y1 + 120))
a.update()
pix = pg.get_pixmap(matrix=fitz.Matrix(2, 2))
print("IMG ft.png", base64.b64encode(pix.tobytes("png")).decode())
# saved & reopened
b = d.tobytes(); d2 = fitz.open("pdf", b)
print("reopen annots", [(x.type[1], x.rect) for x in d2[0].annots()])
