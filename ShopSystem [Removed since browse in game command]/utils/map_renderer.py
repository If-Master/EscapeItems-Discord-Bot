from __future__ import annotations

import asyncio
import io
import math

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

BLUEMAP_BASE_URL = "https://map.escape.systems"
BLUEMAP_MAP_ID   = "minecraft_overworld"

VIEWPORT_W  = 1200
VIEWPORT_H  = 1200

OUTPUT_PX   = 1024

TILE_WAIT_MS = 15000

BLUEMAP_ZOOM = 4

RADIUS_BLOCKS = 350

MARKER_R    = 11
MARKER_FILL = (88, 101, 242)
MARKER_ADV  = (190, 140, 20)
MARKER_RING = (255, 255, 255)
LEADER_COL  = (88, 101, 242, 180)
LABEL_BG    = (18, 21, 28, 215)
OVERLAP_PX  = 32


def _font(bold: bool, size: int):
    paths = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
        if bold else
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]
    )
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()

def _spread_markers(markers: list[dict]) -> list[dict]:
    placed = [dict(m) for m in markers]
    for m in placed:
        m["anchor_px"] = m["px"]
        m["anchor_pz"] = m["pz"]
        m["label_px"]  = m["px"]
        m["label_pz"]  = m["pz"]

    visited = set()
    for i, mi in enumerate(placed):
        if i in visited:
            continue
        cluster = [i]
        for j, mj in enumerate(placed):
            if j == i:
                continue
            dx = mi["anchor_px"] - mj["anchor_px"]
            dz = mi["anchor_pz"] - mj["anchor_pz"]
            if math.hypot(dx, dz) < OVERLAP_PX:
                cluster.append(j)
        if len(cluster) > 1:
            visited.update(cluster)
            cx = sum(placed[k]["anchor_px"] for k in cluster) / len(cluster)
            cz = min(placed[k]["anchor_pz"] for k in cluster)
            spread = 42
            lift   = MARKER_R * 2 + 8 + 30 * len(cluster)
            for n, k in enumerate(cluster):
                offset = (n - (len(cluster) - 1) / 2) * spread
                placed[k]["label_px"] = int(cx + offset)
                placed[k]["label_pz"] = int(cz - lift)

    return placed

async def _screenshot_bluemap(cx: float, cz: float) -> Image.Image | None:
    if not PLAYWRIGHT_AVAILABLE:
        return None

    url = (
        f"{BLUEMAP_BASE_URL}/"
        f"?world={BLUEMAP_MAP_ID}&zoom={BLUEMAP_ZOOM}&x={cx:.1f}&z={cz:.1f}"
    )


    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = await browser.new_page(
            viewport={"width": VIEWPORT_W, "height": VIEWPORT_H},
        )

        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        
        await page.wait_for_timeout(TILE_WAIT_MS)

        await page.evaluate("""() => {
            const selectors = [
                '.side-menu',
                '.toolbar',
                '.bluemap-menu',
                '#bluemap-menu',
                '.control-bar',
                '.attribution',
                '[class*="toolbar"]',
                '[class*="menu"]',
                '[class*="button"]',
                '[class*="control"]',
            ];
            selectors.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => {
                    el.style.display = 'none';
                });
            });
        }""")

        raw = await page.screenshot(type="png", full_page=False)
        await browser.close()

    return Image.open(io.BytesIO(raw)).convert("RGBA")

BLOCKS_VISIBLE_AT_ZOOM_0 = 1000  

def _world_to_screen(wx: float, wz: float, cx: float, cz: float) -> tuple[int, int]:
    scale = OUTPUT_PX / BLOCKS_VISIBLE_AT_ZOOM_0
    px = OUTPUT_PX // 2 + int((wx - cx) * scale)
    pz = OUTPUT_PX // 2 + int((wz - cz) * scale)
    return px, pz


