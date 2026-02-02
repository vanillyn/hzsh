from typing import Optional

import discord
from discord.ext import commands

import config


def has_role(member: discord.Member, role_name: str) -> bool:
    return discord.utils.get(member.roles, name=role_name) is not None


def is_staff(member: discord.Member) -> bool:
    return has_role(member, "staff@hazelrun")


def is_mod(member: discord.Member) -> bool:
    return has_role(member, "mod@hazelrun")


def is_root(member: discord.Member) -> bool:
    return has_role(member, "root@hazelrun")


def has_shell_access(member: discord.Member) -> bool:
    return has_role(member, config.SHELL_ACCESS_ROLE)


async def get_or_create_role(
    guild: discord.Guild, name: str, **kwargs
) -> Optional[discord.Role]:
    role = discord.utils.get(guild.roles, name=name)
    if not role:
        try:
            role = await guild.create_role(name=name, **kwargs)
        except discord.HTTPException:
            return None
    return role


def get_logger(bot: commands.Bot):
    logging_cog = bot.get_cog("Logging")
    if logging_cog and hasattr(logging_cog, "logger"):
        return logging_cog.logger
    return None


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """truncate text to max length with suffix"""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


async def safe_send(
    channel: discord.abc.Messageable, content: str, **kwargs
) -> Optional[discord.Message]:
    """safely send a message, handling errors"""
    try:
        return await channel.send(content, **kwargs)
    except (discord.HTTPException, discord.Forbidden):
        return None


async def safe_dm(user: discord.User, content: str, **kwargs) -> bool:
    """safely dm a user, return True if successful"""
    try:
        await user.send(content, **kwargs)
        return True
    except (discord.HTTPException, discord.Forbidden):
        return False


def format_timestamp(dt) -> str:
    """format datetime to readable string"""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class CogHelper:
    """base class for cogs with common utilities"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._logger = None
        self._data = None

    @property
    def logger(self):
        """lazy load logger"""
        if self._logger is None:
            self._logger = get_logger(self.bot)
        return self._logger

    def log_info(self, message: str):
        """log info if logger available"""
        if self.logger:
            self.logger.info(message)

    def log_error(self, message: str, exc_info=None):
        """log error if logger available"""
        if self.logger:
            self.logger.error(message, exc_info=exc_info)

    def log_warning(self, message: str):
        """log warning if logger available"""
        if self.logger:
            self.logger.warning(message)
