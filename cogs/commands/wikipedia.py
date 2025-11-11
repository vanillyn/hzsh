import re
import shlex
import argparse
from urllib.parse import quote
import aiohttp
import discord
from discord.ext import commands
from discord.ui import LayoutView, TextDisplay, Separator, Container, MediaGallery
from discord import MediaGalleryItem, SeparatorSpacing
from bs4 import BeautifulSoup
from markdownify import markdownify as md

DISCORD_MSG_LIMIT = 2000
EMBED_DESC_LIMIT = 4096
HEADERS = {"User-Agent": "hazelrun/b0.9 (contact: skyykiwi@gmail.com)"}


class WikipediaFlags:
    def __init__(self):
        p = argparse.ArgumentParser(prog="wp", add_help=False)
        p.add_argument(
            "-l", "--lang", type=str, help="two-letter language code (en, ja, ...)"
        )
        p.add_argument(
            "-t",
            "--type",
            choices=("text", "embed", "container"),
            default="embed",
            help="output style",
        )
        p.add_argument(
            "-i", "--image", dest="image", type=str, help="true/false include thumbnail"
        )
        p.add_argument("--link", dest="link", type=str, help="true/false include link")
        p.add_argument(
            "-s",
            "--search",
            dest="search",
            type=str,
            help="search text inside page and show that section",
        )
        p.add_argument(
            "--max",
            dest="max_chars",
            type=int,
            default=1200,
            help="max chars for text output",
        )
        self.parser = p

    def _parse_bool(self, v):
        if v is None:
            return None
        s = str(v).lower()
        if s in ("1", "true", "yes", "y", "on"):
            return True
        if s in ("0", "false", "no", "n", "off"):
            return False
        return None

    def parse(self, raw: str):
        toks = shlex.split(raw)
        ns, extras = self.parser.parse_known_args(toks)
        ns.image = self._parse_bool(ns.image)
        ns.link = self._parse_bool(ns.link)
        leftover = " ".join(extras).strip()
        return ns, leftover


