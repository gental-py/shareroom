"""
MODELS
    POST requests data models.

DESCRIPTION
  Naming
    Request model should start with `M_` representing `Model`
    and name of request they are used in. For easier code modifications
    Each POST request should have its own model even if it has the same
    attributes as other.

  Keys
    Requests sent from client must contain exactly the same keys.
      `key_name: datatype`
    or, to make it optional
      `key_name: Optional[datatype]`

  _Auth
    The _Auth class contains data used in authorization process.
    You can inherit from this class to ensure auth data in request.
"""
from pydantic import BaseModel
from typing import Optional


class _Auth:
    db_key: str
    session_id: str


# -- ACCOUNTS --

class M_CreateAccount(BaseModel):
    username: str
    password: str

class M_ChangeAccountPassword(_Auth, BaseModel):
    current: str
    new: str

class M_DeleteAccount(_Auth, BaseModel):
    password: str

class M_AccountLogin(BaseModel):
    username: str
    password: str

class M_AccountData(_Auth, BaseModel):
    pass

class M_AccountLogout(_Auth, BaseModel):
    pass


# -- ROOMS --

class M_CreateRoom(_Auth, BaseModel):
    name: str
    max_users: int = 5
    password: Optional[str] = None

class M_JoinRoom(_Auth, BaseModel):
    room_code: str
    password: Optional[str] = None

class M_UploadFile(_Auth, BaseModel):
    room_code: str

class M_ConnectRoom(_Auth, BaseModel):
    room_code: str

class M_LockRoom(_Auth, BaseModel):
    room_code: str
    state: int

class M_DownloadFile(_Auth, BaseModel):
    room_code: str
    fileid: str

class M_AddMessage(_Auth, BaseModel):
    room_code: str
    content: str

class M_LeaveRoom(_Auth, BaseModel):
    room_code: str

class M_KickMember(_Auth, BaseModel):
    room_code: str
    member_name: str

class M_RemoveFile(_Auth, BaseModel):
    room_code: str
    fileid: str
