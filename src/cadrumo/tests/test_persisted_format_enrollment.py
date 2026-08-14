"""Every persisted format declares how long its bytes must stay readable.

The per-tier lineage gates prove that each ENROLLED format's floor tracks the
regime. This gate owns the question they cannot ask: is every persisted format
enrolled at all?

The enrollment invariant in the central compatibility gate runs one way — it
asserts that every frozen floor names a live tier. Nothing asserted the
converse, and nothing enumerated the persisted formats, so three formats
carrying their own schema version and their own refusal branch reached main
with no durability declaration: the persisted profile session, the login
throttle sidecar, and the config-reset journal. Two landed inside a single
eight-day window. A gate that only validates what is already declared cannot
see that class of gap by construction.

So this gate ENUMERATES rather than allowlists. It discovers the live
persisted-format set from the storage registry — the declared inventory of the
on-disk hierarchy — and fails on any format absent from
:data:`~cadrumo.core.PERSISTED_FORMATS`. A new format does not pass by
omission; it fails until someone decides whether its bytes are taxpayer data
that must survive every future version, or operational state the application
rebuilds on demand. That decision is the whole point: a durability floor is a
promise to keep reading old bytes, and promising it about a session sidecar is
an obligation rather than a guarantee.
"""

from __future__ import annotations

from typing import Final

import pytest

from ..adapters.persistence.storage import (
    STORAGE_NAMESPACE_REGISTRY,
    SecureObjectNamespaceDefinition,
    StoragePathKind,
)
from ..core import (
    PERSISTED_FORMATS,
    PersistedFormatClass,
    StorageCategory,
    stale_persisted_format_declarations,
    storage_location,
    undeclared_persisted_formats,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Formats that are not single on-disk files and so carry no ``FILE`` path
#: definition: the encrypted SQL secure-object table, the portable profile
#: bundle (a transport payload), and the sealed archive (an export artefact).
#: Each is a real persisted format with its own tier lineage gate, so each is
#: discovered here explicitly rather than through the path registry.
_NON_FILE_FORMAT_KEYS: Final[frozenset[str]] = frozenset(
    {"secure_object", "bundle", "archive"},
)


def _discovered_format_keys() -> frozenset[str]:
    """Return every persisted format the storage registry declares.

    The on-disk half comes from the path registry's ``FILE`` definitions — the
    inventory a new keystore or state-root file must join — and the non-file
    half from the three tier formats that have no single path. Discovery never
    reads :data:`PERSISTED_FORMATS`, so the two sets are independent and a
    format present in one and absent from the other is a real finding rather
    than a tautology.
    """
    file_keys = frozenset(
        definition.key for definition in STORAGE_NAMESPACE_REGISTRY.paths if definition.kind is StoragePathKind.FILE
    )
    return file_keys | _NON_FILE_FORMAT_KEYS


def test_every_persisted_format_declares_a_durability_class() -> None:
    """A persisted format with no durability declaration fails here.

    This is the converse of the central enrollment invariant and the reason
    this module exists: discovery is independent of the declaration, so a new
    format cannot pass by omission.
    """
    undeclared = undeclared_persisted_formats(_discovered_format_keys(), PERSISTED_FORMATS)
    assert undeclared == (), (
        f"persisted format(s) {undeclared} carry no durability declaration; add each to "
        "PERSISTED_FORMATS as DURABLE (taxpayer data — needs a floor, an upgrader registry "
        "and a committed old-version fixture) or REGENERABLE (operational state — "
        "delete-and-refuse, no floor), in the same change that introduces the format"
    )


def test_no_declaration_outlives_its_format() -> None:
    """A declaration left behind by a retired format is stale inventory."""
    stale = stale_persisted_format_declarations(_discovered_format_keys(), PERSISTED_FORMATS)
    assert stale == (), (
        f"PERSISTED_FORMATS declares {stale}, which the storage registry no longer knows; "
        "strike the entry in the same change that retires the format, so the inventory "
        "cannot claim coverage nothing backs"
    )


def test_secure_object_namespaces_are_covered_by_the_secure_object_format() -> None:
    """Every encrypted SQL namespace inherits the secure-object declaration.

    The 60-plus namespaces are rows in one persisted format, not formats in
    their own right: they share one schema-version ceiling and one upgrader
    registry, and the secure-object lineage gate walks them. Pinning that here
    keeps a future reader from concluding each namespace needs its own entry.
    """
    namespaces = STORAGE_NAMESPACE_REGISTRY.namespaces
    assert namespaces, "storage registry declares no secure-object namespaces"
    assert all(isinstance(definition, SecureObjectNamespaceDefinition) for definition in namespaces)
    assert PERSISTED_FORMATS["secure_object"] is PersistedFormatClass.DURABLE


def test_application_owned_journal_name_agrees_with_the_registry() -> None:
    """The config-reset journal has one name, declared once.

    The journal is application-owned but its directory is part of the on-disk
    hierarchy, so the name is declared exactly once in the core taxonomy
    (:class:`~cadrumo.core.StorageCategory.CONFIG_RESET_JOURNAL`) and the gate
    pins the application's own constant against THAT declaration — not
    against a second agreeing constant elsewhere, which a rename could update
    while leaving the other stale. A rename that updates the taxonomy and not
    the application's read of it fails here rather than orphaning a
    taxpayer's interrupted reset.
    """
    from ..application import _config_reset_repository

    assert (
        storage_location(StorageCategory.CONFIG_RESET_JOURNAL).subpath
        == _config_reset_repository.CONFIG_RESET_JOURNAL_DIRNAME
    )
