"""
MODULE
    users.py

DESCRIPTION
    Module contains User object which is interface for user management. 
"""
from models.db_models import UserModel

from modules.database import SET_AFTER_INIT
from modules import timestamp
from modules import database
from modules import sessions
from modules import logs

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
class User:
    """
    User object interface.

    Methods that modifies attributes that are used in database, will automatically
      update user's database entry.  
    That's why it is recommended to use methods instead of manually changing attributes.
      
    To get User object you can:
      - create new user: `User.create_user()`
      - build object from database's model: `User.from_model()`
      - build object using user's name: `User.get_user_by_name()`
      - build object using user's database key: `User.get_user_by_key()`
      
      Using default constructor (`init()`) is not recommended.      
    """
    username: str
    password: str
    date_join: int
    last_interaction: int
    allow_friend_request: bool
    friends: list[str]
    active_rooms: list[str]

    # Automatically set after initialization.
    db_key: str = SET_AFTER_INIT

    @staticmethod
    def create_user(username: str, password: str) -> "User":
        """ Create account and save it to database if name is available. """
        if not is_username_available(username):
            return False
        
        password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        date_join = timestamp.generate_timestamp()

        user = User(
            username=username,
            password=password,
            date_join=date_join,
            allow_friend_request=True,
            last_interaction=date_join,
            friends=[],
            active_rooms=[],
        )

        model = UserModel(
            username=username,
            password=password,
            date_join=date_join,
            allow_friend_request=True,
            friends=[]
        )

        db_key = database.users_db.insert(model)
        user.db_key = db_key

        logs.users_logger.log(db_key, f"Created account: {username}")
        return user
    
    @staticmethod
    def from_model(user_model: UserModel) -> "User":
        """ Convert dbmodels.UserModel into User(). """
        print(f"user_model.active_rooms ({user_model.username}): ", user_model.active_rooms)
        return User(
            username=user_model.username,
            password=user_model.password,
            date_join=user_model.date_join,
            last_interaction=user_model.last_interaction,
            active_rooms=user_model.active_rooms,
            friends=user_model.friends,
            allow_friend_request=user_model.allow_friend_request
        )

    @staticmethod
    def get_user_by_name(username: str) -> "User":
        """ Get User object from it's name. Raises database.KeyNotFound when user not found. """
        if is_username_available(username):
            raise database.KeyNotFound
        return User.from_model(database.users_db.get(create_db_key(username)))

    @staticmethod
    def get_user_by_key(key: str) -> "User":
        """ Get User object from it's key. Raises database.KeyNotFound when user not found.  """
        if key not in database.users_db.get_all_keys():
            raise database.KeyNotFound
        return User.from_model(database.users_db.get(key))
    
    def __post_init__(self) -> None:
        self.db_key = create_db_key(self.username)

    def __repr__(self) -> str:
        return f"<USER: username={self.username} dbKey={self.db_key} activeRooms={self.active_rooms} dateJoin={self.date_join}>"

    def check_password(self, provided_password: str) -> bool:
        """ Check if provided_password matches encrypted password. """
        return bcrypt.checkpw(provided_password.encode(), self.password.encode())

    def change_password(self, old_password: str, new_password: str) -> bool:
        """ Change password in database if old_password is correct. """
        if not self.check_password(old_password):
            return False
        
        new_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        database.users_db.update(self.db_key, {"password": new_password})
        logs.users_logger.log(self.db_key, f"Password changed for: {self.username}")
        return True
    
    def delete_user(self) -> None:
        """ Remove user from database. """
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

    def set_allow_friend_requests(self, state: bool) -> None:
        logs.users_logger.log(self.db_key, f"User: {self.db_key} updated allow_friend_requests state to: {state}")
        self.allow_friend_request = state
        database.users_db.update(self.db_key, {"allow_friend_requests": state})

    def add_friend(self, friend_db_key: str) -> None:
        """ Append friend's db_key to friends list and save changes to DB. """
        if friend_db_key not in self.friends:
            self.friends.append(friend_db_key)

        database.users_db.update(self.db_key, {"friends": friend_db_key}, iter_append=True)

    def remove_friend(self, friend_db_key: str) -> None:
        """ Remove friend's db_key from friends list and save changes to DB. """
        if friend_db_key in self.friends:
            self.friends.remove(friend_db_key)

        database.users_db.update(self.db_key, {"friends": friend_db_key}, iter_pop=True)

    def is_expired(self) -> bool:
        """ Check if user hasn't interacted for a long time. """
        if self.last_interaction == 0:
            return timestamp.is_user_expired(self.date_join)
        return timestamp.is_user_expired(self.last_interaction)

