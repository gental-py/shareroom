"""
MODULE
    sessions.py

DESCRIPTION
    Manage user sessions.
"""
from models.db_models import SessionModel

from modules.database import SET_AFTER_INIT
from modules import timestamp
from modules import database
from modules import users
from modules import logs

from fastapi.responses import JSONResponse
from datetime import datetime as Datetime
from dataclasses import dataclass
from functools import wraps
from uuid import uuid4


VALIDATION_FAIL_ERRMSG = "@VALIDATION_FAIL"
VALIDATION_FAIL_RESPONSE = JSONResponse({"status": False, "err_msg": VALIDATION_FAIL_ERRMSG}, 400)


def remove_expired_sessions() -> None:
    """
    This function is meant to run at startup.
    It removes all left sessions that are expired.
    """
    removed_amount = 0

    for session_model in database.sessions_db.get_all_models():
        session = Session.from_model(session_model)
        if session.is_expired():
            logs.sessions_logger.log(session.session_id, "Removed expired session")
            session.drop()
            removed_amount += 1 

    if removed_amount > 0:
        logs.sessions_logger.log("-", f"Removed: {removed_amount} expired sessions")


@dataclass
class Session:
    user_key: str
    session_id: str
    date_created: int
    date_renewed: int
    date_expire: Datetime = SET_AFTER_INIT


    @staticmethod
    def from_model(model: SessionModel) -> "Session":
        """ Build Session object from it's database model. """
        return Session(
            user_key=model.user_key,
            session_id=model.session_id,
            date_created=model.date_created,
            date_renewed=model.date_renewed            
        )
    
    @staticmethod
    def create_session(user_key: str) -> "Session":
        date_created = timestamp.generate_timestamp()
        session_id = uuid4().hex

        model = SessionModel(
            user_key=user_key,
            session_id=session_id,
            date_created=date_created,
            date_renewed=date_created
        )

        session = Session(
            user_key=user_key,
            session_id=session_id,
            date_created=date_created,
            date_renewed=date_created
        )

        database.sessions_db.insert(model)
        logs.sessions_logger.log(user_key, f"Created session: {session_id}")
        return session
    
    @staticmethod
    def get_session_by_key(user_key: str) -> "Session":
        """
        Get Session object from it's database's user_key
        Raises database.KeyNotFound error at invalid user_key 
        """
        return Session.from_model(database.sessions_db.get(user_key))

    def __post_init__(self):
        if self.date_expire == SET_AFTER_INIT:
            self.date_expire = timestamp.create_session_expiration_datetime(self.date_renewed)
        
    def is_expired(self) -> bool:
        """ Check if session is expired. """
        return Datetime.now() > self.date_expire
    
    def renew(self) -> None:
        """ Renew session. Set date_renewed to current date. """
        self.date_renewed = timestamp.generate_timestamp()
        self.date_expire = timestamp.create_session_expiration_datetime(self.date_renewed)
        database.sessions_db.update(self.user_key, {"date_renewed": self.date_renewed})
        logs.sessions_logger.log(self.user_key, f"Renewed session: {self.session_id}")
    
    def drop(self) -> None:
        """ Remove this session from database. """
        database.sessions_db.delete(self.user_key)
        logs.sessions_logger.log(self.user_key, f"Session dropped: {self.session_id}")


def _validate_auth_data(db_key: str, session_id: str) -> bool:
    """ Check AuthData validity. """
    if db_key is None:
        logs.sessions_logger.log(session_id, "Cannot validate user session (db_key not provided)")
        return False
    
    try:
        account = users.User.get_user_by_key(db_key)

    except database.KeyNotFound:
        logs.sessions_logger.log(session_id, "Cannot validate user session (invalid db_key)")
        return False

    session = account.get_session()

    if session.session_id != session_id:
        logs.sessions_logger.log(session_id, "Cannot validate user session (ids not equal)")
        return False

    if session.is_expired():
        session.drop()
        logs.sessions_logger.log(session.user_key, f"Session: {session_id} was used but is expired.")
        return False

    session.renew()
    account.update_last_interaction_date()
    return True

def validate_client(function):
    @wraps(function)
    async def wrapper(*args, **kwargs):
        data = kwargs.get("data")
        
        status = _validate_auth_data(data.db_key, data.session_id)
        if not status:
            return VALIDATION_FAIL_RESPONSE
        
        # await NotificationServer.flush_buffer(data.db_key)
        return await function(*args, **kwargs)
    return wrapper
