"""Madrid nacimiento/adopción indeterminate-eligibility advisory for verification.

The Madrid nacimiento/adopción deducción autonómica (casilla 1039, DL 1/2010
arts. 4 y 18.1) auto-populates on the calculate path only for the determinable
single/monoparental individual filer
(:func:`~application.modelo.profile_binding.inject_derived_autonomic_deduccion_facts`);
a tributación conjunta declaration or a married/pareja-de-hecho filer is
fail-closed by design because the unidad-familiar 61.860 € límite needs the
spouse's base imponible, which the app does not persist. That fail-closed
branch resolves casilla 1039 to zero with no operator-facing signal that the
entitlement might still exist.

This module implements the advisory: when the filer is a Madrid
resident with at least one nacimiento/adopción-eligible descendant, the unit is
indeterminate (conjunta or married/partnered), and casilla 1039 has resolved to
zero, emit a non-blocking ADVISORY prompting the operator to confirm eligibility
and consider entering the deducción manually. The finding stays advisory
because the unidad-familiar income-limit gate genuinely cannot be evaluated
from data this application holds (``no-silent-under-declaration`` is
symmetric for a deducción: over-claim, not silence, is the hazard the
calculate-path fail-closed default already guards against; this advisory is
the surface half of that same guard).

The advisory reads the casilla-1039 semantic role and the resolved input value
off the verify-time :class:`~domain.calculations.registry.schema.RegistrySnapshot`
for the target modelo revision, the same authority the calculate path resolves
its registry formula against.

See Also:
    :func:`~application.modelo.profile_binding.inject_derived_autonomic_deduccion_facts`
        The calculate-path injector whose fail-closed branch this advisory
        surfaces to the operator.
    :func:`~application.modelo.profile_binding.madrid_nacimiento_adopcion_candidate_weighted_count`
        Shared candidate-count primitive: evaluates only the per-descendant
        window/cohabitation condition, independent of the unit's determinability.
    :func:`~application.modelo.verification_actions._collect_revision_verification_findings`
        Verification collector that appends this advisory beside the DT 12ª /
        art. 20 / art. 52 / Convenio LOB advisories using the same
        non-blocking mechanism.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId
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
from .profile_binding import (
    is_indeterminate_unidad_familiar,
    is_madrid_autonomic_deduccion_filing_year,
    is_madrid_resident,
    madrid_nacimiento_adopcion_candidate_weighted_count,
)
from .semantic_role_resolution import AmbiguousSemanticRoleCasillaError, casilla_id_for_unique_semantic_role

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from .work_profile import ModeloWorkProfile

_MADRID_NACIMIENTO_ADOPCION_SEMANTIC_ROLE = "irpf_deduccion_madrid_nacimiento_adopcion"


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
            f"Madrid nacimiento/adopción advisory casilla {casilla_id!r} has no registry formula provenance",
        )
    formula = next((candidate for candidate in snapshot.revision.formulas if candidate.id == casilla.formula), None)
    if formula is None or not formula.legal_refs:
        raise RegistryValidationError(
            f"Madrid nacimiento/adopción advisory formula {casilla.formula!r} has no legal provenance",
        )
    missing = tuple(ref for ref in formula.legal_refs if ref not in snapshot.legal)
    if missing:
        raise RegistryValidationError(
            f"Madrid nacimiento/adopción advisory formula {formula.id!r} has legal refs absent from the selected "
            f"authority: {missing!r}",
        )
    return tuple(formula.legal_refs)


def madrid_nacimiento_adopcion_eligibility_advisory_finding(
    snapshot: RegistrySnapshot,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None = None,
) -> ModeloVerificationFinding | None:
    """Warn to confirm Madrid nacimiento/adopción eligibility for an indeterminate unit.

    Loads the bucket's :class:`~domain.user_profile.values.UserProfileRecord`
    directly (the same source the calculate-path injector reads) so the verify
    path can see the ``tax_residence.ccaa`` / ``renta_taxpayer.marital_status`` /
    ``renta_filing.declaration_type`` / ``renta_family.descendiente.*`` facts
    that :class:`~domain.deadlines.models.TaxpayerProfile` does not carry.

    Fires only when ALL of the following hold: the revision is the 2025 M100
    filing year the first-slice registry formula covers; the filer is a Madrid
    resident; at least one descendant is inside the nacimiento/adopción
    applicability window and cohabits (the candidate weighted count is
    strictly positive); the unit is indeterminate (tributación conjunta or a
    married/pareja-de-hecho filer — the same condition that makes the
    calculate-path injector fail-closed); and casilla 1039 resolved to zero (the
    auto-trigger did not fire). A determinate single/monoparental filer whose
    entitlement was already auto-populated, or a unit with no eligible
    descendant, never fires this advisory.

    Returns ``None`` when the bucket carries no profile record, the revision
    does not declare the casilla-1039 semantic role, or any of the firing
    conditions above is not met.
    """
    try:
        casilla_id = casilla_id_for_unique_semantic_role(snapshot, _MADRID_NACIMIENTO_ADOPCION_SEMANTIC_ROLE)
    except AmbiguousSemanticRoleCasillaError as exc:
        raise ModeloError(str(exc), context=exc.ambiguity.context()) from exc
    if casilla_id is None:
        return None

    if casilla_values.get(casilla_id, Decimal(0)) != Decimal(0):
        # The auto-trigger already populated the casilla; nothing to advise.
        return None

    fact_index = _load_fact_index(
        bucket_id,
        operation=operation,
        profile=profile,
    )
    if fact_index is None:
        return None

    if not is_madrid_resident(fact_index):
        return None
    if not is_indeterminate_unidad_familiar(fact_index):
        return None

    coordinate = date(snapshot.filing_year, 12, 31)
    family_context = FamilyFactResolutionContext(authority=operation, filing_period=coordinate, devengo_date=coordinate)
    if not is_madrid_autonomic_deduccion_filing_year(
        snapshot.filing_year,
        context=family_context,
        operation=operation,
    ):
        return None
    weighted_count = madrid_nacimiento_adopcion_candidate_weighted_count(
        fact_index,
        snapshot.filing_year,
        context=family_context,
        operation=operation,
    )
    if weighted_count <= 0:
        return None

    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        casilla_id=casilla_id,
        message_locale_key="application.modelo.findings.madrid_nacimiento_adopcion_eligibility_advisory",
        message_facts={
            "casilla_id": casilla_id,
            "weighted_count": weighted_count,
        },
        legal_refs=_advisory_legal_refs(snapshot, casilla_id),
    )


def _load_fact_index(
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
    """Convenience wrapper reading ``bucket_id`` off a :class:`WorkUnit`."""
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
