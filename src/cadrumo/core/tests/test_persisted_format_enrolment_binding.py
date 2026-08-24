"""Gate: the persisted-format inventory and the tree must account for each other.

:data:`PERSISTED_FORMATS` calls itself "the CLOSED inventory the enrollment gate
enumerates against: a new persisted format that does not appear here fails the
gate rather than passing by omission". That was not true. The only gate reading
it validated released FLOORS against the keys, and nothing ever validated the
keys against the tree, so absence was undetectable in both directions at once:

* a key outliving its implementation -- ``bucket_dek`` stayed enrolled DURABLE
  for hours after its format was deleted, asserting a durability guarantee for
  bytes nothing could write;
* an implementation arriving with no key -- all three profile-capsule formats,
  including the one holding the password-wrapped data key, sat outside the
  inventory while the *retired* plaintext manifest sat inside it.

Both from one root, and neither was visible to anything.

**Why this binds rather than infers.** The obvious gate enumerates the tree for
format constants by name and compares. That was tried first and it failed on its
own evidence: a sweep for ``*_SCHEMA_VERSION`` constants matched on the ``Final``
annotation and therefore missed ``ARCHIVE_SCHEMA_VERSION``, which carries none --
so a name-based census missed an ALREADY-ENROLLED canonical tier while auditing
enrolment. A mechanism meant to catch a class of error must not be built on the
technique that produced it.

So the tree side is discovered by AST rather than by pattern (an assignment is
an assignment, annotated or not), and the correspondence is DECLARED. A
declaration can go stale like anything else, but it cannot go stale *silently*,
because each direction gates the other: drop an implementation and its key is
orphaned, add one and it is unbound. That is the difference between a
declaration and an inference, and it is precisely the property the inventory's
comment claimed without having.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from typing import Final

import pytest

from ...tests import SRC_CADRUMO, module_name, production_ast_items
from ..compatibility_lifecycle import PERSISTED_FORMATS

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

VERSIONED_FORMAT_IMPLEMENTATIONS: Final[Mapping[str, str]] = {
    "secure_object": "CIPHER_ENVELOPE_SCHEMA_VERSION",
    "bundle": "BUNDLE_SCHEMA_VERSION",
    "archive": "ARCHIVE_SCHEMA_VERSION",
    "profile_capsule_password_envelope": "PROFILE_CUSTODY_ENVELOPE_SCHEMA_VERSION",
    "profile_capsule_commit": "PROFILE_CUSTODY_COMMIT_SCHEMA_VERSION",
    "profile_capsule_recovery_envelope": "PROFILE_CUSTODY_RECOVERY_SCHEMA_VERSION",
    "profile_capsule_archive_payload": "CAPSULE_ARCHIVE_PAYLOAD_SCHEMA_VERSION",
    "profile_session": "PROFILE_SESSION_SCHEMA_VERSION",
    # These three were first recorded below as carrying no version constant.
    # They do. The gate caught its own author's error on its first run, which is
    # the direction that had never been checked before.
    "secret_index": "SECRET_INDEX_SCHEMA_VERSION",
    "login_throttle": "LOGIN_THROTTLE_SCHEMA_VERSION",
    "config_reset_journal": "CONFIG_RESET_SCHEMA_VERSION",
    "profile_record": "PROFILE_RECORD_SCHEMA_VERSION",
    "participation_index": "PARTICIPATION_INDEX_SCHEMA_VERSION",
    "active_profile_pointer": "POINTER_SCHEMA_VERSION",
    "aeat_certificate_session_metadata": "AEAT_STORAGE_STATE_SCHEMA_VERSION",
    "aeat_clave_movil_session_metadata": "AEAT_CLAVE_MOVIL_METADATA_SCHEMA_VERSION",
    "aeat_clave_permanente_session_metadata": "AEAT_CLAVE_PERMANENTE_METADATA_SCHEMA_VERSION",
    "profile_session_retirement_journal": "PROFILE_SESSION_RETIREMENT_SCHEMA_VERSION",
    "profile_filing_retention_snapshot": "FILING_RETENTION_SNAPSHOT_SCHEMA_VERSION",
    "profile_legal_hold_snapshot": "LEGAL_HOLD_SNAPSHOT_SCHEMA_VERSION",
    "profile_custody_hold_evidence": "CUSTODY_HOLD_EVIDENCE_SCHEMA_VERSION",
}
"""Inventory key -> the module-level version constant that declares its format.

