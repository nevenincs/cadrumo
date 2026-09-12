"""Modelo 100 régimen-de-atribución omission advisory.

The socio-side ``attribution_received`` profile fact group is the typed
home for a base imponible attributed to a member by an entity in the régimen de
atribución de rentas (LIRPF arts. 86-89). That
value is NOT auto-bound onto the M100 atribución casilla — casilla 1577 stays
relation-canonical, and the cross-bucket attributed value enters the member's
own M100 via a documented manual ``--binding`` override. This module is the
non-silent guard on that manual handoff: it emits a non-blocking
:class:`ModeloVerificationFinding` warning when the two halves of the handoff
disagree, so a forgotten transcription surfaces loudly rather than
under-declaring in silence (``no-silent-under-declaration``).

Two symmetric triggers, both ADVISORY / WARNING:

* Captured-but-unfolded: the profile declares ``attribution_received`` facts for
  the filing year, but the atribución casilla resolves empty — the member
  recorded the received share yet did not fold it into the M100.
* Declared-but-uncaptured: the atribución casilla carries a value, but no
  ``attribution_received`` facts back it for the filing year — an
  SC-membership signal (declared attributed income) with no provenance facts to
  explain it; the member is prompted to capture the facts.

See Also:
    :func:`~application.modelo._verification_actions._append_revision_advisory_findings`:
        Verification collector that appends this advisory beside the reduction
        and objective-estimation advisories.
    :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`:
        Active taxpayer profile the advisory reads ``attribution_received``
        facts from.
    :class:`~WorkUnit`:
        Supplies the modelo, filing year, and bucket that bound the advisory.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from ...core.decimal.coercion import coerce_decimal_strict
from ...core.decimal.constants import ZERO
from ...core.modelo import Modelo
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...domain.user_profile.errors import ProfileNotFoundError
from ...domain.user_profile.values import UserProfileFact, UserProfileRecord
from ..user_profile.profile_record_repository import ProfileRecordRepository
from .semantic_role_resolution import casilla_id_for_unique_revision_semantic_role

if TYPE_CHECKING:
    from ...core.casilla_id import CasillaId
    from ...domain.calculations.registry.ids import LegalRefId, SourceRefId
    from ...domain.calculations.registry.schema import RegistrySnapshot
    from ...domain.modelos.work_unit import WorkUnit

_ATRIBUCION_ACT_ECO_ROLE = "irpf_rendimiento_act_eco_atribuido_rdto_neto"
_RECEIVED_FACT_RE = re.compile(r"^attribution_received\.(?P<index>[0-9]+)\.(?P<field>[a-z][a-z0-9_]*)$")


def _attribution_received_omission_advisory_findings(
    *,
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    casilla_values: Mapping[CasillaId, Decimal],
    profile_record: UserProfileRecord | None = None,
) -> tuple[ModeloVerificationFinding, ...]:
    """Return the non-blocking M100 régimen-de-atribución handoff advisories.

    Args:
        work_unit: The :class:`WorkUnit` whose modelo, filing year, and bucket
            scope the advisory (applies to Modelo 100 only).
        snapshot: The :class:`RegistrySnapshot` whose revision declares the
            atribución casilla resolved structurally by semantic role.
        casilla_values: The resolved casilla values from the calculation
            revision under verification.
        profile_record: Optional :class:`UserProfileRecord` override for testing;
            loaded from the work unit's bucket when omitted.

    Returns:
        A tuple carrying at most one :class:`ModeloVerificationFinding` warning:
        empty when the handoff is coherent (both halves present, or both
        absent), one finding when exactly one half is present.
    """
    if str(getattr(work_unit.modelo, "value", work_unit.modelo)) != Modelo("100").value:
        return ()

    casilla_id = casilla_id_for_unique_revision_semantic_role(
        snapshot.revision,
        _ATRIBUCION_ACT_ECO_ROLE,
        modelo_id=Modelo("100").value,
    )
    if casilla_id is None:
        return ()

    casilla_value = casilla_values.get(casilla_id)
    casilla_has_value = casilla_value is not None and casilla_value != ZERO

    legal_refs, source_refs = _attribution_provenance(snapshot, casilla_id)

    record = profile_record
    if record is None:
        try:
            record = ProfileRecordRepository.for_current_session(work_unit.bucket_id).load(work_unit.bucket_id)
        except ProfileNotFoundError:
            return ()

    total_base = _attribution_received_base_for_year(record.facts, work_unit.filing_year)
    facts_present = total_base is not None

    if facts_present and not casilla_has_value:
        return (
            _attribution_received_unfolded_finding(
                work_unit,
                casilla_id,
                total_base,
                legal_refs=legal_refs,
                source_refs=source_refs,
            ),
        )

    if casilla_has_value and not facts_present:
        return (
            _attribution_received_uncaptured_finding(
                work_unit,
                casilla_id,
                casilla_value,
                legal_refs=legal_refs,
                source_refs=source_refs,
            ),
        )

    return ()


def _attribution_received_unfolded_finding(
    work_unit: WorkUnit,
    casilla_id: CasillaId,
    total_base: Decimal,
    *,
    legal_refs: tuple[LegalRefId, ...],
    source_refs: tuple[SourceRefId, ...],
) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        casilla_id=casilla_id,
        message_locale_key="application.modelo.findings.attribution_received_unfolded",
        message_facts={
            "filing_year": work_unit.filing_year,
            "total_base": total_base,
            "casilla_id": casilla_id,
        },
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def _attribution_received_uncaptured_finding(
    work_unit: WorkUnit,
    casilla_id: CasillaId,
    casilla_value: Decimal | None,
    *,
    legal_refs: tuple[LegalRefId, ...],
    source_refs: tuple[SourceRefId, ...],
) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        casilla_id=casilla_id,
        message_locale_key="application.modelo.findings.attribution_received_uncaptured",
        message_facts={
            "casilla_id": casilla_id,
            "filing_year": work_unit.filing_year,
            "casilla_value": casilla_value if casilla_value is not None else "absent",
        },
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def _attribution_provenance(
    snapshot: RegistrySnapshot,
    casilla_id: CasillaId,
) -> tuple[tuple[LegalRefId, ...], tuple[SourceRefId, ...]]:
    """Return provenance declared by the selected attribution casilla."""
    casilla = next((candidate for candidate in snapshot.revision.casillas if candidate.id == casilla_id), None)
    if casilla is None:
        return tuple(snapshot.revision.legal_refs), tuple(snapshot.revision.source_refs)
    return tuple(casilla.legal_refs), tuple(casilla.source_refs)


def _received_fact_parts(fact: UserProfileFact) -> tuple[int, str, object] | None:
    """Extract one indexed attribution fact, skipping malformed/empty values."""
    match = _RECEIVED_FACT_RE.match(fact.path)
    if match is None or fact.value is None:
        return None
    return int(match.group("index")), match.group("field"), fact.value


def _group_received_facts(facts: tuple[UserProfileFact, ...]) -> dict[int, dict[str, object]]:
    """Group attribution facts by their persisted row index in input order."""
    grouped: dict[int, dict[str, object]] = {}
    for fact in facts:
        parts = _received_fact_parts(fact)
        if parts is None:
            continue
        index, field, value = parts
        grouped.setdefault(index, {})[field] = value
    return grouped


def _row_matches_filing_year(row: Mapping[str, object], filing_year: int) -> bool:
    """Return whether one grouped attribution row belongs to the requested year."""
    row_year = row.get("filing_year")
    if row_year is None:
        return False
    return str(row_year).strip() == str(filing_year)


def _coerce_received_base(row: Mapping[str, object]) -> Decimal | None:
    """Coerce a row's attributed base, treating malformed stored text as absent."""
    base = row.get("base_imponible_attributed")
    if base is None:
        return None
    try:
        # DECIMAL-TEXT-RATIONALE-ATTRIBUTION-FACT-SUM: sums an already
        # persisted profile fact, whose write boundary owns the text
        # grammar. Same residual as the rule-3 exemption for
        # ``domain/deadlines/profiles.py``, and recorded as one rather than
        # tightened here: promoting the string at read time would leave the
        # unguarded write still writing it.
        return coerce_decimal_strict(base if isinstance(base, Decimal) else str(base).strip())
    except (InvalidOperation, ValueError):
        return None


def _sum_received_bases_for_year(
    grouped: Mapping[int, Mapping[str, object]],
    filing_year: int,
) -> Decimal | None:
    """Sum parseable attributed bases from rows matching the filing year."""
    total = ZERO
    matched = False
    for row in grouped.values():
        if not _row_matches_filing_year(row, filing_year):
            continue
        base = _coerce_received_base(row)
        if base is None:
            continue
        total += base
        matched = True
    return total if matched else None


def _attribution_received_base_for_year(
    facts: tuple[UserProfileFact, ...],
    filing_year: int,
) -> Decimal | None:
    """Return the summed attributed base for ``filing_year``, or None when absent.

    Groups ``attribution_received.N.*`` facts by row index and keeps the rows
    whose ``filing_year`` matches and that carry a parseable
    ``base_imponible_attributed``. Returns the summed base of the matching rows,
    or ``None`` when no row applies to the year (so the caller can distinguish
    "no facts" from "facts summing to zero").
    """
    grouped = _group_received_facts(facts)
    return _sum_received_bases_for_year(grouped, filing_year)


__all__ = ["_attribution_received_omission_advisory_findings"]
