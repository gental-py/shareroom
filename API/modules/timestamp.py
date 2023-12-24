"""
MODULE
    timestamp.py

DESCRIPTION
    Simple POSIX timestamp generator and parser.
"""
from datetime import datetime as Datetime
from datetime import timedelta


ROOM_EXISTENCE_PERIOD_H = 24
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


def create_room_remove_timestamp(date_created_timestamp: int) -> int:
    """ Create room's remove timestamp based on constant value. """
    base = read_timestamp(date_created_timestamp)
    remove_dt = base + timedelta(hours=ROOM_EXISTENCE_PERIOD_H)
    return generate_timestamp(remove_dt)


def create_session_expiration_datetime(date_created_timestamp: int) -> Datetime:
    """ Create session's remove timestamp based on constant value. """
    base = read_timestamp(date_created_timestamp)
    remove_dt = base + timedelta(hours=SESSION_EXISTENCE_PERIOD_H)
    return remove_dt


def convert_to_readable(timestamp: int) -> str:
    """ Convert timestamp into string with date and time in readable form. """
    dt = read_timestamp(timestamp)
    return f"{dt.day:02d}/{dt.month:02d}/{dt.year} {dt.hour:02d}:{dt.minute:02d}"
