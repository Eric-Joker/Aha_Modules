from re import Match

from core.api import API
from core.expr import PM
from core.i18n import _
from utils.aha import at_or_str
from core.dispatcher import on_message, process_message
from models.api import Message
from models.msg import At


@on_message(_("trigger") % at_or_str(), PM.super == True, threadable=False)
async def trigger(event: Message, match_: Match):
    event.user_id = user_id = match_[2]

    user_info = await API.get_card_by_search(event.user_id, event.group_id, True)
    event.sender.card, event.sender.nickname = user_info
    if processed := (seg := event.message[0]).text.removeprefix(match_[1].partition("[Aha")[0]).strip():
        seg.text = processed
    else:
        del event.message[0]
    if isinstance(seg := event.message[0], At) and seg.user_id == user_id:
        del event.message[0]
    event.message[0].text = event.message[0].text.lstrip()

    await process_message(event, True)
