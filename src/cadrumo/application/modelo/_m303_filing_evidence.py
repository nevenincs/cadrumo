"""Atomic Modelo 303 filing-evidence validation before revision persistence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

from ...core import CasillaId, Modelo
from ...domain.calculations.registry import (
    CasillaObservation,
    RegistrySnapshot,
    resolve_m303_regimen_simplificado_snapshot,
)
from ...domain.deadlines import TaxpayerProfile
from ...domain.iva import is_last_filing_period_of_year, validate_regimen_simplificado_rows
from ...domain.modelos import FilingInstanceEvidence, ModeloError, WorkUnit
from ...domain.user_profile import ProfileNotFoundError, UserProfileStatus
from ..user_profile import UserProfileLifecycleRepository, projection_for_taxpayer
from ._action_errors import ModeloProfileReadinessError
from ._m303_regimen_simplificado_scope import m303_regimen_simplificado_scope_for_profile


def validate_m303_filing_instance_evidence_for_revision(
    *,
    work_unit: WorkUnit,
    registry_snapshot: RegistrySnapshot,
    evidence: FilingInstanceEvidence | None,
    casilla_values: Mapping[CasillaId, Decimal],
    observations: Sequence[CasillaObservation],
) -> FilingInstanceEvidence | None:
    """Validate the complete revision evidence against every canonical owner."""
    if work_unit.modelo != Modelo.M303:
        if evidence is not None:
            raise ModeloError("filing-instance evidence is currently valid only for modelo 303 revisions")
        return None
    if evidence is None:
        raise ModeloError("modelo 303 filing-instance evidence is required before calculation revision creation")
    m303 = evidence.m303
    if m303.period != work_unit.period:
        raise ModeloError("modelo 303 filing-instance evidence period must match its work unit")

    regimen = m303.regimen_simplificado
    profile = _active_taxpayer_profile(work_unit)
    if regimen.scope_decision != m303_regimen_simplificado_scope_for_profile(profile):
        raise ModeloError(
            "modelo 303 simplified-regime evidence scope must match the canonical IVA profile composition"
        )
    expected_snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=regimen.scope_decision,
    )
    if regimen.regimen_snapshot != expected_snapshot:
        raise ModeloError("modelo 303 simplified-regime evidence does not match the selected registry snapshot")
    censo_iae_epigraphs: frozenset[str] = frozenset({profile.iae_epigraph}) if profile.iae_epigraph else frozenset()
    validate_regimen_simplificado_rows(
        regimen.rows,
        orden=regimen.regimen_snapshot.orden.activities,
        applicable=not regimen.scope_decision.is_not_claimed,
        censo_iae_epigraphs=censo_iae_epigraphs,
    )

    exonerado = m303.exonerado_390
    if exonerado.applicable and not is_last_filing_period_of_year(work_unit.period):
        raise ModeloError("modelo 303 exonerado-390 evidence is applicable only in the final filing period")
    expected_ids = {
        casilla.id
        for casilla in registry_snapshot.revision.casillas
        if tuple(casilla.section)[:2] == ("iva", "exonerado_390")
    }
    actual_values = {endpoint.casilla_id: endpoint.value for endpoint in exonerado.endpoints}
    if exonerado.applicable and set(actual_values) != expected_ids:
        raise ModeloError("modelo 303 exonerado-390 evidence must cover every canonical A28 endpoint exactly once")
    if not exonerado.applicable and actual_values:
        raise ModeloError("non-applicable modelo 303 exonerado-390 evidence must not carry endpoint facts")
    if exonerado.applicable:
        revision_values = {casilla_id: casilla_values.get(casilla_id) for casilla_id in expected_ids}
        if revision_values != actual_values:
            raise ModeloError("modelo 303 exonerado-390 evidence values disagree with the calculated revision")
        observation_values = {
            observation.casilla_id: observation.value
            for observation in observations
            if observation.casilla_id in expected_ids
        }
        if observation_values != actual_values:
            raise ModeloError("modelo 303 exonerado-390 evidence values disagree with typed observations")
    return evidence


def _active_taxpayer_profile(work_unit: WorkUnit) -> TaxpayerProfile:
    try:
        record = UserProfileLifecycleRepository(bucket_id=work_unit.bucket_id).load(work_unit.bucket_id)
    except ProfileNotFoundError as exc:
        raise ModeloProfileReadinessError("Modelo 303 requires an active secure profile") from exc
    if record.status is not UserProfileStatus.ACTIVE:
        raise ModeloProfileReadinessError("Modelo 303 requires an active secure profile")
    return projection_for_taxpayer(record)


__all__ = ["validate_m303_filing_instance_evidence_for_revision"]
