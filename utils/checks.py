import discord
from database import users as users_db
from database import shops as shops_db


async def require_admin(interaction: discord.Interaction) -> bool:
    if not await users_db.is_admin(interaction.user.id):
        await interaction.response.send_message(
            "You don't have permission to use this command.", ephemeral=True
        )
        return False
    return True
