"""Populate cross-period filing fixtures through canonical prepared write batches."""

from __future__ import annotations

from datetime import datetime

from ....core.result_disposition import ResultDisposition
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.modelos.work_unit import WorkUnit
from ...calculations.iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol
from ...calculations.observations_repository import (
    CalculationObservationRepositoryProtocol,
    PriorDomiciliationElectionProjection,
)
from ..filed_revision_observation import (
    PreparedFiledRevisionObservation,
    filed_revision_observation_writes,
    prepare_filed_revision_observation,
)


def persist_filed_revision_observation(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    repository: CalculationObservationRepositoryProtocol,
    captured_at: datetime,
    result_disposition: ResultDisposition | None = None,
    prior_domiciliation_election: PriorDomiciliationElectionProjection | None = None,
    taxpayer_nif: str | None = None,
    filing_record_id: str | None = None,
    iva_compensation_history_repository: IvaCompensationHistoryRepositoryProtocol,
    prepared: PreparedFiledRevisionObservation | None = None,
) -> str:
    """Persist a filed revision's casilla observations as a cross-period record.

    Projects the filed revision's provenance-bearing
    :class:`~CalculationRevision` ``observations`` (every
    casilla — inputs, bound, and computed alike, each already carrying
    ``legal_refs`` / ``source_refs`` / formula provenance) into a single
    :class:`~cadrumo.domain.calculations.registry.bindings.RegistryModeloObservation` keyed
    by the work unit's ``(modelo, filing_year, period)`` and saves it through the
    bucket-scoped
    :class:`~cadrumo.application.calculations.observations_repository.CalculationObservationRepositoryProtocol` with
    the NON-official ``source_kind = "app_filing"``.

    Args:
        revision: The just-filed
            :class:`~CalculationRevision` whose typed
            observations are projected.
        work_unit: The revision's parent
            :class:`~WorkUnit`, supplying the ``(modelo,
            filing_year, period)`` key.
        repository: The bucket-scoped observation repository (the same instance
            the filing transition threads through, so the write lands in the
            active bucket's encrypted store).
        captured_at: The filing timestamp, stamped on the stored record.
        result_disposition: The single typed ``Tipo de declaración`` resolved
            at the filing boundary. Required for Modelo 303 carry ingress and
            retained with ``app_filing`` provenance in the persisted envelope.
        prior_domiciliation_election: Safe semantic election and, when the
            marker is ``X``, its official baseline-U join. It never contains
            account data and is retained on the local filing observation.
        taxpayer_nif: Taxpayer NIF from the active profile. When supplied for a
            locally filed Modelo 303, the same observation is projected into the
            profile-local IVA compensation history repository.
        filing_record_id: Local filing record id used only to distinguish the
            ``source_observation_key``. ``APP_FILING`` provenance is declared
            by the required enum.
        iva_compensation_history_repository: Required repository capability for
            the Modelo 303 history projection.
        prepared: The observation :func:`prepare_filed_revision_observation`
            already validated for this filing; prepared here when omitted.

    Returns:
        The ``(modelo, filing_year, period)`` observation key string the record
        was stored under.

    The saved
    :class:`~cadrumo.domain.calculations.registry.bindings.RegistryModeloObservation` feeds
    later calculations through the registry ``previous_filing`` path, but its
    ``source_kind = "app_filing"`` keeps it outside official evidence. For
    locally filed Modelo 303 rows with a taxpayer NIF, the same observation is
    also converted into an
    :class:`~cadrumo.domain.iva_compensation.carry_forward.IvaCompensationPeriodState` via
    :func:`~cadrumo.application.calculations.iva_compensation_history.persist_observation_envelope_and_iva_history`
    together with
    :class:`~cadrumo.application.calculations.iva_compensation_history_ports.IvaCompensationHistoryRepositoryProtocol`;
    that history is read only by the explicit IVA-wallet recurrence comparison
    path, not as a second direct owner of the effective casilla 110 value.

    See Also:
        :class:`~cadrumo.application.calculations.observations_repository.CalculationObservationRepositoryProtocol`:
            Stores the non-official cross-period observation envelope.
        :class:`~cadrumo.application.calculations.iva_compensation_history_ports.IvaCompensationHistoryRepositoryProtocol`:
            Stores the profile-local Modelo 303 compensation period state.
        :func:`~cadrumo.application.calculations.binding_prefill.extract_modelo_303_local_iva_compensation_recurrence`:
            Reads the local IVA history for wallet reconciliation.
    """
    if prepared is None:
        prepared = prepare_filed_revision_observation(
            revision=revision,
            work_unit=work_unit,
            repository=repository,
            captured_at=captured_at,
            result_disposition=result_disposition,
            prior_domiciliation_election=prior_domiciliation_election,
            taxpayer_nif=taxpayer_nif,
            filing_record_id=filing_record_id,
            iva_compensation_history_repository=iva_compensation_history_repository,
        )
    repository.secure_object_repository.apply_batch(
        filed_revision_observation_writes(
            prepared,
            repository=repository,
            taxpayer_nif=taxpayer_nif,
            filing_record_id=filing_record_id,
        ),
    )
    return prepared.key
