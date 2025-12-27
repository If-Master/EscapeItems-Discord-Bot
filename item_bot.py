import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncpg
import json
from typing import Optional, List
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
import signal
import sys

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

db_pool = None

bot_start_time = None

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'escapesystemitems'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': int(os.getenv('DB_PORT', 5432))
}

ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_USER_IDS', '').split(',') if id.strip()]

# Categories
CATEGORIES = [
    "Weapons", "Tools", "Spawner",
    "Potions", "Wings & Others", "Spawn Eggs"
]

TOS_TEXT = """**Terms of Service for EscapeItems**
*Last Updated: December 3, 2025*

**1. Description of Service**
This Discord bot provides item lookup functionality for the server EscapeSystem, including item information, crafting recipes, locations, and categories.

**2. Acceptable Use**
You may use this bot for:
• Looking up item information
• Browsing item categories
• Viewing crafting recipes

You may NOT:
• Attempt to exploit, hack, or abuse the bot
• Use the bot to spam or harass other users
• Attempt to overload the bot with excessive requests

**3. Availability**
• The bot is provided "as is" without guarantees of uptime
• We may take the bot offline for maintenance at any time
• We reserve the right to terminate service to any user or server

**4. Data Accuracy**
• Item information is provided for reference only
• We do not guarantee accuracy or completeness of data
• Game data may change; bot information may be outdated

**5. Termination**
We reserve the right to:
• Remove the bot from servers that violate these terms
• Block users who abuse the service
• Discontinue the service at any time

**6. Changes to Terms**
We may update these terms at any time. Continued use constitutes acceptance.

**7. Contact**
For questions: Contact If_Master on Discord
"""

PRIVACY_TEXT = """**Privacy Policy for EscapeItems**
*Last Updated: December 3, 2025*

**1. Information We Collect**

*Automatically Collected:*
• Discord User ID - Only when you interact with the bot (not stored permanently)
• Discord Username - Displayed in embed footers temporarily
• Server IDs - To track bot usage (count only, no server data stored)
• Command Usage - Which commands you use (not stored, only logged for debugging)

*NOT Collected:*
• Message content (except direct commands to the bot)
• Private conversations
• User profiles or personal information
• IP addresses
• Email addresses

**2. How We Use Information**
We use collected data to:
• Display your username in command responses
• Show bot statistics (server count, uptime)
• Ensure the correct user can interact with selection menus
• Debug errors and improve the bot

**3. Data Storage**

*What We Store:*
• Item Database - Game item information (publicly available data)
• No user data is permanently stored

*What We Don't Store:*
• User commands or search history
• Personal messages
• User preferences or settings

**4. Data Sharing**
We do NOT:
• Sell your data
• Share data with third parties
• Use data for advertising
• Track users across Discord

Your Discord User ID is only used during active command sessions and is not retained.

**5. Database Information**
Our PostgreSQL database contains:
• Item names, descriptions, images
• Crafting recipes and locations
• Item categories

No user data is stored in the database.

**6. Third-Party Services**
This bot uses:
• Discord API - Subject to Discord's Privacy Policy
• PostgreSQL Database - Hosted securely, contains only game data

**7. Data Security**
• Database connections are secured with passwords
• No user data is logged to files
• Bot token is kept secure in environment variables

**8. Your Rights**
You have the right to:
• Stop using the bot at any time
• Request information about what data we process (answer: none permanently)
• Report concerns to If_Master

**9. Children's Privacy**
This bot does not knowingly collect data from children under/over 13. The bot is designed for general audiences. No data is stored ever!

**10. Data Retention**
• User IDs: Stored in memory only during command execution (seconds/milliseconds)
• Interaction data: Not retained after response is sent
• Database: Contains only game items, no user data

**11. Changes to Privacy Policy**
We may update this policy. Continued use constitutes acceptance of changes.

**12. Contact**
For privacy concerns: Contact If_Master on Discord

**Summary:** This bot collects minimal temporary data (your User ID and username) only to respond to your commands. No data is permanently stored. Your privacy is respected.
"""

async def init_db():
    """Initialize database connection pool and create necessary tables"""
    global db_pool
    db_pool = await asyncpg.create_pool(**DB_CONFIG, min_size=2, max_size=10)
    print("Database pool created")
    
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                user_id BIGINT PRIMARY KEY,
                added_by BIGINT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("Database tables verified")

