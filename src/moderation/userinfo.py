import discord
from discord.ext import commands

from ..misc.db import Infraction, format_timestamp, get_session
from ..misc.utils import CogHelper
from .cmdutils import ModCommandParser
from .utils import ModerationHelper, is_mod


class UserInfo(CogHelper, commands.Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.mod_helper = ModerationHelper()
        self.parser = ModCommandParser()

    @commands.command(aliases=["whois", "user", "ui"])
    async def userinfo(self, ctx, target: str = None):
        if not is_mod(ctx.author):
            await ctx.send("you lack the required permissions")
            return

        if target:
            members = await self.parser.resolve_users(ctx, [target])
            if not members:
                await ctx.send("user not found")
                return
            member = members[0]
        else:
            member = ctx.author

        msg = f"**user information: {member.name}**\n\n"

        msg += f"**id:** {member.id}\n"
        msg += f"**mention:** {member.mention}\n"
        msg += f"**bot:** {'yes' if member.bot else 'no'}\n"
        msg += f"**nickname:** {member.nick if member.nick else 'none'}\n\n"

        msg += f"**created:** {format_timestamp(member.created_at)} ({format_timestamp(member.created_at, relative=True)})\n"
        msg += f"**joined:** {format_timestamp(member.joined_at)} ({format_timestamp(member.joined_at, relative=True)})\n\n"

        if len(member.roles) > 1:
            roles = [
                role.mention
                for role in reversed(member.roles)
                if role != ctx.guild.default_role
            ]
            role_text = ", ".join(roles[:10])
            if len(member.roles) > 11:
                role_text += f" (+{len(member.roles) - 11} more)"

            msg += f"**roles [{len(member.roles) - 1}]**\n{role_text}\n\n"

        key_perms = []
        if member.guild_permissions.administrator:
            key_perms.append("administrator")
        if member.guild_permissions.manage_guild:
            key_perms.append("manage server")
        if member.guild_permissions.manage_roles:
            key_perms.append("manage roles")
        if member.guild_permissions.manage_channels:
            key_perms.append("manage channels")
        if member.guild_permissions.kick_members:
            key_perms.append("kick members")
        if member.guild_permissions.ban_members:
            key_perms.append("ban members")

        if key_perms:
            msg += f"**key permissions**\n{', '.join(key_perms)}\n\n"

        if member.activity:
            activity_type = {
                discord.ActivityType.playing: "playing",
                discord.ActivityType.streaming: "streaming",
                discord.ActivityType.listening: "listening to",
                discord.ActivityType.watching: "watching",
                discord.ActivityType.custom: "status",
                discord.ActivityType.competing: "competing in",
            }.get(member.activity.type, "")

            activity_name = member.activity.name
            if isinstance(member.activity, discord.Spotify):
                activity_name = f"{member.activity.title} by {member.activity.artist}"

            msg += f"**activity**\n{activity_type} {activity_name}\n\n"

        session = get_session()
        try:
            infractions = (
                session.query(Infraction)
                .filter_by(user_id=member.id, guild_id=ctx.guild.id)
                .all()
            )

            if infractions:
                active = sum(1 for i in infractions if i.active)
                warns = sum(1 for i in infractions if i.type == "warn")
                mutes = sum(1 for i in infractions if i.type == "mute")
                kicks = sum(1 for i in infractions if i.type == "kick")
                bans = sum(1 for i in infractions if i.type == "ban")

                msg += "**moderation history**\n"
                msg += f"total: {len(infractions)} ({active} active)\n"
                msg += f"warns: {warns} | mutes: {mutes}\n"
                msg += f"kicks: {kicks} | bans: {bans}\n"

                latest = max(infractions, key=lambda x: x.created_at)
                msg += f"latest: {latest.type} - {format_timestamp(latest.created_at, relative=True)}\n\n"
        finally:
            session.close()

        if member.premium_since:
            msg += f"**server booster**\nboosting since {format_timestamp(member.premium_since, relative=True)}\n\n"

        msg += f"-# {member.status.name} • requested by {ctx.author.name}"

        await ctx.send(msg)

    @commands.command(aliases=["avatar", "av", "pfp"])
    async def userimage(self, ctx, target: str = None):
        if target:
            members = await self.parser.resolve_users(ctx, [target])
            if not members:
                await ctx.send("user not found")
                return
            member = members[0]
        else:
            member = ctx.author

        avatar_url = member.display_avatar.url
        formats = []
        if member.display_avatar.is_animated():
            formats.append(f"[gif]({avatar_url.replace('.webp', '.gif')})")
        formats.append(f"[png]({avatar_url.replace('.webp', '.png')})")
        formats.append(f"[jpg]({avatar_url.replace('.webp', '.jpg')})")
        formats.append(f"[webp]({avatar_url})")

        msg = f"**{member.name}'s avatar**\n"
        msg += " | ".join(formats)
        msg += f"\n{avatar_url}"

        await ctx.send(msg)

    @commands.command()
    async def lookup(self, ctx, user_id: int):
        if not is_mod(ctx.author):
            await ctx.send("you lack the required permissions")
            return

        try:
            user = await self.bot.fetch_user(user_id)
        except discord.NotFound:
            await ctx.send(f"user with id {user_id} not found")
            return
        except discord.HTTPException as e:
            await ctx.send(f"error fetching user: {e}")
            return

        msg = f"**user lookup: {user.name}**\n\n"
        msg += f"**id:** {user.id}\n"
        msg += f"**name:** {user.name}\n"
        msg += f"**bot:** {'yes' if user.bot else 'no'}\n"
        msg += f"**created:** {format_timestamp(user.created_at)} ({format_timestamp(user.created_at, relative=True)})\n\n"

        member = ctx.guild.get_member(user_id)
        if member:
            msg += "**server status**\nin server\n"
            msg += f"joined: {format_timestamp(member.joined_at, relative=True)}\n"
            msg += f"roles: {len(member.roles) - 1}\n\n"
        else:
            msg += "**server status**\n❌ not in server\n\n"

        session = get_session()
        try:
            infractions = (
                session.query(Infraction)
                .filter_by(user_id=user_id, guild_id=ctx.guild.id)
                .all()
            )

            if infractions:
                active = sum(1 for i in infractions if i.active)
                msg += "**infractions**\n"
                msg += f"total: {len(infractions)}\n"
                msg += f"active: {active}"
        finally:
            session.close()

        await ctx.send(msg)


async def setup(bot):
    await bot.add_cog(UserInfo(bot))
