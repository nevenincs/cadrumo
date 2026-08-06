"""Persist a locally-filed calculation revision as a cross-period observation.

This is the local-filing sibling of the live-AEAT-capture persistence path
(:func:`~cadrumo.application.live.persist_filed_calculation_observation`). It does
NOT introduce a parallel write path: it is an additional projection of the
single-writer filing transition
(:func:`~cadrumo.application.modelo._revision_persistence.persist_filed_revision`),
co-emitted with ``MODELO_FILED``, that records the filed
:class:`~cadrumo.domain.modelos.CalculationRevision` outputs into the
cross-period observation store so a later period's ``calculate`` can carry them
forward automatically via the ``previous_filing`` resolver.

The persisted observation is stamped with a NON-official ``source_kind``
(``app_filing``): a value an operator filed through the app is not external AEAT
evidence. The cross-period clean-state guard
(:mod:`~cadrumo.application.calculations._cross_period_clean_state`) treats any
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

The projection reads :class:`~cadrumo.domain.modelos.CalculationRevision`
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
    :mod:`~cadrumo.application.calculations._cross_period_clean_state`:
        Classifies ``app_filing`` as non-official evidence for filing-grade
        readiness.
    :func:`~cadrumo.application.calculations.iva_compensation_state_from_registry_observation`:
        Projects local Modelo 303 observations into the IVA compensation history.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Final

from ...core import Modelo
from ...domain.calculations.registry import (
    CasillaId,
    CasillaObservation,
    RegistryModeloObservation,
    validated_casilla_id,
)
from ...domain.modelos import CalculationRevision, WorkUnit
from ..calculations import (
    CalculationObservationRepository,
    IvaCompensationHistoryRepository,
    ObservationSourceKind,
    iva_compensation_state_from_registry_observation,
    observation_key,
)
from ._action_errors import ModeloLocalObservationError

APP_FILING_SOURCE_KIND: Final = ObservationSourceKind.APP_FILING
"""Non-official ``source_kind`` stamped on locally-filed observations.

