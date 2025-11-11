import discord
from discord.ext import commands
import config
import json
from pathlib import Path


class Achievements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = Path("data/achievements.json")
        self.xp_file = Path("data/xp.json")
        self.message_counts_file = Path("data/message_counts.json")
        self.data_file.parent.mkdir(exist_ok=True)

        self.user_achievements = self.load_data()
        self.user_xp = self.load_xp()
        self.message_counts = self.load_message_counts()
        self.logger = (
            self.bot.get_cog("Logging").logger if self.bot.get_cog("Logging") else None
        )

    def load_data(self):
        if self.data_file.exists():
            with open(self.data_file, "r") as f:
                return json.load(f)
        return {}

    def save_data(self):
        with open(self.data_file, "w") as f:
            json.dump(self.user_achievements, f, indent=2)

    def load_xp(self):
        if self.xp_file.exists():
            with open(self.xp_file, "r") as f:
                return json.load(f)
        return {}

    def save_xp(self):
        with open(self.xp_file, "w") as f:
            json.dump(self.user_xp, f, indent=2)

    def load_message_counts(self):
        if self.message_counts_file.exists():
            with open(self.message_counts_file, "r") as f:
                return json.load(f)
        return {}

    def save_message_counts(self):
        with open(self.message_counts_file, "w") as f:
            json.dump(self.message_counts, f, indent=2)

    def get_user_level(self, xp):
        level = 1
        xp_needed = 100

        while xp >= xp_needed:
            xp -= xp_needed
            level += 1
            xp_needed = int(xp_needed * 1.5)

        return level, xp, xp_needed

    def has_achievement(self, user_id, achievement_id):
        user_id = str(user_id)
        return (
            user_id in self.user_achievements
            and achievement_id in self.user_achievements[user_id]
        )

    async def grant_achievement(self, user_id, achievement_id, guild, channel):
        user_id = str(user_id)

        if self.has_achievement(user_id, achievement_id):
            return False

        if user_id not in self.user_achievements:
            self.user_achievements[user_id] = []

        self.user_achievements[user_id].append(achievement_id)
        self.save_data()

        achievement = config.ACHIEVEMENTS[achievement_id]
        xp_gain = config.RARITY_XP[achievement["rarity"]]

        if user_id not in self.user_xp:
            self.user_xp[user_id] = 0

        old_level, _, _ = self.get_user_level(self.user_xp[user_id])
        self.user_xp[user_id] += xp_gain
        new_level, current_xp, xp_needed = self.get_user_level(self.user_xp[user_id])
        self.save_xp()

        member = guild.get_member(int(user_id))

        if achievement["role"] and member:
            role = discord.utils.get(guild.roles, name=achievement["role"])
            if not role:
                role = await guild.create_role(
                    name=achievement["role"],
                    reason=f"achievement role for {achievement_id}",
                )
            await member.add_roles(role)

        ach_count = len(self.user_achievements[user_id])
        for threshold, role_name in config.ACHIEVEMENT_MILESTONES.items():
            if ach_count == threshold:
                milestone_role = discord.utils.get(guild.roles, name=role_name)
                if not milestone_role:
                    milestone_role = await guild.create_role(
                        name=role_name, reason="achievement milestone role"
                    )
                if member:
                    await member.add_roles(milestone_role)

        achievements_channel = guild.get_channel(config.ACHIEVEMENTS_CHANNEL)
        if achievements_channel:
            ach_count = len(self.user_achievements[user_id])

            await achievements_channel.send(
                f"`★` [{ach_count}/17] {member.mention if member else f'user {user_id}'} has gotten the {achievement['rarity']} achievement `{achievement['name']}`!\n"
                f"**{achievement['description']}**"
            )

        if self.logger:
            self.logger.info(
                f"achievement granted to {user_id}: {achievement_id} (+{xp_gain} xp)"
            )

        return True

    async def check_command_achievement(
        self, user_id, command, exit_code, guild, channel
    ):
        for ach_id, ach_data in config.ACHIEVEMENTS.items():
            if ach_data["trigger_type"] == "command":
                trigger = ach_data["trigger_value"]
                if isinstance(trigger, list):
                    if any(cmd in command for cmd in trigger):
                        await self.grant_achievement(user_id, ach_id, guild, channel)
                else:
                    if command.startswith(trigger):
                        await self.grant_achievement(user_id, ach_id, guild, channel)

            elif ach_data["trigger_type"] == "nonzero_exit":
                if exit_code != 0 and exit_code is not None:
                    await self.grant_achievement(user_id, ach_id, guild, channel)

            elif ach_data["trigger_type"] == "file_read":
                if "cat" in command and ach_data["trigger_value"] in command:
                    await self.grant_achievement(user_id, ach_id, guild, channel)

    async def check_mutual_servers(self, member):
        if not self.has_achievement(member.id, "neopolita"):
            other_guild = self.bot.get_guild(config.NEO_POLITA)
            if other_guild and other_guild.get_member(member.id):
                await self.grant_achievement(
                    str(member.id), "neopolita", member.guild, None
                )

    async def check_message_achievements(self, user_id, message_content, guild):
        user_id = str(user_id)

        if user_id not in self.message_counts:
            self.message_counts[user_id] = {}

        content_lower = message_content.lower()

        for ach_id, ach_data in config.ACHIEVEMENTS.items():
            if ach_data["trigger_type"] == "message_count":
                word, threshold = ach_data["trigger_value"]

                if word in content_lower:
                    count_key = f"word_{word}"
                    if count_key not in self.message_counts[user_id]:
                        self.message_counts[user_id][count_key] = 0

                    self.message_counts[user_id][count_key] += 1
                    self.save_message_counts()

                    if self.message_counts[user_id][count_key] >= threshold:
                        if not self.has_achievement(user_id, ach_id):
                            await self.grant_achievement(user_id, ach_id, guild, None)

    async def check_presence_achievements(self, member, activity):
        if not activity:
            return

        for ach_id, ach_data in config.ACHIEVEMENTS.items():
            if ach_data["trigger_type"] == "presence":
                if isinstance(activity, (discord.Game, discord.Activity)):
                    game_name = activity.name
                    if any(
                        game.lower() in str(game_name).lower()
                        for game in ach_data["trigger_value"]
                    ):
                        await self.grant_achievement(
                            str(member.id), ach_id, member.guild, None
                        )

    async def check_steam_games(self, member):
        if self.has_achievement(member.id, "elitegamer"):
            return

        for activity in member.activities:
            if isinstance(activity, discord.Streaming):
                continue

            if hasattr(activity, "application_id"):
                try:
                    if member.public_flags.verified_bot_developer or any(
                        conn.type == "steam" and conn.verified
                        for conn in await member.fetch_connections()
                        if hasattr(member, "fetch_connections")
                    ):
                        pass
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        if message.guild.id == config.GUILD_ID:
            await self.check_message_achievements(
                message.author.id, message.content, message.guild
            )

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id == config.GUILD_ID:
            await self.check_mutual_servers(member)

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        if after.guild.id != config.GUILD_ID:
            return

        if before.activities != after.activities:
            for activity in after.activities:
                await self.check_presence_achievements(after, activity)


async def setup(bot):
    await bot.add_cog(Achievements(bot))
