"""Unit tests for configuration loading, saving, and ID cleaning."""

import os
from pathlib import Path
from notion_pomodoro.config import Config, clean_database_id, load_config, save_config


def test_clean_database_id_raw():
    raw = "a1b2c3d4e5f67890123456789abcdef0"
    assert clean_database_id(raw) == "a1b2c3d4e5f67890123456789abcdef0"


def test_clean_database_id_uuid():
    uuid_str = "a1b2c3d4-e5f6-7890-1234-56789abcdef0"
    assert clean_database_id(uuid_str) == "a1b2c3d4e5f67890123456789abcdef0"


def test_clean_database_id_url():
    url = "https://www.notion.so/myworkspace/a1b2c3d4e5f67890123456789abcdef0?v=999888"
    assert clean_database_id(url) == "a1b2c3d4e5f67890123456789abcdef0"


def test_save_and_load_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env_file = tmp_path / ".env"

    save_config(
        api_key="secret_test_key_123",
        database_id="a1b2c3d4e5f67890123456789abcdef0",
        work_minutes=30,
        short_break_minutes=6,
        long_break_minutes=20,
        cycles=5,
        use_global=False,
    )

    assert env_file.exists()
    
    cfg = load_config()
    assert cfg.api_key == "secret_test_key_123"
    assert cfg.database_id == "a1b2c3d4e5f67890123456789abcdef0"
    assert cfg.work_minutes == 30
    assert cfg.short_break_minutes == 6
    assert cfg.long_break_minutes == 20
    assert cfg.cycles == 5
    assert cfg.is_configured is True
