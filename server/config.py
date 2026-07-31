from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

DEFAULT_PROVIDER_ORDER = ("tickflow", "akshare", "baostock", "sina", "mock")


def get_env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name) or _read_dotenv().get(name) or default


def get_provider_order(default: tuple[str, ...] = DEFAULT_PROVIDER_ORDER) -> tuple[str, ...]:
    raw = get_env("LEEK_PROVIDER_ORDER", ",".join(default)) or ""
    names = tuple(item.strip().lower() for item in raw.split(",") if item.strip())
    return names or default


def _read_dotenv() -> dict[str, str]:
    if not ENV_PATH.exists():
        return {}
    values: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values
