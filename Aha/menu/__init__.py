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

from core.config import cfg
from core.expr import PM, And, Or, evaluate
from core.i18n import _
from core.router import help_items, on_message
from models.api import Message


@on_message(Or(PM.message == _("help"), And(_("help_with_prefix"), PM.prefix == True)))
async def help(event: Message, localizer: Callable[[str], str]):
    available_commands = {}
    for command, expr, desc in help_items:
        if await evaluate(event, expr):
            available_commands[command] = desc
    commands = [
        localizer("menu.line_with_desc") % (cmd, desc) if isinstance(desc, str) else localizer("menu.line") % cmd
        for cmd, desc in available_commands.items()
    ]
    commands.sort(key=lambda x: (-len(x), x))
    await event.reply(localizer("menu.join").join((localizer("menu.head"), *commands, localizer("menu.tail") % cfg.get_msg_prefix())))
