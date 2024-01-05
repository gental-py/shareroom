"""
MODULE
    friends.py

DESCRIPTION
    Manage friend requests.
"""
from models.db_models import FriendRequestsModel

from modules import timestamp
from modules import database
from modules import users
from modules import logs

from dataclasses import dataclass
import hashlib


def create_db_key(author: str, target: str) -> str:
    return hashlib.sha1((author + target).encode()).hexdigest()


@dataclass
class FriendRequest:
    author: str
    target: str
    date_sent: int
    db_key: str

    @staticmethod
    def create_request(auhtor_db_key: str, target_db_key: str) -> "FriendRequest":
        """
        Create new friend request. Save it to the DB. 
        This method is not handling database.KeyNotFound error
          so parameters must be validated before.
        """
        date_sent = timestamp.generate_timestamp()

        model = FriendRequestsModel(
            author=auhtor_db_key,
            target=target_db_key,
            date_sent=date_sent
        )

        db_key = database.friend_requests_db.insert(model)

        friend_request_object = FriendRequest(
            author=auhtor_db_key,
            target=target_db_key,
            date_sent=date_sent,
            db_key=db_key
        )

        logs.users_logger.log(db_key, f"Created friend requests from: {auhtor_db_key} to: {target_db_key}")
        return friend_request_object
    
    @staticmethod
    def from_model(model: FriendRequestsModel) -> "FriendRequest":
        """ Build new FriendRequest object from it's database model. """
        return FriendRequest(
            author=model.author,
            target=model.target,
            date_sent=model.date_sent,
            db_key=create_db_key(model.author, model.target)
        )

    @staticmethod
    def get_request_by_key(db_key: str) -> "FriendRequest":
        """ Return instance of FriendRequest build from it's model saved in database. """
        model = database.friend_requests_db.get(db_key)
        return FriendRequest.from_model(model)

    @staticmethod
    def get_requests_to_account(target_db_key: str) -> list["FriendRequest"]:
        """ Return all pending requests sent to specified target. """
        return [
            FriendRequest.from_model(model) 
            for model in database.friend_requests_db.get_all_models()
            if model.target == target_db_key
        ]
        
    def remove(self) -> None:
        """ Remove friend request from DB. """
        logs.users_logger.log(self.db_key, "Removed friend request.")
        database.friend_requests_db.delete(self.db_key)

    def accept(self) -> None:
        """ Append users to their's friends list and remove request. """
        author_account = users.User.get_user_by_key(self.author)
        target_account = users.User.get_user_by_key(self.target)

        author_account.add_friend(target_account.db_key)
        target_account.add_friend(author_account.db_key)

        logs.users_logger.log(self.db_key, "Accepted friend request.")
        self.remove()

    def reject(self) -> None:
        """ Remove this request. """
        logs.users_logger.log(self.db_key, "Rejected friend request.")
        self.remove()
        