from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

_RAW_PRICES: dict[str, float] = {
    "acacia_leaves": 0.05, "acacia_log": 0.15, "acacia_sapling": 0.10,
    "amethyst_block": 0.25, "ancient_debris": 9.75, "andesite": 0.20,
    "apple": 0.50, "armadillo_scute": 1.25, "arrow": 0.10,
    "azalea": 0.10, "azalea_leaves": 0.05, "bamboo": 0.05,
    "basalt": 0.05, "beetroot": 0.10, "beetroot_seeds": 0.02,
    "birch_leaves": 0.05, "birch_log": 0.15, "birch_sapling": 0.10,
    "black_terracotta": 0.20, "blackstone": 0.20, "blaze_rod": 0.50,
    "blue_ice": 4.05, "blue_terracotta": 0.20, "bone": 0.30,
    "bone_block": 0.90, "bone_meal": 0.10, "breeze_rod": 5.00,
    "brown_mushroom": 0.10, "brown_mushroom_block": 0.05, "brown_terracotta": 0.20,
    "cactus": 0.10, "calcite": 0.15, "carrot": 0.05,
    "cherry_leaves": 0.05, "cherry_log": 0.15, "cherry_sapling": 0.10,
    "chorus_fruit": 0.20, "clay": 0.40, "clay_ball": 0.10,
    "coal": 0.05, "coal_block": 0.45, "coal_ore": 0.50,
    "coarse_dirt": 0.80, "cobbled_deepslate": 0.10, "cobblestone": 0.01,
    "turtle_scute": 1.25, "verdant_froglight": 0.50, "vine": 0.50,
    "warped_fungus": 0.20, "warped_nylium": 0.20, "warped_stem": 0.15,
    "warped_wart_block": 1.80, "wheat": 0.10, "white_terracotta": 0.20,
    "wind_charge": 1.20, "wither_skeleton_skull": 4.00, "yellow_terracotta": 0.20,
    "cocoa_beans": 0.10, "copper_block": 1.35, "copper_ingot": 0.15,
    "copper_ore": 1.25, "crimson_fungus": 0.20, "crimson_nylium": 0.20,
    "crimson_stem": 0.15, "crying_obsidian": 0.50, "cyan_terracotta": 0.20,
    "dark_oak_leaves": 0.05, "dark_oak_log": 0.15, "dark_oak_sapling": 0.10,
    "dark_prismarine": 3.15, "deepslate": 0.10, "deepslate_coal_ore": 0.50,
    "deepslate_copper_ore": 1.25, "deepslate_diamond_ore": 5.00,
    "deepslate_emerald_ore": 7.00, "deepslate_gold_ore": 1.25,
    "deepslate_iron_ore": 0.75, "deepslate_lapis_ore": 1.75,
    "deepslate_redstone_ore": 1.50, "diamond": 0.25, "diamond_block": 2.25,
    "diamond_ore": 5.00, "diorite": 0.20, "dirt": 0.05,
    "dripstone_block": 1.00, "emerald": 0.15, "emerald_block": 1.35,
    "emerald_ore": 7.00, "ender_pearl": 0.01, "end_stone": 0.05,
    "feather": 0.25, "fermented_spider_eye": 0.30, "flint": 0.05,
    "flowering_azalea": 0.10, "flowering_azalea_leaves": 0.05,
    "ghast_tear": 1.50, "gilded_blackstone": 25.00, "glass": 0.08,
    "glass_bottle": 0.20, "glow_berries": 0.80, "glow_ink_sac": 1.00,
    "glowstone": 0.80, "glowstone_dust": 0.20, "gold_block": 2.25,
    "gold_ingot": 0.25, "gold_nugget": 0.02, "gold_ore": 1.25,
    "granite": 0.20, "grass_block": 0.10, "gravel": 0.01,
    "gray_terracotta": 0.20, "green_terracotta": 0.20, "gunpowder": 0.38,
    "honey_bottle": 0.60, "honeycomb": 0.25, "ice": 0.05,
    "ink_sac": 0.75, "iron_block": 1.35, "iron_ingot": 0.15,
    "iron_nugget": 0.01, "iron_ore": 0.75, "jungle_leaves": 0.05,
    "jungle_log": 0.15, "jungle_sapling": 0.10, "kelp": 0.05,
    "lapis_block": 0.45, "lapis_ore": 1.75, "leather": 0.75,
    "light_blue_terracotta": 0.20, "light_gray_terracotta": 0.20,
    "lime_terracotta": 0.20, "magenta_terracotta": 0.20,
    "magma_block": 0.25, "magma_cream": 0.50, "mangrove_leaves": 0.05,
    "mangrove_log": 0.15, "mangrove_propagule": 0.10, "mangrove_roots": 0.13,
    "melon": 0.90, "melon_seeds": 0.02, "melon_slice": 0.10,
    "moss_block": 0.20, "moss_carpet": 0.13, "mud": 0.80,
    "mushroom_stem": 0.20, "mycelium": 0.20, "nether_bricks": 0.25,
    "nether_gold_ore": 0.35, "nether_quartz_ore": 0.50, "nether_star": 12.00,
    "nether_wart": 0.20, "nether_wart_block": 1.80, "netherite_block": 2700.00,
    "netherite_ingot": 304.00, "netherite_scrap": 75.00,
    "oak_leaves": 0.05, "oak_log": 0.15, "oak_sapling": 0.10,
    "obsidian": 0.25, "ochre_froglight": 0.50, "orange_terracotta": 0.20,
    "packed_ice": 0.45, "packed_mud": 0.90, "pale_moss_block": 0.20,
    "pale_moss_carpet": 0.13, "pale_oak_leaves": 0.05, "pale_oak_log": 0.15,
    "pale_oak_sapling": 0.10, "pearlescent_froglight": 0.50,
    "phantom_membrane": 1.50, "pink_terracotta": 0.20, "podzol": 0.25,
    "pointed_dripstone": 0.25, "potato": 0.05, "prismarine": 1.20,
    "prismarine_bricks": 2.70, "prismarine_shard": 0.30, "pufferfish": 1.00,
    "pumpkin": 0.90, "pumpkin_seeds": 0.02, "purple_terracotta": 0.20,
    "quartz": 0.15, "quartz_block": 0.60, "rabbit_hide": 0.25,
    "rabbit_foot": 10.00, "beef": 0.60, "chicken": 0.60, "cod": 0.60,
    "raw_copper": 0.10, "raw_copper_block": 0.90, "raw_gold": 0.35,
    "raw_gold_block": 3.15, "raw_iron": 0.25, "raw_iron_block": 2.25,
    "mutton": 0.60, "porkchop": 0.60, "rabbit": 0.60, "salmon": 0.60,
    "red_mushroom": 0.10, "red_mushroom_block": 0.05, "red_sand": 0.20,
    "red_sandstone": 0.80, "red_terracotta": 0.20, "redstone_block": 0.45,
    "redstone": 0.05, "redstone_ore": 1.50, "rooted_dirt": 1.00,
    "rotten_flesh": 0.05, "sand": 0.02, "sandstone": 0.64,
    "sculk": 0.05, "sculk_catalyst": 1.00, "sculk_sensor": 5.00,
    "sculk_shrieker": 7.50, "sea_lantern": 5.70, "sea_pickle": 0.20,
    "wheat_seeds": 0.05, "shulker_shell": 2.00, "slime_ball": 0.30,
    "smooth_basalt": 0.07, "snow_block": 0.15, "soul_sand": 0.25,
    "soul_soil": 0.25, "spectral_arrow": 0.15, "spider_eye": 0.16,
    "spruce_leaves": 0.05, "spruce_log": 0.15, "spruce_sapling": 0.10,
    "stick": 0.02, "stone": 0.02, "string": 0.40, "sugar": 0.10,
    "sugar_cane": 0.05, "sweet_berries": 0.80, "terracotta": 0.20,
    "tropical_fish": 1.00, "tuff": 0.12,
}

