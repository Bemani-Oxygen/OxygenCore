import os
from typing import Dict, Any
from asyncio import current_task

from sqlalchemy.ext.asyncio import create_async_engine  # type: ignore
from sqlalchemy.ext.asyncio import async_scoped_session  # type: ignore
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine  # type: ignore
from sqlalchemy.sql import text  # type: ignore
from sqlalchemy.exc import ProgrammingError  # type: ignore

import core
from .sqlite.base import metadata
from .sqlite.user import UserData
from .sqlite.music import MusicData
from .sqlite.machine import MachineData
from .sqlite.game import GameData
from .sqlite.network import NetworkData

from core import root_exe

class DBCreateException(Exception):
    pass


class LocalProvider:
    """
    A wrapper object for implementing local data operations only. Right
    now this goes to the MySQL classes and talks to the backend DB.
    """

    def __init__(
            self,
            user: UserData,
            music: MusicData,
            machine: MachineData,
            game: GameData,
            network: NetworkData,
    ) -> None:
        self.user = user
        self.music = music
        self.machine = machine
        self.game = game
        self.network = network


class Data:
    """
    An object that is meant to be used as a singleton, in order to hold
    DB configuration info and provide a set of functions for querying
    and storing data.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initializes the data object.

        Parameters:
            config - A config structure with a 'database' section which is used
                     to initialize an internal DB connection.
        """
        async_session_factory = sessionmaker(
            bind=config['database']['engine'],
            autoflush=True,
            # autocommit=True,
            class_=AsyncSession
        )
        self.__config = config
        self.__session = async_scoped_session(async_session_factory, scopefunc=current_task)
        self.__url = Data.sqlalchemy_url(config)
        self.__user = UserData(config, self.__session)
        self.__music = MusicData(config, self.__session)
        self.__machine = MachineData(config, self.__session)
        self.__game = GameData(config, self.__session)
        self.__network = NetworkData(config, self.__session)
        self.local = LocalProvider(
            self.__user,
            self.__music,
            self.__machine,
            self.__game,
            self.__network
        )

    @classmethod
    def sqlalchemy_url(cls, config: Dict[str, Any]) -> str:
        return f"sqlite+aiosqlite:///{os.path.join(root_exe, config['database']['filename'])}"

    @classmethod
    def create_engine(cls, config: Dict[str, Any]) -> Engine:
        return create_async_engine(
            Data.sqlalchemy_url(config),
            pool_recycle=3600,
            echo=core.DEBUG
        )

    async def create(self) -> None:
        """
        Create any tables that need to be created.
        """
        async with self.__config["database"]["engine"].begin() as conn:
            await conn.run_sync(metadata.create_all, checkfirst=True)

    async def close(self) -> None:
        """
        Close any open data connection.
        """
        # Make sure we don't leak connections between web requests
        if self.__session is not None:
            await self.__session.close()
            self.__session = None
