"""Unit tests for the secure-object row-shape helpers.

Asserts the stored-ancestry parser's encoding invariant: a revision id is
:func:`sha256_hex` output, so the parser accepts lowercase hex only.
"""

from __future__ import annotations

import json

import pytest

from ...errors import StorageValidationError
from .._secure_object_schema import parse_revision_ancestor_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_REVISION_ID = "a" * 64


def test_parse_revision_ancestor_ids_accepts_lowercase_hex() -> None:
    assert parse_revision_ancestor_ids(json.dumps([_REVISION_ID])) == (_REVISION_ID,)


def test_parse_revision_ancestor_ids_accepts_empty_and_absent() -> None:
    assert parse_revision_ancestor_ids(None) == ()
    assert parse_revision_ancestor_ids("") == ()
    assert parse_revision_ancestor_ids(json.dumps([])) == ()


@pytest.mark.parametrize(
    "item",
    [
        "z" * 64,
        "A" * 64,
        "-" * 64,
        f"{'a' * 63} ",
    ],
)
def test_parse_revision_ancestor_ids_rejects_non_hex_of_correct_length(item: str) -> None:
    """A 64-character non-hex string is refused.

    The length-only gate accepted any 64 characters, so an uppercase,
    non-hex, or whitespace-padded value stored in the ancestry column
    parsed cleanly and travelled on as a revision id.
    """
    assert len(item) == 64
    with pytest.raises(StorageValidationError):
        parse_revision_ancestor_ids(json.dumps([item]))


@pytest.mark.parametrize("item", ["a" * 63, "a" * 65])
def test_parse_revision_ancestor_ids_rejects_wrong_length(item: str) -> None:
    with pytest.raises(StorageValidationError):
        parse_revision_ancestor_ids(json.dumps([item]))
