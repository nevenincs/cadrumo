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
off the verify-time :class:`~domain.calculations.registry.RegistrySnapshot`
for the target modelo revision, the same authority the calculate path resolves
its registry formula against.

See Also:
    :func:`~application.modelo.profile_binding.inject_derived_autonomic_deduccion_facts`
        The calculate-path injector whose fail-closed branch this advisory
        surfaces to the operator.
    :func:`~application.modelo.profile_binding.madrid_nacimiento_adopcion_candidate_weighted_count`
        Shared candidate-count primitive: evaluates only the per-descendant
        window/cohabitation condition, independent of the unit's determinability.
    :func:`~application.modelo._verification_actions._collect_revision_verification_findings`
        Verification collector that appends this advisory beside the DT 12ª /
        art. 20 / art. 52 / Convenio LOB advisories using the same
        non-blocking mechanism.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...domain.modelos.work_unit import WorkUnit
from ...domain.user_profile.errors import ProfileNotFoundError
from ...domain.user_profile.loader import load_user_profile_schema
from ...domain.user_profile.values import UserProfileFactValue
from ..user_profile.profile_record_repository import ProfileRecordRepository
from ..user_profile.projections import profile_fact_index
from .profile_binding import (
    MADRID_AUTONOMIC_DEDUCCION_FILING_YEAR,
    is_indeterminate_unidad_familiar,
    is_madrid_resident,
    madrid_nacimiento_adopcion_candidate_weighted_count,
)
from .semantic_role_resolution import AmbiguousSemanticRoleCasillaError, casilla_id_for_unique_semantic_role

_MADRID_NACIMIENTO_ADOPCION_SEMANTIC_ROLE = "irpf_deduccion_madrid_nacimiento_adopcion"
_ADVISORY_LEGAL_REFS = (
    "ley-35-2006:art-77",
    "madrid-dl-1-2010:art-4",
    "madrid-dl-1-2010:art-18",
)


def _madrid_nacimiento_adopcion_eligibility_advisory_finding(
    snapshot: RegistrySnapshot,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    bucket_id: str,
) -> ModeloVerificationFinding | None:
    """Warn to confirm Madrid nacimiento/adopción eligibility for an indeterminate unit.

    Loads the bucket's :class:`~domain.user_profile.values.UserProfileRecord`
    directly (the same source the calculate-path injector reads) so the verify
    path can see the ``tax_residence.ccaa`` / ``renta_taxpayer.marital_status`` /
    ``renta_filing.declaration_type`` / ``renta_family.descendiente.*`` facts
    that :class:`~domain.deadlines.TaxpayerProfile` does not carry.

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
    if snapshot.filing_year != MADRID_AUTONOMIC_DEDUCCION_FILING_YEAR:
        return None

    try:
        casilla_id = casilla_id_for_unique_semantic_role(snapshot, _MADRID_NACIMIENTO_ADOPCION_SEMANTIC_ROLE)
    except AmbiguousSemanticRoleCasillaError as exc:
        raise ModeloError(str(exc), context=exc.ambiguity.context()) from exc
    if casilla_id is None:
        return None

    if casilla_values.get(casilla_id, Decimal(0)) != Decimal(0):
        # The auto-trigger already populated the casilla; nothing to advise.
        return None

    fact_index = _load_fact_index(bucket_id)
    if fact_index is None:
        return None

    if not is_madrid_resident(fact_index):
        return None
    if not is_indeterminate_unidad_familiar(fact_index):
        return None

    weighted_count = madrid_nacimiento_adopcion_candidate_weighted_count(fact_index, snapshot.filing_year)
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
        legal_refs=_ADVISORY_LEGAL_REFS,
    )


def _load_fact_index(bucket_id: str) -> dict[str, UserProfileFactValue] | None:
    """Return the bucket's profile fact index, or ``None`` when no profile exists."""
    try:
        record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return None
    schema = load_user_profile_schema()
    return profile_fact_index(record, schema)


def _madrid_nacimiento_adopcion_advisory_finding_for_work_unit(
    snapshot: RegistrySnapshot,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    work_unit: WorkUnit,
) -> ModeloVerificationFinding | None:
    """Convenience wrapper reading ``bucket_id`` off a :class:`WorkUnit`."""
    return _madrid_nacimiento_adopcion_eligibility_advisory_finding(
        snapshot,
        casilla_values,
        bucket_id=work_unit.bucket_id,
    )


__all__ = [
    "_madrid_nacimiento_adopcion_advisory_finding_for_work_unit",
    "_madrid_nacimiento_adopcion_eligibility_advisory_finding",
]
