from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from database import items as items_db
from database import users as users_db
from utils.formatting import build_item_embed
from views.item_views import CategoryView, ItemSelectionView
from utils.security import secure_check


def _match_confidence(query: str, result_name: str) -> int:
    q = query.lower().strip()
    r = result_name.lower().strip()
    if r == q:
        return 99
    if r.startswith(q):
        return 90
    if q in r:
        return 75
    return 65


class ItemsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="item",
                          description="Look up an item from the database")
    @app_commands.describe(name="The name of the item to look up")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def item_command(
        self, interaction: discord.Interaction, name: Optional[str] = None
    ):
        await users_db.track_user(interaction.user.id, interaction.user.name)
        if not await secure_check(interaction, name):
            return

        if not name:
            await interaction.response.send_message(
                "Please select a category:", view=CategoryView(), ephemeral=True
            )
            return

        await interaction.response.defer()

        item = await items_db.get_item(name)
        if item:
            await interaction.followup.send(
                embed=build_item_embed(item, interaction.user.name)
            )
            return

        similar = await items_db.search_similar_items(name)
        if not similar:
            await interaction.followup.send(
                f"No items found matching **{name}**.\n"
                "Try `/item` without a name to browse categories."
            )
            return

        if len(similar) == 1:
            item = await items_db.get_item(similar[0]["name"])
            if item:
                pct = _match_confidence(name, similar[0]["name"])
                embed = build_item_embed(item, interaction.user.name)
                embed.set_footer(
                    text=f"[{pct}% likely you meant this]  •  Requested by {interaction.user.name}"
                )
                await interaction.followup.send(embed=embed)
                return

        embed = discord.Embed(
            title="Multiple items found",
            description=f"No exact match for **{name}**. Please select from the list below:",
            color=discord.Color.orange(),
        )
        preview = "\n".join(
            f"• **{i['name']}** ({i['category']})" for i in similar[:10]
        )
        embed.add_field(name="Matching items:", value=preview, inline=False)
        if len(similar) > 10:
            embed.set_footer(text=f"Showing 10 of {len(similar)} matches")

        await interaction.followup.send(
            embed=embed, view=ItemSelectionView(similar, interaction.user)
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ItemsCog(bot))