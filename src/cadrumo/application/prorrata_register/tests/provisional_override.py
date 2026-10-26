"""Finite fixture authoring over real typed and atomic storage kernels."""

from __future__ import annotations

from decimal import Decimal

from ....core.prorrata_register import ProrrataRegisterRegime as _ProrrataRegisterRegime
from ....domain.calculations.registry.prorrata_register_catalogue import (
    general_prorrata_register_regime as _general_regime,
)
from ....domain.calculations.registry.tests.provisional_catalogue import (
    aeat_autorizada_prorrata_provenance as _aeat_autorizada_provenance,
)
from ....domain.calculations.registry.tests.provisional_catalogue import (
    inicio_actividad_prorrata_provenance as _inicio_actividad_provenance,
)
from ....domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry
from ..service import ProrrataRegisterService


def record_aeat_autorizada(
    self: ProrrataRegisterService,
    *,
    ejercicio: int,
    provisional_percentage: Decimal,
    authorisation_reference: str,
    sector_id: str | None = None,
    regime: _ProrrataRegisterRegime | None = None,
) -> ProrrataRegister:
    """Record an art. 105.Dos AEAT-authorised provisional prorrata override.

    Args:
        ejercicio: Filing year whose provisional prorrata is authorised.
        provisional_percentage: AEAT-authorised provisional deduction percentage.
        authorisation_reference: Operator-held reference for the AEAT authorisation.
        sector_id: Optional sector identifier for sectores diferenciados.
        regime: Prorrata regime in force for the entry. Defaults to general.

    Returns:
        The updated :class:`ProrrataRegister`.
    """
    if regime is None:
        regime = _general_regime()
    entry = ProrrataRegisterEntry(
        ejercicio=ejercicio,
        regime=regime,
        especial_transition=None,
        sector_id=sector_id,
        provisional_percentage=provisional_percentage,
        provisional_provenance=_aeat_autorizada_provenance(),
        authorisation_reference=authorisation_reference,
        source_registry_snapshot_refs=(),
    )
    return self.declare(entry)


def record_inicio_actividad(
    self: ProrrataRegisterService,
    *,
    ejercicio: int,
    provisional_percentage: Decimal,
    proposal_reference: str,
    sector_id: str | None = None,
    regime: _ProrrataRegisterRegime | None = None,
) -> ProrrataRegister:
    """Record an art. 105.Tres start-of-activity provisional override.

    ``proposal_reference`` identifies the operator-held proposal or filing
    evidence supporting the declared percentage.  The registry supplies
    the typed provenance token so callers cannot manufacture a vocabulary
    value outside the pinned authority.
    """
    if regime is None:
        regime = _general_regime()
    entry = ProrrataRegisterEntry(
        ejercicio=ejercicio,
        regime=regime,
        especial_transition=None,
        sector_id=sector_id,
        provisional_percentage=provisional_percentage,
        provisional_provenance=_inicio_actividad_provenance(),
        authorisation_reference=proposal_reference,
        source_registry_snapshot_refs=(),
    )
    return self.declare(entry)
