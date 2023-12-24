"""
ENTRYPOINT
    api.py

DESCRIPTION
  Job
    Runs and handles API endpoint requests.
    Delegates jobs to the suitable modules.
  
  Categories
    Endpoints are separated into two categories: `rooms/` and `accounts/`

  Response
    Every response has a `"status"` key with a boolean value.
    When the value is True, the action succeeded,
      and additional data may be passed by response
      (check the endpoint's docstr for details).
    When the value is False, the required action failed,
      and the response will contain `"err_msg"` with
      an error message in a displayable form.

  Status code
    The response's HTTP status code is always `200` for successfully
      ended operations and `400` for failed ones.

  Pre-validators
    Before any action in the room will take place, user's data goes
      through validation process which checks for db_key, session_id and room
      errors. If the request's data fails at this point, a response
      with `"err_msg"="@VALIDATION_FAIL"` will be sent.
      Client must then logout user.

  Endpoints:
    (GET) / - Home request, check if system is online.

    /accounts/
      - `create` (POST)
      - `login` (POST)
      - `logout` (POST)
      - `changePassword` (POST)
      - `delete` (POST)
      - `userData` (GET)

    /rooms/
      - `create` (POST)
      - `joinRoom` (POST)
      - `connect` (POST)
      - `uploadFile` (POST)
      - `downloadFile` (POST)
      - `addMessage` (POST)
      - `leaveRoom` (POST)
      - `roomData/{room_key}` (GET)
      - `ws/{room_key}/{db_key}` (WS)
      - `notificationServer/{db_key}` (WS)

      /admin/
        - `setRoomLockState` (POST)
        - `kickMember` (POST)
        - `removeFile` (POST)
"""
from models import request_models

from modules.logs import AccessLogger, SessionLogger, RoomsLogger
from modules import timestamp
from modules import database
from modules import accounts
from modules import sessions
from modules import rooms
from modules import ws

from fastapi import FastAPI, Request, UploadFile, WebSocket, WebSocketDisconnect, Form, File
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import bcrypt

rooms.RoomDataManager.rebuild_ids_register()


def generate_response_and_log(
        request: Request,
        status: bool,
        log_message: str,
        err_msg: str = None,
        additional_data: dict = None
    ) -> JSONResponse:
    """ Generate JSONResponse object and save log. """
    AccessLogger.log(request, status, log_message)

    data = {"status": status}

    if additional_data:
        data.update(additional_data)
    if not status:
        data["err_msg"] = err_msg if err_msg else "error"

    status_code = 200 if status else 400
    return JSONResponse(data, status_code)


api = FastAPI()
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@api.get("/")
def get_home(request: Request) -> JSONResponse:
    """ Used to check if API is online. """
    return generate_response_and_log(request, True, "Home request received")


# -- ACCOUNTS --

@api.post("/accounts/create")
async def create_account(data: request_models.M_CreateAccount, request: Request) -> JSONResponse:
    """
    Create new account.

    Additional data on success:
        + "db_key": STRING
    """
    if len(data.username) < 5:
        return generate_response_and_log(
            request,
            False,
            f"Cannot create account as name is too short: {data.username}",
            "Username is too short."
        )

    if len(data.username) > 16:
        return generate_response_and_log(
            request,
            False,
            f"Cannot create account as name is too long: {data.username}",
            "Username is too long."
        )

    if len(data.password) < 5:
        return generate_response_and_log(
            request,
            False,
            f"Cannot create account as password is too short: {len(data.password)}",
            "Password is too short."
        )

    account = accounts.Account.create_account(data.username, data.password)
    if not account:
        return generate_response_and_log(
            request,
            False,
            f"Cannot create account as name is already in use: {data.username}",
            "Username is not available"
        )

    return generate_response_and_log(
        request,
        True,
        f"Created account: {account.db_key}",
        additional_data={"db_key": account.db_key}
    )

