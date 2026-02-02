import discord
from discord.ext import commands
import json
from pathlib import Path


class Alias(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = Path("data/aliases.json")
        self.data_file.parent.mkdir(exist_ok=True)

        self.aliases = self.load_data()
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
            json.dump(self.aliases, f, indent=2)

    def has_staff_role(self, member):
        return discord.utils.get(member.roles, name="staff@hazelrun") is not None

    def can_modify_alias(self, alias_name, user_id):
        if alias_name not in self.aliases:
            return False

        alias_data = self.aliases[alias_name]
        return str(alias_data["creator"]) == str(user_id)

    @commands.command()
    async def alias(self, ctx, *args):
        if not args:
            await ctx.send(
                "```\n"
                "usage: alias [OPTION]...\n"
                "manage chat aliases\n\n"
                "options:\n"
                "  -a, --add            add a new alias\n"
                "  -r, --remove         remove an existing alias\n"
                "  -e, --edit           edit an existing alias\n"
                "  -n, --name NAME      specify alias name\n"
                "  -c, --content TEXT   content for the alias\n"
                "  -l, --language LANG  language code (default: en)\n"
                "  -L, --list [PAGE]    list all aliases, 10 per page\n"
                "  -N, --newname NAME   new name when editing an alias\n"
                "  -h, --help           display this help\n\n"
                "example:\n"
                "  alias -a -n greet -c 'hello world' -l en\n"
                "```"
            )
            return

        if args[0] in ["-h", "--help"]:
            await ctx.send(
                "```\n"
                "alias - manage chat aliases\n\n"
                "options:\n"
                "  -a, --add            add a new alias\n"
                "  -r, --remove         remove an existing alias\n"
                "  -e, --edit           edit an existing alias\n"
                "  -n, --name NAME      specify alias name\n"
                "  -c, --content TEXT   content for the alias\n"
                "  -l, --language LANG  language code (default: en)\n"
                "  -L, --list [PAGE]    list all aliases, 10 per page\n"
                "  -N, --newname NAME   new name when editing an alias\n"
                "  -h, --help           display this help\n\n"
                "examples:\n"
                "  alias -a -n greet -c 'hello world' -l en\n"
                "  alias -r -n greet\n"
                "  alias -e -n greet -c 'hi there' -N welcome\n"
                "  alias -L 2\n"
                "```"
            )
            return

        if args[0] in ["-a", "--add", "--new"]:
            name = None
            content = "no content set!"
            lang = "en"

            i = 1
            while i < len(args):
                if args[i] == "-n" and i + 1 < len(args):
                    name = args[i + 1]
                    i += 2
                elif args[i] == "-c" and i + 1 < len(args):
                    content_raw = args[i + 1]
                    content = content_raw.replace('\\"', '"')
                    i += 2
                elif args[i] == "-l" and i + 1 < len(args):
                    lang = args[i + 1]
                    i += 2
                else:
                    i += 1

            if not name:
                await ctx.send("you need to provide a name with -n")
                return

            if name in self.aliases:
                await ctx.send(f"alias {name} already exists")
                return

            self.aliases[name] = {
                "content": content,
                "lang": lang,
                "creator": str(ctx.author.id),
                "creator_name": ctx.author.name,
            }
            self.save_data()

            await ctx.send(f"created alias {name}")

            if self.logger:
                self.logger.info(f"alias created: {name} by {ctx.author.name}")

        elif args[0] in ["-r", "--remove"]:
            name = None

            i = 1
            while i < len(args):
                if args[i] == "-n" and i + 1 < len(args):
                    name = args[i + 1]
                    i += 2
                else:
                    i += 1

            if not name:
                await ctx.send("you need to provide a name with -n")
                return

            if name not in self.aliases:
                await ctx.send(f"alias {name} doesnt exist")
                return

            if not self.can_modify_alias(
                name, ctx.author.id
            ) and not self.has_staff_role(ctx.author):
                await ctx.send("you dont have permission to remove this alias")
                return

            del self.aliases[name]
            self.save_data()

            await ctx.send(f"removed alias {name}")

            if self.logger:
                self.logger.info(f"alias removed: {name} by {ctx.author.name}")

        elif args[0] in ["-e", "--edit"]:
            name = None
            new_name = None
            content = None
            lang = None

            i = 1
            while i < len(args):
                if args[i] == "-n" and i + 1 < len(args):
                    name = args[i + 1]
                    i += 2
                elif args[i] == "-N" and i + 1 < len(args):
                    new_name = args[i + 1]
                    i += 2
                elif args[i] == "-c" and i + 1 < len(args):
                    content_raw = args[i + 1]
                    content = content_raw.replace('\\"', '"')
                    i += 2
                elif args[i] == "-l" and i + 1 < len(args):
                    lang = args[i + 1]
                    i += 2
                else:
                    i += 1

            if not name:
                await ctx.send("you need to provide a name with -n")
                return

            if name not in self.aliases:
                await ctx.send(f"alias {name} doesnt exist")
                return

            if not self.can_modify_alias(
                name, ctx.author.id
            ) and not self.has_staff_role(ctx.author):
                await ctx.send("you dont have permission to edit this alias")
                return

            alias_data = self.aliases[name]

            if content:
                alias_data["content"] = content
            if lang:
                alias_data["lang"] = lang
            if new_name:
                if new_name in self.aliases and new_name != name:
                    await ctx.send(f"alias {new_name} already exists")
                    return
                self.aliases[new_name] = alias_data
                del self.aliases[name]
                name = new_name

            self.save_data()

            await ctx.send(f"edited alias {name}")

            if self.logger:
                self.logger.info(f"alias edited: {name} by {ctx.author.name}")

        elif args[0] in ["-L", "--list"]:
            if not self.aliases:
                await ctx.send("no aliases exist yet")
                return

            page = 1
            if len(args) > 1:
                try:
                    page = int(args[1])
                except ValueError:
                    page = 1

            aliases_list = list(self.aliases.items())
            total_pages = (len(aliases_list) + 9) // 10
            page = max(1, min(page, total_pages))

            start = (page - 1) * 10
            end = start + 10

            msg = f"**aliases (page {page}/{total_pages})**\n\n"

            for alias_name, alias_data in aliases_list[start:end]:
                creator_name = alias_data.get("creator_name", "unknown")
                lang = alias_data.get("lang", "en")
                content_preview = alias_data["content"][:50]
                if len(alias_data["content"]) > 50:
                    content_preview += "..."

                msg += f"**{alias_name}** ({lang}) by {creator_name}\n  ⋱ {content_preview}\n"

            await ctx.send(msg)

        else:
            await ctx.send(f"unknown option: {args[0]}\nuse >alias -h for help")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.content.startswith(">"):
            return
        if message.content.startswith("$"):
            content = message.content[1:].strip()
            for alias_name, alias_data in self.aliases.items():
                if content == alias_name:
                    await message.channel.send(alias_data["content"])

                    if self.logger:
                        self.logger.info(
                            f"alias triggered: {alias_name} by {message.author.name}"
                        )

                    break


async def setup(bot):
    await bot.add_cog(Alias(bot))
