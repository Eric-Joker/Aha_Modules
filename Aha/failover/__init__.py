import os
from asyncio import create_task, sleep, wait_for
from collections import defaultdict, deque
from contextlib import suppress
from enum import Enum, auto
from logging import getLogger

from apscheduler.triggers.cron import CronTrigger

from core.api import API
from core.api_service import bots, call_api, start_bot
from core.config import cfg
from core.dispatcher import on_meta, on_start
from core.expr import Field, FieldClause
from core.i18n import _
from models.api import MetaEvent
from services.apscheduler import sched
from utils.apscheduler import TimeTrigger

BACKUP_SERVERS = cfg.register(
    "backup_servers",
    {
        0: deque(
            [
                {
                    "NapCat": {
                        "uri": "ws://127.0.0.1:3001",
                        "token": "napcat",
                        "start_server_command": (
                            r"""set "QQ=114514"
wmic process get CommandLine 2>nul | findstr /i /r /c:"QQNT\\QQ\.exe. --enable-logging -q %QQ%" >nul || start "" /d "\path\to\NapCat.Shell" launcher-user.bat %q%"""
                            if os.name == "nt"
                            else r"napcat start 114514"
                        ),
                        "stop_server_command": (
                            r"""for /f "tokens=*" %A in ('wmic process get CommandLine^,ProcessId 2^>nul ^| findstr /i /r /c:"QQNT\\QQ\.exe. --enable-logging -q 114514"') do if not defined TARGET_PID for %B in (%A) do set "TARGET_PID=%B"
if not defined TARGET_PID exit /b
taskkill /F /PID %TARGET_PID% 2>nul"""
                            if os.name == "nt"
                            else r"napcat stop 114514"
                        ),
                        "retry_config": {"wait_incrementing": {"start": 1, "increment": 2, "max": 5}},
                        "lang": "zh_CN",
                        "_failover_cron": "0 4 * * *",
                    }
                },
            ]
        )
    },
    _("config_comment.servers"),
)
STARTUP_TIMEOUT = cfg.register("startup_timeout", 30, _("config_comment.timeout"))


Ponline = FieldClause("online", Field(lambda event: event.status.online if event.status else None, priority=38))

_server_status = defaultdict(lambda: Status.NEED_RESTART)
_start_scheds = {}
_logger = getLogger()


class Status(Enum):
    NEED_RESTART = auto()
    STARTING = auto()


for k, v in BACKUP_SERVERS.items():
    v.appendleft(cfg.bots[k])


@on_start
async def sched_startup():
    for bots in BACKUP_SERVERS.values():
        for bot in bots:
            if cron := next(iter(bot.items()))[1].get("_failover_cron"):
                await sched.add_schedule(_heartbeat, CronTrigger.from_crontab(cron), args=(bot,))


async def _heartbeat(config):
    if all(x[0] is not config for x in BACKUP_SERVERS.values()):
        task = create_task(wait_for(start_bot(config, block_event=True), 30))
        await sleep(30)
        with suppress(Exception):
            await call_api("stop_server", bot=(await task)[0])


@on_meta("lifecycle", "connect")
async def online(event: MetaEvent):
    if sch := _start_scheds.pop(event.bot_id, None):
        _logger.info(_("server_restore") % event.bot_id)
        await sched.remove_schedule(sch)
        _server_status[event.bot_id] = Status.NEED_RESTART


@on_meta(Ponline == False)
async def offline(event: MetaEvent, is_timeout=False):
    match _server_status[event.bot_id]:
        case Status.NEED_RESTART:
            _logger.info(_("auto_restart") % f"{event.adapter}({event.bot_id})")
            _server_status[event.bot_id] = Status.STARTING
            await API.restart_server()
            _start_scheds[event.bot_id] = await sched.add_schedule(offline, TimeTrigger(STARTUP_TIMEOUT), args=(event, True))

        case Status.STARTING:
            if is_timeout:
                _logger.info(_("rotate.start") % f"{event.adapter}({event.bot_id})")
                await call_api("close", bot=event.bot_id)
                (d := BACKUP_SERVERS[bots.index(event.bot_id)]).rotate(-1)
                _start_scheds[event.bot_id] = await sched.add_schedule(
                    offline, TimeTrigger(STARTUP_TIMEOUT), args=(event, True)
                )
                bots[event.bot_id] = (await start_bot(d[0], event.bot_id))[1]