@api.post("/accounts/login")
async def account_login(data: request_models.M_AccountLogin, request: Request) -> JSONResponse:
    """
    Check provided login credentials.

    Additional data on success:
        + "db_key": STRING
        + "session_id": STRING
    """
    try:
        account = accounts.Account.get_account_by_name(data.username)

    except database.KeyNotFound:
        return generate_response_and_log(
            request,
            False,
            f"Login for: {data.username} failed (invalid username)",
            "Invalid username."
        )

    if not account.check_password(data.password):
        return generate_response_and_log(
            request,
            False,
            f"Login for: {account.db_key} failed (invalid password)",
            "Invalid password.",
        )

    last_interaction = account.last_interaction

    if account.has_valid_session():
        session = account.get_session()
        session.drop()
        SessionLogger.log(session.session_id, "User tried to login but has opened session.")

    if account.has_expired_session():
        session = account.get_session()
        session.drop()
        SessionLogger.log(session.session_id, f"Found expired session while login: {session.session_id}")

    for room_key in account.active_rooms:
        room = rooms.Room.get_room_by_key(room_key)
        if room.last_interaction > last_interaction:
            ws.NotificationServer.feed_buffer(account.db_key, room.code)

    session = account.get_session()
    session.renew()
    return generate_response_and_log(
        request,
        True,
        f"Successful login for: {account.db_key}",
        additional_data={"db_key": account.db_key, "session_id": session.session_id}
    )

@api.post("/accounts/logout")
@sessions.validate_client
async def account_logout(data: request_models.M_AccountLogout, request: Request) -> JSONResponse:
    """ Logout user. Close it's session. """
    account = accounts.Account.get_account_by_key(data.db_key)

    if not account.has_valid_session():
        return generate_response_and_log(
            request,
            False,
            f"User: {data.db_key} tried to logout from session: {data.session_id} but no active session was found.",
            sessions.VALIDATION_FAIL_ERRMSG
        )

    session = account.get_session()
    session.drop()
    account.update_last_interaction_date()
    return generate_response_and_log(
        request,
        True,
        f"User: {data.db_key} logged out from session: {data.session_id}"
    )

@api.post("/accounts/changePassword")
@sessions.validate_client
async def change_account_password(data: request_models.M_ChangeAccountPassword, request: Request) -> JSONResponse:
    """ Change account's password. """
    account = accounts.Account.get_account_by_key(data.db_key)

    if len(data.new) < 5:
        return generate_response_and_log(
            request,
            False,
            f"Cannot change password for: {account.db_key} (new password is too short)",
            "New password is too short.",
        )

    if account.change_password(data.current, data.new):
        return generate_response_and_log(
            request,
            True,
            f"Changed password for user: {account.db_key}"
        )
    else:
        return generate_response_and_log(
            request,
            False,
            f"Cannot change password for user: {account.db_key} (invalid current password)",
            "Invalid current password.",
        )

@api.post("/accounts/delete")
async def delete_account(data: request_models.M_DeleteAccount, request: Request) -> JSONResponse:
    """ Delete account. """
    account = accounts.Account.get_account_by_key(data.db_key)

    for room_key in account.active_rooms:
        room = rooms.Room.get_room_by_key(room_key)
        room.remove_member_key(account.db_key)

    if not account.check_password(data.password):
        return generate_response_and_log(
            request,
            False,
            f"Cannot remove account: {account.db_key} (invalid password)",
            "Invalid password.",
        )

    account.delete_account()
    return generate_response_and_log(
        request,
        True,
        f"Removed account: {account.db_key}"
    )

