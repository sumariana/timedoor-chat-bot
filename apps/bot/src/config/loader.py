import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from src.config.models import (
    AppConfig,
    CacheConfig,
    DiscordConfig,
    LLMConfig,
    NotionConfig,
    NotionDatabases,
    RateLimitConfig,
    SessionConfig,
)


_config: AppConfig | None = None


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(f"Required environment variable is missing: {name}")
    return value


def _required_section(config: dict, section: str, path: str) -> dict:
    try:
        value = config[section]
    except KeyError as error:
        raise KeyError(path) from error
    if not isinstance(value, dict):
        raise KeyError(path)
    return value


def _required_value(config: dict, key: str, path: str):
    try:
        return config[key]
    except KeyError as error:
        raise KeyError(path) from error


def load_config(config_path: str = "../../config/config.yaml") -> AppConfig:
    global _config

    if _config is not None:
        return _config

    resolved_path = Path(config_path).resolve()
    load_dotenv(dotenv_path=resolved_path.parent.parent / ".env")
    try:
        with resolved_path.open(encoding="utf-8") as file:
            raw_config = yaml.safe_load(file)
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Configuration file not found: {resolved_path}") from error

    if not isinstance(raw_config, dict):
        raise KeyError("configuration")

    discord = _required_section(raw_config, "discord", "discord")
    notion = _required_section(raw_config, "notion", "notion")
    databases = _required_section(notion, "databases", "notion.databases")
    session = _required_section(raw_config, "session", "session")
    cache = _required_section(raw_config, "cache", "cache")
    llm = _required_section(raw_config, "llm", "llm")
    rate_limit = _required_section(raw_config, "rate_limit", "rate_limit")

    _config = AppConfig(
        discord=DiscordConfig(
            allowed_channels=_required_value(discord, "allowed_channels", "discord.allowed_channels"),
            denied_channels=_required_value(discord, "denied_channels", "discord.denied_channels"),
            allow_dms=_required_value(discord, "allow_dms", "discord.allow_dms"),
            dm_require_server_membership=_required_value(
                discord, "dm_require_server_membership", "discord.dm_require_server_membership"
            ),
            timedoor_server_id=_required_value(discord, "timedoor_server_id", "discord.timedoor_server_id"),
            token=_required_env("DISCORD_BOT_TOKEN"),
        ),
        notion=NotionConfig(
            databases=NotionDatabases(
                mobile_team=_required_value(databases, "mobile_team", "notion.databases.mobile_team"),
                web_team=_required_value(databases, "web_team", "notion.databases.web_team"),
                backend_team=_required_value(databases, "backend_team", "notion.databases.backend_team"),
            ),
            api_token=_required_env("NOTION_API_TOKEN"),
        ),
        session=SessionConfig(
            max_history=_required_value(session, "max_history", "session.max_history"),
            timeout_minutes=_required_value(session, "timeout_minutes", "session.timeout_minutes"),
        ),
        cache=CacheConfig(
            project_properties_ttl=_required_value(cache, "project_properties_ttl", "cache.project_properties_ttl"),
            bug_counts_ttl=_required_value(cache, "bug_counts_ttl", "cache.bug_counts_ttl"),
            changelog_ttl=_required_value(cache, "changelog_ttl", "cache.changelog_ttl"),
            doc_links_ttl=_required_value(cache, "doc_links_ttl", "cache.doc_links_ttl"),
        ),
        llm=LLMConfig(
            model=_required_value(llm, "model", "llm.model"),
            temperature=_required_value(llm, "temperature", "llm.temperature"),
            max_output_tokens=_required_value(llm, "max_output_tokens", "llm.max_output_tokens"),
            api_key=_required_env("GEMINI_API_KEY"),
        ),
        rate_limit=RateLimitConfig(
            max_queries_per_user_per_minute=_required_value(
                rate_limit, "max_queries_per_user_per_minute", "rate_limit.max_queries_per_user_per_minute"
            ),
        ),
    )
    return _config


def get_config() -> AppConfig:
    if _config is None:
        raise RuntimeError("Configuration has not been initialized; call load_config() first")
    return _config
