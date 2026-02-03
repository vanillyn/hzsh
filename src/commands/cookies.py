from datetime import datetime, timedelta

import discord
from discord.ext import commands

from src.achievements.utils import get_achievement_system
from src.misc import CogHelper, get_data_manager


class CookieView(discord.ui.View):
    def __init__(self, author, target, amount=1):
        super().__init__(timeout=30.0)
        self.author = author
        self.target = target
        self.amount = amount
        self.value = None

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("not your cookies", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="yes", style=discord.ButtonStyle.green)
    async def yes(self, interaction, button):
        self.value = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="no", style=discord.ButtonStyle.grey)
    async def no(self, interaction, button):
        self.value = False
        await interaction.response.defer()
        self.stop()


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
                "last_bake": None,
            }
        return self.data[uid]

    def apply_multiplier(self, base, cakes):
        return base + cakes

    def save(self):
        self.dm.save("cookies", self.data)

    async def give_cookie(self, giver_id, receiver_id, amount, guild, channel):
        if giver_id == receiver_id:
            return False

        giver = self.get_user_data(giver_id)
        receiver = self.get_user_data(receiver_id)

        if giver["cookies"] < amount:
            return False

        giver["cookies"] -= amount
        receiver["cookies"] += amount
        receiver["received"] += amount
        self.save()

        await self.check_receive_achievements(receiver_id, guild, channel)
        return True

    async def reward_cookie(self, user_id, amount, guild, channel):
        user = self.get_user_data(user_id)
        multiplied = self.apply_multiplier(amount, user["cakes"])
        user["cookies"] += multiplied
        user["received"] += multiplied
        self.save()

        await self.check_receive_achievements(user_id, guild, channel)
        return multiplied

    async def check_give_achievements(self, user_id, guild, channel):
        user = self.get_user_data(user_id)
        given = user["given"]

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
        received = user["received"]

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
            giver["given"] += 1
            self.save()

            await self.check_give_achievements(
                message.author.id, message.guild, message.channel
            )

            await message.channel.send(f"{mention.mention} got a cookie")
            break

    @commands.command()
    async def cookies(self, ctx, *args):
        if not args:
            user = self.get_user_data(ctx.author.id)
            msg = f"{ctx.author.name} has {user['cookies']} cookie(s)"
            if user["cakes"] > 0:
                msg += f" and {user['cakes']} cake(s)"
            await ctx.send(msg)
            return

        if args[0] in ["-e", "--eat"]:
            user = self.get_user_data(ctx.author.id)
            if user["cookies"] <= 0:
                await ctx.send("you dont have any cookies to eat")
                return

            user["cookies"] -= 1
            self.save()
            await ctx.send(
                f"{ctx.author.name} has eaten a cookie, they now have {user['cookies']}"
            )
            return

        if args[0] in ["--bake"]:
            user = self.get_user_data(ctx.author.id)

            if user["last_bake"]:
                last = datetime.fromisoformat(user["last_bake"])
                now = datetime.utcnow()
                diff = now - last

                if diff < timedelta(hours=5):
                    remaining = timedelta(hours=5) - diff
                    hours = int(remaining.total_seconds() // 3600)
                    minutes = int((remaining.total_seconds() % 3600) // 60)
                    await ctx.send(
                        f"you need to wait {hours}h {minutes}m before baking again"
                    )
                    return

            user["cookies"] += 1
            user["last_bake"] = datetime.utcnow().isoformat()
            self.save()

            await ctx.send(
                f"{ctx.author.name} has baked a cookie, they now have {user['cookies']}"
            )
            return

        if args[0] in ["--redeem", "--prestige"]:
            user = self.get_user_data(ctx.author.id)

            if user["cookies"] < 100:
                await ctx.send("you need at least 100 cookies to redeem")
                return

            cakes = user["cookies"] // 100
            user["cookies"] %= 100
            user["cakes"] += cakes
            self.save()

            if cakes == 1:
                await self.ach.grant_achievement(
                    str(ctx.author.id), "bakery", ctx.guild, ctx.channel
                )

            await ctx.send(
                f"{ctx.author.name} redeemed {cakes} cake(s)! they now have {user['cookies']} cookies and {user['cakes']} cakes"
            )
            return

        if args[0] in ["-g", "--give"]:
            if len(args) < 2:
                await ctx.send("usage: cookies -g @user [amount]")
                return

            try:
                target = await commands.MemberConverter().convert(ctx, args[1])
            except discord.NotFound:
                await ctx.send("user not found")
                return

            amount = 1
            if len(args) > 2:
                try:
                    amount = int(args[2])
                except Exception:
                    await ctx.send("invalid amount")
                    return

            if amount <= 0:
                await ctx.send("amount must be positive")
                return

            user = self.get_user_data(ctx.author.id)
            if user["cookies"] < amount:
                await ctx.send("you dont have enough cookies")
                return

            success = await self.give_cookie(
                ctx.author.id, target.id, amount, ctx.guild, ctx.channel
            )

            if success:
                giver = self.get_user_data(ctx.author.id)
                receiver = self.get_user_data(target.id)

                giver["given"] += amount
                self.save()

                await self.check_give_achievements(
                    ctx.author.id, ctx.guild, ctx.channel
                )

                await ctx.send(
                    f"{ctx.author.name} ({giver['cookies']}) has given {target.name} ({receiver['cookies']}) {amount} cookie(s)!"
                )
            else:
                await ctx.send("failed to give cookies")
            return

        try:
            target = await commands.MemberConverter().convert(ctx, args[0])
        except discord.NotFound:
            await ctx.send("user not found")
            return

        if len(args) > 1 and args[1] in ["-g", "--give"]:
            amount = 1
            if len(args) > 2:
                try:
                    amount = int(args[2])
                except Exception:
                    await ctx.send("invalid amount")
                    return

            if amount <= 0:
                await ctx.send("amount must be positive")
                return

            user = self.get_user_data(ctx.author.id)
            if user["cookies"] < amount:
                await ctx.send("you dont have enough cookies")
                return

            success = await self.give_cookie(
                ctx.author.id, target.id, amount, ctx.guild, ctx.channel
            )

            if success:
                giver = self.get_user_data(ctx.author.id)
                receiver = self.get_user_data(target.id)

                giver["given"] += amount
                self.save()

                await self.check_give_achievements(
                    ctx.author.id, ctx.guild, ctx.channel
                )

                await ctx.send(
                    f"{ctx.author.name} ({giver['cookies']}) has given {target.name} ({receiver['cookies']}) {amount} cookie(s)!"
                )
            else:
                await ctx.send("failed to give cookies")
            return

        target_data = self.get_user_data(target.id)
        msg = f"{target.name} has {target_data['cookies']} cookie(s)"
        if target_data["cakes"] > 0:
            msg += f" and {target_data['cakes']} cake(s)"
        msg += f". give {target.name} a cookie?"

        view = CookieView(ctx.author, target)
        prompt = await ctx.send(msg, view=view)
        await view.wait()

        try:
            await prompt.delete()
        except Exception:
            pass

        if view.value is None:
            await ctx.send("timed out")
            return

        if not view.value:
            return

        user = self.get_user_data(ctx.author.id)
        if user["cookies"] < 1:
            await ctx.send("you dont have any cookies")
            return

        success = await self.give_cookie(
            ctx.author.id, target.id, 1, ctx.guild, ctx.channel
        )

        if success:
            giver = self.get_user_data(ctx.author.id)
            receiver = self.get_user_data(target.id)

            giver["given"] += 1
            self.save()

            await self.check_give_achievements(ctx.author.id, ctx.guild, ctx.channel)

            await ctx.send(
                f"{ctx.author.name} ({giver['cookies']}) has given {target.name} ({receiver['cookies']}) a cookie!"
            )


async def setup(bot):
    await bot.add_cog(Cookies(bot))