@api.post("/accounts/userData")
@sessions.validate_client
async def get_account_data(data: request_models.M_AccountData, request: Request) -> JSONResponse:
    """
    Get public user's data username.

    Additional data on success:
        + "data"
          | "username": STRING
          | "joined_at": STRING
          | "rooms": {
              "ROOM_CODE": {
                    "name": STRING,
                    "is_admin": BOOLEAN
                }
            }
          | "notifications": [ROOM_CODE: STRING, ROOM_CODE: STRING]
    """
    account = accounts.Account.get_account_by_key(data.db_key)
    user_data = {
        "username": account.username,
        "joined_at": timestamp.convert_to_readable(account.date_join),
        "rooms": {},
        "notifications": []
    }

    for room_key in account.active_rooms:
        try:
            room = rooms.Room.get_room_by_key(room_key)

        except database.KeyNotFound:
            RoomsLogger.log(room_key, "Room not found while passing user data!")
            account.remove_active_room(room_key)
            continue

        user_data["rooms"].update(
            {
                room.code: {
                    "name": room.name,
                    "is_admin": room.admin_key == account.db_key
                }
            }
        )

        if room.db_key not in account.active_rooms:
            RoomsLogger.log(room_key, "Room not found in active rooms while passing user data (added)!")
            account.add_active_room(room.db_key)

    await ws.NotificationServer.flush_buffer(account.db_key)
    return generate_response_and_log(
        request,
        True,
        f"Passed user data: {data.db_key}",
        additional_data={"data": user_data}
    )


# -- ROOMS --


@api.post("/rooms/create")
@sessions.validate_client
async def create_room(data: request_models.M_CreateRoom, request: Request) -> JSONResponse:
    """
    Create new room.

    Additional data on success:
        + "code"
    """
    if len(data.name) < 5:
        return generate_response_and_log(
            request,
            False,
            f"Cannot create room (name: {data.name} is too short)",
            "Name is too short.",
        )

    if len(data.name) > 16:
        return generate_response_and_log(
            request,
            False,
            f"Cannot create room (name: {data.name} is too long)",
            "Name is too long.",
        )

    if not rooms.is_name_available(data.name):
        return generate_response_and_log(
            request,
            False,
            f"Cannot create room (name: {data.name} is unavailable)",
            "Name is unavailable.",
        )

    if data.max_users not in range(2, rooms.MAX_USERS_PER_ROOM +1):
        AccessLogger.log(request, "-", f"Corrected max_users = {data.max_users} to {rooms.MAX_USERS_PER_ROOM}")
        data.max_users = rooms.MAX_USERS_PER_ROOM

    if data.password is not None:
        data.password = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt())

    room = rooms.Room.create_room(data.name, data.db_key, data.max_users, data.password)
    if room is None:
        return generate_response_and_log(
            request,
            False,
            "Cannot create room (check logs above and pray You will find something :) )",
            "Something went wrong... (idk what actually)",
        )

    account = accounts.Account.get_account_by_key(data.db_key)
    account.add_active_room(room.db_key)
    return generate_response_and_log(
        request,
        True,
        f"Created room: {repr(room)}",
        additional_data={"code": room.code}
    )

@api.get("/rooms/roomData/{room_key}")
async def get_room_data(room_key: str, request: Request) -> JSONResponse:
    """
    Get room's public data.

    Additional data on success:
        + "data"
        | "name"
        | "creator"
        | "date_created"
        | "date_remove"
        | "max_users"
        | "is_password"
        | "is_locked"
        | "members": [NAME, NAME, NAME]  <- Admin username not included
        | "admin_username": STRING
        | "messages": [{"author": STRING, "content": STRING}, {...}]
        | "files": {
            "fileid": {
                "name": filename
                "author": username,
                "size": in_bytes
            }
          }
    """
    try:
        room = rooms.Room.get_room_by_key(room_key)

    except database.KeyNotFound:
        return generate_response_and_log(
            request,
            False,
            f"Cannot provide data for room: {room_key} (not found)",
            "Room not found.",
        )

    data = {
        "name": room.name,
        "creator": room.get_admin_account().username,
        "date_created": timestamp.convert_to_readable(room.date_created),
        "date_remove": timestamp.convert_to_readable(room.date_remove),
        "max_users": room.max_users,
        "is_password": int(room.password != ""),
        "is_locked": int(room.is_locked),
        "members": [m.username for m in room.get_members_accounts() if m.db_key != room.admin_key],
        "admin_username": room.get_admin_account().username,
        "messages": room.room_data_manager.get_all_messages(),
        "files": room.room_data_manager.get_all_files_data()
    }

    return generate_response_and_log(
        request,
        True,
        f"Provided room data: {room_key}",
        additional_data={"data": data}
    )

