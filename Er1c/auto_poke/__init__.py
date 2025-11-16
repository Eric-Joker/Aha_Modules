from models.api import Notice

from core.router import on_notice
from core.api import API


@on_notice("notify", "poke")
async def poke(event: Notice):
    if event.target_id == event.self_id:
        await API.poke()