An entry here is the claim that this key names a real, versioned, on-disk shape.
Both gates below read it, from opposite ends.
"""

UNVERSIONED_FORMAT_REASONS: Final[Mapping[str, str]] = {
    "bucket_database_file": "the SQLite container itself; its rows carry the version, the file does not",
    "operation_journal": "per-operation journals version their own payloads rather than the batch",
    "bucket_lock": "an empty lock file; presence is the whole content",
    "bucket_output_language_hint": "a single scalar hint with no surrounding record shape to version",
    "root_fallback_database": "a container, like the per-bucket database file",
    "run_trace": "telemetry rows versioned by their emitting producer",
    "run_events": "telemetry rows versioned by their emitting producer",
    "run_envelope": "telemetry rows versioned by their emitting producer",
    "llm_usage_record": "telemetry rows versioned by their emitting producer",
    "llm_run_telemetry_record": "telemetry rows versioned by their emitting producer",
    "auth_acquisition_lock": "a lock record; presence and holder identity are the content",
    "validation_verdict_cache_entry": "a regenerable cache entry, discarded rather than read forward",
    "llm_cache_entry": "a regenerable cache entry, discarded rather than read forward",
}
"""Inventory keys that legitimately carry no version constant, each with why.

Stated rather than omitted: an unversioned format and a format whose constant
was deleted look identical from here, and only one of them is fine.
"""

CONSTANTS_OUTSIDE_THE_INVENTORY: Final[Mapping[str, str]] = {
    "AUXILIARY_ENVELOPE_HEADER_SCHEMA_VERSION": (
        "Registry export-layout DECLARATION, not an instance payload. It compiles from bundled "
        "TOML that ships inside the wheel and is replaced wholesale on upgrade, and no persistence "
        "adapter references the model at all, which was checked rather than assumed. The bytes an "
        "operator produces here are the rendered fichero, and they carry no copy of this number."
    ),
    "MANUAL_CORPUS_TEXT_SCHEMA_VERSION": (
        "Bundled corpus sidecar. Ships inside the wheel, is versioned with the code and replaced "
        "wholesale on upgrade, and nothing under src/ writes one -- only a dev extraction tool "
        "does, which was measured rather than assumed. The inventory governs bytes an operator's "
        "use produces and the product promises to keep reading."
    ),
    "SIDECAR_SCHEMA_VERSION": "Bundled registry source sidecar; ships with the code, same grounds as the corpus.",
    "ENVELOPE_SCHEMA_VERSION": "The CLI JSON wire envelope. A transport contract, never written to disk as a record.",
    "SCHEMA_VERSION": "Telemetry wire schema; its rows persist under their own enrolled keys, the wire shape does not.",
    "CACHE_SCHEMA_VERSION": "Locale catalogue cache, rebuilt from the shipped catalogues on any mismatch.",
    "COMPILED_CACHE_SCHEMA_VERSION": "Compiled registry cache, rebuilt from the bundled registry tree on any mismatch.",
    "REGISTRY_TREE_CACHE_SCHEMA_VERSION": "Registry tree cache, rebuilt from the bundled registry tree on any mismatch.",
    "SECURE_OBJECT_SCHEMA_VERSION_V1": "A namespace-registry version token for the enrolled secure_object format, not a second format.",
    "SECURE_OBJECT_SCHEMA_VERSION_V2": "A namespace-registry version token for the enrolled secure_object format, not a second format.",
    "SECURE_OBJECT_SCHEMA_VERSION_V3": "A namespace-registry version token for the enrolled secure_object format, not a second format.",
    "SECURE_OBJECT_SCHEMA_VERSION_V4": "A namespace-registry version token for the enrolled secure_object format, not a second format.",
    "M303_ORDEN_CENSUS_SCHEMA_VERSION": (
        "Bundled build-generated Modelo 303 census artefact shipped with each release and regenerated "
        "from the release corpus when absent; it is not operator-owned persisted data."
    ),
    "REGISTRY_IDENTITY_SCHEMA_VERSION": (
        "Build-generated identity stamp for the bundled immutable registry tree; release replacement "
        "recomputes it from shipped registry content rather than preserving operator data."
    ),
    "WORKFLOW_RUN_SCHEMA_VERSION_V3": "A namespace-registry version token for an enrolled secure_object namespace, not a second format.",
    "SUPPORTED_BUNDLE_SCHEMA_VERSIONS": "The accepted-version set for the enrolled bundle format, not a format of its own.",
    "UNREADABLE_SCHEMA_VERSION": "A sentinel standing for 'this row's version could not be read', not a format.",
}
"""Version constants that are deliberately not inventory formats, each with why.