async def render_shop_map(
    shops: list[dict],
    radius: int = RADIUS_BLOCKS,
) -> io.BytesIO | None:
    if not PILLOW_AVAILABLE or not PLAYWRIGHT_AVAILABLE or not shops:
        return None

    cx = sum(s["plot_x"] for s in shops) / len(shops)
    cz = sum(s["plot_z"] for s in shops) / len(shops)

    map_img = await _screenshot_bluemap(cx, cz)
    if map_img is None:
        return None

    canvas = map_img.resize((OUTPUT_PX, OUTPUT_PX), Image.LANCZOS)

    raw_markers = [
        {
            "px":            _world_to_screen(shop["plot_x"], shop["plot_z"], cx, cz)[0],
            "pz":            _world_to_screen(shop["plot_x"], shop["plot_z"], cx, cz)[1],
            "shop_name":     shop["shop_name"],
            "plot_x":        shop["plot_x"],
            "plot_z":        shop["plot_z"],
            "is_advertised": shop.get("is_advertised", False),
        }
        for shop in shops
    ]
    markers = _spread_markers(raw_markers)

    overlay = Image.new("RGBA", (OUTPUT_PX, OUTPUT_PX), (0, 0, 0, 0))
    ov      = ImageDraw.Draw(overlay, "RGBA")
    f_name  = _font(True,  13)
    f_coord = _font(False, 11)

    for m in markers:
        ax, az = m["anchor_px"], m["anchor_pz"]
        lx, lz = m["label_px"],  m["label_pz"]
        fill   = MARKER_ADV if m["is_advertised"] else MARKER_FILL

        if (ax, az) != (lx, lz):
            ov.line([(lx, lz), (ax, az)], fill=LEADER_COL, width=2)

        ov.ellipse(
            [(ax - MARKER_R, az - MARKER_R), (ax + MARKER_R, az + MARKER_R)],
            fill=fill, outline=MARKER_RING, width=2,
        )

        name_t  = m["shop_name"][:22]
        coord_t = f"X={m['plot_x']}  Z={m['plot_z']}"
        nw = int(ov.textlength(name_t,  font=f_name))
        cw = int(ov.textlength(coord_t, font=f_coord))
        bw = max(nw, cw) + 14
        bh = 36
        bx = lx - bw // 2
        bz = lz - bh - 2

        ov.rounded_rectangle(
            [(bx, bz), (bx + bw, bz + bh)],
            radius=4, fill=LABEL_BG, outline=fill, width=1,
        )
        ov.text((bx + 7, bz + 3),  name_t,  font=f_name,  fill=(240, 240, 245))
        ov.text((bx + 7, bz + 20), coord_t, font=f_coord, fill=(160, 165, 175))

    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay)

    fh  = 34
    out = Image.new("RGBA", (OUTPUT_PX, OUTPUT_PX + fh), (18, 21, 28, 255))
    out.paste(canvas, (0, 0))
    fd = ImageDraw.Draw(out)
    fd.line([(0, OUTPUT_PX), (OUTPUT_PX, OUTPUT_PX)], fill=(88, 101, 242), width=2)
    fd.ellipse([(10, OUTPUT_PX + 9), (22, OUTPUT_PX + 21)],
               fill=MARKER_FILL, outline=MARKER_RING, width=1)
    fd.text((26, OUTPUT_PX + 8), "Shop", font=_font(False, 13), fill=(200, 200, 210))
    fd.ellipse([(72, OUTPUT_PX + 9), (84, OUTPUT_PX + 21)],
               fill=MARKER_ADV, outline=MARKER_RING, width=1)
    fd.text((88, OUTPUT_PX + 8), "Advertised", font=_font(False, 13), fill=(200, 200, 210))
    fd.text((OUTPUT_PX - 150, OUTPUT_PX + 8),
            f"+-{radius} blocks", font=_font(False, 13), fill=(110, 115, 125))

    buf = io.BytesIO()
    out.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf
