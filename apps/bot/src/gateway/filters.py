import discord

from src.config import get_config


def is_channel_allowed(channel: discord.abc.Messageable) -> bool:
    config = get_config().discord
    channel_id = str(channel.id)
    if config.allowed_channels:
        return channel_id in config.allowed_channels
    if config.denied_channels:
        return channel_id not in config.denied_channels
    return True


def is_dm(message: discord.Message) -> bool:
    return isinstance(message.channel, discord.DMChannel)


async def is_timedoor_member(user: discord.abc.User, bot: discord.Client) -> bool:
    guild = bot.get_guild(int(get_config().discord.timedoor_server_id))
    if guild is None:
        return False
    try:
        await guild.fetch_member(user.id)
        return True
    except discord.NotFound:
        return False
