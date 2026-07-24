"""Format-hint decoration for the bridged setup FlowDefinition.

The wizard catalogue predates the paged flow's ``format_hint`` copy slot,
so the bridge projects pages without one. This module owns the mapping
from page id to the shared ``wizard.setup.format.*`` hint keys (worked
examples for identity documents, ISO dates, euro amounts, postcodes, and
unit counts) and decorates the bridged definition after projection —
the same post-bridge decoration seam as the legal-zone projection, so
the substrate's bridge stays domain-blind.

The key constants carry the ``_LOCALE_KEYS`` suffix so the locale
scaffold's AST scanner treats them as live usage (these keys are
referenced only through this mapping, never at a literal ``tr()`` call
site).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.flows import CopyRefKind
from ..flows import CopyRef, FlowDefinition, FlowPage, FlowSection

if TYPE_CHECKING:
    from collections.abc import Mapping

_FORMAT_TAX_ID_LOCALE_KEY = "wizard.setup.format.tax-id"
_FORMAT_DATE_LOCALE_KEY = "wizard.setup.format.date-iso"
_FORMAT_AMOUNT_LOCALE_KEY = "wizard.setup.format.amount-eur"
_FORMAT_POSTCODE_LOCALE_KEY = "wizard.setup.format.postcode"
_FORMAT_UNITS_LOCALE_KEY = "wizard.setup.format.units-count"

FORMAT_HINT_LOCALE_KEYS: tuple[str, ...] = (
    _FORMAT_TAX_ID_LOCALE_KEY,
    _FORMAT_DATE_LOCALE_KEY,
    _FORMAT_AMOUNT_LOCALE_KEY,
    _FORMAT_POSTCODE_LOCALE_KEY,
    _FORMAT_UNITS_LOCALE_KEY,
)

#: Registered-value provenance suffix (consumed by the registered-values
#: projection when a fact carries the censo-artefact provenance token).
REGISTERED_NON_OFFICIAL_SUFFIX_LOCALE_KEY = "wizard.setup.review.registered-non-official-suffix"

PAGE_FORMAT_HINTS: Mapping[str, str] = {
    "tax-id": _FORMAT_TAX_ID_LOCALE_KEY,
    "spouse-tax-id": _FORMAT_TAX_ID_LOCALE_KEY,
    "representante-fiscal-nif": _FORMAT_TAX_ID_LOCALE_KEY,
    "activity-start-date": _FORMAT_DATE_LOCALE_KEY,
    "taxpayer-marriage-date": _FORMAT_DATE_LOCALE_KEY,
    "taxpayer-birth-date": _FORMAT_DATE_LOCALE_KEY,
    "taxpayer-death-date": _FORMAT_DATE_LOCALE_KEY,
    "spouse-birth-date": _FORMAT_DATE_LOCALE_KEY,
    "ley-49-2002-option-date": _FORMAT_DATE_LOCALE_KEY,
    "ley-49-2002-renunciation-date": _FORMAT_DATE_LOCALE_KEY,
    "irpf-special-regime-start-date": _FORMAT_DATE_LOCALE_KEY,
    "incn-prior-12-months": _FORMAT_AMOUNT_LOCALE_KEY,
    "address-postcode": _FORMAT_POSTCODE_LOCALE_KEY,
    "modelo-111-no-retenciones-periods": _FORMAT_UNITS_LOCALE_KEY,
    "objective-estimation-modulos-module-1-units": _FORMAT_UNITS_LOCALE_KEY,
    "objective-estimation-modulos-module-2-units": _FORMAT_UNITS_LOCALE_KEY,
    "objective-estimation-modulos-module-3-units": _FORMAT_UNITS_LOCALE_KEY,
    "objective-estimation-modulos-module-4-units": _FORMAT_UNITS_LOCALE_KEY,
    "objective-estimation-modulos-module-5-units": _FORMAT_UNITS_LOCALE_KEY,
    "objective-estimation-modulos-module-6-units": _FORMAT_UNITS_LOCALE_KEY,
    "objective-estimation-modulos-module-7-units": _FORMAT_UNITS_LOCALE_KEY,
}


def attach_format_hints(definition: FlowDefinition) -> FlowDefinition:
    """Return ``definition`` with format-hint CopyRefs on the mapped pages.

    Pages outside :data:`PAGE_FORMAT_HINTS` — and pages that already carry
    a hint (a future catalogue- or bridge-supplied one wins) — pass through
    untouched.
    """
    sections: list[FlowSection] = []
    for section in definition.sections:
        items: list[object] = []
        changed = False
        for item in section.items:
            hint_key = PAGE_FORMAT_HINTS.get(getattr(item, "id", ""))
            if hint_key is not None and isinstance(item, FlowPage) and item.format_hint is None:
                items.append(
                    item.model_copy(update={"format_hint": CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=hint_key)}),
                )
                changed = True
            else:
                items.append(item)
        sections.append(section.model_copy(update={"items": tuple(items)}) if changed else section)
    return definition.model_copy(update={"sections": tuple(sections)})


__all__ = [
    "FORMAT_HINT_LOCALE_KEYS",
    "PAGE_FORMAT_HINTS",
    "REGISTERED_NON_OFFICIAL_SUFFIX_LOCALE_KEY",
    "attach_format_hints",
]
