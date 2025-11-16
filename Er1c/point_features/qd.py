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

import random
from datetime import datetime, timedelta
from enum import Enum

from sqlalchemy import insert

from core.config import cfg
from core.database import db_session_factory
from services.point import adjust_point, inquiry_point
from utils.misc import round_decimal
from utils.typekit import decimal_to_str

from .database import UserSign

POINT_ITEMS = ((1, 18), (2, 28), (3, 35), (4, 12), (5, 5), (6, 2), (10, 1))  # (点数, 权重)
RANDOM_EVENTS = (
    {
        "text": ("发现能量晶簇！", "量子泡沫共振效应！", "捕获游离光子！", "时空折叠增益！", "检测到宇宙微波背景辐射异常！"),
        "points": 1,
    },
    {"text": ("遭遇时空湍流！", "反物质侵蚀！", "维度塌缩损耗！", "观测者效应干扰！", "遭遇熵增不可逆过程！"), "points": -1},
)
EVENT_PROB = cfg.register("event_prob", 0.05, "随机事件总触发概率。")
STREAK_BONUS_CYCLE = cfg.register("streak_cycle", 7, "连续签到周期。")
STREAK_BONUS_STAGES = cfg.register("streak_stages", 6, "固定周期次数。")
STREAK_BONUS_MAX = cfg.register("streak_max", 3, "固定周期奖励上限。")
STREAK_BONUS_RANGE = cfg.register("streak_range", (5, 10), "随机周期范围。")
STREAK_BONUS_PONITS = cfg.register("streak_points", (1, 15), "随机周期奖励范围。")


# 随机算法
def weighted_choice(items):
    rand = random.uniform(0, sum(w for _, w in items))
    cumulative = 0
    for value, weight in items:
        cumulative += weight
        if rand < cumulative:
            return value
    return items[-1][0]


class BonusType(Enum):
    NONE = 0
    FIXED = 1
    RANDOM = 2


# 连续签到奖励算法
def calculate_streak_bonus(user: UserSign, now: datetime):
    user.continuous_days = (
        user.continuous_days + 1 if user.last_sign and (now.date() - user.last_sign.date()) == timedelta(days=1) else 1
    )
    if user.streak_stage < STREAK_BONUS_STAGES:
        if user.continuous_days >= STREAK_BONUS_CYCLE * (user.streak_stage + 1):
            user.streak_stage += 1
            user.last_bonus_date = now
            return min(STREAK_BONUS_MAX, user.streak_stage), BonusType.FIXED
    elif (now - user.last_bonus_date).days >= random.randint(*STREAK_BONUS_RANGE):
        user.last_bonus_date = now
        return random.randint(*STREAK_BONUS_PONITS), BonusType.RANDOM
    return 0, BonusType.NONE


async def sign(user_id, nickname):
    now: datetime = datetime.now()
    async with db_session_factory() as session:
        if not (user := await session.get(UserSign, user_id)):
            result = await session.execute(
                insert(UserSign).values(user_id=user_id, last_sign=None, last_bonus_date=None).returning(UserSign)
            )
            user = result.scalar_one()

        # 冷却检查
        if user.last_sign and user.last_sign >= (today_0am := now.replace(hour=0, minute=0, second=0, microsecond=0)):
            remaining_seconds = (today_0am + timedelta(days=1) - now).total_seconds()
            hours = int(remaining_seconds // 3600)
            minutes = int((remaining_seconds % 3600) // 60)
            return f"⏳ 时空稳定协议生效中（剩余{hours}小时{minutes}分钟）"

        # 基础积分
        points = base_points = weighted_choice(POINT_ITEMS)

        # 连续签到
        bonus_points, bonus_type = calculate_streak_bonus(user, now)
        points += bonus_points

        # 随机事件
        event_points = 0
        event_text = ""
        if random.random() < EVENT_PROB:
            event_text = random.choice((event_type := random.choice(RANDOM_EVENTS))["text"])
            points += (event_points := event_type["points"])

        user.last_sign = now
        user.last_base_points = base_points
        user.last_bonus_points = bonus_points
        user.last_bonus_type = bonus_type.value
        user.last_event_points = event_points
        user.last_event_text = event_text

        await session.commit()

    return f"{nickname} 签到成功，当前持有 {decimal_to_str(round_decimal(await inquiry_point(user_id)))}+{await adjust_point(user_id, points)} 点。"


async def detail(user_id):
    async with db_session_factory() as session:
        if not (user := await session.get(UserSign, user_id)) or not user.last_sign:
            return "暂无签到记录"

        response = [f"📅 签到时间：{user.last_sign.strftime('%Y-%m-%d %H:%M:%S')}", f"- 获得能量：{user.last_base_points}点"]

        # 连续签到
        if user.last_bonus_points > 0:
            if user.last_bonus_type == BonusType.FIXED.value:
                response.append(f"- 🌟 连续观测奖励 +{user.last_bonus_points}点")
            elif user.last_bonus_type == BonusType.RANDOM.value:
                response.append(f"- 💥 观测暴击！+{user.last_bonus_points}点随机能量波动")

        # 随机事件
        if user.last_event_text:
            sign = "+" if user.last_event_points > 0 else ""
            response.append(f"- ⚡ {user.last_event_text} 能量{sign}{user.last_event_points}点")

        # 连续天数
        response.append(f"- 连续观测：{user.continuous_days}天")

        # 总点数
        total = user.last_base_points + user.last_bonus_points + user.last_event_points
        if total != user.last_base_points:  # 有额外点数
            response.append(f"- 累计总量：{total}点")

        return "\n".join(response)
