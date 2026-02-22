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


def render_shop_items(
    shop_name: str,
    owner_name: str,
    plot_x: int,
    plot_z: int,
    items: list[dict],
) -> io.BytesIO | None:
    if not PILLOW_AVAILABLE:
        return None

    visible = sorted(
        items,
        key=lambda e: (not e.get("is_advertised", False), e["item_name"].lower()),
    )

    f_title  = _font(True,  26)
    f_sub    = _font(False, 16)
    f_ch     = _font(True,  15)
    f_pill   = _font(True,  13)
    f_body   = _font(False, 16)
    f_body_b = _font(True,  16)

    C_TYPE   = PADDING
    C_ITEM   = PADDING + 185
    C_QTY    = PADDING + 510
    C_PRICE  = PADDING + 620
    C_STATUS = PADDING + 730
    IMG_W    = PADDING + 900

    n_rows = len(visible) if visible else 1
    img_h  = HEADER_H + COL_HEADER_H + n_rows * ROW_H + FOOTER_H + PADDING

    img  = Image.new("RGB", (IMG_W, img_h), BG_COLOR)
    draw = ImageDraw.Draw(img)

    _header(draw, IMG_W,
            shop_name,
            f"Owner: {owner_name}   |   Plot: X={plot_x}, Z={plot_z}   |   {len(visible)} listing(s)",
            f_title, f_sub)

    col_y = HEADER_H
    _col_headers(draw, IMG_W, col_y, [
        (C_TYPE,   "Type"),
        (C_ITEM,   "Item"),
        (C_QTY,    "Qty"),
        (C_PRICE,  "Price"),
        (C_STATUS, "Status"),
    ], f_ch)

    if not visible:
        row_y = col_y + COL_HEADER_H
        _row_bg(draw, IMG_W, row_y, 0, False)
        draw.text((C_ITEM, row_y + (ROW_H - f_body.size) // 2),
                  "No listings yet.", font=f_body, fill=TEXT_SECONDARY)
    else:
        for idx, entry in enumerate(visible):
            row_y    = col_y + COL_HEADER_H + idx * ROW_H
            adv      = entry.get("is_advertised", False)
            is_draft = entry.get("is_draft", False)
            _row_bg(draw, IMG_W, row_y, idx, adv)

            cy = row_y + (ROW_H - PILL_H) // 2

            pill_x = C_TYPE
            if entry["is_selling"]:
                pw = _pill(draw, pill_x, cy, "SELLING", SELL_BG, SELL_TEXT, f_pill)
            else:
                pw = _pill(draw, pill_x, cy, "BUYING",  BUY_BG,  BUY_TEXT,  f_pill)
            if adv:
                _pill(draw, pill_x + pw + 6, cy, "ADVERTISED", ADV_BG, ADV_TEXT, f_pill)

            name  = entry["item_name"]
            if is_draft:
                name = f"[DRAFT] {name}"
            name  = _truncate(name, draw, f_body, C_QTY - C_ITEM - 14)
            color = DRAFT_TEXT if is_draft else TEXT_PRIMARY
            ty    = row_y + (ROW_H - f_body.size) // 2
            draw.text((C_ITEM, ty), name, font=f_body, fill=color)

            qty_label = f"{entry['quantity']} SB" if entry["is_shulker"] else str(entry["quantity"])
            draw.text((C_QTY, ty), qty_label, font=f_body, fill=TEXT_PRIMARY)

            draw.text((C_PRICE, ty), f"{entry['price']:.2f}", font=f_body_b, fill=TEXT_PRIMARY)

            status = "Shulker Box" if entry["is_shulker"] else "Single Item"
            draw.text((C_STATUS, ty), status, font=f_body, fill=TEXT_SECONDARY)

            _row_sep(draw, IMG_W, row_y)

    draw.text((PADDING, img_h - FOOTER_H + 10),
              "EscapeItems Shop System", font=f_sub, fill=TEXT_SECONDARY)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def render_shops_list(shops: list[dict]) -> io.BytesIO | None:
    if not PILLOW_AVAILABLE:
        return None

    sorted_shops = sorted(
        shops,
        key=lambda s: (not s.get("is_advertised", False), int(s.get("shop_id", 9999))),
    )

    f_title  = _font(True,  26)
    f_sub    = _font(False, 16)
    f_ch     = _font(True,  15)
    f_pill   = _font(True,  13)
    f_body   = _font(False, 16)

    C_ID       = PADDING             
    C_STATUS   = PADDING + 65       
    C_NAME     = PADDING + 240      
    C_OWNER    = PADDING + 490     
    C_PLOT     = PADDING + 690      
    C_LISTINGS = PADDING + 850      
    IMG_W      = PADDING + 990

    n_rows  = len(sorted_shops) if sorted_shops else 1
    img_h   = HEADER_H + COL_HEADER_H + n_rows * ROW_H + FOOTER_H + PADDING

    img  = Image.new("RGB", (IMG_W, img_h), BG_COLOR)
    draw = ImageDraw.Draw(img)

    total     = len(shops)
    adv_count = sum(1 for s in shops if s.get("is_advertised", False))
    _header(draw, IMG_W,
            "Shops List",
            f"{total} shop(s) registered   |   {adv_count} advertised",
            f_title, f_sub)

    col_y = HEADER_H
    _col_headers(draw, IMG_W, col_y, [
        (C_ID,       "ID"),
        (C_STATUS,   "Status"),
        (C_NAME,     "Shop Name"),
        (C_OWNER,    "Owner"),
        (C_PLOT,     "Plot"),
        (C_LISTINGS, "Listings"),
    ], f_ch)

    if not sorted_shops:
        row_y = col_y + COL_HEADER_H
        _row_bg(draw, IMG_W, row_y, 0, False)
        draw.text((C_NAME, row_y + (ROW_H - f_body.size) // 2),
                  "No shops registered yet.", font=f_body, fill=TEXT_SECONDARY)
    else:
        for idx, shop in enumerate(sorted_shops):
            row_y = col_y + COL_HEADER_H + idx * ROW_H
            adv   = shop.get("is_advertised", False)
            _row_bg(draw, IMG_W, row_y, idx, adv)

            cy = row_y + (ROW_H - PILL_H) // 2
            ty = row_y + (ROW_H - f_body.size) // 2

            shop_id_label = f"#{shop.get('shop_id', '?')}"
            draw.text((C_ID, ty), shop_id_label, font=f_body, fill=TEXT_SECONDARY)

            if adv:
                _pill(draw, C_STATUS, cy, "ADVERTISED", ADV_BG, ADV_TEXT, f_pill)
            else:
                draw.text((C_STATUS + 6, ty), "—", font=f_body, fill=TEXT_SECONDARY)

            name = _truncate(shop["shop_name"], draw, f_body, C_OWNER - C_NAME - 14)
            draw.text((C_NAME, ty), name, font=f_body, fill=TEXT_PRIMARY)

            owner = _truncate(shop.get("owner_name", "—"), draw, f_body, C_PLOT - C_OWNER - 14)
            draw.text((C_OWNER, ty), owner, font=f_body, fill=TEXT_SECONDARY)

            plot = f"X={shop.get('plot_x', '?')}, Z={shop.get('plot_z', '?')}"
            draw.text((C_PLOT, ty), plot, font=f_body, fill=TEXT_SECONDARY)

            draw.text((C_LISTINGS, ty), str(shop.get("item_count", 0)),
                      font=f_body, fill=TEXT_PRIMARY)

            _row_sep(draw, IMG_W, row_y)

    draw.text((PADDING, img_h - FOOTER_H + 10),
              "EscapeItems Shop System", font=f_sub, fill=TEXT_SECONDARY)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def render_item_search(
    query: str,
    results: list[dict],
) -> io.BytesIO | None:
    if not PILLOW_AVAILABLE:
        return None

    sorted_results = sorted(
        results,
        key=lambda r: (not r.get("is_advertised", False), r["price"]),
    )

    f_title  = _font(True,  26)
    f_sub    = _font(False, 16)
    f_ch     = _font(True,  15)
    f_pill   = _font(True,  13)
    f_body   = _font(False, 16)
    f_body_b = _font(True,  16)

    C_TYPE  = PADDING
    C_ITEM  = PADDING + 185
    C_SHOP  = PADDING + 420
    C_OWNER = PADDING + 640
    C_QTY   = PADDING + 790
    C_PRICE = PADDING + 890
    IMG_W   = PADDING + 1010

    n_rows  = len(sorted_results) if sorted_results else 1
    img_h   = HEADER_H + COL_HEADER_H + n_rows * ROW_H + FOOTER_H + PADDING

    img  = Image.new("RGB", (IMG_W, img_h), BG_COLOR)
    draw = ImageDraw.Draw(img)

    _header(draw, IMG_W,
            f'Search: "{query}"',
            f"{len(sorted_results)} result(s) — sorted by price (advertised first)",
            f_title, f_sub)

    col_y = HEADER_H
    _col_headers(draw, IMG_W, col_y, [
        (C_TYPE,  "Type"),
        (C_ITEM,  "Item"),
        (C_SHOP,  "Shop"),
        (C_OWNER, "Owner"),
        (C_QTY,   "Qty"),
        (C_PRICE, "Price"),
    ], f_ch)

    if not sorted_results:
        row_y = col_y + COL_HEADER_H
        _row_bg(draw, IMG_W, row_y, 0, False)
        draw.text((C_ITEM, row_y + (ROW_H - f_body.size) // 2),
                  "No results found.", font=f_body, fill=TEXT_SECONDARY)
    else:
        for idx, entry in enumerate(sorted_results):
            row_y = col_y + COL_HEADER_H + idx * ROW_H
            adv   = entry.get("is_advertised", False)
            _row_bg(draw, IMG_W, row_y, idx, adv)

            cy = row_y + (ROW_H - PILL_H) // 2
            ty = row_y + (ROW_H - f_body.size) // 2

            pill_x = C_TYPE
            if entry["is_selling"]:
                pw = _pill(draw, pill_x, cy, "SELLING", SELL_BG, SELL_TEXT, f_pill)
            else:
                pw = _pill(draw, pill_x, cy, "BUYING",  BUY_BG,  BUY_TEXT,  f_pill)
            if adv:
                _pill(draw, pill_x + pw + 6, cy, "ADVERTISED", ADV_BG, ADV_TEXT, f_pill)

            item = _truncate(entry["item_name"], draw, f_body, C_SHOP - C_ITEM - 14)
            draw.text((C_ITEM, ty), item, font=f_body, fill=TEXT_PRIMARY)

            shop = _truncate(entry.get("shop_name", "—"), draw, f_body, C_OWNER - C_SHOP - 14)
            draw.text((C_SHOP, ty), shop, font=f_body, fill=TEXT_SECONDARY)

            owner = _truncate(entry.get("owner_name", "—"), draw, f_body, C_QTY - C_OWNER - 14)
            draw.text((C_OWNER, ty), owner, font=f_body, fill=TEXT_SECONDARY)

            qty_label = f"{entry['quantity']} SB" if entry["is_shulker"] else str(entry["quantity"])
            draw.text((C_QTY, ty), qty_label, font=f_body, fill=TEXT_PRIMARY)

            draw.text((C_PRICE, ty), f"{entry['price']:.2f}", font=f_body_b, fill=TEXT_PRIMARY)

            _row_sep(draw, IMG_W, row_y)

    draw.text((PADDING, img_h - FOOTER_H + 10),
              "EscapeItems Shop System", font=f_sub, fill=TEXT_SECONDARY)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

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


def render_shop_layout(
    shop_name: str,
    owner_name: str,
    plot_x: int,
    plot_z: int,
    items: list[dict],
) -> io.BytesIO | None:
    return render_shop_items(shop_name, owner_name, plot_x, plot_z, items)