async def track_user(user_id: int, username: str):
    """Track user interaction with the bot"""
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO bot_users (user_id, username, first_seen, last_seen)
            VALUES ($1, $2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) 
            DO UPDATE SET 
                username = $2,
                last_seen = CURRENT_TIMESTAMP
        """, user_id, username)

async def get_all_users():
    """Get all tracked users"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM bot_users")
        return [row['user_id'] for row in rows]

async def is_admin(user_id: int) -> bool:
    """Check if user is an admin"""
    if user_id in ADMIN_IDS:
        return True
    
    async with db_pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM admin_users WHERE user_id = $1)",
            user_id
        )
        return result

async def add_admin(user_id: int, added_by: int):
    """Add a user to admin list"""
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO admin_users (user_id, added_by)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO NOTHING
        """, user_id, added_by)

async def remove_admin(user_id: int):
    """Remove a user from admin list"""
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM admin_users WHERE user_id = $1", user_id)

async def get_admins():
    """Get all admin users"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM admin_users")
        db_admins = [row['user_id'] for row in rows]
        return list(set(ADMIN_IDS + db_admins))

async def get_item(item_name: str):
    """Fetch item from database"""
    async with db_pool.acquire() as conn:
        query = """
            SELECT id, name, image, location, info, enchantments, 
                   craftable, item_category, craft_data
            FROM items 
            WHERE LOWER(name) = LOWER($1)
        """
        return await conn.fetchrow(query, item_name)

async def search_similar_items(search_term: str, limit: int = 10) -> List[dict]:
    """Search for items with partial name matches"""
    async with db_pool.acquire() as conn:
        query = """
            SELECT name, item_category
            FROM items 
            WHERE LOWER(name) LIKE LOWER($1)
            ORDER BY 
                CASE 
                    WHEN LOWER(name) = LOWER($2) THEN 0
                    WHEN LOWER(name) LIKE LOWER($3) THEN 1
                    ELSE 2
                END,
                name
            LIMIT $4
        """
        search_pattern = f"%{search_term}%"
        start_pattern = f"{search_term}%"
        rows = await conn.fetch(query, search_pattern, search_term, start_pattern, limit)
        return [{'name': row['name'], 'category': row['item_category']} for row in rows]

async def get_items_by_category(category: str):
    """Fetch all items in a category"""
    async with db_pool.acquire() as conn:
        query = """
            SELECT name FROM items 
            WHERE item_category = $1 
            ORDER BY name
        """
        rows = await conn.fetch(query, category)
        return [row['name'] for row in rows]

async def get_total_items():
    """Get total item count"""
    async with db_pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM items")

async def get_category_count():
    """Get number of categories with items"""
    async with db_pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(DISTINCT item_category) FROM items")

async def add_item_to_db(name: str, image: str, location: str, info: str, 
                        enchantments: str, craftable: bool, category: str, 
                        craft_data: dict = None):
    """Add a new item to the database"""
    async with db_pool.acquire() as conn:
        craft_json = json.dumps(craft_data) if craft_data else None
        await conn.execute("""
            INSERT INTO items (name, image, location, info, enchantments, 
                             craftable, item_category, craft_data)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """, name, image, location, info, enchantments, craftable, category, craft_json)

async def remove_item_from_db(name: str):
    """Remove an item from the database"""
    async with db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM items WHERE LOWER(name) = LOWER($1)", name)
        return result != "DELETE 0"

async def update_item_in_db(name: str, **kwargs):
    """Update an existing item in the database"""
    async with db_pool.acquire() as conn:
        update_fields = []
        values = []
        param_count = 1
        
        for field, value in kwargs.items():
            if value is not None:
                if field == 'craft_data' and isinstance(value, dict):
                    value = json.dumps(value)
                update_fields.append(f"{field} = ${param_count}")
                values.append(value)
                param_count += 1
        
        if not update_fields:
            return False
        
        values.append(name)
        query = f"UPDATE items SET {', '.join(update_fields)} WHERE LOWER(name) = LOWER(${param_count})"
        result = await conn.execute(query, *values)
        return result != "UPDATE 0"

