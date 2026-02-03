from typing import List, Tuple

import discord
from discord.ext import commands


class ModCommandParser:
    @staticmethod
    async def parse_targets_and_reason(
        ctx: commands.Context, args: str
    ) -> Tuple[List[str], str]:
        """extract user targets (mentions/ids/usernames) and reason from args"""
        parts = args.split()
        targets = []
        reason_parts = []

        i = 0
        while i < len(parts):
            part = parts[i]

            # mention
            if part.startswith("<@") and part.endswith(">"):
                if not reason_parts:
                    targets.append(part)
                else:
                    reason_parts.append(part)
            # snowflake id
            elif part.isdigit() and len(part) >= 17 and not reason_parts:
                targets.append(part)
            # everything else is reason once we hit non-target
            else:
                reason_parts.append(part)

            i += 1

        return targets, " ".join(reason_parts) if reason_parts else "no reason provided"

    @staticmethod
    def parse_ban(args: str) -> dict:
        result = {
            "duration": None,
            "quick": False,
            "silent": False,
            "purge": True,
            "dry_run": False,
            "raw_args": "",
        }

        parts = args.split()
        i = 0
        remaining = []

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
            if part == "-D":
                result["dry_run"] = True
                i += 1
                continue

            remaining.append(part)
            i += 1

        result["raw_args"] = " ".join(remaining)
        return result

    @staticmethod
    def parse_kick(args: str) -> dict:
        result = {"silent": False, "dry_run": False, "raw_args": ""}

        parts = args.split()
        i = 0
        remaining = []

        while i < len(parts):
            part = parts[i]

            if part == "-s":
                result["silent"] = True
                i += 1
                continue
            if part == "-D":
                result["dry_run"] = True
                i += 1
                continue

            remaining.append(part)
            i += 1

        result["raw_args"] = " ".join(remaining)
        return result

    @staticmethod
    def parse_mute(args: str) -> dict:
        result = {
            "duration": None,
            "silent": False,
            "dry_run": False,
            "raw_args": "",
        }

        parts = args.split()
        i = 0
        remaining = []

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
            if part == "-D":
                result["dry_run"] = True
                i += 1
                continue

            remaining.append(part)
            i += 1

        result["raw_args"] = " ".join(remaining)
        return result

    @staticmethod
    def parse_pardon(args: str) -> dict:
        result = {
            "unban": False,
            "unmute": False,
            "remove_infraction": None,
            "raw_args": "",
        }

        parts = args.split()
        i = 0
        remaining = []

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

            remaining.append(part)
            i += 1

        result["raw_args"] = " ".join(remaining)

        if (
            not result["unban"]
            and not result["unmute"]
            and result["remove_infraction"] is None
        ):
            result["remove_infraction"] = "latest"

        return result

    @staticmethod
    async def resolve_users(
        ctx: commands.Context, targets: List[str]
    ) -> List[discord.Member]:
        """resolve mentions, ids, and usernames to member objects"""
        members = []
        converter = commands.MemberConverter()

        for target in targets:
            try:
                member = await converter.convert(ctx, target)
                members.append(member)
            except commands.BadArgument:
                continue

        return members

    @staticmethod
    def validate_targets(
        members: List[discord.Member],
        author: discord.Member,
        action: str,
        dry_run: bool = False,
    ) -> Tuple[List[discord.Member], List[str]]:
        valid = []
        errors = []

        for member in members:
            if not dry_run:
                if member == author:
                    errors.append(f"cant {action} yourself")
                    continue

                if member.bot:
                    errors.append(f"cant {action} bots")
                    continue

                if any(
                    role.name in ["staff@hazelrun", "mod@hazelrun"]
                    for role in member.roles
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
    duration: str = None,
    reason: str = "no reason provided",
    quick: bool = False,
    dry_run: bool = False,
) -> bool:
    if quick:
        return True

    from .utils import is_op

    if is_op(ctx.author) and not dry_run:
        return True

    target_names = ", ".join(f"**{t.name}**" for t in targets)

    prefix = "[DRY RUN] " if dry_run else ""

    if len(targets) == 1:
        msg = f"{prefix}{action} {target_names}"
    else:
        msg = f"{prefix}{action} {len(targets)} users: {target_names}"

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
