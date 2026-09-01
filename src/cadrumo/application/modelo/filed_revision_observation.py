"""Persist a locally-filed calculation revision as a cross-period observation.

This is the local-filing sibling of the live-AEAT-capture persistence path
(:func:`~cadrumo.application.live.persist_filed_calculation_observation`). It does
NOT introduce a parallel write path: it is an additional projection of the
single-writer filing transition
(:func:`~cadrumo.application.modelo._revision_persistence.persist_filed_revision`),
co-emitted with ``MODELO_FILED``, that records the filed
:class:`~CalculationRevision` outputs into the
cross-period observation store so a later period's ``calculate`` can carry them
forward automatically via the ``previous_filing`` resolver.

The persisted observation is stamped with a NON-official ``source_kind``
(``app_filing``): a value an operator filed through the app is not external AEAT
evidence. The cross-period clean-state guard
(:mod:`~cadrumo.application.calculations.cross_period_clean_state`) treats any
``source_kind`` outside its official set as the
``LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`` blocker, so this carry feeds
calculate/draft but never satisfies the filing gate for a dependent period —
filing still requires real external evidence. ``app_filing`` MUST NOT gain the
official-AEAT capability.

Non-goal (grupo ``per_grupo_member`` fan-in): this helper persists the
single-filer ``(modelo, filing_year, period)`` row only. It does not stamp a
``member_nif`` and therefore does not feed the cross-member fan-in the 353<-322
aggregation enumerates; member-row persistence for the local filing flow is out
of scope and remains a live-capture concern.

The projection reads :class:`~CalculationRevision`
observations, rewrites the affected
:class:`~cadrumo.domain.calculations.registry.CasillaObservation` rows for refunded
Modelo 303 filings, and persists a
:class:`~cadrumo.domain.calculations.registry.RegistryModeloObservation` record.

See Also:
    :func:`~cadrumo.application.modelo._revision_persistence.persist_filed_revision`:
        Calls this projection after the filing catalogue write and
        ``MODELO_FILED`` event succeed.
    :func:`~cadrumo.domain.calculations.registry.resolve_previous_filing_binding_values`:
        Consumes stored
        :class:`~cadrumo.domain.calculations.registry.RegistryModeloObservation`
        rows for ``previous_filing`` bindings during calculation.
    :mod:`~cadrumo.application.calculations.cross_period_clean_state`:
        Classifies ``app_filing`` as non-official evidence for filing-grade
        readiness.
    :func:`~cadrumo.application.calculations.persist_observation_envelope_and_iva_history`:
        Atomically co-emits local Modelo 303 observations and IVA history.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from ...core.iva_compensation_provenance import IvaCompensationStateProvenance
from ...core.modelo import Modelo
from ...core.result_disposition import ResultDisposition
from ...domain.calculations.registry.bindings import RegistryModeloObservation
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.work_unit import WorkUnit
from ..calculations.iva_compensation_history import (
    IvaCompensationHistoryRepository,
    persist_observation_envelope_and_iva_history,
)
from ..calculations.observations_repository import (
    CalculationObservationRepository,
    ObservationSourceKind,
    PriorDomiciliationElectionProjection,
    ResultDispositionProjection,
    observation_key,
)
from .action_errors import ModeloLocalObservationError

APP_FILING_SOURCE_KIND: Final = ObservationSourceKind.APP_FILING
"""Non-official ``source_kind`` stamped on locally-filed observations.

