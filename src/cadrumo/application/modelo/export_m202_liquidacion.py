"""Resolve the Modelo 202 page 01 modality and foral-normativa slots, or name the profile facts they need.

Both slots are derived, never asked for as such:

- "Liquidación de modalidad A ó B" (2025 design position 148, Nota 11; 2019 and
  2023 designs position 513, Nota 4 of 2023): "A" is the LIS art. 40.2 modality,
  the base being the cuota of the last declared período, and "B" the art. 40.3
  one, the base being the período's own result. Above the art. 40.3 turnover
  threshold "B" is mandatory; below it the declaración censal election decides.
  The modality has one definition, ``modelo_202_modality_from_path_values``, and
  the election one reader, so neither is derived again here. An unknown modality
  is refused naming the facts that decide it, never written blank: the 2023 and
  2025 designs admit only "A ó B".
- "Contribuyente sometido a normativa de Territorio Foral" (2025 design
  position 103, Nota 9; 2019 and 2023 designs position 514, Nota 2): blank
  "Sin contenido" for the common normativa, "1" Navarra, "2" Guipúzcoa,
  "3" Vizcaya, "4" Álava. The profile's ``tax_residence.jurisdiction_scope``
  decides it through the registry's foral classification of that token: the
  common régimen writes the blank. A foral token names no territory, so it
  refuses rather than write a blank that would declare the common normativa.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Final

from ...core.filing_producer_key import FilingProducerKey
from ...domain.calculations.registry.applicability_modelo202 import (
    Modelo202Modality,
    art_40_3_method_applies,
    modelo_202_modality_from_path_values,
)
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.m303_schema_vocabulary import m303_tax_territory_is_foral
from ..filing.producer_snapshot import FilingProducerSnapshotError
from .profile_binding_refusal_doors import profile_fact_value_refused_verdict

_K = FilingProducerKey

ENTITY_TYPE_PATH: Final = "taxpayer_type.entity_type"
INCN_PRIOR_12_MONTHS_PATH: Final = "taxpayer_type.incn_prior_12_months"
ART_40_3_ELECTION_PATH: Final = "taxpayer_type.pago_fraccionado_art_40_3_elected"
JURISDICTION_SCOPE_PATH: Final = "tax_residence.jurisdiction_scope"

#: Nota 11 of the 2025 design: "A" art. 40.2 LIS, "B" art. 40.3 LIS.
_MODALIDAD_ART_40_2: Final = "A"
_MODALIDAD_ART_40_3: Final = "B"

_FORAL_REASON: Final = "m202_foral_territory_unstated"
_FORAL_MESSAGE: Final = "application.filing.export.errors.m202_foral_territory_unstated"


@dataclass(frozen=True, slots=True)
class LiquidacionSlots:
    """The derived slot values keyed by producer-view field, and the facts still unstated, in page order."""

    fields: Mapping[str, object] = field(default_factory=dict[str, object])
    missing: tuple[str, ...] = ()


def liquidacion_slots(
    *,
    profile_values: Mapping[str, str],
    cited: frozenset[FilingProducerKey],
    filing_year: int,
    art_40_3_elected: bool | None,
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> LiquidacionSlots:
    """Derive the cited modality and foral slots, naming every profile fact one of them lacks.

    Raises:
        FilingProducerSnapshotError: The profile states a foral territory, which
            names no territory the design's Nota 9 can consign.
    """
    fields: dict[str, object] = {}
    missing: list[str] = []
    if _K.M202_NORMATIVA_TERRITORIO_FORAL in cited:
        scope = (profile_values.get(JURISDICTION_SCOPE_PATH) or "").strip()
        # The common normativa is the design's blank, so the field keeps its no-value.
        if not _common_normativa_stated(scope, effective_date=effective_date, operation=operation):
            missing.append(JURISDICTION_SCOPE_PATH)
    if _K.M202_MODALIDAD_LIQUIDACION in cited:
        modality = modelo_202_modality_from_path_values(profile_values, filing_year=filing_year, authority=operation)
        art_40_3 = art_40_3_method_applies(modality, elected=art_40_3_elected)
        if art_40_3 is None:
            missing.extend(_modality_facts_unstated(profile_values, modality))
        else:
            fields["modalidad_liquidacion"] = _MODALIDAD_ART_40_3 if art_40_3 else _MODALIDAD_ART_40_2
    return LiquidacionSlots(fields=fields, missing=tuple(missing))


def _common_normativa_stated(scope: str, *, effective_date: date, operation: PinnedAuthorityOperation) -> bool:
    """Whether the stated territory is the common one; unstated or unknown is not, and a foral one refuses."""
    if not scope:
        return False
    try:
        foral = m303_tax_territory_is_foral(scope, effective_date=effective_date, authority=operation)
    except RegistryValidationError:
        return False
    if foral:
        raise FilingProducerSnapshotError(
            f"Modelo 202 export cannot name the foral territory of {JURISDICTION_SCOPE_PATH}={scope!r}",
            translated_message=_FORAL_MESSAGE,
            context={"reason": _FORAL_REASON, "profile_path": JURISDICTION_SCOPE_PATH, "scope": scope},
            precondition_verdict=profile_fact_value_refused_verdict(_FORAL_REASON, {"field": JURISDICTION_SCOPE_PATH}),
        )
    return True


def _modality_facts_unstated(profile_values: Mapping[str, str], modality: Modelo202Modality) -> tuple[str, ...]:
    """The facts that leave the modality unknown: the election below the threshold, else what decides the threshold."""
    if modality is Modelo202Modality.ART_40_2_OPTIONAL:
        return (ART_40_3_ELECTION_PATH,)
    unstated = tuple(
        path for path in (ENTITY_TYPE_PATH, INCN_PRIOR_12_MONTHS_PATH) if not (profile_values.get(path) or "").strip()
    )
    # Both stated and still incomplete means one is unreadable or not a sociedad's, so both are named.
    return unstated or (ENTITY_TYPE_PATH, INCN_PRIOR_12_MONTHS_PATH)


__all__ = [
    "ART_40_3_ELECTION_PATH",
    "ENTITY_TYPE_PATH",
    "JURISDICTION_SCOPE_PATH",
    "LiquidacionSlots",
    "liquidacion_slots",
]
