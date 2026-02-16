import discord
from discord import MediaGalleryItem, SeparatorSpacing
from discord.ext import commands
from discord.ui import Container, LayoutView, MediaGallery, Separator, TextDisplay

import config
from src.achievements.utils import get_achievement_system
from src.misc import CogHelper, get_data_manager, is_staff


class ProfileView(LayoutView):
    def __init__(self, author, member, ach_sys, dm):
        super().__init__(timeout=180.0)
        self.author = author
        self.member = member
        self.ach_sys = ach_sys
        self.dm = dm
        self.message = None
        self.page = "profile"
        self.achievement_page = 0
        self.build_view()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("not your profile", ephemeral=True)
            return False
        return True

    def build_view(self):
        self.clear_items()

        if self.page == "profile":
            self.build_profile_page()
        elif self.page == "achievements":
            self.build_achievements_page()
        elif self.page == "edit":
            self.build_edit_page()

    def build_profile_page(self):
        from src.commands.cookies import get_cookie_system

        cookie_sys = get_cookie_system()

        user_data = cookie_sys.get_user_data(self.member.id)
        cookies = user_data.get("cookies", 0)

        level, current, needed = self.ach_sys.get_level_from_cookies(cookies)

        user_achs = self.ach_sys.get_user_achievements(str(self.member.id))
        recent_achs = self.ach_sys.get_recent_achievements(str(self.member.id), 3)

        profile_data = self.dm.load("profiles", {})
        user_profile = profile_data.get(str(self.member.id), {})
        bio = user_profile.get("bio", "no bio set")

        text = f"# {self.member.display_name}\n"
        text += f"**level {level}** | {current}/{needed} cookies\n"
        text += f"**achievements:** {len(user_achs)}\n\n"
        text += f"**bio**\n{bio}\n\n"

        if recent_achs:
            text += "**recent achievements**\n"
            for ach_id in recent_achs:
                if ach_id in config.ACHIEVEMENTS:
                    ach = config.ACHIEVEMENTS[ach_id]
                    text += f"☆ **{ach['name']}** ({ach['rarity']})\n"
        else:
            text += "**recent achievements**\nno achievements yet"

        avatar_url = self.member.display_avatar.url

        container = Container(
            MediaGallery(
                MediaGalleryItem(
                    avatar_url, description=f"{self.member.display_name}'s avatar"
                )
            ),
            Separator(spacing=SeparatorSpacing.small),
            TextDisplay(text),
        )

        self.add_item(container)
        self.add_item(Separator(spacing=SeparatorSpacing.small))

        action_row = discord.ui.ActionRow()

        btn = discord.ui.Button(
            label="cookies",
            style=discord.ButtonStyle.primary,
            emoji="🍪",
            custom_id="cookies",
        )
        btn.callback = self.cookies_callback
        action_row.add_item(btn)

        btn = discord.ui.Button(
            label="achievements",
            style=discord.ButtonStyle.primary,
            emoji="🏆",
            custom_id="achievements",
        )
        btn.callback = self.achievements_callback
        action_row.add_item(btn)

        if self.author.id == self.member.id:
            btn = discord.ui.Button(
                label="edit",
                style=discord.ButtonStyle.secondary,
                emoji="✏️",
                custom_id="edit",
            )
            btn.callback = self.edit_callback
            action_row.add_item(btn)

        btn = discord.ui.Button(
            label="close", style=discord.ButtonStyle.secondary, custom_id="close"
        )
        btn.callback = self.close_callback
        action_row.add_item(btn)

        if len(action_row.children) > 0:
            self.add_item(action_row)

    def build_achievements_page(self):
        user_achs = self.ach_sys.get_user_achievements(str(self.member.id))

        per_page = 5
        total_pages = (len(user_achs) + per_page - 1) // per_page if user_achs else 1
        self.achievement_page = max(0, min(self.achievement_page, total_pages - 1))

        start_idx = self.achievement_page * per_page
        end_idx = start_idx + per_page
        page_achs = user_achs[start_idx:end_idx] if user_achs else []

        text = f"# achievements\n"
        text += f"**{self.member.display_name}** | {len(user_achs)} unlocked\n"
        text += f"page {self.achievement_page + 1}/{total_pages}\n\n"

        if page_achs:
            for ach_id in page_achs:
                if ach_id in config.ACHIEVEMENTS:
                    ach = config.ACHIEVEMENTS[ach_id]
                    cookies = config.RARITY_XP.get(ach["rarity"], 25)
                    text += f"☆ **{ach['name']}** ({ach['rarity']})\n"
                    text += f"  {ach['description']}\n"
                    text += f"  +{cookies} cookies\n\n"
        else:
            text += "no achievements unlocked yet"

        container = Container(TextDisplay(text), accent_color=0xF4A261)

        self.add_item(container)
        self.add_item(Separator(spacing=SeparatorSpacing.small))

        action_row = discord.ui.ActionRow()

        if self.achievement_page > 0:
            btn = discord.ui.Button(
                label="previous",
                style=discord.ButtonStyle.secondary,
                custom_id="ach_prev",
            )
            btn.callback = self.ach_prev_callback
            action_row.add_item(btn)

        if self.achievement_page < total_pages - 1:
            btn = discord.ui.Button(
                label="next", style=discord.ButtonStyle.secondary, custom_id="ach_next"
            )
            btn.callback = self.ach_next_callback
            action_row.add_item(btn)

        btn = discord.ui.Button(
            label="back to profile",
            style=discord.ButtonStyle.primary,
            custom_id="back_profile",
        )
        btn.callback = self.back_profile_callback
        action_row.add_item(btn)

        if len(action_row.children) > 0:
            self.add_item(action_row)

    def build_edit_page(self):
        text = f"# edit profile\n"
        text += f"use the buttons below to update your profile\n\n"
        text += f"-# you can also use >usermod for roles and settings"

        container = Container(TextDisplay(text), accent_color=0x43B581)

        self.add_item(container)
        self.add_item(Separator(spacing=SeparatorSpacing.small))

        action_row = discord.ui.ActionRow()

        btn = discord.ui.Button(
            label="edit bio", style=discord.ButtonStyle.primary, custom_id="edit_bio"
        )
        btn.callback = self.edit_bio_callback
        action_row.add_item(btn)

        btn = discord.ui.Button(
            label="back to profile",
            style=discord.ButtonStyle.secondary,
            custom_id="back_profile",
        )
        btn.callback = self.back_profile_callback
        action_row.add_item(btn)

        if len(action_row.children) > 0:
            self.add_item(action_row)

    async def cookies_callback(self, interaction: discord.Interaction):
        from src.commands.cookies import CookieGameView, get_cookie_system

        cookie_sys = get_cookie_system()
        cookie_view = CookieGameView(self.author, cookie_sys)

        await interaction.response.edit_message(view=cookie_view)
        cookie_view.message = self.message
        self.stop()

    async def achievements_callback(self, interaction: discord.Interaction):
        self.page = "achievements"
        self.achievement_page = 0
        self.build_view()
        await interaction.response.edit_message(view=self)

    async def edit_callback(self, interaction: discord.Interaction):
        self.page = "edit"
        self.build_view()
        await interaction.response.edit_message(view=self)

    async def back_profile_callback(self, interaction: discord.Interaction):
        self.page = "profile"
        self.build_view()
        await interaction.response.edit_message(view=self)

    async def ach_prev_callback(self, interaction: discord.Interaction):
        self.achievement_page -= 1
        self.build_view()
        await interaction.response.edit_message(view=self)

    async def ach_next_callback(self, interaction: discord.Interaction):
        self.achievement_page += 1
        self.build_view()
        await interaction.response.edit_message(view=self)

    async def edit_bio_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "type your new bio and send it as a message (within 60 seconds)",
            ephemeral=True,
        )

        def check(m):
            return (
                m.author.id == self.author.id and m.channel.id == interaction.channel_id
            )

        try:
            bot = interaction.client
            msg = await bot.wait_for("message", timeout=60.0, check=check)

            profile_data = self.dm.load("profiles", {})
            if str(self.author.id) not in profile_data:
                profile_data[str(self.author.id)] = {}

            profile_data[str(self.author.id)]["bio"] = msg.content[:200]
            self.dm.save("profiles", profile_data)

            try:
                await msg.delete()
            except:
                pass

            self.page = "profile"
            self.build_view()
            await self.message.edit(view=self)
        except:
            pass

    async def set_color_callback(self, interaction: discord.Interaction):
        modal = discord.ui.Modal(title="set color")
        color_input = discord.ui.TextInput(
            label="hex color code",
            placeholder="#xxxxxx or xxxxxx",
            max_length=7,
            required=True,
        )
        modal.add_item(color_input)

        async def modal_callback(modal_interaction: discord.Interaction):
            import re

            value = color_input.value.strip()
            hex_match = re.match(r"^#?([0-9a-fA-F]{6})$", value)

            if not hex_match:
                await modal_interaction.response.send_message(
                    "invalid hex color. use format: #xxxxxx or xxxxxx", ephemeral=True
                )
                return

            hex_code = hex_match.group(1).upper()
            color_value = int(hex_code, 16)

            guild = modal_interaction.guild
            member = modal_interaction.user

            # remove old color role
            for role in member.roles:
                if role.name.startswith(f"# {member.name} / "):
                    await member.remove_roles(role)
                    await role.delete(reason="replacing with new color")

            # find marker position
            marker = discord.utils.get(guild.roles, name="colors:")
            if not marker:
                await modal_interaction.response.send_message(
                    "colors marker role not found", ephemeral=True
                )
                return

            marker_pos = marker.position

            # create new role
            new_role = await guild.create_role(
                name=f"# {member.name} / {hex_code}",
                color=discord.Color(color_value),
                reason=f"custom color for {member.name}",
            )

            try:
                await new_role.edit(position=marker_pos - 1)
            except:
                pass

            await member.add_roles(new_role)
            await modal_interaction.response.send_message(
                f"set your color to #{hex_code}", ephemeral=True
            )

        modal.on_submit = modal_callback
        await interaction.response.send_modal(modal)

    async def set_nickname_callback(self, interaction: discord.Interaction):
        modal = discord.ui.Modal(title="set nickname")
        nick_input = discord.ui.TextInput(
            label="nickname",
            placeholder="leave blank to remove",
            max_length=32,
            required=False,
        )
        modal.add_item(nick_input)

        async def modal_callback(modal_interaction: discord.Interaction):
            value = nick_input.value.strip()
            member = modal_interaction.user

            try:
                await member.edit(nick=value if value else None)
                await modal_interaction.response.send_message(
                    f"nickname updated" if value else "nickname removed", ephemeral=True
                )
            except discord.Forbidden:
                await modal_interaction.response.send_message(
                    "failed to update nickname (permission denied)", ephemeral=True
                )

        modal.on_submit = modal_callback
        await interaction.response.send_modal(modal)

    async def role_select_callback(self, interaction: discord.Interaction):
        category = interaction.data["custom_id"].replace("role_", "")
        value = interaction.data["values"][0]

        role_name = config.USERMOD_MAPPINGS[category][value]
        guild = interaction.guild
        member = interaction.user

        # remove existing roles in this category
        existing_roles = [
            role
            for role in member.roles
            if role.name in config.USERMOD_MAPPINGS[category].values()
        ]

        target_role = discord.utils.get(guild.roles, name=role_name)

        if not target_role:
            await interaction.response.send_message(
                f"role {role_name} not found", ephemeral=True
            )
            return

        if target_role in member.roles:
            await interaction.response.send_message(
                f"you already have {role_name}", ephemeral=True
            )
            return

        if existing_roles:
            await member.remove_roles(*existing_roles)

        await member.add_roles(target_role)
        await interaction.response.send_message(
            f"updated {config.USERMOD_CATEGORIES[category]} to {role_name}",
            ephemeral=True,
        )

    async def close_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.stop()
        if self.message:
            try:
                await self.message.delete()
            except:
                pass

    async def on_timeout(self):
        if self.message:
            try:
                self.disable_all_items()
                await self.message.edit(view=self)
            except:
                pass


