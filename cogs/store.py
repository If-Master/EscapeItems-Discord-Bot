from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass, field

import discord
from discord import app_commands
from discord.ext import commands

from database import users as users_db
from utils import mc_cache

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL = True
except ImportError:
    _PIL = False


@dataclass
class StoreEntry:
    display_name: str
    mc_name:      str
    image_url:    str
    quantity:     int
    price:        float


@dataclass
class _Pending:
    raw_name: str
    matches:  list[dict]
    quantity: int
    price:    float


@dataclass
class StoreSession:
    owner_name: str
    items:      list[StoreEntry] = field(default_factory=list)
    pending:    list[_Pending]   = field(default_factory=list)
    _log:       list[int]        = field(default_factory=list)


def _build_embed(session: StoreSession) -> discord.Embed:
    embed = discord.Embed(
        title=f"\U0001f3ea {session.owner_name}'s Store",
        description=(
            "Bulk-add items with **\u2795 Add Items** \u2014 one per line: `Name, Qty, Price`.\n"
            "When ready hit **\U0001f4e2 Publish** to post your store card.\n\u200b"
        ),
        color=discord.Color.blurple(),
    )

    if session.items:
        lines = [
            f"`{e.display_name}` \u2014 **\u00d7{e.quantity}**  \u00b7  **{e.price:,.0f} \U00010a0c**"
            for e in session.items
        ]
        embed.add_field(
            name=f"\U0001f4e6 Items ({len(session.items)})",
            value="\n".join(lines[:20]) + (f"\n*\u2026and {len(session.items)-20} more*" if len(session.items) > 20 else ""),
            inline=False,
        )
    else:
        embed.add_field(name="\U0001f4e6 Items", value="*None added yet*", inline=False)

    if session.pending:
        names = ", ".join(f"**{p.raw_name}**" for p in session.pending)
        embed.add_field(
            name="\u26a0\ufe0f Needs Clarification",
            value=f"{names}\nPress **\U0001f50d Resolve** to pick the right item.",
            inline=False,
        )

    embed.set_footer(text="Session expires after 10 min  \u2022  EscapeItems Shop System")
    return embed


class _AddItemsModal(discord.ui.Modal, title="\u2795 Add Items to Store"):
    bulk = discord.ui.TextInput(
        label="Items  (Name, Qty, Price \u2014 one per line)",
        placeholder="Diamond Sword, 5, 100\nGolden Apple, 10, 50\nNetherite Ingot, 2, 300",
        style=discord.TextStyle.paragraph,
        max_length=2000,
    )

    def __init__(self, session: StoreSession, view: "StoreView"):
        super().__init__()
        self._session = session
        self._view    = view

    async def on_submit(self, interaction: discord.Interaction):
        lines  = [l.strip() for l in self.bulk.value.splitlines() if l.strip()]
        added  = 0
        errors: list[str] = []

        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 3:
                errors.append(f"\u274c `{line[:60]}` \u2014 need: Name, Qty, Price")
                continue

            raw_name  = parts[0]
            qty_raw   = parts[1].replace(",", "")
            price_raw = parts[2].replace(",", "")

            try:
                qty = int(qty_raw)
                assert qty > 0
            except (ValueError, AssertionError):
                errors.append(f"\u274c `{raw_name}` \u2014 bad quantity `{qty_raw}`")
                continue

            try:
                price = float(price_raw)
                assert price >= 0
            except (ValueError, AssertionError):
                errors.append(f"\u274c `{raw_name}` \u2014 bad price `{price_raw}`")
                continue

            matches    = await mc_cache.find_mc_items(raw_name, limit=6, threshold=0.45)
            best_score = mc_cache._score(raw_name, matches[0]) if matches else 0.0

            if not matches or best_score < 0.45:
                self._session.items.append(
                    StoreEntry(display_name=raw_name, mc_name="", image_url="", quantity=qty, price=price)
                )
                self._session._log.append(len(self._session.items) - 1)
                added += 1

            elif best_score >= 0.88 or len(matches) == 1:
                m = matches[0]
                self._session.items.append(
                    StoreEntry(display_name=raw_name, mc_name=m["name"], image_url=m["image"], quantity=qty, price=price)
                )
                self._session._log.append(len(self._session.items) - 1)
                added += 1

            else:
                self._session.pending.append(_Pending(raw_name=raw_name, matches=matches, quantity=qty, price=price))

        parts: list[str] = []
        if added:
            parts.append(f"\u2705 Added **{added}** item{'s' if added != 1 else ''}")
        if self._session.pending:
            parts.append(f"\u26a0\ufe0f **{len(self._session.pending)}** item{'s need' if len(self._session.pending) != 1 else ' needs'} clarification \u2014 use \U0001f50d Resolve")
        if errors:
            parts.extend(errors[:5])

        await interaction.response.edit_message(embed=_build_embed(self._session), view=self._view)
        if parts:
            await interaction.followup.send("\n".join(parts), ephemeral=True)


