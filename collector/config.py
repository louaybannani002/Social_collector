"""Application settings, loaded from environment variables (or a .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass

try:  # python-dotenv is optional: plain environment variables work too
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


class ConfigError(Exception):
    """Raised when a required setting is missing."""


def mongo_uri_from_env() -> str:
    """Read either the app's documented Mongo setting or the Atlas-style alias."""
    return os.getenv("MONGO_URI", "").strip() or os.getenv(
        "MONGODB_URI", "mongodb://localhost:27017"
    ).strip()


@dataclass(frozen=True)
class Settings:
    access_token: str
    graph_version: str = "v23.0"
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "social_collector"
    request_timeout: int = 20
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("META_ACCESS_TOKEN", "").strip()
        if not token:
            raise ConfigError("META_ACCESS_TOKEN is not set (see .env.example).")
        return cls(
            access_token=token,
            graph_version=os.getenv("GRAPH_API_VERSION", cls.graph_version),
            mongo_uri=mongo_uri_from_env(),
            mongo_db=os.getenv("MONGO_DB", cls.mongo_db),
        )