Deliberately not official AEAT evidence: a locally-filed value must never
satisfy the cross-period clean-state filing gate.
"""


def _casilla_id(value: object) -> CasillaId:
    """Validate a static filed-observation casilla constant.

    Returns a :class:`~cadrumo.domain.calculations.registry.CasillaId`.
    """
    try:
        return validated_casilla_id(value, surface="filed-revision observation casilla constant")
    except ValueError as exc:
        raise RuntimeError(f"filed-revision observation casilla constant {value!r} is not a CasillaId") from exc


#: Canonical id for the Modelo 303 end-of-period available compensation carry-forward casilla. A
#: refunded (devolución) period must carry ZERO generated credit forward, so when
#: the filed revision is refunded this casilla is re-stamped to its posterior-only
#: value before the cross-period observation is persisted (RD 1624/1992 art. 30 /
#: Ley 37/1992 art. 116).
_M303_DISPONIBLE_CASILLA: Final[CasillaId] = _casilla_id("iva.compensacion-disponible-fin-periodo")
#: Canonical id for Modelo 303 compensación pendiente de periodos posteriores (AEAT box 87):
#: the posterior-only component that survives a refund.
_M303_POSTERIOR_CASILLA: Final[CasillaId] = _casilla_id("iva.compensacion-pendiente-periodos-posteriores")
#: The per-period generated-credit casilla, zeroed on a refunded period.
_M303_GENERADA_CASILLA: Final[CasillaId] = _casilla_id("iva.compensacion-generada-periodo")
_ZERO: Final = Decimal("0")


def _refunded_303_observations(
    observations: tuple[CasillaObservation, ...],
) -> tuple[CasillaObservation, ...]:
    """Zero the generated-credit components of a refunded Modelo 303 observation.

    A refunded (devolución) period is requested as devolución rather than
    compensación carry, so the persisted cross-period carry must drop the generated credit:
    ``iva.compensacion-disponible-fin-periodo`` is re-stamped to its
    posterior-only value from ``iva.compensacion-pendiente-periodos-posteriores``
    (AEAT box 87) and ``iva.compensacion-generada-periodo`` to zero. Every other
    casilla is preserved verbatim — including its provenance — so the carried
    observation stays a faithful projection of the filed revision except for the
    one disposition-determined correction.

    The rewrite is applied only to the
    :class:`~cadrumo.domain.calculations.registry.CasillaObservation` rows that
    encode the generated compensation credit. It leaves the filed revision's
    remaining observations and provenance unchanged so the saved
    :class:`~cadrumo.domain.calculations.registry.RegistryModeloObservation` still
    represents the local filing.
    """
    by_id = {item.casilla_id: item for item in observations}
    posterior = by_id.get(_M303_POSTERIOR_CASILLA)
    posterior_value = posterior.value if posterior is not None else _ZERO
    rewritten: list[CasillaObservation] = []
    for item in observations:
        if item.casilla_id == _M303_DISPONIBLE_CASILLA:
            rewritten.append(item.model_copy(update={"value": posterior_value}))
        elif item.casilla_id == _M303_GENERADA_CASILLA:
            rewritten.append(item.model_copy(update={"value": _ZERO}))
        else:
            rewritten.append(item)
    return tuple(rewritten)


def _local_iva_history_expediente_id(filing_ref: str) -> str:
    """Derive the non-AEAT expediente marker stored for local IVA history rows."""
    return f"local-{filing_ref[:26]}"


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
            "iva compensation history repository is backed by a different database "
            f"({override_context.engine.url!r}) than the calculation observation repository "
            f"({context.engine.url!r})",
            translated_message="application.modelo.errors.filed_observation_split_storage_context",
            context={
                "history_backend": str(override_context.engine.url),
                "observation_backend": str(context.engine.url),
            },
        )
    return override


def persist_filed_revision_observation(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    repository: CalculationObservationRepository,
    captured_at: datetime,
    refunded: bool = False,
    taxpayer_nif: str | None = None,
    filing_record_id: str | None = None,
    iva_compensation_history_repository: IvaCompensationHistoryRepository | None = None,
) -> str:
    """Persist a filed revision's casilla observations as a cross-period record.

    Projects the filed revision's provenance-bearing
    :class:`~cadrumo.domain.modelos.CalculationRevision` ``observations`` (every
    casilla — inputs, bound, and computed alike, each already carrying
    ``legal_refs`` / ``source_refs`` / formula provenance) into a single
    :class:`~cadrumo.domain.calculations.registry.RegistryModeloObservation` keyed
    by the work unit's ``(modelo, filing_year, period)`` and saves it through the
    bucket-scoped
    :class:`~cadrumo.application.calculations.CalculationObservationRepository` with
    the NON-official ``source_kind = "app_filing"``.

    Args:
        revision: The just-filed
            :class:`~cadrumo.domain.modelos.CalculationRevision` whose typed
            observations are projected.
        work_unit: The revision's parent
            :class:`~cadrumo.domain.modelos.WorkUnit`, supplying the ``(modelo,
            filing_year, period)`` key.
        repository: The bucket-scoped observation repository (the same instance
            the filing transition threads through, so the write lands in the
            active bucket's encrypted store).
        captured_at: The filing timestamp, stamped on the stored record.
        refunded: When ``True`` and the work unit is Modelo 303, the filed period
            was disposed as a refund request (devolución, Tipo de declaración
            ``D``): the generated compensación credit is excluded from carry, so
            the persisted ``iva.compensacion-disponible-fin-periodo`` (and the
            per-period generada casilla) are zeroed for the generated component
            before the carry row is written. The default ``False`` preserves the
            standard compensación carry. Legal basis: RD 1624/1992 art. 30 / Ley
            37/1992 art. 116.
        taxpayer_nif: Taxpayer NIF from the active profile. When supplied for a
            locally filed Modelo 303, the same observation is projected into the
            profile-local IVA compensation history repository.
        filing_record_id: Local filing record id used as non-AEAT provenance for
            the IVA compensation history state.
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
    :func:`~cadrumo.application.calculations.iva_compensation_state_from_registry_observation`
    and saved through
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
    observations = revision.observations
    if refunded and work_unit.modelo == Modelo.M303.value:
        observations = _refunded_303_observations(observations)
    observation = RegistryModeloObservation(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
        observations=observations,
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
    repository.save_observation(
        observation,
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=captured_at,
        stamped_revision_id=work_unit.revision_id,
    )
    if history_repo is not None and taxpayer_nif is not None:
        filing_ref = filing_record_id or key
        history_repo.save_period(
            iva_compensation_state_from_registry_observation(
                observation,
                taxpayer_nif=taxpayer_nif.strip(),
                expediente_id=_local_iva_history_expediente_id(filing_ref),
                status=APP_FILING_SOURCE_KIND,
                presented_at=captured_at,
                source_observation_key=f"{key}:local:{filing_ref[:64]}",
            ),
        )
    return key


__all__ = [
    "APP_FILING_SOURCE_KIND",
    "persist_filed_revision_observation",
]
