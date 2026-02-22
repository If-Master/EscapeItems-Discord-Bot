# EscapeItems Bot

A Discord bot for the **EscapeSystem** Minecraft server. Look up custom items, calculate farm profits, and browse item prices — all from Discord.

---

## Features

### `/item [name]`
Look up any special item in the database.
- Leave `name` blank to browse by category
- Fuzzy search — if one match is found it pulls it up automatically with a confidence indicator
- Shows description, location, enchantments, crafting recipe if applicable

### `/farmcalc`
Interactive farm profit calculator.
- Add produced and consumed items with quantities per hour
- Override consume prices with custom player-shop prices
- Undo last entry, reset, or calculate at any time
- Outputs a detailed breakdown image with income, costs, and net profit

### `/farmprices [item]`
Look up NBT Worth Scanner prices.
- Leave blank to get the full price list as a paginated image (sorted highest to lowest)
- Provide an item ID (e.g. `minecraft:wheat`) to look up a single item and see its rank

### `/escapeitems-tos`
View the Terms of Service (sent to your DMs).

### `/escapeitems-privacy`
View the Privacy Policy (sent to your DMs).

---

## Admin Commands

All admin commands are under `/admin` and require admin permissions.

| Action | Description |
|---|---|
| `add-item` | Add a new item to the database |
| `modify-item` | Edit an existing item |
| `remove-item` | Delete an item |
| `add-admin` | Grant a user admin access |
| `remove-admin` | Revoke admin access |
| `list-admins` | List all current admins |
| `announce` | Send a DM announcement to all bot users |
| `stats` | View bot statistics (users, servers, items, uptime) |

---

## Setup

### Requirements
- Python 3.11+
- PostgreSQL database
- The following Python packages:

```
discord.py
asyncpg
python-dotenv
pillow
```

### Installation

```bash
git clone https://github.com/If-Master/EscapeItems-Discord-Bot
cd escapeitems-bot
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the root directory:

```env
DISCORD_TOKEN=your_bot_token_here
DB_HOST=localhost
DB_NAME=escapesystemitems
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_PORT=5432
ADMIN_USER_IDS=123456789,987654321
```

`ADMIN_USER_IDS` is a comma-separated list of Discord user IDs that always have admin access regardless of the database.

### Running

```bash
python main.py
```

The bot will automatically create all required database tables on first run.

---

## Project Structure

```
├── main.py                  # Entry point
├── config.py                # Config, constants, TOS/Privacy text
├── cogs/
│   ├── admin.py             # Admin command panel
│   ├── farm.py              # Farm calculator & price lookup
│   ├── items.py             # Item lookup command
│   └── utility.py           # Status loop, TOS, Privacy
├── database/
│   ├── pool.py              # asyncpg connection pool
│   ├── items.py             # Item DB queries
│   └── users.py             # User tracking & admin DB queries
├── utils/
│   ├── checks.py            # Permission check helpers
│   ├── formatting.py        # Embed builders & text formatters
│   ├── renderer.py          # Pillow image renderer
│   └── security.py          # Input sanitisation & injection detection
└── views/
    └── item_views.py        # Category browser & item selector views
```

---

## Notes

- The bot works as both a **server bot** and a **user-installed app** (works in DMs and private channels)
- Image rendering requires Pillow — the bot falls back to plain embeds if unavailable
- Item prices in `/farmcalc` and `/farmprices` are sourced from the **NBT Worth Scanner** plugin

---

## Contact

For issues or questions, contact **If_Master** on Discord.
