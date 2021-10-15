# Oxygen Core
This project is based on [bemaniutils](https://github.com/DragonMinded/bemaniutils).

We changed the web engine from flask to fastapi and used aiosqlite for local database. 
We also removed some tables to simplify the database for local service (bemaniutils is used for online service).

This project will only support iidx now and you can easily add other games by yourself.
plugin folder will not be committed now.

# Plugin
To be soon.

# How to use
- run directly by source code
1. Add the plugin folder to root path
2. run 'main.py'
- run exe
1. Add the plugin folder and 'config.yaml' to root path
2. run 'Oxygen.exe'

# How to build
You can use pyinstaller to build this project. Of course, you can run this project directly.

In our 'build.spec' (config file of pyinstaller), upx option is true. In our test, you need to setup your own upx instead of default upx.exe of pyinstaller.
and then you can use this command to build the project.

```
pyinstaller -F .\build.spec --upx-dir (path to upx) --clean --p (venv path)
```


