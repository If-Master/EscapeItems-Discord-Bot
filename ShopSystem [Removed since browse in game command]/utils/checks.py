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


async def require_not_globally_blacklisted(
    interaction: discord.Interaction,
) -> bool:
    if await shops_db.is_globally_blacklisted(interaction.user.id):
        await interaction.response.send_message(
            "You have been banned from using shop commands.", ephemeral=True
        )
        return False
    return True


async def require_shop_owner(
    interaction: discord.Interaction, shop: dict
) -> bool:
    if shop["owner_id"] != interaction.user.id:
        if not await users_db.is_admin(interaction.user.id):
            await interaction.response.send_message(
                "You do not own this shop.", ephemeral=True
            )
            return False
    return True
