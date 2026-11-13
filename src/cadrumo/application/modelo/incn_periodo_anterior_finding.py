"""The Modelo 200 finding raised when the held preceding return and the stated twelve-month turnover disagree.

LIS art. 29.1 and art. 101 read the importe neto de la cifra de negocios of the
período impositivo inmediato anterior. When that período lasted twelve months,
the turnover the filer states on the profile for the twelve months before the
período began is that período's own, so it must equal the net turnover the
held preceding Modelo 200 declares. When they differ, neither is taken over
the other: the verification blocks with both figures and the filer corrects
the one that is wrong.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Final

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
)
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...domain.modelos.work_unit import WorkUnit
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..calculations.iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol
from ..calculations.observations_repository import CalculationObservationRepositoryProtocol
from ..filing.producer_snapshot import FilingProducerSnapshotError
from .export_m202_profile import INCN_PRIOR_12_MONTHS_PATH
from .export_periodo_impositivo import periodo_impositivo_from_facts
from .incn_periodo_anterior import (
    INCN_PERIODO_ANTERIOR_BINDING_ID,
    IncnPeriodoAnteriorGap,
    IncnPeriodoAnteriorStores,
    resolve_incn_periodo_anterior,
)
from .profile_export_binding import resolve_profile_path_values

INCN_PERIODO_ANTERIOR_DISAGREES_KEY: Final = "application.modelo.findings.m200_incn_periodo_anterior_disagrees"
"""The served words of the finding: the held return and the stated twelve-month turnover differ."""

_IS_ANNUAL_ROLE: Final = "sociedades.annual"


def incn_periodo_anterior_disagreement_finding(
    *,
    work_unit: WorkUnit,
    workflow_profile: TaxpayerProfile,
    operation: PinnedAuthorityOperation,
    observation_repository: CalculationObservationRepositoryProtocol,
    iva_compensation_history_repository: IvaCompensationHistoryRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
) -> ModeloVerificationFinding | None:
    """Return the blocking finding when the two figures for the preceding período disagree, else ``None``.

    ``None`` too for any other modelo, when the profile states no twelve-month
    turnover, when the período facts are unstated (their own gates name them),
    when the preceding período was shorter than twelve months (its turnover is
    not the twelve-month one), and when no work catalogue is bound.
    """
    if work_unit_repository is None or str(work_unit.modelo) != form_for_role(_IS_ANNUAL_ROLE, authority=operation):
        return None
    stated = workflow_profile.incn_prior_12_months
    if stated is None:
        return None
    if not _prior_lasted_twelve_months(work_unit, operation):
        return None
    located = resolve_incn_periodo_anterior(
        work_unit.bucket_id,
        work_unit.filing_year,
        stores=IncnPeriodoAnteriorStores(
            operation=operation,
            observation_repository=observation_repository,
            iva_compensation_history_repository=iva_compensation_history_repository,
            calculation_repository=calculation_repository,
            work_unit_repository=work_unit_repository,
            filing_repository=filing_repository,
        ),
        activity_start_date=workflow_profile.activity_start_date,
        twelve_month_statement=stated,
    )
    held_value = located.held_value
    if located.gap is not IncnPeriodoAnteriorGap.TWELVE_MONTH_STATEMENT_DISAGREES or held_value is None:
        return None
    return _disagreement_finding(
        work_unit,
        held_value=held_value,
        source_filing_year=located.source_filing_year,
        stated=stated,
        operation=operation,
    )


def _prior_lasted_twelve_months(work_unit: WorkUnit, operation: PinnedAuthorityOperation) -> bool:
    """Whether the preceding período lasted twelve months; ``False`` while the período facts are unstated."""
    # The ejercicio of a Modelo 200 is the período that begins in its filing year.
    last_day = date(work_unit.filing_year, 12, 31)
    try:
        periodo = periodo_impositivo_from_facts(
            modelo=str(work_unit.modelo),
            on=last_day,
            profile_values=resolve_profile_path_values(
                bucket_id=work_unit.bucket_id, operation=operation, as_of=last_day
            ),
        )
    except FilingProducerSnapshotError:
        return False
    return periodo.prior_lasted_twelve_months


def _disagreement_finding(
    work_unit: WorkUnit,
    *,
    held_value: Decimal,
    source_filing_year: int | None,
    stated: Decimal,
    operation: PinnedAuthorityOperation,
) -> ModeloVerificationFinding:
    """The blocking finding naming both figures, cited to the binding that reads the preceding turnover."""
    snapshot = operation.reading_snapshot(
        work_unit.modelo, filing_year=work_unit.filing_year, period=work_unit.period.registry_token
    )
    binding = next(binding for binding in snapshot.revision.bindings if binding.id == INCN_PERIODO_ANTERIOR_BINDING_ID)
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.RECONCILIATION_MISMATCH,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key=INCN_PERIODO_ANTERIOR_DISAGREES_KEY,
        message_facts={
            "modelo": str(work_unit.modelo),
            "filing_year": work_unit.filing_year,
            "source_filing_year": source_filing_year or work_unit.filing_year - 1,
            "held_turnover": held_value,
            "stated_turnover": stated,
            "profile_path": INCN_PRIOR_12_MONTHS_PATH,
        },
        legal_refs=tuple(binding.legal_refs),
        source_refs=tuple(citation.source_ref for citation in binding.source_citations),
    )


__all__ = ["INCN_PERIODO_ANTERIOR_DISAGREES_KEY", "incn_periodo_anterior_disagreement_finding"]
