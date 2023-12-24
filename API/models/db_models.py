"""
MODELS
    Database table models.

DESCRIPTION
  Required attributes
    Model must contain three special attributes:
      `__tablename__` - It is used to identify tables.
      `__filepath__` - Relative path to table's save file.
      `__keyprovier__` - Explained in section below.

  Key provider
    Model's key provider defines which value should be hashed to create unique key.
    If key provider is set to "username", model's username attribute will be hashed
      to generate a database key.
    If key provider is set to KEY_AS_UUID4, new uuid4 value will be generated and set as key.
    If key provider starts with !, following name will be used as attribute without
      hashing. It is useful when different information about single object is spread
      between multiple databases. It works like foreign key.

  Define keys
    To define key in model create class variable:
      `key_name: datatype`
    or, to make it optional:
      `key_name: datatype = NOT_REQUIRED`
"""
from dataclasses import dataclass

NOT_REQUIRED = "_NOTREQ"
KEY_AS_UUID4 = "_UUID4KEY"


@dataclass
class UserModel:
    __tablename__ = "users"
    __filepath__ = "./db/users.json"
    __keyprovider__ = "username"
    username: str
    password: str
    date_join: int = NOT_REQUIRED
    last_interaction: int = NOT_REQUIRED
    active_rooms: list = NOT_REQUIRED


@dataclass
class RoomModel:
    __tablename__ = "rooms"
    __filepath__ = "./db/rooms.json"
    __keyprovider__ = "name"
    name: str
    admin: str
    date_created: int
    last_interaction: int
    max_users: int = 5
    password: str = NOT_REQUIRED
    members: list = NOT_REQUIRED
    is_locked: bool = NOT_REQUIRED


@dataclass
class SessionModel:
    __tablename__ = "sessions"
    __filepath__ = "./db/sessions.json"
    __keyprovider__ = "!user_key"
    user_key: str
    session_id: str
    date_created: int
    date_renewed: int = NOT_REQUIRED
