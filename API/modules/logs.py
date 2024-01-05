"""
MODULE
    logs.py

DESCRIPTION
    Allows to easily log information to further debugging.

    All logs are saved to file and printed to console.
    You can disable printing by setting no_verbose to True.

    Log format:
        [dd/mm/yyyy h:m:s] (author) [filename.function#line]  message
        [31/12/2023 11:59:58] (e.g user_id) [logs.py.log#21]  This is the message.

        In console, (logger_name) will be put at front of the log.

        If log function was not called from any function, @ will be used instead of name.
"""
from modules.paths import Path

from fastapi import Request 
from datetime import datetime
import inspect
import os

no_verbose = False


def get_time():
    """ Get current time and format it into: 31/12/2000 18:30:20 """
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


class Logger:
    """ Provides configurable logging abilities. """
    logs_path = Path("./")
    
    def __init__(self, name: str, stack_depth: int = 2) -> None:
        self.name = name
        self.log_path = Logger.logs_path / name + ".log"
        self.stack_depth = stack_depth

        self.log_path.touch()

    def __get_caller_info(self):
        """ Get information about place in code where log method was called. """
        caller_frame = inspect.stack()[self.stack_depth]
        filename = os.path.basename(caller_frame.filename)
        function = caller_frame.function
        lineno = caller_frame.lineno
        if function == "<module>":
            function = "@"

        return f"{filename}.{function}#{lineno}"
    
    def log(self, author: str, content: str) -> None:
        """ Save log to file and write to console if no_verbose is False. """
        if isinstance(author, Request):
            author = f"{author.client.host}:{author.client.port}"

        content = f"[{get_time()}] ({author}) [{self.__get_caller_info()}]  {content}"

        if not no_verbose:
            print(f"({self.name}) {content}")

        self.log_path.write(content+"\n")


Logger.logs_path = Path("./data/logs/")
access_logger = Logger("access", 3)
rooms_logger = Logger("room")
websocket_logger = Logger("ws")
sessions_logger = Logger("session")
users_logger = Logger("user")
database_logger = Logger("db")
dms_logger = Logger("dms")
