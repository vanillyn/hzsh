import discord
from discord.ext import commands

from src.misc import CogHelper, get_data_manager, safe_dm

CATEGORIES = ["installation", "troubleshooting", "configuration", "misc"]


class CategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="installation",
                description="installing an operating system or software",
            ),
            discord.SelectOption(
                label="troubleshooting", description="fixing common bugs or issues"
            ),
            discord.SelectOption(
                label="configuration",
                description="configuring software or system settings",
            ),
            discord.SelectOption(
                label="misc",
                description="other guides that don't fit the above categories",
            ),
        ]
        super().__init__(
            placeholder="select a category", options=options, min_values=1, max_values=1
        )

    async def callback(self, interaction):
        await interaction.response.defer()


class CategoryView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
        self.category = None
        self.cancelled = False
        select = CategorySelect()
        select.callback = self.on_select
        self.add_item(select)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("not your guide", ephemeral=True)
            return False
        return True

    async def on_select(self, interaction):
        self.category = interaction.data["values"][0]
        await interaction.response.send_message(
            f"category set to: {self.category}", ephemeral=True
        )
        self.stop()

    @discord.ui.button(label="cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction, button):
        self.cancelled = True
        await interaction.response.send_message("cancelled", ephemeral=True)
        self.stop()


class GuideView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=1200)
        self.author = author
        self.cancelled = False
        self.sent = False
        self.guide_messages = []
        self.attachments = []
        self.citations = None
        self.waiting_for_citations = False

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("not your guide", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction, button):
        self.cancelled = True
        await interaction.response.send_message(
            "cancelled guide creation", ephemeral=True
        )
        self.stop()

    @discord.ui.button(label="send", style=discord.ButtonStyle.green)
    async def send(self, interaction, button):
        if not self.guide_messages:
            await interaction.response.send_message(
                "you need to send the guide content first", ephemeral=True
            )
            return

        self.sent = True
        await interaction.response.send_message("creating guide...", ephemeral=True)
        self.stop()

    @discord.ui.button(label="citation", style=discord.ButtonStyle.blurple)
    async def citation(self, interaction, button):
        self.waiting_for_citations = True
        await interaction.response.send_message(
            "send your citations (links separated by newlines)", ephemeral=True
        )


