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

A format is not always a file. Discovery draws on three sources, and every one
of them now ENUMERATES a production declaration: the path registry's file
definitions, the four payload formats with no single path, and the record
formats each secure-object namespace declares for the rows it carries.

The third source used to be a hand-maintained table in this module, and so did
a fourth: files whose location the owning authority joined at the call site,
which the path registry therefore could not see. Both tables were written for
the same reason and both had the same weakness — an entry could only be
checked for naming something live, never for being absent — so a new format of
either shape could still be missed, and the tables said so rather than hiding
it. That is fixed at the source instead of documented: the four call-site
files now carry real path definitions anchored on taxonomy-declared
directories, and a namespace declares its own record formats beside itself.
Discovery has no hand-maintained half left, so a new format of either shape
fails here rather than passing by omission.
"""

from __future__ import annotations

from typing import Final

import pytest

from ..adapters.persistence.storage.namespace_registry import STORAGE_NAMESPACE_REGISTRY
from ..adapters.persistence.storage.namespace_taxonomy import StoragePathKind
from ..adapters.persistence.storage.secure_object_namespaces import SecureObjectNamespaceDefinition
from ..core.compatibility_lifecycle import (
    PERSISTED_FORMATS,
    PersistedFormatClass,
    stale_persisted_format_declarations,
    undeclared_persisted_formats,
)
from ..core.storage_taxonomy import StorageCategory
from ..core.storage_taxonomy_locations import storage_location
from ._storage_path_grammar import literal_directory_runs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Formats that are not single on-disk files and so carry no ``FILE`` path
#: definition: the encrypted SQL secure-object table, the portable profile
#: bundle, the sealed archive, and its independently versioned capsule payload.
#: Each is a real persisted format with its own tier lineage gate, so each is
#: discovered here explicitly rather than through the path registry.
_NON_FILE_FORMAT_KEYS: Final[frozenset[str]] = frozenset(
    {"secure_object", "bundle", "archive", "profile_capsule_archive_payload"},
)


def _declared_record_formats() -> frozenset[str]:
    """Return every record format the secure-object namespaces declare.

    A namespace is not a format; a record grammar enrolled on its own axis is.
    The great majority of namespaces are exactly what the pin below says they
    are — rows sharing the secure-object envelope's one version ceiling and one
    upgrader registry — and declare nothing. The few that do carry a record the
    inventory classifies separately: the envelope governs whether the bytes
    decrypt, the record's own declaration governs whether what is inside them
    can still be read, and a floor on the container does not cover the record.

    Read off the production registry rather than a table in this module, so an
    author adding such a record meets the obligation beside the namespace and
    this gate cannot be satisfied by an entry nothing in production points at.
    """
    return frozenset(key for definition in STORAGE_NAMESPACE_REGISTRY.namespaces for key in definition.record_formats)


def _discovered_format_keys() -> frozenset[str]:
    """Return every persisted format the storage registry declares.

    Three sources, each enumerating a production declaration. The on-disk half
    comes from the path registry's ``FILE`` definitions — the inventory a new
    keystore, capsule, hold-evidence or state-root file must join. The non-file
    half is the four payload formats that have no single path. The third is the
    record formats the secure-object namespaces declare, which are formats by
    grammar rather than by file.

    Discovery never reads :data:`PERSISTED_FORMATS`, so the sets are
    independent and a format present in one and absent from the other is a real
    finding rather than a tautology.
    """
    file_keys = frozenset(
        definition.key for definition in STORAGE_NAMESPACE_REGISTRY.paths if definition.kind is StoragePathKind.FILE
    )
    return file_keys | _NON_FILE_FORMAT_KEYS | _declared_record_formats()


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


def test_being_a_namespace_earns_no_entry_but_carrying_a_record_format_does() -> None:
    """The pin excludes namespaces without excluding the records they carry.

    The 60-plus namespaces are rows in one persisted format, not formats in
    their own right: they share the secure-object envelope's one schema-version
    ceiling and one upgrader registry, and the secure-object lineage gate walks
    them. Pinning that here keeps a future reader from concluding each namespace
    needs its own entry — the hazard is undiminished and this pin still exists
    for it.

    What it must NOT do is exclude the record grammars living in those rows,
    which is the conflict the earlier wording carried: LIVING IN A NAMESPACE
    read as the disqualifying property, and that reading refuses exactly the
    records the inventory has since enrolled. The two are separated
    structurally rather than by wording. A namespace KEY may not be an
    inventory format; a record format a namespace DECLARES must be one.
    """
    namespaces = STORAGE_NAMESPACE_REGISTRY.namespaces
    assert namespaces, "storage registry declares no secure-object namespaces"
    assert all(isinstance(definition, SecureObjectNamespaceDefinition) for definition in namespaces)
    assert PERSISTED_FORMATS["secure_object"] is PersistedFormatClass.DURABLE

    namespace_keys = {definition.key for definition in namespaces}
    namespaces_as_formats = tuple(sorted(namespace_keys & set(PERSISTED_FORMATS)))
    assert namespaces_as_formats == (), (
        f"secure-object namespace(s) {namespaces_as_formats} are enrolled as persisted formats in "
        "their own right. A namespace is a home for rows, not a format: its rows already sit under "
        "the secure_object envelope's floor and upgrader registry. Enrol the RECORD grammar the "
        "namespace carries, declared on the namespace as a record format, not the namespace itself"
    )

    unenrolled = tuple(sorted(_declared_record_formats() - set(PERSISTED_FORMATS)))
    assert unenrolled == (), (
        f"record format(s) {unenrolled} are declared on a secure-object namespace but carry no "
        "durability declaration. Declaring one is the claim that the record is classified on its "
        "own axis, so it must be enrolled -- otherwise the pin excludes a grammar rather than a "
        "namespace, which is the confusion this test separates"
    )

    backing = {definition.key for definition in namespaces if definition.record_formats}
    assert backing < namespace_keys, (
        "the namespaces declaring record formats must be a PROPER subset of the namespaces. "
        "If they ever coincide, the narrowing above has quietly become 'every namespace is "
        "a format' -- which is the conclusion this pin exists to prevent"
    )


def test_one_namespace_carries_several_record_formats() -> None:
    """The clearest evidence that a namespace is not a format.

    The three AEAT authority-session metadata records ride one session store
    and one namespace, and each declares its own metadata version. If a
    namespace were the unit of format, this arrangement could not exist -- so
    this is the case that forces the distinction rather than illustrating it,
    and it fails if someone later collapses the three back into one entry.
    """
    shared = {
        definition.key: definition.record_formats
        for definition in STORAGE_NAMESPACE_REGISTRY.namespaces
        if len(definition.record_formats) > 1
    }
    assert shared, (
        "no namespace carries more than one record format, so nothing here demonstrates that a "
        "namespace and a format are different units. Restore the case or this distinction rests "
        "on argument alone"
    )


def test_every_discovered_file_format_resolves_to_a_declared_directory() -> None:
    """Discovery's file half is anchored on the taxonomy, not on free text.

    The four formats whose writers join their own location once sat in a
    hand-maintained table here, each entry carrying a prose reason and checked
    only for naming a live storage category. They now carry real path
    definitions, so this asserts the stronger property the table could not: the
    directory portion each format's grammar spells is a subpath some
    :class:`~cadrumo.core.StorageCategory` declares. A definition invented to
    silence a key would have to invent a taxonomy member to sit under.
    """
    known = {storage_location(category).subpath for category in StorageCategory}
    unanchored: list[str] = []
    for definition in STORAGE_NAMESPACE_REGISTRY.paths:
        if definition.kind is not StoragePathKind.FILE or definition.key not in PERSISTED_FORMATS:
            continue
        for run in literal_directory_runs(grammar=definition.grammar, kind=definition.kind):
            if run not in known:
                unanchored.append(f"{definition.key!r} spells directory {run!r}, which no StorageCategory declares")
    assert not unanchored, "\n".join(unanchored)


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
