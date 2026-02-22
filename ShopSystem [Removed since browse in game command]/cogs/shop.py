from __future__ import annotations

import io
import math
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from database import shops as shops_db
from database import users as users_db
from utils.checks import require_not_globally_blacklisted, require_shop_owner
from utils.formatting import format_shop_item_row
from utils.renderer import render_shop_items, render_shops_list, render_item_search
from utils.map_renderer import render_shop_map
from utils.security import secure_check
from views.shop_views import BrowsePaginatorView, ShopItemsView


class CreateShopModal(discord.ui.Modal, title="Create Shop"):
    shop_name = discord.ui.TextInput(label="Shop name")
    plot_x    = discord.ui.TextInput(label="Plot X coordinate")
    plot_z    = discord.ui.TextInput(label="Plot Z coordinate")

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            x = int(self.plot_x.value.strip())
            z = int(self.plot_z.value.strip())
        except ValueError:
            await interaction.response.send_message(
                "X and Z must be numbers.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        if not await secure_check(interaction, self.shop_name.value, deferred=True):
            return

        current = await shops_db.get_shop_count(interaction.user.id)
        maximum = await shops_db.get_max_shops(interaction.user.id)
        if current >= maximum:
            await interaction.followup.send(
                f"You've reached your shop limit ({maximum}). "
                "Ask an admin to grant more slots with `/admin` → `add-slots`.",
                ephemeral=True,
            )
            return

        try:
            await shops_db.create_shop(interaction.user.id, self.shop_name.value, x, z)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        except Exception as exc:
            await interaction.followup.send(f"Error creating shop: {exc}", ephemeral=True)
            return

        next_slot = current + 1
        embed = discord.Embed(
            title="Shop Created",
            description=f"**{self.shop_name.value}** is now open!",
            color=discord.Color.green(),
        )
        embed.add_field(name="Location",    value=f"X={x}, Z={z}", inline=True)
        embed.add_field(name="Slot",        value=f"#{next_slot}",  inline=True)
        embed.add_field(name="Your Shops",  value=f"{next_slot}/{maximum}", inline=True)
        embed.set_footer(
            text=f"Use /shop action:items shop_number:{next_slot} to add listings"
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


Action = Literal[
    "create", "list", "items", "map",
    "blacklist-add", "blacklist-remove",
    "delete",
]


class ShopCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="shop", description="Manage your shops")
    @app_commands.describe(
        action="What do you want to do?",
        shop_number="Your shop slot number (use list to check)",
        user="User (required for blacklist actions)",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def shop(
        self,
        interaction: discord.Interaction,
        action: Action,
        shop_number: Optional[int] = None,
        user: Optional[discord.User] = None,
    ):
        await users_db.track_user(interaction.user.id, interaction.user.name)
        if not await require_not_globally_blacklisted(interaction):
            return

        if action == "create":
            return await interaction.response.send_modal(CreateShopModal(self.bot))

        await interaction.response.defer(ephemeral=True)

        if action == "list":
            return await self._list(interaction)
        if action == "items":
            if shop_number is None:
                return await interaction.followup.send(
                    "Provide `shop_number` (use `list` to check yours).", ephemeral=True
                )
            return await self._items(interaction, shop_number)
        if action == "map":
            if shop_number is None:
                return await interaction.followup.send(
                    "Provide `shop_number`.", ephemeral=True
                )
            return await self._shop_map(interaction, shop_number)
        if action in ("blacklist-add", "blacklist-remove"):
            if user is None:
                return await interaction.followup.send(
                    "Provide `user` for blacklist actions.", ephemeral=True
                )
            return await self._blacklist(interaction, action, user, shop_number)
        if action == "delete":
            if shop_number is None:
                return await interaction.followup.send(
                    "Provide `shop_number`.", ephemeral=True
                )
            return await self._delete(interaction, shop_number)

    async def _resolve_shop(
        self, interaction: discord.Interaction, shop_number: int
    ) -> dict | None:
        shop = await shops_db.get_shop_by_position(interaction.user.id, shop_number)
        if not shop:
            await interaction.followup.send(
                f"You don't have a shop in slot #{shop_number}. "
                "Use `/shop action:list` to see your shops.",
                ephemeral=True,
            )
        return shop

    async def _resolve_owner_name(self, owner_id: int) -> str:
        try:
            owner = await self.bot.fetch_user(owner_id)
            return owner.name
        except Exception:
            return f"User {owner_id}"

    async def _list(self, interaction: discord.Interaction):
        owned   = await shops_db.get_shops_by_owner(interaction.user.id)
        maximum = await shops_db.get_max_shops(interaction.user.id)

        if not owned:
            return await interaction.followup.send(
                "You don't own any shops yet. Use `/shop action:create` to make one.",
                ephemeral=True,
            )

        shop_rows = []
        for shop in owned:
            item_count = await shops_db.count_shop_items(shop["id"])
            shop_rows.append({
                "shop_id":       shop["id"],
                "position":      shop.get("position", shop["id"]),
                "shop_name":     shop["shop_name"],
                "owner_name":    interaction.user.name,
                "plot_x":        shop["plot_x"],
                "plot_z":        shop["plot_z"],
                "item_count":    item_count,
                "is_advertised": shop.get("is_promoted", False),
            })

        buf = render_shops_list(shop_rows)
        if buf:
            await interaction.followup.send(
                file=discord.File(buf, filename="shops_list.png"),
                ephemeral=True,
            )
        else:
            embed = discord.Embed(
                title="Your Shops",
                description=f"Using {len(owned)}/{maximum} shop slot(s)",
                color=discord.Color.blue(),
            )
            for shop in owned:
                item_count = await shops_db.count_shop_items(shop["id"])
                promo = " *(advertised)*" if shop.get("is_promoted") else ""
                embed.add_field(
                    name=f"Slot {shop['position']} — {shop['shop_name']}{promo}",
                    value=f"X={shop['plot_x']}, Z={shop['plot_z']} | {item_count} listing(s)",
                    inline=False,
                )
            await interaction.followup.send(embed=embed, ephemeral=True)

    async def _items(self, interaction: discord.Interaction, shop_number: int):
        shop = await self._resolve_shop(interaction, shop_number)
        if not shop:
            return

        is_owner  = shop["owner_id"] == interaction.user.id
        is_admin_ = await users_db.is_admin(interaction.user.id)

        if not is_owner and not is_admin_:
            if await shops_db.is_shop_blacklisted(shop["id"], interaction.user.id):
                return await interaction.followup.send(
                    "You are not allowed to view this shop.", ephemeral=True
                )

        items      = await shops_db.get_shop_items(
            shop["id"], include_drafts=is_owner or is_admin_
        )
        owner_name = await self._resolve_owner_name(shop["owner_id"])
        view       = ShopItemsView(shop, items, interaction.user, owner_name=owner_name)
        await view.send(interaction)

    async def _shop_map(self, interaction: discord.Interaction, shop_number: int):
        shop = await self._resolve_shop(interaction, shop_number)
        if not shop:
            return

        if await shops_db.is_shop_blacklisted(shop["id"], interaction.user.id):
            return await interaction.followup.send(
                "You are not allowed to view this shop.", ephemeral=True
            )

        owner_name = await self._resolve_owner_name(shop["owner_id"])

        shop_row = [{
            "shop_name":     shop["shop_name"],
            "plot_x":        shop["plot_x"],
            "plot_z":        shop["plot_z"],
            "is_advertised": shop.get("is_promoted", False),
        }]

        try:
            buf = await render_shop_map(shop_row, radius=200)
        except Exception as exc:
            return await interaction.followup.send(
                f"Failed to render map: `{exc}`", ephemeral=True
            )

        if buf is None:
            return await interaction.followup.send(
                f"Could not load map tiles for **{shop['shop_name']}**.\n"
                f"Location: X=`{shop['plot_x']}`, Z=`{shop['plot_z']}`\n"
                "Use `/maptest` to diagnose tile fetching.",
                ephemeral=True,
            )

        embed = discord.Embed(
            title=f"{shop['shop_name']} — Map",
            description=(
                f"Owner: {owner_name}  |  X=`{shop['plot_x']}`, Z=`{shop['plot_z']}`\n"
                f"[View on full map](https://map.escape.systems/?world=minecraft_overworld"
                f"#minecraft_overworld:{shop['plot_x']}:64:{shop['plot_z']}:100)"
            ),
            color=discord.Color.blue(),
        )
        embed.set_image(url="attachment://shop_map.png")
        await interaction.followup.send(
            embed=embed,
            file=discord.File(buf, filename="shop_map.png"),
            ephemeral=True,
        )

    async def _blacklist(
        self,
        interaction: discord.Interaction,
        action: str,
        user: discord.User,
        shop_number: Optional[int],
    ):
        if shop_number is None:
            owned = await shops_db.get_shops_by_owner(interaction.user.id)
            if not owned:
                return await interaction.followup.send(
                    "You don't own any shops.", ephemeral=True
                )
            if len(owned) > 1:
                return await interaction.followup.send(
                    "You own multiple shops — provide `shop_number`.", ephemeral=True
                )
            shop = owned[0]
        else:
            shop = await self._resolve_shop(interaction, shop_number)
            if not shop:
                return

        if not await require_shop_owner(interaction, shop):
            return

        if action == "blacklist-add":
            await shops_db.add_shop_blacklist(shop["id"], user.id)
            await interaction.followup.send(
                f"**{user.name}** blacklisted from **{shop['shop_name']}**.", ephemeral=True
            )
        else:
            await shops_db.remove_shop_blacklist(shop["id"], user.id)
            await interaction.followup.send(
                f"**{user.name}** removed from **{shop['shop_name']}**'s blacklist.",
                ephemeral=True,
            )

    async def _delete(self, interaction: discord.Interaction, shop_number: int):
        shop = await self._resolve_shop(interaction, shop_number)
        if not shop:
            return
        if not await require_shop_owner(interaction, shop):
            return
        await shops_db.delete_shop(shop["id"])
        await interaction.followup.send(
            f"Shop **{shop['shop_name']}** (slot #{shop_number}) deleted. "
            "Remaining shops have been renumbered.",
            ephemeral=True,
        )

    @app_commands.command(
        name="browse",
        description="Browse shops or search for items across all shops",
    )
    @app_commands.describe(
        mode="What to browse: shops, shop, or item",
        shop_number="Shop ID (used with mode=shop)",
        item_name="Item name to search (used with mode=item)",
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="shops — list all shops", value="shops"),
        app_commands.Choice(name="shop — view one shop",   value="shop"),
        app_commands.Choice(name="item — search for item", value="item"),
    ])
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def browse(
        self,
        interaction: discord.Interaction,
        mode: str,
        shop_number: Optional[int] = None,
        item_name: Optional[str] = None,
    ):
        await users_db.track_user(interaction.user.id, interaction.user.name)
        if not await secure_check(interaction, item_name, deferred=True):
            return
        if not await require_not_globally_blacklisted(interaction):
            return

        await interaction.response.defer()

        if mode == "shops":
            await self._browse_shops(interaction)
        elif mode == "shop":
            if shop_number is None:
                return await interaction.followup.send(
                    "Provide `shop_number` when using mode=shop.", ephemeral=True
                )
            await self._browse_shop(interaction, shop_number)
        elif mode == "item":
            if not item_name:
                return await interaction.followup.send(
                    "Provide `item_name` when using mode=item.", ephemeral=True
                )
            await self._browse_item(interaction, item_name)

    async def _browse_shops(self, interaction: discord.Interaction):
        all_shops = await shops_db.get_all_shops()
        if not all_shops:
            return await interaction.followup.send("No shops registered yet.")

        shop_rows = []
        for shop in all_shops:
            owner_name = await self._resolve_owner_name(shop["owner_id"])
            item_count = await shops_db.count_shop_items(shop["id"])
            shop_rows.append({
                "shop_id":       shop["id"],
                "position":      shop.get("position", shop["id"]),
                "shop_name":     shop["shop_name"],
                "owner_name":    owner_name,
                "plot_x":        shop["plot_x"],
                "plot_z":        shop["plot_z"],
                "item_count":    item_count,
                "is_advertised": shop.get("is_promoted", False),
            })

        buf = render_shops_list(shop_rows)
        if buf:
            await interaction.followup.send(
                file=discord.File(buf, filename="shops_list.png"),
            )
        else:
            per_page = 8
            pages    = math.ceil(len(shop_rows) / per_page)
            embeds   = []
            for p in range(pages):
                chunk = shop_rows[p * per_page:(p + 1) * per_page]
                embed = discord.Embed(
                    title="All Shops",
                    description=f"Page {p + 1}/{pages}",
                    color=discord.Color.blue(),
                )
                for s in chunk:
                    promo = " *(advertised)*" if s["is_advertised"] else ""
                    embed.add_field(
                        name=f"{s['shop_name']}{promo}",
                        value=f"Owner: {s['owner_name']} | X={s['plot_x']}, Z={s['plot_z']}",
                        inline=False,
                    )
                embeds.append(embed)
            if len(embeds) == 1:
                await interaction.followup.send(embed=embeds[0])
            else:
                await interaction.followup.send(embed=embeds[0], view=BrowsePaginatorView(embeds))

    async def _browse_shop(self, interaction: discord.Interaction, shop_number: int):
        shop = await shops_db.get_shop(shop_number)
        if not shop:
            return await interaction.followup.send(f"Shop #{shop_number} not found.")

        if await shops_db.is_shop_blacklisted(shop_number, interaction.user.id):
            return await interaction.followup.send(
                "You are not allowed to view this shop.", ephemeral=True
            )

        is_owner  = shop["owner_id"] == interaction.user.id
        is_admin_ = await users_db.is_admin(interaction.user.id)
        items      = await shops_db.get_shop_items(
            shop_number, include_drafts=is_owner or is_admin_
        )

        if not items:
            return await interaction.followup.send(
                f"**{shop['shop_name']}** has no listings yet."
            )

        owner_name = await self._resolve_owner_name(shop["owner_id"])

        buf = render_shop_items(
            shop["shop_name"], owner_name, shop["plot_x"], shop["plot_z"], items
        )

        if buf:
            filename = f"shop_{shop_number}_items.png"
            await interaction.followup.send(
                file=discord.File(buf, filename=filename),
            )
        else:
            per_page = 10
            pages    = math.ceil(len(items) / per_page)
            embeds   = []
            for p in range(pages):
                chunk = items[p * per_page:(p + 1) * per_page]
                embed = discord.Embed(
                    title=f"{shop['shop_name']} — Listings",
                    description=(
                        f"Owner: {owner_name} | X={shop['plot_x']}, Z={shop['plot_z']}\n"
                        f"Page {p + 1}/{pages}"
                    ),
                    color=discord.Color.gold(),
                )
                for entry in chunk:
                    embed.add_field(
                        name=entry["item_name"] + (" [DRAFT]" if entry.get("is_draft") else ""),
                        value=format_shop_item_row(entry),
                        inline=False,
                    )
                embeds.append(embed)
            if len(embeds) == 1:
                await interaction.followup.send(embed=embeds[0])
            else:
                await interaction.followup.send(embed=embeds[0], view=BrowsePaginatorView(embeds))

    async def _browse_item(self, interaction: discord.Interaction, item_name: str):
        results = await shops_db.search_items_across_shops(item_name, interaction.user.id)
        if not results:
            return await interaction.followup.send(
                f"No listings found for **{item_name}** across any shops."
            )

        owner_cache: dict[int, str] = {}
        for entry in results:
            oid = entry.get("owner_id")
            if oid and oid not in owner_cache:
                owner_cache[oid] = await self._resolve_owner_name(oid)
            entry["owner_name"] = owner_cache.get(oid, entry.get("owner_name", "—"))

        buf = render_item_search(item_name, results)
        if buf:
            await interaction.followup.send(
                file=discord.File(buf, filename="item_search.png"),
            )
        else:
            per_page = 8
            pages    = math.ceil(len(results) / per_page)
            embeds   = []
            for p in range(pages):
                chunk = results[p * per_page:(p + 1) * per_page]
                embed = discord.Embed(
                    title=f"Listings for: {item_name}",
                    description=f"Sorted by price (cheapest first) | Page {p + 1}/{pages}",
                    color=discord.Color.green(),
                )
                for entry in chunk:
                    mode = "SELL" if entry["is_selling"] else "BUY"
                    qty  = f"{entry['quantity']} SB" if entry["is_shulker"] else str(entry["quantity"])
                    embed.add_field(
                        name=f"{entry['shop_name']}",
                        value=(
                            f"{entry['item_name']} | {mode} | Qty: {qty} | "
                            f"Price: {entry['price']:.2f}"
                        ),
                        inline=False,
                    )
                embeds.append(embed)
            if len(embeds) == 1:
                await interaction.followup.send(embed=embeds[0])
            else:
                await interaction.followup.send(embed=embeds[0], view=BrowsePaginatorView(embeds))


    @app_commands.command(
        name="map",
        description="Show all shops plotted on the server map",
    )
    @app_commands.describe(
        radius="Block radius around the shop cluster to show (default 350)",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def map_cmd(
        self,
        interaction: discord.Interaction,
        radius: Optional[int] = 350,
    ):
        await users_db.track_user(interaction.user.id, interaction.user.name)
        if not await require_not_globally_blacklisted(interaction):
            return

        await interaction.response.defer()

        all_shops = await shops_db.get_all_shops()
        if not all_shops:
            return await interaction.followup.send("No shops registered yet.")

        shop_rows = [
            {
                "shop_name":     shop["shop_name"],
                "plot_x":        shop["plot_x"],
                "plot_z":        shop["plot_z"],
                "is_advertised": shop.get("is_promoted", False),
            }
            for shop in all_shops
        ]

        radius = max(100, min(radius or 350, 2000))

        try:
            buf = await render_shop_map(shop_rows, radius=radius)
        except Exception as exc:
            return await interaction.followup.send(
                f"Failed to render map: `{exc}`\n"
                "Make sure the BlueMap tile server is reachable.",
            )

        if buf is None:
            lines = [f"**{s['shop_name']}** — X={s['plot_x']}, Z={s['plot_z']}" for s in shop_rows]
            embed = discord.Embed(
                title="Shop Locations",
                description="\n".join(lines[:25]),
                color=discord.Color.blue(),
            )
            embed.set_footer(text="Install Pillow on the bot server to enable map images.")
            return await interaction.followup.send(embed=embed)

        embed = discord.Embed(
            title="Shop Map",
            description=(
                f"{len(shop_rows)} shop(s) plotted  |  "
                f"[View full map](https://map.escape.systems/?world=minecraft_overworld)"
            ),
            color=discord.Color.blue(),
        )
        embed.set_image(url="attachment://shop_map.png")
        await interaction.followup.send(
            embed=embed,
            file=discord.File(buf, filename="shop_map.png"),
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ShopCog(bot))