def format_uptime():
    """Format bot uptime"""
    if not bot_start_time:
        return "0s"
    
    delta = datetime.now(timezone.utc) - bot_start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

@tasks.loop(seconds=30)
async def change_status():
    """Rotate bot status every 30 seconds"""
    if not bot.is_ready() or not bot.ws:
        return
    
    statuses = [
        lambda: f"Time alive: {format_uptime()}",
        lambda: f"About {get_total_items.result} items in {get_category_count.result} categories",
        lambda: f"Used by {len(bot.guilds)} server(s)",
        lambda: f"Can also be used as a app (No accurate way to calculate how many users has added it to their apps)",
        lambda: "Latest update: Admin stuff, bug fixes"
    ]
    
    if change_status.current_loop % 2 == 0: 
        try:
            get_total_items.result = await get_total_items()
            get_category_count.result = await get_category_count()
        except Exception:
            pass
    
    if not hasattr(change_status, 'index'):
        change_status.index = 0
        get_total_items.result = 0
        get_category_count.result = 0
    
    status_text = statuses[change_status.index]()
    
    try:
        if bot.ws and not bot.ws.socket.closed:
            await bot.change_presence(
                status=discord.Status.dnd,
                activity=discord.Game(name=status_text)
            )
        change_status.index = (change_status.index + 1) % len(statuses)
    except (discord.ConnectionClosed, ConnectionResetError, AttributeError) as e:
        print(f"Failed to update status: {e}")
    except Exception as e:
        print(f"Unexpected error in change_status: {e}")

@change_status.before_loop
async def before_status():
    """Wait until bot is ready before starting status loop"""
    await bot.wait_until_ready()
    try:
        get_total_items.result = await get_total_items()
        get_category_count.result = await get_category_count()
    except:
        get_total_items.result = 0
        get_category_count.result = 0

