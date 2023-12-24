"""
MODULE
    database.py

DESCRIPTION
    Custom key-value, json based database system.

CODE SUMMARY
  KeyNotFound:
      Exception raised when provided key
      has not been found in database.
  
  Column:
      Parsed form of each Model's entry (row).
  
      Contains:
          - name
          - type
          - default value
  
      Model:  date_join: int = None
      Column: name       type  default
  
      Methods:
          - prepare_value(value)
            Casts value's type to required by Column.
          - validate(value) -> bool
            Validates value's type.
  
  Database:
      Database must be initialized from model which type is called T_Model.
      Each database contains ONLY ONE column, name and it's file path.
      After initialization, DB's object is saved into register.
      Register prevents reinitialization and allows quick DB access.
      You can get initialized Database object by calling Database.get_database(name).
  
      Methods: (only public)
          - insert(data: T_Model) -> str
            Inserts new row to database, returns provided key.
          - update(key: str, changes: dict[str, Any], iter_append: bool = False, iter_pop: bool = True)
            Updates specified in changes parameter values. Append/pop from iterable if flag is set.
          - get(key: str) -> T_Model
            Returns T_Model object with data from database.
          - get_all_models() -> List[T_Model]
            Returns list of all models saved in database.
          - get_all_keys() -> List[str]
            Returns list of all keys saved in database. 
  
  Defined databases:
      users_db, rooms_db, sessions_db
  
"""
from models.db_models import UserModel, RoomModel, SessionModel
from models.db_models import NOT_REQUIRED, KEY_AS_UUID4

from modules.logs import SysLogger
from modules import timestamp

from dataclasses import dataclass, fields, asdict
from typing import Any, List, Iterable
import hashlib
import uuid
import json
import os


UNDEFINED_DEFAULT_VALUE = "_NOTDEF"
SET_AFTER_INIT = "_SET_AFTER_INIT"


class KeyNotFound(Exception):
    """
    Exception raised when provided key
    has not been found in database.
    """
    pass


@dataclass
class Column:
    """
    Representation of single model's key.

    date_join: int = None
    ^^^^^^^^^  ^^^   ^^^^
    name       type_ default
    """
    name: str
    type_: type
    default: Any = UNDEFINED_DEFAULT_VALUE

    def __repr__(self) -> str:
        return f"<COLUMN: name={self.name} type:{self.type_} default:{self.default}>"

    def prepare_value(self, value: Any) -> Any:
        """ Cast value to required type if is not. """
        if value is None or value == NOT_REQUIRED:
            if self.default != UNDEFINED_DEFAULT_VALUE:
                value = self.type_()
            else:
                SysLogger.error("Required value not provided")

        elif not isinstance(value, self.type_):
            value = self.type_(value)

        return value

    def validate(self, value: Any) -> bool:
        """ Check if value's type is same as required. """
        return isinstance(value, self.type_)


