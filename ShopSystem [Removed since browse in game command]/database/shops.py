from database.pool import get_pool
from config import DEFAULT_SHOP_SLOTS


async def create_tables() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS plots (
                plot_x   INTEGER NOT NULL,
                plot_z   INTEGER NOT NULL,
                owner_id BIGINT NOT NULL,
                PRIMARY KEY (plot_x, plot_z)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS shops (
                id          SERIAL PRIMARY KEY,
                owner_id    BIGINT NOT NULL,
                shop_name   TEXT NOT NULL,
                plot_x      INTEGER NOT NULL,
                plot_z      INTEGER NOT NULL,
                position    INTEGER NOT NULL,
                is_promoted BOOLEAN DEFAULT FALSE,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (plot_x, plot_z)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS shop_items (
                id         SERIAL PRIMARY KEY,
                shop_id    INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
                item_name  TEXT NOT NULL,
                is_selling BOOLEAN NOT NULL,
                is_shulker BOOLEAN DEFAULT FALSE,
                quantity   INTEGER NOT NULL,
                price      NUMERIC(12,2) NOT NULL,
                is_draft   BOOLEAN DEFAULT FALSE
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS shop_blacklist (
                shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
                user_id BIGINT NOT NULL,
                PRIMARY KEY (shop_id, user_id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS global_shop_blacklist (
                user_id   BIGINT PRIMARY KEY,
                reason    TEXT,
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS shop_slots (
                user_id     BIGINT PRIMARY KEY,
                extra_slots INTEGER DEFAULT 0
            )
        """)


async def register_plot(x: int, z: int, owner_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO plots (plot_x, plot_z, owner_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (plot_x, plot_z) DO UPDATE SET owner_id = $3
        """, x, z, owner_id)


async def get_plot_owner(x: int, z: int) -> int | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT owner_id FROM plots WHERE plot_x = $1 AND plot_z = $2", x, z
        )


async def delete_plot(x: int, z: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM plots WHERE plot_x = $1 AND plot_z = $2", x, z
        )


async def get_max_shops(user_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        extra = await conn.fetchval(
            "SELECT extra_slots FROM shop_slots WHERE user_id = $1", user_id
        ) or 0
        return DEFAULT_SHOP_SLOTS + extra


async def add_slots(user_id: int, amount: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        new_extra = await conn.fetchval("""
            INSERT INTO shop_slots (user_id, extra_slots)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE
                SET extra_slots = shop_slots.extra_slots + $2
            RETURNING extra_slots
        """, user_id, amount)
        return DEFAULT_SHOP_SLOTS + new_extra


async def get_shop_count(user_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM shops WHERE owner_id = $1", user_id
        )


async def create_shop(
    owner_id: int, shop_name: str, plot_x: int, plot_z: int
) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            existing = await conn.fetchrow(
                "SELECT id FROM shops WHERE plot_x = $1 AND plot_z = $2",
                plot_x, plot_z,
            )
            if existing:
                raise ValueError(f"A shop already exists at X={plot_x}, Z={plot_z}.")

            existing_shops = await conn.fetch(
                "SELECT id FROM shops WHERE owner_id = $1 ORDER BY position",
                owner_id
            )
            
            for idx, shop_row in enumerate(existing_shops, start=1):
                await conn.execute(
                    "UPDATE shops SET position = $1 WHERE id = $2",
                    idx, shop_row['id']
                )
            
            next_pos = len(existing_shops) + 1

            return await conn.fetchval("""
                INSERT INTO shops (owner_id, shop_name, plot_x, plot_z, position)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            """, owner_id, shop_name, plot_x, plot_z, next_pos)


async def get_shop_by_position(owner_id: int, position: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM shops WHERE owner_id = $1 AND position = $2",
            owner_id, position,
        )
        return dict(row) if row else None


async def get_shop(shop_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM shops WHERE id = $1", shop_id
        )
        return dict(row) if row else None


async def get_shop_at_plot(x: int, z: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM shops WHERE plot_x = $1 AND plot_z = $2", x, z
        )
        return dict(row) if row else None


async def get_shops_by_owner(owner_id: int) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM shops WHERE owner_id = $1 ORDER BY position", owner_id
        )
        return [dict(r) for r in rows]


async def get_all_shops(include_promoted_first: bool = True) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        order = "is_promoted DESC, id ASC" if include_promoted_first else "id ASC"
        rows = await conn.fetch(f"SELECT * FROM shops ORDER BY {order}")
        return [dict(r) for r in rows]


async def delete_shop(shop_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():

            shop = await conn.fetchrow(
                "SELECT owner_id, position FROM shops WHERE id = $1", shop_id
            )
            if not shop:
                return False

            await conn.execute("DELETE FROM shops WHERE id = $1", shop_id)

            remaining_shops = await conn.fetch(
                "SELECT id FROM shops WHERE owner_id = $1 ORDER BY position",
                shop["owner_id"]
            )
            
            for idx, shop_row in enumerate(remaining_shops, start=1):
                await conn.execute(
                    "UPDATE shops SET position = $1 WHERE id = $2",
                    idx, shop_row['id']
                )

            await _renumber_all_shop_ids(conn)

            return True


async def _renumber_all_shop_ids(conn) -> None:
    
    all_shops = await conn.fetch("SELECT * FROM shops ORDER BY id")
    
    if not all_shops:
        await conn.execute("ALTER SEQUENCE shops_id_seq RESTART WITH 1")
        return
    
    id_mapping = {}
    for new_id, shop in enumerate(all_shops, start=1):
        id_mapping[shop['id']] = new_id
    
    if all(shop['id'] == idx for idx, shop in enumerate(all_shops, start=1)):
        next_id = len(all_shops) + 1
        await conn.execute(f"ALTER SEQUENCE shops_id_seq RESTART WITH {next_id}")
        return
    
    for old_id in id_mapping.keys():
        await conn.execute(
            "UPDATE shops SET id = $1 WHERE id = $2",
            -old_id, old_id
        )
        await conn.execute(
            "UPDATE shop_items SET shop_id = $1 WHERE shop_id = $2",
            -old_id, old_id
        )
        await conn.execute(
            "UPDATE shop_blacklist SET shop_id = $1 WHERE shop_id = $2",
            -old_id, old_id
        )
    
    for old_id, new_id in id_mapping.items():
        await conn.execute(
            "UPDATE shops SET id = $1 WHERE id = $2",
            new_id, -old_id
        )
        await conn.execute(
            "UPDATE shop_items SET shop_id = $1 WHERE shop_id = $2",
            new_id, -old_id
        )
        await conn.execute(
            "UPDATE shop_blacklist SET shop_id = $1 WHERE shop_id = $2",
            new_id, -old_id
        )
    
    next_id = len(all_shops) + 1
    await conn.execute(f"ALTER SEQUENCE shops_id_seq RESTART WITH {next_id}")


async def update_shop(shop_id: int, **kwargs) -> bool:
    if not kwargs:
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        fields, values, idx = [], [], 1
        for field, value in kwargs.items():
            fields.append(f"{field} = ${idx}")
            values.append(value)
            idx += 1
        values.append(shop_id)
        result = await conn.execute(
            f"UPDATE shops SET {', '.join(fields)} WHERE id = ${idx}",
            *values,
        )
        return result != "UPDATE 0"


async def promote_shop(shop_id: int) -> bool:
    return await update_shop(shop_id, is_promoted=True)


async def demote_shop(shop_id: int) -> bool:
    return await update_shop(shop_id, is_promoted=False)


async def get_shop_items(
    shop_id: int, include_drafts: bool = False
) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM shop_items WHERE shop_id = $1"
        if not include_drafts:
            query += " AND is_draft = FALSE"
        query += " ORDER BY id"
        rows = await conn.fetch(query, shop_id)
        return [dict(r) for r in rows]


async def add_shop_item(
    shop_id: int, item_name: str, is_selling: bool,
    is_shulker: bool, quantity: int, price: float, is_draft: bool,
) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("""
            INSERT INTO shop_items
                (shop_id, item_name, is_selling, is_shulker, quantity, price, is_draft)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """, shop_id, item_name, is_selling, is_shulker, quantity, price, is_draft)


async def update_shop_item(item_id: int, **kwargs) -> bool:
    if not kwargs:
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        fields, values, idx = [], [], 1
        for field, value in kwargs.items():
            fields.append(f"{field} = ${idx}")
            values.append(value)
            idx += 1
        values.append(item_id)
        result = await conn.execute(
            f"UPDATE shop_items SET {', '.join(fields)} WHERE id = ${idx}",
            *values,
        )
        return result != "UPDATE 0"


async def remove_shop_item(item_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM shop_items WHERE id = $1", item_id
        )
        return result != "DELETE 0"


async def count_shop_items(shop_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM shop_items WHERE shop_id = $1", shop_id
        )


async def search_items_across_shops(
    item_name: str, viewer_id: int
) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT si.*, s.shop_name, s.owner_id, s.id AS shop_id
            FROM shop_items si
            JOIN shops s ON s.id = si.shop_id
            WHERE LOWER(si.item_name) LIKE LOWER($1)
              AND si.is_draft = FALSE
              AND NOT EXISTS (
                  SELECT 1 FROM shop_blacklist sb
                  WHERE sb.shop_id = s.id AND sb.user_id = $2
              )
            ORDER BY si.price ASC
        """, f"%{item_name}%", viewer_id)
        return [dict(r) for r in rows]


async def add_shop_blacklist(shop_id: int, user_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO shop_blacklist (shop_id, user_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
        """, shop_id, user_id)


async def remove_shop_blacklist(shop_id: int, user_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM shop_blacklist WHERE shop_id = $1 AND user_id = $2",
            shop_id, user_id,
        )


async def is_shop_blacklisted(shop_id: int, user_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM shop_blacklist
                WHERE shop_id = $1 AND user_id = $2
            )
        """, shop_id, user_id)


async def add_global_blacklist(user_id: int, reason: str = "") -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO global_shop_blacklist (user_id, reason)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET reason = $2
        """, user_id, reason)


async def remove_global_blacklist(user_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM global_shop_blacklist WHERE user_id = $1", user_id
        )


async def is_globally_blacklisted(user_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM global_shop_blacklist WHERE user_id = $1
            )
        """, user_id)
