import logging
import re
from pathlib import Path

import pytest
import yaml

from src.config import (
    AppConfig,
    get_audit_logger,
    get_config,
    get_error_logger,
    get_latency_logger,
    load_config,
    setup_logging,
)
from src.config import loader as config_loader
from src.config import logging as config_logging


CONFIG = {
    "discord": {
        "allowed_channels": ["channel-1"],
        "denied_channels": [],
        "allow_dms": True,
        "dm_require_server_membership": True,
        "timedoor_server_id": "server-1",
    },
    "notion": {
        "databases": {
            "mobile_team": "mobile-db",
            "web_team": "web-db",
            "backend_team": "backend-db",
        }
    },
    "session": {"max_history": 5, "timeout_minutes": 30},
    "cache": {
        "project_properties_ttl": 1800,
        "bug_counts_ttl": 300,
        "changelog_ttl": 900,
        "doc_links_ttl": 3600,
    },
    "llm": {"model": "gemini-2.0-flash", "temperature": 0.2, "max_output_tokens": 1024},
    "rate_limit": {"max_queries_per_user_per_minute": 5},
}


@pytest.fixture(autouse=True)
def reset_module_state(monkeypatch):
    monkeypatch.setattr(config_loader, "_config", None)
    monkeypatch.setattr(config_logging, "_configured", False)
    for name in ("tab.latency", "tab.errors", "tab.audit"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "discord-test-token")
    monkeypatch.setenv("NOTION_API_TOKEN", "notion-test-token")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")


def write_config(tmp_path: Path, config: dict = CONFIG) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path


def test_valid_config_loads_with_typed_fields(tmp_path):
    config = load_config(str(write_config(tmp_path)))

    assert isinstance(config, AppConfig)
    assert config.discord.allowed_channels == ["channel-1"]
    assert config.discord.token == "discord-test-token"
    assert config.notion.databases.mobile_team == "mobile-db"
    assert config.notion.api_token == "notion-test-token"
    assert config.llm.api_key == "gemini-test-key"
    assert isinstance(config.cache.bug_counts_ttl, int)


def test_missing_env_var_names_variable(monkeypatch, tmp_path):
    monkeypatch.delenv("DISCORD_BOT_TOKEN")

    with pytest.raises(EnvironmentError, match="DISCORD_BOT_TOKEN"):
        load_config(str(write_config(tmp_path)))


def test_missing_yaml_file_names_resolved_path(tmp_path):
    path = tmp_path / "missing.yaml"

    with pytest.raises(FileNotFoundError, match=re.escape(str(path.resolve()))):
        load_config(str(path))


def test_get_config_before_load_requires_initialization():
    with pytest.raises(RuntimeError, match=r"load_config\(\)"):
        get_config()


def test_cache_ttl_is_integer(tmp_path):
    config = load_config(str(write_config(tmp_path)))

    assert config.cache.bug_counts_ttl == 300
    assert isinstance(config.cache.bug_counts_ttl, int)


def test_logger_getter_before_setup_requires_initialization():
    with pytest.raises(RuntimeError):
        get_error_logger()


def test_all_loggers_write_after_setup(tmp_path, capsys):
    config = load_config(str(write_config(tmp_path)))
    setup_logging(config)

    get_latency_logger().info("latency entry")
    get_error_logger().error("error entry")
    get_audit_logger().info("audit entry")

    output = capsys.readouterr().err
    assert "[tab.latency]" in output
    assert "latency entry" in output
    assert "[tab.errors]" in output
    assert "error entry" in output
    assert "[tab.audit]" in output
    assert "audit entry" in output