class _RemoveItemModal(discord.ui.Modal, title="\U0001f5d1\ufe0f Remove Item"):
    name = discord.ui.TextInput(label="Item name (as listed)", max_length=100)

    def __init__(self, session: StoreSession, view: "StoreView"):
        super().__init__()
        self._session = session
        self._view    = view

    async def on_submit(self, interaction: discord.Interaction):
        target = self.name.value.strip().lower()
        before = len(self._session.items)
        self._session.items = [e for e in self._session.items if e.display_name.lower() != target]
        if len(self._session.items) < before:
            await interaction.response.edit_message(embed=_build_embed(self._session), view=self._view)
            await interaction.followup.send(f"\U0001f5d1\ufe0f Removed **{self.name.value.strip()}**.", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"No item named **{self.name.value.strip()}** found.", ephemeral=True
            )


class _ResolvePendingSelect(discord.ui.Select):
    def __init__(self, pending: _Pending, session: StoreSession, store_view: "StoreView"):
        self._pending    = pending
        self._session    = session
        self._store_view = store_view

        options = [
            discord.SelectOption(
                label=m["display"][:100],
                value=m["name"],
                description=f"minecraft:{m['name']}"[:100],
            )
            for m in pending.matches[:24]
        ]
        options.append(discord.SelectOption(label="Skip \u2014 add without image", value="__skip__"))
        super().__init__(
            placeholder=f"Match for: {pending.raw_name[:50]}",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        chosen = self.values[0]
        if chosen == "__skip__":
            entry = StoreEntry(
                display_name=self._pending.raw_name,
                mc_name="",
                image_url="",
                quantity=self._pending.quantity,
                price=self._pending.price,
            )
        else:
            m = next((x for x in self._pending.matches if x["name"] == chosen), None)
            entry = StoreEntry(
                display_name=self._pending.raw_name,
                mc_name=m["name"] if m else "",
                image_url=m["image"] if m else "",
                quantity=self._pending.quantity,
                price=self._pending.price,
            )

        self._session.items.append(entry)
        self._session._log.append(len(self._session.items) - 1)
        try:
            self._session.pending.remove(self._pending)
        except ValueError:
            pass

        self.disabled = True
        self.view.stop()
        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send(embed=_build_embed(self._session), view=self._store_view)


class _ResolveView(discord.ui.View):
    def __init__(self, pending: _Pending, session: StoreSession, store_view: "StoreView", owner_id: int):
        super().__init__(timeout=60)
        self._owner_id = owner_id
        self.add_item(_ResolvePendingSelect(pending, session, store_view))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._owner_id:
            await interaction.response.send_message("This isn't yours!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


_BG       = (28,  32,  40)
_HDR_BG   = (18,  21,  28)
_ACCENT   = (88, 101, 242)
_COL_BG   = (40,  45,  55)
_COL_TEXT = (200, 200, 210)
_ROW_ODD  = (35,  40,  50)
_ROW_EVEN = (42,  47,  58)
_TEXT_PRI = (240, 240, 245)
_TEXT_SEC = (150, 155, 165)
_BORDER   = (60,  65,  78)
_GOLD     = (255, 200,  60)
_FOOTER_C = (100, 105, 120)
_PAD      = 28
_HDR_H    = 100
_FTR_H    = 36
_ROW_H    = 62
_ICON_SZ  = 42
_CH_H     = 36


def _fnt(bold: bool, size: int):
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


def _trunc(text: str, draw: "ImageDraw.ImageDraw", font, max_px: int) -> str:
    if draw.textlength(text, font=font) <= max_px:
        return text
    while text and draw.textlength(text + "\u2026", font=font) > max_px:
        text = text[:-1]
    return text + "\u2026"


def _render_store(session: StoreSession, icons: dict[str, bytes]) -> io.BytesIO | None:
    if not _PIL or not session.items:
        return None

    f_title = _fnt(True,  24)
    f_sub   = _fnt(False, 14)
    f_ch    = _fnt(True,  13)
    f_name  = _fnt(True,  15)
    f_body  = _fnt(False, 14)
    f_price = _fnt(True,  16)

    COLS  = 2
    COL_W = 420
    IMG_W = _PAD * 2 + COLS * COL_W

    n     = len(session.items)
    rows  = -(-n // COLS)
    img_h = _HDR_H + _CH_H + rows * _ROW_H + _FTR_H + _PAD

    img  = Image.new("RGB", (IMG_W, img_h), _BG)
    draw = ImageDraw.Draw(img)

    draw.rectangle([(0, 0), (IMG_W, _HDR_H)], fill=_HDR_BG)
    draw.rectangle([(0, _HDR_H - 4), (IMG_W, _HDR_H)], fill=_ACCENT)
    draw.text((_PAD, 18), f"\U0001f3ea {session.owner_name}'s Store", font=f_title, fill=(255, 255, 255))
    draw.text((_PAD, 58), f"{n} item{'s' if n != 1 else ''} for sale  \u2022  EscapeItems Shop System", font=f_sub, fill=_TEXT_SEC)

    draw.rectangle([(0, _HDR_H), (IMG_W, _HDR_H + _CH_H)], fill=_COL_BG)
    draw.line([(0, _HDR_H + _CH_H - 1), (IMG_W, _HDR_H + _CH_H - 1)], fill=_BORDER, width=1)
    for c in range(COLS):
        bx = _PAD + c * COL_W
        cy = _HDR_H + (_CH_H - f_ch.size) // 2
        draw.text((bx + _ICON_SZ + 10, cy), "Item",  font=f_ch, fill=_COL_TEXT)
        draw.text((bx + COL_W - 125,   cy), "Qty",   font=f_ch, fill=_COL_TEXT)
        draw.text((bx + COL_W - 80,    cy), "Price", font=f_ch, fill=_COL_TEXT)

    for idx, entry in enumerate(session.items):
        col   = idx % COLS
        row   = idx // COLS
        bx    = _PAD + col * COL_W
        row_y = _HDR_H + _CH_H + row * _ROW_H

        bg = _ROW_ODD if (idx // COLS) % 2 == 0 else _ROW_EVEN
        draw.rectangle([(bx - 4, row_y), (bx + COL_W - 4, row_y + _ROW_H)], fill=bg)

        icon_raw = icons.get(entry.image_url) if entry.image_url else None
        if icon_raw:
            try:
                ico = Image.open(io.BytesIO(icon_raw)).convert("RGBA").resize((_ICON_SZ, _ICON_SZ), Image.NEAREST)
                bg_patch = Image.new("RGBA", (_ICON_SZ, _ICON_SZ), (*bg, 255))
                bg_patch.paste(ico, mask=ico)
                img.paste(bg_patch, (bx, row_y + (_ROW_H - _ICON_SZ) // 2))
            except Exception:
                pass

        mid = row_y + (_ROW_H - f_name.size) // 2
        draw.text((bx + _ICON_SZ + 10, mid), _trunc(entry.display_name, draw, f_name, COL_W - _ICON_SZ - 150), font=f_name, fill=_TEXT_PRI)
        draw.text((bx + COL_W - 125,   mid), f"\u00d7{entry.quantity}",        font=f_body,  fill=_TEXT_SEC)
        draw.text((bx + COL_W - 80,    mid), f"{entry.price:,.0f} \U00010a0c", font=f_price, fill=_GOLD)

        draw.line(
            [(bx - 4, row_y + _ROW_H - 1), (bx + COL_W - 4, row_y + _ROW_H - 1)],
            fill=_BORDER, width=1,
        )

    draw.text((_PAD, _HDR_H + _CH_H + rows * _ROW_H + 10),
              "EscapeItems Shop System", font=f_sub, fill=_FOOTER_C)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


class StoreView(discord.ui.View):
    def __init__(self, session: StoreSession, owner_id: int):
        super().__init__(timeout=600)
        self._session  = session
        self._owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._owner_id:
            await interaction.response.send_message("This isn't your store session!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label="\u2795 Add Items", style=discord.ButtonStyle.success, row=0)
    async def add_items(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(_AddItemsModal(self._session, self))

    @discord.ui.button(label="\U0001f5d1\ufe0f Remove Item", style=discord.ButtonStyle.danger, row=0)
    async def remove_item(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self._session.items:
            await interaction.response.send_message("Your store is empty.", ephemeral=True)
            return
        await interaction.response.send_modal(_RemoveItemModal(self._session, self))

    @discord.ui.button(label="\U0001f50d Resolve", style=discord.ButtonStyle.secondary, row=0)
    async def resolve(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self._session.pending:
            await interaction.response.send_message("Nothing to resolve.", ephemeral=True)
            return
        pending      = self._session.pending[0]
        resolve_view = _ResolveView(pending, self._session, self, interaction.user.id)
        embed = discord.Embed(
            title=f"Clarify: {pending.raw_name}",
            description=f"Multiple Minecraft items match **{pending.raw_name}** \u2014 pick the right one:",
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed, view=resolve_view, ephemeral=True)

    @discord.ui.button(label="\u21a9\ufe0f Undo", style=discord.ButtonStyle.secondary, row=1)
    async def undo(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self._session._log:
            await interaction.response.send_message("Nothing to undo.", ephemeral=True)
            return
        idx = self._session._log.pop()
        if 0 <= idx < len(self._session.items):
            removed = self._session.items.pop(idx)
            await interaction.response.edit_message(embed=_build_embed(self._session), view=self)
            await interaction.followup.send(f"\u21a9\ufe0f Removed **{removed.display_name}**.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing to undo.", ephemeral=True)

    @discord.ui.button(label="\U0001f504 Reset", style=discord.ButtonStyle.secondary, row=1)
    async def reset(self, interaction: discord.Interaction, _: discord.ui.Button):
        self._session.items.clear()
        self._session.pending.clear()
        self._session._log.clear()
        await interaction.response.edit_message(embed=_build_embed(self._session), view=self)

    @discord.ui.button(label="\U0001f4e2 Publish Store", style=discord.ButtonStyle.primary, row=1)
    async def publish(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self._session.items:
            await interaction.response.send_message("Add some items first.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        icon_urls = list({e.image_url for e in self._session.items if e.image_url})
        icon_data = await asyncio.gather(*(mc_cache.fetch_icon(u) for u in icon_urls))
        icons     = {url: data for url, data in zip(icon_urls, icon_data) if data}

        buf = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _render_store(self._session, icons)
        )

        send_target = interaction.channel or interaction.user

        if buf:
            embed = discord.Embed(
                title=f"\U0001f3ea {self._session.owner_name}'s Store",
                description=f"**{len(self._session.items)}** item{'s' if len(self._session.items) != 1 else ''} available for sale",
                color=discord.Color.blurple(),
            )
            embed.set_image(url="attachment://store.png")
            embed.set_footer(text="EscapeItems Shop System")
            await send_target.send(embed=embed, file=discord.File(buf, "store.png"))
        else:
            lines = [
                f"\u2022 **{e.display_name}** \u2014 \u00d7{e.quantity}  \u00b7  {e.price:,.0f} \U00010a0c"
                for e in self._session.items
            ]
            embed = discord.Embed(
                title=f"\U0001f3ea {self._session.owner_name}'s Store",
                description="\n".join(lines),
                color=discord.Color.blurple(),
            )
            embed.set_footer(text="EscapeItems Shop System")
            await send_target.send(embed=embed)

        await interaction.followup.send("\u2705 Store published!", ephemeral=True)


class StoreCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="store", description="Build and publish your item store")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def store(self, interaction: discord.Interaction):
        await users_db.track_user(interaction.user.id, interaction.user.name)
        asyncio.create_task(mc_cache.ensure_items())
        session = StoreSession(owner_name=interaction.user.display_name)
        view    = StoreView(session=session, owner_id=interaction.user.id)
        await interaction.response.send_message(embed=_build_embed(session), view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(StoreCog(bot))