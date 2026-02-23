from __future__ import annotations

from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from database import items as items_db
from database import users as users_db
from utils.checks import require_admin
from utils.security import secure_check
from utils.renderer import render_item_data_sheet


class AddItemModal(discord.ui.Modal, title="Add Item"):
    name         = discord.ui.TextInput(label="Name")
    category     = discord.ui.TextInput(label="Category")
    info         = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph)
    image        = discord.ui.TextInput(label="Image URL",   required=False)
    location     = discord.ui.TextInput(label="Location",    required=False)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.name.value.strip()
        if await items_db.get_item(name):
            await interaction.response.send_message(
                f"Item **{name}** already exists. Use `/admin` → `modify-item` to update it.",
                ephemeral=True,
            )
            return
        try:
            await items_db.add_item(
                name, self.image.value or "", self.location.value or "",
                self.info.value, "", False, self.category.value,
            )
            embed = discord.Embed(
                title="Item Added",
                description=f"**{name}** added to the database.",
                color=discord.Color.green(),
            )
            embed.add_field(name="Category", value=self.category.value, inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as exc:
            await interaction.response.send_message(f"Error: {exc}", ephemeral=True)


class ModifyItemModal(discord.ui.Modal, title="Modify Item"):
    name     = discord.ui.TextInput(label="Item name (exact)")
    new_name = discord.ui.TextInput(label="New name",        required=False)
    category = discord.ui.TextInput(label="New category",    required=False)
    info     = discord.ui.TextInput(label="New description",
                                    style=discord.TextStyle.paragraph, required=False)
    location = discord.ui.TextInput(label="New location",    required=False)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.name.value.strip()
        if not await items_db.get_item(name):
            await interaction.response.send_message(f"Item **{name}** not found.", ephemeral=True)
            return

        updates = {k: v for k, v in {
            "name":          self.new_name.value or None,
            "item_category": self.category.value or None,
            "info":          self.info.value      or None,
            "location":      self.location.value or None,
        }.items() if v}

        if not updates:
            await interaction.response.send_message("No fields provided to update.", ephemeral=True)
            return

        item = await items_db.get_item(name)
        if item:
            buf = await asyncio.get_event_loop().run_in_executor(
                None, partial(render_item_data_sheet, item)
            )
            if buf:
                await interaction.followup.send(file=discord.File(buf, "item_data.png"), ephemeral=True)


class RemoveItemModal(discord.ui.Modal, title="Remove Item"):
    name = discord.ui.TextInput(label="Item name (exact)")

    async def on_submit(self, interaction: discord.Interaction):
        name = self.name.value.strip()
        if await items_db.remove_item(name):
            await interaction.response.send_message(f"**{name}** removed.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Item **{name}** not found.", ephemeral=True)


class AnnounceModal(discord.ui.Modal, title="Send Announcement"):
    message = discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph, max_length=2000)

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        users = await users_db.get_all_user_ids()
        if not users:
            await interaction.followup.send("No users to announce to.", ephemeral=True)
            return

        embed = discord.Embed(title="EscapeItems Announcement",
                              description=self.message.value, color=discord.Color.blue())
        embed.set_footer(text="EscapeItems Bot")

        sent = failed = 0
        for uid in users:
            try:
                user = await self.bot.fetch_user(uid)
                await user.send(embed=embed)
                sent += 1
            except Exception:
                failed += 1

        result = discord.Embed(title="Announcement Results", color=discord.Color.green())
        result.add_field(name="Sent",   value=str(sent),       inline=True)
        result.add_field(name="Failed", value=str(failed),     inline=True)
        result.add_field(name="Total",  value=str(len(users)), inline=True)
        await interaction.followup.send(embed=result, ephemeral=True)


Action = Literal[
    "add-item", "remove-item", "modify-item",
    "add-admin", "remove-admin", "list-admins",
    "announce", "stats",
]


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="admin", description="Admin panel")
    @app_commands.describe(action="What do you want to do?")
    async def admin(self, interaction: discord.Interaction, action: Action,
                    user: Optional[discord.User] = None,
                    number: Optional[int] = None):
        if not await require_admin(interaction):
            return

        if action == "add-item":
            return await interaction.response.send_modal(AddItemModal())

        if action == "remove-item":
            return await interaction.response.send_modal(RemoveItemModal())

        if action == "modify-item":
            return await interaction.response.send_modal(ModifyItemModal())

        if action == "announce":
            return await interaction.response.send_modal(AnnounceModal(self.bot))

        await interaction.response.defer(ephemeral=True)

        if action == "add-admin":
            if not user:
                return await interaction.followup.send("Provide `user`.", ephemeral=True)
            await users_db.add_admin(user.id, interaction.user.id)
            return await interaction.followup.send(f"**{user.name}** added as admin.", ephemeral=True)

        if action == "remove-admin":
            if not user:
                return await interaction.followup.send("Provide `user`.", ephemeral=True)
            if user.id == interaction.user.id:
                return await interaction.followup.send("Cannot remove yourself.", ephemeral=True)
            from config import ADMIN_IDS
            if user.id in ADMIN_IDS:
                return await interaction.followup.send(
                    "Cannot remove base admins defined in .env.", ephemeral=True)
            await users_db.remove_admin(user.id)
            return await interaction.followup.send(
                f"**{user.name}** removed from admin list.", ephemeral=True)

        if action == "list-admins":
            admins = await users_db.get_all_admins()
            from config import ADMIN_IDS
            lines = []
            for aid in admins:
                try:
                    u   = await self.bot.fetch_user(aid)
                    src = "ENV" if aid in ADMIN_IDS else "DB"
                    lines.append(f"• {u.name} (ID: {aid}) [{src}]")
                except Exception:
                    lines.append(f"• Unknown (ID: {aid})")
            embed = discord.Embed(title="Admin Users",
                                  description="\n".join(lines) or "None",
                                  color=discord.Color.gold())
            embed.set_footer(text=f"Total: {len(admins)}")
            return await interaction.followup.send(embed=embed, ephemeral=True)

        if action == "stats":
            from utils.formatting import format_uptime
            cog   = self.bot.get_cog("UtilityCog")
            start = cog.bot_start_time if cog else None
            embed = discord.Embed(title="Bot Statistics", color=discord.Color.blue())
            embed.add_field(name="Tracked Users", value=str(len(await users_db.get_all_user_ids())), inline=True)
            embed.add_field(name="Servers",       value=str(len(self.bot.guilds)),                   inline=True)
            embed.add_field(name="Admins",        value=str(len(await users_db.get_all_admins())),   inline=True)
            embed.add_field(name="Total Items",   value=str(await items_db.get_total_item_count()),  inline=True)
            embed.add_field(name="Categories",    value=str(await items_db.get_category_count()),    inline=True)
            embed.add_field(name="Uptime",        value=format_uptime(start),                        inline=True)
            return await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
