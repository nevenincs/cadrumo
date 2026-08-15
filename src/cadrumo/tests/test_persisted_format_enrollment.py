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

A format is not always a file. Discovery draws on three sources — the path
registry's file definitions, the three tier formats with no single path, and
the secure-object payloads that carry their own version constant. The third
was added after this gate spent several changes red: every capsule record,
the profile record and the authority-session metadata were enrolled while
discovery could see none of them, so each correct declaration read as a stale
one. The enumerating half and the hand-listed half are marked as such below,
because they do not offer the same guarantee.
"""

from __future__ import annotations

from collections.abc import Mapping
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

#: Inventory key -> the secure-object namespace whose rows carry it.
#:
#: A namespace is not a format; an independently versioned payload grammar is.
#: The great majority of namespaces are exactly what the pin below says they
#: are — rows sharing the secure-object envelope's one version ceiling — and
#: those need no entry here. The few listed carry their OWN version constant
#: inside the row, on a separate axis from the envelope that decrypts it: the
#: envelope governs whether the bytes open, the payload version governs
#: whether the record inside them can still be read. A frozen floor on the
#: container does not cover a grammar that versions itself.
#:
#: The three AEAT entries share one namespace, which is the clearest statement
#: of the distinction: if a namespace were a format, three formats could not
#: live in one. They ride a single session store and each declares its own
#: metadata version.
#:
#: Honest limit, stated because the file half does not share it: the on-disk
#: half of discovery ENUMERATES from the path registry, so a new file format
#: cannot be omitted. This half is hand-listed, and only its namespace
#: reference is checked against production. Closing that gap needs the
#: namespace definition to declare its payload's version constant, which is a
#: production change deliberately not made here — so a new independently
#: versioned payload CAN still be missed, and that is a known gap rather than
#: a covered case.
_NAMESPACE_PAYLOAD_FORMATS: Final[Mapping[str, str]] = {
    "profile_record": "user_profile_value",
    "participation_index": "transaction_participation_index",
    "aeat_certificate_session_metadata": "aeat_browser_sessions",
    "aeat_clave_movil_session_metadata": "aeat_browser_sessions",
    "aeat_clave_permanente_session_metadata": "aeat_browser_sessions",
}

#: Inventory key -> (the storage category it lives under, why the path registry
#: does not define it).
#:
#: The fourth discovery source, and the second hand-listed one. Each of these is
#: a real file written to the operator's disk, parsed back through its own
#: grammar, and carrying its own version -- but its LOCATION is derived at the
#: call site rather than declared as a ``FILE`` path definition, so the
#: enumerating half of discovery cannot see it and a correct declaration would
#: read as a stale one.
#:
#: That the storage taxonomy does not name a file is a fact about the taxonomy,
#: not evidence that the bytes are not a format. The same reasoning already
#: applies one source up: capsule records and authority-session metadata were
#: enrolled while discovery could see none of them, and the answer was to teach
#: discovery about them rather than to de-enrol them.
#:
#: Honest limit, identical to the namespace half: this is hand-listed, so only
#: the category reference is checked against production. A new file format
#: derived at its call site CAN still be missed. Closing it needs the file's
#: location declared in the path registry, which for a sidecar whose name is
#: derived from a neighbouring file would put that name in two places -- the
#: duplication the version inventory exists to prevent -- so it is a real design
#: question rather than an omission to patch here.
_UNREGISTERED_FILE_FORMATS: Final[Mapping[str, tuple[StorageCategory, str]]] = {
    "profile_session_retirement_journal": (
        StorageCategory.KEYSTORE_PROFILE_SESSION,
        "A crash-window journal whose path is derived from the session receipt's own path, so it "
        "has no path definition of its own while living in that file's directory.",
    ),
    "profile_legal_hold_snapshot": (
        StorageCategory.PROFILE_CUSTODY_HOLD_EVIDENCE,
        "A per-profile owner snapshot under an owner subdirectory of the hold-evidence root; the "
        "registry declares the root, and the owner leaf is joined by the owning authority.",
    ),
    "profile_filing_retention_snapshot": (
        StorageCategory.PROFILE_CUSTODY_HOLD_EVIDENCE,
        "The filing-owner sibling of the legal-hold snapshot, under its own owner subdirectory of "
        "the same registry-declared hold-evidence root.",
    ),
    "profile_custody_hold_evidence": (
        StorageCategory.PROFILE_CUSTODY_HOLD_EVIDENCE,
        "The derived join of the two owner snapshots above, one file per owner under a "
        "'derived-evidence/<owner>' subdirectory the owning authority joins onto the same "
        "registry-declared hold-evidence root, so it has no path definition of its own.",
    ),
}


def _discovered_format_keys() -> frozenset[str]:
    """Return every persisted format the storage registry declares.

    Four sources. The on-disk half comes from the path registry's ``FILE``
    definitions — the inventory a new keystore, capsule or state-root file must
    join. The non-file half is the three tier formats that have no single path.
    The third is the independently versioned secure-object payloads, which are
    formats by grammar rather than by file. The fourth is the files whose
    location is derived at their call site rather than declared as a path
    definition, which the enumerating half cannot see.

    Discovery never reads :data:`PERSISTED_FORMATS`, so the sets are
    independent and a format present in one and absent from the other is a real
    finding rather than a tautology.
    """
    file_keys = frozenset(
        definition.key for definition in STORAGE_NAMESPACE_REGISTRY.paths if definition.kind is StoragePathKind.FILE
    )
    return (
        file_keys
        | _NON_FILE_FORMAT_KEYS
        | frozenset(_NAMESPACE_PAYLOAD_FORMATS)
        | frozenset(_UNREGISTERED_FILE_FORMATS)
    )


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
    """Being a namespace earns no entry; carrying your own version does.

    The 60-plus namespaces are rows in one persisted format, not formats in
    their own right: they share the secure-object envelope's one schema-version
    ceiling and one upgrader registry, and the secure-object lineage gate walks
    them. Pinning that here keeps a future reader from concluding each namespace
    needs its own entry — the hazard is undiminished and this pin still exists
    for it.

    The wording is narrower than it once was. It previously read as though
    LIVING IN A NAMESPACE were the disqualifying property, which put it in
    direct conflict with enrolling a payload that versions itself. The actual
    discriminator is CARRYING AN INDEPENDENT VERSION: the envelope governs
    whether the bytes decrypt, a payload's own version governs whether the
    record inside them can still be read, and a floor on the first does not
    cover the second. Only a handful of payloads carry one, so narrowing costs
    this pin nothing it was protecting.
    """
    namespaces = STORAGE_NAMESPACE_REGISTRY.namespaces
    assert namespaces, "storage registry declares no secure-object namespaces"
    assert all(isinstance(definition, SecureObjectNamespaceDefinition) for definition in namespaces)
    assert PERSISTED_FORMATS["secure_object"] is PersistedFormatClass.DURABLE

    backing = {namespace for namespace in _NAMESPACE_PAYLOAD_FORMATS.values()}
    declared = {definition.key for definition in namespaces}
    assert backing < declared, (
        "the independently versioned payloads must be a PROPER subset of the namespaces. "
        "If they ever coincide, the narrowing above has quietly become 'every namespace is "
        "a format' -- which is the conclusion this pin exists to prevent"
    )


def test_every_namespace_payload_format_names_a_live_namespace() -> None:
    """The hand-listed half is checked against production, not merely asserted.

    This map is the weaker half of discovery: the file half enumerates, so a
    new file format cannot be omitted, while an entry here is written by hand.
    What keeps it from being a free-text allowlist is that the namespace it
    names must exist in the registry -- an entry cannot be invented for a key
    somebody wanted to silence, because there would be no namespace to point
    at. It does NOT close the omission direction, which the map's own comment
    states rather than leaving to be discovered.
    """
    declared = {definition.key for definition in STORAGE_NAMESPACE_REGISTRY.namespaces}
    unknown = tuple(
        sorted(
            f"{key} -> {namespace}"
            for key, namespace in _NAMESPACE_PAYLOAD_FORMATS.items()
            if namespace not in declared
        )
    )
    assert unknown == (), (
        f"payload format(s) name secure-object namespace(s) the registry does not declare: {unknown}. "
        "Strike the entry with the namespace it described, or the inventory discovers a format "
        "whose home no longer exists"
    )


def test_every_unregistered_file_format_names_a_live_storage_category() -> None:
    """The second hand-listed half is checked against production too.

    Same discipline as the namespace map, and for the same reason: an entry here
    cannot be invented to silence a key, because the storage category it claims
    to live under must resolve to a real location in the taxonomy. It does NOT
    close the omission direction, which the map's own comment states.
    """
    unresolved = tuple(
        sorted(key for key, (category, _reason) in _UNREGISTERED_FILE_FORMATS.items() if not storage_location(category))
    )
    assert unresolved == (), (
        f"unregistered file format(s) {unresolved} name a storage category that resolves to no "
        "location; strike the entry with the category it described"
    )


def test_every_unregistered_file_format_states_why_it_is_unregistered() -> None:
    """A blank reason turns the weaker half into a free-text allowlist."""
    for key, (_category, reason) in _UNREGISTERED_FILE_FORMATS.items():
        assert len(reason.split()) >= 12, f"{key} carries a reason too thin to inform a reader: {reason!r}"


def test_one_namespace_backs_several_independently_versioned_payloads() -> None:
    """The clearest evidence that a namespace is not a format.

    The three AEAT authority-session metadata records ride one session store
    and one namespace, and each declares its own metadata version. If a
    namespace were the unit of format, this arrangement could not exist -- so
    this is the case that forces the distinction rather than illustrating it,
    and it fails if someone later collapses the three back into one entry.
    """
    per_namespace: dict[str, set[str]] = {}
    for key, namespace in _NAMESPACE_PAYLOAD_FORMATS.items():
        per_namespace.setdefault(namespace, set()).add(key)
    shared = {namespace: keys for namespace, keys in per_namespace.items() if len(keys) > 1}
    assert shared, (
        "no namespace backs more than one payload format, so nothing here demonstrates that a "
        "namespace and a format are different units. Restore the case or this distinction rests "
        "on argument alone"
    )


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
