import discord

from src.models import BotResponse

COLOUR_SUCCESS = discord.Colour.green()
COLOUR_CREDENTIAL = discord.Colour.yellow()
COLOUR_ERROR = discord.Colour.red()

_MAX_DESCRIPTION = 4096
_TRUNCATE_SUFFIX = "... (truncated)"


def _truncate(content: str) -> str:
    if len(content) <= _MAX_DESCRIPTION:
        return content
    return content[: _MAX_DESCRIPTION - len(_TRUNCATE_SUFFIX)] + _TRUNCATE_SUFFIX


def build_embed(response: BotResponse, project_name: str | None = None) -> discord.Embed:
    if response.is_error:
        colour = COLOUR_ERROR
    elif response.is_credential:
        colour = COLOUR_CREDENTIAL
    else:
        colour = COLOUR_SUCCESS

    embed = discord.Embed(description=_truncate(response.content), colour=colour)
    if project_name and not response.is_error:
        embed.title = f"Project: {project_name}"
    return embed


def build_rate_limit_embed(language: str = "id") -> discord.Embed:
    message = (
        "Terlalu banyak pertanyaan. Coba lagi dalam 1 menit."
        if language == "id"
        else "Too many requests. Please wait 1 minute before trying again."
    )
    return discord.Embed(description=message, colour=COLOUR_ERROR)


def build_dm_rejected_embed() -> discord.Embed:
    return discord.Embed(
        description=(
            "Maaf, bot ini hanya tersedia untuk anggota internal Timedoor. "
            "Silakan hubungi tim Timedoor jika kamu membutuhkan akses."
        ),
        colour=COLOUR_ERROR,
    )


def build_channel_denied_embed(language: str = "id") -> discord.Embed:
    message = (
        "Bot ini tidak aktif di channel ini." if language == "id" else "This bot is not active in this channel."
    )
    return discord.Embed(description=message, colour=COLOUR_ERROR)
