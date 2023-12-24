"""
MODULE
    accounts.py

DESCRIPTION
    Module contains Account object which is interface for user management. 
    Check Account's object docstr for more details.
"""
from modules.database import SET_AFTER_INIT
from modules.logs import SysLogger
from modules import timestamp
from modules import database
from modules import sessions

from dataclasses import dataclass
import hashlib
import bcrypt


def create_db_key(username: str) -> str:
    """ Hash username using SHA1 algorithm. """
    return hashlib.sha1(username.encode()).hexdigest()

def is_username_available(username: str) -> bool:
    """ Check if any saved user has provided username. """
    return not create_db_key(username) in database.users_db.get_all_keys()


@dataclass
class Account:
    """
    User object interface.

    Methods that modifies attributes that are used in database, will automatically
      update user's database entry.  
    That's why it is recommended to use methods instead of manually changing attributes.
      
    To get Account object you can:
      - create new account: `Account.create_account()`
      - build object from database's model: `Account.from_model()`
      - build object using user's name: `Account.get_account_by_name()`
      - build object using user's database key: `Account.get_account_by_key()`
      
      Using default constructor (`init()`) is not recommended.      
    """
    username: str
    password: str
    date_join: int
    last_interaction: int
    active_rooms: list[str]

    # Automatically set after initialization.
    db_key: str = SET_AFTER_INIT

    @staticmethod
    def create_account(username: str, password: str) -> "Account":
        """ Create account and save it to database if name is available. """
        if not is_username_available(username):
            return False
        
        password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        date_join = timestamp.generate_timestamp()

        account = Account(
            username=username,
            password=password,
            date_join=date_join,
            last_interaction=date_join,
            active_rooms=[]
        )

        model = database.UserModel(
            username=username,
            password=password,
            date_join=date_join,
        )

        db_key = database.users_db.insert(model)
        account.db_key = db_key

        SysLogger.success(f"Created account: {username}")
        return account
    
    @staticmethod
    def from_model(user_model: database.UserModel) -> "Account":
        """ Convert database.UserModel into Account. """
        return Account(
            username=user_model.username,
            password=user_model.password,
            date_join=user_model.date_join,
            last_interaction=user_model.last_interaction,
            active_rooms=user_model.active_rooms
        )

    @staticmethod
    def get_account_by_name(username: str) -> "Account":
        """ Get Account object from it's name. Raises database.KeyNotFound when account not found. """
        if is_username_available(username):
            raise database.KeyNotFound
        return Account.from_model(database.users_db.get(create_db_key(username)))

    @staticmethod
    def get_account_by_key(key: str) -> "Account":
        """ Get Account object from it's key. Raises database.KeyNotFound when account not found.  """
        if key not in database.users_db.get_all_keys():
            raise database.KeyNotFound
        return Account.from_model(database.users_db.get(key))
    
    def __post_init__(self) -> None:
        self.db_key = create_db_key(self.username)

    def __repr__(self) -> str:
        return f"<ACCOUNT: username={self.username} dbKey={self.db_key} activeRooms={self.active_rooms} dateJoin={self.date_join}>"

    def check_password(self, provided_password: str) -> bool:
        """ Check if provided_password matches encrypted password. """
        return bcrypt.checkpw(provided_password.encode(), self.password.encode())

    def change_password(self, old_password: str, new_password: str) -> bool:
        """ Change password in database if old_password is correct. """
        if not self.check_password(old_password):
            return False
        
        new_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        database.users_db.update(self.db_key, {"password": new_password})
        SysLogger.info(f"Password changed for: {self.username} ({self.db_key})")
        return True
    
    def delete_account(self) -> None:
        """ Remove account from database. """
        session = self.get_session()
        session.drop()
        database.users_db.delete(self.db_key)

    def add_active_room(self, room_id: str) -> None:
        """ Add new active room and save it to database. """
        if not room_id in self.active_rooms:
            database.users_db.update(self.db_key, {"active_rooms": room_id}, iter_append=True)
            self.active_rooms.append(room_id)

    def remove_active_room(self, room_id: str) -> None:
        """ Remove active room from database. """
        if room_id in self.active_rooms:
            database.users_db.update(self.db_key, {"active_rooms": room_id}, iter_pop=True)
            self.active_rooms.remove(room_id)

    def update_last_interaction_date(self) -> None:
        """ Update last_interaction field in database. """
        self.last_interaction = timestamp.generate_timestamp()
        database.users_db.update(self.db_key, {"last_interaction": self.last_interaction})

    def has_valid_session(self) -> bool:
        """ Check if user has opened and valid session. """
        try:
            session = sessions.Session.get_session_by_key(self.db_key)
            return not session.is_expired()
        
        except database.KeyNotFound:
            return False

    def has_expired_session(self) -> bool:
        """ Check if user has opened expired session. """
        try:
            session = sessions.Session.get_session_by_key(self.db_key)
            return session.is_expired()
        
        except database.KeyNotFound:
            return False

    def get_session(self) -> sessions.Session:
        """ Return existing user's session if exists or create new. """
        try:
            return sessions.Session.get_session_by_key(self.db_key)
        
        except database.KeyNotFound:
            return sessions.Session.create_session(self.db_key)
