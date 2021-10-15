import yaml
import copy
import traceback
import os
import importlib

from typing import Any, Dict
from fastapi import FastAPI, Response, Request
from fastapi.logger import logger
from starlette.responses import RedirectResponse

import core
from .data.data import Data
from .protocol import EAmuseProtocol
from .dispatch import Dispatch
from . import root_exe
from settings import Settings

app = FastAPI()
config: Dict[str, Any] = {}


@app.get('/')
@app.get('/{path:path}')
async def receive_healthcheck(path: str, request: Request) -> Response:
    global config

    frontend_port = config['server'].get('frontend_port')
    if frontend_port is None:
        return Response("Please set frontend port in config.")
    else:
        # Redirect to the frontend location.
        return RedirectResponse(url='localhost:%d' % frontend_port, status_code=308)  # type: ignore


@app.post('/')
@app.post('/{path:path}')
async def receive_request(path: str, request: Request) -> Response:
    global config

    proto = EAmuseProtocol()
    remote_address = request.headers.get('x-remote-address', None)
    compression = request.headers.get('x-compress', None)
    encryption = request.headers.get('x-eamuse-info', None)
    data = await request.body()
    req = proto.decode(
        compression,
        encryption,
        data,
    )

    if req is None:
        # Nothing to do here
        return Response("Unrecognized packet!", 500)
    if req.name in {'soapenv:Envelope', 'soap:Envelope', 'methodCall'}:
        # We get lots of spam from random bots trying to SOAP
        # us up, so ignore this shit.
        return Response("Unrecognized packet!", 500)

    # Create and format config
    requestconfig = copy.copy(config)
    requestconfig['client'] = {
        'address': remote_address or request.client.host,
    }

    dataprovider = Data(requestconfig)
    try:
        dispatch = Dispatch(requestconfig, dataprovider, core.DEBUG)
        resp = await dispatch.handle(req)

        if resp is None:
            # Nothing to do here
            await dataprovider.local.network.put_event(
                'unhandled_packet',
                {
                    'request': str(req),
                },
            )
            return Response("No response generated", 404)

        compression = None

        data = proto.encode(
            compression,
            encryption,
            resp,
        )

        response = Response(data)

        # Some old clients are case-sensitive, even though http spec says these
        # shouldn't matter, so capitalize correctly.
        if compression:
            response.headers['X-Compress'] = compression
        else:
            response.headers['X-Compress'] = 'none'
        if encryption:
            response.headers['X-Eamuse-Info'] = encryption

        return response
    except Exception:
        stack = traceback.format_exc()
        await dataprovider.local.network.put_event(
            'exception',
            {
                'service': 'xrpc',
                'request': str(req),
                'traceback': stack,
            },
        )
        return Response("Crash when handling packet!", 500)
    finally:
        await dataprovider.close()


def load_config(filename: str) -> None:
    global config

    config.update(yaml.safe_load(open(filename)))
    config['database']['engine'] = Data.create_engine(config)
    config['settings'] = Settings()

def register_plugins(plugins_root: str) -> None:
    plugins_list = os.listdir('plugins')

    for plugin in plugins_list:
        plugin_root = os.path.join(plugins_root, plugin)
        if os.path.isdir(plugin_root):
            game_factory_filepath = os.path.join(plugin_root, "factory.py")
            if os.path.exists(game_factory_filepath):
                factory = importlib.import_module("plugins.%s.factory" % plugin)
                logger.info('Plugin:%s factory found.' % plugin)

                IIDXFactory = getattr(factory, "IIDXFactory")()
                IIDXFactory.register_all()
                logger.info('Plugin:%s factory loaded.' % plugin)


async def create_database() -> None:
    global config

    if not os.path.exists(os.path.join(root_exe, config['database']['filename'])):
        _config = copy.copy(config)
        dataprovider = Data(_config)
        await dataprovider.create()


@app.on_event("startup")
async def startup_event():
    load_config(os.path.join(root_exe, "config.yaml"))
    register_plugins(os.path.join(root_exe, "plugins"))
    await create_database()