_ALIASES: dict[str, str] = {
    "log": "oak_log", "leaves": "oak_leaves", "sapling": "oak_sapling",
    "lapis_lazuli": "lapis_block", "lapis": "lapis_block",
    "redstone_dust": "redstone", "melon_block": "melon",
    "pumpkin_block": "pumpkin", "nether_quartz": "quartz",
    "raw_beef": "beef", "raw_chicken": "chicken", "raw_cod": "cod",
    "raw_mutton": "mutton", "raw_porkchop": "porkchop",
    "raw_rabbit": "rabbit", "raw_salmon": "salmon",
    "netherite_ingots": "netherite_ingot", "slimeball": "slime_ball",
    "nether_brick": "nether_bricks",
}

_ITEMS_PER_PAGE = 75

@dataclass
class FarmEntry:
    item_id:      str
    price:        float          
    qty:          float
    nbt_price:    float         
    custom_price: bool = False  


@dataclass
class FarmSession:
    produced: list[FarmEntry] = field(default_factory=list)
    consumed: list[FarmEntry] = field(default_factory=list)
    _log:     list[tuple[str, int]] = field(default_factory=list)


def _normalise(item: str) -> str:
    import re
    item = item.strip().lower()
    item = re.sub(r"^minecraft:", "", item)
    return item.replace(" ", "_").replace("-", "_")


