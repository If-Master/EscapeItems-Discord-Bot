import json
from collections import Counter
from datetime import datetime, timezone

import discord


def split_message(text: str, max_length: int = 2000) -> list[str]:
    if len(text) <= max_length:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_length:
            if current:
                chunks.append(current.strip())
            current = line + "\n"
        else:
            current += line + "\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks


def format_crafting_recipe(craft_data: dict) -> str:
    grid = craft_data.get("grid", [[None] * 3 for _ in range(3)])
    output = craft_data.get("output", 1)
    ingredients = [item for row in grid for item in row if item]
    counts = Counter(ingredients)
    lines = [
        f"• {n}x {item}" if n > 1 else f"• {item}"
        for item, n in sorted(counts.items())
    ]
    return "\n".join(lines) + f"\n\n**Output:** {output}x"


def format_crafting_table(craft_data: dict) -> str:
    grid = craft_data.get("grid", [[None] * 3 for _ in range(3)])
    output = craft_data.get("output", 1)
    lines = ["**Crafting Grid (3x3):**\n"]
    for i, row in enumerate(grid, 1):
        lines.append(
            f"Row {i}: " + " | ".join(item if item else "Empty" for item in row)
        )
    lines.append(f"\n**Output:** {output}x")
    return "\n".join(lines)


def build_item_embed(item: dict, requester_name: str) -> discord.Embed:
    embed = discord.Embed(
        title=item["name"],
        description=item["info"] or "No description available",
        color=discord.Color.gold(),
    )
    if item["image"]:
        embed.set_thumbnail(url=item["image"])
    if item["location"]:
        embed.add_field(name="Location", value=item["location"], inline=False)
    if item["enchantments"]:
        embed.add_field(name="Enchantments", value=item["enchantments"], inline=False)
    embed.add_field(name="Category", value=item["item_category"], inline=True)
    if item["craftable"]:
        embed.add_field(name="Craftable", value="Yes", inline=True)
        if item["craft_data"]:
            craft = (
                json.loads(item["craft_data"])
                if isinstance(item["craft_data"], str)
                else item["craft_data"]
            )
            embed.add_field(
                name="Ingredients", value=format_crafting_recipe(craft), inline=False
            )
            embed.add_field(
                name="Crafting Grid", value=format_crafting_table(craft), inline=False
            )
    else:
        embed.add_field(name="Craftable", value="No", inline=True)
    embed.set_footer(text=f"Requested by {requester_name}")
    embed.timestamp = datetime.now(timezone.utc)
    return embed


def format_uptime(start_time: datetime | None) -> str:
    if not start_time:
        return "0s"
    delta = datetime.now(timezone.utc) - start_time
    h, rem = divmod(int(delta.total_seconds()), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"