class AchCommands(CogHelper, commands.Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.ach_system = get_achievement_system()
        self.dm = get_data_manager()

    @commands.command(aliases=["achs", "achievement", "ach", "quests"])
    async def profile(self, ctx, *args):
        if args and args[0] in ["-a", "--all"]:
            user_id = str(ctx.author.id)
            user_achs = self.ach_system.get_user_achievements(user_id)

            if not user_achs:
                await ctx.send("no achievements unlocked yet")
                return

            msg = f"**all achievements** ({len(user_achs)})\n\n"

            for ach_id in user_achs:
                if ach_id not in config.ACHIEVEMENTS:
                    continue
                ach = config.ACHIEVEMENTS[ach_id]
                msg += f"`☆` **{ach['name']}** ({ach['rarity']})\n"

            await ctx.send(msg)
            return

        if args and args[0] in ["-g", "--grant"]:
            if not is_staff(ctx.author):
                await ctx.send("you lack the required permissions")
                return

            if len(args) < 3:
                await ctx.send("usage: >profile -g user achievement")
                return

            try:
                member = await commands.MemberConverter().convert(ctx, args[1])
            except:
                await ctx.send("user not found")
                return

            achievement_name = " ".join(args[2:])
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
                self.log_info(
                    f"achievement {ach_id} granted to {member.id} by {ctx.author.id}"
                )
            else:
                await ctx.send(f"{member.mention} already has this achievement")

            return

        if args and args[0] in ["-r", "--revoke"]:
            if not is_staff(ctx.author):
                await ctx.send("you lack the required permissions")
                return

            if len(args) < 3:
                await ctx.send("usage: >profile -r user achievement")
                return

            try:
                member = await commands.MemberConverter().convert(ctx, args[1])
            except:
                await ctx.send("user not found")
                return

            achievement_name = " ".join(args[2:])
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

            return

        if args and args[0] in ["-u"]:
            if len(args) < 2:
                await ctx.send("usage: >profile -u user")
                return

            try:
                member = await commands.MemberConverter().convert(ctx, args[1])
            except:
                await ctx.send("user not found")
                return
        else:
            member = ctx.author

        view = ProfileView(ctx.author, member, self.ach_system, self.dm)
        msg = await ctx.send(view=view)
        view.message = msg

    @commands.command()
    async def leaderboard(self, ctx, page: int = 1):
        from src.commands.cookies import get_cookie_system

        cookie_sys = get_cookie_system()

        all_cookies = {}
        for user_id, data in cookie_sys.data.items():
            all_cookies[user_id] = data.get("cookies", 0)

        sorted_users = sorted(all_cookies.items(), key=lambda x: x[1], reverse=True)

        if not sorted_users:
            await ctx.send("no users on the leaderboard yet")
            return

        user_rank = None
        user_cookies = cookie_sys.get_user_data(ctx.author.id).get("cookies", 0)
        for i, (uid, cookies) in enumerate(sorted_users, 1):
            if uid == str(ctx.author.id):
                user_rank = i
                break

        per_page = 10
        total_pages = (len(sorted_users) + per_page - 1) // per_page
        page = max(1, min(page, total_pages))

        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page

        msg = f"**cookie leaderboard** (page {page}/{total_pages})\n"
        if user_rank:
            level, _, _ = self.ach_system.get_level_from_cookies(user_cookies)
            msg += f"-# your rank: #{user_rank} | level {level} | {user_cookies} cookies\n\n"
        else:
            msg += "\n"

        for i, (user_id, cookies) in enumerate(
            sorted_users[start_idx:end_idx], start_idx + 1
        ):
            level, current, needed = self.ach_system.get_level_from_cookies(cookies)
            member = ctx.guild.get_member(int(user_id))
            username = member.display_name if member else f"user {user_id}"

            if i <= 3 and page == 1:
                medals = ["# [1] ", "## [2] ", "### [3] "]
                msg += f"{medals[i - 1]}{i}. **{username}** - level {level} ({cookies} cookies)\n"
            else:
                msg += f"{i}. **{username}** - level {level} ({cookies} cookies)\n"

        if total_pages > 1:
            msg += "\n-# use >leaderboard <page> to view other pages"

        await ctx.send(msg)


async def setup(bot):
    await bot.add_cog(AchCommands(bot))
