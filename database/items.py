import json
from database.pool import get_pool


async def create_tables() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id            SERIAL PRIMARY KEY,
                name          TEXT UNIQUE NOT NULL,
                image         TEXT,
                location      TEXT,
                info          TEXT,
                enchantments  TEXT,
                craftable     BOOLEAN DEFAULT FALSE,
                item_category TEXT,
                craft_data    TEXT
            )
        """)


async def get_item(name: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id, name, image, location, info, enchantments,
                   craftable, item_category, craft_data
            FROM items
            WHERE LOWER(name) = LOWER($1)
        """, name)
        return dict(row) if row else None


async def search_similar_items(term: str, limit: int = 10) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT name, item_category FROM items
            WHERE LOWER(name) LIKE LOWER($1)
            ORDER BY
                CASE
                    WHEN LOWER(name) = LOWER($2)        THEN 0
                    WHEN LOWER(name) LIKE LOWER($3)     THEN 1
                    ELSE 2
                END, name
            LIMIT $4
        """, f"%{term}%", term, f"{term}%", limit)
        return [{"name": r["name"], "category": r["item_category"]} for r in rows]


async def get_items_by_category(category: str) -> list[str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT name FROM items WHERE item_category = $1 ORDER BY name",
            category,
        )
        return [r["name"] for r in rows]


async def get_total_item_count() -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM items")


async def get_category_count() -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(DISTINCT item_category) FROM items"
        )


async def add_item(
    name: str, image: str, location: str, info: str,
    enchantments: str, craftable: bool, category: str,
    craft_data: dict | None = None,
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO items
                (name, image, location, info, enchantments, craftable, item_category, craft_data)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """, name, image, location, info, enchantments, craftable, category,
            json.dumps(craft_data) if craft_data else None)


async def remove_item(name: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM items WHERE LOWER(name) = LOWER($1)", name
        )
        return result != "DELETE 0"


async def update_item(name: str, **kwargs) -> bool:
    if not kwargs:
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        fields, values, idx = [], [], 1
        for field, value in kwargs.items():
            if value is not None:
                if field == "craft_data" and isinstance(value, dict):
                    value = json.dumps(value)
                fields.append(f"{field} = ${idx}")
                values.append(value)
                idx += 1
        if not fields:
            return False
        values.append(name)
        query = (
            f"UPDATE items SET {', '.join(fields)} "
            f"WHERE LOWER(name) = LOWER(${idx})"
        )
        result = await conn.execute(query, *values)
        return result != "UPDATE 0"
