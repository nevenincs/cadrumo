"""Ordered structural removals and resolution-preserving lineage lifts."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .modelo_casilla_catalogue import ModeloCasillaCatalogue
from collections.abc import Mapping

from .casilla_catalogue_models import (
    CollapsePlan,
    Coordinate,
    Values,
)
from .casilla_text_comparison import (
    _is_derived_help,
)


def _remove_casilla_structural_leaf(
    self: ModeloCasillaCatalogue, locale: str, key: str, value: str | None, working: Values, plan: CollapsePlan
) -> None:
    """Remove casilla structural leaf."""
    if self._undeclared_revision(key) or key in self.binding_presentation_keys:
        return
    if key not in self.dependents:
        plan.remove(locale, key, "orphan")
    elif value is None:
        plan.remove(locale, key, "null")
    elif _is_derived_help(key, value):
        plan.remove(locale, key, "derived-help")
    else:
        return
    del working[locale][key]


def _lift_casilla_lineage_key(
    self: ModeloCasillaCatalogue,
    working: Values,
    baseline: Mapping[Coordinate, str | None],
    plan: CollapsePlan,
    lifted_keys: dict[str, set[str]],
    locale: str,
    key: str,
) -> int:
    """Lift one agreed lineage value and return the exact count increment."""
    lifted = 0
    if working[locale].get(key) is not None or key in lifted_keys[locale]:
        return 0
    texts = {baseline[(index, field_name, locale)] for index, field_name in self.dependents[key]}
    if len(texts) != 1:
        return 0
    (text,) = texts
    if text is None:
        return 0
    working[locale][key] = text
    if self._unchanged(key, locale, working, baseline):
        plan.assign(locale, key, text, "lineage-lift")
        lifted_keys[locale].add(key)
        lifted += 1
    else:
        del working[locale][key]
    return lifted
