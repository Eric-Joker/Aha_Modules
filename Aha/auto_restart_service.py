from core.api import API
from core.i18n import _
from core.dispatcher import on_meta
from models.api import MetaEvent


@on_meta("heartbeat")
async def auto_restart(event: MetaEvent):
    if event.status and not event.status.online:
        await API.restart_server()
