"""The advisory for an enrolled deducción whose unidad familiar income limit cannot be read.

An enrolment on the descendant entry-window axis whose comunidad limits the income
of the whole unidad familiar needs the other members' base imponible, which no
stored fact holds. For a joint return or a partnered filer the shared dispatch
(:mod:`~application.modelo.autonomic_deduccion_dispatch`) therefore resolves the
box to zero, the over-claim-safe default, until a door lets the filer state that
base. This advisory is the surface half of that default: when the filer resides in
the enrolment's comunidad, at least one descendant is inside the window, the unit is
indeterminate and the box resolved to zero, it emits a non-blocking ADVISORY asking
the filer to confirm the entitlement and enter the deducción by hand.

The window count and the indeterminacy test are the dispatch's own primitives, so
calculation and verification read one answer.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId
from ...core.casilla_value_absence import AbsentCasillaReading
from ...domain.calculations.registry.autonomic_deduccion_enrolment import (
    AutonomicDeduccionEnrolment,
    AutonomicIncomeLimit,
    AutonomicIncomeUnit,
    DescendantEntryWindowAxis,
)
from ...domain.calculations.registry.autonomic_deduccion_enrolment_checks import autonomic_deduccion_enrolments
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.ids import LegalRefId
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.contribuyente.family_fact_context import FamilyFactResolutionContext
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...domain.modelos.work_unit import WorkUnit
from ...domain.user_profile.errors import ProfileNotFoundError
from ...domain.user_profile.values import UserProfileFactValue
from ..user_profile.profile_record_repository import ProfileRecordRepository
from ..user_profile.projections import profile_fact_index
from .autonomic_deduccion_dispatch import (
    descendant_entry_window_weighted_count,
    is_indeterminate_unidad_familiar,
    residence_ccaa,
)
from .calculation_input_refusal_doors import semantic_role_ambiguous_verdict
from .registry_input_refusals import registry_integrity_verdict
from .semantic_role_resolution import AmbiguousSemanticRoleCasillaError, casilla_id_for_unique_semantic_role

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from .work_profile import ModeloWorkProfile


def _require_formula_legal_refs(
    snapshot: RegistrySnapshot, legal_refs: tuple[LegalRefId, ...], formula_id: str
) -> tuple[LegalRefId, ...]:
    """Reject formula legal references absent from the selected authority."""
    missing = tuple(ref for ref in legal_refs if ref not in snapshot.legal)
    if missing:
        raise RegistryValidationError(
            f"autonomic deducción advisory formula {formula_id!r} has legal refs absent from the selected "
            f"authority: {missing!r}",
            precondition_verdict=registry_integrity_verdict("madrid_nacimiento_adopcion_advisory"),
        )
    return tuple(legal_refs)


def _advisory_legal_refs(snapshot: RegistrySnapshot, casilla_id: CasillaId) -> tuple[LegalRefId, ...]:
    """Project the advisory's grounding from the selected registry formula.

    The advisory concerns a computed casilla, so its legal grounding is the
    formula's typed provenance rather than a second application-owned tuple.
    Refuse an incomplete or out-of-snapshot declaration instead of emitting a
    finding whose legal references cannot be checked against the selected
    authority.
    """
    casilla = next((candidate for candidate in snapshot.revision.casillas if candidate.id == casilla_id), None)
    if casilla is None or casilla.formula is None:
        raise RegistryValidationError(
            f"autonomic deducción advisory casilla {casilla_id!r} has no registry formula provenance",
            precondition_verdict=registry_integrity_verdict("madrid_nacimiento_adopcion_advisory"),
        )
    formula = next((candidate for candidate in snapshot.revision.formulas if candidate.id == casilla.formula), None)
    if formula is None or not formula.legal_refs:
        raise RegistryValidationError(
            f"autonomic deducción advisory formula {casilla.formula!r} has no legal provenance",
            precondition_verdict=registry_integrity_verdict("madrid_nacimiento_adopcion_advisory"),
        )
    return _require_formula_legal_refs(snapshot, formula.legal_refs, formula.id)


def _unit_limited_window_enrolments(
    snapshot: RegistrySnapshot,
) -> list[tuple[DescendantEntryWindowAxis, AutonomicDeduccionEnrolment]]:
    """The edition's window-axis enrolments whose income limit covers the whole unidad familiar."""
    return [
        (enrolment.eligibility, enrolment)
        for _formula, enrolment in autonomic_deduccion_enrolments(snapshot.revision)
        if isinstance(enrolment.eligibility, DescendantEntryWindowAxis)
        and isinstance(enrolment.income_limit, AutonomicIncomeLimit)
        and enrolment.income_limit.unit is AutonomicIncomeUnit.UNIDAD_FAMILIAR
    ]


