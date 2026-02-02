import discord
from discord.ext import commands

import config
from src.achievements.utils import get_achievement_system
from src.misc import CogHelper, is_staff


class AchCommands(CogHelper, commands.Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.ach_system = get_achievement_system()

    @commands.command(aliases=["achs", "achievement", "ach", "quests"])
    async def achievements(self, ctx, *args):
        """view and manage achievements"""

        if not args:
            user_id = str(ctx.author.id)
            user_achs = self.ach_system.get_user_achievements(user_id)
            xp = self.ach_system.get_user_xp(user_id)
            level, current_xp, xp_needed = self.ach_system.get_level(xp)

            if not user_achs:
                await ctx.send(
                    f"**{ctx.author.display_name}s achievements**\n"
                    f"level {level} | {current_xp}/{xp_needed} xp\n\n"
                    "no achievements unlocked yet"
                )
                return

            msg = f"**{ctx.author.display_name}s achievements**\n"
            msg += f"level {level} | {current_xp}/{xp_needed} xp\n\n"
            msg += f"**unlocked: {len(user_achs)}**\n\n"

            for ach_id in user_achs:
                if ach_id not in config.ACHIEVEMENTS:
                    continue
                ach = config.ACHIEVEMENTS[ach_id]
                msg += f"`☆` **{ach['name']}** ({ach['rarity']})\n  ⋱ {ach['description']}\n"

            await ctx.send(msg)
            return

        if args[0] in ["-a", "--all"]:
            user_id = str(ctx.author.id)
            user_achs = self.ach_system.get_user_achievements(user_id)
            xp = self.ach_system.get_user_xp(user_id)
            level, current_xp, xp_needed = self.ach_system.get_level(xp)

            visible_count = sum(
                1
                for ach_id in config.ACHIEVEMENTS
                if config.ACHIEVEMENTS[ach_id]["rarity"] not in ["master", "legendary"]
            )
            visible_count += sum(
                1
                for ach_id in user_achs
                if ach_id in config.ACHIEVEMENTS
                and config.ACHIEVEMENTS[ach_id]["rarity"] in ["master", "legendary"]
            )

            msg = f"**{ctx.author.display_name}s achievements**\n"
            msg += f"level {level} | {current_xp}/{xp_needed} xp\n\n"
            msg += f"**unlocked: {len(user_achs)}/{visible_count}**\n\n"

            for ach_id in config.ACHIEVEMENTS:
                ach = config.ACHIEVEMENTS[ach_id]
                user_has = ach_id in user_achs
                if ach["rarity"] in ["master", "legendary"] and not user_has:
                    continue

                if user_has:
                    msg += f"`☆` **{ach['name']}** ({ach['rarity']})\n  ⋱ {ach['description']}\n"
                else:
                    if ach["rarity"] == "rare":
                        msg += f"`☆` ||**{ach['name']}**|| ({ach['rarity']})\n  ⋱ ||{ach['description']}||\n"
                    else:
                        msg += f"`☆` **{ach['name']}** ({ach['rarity']})\n  ⋱ {ach['description']}\n"

            await ctx.send(msg)
            return

        if args[0] in ["-g", "--grant"]:
            if not is_staff(ctx.author):
                await ctx.send("you lack the required permissions")
                return

            if len(args) < 3 or args[1] not in ["-u"]:
                await ctx.send("usage: >achievements -g -u user achievement_name")
                return

            try:
                member = await commands.MemberConverter().convert(ctx, args[2])
            except discord.errors.NotFound:
                await ctx.send("user not found")
                return

            achievement_name = " ".join(args[3:]) if len(args) > 3 else args[2]

            ach_id = None
            for aid, adata in config.ACHIEVEMENTS.items():
                if (
                    aid == achievement_name
                    or adata["name"].lower() == achievement_name.lower()
                ):
                    ach_id = aid
                    break

            if not ach_id:
                await ctx.send(f"achievement not found: {achievement_name}")
                return

            success = await self.ach_system.grant_achievement(
                str(member.id), ach_id, ctx.guild, ctx.channel
            )

            if success:
                await ctx.send(f"granted achievement {ach_id} to {member.mention}")
                self.log_info(
                    f"achievement {ach_id} granted to {member.id} by {ctx.author.id}"
                )
            else:
                await ctx.send(f"{member.mention} already has this achievement")

        elif args[0] in ["-r", "--revoke"]:
            if not is_staff(ctx.author):
                await ctx.send("you lack the required permissions")
                return

            if len(args) < 3 or args[1] not in ["-u"]:
                await ctx.send("usage: >achievements -r -u user achievement_name")
                return

            try:
                member = await commands.MemberConverter().convert(ctx, args[2])
            except discord.errors.NotFound:
                await ctx.send("user not found")
                return

            achievement_name = " ".join(args[3:]) if len(args) > 3 else args[2]

            ach_id = None
            for aid, adata in config.ACHIEVEMENTS.items():
                if (
                    aid == achievement_name
                    or adata["name"].lower() == achievement_name.lower()
                ):
                    ach_id = aid
                    break

            if not ach_id:
                await ctx.send(f"achievement not found: {achievement_name}")
                return

            success = await self.ach_system.revoke_achievement(
                str(member.id), ach_id, ctx.guild
            )

            if success:
                await ctx.send(f"revoked achievement {ach_id} from {member.mention}")
                self.log_info(
                    f"achievement {ach_id} revoked from {member.id} by {ctx.author.id}"
                )
            else:
                await ctx.send(f"{member.mention} doesnt have this achievement")

        elif args[0] in ["-u"]:
            if len(args) < 2:
                await ctx.send("usage: >achievements -u user")
                return

            try:
                member = await commands.MemberConverter().convert(ctx, args[1])
            except discord.errors.NotFound:
                await ctx.send("user not found")
                return

            user_id = str(member.id)
            user_achs = self.ach_system.get_user_achievements(user_id)
            xp = self.ach_system.get_user_xp(user_id)
            level, current_xp, xp_needed = self.ach_system.get_level(xp)

            if not user_achs:
                await ctx.send(
                    f"**{member.display_name}s achievements**\n"
                    f"level {level} | {current_xp}/{xp_needed} xp\n\n"
                    "no achievements unlocked yet"
                )
                return

            msg = f"**{member.display_name}s achievements**\n"
            msg += f"level {level} | {current_xp}/{xp_needed} xp\n\n"
            msg += f"**unlocked: {len(user_achs)}**\n\n"

            for ach_id in user_achs:
                if ach_id not in config.ACHIEVEMENTS:
                    continue
                ach = config.ACHIEVEMENTS[ach_id]
                msg += f"`☆` **{ach['name']}** ({ach['rarity']})\n  ⋱ {ach['description']}\n"

            await ctx.send(msg)

    @commands.command()
    async def leaderboard(self, ctx, page: int = 1):
        """view xp leaderboard"""
        all_xp = self.ach_system.xp
        sorted_users = sorted(all_xp.items(), key=lambda x: x[1], reverse=True)

        if not sorted_users:
            await ctx.send("no users on the leaderboard yet")
            return

        user_rank = None
        user_xp_val = self.ach_system.get_user_xp(str(ctx.author.id))
        for i, (uid, xp) in enumerate(sorted_users, 1):
            if uid == str(ctx.author.id):
                user_rank = i
                break

        per_page = 10
        total_pages = (len(sorted_users) + per_page - 1) // per_page
        page = max(1, min(page, total_pages))

        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page

        msg = f"**xp leaderboard** (page {page}/{total_pages})\n"
        if user_rank:
            level, _, _ = self.ach_system.get_level(user_xp_val)
            msg += f"-# your rank: #{user_rank} | level {level} | {user_xp_val} xp\n\n"
        else:
            msg += "\n"

        for i, (user_id, xp) in enumerate(
            sorted_users[start_idx:end_idx], start_idx + 1
        ):
            level, current_xp, xp_needed = self.ach_system.get_level(xp)
            member = ctx.guild.get_member(int(user_id))
            username = member.display_name if member else f"user {user_id}"

            if i <= 3 and page == 1:
                medals = ["# [1] ", "## [2] ", "### [3] "]
                msg += f"{medals[i - 1]}{i}. **{username}** - level {level} ({xp} xp)\n"
            else:
                msg += f"{i}. **{username}** - level {level} ({xp} xp)\n"

        if total_pages > 1:
            msg += "\n-# use >leaderboard <page> to view other pages"

        await ctx.send(msg)


async def setup(bot):
    await bot.add_cog(AchCommands(bot))
