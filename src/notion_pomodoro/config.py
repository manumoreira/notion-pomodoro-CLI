"""Configuration loader and manager for Notion Pomodoro CLI."""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import dotenv_values, set_key

GLOBAL_CONFIG_DIR = Path.home() / ".config" / "notion-pomodoro"
GLOBAL_ENV_FILE = GLOBAL_CONFIG_DIR / ".env"
LOCAL_ENV_FILE = Path(".env")


@dataclass
class Config:
    """Application configuration settings."""
    api_key: Optional[str] = None
    database_id: Optional[str] = None
    work_minutes: int = 25
    short_break_minutes: int = 5
    long_break_minutes: int = 15
    cycles: int = 4
    config_source: Optional[str] = None

    @property
    def is_configured(self) -> bool:
        """Check if essential Notion credentials are present."""
        return bool(self.api_key and self.database_id)


def clean_database_id(raw_id_or_url: str) -> str:
    """
    Extract clean 32-character database ID from a raw ID or full Notion database URL.
    
    Examples:
        - 'a1b2c3d4e5f67890123456789abcdef0'
        - 'a1b2c3d4-e5f6-7890-1234-56789abcdef0'
        - 'https://www.notion.so/workspace/My-Database-a1b2c3d4e5f67890123456789abcdef0?v=...'
    """
    cleaned = raw_id_or_url.strip()
    # Strip URL query params if present
    if "?" in cleaned:
        cleaned = cleaned.split("?")[0]
    # Extract 32 hex characters if part of a URL
    match = re.search(r"([0-9a-fA-F]{32})", cleaned.replace("-", ""))
    if match:
        return match.group(1)
    # If standard UUID with dashes
    uuid_match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", cleaned)
    if uuid_match:
        return uuid_match.group(1).replace("-", "")
    return cleaned.replace("-", "")


def get_config_file_path() -> Path:
    """Find the active config file: local .env if exists, otherwise global."""
    if LOCAL_ENV_FILE.exists():
        return LOCAL_ENV_FILE
    if GLOBAL_ENV_FILE.exists():
        return GLOBAL_ENV_FILE
    return LOCAL_ENV_FILE


def load_config() -> Config:
    """Load configuration from environment or .env files."""
    env_path = None
    env_vals = {}

    # 1. Try local .env
    if LOCAL_ENV_FILE.exists():
        env_path = str(LOCAL_ENV_FILE.resolve())
        env_vals = dotenv_values(LOCAL_ENV_FILE)
    # 2. Try global config .env
    elif GLOBAL_ENV_FILE.exists():
        env_path = str(GLOBAL_ENV_FILE.resolve())
        env_vals = dotenv_values(GLOBAL_ENV_FILE)

    # 3. Environment variables override .env file values
    api_key = os.getenv("NOTION_API_KEY") or env_vals.get("NOTION_API_KEY")
    raw_db_id = os.getenv("NOTION_DATABASE_ID") or env_vals.get("NOTION_DATABASE_ID")
    db_id = clean_database_id(raw_db_id) if raw_db_id else None

    def _get_int(key: str, default: int) -> int:
        val = os.getenv(key) or env_vals.get(key)
        if val is not None:
            try:
                return int(val)
            except ValueError:
                pass
        return default

    work_minutes = _get_int("POMODORO_WORK_MINUTES", 25)
    short_break_minutes = _get_int("POMODORO_SHORT_BREAK_MINUTES", 5)
    long_break_minutes = _get_int("POMODORO_LONG_BREAK_MINUTES", 15)
    cycles = _get_int("POMODORO_CYCLES", 4)

    return Config(
        api_key=api_key.strip() if api_key else None,
        database_id=db_id,
        work_minutes=work_minutes,
        short_break_minutes=short_break_minutes,
        long_break_minutes=long_break_minutes,
        cycles=cycles,
        config_source=env_path or "Environment / Defaults"
    )


def save_config(
    api_key: str,
    database_id: str,
    work_minutes: int = 25,
    short_break_minutes: int = 5,
    long_break_minutes: int = 15,
    cycles: int = 4,
    use_global: bool = False
) -> Path:
    """Save configuration values to .env file."""
    clean_db_id = clean_database_id(database_id)

    if use_global:
        GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        target_file = GLOBAL_ENV_FILE
    else:
        target_file = LOCAL_ENV_FILE

    if not target_file.exists():
        target_file.touch(mode=0o600)

    target_str = str(target_file)
    set_key(target_str, "NOTION_API_KEY", api_key.strip(), quote_mode="never")
    set_key(target_str, "NOTION_DATABASE_ID", clean_db_id, quote_mode="never")
    set_key(target_str, "POMODORO_WORK_MINUTES", str(work_minutes), quote_mode="never")
    set_key(target_str, "POMODORO_SHORT_BREAK_MINUTES", str(short_break_minutes), quote_mode="never")
    set_key(target_str, "POMODORO_LONG_BREAK_MINUTES", str(long_break_minutes), quote_mode="never")
    set_key(target_str, "POMODORO_CYCLES", str(cycles), quote_mode="never")

    return target_file
