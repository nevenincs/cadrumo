"""The registry values the Modelo 232 related-party grounds are applied with.

The thresholds and the turnover share are dated parameters of the Modelo 232
revision that governs the ejercicio, and the operation types that are always
specific are a dated mapping fact. Both are read through the generation-pinned
authority at the end of the ejercicio, so one operation never mixes generations
and nothing in code restates an amount.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Final

from ...core.modelo import Modelo
from ...domain.calculations.registry.form_codes import resolve_form_codes
from ...domain.calculations.registry.formula_runtime_ops import read_parameter
from ...domain.modelos.m232_obligation import Modelo232Thresholds

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

__all__ = [
    "ALWAYS_SPECIFIC_FACT_ID",
    "always_specific_operation_types",
    "modelo_232_thresholds",
]

ALWAYS_SPECIFIC_FACT_ID: Final = "modelo-232-always-specific-operation-types"
_ALWAYS_SPECIFIC_KEY: Final = "m232.tipo_operacion.always_specific"
_SAME_PARTY_PARAMETER: Final = "modelo-232-same-related-party-threshold-eur"
_SPECIFIC_PARAMETER: Final = "modelo-232-specific-operations-threshold-eur"
_TURNOVER_SHARE_PARAMETER: Final = "modelo-232-same-type-turnover-share"


def always_specific_operation_types(ejercicio: int, *, operation: PinnedAuthorityOperation) -> frozenset[str]:
    """Return the Tabla C types the registry lists as specific whatever the filer states, for ``ejercicio``."""
    return resolve_form_codes(
        ALWAYS_SPECIFIC_FACT_ID, effective_date=date(ejercicio, 12, 31), authority=operation
    ).codes(_ALWAYS_SPECIFIC_KEY)


def modelo_232_thresholds(
    ejercicio: int,
    *,
    operation: PinnedAuthorityOperation,
    modelo: Modelo,
    period: str,
) -> Modelo232Thresholds:
    """Read the art. 2 thresholds from the revision of ``modelo`` that governs ``ejercicio`` and ``period``."""
    revision = operation.revision_for_context(modelo, filing_year=ejercicio, period=period)
    context = {"filing_period": date(ejercicio, 12, 31)}

    return Modelo232Thresholds(
        same_related_party_eur=read_parameter(
            modelo.value, revision.id, _SAME_PARTY_PARAMETER, date_context=context, operation=operation
        ),
        specific_operations_eur=read_parameter(
            modelo.value, revision.id, _SPECIFIC_PARAMETER, date_context=context, operation=operation
        ),
        turnover_share=read_parameter(
            modelo.value, revision.id, _TURNOVER_SHARE_PARAMETER, date_context=context, operation=operation
        ),
        always_specific_types=always_specific_operation_types(ejercicio, operation=operation),
    )