@api.post("/rooms/joinRoom")
@sessions.validate_client
async def join_room(data: request_models.M_JoinRoom, request: Request) -> JSONResponse:
    """
    Join to existing room using it's code.

    Additional data on success:
        + "name": STRING (room's name)
    """
    account = accounts.Account.get_account_by_key(data.db_key)

    try:
        room = rooms.Room.get_room_by_code(data.room_code)

    except database.KeyNotFound:
        return generate_response_and_log(
            request,
            False,
            f"Room code not found: {data.room_code}",
            "Invalid code."
        )

    if room.is_locked:
        return generate_response_and_log(
            request,
            False,
            f"Room: {room.db_key} is locked, user: {account.db_key} cannot join",
            "This room is locked.",
        )

    if room.get_free_slots() < 1:
        return generate_response_and_log(
            request,
            False,
            f"Room is full: {room.db_key} (free={room.get_free_slots()})",
            "This room is full.",
        )

    if not room.password:
        room.add_member_key(account.db_key)
        await ws.get_instance(room.db_key).send_to_everyone({
            "status": "USER_JOIN",
            "username": account.username,
        })
        account.add_active_room(room.db_key)
        return generate_response_and_log(
            request,
            True,
            f"User: {account.db_key} joined room: {room.db_key} (no password)",
            additional_data={"name": room.name}
        )

    if data.password is None:
        return generate_response_and_log(
            request,
            False,
            "Password required but not provided",
            "This room requires password.",
        )

    if room.check_password(data.password):
        room.add_member_key(account.db_key)
        await ws.get_instance(room.db_key).send_to_everyone({
            "status": "USER_JOIN",
            "username": account.username,
        })
        account.add_active_room(room.db_key)
        return generate_response_and_log(
            request,
            True,
            f"User: {account.db_key} joined room: {room.db_key} (valid password)",
            additional_data={"name": room.name}
        )

    else:
        return generate_response_and_log(
            request,
            False,
            f"Client provided invalid password to room: {room.db_key}",
            "Invalid password.",
        )

@api.post("/rooms/connect")
@sessions.validate_client
@rooms.validate_room
async def connect_to_room(data: request_models.M_ConnectRoom, request: Request) -> JSONResponse:
    """
    Allow user to connect to room's websocket. Build one if needed.

    Additional data on success:
        + "room_key": (used to connect with WS)
        + "is_admin"
    """
    account = accounts.Account.get_account_by_key(data.db_key)
    room = rooms.Room.get_room_by_code(data.room_code)

    return generate_response_and_log(
        request,
        True,
        f"Provided room: {room.db_key} key for: {account.db_key}",
        additional_data={
            "room_key": room.db_key,
            "is_admin": room.admin_key == account.db_key
        }
    )

@api.post("/rooms/uploadFile")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    db_key: str = Form(...),
    session_id: str = Form(...),
    room_code: str = Form(...),
) -> JSONResponse:
    """
    Upload user-provided file to room's storage.

    Additional data on success:
        + "id": STRING
        + "name": STRING
    """
    if not sessions.validate_auth_data(db_key, session_id):
        return sessions.VALIDATION_FAIL_RESPONSE

    account = accounts.Account.get_account_by_key(db_key)
    room = rooms.Room.get_room_by_code(room_code)

    response = room.upload_file(db_key, file)
    if response:
        file_id, file_name = response
        await ws.get_instance(room.db_key).send_to_everyone({
            "status": "ADD_FILE",
            "author": account.username,
            "fileid": file_id,
            "name": file_name,
            "size": file.size
        })
        await ws.NotificationServer.notify_room_event(room)

        room.update_interaction_date()
        return generate_response_and_log(
            request,
            True,
            f"Uploaded file: {file.filename} in room: {room_code} for user: {db_key}",
            additional_data={"id": file_id, "name": file_name}
        )

    else:
        return generate_response_and_log(
            request,
            False,
            f"Cannot upload file: {file.filename} (not enough space.)",
            "Not enough space left in room",
        )

