from __future__ import annotations

import io
import json
import urllib.request
import urllib.error

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False


def _fetch_image(url: str, size: tuple[int, int]) -> "Image.Image | None":
    if not url or not url.startswith("http"):
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EscapeItems/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read()
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        img = img.resize(size, Image.NEAREST)
        return img
    except Exception:
        return None

BG_COLOR          = (28,  32,  40, 255)
HEADER_BG         = (18,  21,  28, 255)
HEADER_ACCENT     = (88, 101, 242, 255)
COL_HEADER_BG     = (40,  45,  55, 255)
COL_HEADER_TEXT   = (200, 200, 210, 255)
ROW_ODD           = (35,  40,  50, 255)
ROW_EVEN          = (42,  47,  58, 255)
ROW_ADV_ODD       = (40,  50,  38, 255)
ROW_ADV_EVEN      = (46,  56,  44, 255)
TEXT_PRIMARY      = (240, 240, 245, 255)
TEXT_SECONDARY    = (150, 155, 165, 255)
SELL_BG           = (56,  161,  90, 255)
SELL_TEXT         = (210, 255, 220, 255)
BUY_BG            = (190,  50,  55, 255)
BUY_TEXT          = (255, 215, 215, 255)
ADV_BG            = (190, 140,  20, 255)
ADV_TEXT          = (255, 245, 200, 255)
DRAFT_TEXT        = (130, 130, 140, 255)
BORDER_COLOR      = (60,  65,  78, 255)
TITLE_TEXT        = (255, 255, 255, 255)

PADDING           = 28
ROW_H             = 54
COL_HEADER_H      = 42
HEADER_H          = 110
FOOTER_H          = 36
CORNER_R          = 6
PILL_H            = 28
PILL_PAD_X        = 12

SCALE = 3

def _px(n: int) -> int:
    return n * SCALE


def _font(bold: bool, size: int):
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
            return ImageFont.truetype(p, _px(size))
        except OSError:
            pass
    return ImageFont.load_default()


