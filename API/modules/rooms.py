"""
MODULE
    rooms.py

DESCRIPTION
    Contains room management tools.
"""
from models.db_models import RoomModel

from modules.database import SET_AFTER_INIT
from modules.paths import Path
from modules import timestamp
from modules import database
from modules import users
from modules import logs

from fastapi.responses import JSONResponse
from dataclasses import dataclass
from fastapi import UploadFile
from functools import wraps
from typing import List
import hashlib
import bcrypt
import json
import os


ROOMS_DATA_PATH = Path("./data/rooms/")
MAX_ROOM_DATA_SIZE = 1073741824 // 10  # tenth of GB per room
TOTAL_DATA_SIZE = 1073741824  # one GB
MAX_USERS_PER_ROOM = 5
CODE_LENGTH = 6

ROOM_VALIDATION_FAIL_MSG = "@ROOM_VALIDATION_FAIL"
ROOM_VALIDATION_FAIL_RESPONSE = JSONResponse({"status": False, "err_msg": ROOM_VALIDATION_FAIL_MSG})


def create_db_key(name: str) -> str:
    """ Hash room's name using SHA1 algorithm. """
    return hashlib.sha1(name.encode()).hexdigest()

def is_name_available(name: str) -> bool:
    """ Check if name is already in use by other room. """
    return not create_db_key(name) in database.rooms_db.get_all_keys()

def create_file_id(user_key: str, filename: str) -> str:
    """ Create file id from user's key an file's name. """
    return hashlib.sha1((user_key+filename).encode()).hexdigest()

def get_total_space_left() -> int:
    """ Check data size from all rooms and check left space. """
    rooms_size = 0
    for room_path in RoomDataManager.ids_register.values():
        for path, _, files in os.walk(str(room_path)):
            for file in files:
                file_path = os.path.join(path, file)
                size += os.path.getsize(file_path)

    space_left = TOTAL_DATA_SIZE - rooms_size
    logs.rooms_logger.log("(space calculator)" ,f"Calculated total space left: {space_left}b")
    return space_left