def _lookup(raw: str) -> tuple[str, float] | tuple[None, None]:
    key = _normalise(raw)
    if key in _RAW_PRICES:
        return key, _RAW_PRICES[key]
    if key in _ALIASES:
        resolved = _ALIASES[key]
        return resolved, _RAW_PRICES[resolved]
    return None, None


def _pretty(item_id: str) -> str:
    return item_id.replace("_", " ").title()


def _eph(interaction: discord.Interaction) -> bool:
    return True


def _build_embed(session: FarmSession) -> discord.Embed:
    income = sum(e.price * e.qty for e in session.produced)
    cost   = sum(e.price * e.qty for e in session.consumed)
    profit = income - cost
    sign   = "+" if profit >= 0 else "−"
    color  = discord.Color.green() if profit >= 0 else discord.Color.red()

    embed = discord.Embed(
        title="🌾 Farm Calculator",
        description=(
            "Add as many produced and consumed items as you like, "
            "then click **📊 Calculate** to generate your breakdown image.\n\u200b"
        ),
        color=color,
    )

    if session.produced:
        lines = [
            f"`{_pretty(e.item_id)}` — **{e.qty:,.0f}**/hr  →  +{e.price * e.qty:,.2f} 𐃌"
            for e in session.produced
        ]
        embed.add_field(name="📦 Producing", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="📦 Producing", value="*None added yet — use ➕ Add Produced Item*", inline=False)

    if session.consumed:
        lines = []
        for e in session.consumed:
            custom_tag = " *(custom price)*" if e.custom_price else ""
            lines.append(
                f"`{_pretty(e.item_id)}` — **{e.qty:,.0f}**/hr @ {e.price:.4f} 𐃌{custom_tag}"
                f"  →  −{e.price * e.qty:,.2f} 𐃌"
            )
        embed.add_field(name="⛏️ Consuming", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="⛏️ Consuming", value="*None added — optional*", inline=False)

    if session.produced or session.consumed:
        embed.add_field(
            name="Estimated Profit / hr",
            value=f"**`{sign}{abs(profit):,.2f} 𐃌`**",
            inline=False,
        )

    embed.set_footer(text="Session expires after 5 min of inactivity  •  EscapeItems Shop System")
    return embed


class _AddProduceModal(discord.ui.Modal, title="➕ Add Produced Item"):
    item_field = discord.ui.TextInput(
        label="Item ID (minecraft:xxx)",
        placeholder="e.g. minecraft:wheat",
        min_length=3,
        max_length=80,
    )
    amount_field = discord.ui.TextInput(
        label="Amount per hour",
        placeholder="e.g. 3600",
        min_length=1,
        max_length=20,
    )

    def __init__(self, session: FarmSession, view: "FarmView"):
        super().__init__()
        self._session = session
        self._view    = view

    async def on_submit(self, interaction: discord.Interaction):
        raw      = self.item_field.value.strip()
        item_id, nbt_price = _lookup(raw)

        if item_id is None:
            await interaction.response.send_message(
                f"❌ **Unknown item:** `{raw}`\n"
                f"Use the exact Minecraft ID, e.g. `minecraft:sugar_cane`.\n"
                f"*Tip: `/farmprices` shows the full price list.*",
                ephemeral=_eph(interaction),
            )
            return

        try:
            qty = float(self.amount_field.value.strip().replace(",", ""))
            if qty <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ Amount must be a positive number.", ephemeral=_eph(interaction)
            )
            return

        entry = FarmEntry(item_id=item_id, price=nbt_price, qty=qty, nbt_price=nbt_price)
        self._session.produced.append(entry)
        self._session._log.append(("produce", len(self._session.produced) - 1))

        await interaction.response.edit_message(embed=_build_embed(self._session), view=self._view)


