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

from core.api import API
from core.config import cfg
from core.expr import PM, And, Or
from core.router import on_message
from models.api import Message
from utils.api import get_card_by_event
from utils.typekit import sec2str, str2sec

if ENABLE_POINT := cfg.point_feat:
    from services.point import adjust_point, inquiry_point

    PRICE = Decimal(cfg.get_config("price", "5", "每从一个群解禁消耗的点数。"))


@on_message(Or(And(r"(?:禁言我|jy)\s*(\S+)", PM.prefix == True), r"(?:禁言我|jy)\s*(\S+)\s+(\S+)", r"随机禁言|sjjy"))
async def shutup(event: Message, match: Match):
    num1 = str2sec(match[1]) if match.lastindex else 1
    num2 = str2sec(match[2]) if match.lastindex == 2 else num1 if match.lastindex else 60
    if not num1 or not num2:
        return await event.reply("无法识别为时间段")

    num1 = max(min(num1, 2591940), 1)
    num2 = max(min(num2, 2591940), 1)
    await event.ban(seconds := randint(min(num1, num2), max(num1, num2)) if num2 else num1)
    await event.reply(f"禁言 {await get_card_by_event(event)} {sec2str(seconds)}")


@on_message(PM.message == "禁言", PM.prefix == True, register_help={"禁言": "Shut up!"})
async def su(event: Message):
    await event.reply(
        f"闭嘴！：\n🔥[随机禁言/sjjy]🔥 - 1~60s\n[禁言我/jy 时长 时长] - 随机禁言\n[{cfg.message_prefix}禁言我/{cfg.message_prefix}jy 时长]\n\n最小1s，最大29天23时59秒，自动校正\n作死后可以加其他分群发送“解除禁言”"
    )


@on_message(PM.message == "解除禁言")
async def speak(event: Message):
    times = 0
    for g in cfg.get_group_whitelist():
        if g.platform == event.platform:
            if ENABLE_POINT:
                if await inquiry_point() < PRICE and times == 0:
                    return await event.reply(f"能量不足{PRICE}点")
                if await API.set_group_ban(g.group_id, event.user_id):
                    await adjust_point(-PRICE)
                    times += 1
            elif await API.set_group_ban(g.group_id, event.user_id):
                times += 1
    await event.reply(f"消耗{times * PRICE}能量，解除{times}个群的禁言")
