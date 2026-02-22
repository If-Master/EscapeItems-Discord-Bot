import asyncio
import signal
import sys

import discord
from discord.ext import commands

from config import DISCORD_TOKEN, COMMAND_PREFIX
from database.pool import init_pool, close_pool
from database import items as items_db
from database import users as users_db

COGS = [
    "cogs.utility",
    "cogs.items",
    "cogs.admin",
    "cogs.farm",
]


def build_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    return commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


bot = build_bot()


@bot.event
async def on_ready():
    await init_pool()

    await users_db.create_tables()
    await items_db.create_tables()

    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"Loaded {cog}")
        except Exception as exc:
            print(f"Failed to load {cog}: {exc}")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as exc:
        print(f"Command sync failed: {exc}")

    print(f"Online as {bot.user} | {len(bot.guilds)} server(s)")


@bot.event
async def on_command_error(ctx, error):
    print(f"Command error: {error}")


async def shutdown():
    print("Shutting down...")
    await close_pool()
    await bot.close()


def _signal_handler(sig, frame):
    asyncio.get_event_loop().create_task(shutdown())
    sys.exit(0)


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN missing from .env")
        sys.exit(1)

    signal.signal(signal.SIGINT, _signal_handler)
    print("Starting bot — press Ctrl+C to stop")

    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("Stopped by user")