class _AddConsumeModal(discord.ui.Modal, title="⛏️ Add Consumed Item"):
    item_field = discord.ui.TextInput(
        label="Item ID (minecraft:xxx)",
        placeholder="e.g. minecraft:bone_meal",
        min_length=3,
        max_length=80,
    )
    amount_field = discord.ui.TextInput(
        label="Amount per hour",
        placeholder="e.g. 200",
        min_length=1,
        max_length=20,
    )
    custom_price_field = discord.ui.TextInput(
        label="Custom price per item (optional)",
        placeholder="Leave blank to use NBT price — or enter player-shop price",
        required=False,
        max_length=20,
    )

    def __init__(self, session: FarmSession, view: "FarmView"):
        super().__init__()
        self._session = session
        self._view    = view

    async def on_submit(self, interaction: discord.Interaction):
        raw      = self.item_field.value.strip()
        item_id, nbt_price = _lookup(raw)

        if item_id is None:
            await interaction.response.send_message(
                f"❌ **Unknown item:** `{raw}`\n"
                f"Use the exact Minecraft ID, e.g. `minecraft:bone_meal`.\n"
                f"*Tip: `/farmprices` shows the full price list.*",
                ephemeral=_eph(interaction),
            )
            return

        try:
            qty = float(self.amount_field.value.strip().replace(",", ""))
            if qty <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ Amount must be a positive number.", ephemeral=_eph(interaction)
            )
            return

        custom_raw   = self.custom_price_field.value.strip()
        custom_price = False
        price        = nbt_price

        if custom_raw:
            try:
                override = float(custom_raw.replace(",", ""))
                if override <= 0:
                    raise ValueError
                price        = override
                custom_price = True
            except ValueError:
                await interaction.response.send_message(
                    "❌ Custom price must be a positive number (or leave it blank to use the NBT price).",
                    ephemeral=_eph(interaction),
                )
                return

        entry = FarmEntry(
            item_id=item_id, price=price, qty=qty,
            nbt_price=nbt_price, custom_price=custom_price,
        )
        self._session.consumed.append(entry)
        self._session._log.append(("consume", len(self._session.consumed) - 1))

        await interaction.response.edit_message(embed=_build_embed(self._session), view=self._view)

