"""
MODULE
    revision.py

DESCRIPTION
    Run scheduled tasks to remove expired rooms and users.
"""
import threading
import schedule
import time

from modules import database
from modules import users
from modules import rooms
from modules import logs


REVISION_COOLDOWN_H = 6


def check_all_users():
    """ Find and remove all expired users. """
    logs.users_logger.log("REVISION", "Revision started...")

    for user_model in database.users_db.get_all_models():
        user = users.User.from_model(user_model)
        if user.is_expired():
            logs.users_logger.log("REVISION", f"Revision found expired user: {repr(user)}")
            
            for room_key in user.active_rooms:
                room = rooms.Room.get_room_by_key(room_key)
                room.remove_member_key(user.db_key)

            user.delete_user()

def check_all_rooms():
    """ Find and remove all expired rooms. """
    logs.rooms_logger.log("REVISION", "Revision started...")

    for room_model in database.rooms_db.get_all_models():
        room = rooms.Room.from_model(room_model)
        if room.is_expired():
            logs.rooms_logger.log("REVISION", f"Revision found expired room: {repr(room)}")

            room.remove_room()


schedule.every(REVISION_COOLDOWN_H).hours.do(check_all_users)
schedule.every(REVISION_COOLDOWN_H).hours.do(check_all_rooms)

def pending_tasks_runner():
    while True:
        schedule.run_pending()
        time.sleep(1)

def run_scheduled_tasks():
    """ Run checkers in thread. """
    runner = threading.Thread(target=pending_tasks_runner, daemon=True)
    runner.start()
