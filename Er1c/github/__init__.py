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

from .client import GithubClient, Repository

SHORTCUT = cfg.register("shortcut", {"aha": "Eric-Joker/Aha"})
TOKEN = cfg.register("token", "")


@on_message(And(PM.message == "github", PM.prefix == True), register_help={"github": "查询 Github 仓库/用户信息"})
async def gh(event: Message):
    await event.reply("Github：\n[gh/github (用户名/)仓库名] - 查询/搜索仓库\n[gu 用户名]")


async def send_repo_response(event: Message, result: Repository):
    await event.reply(
        (
            f"📦 仓库: {result.name}\n"
            f"🔗 链接: {result.html_url}\n"
            f"📝 简介: {result.description or '暂无描述'}\n"
            f"🌐 语言: {result.language or '未指定'}\n"
            f"⭐ {result.stars} | 🍴 {result.forks} | 👀 {result.watchers}\n"
            f"📜 证书: {(result.license.name if result.license else None) or '无'}\n"
            f"⏰ 创建于: {result.created_at} | 更新于: {result.updated_at}"
        ),
    )


async def handle_error(event: Message):
    create_task(post_msg_to_supers(f"请求 Github 时报错：\n{format_exc()}"))
    await event.reply("出错了。")


@on_message(r"(?:gh|github)\s*([\s\S]+)")
async def fetch_repo(event: Message, match_: Match):
    await API.poke()

    is_repo = "/" in (term := SHORTCUT.get((term := match_[1].strip()).lower()) or term)
    try:
        if is_repo and (result := await GithubClient.get_repo(term)):
            await send_repo_response(event, result)
        else:
            similar = await GithubClient.cache_search(uid := await event.user_aha_id(), term)
            on_message(r"(\d+)", PM.uid == uid, exp=300, callback=reget)
            await event.reply(
                f"{"找不到该仓库。" if is_repo else ""}{f"相似的有：\n{"\n".join(f"{i+1}. {v}" for i, v in enumerate(similar))}\n五分钟内发送序号即可获取" if similar else ""}"
            )
    except Exception:
        await handle_error(event)


@on_message(r"gu\s*([\s\S]+)")
async def fetch_gh_user(event: Message, match_: Match):
    await API.poke()
    try:
        await event.reply(
            (
                (
                    f"👤 用户: {result.login}\n"
                    f"🔗 链接: {result.html_url}\n"
                    f"🏷️ 类型: {result.type}\n"
                    f"❤️ 关注: {result.following} | 🕴️ 粉丝: {result.followers}\n"
                    f"📂 仓库: {result.public_repos} | 📝 Gists: {result.public_gists}\n"
                    f"⏰ 创建于: {result.created_at} | 活跃于: {result.updated_at}"
                )
                if (result := await GithubClient.get_user(match_[1].strip()))
                else "未找到该用户。"
            )
        )
    except Exception:
        await handle_error(event)


async def reget(event: Message, match_: Match):
    create_task(API.poke())
    try:
        if result := await GithubClient.get_cached_repo(await event.user_aha_id(), int(match_[1]) - 1):
            await send_repo_response(event, result)
    except Exception:
        await handle_error(event)
