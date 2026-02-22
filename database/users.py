from database.pool import get_pool
from config import ADMIN_IDS


async def create_tables() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_users (
                user_id    BIGINT PRIMARY KEY,
                username   TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                user_id  BIGINT PRIMARY KEY,
                added_by BIGINT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


async def track_user(user_id: int, username: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO bot_users (user_id, username, first_seen, last_seen)
            VALUES ($1, $2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
                username  = $2,
                last_seen = CURRENT_TIMESTAMP
        """, user_id, username)


async def get_all_user_ids() -> list[int]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM bot_users")
        return [r["user_id"] for r in rows]


async def is_admin(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM admin_users WHERE user_id = $1)",
            user_id,
        )


async def add_admin(user_id: int, added_by: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO admin_users (user_id, added_by)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO NOTHING
        """, user_id, added_by)


async def remove_admin(user_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM admin_users WHERE user_id = $1", user_id
        )


async def get_all_admins() -> list[int]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM admin_users")
        db_admins = [r["user_id"] for r in rows]
        return list(set(ADMIN_IDS + db_admins))
