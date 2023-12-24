"""
MODULE
    logs.py

DESCRIPTION
    Allows to easily log information to further debugging.

CODE SUMMARY
    All logs are saved to file and printed to console.
    You can disable printing by setting no_verbose to True.

  SysLogger:
      Logs system messages from all modules.
  
      All log levels have their corresponding methods:
          - error(message: str)
          - warn(message: str)
          - info(message: str)
          - success(message: str)
  
      Log format:
          [dd/mm/yyyy h:m:s] <level> [filename.function#line] -> message
          [31/12/2023 11:59:58] <ERROR> [logs.py.log#21] -> This is the message.
  
          If log function was not called from any function,
          <module> will be used instead of name.
  
  AccessLogger:
      Logs API's endpoints requests.
  
      There is only one log method:
          - log(request: fastapi.Request, status_code: str, message: str)
  
      Log format:
          [dd/mm/yyyy h:m:s] host:port [function] (status code) message
          [31/12/2023 11:59:58] 192.168.0.1:8008 [get_home] (True) This is the message.

  RoomsLogger:
      Logs events in rooms.

      Like in AccessLogger, there is only one log method:
          - log(room_key: str, message: str)

      Log format:
          [dd/mm/yyyy h:m:s] room_id [function] message
          [31/12/2023 11:59:58] e023f7e4e5514a6e9967b936d7147fb3 [add_member] This is the message.

  WsLogger:
      Logs events from Websocket connection.

      There is only one log method:
          - log(room_key: str, message: str)

      Log format:
          [dd/mm/yyyy h:m:s] (room:ROOM_KEY) [function] message
          [31/12/2023 11:59:58] (room:b444ac06613fc8d63795be9ad0beaf55011936ac) [feed] This is the message.    

  SessionLogger:
      Logs changes in sessions system.
  
      There is only one log method:
          - log(session_key: str, message: str)
  
      Log format:
          [dd/mm/yyyy h:m:s] (userkey:SESSION_KEY) [function] message
          [31/12/2023 11:59:58] (userkey:) [feed] This is the message.
"""
from fastapi import Request 
from datetime import datetime
import inspect
import os

SYSLOGS_FILE_PATH = "./logs/sys.log"
ACCESSLOGS_FILE_PATH = "./logs/access.log"
ROOMSLOGS_FILE_PATH = "./logs/rooms.log"
WSLOGS_FILE_PATH = "./logs/ws.log"
SESSIONLOGS_FILE_PATH = "./logs/sessions.log"

no_verbose = False


def get_time():
    """ Get current time and format it into: 31/12/2000 18:30:20 """
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


class SysLogger:
    """ System logs handler. """

    @staticmethod
    def _grab_caller_info():
        """ Grab data about place in code where log method was called. """
        caller_frame = inspect.stack()[3]
        filename = os.path.basename(caller_frame.filename)
        function = caller_frame.function
        lineno = caller_frame.lineno
        if function == "<module>":
            function = "@"

        return f"{filename}.{function}#{lineno}"

    @staticmethod
    def _log(level: str, message: str):
        """ Save log and write to console if no_verbose is False. """
        caller_info = SysLogger._grab_caller_info()
        content = f"[{get_time()}] <{level}> [{caller_info}] -> {message}"
        if not no_verbose:
            print(f"(sys) {content}")
        with open(SYSLOGS_FILE_PATH, "a") as file:
            file.write(content+"\n")

    @staticmethod
    def error(message: str):
        SysLogger._log("ERROR", message)

    @staticmethod
    def warn(message: str):
        SysLogger._log("WARN", message)

    @staticmethod
    def info(message: str):
        SysLogger._log("info", message)

    @staticmethod
    def success(message: str):
        SysLogger._log("success", message)


class AccessLogger:
    """ API endpoints requests logger. """

    @staticmethod
    def _grab_caller_info():
        """ Get name of function that called log() method. """
        caller_frame = inspect.stack()[3]
        return caller_frame.function

    @staticmethod
    def log(request: Request, status_code: str, message: str):
        """ Save log to file and write to console if no_verbose is False. """
        content = f"[{get_time()}] {request.client.host}:{request.client.port} [{AccessLogger._grab_caller_info()}] ({status_code}) {message}"
        if not no_verbose:
            print(f"(access) {content}")
        with open(ACCESSLOGS_FILE_PATH, "a") as file:
            file.write(content+"\n")


class RoomsLogger:
    """ Rooms events logger. """

    @staticmethod
    def _grab_caller_info():
        """ Get name of function that called log() method. """
        caller_frame = inspect.stack()[2]
        return caller_frame.function

    @staticmethod
    def log(room_key: str, message: str):
        """ Save log to file and write to console if no_verbose is False. """
        content = f"[{get_time()}] {room_key} [{AccessLogger._grab_caller_info()}] {message}"
        if not no_verbose:
            print(f"(room) {content}")
        with open(ROOMSLOGS_FILE_PATH, "a") as file:
            file.write(content+"\n")


class WsLogger:
    """ Logs information from Websocket connections. """

    @staticmethod
    def _grab_caller_info():
        """ Get name of function that called log() method. """
        caller_frame = inspect.stack()[2]
        return caller_frame.function
    
    @staticmethod
    def log(room_key: str, message: str):
        """ Save log to file and write to console if no_verbose is False. """
        content = f"[{get_time()}] (room:{room_key}) [{WsLogger._grab_caller_info()}] {message}"
        if not no_verbose:
            print(f"(ws) {content}")
        with open(WSLOGS_FILE_PATH, "a") as file:
            file.write(content+"\n")


class SessionLogger:
    """ Logs information about sessions' events. """

    @staticmethod
    def _grab_caller_info():
        """ Get name of function that called log() method. """
        caller_frame = inspect.stack()[2]
        return caller_frame.function
    
    @staticmethod
    def log(session_key: str, message: str):
        """ Save log to file and write to console if no_verbose is False. """
        content = f"[{get_time()}] (userkey:{session_key}) [{SessionLogger._grab_caller_info()}] {message}"
        if not no_verbose:
            print(f"(sessions) {content}")
        with open(SESSIONLOGS_FILE_PATH, "a") as file:
            file.write(content+"\n")
