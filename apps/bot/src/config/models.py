from dataclasses import dataclass


@dataclass
class DiscordConfig:
    allowed_channels: list[str]
    denied_channels: list[str]
    allow_dms: bool
    dm_require_server_membership: bool
    timedoor_server_id: str
    token: str


@dataclass
class NotionDatabases:
    mobile_team: str
    web_team: str
    backend_team: str


@dataclass
class NotionConfig:
    databases: NotionDatabases
    api_token: str


@dataclass
class SessionConfig:
    max_history: int
    timeout_minutes: int


@dataclass
class CacheConfig:
    project_properties_ttl: int
    bug_counts_ttl: int
    changelog_ttl: int
    doc_links_ttl: int


@dataclass
class LLMConfig:
    model: str
    temperature: float
    max_output_tokens: int
    api_key: str


@dataclass
class RateLimitConfig:
    max_queries_per_user_per_minute: int


@dataclass
class AppConfig:
    discord: DiscordConfig
    notion: NotionConfig
    session: SessionConfig
    cache: CacheConfig
    llm: LLMConfig
    rate_limit: RateLimitConfig