@api.post("/rooms/downloadFile")
@sessions.validate_client
@rooms.validate_room
async def download_file(data: request_models.M_DownloadFile, request: Request) -> FileResponse:
    """ Download file from room's pool. """
    room = rooms.Room.get_room_by_code(data.room_code)
    file_path = room.room_data_manager.get_file_path(data.fileid)

    if file_path is False:
        return generate_response_and_log(
            request,
            False,
            f"Cannot pass file with id: {data.fileid} (invalid id)",
            "Invalid file id",
        )

    AccessLogger.log(request, True, f"Passed file: {data.fileid} to: {data.db_key}")
    return FileResponse(path=str(file_path), filename=file_path.get_name())

@api.post("/rooms/addMessage")
@sessions.validate_client
@rooms.validate_room
async def add_message(data: request_models.M_AddMessage, request: Request) -> JSONResponse:
    """ Add new message to room's stack. """
    account = accounts.Account.get_account_by_key(data.db_key)
    room = rooms.Room.get_room_by_code(data.room_code)

    if len(data.content) > 1024:
        return generate_response_and_log(
            request,
            False,
            f"Cannot add message (content is too long - {len(data.content)})",
            "Content is too long.",
        )

    room.room_data_manager.add_message(account.username, data.content)
    await ws.get_instance(room.db_key).send_to_everyone({
        "status": "ADD_MSG",
        "author": account.username,
        "content": data.content
    })
    await ws.NotificationServer.notify_room_event(room)

    room.update_interaction_date()
    return generate_response_and_log(
        request,
        True,
        f"Added message from: {data.db_key} to: {room.db_key}"
    )

@api.post("/rooms/leaveRoom")
@sessions.validate_client
@rooms.validate_room
async def leave_room(data: request_models.M_LeaveRoom, request: Request) -> JSONResponse:
    """ Remove user from room. """
    room = rooms.Room.get_room_by_code(data.room_code)
    room.remove_member_key(data.db_key)
    account = accounts.Account.get_account_by_key(data.db_key)
    account.remove_active_room(room.db_key)

    if room.admin_key == data.db_key:
        RoomsLogger.log(room.db_key, "Admin left, removing room...")
        await ws.NotificationServer.notify_room_event(room, "RM_ROOM")
        room.remove_room()
        await ws.get_instance(room.db_key).send_to_everyone({
            "status": "RM_ROOM",
            "room_code": room.code,
            "room_name": room.name
        })

    else:
        await ws.get_instance(room.db_key).send_to_everyone({
            "status": "USER_LEFT",
            "username": account.username
        })

    return generate_response_and_log(
        request,
        True,
        f"User: {data.db_key} left room: {room.db_key}"
    )


@api.websocket("/rooms/ws/{room_key}/{db_key}")
async def room_ws(room_key: str, db_key: str, websocket: WebSocket):
    """ Connect client with room's websocket for instant updates. """
    ws_manager = ws.get_instance(room_key)
    await ws_manager.register_client(db_key, websocket)
    await websocket.send_json({"status": "connected"})
    try:
        while True:
            # Data from user is sent using HTTP requests, not WS.
            await websocket.receive_text()

    except WebSocketDisconnect:
        ws_manager.remove_client(db_key)

@api.websocket("/rooms/notificationServer/{db_key}")
async def notification_server_ws(db_key: str, websocket: WebSocket):
    """ Register user to notification server. """
    if db_key not in database.users_db.get_all_keys():
        ws.WsLogger.log("API (NS)", f"NS register request received from invalid db_key: {db_key}")
        return

    await ws.NotificationServer.register_client(db_key, websocket)
    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        ws.NotificationServer.remove_client(db_key)


