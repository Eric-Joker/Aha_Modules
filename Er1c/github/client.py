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

from httpx import HTTPStatusError, RequestError
from orjson import loads
from pydantic import BaseModel, Field
from sqlalchemy import select
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.config import cfg
from core.database import db_session_factory
from utils.network import get_httpx_client
from utils.sqlalchemy import upsert

from .database import GithubSearch


class LicenseInfo(BaseModel):
    key: str | None
    name: str | None
    spdx_id: str | None
    url: str | None


class Repository(BaseModel):
    name: str | None
    description: str | None
    language: str | None
    forks: int | None = Field(validation_alias="forks_count")
    stars: int | None = Field(validation_alias="stargazers_count")
    watchers: int | None = Field(validation_alias="subscribers_count")
    license: LicenseInfo | None = None
    created_at: str | None
    updated_at: str | None
    html_url: str | None


class User(BaseModel):
    login: str | None
    type: str | None
    following: int | None
    followers: int | None
    public_repos: int | None
    public_gists: int | None
    created_at: str | None
    updated_at: str | None
    html_url: str | None


class GithubClient:
    @classmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=5, max=15),
        retry_error_callback=lambda _: None,
        retry=retry_if_exception_type((RequestError, HTTPStatusError)),
        reraise=True,
    )
    async def _fetch_api(cls, endpoint: str, params: dict = None):
        (
            response := await get_httpx_client().get(
                f"https://api.github.com/{endpoint}",
                params=params,
                headers={"Authorization": f"Bearer {cfg.token}"} if cfg.token else None,
            )
        ).raise_for_status()
        return response.content

    @classmethod
    async def get_repo(cls, repo: str):
        try:
            return Repository.model_validate_json(await cls._fetch_api(f"repos/{repo}"))
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    @classmethod
    async def get_user(cls, username: str):
        try:
            return User.model_validate_json(await cls._fetch_api(f"users/{username}"))
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    @classmethod
    async def search_repos(cls, query: str, limit: int = 5):
        data = loads(await cls._fetch_api("search/repositories", params={"q": query, "per_page": limit, "sort": "stars"}))
        return (item["full_name"] for item in data.get("items", []))

    @classmethod
    async def cache_search(cls, user, query: str, limit: int = 5):
        """缓存搜索结果"""
        if results := tuple(await cls.search_repos(query, limit)):
            async with db_session_factory() as session:
                await session.execute(upsert(GithubSearch, user_id=user, results=results))
                await session.commit()
        return results

    @classmethod
    async def get_cached_repo(cls, user, index: int):
        """获取缓存结果"""
        async with db_session_factory() as session:
            record = await session.scalar(select(GithubSearch).where(GithubSearch.user_id == user))

            if not record or index >= len(record.results):
                return None

            return await cls.get_repo(record.results[index])
