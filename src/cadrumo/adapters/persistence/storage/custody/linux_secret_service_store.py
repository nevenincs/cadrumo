"""Bounded, non-prompting custody in an existing GNOME Secret Service collection.

Immutable secret bytes allocated by SecretStorage and the cryptographic library
cannot be reliably wiped and live only for the current operation.
"""

from __future__ import annotations

import secrets
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, cast

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from pydantic import SecretBytes

from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    NativeSecretBackend,
)
from .....core.async_cleanup import AsyncResourceCleanupError
from .automation_secret_target import require_automation_secret_target
from .gnome_collection_protection import require_protected_gnome_collection
from .linux_secret_bus import DeadlineSecretBus, user_secret_bus_path
from .linux_secret_cleanup import close_secret_bus_after_failure
from .linux_secret_contracts import (
    ALGORITHM,
    COLLECTION_IFACE,
    CONTENT_TYPE,
    GNOME_READ_CONTENT_TYPES,
    ITEM_IFACE,
    MAX_SECRET_SIZE,
    OPERATION_SECONDS,
    PROPERTIES,
    ROOT,
    SERVICE_IFACE,
    SESSION_IFACE,
    invalid_secret_reply,
    secret_object_path,
    secret_reply_body,
)

if TYPE_CHECKING:
    pass


def _attributes(namespace: str, account: str) -> dict[str, str]:
    require_automation_secret_target(namespace, account)
    if sys.platform != "linux":
        raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
    return {
        "application": "cadrumo",
        "namespace": namespace,
        "account": account,
        "xdg:schema": "org.freedesktop.Secret.Generic",
    }


@contextmanager
def _native_bus() -> Generator[DeadlineSecretBus]:
    try:
        bus = DeadlineSecretBus(user_secret_bus_path(), time.monotonic() + OPERATION_SECONDS)
        try:
            bus.verify_owner()
            yield bus
            bus.verify_owner()
        except BaseException as error:
            close_secret_bus_after_failure(bus, error)
            raise
        else:
            bus.close()
    except (AutomationCustodyError, AsyncResourceCleanupError):
        raise
    except (ValueError, TypeError, IndexError, KeyError, OverflowError) as error:
        primary = invalid_secret_reply()
        for name in ("async_cleanup_error", "cleanup_error", "body_error"):
            previous = error.__dict__.get(name)
            if isinstance(previous, BaseException):
                primary.__dict__[name] = previous
        raise primary from None
    except Exception as error:
        primary = AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        for name in ("async_cleanup_error", "cleanup_error", "body_error"):
            previous = error.__dict__.get(name)
            if isinstance(previous, BaseException):
                primary.__dict__[name] = previous
        raise primary from None


def _property(bus: DeadlineSecretBus, path: str, interface: str, name: str, signature: str) -> Any:
    (variant,) = secret_reply_body(bus.call(path, PROPERTIES, "Get", "ss", (interface, name)), 1)
    actual_signature, value = secret_reply_body(variant, 2)
    if actual_signature != signature:
        raise invalid_secret_reply()
    return value


def _unlocked(bus: DeadlineSecretBus, path: str, interface: str) -> None:
    locked = _property(bus, path, interface, "Locked", "b")
    if type(locked) is not bool:
        raise invalid_secret_reply()
    if locked:
        raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)


def _collection(bus: DeadlineSecretBus) -> str:
    (path,) = secret_reply_body(bus.call(ROOT, SERVICE_IFACE, "ReadAlias", "s", ("default",)), 1)
    path = secret_object_path(path, allow_root=True)
    if path == "/":
        raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
    if not path.startswith(ROOT + "/collection/"):
        raise invalid_secret_reply()
    _unlocked(bus, path, COLLECTION_IFACE)
    return path


def _find(bus: DeadlineSecretBus, collection: str, attributes: dict[str, str]) -> str | None:
    _unlocked(bus, collection, COLLECTION_IFACE)
    (paths,) = secret_reply_body(bus.call(collection, COLLECTION_IFACE, "SearchItems", "a{ss}", (attributes,)), 1)
    if not isinstance(paths, list):
        raise invalid_secret_reply()
    matches = cast(list[object], paths)
    if len(matches) > 1:
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    if not matches:
        return None
    path = secret_object_path(matches[0])
    if not path.startswith(collection + "/"):
        raise invalid_secret_reply()
    observed = _property(bus, path, ITEM_IFACE, "Attributes", "a{ss}")
    if not isinstance(observed, dict) or observed != attributes:
        raise invalid_secret_reply()
    _unlocked(bus, path, ITEM_IFACE)
    return path


