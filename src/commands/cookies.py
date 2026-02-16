from datetime import datetime

import discord
from discord import SeparatorSpacing
from discord.ext import commands
from discord.ui import ActionRow, Container, LayoutView, Separator, TextDisplay
from discord.ui.section import Section

from src.achievements.utils import get_achievement_system
from src.misc import CogHelper, get_data_manager


class CookieGameView(LayoutView):
    def __init__(self, author, cookie_sys):
        super().__init__(timeout=180.0)
        self.author = author
        self.cookie_sys = cookie_sys
        self.message = None
        self.build_view()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("not your cookies", ephemeral=True)
            return False
        return True

    def build_view(self):
        self.clear_items()

        user = self.cookie_sys.get_user_data(self.author.id)
        cookies = user.get("cookies", 0)
        factories = user.get("factories", 0)
        cakes = user.get("cakes", 0)

        text = "# cookie factory\n"
        text += f"**cookies:** {cookies}\n"
        text += f"**factories:** {factories} (produces {factories} cookies / 5h)\n"
        text += f"**cakes:** {cakes} (multiplier: +{cakes} per source)\n\n"

        if factories > 0:
            last_collect = user.get("last_collect")
            if last_collect:
                last_dt = datetime.fromisoformat(last_collect)
                elapsed = (datetime.utcnow() - last_dt).total_seconds()
                periods = int(elapsed / (5 * 3600))
                if periods > 0:
                    ready = periods * factories * (1 + cakes)
                    text += f"**ready to collect:** {ready} cookies\n\n"

        action_row = discord.ui.ActionRow()

        if cookies >= 20:
            btn = discord.ui.Button(
                label="buy factory (20 cookies)",
                style=discord.ButtonStyle.primary,
                custom_id="buy_factory",
            )
            btn.callback = self.buy_factory_callback
            action_row.add_item(btn)

        if factories > 0:
            btn = discord.ui.Button(
                label="collect cookies",
                style=discord.ButtonStyle.success,
                custom_id="collect",
            )
            btn.callback = self.collect_callback
            action_row.add_item(btn)

        if cookies >= 100:
            btn = discord.ui.Button(
                label="bake cake (100 cookies)",
                style=discord.ButtonStyle.danger,
                custom_id="prestige",
            )
            btn.callback = self.prestige_callback
            action_row.add_item(btn)

        if cakes >= 5 and factories < 5:
            btn = discord.ui.Button(
                label="expand factory (5 cakes)",
                style=discord.ButtonStyle.primary,
                custom_id="upgrade",
            )
            btn.callback = self.upgrade_callback
            action_row.add_item(btn)

        btn = discord.ui.Button(
            label="close", style=discord.ButtonStyle.secondary, custom_id="close"
        )
        btn.callback = self.close_callback
        action_row.add_item(btn)

        container = Container(
            TextDisplay(text),
            Separator(spacing=SeparatorSpacing.small),
            action_row,
            accent_color=0xF4A261,
        )

        self.add_item(container)

    async def buy_factory_callback(self, interaction: discord.Interaction):
        user = self.cookie_sys.get_user_data(self.author.id)

        if user.get("cookies", 0) >= 20:
            user["cookies"] = user.get("cookies", 0) - 20
            user["factories"] = user.get("factories", 0) + 1
            self.cookie_sys.save()
            self.build_view()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message(
                "not enough cookies", ephemeral=True
            )

    async def collect_callback(self, interaction: discord.Interaction):
        user = self.cookie_sys.get_user_data(self.author.id)
        last_collect = user.get("last_collect")

        if not last_collect:
            user["last_collect"] = datetime.utcnow().isoformat()
            self.cookie_sys.save()
            await interaction.response.send_message("factory started", ephemeral=True)
            return

        last_dt = datetime.fromisoformat(last_collect)
        elapsed = (datetime.utcnow() - last_dt).total_seconds()
        periods = int(elapsed / (5 * 3600))

        if periods > 0:
            factories = user.get("factories", 0)
            cakes = user.get("cakes", 0)
            base_cookies = periods * factories
            earned = self.cookie_sys.apply_multiplier(base_cookies, cakes)
            user["cookies"] = user.get("cookies", 0) + earned
            user["last_collect"] = datetime.utcnow().isoformat()
            self.cookie_sys.save()

            await self.cookie_sys.check_receive_achievements(
                self.author.id, interaction.guild, interaction.channel
            )

            self.build_view()
            await interaction.response.edit_message(view=self)
        else:
            remaining = (5 * 3600) - elapsed
            hours = int(remaining // 3600)
            mins = int((remaining % 3600) // 60)
            await interaction.response.send_message(
                f"wait {hours}h {mins}m before collecting", ephemeral=True
            )

    async def prestige_callback(self, interaction: discord.Interaction):
        user = self.cookie_sys.get_user_data(self.author.id)

        if user.get("cookies", 0) >= 100:
            user["cookies"] = user.get("cookies", 0) - 100
            user["cakes"] = user.get("cakes", 0) + 1
            user["factories"] = 0
            user["last_collect"] = None
            self.cookie_sys.save()

            if user["cakes"] == 1:
                await self.cookie_sys.ach.grant_achievement(
                    str(self.author.id),
                    "bakery",
                    interaction.guild,
                    interaction.channel,
                )

            self.build_view()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("need 100 cookies", ephemeral=True)

    async def upgrade_callback(self, interaction: discord.Interaction):
        user = self.cookie_sys.get_user_data(self.author.id)

        if user.get("cakes", 0) >= 5:
            user["cakes"] = user.get("cakes", 0) - 5
            multiplier = 5

            factories = user.get("factories", 0)
            cakes = user.get("cakes", 0)
            for factory_idx in range(factories):
                user["cookies"] = user.get("cookies", 0) + multiplier * (1 + cakes)

            self.cookie_sys.save()
            self.build_view()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("need 5 cakes", ephemeral=True)

    async def eat_callback(self, interaction: discord.Interaction):
        user = self.cookie_sys.get_user_data(self.author.id)

        if user.get("cookies", 0) > 0:
            user["cookies"] = user.get("cookies", 0) - 1
            self.cookie_sys.save()
            self.build_view()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("no cookies to eat", ephemeral=True)

    async def bake_callback(self, interaction: discord.Interaction):
        user = self.cookie_sys.get_user_data(self.author.id)
        last_bake = user.get("last_bake")

        if last_bake:
            last_dt = datetime.fromisoformat(last_bake)
            elapsed = (datetime.utcnow() - last_dt).total_seconds()

            if elapsed < 5 * 3600:
                remaining = (5 * 3600) - elapsed
                hours = int(remaining // 3600)
                mins = int((remaining % 3600) // 60)
                await interaction.response.send_message(
                    f"wait {hours}h {mins}m before baking again", ephemeral=True
                )
                return

        user["cookies"] = user.get("cookies", 0) + 1
        user["last_bake"] = datetime.utcnow().isoformat()
        self.cookie_sys.save()
        self.build_view()
        await interaction.response.edit_message(view=self)

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


class Cookies(CogHelper, commands.Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.dm = get_data_manager()
        self.ach = get_achievement_system()
        self.data = self.dm.load("cookies", {})

    def get_user_data(self, user_id):
        uid = str(user_id)
        if uid not in self.data:
            self.data[uid] = {
                "cookies": 0,
                "cakes": 0,
                "given": 0,
                "received": 0,
                "factories": 0,
                "last_collect": None,
                "last_bake": None,
            }
        return self.data[uid]

    def apply_multiplier(self, base, cakes):
        return base + cakes * base

    def save(self):
        self.dm.save("cookies", self.data)

    async def give_cookie(self, giver_id, receiver_id, amount, guild, channel):
        if giver_id == receiver_id:
            return False

        giver = self.get_user_data(giver_id)
        receiver = self.get_user_data(receiver_id)

        if giver.get("cookies", 0) < amount:
            return False

        giver["cookies"] = giver.get("cookies", 0) - amount
        receiver["cookies"] = receiver.get("cookies", 0) + amount
        receiver["received"] = receiver.get("received", 0) + amount
        self.save()

        await self.check_receive_achievements(receiver_id, guild, channel)
        return True

    async def reward_cookie(self, user_id, amount, guild, channel):
        user = self.get_user_data(user_id)
        cakes = user.get("cakes", 0)
        multiplied = self.apply_multiplier(amount, cakes)
        user["cookies"] = user.get("cookies", 0) + multiplied
        user["received"] = user.get("received", 0) + multiplied
        self.save()

        await self.check_receive_achievements(user_id, guild, channel)
        return multiplied

    async def check_give_achievements(self, user_id, guild, channel):
        user = self.get_user_data(user_id)
        given = user.get("given", 0)

        if given >= 1:
            await self.ach.grant_achievement(
                str(user_id), "haveacookie", guild, channel
            )
        if given >= 20:
            await self.ach.grant_achievement(
                str(user_id), "haveacookietray", guild, channel
            )
        if given >= 100:
            await self.ach.grant_achievement(
                str(user_id), "haveacookiemachine", guild, channel
            )

    async def check_receive_achievements(self, user_id, guild, channel):
        user = self.get_user_data(user_id)
        received = user.get("received", 0)

        if received >= 1:
            await self.ach.grant_achievement(str(user_id), "yay", guild, channel)
        if received >= 20:
            await self.ach.grant_achievement(str(user_id), "cookietray", guild, channel)
        if received >= 100:
            await self.ach.grant_achievement(
                str(user_id), "cookiemachine", guild, channel
            )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        if not message.mentions:
            return

        content = message.content.lower()
        thanks = ["thank you", "thanks", "thank u", "thankyou", "ty", "thx"]

        if not any(t in content for t in thanks):
            return

        for mention in message.mentions:
            if mention.id == message.author.id or mention.bot:
                continue

            await self.reward_cookie(mention.id, 1, message.guild, message.channel)

            giver = self.get_user_data(message.author.id)
            giver["given"] = giver.get("given", 0) + 1
            self.save()

            await self.check_give_achievements(
                message.author.id, message.guild, message.channel
            )

            await message.channel.send(f"{mention.mention} got a cookie")
            break

    @commands.command()
    async def cookies(self, ctx):
        view = CookieGameView(ctx.author, self)
        msg = await ctx.send(view=view)
        view.message = msg


_cookie_system = None


def get_cookie_system():
    global _cookie_system
    return _cookie_system


async def setup(bot):
    cog = Cookies(bot)
    global _cookie_system
    _cookie_system = cog
    await bot.add_cog(cog)
