import logging
import time

import discord

from src.config import AppConfig, get_config, get_error_logger, get_latency_logger

_log = logging.getLogger(__name__)
from src.gateway.filters import is_channel_allowed, is_dm, is_timedoor_member
from src.gateway.formatters import build_dm_rejected_embed, build_embed, build_rate_limit_embed
from src.gateway.rate_limiter import get_rate_limiter
from src.models import BotResponse, NotionResult, QueryIntent
from src.parser import add_to_session, initialize_project_registry, parse_message, update_session_project
from src.router import route_query
from src.synthesizer import synthesize_response


def _extract_resolved_project(results: list[tuple[QueryIntent, NotionResult]]) -> str | None:
    for intent, _ in results:
        if not intent.is_ambiguous and intent.project_name:
            return intent.project_name
    return None


def create_bot(config: AppConfig) -> discord.Client:
    intents = discord.Intents.default()
    intents.message_content = True
    bot = discord.Client(intents=intents)

    @bot.event
    async def on_ready() -> None:
        _log.info("Logged in as %s", bot.user)
        await initialize_project_registry()

    @bot.event
    async def on_message(message: discord.Message) -> None:
        await _handle_message(message, bot)

    return bot


async def _handle_message(message: discord.Message, bot: discord.Client) -> None:
    if message.author == bot.user:
        return

    if is_dm(message):
        if not get_config().discord.allow_dms:
            return
        if not await is_timedoor_member(message.author, bot):
            await message.reply(embed=build_dm_rejected_embed(), mention_author=False)
            return
    else:
        if bot.user not in message.mentions:
            return
        if not is_channel_allowed(message.channel):
            return

    if not get_rate_limiter().is_allowed(message.author.id):
        await message.reply(embed=build_rate_limit_embed(), mention_author=False)
        return

    async with message.channel.typing():
        await _run_pipeline(message, bot)


async def _run_pipeline(message: discord.Message, bot: discord.Client) -> None:
    start_time = time.perf_counter()
    language = "id"
    try:
        parsed = await parse_message(
            message_text=message.content,
            user_id=message.author.id,
            channel_id=message.channel.id,
        )
        language = parsed.questions[0].language if parsed.questions else "id"

        results = await route_query(parsed)

        response = await synthesize_response(results=results, history=parsed.history)

        resolved_project = _extract_resolved_project(results)

        embed = build_embed(response, project_name=resolved_project)

        await message.reply(embed=embed, mention_author=False)

        is_reset = any(intent.intent == "session_reset" for intent, _ in results)
        if not is_reset:
            add_to_session(
                user_id=message.author.id,
                channel_id=message.channel.id,
                user_message=message.content,
                bot_response=response.content,
            )
            if resolved_project is not None:
                update_session_project(
                    user_id=message.author.id,
                    channel_id=message.channel.id,
                    project_name=resolved_project,
                )

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        get_latency_logger().info(
            "request_complete",
            extra={
                "user_id": message.author.id,
                "duration_ms": duration_ms,
                "question_count": len(parsed.questions),
                "is_error": response.is_error,
            },
        )
    except Exception as exc:
        get_error_logger().error("Pipeline failed: %s", exc, extra={"module": "gateway"})
        error_content = (
            "Maaf, terjadi kesalahan saat memproses permintaan Anda."
            if language == "id"
            else "Sorry, something went wrong while processing your request."
        )
        error_embed = build_embed(BotResponse(content=error_content, language=language, is_error=True))
        await message.reply(embed=error_embed, mention_author=False)
