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
from collections.abc import Callable
from datetime import datetime, timedelta
from re import Match

from apscheduler.triggers.date import DateTrigger

from core.api import API
from core.config import cfg
from core.expr import PM
from core.i18n import _
from core.router import on_message, process_message
from models.api import Message
from services.apscheduler import scheduler
from utils.typekit import decimal_to_str
from utils.unit import chs2sec

if ENABLE_POINT := cfg.point_feat:
    from services.point import adjust_point, inquiry_point


@on_message(_("appointment"), PM.prefix == True, register_help={_("appointment"): _("appointment.desc")})
async def aps_trigger_main(event: Message, localizer):
    await event.reply(localizer("appointment.help"))


@on_message(_("appointment.command"))
async def aps_trigger(event: Message, match_: Match, localizer: Callable[[str], str]):
    if (sec := chs2sec(match_[2])) is None:
        return await event.reply(localizer("appointment.identification_failed"))

    metadata = {"user_id": (aha_id := await event.user_aha_id()), "tag": "trigger"}
    points = len(await scheduler.get_persist_schedules(metadata=metadata)) + 1
    if ENABLE_POINT and not await API.is_admin(event.group_id, event.user_id):
        if (user_point := await inquiry_point(aha_id)) < points:
            return await event.reply(localizer("appointment.insufficient_funds") % (points, decimal_to_str(user_point)))
        else:
            await adjust_point(aha_id, -1)

    if processed := (seg := event.message[0]).text.removeprefix(match_[1].partition("[Aha")[0]).strip():
        seg.text = processed
    else:
        del event.message[0]
    date = datetime.now() + timedelta(seconds=sec)

    await scheduler.add_persist_schedule(process_message, DateTrigger(date), args=(event, True), metadata=metadata)
    await event.reply(
        localizer("appointment.success")
        % {"point": points, "time": date.strftime("%Y年%m月%d日 %H:%M:%S"), "command": match_[3]}
    )


@on_message(_("appointment.cancel"))
async def cannel_trigger(event: Message, localizer: Callable[[str], str]):
    count = await scheduler.rm_persist_schedules_by_meta({"user_id": event.user_id, "tag": "trigger"})
    if ENABLE_POINT:
        await adjust_point(point := count * (count + 1) / 4)
        await event.reply(localizer("appointment.cancel.success") % (count, decimal_to_str(point)))
    else:
        await event.reply(localizer("appointment.cancel.success.admin") % count)
