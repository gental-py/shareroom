"""
MODULE
    ws.py

DESCRIPTION
    WebSockets managers.
"""
from modules.logs import WsLogger

from fastapi import WebSocket


class NotificationServer:
    """ 
    Clients register to receive live notifications 
      from all of their's active rooms while they are on dashboard.
    Unsent buffer holds rooms that user should be notified about.
      flush_buffer() sends all rooms to user.
      feed_buffer() appends room_code to user's buffer.
    """
    register: dict[str, WebSocket] = {}
    unsent_buffer: dict[str, list[str]] = {}

    @staticmethod
    async def register_client(db_key: str, client: WebSocket) -> None:
        """ Register new client to NS. """
        await client.accept()
        NotificationServer.register[db_key] = client
        WsLogger.log("NS", f"Registered new client: {db_key}")

    @staticmethod
    def remove_client(db_key: str) -> None:
        """ Remove client from room's register. """
        if db_key in NotificationServer.register:
            WsLogger.log("NS", f"Removed client from register: {db_key}")
            NotificationServer.register.pop(db_key)

    @staticmethod
    async def notify_room_event(room, status: str = "notification") -> None:
        """ Iterate over all registered account and send message to all room members. """
        for db_key in NotificationServer.register:
            if room.has_member(db_key):
                WsLogger.log("NS", f"Notifying client: {db_key} for room: {room.db_key}")
                ws = NotificationServer.register.get(db_key)
                await ws.send_json({"status": status, "room_code": room.code})

    @staticmethod
    async def flush_buffer(db_key: str) -> None:
        """ Send all notification about event in all rooms saved in buffer to user. """
        client_ws = NotificationServer.register.get(db_key, False)
        if client_ws is False:
            WsLogger.log("NS", "Cannot flush buffer (client is not registered)")
            return

        room_codes = NotificationServer.unsent_buffer.get(db_key, [])
        for room_code in room_codes:
            await client_ws.send_json({"status": "notification", "room_code": room_code})

        if db_key in NotificationServer.unsent_buffer:
            NotificationServer.unsent_buffer.pop(db_key)
            WsLogger.log("NS", f"Flushed buffer containing {len(room_codes)} unsent notifications for: {db_key}")

    @staticmethod
    def feed_buffer(db_key: str, room_code: str) -> None:
        """ Append room_code to user's unsent_buffer. """
        if db_key not in NotificationServer.unsent_buffer:
            NotificationServer.unsent_buffer[db_key] = [room_code]
            WsLogger.log("NS", f"Feed buffer for: {db_key} with: {room_code} (created buffer)")
            return
        
        NotificationServer.unsent_buffer[db_key].append(room_code)
        WsLogger.log("NS", f"Feed buffer for: {db_key} with: {room_code}")


class RoomConnectionManager:
    """ Keep track of websocket clients of specific room. """
    register = {}

    def __init__(self, room_key: str) -> None:
        self.room_key = room_key
        self.clients: dict[str, WebSocket] = {}

    async def register_client(self, db_key: str, client: WebSocket) -> None:
        """ Accept pending request from websocket client and register address. """
        await client.accept()
        WsLogger.log(self.room_key, f"Registered client: {client.client} for: {db_key}")
        self.clients[db_key] = client

    def remove_client(self, db_key: str) -> None:
        """ Remove client from room's register. """
        if db_key in self.clients:
            WsLogger.log(self.room_key, f"Removed client from register: {db_key}")
            self.clients.pop(db_key)
    
    async def send_to_everyone(self, content: dict) -> None:
        """ Send content to all registered addresses. """
        WsLogger.log(self.room_key, f"Sending message to: {len(self.clients)} clients")
        for ws in self.clients.values():
            await ws.send_json(content)


def get_instance(room_key: str) -> "RoomConnectionManager":
    """
    Get instance of RoomConnectionManager for specific room.
    If instance has been already registered before, return existing one,
      else, create new one. 
    """
    if room_key in RoomConnectionManager.register:
        return RoomConnectionManager.register.get(room_key)
    
    instance = RoomConnectionManager(room_key)
    RoomConnectionManager.register[room_key] = instance
    WsLogger.log(room_key, "Created new RoomConnectionManager instance.")
    return instance
