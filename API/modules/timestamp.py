"""
MODULE
    timestamp.py

DESCRIPTION
    Simple POSIX timestamp generator and parser.
"""
from datetime import datetime as Datetime
from datetime import timedelta


INACTIVE_USER_EXISTENCE_PERIOD_D = 30
INACTIVE_ROOM_EXISTENCE_PERIOD_D = 14
SESSION_EXISTENCE_PERIOD_H = 1


def generate_timestamp(datetime: Datetime = None) -> int:
    """
    Generate timestamp.
    If datetime param is not provided, current datetime will be used.
    """
    if datetime is None:
        return int(Datetime.now().timestamp())
    return int(datetime.timestamp())


def read_timestamp(timestamp: int) -> Datetime:
    """ Read POSIX timestamp. """
    return Datetime.fromtimestamp(timestamp)


def is_room_expired(last_interaction: int) -> bool:
    """ Check if room has expired. """
    base = read_timestamp(last_interaction)
    expiration_dt = base + timedelta(days=INACTIVE_ROOM_EXISTENCE_PERIOD_D)
    return Datetime.now() > expiration_dt 


def is_user_expired(last_interaction: int) -> bool:
    """ Check if user is expired. """
    base = read_timestamp(last_interaction)
    expiration_dt = base + timedelta(days=INACTIVE_USER_EXISTENCE_PERIOD_D)
    return Datetime.now() > expiration_dt
    

def create_session_expiration_datetime(date_created_timestamp: int) -> Datetime:
    """ Create session's remove timestamp based on constant value. """
    base = read_timestamp(date_created_timestamp)
    remove_dt = base + timedelta(hours=SESSION_EXISTENCE_PERIOD_H)
    return remove_dt


def convert_to_readable(timestamp: int) -> str:
    """ Convert timestamp into string with date and time in readable form. """
    dt = read_timestamp(timestamp)
    return f"{dt.day:02d}/{dt.month:02d}/{dt.year} {dt.hour:02d}:{dt.minute:02d}"
