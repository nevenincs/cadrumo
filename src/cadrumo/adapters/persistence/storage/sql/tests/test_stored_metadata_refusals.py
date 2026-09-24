"""Malformed stored secure-object metadata is refused, never quietly accepted.

These helpers read columns back off disk: the raw payload bytes and the
revision-ancestry chain. Everything they parse has already survived one trip
through storage, so what reaches them is whatever the database actually holds
-- a truncated write, a hand-edited row, a column written by something other
than this code.

Coverage put the module at 70%, and the unexecuted lines were the refusals
themselves: every branch that raises on a shape the format cannot produce.
The accepting paths were exercised, so the module looked tested while the
question it exists to answer -- what happens when the bytes are wrong -- had
never been asked.

``no-legacy-compatibility`` is explicit about the direction: refuse, do not
tolerate. An ancestry column that will not parse is corruption now, and
returning an empty chain for it would silently erase a revision's lineage
rather than report that it cannot be read.
"""

from __future__ import annotations

import json

import pytest

from ...errors import StorageValidationError
from .._secure_object_schema import (
    build_revision_ancestor_ids,
    database_bytes,
    parse_revision_ancestor_ids,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_REVISION = "a" * 64
_OTHER_REVISION = "b" * 64


def test_an_unparseable_ancestry_column_is_refused() -> None:
    """DISCRIMINATING: corruption reported, not read as an empty lineage."""
    with pytest.raises(StorageValidationError, match="ancestry_json"):
        parse_revision_ancestor_ids("{not json")


def test_an_ancestry_column_that_is_not_a_list_is_refused() -> None:
    """Valid JSON of the wrong shape is still not an ancestry chain."""
    with pytest.raises(StorageValidationError, match="ancestry_shape"):
        parse_revision_ancestor_ids(json.dumps({"revision": _REVISION}))


def test_an_ancestry_entry_that_is_not_a_revision_id_is_refused() -> None:
    """DISCRIMINATING: a well-formed list whose members are not revisions.

    This is the shape closest to valid, and the one a partial write or a
    hand-edit produces. Accepting it would put a value into a lineage chain
    that no revision can ever match.
    """
    with pytest.raises(StorageValidationError, match="ancestry_shape"):
        parse_revision_ancestor_ids(json.dumps([_REVISION, "not-a-revision-id"]))


def test_an_absent_ancestry_column_is_an_empty_chain() -> None:
    """ANTI-TAUTOLOGY: absence is a real answer, distinct from corruption.

    A first revision has no ancestry, and its column is NULL or empty. If that
    raised, every initial write would look corrupt -- and if the refusals
    above were satisfied by "everything raises", this is what would catch it.
    """
    assert parse_revision_ancestor_ids(None) == ()
    assert parse_revision_ancestor_ids("") == ()
    assert parse_revision_ancestor_ids(json.dumps([_REVISION]).encode("utf-8")) == (_REVISION,)


def test_the_ancestry_chain_does_not_repeat_its_direct_parent() -> None:
    """The builder prepends the parent and drops it from the inherited tail."""
    assert build_revision_ancestor_ids(None, ()) == ()
    assert build_revision_ancestor_ids(_REVISION, ()) == (_REVISION,)
    assert build_revision_ancestor_ids(_REVISION, (_OTHER_REVISION, _REVISION)) == (_REVISION, _OTHER_REVISION)


def test_database_bytes_refuses_a_value_it_cannot_normalise() -> None:
    """The text-query sibling of the payload coercion, same failure direction."""
    assert database_bytes(b"x") == b"x"
    assert database_bytes("x") == b"x"

    with pytest.raises(TypeError, match="bytes-like or str"):
        database_bytes(object())
