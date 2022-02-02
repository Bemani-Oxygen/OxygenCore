import yaml
import copy
import traceback
import os
import importlib

from typing import Any, Dict
from fastapi import FastAPI, Response, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.logger import logger

from .data.data import Data
from . import root_temp, root_exe
from settings import Settings

app = FastAPI()
config: Dict[str, Any] = {}

templates = Jinja2Templates(os.path.join(root_temp, "core", "templates"))

menuMap = {}
webuiMap = {}


@app.get('/', response_class=HTMLResponse)
async def main(request: Request) -> Response:
    global menuMap

    return templates.TemplateResponse("base.html",
                                      {"request": request,
                                       'appname': config['settings'].appname,
                                       'version': config['settings'].version,
                                       'menuMap': menuMap,
                                       'url': '/index'})


@app.get('/index', response_class=HTMLResponse)
async def index(request: Request) -> Response:
    return templates.TemplateResponse("index.html",
                                      {"request": request,
                                       "request": request,
                                       'appname': config['settings'].appname,
                                       'version': config['settings'].version,
                                       'host': config['server']['host'],
                                       'backend_port': config['server']['backend_port'],
                                       'frontend_port': config['server']['frontend_port']})


@app.get('/plugin/{plugin}/{method}', response_class=HTMLResponse)
@app.post('/plugin/{plugin}/{method}')
async def plugin_handler(plugin: str, method: str, request: Request) -> Response:
    global webuiMap

    webui = webuiMap[plugin]

    try:
        if request.method == "GET":
            handler = getattr(webui, f'handle_{plugin}_{method}_get')
        elif request.method == "POST":
            handler = getattr(webui, f'handle_{plugin}_{method}_post')
        elif request.method == "PUT":
            handler = getattr(webui, f'handle_{plugin}_{method}_put')
        else:
            handler = None
    except AttributeError:
        handler = None

    if handler is not None:
        # Create and format config
        requestconfig = copy.copy(config)
        requestconfig['client'] = {
            'address': request.client.host,
        }

        dataprovider = Data(requestconfig)
        return await handler(request, dataprovider)

    return Response("No handler found for request.")


@app.get('/{plugin}/{method}', response_class=HTMLResponse)
async def plugin_webui(plugin: str, method: str, request: Request) -> Response:
    global menuMap

    return templates.TemplateResponse("base.html",
                                      {"request": request,
                                       'appname': config['settings'].appname,
                                       'version': config['settings'].version,
                                       'menuMap': menuMap,
                                       'url': '/plugin/%s/%s' % (plugin, method)})


def load_config(filename: str) -> None:
    global config

    config.update(yaml.safe_load(open(filename)))
    config['database']['engine'] = Data.create_engine(config)
    config['settings'] = Settings()


def add_menu(href, title):
    global menuMap

    plugin_name = traceback.extract_stack()[-2][0].split('\\')[-2].upper()

    if plugin_name not in menuMap:
        menuMap[plugin_name] = []

    menuMap[plugin_name].append({
        'href': '/%s/%s' % (plugin_name.lower(), href),
        'title': title
    })


def add_static(directory):
    plugin_name = traceback.extract_stack()[-2][0].split('\\')[-2]
    app.mount("/static/plugin/" + plugin_name, StaticFiles(directory=directory))


def register_plugins(plugins_root: str) -> None:
    global webuiMap

    plugins_list = os.listdir('plugins')

    for plugin in plugins_list:
        plugin_root = os.path.join(plugins_root, plugin)
        if os.path.isdir(plugin_root):
            game_factory_filepath = os.path.join(plugin_root, "webui.py")
            if os.path.exists(game_factory_filepath):
                webui = importlib.import_module("plugins.%s.webui" % plugin)
                logger.info('Plugin:%s webui found.' % plugin)

                try:
                    menu_handler = getattr(webui, 'menu_handler')
                    menu_handler(add_menu)
                except:
                    logger.info('Plugin %s does not have webui menu handler.' % plugin)

                try:
                    static_handler = getattr(webui, 'static_handler')
                    static_handler(add_static)
                except:
                    logger.info('Plugin %s does not have webui static handler.' % plugin)

                webuiMap[plugin] = webui
                logger.info('Plugin:%s webui loaded.' % plugin)


@app.on_event("startup")
async def startup_event():
    load_config(os.path.join(root_exe, "config.yaml"))
    register_plugins(os.path.join(root_exe, "plugins"))
