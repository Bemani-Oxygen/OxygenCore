import asyncio
import os
import yaml
import multiprocessing

import core

from typing import Any, Dict
from uvicorn import Server, Config
from core.data.data import Data
from core import root_exe

DEBUG = False
core.DEBUG = DEBUG

config: Dict[str, Any] = {}


class MyServer(Server):
    async def run(self, sockets=None):
        self.config.setup_event_loop()
        return await self.serve(sockets=sockets)


def load_config(filename: str) -> None:
    config.update(yaml.safe_load(open(filename)))
    config['database']['engine'] = Data.create_engine(config)
    config['appname'] = 'Oxygen'

async def run() -> None:
    global config
    global DEBUG

    multiprocessing.freeze_support()
    apps = []

    for server in ['backend', 'frontend']:
        server = MyServer(config=Config("core.%s:app" % server,
                                        host=config['server']['host'],
                                        port=config["server"]["%s_port" % server],
                                        debug=DEBUG,
                                        ))
        apps.append(server.run())

    return await asyncio.gather(*apps)


if __name__ == '__main__':
    load_config(os.path.join(root_exe, "config.yaml"))
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