class RoomDataManager:
    """ Manage users' data in rooms. """
    ids_register: dict[str, Path] = {}

    @staticmethod
    def rebuild_ids_register() -> None:
        """ Iterate over all rooms_data' directories and save id's for files. """
        for room_dir in ROOMS_DATA_PATH.list_dir():
            for user_dir in room_dir.list_dir():
                for file in user_dir.list_dir(as_str=True):
                    file_id = create_file_id(user_dir.get_name(), file)
                    file_path = user_dir / file
                    RoomDataManager.ids_register[file_id] = file_path
                    logs.rooms_logger.log("(id rebuilder)", f"Saved id: {file_id} for: {str(file_path)}")

    @staticmethod
    def get_file_path(file_id: str) -> Path | bool:
        """ Return path to file by it's id. (False if not found) """
        path = RoomDataManager.ids_register.get(file_id, False)
        return path

    def __init__(self, room_key: str) -> None:
        self.room_key = room_key
        self.room_path = ROOMS_DATA_PATH // self.room_key
        if not self.room_path.exists():
            self.room_path.touch()
            logs.rooms_logger.log(self.room_key, "Created room data directory.")
        
        self.msg_path = self.room_path / "messages.json"
        if not self.msg_path.exists():
            self.msg_path.touch()
            with open(str(self.msg_path), "w") as file:
                json.dump([], file)            
            logs.rooms_logger.log(self.room_key, "Created messages file")

    def __get_msg_content(self) -> List[dict]:
        """ Returns content of messages.json file. """
        with open(str(self.msg_path), "r") as file:
            return json.load(file)
        
    def __save_msg_content(self, content: List[dict]) -> None:
        """ Dump content to messages file. """
        with open(str(self.msg_path), "w+") as file:
            json.dump(content, file)

    def calculate_total_space(self) -> int:
        """ Calculate total space took by user files in bytes. """
        total_size = 0
        for user_dir in self.room_path.list_dir():
            for file in user_dir.list_dir():
                total_size += file.get_size()
        return total_size
    
    def user_dir_exists(self, user_key: str) -> bool:
        """ Check if user's directory exists in this room. """
        return (self.room_path // user_key).exists()

    def add_user_dir(self, user_key: str) -> None:
        """ Create user directory. """
        (self.room_path // user_key).touch()
        logs.rooms_logger.log(self.room_key, f"Created user data directory for: {user_key}")

    def remove_user_dir(self, user_key: str) -> None:
        """ Remove user directory. """
        path = self.room_path // user_key
        if path.exists():
            path.remove()
            logs.rooms_logger.log(self.room_key, f"Removed user dir: {user_key}")
        else:
            logs.rooms_logger.log(self.room_key, f"WARN: Cannot remove user dir (not exists) for: {user_key}")

    def upload_file(self, user_key: str, uploaded_file: UploadFile) -> tuple[str, str] | bool:
        """ Upload file to user's directory if there is enough space. Returns upload status. """
        if uploaded_file.size is None:
            uploaded_file.size = len(uploaded_file.file.read())
        if (self.calculate_total_space() + uploaded_file.size) > MAX_ROOM_DATA_SIZE:
            logs.rooms_logger.log(self.room_key, "Cannot upload file (room size limit reached.)")
            return False
        if ((TOTAL_DATA_SIZE - get_total_space_left()) + uploaded_file.size) > TOTAL_DATA_SIZE:
            logs.rooms_logger.log(self.room_key, "Cannot upload file (total data size limit reached.)")
            return False
        
        if not self.user_dir_exists(user_key):
            logs.rooms_logger.log(self.room_key, f"User's room does not exists: {user_key} (creating...)")
            self.add_user_dir(user_key)

        user_path = self.room_path // user_key
        if uploaded_file.filename in user_path.list_dir(as_str=True):
            logs.rooms_logger.log(self.room_key, f"Renaming uploaded file as same was found: {uploaded_file.filename}")
            suffix = str(timestamp.generate_timestamp())[-4:]
            name, ext = os.path.splitext(uploaded_file.filename)
            uploaded_file.filename = name + suffix + ext
    
        file_path = user_path + uploaded_file.filename
        file_path.touch()
        with open(file_path.path, "wb+") as file:
            uploaded_file.file.seek(0)
            content = uploaded_file.file.read()
            file.write(content)

        file_id = create_file_id(user_key, uploaded_file.filename)
        RoomDataManager.ids_register[file_id] = file_path
        logs.rooms_logger.log(self.room_key, f"Uploaded file to user directory: {uploaded_file.filename} (id: {file_id})")
        return file_id, uploaded_file.filename

    def remove_file(self, file_id: str) -> bool:
        """ Remove file with provided id. Returns if file was removed. """
        path = RoomDataManager.ids_register.get(file_id, False)
        if not path:
            logs.rooms_logger.log(self.room_key, f"Tried to remove file id: {file_id} (id not found in register)")
            return False
        
        path.remove()
        RoomDataManager.ids_register.pop(file_id)
        logs.rooms_logger.log(self.room_key, f"Removed file: {str(path)} ({file_id})")
        return True

    def get_all_files_data(self) -> dict:
        """ Used in /rooms/roomData request, returns all files' data. """
        data = {}

        for user_dir in self.room_path.list_dir():
            for file in user_dir.list_dir():
                file_id = create_file_id(user_dir.get_name(), file.get_name())
                size = file.get_size()
                user_key = user_dir.get_name()

                try:
                    username = users.User.get_user_by_key(user_key).username

                except database.KeyNotFound:
                    logs.rooms_logger.log(self.room_key, f"Invalid user key found: {user_key}")
                    username = "?"

                data[file_id] = {"name": file.get_name(), "author": username, "size": size}
        return data
    
    def get_all_messages(self) -> dict:
        """ Used in /rooms/roomData request, returns all messages in JSON format. """
        return self.__get_msg_content()
    
    def add_message(self, author_name: str, content: str) -> None:
        """ Append message to file. """
        message_object = {"author": author_name, "content": content}
        file_content = self.__get_msg_content()
        file_content.append(message_object)
        self.__save_msg_content(file_content)
    
    def cleanup(self) -> None:
        """ Remove all files and directories including room dir. """
        self.room_path.remove()


@dataclass
class Room:
    name: str
    admin_key: str
    date_created: int
    last_interaction: int
    members: list
    max_users: int = 5
    password: str = None
    is_locked: bool = False

    # Automatically set after initialization
    code: str = SET_AFTER_INIT
    db_key: str = SET_AFTER_INIT
    room_data_manager: RoomDataManager = SET_AFTER_INIT

    @staticmethod
    def create_room(name: str, admin_key: int, max_users: int = 5, password: str = None) -> "Room":
        """ 
        Create new room and return it's instance if name is available 
        and admin_key exists in users database, else return False. 
        Automatically repair max_users amount if is out of range: <1, MAX_USERS_PER_ROOM>.
        Save room to rooms database. 
        """
        if not is_name_available(name):
            logs.rooms_logger.log(name, f"Cannot create room (name in use): {name}")
            return False
        
        if admin_key not in database.users_db.get_all_keys():
            logs.rooms_logger.log(name, f"Cannot create room (admin_key not found in users_db): {admin_key}")
            return False

        if max_users not in range(1, MAX_USERS_PER_ROOM+1):
            logs.rooms_logger.log(name, f"Invalid max_users value detected: {max_users}, settings to: {MAX_USERS_PER_ROOM}")
            max_users = MAX_USERS_PER_ROOM

        if isinstance(password, bytes):
            password = password.decode()

        date_created = timestamp.generate_timestamp()
        last_interaction = date_created

        room = Room(
            name=name,
            admin_key=admin_key,
            date_created=date_created,
            last_interaction=last_interaction,
            max_users=max_users,
            password=password,
            members=[admin_key]
        )

        model = RoomModel(
            name=name,
            admin=admin_key,
            date_created=date_created,
            last_interaction=last_interaction,
            max_users=max_users,
            password=password,
            members=[admin_key]
        )

        db_key = database.rooms_db.insert(model)
        room.db_key = db_key
        logs.rooms_logger.log(room.db_key, f"Created room: {repr(room)}")
        return room
    
    @staticmethod
    def from_model(model: RoomModel) -> "Room":
        """ Build instance of Room object from it's database's model. """
        return Room(
            name=model.name,
            admin_key=model.admin,
            date_created=model.date_created,
            last_interaction=model.last_interaction,
            max_users=model.max_users,
            password=model.password,
            is_locked=model.is_locked,
            members=model.members,
            db_key=create_db_key(model.name)
        )
    
    @staticmethod
    def get_room_by_name(name: str) -> "Room":
        """ Create instance of Room object by room's name. Raises database.KeyNotFound when name was not found. """
        db_key = create_db_key(name)
        if not db_key in database.rooms_db.get_all_keys():
            raise database.KeyNotFound
        model = database.rooms_db.get(db_key)
        return Room.from_model(model)
    
    @staticmethod
    def get_room_by_code(code: str) -> "Room":
        """ Create instance of Room object by it's code. If not found, database.KeyNotFound will be raised. """
        for key in database.rooms_db.get_all_keys():
            if code == key[:CODE_LENGTH]:
                return Room.from_model(database.rooms_db.get(key))
        raise database.KeyNotFound

    @staticmethod
    def get_room_by_key(key: str) -> "Room":
        """ Create instance of Room object by it's database key. database.KeyNotFound might be raised. """
        model = database.rooms_db.get(key)
        return Room.from_model(model)

    def __post_init__(self):
        self.db_key = hashlib.sha1(self.name.encode()).hexdigest()
        self.code = self.db_key[:CODE_LENGTH]
        self.room_data_manager = RoomDataManager(self.db_key)

    def __repr__(self) -> str:
        return f"<ROOM: name={self.name} code={self.code} adminKey={self.admin_key} dbKey={self.db_key} password={bool(self.password)} maxUsers={self.max_users} dateCreated={self.date_created} lastInteraction={self.last_interaction}>"
    
    def get_free_slots(self) -> int:
        """ Calculate available slots where new members can join. """
        free_slots = self.max_users - len(self.members)
        return free_slots

    def is_expired(self) -> bool:
        """ Check if room was inactive for a long time. """
        return timestamp.is_room_expired(self.last_interaction)

    def check_password(self, provided_password: str) -> bool:
        """ 
        Check if provided password matches hashed room password. 
        If room have no password, True will be returned.
        """
        if not self.password:
            return True
        return bcrypt.checkpw(provided_password.encode(), self.password.encode())
    
    def remove_room(self) -> None:
        """ Remove this room from database. Cleanup data. """
        database.rooms_db.delete(self.db_key)
        self.room_data_manager.cleanup()
        logs.rooms_logger.log(self.db_key, f"Removed room: {repr(self)}")

    def add_member_key(self, member_key: str) -> None:
        """ Add new member to the room. """
        self.members.append(member_key)
        database.rooms_db.update(self.db_key, {"members": (member_key)}, iter_append=True)
        logs.rooms_logger.log(self.db_key, f"Added member: {member_key}")

    def remove_member_key(self, member_key: str) -> None:
        """ Remove member from the room. Remove it's files. """
        if member_key not in self.members:
            logs.rooms_logger.log(self.db_key, f"Cannot remove member: {member_key} (not found)")
            return
            
        database.rooms_db.update(self.db_key, {"members": (member_key)}, iter_pop=True)
        self.members.remove(member_key)
        self.room_data_manager.remove_user_dir(member_key)
        logs.rooms_logger.log(self.db_key, f"Removed member: {member_key}")

    def has_member(self, user_key: str) -> bool:
        return user_key in self.members or user_key == self.admin_key

    def get_admin_account(self) -> users.User:
        """ Return admin's users.User() object. """
        return users.User.get_user_by_key(self.admin_key)
    
    def get_members_accounts(self) -> List[users.User]:
        """ Return all members' User objects. """
        return [users.User.get_user_by_key(key) for key in self.members]

    def upload_file(self, member_key: str, file: UploadFile) -> tuple[str, str] | bool:
        """ Upload file to server, return status. """
        return self.room_data_manager.upload_file(member_key, file)

    def set_lock_state(self, state: bool) -> None:
        """ Update room's lock state. """
        self.is_locked = state
        database.rooms_db.update(self.db_key, {"is_locked": state})
        logs.rooms_logger.log(self.db_key, f"Updated room's lock state to: {state}")

    def update_interaction_date(self) -> None:
        """ Update last_interaction field to current date. """
        current_timestamp = timestamp.generate_timestamp()
        self.last_interaction = current_timestamp
        database.rooms_db.update(self.db_key, {"last_interaction": self.last_interaction})
        logs.rooms_logger.log(self.db_key, "Updated last_interaction field.")


def validate_room(function):
    """ Checks provided room existence and if user belongs to room. """
    
    @wraps(function)
    async def wrapper(*args, **kwargs):
        data = kwargs.get("data")
        room = None

        if 'room_code' in data.model_fields:
            try:
                room = Room.get_room_by_code(data.room_code)

            except database.KeyNotFound:
                return ROOM_VALIDATION_FAIL_RESPONSE

        elif 'room_key' in data.model_fields:
            try:
                room = Room.get_room_by_key(data.room_key)

            except database.KeyNotFound:
                return ROOM_VALIDATION_FAIL_RESPONSE

        if 'db_key' in data.model_fields:
            if room and not room.has_member(data.db_key):
                return ROOM_VALIDATION_FAIL_RESPONSE
            
        if room and room.is_expired():
            logs.rooms_logger.log(room.db_key, "Room has expired")
            room.remove_room()
            return ROOM_VALIDATION_FAIL_RESPONSE
        
        return await function(*args, **kwargs)
    return wrapper

