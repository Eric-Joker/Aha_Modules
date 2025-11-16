from collections.abc import Callable

from core.config import cfg
from core.expr import PM, And, Or, evaluate
from core.i18n import _
from core.router import menu_commands, on_message
from models.api import Message


@on_message(Or(PM.message == _("help"), And(_("help_with_prefix"), PM.prefix == True)))
async def help(event: Message, localizer: Callable[[str], str]):
    available_commands = {}
    for command, expr, desc in menu_commands:
        if await evaluate(event, expr):
            available_commands[command] = desc
    commands = [
        localizer("menu.line_with_desc") % (cmd, desc) if isinstance(desc, str) else localizer("menu.line") % cmd
        for cmd, desc in available_commands.items()
    ]
    commands.sort(key=lambda x: (-len(x), x))
    await event.reply(localizer("menu.join").join((localizer("menu.head"), *commands, localizer("menu.tail") % cfg.message_prefix)))
