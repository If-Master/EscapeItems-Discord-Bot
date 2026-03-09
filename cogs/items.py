from __future__ import annotations

import asyncio
from functools import partial
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from database import items as items_db
from database import users as users_db
from utils.formatting import build_item_embed
from views.item_views import CategoryView, ItemSelectionView
from utils.security import secure_check
from utils.renderer import render_item_panel, render_items_list, render_items_combined


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


BrowseBy   = Literal['type', 'location']
DisplayMode = Literal['Images', 'List']


class ItemsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='item', description='Look up an item from the database')
    @app_commands.describe(name='The name of the item to look up')
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def item_command(
        self,
        interaction: discord.Interaction,
        name: Optional[str] = None,
    ):
        await users_db.track_user(interaction.user.id, interaction.user.name)
        if not await secure_check(interaction, name):
            return

        if not name:
            await interaction.response.send_message(
                'Please select a category:', view=CategoryView(), ephemeral=True
            )
            return

        await interaction.response.defer()

        item = await items_db.get_item(name)
        if item:
            buf = await asyncio.get_event_loop().run_in_executor(
                None, partial(render_item_panel, item)
            )
            if buf:
                await interaction.followup.send(file=discord.File(buf, 'item.png'))
            else:
                await interaction.followup.send(
                    embed=build_item_embed(item, interaction.user.name)
                )
            return

        similar = await items_db.search_similar_items(name)
        if not similar:
            await interaction.followup.send(
                f'No items found matching **{name}**.\n'
                'Try `/item` without a name to browse categories.'
            )
            return

        if len(similar) == 1:
            item = await items_db.get_item(similar[0]['name'])
            if item:
                pct = _match_confidence(name, similar[0]['name'])
                buf = await asyncio.get_event_loop().run_in_executor(
                    None, partial(render_item_panel, item)
                )
                if buf:
                    await interaction.followup.send(
                        content=f'*{pct}% match*',
                        file=discord.File(buf, 'item.png'),
                    )
                else:
                    await interaction.followup.send(
                        embed=build_item_embed(item, interaction.user.name)
                    )
                return

        embed = discord.Embed(
            title='Multiple items found',
            description=f'No exact match for **{name}**. Please select from the list below:',
            color=discord.Color.orange(),
        )
        preview = '\n'.join(
            f'• **{i["name"]}** ({i["category"]})' for i in similar[:10]
        )
        embed.add_field(name='Matching items:', value=preview, inline=False)
        if len(similar) > 10:
            embed.set_footer(text=f'Showing 10 of {len(similar)} matches')

        await interaction.followup.send(
            embed=embed, view=ItemSelectionView(similar, interaction.user)
        )

    @app_commands.command(name='browse', description='Browse items by type or location')
    @app_commands.describe(
        by='Browse by item type or by location',
        value='The type or location to browse (e.g. Swords, Dungeon)',
        display='Show item images or a text list',
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def browse(
        self,
        interaction: discord.Interaction,
        by: BrowseBy,
        value: str,
        display: DisplayMode,
    ):
        await users_db.track_user(interaction.user.id, interaction.user.name)
        await interaction.response.defer()

        if by == 'type':
            items = await items_db.get_items_by_subcategory(value)
            title = f'{value} Items'
        else:
            items = await items_db.get_items_by_location(value)
            title = f'Items at: {value}'

        if not items:
            await interaction.followup.send(
                f'No items found for **{value}**.\n'
                'Check spelling or try a different value.',
                ephemeral=True,
            )
            return

        await _send_browse_result(interaction, items=items, title=title, display=display)

    @browse.autocomplete('value')
    async def browse_value_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        by = interaction.namespace.by

        if by == 'type':
            options = await items_db.get_all_subcategories()
        elif by == 'location':
            options = await items_db.get_all_locations()
        else:
            options = []

        return [
            app_commands.Choice(name=o, value=o)
            for o in options
            if current.lower() in o.lower()
        ][:25]


async def _send_browse_result(
    interaction: discord.Interaction,
    items: list[dict],
    title: str,
    display: DisplayMode,
) -> None:
    if display == 'Images':
        item_dicts: list[dict] = []
        for entry in items:
            full = await items_db.get_item(
                entry['name'] if isinstance(entry, dict) else entry
            )
            if full:
                item_dicts.append(full)

        image_groups = [item_dicts[i : i + 5] for i in range(0, len(item_dicts), 5)]
        total_items  = len(item_dicts)

        files_per_batch = 5
        batches  = [image_groups[i : i + files_per_batch] for i in range(0, len(image_groups), files_per_batch)]
        _sem     = asyncio.Semaphore(3)

        async def _render_group(group, label):
            async with _sem:
                return label, await asyncio.get_event_loop().run_in_executor(
                    None, partial(render_items_combined, group)
                )

        for batch_idx, batch in enumerate(batches):
            results = await asyncio.gather(
                *[
                    _render_group(group, batch_idx * files_per_batch + gi + 1)
                    for gi, group in enumerate(batch)
                ]
            )
            files: list[discord.File] = [
                discord.File(buf, f'items_{label}.png')
                for label, buf in sorted(results)
                if buf
            ]

            if not files:
                continue

            if batch_idx == 0:
                caption = (
                    f'**{title}** — {total_items} item{"s" if total_items != 1 else ""}'
                    + (f'  •  Part 1 of {len(batches)}' if len(batches) > 1 else '')
                )
                await interaction.followup.send(content=caption, files=files)
            else:
                await asyncio.sleep(5)
                caption = f'**{title}** — Part {batch_idx + 1} of {len(batches)}'
                await interaction.followup.send(content=caption, files=files)

    else:
        item_list = [
            {
                'name': it['name'],
                'category': it.get('subcategory') or it.get('category', ''),
            }
            if isinstance(it, dict)
            else {'name': it}
            for it in items
        ]
        buf = render_items_list(
            title=title,
            subtitle=f'{len(items)} item(s)',
            items=item_list,
            detail_mode=True,
        )
        if buf:
            embed = discord.Embed(title=title, color=discord.Color.blurple())
            embed.set_image(url='attachment://items_list.png')
            embed.set_footer(text=f'{len(items)} item(s)  •  EscapeItems Shop System')
            await interaction.followup.send(embed=embed, file=discord.File(buf, 'items_list.png'))
        else:
            names = '\n'.join(
                f'• {it["name"] if isinstance(it, dict) else it}'
                for it in items[:30]
            )
            if len(items) > 30:
                names += f'\n*...and {len(items) - 30} more*'
            await interaction.followup.send(names)


async def setup(bot: commands.Bot):
    await bot.add_cog(ItemsCog(bot))