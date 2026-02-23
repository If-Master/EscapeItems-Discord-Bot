import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
COMMAND_PREFIX: str = "!"

DB_CONFIG: dict = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "escapesystemitems"),
    "user":     os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port":     int(os.getenv("DB_PORT", 5432)),
}

ADMIN_IDS: list[int] = [
    int(i.strip())
    for i in os.getenv("ADMIN_USER_IDS", "").split(",")
    if i.strip()
]

ITEM_CATEGORIES: list[str] = [
    "Weapons", "Tools", "Spawner",
    "Potions", "Wings & Others", "Spawn Eggs",
]

TOS_TEXT = """**Terms of Service for EscapeItems**
*Last Updated: February 2026*

**1. Description of Service**
EscapeItems is a Discord bot for the EscapeSystem Minecraft server. It provides:
• Custom item lookup with descriptions, locations, and crafting recipes
• A farm profit calculator using NBT Worth Scanner prices
• An item price reference list
• Admin tools for managing bot content

**2. Acceptable Use**
You may use this bot for:
• Looking up item information and categories
• Calculating farm profits and referencing item prices
• Browsing crafting recipes and item locations

You may NOT:
• Attempt to exploit, hack, or abuse the bot in any way
• Submit malicious input to manipulate bot behaviour
• Spam commands or attempt to overload the bot
• Use the bot to harass other users

**3. Availability**
• The bot is provided "as is" with no uptime guarantees
• We may take the bot offline for maintenance at any time without notice
• We reserve the right to restrict or terminate access for any user or server

**4. Data Accuracy**
• Item information and prices are provided for reference only
• NBT Worth Scanner prices are a snapshot and may not reflect current in-game rates
• We do not guarantee the accuracy or completeness of any data
• Game updates may make bot data outdated

**5. Admin Access**
• Admin users have elevated permissions to manage bot content
• Admin access is granted manually and can be revoked at any time
• Abuse of admin privileges will result in immediate removal

**6. Changes to Terms**
We may update these terms at any time. Continued use of the bot constitutes acceptance of the updated terms.

**7. Contact**
For questions or concerns: Contact **If_Master** on Discord
"""

PRIVACY_TEXT = """**Privacy Policy for EscapeItems**
*Last Updated: February 2026*

**1. Information We Collect**

*Automatically collected when you use the bot:*
• Discord User ID - used to track interactions and admin permissions
• Discord Username - displayed in command responses and embed footers
• Server IDs - used for bot statistics (count only, no server content stored)

*Never collected:*
• Message content outside of direct bot commands
• Private conversations
• Personal information, IP addresses, or email addresses
• Payment or financial information

**2. How We Use Your Information**
• To display your username in command responses
• To verify admin permissions
• To send announcements via DM (only from admin-initiated broadcasts)
• To track bot usage statistics (user count, server count)
• To debug errors and improve the bot

**3. What We Store**

*Database contents:*
• Item data - names, descriptions, images, locations, crafting recipes (game data only)
• User IDs and usernames - stored to enable user tracking and the admin system

*We do NOT store:*
• Command history or search queries
• DM message content
• Any financial or personal information

**4. Data Sharing**
We do not sell, share, or distribute your data to any third parties. Your data is used solely to operate the bot.

**5. Third-Party Services**
This bot uses:
• **Discord API** - subject to Discord's own Privacy Policy (discord.com/privacy)
• **PostgreSQL** - a self-hosted database containing only item and user ID data

**6. Data Security**
• Database access is password-protected
• The bot token is stored securely in environment variables, never in code
• All user input is scanned and sanitised to prevent injection attacks

**7. Your Rights**
You have the right to:
• Stop using the bot at any time
• Request information about what data we hold on you
• Request deletion of your stored data (User ID and username)
• Report concerns to If_Master on Discord

**8. Data Retention**
• User IDs and usernames are stored in the database for as long as you use the bot
• To request deletion of your data, contact If_Master directly

**9. Children's Privacy**
This bot is designed for general audiences. We do not knowingly collect data from users under 13. If you believe a minor's data has been stored, please contact us for removal.

**10. Changes to This Policy**
We may update this policy at any time. Continued use of the bot after changes constitutes acceptance.

**11. Contact**
For any privacy concerns: Contact **If_Master** on Discord
"""
