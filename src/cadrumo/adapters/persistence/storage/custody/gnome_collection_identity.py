"""Canonical GNOME collection object path identity."""

from __future__ import annotations

from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError

GNOME_COLLECTION_PATH_PREFIX = "/org/freedesktop/secrets/collection/"
"""Object path prefix for a persistent GNOME collection."""


def _require(condition: bool) -> None:
    if not condition:
        raise AutomationCustodyError(AutomationCustodyCode.INVALID)


def gnome_collection_id(collection: str) -> bytes:
    """Decode only canonical GNOME collection paths, with an exact roundtrip."""
    _require(
        isinstance(collection, str) and collection.startswith(GNOME_COLLECTION_PATH_PREFIX) and len(collection) <= 1024
    )
    encoded = collection[len(GNOME_COLLECTION_PATH_PREFIX) :]
    result = bytearray()
    index = 0
    while index < len(encoded):
        character = encoded[index]
        if character.isascii() and character.isalnum():
            result.append(ord(character))
            index += 1
        else:
            _require(character == "_" and index + 2 < len(encoded))
            hexadecimal = encoded[index + 1 : index + 3]
            _require(all(value in "0123456789abcdef" for value in hexadecimal))
            result.append(int(hexadecimal, 16))
            index += 3
    _require(bool(result) and 0 not in result)
    roundtrip = _collection_path_spelling(result)
    _require(roundtrip == encoded)
    return bytes(result)


def _collection_path_spelling(result: bytearray) -> str:
    roundtrip = "".join(
        chr(value) if chr(value).isascii() and chr(value).isalnum() else f"_{value:02x}" for value in result
    )
    return roundtrip