@contextmanager
def _session(bus: DeadlineSecretBus) -> Generator[Any]:
    from secretstorage.dhcrypto import DH_PRIME_1024, Session

    session = Session()
    try:
        public = session.my_public_key.to_bytes(128, "big")
        output, path = secret_reply_body(
            bus.call(ROOT, SERVICE_IFACE, "OpenSession", "sv", (ALGORITHM, ("ay", public))), 2
        )
        signature, value = secret_reply_body(output, 2)
        if signature != "ay" or not isinstance(value, bytes) or not 1 <= len(value) <= 128:
            raise invalid_secret_reply()
        server_key = int.from_bytes(value, "big")
        if not 1 < server_key < DH_PRIME_1024 - 1:
            raise invalid_secret_reply()
        session.object_path = secret_object_path(path)
        if not session.object_path.startswith(ROOT + "/session/"):
            raise invalid_secret_reply()
        try:
            session.set_server_public_key(server_key)
            yield session
        except BaseException as primary:
            close_secret_bus_after_failure(bus, primary, session_path=session.object_path)
            raise
        else:
            # A failed mutation may already have committed. Surface close failure
            # without replay; the enclosing bus disconnect closes this session.
            bus.call(session.object_path, SESSION_IFACE, "Close")
    finally:
        session.aes_key = None
        session.my_private_key = 0


def _read_item(bus: DeadlineSecretBus, path: str, session: Any) -> bytes:
    (secret,) = secret_reply_body(bus.call(path, ITEM_IFACE, "GetSecret", "o", (session.object_path,)), 1)
    session_path, iv, ciphertext, content_type = secret_reply_body(secret, 4)
    if (
        session_path != session.object_path
        or not isinstance(iv, bytes)
        or len(iv) != 16
        or not isinstance(ciphertext, bytes)
        or not 0 < len(ciphertext) <= MAX_SECRET_SIZE + 16
        or len(ciphertext) % 16
        or not isinstance(content_type, str)
        or content_type not in GNOME_READ_CONTENT_TYPES
    ):
        raise invalid_secret_reply()
    decryptor = Cipher(algorithms.AES(session.aes_key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    raw = unpadder.update(padded) + unpadder.finalize()
    if not 0 < len(raw) <= MAX_SECRET_SIZE:
        raise invalid_secret_reply()
    return raw


class LinuxSecretServiceAutomationSecretStore:
    """Explicit GNOME Secret Service backend with no unlock or prompt execution."""

    backend = NativeSecretBackend.LINUX_DBUS

    def read(self, namespace: str, account: str) -> SecretBytes | None:
        """Read the uniquely matching unlocked item within the existing collection."""
        attributes = _attributes(namespace, account)
        with _native_bus() as bus:
            collection = _collection(bus)
            require_protected_gnome_collection(bus, collection)
            path = _find(bus, collection, attributes)
            if path is None:
                return None
            with _session(bus) as session:
                return SecretBytes(_read_item(bus, path, session))

    def replace(self, namespace: str, account: str, value: SecretBytes) -> None:
        """Atomically replace exact attributes and verify the resulting secret."""
        attributes = _attributes(namespace, account)
        if not isinstance(value, SecretBytes):
            raise invalid_secret_reply()
        raw = value.get_secret_value()
        if not 0 < len(raw) <= MAX_SECRET_SIZE:
            raise invalid_secret_reply()
        with _native_bus() as bus:
            from secretstorage.util import format_secret

            collection = _collection(bus)
            require_protected_gnome_collection(bus, collection)
            _find(bus, collection, attributes)
            with _session(bus) as session:
                properties = {
                    ITEM_IFACE + ".Label": ("s", "Cadrumo automation"),
                    ITEM_IFACE + ".Attributes": ("a{ss}", attributes),
                }
                item, prompt = secret_reply_body(
                    bus.call(
                        collection,
                        COLLECTION_IFACE,
                        "CreateItem",
                        "a{sv}(oayays)b",
                        (properties, format_secret(session, raw, CONTENT_TYPE), True),
                    ),
                    2,
                )
                if secret_object_path(prompt, allow_root=True) != "/":
                    raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
                item = secret_object_path(item)
                observed = _find(bus, collection, attributes)
                if observed != item or not secrets.compare_digest(_read_item(bus, item, session), raw):
                    raise invalid_secret_reply()

    def delete(self, namespace: str, account: str) -> None:
        """Delete the uniquely matching item and verify absence without prompting."""
        attributes = _attributes(namespace, account)
        with _native_bus() as bus:
            collection = _collection(bus)
            require_protected_gnome_collection(bus, collection)
            path = _find(bus, collection, attributes)
            if path is not None:
                (prompt,) = secret_reply_body(bus.call(path, ITEM_IFACE, "Delete"), 1)
                if secret_object_path(prompt, allow_root=True) != "/":
                    raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
            if _find(bus, collection, attributes) is not None:
                raise invalid_secret_reply()
