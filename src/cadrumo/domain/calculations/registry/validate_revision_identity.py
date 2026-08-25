"""Revision identity and completeness validation helpers.

Checks for duplicate ids, cross-kind primary-id collisions, and
empty-payload violations within a single :class:`ModeloRevision`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import ModeloRevision


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return dupes


duplicates = _duplicates


_RECORD_ID_KINDS: tuple[tuple[str, str], ...] = (
    ("casilla", "casillas"),
    ("formula", "formulas"),
    ("binding", "bindings"),
    ("relation", "relations"),
    ("parameter", "parameters"),
    ("export layout", "export_layouts"),
    ("extraction profile", "extraction_profiles"),
    ("cross-reference", "live_cross_references"),
    ("workbook parity reference", "workbook_parity_refs"),
    ("verification expectation", "verification_expectations"),
    ("application link", "application_links"),
    ("deadline window", "deadline_windows"),
    ("filing schedule", "filing_schedules"),
    ("construct", "constructs"),
    ("dependency classification", "dependency_classifications"),
)


def _collect_record_id_lists(revision: ModeloRevision) -> dict[str, list[str]]:
    return {kind: [record.id for record in getattr(revision, attr)] for kind, attr in _RECORD_ID_KINDS}


collect_record_id_lists = _collect_record_id_lists


def _emit_per_kind_duplicate_failures(
    failures: list[str],
    prefix: str,
    ids_by_kind: Mapping[str, list[str]],
) -> None:
    for kind, ids in ids_by_kind.items():
        for duplicate in sorted(_duplicates(ids)):
            failures.append(f"{prefix}: duplicate {kind} id {duplicate!r}")


_PRIMARY_ID_KINDS: frozenset[str] = frozenset(kind for kind, _ in _RECORD_ID_KINDS)


def _emit_combined_primary_id_failures(
    failures: list[str],
    prefix: str,
    ids_by_kind: Mapping[str, list[str]],
) -> None:
    owners_by_id: dict[str, list[str]] = {}
    for kind, _attr in _RECORD_ID_KINDS:
        if kind not in _PRIMARY_ID_KINDS:
            continue
        for record_id in ids_by_kind[kind]:
            owners_by_id.setdefault(record_id, []).append(kind)
    for duplicate, owners in sorted(owners_by_id.items()):
        if len(owners) > 1:
            failures.append(f"{prefix}: duplicate registry id {duplicate!r} shared by {', '.join(owners)}")


def _emit_duplicate_export_ref_failures(
    failures: list[str],
    prefix: str,
    revision: ModeloRevision,
) -> None:
    owners_by_export_ref: dict[str, list[str]] = {}
    for casilla in revision.casillas:
        for export_ref in casilla.export_refs:
            owners_by_export_ref.setdefault(export_ref, []).append(casilla.id)
    for export_ref, owners in sorted(owners_by_export_ref.items()):
        if len(owners) <= 1:
            continue
        failures.append(
            f"{prefix}: export field {export_ref!r} is declared by multiple casillas {sorted(owners)!r}",
        )


def revision_reference_identity_failures(prefix: str, revision: ModeloRevision) -> tuple[str, ...]:
    """Return :class:`ModeloRevision` identity failures that make references ambiguous."""
    failures: list[str] = []
    ids_by_kind = _collect_record_id_lists(revision)
    _emit_per_kind_duplicate_failures(failures, prefix, ids_by_kind)
    _emit_combined_primary_id_failures(failures, prefix, ids_by_kind)
    failures.extend(revision_casilla_identity_failures(prefix, revision))
    _emit_duplicate_export_ref_failures(failures, prefix, revision)
    return tuple(failures)


def revision_casilla_identity_failures(prefix: str, revision: ModeloRevision) -> tuple[str, ...]:
    """Return :class:`ModeloRevision` casilla identity failures."""
    failures: list[str] = []
    _emit_casilla_metadata_uniqueness_failures(failures, prefix, revision)
    _emit_ambiguous_bare_casilla_id_failures(failures, prefix, revision)
    _emit_ambiguous_casilla_reference_token_failures(failures, prefix, revision)
    return tuple(failures)


def _emit_ambiguous_bare_casilla_id_failures(
    failures: list[str],
    prefix: str,
    revision: ModeloRevision,
) -> None:
    """Reject bare casilla ids when a printed number is reused."""
    owners_by_printed_number: dict[str, list[tuple[str, str | None]]] = {}
    for casilla in revision.casillas:
        owners_by_printed_number.setdefault(casilla.number, []).append((casilla.id, casilla.segmento))

    for number, owners in sorted(owners_by_printed_number.items()):
        if len(owners) <= 1:
            continue
        ambiguous_owner_ids = sorted(
            casilla_id for casilla_id, segmento in owners if segmento is None or casilla_id == number
        )
        if not ambiguous_owner_ids:
            continue
        candidate_ids = sorted(casilla_id for casilla_id, _ in owners)
        failures.append(
            f"{prefix}: casilla number {number!r} is reused by multiple casillas; "
            f"ambiguous bare casilla ids {ambiguous_owner_ids!r} must declare a "
            f"segment-qualified casilla id and segmento (candidates {candidate_ids!r})",
        )


def _emit_ambiguous_casilla_reference_token_failures(
    failures: list[str],
    prefix: str,
    revision: ModeloRevision,
) -> None:
    """Reject a token that is a primary id and casilla display/export metadata."""
    primary_id_owners: dict[str, list[str]] = {}
    for kind, attr in _RECORD_ID_KINDS:
        if kind not in _PRIMARY_ID_KINDS:
            continue
        for record in getattr(revision, attr):
            primary_id_owners.setdefault(record.id, []).append(kind)

    metadata_owners: dict[str, list[str]] = {}
    for casilla in revision.casillas:
        metadata_tokens: list[tuple[str, str | None]] = [
            ("number", casilla.number),
            ("form_number", casilla.form_number),
        ]
        metadata_tokens.extend(("export_ref", export_ref) for export_ref in casilla.export_refs)
        for kind, token in metadata_tokens:
            if token is None or token == casilla.id:
                continue
            metadata_owners.setdefault(token, []).append(f"{kind} metadata for casilla {casilla.id!r}")

    for token, owners in sorted(metadata_owners.items()):
        primary_owners = primary_id_owners.get(token)
        if primary_owners is None:
            continue
        failures.append(
            f"{prefix}: casilla reference token {token!r} is ambiguous; it is "
            f"{', '.join(sorted(primary_owners))} id {token!r} and {', '.join(sorted(owners))}",
        )


def _emit_casilla_metadata_uniqueness_failures(
    failures: list[str],
    prefix: str,
    revision: ModeloRevision,
) -> None:
    """Append failures for duplicate ``(segmento, number)`` metadata pairs.

    ``casilla.id`` is canonical; ``number`` is AEAT/display metadata.
    With ``segmento`` unset, the pair preserves single-segment
    duplicate-number failures.
    """
    pairs = [(casilla.segmento, casilla.number) for casilla in revision.casillas]
    seen: set[tuple[str | None, str]] = set()
    reported: set[tuple[str | None, str]] = set()
    for pair in pairs:
        if pair in seen and pair not in reported:
            reported.add(pair)
        seen.add(pair)
    for segmento, number in sorted(reported, key=lambda item: (item[0] or "", item[1])):
        if segmento is None:
            failures.append(f"{prefix}: duplicate casilla number {number!r}")
        else:
            failures.append(f"{prefix}: duplicate casilla number {number!r} within segmento {segmento!r}")


def _emit_revision_payload_failures(
    failures: list[str],
    prefix: str,
    revision: ModeloRevision,
) -> None:
    if revision.casillas:
        return
    failures.append(
        f"{prefix}: revision must declare at least one casilla; zero-casilla "
        "revisions are unsupported placeholder definitions",
    )


emit_revision_payload_failures = _emit_revision_payload_failures
