from datetime import datetime
from typing import Optional

import discord

from ..misc.db import (
    Infraction,
    ModerationConfig,
    ModSession,
    get_expiry_time,
    get_session,
)


class ModerationHelper:
    @staticmethod
    def get_config(guild_id):
        session = get_session()
        try:
            config = (
                session.query(ModerationConfig).filter_by(guild_id=guild_id).first()
            )

            if not config:
                config = ModerationConfig(guild_id=guild_id)
                session.add(config)
                session.commit()

            return config
        finally:
            session.close()

    @staticmethod
    def update_config(guild_id, **kwargs):
        """update moderation config
        available configs:
        - mod_role_id: int
        - muted_role_id: int
        - log_channel_id: int
        - mute_channel_id: int
        - ticket_category_id: int
        - archive_category_id: int
        - op_role_id: int

        """
        session = get_session()
        try:
            config = (
                session.query(ModerationConfig).filter_by(guild_id=guild_id).first()
            )

            if not config:
                config = ModerationConfig(guild_id=guild_id)
                session.add(config)

            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)

            session.commit()
            return config
        finally:
            session.close()

    @staticmethod
    async def log_action(
        bot,
        guild: discord.Guild,
        action_type: str,
        moderator: discord.Member,
        target: discord.Member,
        reason: str,
        duration: Optional[int] = None,
        infraction_id: Optional[int] = None,
    ):
        config = ModerationHelper.get_config(guild.id)

        if not config.log_channel_id:
            return None

        log_channel = guild.get_channel(config.log_channel_id)
        if not log_channel:
            return None

        color_map = {
            "warn": discord.Color.yellow(),
            "mute": discord.Color.orange(),
            "kick": discord.Color.red(),
            "ban": discord.Color.dark_red(),
            "unmute": discord.Color.green(),
            "unban": discord.Color.green(),
        }

        embed = discord.Embed(
            title=f"case #{infraction_id}: {action_type}",
            color=color_map.get(action_type, discord.Color.blurple()),
            timestamp=datetime.utcnow(),
        )

        embed.add_field(
            name="user", value=f"{target.mention} ({target.id})", inline=True
        )
        embed.add_field(
            name="moderator", value=f"{moderator.mention} ({moderator.id})", inline=True
        )

        if infraction_id:
            embed.add_field(name="case", value=f"#{infraction_id}", inline=True)

        embed.add_field(name="reason", value=reason, inline=False)

        if duration:
            from ..misc.db import format_relative_time

            embed.add_field(
                name="duration", value=format_relative_time(duration), inline=True
            )

        try:
            msg = await log_channel.send(embed=embed)
            return msg.id
        except discord.HTTPException:
            return None

    @staticmethod
    async def notify_user(
        user: discord.User,
        guild: discord.Guild,
        action_type: str,
        reason: str,
        duration: Optional[int] = None,
        moderator: Optional[discord.Member] = None,
    ) -> bool:
        try:
            embed = discord.Embed(
                title=f"moderation action in {guild.name}",
                description=f"you have been **{action_type}**",
                color=discord.Color.red(),
                timestamp=datetime.utcnow(),
            )

            embed.add_field(name="reason", value=reason, inline=False)

            if duration:
                from ..misc.db import format_relative_time

                embed.add_field(
                    name="duration", value=format_relative_time(duration), inline=True
                )

            if moderator:
                embed.set_footer(
                    text=f"moderator: {moderator.name}",
                    icon_url=moderator.display_avatar.url,
                )

            await user.send(embed=embed)
            return True
        except discord.HTTPException:
            return False

    @staticmethod
    def create_infraction(
        user_id: int,
        moderator_id: int,
        guild_id: int,
        infraction_type: str,
        reason: str,
        duration: Optional[int] = None,
        message_id: Optional[int] = None,
        dm_sent: bool = False,
    ) -> Infraction:
        session = get_session()
        try:
            infraction = Infraction(
                user_id=user_id,
                moderator_id=moderator_id,
                guild_id=guild_id,
                type=infraction_type,
                reason=reason,
                duration=duration,
                expires_at=get_expiry_time(duration) if duration else None,
                message_id=message_id,
                dm_sent=dm_sent,
            )

            session.add(infraction)
            session.commit()
            session.refresh(infraction)

            return infraction
        finally:
            session.close()

    @staticmethod
    def get_user_infractions(user_id: int, guild_id: int, active_only=False):
        """get all infractions for a user"""
        session = get_session()
        try:
            query = session.query(Infraction).filter_by(
                user_id=user_id,
                guild_id=guild_id,
            )

            if active_only:
                query = query.filter_by(active=True)

            return query.order_by(Infraction.created_at.desc()).all()
        finally:
            session.close()

    @staticmethod
    def get_infraction(infraction_id: int, guild_id: int):
        """get specific infraction"""
        session = get_session()
        try:
            return (
                session.query(Infraction)
                .filter_by(
                    id=infraction_id,
                    guild_id=guild_id,
                )
                .first()
            )
        finally:
            session.close()

    @staticmethod
    def deactivate_infraction(infraction_id: int, guild_id: int) -> bool:
        """deactivate an infraction"""
        session = get_session()
        try:
            infraction = (
                session.query(Infraction)
                .filter_by(
                    id=infraction_id,
                    guild_id=guild_id,
                )
                .first()
            )

            if infraction:
                infraction.active = False
                session.commit()
                return True
            return False
        finally:
            session.close()


