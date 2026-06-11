"""Revision identity and completeness validation helpers.

Checks for duplicate ids, cross-kind primary-id collisions, and
empty-payload violations within a single :class:`ModeloRevision`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ._schema import ModeloRevision


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return dupes


_RECORD_ID_KINDS: tuple[tuple[str, str], ...] = (
    ("casilla", "casillas"),
    ("formula", "formulas"),
    ("binding", "bindings"),
    ("relation", "relations"),
    ("parameter", "parameters"),
    ("algorithm provider", "algorithm_providers"),
    ("algorithm binding", "algorithm_bindings"),
    ("export layout", "export_layouts"),
    ("extraction profile", "extraction_profiles"),
    ("cross-reference", "live_cross_references"),
    ("workbook parity reference", "workbook_parity_refs"),
    ("verification expectation", "verification_expectations"),
    ("application link", "application_links"),
    ("deadline window", "deadline_windows"),
    ("filing schedule", "filing_schedules"),
    ("support removal decision", "support_removal_decisions"),
    ("construct", "constructs"),
    ("dependency classification", "dependency_classifications"),
)
"""Maps the human-readable record kind name to the ``ModeloRevision`` attribute.

Used to fold the 18 per-kind ``[record.id for record in revision.<kind>]``
comprehensions in :meth:`RegistryValidator._validate_revision` into a
single iteration over a typed table. The (kind, attribute) tuple shape
is what every downstream consumer needs: the human-readable label
appears in failure messages, the attribute is what we read.
"""


def _collect_record_id_lists(revision: ModeloRevision) -> dict[str, list[str]]:
    """Return ``{kind: [record.id, ...]}`` for every record kind on the revision."""
    return {kind: [record.id for record in getattr(revision, attr)] for kind, attr in _RECORD_ID_KINDS}


def _emit_per_kind_duplicate_failures(
    failures: list[str],
    prefix: str,
    ids_by_kind: Mapping[str, list[str]],
) -> None:
    """Append a "duplicate <kind> id <id>" failure for every duplicate id, per kind."""
    for kind, ids in ids_by_kind.items():
        for duplicate in sorted(_duplicates(ids)):
            failures.append(f"{prefix}: duplicate {kind} id {duplicate!r}")


# Primary-id deduplication checks the union of every typed-record kind
# EXCEPT ``provider`` (algorithm providers share a namespace with
# algorithm-binding ``provider`` references; collisions there are not
# duplicate-id offences).
_PRIMARY_ID_KINDS: frozenset[str] = frozenset(kind for kind, _ in _RECORD_ID_KINDS) - {"algorithm provider"}


def _emit_combined_primary_id_failures(
    failures: list[str],
    prefix: str,
    ids_by_kind: Mapping[str, list[str]],
) -> None:
    """Cross-kind id uniqueness: no two record kinds may share an id."""
    primary_ids: list[str] = []
    for kind in _PRIMARY_ID_KINDS:
        primary_ids.extend(ids_by_kind[kind])
    for duplicate in sorted(_duplicates(primary_ids)):
        failures.append(f"{prefix}: duplicate registry id {duplicate!r}")


def _resolvable_casilla_references(revision: ModeloRevision) -> frozenset[str]:
    """Return every token that resolves to a casilla within ``revision``.

    A casilla reference — a formula ``casilla`` leaf or ``target``, an
    export field ``casilla``, a relation ``source_output``, an algorithm
    binding input or output — is segment-aware.

    A reference resolves when it is either:

    * a casilla ``id`` declared on the revision (the stable
      within-revision handle), or
    * a bare ``number`` that occurs on exactly one casilla across the
      whole revision, so the segment is unambiguous and the bare number
      resolves within its segment context.

    A bare ``number`` that recurs across distinct record segments is
    NOT resolvable on its own: the reference must use the
    segment-qualified ``id`` to name the intended occurrence. Only those
    genuinely cross-segment numbers carry that cost.

    For a single-segment modelo every casilla sets ``id == number`` and
    every number is unique, so the resolvable set is exactly the set of
    casilla ids — identical to the pre-change ``set(casilla_by_id)``
    behaviour. Single-segment references resolve precisely as before.
    """
    ids = {casilla.id for casilla in revision.casillas}
    number_counts: dict[str, int] = {}
    for casilla in revision.casillas:
        number_counts[casilla.number] = number_counts.get(casilla.number, 0) + 1
    unambiguous_numbers = {number for number, count in number_counts.items() if count == 1}
    return frozenset(ids | unambiguous_numbers)


def _emit_casilla_identity_failures(
    failures: list[str],
    prefix: str,
    revision: ModeloRevision,
) -> None:
    """Append a failure for every duplicate ``(segmento, number)`` casilla pair.

    A casilla's identity is the pair ``(segmento, number)``: a
    multi-segment AEAT modelo (e.g. Modelo 200) reuses the same bare
    five-digit ``number`` across distinct record segments, so uniqueness
    must be keyed on the pair, not on ``number`` alone.

    For a single-segment modelo every casilla leaves ``segmento`` unset,
    so the pair degrades to ``(None, number)`` and this check reproduces
    the prior bare-number uniqueness exactly: two casillas sharing a
    number with no ``segmento`` collide on ``(None, number)`` and
    hard-fail precisely as the previous duplicate-id check did.
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
    """Reject registry revisions that carry no casilla payload at all."""
    if revision.casillas:
        return
    failures.append(
        f"{prefix}: revision must declare at least one casilla; zero-casilla "
        "revisions are unsupported placeholder definitions",
    )
