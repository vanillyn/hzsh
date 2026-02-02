from typing import List, Tuple

import discord
from discord.ext import commands


class ModCommandParser:
    @staticmethod
    def parse_ban(args: str) -> dict:
        """
        ban {-d [duration]} {-q|-s|-p} [@user] {"reason"}
        """
        result = {
            "duration": None,
            "quick": False,
            "silent": False,
            "purge": True,
            "users": [],
            "reason": "no reason provided",
        }

        parts = args.split()
        i = 0
        user_mentions = []
        reason_parts = []

        while i < len(parts):
            part = parts[i]

            if part == "-d" and i + 1 < len(parts):
                result["duration"] = parts[i + 1]
                i += 2
                continue

            if part == "-q":
                result["quick"] = True
                i += 1
                continue
            if part == "-s":
                result["silent"] = True
                i += 1
                continue

            if part == "-p":
                result["purge"] = False
                i += 1
                continue

            if part.startswith("<@") and part.endswith(">"):
                user_mentions.append(part)
                i += 1
                continue
            reason_parts.append(part)
            i += 1

        result["users"] = user_mentions
        if reason_parts:
            result["reason"] = " ".join(reason_parts)

        return result

    @staticmethod
    def parse_kick(args: str) -> dict:
        """
        kick [@user] {-s} {"reason"}
        """
        result = {"silent": False, "users": [], "reason": "no reason provided"}

        parts = args.split()
        i = 0
        user_mentions = []
        reason_parts = []

        while i < len(parts):
            part = parts[i]

            if part == "-s":
                result["silent"] = True
                i += 1
                continue

            if part.startswith("<@") and part.endswith(">"):
                user_mentions.append(part)
                i += 1
                continue

            reason_parts.append(part)
            i += 1

        result["users"] = user_mentions
        if reason_parts:
            result["reason"] = " ".join(reason_parts)

        return result

    @staticmethod
    def parse_mute(args: str) -> dict:
        """
        mute [-d duration] {-s} [@user] {"reason"}
        """
        result = {
            "duration": None,
            "silent": False,
            "users": [],
            "reason": "no reason provided",
        }

        parts = args.split()
        i = 0
        user_mentions = []
        reason_parts = []

        while i < len(parts):
            part = parts[i]

            if part == "-d" and i + 1 < len(parts):
                result["duration"] = parts[i + 1]
                i += 2
                continue

            if part == "-s":
                result["silent"] = True
                i += 1
                continue

            if part.startswith("<@") and part.endswith(">"):
                user_mentions.append(part)
                i += 1
                continue

            reason_parts.append(part)
            i += 1

        result["users"] = user_mentions
        if reason_parts:
            result["reason"] = " ".join(reason_parts)

        return result

    @staticmethod
    def parse_pardon(args: str) -> dict:
        """
        pardon [@user] {-b|-m|-r} [id] {"reason"}
        """
        result = {
            "unban": False,
            "unmute": False,
            "remove_infraction": None,
            "users": [],
            "reason": "no reason provided",
        }

        parts = args.split()
        i = 0
        user_mentions = []
        reason_parts = []

        while i < len(parts):
            part = parts[i]

            if part in ["-b", "-br", "-rb"]:
                result["unban"] = True
                if "r" in part:
                    result["remove_infraction"] = "latest"
                i += 1
                continue

            if part in ["-m", "-mr", "-rm"]:
                result["unmute"] = True
                if "r" in part:
                    result["remove_infraction"] = "latest"
                i += 1
                continue

            if part == "-r":
                if i + 1 < len(parts) and parts[i + 1].isdigit():
                    result["remove_infraction"] = int(parts[i + 1])
                    i += 2
                else:
                    result["remove_infraction"] = "latest"
                    i += 1
                continue
            if part.startswith("<@") and part.endswith(">"):
                user_mentions.append(part)
                i += 1
                continue

            if part.isdigit() and not result["remove_infraction"]:
                result["remove_infraction"] = int(part)
                i += 1
                continue

            reason_parts.append(part)
            i += 1

        result["users"] = user_mentions
        if reason_parts:
            result["reason"] = " ".join(reason_parts)

        if (
            not result["unban"]
            and not result["unmute"]
            and result["remove_infraction"] is None
        ):
            result["remove_infraction"] = "latest"

        return result

    @staticmethod
    async def convert_mentions_to_members(
        ctx: commands.Context, mentions: List[str]
    ) -> List[discord.Member]:
        """convert mention strings to member objects"""
        members = []
        converter = commands.MemberConverter()

        for mention in mentions:
            try:
                member = await converter.convert(ctx, mention)
                members.append(member)
            except commands.BadArgument:
                continue

        return members

    @staticmethod
    def validate_targets(
        members: List[discord.Member], author: discord.Member, action: str
    ) -> Tuple[List[discord.Member], List[str]]:
        valid = []
        errors = []

        for member in members:
            if member == author:
                errors.append(f"cant {action} yourself")
                continue

            if member.bot:
                errors.append(f"cant {action} bots")
                continue

            if any(
                role.name in ["staff@hazelrun", "mod@hazelrun"] for role in member.roles
            ):
                errors.append(f"cant {action} staff members")
                continue

            if member.top_role >= author.top_role:
                errors.append(f"cant {action} {member.mention} (higher role)")
                continue

            valid.append(member)

        return valid, errors


class Confirm(discord.ui.View):
    def __init__(self, author: discord.Member, timeout: float = 30.0):
        super().__init__(timeout=timeout)
        self.author = author
        self.value = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "this confirmation is not for you", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="yes", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.value = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="no", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.defer()
        self.stop()


async def confirm_action(
    ctx,
    action: str,
    targets: list,
    duration: Optional[str] = None,
    reason: str = "no reason provided",
    quick: bool = False,
) -> bool:
    if quick:
        return True

    from .utils import is_op

    if is_op(ctx.author):
        return True

    target_names = ", ".join(f"**{t.name}**" for t in targets)

    if len(targets) == 1:
        msg = f"{action} {target_names}"
    else:
        msg = f"{action} {len(targets)} users: {target_names}"

    if duration:
        from ..misc.db import format_relative_time, parse_duration

        duration_seconds = parse_duration(duration)
        if duration_seconds:
            msg += f" for **{format_relative_time(duration_seconds)}**"
        else:
            msg += " **permanently**"
    else:
        msg += " **permanently**"

    msg += f"\nreason: {reason}"
    msg += "\n\nare you sure?"

    view = Confirm(ctx.author, timeout=30.0)

    confirm_msg = await ctx.send(msg, view=view)

    await view.wait()

    try:
        await confirm_msg.delete()
    except discord.HTTPException:
        pass

    if view.value is None:
        await ctx.send("confirmation timed out")
        return False

    if not view.value:
        await ctx.send("cancelled")
        return False

    return True
