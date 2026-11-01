import base64
import pymupdf as fitz
d = fitz.open()
pg = d.new_page(width=420, height=300)
pg.insert_text((20, 30), "FreeText plain test", fontsize=12)
a = pg.add_freetext_annot(fitz.Rect(20, 50, 200, 110), "한글 메모 첫째 줄\n둘째 줄 ABC 123", fontsize=11,
                          text_color=(0.24, 0.16, 0), fill_color=(1, 0.97, 0.77), border_color=(0.98, 0.65, 0.15))
a.set_border(width=1)
a.set_info(title="메모")
a.update()
b = pg.add_freetext_annot(fitz.Rect(220, 50, 400, 110), "옮기고 고칠 메모", fontsize=11,
                          text_color=(0.24, 0.16, 0), fill_color=(1, 0.97, 0.77), border_color=(0.98, 0.65, 0.15))
b.set_border(width=1)
b.update()
# 옮기기
r = b.rect
b.set_rect(fitz.Rect(r.x0, r.y0 + 120, r.x1, r.y1 + 120))
b.update()
print("moved content", repr(b.info.get("content")))
# 내용 고치기
b.set_info(content="고친 내용입니다\n줄바꿈도")
b.update(fontsize=11, text_color=(0.24, 0.16, 0), fill_color=(1, 0.97, 0.77), border_color=(0.98, 0.65, 0.15))
print("edited content", repr(b.info.get("content")))
# 회전된 쪽
p2 = d.new_page(width=420, height=300)
p2.set_rotation(90)
c = p2.add_freetext_annot(fitz.Rect(20, 50, 200, 110), "회전된 쪽 메모", fontsize=11, rotate=p2.rotation,
                          fill_color=(1, 0.97, 0.77))
c.update()
pix = pg.get_pixmap(matrix=fitz.Matrix(2, 2))
print("IMG ft.png", base64.b64encode(pix.tobytes("png")).decode())
pix = p2.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
print("IMG ft2.png", base64.b64encode(pix.tobytes("png")).decode())
d2 = fitz.open("pdf", d.tobytes())
print("reopen", [(x.type[1], repr(x.info.get("content"))) for x in d2[0].annots()])
print("text extract", repr(d2[0].get_text()[:80]))
