from __future__ import annotations

import io
from typing import List

import discord

from database import items as items_db
from utils.formatting import build_item_embed
from utils.renderer import render_items_list
from config import ITEM_CATEGORIES
import asyncio
from functools import partial
from utils.renderer import render_item_panel

class CategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=cat, value=cat)
            for cat in ITEM_CATEGORIES
        ]
        super().__init__(
            placeholder="Select a category...",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        items = await items_db.get_items_by_category(category)
        if not items:
            await interaction.response.send_message(
                f"No items found in **{category}**", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        buf = render_items_list(
            title=f"{category} Items",
            subtitle=f"{len(items)} item(s) in this category",
            items=[{"name": it} if isinstance(it, str) else it for it in items],
        )
        if buf:
            embed = discord.Embed(
                title=f"{category} — Item List",
                color=discord.Color.blue(),
            )
            embed.set_image(url="attachment://items_list.png")
            embed.set_footer(
                text=f"{len(items)} item(s)  •  Requested by {interaction.user.name}"
            )
            await interaction.followup.send(
                embed=embed,
                file=discord.File(buf, filename="items_list.png"),
                ephemeral=True,
            )
        else:
            chunks = [items[i : i + 25] for i in range(0, len(items), 25)]
            embed = discord.Embed(
                title=f"{category} Items",
                description="\n".join(
                    f"• {it if isinstance(it, str) else it['name']}"
                    for it in chunks[0]
                ),
                color=discord.Color.blue(),
            )
            embed.set_footer(
                text=f"Showing {len(chunks[0])} of {len(items)} items"
                f"  •  Requested by {interaction.user.name}"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


class CategoryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(CategorySelect())

class ItemSelectionSelect(discord.ui.Select):
    def __init__(self, items: List[dict], original_user: discord.User):
        self.original_user = original_user
        options = [
            discord.SelectOption(
                label=item["name"][:100],
                value=item["name"],
                description=f"Category: {item['category']}"[:100],
            )
            for item in items[:25]
        ]
        super().__init__(
            placeholder="Select the item you meant...",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.original_user.id:
            await interaction.response.send_message(
                "This selection menu is not for you.", ephemeral=True
            )
            return

        item = await items_db.get_item(self.values[0])
        if not item:
            await interaction.response.send_message(
                f"Error loading item **{self.values[0]}**", ephemeral=True
            )
            return

        for child in self.view.children:
            child.disabled = True
        self.view.stop()

        await interaction.response.edit_message(
            content="Item selected:", view=self.view
        )

        buf = render_items_list(
            title=item["name"],
            subtitle=f"Category: {item.get('category', 'Unknown')}",
            items=[item],
            detail_mode=True,
        )
        buf = await asyncio.get_event_loop().run_in_executor(None, partial(render_item_panel, item))
        if buf:
            await interaction.followup.send(file=discord.File(buf, "item.png"))
        else:
            await interaction.followup.send(embed=build_item_embed(item, interaction.user.name))




class ItemSelectionView(discord.ui.View):
    def __init__(self, items: List[dict], original_user: discord.User):
        super().__init__(timeout=60)
        self.add_item(ItemSelectionSelect(items, original_user))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
