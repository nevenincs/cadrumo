"""The words a Modelo 100 projection serves for what it left without a value.

A projection names an unresolved credit and every total computed from it by
closed tokens. These sentences say the same thing in the output language, so a
frontend states it as served and maps no token itself. The same goes for the
name of each figure the projection gives, which :func:`m130_figure_words` and
:func:`m100_figure_words` serve.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from ...core.aggregation import BindingSourceKind
from ...core.i18n.render import tr
from ...domain.calculations.registry.formula_runtime_ops import RegistryUnresolvedOutcomeReason
from .calculation_notes import note_fact_text
from .projection_unresolved import UNRESOLVED_OPERAND_REASON
from .source_policy import source_policy

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ...core.external_constants import OutputLanguage
    from ...domain.modelos.calculation_revision_sources import CalculationNoteFact

_BINDING_WITHOUT_FACT_LOCALE_KEY: Final[str] = "application.modelo.projection_words.binding_unresolved"
_OTHER_CASILLA_REASON_LOCALE_KEY: Final[str] = "application.modelo.projection_words.casilla_reason.other"
_CASILLA_REASON_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        UNRESOLVED_OPERAND_REASON: "application.modelo.projection_words.casilla_reason.unresolved_operand",
        RegistryUnresolvedOutcomeReason.M210_BASELINE_TIPO_DEFERRED.value: (
            "application.modelo.projection_words.casilla_reason.m210_baseline_tipo_deferred"
        ),
        RegistryUnresolvedOutcomeReason.M210_CONVENIO_RATE_MISSING.value: (
            "application.modelo.projection_words.casilla_reason.m210_convenio_rate_missing"
        ),
        RegistryUnresolvedOutcomeReason.WAIVED_REFUND_RESULT_UNSUPPORTED.value: (
            "application.modelo.projection_words.casilla_reason.waived_refund_result_unsupported"
        ),
        RegistryUnresolvedOutcomeReason.INCOME_FAMILY_CONTRADICTS_PROFILE.value: (
            "application.modelo.projection_words.casilla_reason.income_family_contradicts_profile"
        ),
        RegistryUnresolvedOutcomeReason.AUTONOMIC_DEDUCTION_OTHER_COMUNIDAD.value: (
            "application.modelo.projection_words.casilla_reason.autonomic_deduction_other_comunidad"
        ),
        RegistryUnresolvedOutcomeReason.AUTONOMIC_DEDUCTION_UNSUMMED_BOX.value: (
            "application.modelo.projection_words.casilla_reason.autonomic_deduction_unsummed_box"
        ),
        RegistryUnresolvedOutcomeReason.JOINT_RETURN_MEMBER_INCOME_UNAVAILABLE.value: (
            "application.modelo.projection_words.casilla_reason.joint_return_member_income_unavailable"
        ),
        RegistryUnresolvedOutcomeReason.M200_TAX_REGIME_UNSUPPORTED.value: (
            "application.modelo.projection_words.casilla_reason.m200_tax_regime_unsupported"
        ),
    }
)
"""The sentence of each reason a computed box can be left without a value."""
_M130_FIGURE_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "ingresos": "application.modelo.projection_words.figure.m130.ingresos",
        "gastos": "application.modelo.projection_words.figure.m130.gastos",
        "rendimiento_neto": "application.modelo.projection_words.figure.m130.rendimiento_neto",
        "pagos_fraccionados": "application.modelo.projection_words.figure.m130.pagos_fraccionados",
    }
)
"""The name of each cumulative quarterly-declaration figure a projection gives."""
_M100_FIGURE_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "base_liquidable_general": "application.modelo.projection_words.figure.m100.base_liquidable_general",
        "pagos_fraccionados": "application.modelo.projection_words.figure.m100.pagos_fraccionados",
        "cuota_integra_estatal": "application.modelo.projection_words.figure.m100.cuota_integra_estatal",
        "cuota_integra_autonomica": "application.modelo.projection_words.figure.m100.cuota_integra_autonomica",
        "cuota_liquida_estatal": "application.modelo.projection_words.figure.m100.cuota_liquida_estatal",
        "cuota_liquida_autonomica": "application.modelo.projection_words.figure.m100.cuota_liquida_autonomica",
        "cuota_resultante": "application.modelo.projection_words.figure.m100.cuota_resultante",
    }
)
"""The name of each projected annual-return figure."""


def _require_every_outcome_reason_worded() -> None:
    """Refuse an engine outcome reason the catalogue has no sentence for."""
    unworded = {reason.value for reason in RegistryUnresolvedOutcomeReason} - set(_CASILLA_REASON_LOCALE_KEYS)
    if unworded:
        raise ValueError(f"projection words must cover every engine outcome reason; missing={sorted(unworded)}")


_require_every_outcome_reason_worded()


def unresolved_binding_words(fact: CalculationNoteFact | None, *, language: OutputLanguage) -> str:
    """State why a source-owned binding has no value, and what puts it right, in ``language``.

    The resolver's own note says it when the resolver named one; otherwise the
    binding is only known to be unresolved, and the sentence says no more.
    """
    if fact is None:
        return tr(_BINDING_WITHOUT_FACT_LOCALE_KEY, locale=language.value)
    return note_fact_text(fact, locale=language.value)


def binding_source_words(source_kind: str, *, language: OutputLanguage) -> str | None:
    """Name the source of a binding in a few words, or ``None`` for a source kind the product does not know."""
    try:
        kind = BindingSourceKind(source_kind)
    except ValueError:
        return None
    return tr(source_policy(kind).label_key, locale=language.value)


def unresolved_casilla_reason_words(reason: str, *, language: OutputLanguage) -> str:
    """State why a computed box has no value, in ``language``."""
    return tr(_CASILLA_REASON_LOCALE_KEYS.get(reason, _OTHER_CASILLA_REASON_LOCALE_KEY), locale=language.value)


def m130_figure_words(figure: str, *, language: OutputLanguage) -> str:
    """Name one cumulative quarterly-declaration figure of a projection in ``language``."""
    return tr(_M130_FIGURE_LOCALE_KEYS[figure], locale=language.value)


def m100_figure_words(figure: str, *, language: OutputLanguage) -> str:
    """Name one projected annual-return figure in ``language``."""
    return tr(_M100_FIGURE_LOCALE_KEYS[figure], locale=language.value)


__all__ = [
    "binding_source_words",
    "m100_figure_words",
    "m130_figure_words",
    "unresolved_binding_words",
    "unresolved_casilla_reason_words",
]
