"""What the taxpayer's own annual returns state about the imputation criterion of a year."""

from __future__ import annotations

from ...core.period import Period, StandardPeriodCode
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.bindings import RegistryModeloObservation
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.modelos.protocols import ModeloRecordCatalogueRepositoryProtocol
from ..aggregation.renta_imputation import ImputationFilingHistory, imputation_filing_history
from ..calculations.observations_repository import CalculationObservationRepositoryProtocol


def imputation_filings_from_repositories(
    *,
    bucket_id: str,
    year: int,
    observation_repository: CalculationObservationRepositoryProtocol,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    authority: PinnedAuthorityOperation,
) -> ImputationFilingHistory:
    """Read the filing history every reader of a year's criterion has to judge it by."""

    def load_filed(modelo: str, period: Period) -> RegistryModeloObservation | None:
        envelope = observation_repository.load_observation(modelo, period)
        return None if envelope is None else envelope.observation

    return imputation_filing_history(
        bucket_id=bucket_id,
        year=year,
        annual_form=form_for_role("renta.annual"),
        annual_period_code=StandardPeriodCode.ANNUAL.value,
        load_observation=load_filed,
        filing_records=filing_repository.load(),
        authority=authority,
    )


__all__ = ["imputation_filings_from_repositories"]
