from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import TOS_TEXT, PRIVACY_TEXT
from database import items as items_db
from database import users as users_db
from utils.formatting import split_message, format_uptime


class UtilityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot_start_time: datetime | None = None
        self._cached_item_count: int = 0
        self._cached_cat_count: int = 0
        self._status_index: int = 0

    def cog_load(self):
        self.bot_start_time = datetime.now(timezone.utc)
        self.status_loop.start()

    def cog_unload(self):
        self.status_loop.cancel()

    @tasks.loop(seconds=30)
    async def status_loop(self):
        if not self.bot.is_ready() or not self.bot.ws:
            return

        if self.status_loop.current_loop % 2 == 0:
            try:
                self._cached_item_count = await items_db.get_total_item_count()
                self._cached_cat_count  = await items_db.get_category_count()
            except Exception:
                pass

        statuses = [
            f"Uptime: {format_uptime(self.bot_start_time)}",
            f"{self._cached_item_count} items in {self._cached_cat_count} categories",
            f"Used by {len(self.bot.guilds)} server(s)",
            "Also available as a user-installed app",
            "/farmcalc — calculate your farm profits",
            "/item — look up any special item",
        ]

        text = statuses[self._status_index % len(statuses)]
        self._status_index += 1

        try:
            if self.bot.ws and not self.bot.ws.socket.closed:
                await self.bot.change_presence(
                    status=discord.Status.dnd,
                    activity=discord.Game(name=text),
                )
        except Exception as exc:
            print(f"Status update error: {exc}")

    @status_loop.before_loop
    async def before_status(self):
        await self.bot.wait_until_ready()
        try:
            self._cached_item_count = await items_db.get_total_item_count()
            self._cached_cat_count  = await items_db.get_category_count()
        except Exception:
            pass

    @app_commands.command(
        name="escapeitems-tos",
        description="View the Terms of Service for EscapeItems",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def tos_command(self, interaction: discord.Interaction):
        await users_db.track_user(interaction.user.id, interaction.user.name)
        await self._send_dm(interaction, TOS_TEXT, "Terms of Service")

    @app_commands.command(
        name="escapeitems-privacy",
        description="View the Privacy Policy for EscapeItems",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def privacy_command(self, interaction: discord.Interaction):
        await users_db.track_user(interaction.user.id, interaction.user.name)
        await self._send_dm(interaction, PRIVACY_TEXT, "Privacy Policy")

    async def _send_dm(
        self, interaction: discord.Interaction, text: str, label: str
    ):
        try:
            for chunk in split_message(text):
                await interaction.user.send(chunk)
            await interaction.response.send_message(
                f"{label} sent to your DMs!", ephemeral=True
            )
        except discord.Forbidden:
            chunks = split_message(text, max_length=1900)
            if len(chunks) == 1:
                await interaction.response.send_message(
                    f"Could not DM you. Here it is:\n\n{chunks[0]}", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "Could not send DM. Please enable DMs from server members.",
                    ephemeral=True,
                )
        except Exception as exc:
            await interaction.response.send_message(
                f"An error occurred: {exc}", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCog(bot))
