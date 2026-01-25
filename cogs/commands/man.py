import discord
from discord.ext import commands
import aiohttp
import asyncio
import os
import re
from urllib.parse import quote


class Docs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    def clean_html(self, text):
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def truncate_text(self, text, sentences=3):
        sentences_list = re.split(r"(?<=[.!?])\s+", text)
        return " ".join(sentences_list[:sentences])

    @commands.command()
    async def man(self, ctx, *, command: str):
        candidates = [
            f"https://man.archlinux.org/man/{quote(command)}.1p.raw",
            f"https://man.archlinux.org/man/{quote(command)}.1.raw",
        ]

        text = None

        try:
            for c in candidates:
                async with self.session.get(c) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        break
                    if resp.status == 404:
                        continue

            if not text:
                await ctx.send(f"no manual entry for {command}")
                return

            import tempfile

            with tempfile.NamedTemporaryFile(mode="w", suffix=".1", delete=False) as f:
                f.write(text)
                temp_path = f.name

            try:
                process = await asyncio.create_subprocess_exec(
                    "groff",
                    "-man",
                    "-Tutf8",
                    temp_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await process.communicate()
                result = stdout.decode("utf-8", errors="replace")

                result = re.sub(r"\x1b\[[0-9;]*m", "", result)

                lines = result.split("\n")
                header_line = lines[0].strip() if lines else f"{command.upper()}(1)"

                name_start = result.find("NAME")
                synopsis_start = result.find("SYNOPSIS")
                description_start = result.find("DESCRIPTION")

                if name_start == -1 or synopsis_start == -1 or description_start == -1:
                    await ctx.send("failed to parse manual page")
                    return

                name_content = (
                    result[name_start:synopsis_start].replace("NAME", "").strip()
                )
                name_content = "\n".join(
                    [line.strip() for line in name_content.split("\n") if line.strip()]
                )

                synopsis_content = (
                    result[synopsis_start:description_start]
                    .replace("SYNOPSIS", "")
                    .strip()
                )
                synopsis_content = "\n".join(
                    [
                        line.strip()
                        for line in synopsis_content.split("\n")
                        if line.strip()
                    ]
                )

                desc_section = (
                    result[description_start:].replace("DESCRIPTION", "", 1).strip()
                )
                desc_lines = desc_section.split("\n")
                desc_paragraph = []
                for line in desc_lines:
                    stripped = line.strip()
                    if stripped:
                        desc_paragraph.append(stripped)
                    elif desc_paragraph:
                        break
                desc_content = " ".join(desc_paragraph)

                output = f"-# {header_line}\n\n"
                output += f"**NAME**\n{name_content}\n\n"
                output += f"**SYNOPSIS**\n```\n{synopsis_content}\n```\n\n"
                output += f"**DESCRIPTION**\n{desc_content}\n\n"

                if len(output) > 2000:
                    output = output[:1950] + "...\n" + f"-# {header_line}"

                await ctx.send(output)

            finally:
                os.unlink(temp_path)

        except Exception as e:
            print(f"error fetching man page: {e}")
            await ctx.send("failed to fetch manual page")

    @commands.command()
    async def aw(self, ctx, *, page: str):
        page_title = page.replace(" ", "_")
        url = f"https://wiki.archlinux.org/title/{quote(page_title)}"

        try:
            async with self.session.get(
                f"https://wiki.archlinux.org/api.php?action=parse&page={quote(page_title)}&format=json&prop=text"
            ) as resp:
                if resp.status != 200:
                    await ctx.send("page not found on arch wiki")
                    return

                data = await resp.json()

                if "error" in data:
                    await ctx.send("page not found on arch wiki")
                    return

                html = data["parse"]["text"]["*"]

                text = self.clean_html(html)
                snippet = self.truncate_text(text, 3)

                class ArchWikiView(discord.ui.LayoutView):
                    def __init__(self, url, text, snippet):
                        super().__init__(timeout=None)
                        container = discord.ui.Container(
                            discord.ui.TextDisplay(content=f"## {page_title}"),
                            discord.ui.TextDisplay(
                                content="-# From [ArchWiki](https://wiki.archlinux.org/)."
                            ),
                            discord.ui.Separator(
                                visible=True, spacing=discord.SeparatorSpacing.large
                            ),
                            discord.ui.TextDisplay(content=snippet),
                            discord.ui.Separator(
                                visible=True, spacing=discord.SeparatorSpacing.small
                            ),
                            discord.ui.TextDisplay(
                                content=f"-# read the full article here: {url}"
                            ),
                        )
                        self.add_item(container)

                view = ArchWikiView(url, text, snippet)
                await ctx.send(view=view)

        except Exception as e:
            print(f"error fetching arch wiki: {e}")
            await ctx.send("failed to fetch arch wiki page")

    @commands.command()
    async def gw(self, ctx, *, page: str):
        page_title = page.replace(" ", "_")
        url = f"https://wiki.gentoo.org/wiki/{quote(page_title)}"

        try:
            async with self.session.get(
                f"https://wiki.gentoo.org/api.php?action=parse&page={quote(page_title)}&format=json&prop=text"
            ) as resp:
                if resp.status != 200:
                    await ctx.send("page not found on gentoo wiki")
                    return

                data = await resp.json()

                if "error" in data:
                    await ctx.send("page not found on gentoo wiki")
                    return

                html = data["parse"]["text"]["*"]

                text = self.clean_html(html)
                snippet = self.truncate_text(text, 3)

                class GentooWikiView(discord.ui.LayoutView):
                    def __init__(self, url, text, snippet):
                        super().__init__(timeout=None)
                        container = discord.ui.Container(
                            discord.ui.TextDisplay(content=f"## {page_title}"),
                            discord.ui.TextDisplay(
                                content="-# From [Gentoo Wiki](https://wiki.gentoo.org/)."
                            ),
                            discord.ui.Separator(
                                visible=True, spacing=discord.SeparatorSpacing.large
                            ),
                            discord.ui.TextDisplay(content=snippet),
                            discord.ui.Separator(
                                visible=True, spacing=discord.SeparatorSpacing.small
                            ),
                            discord.ui.TextDisplay(
                                content=f"-# read the full article here: {url}"
                            ),
                        )
                        self.add_item(container)

                view = GentooWikiView(url, text, snippet)

                await ctx.send(view=view)

        except Exception as e:
            print(f"error fetching gentoo wiki: {e}")
            await ctx.send("failed to fetch gentoo wiki page")


async def setup(bot):
    await bot.add_cog(Docs(bot))
