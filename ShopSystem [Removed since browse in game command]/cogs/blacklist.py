from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from database import shops as shops_db
from utils.checks import require_admin
from utils.security import secure_check


class BlacklistCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    blacklist = app_commands.Group(
        name="blacklist",
        description="Manage shop blacklists",
    )

    @blacklist.command(name="add", description="[ADMIN] Blacklist a user from a shop or all shop commands")
    @app_commands.describe(
        user="User to blacklist",
        shop_number="Specific shop — omit to ban globally",
        reason="Reason (used for global bans)",
    )
    async def blacklist_add(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        shop_number: Optional[int] = None,
        reason: Optional[str] = None,
    ):
        if not await require_admin(interaction):
            return
        if not await secure_check(interaction, reason):
            return

        if shop_number is not None:
            shop = await shops_db.get_shop(shop_number)
            if not shop:
                await interaction.response.send_message(
                    f"Shop #{shop_number} not found.", ephemeral=True
                )
                return
            await shops_db.add_shop_blacklist(shop_number, user.id)
            await interaction.response.send_message(
                f"**{user.name}** blacklisted from shop #{shop_number}.", ephemeral=True
            )
        else:
            await shops_db.add_global_blacklist(user.id, reason or "")
            await interaction.response.send_message(
                f"**{user.name}** globally banned from all shop commands.", ephemeral=True
            )

    @blacklist.command(name="remove", description="[ADMIN] Remove a blacklist from a shop or globally")
    @app_commands.describe(
        user="User to unblacklist",
        shop_number="Specific shop — omit to restore globally",
    )
    async def blacklist_remove(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        shop_number: Optional[int] = None,
    ):
        if not await require_admin(interaction):
            return

        if shop_number is not None:
            await shops_db.remove_shop_blacklist(shop_number, user.id)
            await interaction.response.send_message(
                f"**{user.name}** unblacklisted from shop #{shop_number}.", ephemeral=True
            )
        else:
            await shops_db.remove_global_blacklist(user.id)
            await interaction.response.send_message(
                f"**{user.name}**'s global shop ban removed.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(BlacklistCog(bot))
