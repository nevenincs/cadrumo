from enum import Enum, IntEnum, IntFlag
from typing import Any

class HeaderFields(IntEnum):
    error_name = 4
    reply_serial = 5
    sender = 7

class MessageFlag(IntFlag):
    no_auto_start = 2

class MessageType(Enum):
    method_return = 2
    error = 3

class Header:
    flags: MessageFlag
    message_type: MessageType
    fields: dict[HeaderFields, Any]

class Message:
    header: Header
    body: tuple[Any, ...]

    def serialise(self, serial: int) -> bytes: ...

class Parser:
    def get_next_message(self) -> Message | None: ...
    def add_data(self, data: bytes) -> None: ...

class DBusAddress:
    def __init__(
        self,
        object_path: str,
        bus_name: str | None = None,
        interface: str | None = None,
    ) -> None: ...

def new_method_call(
    remote_obj: DBusAddress,
    method: str,
    signature: str | None = None,
    body: tuple[Any, ...] = (),
) -> Message: ...