class Database[T_Model]:
    """
    Database must be initialized from model which type is called T_Model.
    Each database contains ONLY ONE column, name and it's file path.
    After initialization, DB's object is saved into register.
    Register prevents reinitialization and allows quick DB access.
    You can get initialized Database object by calling Database.get_database(name).
    """
    register: dict[str, "Database"] = {}

    @staticmethod
    def get_database(name: str) -> "Database":
        """ Get initialized Database object. """
        if name not in Database.register:
            return None
        return Database.register.get(name)

    def __init__(self, model: T_Model):
        self.__model: T_Model = model
        self.name: str = ""
        self.filepath: str = ""
        self.key_provider: str = ""
        self.columns: dict[str, Column] = {}

        if self.name in Database.register:
            SysLogger.warn(f"Database: {self.name} is already initialized.")
            self = Database.register.get(self.name)
            return

        self.__build_from_model()
        self.__ensure_db_file()
        Database.register[self.name] = self
        SysLogger.info(f"Build Database object for: {self.name} {repr(self)}")

    def __repr__(self) -> str:
        return f"<DB: name={self.name} keyProvider={self.key_provider} columns={set(self.columns.keys())} file={self.filepath}>"

    def __build_from_model(self) -> None:
        """
        Read and parse all data from DB's model provided at initialization.
        Reads model's properties and turns each key into Column object.
        """
        self.name = self.__model.__tablename__
        self.filepath = self.__model.__filepath__
        self.key_provider = self.__model.__keyprovider__

        object_fields = fields(self.__model)
        for field in object_fields:
            try:
                default_value = getattr(self.__model, field.name)
            except AttributeError:
                default_value = UNDEFINED_DEFAULT_VALUE

            column = Column(field.name, field.type, default_value)
            self.columns[field.name] = column

    def __ensure_db_file(self) -> None:
        """ Check and create blank DB file if not exists. """
        if not os.path.exists(self.filepath):
            with open(self.filepath, "a+") as file:
                SysLogger.info(f"Created DB file: {self.filepath}")
                json.dump({}, file)
                
            return

        try:
            self.__get_db_content()

        except json.JSONDecodeError:
            with open(self.filepath, "r") as file_read:
                corrupted_content = file_read.read()

            with open(self.filepath+".dump", "a+") as dumpfile:
                dumpfile.write(f"\n\n--- DUMP: {timestamp.generate_timestamp()} ---\n" + corrupted_content)

            with open(self.filepath, "w") as file_write:
                SysLogger.error(f"DB file: {self.filepath} was corrupted and content was saved to {self.filepath}.dump")
                json.dump({}, file_write)

    def __get_db_content(self) -> dict:
        """ Get and return database's file content as dict. """
        with open(self.filepath, "r") as file:
            return json.loads(file.read())

    def __save_model(self, model: T_Model, db_key: str = None) -> str:
        """
        Write entry to database. If key is not provided,
        new entry will be created with provided key.
        Returns database key.
        """
        if db_key is None:
            if self.key_provider == KEY_AS_UUID4:
                db_key = uuid.uuid4().hex
            elif self.key_provider.startswith("!"):
                db_key = getattr(model, self.key_provider.removeprefix("!"))
            else:
                key_seed = getattr(model, self.key_provider)
                db_key = hashlib.sha1(key_seed.encode()).hexdigest()

        content = {}
        for column_name, value in asdict(model).items():
            column = self.columns.get(column_name)
            value = column.prepare_value(value)
            if not column.validate(value):
                SysLogger.warn(f"Value: <{value}> did not pass column's validation.")
                if column.default != UNDEFINED_DEFAULT_VALUE:
                    SysLogger.warn(f"Replaced <{value}> with default value.")
                    value = column.default

                else:
                    SysLogger.error(f"Column: {repr(column)} have no default value. Using type's default.")
                    value = column.type_()

            content[column_name] = value

        current_content = self.__get_db_content()
        with open(self.filepath, "w") as file:
            current_content[db_key] = content
            json.dump(current_content, file, indent=2, separators=(',', ': '), ensure_ascii=True)

        return db_key

    def __write_content(self, content: dict) -> None:
        """ Write content to DB file. """
        with open(self.filepath, "w") as file:
            json.dump(content, file, indent=2, separators=(',', ': '), ensure_ascii=True)

    def insert(self, data: T_Model) -> str:
        """ Insert new entry to database. Returns key. """
        return self.__save_model(data)

    def update(self, key: str, changes: dict[str, Any] | Any, iter_append: bool = False, iter_pop: bool = False) -> None:
        """
        Update specified keys in entry.
        changes parameter does not have to contain all keys with values
          but only changed ones.

        If iter_append is set to True additional data will be appended 
          to the original instead of completely replacing list with new data.

        If iter_pop is set to True value will be popped from current list
          instead of being completely replacing list new data.
        """
        if iter_append and iter_pop:
            SysLogger.error("method called with both iter_append and iter_pop flags!")
            return
        
        model_object = self.get(key)
        for key_name, value in changes.items():
            if not hasattr(model_object, key_name):
                SysLogger.error(f"Cannot change value of {key_name} (key not found)")
                continue

            if iter_append and isinstance(value, Iterable):
                current_data = getattr(model_object, key_name)
                if isinstance(current_data, list):
                    value = current_data + [value]

            if iter_pop and isinstance(value, Iterable):
                current_data = getattr(model_object, key_name)
                if isinstance(current_data, list):
                    if value in current_data:
                        current_data.remove(value)
                        value = current_data
                    else:
                        SysLogger.error(f"Cannot iter_pop {value} from {key_name} (not found)")
                        return
                    
            setattr(model_object, key_name, value)
        self.__save_model(model_object, key)

    def delete(self, key: str) -> None:
        """ Delete key-value pair from database. """
        db_content = self.__get_db_content()
        if key not in db_content:
            raise KeyNotFound
        
        db_content.pop(key)
        self.__write_content(db_content)

    def get(self, key: str) -> T_Model:
        """
        Get object from database by it's key.
        Raises KeyNotFound error if key is invalid.
        """
        db_content = self.__get_db_content()
        object_content = db_content.get(key)
        if object_content is None:
            SysLogger.error(f"({self.name}) KeyNotFound: {key}")
            raise KeyNotFound

        model_object = self.__model(**object_content)
        model_object._key = key
        return model_object

    def get_all_models(self) -> List[T_Model]:
        """ Get all models saved in database. """
        objects = []
        db_content = self.__get_db_content()
        for key, content in db_content.items():
            model = self.__model(**content)
            model._key = key
            objects.append(model)

        return objects
    
    def get_all_keys(self) -> List[str]:
        """ Get all keys saved in database. """
        return list(self.__get_db_content().keys())


users_db = Database(UserModel)
rooms_db = Database(RoomModel)
sessions_db = Database(SessionModel)
