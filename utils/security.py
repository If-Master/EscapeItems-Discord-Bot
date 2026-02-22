from __future__ import annotations

import os
import re

import discord

_PATTERNS: list[tuple[re.Pattern, str]] = [

    (re.compile(r"\.env",                                         re.I), "env file reference"),
    (re.compile(r"\benv(ironment)?\s*(var|file|config|variable)s?\b", re.I), "env variable probe"),
    (re.compile(r"os\s*\.\s*getenv",                              re.I), "getenv call"),
    (re.compile(r"os\s*\.\s*environ",                             re.I), "environ access"),
    (re.compile(r"\bDB_(HOST|NAME|USER|PASS(?:WORD)?|PORT)\b",    re.I), "db credential key"),
    (re.compile(r"\bdiscord[_\s\-]?token\b",                      re.I), "token reference"),
    (re.compile(r"\bbot[_\s\-]?token\b",                          re.I), "token reference"),
    (re.compile(r"\bsecret[_\s\-]?key\b",                         re.I), "secret key reference"),
    (re.compile(r"\bapi[_\s\-]?key\b",                            re.I), "api key reference"),
    (re.compile(r"\bpassword\b",                                  re.I), "password reference"),
    (re.compile(r"\bcredential",                                  re.I), "credential reference"),
    (re.compile(r"\bprivate[_\s\-]?key\b",                        re.I), "private key reference"),
    (re.compile(r"\badmin[_\s\-]?user[_\s\-]?ids?\b",             re.I), "admin id probe"),
    (re.compile(r"MTx|NDx|OTx|NTx",                               re.I), "possible token fragment"),

    (re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?|context)", re.I), "prompt injection"),
    (re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?)",             re.I), "prompt injection"),
    (re.compile(r"forget\s+(all\s+)?(previous|prior|your)\s+(instructions?|prompts?|training)",        re.I), "prompt injection"),
    (re.compile(r"you\s+are\s+now\s+(a\s+|an\s+)?(?!looking|aware|online)",                           re.I), "role override attempt"),
    (re.compile(r"(new|your\s+new)\s+(role|persona|identity|instructions?|prime\s+directive)",         re.I), "role override attempt"),
    (re.compile(r"(act|behave|respond|pretend)\s+(as|like)\s+(if\s+you\s+(are|were)\s+|a\s+|an\s+)",  re.I), "persona hijack"),
    (re.compile(r"\bsystem\s*(prompt|message|instruction)\b",     re.I), "system prompt probe"),
    (re.compile(r"\bjailbreak\b",                                 re.I), "jailbreak attempt"),
    (re.compile(r"\bdo\s+anything\s+now\b",                       re.I), "DAN attempt"),
    (re.compile(r"\b(DAN|DUDE|AIM|STAN|KEVIN)\b",                 re.I), "jailbreak persona"),
    (re.compile(r"developer\s+mode",                              re.I), "developer mode attempt"),
    (re.compile(r"(enable|activate|unlock)\s+(dev|developer|god|admin|unrestricted|unsafe)\s*mode", re.I), "mode unlock attempt"),

    (re.compile(
        r"(show|print|reveal|expose|leak|dump|return|output|give\s+me|tell\s+me|what\s+is)\s+"
        r"(the\s+)?(token|password|secret|config(uration)?|env(ironment)?|database|db|credentials?|key)",
        re.I), "data exfiltration probe"),
    (re.compile(r"(read|cat|open|load|import)\s+(the\s+)?\.env",  re.I), "file read probe"),
    (re.compile(r"config\s*\[",                                   re.I), "config access attempt"),
    (re.compile(r"DB_CONFIG",                                     re.I), "db config probe"),
    (re.compile(r"ADMIN_IDS",                                     re.I), "admin ids probe"),

    (re.compile(r"\bsubprocess\b",                                re.I), "subprocess probe"),
    (re.compile(r"\bos\.system\b",                                re.I), "os.system probe"),
    (re.compile(r"\bexec\s*\(",                                   re.I), "exec injection"),
    (re.compile(r"\beval\s*\(",                                   re.I), "eval injection"),
    (re.compile(r"\b__import__\b",                                re.I), "import injection"),
    (re.compile(r"\b__builtins__\b",                              re.I), "builtins probe"),
    (re.compile(r"\bpickle\b",                                    re.I), "deserialisation probe"),
    (re.compile(r"\bgetattr\s*\(",                                re.I), "attribute probe"),
    (re.compile(r"\bglobals\s*\(\s*\)",                           re.I), "globals probe"),
    (re.compile(r"\blocals\s*\(\s*\)",                            re.I), "locals probe"),

    (re.compile(r"'\s*;\s*(drop|delete|insert|update|truncate|alter)\s", re.I), "sql injection"),
    (re.compile(r"(union\s+(all\s+)?select|or\s+1\s*=\s*1|and\s+1\s*=\s*1)", re.I), "sql injection"),
    (re.compile(r"--\s*(drop|delete|insert|select)",              re.I), "sql comment injection"),
]

_SENSITIVE_ENV_KEYS: set[str] = {
    "DISCORD_TOKEN",
    "DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_PORT",
    "ADMIN_USER_IDS",
}


class SecurityViolation(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def check_input(text: str) -> None:
    if not text:
        return
    for pattern, reason in _PATTERNS:
        if pattern.search(text):
            raise SecurityViolation(reason)


def sanitize_output(text: str) -> str:
    for key in _SENSITIVE_ENV_KEYS:
        value = os.getenv(key)
        if value and len(value) > 3:
            text = text.replace(value, "[REDACTED]")
    return text



_REFUSAL = "No, I'm not allowed to hand you that information."


async def _send_refusal(interaction: discord.Interaction, deferred: bool) -> None:
    try:
        if deferred:
            await interaction.followup.send(_REFUSAL, ephemeral=True)
        else:
            await interaction.response.send_message(_REFUSAL, ephemeral=True)
    except discord.InteractionResponded:
        await interaction.followup.send(_REFUSAL, ephemeral=True)


def _log_violation(
    interaction: discord.Interaction, reason: str, field_value: str
) -> None:
    print(
        f"[SECURITY BLOCK] user={interaction.user} id={interaction.user.id} "
        f"command={interaction.command.name if interaction.command else 'unknown'} "
        f"reason={reason!r} input={field_value[:120]!r}"
    )


async def secure_check(
    interaction: discord.Interaction,
    *fields: str | None,
    deferred: bool = False,
) -> bool:
    for field in fields:
        if field is None:
            continue
        raw = str(field)
        try:
            check_input(raw)
        except SecurityViolation as exc:
            _log_violation(interaction, exc.reason, raw)
            await _send_refusal(interaction, deferred=deferred)
            return False
    return True