@api.post("/rooms/admin/setRoomLockState")
@sessions.validate_client
@rooms.validate_room
async def set_lock_state(data: request_models.M_LockRoom, request: Request) -> JSONResponse:
    """ Set room's lock state to provided by client. """
    account = accounts.Account.get_account_by_key(data.db_key)
    room = rooms.Room.get_room_by_code(data.room_code)

    if room.admin_key != account.db_key:
        return generate_response_and_log(
            request,
            False,
            f"User: {data.db_key} is not an admin of room: {data.room_code}",
            "You are not administrator.",
        )

    if data.state not in (0, 1):
        return generate_response_and_log(
            request,
            False,
            f"User: {data.db_key} provided invalid lock state for room: {data.room_code} ({data.state}, {type(data.state)})",
            "Invalid state provided.",
        )

    state = bool(data.state)
    room.set_lock_state(state)
    await ws.get_instance(room.db_key).send_to_everyone({
        "status": "UPDATE_LOCK_STATE",
        "state": int(state)
    })

    return generate_response_and_log(
        request,
        True,
        f"User: {data.db_key} changed lock state for room: {data.room_code} to: {state}",
    )

@api.post("/rooms/admin/kickMember")
@sessions.validate_client
@rooms.validate_room
async def kick_member(data: request_models.M_KickMember, request: Request) -> JSONResponse:
    """ Kick member from room. """
    admin_account = accounts.Account.get_account_by_key(data.db_key)
    room = rooms.Room.get_room_by_code(data.room_code)

    if not room.admin_key == admin_account.db_key:
        return generate_response_and_log(
            request,
            False,
            f"Command author is not a admin: {admin_account.db_key}",
            "You are not an admin"
        )

    try:
        member_account = accounts.Account.get_account_by_name(data.member_name)

    except database.KeyNotFound:
        return generate_response_and_log(
            request,
            False,
            f"Cannot kick member: {data.member_name} (invalid username)",
            "Member not found"
        )

    if not room.has_member(member_account.db_key):
        return generate_response_and_log(
            request,
            False,
            f"Cannot kick member: {member_account.db_key} (user does not belong to room: {room.db_key})",
            "Member not found in room"
        )

    room.remove_member_key(member_account.db_key)
    member_account.remove_active_room(room.db_key)

    await ws.get_instance(room.db_key).send_to_everyone({
        "status": "KICK_MEMBER",
        "username": data.member_name
    })

    if member_account.db_key in ws.NotificationServer.register:
        await ws.NotificationServer.register.get(member_account.db_key).send_json(
            {
                "status": "ROOM_KICK",
                "room_code": room.code,
                "room_name": room.name
            }
        )

    return generate_response_and_log(
        request,
        True,
        f"Admin: {admin_account.db_key} removed member: {member_account.db_key} from room: {room.db_key}"
    )

@api.post("/rooms/admin/removeFile")
@sessions.validate_client
@rooms.validate_room
async def remove_file(data: request_models.M_RemoveFile, request: Request) -> JSONResponse:
    """ Remove file from room's pool. """
    account = accounts.Account.get_account_by_key(data.db_key)
    room = rooms.Room.get_room_by_code(data.room_code)

    if not room.admin_key == account.db_key:
        return generate_response_and_log(
            request,
            False,
            f"Command author is not a admin: {account.db_key}",
            "You are not an admin"
        )

    status = room.room_data_manager.remove_file(data.fileid)
    if not status:
        return generate_response_and_log(
            request,
            False,
            f"Cannot remove file: {data.fileid} (not found in register)",
            "File not found!"
        )

    await ws.get_instance(room.db_key).send_to_everyone({
        "status": "RM_FILE",
        "fileid": data.fileid
    })

    return generate_response_and_log(
        request,
        True,
        f"Admin: {account.db_key} removed file: {data.fileid} from room: {room.db_key}"
    )


if __name__ == "__main__":
    uvicorn.run(api)
