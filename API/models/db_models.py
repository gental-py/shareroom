"""
MODELS
    Database table models.

DESCRIPTION
    Model must contain three special attributes:
      `__tablename__` - It is used to identify tables.
      `__filepath__` - Relative path to table's save file.
      `__keyprovider__` - Explained in section below.

    Model's key provider defines which value should be hashed to create unique key.
    If key provider is set to "username", model's username attribute will be hashed
      to generate a database key.
    If key provider is set to KEY_AS_UUID4, new uuid4 value will be generated and set as key.
    If key provider starts with !, following name will be used as attribute without
      hashing. It is useful when different information about single object is spread
      between multiple databases. It works like foreign key.
    If key provider includes "+", values of multiple attributes will be concatenated to
      and then hashed. 
    
    Key provider can have ! and + at once. (`"!attr_a+attr_b"`) 
      
    To define key in model create class variable:
      `key_name: datatype`
    or, to make it optional:
      `key_name: datatype = NOT_REQUIRED`
"""
from modules.paths import Path

from dataclasses import dataclass
from typing import Type


NOT_REQUIRED = "_NOTREQ"
KEY_AS_UUID4 = "_UUID4KEY"


class DBModel:
    dbs_path: Path = Path("./")

    @staticmethod
    def model(
        name: str, 
        key_provider: str, 
        file_path: str = None, 
        allow_invalid_values: bool = None, 
        dump_on_error: bool = None
    ):
        def wrapper(cls):
            nonlocal file_path
            if file_path is None:
                file_path = DBModel.dbs_path / name + ".json"

            nonlocal allow_invalid_values
            if allow_invalid_values is None:
                allow_invalid_values = False
                
            nonlocal dump_on_error
            if dump_on_error is None:
                dump_on_error = False

            db_model = DBModel(
                name, 
                key_provider, 
                file_path, 
                allow_invalid_values, 
                dump_on_error, 
                cls
            )
            cls.__dbmodel__ = db_model
            return dataclass(cls)
        return wrapper
    
    def __call__(self, *args, **kwargs):
        return self.model_cls(*args, **kwargs)

    def __init__(self, name: str, key_provider: str, file_path: str, allow_invalid_values: bool, dump_on_error: bool, model_cls: Type) -> None:
        self.name = name
        self.key_provider = key_provider
        self.file_path = file_path
        self.allow_invalid_values = allow_invalid_values
        self.dump_on_error = dump_on_error

        self.model_cls = model_cls
        self.fields = self.model_cls.__annotations__
        
    def __repr__(self) -> str:
        model_class_name = self.__class__.__name__
        return f"<DBModel: name={self.name} key_provider={self.key_provider} file_path={self.file_path} model_class_name={model_class_name} allow_invalid_values={self.allow_invalid_values} fields={self.fields}>"


DBModel.dbs_path = Path("./data/db/")

@DBModel.model("users", "username", allow_invalid_values=True, dump_on_error=True)
class UserModel:
    username: str
    password: str
    allow_friend_request: bool = True
    friends: list = NOT_REQUIRED
    date_join: int = NOT_REQUIRED
    last_interaction: int = NOT_REQUIRED
    active_rooms: list = NOT_REQUIRED


@DBModel.model("rooms", "name", allow_invalid_values=True, dump_on_error=True)
class RoomModel:
    name: str
    admin: str
    date_created: int
    last_interaction: int
    max_users: int = 5
    is_locked: bool = False
    password: str = NOT_REQUIRED
    members: list = NOT_REQUIRED


@DBModel.model("sessions", "!user_key", allow_invalid_values=True, dump_on_error=True)
class SessionModel:
    user_key: str
    session_id: str
    date_created: int
    date_renewed: int = NOT_REQUIRED


@DBModel.model("friend_requests", "author+target", allow_invalid_values=True, dump_on_error=True)
class FriendRequestsModel:
    author: str
    target: str
    date_sent: int
