from datetime import datetime, timedelta
from typing import Optional, Tuple

import discord

import config
from src.misc import get_data_manager, get_or_create_role, safe_send


class AchievementSystem:
    def __init__(self):
        self.dm = get_data_manager()
        self.achievements = self.dm.load("achievements", {})
        self.xp = self.dm.load("xp", {})
        self.message_counts = self.dm.load("message_counts", {})
        self.reaction_counts = self.dm.load("reaction_counts", {})
        self.last_message = self.dm.load("last_message", {})

    def get_level(self, xp: int) -> Tuple[int, int, int]:
        level = 1
        xp_needed = 100
        current_xp = xp

        while current_xp >= xp_needed:
            current_xp -= xp_needed
            level += 1
            xp_needed = int(xp_needed * 1.5)

        return level, current_xp, xp_needed

    def has_achievement(self, user_id: str, achievement_id: str) -> bool:
        user_id = str(user_id)
        return achievement_id in self.achievements.get(user_id, [])

    def get_user_achievements(self, user_id: str) -> list:
        return self.achievements.get(str(user_id), [])

    def get_user_xp(self, user_id: str) -> int:
        return self.xp.get(str(user_id), 0)

    def get_message_count(self, user_id: str, word: str) -> int:
        user_id = str(user_id)
        count_key = f"word_{word}"
        return self.message_counts.get(user_id, {}).get(count_key, 0)

    def increment_message_count(self, user_id: str, word: str) -> int:
        user_id = str(user_id)
        count_key = f"word_{word}"

        if user_id not in self.message_counts:
            self.message_counts[user_id] = {}

        if count_key not in self.message_counts[user_id]:
            self.message_counts[user_id][count_key] = 0

        self.message_counts[user_id][count_key] += 1
        self.dm.save("message_counts", self.message_counts)

        return self.message_counts[user_id][count_key]

    def get_reaction_count(self, user_id: str) -> int:
        user_id = str(user_id)
        return self.reaction_counts.get(user_id, 0)

    def increment_reaction_count(self, user_id: str) -> int:
        user_id = str(user_id)
        if user_id not in self.reaction_counts:
            self.reaction_counts[user_id] = 0
        self.reaction_counts[user_id] += 1
        self.dm.save("reaction_counts", self.reaction_counts)
        return self.reaction_counts[user_id]

    def update_last_message(self, user_id: str):
        user_id = str(user_id)
        self.last_message[user_id] = datetime.utcnow().isoformat()
        self.dm.save("last_message", self.last_message)

    def get_last_message(self, user_id: str) -> Optional[datetime]:
        user_id = str(user_id)
        if user_id not in self.last_message:
            return None
        return datetime.fromisoformat(self.last_message[user_id])

    async def grant_achievement(
        self,
        user_id: str,
        achievement_id: str,
        guild: discord.Guild,
        channel: Optional[discord.abc.Messageable] = None,
    ) -> bool:
        user_id = str(user_id)

        if self.has_achievement(user_id, achievement_id):
            return False

        if achievement_id not in config.ACHIEVEMENTS:
            return False

        if user_id not in self.achievements:
            self.achievements[user_id] = []

        self.achievements[user_id].append(achievement_id)
        self.dm.save("achievements", self.achievements)

        achievement = config.ACHIEVEMENTS[achievement_id]
        xp_gain = config.RARITY_XP[achievement["rarity"]]

        old_level, _, _ = self.get_level(self.get_user_xp(user_id))

        if user_id not in self.xp:
            self.xp[user_id] = 0

        self.xp[user_id] += xp_gain
        self.dm.save("xp", self.xp)

        new_level, current_xp, xp_needed = self.get_level(self.xp[user_id])

        member = guild.get_member(int(user_id))
        if achievement["role"] and member:
            role = await get_or_create_role(
                guild,
                achievement["role"],
                reason=f"achievement role for {achievement_id}",
            )
            if role:
                await member.add_roles(role)

        ach_count = len(self.achievements[user_id])
        for threshold, role_name in config.ACHIEVEMENT_MILESTONES.items():
            if ach_count == threshold and member:
                milestone_role = await get_or_create_role(
                    guild, role_name, reason="achievement milestone role"
                )
                if milestone_role:
                    await member.add_roles(milestone_role)

        await self.check_achievement_count(user_id, guild)

        achievements_channel = guild.get_channel(config.ACHIEVEMENTS_CHANNEL)
        if achievements_channel:
            mention = member.mention if member else f"user {user_id}"
            await safe_send(
                achievements_channel,
                f"`★` [{ach_count}/{len(config.ACHIEVEMENTS)}] {mention} has gotten the {achievement['rarity']} achievement `{achievement['name']}`!\n"
                f"**{achievement['description']}**",
            )

        return True

    async def revoke_achievement(
        self, user_id: str, achievement_id: str, guild: discord.Guild
    ) -> bool:
        user_id = str(user_id)

        if not self.has_achievement(user_id, achievement_id):
            return False

        if achievement_id not in config.ACHIEVEMENTS:
            return False

        self.achievements[user_id].remove(achievement_id)
        self.dm.save("achievements", self.achievements)

        achievement = config.ACHIEVEMENTS[achievement_id]
        xp_loss = config.RARITY_XP[achievement["rarity"]]

        if user_id in self.xp:
            self.xp[user_id] = max(0, self.xp[user_id] - xp_loss)
            self.dm.save("xp", self.xp)

        member = guild.get_member(int(user_id))
        if achievement["role"] and member:
            role = discord.utils.get(guild.roles, name=achievement["role"])
            if role and role in member.roles:
                await member.remove_roles(role)

        return True

    async def check_command_achievement(
        self,
        user_id: str,
        command: str,
        exit_code: Optional[int],
        guild: discord.Guild,
        channel: Optional[discord.abc.Messageable],
    ):
        for ach_id, ach_data in config.ACHIEVEMENTS.items():
            if ach_data["trigger_type"] == "command":
                trigger = ach_data["trigger_value"]

                triggered = False
                if isinstance(trigger, list):
                    triggered = any(t in command for t in trigger)
                else:
                    triggered = command.startswith(trigger)

                if triggered:
                    await self.grant_achievement(user_id, ach_id, guild, channel)

            elif ach_data["trigger_type"] == "nonzero_exit":
                if exit_code != 0 and exit_code is not None:
                    await self.grant_achievement(user_id, ach_id, guild, channel)

            elif ach_data["trigger_type"] == "file_read":
                if "cat" in command and ach_data["trigger_value"] in command:
                    await self.grant_achievement(user_id, ach_id, guild, channel)

    async def check_message_achievements(
        self, user_id: str, message_content: str, guild: discord.Guild
    ):
        content_lower = message_content.lower()

        for ach_id, ach_data in config.ACHIEVEMENTS.items():
            if ach_data["trigger_type"] == "message_count":
                word, threshold = ach_data["trigger_value"]

                if word in content_lower:
                    count = self.increment_message_count(user_id, word)

                    if count >= threshold and not self.has_achievement(user_id, ach_id):
                        await self.grant_achievement(str(user_id), ach_id, guild, None)

    async def check_presence_achievements(
        self, member: discord.Member, activity: discord.Activity
    ):
        if not activity:
            return

        for ach_id, ach_data in config.ACHIEVEMENTS.items():
            if ach_data["trigger_type"] == "presence":
                if isinstance(activity, (discord.Game, discord.Activity)):
                    game_name = str(activity.name)
                    if any(
                        game.lower() in game_name.lower()
                        for game in ach_data["trigger_value"]
                    ):
                        await self.grant_achievement(
                            str(member.id), ach_id, member.guild, None
                        )

    async def check_infraction_achievement(
        self, user_id: str, infraction_type: str, guild: discord.Guild
    ):
        for ach_id, ach_data in config.ACHIEVEMENTS.items():
            if ach_data["trigger_type"] == "infraction":
                if infraction_type in ach_data["trigger_value"]:
                    await self.grant_achievement(str(user_id), ach_id, guild, None)

    async def check_forum_post_achievement(
        self, user_id: str, channel_id: int, guild: discord.Guild
    ):
        for ach_id, ach_data in config.ACHIEVEMENTS.items():
            if ach_data["trigger_type"] == "forum_post":
                if channel_id == ach_data["trigger_value"]:
                    await self.grant_achievement(str(user_id), ach_id, guild, None)

    async def check_achievement_count(self, user_id: str, guild: discord.Guild):
        user_id = str(user_id)
        ach_count = len(self.achievements.get(user_id, []))

        for ach_id, ach_data in config.ACHIEVEMENTS.items():
            if ach_data["trigger_type"] == "achievement_count":
                if ach_count >= ach_data["trigger_value"]:
                    await self.grant_achievement(user_id, ach_id, guild, None)

    async def check_inactivity_achievement(self, user_id: str, guild: discord.Guild):
        user_id = str(user_id)
        last = self.get_last_message(user_id)

        if not last:
            self.update_last_message(user_id)
            return

        time_since = datetime.utcnow() - last

        for ach_id, ach_data in config.ACHIEVEMENTS.items():
            if ach_data["trigger_type"] == "inactivity":
                required_seconds = ach_data["trigger_value"]
                if time_since.total_seconds() >= required_seconds:
                    await self.grant_achievement(user_id, ach_id, guild, None)

        self.update_last_message(user_id)

    async def check_reaction_achievements(
        self, user_id: str, emoji: str, guild: discord.Guild
    ):
        user_id = str(user_id)
        count = self.increment_reaction_count(user_id)

        for ach_id, ach_data in config.ACHIEVEMENTS.items():
            if ach_data["trigger_type"] == "reaction_count":
                if count >= ach_data["trigger_value"]:
                    await self.grant_achievement(user_id, ach_id, guild, None)

            elif ach_data["trigger_type"] == "specific_reaction":
                emoji_name = emoji.name if hasattr(emoji, "name") else str(emoji)
                if ach_data["trigger_value"] in emoji_name:
                    await self.grant_achievement(user_id, ach_id, guild, None)


_achievement_system = None


def get_achievement_system() -> AchievementSystem:
    global _achievement_system
    if _achievement_system is None:
        _achievement_system = AchievementSystem()
    return _achievement_system
