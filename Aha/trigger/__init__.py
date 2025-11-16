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

from re import Match

from core.api import API
from core.expr import PM
from core.i18n import _
from utils.api import at_or_str
from core.router import on_message, process_message
from models.api import Message
from models.msg import At


@on_message(_("trigger") % at_or_str(), PM.super == True)
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

    await process_message(event, True)