Two different grounds live here and both are decisions: a format on its way out,
excluded so its absence is not later read as another gap; and a constant that
versions something other than a file this product keeps reading -- a wire
contract, a rebuildable cache, a record shape carried inside an enrolled
container, or a token naming an enrolled format's version.
"""

CONSTANTS_AWAITING_CLASSIFICATION: Final[Mapping[str, str]] = {
    "CUSTODY_TRANSACTION_SCHEMA_VERSION": "Profile-deletion transaction journal; carries lifecycle facts after real effects.",
    "CUSTODY_RECEIPT_SCHEMA_VERSION": "Per-owner deletion receipts; the durable evidence that each owner step ran.",
    "SECRET_RECORD_SCHEMA_VERSION": "Secret-store record shape; sits beneath the enrolled secret index.",
    "BLOB_MANIFEST_SCHEMA_VERSION": "Blob-store manifest; the reference layer over stored blob bytes.",
    "EVIDENCE_SIDECAR_SCHEMA_VERSION": "Workbook-export evidence sidecar; grounding that travels with an export.",
    "SECURE_REFERENCE_SCHEMA_VERSION": "Cross-store secure reference; resolves one record to another.",
    "REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION": "Remote mirror manifest; written to an operator's own remote mirror.",
    "ENCRYPTED_BUNDLE_ENVELOPE_SCHEMA_VERSION": "The envelope around an encrypted bundle, distinct from the bundle payload.",
    "DIAGNOSTIC_SCHEMA_VERSION": "Auth diagnostic record; persisted for later operator inspection.",
    "ASSETS_SCHEMA_VERSION": (
        "Taxpayer asset register. Moved here from the exclusions: it was excused as a shape living "
        "inside a secure object, and being inside an enrolled container does not put a record's own "
        "grammar under that container's floor. It carries a strict version validator on persisted "
        "taxpayer data and needs a class of its own."
    ),
    "BIENES_INVERSION_SCHEMA_VERSION": "Investment-goods register; same correction as the asset register above.",
    "INVENTORY_SCHEMA_VERSION": "Taxpayer inventory register; same correction as the asset register above.",
    "PRORRATA_REGISTER_SCHEMA_VERSION": "Prorrata register; same correction as the asset register above.",
    "FINCA_SCHEMA_VERSION": (
        "Rental-register finca record. These five arrive here by being NAMED, not by being new: "
        "each was a bare literal on the domain model duplicated by a column default on the "
        "persistence row, so the version existed twice and this gate could see neither. Naming "
        "them makes them visible and openly unclassified, which is the honest state -- giving a "
        "literal a name is not a durability decision, and pretending otherwise is how the four "
        "register shapes above came to be excused without anyone deciding."
    ),
    "ARRENDAMIENTO_SCHEMA_VERSION": "Rental-register arrendamiento record; named alongside the finca record above.",
    "FINCA_RENDIMIENTO_RECORD_SCHEMA_VERSION": "Per-period gross-rent ledger record; named alongside the finca record.",
    "FINCA_GASTO_SCHEMA_VERSION": "Deductible-gasto record; named alongside the finca record above.",
    "FINCA_AMORTIZACION_LEDGER_ENTRY_SCHEMA_VERSION": (
        "Amortización cumulative-ledger entry; named alongside the finca record above."
    ),
}
"""Formats with NO durability class yet -- an open gap, not a set of exemptions.

