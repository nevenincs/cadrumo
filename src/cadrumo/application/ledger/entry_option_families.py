"""The closed vocabularies a ledger entry form offers, and the link fields that name three of them.

A ledger row states its rental links in three fields, each choosing among the
values of one served family. This module owns that field-to-family list, in form
order, so the entry options and every transaction projection serve the same one
and no frontend holds a table of its own. Each field's name is a locale word
served in the operator's output language.
"""

from __future__ import annotations

from typing import Final, Literal, NamedTuple

from pydantic import BaseModel

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

type EntryOptionFamily = Literal[
    "country",
    "currency",
    "deduction_fact_kind",
    "m210_payer_mode",
    "m210_tipo_renta",
    "iva_category",
    "irpf_category",
    "spending_category",
    "usage_ratio_category",
    "invoice_class",
    "premises_situation",
    "prorrata_provenance",
    "prorrata_sector_letter",
    "capital_good_kind",
    "capital_good_disposal",
    "import_format",
    "export_format",
    "gasto_capital_inmobiliario",
    "rental_lease",
    "rental_property",
    "withholding_certificate_figure",
]


class LedgerLinkFieldSpec(NamedTuple):
    """One field a ledger row states a link in, the served family its choices come from, and where its name lives."""

    field: str
    family: EntryOptionFamily
    words_locale_key: str


_LEASE_WORDS_LOCALE_KEY: Final = "ledger.link_field.arrendamiento_ref"
_PROPERTY_WORDS_LOCALE_KEY: Final = "ledger.link_field.inmueble_ref"
_EXPENSE_CONCEPT_WORDS_LOCALE_KEY: Final = "ledger.link_field.gasto_capital_inmobiliario"

LEDGER_LINK_FIELDS: Final[tuple[LedgerLinkFieldSpec, ...]] = (
    LedgerLinkFieldSpec("arrendamiento_ref", "rental_lease", _LEASE_WORDS_LOCALE_KEY),
    LedgerLinkFieldSpec("inmueble_ref", "rental_property", _PROPERTY_WORDS_LOCALE_KEY),
    LedgerLinkFieldSpec("gasto_capital_inmobiliario", "gasto_capital_inmobiliario", _EXPENSE_CONCEPT_WORDS_LOCALE_KEY),
)
"""The link fields of a ledger row in form order; the one owner of which served family each takes its choices from."""


class LedgerLinkFieldProjection(BaseModel):
    """A link field of a ledger row, the served family its choices come from, and its name in a language."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    field: str
    family: EntryOptionFamily
    field_words: str
    field_words_language: OutputLanguage


def served_link_fields(language: OutputLanguage) -> tuple[LedgerLinkFieldProjection, ...]:
    """Every link field in form order, each named in ``language``."""
    return tuple(
        LedgerLinkFieldProjection(
            field=spec.field,
            family=spec.family,
            field_words=tr(spec.words_locale_key, locale=language.value),
            field_words_language=language,
        )
        for spec in LEDGER_LINK_FIELDS
    )


__all__ = [
    "LEDGER_LINK_FIELDS",
    "EntryOptionFamily",
    "LedgerLinkFieldProjection",
    "LedgerLinkFieldSpec",
    "served_link_fields",
]
