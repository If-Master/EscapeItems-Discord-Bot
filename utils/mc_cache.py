from __future__ import annotations

import asyncio
import json
import re
import time
from difflib import SequenceMatcher
from pathlib import Path

import aiohttp

_MC_ITEMS_URL     = "https://raw.githubusercontent.com/PrismarineJS/minecraft-data/master/data/pc/1.21.4/items.json"
_ASSET_BASE       = "https://raw.githubusercontent.com/InventivetalentDev/minecraft-assets/1.21.4/assets/minecraft/textures/item/{}.png"
_ITEMS_CACHE_FILE = Path("mc_items_cache.json")
_CACHE_TTL        = 86_400 * 7

_mc_items:     list[dict]       = []
_mc_loaded:    bool             = False
_mc_lock                        = asyncio.Lock()
_icon_mem:     dict[str, bytes] = {}

_STRIP_SUFFIXES = re.compile(
    r"\s*(recipe|block|item|s\b|es\b|\(s\)|\(es\))",
    re.IGNORECASE,
)


async def ensure_items() -> None:
    global _mc_items, _mc_loaded
    if _mc_loaded:
        return
    async with _mc_lock:
        if _mc_loaded:
            return
        if _ITEMS_CACHE_FILE.exists():
            try:
                data = json.loads(_ITEMS_CACHE_FILE.read_text())
                if time.time() - data.get("ts", 0) < _CACHE_TTL:
                    _mc_items  = data["items"]
                    _mc_loaded = True
                    return
            except Exception:
                pass
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(_MC_ITEMS_URL, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    raw = await r.json(content_type=None)
            _mc_items = [
                {
                    "name":    e["name"],
                    "display": e["name"].replace("_", " ").title(),
                    "image":   _ASSET_BASE.format(e["name"]),
                }
                for e in raw
            ]
            _ITEMS_CACHE_FILE.write_text(json.dumps({"ts": time.time(), "items": _mc_items}))
        except Exception as exc:
            print(f"[mc_cache] fetch failed: {exc}")
        _mc_loaded = True


def _score(query: str, item: dict) -> float:
    q, n, m = query.lower().strip(), item["display"].lower(), item["name"].lower()
    if n == q or m == q:
        return 1.0
    if n.startswith(q) or m.startswith(q):
        return 0.9
    if q in n or q in m:
        return 0.75
    return max(SequenceMatcher(None, q, n).ratio(), SequenceMatcher(None, q, m).ratio())


async def find_mc_items(query: str, limit: int = 6, threshold: float = 0.45) -> list[dict]:
    await ensure_items()
    scored = sorted(((_score(query, i), i) for i in _mc_items), key=lambda x: -x[0])
    return [i for s, i in scored if s >= threshold][:limit]


def find_mc_item_sync(query: str, threshold: float = 0.55) -> dict | None:
    if not _mc_items:
        return None
    cleaned = _STRIP_SUFFIXES.sub("", query).strip()
    for candidate in [query, cleaned]:
        scored = sorted(((_score(candidate, i), i) for i in _mc_items), key=lambda x: -x[0])
        if scored and scored[0][0] >= threshold:
            return scored[0][1]
    return None


async def fetch_icon(url: str) -> bytes | None:
    if url in _icon_mem:
        return _icon_mem[url]
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    data = await r.read()
                    _icon_mem[url] = data
                    return data
    except Exception:
        pass
    return None