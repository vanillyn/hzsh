from datetime import datetime

import discord
from discord.ext import commands

from ..misc.db import Infraction, format_timestamp, get_session
from ..misc.utils import CogHelper
from .utils import ModerationHelper, is_mod


class UserInfo(CogHelper, commands.Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.mod_helper = ModerationHelper()

    @commands.command(aliases=["whois", "user", "ui"])
    async def userinfo(self, ctx, member: discord.Member = None):
        if not is_mod(ctx.author):
            await ctx.send("you lack the required permissions")
            return

        target = member or ctx.author

        embed = discord.Embed(
            title=f"user information: {target.name}",
            color=target.color
            if target.color != discord.Color.default()
            else discord.Color.blurple(),
            timestamp=datetime.utcnow(),
        )

        embed.set_thumbnail(url=target.display_avatar.url)

        embed.add_field(
            name="basic info",
            value=f"**id:** {target.id}\n"
            f"**mention:** {target.mention}\n"
            f"**bot:** {'yes' if target.bot else 'no'}\n"
            f"**nickname:** {target.nick if target.nick else 'none'}",
            inline=False,
        )

        embed.add_field(
            name="dates",
            value=f"**created:** {format_timestamp(target.created_at)} ({format_timestamp(target.created_at, relative=True)})\n"
            f"**joined:** {format_timestamp(target.joined_at)} ({format_timestamp(target.joined_at, relative=True)})",
            inline=False,
        )

        if len(target.roles) > 1:
            roles = [
                role.mention
                for role in reversed(target.roles)
                if role != ctx.guild.default_role
            ]
            role_text = ", ".join(roles[:10])
            if len(target.roles) > 11:
                role_text += f" (+{len(target.roles) - 11} more)"

            embed.add_field(
                name=f"roles [{len(target.roles) - 1}]", value=role_text, inline=False
            )

        key_perms = []
        if target.guild_permissions.administrator:
            key_perms.append("administrator")
        if target.guild_permissions.manage_guild:
            key_perms.append("manage server")
        if target.guild_permissions.manage_roles:
            key_perms.append("manage roles")
        if target.guild_permissions.manage_channels:
            key_perms.append("manage channels")
        if target.guild_permissions.kick_members:
            key_perms.append("kick members")
        if target.guild_permissions.ban_members:
            key_perms.append("ban members")

        if key_perms:
            embed.add_field(
                name="key permissions", value=", ".join(key_perms), inline=False
            )

        if target.activity:
            activity_type = {
                discord.ActivityType.playing: "playing",
                discord.ActivityType.streaming: "streaming",
                discord.ActivityType.listening: "listening to",
                discord.ActivityType.watching: "watching",
                discord.ActivityType.custom: "status",
                discord.ActivityType.competing: "competing in",
            }.get(target.activity.type, "")

            activity_name = target.activity.name
            if isinstance(target.activity, discord.Spotify):
                activity_name = f"{target.activity.title} by {target.activity.artist}"

            embed.add_field(
                name="activity", value=f"{activity_type} {activity_name}", inline=False
            )

        session = get_session()
        try:
            infractions = (
                session.query(Infraction)
                .filter_by(user_id=target.id, guild_id=ctx.guild.id)
                .all()
            )

            if infractions:
                active = sum(1 for i in infractions if i.active)
                warns = sum(1 for i in infractions if i.type == "warn")
                mutes = sum(1 for i in infractions if i.type == "mute")
                kicks = sum(1 for i in infractions if i.type == "kick")
                bans = sum(1 for i in infractions if i.type == "ban")

                mod_text = f"**total:** {len(infractions)} ({active} active)\n"
                mod_text += f"**warns:** {warns} | **mutes:** {mutes}\n"
                mod_text += f"**kicks:** {kicks} | **bans:** {bans}"

                latest = max(infractions, key=lambda x: x.created_at)
                mod_text += f"\n**latest:** {latest.type} - {format_timestamp(latest.created_at, relative=True)}"

                embed.add_field(
                    name=" moderation history", value=mod_text, inline=False
                )
        finally:
            session.close()

        if target.premium_since:
            embed.add_field(
                name="server booster",
                value=f"boosting since {format_timestamp(target.premium_since, relative=True)}",
                inline=False,
            )

        embed.set_footer(text=f"{target.status.name} • requested by {ctx.author.name}")

        await ctx.send(embed=embed)

    @commands.command(aliases=["avatar", "av", "pfp"])
    async def userimage(self, ctx, member: discord.Member = None):
        """get a user's avatar"""
        target = member or ctx.author

        embed = discord.Embed(
            title=f"{target.name}'s avatar",
            color=target.color
            if target.color != discord.Color.default()
            else discord.Color.blurple(),
        )

        embed.set_image(url=target.display_avatar.url)

        avatar_url = target.display_avatar.url
        formats = []
        if target.display_avatar.is_animated():
            formats.append(f"[gif]({avatar_url.replace('.webp', '.gif')})")
        formats.append(f"[png]({avatar_url.replace('.webp', '.png')})")
        formats.append(f"[jpg]({avatar_url.replace('.webp', '.jpg')})")
        formats.append(f"[webp]({avatar_url})")

        embed.description = " | ".join(formats)

        await ctx.send(embed=embed)

    @commands.command()
    async def lookup(self, ctx, user_id: int):
        """look up a user by id (mods only)"""
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

        embed = discord.Embed(
            title=f"user lookup: {user.name}",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow(),
        )

        embed.set_thumbnail(url=user.display_avatar.url)

        embed.add_field(
            name="info",
            value=f"**id:** {user.id}\n"
            f"**name:** {user.name}\n"
            f"**bot:** {'yes' if user.bot else 'no'}\n"
            f"**created:** {format_timestamp(user.created_at)} ({format_timestamp(user.created_at, relative=True)})",
            inline=False,
        )

        member = ctx.guild.get_member(user_id)
        if member:
            embed.add_field(
                name="server status",
                value=f"✅ in server\n"
                f"**joined:** {format_timestamp(member.joined_at, relative=True)}\n"
                f"**roles:** {len(member.roles) - 1}",
                inline=False,
            )
        else:
            embed.add_field(
                name="server status", value="❌ not in server", inline=False
            )

        session = get_session()
        try:
            infractions = (
                session.query(Infraction)
                .filter_by(user_id=user_id, guild_id=ctx.guild.id)
                .all()
            )

            if infractions:
                active = sum(1 for i in infractions if i.active)
                embed.add_field(
                    name="⚠️ infractions",
                    value=f"**total:** {len(infractions)}\n**active:** {active}",
                    inline=False,
                )
        finally:
            session.close()

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(UserInfo(bot))
