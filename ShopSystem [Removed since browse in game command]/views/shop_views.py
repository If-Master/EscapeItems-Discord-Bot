from __future__ import annotations

import io
from typing import List

import discord

from database import shops as shops_db
from utils.renderer import render_shop_items


class ShopItemModal(discord.ui.Modal):
    item_name = discord.ui.TextInput(
        label="Item Name",
        placeholder="e.g. Diamond Sword",
        max_length=100,
    )
    quantity = discord.ui.TextInput(
        label="Quantity",
        placeholder="e.g. 64",
        max_length=10,
    )
    price = discord.ui.TextInput(
        label="Price",
        placeholder="e.g. 500",
        max_length=20,
    )

    def __init__(
        self,
        shop_id: int,
        is_selling: bool,
        is_shulker: bool,
        is_draft: bool,
        edit_item_id: int | None = None,
    ):
        title = "Edit Listing" if edit_item_id else "Add Listing"
        super().__init__(title=title)
        self.shop_id = shop_id
        self.is_selling = is_selling
        self.is_shulker = is_shulker
        self.is_draft = is_draft
        self.edit_item_id = edit_item_id

    async def on_submit(self, interaction: discord.Interaction):
        from utils.security import check_input, SecurityViolation
        try:
            check_input(self.item_name.value)
        except SecurityViolation:
            await interaction.response.send_message(
                "No, I'm not allowed to hand you that information.",
                ephemeral=True,
            )
            return

        try:
            qty = int(self.quantity.value)
            price = float(self.price.value)
        except ValueError:
            await interaction.response.send_message(
                "Quantity must be a whole number and Price must be a number.",
                ephemeral=True,
            )
            return

        if qty <= 0 or price < 0:
            await interaction.response.send_message(
                "Quantity must be positive and price cannot be negative.",
                ephemeral=True,
            )
            return

        if self.edit_item_id:
            await shops_db.update_shop_item(
                self.edit_item_id,
                item_name=self.item_name.value,
                is_selling=self.is_selling,
                is_shulker=self.is_shulker,
                quantity=qty,
                price=price,
                is_draft=self.is_draft,
            )
            await interaction.response.send_message(
                f"Listing **{self.item_name.value}** updated.", ephemeral=True
            )
        else:
            from config import MAX_SHOP_ITEMS
            count = await shops_db.count_shop_items(self.shop_id)
            if count >= MAX_SHOP_ITEMS:
                await interaction.response.send_message(
                    f"Shop is full ({MAX_SHOP_ITEMS} item limit).",
                    ephemeral=True,
                )
                return
            await shops_db.add_shop_item(
                self.shop_id,
                self.item_name.value,
                self.is_selling,
                self.is_shulker,
                qty,
                price,
                self.is_draft,
            )
            await interaction.response.send_message(
                f"Listing **{self.item_name.value}** added!",
                view=AddAnotherView(
                    self.shop_id,
                    is_selling=self.is_selling,
                    is_shulker=self.is_shulker,
                    is_draft=self.is_draft,
                ),
                ephemeral=True,
            )


class AddAnotherView(discord.ui.View):
    def __init__(self, shop_id: int, is_selling: bool, is_shulker: bool, is_draft: bool):
        super().__init__(timeout=60)
        self.shop_id = shop_id
        self.is_selling = is_selling
        self.is_shulker = is_shulker
        self.is_draft = is_draft

    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary, emoji="✅")
    async def done(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "All set! Use `/shop-items` to view and manage your listings.",
            ephemeral=True,
        )
        self.stop()


