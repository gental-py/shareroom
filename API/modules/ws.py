"""
MODULE
    ws.py

DESCRIPTION
    WebSockets managers.

    DashboardNotificationServer message scheme:
    {
      "status": "ROOM_NOTIFICATION"/"RM_ROOM"/"ROOM_KICK"
      "room_code": STRING
      (*) "room_name": STRING 
    }
    
    InRoomEventsServer message scheme:
    {
      "status": STRING
      "data": OBJECT
    }
"""
from modules import logs

from fastapi import WebSocket


class NotificationStatus:
    ROOM_NOTIFICATION = "ROOM_NOTIFICATION"
    ROOM_REMOVED = "RM_ROOM"
    KICKED_FROM_ROOM = "ROOM_KICK"


class DashboardNotificationServer:
    clients: dict[str, WebSocket] = {}

    @staticmethod
    async def register_client(db_key: str, client: WebSocket) -> None:
        """ Register new client. """
        if db_key in DashboardNotificationServer.clients:
            logs.websocket_logger.log("DashboardNotificationServer", f"Client already registered: {db_key}")
            return

        await client.accept()
        DashboardNotificationServer.clients[db_key] = client
        logs.websocket_logger.log("DashboardNotificationServer", f"Registered new client: {db_key}")

    @staticmethod
    async def remove_client(db_key: str) -> None:
        """ Remove client from register. """
        if db_key not in DashboardNotificationServer.clients:
            logs.websocket_logger.log("DashboardNotificationServer", f"Cannot remove client from register: {db_key} (not found)")
            return 
        
        DashboardNotificationServer.clients.pop(db_key)
        logs.websocket_logger.log("DashboardNotificationServer", f"Removed client from register: {db_key}")

    @staticmethod
    def get_client_ws(db_key: str) -> WebSocket | None:
        """ Returns registered client's websocket or None if not found. """
        ws = DashboardNotificationServer.clients.get(db_key)
        if ws is None:
            logs.websocket_logger.log(db_key, f"Cannot get client from register: {db_key} (not found)")
        return ws

    @staticmethod
    async def send_message_to(db_key: str, status: NotificationStatus, room_code: str, room_name: str = None) -> None:
        """ Send message to single client. """ 
        ws = DashboardNotificationServer.get_client_ws(db_key)
        if ws is None:
            logs.websocket_logger.log(db_key, "Cannot send message to client")
            return
        
        content = {
            "status": status,
            "room_code": room_code
        }
        
        if room_name is not None:
            content.update({"room_name": room_name})
        
        await ws.send_json(content)
        logs.websocket_logger.log(db_key, f"Sent message ({status})")

    @staticmethod
    async def send_room_notification(room, status: NotificationStatus, include_room_name: bool = False) -> None:
        """ Send notification to all room's members not being connected to the room. """
        for db_key in DashboardNotificationServer.clients.keys():
            if not room.has_member(db_key):
                continue
        
            await DashboardNotificationServer.send_message_to(
                db_key,
                status,
                room.code,
                room.name if include_room_name else None
            )
            logs.websocket_logger.log(room.db_key, f"Notifying client: {db_key} for room: {room.db_key}")

    
class InRoomEventsServer:
    rooms_instances: dict[str, "InRoomEventsServer"] = {}

    @staticmethod
    def get_instance(room_key: str) -> "InRoomEventsServer":
        """ Return instance of InRoomEventsServer for specified room_key. """
        instance = InRoomEventsServer.rooms_instances.get(room_key)
        if instance is None:
            instance = InRoomEventsServer(room_key)
            InRoomEventsServer.rooms_instances[room_key] = instance
            logs.websocket_logger.log(room_key, "Created InRoomEventsServer")
        return instance
    
    def __init__(self, room_key: str) -> None:
        self.room_key = room_key 
        self.connections: list[WebSocket] = []

    async def assign_to_room(self, websocket: WebSocket) -> None:
        """ Assign client's connection to room's register. """
        if websocket in self.connections:
            logs.websocket_logger.log(self.room_key, "Connection already in room register.")
            return
        
        await websocket.accept()
        
        self.connections.append(websocket)
        logs.websocket_logger.log(self.room_key, "Assigned new connection to room's register.")

    def remove_from_room(self, websocket: WebSocket) -> None:
        """ Remove connection from room's register. """
        if websocket not in self.connections:
            logs.websocket_logger.log(self.room_key, "Cannot remove connection from register (not found)")
            return
        
        self.connections.remove(websocket)
        logs.websocket_logger.log(self.room_key, "Removed connection from room's register.")

    async def send_event(self, status: str, content: dict = {}) -> None:
        """ Send in-room update to connected clients. """
        for connection in self.connections:
            await connection.send_json({
                "status": status.upper(),
                "data": content
            })
        logs.websocket_logger.log(self.room_key, f"Sent: {status.upper()} in room event.")
        
    