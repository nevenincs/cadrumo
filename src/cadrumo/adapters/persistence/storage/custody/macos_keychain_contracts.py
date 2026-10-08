"""Typed native Keychain values, authorization roles, and exact platform constants."""

from __future__ import annotations

import threading
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Literal, Protocol

SECURITY = "/System/Library/Frameworks/Security.framework/Security"


CORE_FOUNDATION = "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"


MAX_SECRET_BYTES = 2560


UTF8 = 0x08000100


SUCCESS = 0


NOT_FOUND = -25300


DUPLICATE = -25299


INTERACTION_NOT_ALLOWED = -25308


AUTH_FAILED = -25293


INTERACTION_REQUIRED = -25315


UI_LOCK = threading.RLock()


DESCRIPTION = "Cadrumo automation"


RESTRICTED_AUTHORIZATIONS = frozenset({"decrypt", "sign", "mac", "derive", "export_clear", "export_wrapped"})


SAFE_AUTHORIZATIONS = frozenset({"encrypt"})


OWNER_AUTHORIZATIONS = frozenset({"change_acl"})


INTEGRITY_AUTHORIZATIONS = frozenset({"integrity"})


PARTITION_AUTHORIZATIONS = frozenset({"partition"})


AUTHORIZATIONS = {
    "kSecACLAuthorizationDecrypt": "decrypt",
    "kSecACLAuthorizationSign": "sign",
    "kSecACLAuthorizationMAC": "mac",
    "kSecACLAuthorizationDerive": "derive",
    "kSecACLAuthorizationExportClear": "export_clear",
    "kSecACLAuthorizationExportWrapped": "export_wrapped",
    "kSecACLAuthorizationEncrypt": "encrypt",
    "kSecACLAuthorizationChangeACL": "change_acl",
    "kSecACLAuthorizationIntegrity": "integrity",
    "kSecACLAuthorizationPartitionID": "partition",
}


KeychainAclRole = Literal["restricted", "safe", "owner", "integrity", "partition"]


@dataclass(frozen=True)
class KeychainItemIdentity:
    """Exact service, account and verified login-Keychain coordinates of one item."""

    namespace: str
    account: str
    keychain_path: str


@dataclass(frozen=True, repr=False)
class KeychainItem:
    """Verified native item binding, access state and ephemeral credential bytes."""

    identity: KeychainItemIdentity
    account_access: bool
    data: bytes


class KeychainApi(Protocol):
    """Native decisions isolated for portable protocol tests, never a fallback."""

    def session(self) -> AbstractContextManager[str]:
        """Own a verified noninteractive login-Keychain session and expose its exact path."""
        ...

    def read(self, identity: KeychainItemIdentity) -> KeychainItem | None:
        """Read one exact item after native binding and access admission."""
        ...

    def update(self, identity: KeychainItemIdentity, value: bytes) -> int:
        """Update one exact native item and return its original status."""
        ...

    def add(self, identity: KeychainItemIdentity, value: bytes) -> int:
        """Create one exact native item with an owned verified access description."""
        ...

    def delete(self, identity: KeychainItemIdentity) -> int:
        """Delete only the exact native item selected by its verified identity."""
        ...


class NativeKeychainFunction(Protocol):
    """An ABI-bound native function with explicit result and argument declarations."""

    argtypes: list[object]
    restype: object

    def __call__(self, *args: object) -> int | None:
        """Invoke the already bound native function with its typed ABI."""
        ...
