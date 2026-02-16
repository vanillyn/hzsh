import discord
from discord.ext import commands, tasks

from ..misc.db import (
    Infraction,
    format_relative_time,
    format_timestamp,
    get_session,
    parse_duration,
)
from ..misc.utils import CogHelper
from .cmdutils import ModCommandParser, confirm_action
from .utils import (
    ModerationHelper,
    check_expired_infractions,
    create_mod_session,
    end_mod_session,
    get_mod_session,
    is_mod,
    is_op,
)


class ModerationCommands(CogHelper, commands.Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.mod_helper = ModerationHelper()
        self.parser = ModCommandParser()
        self.check_expirations.start()

    def cog_unload(self):
        self.check_expirations.cancel()

    @tasks.loop(minutes=1)
    async def check_expirations(self):
        await check_expired_infractions(self.bot)

    @check_expirations.before_loop
    async def before_check_expirations(self):
        await self.bot.wait_until_ready()

    async def cog_check(self, ctx):
        return ctx.guild is not None

    @commands.command(aliases=["sudo", "doas"])
    async def op(self, ctx, flag: str = ""):
        if not is_mod(ctx.author):
            await ctx.send("you lack the required permissions")
            return

        config = self.mod_helper.get_config(ctx.guild.id)
        existing_session = get_mod_session(ctx.author.id, ctx.guild.id)

        if existing_session:
            end_mod_session(ctx.author.id, ctx.guild.id)

            if config.op_role_id:
                op_role = ctx.guild.get_role(config.op_role_id)
                if op_role:
                    await ctx.author.remove_roles(op_role)

            await ctx.send("operator mode deactivated")
            self.log_info(f"{ctx.author.name} deactivated op mode")
            return

        permanent = flag in ["-p", "--permanent", "--perm"]

        create_mod_session(
            ctx.author.id,
            ctx.guild.id,
            duration=None if permanent else 3600,
            permanent=permanent,
        )

        if config.op_role_id:
            op_role = ctx.guild.get_role(config.op_role_id)
            if op_role:
                await ctx.author.add_roles(op_role)

        duration_msg = "permanent" if permanent else "1 hour"
        await ctx.send(f"operator mode activated for {duration_msg}")
        self.log_info(f"{ctx.author.name} activated op mode (perm={permanent})")

    @commands.command()
    async def ban(self, ctx, *, args: str = ""):
        if not is_mod(ctx.author):
            await ctx.send("you lack the required permissions")
            return

        if not args:
            await ctx.send(
                'usage: ban {-d [dur]} {-q|-s|-p|-D} [@user|id|name] {"reason"}'
            )
            return

        parsed = self.parser.parse_ban(args)
        targets, reason = await self.parser.parse_targets_and_reason(
            ctx, parsed["raw_args"]
        )
        members = await self.parser.resolve_users(ctx, targets)

        if not members:
            await ctx.send("no valid users provided")
            return

        valid_members, errors = self.parser.validate_targets(
            members, ctx.author, "ban", parsed["dry_run"]
        )

        if errors:
            await ctx.send("\n".join(errors))

        if not valid_members:
            return

        duration_seconds = None
        if parsed["duration"]:
            duration_seconds = parse_duration(parsed["duration"])
            if duration_seconds is None:
                await ctx.send(f"invalid duration: {parsed['duration']}")
                return

        confirmed = await confirm_action(
            ctx,
            "ban",
            valid_members,
            parsed["duration"],
            reason,
            parsed["quick"],
            parsed["dry_run"],
        )

        if not confirmed:
            return

        success_count = 0
        for member in valid_members:
            try:
                dm_sent = False
                if not parsed["silent"] and not parsed["dry_run"]:
                    dm_sent = await self.mod_helper.notify_user(
                        member,
                        ctx.guild,
                        "banned",
                        reason,
                        duration_seconds,
                        ctx.author,
                    )

                infraction = self.mod_helper.create_infraction(
                    member.id,
                    ctx.author.id,
                    ctx.guild.id,
                    "ban" if not parsed["dry_run"] else "ban",
                    reason,
                    duration=duration_seconds,
                    dm_sent=dm_sent,
                )

                if not parsed["silent"]:
                    await self.mod_helper.log_action(
                        self.bot,
                        ctx.guild,
                        "ban" if not parsed["dry_run"] else "ban",
                        ctx.author,
                        member,
                        reason,
                        duration_seconds,
                        infraction.id,
                    )

                if not parsed["dry_run"]:
                    delete_days = 1 if parsed["purge"] else 0
                    await member.ban(
                        reason=f"{ctx.author.name}: {reason}",
                        delete_message_days=delete_days,
                    )

                success_count += 1

            except discord.HTTPException as e:
                await ctx.send(f"failed to ban {member.mention}: {e}")

        if success_count > 0:
            duration_text = (
                f" for {format_relative_time(duration_seconds)}"
                if duration_seconds
                else ""
            )
            prefix = "[ TEST ] " if parsed["dry_run"] else ""
            if success_count == 1:
                await ctx.send(
                    f"{prefix}banned {valid_members[0].mention}{duration_text}"
                )
            else:
                await ctx.send(f"{prefix}banned {success_count} users{duration_text}")

            self.log_info(
                f"{ctx.author.name} {'dry-run ' if parsed['dry_run'] else ''}banned {success_count} users: {reason}"
            )

    @commands.command()
    async def kick(self, ctx, *, args: str = ""):
        if not is_mod(ctx.author):
            await ctx.send("you lack the required permissions")
            return

        if not args:
            await ctx.send('usage: kick {-s|-D} [@user|id|name] {"reason"}')
            return

        parsed = self.parser.parse_kick(args)
        targets, reason = await self.parser.parse_targets_and_reason(
            ctx, parsed["raw_args"]
        )
        members = await self.parser.resolve_users(ctx, targets)

        if not members:
            await ctx.send("no valid users provided")
            return

        valid_members, errors = self.parser.validate_targets(
            members, ctx.author, "kick", parsed["dry_run"]
        )

        if errors:
            await ctx.send("\n".join(errors))

        if not valid_members:
            return

        success_count = 0
        for member in valid_members:
            try:
                dm_sent = False
                if not parsed["silent"] and not parsed["dry_run"]:
                    dm_sent = await self.mod_helper.notify_user(
                        member,
                        ctx.guild,
                        "kicked",
                        reason,
                        moderator=ctx.author,
                    )

                infraction = self.mod_helper.create_infraction(
                    member.id,
                    ctx.author.id,
                    ctx.guild.id,
                    "kick" if not parsed["dry_run"] else "kick",
                    reason,
                    dm_sent=dm_sent,
                )

                if not parsed["silent"]:
                    await self.mod_helper.log_action(
                        self.bot,
                        ctx.guild,
                        "kick" if not parsed["dry_run"] else "kick",
                        ctx.author,
                        member,
                        reason,
                        infraction_id=infraction.id,
                    )

                if not parsed["dry_run"]:
                    await member.kick(reason=f"{ctx.author.name}: {reason}")

                success_count += 1

            except discord.HTTPException as e:
                await ctx.send(f"failed to kick {member.mention}: {e}")

        if success_count > 0:
            prefix = "[ TEST ] " if parsed["dry_run"] else ""
            if success_count == 1:
                await ctx.send(f"{prefix}kicked {valid_members[0].mention}")
            else:
                await ctx.send(f"{prefix}kicked {success_count} users")

            self.log_info(
                f"{ctx.author.name} {'dry-run ' if parsed['dry_run'] else ''}kicked {success_count} users: {reason}"
            )

    @commands.command()
    async def mute(self, ctx, *, args: str = ""):
        if not is_mod(ctx.author):
            await ctx.send("you lack the required permissions")
            return

        if not args:
            await ctx.send('usage: mute [-d dur] {-s|-D} [@user|id|name] {"reason"}')
            return

        config = self.mod_helper.get_config(ctx.guild.id)

        if not config.muted_role_id:
            await ctx.send("muted role not configured. use >config muted_role @role")
            return

        muted_role = ctx.guild.get_role(config.muted_role_id)
        if not muted_role:
            await ctx.send("muted role not found")
            return

        parsed = self.parser.parse_mute(args)
        targets, reason = await self.parser.parse_targets_and_reason(
            ctx, parsed["raw_args"]
        )
        members = await self.parser.resolve_users(ctx, targets)

        if not members:
            await ctx.send("no valid users provided")
            return

        valid_members, errors = self.parser.validate_targets(
            members, ctx.author, "mute", parsed["dry_run"]
        )

        if errors:
            await ctx.send("\n".join(errors))

        if not valid_members:
            return

        duration_seconds = None
        if parsed["duration"]:
            duration_seconds = parse_duration(parsed["duration"])
            if duration_seconds is None:
                await ctx.send(f"invalid duration: {parsed['duration']}")
                return

        success_count = 0
        for member in valid_members:
            try:
                if not parsed["dry_run"]:
                    await member.add_roles(
                        muted_role, reason=f"muted by {ctx.author.name}: {reason}"
                    )

                dm_sent = False
                if not parsed["silent"] and not parsed["dry_run"]:
                    dm_sent = await self.mod_helper.notify_user(
                        member,
                        ctx.guild,
                        "muted",
                        reason,
                        duration_seconds,
                        ctx.author,
                    )

                infraction = self.mod_helper.create_infraction(
                    member.id,
                    ctx.author.id,
                    ctx.guild.id,
                    "mute" if not parsed["dry_run"] else "mute",
                    reason,
                    duration=duration_seconds,
                    dm_sent=dm_sent,
                )
                await self.bot.get_cog(
                    "Achievements"
                ).ach_system.check_infraction_achievement(
                    str(member.id), infraction.type, ctx.guild
                )
                if not parsed["silent"]:
                    await self.mod_helper.log_action(
                        self.bot,
                        ctx.guild,
                        "mute" if not parsed["dry_run"] else "mute",
                        ctx.author,
                        member,
                        reason,
                        duration_seconds,
                        infraction.id,
                    )

                if (
                    not parsed["silent"]
                    and not parsed["dry_run"]
                    and config.mute_channel_id
                ):
                    mute_channel = ctx.guild.get_channel(config.mute_channel_id)
                    if mute_channel:
                        duration_text = (
                            f" for {format_relative_time(duration_seconds)}"
                            if duration_seconds
                            else ""
                        )
                        await mute_channel.send(
                            f"{member.mention}, you have been muted{duration_text}.\n"
                            f"**reason:** {reason}\n"
                            f"*if you believe this is a mistake, please wait for a moderator to respond*"
                        )

                success_count += 1

            except discord.HTTPException as e:
                await ctx.send(f"failed to mute {member.mention}: {e}")

        if success_count > 0:
            duration_text = (
                f" for {format_relative_time(duration_seconds)}"
                if duration_seconds
                else ""
            )
            prefix = "[ TEST ] " if parsed["dry_run"] else ""
            if success_count == 1:
                await ctx.send(
                    f"{prefix}muted {valid_members[0].mention}{duration_text}"
                )
            else:
                await ctx.send(f"{prefix}muted {success_count} users{duration_text}")

            self.log_info(
                f"{ctx.author.name} {'dry-run ' if parsed['dry_run'] else ''}muted {success_count} users: {reason}"
            )

    @commands.command()
    async def warn(self, ctx, *, args: str = ""):
        if not is_mod(ctx.author):
            await ctx.send("you lack the required permissions")
            return

        if not args:
            await ctx.send('usage: warn [@user|id|name] ["reason"]')
            return

        targets, reason = await self.parser.parse_targets_and_reason(ctx, args)
        members = await self.parser.resolve_users(ctx, targets)

        if not members:
            await ctx.send("no valid users provided")
            return

        valid_members, errors = self.parser.validate_targets(
            members, ctx.author, "warn"
        )

        if errors:
            await ctx.send("\n".join(errors))

        if not valid_members:
            return

        success_count = 0
        for member in valid_members:
            dm_sent = await self.mod_helper.notify_user(
                member, ctx.guild, "warned", reason, moderator=ctx.author
            )

            infraction = self.mod_helper.create_infraction(
                member.id, ctx.author.id, ctx.guild.id, "warn", reason, dm_sent=dm_sent
            )
            await self.bot.get_cog(
                "Achievements"
            ).ach_system.check_infraction_achievement(
                str(member.id), infraction.type, ctx.guild
            )
            await self.mod_helper.log_action(
                self.bot,
                ctx.guild,
                "warn",
                ctx.author,
                member,
                reason,
                infraction_id=infraction.id,
            )

            success_count += 1

        if success_count == 1:
            await ctx.send(f"warned {valid_members[0].mention}")
        else:
            await ctx.send(f"warned {success_count} users")

        self.log_info(f"{ctx.author.name} warned {success_count} users: {reason}")

    @commands.command()
    async def pardon(self, ctx, *, args: str = ""):
        if not is_mod(ctx.author):
            await ctx.send("you lack the required permissions")
            return

        if not args:
            await ctx.send('usage: pardon [@user|id|name] {-b|-m|-r} [id] {"reason"}')
            return

        parsed = self.parser.parse_pardon(args)
        targets, reason = await self.parser.parse_targets_and_reason(
            ctx, parsed["raw_args"]
        )
        members = await self.parser.resolve_users(ctx, targets)

        if not members:
            await ctx.send("no valid users provided")
            return

        config = self.mod_helper.get_config(ctx.guild.id)

        for member in members:
            actions_taken = []

            if parsed["unban"]:
                try:
                    await ctx.guild.unban(member, reason=f"{ctx.author.name}: {reason}")
                    actions_taken.append("unbanned")
                except discord.NotFound:
                    pass
                except discord.HTTPException:
                    pass

            if parsed["unmute"]:
                if config.muted_role_id:
                    muted_role = ctx.guild.get_role(config.muted_role_id)
                    if muted_role and muted_role in member.roles:
                        await member.remove_roles(
                            muted_role,
                            reason=f"unmuted by {ctx.author.name}: {reason}",
                        )
                        actions_taken.append("unmuted")

            if parsed["remove_infraction"]:
                session = get_session()
                try:
                    if parsed["remove_infraction"] == "latest":
                        latest = (
                            session.query(Infraction)
                            .filter_by(
                                user_id=member.id, guild_id=ctx.guild.id, active=True
                            )
                            .order_by(Infraction.created_at.desc())
                            .first()
                        )

                        if latest:
                            latest.active = False
                            session.commit()
                            actions_taken.append(f"removed case #{latest.id}")
                    else:
                        infraction = (
                            session.query(Infraction)
                            .filter_by(
                                id=parsed["remove_infraction"], guild_id=ctx.guild.id
                            )
                            .first()
                        )

                        if infraction:
                            infraction.active = False
                            session.commit()
                            actions_taken.append(f"removed case #{infraction.id}")
                finally:
                    session.close()

            if actions_taken:
                await ctx.send(f"{member.mention}: {', '.join(actions_taken)}")
                self.log_info(
                    f"{ctx.author.name} pardoned {member.name}: {', '.join(actions_taken)}"
                )
            else:
                await ctx.send(f"no actions taken for {member.mention}")

    @commands.command()
    async def slowmode(self, ctx, duration: str = "0s"):
        if not is_mod(ctx.author):
            await ctx.send("you lack the required permissions")
            return

        duration_seconds = parse_duration(duration)

        if duration_seconds is None:
            await ctx.send(f"invalid duration: {duration}")
            return

        if duration_seconds > 21600:
            await ctx.send("slowmode cannot exceed 6 hours")
            return

        try:
            await ctx.channel.edit(slowmode_delay=duration_seconds)

            if duration_seconds == 0:
                await ctx.send("slowmode disabled")
            else:
                await ctx.send(
                    f"slowmode set to {format_relative_time(duration_seconds)}"
                )

            self.log_info(
                f"{ctx.author.name} set slowmode to {duration_seconds}s in #{ctx.channel.name}"
            )

        except discord.HTTPException as e:
            await ctx.send(f"failed to set slowmode: {e}")

    @commands.command(aliases=["warnings", "infractions"])
    async def cases(self, ctx, target: str = None):
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

        infractions = self.mod_helper.get_user_infractions(member.id, ctx.guild.id)

        if not infractions:
            await ctx.send(f"{member.mention} has no infractions")
            return

        active_count = sum(1 for i in infractions if i.active)

        msg = f"**moderation history for {member.name}**\n"
        msg += f"total: {len(infractions)} | active: {active_count}\n\n"

        for infraction in infractions[:10]:
            status = "[ACTIVE]" if infraction.active else "[RESOLVED]"
            moderator = ctx.guild.get_member(infraction.moderator_id)
            mod_name = moderator.name if moderator else f"id:{infraction.moderator_id}"

            msg += f"{status} case #{infraction.id} - {infraction.type}\n"
            msg += f"  reason: {infraction.reason}\n"
            msg += f"  moderator: {mod_name}\n"
            msg += f"  date: {format_timestamp(infraction.created_at)}\n"

            if infraction.duration:
                msg += f"  duration: {format_relative_time(infraction.duration)}\n"

            msg += "\n"

        if len(infractions) > 10:
            msg += f"-# showing 10 of {len(infractions)} infractions"

        await ctx.send(msg)

    @commands.group(invoke_without_command=True)
    async def config(self, ctx):
        if not is_op(ctx.author):
            await ctx.send("requires operator mode. run >op first")
            return

        config = self.mod_helper.get_config(ctx.guild.id)

        log_ch = (
            ctx.guild.get_channel(config.log_channel_id)
            if config.log_channel_id
            else None
        )
        mute_ch = (
            ctx.guild.get_channel(config.mute_channel_id)
            if config.mute_channel_id
            else None
        )

        muted_role = (
            ctx.guild.get_role(config.muted_role_id) if config.muted_role_id else None
        )
        mod_role = (
            ctx.guild.get_role(config.mod_role_id) if config.mod_role_id else None
        )
        op_role = ctx.guild.get_role(config.op_role_id) if config.op_role_id else None

        msg = "**moderation configuration**\n\n"
        msg += "**channels**\n"
        msg += f"log: {log_ch.mention if log_ch else 'not set'}\n"
        msg += f"mute: {mute_ch.mention if mute_ch else 'not set'}\n\n"
        msg += "**roles**\n"
        msg += f"muted: {muted_role.mention if muted_role else 'not set'}\n"
        msg += f"mod: {mod_role.mention if mod_role else 'not set'}\n"
        msg += f"op: {op_role.mention if op_role else 'not set'}"

        await ctx.send(msg)

    @config.command(name="log_channel")
    async def config_log_channel(self, ctx, channel: discord.TextChannel):
        if not is_op(ctx.author):
            await ctx.send("requires operator mode. run >op first")
            return

        self.mod_helper.update_config(ctx.guild.id, log_channel_id=channel.id)
        await ctx.send(f"set log channel to {channel.mention}")

    @config.command(name="mute_channel")
    async def config_mute_channel(self, ctx, channel: discord.TextChannel):
        if not is_op(ctx.author):
            await ctx.send("requires operator mode. run >op first")
            return

        self.mod_helper.update_config(ctx.guild.id, mute_channel_id=channel.id)
        await ctx.send(f"set mute channel to {channel.mention}")

    @config.command(name="muted_role")
    async def config_muted_role(self, ctx, role: discord.Role):
        if not is_op(ctx.author):
            await ctx.send("requires operator mode. run >op first")
            return

        self.mod_helper.update_config(ctx.guild.id, muted_role_id=role.id)
        await ctx.send(f"set muted role to {role.mention}")

    @config.command(name="mod_role")
    async def config_mod_role(self, ctx, role: discord.Role):
        if not is_op(ctx.author):
            await ctx.send("requires operator mode. run >op first")
            return

        self.mod_helper.update_config(ctx.guild.id, mod_role_id=role.id)
        await ctx.send(f"set mod role to {role.mention}")

    @config.command(name="op_role")
    async def config_op_role(self, ctx, role: discord.Role):
        if not is_op(ctx.author):
            await ctx.send("requires operator mode. run >op first")
            return

        self.mod_helper.update_config(ctx.guild.id, op_role_id=role.id)
        await ctx.send(f"set op role to {role.mention}")


async def setup(bot):
    await bot.add_cog(ModerationCommands(bot))