def is_mod(member: discord.Member) -> bool:
    """check if member is a moderator"""
    config = ModerationHelper.get_config(member.guild.id)

    if config.mod_role_id:
        mod_role = member.guild.get_role(config.mod_role_id)
        if mod_role and mod_role in member.roles:
            return True

    return any(role.name in ["mod@hazelrun", "staff@hazelrun"] for role in member.roles)


def is_op(member: discord.Member) -> bool:
    """check if member has active op session"""
    session = get_session()
    try:
        mod_session = (
            session.query(ModSession)
            .filter_by(
                user_id=member.id,
                guild_id=member.guild.id,
            )
            .first()
        )

        if not mod_session:
            return False

        if mod_session.is_expired:
            session.delete(mod_session)
            session.commit()
            return False

        return True
    finally:
        session.close()


def get_mod_session(user_id: int, guild_id: int) -> Optional[ModSession]:
    """get active mod session for user"""
    session = get_session()
    try:
        mod_session = (
            session.query(ModSession)
            .filter_by(
                user_id=user_id,
                guild_id=guild_id,
            )
            .first()
        )

        if mod_session and mod_session.is_expired:
            session.delete(mod_session)
            session.commit()
            return None

        return mod_session
    finally:
        session.close()


def create_mod_session(
    user_id: int, guild_id: int, duration: Optional[int] = 3600, permanent: bool = False
):
    """create new mod session"""
    session = get_session()
    try:
        existing = (
            session.query(ModSession)
            .filter_by(
                user_id=user_id,
                guild_id=guild_id,
            )
            .first()
        )

        if existing:
            session.delete(existing)

        mod_session = ModSession(
            user_id=user_id,
            guild_id=guild_id,
            expires_at=get_expiry_time(duration) if not permanent else None,
            permanent=permanent,
        )

        session.add(mod_session)
        session.commit()
        session.refresh(mod_session)

        return mod_session
    finally:
        session.close()


def end_mod_session(user_id: int, guild_id: int) -> bool:
    """end active mod session"""
    session = get_session()
    try:
        mod_session = (
            session.query(ModSession)
            .filter_by(
                user_id=user_id,
                guild_id=guild_id,
            )
            .first()
        )

        if mod_session:
            session.delete(mod_session)
            session.commit()
            return True
        return False
    finally:
        session.close()


async def check_expired_infractions(bot):
    session = get_session()
    try:
        expired = (
            session.query(Infraction)
            .filter(
                Infraction.active,
                Infraction.expires_at is not None,
                Infraction.expires_at <= datetime.utcnow(),
            )
            .all()
        )

        for infraction in expired:
            infraction.active = False

            if infraction.type == "mute":
                guild = bot.get_guild(infraction.guild_id)
                if guild:
                    member = guild.get_member(infraction.user_id)
                    config = ModerationHelper.get_config(guild.id)

                    if member and config.muted_role_id:
                        muted_role = guild.get_role(config.muted_role_id)
                        if muted_role:
                            try:
                                await member.remove_roles(
                                    muted_role, reason="mute expired"
                                )
                            except discord.HTTPException:
                                pass

        session.commit()
    finally:
        session.close()
