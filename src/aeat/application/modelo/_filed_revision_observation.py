"""Persist a locally-filed calculation revision as a cross-period observation.

This is the local-filing sibling of the live-AEAT-capture persistence path
(:func:`aeat.application.live.persist_filed_calculation_observation`). It does
NOT introduce a parallel write path: it is an additional projection of the
single-writer filing transition (:func:`persist_filed_revision`), co-emitted
with ``MODELO_FILED``, that records the filed
:class:`CalculationRevision` outputs into the
cross-period observation store so a later period's ``calculate`` can carry them
forward automatically via the ``previous_filing`` resolver.

The persisted observation is stamped with a NON-official ``source_kind``
(``app_filing``): a value an operator filed through the app is not external AEAT
evidence. The cross-period clean-state guard
(:mod:`aeat.application.calculations._cross_period_clean_state`) treats any
``source_kind`` outside its official set as the
``LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`` blocker, so this carry feeds
calculate/draft but never satisfies the filing gate for a dependent period —
filing still requires real external evidence. ``app_filing`` MUST NOT be added
to ``_OFFICIAL_SOURCE_KINDS``.

Non-goal (grupo ``per_grupo_member`` fan-in): this helper persists the
single-filer ``(modelo, filing_year, period)`` row only. It does not stamp a
``member_nif`` and therefore does not feed the cross-member fan-in the 353<-322
aggregation enumerates; member-row persistence for the local filing flow is out
of scope (ADR ``2026-06-09-modelo-iva-routing-carry`` ruling D4) and remains a
live-capture concern.

The projection reads :class:`CalculationRevision` observations, rewrites the
affected :class:`CasillaObservation` rows for refunded Modelo 303 filings, and
persists a :class:`RegistryModeloObservation` record.
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
from ...domain.modelos._calculation_revision import CalculationRevision
from ...domain.modelos._work_unit import WorkUnit
from ..calculations import (
    CalculationObservationRepository,
    IvaCompensationHistoryRepository,
    iva_compensation_state_from_registry_observation,
    observation_key,
)

APP_FILING_SOURCE_KIND: Final = "app_filing"


def _casilla_id(value: object) -> CasillaId:
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
"""Non-official ``source_kind`` stamped on locally-filed observations.

Deliberately NOT a member of
``aeat.application.calculations._cross_period_clean_state._OFFICIAL_SOURCE_KINDS``:
a locally-filed value is not external AEAT evidence and must never satisfy the
cross-period clean-state filing gate. See ADR
``2026-06-09-modelo-iva-routing-carry`` ruling D1.
"""


def _refunded_303_observations(
    observations: tuple[CasillaObservation, ...],
) -> tuple[CasillaObservation, ...]:
    """Zero the generated-credit components of a refunded Modelo 303 observation.

    A refunded (devolución) period returns its credit rather than carrying it
    forward, so the persisted cross-period carry must drop the generated credit:
    ``iva.compensacion-disponible-fin-periodo`` is re-stamped to its
    posterior-only value from ``iva.compensacion-pendiente-periodos-posteriores``
    (AEAT box 87) and ``iva.compensacion-generada-periodo`` to zero. Every other
    casilla is preserved verbatim — including its provenance — so the carried
    observation stays a faithful projection of the filed revision except for the
    one disposition-determined correction.
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
    return f"local-{filing_ref[:26]}"


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
    :attr:`CalculationRevision.observations` (every casilla — inputs, bound, and
    computed alike, each already carrying ``legal_refs`` / ``source_refs`` /
    formula provenance) into a single
    :class:`~aeat.domain.calculations.registry.RegistryModeloObservation` keyed
    by the work unit's ``(modelo, filing_year, period)`` and saves it through the
    bucket-scoped :class:`CalculationObservationRepository` with the NON-official
    ``source_kind = "app_filing"``.

    Args:
        revision: The just-filed :class:`CalculationRevision` whose typed
            observations are projected.
        work_unit: The revision's parent :class:`WorkUnit`, supplying the
            ``(modelo, filing_year, period)`` key.
        repository: The bucket-scoped observation repository (the same instance
            the filing transition threads through, so the write lands in the
            active bucket's encrypted store).
        captured_at: The filing timestamp, stamped on the stored record.
        refunded: When ``True`` and the work unit is Modelo 303, the filed period
            was disposed as a refund (devolución, Tipo de declaración ``D``): the
            generated compensación credit is returned by AEAT, not carried, so the
            persisted ``iva.compensacion-disponible-fin-periodo`` (and the
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
    repository.save_observation(
        observation,
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=captured_at,
        stamped_revision_id=work_unit.revision_id,
    )
    if work_unit.modelo == Modelo.M303.value and taxpayer_nif is not None and taxpayer_nif.strip():
        filing_ref = filing_record_id or key
        history_repo = (
            iva_compensation_history_repository
            if iva_compensation_history_repository is not None
            else IvaCompensationHistoryRepository()
        )
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