def _zero_box(
    snapshot: RegistrySnapshot, enrolment: AutonomicDeduccionEnrolment, casilla_values: Mapping[CasillaId, Decimal]
) -> CasillaId | None:
    """The enrolment's box when the calculation resolved it to zero, else ``None``."""
    try:
        casilla_id = casilla_id_for_unique_semantic_role(snapshot, enrolment.target_semantic_role)
    except AmbiguousSemanticRoleCasillaError as exc:
        raise ModeloError(
            str(exc),
            translated_message="application.modelo.errors.semantic_role_ambiguous",
            context=exc.ambiguity.context(),
            precondition_verdict=semantic_role_ambiguous_verdict(exc.ambiguity.semantic_role),
        ) from exc
    if casilla_id is None:
        return None
    if AbsentCasillaReading.ADVISORY_GAP_OPERAND.read(casilla_values, casilla_id) != Decimal(0):
        return None
    return casilla_id


def madrid_nacimiento_adopcion_eligibility_advisory_finding(
    snapshot: RegistrySnapshot,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None = None,
) -> ModeloVerificationFinding | None:
    """Warn to confirm a window deducción's entitlement for a unit whose income limit cannot be read.

    Considers each enrolment of the edition on the descendant entry-window axis with
    a unidad familiar income limit. Fires for the first whose comunidad is the
    filer's residence, whose box resolved to zero, whose unit is indeterminate (a
    joint return or a partnered filer) and whose window count is strictly positive.
    Returns ``None`` when no enrolment qualifies or the bucket has no profile.
    """
    candidates = _unit_limited_window_enrolments(snapshot)
    if not candidates:
        return None
    fact_index = load_fact_index(bucket_id, operation=operation, profile=profile)
    if fact_index is None or not is_indeterminate_unidad_familiar(fact_index):
        return None
    coordinate = date(snapshot.filing_year, 12, 31)
    family_context = FamilyFactResolutionContext(authority=operation, filing_period=coordinate, devengo_date=coordinate)
    for eligibility, enrolment in candidates:
        if enrolment.ccaa != residence_ccaa(fact_index):
            continue
        casilla_id = _zero_box(snapshot, enrolment, casilla_values)
        if casilla_id is None:
            continue
        weighted_count = descendant_entry_window_weighted_count(
            fact_index,
            snapshot.filing_year,
            following_periods=family_context.integer(eligibility.following_periods_fact),
            context=family_context,
        )
        if weighted_count <= 0:
            continue
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.ADVISORY,
            severity=ModeloVerificationFindingSeverity.WARNING,
            casilla_id=casilla_id,
            message_locale_key="application.modelo.findings.madrid_nacimiento_adopcion_eligibility_advisory",
            message_facts={"casilla_id": casilla_id, "weighted_count": weighted_count},
            legal_refs=_advisory_legal_refs(snapshot, casilla_id),
        )
    return None


def load_fact_index(
    bucket_id: str,
    *,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None,
) -> dict[str, UserProfileFactValue] | None:
    """Return the bucket's profile fact index, or ``None`` when no profile exists."""
    if profile is not None:
        return profile_fact_index(profile.record, profile.profile_decode_context.schema)
    try:
        repository = ProfileRecordRepository.for_current_session(
            bucket_id,
            profile_decode_context=operation.profile_decode_context(),
        )
        record = repository.load(bucket_id)
    except ProfileNotFoundError:
        return None
    return profile_fact_index(record, repository.session.profile_decode_context.schema)


def madrid_nacimiento_adopcion_advisory_finding_for_work_unit(
    snapshot: RegistrySnapshot,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    work_unit: WorkUnit,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None = None,
) -> ModeloVerificationFinding | None:
    """Convenience wrapper reading ``bucket_id`` off a :class:`WorkUnit`.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
    """
    return madrid_nacimiento_adopcion_eligibility_advisory_finding(
        snapshot,
        casilla_values,
        bucket_id=work_unit.bucket_id,
        operation=operation,
        profile=profile,
    )


__all__ = [
    "madrid_nacimiento_adopcion_advisory_finding_for_work_unit",
    "madrid_nacimiento_adopcion_eligibility_advisory_finding",
]
