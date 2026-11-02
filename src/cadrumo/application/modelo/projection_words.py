"""The words a Modelo 100 projection serves for what it left without a value.

A projection names an unresolved credit and every total computed from it by
closed tokens. These sentences say the same thing in the output language, so a
frontend states it as served and maps no token itself.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from ...core.aggregation import BindingSourceKind
from ...core.i18n.render import tr
from ...domain.calculations.registry.formula_runtime_ops import RegistryUnresolvedOutcomeReason
from .calculation_notes import note_fact_text
from .projection import UNRESOLVED_OPERAND_REASON
from .source_policy import source_policy

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ...core.external_constants import OutputLanguage
    from ...domain.modelos.calculation_revision_sources import CalculationNoteFact

_BINDING_WITHOUT_FACT_LOCALE_KEY: Final[str] = "application.modelo.projection_words.binding_unresolved"
_CASILLA_REASON_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        UNRESOLVED_OPERAND_REASON: "application.modelo.projection_words.casilla_reason.unresolved_operand",
        RegistryUnresolvedOutcomeReason.M210_BASELINE_TIPO_DEFERRED.value: (
            "application.modelo.projection_words.casilla_reason.m210_baseline_tipo_deferred"
        ),
        RegistryUnresolvedOutcomeReason.M210_CONVENIO_RATE_MISSING.value: (
            "application.modelo.projection_words.casilla_reason.m210_convenio_rate_missing"
        ),
    }
)
"""The sentence of each reason a computed box can be left without a value."""
_OTHER_CASILLA_REASON_LOCALE_KEY: Final[str] = "application.modelo.projection_words.casilla_reason.other"


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


__all__ = ["binding_source_words", "unresolved_binding_words", "unresolved_casilla_reason_words"]
