from asyncio import create_task, gather
from bisect import bisect_left
from collections.abc import Callable
from datetime import datetime, timedelta
from logging import getLogger
from types import CoroutineType
from typing import TYPE_CHECKING, overload
from weakref import WeakSet

from core.config import cfg
from sqlalchemy import select

from core.api import API, SS, select_bot
from core.api_service import friend_conv_lock
from core.database import db_sessionmaker
from core.dispatcher import on_message, on_start, process_message
from core.i18n import _
from models.api import Message
from utils.sqlalchemy import upsert

from .database import Status

COUNT = cfg.register("size", 1024, _("config_comment.count"))
LIMIT = cfg.register("seconds", 86400, _("config_comment.seconds"))

_callbacks = WeakSet()
_logger = getLogger()


if TYPE_CHECKING:

    @overload
    def reg_backfill[T: Callable[..., CoroutineType]](func: T) -> T: ...
    @overload
    def reg_backfill[T: Callable[..., CoroutineType]]() -> Callable[[T], T]: ...


def reg_backfill(func=None):
    global _callbacks
    if func is None:
        return reg_backfill
    if meta := getattr(func, "aha_meta", None):
        _callbacks |= meta
    else:
        _logger.warning(_("not_available_callback"), stack_info=True)


@on_message()
async def record(event: Message):
    async with db_sessionmaker() as session:
        await session.execute(
            upsert(
                Status,
                platform=event.platform,
                user_id="" if event.group_id else event.user_id,
                group_id=event.group_id or "",
                message=event.message_id,
            )
        )
        await session.commit()


if cfg.cache_conv:
    from core.api_service import friends

    def del_unnecessary(events: list[Message], target_time, self_id):
        if idx := bisect_left(events, target_time, key=lambda e: e.time):
            del events[:idx]
        else:
            del events[0]
        for i in range(len(events) - 1, -1, -1):
            if events[i].user_id == self_id:
                del events[i]

    async def process_friend(row: Status, bot, target_time):
        events = await API.get_private_msg_history(row.user_id, row.message, COUNT, bot=bot)
        del_unnecessary(events, target_time, (await API.get_login_info(bot=bot)).user_id)
        if events:
            for e in events:
                for c in _callbacks:
                    create_task(process_message(e, once=c))
            await record(events[-1])

    async def process_row(row: Status, target_time):
        if row.group_id:
            bot = await select_bot(SS.GROUP, platform=row.platform, conv_id=row.group_id)
            events = await API.get_group_msg_history(row.group_id, row.message, COUNT, bot=bot)
            del_unnecessary(events, target_time, (await API.get_login_info(bot=bot)).user_id)
            if events:
                for e in events:
                    for c in _callbacks:
                        create_task(process_message(e, once=c))
                await record(events[-1])
        else:
            async with friend_conv_lock:
                await gather(*[process_friend(row, bot, target_time) for bot in friends[row.platform][row.user_id]])

    @on_start
    async def __():
        target_time = datetime.now().astimezone() - timedelta(seconds=LIMIT)
        async with db_sessionmaker() as session:
            await gather(*[process_row(row, target_time) for row in (await session.scalars(select(Status))).all()])

else:
    _logger.warning(_("unavailable"))
