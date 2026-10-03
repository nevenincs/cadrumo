"""Strict GNOME Secret Service message shapes and protocol constants."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
)

if TYPE_CHECKING:
    pass


SERVICE = "org.freedesktop.secrets"


ROOT = "/org/freedesktop/secrets"


SERVICE_IFACE = "org.freedesktop.Secret.Service"


COLLECTION_IFACE = "org.freedesktop.Secret.Collection"


ITEM_IFACE = "org.freedesktop.Secret.Item"


SESSION_IFACE = "org.freedesktop.Secret.Session"


PROPERTIES = "org.freedesktop.DBus.Properties"


BUS = "org.freedesktop.DBus"


BUS_PATH = "/org/freedesktop/DBus"


ALGORITHM = "dh-ietf1024-sha256-aes128-cbc-pkcs7"


CONTENT_TYPE = "application/octet-stream"


# GNOME returns text/plain for encrypted secret bytes regardless of the input MIME.
GNOME_READ_CONTENT_TYPES = frozenset({CONTENT_TYPE, "text/plain"})


MAX_SECRET_SIZE = 2560


MAX_REPLY_BYTES = 65536


OPERATION_SECONDS = 5.0


PATH_PATTERN = re.compile(r"/(?:[A-Za-z0-9_]+/)*[A-Za-z0-9_]+\Z")


def invalid_secret_reply() -> AutomationCustodyError:
    """Create the typed refusal for a malformed native secret reply."""
    return AutomationCustodyError(AutomationCustodyCode.INVALID)


def secret_object_path(value: object, *, allow_root: bool = False) -> str:
    """Admit only bounded canonical D-Bus object paths."""
    if allow_root and value == "/":
        return "/"
    if not isinstance(value, str) or len(value) > 1024 or not PATH_PATTERN.fullmatch(value):
        raise invalid_secret_reply()
    return value


def secret_reply_body(value: object, length: int) -> tuple[Any, ...]:
    """Require the exact tuple shape expected by a protocol operation."""
    if not isinstance(value, tuple):
        raise invalid_secret_reply()
    result = cast(tuple[Any, ...], value)
    if len(result) != length:
        raise invalid_secret_reply()
    return result