def _pill(draw, x, y, text, bg, fg, font):
    tw  = int(draw.textlength(text, font=font))
    pw  = tw + PILL_PAD_X * 2
    ph  = PILL_H
    r   = ph // 2
    draw.rounded_rectangle([(x, y), (x + pw, y + ph)], radius=r, fill=bg)
    draw.text((x + PILL_PAD_X, y + (ph - font.size) // 2 - 1), text, font=font, fill=fg)
    return pw


def _truncate(text, draw, font, max_px):
    if draw.textlength(text, font=font) <= max_px:
        return text
    while text and draw.textlength(text + "…", font=font) > max_px:
        text = text[:-1]
    return text + "…"


def _header(draw, img_w, title, subtitle, font_title, font_sub):
    draw.rectangle([(0, 0), (img_w, HEADER_H)], fill=HEADER_BG)
    draw.rectangle([(0, HEADER_H - 4), (img_w, HEADER_H)], fill=HEADER_ACCENT)
    draw.text((PADDING, 22), title,    font=font_title, fill=TITLE_TEXT)
    draw.text((PADDING, 62), subtitle, font=font_sub,   fill=TEXT_SECONDARY)


def _col_headers(draw, img_w, y, cols, font):
    draw.rectangle([(0, y), (img_w, y + COL_HEADER_H)], fill=COL_HEADER_BG)
    for cx, label in cols:
        draw.text((cx, y + (COL_HEADER_H - font.size) // 2), label, font=font, fill=COL_HEADER_TEXT)
    draw.line([(0, y + COL_HEADER_H - 1), (img_w, y + COL_HEADER_H - 1)], fill=BORDER_COLOR, width=1)


def _row_bg(draw, img_w, y, idx, advertised):
    if advertised:
        fill = ROW_ADV_ODD if idx % 2 == 0 else ROW_ADV_EVEN
    else:
        fill = ROW_ODD if idx % 2 == 0 else ROW_EVEN
    draw.rectangle([(0, y), (img_w, y + ROW_H)], fill=fill)


def _row_sep(draw, img_w, y):
    draw.line([(0, y + ROW_H - 1), (img_w, y + ROW_H - 1)], fill=BORDER_COLOR, width=1)


def render_items_list(title, subtitle, items, detail_mode=False):
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

    img  = Image.new("RGB", (IMG_W, img_h), BG_COLOR[:3])
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
        draw.text((C_NAME, row_y + (ROW_H - f_body.size) // 2), "No items found.", font=f_body, fill=TEXT_SECONDARY)
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

    draw.text((PADDING, img_h - FOOTER_H + 10), "EscapeItems Shop System", font=f_sub, fill=TEXT_SECONDARY)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _panel_draw_bg(img, draw, x, y, w, h):
    draw.rectangle([x, y, x + w - 1, y + h - 1], fill=(22, 23, 28, 255))

    draw.rectangle([x, y, x + w - 1, y + h - 1],
                   outline=(12, 12, 12, 255), width=_px(2))

    draw.rectangle(
        [x + _px(2), y + _px(2), x + w - _px(3), y + h - _px(3)],
        outline=(75, 78, 92, 255), width=_px(1)
    )

    draw.rectangle(
        [x + _px(3), y + _px(3), x + w - _px(4), y + h - _px(4)],
        outline=(45, 47, 58, 255), width=_px(1)
    )

    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sdraw  = ImageDraw.Draw(shadow, "RGBA")
    for i in range(_px(6)):
        alpha = int(60 * (1 - i / _px(6)))
        sdraw.line(
            [(x + _px(4) + i, y + _px(4) + i),
             (x + _px(4) + i, y + h - _px(4) - i)],
            fill=(0, 0, 0, alpha)
        )
        sdraw.line(
            [(x + _px(4) + i, y + _px(4) + i),
             (x + w - _px(4) - i, y + _px(4) + i)],
            fill=(0, 0, 0, alpha)
        )
    img.alpha_composite(shadow)


def _panel_slot(draw, x, y, size):
    draw.rectangle([x, y, x + size - 1, y + size - 1], fill=(20, 20, 20, 255))
    draw.line([(x, y), (x + size - 2, y)], fill=(12, 12, 12, 255), width=_px(2))
    draw.line([(x, y), (x, y + size - 2)], fill=(12, 12, 12, 255), width=_px(2))
    draw.line([(x + size - 1, y + 1), (x + size - 1, y + size - 1)], fill=(70, 70, 70, 255), width=_px(2))
    draw.line([(x + 1, y + size - 1), (x + size - 1, y + size - 1)], fill=(70, 70, 70, 255), width=_px(2))
    inner = _px(2)
    draw.rectangle([x + inner, y + inner, x + size - inner - 1, y + size - inner - 1], fill=(35, 35, 35, 255))


def _panel_badge(draw, x, y, text, bg, fg, font):
    tw  = int(draw.textlength(text, font=font))
    pad = _px(5)
    bh  = _px(9)
    bw  = tw + pad * 2
    r   = bh // 3
    draw.rounded_rectangle([x, y, x + bw, y + bh], radius=r, fill=bg)
    draw.text((x + pad, y + (bh - font.size) // 2), text, font=font, fill=fg)
    return bw


def _panel_divider(draw, x, y, w):
    draw.line([(x, y + _px(1)), (x + w, y + _px(1))], fill=(12, 12, 12, 255), width=_px(1))
    draw.line([(x, y + _px(2)), (x + w, y + _px(2))], fill=(90, 90, 90, 255), width=_px(1))


_TEXTURE_CACHE: dict[str, "Image.Image | None"] = {}

_WIKI_NAME_OVERRIDES: dict[str, str] = {
    "cheap elytra":     "Elytra",
    "expensive elytra": "Elytra",
}


def _name_to_wiki_url(item_name: str) -> str:
    key       = item_name.strip().lower()
    wiki_name = _WIKI_NAME_OVERRIDES.get(key) or item_name.strip().title().replace(" ", "_")
    return f"https://minecraft.wiki/w/Special:FilePath/{wiki_name}.png"


def _fetch_item_texture(item_name: str, size: int) -> "Image.Image | None":
    key = item_name.strip().lower()
    if key in _TEXTURE_CACHE:
        cached = _TEXTURE_CACHE[key]
        if cached is None:
            return None
        return cached.resize((size, size), Image.NEAREST)

    url = _name_to_wiki_url(item_name)
    result = _fetch_image(url, (size, size))
    _TEXTURE_CACHE[key] = result.resize((64, 64), Image.NEAREST) if result else None
    return result


def _paste_item_texture(img: "Image.Image", item_name: str, x: int, y: int, size: int) -> bool:
    texture = _fetch_item_texture(item_name, size)
    if texture is None:
        return False
    img.paste(texture, (x, y), texture)
    return True


def _draw_generic_fallback(
    img: "Image.Image",
    draw: "ImageDraw.Draw",
    item_name: str,
    x: int,
    y: int,
    size: int,
) -> None:
    h     = hash(item_name.lower()) & 0xFFFFFF
    r     = max(80, min(200, (h >> 16) & 0xFF))
    g     = max(80, min(200, (h >>  8) & 0xFF))
    b     = max(80, min(200,  h        & 0xFF))
    base  = (r, g, b, 255)
    dark  = (r * 6 // 10, g * 6 // 10, b * 6 // 10, 255)
    light = (min(255, r + 60), min(255, g + 60), min(255, b + 60), 255)
    pad   = max(1, size // 8)
    bevel = max(1, size // 5)
    draw.rectangle([x + pad, y + pad, x + size - pad, y + size - pad], fill=base)
    draw.rectangle([x + pad, y + pad, x + size - pad, y + pad + bevel], fill=light)
    draw.rectangle([x + pad, y + pad, x + pad + bevel, y + size - pad], fill=light)
    draw.rectangle([x + pad, y + size - pad - bevel, x + size - pad, y + size - pad], fill=dark)
    draw.rectangle([x + size - pad - bevel, y + pad, x + size - pad, y + size - pad], fill=dark)
    words = item_name.strip().split()
    abbr  = (words[0][0] + words[1][0]).upper() if len(words) >= 2 else item_name[:2].upper()
    try:
        fnt = None
        for fp in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                   "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]:
            try:
                fnt = ImageFont.truetype(fp, max(2, (size - pad * 2) // 2))
                break
            except OSError:
                pass
        if fnt is None:
            fnt = ImageFont.load_default()
        tw = int(draw.textlength(abbr, font=fnt))
        tx = x + (size - tw) // 2
        ty = y + (size - fnt.size) // 2
        draw.text((tx + 1, ty + 1), abbr, font=fnt, fill=dark)
        draw.text((tx, ty), abbr, font=fnt, fill=(255, 255, 255, 255))
    except Exception:
        pass


def _wrap_text(text: str, draw, font, max_width: int) -> list[str]:
    words  = text.split()
    lines  = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _ench_pill_bg(color: tuple, alpha: int = 30, bg: tuple = (22, 23, 28)) -> tuple:
    """Pre-blend a semi-transparent tint over the panel bg into a solid opaque colour."""
    a = alpha / 255.0
    return (
        int(bg[0] * (1 - a) + color[0] * a),
        int(bg[1] * (1 - a) + color[1] * a),
        int(bg[2] * (1 - a) + color[2] * a),
        255,
    )


def _ench_color(ench: str) -> tuple:
    e = ench.lower()
    if any(k in e for k in ("sharpness", "power", "smite", "bane", "fire aspect", "impaling")):
        return (200, 100, 255, 255)
    if any(k in e for k in ("mending", "fortune", "looting", "efficiency", "silk touch")):
        return (80, 200, 255, 255)
    if any(k in e for k in ("protection", "feather", "thorns", "respiration", "aqua", "depth")):
        return (100, 220, 120, 255)
    if any(k in e for k in ("unbreaking", "infinity", "multishot", "quick charge", "piercing")):
        return (255, 200, 80, 255)
    return (200, 200, 215, 255)


def _draw_slot_with_image(img, draw, item_name: str, image_url: str,
                          sx: int, sy: int, slot_size: int, glow: bool = False):
    if glow:
        for gi in range(5):
            alpha = max(12, 65 - gi * 14)
            draw.rectangle(
                [sx - _px(gi+1), sy - _px(gi+1), sx + slot_size + _px(gi+1), sy + slot_size + _px(gi+1)],
                fill=(100, 60, 210, alpha)
            )
    _panel_slot(draw, sx, sy, slot_size)
    pad  = _px(3)
    isz  = slot_size - pad * 2
    fetched = None
    if image_url:
        fetched = _fetch_image(image_url, (isz, isz))
    if fetched is None and item_name:
        fetched = _fetch_item_texture(item_name, isz)
    if fetched:
        img.paste(fetched, (sx + pad, sy + pad), fetched)
    elif item_name:
        _draw_generic_fallback(img, draw, item_name, sx + pad, sy + pad, isz)


def render_item_panel(item: dict) -> io.BytesIO | None:
    if not PILLOW_AVAILABLE:
        return None

    from collections import Counter

    name      = item.get("name", "Unknown")
    location  = item.get("location") or ""
    info      = item.get("info") or ""
    enchants  = [e.strip() for e in (item.get("enchantments") or "").replace("\n", ",").split(",") if e.strip()]
    craftable = bool(item.get("craftable"))
    category  = item.get("item_category") or ""
    image_url = item.get("image") or ""
    craft_raw = item.get("craft_data")

    craft_data = None
    if craftable and craft_raw:
        if isinstance(craft_raw, str):
            try:
                craft_data = json.loads(craft_raw)
            except Exception:
                pass
        elif isinstance(craft_raw, dict):
            craft_data = craft_raw

    grid = craft_data.get("grid", [[None]*3]*3) if craft_data else [[None]*3]*3
    flat_ingredients = [cell for row in grid for cell in row if cell]
    ingredient_counts = Counter(flat_ingredients)
    output_item  = name
    output_count = int(craft_data.get("output", 1) or 1) if craft_data else 1

    INNER  = _px(12)
    MARGIN = _px(16)

    f_title  = _font(True,  10)
    f_cat    = _font(True,   5)
    f_header = _font(True,   6)
    f_body   = _font(False,  5)
    f_ench   = _font(True,   5)
    f_small  = _font(False,  4)
    f_ing    = _font(False,  5)

    PANEL_W = _px(260)

    dummy_img  = Image.new("RGBA", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)

    if craftable:
        CELL    = _px(18)
        GP      = _px(3)
        GRID_W  = CELL * 3 + GP * 4
        GRID_H  = CELL * 3 + GP * 4
        ARW     = _px(10)
        OUT     = CELL + _px(8)
        RIGHT_W = GRID_W + ARW + OUT + _px(10)
        LEFT_W  = PANEL_W - RIGHT_W - INNER * 3

        content_h = _px(12)
        content_h += _px(8)
        info_lines = _wrap_text(info, dummy_draw, f_body, LEFT_W) if info else []
        content_h += len(info_lines[:3]) * (_px(6) + _px(1))
        if info_lines:
            content_h += _px(4)
        if enchants:
            content_h += _px(7)
            content_h += len(enchants) * (_px(7) + _px(1))
            content_h += _px(3)
        if location:
            content_h += _px(7)

        grid_content_h = GRID_H + _px(6)
        body_section_h = max(content_h, grid_content_h)

        ing_h   = _px(8) + _px(2) + _px(7) * len(ingredient_counts)
        body_h  = body_section_h + ing_h + _px(8)
        PANEL_H = _px(12) + _px(14) + _px(4) + body_h + _px(10)
    else:
        IMG_SLOT = _px(60)
        RIGHT_W  = IMG_SLOT + _px(8)
        LEFT_W   = PANEL_W - RIGHT_W - INNER * 3

        content_h = _px(12)
        if location:
            content_h += _px(7)
        if info:
            info_lines = _wrap_text(info, dummy_draw, f_body, LEFT_W)
            content_h += _px(7) + len(info_lines[:4]) * (_px(6) + _px(1)) + _px(4)
        if enchants:
            content_h += _px(7)
            content_h += len(enchants) * (_px(7) + _px(1))

        PANEL_H = _px(12) + _px(14) + _px(4) + max(content_h, IMG_SLOT + _px(4)) + _px(10)

    IMG_W = MARGIN * 2 + PANEL_W
    IMG_H = MARGIN * 2 + PANEL_H

    img  = Image.new("RGBA", (IMG_W, IMG_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    PX = MARGIN
    PY = MARGIN
    _panel_draw_bg(img, draw, PX, PY, PANEL_W, PANEL_H)

    y  = PY + INNER
    lx = PX + INNER

    title_tw = int(draw.textlength(name, font=f_title))
    draw.text((lx, y), name, font=f_title, fill=(255, 255, 255, 255))

    if category:
        cat_text = category.upper()
        cat_tw   = int(draw.textlength(cat_text, font=f_cat))
        cat_bw   = cat_tw + _px(8)
        cat_bh   = _px(9)
        cat_x    = PX + PANEL_W - INNER - cat_bw
        cat_y    = y + (f_title.size - cat_bh) // 2
        draw.rounded_rectangle([cat_x, cat_y, cat_x + cat_bw, cat_y + cat_bh],
                                radius=_px(2), fill=(50, 55, 70, 255))
        draw.rounded_rectangle([cat_x, cat_y, cat_x + cat_bw, cat_y + cat_bh],
                                radius=_px(2), outline=(80, 90, 110, 255), width=_px(1))
        draw.text((cat_x + _px(4), cat_y + (cat_bh - f_cat.size) // 2),
                  cat_text, font=f_cat, fill=(160, 170, 195, 255))

    y += _px(14)
    _panel_divider(draw, lx, y, PANEL_W - INNER * 2)
    y += _px(5)

    if craftable:
        rx = PX + PANEL_W - INNER - RIGHT_W

        body_y = y  

        left_content_h = 0
        if info:
            _info_lines_measure = _wrap_text(info, draw, f_body, LEFT_W)
            left_content_h += _px(8)
            left_content_h += len(_info_lines_measure[:3]) * (_px(6) + _px(1))
            left_content_h += _px(3)
        if enchants:
            left_content_h += _px(7)
            left_content_h += len(enchants) * (_px(7) + _px(1))
            left_content_h += _px(2)
        if location:
            left_content_h += _px(7)

        left_y = y
        gy     = y + (body_section_h - GRID_H) // 2

        if info:
            draw.text((lx, left_y), "Description", font=f_header, fill=(180, 185, 200, 255))
            left_y += _px(8)
            info_lines = _wrap_text(info, draw, f_body, LEFT_W)
            for line in info_lines[:3]:
                draw.text((lx, left_y), line, font=f_body, fill=(190, 192, 205, 255))
                left_y += _px(6) + _px(1)
            left_y += _px(3)

        if enchants:
            draw.text((lx, left_y), "Enchantments", font=f_header, fill=(180, 185, 200, 255))
            left_y += _px(8)
            for ench in enchants:
                ec = _ench_color(ench)
                tw_e = int(draw.textlength(ench, font=f_ench))
                draw.rounded_rectangle([lx, left_y - _px(1),
                                         lx + tw_e + _px(6), left_y + f_ench.size + _px(1)],
                                        radius=_px(2), fill=_ench_pill_bg(ec))
                draw.text((lx + _px(3), left_y), ench, font=f_ench, fill=ec)
                left_y += _px(7) + _px(1)
            left_y += _px(2)

        if location:
            draw.rectangle([lx, left_y + _px(1), lx + _px(5), left_y + _px(6)],
                           fill=(180, 130, 50, 255))
            draw.text((lx + _px(7), left_y), location, font=f_body, fill=(160, 162, 175, 255))

        draw.rounded_rectangle([rx - _px(3), gy - _px(3),
                                  rx + GRID_W + _px(3), gy + GRID_H + _px(3)],
                                radius=_px(2), fill=(15, 15, 15, 255))
        draw.rounded_rectangle([rx - _px(3), gy - _px(3),
                                  rx + GRID_W + _px(3), gy + GRID_H + _px(3)],
                                radius=_px(2), outline=(70, 70, 75, 255), width=_px(1))

        for row in range(3):
            for col in range(3):
                sx     = rx + GP + col * (CELL + GP)
                sy     = gy + GP + row * (CELL + GP)
                cell_v = grid[row][col] if row < len(grid) and col < len(grid[row]) else None
                _draw_slot_with_image(img, draw, cell_v or "", "", sx, sy, CELL)

        ax  = rx + GRID_W + _px(4)
        ay  = gy + GRID_H // 2
        pts = [ax, ay - _px(3),
               ax + ARW - _px(4), ay - _px(3),
               ax + ARW - _px(4), ay - _px(6),
               ax + ARW, ay,
               ax + ARW - _px(4), ay + _px(6),
               ax + ARW - _px(4), ay + _px(3),
               ax, ay + _px(3)]
        draw.polygon(pts, fill=(180, 185, 200, 255))

        ox = ax + ARW + _px(4)
        oy = gy + (GRID_H - OUT) // 2
        _draw_slot_with_image(img, draw, name, image_url, ox, oy, OUT, glow=True)

        ing_section_y = body_y + max(left_content_h, body_section_h) + _px(10)
        _panel_divider(draw, lx, ing_section_y, PANEL_W - INNER * 2)
        ing_section_y += _px(5)

        draw.text((lx, ing_section_y), "Ingredients", font=f_header, fill=(180, 185, 200, 255))
        ing_section_y += _px(8)

        ing_x = lx
        ing_row_h = _px(7)
        for ingredient, count in sorted(ingredient_counts.items()):
            tex = _fetch_item_texture(ingredient, _px(5))
            if tex:
                img.paste(tex, (ing_x, ing_section_y), tex)
                text_x = ing_x + _px(5) + _px(3)
            else:
                text_x = ing_x
            label = f"{count}×  {ingredient}"
            label_w = int(draw.textlength(label, font=f_ing))
            draw.text((text_x, ing_section_y), f"{count}×", font=f_ing, fill=(255, 200, 80, 255))
            draw.text((text_x + int(draw.textlength(f"{count}×  ", font=f_ing)), ing_section_y),
                      ingredient, font=f_ing, fill=(210, 212, 225, 255))
            ing_x += label_w + _px(5) + _px(3) + _px(10)
            max_x = PX + PANEL_W - INNER - _px(60)  
            if ing_x + int(draw.textlength(f"1×  {'X' * 12}", font=f_ing)) > max_x:
                ing_x = lx
                ing_section_y += ing_row_h

        out_label  = f"{output_count}×  {output_item}"
        out_tw     = int(draw.textlength(out_label, font=f_ing))
        out_icon_w = _px(5) + _px(3)
        out_total_w = out_icon_w + out_tw
        out_x = PX + PANEL_W - INNER - out_total_w

        div_x = out_x - _px(8)
        out_y_base = ing_section_y - _px(8) 
        draw.line([(div_x, out_y_base), (div_x, out_y_base + _px(14))],
                  fill=(60, 65, 78, 255), width=_px(1))

        draw.text((out_x, out_y_base), "Output", font=f_header, fill=(180, 185, 200, 255))
        out_y = out_y_base + _px(8)

        tex_out = _fetch_item_texture(output_item, _px(5))
        if tex_out:
            img.paste(tex_out, (out_x, out_y), tex_out)
            out_text_x = out_x + out_icon_w
        else:
            out_text_x = out_x
        draw.text((out_text_x, out_y), f"{output_count}×", font=f_ing, fill=(100, 210, 120, 255))
        draw.text((out_text_x + int(draw.textlength(f"{output_count}×  ", font=f_ing)), out_y),
                  output_item, font=f_ing, fill=(210, 212, 225, 255))

    else:
        IMG_SLOT = _px(60)
        rx       = PX + PANEL_W - INNER - IMG_SLOT
        LEFT_W   = rx - lx - _px(6)

        _draw_slot_with_image(img, draw, name, image_url, rx, y, IMG_SLOT, glow=True)

        left_y = y

        if location:
            draw.rectangle([lx, left_y + _px(1), lx + _px(5), left_y + _px(6)],
                           fill=(180, 130, 50, 255))
            draw.text((lx + _px(7), left_y), location, font=f_body, fill=(160, 162, 175, 255))
            left_y += _px(7)

        if info:
            draw.text((lx, left_y), "Description", font=f_header, fill=(180, 185, 200, 255))
            left_y += _px(8)
            info_lines = _wrap_text(info, draw, f_body, LEFT_W)
            for line in info_lines[:4]:
                draw.text((lx, left_y), line, font=f_body, fill=(190, 192, 205, 255))
                left_y += _px(6) + _px(1)
            left_y += _px(3)

        if enchants:
            _panel_divider(draw, lx, left_y, LEFT_W)
            left_y += _px(5)
            draw.text((lx, left_y), "Enchantments", font=f_header, fill=(180, 185, 200, 255))
            left_y += _px(8)
            for ench in enchants:
                ec = _ench_color(ench)
                tw_e = int(draw.textlength(ench, font=f_ench))
                draw.rounded_rectangle([lx, left_y - _px(1),
                                         lx + tw_e + _px(6), left_y + f_ench.size + _px(1)],
                                        radius=_px(2), fill=_ench_pill_bg(ec))
                draw.text((lx + _px(3), left_y), ench, font=f_ench, fill=ec)
                left_y += _px(7) + _px(1)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def render_item_data_sheet(item: dict) -> io.BytesIO | None:
    if not PILLOW_AVAILABLE:
        return None

    name      = item.get("name", "Unknown")
    location  = item.get("location") or ""
    info      = item.get("info") or ""
    enchants  = [e.strip() for e in (item.get("enchantments") or "").replace("\n", ",").split(",") if e.strip()]
    craftable = bool(item.get("craftable"))
    category  = item.get("item_category") or ""
    image_url = item.get("image") or ""

    INNER  = _px(12)
    MARGIN = _px(16)
    PANEL_W = _px(240)

    f_title  = _font(True,  9)
    f_header = _font(True,  5)
    f_body   = _font(False, 5)
    f_ench   = _font(True,  5)
    f_val    = _font(False, 5)
    f_url    = _font(False, 4)

    IMG_SLOT = _px(40)

    dummy_img  = Image.new("RGBA", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)

    LEFT_W = PANEL_W - INNER * 3 - IMG_SLOT

    ROW_H   = _px(7)
    ROW_GAP = _px(2)

    fields = []
    if category:
        fields.append(("Category",     category))
    if location:
        fields.append(("Location",     location))
    if craftable:
        fields.append(("Craftable",    "Yes"))
    else:
        fields.append(("Craftable",    "No"))
    if image_url:
        fields.append(("Image URL",    image_url))
    else:
        fields.append(("Image URL",    "Not set"))

    content_h = _px(12)
    content_h += _px(14)
    content_h += _px(5)
    for label, value in fields:
        val_lines = _wrap_text(value, dummy_draw, f_val, LEFT_W - _px(4))
        content_h += ROW_H + (len(val_lines) - 1) * (ROW_H - _px(1)) + ROW_GAP + _px(4)

    if info:
        info_lines = _wrap_text(info, dummy_draw, f_body, PANEL_W - INNER * 2)
        content_h += _px(5) + ROW_H + len(info_lines) * (ROW_H - _px(1)) + _px(4)

    if enchants:
        content_h += _px(5) + ROW_H + len(enchants) * (ROW_H + _px(1)) + _px(2)

    PANEL_H = content_h + _px(10)

    IMG_W = MARGIN * 2 + PANEL_W
    IMG_H = MARGIN * 2 + PANEL_H

    img  = Image.new("RGBA", (IMG_W, IMG_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    PX = MARGIN
    PY = MARGIN
    _panel_draw_bg(img, draw, PX, PY, PANEL_W, PANEL_H)

    lx = PX + INNER
    y  = PY + INNER

    draw.text((lx, y), name, font=f_title, fill=(255, 255, 255, 255))

    if category:
        cat_tw = int(draw.textlength(category.upper(), font=f_header))
        cat_bw = cat_tw + _px(8)
        cat_bh = _px(9)
        cat_x  = PX + PANEL_W - INNER - cat_bw
        cat_y  = y + (f_title.size - cat_bh) // 2
        draw.rounded_rectangle([cat_x, cat_y, cat_x + cat_bw, cat_y + cat_bh],
                                radius=_px(2), fill=(40, 44, 58, 255))
        draw.rounded_rectangle([cat_x, cat_y, cat_x + cat_bw, cat_y + cat_bh],
                                radius=_px(2), outline=(70, 75, 95, 255), width=_px(1))
        draw.text((cat_x + _px(4), cat_y + (cat_bh - f_header.size) // 2),
                  category.upper(), font=f_header, fill=(140, 150, 180, 255))

    y += _px(14)
    _panel_divider(draw, lx, y, PANEL_W - INNER * 2)
    y += _px(6)

    rx        = PX + PANEL_W - INNER - IMG_SLOT
    field_max = PANEL_W - INNER * 3 - IMG_SLOT - _px(4)

    _draw_slot_with_image(img, draw, name, image_url, rx, y, IMG_SLOT, glow=False)

    LABEL_W = _px(28)

    for label, value in fields:
        label_text = label + ":"
        draw.text((lx, y), label_text, font=f_header, fill=(120, 125, 150, 255))

        val_lines = _wrap_text(value, draw, f_val, field_max - LABEL_W)
        val_x     = lx + LABEL_W
        val_color = (200, 205, 220, 255) if value not in ("Not set", "No") else (90, 95, 110, 255)
        if label == "Craftable" and value == "Yes":
            val_color = (100, 210, 120, 255)
        if label == "Image URL" and value != "Not set":
            val_color = (80, 160, 255, 255)
            for vl in val_lines:
                trunc = _truncate(vl, draw, f_url, field_max - LABEL_W)
                draw.text((val_x, y + _px(1)), trunc, font=f_url, fill=val_color)
                y += ROW_H - _px(1)
        else:
            for vl in val_lines:
                draw.text((val_x, y), vl, font=f_val, fill=val_color)
                y += ROW_H - _px(1)

        y += ROW_GAP + _px(3)

    if info:
        _panel_divider(draw, lx, y, PANEL_W - INNER * 2)
        y += _px(6)
        draw.text((lx, y), "Info:", font=f_header, fill=(120, 125, 150, 255))
        y += ROW_H
        info_lines = _wrap_text(info, draw, f_body, PANEL_W - INNER * 2)
        for line in info_lines:
            draw.text((lx, y), line, font=f_body, fill=(185, 188, 205, 255))
            y += ROW_H - _px(1)
        y += _px(3)

    if enchants:
        _panel_divider(draw, lx, y, PANEL_W - INNER * 2)
        y += _px(6)
        draw.text((lx, y), "Enchantments:", font=f_header, fill=(120, 125, 150, 255))
        y += ROW_H
        for ench in enchants:
            ec   = _ench_color(ench)
            tw_e = int(draw.textlength(ench, font=f_ench))
            draw.rounded_rectangle([lx, y - _px(1), lx + tw_e + _px(6), y + f_ench.size + _px(1)],
                                    radius=_px(2), fill=_ench_pill_bg(ec, alpha=28))
            draw.text((lx + _px(3), y), ench, font=f_ench, fill=ec)
            y += ROW_H + _px(1)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
