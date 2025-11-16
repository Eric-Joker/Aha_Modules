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

from contextlib import suppress

from orjson import loads
from sqlalchemy import select
from tenacity import retry, stop_after_attempt, wait_exponential
from urllib.parse import urljoin

from core.database import db_session_factory
from utils.network import get_httpx_client
from utils.sqlalchemy import upsert

from .database import WikiSearch


class MediaWikiClient:
    __slots__ = ("_base_url",)

    def __init__(
        self,
        base_url: str = None,
    ):
        """
        Args:
            base_url: MediaWiki站点基础URL (e.g. "https://zh.minecraft.wiki")。
        """
        self._base_url = base_url

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5), reraise=True)
    async def _fetch_api(self, params: dict) -> dict:
        (resp := await get_httpx_client().get(urljoin(self._base_url, "api.php"), params=params)).raise_for_status()
        data = loads(resp.content)
        with suppress(KeyError):
            raise ValueError(f"API Error: {data['error']['info']}")
        return data

    async def fetch_intro(self, term: str) -> tuple[str, str] | None:
        """
        :return: (简介文本, 页面URL)
        """
        try:
            data = await self._fetch_api(
                {
                    "action": "query",
                    "format": "json",
                    "titles": term,
                    "redirects": "1",  # 自动重定向处理
                    "prop": "extracts|info",  # 获取简介和页面信息
                    "inprop": "url",  # 包含完整页面URL
                    "exintro": "1",  # 仅获取简介部分
                    "explaintext": "1",  # 返回纯文本
                }
            )
        except ValueError as e:
            if "missingtitle" in str(e).lower():
                return None
            raise

        if not (pages := data.get("query", {}).get("pages", {})):
            return None
        if (page := next(iter(pages.values()))).get("pageid", -1) == -1:
            return None

        return page.get("extract", ""), page.get("fullurl", "")

    async def search_similar(self, term: str, limit: int = 3):
        """搜索相似词条

        Args:
            limit: 最多返回几个结果。
        """
        data = await self._fetch_api(
            {
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": term,
                "srlimit": str(limit),
                "srwhat": "text",
            }
        )

        search_results = data.get("query", {}).get("search", [])
        return [result["title"] for result in search_results]

    async def get_cached_intro(self, user, index: int):
        async with db_session_factory() as session:
            record = await session.scalar(select(WikiSearch).where(WikiSearch.user_id == user))

            if not record or index >= len(record.results):
                return None

            self._base_url = record.base_url

            await session.delete(record)
            await session.commit()

            return await self.fetch_intro(record.results[index])

    async def search_and_cache_results(self, user, term: str, limit: int = 3):
        if results := await self.search_similar(term, limit):
            async with db_session_factory() as session:
                await session.execute(upsert(WikiSearch, user_id=user, base_url=self._base_url, results=results))
                await session.commit()
        return results
