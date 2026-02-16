from datetime import datetime
from typing import Optional, Tuple

import discord

import config
from src.misc import get_data_manager, get_or_create_role, safe_send


class AchievementSystem:
    def __init__(self):
        self.dm = get_data_manager()
        self.achievements = self.dm.load("achievements", {})
        self.message_counts = self.dm.load("message_counts", {})
        self.reaction_counts = self.dm.load("reaction_counts", {})
        self.last_message = self.dm.load("last_message", {})

    def get_level_from_cookies(self, cookies: int) -> Tuple[int, int, int]:
        level = 1
        cookies_needed = 100
        current_cookies = cookies

        while current_cookies >= cookies_needed:
            current_cookies -= cookies_needed
            level += 1
            cookies_needed = int(cookies_needed * 1.5)

        return level, current_cookies, cookies_needed

    def has_achievement(self, user_id: str, achievement_id: str) -> bool:
        user_id = str(user_id)
        return achievement_id in self.achievements.get(user_id, [])

    def get_user_achievements(self, user_id: str) -> list:
        return self.achievements.get(str(user_id), [])

    def get_recent_achievements(self, user_id: str, limit: int = 3) -> list:
        user_achs = self.get_user_achievements(user_id)
        return user_achs[-limit:] if user_achs else []

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

    def get_last_message(self, user_id: str) -> Optional[datetime]:
        user_id = str(user_id)
        last = self.last_message.get(user_id)
        if last:
            return datetime.fromisoformat(last)
        return None

    def update_last_message(self, user_id: str):
        user_id = str(user_id)
        self.last_message[user_id] = datetime.utcnow().isoformat()
        self.dm.save("last_message", self.last_message)

    async def grant_achievement(
        self,
        user_id: str,
        achievement_id: str,
        guild: Optional[discord.Guild],
        channel: Optional[discord.abc.Messageable],
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

        ach_data = config.ACHIEVEMENTS[achievement_id]
        cookies = config.RARITY_XP.get(ach_data["rarity"], 25)

        from src.commands.cookies import get_cookie_system

        cookie_sys = get_cookie_system()
        await cookie_sys.reward_cookie(user_id, cookies, guild, channel)

        if guild and ach_data.get("role"):
            role = await get_or_create_role(guild, ach_data["role"])
            if role:
                member = guild.get_member(int(user_id))
                if member:
                    await member.add_roles(role)

        if channel:
            name = ach_data["name"]
            rarity = ach_data["rarity"]
            member = guild.get_member(int(user_id)) if guild else None
            mention = member.mention if member else f"user {user_id}"

            msg = f"🏆 {mention} unlocked **{name}** ({rarity}) +{cookies} cookies"
            await safe_send(channel, msg)

        await self.check_achievement_count(user_id, guild)

        return True

    async def revoke_achievement(
        self, user_id: str, achievement_id: str, guild: Optional[discord.Guild]
    ) -> bool:
        user_id = str(user_id)

        if not self.has_achievement(user_id, achievement_id):
            return False

        self.achievements[user_id].remove(achievement_id)
        self.dm.save("achievements", self.achievements)

        return True

    async def check_command_achievement(
        self,
        user_id: str,
        command: str,
        exit_code: Optional[int],
        guild: discord.Guild,
        channel: Optional[discord.abc.Messageable],
    ):
        """check if command triggers any achievements"""
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
        self,
        user_id: str,
        content: str,
        guild: discord.Guild,
        channel: discord.abc.Messageable,
    ):
        for ach_id, ach_data in config.ACHIEVEMENTS.items():
            if ach_data["trigger_type"] == "message_count":
                trigger_word, count = ach_data["trigger_value"]
                if trigger_word.lower() in content.lower():
                    current = self.increment_message_count(user_id, trigger_word)
                    if current >= count:
                        await self.grant_achievement(user_id, ach_id, guild, channel)

    async def check_presence_achievements(
        self, user_id: str, presence: discord.Member, guild: discord.Guild
    ):
        for activity in presence.activities:
            if isinstance(activity, (discord.Game, discord.Activity)):
                name = activity.name
                for ach_id, ach_data in config.ACHIEVEMENTS.items():
                    if ach_data["trigger_type"] == "presence":
                        if name in ach_data["trigger_value"]:
                            await self.grant_achievement(
                                str(user_id), ach_id, guild, None
                            )

    async def check_forum_achievements(
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
