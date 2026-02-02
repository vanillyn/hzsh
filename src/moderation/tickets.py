import traceback
from datetime import datetime
from types import TracebackType

import discord
from discord.client import T
from discord.errors import Forbidden
from discord.ext import commands

from ..misc.db import Ticket, get_session
from ..misc.utils import CogHelper
from .utils import ModerationHelper, is_mod


class Tickets(CogHelper, commands.Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.mod_helper = ModerationHelper()

    async def cog_check(self, ctx):
        return ctx.guild is not None

    def get_ticket_by_channel(self, channel_id):
        """get ticket by channel id"""
        session = get_session()
        try:
            return session.query(Ticket).filter_by(channel_id=channel_id).first()
        finally:
            session.close()

    def get_ticket_by_id(self, ticket_id, guild_id):
        """get ticket by id"""
        session = get_session()
        try:
            return (
                session.query(Ticket).filter_by(id=ticket_id, guild_id=guild_id).first()
            )
        finally:
            session.close()

    def get_ticket_by_name(self, name, guild_id):
        """get ticket by name"""
        session = get_session()
        try:
            return (
                session.query(Ticket)
                .filter_by(name=name, guild_id=guild_id, archived=False)
                .first()
            )
        finally:
            session.close()

    @commands.group(invoke_without_command=True)
    async def tickets(self, ctx):
        help_text = """```
ticket command help -
tickets new [name] {@users} - create a new ticket
tickets remove [id/name] - close and delete a ticket
tickets modify [id/name] [add/remove|rename] [@users|newname] - modify ticket access
tickets archive [id] - archive a ticket
tickets list - list all tickets
```"""
        await ctx.send(help_text)

    @tickets.command(name="new", aliases=["create"])
    async def tickets_new(self, ctx, name: str, *users: discord.Member):
        config = self.mod_helper.get_config(ctx.guild.id)

        category = None
        if config.ticket_category_id:
            category = ctx.guild.get_channel(config.ticket_category_id)

        mod_role = None
        if config.mod_role_id:
            mod_role = ctx.guild.get_role(config.mod_role_id)

        session = get_session()
        try:
            ticket_count = (
                session.query(Ticket).filter_by(guild_id=ctx.guild.id).count()
            )
        finally:
            session.close()

        ticket_number = ticket_count + 1
        channel_name = f"{ticket_number}-{name}"

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.author: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True,
            ),
            ctx.guild.me: discord.PermissionOverwrite(
                read_messages=True,
                read_message_history=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
            ),
        }

        if mod_role:
            overwrites[mod_role] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True,
            )

        for user in users:
            overwrites[user] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True,
            )

        try:
            channel = await ctx.guild.create_text_channel(
                f"{ticket_number}-{name}",
                category=category,
                overwrites=overwrites,
                reason=f"Ticket created by {ctx.author.name}",
            )
        except discord.Forbidden as e:
            await ctx.send(
                f"permission error: {traceback.print_exc()} ({e.code} - {e.text})"
            )
            return
        except discord.HTTPException as e:
            await ctx.send(f"[http]: {e.text} (Code: {e.code})")
            return
        except Exception as e:
            await ctx.send(f"an unexpected error occurred: {e}")
            return

        session = get_session()
        try:
            ticket = Ticket(
                channel_id=channel.id,
                guild_id=ctx.guild.id,
                creator_id=ctx.author.id,
                name=name,
            )

            for user in users:
                ticket.add_user(user.id)

            session.add(ticket)
            session.commit()
            session.refresh(ticket)

            embed = discord.Embed(
                title=f"ticket #{ticket.id}: {name}",
                description=f"ticket created by {ctx.author.mention}",
                color=discord.Color.green(),
                timestamp=datetime.utcnow(),
            )

            embed.add_field(
                name="what happens now?",
                value="a moderator will respond to your ticket as soon as possible.\n"
                "please describe your issue in detail.",
                inline=False,
            )

            if users:
                user_mentions = ", ".join(u.mention for u in users)
                embed.add_field(
                    name="users with access", value=user_mentions, inline=False
                )

            await channel.send(embed=embed)

            await ctx.send(f"created ticket {channel.mention}")
            self.log_info(f"{ctx.author.name} created ticket #{ticket.id}: {name}")

        finally:
            session.close()

    @tickets.command(name="remove", aliases=["close", "delete"])
    async def tickets_remove(self, ctx, identifier: str):
        ticket = None
        try:
            ticket_id = int(identifier)
            ticket = self.get_ticket_by_id(ticket_id, ctx.guild.id)
        except ValueError:
            ticket = self.get_ticket_by_name(identifier, ctx.guild.id)

        if not ticket:
            await ctx.send(f"ticket not found: {identifier}")
            return

        if ticket.creator_id != ctx.author.id and not is_mod(ctx.author):
            await ctx.send("only the creator or moderators can close this ticket")
            return

        channel = ctx.guild.get_channel(ticket.channel_id)

        session = get_session()
        try:
            session.delete(ticket)
            session.commit()
        finally:
            session.close()

        if channel:
            try:
                await channel.delete(reason=f"ticket closed by {ctx.author.name}")
            except discord.HTTPException:
                pass

        if ctx.channel.id != ticket.channel_id:
            await ctx.send(f"closed ticket #{ticket.id}")

        self.log_info(f"{ctx.author.name} closed ticket #{ticket.id}")

    @tickets.command(name="modify", aliases=["edit"])
    async def tickets_modify(self, ctx, identifier: str, action: str, *targets):
        ticket = None
        try:
            ticket_id = int(identifier)
            ticket = self.get_ticket_by_id(ticket_id, ctx.guild.id)
        except ValueError:
            ticket = self.get_ticket_by_name(identifier, ctx.guild.id)

        if not ticket:
            await ctx.send(f"ticket not found: {identifier}")
            return

        if ticket.creator_id != ctx.author.id and not is_mod(ctx.author):
            await ctx.send("only the creator or moderators can modify this ticket")
            return

        channel = ctx.guild.get_channel(ticket.channel_id)
        if not channel:
            await ctx.send("ticket channel not found")
            return

        action = action.lower()

        if action in ["add", "invite"]:
            if not targets:
                await ctx.send("provide users to add")
                return

            added = []
            for target in targets:
                try:
                    member = await commands.MemberConverter().convert(ctx, target)

                    session = get_session()
                    try:
                        ticket = session.query(Ticket).filter_by(id=ticket.id).first()
                        ticket.add_user(member.id)
                        session.commit()
                    finally:
                        session.close()

                    await channel.set_permissions(
                        member,
                        read_messages=True,
                        send_messages=True,
                        embed_links=True,
                        attach_files=True,
                        read_message_history=True,
                    )

                    added.append(member.mention)
                except (commands.BadArgument, discord.HTTPException):
                    continue

            if added:
                await ctx.send(f"added {', '.join(added)} to ticket")
                await channel.send(
                    f"{', '.join(added)} added to ticket by {ctx.author.mention}"
                )
                self.log_info(f"{ctx.author.name} added users to ticket #{ticket.id}")
            else:
                await ctx.send("no users added")

        elif action in ["remove", "kick"]:
            if not targets:
                await ctx.send("provide users to remove")
                return

            removed = []
            for target in targets:
                try:
                    if target.startswith("@&") or target == "@mods":
                        config = self.mod_helper.get_config(ctx.guild.id)
                        if config.mod_role_id:
                            mod_role = ctx.guild.get_role(config.mod_role_id)
                            if mod_role:
                                await channel.set_permissions(mod_role, overwrite=None)

                                session = get_session()
                                try:
                                    ticket = (
                                        session.query(Ticket)
                                        .filter_by(id=ticket.id)
                                        .first()
                                    )
                                    ticket.mods_removed = True
                                    session.commit()
                                finally:
                                    session.close()

                                removed.append("moderators")
                        continue

                    member = await commands.MemberConverter().convert(ctx, target)

                    session = get_session()
                    try:
                        ticket = session.query(Ticket).filter_by(id=ticket.id).first()
                        ticket.remove_user(member.id)
                        session.commit()
                    finally:
                        session.close()

                    await channel.set_permissions(member, overwrite=None)

                    removed.append(member.mention)
                except (commands.BadArgument, discord.HTTPException):
                    continue

            if removed:
                await ctx.send(f"removed {', '.join(removed)} from ticket")
                self.log_info(
                    f"{ctx.author.name} removed users from ticket #{ticket.id}"
                )
            else:
                await ctx.send("no users removed")

        elif action in ["rename", "name"]:
            if not targets:
                await ctx.send("provide new name")
                return

            new_name = " ".join(targets)

            session = get_session()
            try:
                ticket = session.query(Ticket).filter_by(id=ticket.id).first()
                old_name = ticket.name
                ticket.name = new_name
                session.commit()
            finally:
                session.close()

            new_channel_name = f"{ticket.id}-{new_name}"
            try:
                await channel.edit(name=new_channel_name)
                await ctx.send(f"renamed ticket from `{old_name}` to `{new_name}`")
                self.log_info(f"{ctx.author.name} renamed ticket #{ticket.id}")
            except discord.HTTPException as e:
                await ctx.send(f"failed to rename channel: {e}")

        else:
            await ctx.send(f"unknown action: {action}")

    @tickets.command(name="archive")
    async def tickets_archive(self, ctx, ticket_id: int):
        """archive a ticket"""
        if not is_mod(ctx.author):
            await ctx.send("only moderators can archive tickets")
            return

        ticket = self.get_ticket_by_id(ticket_id, ctx.guild.id)

        if not ticket:
            await ctx.send(f"ticket #{ticket_id} not found")
            return

        channel = ctx.guild.get_channel(ticket.channel_id)
        if not channel:
            await ctx.send("ticket channel not found")
            return

        config = self.mod_helper.get_config(ctx.guild.id)

        archive_category = None
        if config.archive_category_id:
            archive_category = ctx.guild.get_channel(config.archive_category_id)

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.guild.me: discord.PermissionOverwrite(
                read_messages=True, send_messages=True
            ),
        }

        try:
            await channel.edit(
                category=archive_category,
                overwrites=overwrites,
                reason=f"archived by {ctx.author.name}",
            )

            session = get_session()
            try:
                ticket = session.query(Ticket).filter_by(id=ticket_id).first()
                ticket.archived = True
                ticket.closed_at = datetime.utcnow()
                session.commit()
            finally:
                session.close()

            await ctx.send(f"archived ticket #{ticket_id}")

            embed = discord.Embed(
                title="ticket archived",
                description=f"this ticket has been archived by {ctx.author.mention}",
                color=discord.Color.greyple(),
                timestamp=datetime.utcnow(),
            )
            await channel.send(embed=embed)

            self.log_info(f"{ctx.author.name} archived ticket #{ticket_id}")

        except discord.HTTPException as e:
            await ctx.send(f"failed to archive ticket: {e}")

    @tickets.command(name="list")
    async def tickets_list(self, ctx):
        """list all active tickets"""
        if not is_mod(ctx.author):
            await ctx.send("only moderators can list tickets")
            return

        session = get_session()
        try:
            tickets = (
                session.query(Ticket)
                .filter_by(guild_id=ctx.guild.id, archived=False)
                .order_by(Ticket.created_at.desc())
                .all()
            )
        finally:
            session.close()

        if not tickets:
            await ctx.send("no active tickets")
            return

        embed = discord.Embed(
            title="active tickets",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow(),
        )

        for ticket in tickets[:15]:
            creator = ctx.guild.get_member(ticket.creator_id)
            creator_name = creator.mention if creator else f"id:{ticket.creator_id}"

            channel = ctx.guild.get_channel(ticket.channel_id)
            channel_mention = channel.mention if channel else "deleted"

            from ..misc.db import format_timestamp

            embed.add_field(
                name=f"#{ticket.id}: {ticket.name}",
                value=f"creator: {creator_name}\n"
                f"channel: {channel_mention}\n"
                f"created: {format_timestamp(ticket.created_at)}",
                inline=False,
            )

        if len(tickets) > 15:
            embed.set_footer(text=f"showing 15 of {len(tickets)} tickets")

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Tickets(bot))
