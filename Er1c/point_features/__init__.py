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

from decimal import Decimal
from random import randint
from re import Match

from sqlalchemy import and_, func, or_, select

from core.api import API
from core.config import cfg
from core.database import db_session_factory
from core.expr import PM, And, Or
from core.identity import user2aha_id
from core.router import on_message
from models.api import Message
from services.point import Point, adjust_point, inquiry_point
from utils.api import at_or_str, get_card_by_event
from utils.misc import round_decimal
from utils.sqlalchemy import upsert
from utils.typekit import decimal_to_str

from .qd import detail, sign

HANDLING_FEE_RATIO = Decimal(cfg.register("handling_fee", "0.01", "转账手续费"))


@on_message(Or(r"q+d+|早|签到", And("sign", (PM.prefix == True))))
async def dk(event: Message):
    await event.send(await sign(await event.user_aha_id(), await get_card_by_event(event)))


@on_message(r"签到(详情|明细)", register_help={"签到详情": "查询上次签到明细"})
async def dt(event: Message):
    await event.reply(await detail(await event.user_aha_id()))


@on_message("(能量|积分|货币)系统", PM.prefix == True, register_help={"能量系统": None})
async def point_system(event: Message):
    await event.reply(
        f"能量系统：\n[{cfg.get_msg_prefix()}能量守恒] - 查询全体用户能量总量\n[{cfg.get_msg_prefix()}(能量)查询] - 查询个人能量数量\n[(能量)转账 @或uid 数量]"
    )


@on_message(PM.message == "能量守恒", PM.prefix == True)
async def conservation_handler(event: Message):
    async with db_session_factory() as session:
        result = await session.execute(
            select(func.sum(Point.points)).where(
                ~or_(*[and_(Point.user_id == await user2aha_id(item.platform, item.user_id, session=session)) for item in cfg.super])
            )
        )
    await event.reply(f"📊 当前时空总能量：{decimal_to_str(round_decimal(result.scalar())) or 0}点（守恒率99.{randint(80,99)}%）")


@on_message(Or(r"(?:能量|积分)(?:查询)?", r"查询") & (PM.prefix == True))
async def query_points(event: Message):
    await event.reply(f"🔋当前能量储备：{decimal_to_str(round_decimal(await inquiry_point()))} 点")


@on_message(rf"(?:能量|积分)?转(?:移|账)\s*{at_or_str()}\s+(\d+(?:\.\d+)?)")
async def transfer_handler(event: Message, match_: Match):
    if await inquiry_point() <= HANDLING_FEE_RATIO:
        return await event.reply("⚠️ 能量不足以转出")
    if (receiver_id := match_[1]) not in {i.user_id for i in (await API.get_group_member_list(event.group_id))}:
        return await event.reply("⚠️ 目标用户不是本群成员")

    points = Decimal(match_[2])

    # 手续费
    tax = max(HANDLING_FEE_RATIO, round_decimal(HANDLING_FEE_RATIO * points, abs(HANDLING_FEE_RATIO.as_tuple().exponent)))
    actual_points = points - tax

    # 执行转移
    await adjust_point(-points)
    await adjust_point(event.platform, receiver_id, actual_points)

    if receiver_id == event.self_id:
        return await event.reply(f"⚫已将 {match_[2]} 点能量投入黑洞！")
    await event.reply(
        f"⚡能量转移成功！\n- 转出：{match_[2]}点\n- 手续费：{decimal_to_str(tax)}点\n- 实际到账：{decimal_to_str(actual_points)}点"
    )


@on_message(rf"(?:能量|积分)?调整\s*{at_or_str()}\s+(\d+\.?\d*)", PM.super == True)
async def adjust_points(event: Message, match_: Match):
    await adjust_point(event.platform, user_id := match_[1], Decimal(point := match_[2]))
    await event.reply(f"已为 {await API.get_card_by_search(user_id, event.group_id)} 添加 {point} 点")


@on_message(rf"(?:能量|积分)?设置\s*{at_or_str()}\s+(\d+\.?\d*)", PM.super == True)
async def set_points(event: Message, match_: Match):
    points = match_[2]
    user_id = match_[1]
    async with db_session_factory() as session:
        await session.execute(upsert(Point, user_id=await user2aha_id(user_id), points=Decimal(points)))
        await session.commit()

    await event.reply(f"已将 {await API.get_card_by_search(user_id, event.group_id)} 的积分设置为 {match_[2]} 点")
