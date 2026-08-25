"""Post-bridge decoration for the bridged setup FlowDefinition.

The wizard catalogue predates the paged flow's ``format_hint`` copy slot
and its shape-validated ``DATE`` / ``DECIMAL`` widget kinds, so the
bridge projects every free-text question as a plain ``TEXT`` page with no
hint. This module owns two page-keyed override maps and applies both in a
single post-projection walk — the same post-bridge decoration seam as the
legal-zone projection, so the substrate's bridge stays domain-blind:

* :data:`PAGE_FORMAT_HINTS` attaches the shared ``wizard.setup.format.*``
  hint keys (worked examples for identity documents, ISO dates, euro
  amounts, postcodes, and unit counts).
* :data:`PAGE_WIDGET_KINDS` upgrades the shape-bearing free-text pages to
  the substrate's first-class ``DATE`` (ISO-8601) and ``DECIMAL`` widget
  kinds, so the engine's built-in shape validation refuses a malformed
  date or amount before commit. The format-hint ref stays as authored —
  the widget adds live verification on top of the worked-example copy.

The key constants carry the ``_LOCALE_KEYS`` suffix so the locale
scaffold's AST scanner treats them as live usage (these keys are
referenced only through this mapping, never at a literal ``tr()`` call
site). The widget override adds no copy, so it needs no locale key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.flows import CopyRefKind, FlowWidgetKind
from ..flows.definition import CopyRef, FlowDefinition, FlowPage, FlowSection

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

#: Shape-bearing free-text pages upgraded from the projected ``TEXT``
#: default to a first-class shape-validated widget kind. The DATE pages
#: are ISO-8601 calendar dates; the DECIMAL pages are Decimal quantities
#: (the INCN euro amount and the módulos unit counts, which are
#: fractional). Each carries ``answer_type = str`` after projection and
#: no choices, so the override yields a valid non-choice page.
PAGE_WIDGET_KINDS: Mapping[str, FlowWidgetKind] = {
    "activity-start-date": FlowWidgetKind.DATE,
    "taxpayer-marriage-date": FlowWidgetKind.DATE,
    "taxpayer-birth-date": FlowWidgetKind.DATE,
    "taxpayer-death-date": FlowWidgetKind.DATE,
    "spouse-birth-date": FlowWidgetKind.DATE,
    "ley-49-2002-option-date": FlowWidgetKind.DATE,
    "ley-49-2002-renunciation-date": FlowWidgetKind.DATE,
    "irpf-special-regime-start-date": FlowWidgetKind.DATE,
    "incn-prior-12-months": FlowWidgetKind.DECIMAL,
    "objective-estimation-modulos-module-1-units": FlowWidgetKind.DECIMAL,
    "objective-estimation-modulos-module-2-units": FlowWidgetKind.DECIMAL,
    "objective-estimation-modulos-module-3-units": FlowWidgetKind.DECIMAL,
    "objective-estimation-modulos-module-4-units": FlowWidgetKind.DECIMAL,
    "objective-estimation-modulos-module-5-units": FlowWidgetKind.DECIMAL,
    "objective-estimation-modulos-module-6-units": FlowWidgetKind.DECIMAL,
    "objective-estimation-modulos-module-7-units": FlowWidgetKind.DECIMAL,
}


def attach_format_hints(definition: FlowDefinition) -> FlowDefinition:
    """Return ``definition`` decorated with format hints and widget kinds.

    One walk applies both overrides. A page in :data:`PAGE_FORMAT_HINTS`
    that carries no hint yet (a future catalogue- or bridge-supplied one
    wins) gains its format-hint CopyRef; a page in :data:`PAGE_WIDGET_KINDS`
    is upgraded to its shape-validated widget kind. A page in both maps
    receives both updates in a single ``model_copy``; every other page
    passes through untouched.
    """
    sections: list[FlowSection] = []
    for section in definition.sections:
        updates = [_page_overrides(item) for item in section.items]
        if not any(updates):
            sections.append(section)
            continue
        items = tuple(
            item.model_copy(update=update) if update else item
            for item, update in zip(section.items, updates, strict=True)
        )
        sections.append(section.model_copy(update={"items": items}))
    return definition.model_copy(update={"sections": tuple(sections)})


def _page_overrides(item: object) -> dict[str, object]:
    """Return the field updates one item needs, empty when it passes through.

    A declared hint yields a CopyRef only when the page carries none, so a
    future catalogue- or bridge-supplied hint wins over this fallback; a
    declared widget kind applies only when it actually differs.
    """
    if not isinstance(item, FlowPage):
        return {}
    update: dict[str, object] = {}
    hint_key = PAGE_FORMAT_HINTS.get(item.id)
    if hint_key is not None and item.format_hint is None:
        update["format_hint"] = CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=hint_key)
    widget_kind = PAGE_WIDGET_KINDS.get(item.id)
    if widget_kind is not None and item.widget is not widget_kind:
        update["widget"] = widget_kind
    return update


__all__ = [
    "FORMAT_HINT_LOCALE_KEYS",
    "PAGE_FORMAT_HINTS",
    "PAGE_WIDGET_KINDS",
    "REGISTERED_NON_OFFICIAL_SUFFIX_LOCALE_KEY",
    "attach_format_hints",
]
