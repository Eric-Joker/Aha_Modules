# Copyright (C) 2025 github.com/Eric-Joker
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from asyncio import create_task
from re import Match
from traceback import format_exc

from core.api import API
from core.config import cfg
from core.expr import PM, And
from core.router import on_message
from models.api import Message
from utils.api import post_msg_to_supers
from utils.playwright import capture_element

from .client import MediaWikiClient

WIKI_MAP = cfg.register(
    "wiki", {"wiki": "https://zh.minecraft.wiki", "enwiki": "https://minecraft.wiki", "devwiki": "https://wiki.mcbe-dev.net/w"}
)


@on_message(And(PM.message == "wiki", PM.prefix == True), register_help={"wiki": "查询 Wiki 词条"})
async def wk(event: Message):
    await event.reply("Wiki：\n[wiki/enwiki/devwiki 词条] - 中文MCwiki/英文MCwiki/基岩开发wiki")


async def send_response(event: Message, result):
    task = create_task(capture_element(result[1], "div.tabber-container-infobox", quality=100))
    await event.reply("\n".join(result))
    if img := await task:
        await event.reply(image=img)


async def handle_error(event: Message):
    create_task(post_msg_to_supers(f"请求 wiki 时报错：\n{format_exc()}"))
    await event.reply("出错了。")


@on_message(r"(\S*wiki)\s*([\s\S]+)")
async def fetch(event: Message, match_: Match):
    if not (url := WIKI_MAP.get(match_[1])):
        return

    await API.poke()

    try:
        if result := await (client := MediaWikiClient(url)).fetch_intro(term := match_[2].strip()):
            await send_response(event, result)
        else:
            similar = await client.search_and_cache_results(uid := await event.user_aha_id(), term)
            on_message(r"(\d+)", PM.uid == uid, exp=300)(reget)
            await event.reply(
                f"找不到该词条{f"，相似的有：\n{"\n".join(f"{i+1}. {v}" for i, v in enumerate(similar))}\n五分钟内发送序号即可获取" if similar else "。"}"
            )
    except Exception:
        await handle_error(event)


async def reget(event: Message, match_: Match):
    create_task(API.poke())
    try:
        if result := await MediaWikiClient().get_cached_intro(await event.user_aha_id(), int(match_[1]) - 1):
            await send_response(event, result)
    except Exception:
        await handle_error(event)