class Guides(CogHelper, commands.Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.dm = get_data_manager()
        self.data = self.dm.load("guides", {})
        self.guide_channel_id = 1429678741633634346
        self.pending_guides = {}

    def save(self):
        self.dm.save("guides", self.data)

    def has_guide_role(self, member):
        if discord.utils.get(member.roles, name="guide@hazelrun"):
            return True
        if member.guild_permissions.administrator:
            return True
        return False

    @commands.group(invoke_without_command=True)
    async def guides(self, ctx):
        await ctx.send(
            "use `>guides show [name]` to view a guide\nuse `>guides new [name]` to create a guide (guide role required)"
        )

    @guides.command(name="new", aliases=["n"])
    async def new_guide(self, ctx, *, name: str):
        if not self.has_guide_role(ctx.author):
            await ctx.send("you need the guide role")
            return

        if name.lower() in self.data:
            await ctx.send("a guide with that name already exists")
            return

        category_view = CategoryView(ctx.author)
        await safe_dm(ctx.author, "select a category for your guide")
        await ctx.author.send(view=category_view)
        await ctx.send("check your dms")

        await category_view.wait()

        if category_view.cancelled or not category_view.category:
            return

        category = category_view.category

        await ctx.author.send("send a short description of your guide (1-2 sentences)")

        def check(m):
            return m.author.id == ctx.author.id and isinstance(
                m.channel, discord.DMChannel
            )

        try:
            desc_msg = await self.bot.wait_for("message", timeout=600, check=check)
            description = desc_msg.content
            await desc_msg.add_reaction("✅")
        except Exception:
            await safe_dm(ctx.author, "timed out waiting for description")
            return

        view = GuideView(ctx.author)
        await ctx.author.send("send your guide content\npress send when done")
        await ctx.author.send(view=view)

        while not view.is_finished():
            try:
                message = await self.bot.wait_for("message", timeout=1200, check=check)

                if view.waiting_for_citations:
                    view.citations = message.content
                    view.waiting_for_citations = False
                    await message.add_reaction("✅")
                else:
                    view.guide_messages.append(message.content)
                    if message.attachments:
                        view.attachments.extend(
                            [att.url for att in message.attachments]
                        )
                    await message.add_reaction("✅")

            except:
                break

        if view.cancelled or not view.sent:
            return

        await self.create_guide_thread(
            ctx.guild, name.lower(), description, category, view, ctx.author
        )

    @guides.command(name="edit")
    async def edit_guide(self, ctx, *, name: str):
        if not self.has_guide_role(ctx.author):
            await ctx.send("you need the guide role")
            return

        name_key = name.lower()
        if name_key not in self.data:
            await ctx.send("guide not found")
            return

        guide = self.data[name_key]

        category_view = CategoryView(ctx.author)
        await safe_dm(
            ctx.author, f"editing guide: **{guide['name']}**\nselect a category"
        )
        await ctx.author.send(view=category_view)
        await ctx.send("check your dms")

        await category_view.wait()

        if category_view.cancelled or not category_view.category:
            return

        category = category_view.category

        await ctx.author.send(
            f"send a new description\n-# current: {guide.get('description', 'none')}"
        )

        def check(m):
            return m.author.id == ctx.author.id and isinstance(
                m.channel, discord.DMChannel
            )

        try:
            desc_msg = await self.bot.wait_for("message", timeout=600, check=check)
            description = desc_msg.content
            await desc_msg.add_reaction("✅")
        except Exception:
            await safe_dm(ctx.author, "timed out waiting for description")
            return

        view = GuideView(ctx.author)
        await ctx.author.send(
            "send your updated guide content (you can send multiple messages)\npress send when done"
        )
        await ctx.author.send(view=view)

        while not view.is_finished():
            try:
                message = await self.bot.wait_for("message", timeout=1200, check=check)

                if view.waiting_for_citations:
                    view.citations = message.content
                    view.waiting_for_citations = False
                    await message.add_reaction("✅")
                else:
                    view.guide_messages.append(message.content)
                    if message.attachments:
                        view.attachments.extend(
                            [att.url for att in message.attachments]
                        )
                    await message.add_reaction("✅")

            except:
                break

        if view.cancelled or not view.sent:
            return

        await self.edit_guide_thread(
            ctx.guild,
            name_key,
            description,
            category,
            view,
            guide.get("thread_id"),
            ctx.author,
        )

    @guides.command(name="remove")
    async def remove_guide(self, ctx, *, name: str):
        if not self.has_guide_role(ctx.author):
            await ctx.send("you need the guide role")
            return

        name_key = name.lower()
        if name_key not in self.data:
            await ctx.send("guide not found")
            return

        guide = self.data[name_key]

        try:
            channel = self.bot.get_channel(self.guide_channel_id)
            if channel and guide.get("thread_id"):
                thread = channel.get_thread(guide["thread_id"])
                if thread:
                    await thread.delete()
        except:
            pass

        del self.data[name_key]
        self.save()

        await self.update_guide_list(ctx.guild)
        await ctx.send(f"removed guide: {guide['name']}")

    @guides.command(name="show", aliases=["s"])
    async def show_guide(self, ctx, *, name: str):
        name_key = name.lower()
        if name_key not in self.data:
            await ctx.send("guide not found")
            return

        guide = self.data[name_key]
        thread_id = guide.get("thread_id")

        container = discord.ui.Container(
            discord.ui.TextDisplay(content=f"## {guide['name']}"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                content=f"**category:** {guide.get('category', 'misc')}"
            ),
            discord.ui.TextDisplay(
                content=f"**description:** {guide.get('description', 'no description')}"
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                content=f"-# [view full guide](<https://discord.com/channels/{ctx.guild.id}/{thread_id}>)"
                if thread_id
                else "-# thread not found"
            ),
        )

        view = discord.ui.LayoutView(timeout=None)
        view.add_item(container)

        await ctx.send(view=view)

    async def create_guide_thread(
        self, guild, name_key, description, category, view, author
    ):
        channel = guild.get_channel(self.guide_channel_id)
        if not channel:
            await safe_dm(author, "guide channel not found")
            return

        display_name = name_key.replace("_", " ").title()
        guide_content = "\n\n".join(view.guide_messages)

        if view.attachments:
            guide_content += "\n\n"
            for att in view.attachments:
                guide_content += f"{att}\n"

        footer_text = f"guide by {author.name}"
        if view.citations:
            footer_text += f"\nsources:\n{view.citations}"

        try:
            thread = await channel.create_thread(
                name=f"[{category}] {display_name}",
                type=discord.ChannelType.public_thread,
                auto_archive_duration=10080,
            )

            content = f"{guide_content}\n\n-# {footer_text}"
            await thread.send(content)

            self.data[name_key] = {
                "name": display_name,
                "description": description,
                "category": category,
                "author_id": author.id,
                "thread_id": thread.id,
                "messages": view.guide_messages,
                "attachments": view.attachments,
                "citations": view.citations,
            }
            self.save()

            await self.update_guide_list(guild)
            await safe_dm(author, f"created guide: {display_name}")

        except Exception as e:
            self.log_error(f"failed to create guide: {e}")
            await safe_dm(author, "failed to create guide")

    async def edit_guide_thread(
        self, guild, name_key, description, category, view, thread_id, author
    ):
        channel = guild.get_channel(self.guide_channel_id)
        if not channel:
            await safe_dm(author, "guide channel not found")
            return

        guide_content = "\n\n".join(view.guide_messages)

        if view.attachments:
            guide_content += "\n\n"
            for att in view.attachments:
                guide_content += f"{att}\n"

        footer_text = f"guide by {author.name}"
        if view.citations:
            footer_text += f"\nsources:\n{view.citations}"

        try:
            thread = channel.get_thread(thread_id)
            if not thread:
                await safe_dm(author, "thread not found")
                return

            display_name = self.data[name_key]["name"]
            await thread.edit(name=f"[{category}] {display_name}")

            messages = [m async for m in thread.history(limit=1, oldest_first=True)]
            if messages:
                content = f"{guide_content}\n\n-# {footer_text}"
                await messages[0].edit(content=content)

                self.data[name_key]["description"] = description
                self.data[name_key]["category"] = category
                self.data[name_key]["messages"] = view.guide_messages
                self.data[name_key]["attachments"] = view.attachments
                self.data[name_key]["citations"] = view.citations
                self.save()

                await self.update_guide_list(guild)
                await safe_dm(author, f"updated guide: {display_name}")

        except Exception as e:
            self.log_error(f"failed to edit guide: {e}")
            await safe_dm(author, "failed to edit guide")

    async def update_guide_list(self, guild):
        channel = guild.get_channel(self.guide_channel_id)
        if not channel:
            return

        header_text = """# hazel / run
-# guides/tutorials channel
in this channel, there will be various guides posted here on various topics! if you want to request a guide be made, make a ticket with `>tickets new os-guide`. if you want to help write a guide, make a ticket as well!
guides can be about installing an operating system, configuring a software, or fixing a common bug.
-# if you need help with installing an operating system, don't feel afraid to make a post in <#1429678765570785300>!"""

        categories_data = {cat: [] for cat in CATEGORIES}

        for name, guide in sorted(self.data.items()):
            if name.startswith("_"):
                continue
            category = guide.get("category", "misc")
            thread_id = guide.get("thread_id")
            description = guide.get("description", "no description")

            if thread_id:
                categories_data[category].append(
                    f"• <#{thread_id}> - {guide['name']}\n-# {description}"
                )
            else:
                categories_data[category].append(f"• {guide['name']}\n-# {description}")

        containers = [discord.ui.TextDisplay(content=header_text)]

        for cat in CATEGORIES:
            if categories_data[cat]:
                cat_title = f"**{cat}**"
                cat_content = "\n".join(categories_data[cat])

                containers.append(
                    discord.ui.Separator(
                        visible=True, spacing=discord.SeparatorSpacing.large
                    )
                )
                containers.append(discord.ui.TextDisplay(content=cat_title))
                containers.append(discord.ui.TextDisplay(content=cat_content))

        if all(not categories_data[cat] for cat in CATEGORIES):
            containers.append(
                discord.ui.Separator(
                    visible=True, spacing=discord.SeparatorSpacing.large
                )
            )
            containers.append(discord.ui.TextDisplay(content="no guides yet"))

        containers.append(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        containers.append(
            discord.ui.TextDisplay(
                content="-# use `>guides show [name]` to view a guide"
            )
        )

        container = discord.ui.Container(*containers)
        view = discord.ui.LayoutView(timeout=None)
        view.add_item(container)

        message_id = self.data.get("_list_message_id")

        try:
            if message_id:
                msg = await channel.fetch_message(message_id)
                await msg.edit(content="", view=view)
            else:
                msg = await channel.send(view=view)
                self.data["_list_message_id"] = msg.id
                self.save()
        except:
            msg = await channel.send(view=view)
            self.data["_list_message_id"] = msg.id
            self.save()

    @commands.command(name="gn")
    async def gn_alias(self, ctx, *, name: str):
        await self.new_guide(ctx, name=name)

    @commands.command(name="gs")
    async def gs_alias(self, ctx, *, name: str):
        await self.show_guide(ctx, name=name)


async def setup(bot):
    await bot.add_cog(Guides(bot))
