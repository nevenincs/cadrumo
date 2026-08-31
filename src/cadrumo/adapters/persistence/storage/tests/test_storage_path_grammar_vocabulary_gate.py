"""Gate: every filesystem-kind grammar compiles against the declared vocabulary.

A :class:`~adapters.persistence.storage.StoragePathDefinition` grammar's
``<placeholder>`` tokens must each resolve to a regex fragment declared in
``_storage_path_grammar.py``'s ``_PLACEHOLDER_PATTERNS`` -- otherwise a real-write
conformance test pinning that key fails with the compiler's own tooling error
("no declared regex fragment") instead of a genuine conformance verdict. This is
exactly how ``secret_index`` shipped for a while: its grammar spelled
``<cadrumo_secret_store_dir>``, a token nobody had declared a fragment for, so the
grammar was declared but unverifiable. This gate makes that class of gap a loud,
named CI failure rather than a silent one discovered only when someone tries to
pin the key.

``<object_key>`` (``secure_objects_table``'s ``db://`` grammar) is correctly out
of scope: it is a `LOGICAL_SQL` logical path, not a filesystem path, and belongs
to a different vocabulary this compiler does not govern.
"""

from __future__ import annotations

from typing import Final

import pytest

from .....tests import assert_grammar_vocabulary_is_declared
from ..namespace_registry import STORAGE_NAMESPACE_REGISTRY
from ..namespace_taxonomy import StoragePathKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_FILESYSTEM_KINDS: Final[frozenset[StoragePathKind]] = frozenset(
    kind for kind in StoragePathKind if kind != StoragePathKind.LOGICAL_SQL
)


def test_the_registry_declares_more_than_a_handful_of_filesystem_kind_grammars() -> None:
    """Non-vacuity floor: a near-empty filtered set would make the gate trivial."""
    filesystem_definitions = [d for d in STORAGE_NAMESPACE_REGISTRY.paths if d.kind in _FILESYSTEM_KINDS]
    assert len(filesystem_definitions) > 10


def test_every_filesystem_kind_grammar_compiles_against_the_declared_vocabulary() -> None:
    failures: list[str] = []
    for definition in STORAGE_NAMESPACE_REGISTRY.paths:
        if definition.kind not in _FILESYSTEM_KINDS:
            continue
        try:
            assert_grammar_vocabulary_is_declared(definition.grammar)
        except AssertionError as exc:
            failures.append(f"{definition.key!r} (grammar {definition.grammar!r}): {exc}")
    assert not failures, "\n".join(failures)


def test_the_logical_sql_kind_is_genuinely_excluded_not_accidentally_empty() -> None:
    """Confirms secure_objects_table (the one LOGICAL_SQL entry) is real and
    would fail the vocabulary check if it weren't filtered -- proving the
    LOGICAL_SQL carve-out is a deliberate exclusion of a real entry, not a
    no-op over an empty set."""
    logical_sql_definitions = [d for d in STORAGE_NAMESPACE_REGISTRY.paths if d.kind == StoragePathKind.LOGICAL_SQL]
    assert len(logical_sql_definitions) >= 1
    (secure_objects_table,) = (d for d in logical_sql_definitions if d.key == "secure_objects_table")
    assert "<object_key>" in secure_objects_table.grammar
    with pytest.raises(AssertionError, match="object_key"):
        assert_grammar_vocabulary_is_declared(secure_objects_table.grammar)


def test_an_undeclared_placeholder_is_caught_by_construction() -> None:
    """Positive control: a synthetic grammar naming a token nobody declared a
    fragment for must raise, proving the check is not vacuously true for
    every string -- reproduces the exact secret_index failure mode."""
    with pytest.raises(AssertionError, match="definitely_not_a_declared_token"):
        assert_grammar_vocabulary_is_declared("<root>/some-dir/<definitely_not_a_declared_token>.json")


def test_a_real_declared_token_does_not_raise_positive_control() -> None:
    """The inverse control: a grammar built only from real declared tokens
    must NOT raise, so the two controls together prove the check
    discriminates rather than always raising or never raising."""
    assert_grammar_vocabulary_is_declared("<root>/blobs/<sha256[:2]>/<sha256>")
