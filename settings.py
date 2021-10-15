from pydantic import BaseSettings


class Settings(BaseSettings):
    appname: str = "Oxygen"
    version: str = 'v0.0.1'