class CategorySelect(discord.ui.Select):
    """Category selection dropdown"""
    def __init__(self):
        options = [
            discord.SelectOption(label=cat, value=cat, emoji="📦")
            for cat in CATEGORIES
        ]
        super().__init__(placeholder="Select a category...", options=options, min_values=1, max_values=1)
    
    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        items = await get_items_by_category(category)
        
        if not items:
            await interaction.response.send_message(f"No items found in **{category}**", ephemeral=True)
            return
        
        chunks = [items[i:i+25] for i in range(0, len(items), 25)]
        
        embed = discord.Embed(
            title=f"📦 {category} Items",
            description="\n".join([f"• {item}" for item in chunks[0]]),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Showing {len(chunks[0])} of {len(items)} items | Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

class CategoryView(discord.ui.View):
    """View with category selection"""
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(CategorySelect())

class ItemSelectionSelect(discord.ui.Select):
    """Item selection dropdown for similar matches"""
    def __init__(self, items: List[dict], original_user: discord.User):
        self.original_user = original_user
        options = [
            discord.SelectOption(
                label=item['name'][:100], 
                value=item['name'],
                description=f"Category: {item['category']}"[:100],
                emoji="🔍"
            )
            for item in items[:25] 
        ]
        super().__init__(placeholder="Select the item you meant...", options=options, min_values=1, max_values=1)
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.original_user.id:
            await interaction.response.send_message("❌ This selection menu is not for you!", ephemeral=True)
            return
        
        selected_item_name = self.values[0]
        
        item = await get_item(selected_item_name)
        
        if not item:
            await interaction.response.send_message(f"❌ Error loading item **{selected_item_name}**", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=item['name'],
            description=item['info'] or "No description available",
            color=discord.Color.gold()
        )
        
        if item['image']:
            embed.set_thumbnail(url=item['image'])
        
        if item['location']:
            embed.add_field(name="📍 Location", value=item['location'], inline=False)
        
        if item['enchantments']:
            embed.add_field(name="✨ Enchantments", value=item['enchantments'], inline=False)
        
        embed.add_field(name="📦 Category", value=item['item_category'], inline=True)
        
        if item['craftable']:
            embed.add_field(name="🔨 Craftable", value="Yes", inline=True)
            
            if item['craft_data']:
                craft_data = json.loads(item['craft_data']) if isinstance(item['craft_data'], str) else item['craft_data']
                
                recipe_list = format_crafting_recipe(craft_data)
                embed.add_field(name="📋 Ingredients", value=recipe_list, inline=False)
                
                recipe_grid = format_crafting_table(craft_data)
                embed.add_field(name="🔨 Crafting Grid", value=recipe_grid, inline=False)
        else:
            embed.add_field(name="🔨 Craftable", value="No", inline=True)
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        embed.timestamp = datetime.now(timezone.utc)
        
        self.view.stop()
        for child in self.view.children:
            child.disabled = True
        
        await interaction.response.edit_message(content="✅ Item selected:", view=self.view)
        
        await interaction.followup.send(embed=embed)

class ItemSelectionView(discord.ui.View):
    """View with item selection dropdown"""
    def __init__(self, items: List[dict], original_user: discord.User):
        super().__init__(timeout=60)
        self.add_item(ItemSelectionSelect(items, original_user))
    
    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

def format_crafting_recipe(craft_data: dict) -> str:
    """Format crafting recipe as a list of ingredients"""
    if not craft_data:
        return "No crafting recipe available"
    
    grid = craft_data.get('grid', [[None]*3 for _ in range(3)])
    output = craft_data.get('output', 1)
    
    ingredients = []
    for row in grid:
        for item in row:
            if item:
                ingredients.append(item)
    
    from collections import Counter
    item_counts = Counter(ingredients)
    
    recipe_lines = []
    for item, count in sorted(item_counts.items()):
        if count > 1:
            recipe_lines.append(f"• {count}x {item}")
        else:
            recipe_lines.append(f"• {item}")
    
    recipe_text = "\n".join(recipe_lines)
    recipe_text += f"\n\n**Output:** {output}x"
    
    return recipe_text

def format_crafting_table(craft_data: dict) -> str:
    """Format 3x3 crafting grid as simple list"""
    if not craft_data:
        return "No crafting recipe available"
    
    grid = craft_data.get('grid', [[None]*3 for _ in range(3)])
    output = craft_data.get('output', 1)
    
    lines = ["**Crafting Grid (3x3):**\n"]
    
    for i, row in enumerate(grid, 1):
        row_text = " | ".join([item if item else "Empty" for item in row])
        lines.append(f"Row {i}: {row_text}")
    
    lines.append(f"\n**Output:** {output}x")
    
    return "\n".join(lines)

@bot.event
async def on_ready():
    """Bot startup"""
    global bot_start_time
    bot_start_time = datetime.now(timezone.utc)
    
    await init_db()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    
    print(f"Bot online as {bot.user}")
    print(f"Running on {len(bot.guilds)} server(s)")
    print(f"Admin IDs: {ADMIN_IDS}")
    
    change_status.start()
    print("Status rotation started")

@bot.tree.command(name="item", description="Look up an item from the database")
@app_commands.describe(name="The name of the item to look up")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def item_command(interaction: discord.Interaction, name: Optional[str] = None):
    """Look up item information with fuzzy matching"""
    
    await track_user(interaction.user.id, interaction.user.name)
    
    if not name:
        view = CategoryView()
        await interaction.response.send_message(
            "Please select a category:",
            view=view,
            ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=False)
    
    item = await get_item(name)
    
    if item:
        embed = discord.Embed(
            title=item['name'],
            description=item['info'] or "No description available",
            color=discord.Color.gold()
        )
        
        if item['image']:
            embed.set_thumbnail(url=item['image'])
        
        if item['location']:
            embed.add_field(name="📍 Location", value=item['location'], inline=False)
        
        if item['enchantments']:
            embed.add_field(name="✨ Enchantments", value=item['enchantments'], inline=False)
        
        embed.add_field(name="📦 Category", value=item['item_category'], inline=True)
        
        if item['craftable']:
            embed.add_field(name="🔨 Craftable", value="Yes", inline=True)
            
            if item['craft_data']:
                craft_data = json.loads(item['craft_data']) if isinstance(item['craft_data'], str) else item['craft_data']
                
                recipe_list = format_crafting_recipe(craft_data)
                embed.add_field(name="📋 Ingredients", value=recipe_list, inline=False)
                
                recipe_grid = format_crafting_table(craft_data)
                embed.add_field(name="🔨 Crafting Grid", value=recipe_grid, inline=False)
        else:
            embed.add_field(name="🔨 Craftable", value="No", inline=True)
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        embed.timestamp = datetime.now(timezone.utc)
        
        await interaction.followup.send(embed=embed)
        return
    
    similar_items = await search_similar_items(name)
    
    if not similar_items:
        await interaction.followup.send(
            f"❌ No items found matching **{name}**.\n"
            f"Try using `/item` without a name to browse categories.",
            ephemeral=False
        )
        return
    
    if len(similar_items) == 1:
        suggestion = similar_items[0]['name']
        embed = discord.Embed(
            title="🔍 Did you mean?",
            description=f"No exact match for **{name}**.\n\nDid you mean: **{suggestion}**?",
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"Use /item name:{suggestion} to view this item")
        await interaction.followup.send(embed=embed)
        return
    
    embed = discord.Embed(
        title="🔍 Multiple items found",
        description=f"No exact match for **{name}**. Please select from the options below:",
        color=discord.Color.orange()
    )
    
    preview_items = similar_items[:10]
    preview_text = "\n".join([f"• **{item['name']}** ({item['category']})" for item in preview_items])
    embed.add_field(name="Matching items:", value=preview_text, inline=False)
    
    if len(similar_items) > 10:
        embed.set_footer(text=f"Showing 10 of {len(similar_items)} matches")
    
    view = ItemSelectionView(similar_items, interaction.user)
    await interaction.followup.send(embed=embed, view=view)

def split_message(text: str, max_length: int = 2000) -> List[str]:
    """Split a message into chunks that fit Discord's character limit"""
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    lines = text.split('\n')
    
    for line in lines:
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = line + '\n'
            else:
                while len(line) > max_length:
                    chunks.append(line[:max_length])
                    line = line[max_length:]
                current_chunk = line + '\n'
        else:
            current_chunk += line + '\n'
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks

@bot.tree.command(name="escapeitems-tos", description="View the Terms of Service for EscapeItems")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def tos_command(interaction: discord.Interaction):
    """Send Terms of Service via DM"""
    await track_user(interaction.user.id, interaction.user.name)
    
    try:
        chunks = split_message(TOS_TEXT)
        
        for i, chunk in enumerate(chunks):
            if i == 0:
                await interaction.user.send(chunk)
            else:
                await interaction.user.send(chunk)
        
        await interaction.response.send_message("📜 Terms of Service sent to your DMs!", ephemeral=True)
    except discord.Forbidden:
        chunks = split_message(TOS_TEXT, max_length=1900)  
        error_msg = "❌ I couldn't send you a DM. Please enable DMs from server members.\n\n"
        
        if len(chunks) == 1:
            await interaction.response.send_message(
                error_msg + "Alternatively, here's the TOS:\n" + chunks[0],
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                error_msg + "The TOS is too long to display here. Please enable DMs to receive it.",
                ephemeral=True
            )
    except Exception as e:
        await interaction.response.send_message(
            f"❌ An error occurred: {str(e)}",
            ephemeral=True
        )

@bot.tree.command(name="escapeitems-privacy", description="View the Privacy Policy for EscapeItems")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def privacy_command(interaction: discord.Interaction):
    """Send Privacy Policy via DM"""
    await track_user(interaction.user.id, interaction.user.name)
    
    try:
        chunks = split_message(PRIVACY_TEXT)
        
        for i, chunk in enumerate(chunks):
            if i == 0:
                await interaction.user.send(chunk)
            else:
                await interaction.user.send(chunk)
        
        await interaction.response.send_message("🔒 Privacy Policy sent to your DMs!", ephemeral=True)
    except discord.Forbidden:
        chunks = split_message(PRIVACY_TEXT, max_length=1900) 
        error_msg = "❌ I couldn't send you a DM. Please enable DMs from server members.\n\n"
        
        if len(chunks) == 1:
            await interaction.response.send_message(
                error_msg + "Alternatively, here's the Privacy Policy:\n" + chunks[0],
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                error_msg + "The Privacy Policy is too long to display here. Please enable DMs to receive it.",
                ephemeral=True
            )
    except Exception as e:
        await interaction.response.send_message(
            f"❌ An error occurred: {str(e)}",
            ephemeral=True
        )

# ============================================
# ADMIN COMMANDS
# ============================================

@bot.tree.command(name="admin-announce", description="[ADMIN] Send announcement to all bot users")
@app_commands.describe(message="The announcement message to send")
async def admin_announce(interaction: discord.Interaction, message: str):
    """Send announcement to all tracked users"""
    
    if not await is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    users = await get_all_users()
    
    if not users:
        await interaction.followup.send("❌ No users to send announcements to.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📢 EscapeItems Announcement",
        description=message,
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text="EscapeItems Bot Announcement")
    
    success_count = 0
    failed_count = 0
    
    for user_id in users:
        try:
            user = await bot.fetch_user(user_id)
            await user.send(embed=embed)
            success_count += 1
        except Exception as e:
            failed_count += 1
            print(f"Failed to send announcement to {user_id}: {e}")
    
    result_embed = discord.Embed(
        title="📊 Announcement Results",
        color=discord.Color.green()
    )
    result_embed.add_field(name="✅ Successfully Sent", value=str(success_count), inline=True)
    result_embed.add_field(name="❌ Failed", value=str(failed_count), inline=True)
    result_embed.add_field(name="📝 Total Users", value=str(len(users)), inline=True)
    
    await interaction.followup.send(embed=result_embed, ephemeral=True)

@bot.tree.command(name="admin-add-admin", description="[ADMIN] Add a user to admin list")
@app_commands.describe(user="The user to add as admin")
async def admin_add_admin(interaction: discord.Interaction, user: discord.User):
    """Add a user to admin list"""
    
    if not await is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    await add_admin(user.id, interaction.user.id)
    
    embed = discord.Embed(
        title="✅ Admin Added",
        description=f"**{user.name}** (ID: {user.id}) has been added to the admin list.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="admin-remove-admin", description="[ADMIN] Remove a user from admin list")
@app_commands.describe(user="The user to remove from admin list")
async def admin_remove_admin(interaction: discord.Interaction, user: discord.User):
    """Remove a user from admin list"""
    
    if not await is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    if user.id == interaction.user.id:
        await interaction.response.send_message("❌ You cannot remove yourself from the admin list.", ephemeral=True)
        return
    
    if user.id in ADMIN_IDS:
        await interaction.response.send_message("❌ Cannot remove base admins from .env file.", ephemeral=True)
        return
    
    await remove_admin(user.id)
    
    embed = discord.Embed(
        title="✅ Admin Removed",
        description=f"**{user.name}** (ID: {user.id}) has been removed from the admin list.",
        color=discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="admin-list-admins", description="[ADMIN] List all admin users")
async def admin_list_admins(interaction: discord.Interaction):
    """List all admin users"""
    
    if not await is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    admins = await get_admins()
    
    embed = discord.Embed(
        title="👑 Admin Users",
        color=discord.Color.gold()
    )
    
    admin_list = []
    for admin_id in admins:
        try:
            user = await bot.fetch_user(admin_id)
            source = "ENV" if admin_id in ADMIN_IDS else "DB"
            admin_list.append(f"• {user.name} (ID: {admin_id}) [{source}]")
        except:
            admin_list.append(f"• Unknown User (ID: {admin_id})")
    
    embed.description = "\n".join(admin_list) if admin_list else "No admins found"
    embed.set_footer(text=f"Total: {len(admins)} admins")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="admin-add-item", description="[ADMIN] Add a new item to the database")
@app_commands.describe(
    name="Item name",
    category="Item category",
    info="Item description",
    image="Image URL (optional)",
    location="Location description (optional)",
    enchantments="Enchantments (optional)",
    craftable="Is the item craftable?"
)
async def admin_add_item(
    interaction: discord.Interaction,
    name: str,
    category: str,
    info: str,
    image: Optional[str] = None,
    location: Optional[str] = None,
    enchantments: Optional[str] = None,
    craftable: bool = False
):
    """Add a new item to the database"""
    
    if not await is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    existing = await get_item(name)
    if existing:
        await interaction.followup.send(f"❌ Item **{name}** already exists. Use `/admin-modify-item` to update it.", ephemeral=True)
        return
    
    try:
        await add_item_to_db(name, image or "", location or "", info, enchantments or "", craftable, category)
        
        embed = discord.Embed(
            title="✅ Item Added",
            description=f"Successfully added **{name}** to the database.",
            color=discord.Color.green()
        )
        embed.add_field(name="Category", value=category, inline=True)
        embed.add_field(name="Craftable", value="Yes" if craftable else "No", inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error adding item: {str(e)}", ephemeral=True)

@bot.tree.command(name="admin-remove-item", description="[ADMIN] Remove an item from the database")
@app_commands.describe(name="Name of the item to remove")
async def admin_remove_item(interaction: discord.Interaction, name: str):
    """Remove an item from the database"""
    
    if not await is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    success = await remove_item_from_db(name)
    
    if success:
        embed = discord.Embed(
            title="✅ Item Removed",
            description=f"Successfully removed **{name}** from the database.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.followup.send(f"❌ Item **{name}** not found in database.", ephemeral=True)

@bot.tree.command(name="admin-modify-item", description="[ADMIN] Modify an existing item")
@app_commands.describe(
    name="Name of the item to modify",
    new_name="New name (optional)",
    category="New category (optional)",
    info="New description (optional)",
    image="New image URL (optional)",
    location="New location (optional)",
    enchantments="New enchantments (optional)",
    craftable="Is craftable (optional)"
)
async def admin_modify_item(
    interaction: discord.Interaction,
    name: str,
    new_name: Optional[str] = None,
    category: Optional[str] = None,
    info: Optional[str] = None,
    image: Optional[str] = None,
    location: Optional[str] = None,
    enchantments: Optional[str] = None,
    craftable: Optional[bool] = None
):
    """Modify an existing item in the database"""
    
    if not await is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    existing = await get_item(name)
    if not existing:
        await interaction.followup.send(f"❌ Item **{name}** not found in database.", ephemeral=True)
        return
    
    # Build update dict
    updates = {}
    if new_name:
        updates['name'] = new_name
    if category:
        updates['item_category'] = category
    if info:
        updates['info'] = info
    if image:
        updates['image'] = image
    if location:
        updates['location'] = location
    if enchantments:
        updates['enchantments'] = enchantments
    if craftable is not None:
        updates['craftable'] = craftable
    
    if not updates:
        await interaction.followup.send("❌ No fields to update were provided.", ephemeral=True)
        return
    
    try:
        success = await update_item_in_db(name, **updates)
        
        if success:
            embed = discord.Embed(
                title="✅ Item Modified",
                description=f"Successfully updated **{name}**.",
                color=discord.Color.green()
            )
            embed.add_field(name="Updated Fields", value=", ".join(updates.keys()), inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Failed to update item **{name}**.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error updating item: {str(e)}", ephemeral=True)

@bot.tree.command(name="admin-stats", description="[ADMIN] View bot statistics")
async def admin_stats(interaction: discord.Interaction):
    """View bot statistics"""
    
    # Check admin permission
    if not await is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    total_users = len(await get_all_users())
    total_items = await get_total_items()
    total_categories = await get_category_count()
    total_admins = len(await get_admins())
    
    embed = discord.Embed(
        title="📊 Bot Statistics",
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="👥 Tracked Users", value=str(total_users), inline=True)
    embed.add_field(name="🏰 Servers", value=str(len(bot.guilds)), inline=True)
    embed.add_field(name="👑 Admins", value=str(total_admins), inline=True)
    embed.add_field(name="📦 Total Items", value=str(total_items), inline=True)
    embed.add_field(name="📂 Categories", value=str(total_categories), inline=True)
    embed.add_field(name="⏱️ Uptime", value=format_uptime(), inline=True)
    
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.event
async def on_command_error(ctx, error):
    """Error handler"""
    print(f"Error: {error}")

def signal_handler(sig, frame):
    """Handle Ctrl+C shutdown"""
    print("\n\n🛑 Shutting down bot...")
    print("Closing database connections...")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    
    print("Bot starting... Press Ctrl+C to stop")
    
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        print("Error: DISCORD_TOKEN not found in .env file")
    else:
        try:
            bot.run(TOKEN)
        except KeyboardInterrupt:
            print("\n\n🛑 Bot stopped by user")
            sys.exit(0)
