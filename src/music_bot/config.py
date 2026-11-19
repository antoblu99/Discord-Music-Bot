"""Configuration is read at startup; credentials never belong in source files."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    token: str = field(repr=False)
    guild_id: int
    idle_timeout: int = 180
    queue_limit: int = 50
    max_duration: int = 3600

    @classmethod
    def from_env(cls):
        token = os.environ.get("DISCORD_TOKEN", "").strip()
        if not token:
            raise ValueError("DISCORD_TOKEN is required")
        values = {}
        for key, default in (
            ("DISCORD_GUILD_ID", None),
            ("IDLE_TIMEOUT", "180"),
            ("QUEUE_LIMIT", "50"),
            ("MAX_DURATION", "3600"),
        ):
            raw = os.environ.get(key, default)
            if raw is None or not raw.isdecimal() or int(raw) <= 0:
                raise ValueError(f"{key} must be a positive integer")
            values[key] = int(raw)
        return cls(token, *values.values())