class FarmView(discord.ui.View):

    def __init__(self, session: FarmSession, owner_id: int):
        super().__init__(timeout=300)
        self._session  = session
        self._owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._owner_id:
            await interaction.response.send_message(
                "This isn't your farm calculator!", ephemeral=_eph(interaction)
            )
            return False
        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True  


    @discord.ui.button(label="➕ Add Produced Item", style=discord.ButtonStyle.success, row=0)
    async def add_produced(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(_AddProduceModal(self._session, self))

    @discord.ui.button(label="⛏️ Add Consumed Item", style=discord.ButtonStyle.danger, row=0)
    async def add_consumed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(_AddConsumeModal(self._session, self))

    @discord.ui.button(label="↩️ Undo Last", style=discord.ButtonStyle.secondary, row=0)
    async def undo_last(self, interaction: discord.Interaction, button: discord.ui.Button):
        log = self._session._log
        if not log:
            await interaction.response.send_message("Nothing to undo!", ephemeral=_eph(interaction))
            return

        role, idx = log.pop()
        if role == "produce" and self._session.produced:
            removed = self._session.produced.pop(idx)
            verb    = "produced"
        elif role == "consume" and self._session.consumed:
            removed = self._session.consumed.pop(idx)
            verb    = "consumed"
        else:
            await interaction.response.send_message("Nothing to undo!", ephemeral=_eph(interaction))
            return

        await interaction.response.edit_message(embed=_build_embed(self._session), view=self)
        await interaction.followup.send(
            f"↩️ Removed **{_pretty(removed.item_id)}** from {verb}.",
            ephemeral=_eph(interaction),
        )


    @discord.ui.button(label="🔄 Reset", style=discord.ButtonStyle.secondary, row=1)
    async def reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._session.produced.clear()
        self._session.consumed.clear()
        self._session._log.clear()
        await interaction.response.edit_message(embed=_build_embed(self._session), view=self)

    @discord.ui.button(label="📊 Calculate", style=discord.ButtonStyle.primary, row=1)
    async def calculate(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._session.produced:
            await interaction.response.send_message(
                "❌ Add at least one **produced** item before calculating!",
                ephemeral=_eph(interaction),
            )
            return

        await interaction.response.defer(ephemeral=_eph(interaction))

        income = sum(e.price * e.qty for e in self._session.produced)
        cost   = sum(e.price * e.qty for e in self._session.consumed)
        profit = income - cost
        buf    = _render_farm(self._session, income, cost, profit)

        for child in self.children:
            child.disabled = True  
        final_embed = _build_embed(self._session)
        final_embed.set_footer(text="Session complete  •  EscapeItems Shop System")
        await interaction.edit_original_response(embed=final_embed, view=self)

        sign    = "+" if profit >= 0 else "−"
        caption = (
            f"🌾 **Farm Calculator** — requested by {interaction.user.mention}\n"
            f"Net profit: **`{sign}{abs(profit):,.2f} 𐃌/hr`**"
        )

        if buf is None:
            lines = [caption, ""]
            for e in self._session.produced:
                lines.append(f"PRODUCE  {_pretty(e.item_id)} ×{e.qty:,.0f}/hr  → +{e.price*e.qty:,.2f} 𐃌")
            for e in self._session.consumed:
                custom = " (custom)" if e.custom_price else ""
                lines.append(f"CONSUME  {_pretty(e.item_id)} ×{e.qty:,.0f}/hr @ {e.price:.4f} 𐃌{custom}  → −{e.price*e.qty:,.2f} 𐃌")
            lines += ["", f"Income: +{income:,.2f} 𐃌", f"Cost:   −{cost:,.2f} 𐃌",
                      f"**Profit: {sign}{abs(profit):,.2f} 𐃌/hr**"]
            await interaction.followup.send("\n".join(lines), ephemeral=False)
        else:
            await interaction.followup.send(content=caption,
                                            file=discord.File(buf, "farm_calc.png"),
                                            ephemeral=False)


_BG          = (28,  32,  40)
_HEADER_BG   = (18,  21,  28)
_ACCENT      = (88, 101, 242)
_COL_BG      = (40,  45,  55)
_COL_TEXT    = (200, 200, 210)
_ROW_ODD     = (35,  40,  50)
_ROW_EVEN    = (42,  47,  58)
_TEXT_PRI    = (240, 240, 245)
_TEXT_SEC    = (150, 155, 165)
_TITLE_TEXT  = (255, 255, 255)
_BORDER      = (60,  65,  78)
_GREEN_BG    = (56,  161,  90)
_GREEN_TEXT  = (210, 255, 220)
_RED_BG      = (190,  50,  55)
_RED_TEXT    = (255, 215, 215)
_ORANGE_BG   = (190, 110,  20)
_ORANGE_TEXT = (255, 235, 190)
_PROFIT_COL  = ( 80, 220, 120)
_LOSS_COL    = (220,  80,  80)
_FOOTER_TEXT = (100, 105, 120)

_PAD   = 28
_ROW_H = 52
_CH_H  = 40
_HDR_H = 100
_FTR_H = 36
_PH    = 28
_PPX   = 12


def _fnt(bold: bool, size: int):
    bold_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    reg_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in (bold_paths if bold else reg_paths):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _pill(draw, x, y, label, bg, fg, font):
    tw = int(draw.textlength(label, font=font))
    pw = tw + _PPX * 2
    draw.rounded_rectangle([(x, y), (x + pw, y + _PH)], radius=_PH // 2, fill=bg)
    draw.text((x + _PPX, y + (_PH - font.size) // 2 - 1), label, font=font, fill=fg)
    return pw


def _trunc(text, draw, font, max_px):
    if draw.textlength(text, font=font) <= max_px:
        return text
    while text and draw.textlength(text + "…", font=font) > max_px:
        text = text[:-1]
    return text + "…"


def _draw_header(draw, img_w, title, subtitle, f_title, f_sub):
    draw.rectangle([(0, 0), (img_w, _HDR_H)], fill=_HEADER_BG)
    draw.rectangle([(0, _HDR_H - 4), (img_w, _HDR_H)], fill=_ACCENT)
    draw.text((_PAD, 18), title,    font=f_title, fill=_TITLE_TEXT)
    draw.text((_PAD, 56), subtitle, font=f_sub,   fill=_TEXT_SEC)


def _draw_col_headers(draw, img_w, cols, f_ch):
    draw.rectangle([(0, _HDR_H), (img_w, _HDR_H + _CH_H)], fill=_COL_BG)
    for cx, label in cols:
        draw.text((cx, _HDR_H + (_CH_H - f_ch.size) // 2), label, font=f_ch, fill=_COL_TEXT)
    draw.line([(0, _HDR_H + _CH_H - 1), (img_w, _HDR_H + _CH_H - 1)], fill=_BORDER, width=1)


def _render_farm(session: FarmSession, income: float, cost: float, profit: float) -> Optional[io.BytesIO]:
    if not PILLOW_AVAILABLE:
        return None

    f_title = _fnt(True,  24)
    f_sub   = _fnt(False, 15)
    f_ch    = _fnt(True,  14)
    f_pill  = _fnt(True,  12)
    f_body  = _fnt(False, 15)
    f_bb    = _fnt(True,  15)

    C_ROLE  = _PAD
    C_ITEM  = _PAD + 175
    C_QTY   = _PAD + 455
    C_UNIT  = _PAD + 565
    C_TOTAL = _PAD + 705
    IMG_W   = _PAD + 855

    n_data = len(session.produced) + len(session.consumed)
    n_rows = n_data + 1 + 3
    img_h  = _HDR_H + _CH_H + n_rows * _ROW_H + _FTR_H + _PAD

    img  = Image.new("RGB", (IMG_W, img_h), _BG)
    draw = ImageDraw.Draw(img)

    n_prod = len(session.produced)
    n_cons = len(session.consumed)
    _draw_header(draw, IMG_W, "Farm Calculator",
                 f"{n_prod} produced item{'s' if n_prod != 1 else ''}  •  "
                 f"{n_cons} consumed item{'s' if n_cons != 1 else ''}  •  "
                 f"NBT Worth Scanner prices",
                 f_title, f_sub)

    _draw_col_headers(draw, IMG_W, [
        (C_ROLE,  "Role"),
        (C_ITEM,  "Item"),
        (C_QTY,   "Qty / hr"),
        (C_UNIT,  "Unit Price"),
        (C_TOTAL, "Total / hr"),
    ], f_ch)

    row_y = _HDR_H + _CH_H
    ri    = 0

    def _data_row(entry: FarmEntry, role: str):
        nonlocal row_y, ri
        is_prod = role == "produce"
        draw.rectangle([(0, row_y), (IMG_W, row_y + _ROW_H)],
                       fill=_ROW_ODD if ri % 2 == 0 else _ROW_EVEN)
        cy2 = row_y + (_ROW_H - _PH) // 2
        ty2 = row_y + (_ROW_H - f_body.size) // 2

        p_bg, p_fg = (_GREEN_BG, _GREEN_TEXT) if is_prod else (_RED_BG, _RED_TEXT)
        pw = _pill(draw, C_ROLE, cy2, "PRODUCE" if is_prod else "CONSUME", p_bg, p_fg, f_pill)

        if not is_prod and entry.custom_price:
            _pill(draw, C_ROLE + pw + 6, cy2, "CUSTOM", _ORANGE_BG, _ORANGE_TEXT, f_pill)

        draw.text((C_ITEM, ty2),
                  _trunc(_pretty(entry.item_id), draw, f_body, C_QTY - C_ITEM - 14),
                  font=f_body, fill=_TEXT_PRI)
        draw.text((C_QTY,  ty2), f"{entry.qty:,.0f}", font=f_body, fill=_TEXT_PRI)

        if not is_prod and entry.custom_price:
            unit_label = f"{entry.price:.4f} 𐃌  (NBT: {entry.nbt_price:.4f})"
        else:
            unit_label = f"{entry.price:.4f} 𐃌"
        draw.text((C_UNIT, ty2), unit_label, font=f_body, fill=_TEXT_SEC)

        total  = entry.price * entry.qty
        col    = _PROFIT_COL if is_prod else _LOSS_COL
        prefix = "+" if is_prod else "−"
        draw.text((C_TOTAL, ty2), f"{prefix}{total:,.2f} 𐃌", font=f_bb, fill=col)
        draw.line([(0, row_y + _ROW_H - 1), (IMG_W, row_y + _ROW_H - 1)], fill=_BORDER)
        row_y += _ROW_H
        ri    += 1

    for e in session.produced:
        _data_row(e, "produce")
    for e in session.consumed:
        _data_row(e, "consume")

    draw.rectangle([(0, row_y), (IMG_W, row_y + _ROW_H)], fill=_COL_BG)
    draw.text((_PAD, row_y + (_ROW_H - f_ch.size) // 2),
              "─── Summary ─────────────────────────────────────────────",
              font=f_ch, fill=_COL_TEXT)
    row_y += _ROW_H

    def _summary_row(label, value_str, color):
        nonlocal row_y, ri
        draw.rectangle([(0, row_y), (IMG_W, row_y + _ROW_H)],
                       fill=_ROW_ODD if ri % 2 == 0 else _ROW_EVEN)
        ty3 = row_y + (_ROW_H - f_body.size) // 2
        draw.text((C_ITEM,  ty3), label,     font=f_body, fill=_TEXT_SEC)
        draw.text((C_TOTAL, ty3), value_str, font=f_bb,   fill=color)
        draw.line([(0, row_y + _ROW_H - 1), (IMG_W, row_y + _ROW_H - 1)], fill=_BORDER)
        row_y += _ROW_H
        ri    += 1

    _summary_row("Total Income / hr", f"+{income:,.2f} 𐃌",  _PROFIT_COL)
    _summary_row("Total Cost / hr",   f"−{cost:,.2f} 𐃌",    _LOSS_COL)
    profit_col = _PROFIT_COL if profit >= 0 else _LOSS_COL
    prefix     = "+" if profit >= 0 else "−"
    _summary_row("Net Profit / hr", f"{prefix}{abs(profit):,.2f} 𐃌", profit_col)

    draw.text((_PAD, row_y + 10),
              "EscapeItems Shop System  •  Prices from NBT Worth Scanner",
              font=f_sub, fill=_FOOTER_TEXT)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _render_price_list_pages() -> list[io.BytesIO]:
    if not PILLOW_AVAILABLE:
        return []

    sorted_items = sorted(_RAW_PRICES.items(), key=lambda kv: kv[1], reverse=True)
    total        = len(sorted_items)

    pages = [
        sorted_items[i : i + _ITEMS_PER_PAGE]
        for i in range(0, total, _ITEMS_PER_PAGE)
    ]
    n_pages = len(pages)

    f_title  = _fnt(True,  24)
    f_sub    = _fnt(False, 15)
    f_ch     = _fnt(True,  13)
    f_body   = _fnt(False, 14)
    f_bb     = _fnt(True,  14)

    COLS   = 2
    COL_W  = 400
    RANK_W = 40
    NAME_W = 220
    IMG_W  = _PAD * 2 + COLS * COL_W
    ROW_H_SM = 34

    buffers: list[io.BytesIO] = []

    for page_idx, page_items in enumerate(pages):
        n            = len(page_items)
        rows_per_col = math.ceil(n / COLS)
        img_h        = _HDR_H + _CH_H + rows_per_col * ROW_H_SM + _FTR_H + _PAD

        img  = Image.new("RGB", (IMG_W, img_h), _BG)
        draw = ImageDraw.Draw(img)

        rank_offset = page_idx * _ITEMS_PER_PAGE

        subtitle = (
            f"Page {page_idx + 1}/{n_pages}  •  "
            f"Items #{rank_offset + 1}–{rank_offset + n} of {total}  •  "
            f"sorted highest to lowest  •  NBT Worth Scanner"
        )
        _draw_header(draw, IMG_W, "Item Price List", subtitle, f_title, f_sub)

        draw.rectangle([(0, _HDR_H), (IMG_W, _HDR_H + _CH_H)], fill=_COL_BG)
        for c in range(COLS):
            base = _PAD + c * COL_W
            draw.text((base,             _HDR_H + (_CH_H - f_ch.size) // 2), "#",     font=f_ch, fill=_COL_TEXT)
            draw.text((base + RANK_W,    _HDR_H + (_CH_H - f_ch.size) // 2), "Item",  font=f_ch, fill=_COL_TEXT)
            draw.text((base + RANK_W + NAME_W, _HDR_H + (_CH_H - f_ch.size) // 2), "Price", font=f_ch, fill=_COL_TEXT)
        draw.line([(0, _HDR_H + _CH_H - 1), (IMG_W, _HDR_H + _CH_H - 1)], fill=_BORDER, width=1)

        top_threshold    = sorted_items[max(0, int(total * 0.10))][1]
        bottom_threshold = sorted_items[min(total - 1, int(total * 0.90))][1]

        for local_idx, (item_id, price) in enumerate(page_items):
            global_idx = rank_offset + local_idx
            col        = local_idx // rows_per_col
            row        = local_idx % rows_per_col
            base_x     = _PAD + col * COL_W
            row_y      = _HDR_H + _CH_H + row * ROW_H_SM

            bg = _ROW_ODD if row % 2 == 0 else _ROW_EVEN
            draw.rectangle([(base_x - 4, row_y), (base_x + COL_W - 4, row_y + ROW_H_SM)], fill=bg)

            ty = row_y + (ROW_H_SM - f_body.size) // 2
            draw.text((base_x, ty), str(global_idx + 1), font=f_body, fill=_TEXT_SEC)

            name = _trunc(_pretty(item_id), draw, f_body, NAME_W - 8)
            draw.text((base_x + RANK_W, ty), name, font=f_body, fill=_TEXT_PRI)

            if price >= top_threshold:
                price_col = _PROFIT_COL
            elif price <= bottom_threshold:
                price_col = (160, 160, 170)
            else:
                price_col = _TEXT_PRI

            draw.text((base_x + RANK_W + NAME_W, ty), f"{price:.2f} 𐃌", font=f_bb, fill=price_col)
            draw.line(
                [(base_x - 4, row_y + ROW_H_SM - 1), (base_x + COL_W - 4, row_y + ROW_H_SM - 1)],
                fill=_BORDER, width=1,
            )

        footer_y = _HDR_H + _CH_H + rows_per_col * ROW_H_SM + 10
        draw.text((_PAD, footer_y),
                  "EscapeItems Shop System  •  Prices from NBT Worth Scanner",
                  font=f_sub, fill=_FOOTER_TEXT)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        buffers.append(buf)

    return buffers


class FarmCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="farmcalc",
        description="Calculate how much 𐃌 your farm earns per hour",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def farmcalc(self, interaction: discord.Interaction):
        session = FarmSession()
        view    = FarmView(session=session, owner_id=interaction.user.id)
        embed   = _build_embed(session)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=_eph(interaction))

    @app_commands.command(
        name="farmprices",
        description="Look up an item price, or leave blank to see all items sorted best → worst",
    )
    @app_commands.describe(item="Minecraft item ID (e.g. minecraft:wheat) — leave blank for full list")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def farmprices(self, interaction: discord.Interaction, item: Optional[str] = None):

        if not item or not item.strip():
            await interaction.response.defer(ephemeral=_eph(interaction))

            pages = _render_price_list_pages()

            if not pages:
                sorted_items = sorted(_RAW_PRICES.items(), key=lambda kv: kv[1], reverse=True)
                lines = ["**Full Item Price List (top 30 shown — install Pillow for the full image)**", ""]
                for idx, (iid, p) in enumerate(sorted_items[:30], 1):
                    lines.append(f"`{idx:3}.` {_pretty(iid):<35} {p:.2f} 𐃌")
                await interaction.followup.send("\n".join(lines), ephemeral=_eph(interaction))
                return

            total_items = len(_RAW_PRICES)
            n_pages     = len(pages)

            BATCH = 10
            first = True
            for batch_start in range(0, n_pages, BATCH):
                batch = pages[batch_start : batch_start + BATCH]
                files = [
                    discord.File(buf, filename=f"price_list_p{batch_start + i + 1}.png")
                    for i, buf in enumerate(batch)
                ]
                caption = (
                    f"💰 **All {total_items} item prices — sorted highest to lowest "
                    f"({n_pages} image{'s' if n_pages > 1 else ''}, {_ITEMS_PER_PAGE} items each):**"
                    if first else ""
                )
                await interaction.followup.send(
                    content=caption or None,
                    files=files,
                    ephemeral=_eph(interaction),
                )
                first = False
            return

        item_id, price = _lookup(item)
        if item_id is None:
            await interaction.response.send_message(
                f"❌ `{item}` was not found in the NBT Worth Scanner price list.\n"
                f"Use the full Minecraft ID, e.g. `minecraft:wheat`, "
                f"or leave the field blank to see all items.",
                ephemeral=_eph(interaction),
            )
            return

        sorted_prices = sorted(_RAW_PRICES.values(), reverse=True)
        rank = sorted_prices.index(price) + 1

        await interaction.response.send_message(
            f"💰 **{_pretty(item_id)}** (`minecraft:{item_id}`)\n"
            f"Worth **{price} 𐃌** each  •  Rank **#{rank}** of {len(_RAW_PRICES)} items",
            ephemeral=_eph(interaction),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FarmCog(bot))
