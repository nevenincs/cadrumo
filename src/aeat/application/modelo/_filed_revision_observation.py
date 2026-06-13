"""Persist a locally-filed calculation revision as a cross-period observation.

This is the local-filing sibling of the live-AEAT-capture persistence path
(:func:`aeat.application.live.persist_filed_calculation_observation`). It does
NOT introduce a parallel write path: it is an additional projection of the
single-writer filing transition (:func:`persist_filed_revision`), co-emitted
with ``MODELO_FILED``, that records the filed
:class:`~aeat.domain.calculations.registry.CalculationRevision` outputs into the
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

Uses :class:`CalculationRevision` for the source revision and
:class:`RegistryModeloObservation` as the persisted record.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from ...domain.calculations.registry import RegistryModeloObservation
from ...domain.modelos._calculation_revision import CalculationRevision
from ...domain.modelos._work_unit import WorkUnit
from ..calculations import CalculationObservationRepository, observation_key

APP_FILING_SOURCE_KIND: Final = "app_filing"
"""Non-official ``source_kind`` stamped on locally-filed observations.

Deliberately NOT a member of
``aeat.application.calculations._cross_period_clean_state._OFFICIAL_SOURCE_KINDS``:
a locally-filed value is not external AEAT evidence and must never satisfy the
cross-period clean-state filing gate. See ADR
``2026-06-09-modelo-iva-routing-carry`` ruling D1.
"""


def persist_filed_revision_observation(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    repository: CalculationObservationRepository,
    captured_at: datetime,
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

    Returns:
        The ``(modelo, filing_year, period)`` observation key string the record
        was stored under.
    """
    observation = RegistryModeloObservation(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
        observations=revision.observations,
    )
    repository.save_observation(
        observation,
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=captured_at,
        stamped_revision_id=work_unit.revision_id,
    )
    return observation_key(work_unit.modelo, work_unit.period)


__all__ = [
    "APP_FILING_SOURCE_KIND",
    "persist_filed_revision_observation",
]