Deliberately not official AEAT evidence: a locally-filed value must never
satisfy the cross-period clean-state filing gate.
"""


def _history_repository_in_observation_context(
    override: IvaCompensationHistoryRepository | None,
    *,
    observation_repository: CalculationObservationRepository,
) -> IvaCompensationHistoryRepository:
    """Return the IVA history repository bound to the observation's own store.

    One filed Modelo 303 period produces two rows that describe the same event:
    the cross-period carry observation and the IVA compensation history state.
    They are only coherent if they land in the same encrypted store, because the
    readers resolve each through the active bucket independently -- a split
    leaves the carry row discoverable while the history lookup returns ``None``,
    with nothing reporting the divergence.

    Nothing previously tied the two together. With no override the history
    repository resolved the ACTIVE bucket while ``observation_repository`` was
    whatever the caller threaded in, so even the default path could split; with
    an override the caller could pass an unrelated database outright.

    Deriving the default from ``observation_repository``'s own secure-object
    backend makes the shared context structural rather than coincidental. An
    override is still honoured -- the filing path and its tests legitimately
    supply one -- but only when it is backed by the same database; a foreign
    pairing is refused before either row is written, never half-persisted.
    """
    context = observation_repository.secure_object_repository
    if override is None:
        return IvaCompensationHistoryRepository(objects=context)
    override_context = override.secure_object_repository
    if override_context is context:
        return override
    if override_context.engine.url != context.engine.url:
        raise ModeloLocalObservationError(
            translated_message="application.modelo.errors.filed_observation_split_storage_context",
            context={
                "history_backend": str(override_context.engine.url),
                "observation_backend": str(context.engine.url),
            },
        )
    return IvaCompensationHistoryRepository(objects=context)


def require_filing_result_disposition(
    *,
    work_unit: WorkUnit,
    result_disposition: ResultDisposition | None,
) -> None:
    """Refuse a Modelo 303 filing whose result disposition was never resolved.

    The disposition is a determined fact resolved once at the calculate/file
    boundary by ``resolve_modelo_result_disposition``. This is a PRESENCE
    requirement and never a second derivation: recomputing it here would make
    a regulated determination answerable in two places, which is how the fichero
    an operator submits and the carry a later period reads come to disagree.

    Declared as a callable rather than left inline because the same condition has
    to hold at two positions in one filing transition: ahead of the first
    repository write, where a refusal leaves every catalogue untouched, and again
    at the observation write itself, which other callers reach directly. Two
    copies of the condition would be two authorities on when a filing is
    under-declared, and they would drift.
    """
    if work_unit.modelo == Modelo.M303.value and result_disposition is None:
        raise ModeloLocalObservationError(
            translated_message="errors.error.error_modelos",
            context={"modelo": work_unit.modelo, "period": work_unit.period.registry_token},
        )


def persist_filed_revision_observation(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    repository: CalculationObservationRepository,
    captured_at: datetime,
    result_disposition: ResultDisposition | None = None,
    prior_domiciliation_election: PriorDomiciliationElectionProjection | None = None,
    taxpayer_nif: str | None = None,
    filing_record_id: str | None = None,
    iva_compensation_history_repository: IvaCompensationHistoryRepository | None = None,
) -> str:
    """Persist a filed revision's casilla observations as a cross-period record.

    Projects the filed revision's provenance-bearing
    :class:`~CalculationRevision` ``observations`` (every
    casilla — inputs, bound, and computed alike, each already carrying
    ``legal_refs`` / ``source_refs`` / formula provenance) into a single
    :class:`~cadrumo.domain.calculations.registry.RegistryModeloObservation` keyed
    by the work unit's ``(modelo, filing_year, period)`` and saves it through the
    bucket-scoped
    :class:`~cadrumo.application.calculations.CalculationObservationRepository` with
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
        iva_compensation_history_repository: Optional repository override for
            the Modelo 303 history projection.

    Returns:
        The ``(modelo, filing_year, period)`` observation key string the record
        was stored under.

    The saved
    :class:`~cadrumo.domain.calculations.registry.RegistryModeloObservation` feeds
    later calculations through the registry ``previous_filing`` path, but its
    ``source_kind = "app_filing"`` keeps it outside official evidence. For
    locally filed Modelo 303 rows with a taxpayer NIF, the same observation is
    also converted into an
    :class:`~cadrumo.domain.iva_compensation.IvaCompensationPeriodState` via
    :func:`~cadrumo.application.calculations.persist_observation_envelope_and_iva_history`
    together with
    :class:`~cadrumo.application.calculations.IvaCompensationHistoryRepository`;
    that history is read only by the explicit IVA-wallet recurrence comparison
    path, not as a second direct owner of the effective casilla 110 value.

    See Also:
        :class:`~cadrumo.application.calculations.CalculationObservationRepository`:
            Stores the non-official cross-period observation envelope.
        :class:`~cadrumo.application.calculations.IvaCompensationHistoryRepository`:
            Stores the profile-local Modelo 303 compensation period state.
        :func:`~cadrumo.application.calculations.extract_modelo_303_local_iva_compensation_recurrence`:
            Reads the local IVA history for wallet reconciliation.
    """
    observation = RegistryModeloObservation(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
        observations=revision.observations,
    )
    key = observation_key(work_unit.modelo, work_unit.period)
    projects_iva_history = (
        work_unit.modelo == Modelo.M303.value and taxpayer_nif is not None and bool(taxpayer_nif.strip())
    )
    # Resolve the history repository BEFORE the carry write: both rows describe
    # the one filed period, so a mismatched pair must refuse with neither
    # written rather than leave the carry half behind for a reader to find.
    history_repo = (
        _history_repository_in_observation_context(
            iva_compensation_history_repository,
            observation_repository=repository,
        )
        if projects_iva_history
        else None
    )
    require_filing_result_disposition(work_unit=work_unit, result_disposition=result_disposition)
    disposition_projection = (
        ResultDispositionProjection(
            disposition=result_disposition,
            provenance_kind="app_filing",
            provenance_locator=f"local-filing:{filing_record_id or key}",
        )
        if result_disposition is not None
        else None
    )
    payload = repository.prepare_observation_envelope(
        observation,
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=captured_at,
        stamped_revision_id=work_unit.revision_id,
        result_disposition=disposition_projection,
        prior_domiciliation_election=prior_domiciliation_election,
        normalize_m303_carry=work_unit.modelo == Modelo.M303.value,
    )
    if history_repo is not None and taxpayer_nif is not None:
        filing_ref = filing_record_id or key
        persist_observation_envelope_and_iva_history(
            observation_repository=repository,
            history_repository=history_repo,
            envelope=payload,
            taxpayer_nif=taxpayer_nif.strip(),
            provenance=IvaCompensationStateProvenance.APP_FILING,
            source_observation_key=f"{key}:local:{filing_ref[:64]}",
        )
    else:
        repository.save(payload)
    return key


__all__ = [
    "APP_FILING_SOURCE_KIND",
    "persist_filed_revision_observation",
    "require_filing_result_disposition",
]