Held separately from the exclusions above on purpose. Both would keep the gate
green, and only one of them means somebody decided. Collapsing them would let
"nobody has looked at this" read as "looked at and ruled out", which is the
precise misreading that let a retired plaintext manifest sit governed while the
capsule holding the password-wrapped data key sat outside the inventory.

Every entry here is a durability decision owed. The count is asserted below so
the gap is a number a reader can see rather than a silence they must notice.
"""


def _declared_version_constants() -> dict[str, str]:
    """Return every module-level ``*SCHEMA_VERSION*`` constant and its module.

    Discovered from the AST rather than matched by text: an assignment is an
    assignment whether or not it carries a ``Final`` annotation, and it was
    exactly that annotation which a text sweep keyed on while missing an
    enrolled format.
    """
    found: dict[str, str] = {}
    for path, tree in production_ast_items():
        if not isinstance(tree, ast.Module):
            continue
        for node in tree.body:
            targets: list[str] = []
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets.append(node.target.id)
            elif isinstance(node, ast.Assign):
                targets.extend(t.id for t in node.targets if isinstance(t, ast.Name))
            for name in targets:
                if "SCHEMA_VERSION" in name:
                    found[name.lstrip("_")] = module_name(path)
    return found


def test_every_inventory_key_is_accounted_for() -> None:
    """A key names a versioned format, or states why it carries no version.

    Catches the ``bucket_dek`` shape: an entry whose implementation has been
    deleted keeps asserting a durability guarantee for bytes nothing writes.
    """
    accounted = set(VERSIONED_FORMAT_IMPLEMENTATIONS) | set(UNVERSIONED_FORMAT_REASONS)
    unaccounted = tuple(sorted(set(PERSISTED_FORMATS) - accounted))
    assert unaccounted == (), (
        f"inventory key(s) {unaccounted} name neither a version constant nor a stated reason for "
        "carrying none. Bind the key to the constant that declares its format, or record why the "
        "format is unversioned -- an unversioned format and a format whose constant was deleted "
        "are indistinguishable from here."
    )
    stale = tuple(sorted(accounted - set(PERSISTED_FORMATS)))
    assert stale == (), (
        f"binding(s) {stale} name inventory keys that no longer exist. Remove the binding with the "
        "key it described, in the same change."
    )


def test_every_bound_constant_still_exists_in_the_tree() -> None:
    """A binding must name a live constant, or the key outlived its format."""
    declared = _declared_version_constants()
    missing = tuple(
        sorted(
            f"{key} -> {constant}"
            for key, constant in VERSIONED_FORMAT_IMPLEMENTATIONS.items()
            if constant not in declared
        )
    )
    assert missing == (), (
        f"inventory key(s) bind to version constant(s) that no longer exist: {missing}. This is the "
        "failure the de-enrolled bucket data key demonstrated -- a durability guarantee outliving "
        "the format it guaranteed. De-enrol the key in the same change that deletes its format."
    )


def test_every_version_constant_is_bound_or_deliberately_excluded() -> None:
    """A new persisted format cannot pass by omission, which was the claim.

    Catches the profile-capsule shape: a versioned format arriving with no
    inventory key at all, invisible because nothing looked in this direction.
    """
    declared = _declared_version_constants()
    bound = (
        set(VERSIONED_FORMAT_IMPLEMENTATIONS.values())
        | set(CONSTANTS_OUTSIDE_THE_INVENTORY)
        | set(CONSTANTS_AWAITING_CLASSIFICATION)
    )
    unbound = tuple(sorted(f"{name} ({module})" for name, module in declared.items() if name not in bound))
    assert unbound == (), (
        f"version constant(s) declare a persisted format that is accounted for nowhere: {unbound}. "
        "Enrol it with an argued durability class, record it in CONSTANTS_OUTSIDE_THE_INVENTORY as "
        "not this inventory's subject, or place it in CONSTANTS_AWAITING_CLASSIFICATION if the "
        "decision is genuinely open. Adding a key is a durability decision, so it may not be "
        "assigned by copying whichever neighbour is nearest."
    )


def test_no_exclusion_outlives_the_constant_it_excuses() -> None:
    """A stale exclusion silently re-opens the hole it was written to document."""
    declared = _declared_version_constants()
    excused = set(CONSTANTS_OUTSIDE_THE_INVENTORY) | set(CONSTANTS_AWAITING_CLASSIFICATION)
    stale = tuple(sorted(name for name in excused if name not in declared))
    assert stale == (), (
        f"exclusion(s) {stale} name version constants the tree no longer declares. Drop the "
        "exclusion with the constant, or it will excuse a future format that reuses the name."
    )


def test_every_stated_reason_says_something() -> None:
    """A reason is the whole mechanism here, so a blank one is a silent pass."""
    for mapping in (
        UNVERSIONED_FORMAT_REASONS,
        CONSTANTS_OUTSIDE_THE_INVENTORY,
        CONSTANTS_AWAITING_CLASSIFICATION,
    ):
        for key, reason in mapping.items():
            assert len(reason.split()) >= 6, f"{key} carries a reason too thin to inform a reader: {reason!r}"


def test_the_discovery_walk_finds_an_unannotated_constant() -> None:
    """Anti-tautology, and the specific failure that motivated the design.

    A text sweep keyed on the ``Final`` annotation missed
    ``ARCHIVE_SCHEMA_VERSION``, which carries none, while auditing enrolment --
    so this pins that the AST walk sees it. Without this, the gate could be
    rebuilt on the technique that produced the class it catches.
    """
    declared = _declared_version_constants()
    assert "ARCHIVE_SCHEMA_VERSION" in declared
    source = (SRC_CADRUMO / "adapters/persistence/storage/bucket/_export_header.py").read_text(encoding="utf-8")
    assert "ARCHIVE_SCHEMA_VERSION: Final" not in source, (
        "this constant is expected to carry NO annotation; if it gained one, the anti-tautology "
        "value of this test is gone and it needs a different unannotated subject"
    )


def test_the_unclassified_gap_is_a_number_a_reader_can_see() -> None:
    """The open gap is asserted as a count, not left to be noticed.

    This is the property whose absence caused everything this gate exists for.
    A format nobody had classified was indistinguishable from one nobody needed
    to, because absence is silent and silence is not a signal. Pinning the count
    means shrinking the gap is a deliberate edit here, and GROWING it is too --
    a new unclassified format cannot be added quietly while the number stands.

    Raise it only when a genuinely new format arrives unclassified; lower it as
    each one is argued. Never adjust it to make a run pass.

    It moved UP, from 14 to 19, and that direction was the good outcome:
    five rental-register shapes had been carrying their version as a bare
    literal, which this gate discovers by constant NAME and therefore could not
    see at all. Naming them did not classify them. A number that grows because
    five hidden formats became visible is worth more than one that stayed still
    while they hid.

    It then moved DOWN to 18, because the interrupted-session-key-swap journal
    was argued and enrolled rather than left excused for being privately named.
    Two further formats were enrolled in the same change without ever passing
    through here -- the legal-hold and filing-retention snapshots carried their
    version as a bare literal, so like the five above they were invisible to
    this gate until named, and they were named and classed in one move.
    """
    assert len(CONSTANTS_AWAITING_CLASSIFICATION) == 18, (
        f"{len(CONSTANTS_AWAITING_CLASSIFICATION)} persisted formats await a durability class, not "
        "the 18 recorded here. If one has been argued, remove it from "
        "CONSTANTS_AWAITING_CLASSIFICATION and lower this number in the same change; if a new "
        "format arrived unclassified, raise it deliberately rather than to restore green."
    )


def test_no_constant_is_both_excluded_and_awaiting_classification() -> None:
    """The two states must stay distinguishable, which is their whole purpose."""
    overlap = tuple(sorted(set(CONSTANTS_OUTSIDE_THE_INVENTORY) & set(CONSTANTS_AWAITING_CLASSIFICATION)))
    assert overlap == (), (
        f"constant(s) {overlap} are recorded as both decided and undecided. One of those claims is "
        "false, and the pair reads as a decision either way."
    )
