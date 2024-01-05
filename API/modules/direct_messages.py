"""
MODULE
    direct_messages.py

DESCRIPTION
    Manage DMs storage and access.
"""
from modules.paths import Path
from modules import timestamp
from modules import database
from modules import users
from modules import logs

from dataclasses import dataclass
import hashlib
import json


MESSAGE_CONTENT_LENGTH_LIMIT = 2048
DMS_DATA_PATH = Path("./data/dms/")

#TODO: ws

class MessageNotFound(Exception):
    """
    This exception occures when an operation on not-existing message happens.
    """


def create_relation_id(user_a_db_key: str, user_b_db_key: str) -> str:
    """ Create two users relation id. It does not matter which db_key comes first. """
    hash_a = sum([ord(char) for char in user_a_db_key])
    hash_b = sum([ord(char) for char in user_b_db_key])
    seed = (hash_a + hash_b)
    return hashlib.sha1(str(seed).encode()).hexdigest()


@dataclass
class Message:
    author: str
    target: str
    content: str
    date_sent: int
    id: str = None
    is_sent: bool = False
    _no_stack: bool = False


    @staticmethod
    def create_message(author: str, target: str, content: str) -> "Message":
        """ Create new Message object. """
        if len(content) > MESSAGE_CONTENT_LENGTH_LIMIT:
            logs.dms_logger.log(f"author:{author}", f"Failed to create Message object: content is too long: ({len(content)})")
            return

        return Message(
            author=author,
            target=target,
            content=content,
            date_sent=timestamp.generate_timestamp(),
            is_sent=False,
        )

    @staticmethod
    def from_saved_dict(saved_dict: dict, no_stack: bool = False) -> "Message":
        """ Build Message object from content generated using as_dict() method. """
        return Message(
            author=saved_dict.get("author"),
            target=saved_dict.get("target"),
            content=saved_dict.get("content"),
            date_sent=saved_dict.get("date_sent"),
            id=saved_dict.get("id"),
            is_sent=True,
            _no_stack=no_stack
        )

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = self.create_id()
        
        self.relation_id = create_relation_id(self.author, self.target) 
        if not self._no_stack:
            self.stack = RelationStackManager.get_stack(self.relation_id)

    def create_id(self) -> str:
        seed = self.author + self.content + str(self.date_sent)
        return hashlib.sha1(seed.encode()).hexdigest()

    def send(self):
        """ Send message to stack. Returns True on success, False on fail. """
        if self.is_sent:
            logs.dms_logger.log(self.id, f"Failed to send message: {self.id} (message already sent)")
            return
        
        self.stack.append_message(self)
        self.is_sent = True
        logs.dms_logger.log(self.id, f"Sent message to relation: {self.relation_id}")

    def edit(self, new_content: str) -> bool:
        """ Edit content of already sent message. Returns status. """
        if len(new_content) > MESSAGE_CONTENT_LENGTH_LIMIT:
            logs.dms_logger.log(self.id, "Failed to edit content: new content is too long.")

        self.content = new_content

        try:
            self.stack.edit_message(self.id, new_content)
            return True
        
        except MessageNotFound:
            return False

    def remove(self) -> bool:
        """ Remove this message from stack. Returns True on success, False on fail. """
        try:
            self.stack.remove_message(self.id)
            return True
        
        except MessageNotFound:
            return False

    def as_dict(self) -> dict:
        """ Convert data of this object into savable dictionary. """
        return {
            "author": self.author,
            "target": self.target,
            "content": self.content,
            "date_sent": self.date_sent,
            "id": self.id
        }


class RelationStackManager:
    """
    Represents stack of messages sent in relation.
    Stack is dynamically saved in dms_data directory.
    Each stack is registered as each message must contain
      it's stack.
    """
    register: dict[str, "RelationStackManager"] = {}


    @staticmethod
    def get_stack(relation_id: str) -> "RelationStackManager":
        """ Get instance of RelationStackManager. Returns existing one or creates new. """
        stack = RelationStackManager.register.get(relation_id)
        if stack is None:
            stack = RelationStackManager(relation_id)
            RelationStackManager.register[relation_id] = stack
            logs.dms_logger.log("(RelationStackManager)", f"Created new instance for relation: {relation_id}")
        return stack

    def __init__(self, relation_id: str) -> None:
        self.relation_id = relation_id
        self.file_path = (DMS_DATA_PATH / relation_id) + ".json"
        self.messages_stack: list[Message] = []
        self.__message_ids_history = [] # Prevents sendMessage spam

        self.__ensure_file()
        self.__load_stack()

    def __ensure_file(self) -> None:
        if not self.file_path.exists():
            self.file_path.touch()
            logs.dms_logger.log(self.relation_id, f"Created relation file: {str(self.file_path)}")

    def __load_stack(self) -> None:
        """ Load stack messages and save them as Message objects to """
        try:
            raw_stack = self.file_path.get_json_content()
            for message_data in raw_stack:
                message = Message.from_saved_dict(message_data, no_stack=True)
                message.stack = self
                self.messages_stack.append(message)

            logs.dms_logger.log(self.relation_id, f"Loaded: {len(self.messages_stack)} messages to stack.")

        except json.JSONDecodeError:
            logs.dms_logger.log(self.relation_id, "Cannot read relation content (JsonDecodeError)")
            self.messages_stack = []

    def __save_stack(self) -> None:
        """ Save object's message_stack to its file. """
        content = [msg.as_dict() for msg in self.messages_stack]
        self.file_path.save_json_content(content)

    def get_message_by_id(self, message_id: str) -> Message:
        """ Get Message object from stack by it's id. """
        for message in self.messages_stack:
            if message.id == message_id:
                return message
            
        logs.dms_logger.log(self.relation_id, f"Message not found in stack: {message_id}")
        raise MessageNotFound

    def append_message(self, message: Message) -> None:
        """ Apennd new message to stack. """
        if message.id in self.__message_ids_history:
            return
 
        self.__message_ids_history.append(message.id)
        if len(self.__message_ids_history) > 5:
            self.__message_ids_history = self.__message_ids_history[:5]

        self.messages_stack.append(message)
        self.__save_stack()
        

    def remove_message(self, message_id: str) -> None:
        """ Find and remove message with provided id. Returns status. """
        message = self.get_message_by_id(message_id)

        self.messages_stack.remove(message)
        self.__save_stack()
        logs.dms_logger.log(self.relation_id, f"Removed message: {message_id} from stack")

    def edit_message(self, message_id: str, new_content: str) -> None:
        message = self.get_message_by_id(message_id)
            
        message.content = new_content
        self.__save_stack()
        logs.dms_logger.log(self.relation_id, f"Edited message: {message_id}")
    
