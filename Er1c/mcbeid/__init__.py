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

import re
from asyncio import create_task
from traceback import format_exc

from httpx import HTTPStatusError
from orjson import loads
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import cfg
from core.expr import PM, And
from core.router import on_message
from models.api import Message
from utils.api import post_msg_to_supers
from utils.network import get_httpx_client

SEARCH_LIMIT = cfg.register("search_limit", 3)


@on_message(And(PM.message == "beid", PM.prefix == True), register_help={"beid": "查询 MCBE 的 ID 表。"})
async def wk(event: Message):
    await event.reply("BEID：\n[beid 词条]")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5), reraise=True)
async def _fetch_api(query):
    try:
        resp = await get_httpx_client().get(
            "https://ca.projectxero.top/idlist/search", params={"q": query, "limit": SEARCH_LIMIT + 1}
        )
        resp.raise_for_status()
        return loads(resp.content)
    except HTTPStatusError:
        raise


@on_message(r"beid\s*(\S+)")
async def mcbeid(event: Message, match_: re.Match):
    await event.poke()
    try:
        data = (await _fetch_api(match_[1].strip()))["data"]
    except Exception:
        create_task(post_msg_to_supers(f"请求 API 时报错：\n{format_exc()}"))
        return await event.reply("出错了。")
    if result := data["result"]:
        plain_texts = [f'{item["enumName"]}：{item["key"]} -> {item["value"].split("\n")[0]}' for item in result[:SEARCH_LIMIT]]
        if len(result) > SEARCH_LIMIT:
            plain_texts.append(f"\n查看更多：https://ca.projectxero.top/idlist/{data["hash"]}")
        return await event.reply("\n".join(plain_texts))
    await event.reply("没有找到结果。")
