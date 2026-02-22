from __future__ import annotations

import io

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

BG_COLOR          = (28,  32,  40)
HEADER_BG         = (18,  21,  28)
HEADER_ACCENT     = (88, 101, 242)
COL_HEADER_BG     = (40,  45,  55)
COL_HEADER_TEXT   = (200, 200, 210)
ROW_ODD           = (35,  40,  50)
ROW_EVEN          = (42,  47,  58)
ROW_ADV_ODD       = (40,  50,  38)
ROW_ADV_EVEN      = (46,  56,  44)
TEXT_PRIMARY      = (240, 240, 245)
TEXT_SECONDARY    = (150, 155, 165)
SELL_BG           = (56,  161,  90)
SELL_TEXT         = (210, 255, 220)
BUY_BG            = (190,  50,  55)
BUY_TEXT          = (255, 215, 215)
ADV_BG            = (190, 140,  20)
ADV_TEXT          = (255, 245, 200)
DRAFT_TEXT        = (130, 130, 140)
BORDER_COLOR      = (60,  65,  78)
TITLE_TEXT        = (255, 255, 255)

PADDING           = 28
ROW_H             = 54
COL_HEADER_H      = 42
HEADER_H          = 110
FOOTER_H          = 36
CORNER_R          = 6
PILL_H            = 28
PILL_PAD_X        = 12


def _font(bold: bool, size: int) -> "ImageFont.FreeTypeFont | ImageFont.ImageFont":
    paths_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    paths_reg = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in (paths_bold if bold else paths_reg):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()

def _pill(draw: ImageDraw.Draw, x: int, y: int, text: str,
          bg: tuple, fg: tuple, font: "ImageFont.FreeTypeFont"):
    tw  = int(draw.textlength(text, font=font))
    pw  = tw + PILL_PAD_X * 2
    ph  = PILL_H
    r   = ph // 2
    x2, y2 = x + pw, y + ph
    draw.rounded_rectangle([(x, y), (x2, y2)], radius=r, fill=bg)
    draw.text((x + PILL_PAD_X, y + (ph - font.size) // 2 - 1), text, font=font, fill=fg)
    return pw


def _truncate(text: str, draw: ImageDraw.Draw,
              font: "ImageFont.FreeTypeFont", max_px: int) -> str:
    if draw.textlength(text, font=font) <= max_px:
        return text
    while text and draw.textlength(text + "…", font=font) > max_px:
        text = text[:-1]
    return text + "…"


def _header(draw: ImageDraw.Draw, img_w: int, title: str,
            subtitle: str, font_title, font_sub):
    draw.rectangle([(0, 0), (img_w, HEADER_H)], fill=HEADER_BG)
    draw.rectangle([(0, HEADER_H - 4), (img_w, HEADER_H)], fill=HEADER_ACCENT)
    draw.text((PADDING, 22), title,    font=font_title, fill=TITLE_TEXT)
    draw.text((PADDING, 62), subtitle, font=font_sub,   fill=TEXT_SECONDARY)


def _col_headers(draw: ImageDraw.Draw, img_w: int, y: int,
                 cols: list[tuple[int, str]], font):
    draw.rectangle([(0, y), (img_w, y + COL_HEADER_H)], fill=COL_HEADER_BG)
    for cx, label in cols:
        draw.text((cx, y + (COL_HEADER_H - font.size) // 2), label,
                  font=font, fill=COL_HEADER_TEXT)
    draw.line([(0, y + COL_HEADER_H - 1), (img_w, y + COL_HEADER_H - 1)],
              fill=BORDER_COLOR, width=1)


def _row_bg(draw: ImageDraw.Draw, img_w: int, y: int,
            idx: int, advertised: bool):
    if advertised:
        fill = ROW_ADV_ODD if idx % 2 == 0 else ROW_ADV_EVEN
    else:
        fill = ROW_ODD if idx % 2 == 0 else ROW_EVEN
    draw.rectangle([(0, y), (img_w, y + ROW_H)], fill=fill)


def _row_sep(draw: ImageDraw.Draw, img_w: int, y: int):
    draw.line([(0, y + ROW_H - 1), (img_w, y + ROW_H - 1)],
              fill=BORDER_COLOR, width=1)



def render_items_list(
    title: str,
    subtitle: str,
    items: list[dict],
    detail_mode: bool = False,
) -> io.BytesIO | None:
    if not PILLOW_AVAILABLE:
        return None

    f_title  = _font(True,  26)
    f_sub    = _font(False, 16)
    f_ch     = _font(True,  15)
    f_body   = _font(False, 16)

    C_IDX    = PADDING
    C_NAME   = PADDING + 60
    C_CAT    = PADDING + 450
    IMG_W    = PADDING + (680 if not detail_mode else 820)

    n_rows   = len(items) if items else 1
    img_h    = HEADER_H + COL_HEADER_H + n_rows * ROW_H + FOOTER_H + PADDING

    img  = Image.new("RGB", (IMG_W, img_h), BG_COLOR)
    draw = ImageDraw.Draw(img)

    _header(draw, IMG_W, title, subtitle, f_title, f_sub)

    col_y = HEADER_H
    cols  = [(C_IDX, "#"), (C_NAME, "Item Name")]
    if detail_mode:
        cols.append((C_CAT, "Category"))
    _col_headers(draw, IMG_W, col_y, cols, f_ch)

    if not items:
        row_y = col_y + COL_HEADER_H
        _row_bg(draw, IMG_W, row_y, 0, False)
        draw.text((C_NAME, row_y + (ROW_H - f_body.size) // 2),
                  "No items found.", font=f_body, fill=TEXT_SECONDARY)
    else:
        for idx, entry in enumerate(items):
            row_y = col_y + COL_HEADER_H + idx * ROW_H
            _row_bg(draw, IMG_W, row_y, idx, False)
            ty = row_y + (ROW_H - f_body.size) // 2

            draw.text((C_IDX, ty), str(idx + 1), font=f_body, fill=TEXT_SECONDARY)

            max_name_w = (C_CAT if detail_mode else IMG_W - PADDING) - C_NAME - 14
            name = _truncate(entry.get("name", "?"), draw, f_body, max_name_w)
            draw.text((C_NAME, ty), name, font=f_body, fill=TEXT_PRIMARY)

            if detail_mode and "category" in entry:
                cat = _truncate(entry["category"], draw, f_body, IMG_W - C_CAT - PADDING)
                draw.text((C_CAT, ty), cat, font=f_body, fill=TEXT_SECONDARY)

            _row_sep(draw, IMG_W, row_y)

    draw.text((PADDING, img_h - FOOTER_H + 10),
              "EscapeItems Shop System", font=f_sub, fill=TEXT_SECONDARY)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