class Wikipedia(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.flags = WikipediaFlags()

    async def cog_unload(self):
        try:
            await self.session.close()
        except Exception:
            pass

    async def fetch_html(self, lang: str, title: str):
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/html/{title}"
        async with self.session.get(url, headers=HEADERS) as resp:
            if resp.status == 404:
                return None
            if resp.status != 200:
                raise RuntimeError(f"wikipedia html returned {resp.status}")
            return await resp.text()

    async def fetch_summary(self, lang: str, title: str):
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}?redirect=true"
        async with self.session.get(url, headers=HEADERS) as resp:
            if resp.status == 404:
                return None
            if resp.status != 200:
                raise RuntimeError(f"wikipedia summary returned {resp.status}")
            return await resp.json()

    def extract_sections(self, html: str):
        soup = BeautifulSoup(html, "lxml")
        for bad in soup.select(
            "script, style, link, nav, .references, .mw-references-wrap"
        ):
            bad.decompose()

        main = soup.find(id="mw-content-text") or soup.body or soup

        from bs4 import Tag

        if not isinstance(main, Tag):
            main = BeautifulSoup(str(main), "lxml")

        sections = []
        lead_parts = []
        from bs4 import Tag

        for child in list(main.children):
            if isinstance(child, Tag) and child.name == "h2":
                break
            lead_parts.append(str(child))
        lead_html = "".join(lead_parts).strip()
        if lead_html:
            sections.append((None, 0, lead_html))

        headers = main.find_all(re.compile("^h[2-6]$"))
        for header in headers:
            header_name = getattr(header, "name", None)
            level = int(header_name[1]) if header_name and len(header_name) > 1 else 0
            heading_text = header.get_text(strip=True)
            frag = []
            for sib in header.next_siblings:
                sib_name = getattr(sib, "name", None)
                if sib_name and re.match("^h[2-6]$", sib_name):
                    next_level = int(sib_name[1]) if len(sib_name) > 1 else 0
                    if next_level <= level:
                        break
                frag.append(str(sib))
            frag_html = "".join(frag).strip()
            sections.append((heading_text, level, frag_html))
        return sections

    def choose_section_by_search(self, sections, needle: str):
        needle_l = needle.lower()
        for heading, lvl, html in sections:
            text = (
                (heading or "")
                + " "
                + BeautifulSoup(html, "lxml").get_text(" ", strip=True)
            )
            if needle_l in text.lower():
                return heading, lvl, html
        return sections[0] if sections else (None, 0, "")

    def html_to_markdown(self, html_fragment: str, max_chars: int = 1200):
        mdtxt = md(html_fragment, heading_style="ATX")
        if len(mdtxt) <= max_chars:
            return mdtxt.strip()
        cut = mdtxt[:max_chars]
        last_double_nl = cut.rfind("\n\n")
        if last_double_nl > max_chars // 3:
            cut = cut[:last_double_nl]
        return cut.strip() + "\n\n... (truncated)"

    async def _handle(self, ctx, lang: str, page: str, ns):
        lang = (lang or "en").lower()
        if not (lang.isalpha() and len(lang) == 2):
            await ctx.send("invalid language code (two letters like en, ja, de)")
            return
        if not page:
            await ctx.send("no page provided")
            return

        title = quote(page.replace(" ", "_"))
        try:
            summary = await self.fetch_summary(lang, title)
        except Exception:
            summary = None
        try:
            html = await self.fetch_html(lang, title)
        except Exception:
            html = None

        if summary is None and html is None:
            await ctx.send("page not found on wikipedia")
            return

        thumbnail = None
        page_url = f"https://{lang}.wikipedia.org/wiki/{title}"
        if summary:
            thumbnail = summary.get("thumbnail", {}).get("source")
            page_url = (
                summary.get("content_urls", {}).get("desktop", {}).get("page", page_url)
            )
            page_title = summary.get("title", page)
            lead_extract = summary.get("extract", "")
        else:
            page_title = page.replace("_", " ")
            lead_extract = ""

        want_image = ns.image if ns.image is not None else True
        want_link = ns.link if ns.link is not None else True

        sections = []
        if html:
            sections = self.extract_sections(html)

            if ns.search:
                heading, lvl, frag_html = self.choose_section_by_search(
                    sections, ns.search
                )
                md = self.html_to_markdown(frag_html or "", max_chars=ns.max_chars)
                header_line = f"**{heading}**\n\n" if heading else ""
                out_text = header_line + md
            else:
                if lead_extract:
                    out_text = lead_extract
                else:
                    for h, frag in sections:
                        if frag and BeautifulSoup(frag, "lxml").get_text(strip=True):
                            out_text = self.html_to_markdown(
                                frag, max_chars=ns.max_chars
                            )
                            break
                    else:
                        out_text = ""
        else:
            out_text = lead_extract or ""

        out_type = ns.type or "embed"

        if out_type == "text":
            pieces = []
            pieces.append(f"**{page_title}**")
            pieces.append(out_text or "")
            if want_link:
                pieces.append(f"<{page_url}>")
            if want_image and thumbnail:
                pieces.append(f"[thumbnail] {thumbnail}")

            final = "\n\n".join(pieces)
            if len(final) > DISCORD_MSG_LIMIT:
                final = final[: DISCORD_MSG_LIMIT - 10] + "\n\n... (truncated)"
            await ctx.send(final)
            return

        if out_type == "embed":
            desc = out_text or ""
            if len(desc) > EMBED_DESC_LIMIT:
                desc = desc[: EMBED_DESC_LIMIT - 50] + "\n\n... (truncated)"
            emb = discord.Embed(
                title=f"wikipedia ({lang}): {page_title}",
                description=desc,
                url=page_url,
            )
            if want_image and thumbnail:
                emb.set_thumbnail(url=thumbnail)
            await ctx.send(embed=emb)
            return

        if out_type == "container":

            class Components(LayoutView):
                def __init__(
                    self, lang, page_title, out_text, page_url, want_image, thumbnail
                ):
                    super().__init__(timeout=None)
                    container = Container(
                        TextDisplay(content=f"## {page_title}"),
                        TextDisplay(
                            content=f"-# From [Wikipedia](https://en.wikipedia.org/wiki/Wikipedia), the free encyclopedia. ({lang})"
                        ),
                        Separator(visible=True, spacing=SeparatorSpacing.large),
                        TextDisplay(content=f"{out_text}"),
                        Separator(visible=True, spacing=SeparatorSpacing.small),
                        TextDisplay(
                            content=f"-# read the full article here: {page_url}\n"
                        ),
                    )
                    if want_image and thumbnail:
                        container.add_item(
                            MediaGallery(
                                MediaGalleryItem(media=thumbnail),
                            )
                        )
                    self.add_item(container)

                async def on_error(
                    self,
                    interaction: discord.Interaction,
                    error: Exception,
                    item: discord.ui.Item,
                ) -> None:
                    self.stop()

            view = Components(
                lang, page_title, out_text, page_url, want_image, thumbnail
            )
            await ctx.send(view=view)

    @commands.command(name="wp")
    async def wp_cmd(self, ctx: commands.Context, *, raw: str = ""):
        ns, leftover = self.flags.parse(raw or "")
        if not raw:
            await ctx.send(
                "usage: >wp [-l lang] [-t text|embed|container] [-i true|false] [--link true|false] [-s search] page"
            )
            return
        toks = leftover.split()
        if toks and len(toks[0]) == 2 and ns.lang is None:
            ns.lang = toks[0]
            leftover = " ".join(toks[1:]).strip()
        await self._handle(ctx, ns.lang or "en", leftover, ns)


@commands.Cog.listener()
async def on_message(self, message):
    if message.author.bot:
        return

    ctx = await self.bot.get_context(message)
    if ctx.valid:
        return

    m = re.match(r"^(?P<lang>[a-z]{2})wp\b(?:\s+(?P<rest>.+))?", message.content, re.I)
    if not m:
        return

    lang = m.group("lang").lower()
    rest = m.group("rest") or ""
    if not re.search(r"(^|\s)(-l|--lang)\b", rest):
        rest = f"-l {lang} {rest}".strip()
    ns, leftover = self.flags.parse(rest)
    await self._handle(ctx, ns.lang or lang, leftover, ns)


async def setup(bot: commands.Bot):
    await bot.add_cog(Wikipedia(bot))