class AddItemFlagView(discord.ui.View):
    def __init__(self, shop_id: int, edit_item_id: int | None = None):
        super().__init__(timeout=120)
        self.shop_id = shop_id
        self.edit_item_id = edit_item_id
        self.is_selling: bool | None = None
        self.is_shulker: bool | None = None
        self.is_draft: bool | None = None

    def _all_selected(self) -> bool:
        return all(
            v is not None
            for v in (self.is_selling, self.is_shulker, self.is_draft)
        )

    @discord.ui.select(
        placeholder="Selling or Buying?",
        options=[
            discord.SelectOption(label="Selling", value="sell"),
            discord.SelectOption(label="Buying", value="buy"),
        ],
        row=0,
    )
    async def mode_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.is_selling = select.values[0] == "sell"
        if self._all_selected():
            await self._open_modal(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.select(
        placeholder="Quantity in Shulker Boxes?",
        options=[
            discord.SelectOption(label="Yes - shulker boxes", value="yes"),
            discord.SelectOption(label="No - individual items", value="no"),
        ],
        row=1,
    )
    async def shulker_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.is_shulker = select.values[0] == "yes"
        if self._all_selected():
            await self._open_modal(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.select(
        placeholder="Draft mode? (Only you can see it)",
        options=[
            discord.SelectOption(label="Yes - draft", value="yes"),
            discord.SelectOption(label="No - public", value="no"),
        ],
        row=2,
    )
    async def draft_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.is_draft = select.values[0] == "yes"
        if self._all_selected():
            await self._open_modal(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Continue", style=discord.ButtonStyle.primary, row=3)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._all_selected():
            await interaction.response.send_message(
                "Please answer all three questions first.", ephemeral=True
            )
            return
        await self._open_modal(interaction)

    async def _open_modal(self, interaction: discord.Interaction):
        modal = ShopItemModal(
            shop_id=self.shop_id,
            is_selling=self.is_selling,
            is_shulker=self.is_shulker,
            is_draft=self.is_draft,
            edit_item_id=self.edit_item_id,
        )
        await interaction.response.send_modal(modal)

class ShopItemsView(discord.ui.View):
    ITEMS_PER_PAGE = 15

    def __init__(
        self,
        shop: dict,
        items: list[dict],
        owner: discord.User,
        owner_name: str = "",
    ):
        super().__init__(timeout=180)
        self.shop = shop
        self.all_items = items
        self.owner = owner
        self.owner_name = owner_name or owner.name
        self.page = 0
        self._refresh_page_buttons()


    @property
    def total_pages(self) -> int:
        return max(1, -(-len(self.all_items) // self.ITEMS_PER_PAGE))

    def current_page_items(self) -> list[dict]:
        start = self.page * self.ITEMS_PER_PAGE
        return self.all_items[start : start + self.ITEMS_PER_PAGE]

    def _refresh_page_buttons(self):
        self.prev_page.disabled = self.page == 0
        self.next_page.disabled = self.page >= self.total_pages - 1

    def _render(self) -> io.BytesIO | None:
        page_items = self.current_page_items()
        buf = render_shop_items(
            shop_name=self.shop["shop_name"],
            owner_name=self.owner_name,
            plot_x=self.shop["plot_x"],
            plot_z=self.shop["plot_z"],
            items=page_items,
        )
        return buf

    def _build_embed(self, with_image: bool = True) -> discord.Embed:
        embed = discord.Embed(
            title=f"My Listings — {self.shop['shop_name']}",
            description=f"Page {self.page + 1}/{self.total_pages}  •  {len(self.all_items)} listing(s)",
            color=discord.Color.blue(),
        )
        if with_image:
            embed.set_image(url="attachment://listings.png")
        else:
            for entry in self.current_page_items():
                mode = "SELL" if entry["is_selling"] else "BUY"
                qty = f"{entry['quantity']} SB" if entry["is_shulker"] else str(entry["quantity"])
                draft = " [DRAFT]" if entry.get("is_draft") else ""
                embed.add_field(
                    name=f"[{entry['id']}] {entry['item_name']}{draft}",
                    value=f"{mode} | Qty: {qty} | Price: {entry['price']:.2f}",
                    inline=False,
                )
            if not self.all_items:
                embed.description = "No listings yet. Use **Add Listing** to get started."
        return embed

    async def send(self, interaction: discord.Interaction):
        buf = self._render()
        if buf:
            embed = self._build_embed(with_image=True)
            await interaction.followup.send(
                embed=embed,
                file=discord.File(buf, filename="listings.png"),
                view=self,
                ephemeral=True,
            )
        else:
            embed = self._build_embed(with_image=False)
            await interaction.followup.send(embed=embed, view=self, ephemeral=True)


    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary, row=0)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        self._refresh_page_buttons()
        await self._update(interaction)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, row=0)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        self._refresh_page_buttons()
        await self._update(interaction)

    async def _update(self, interaction: discord.Interaction):
        buf = self._render()
        if buf:
            embed = self._build_embed(with_image=True)
            await interaction.response.edit_message(
                embed=embed,
                attachments=[discord.File(buf, filename="listings.png")],
                view=self,
            )
        else:
            embed = self._build_embed(with_image=False)
            await interaction.response.edit_message(embed=embed, view=self)


    @discord.ui.button(label="Add Listing", style=discord.ButtonStyle.success, row=1)
    async def add_listing(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                "Only the shop owner can manage this shop.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            "Configure your new listing:",
            view=AddItemFlagView(self.shop["id"]),
            ephemeral=True,
        )

    @discord.ui.button(label="Edit Listing", style=discord.ButtonStyle.primary, row=1)
    async def edit_listing(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                "Only the shop owner can manage this shop.", ephemeral=True
            )
            return
        if not self.all_items:
            await interaction.response.send_message("No listings to edit.", ephemeral=True)
            return
        await interaction.response.send_message(
            "Select a listing to edit:",
            view=_EditSelectView(self.shop["id"], self.all_items),
            ephemeral=True,
        )

    @discord.ui.button(label="Remove Listing", style=discord.ButtonStyle.danger, row=1)
    async def remove_listing(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                "Only the shop owner can manage this shop.", ephemeral=True
            )
            return
        if not self.all_items:
            await interaction.response.send_message("No listings to remove.", ephemeral=True)
            return
        await interaction.response.send_message(
            "Select a listing to remove:",
            view=_RemoveSelectView(self.shop["id"], self.all_items),
            ephemeral=True,
        )

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, row=2)
    async def refresh_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_owner  = self.shop["owner_id"] == interaction.user.id
        new_items = await shops_db.get_shop_items(
            self.shop["id"], include_drafts=is_owner
        )
        self.all_items = new_items
        self.page = min(self.page, max(0, self.total_pages - 1))
        self._refresh_page_buttons()
        await self._update(interaction)

class _EditSelectView(discord.ui.View):
    def __init__(self, shop_id: int, items: list[dict]):
        super().__init__(timeout=60)
        self._shop_id = shop_id
        self._items_map = {e["id"]: e for e in items}
        options = [
            discord.SelectOption(
                label=f"[{e['id']}] {e['item_name'][:80]}",
                value=str(e["id"]),
            )
            for e in items[:25]
        ]
        select = discord.ui.Select(placeholder="Choose listing...", options=options)
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        item_id = int(interaction.data["values"][0])
        entry = self._items_map[item_id]
        await interaction.response.send_message(
            f"Editing **{entry['item_name']}** — re-select flags then confirm:",
            view=AddItemFlagView(self._shop_id, edit_item_id=item_id),
            ephemeral=True,
        )
        self.stop()


class _RemoveSelectView(discord.ui.View):
    def __init__(self, shop_id: int, items: list[dict]):
        super().__init__(timeout=60)
        options = [
            discord.SelectOption(
                label=f"[{e['id']}] {e['item_name'][:80]}",
                value=str(e["id"]),
            )
            for e in items[:25]
        ]
        select = discord.ui.Select(
            placeholder="Choose listing to remove...", options=options
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        item_id = int(interaction.data["values"][0])
        removed = await shops_db.remove_shop_item(item_id)
        await interaction.response.send_message(
            "Listing removed." if removed else "Could not find that listing.",
            ephemeral=True,
        )
        self.stop()

class BrowsePaginatorView(discord.ui.View):
    def __init__(self, embeds: list[discord.Embed]):
        super().__init__(timeout=120)
        self.embeds = embeds
        self.page = 0
        self._refresh()

    def _refresh(self):
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= len(self.embeds) - 1

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        self._refresh()
        await interaction.response.edit_message(embed=self.embeds[self.page], view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        self._refresh()
        await interaction.response.edit_message(embed=self.embeds[self.page], view=self)
