from collections.abc import Callable
from datetime import datetime, timedelta
from re import Match

from apscheduler.triggers.date import DateTrigger

from core.api import API
from core.config import cfg
from core.expr import PM
from core.i18n import _
from core.dispatcher import on_message, process_message
from models.api import Message
from services.apscheduler import sched
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
    points = len(await sched.get_persist_schedules(metadata=metadata)) + 1
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

    await sched.add_persist_schedule(process_message, DateTrigger(date), args=(event, True), metadata=metadata)
    await event.reply(
        localizer("appointment.success")
        % {"point": points, "time": date.strftime("%Y年%m月%d日 %H:%M:%S"), "command": match_[3]}
    )


@on_message(_("appointment.cancel"))
async def cannel_trigger(event: Message, localizer: Callable[[str], str]):
    count = await sched.rm_persist_schedules_by_meta({"user_id": await event.user_aha_id(), "tag": "trigger"})
    if ENABLE_POINT:
        await adjust_point(point := count * (count + 1) / 4)
        await event.reply(localizer("appointment.cancel.success") % (count, decimal_to_str(point)))
    else:
        await event.reply(localizer("appointment.cancel.success.admin") % count)
