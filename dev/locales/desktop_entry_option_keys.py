"""The words the desktop shows for the ledger entry vocabularies the backend serves.

The operation serves registry tokens with the key of each word. The members are
read from the governed facts that declare them, so a token the registry adds is
declared here with it and generation refuses until its word is authored.

Some served tokens are worded by the window's own chrome keys instead, one family
per kind of token, because the window already speaks them in places the
operation does not reach. Their members are read from the same facts, so the
chrome cannot word a list of its own that drifts from what is served.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from cadrumo.application.ledger.actions_import import LedgerProviderID
from cadrumo.application.ledger.entry_options_operation import ENTRY_OPTION_LABEL_PREFIX
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.retencion_soportada import RetencionSoportadaClase
from cadrumo.domain.renta.retencion_soportada import certificate_figures

_DEDUCTION_FACT: Final[str] = "0085-iva-deduction-applicability-catalogue.toml"
_M210_FACT: Final[str] = "0080-detail-m349-m210-catalogues.toml"
_IVA_CATEGORY_FACT: Final[str] = "0084-iva-category-component-catalogue.toml"
_IRPF_TAXONOMY_FACT: Final[str] = "0081-irpf-ledger-category-taxonomy.toml"
_CATEGORIES_FACT: Final[str] = "0064-categories-profile.toml"
_PRORRATA_FACT: Final[str] = "0116-renta-iva-deduction-ratio-policy.toml"
_CAPITAL_FACT: Final[str] = "0130-liva-bienes-inversion-vocabulary.toml"
_INVOICE_CLASS_FACT: Final[str] = "0141-invoice-legal-classification-catalogue.toml"
_PREMISES_FACT: Final[str] = "0155-modelo-347-premises-form-codes.toml"
_GASTO_INMOBILIARIO_FACT: Final[str] = "0185-renta-capital-inmobiliario-gasto-concept-vocabulary.toml"


def _entries(fact_file: str) -> list[dict[str, str]]:
    """Return each variant's entries of one mapping fact, as plain key to value maps."""
    with bundled_path("registry", "aeat", "facts", fact_file).open("rb") as handle:
        fact = tomllib.load(handle)["fact"]
    return [{entry["key"]: entry["value"] for entry in variant["payload"]["entries"]} for variant in fact["variants"]]


def _under(fact_file: str, key_prefix: str, *, values: bool = False) -> tuple[str, ...]:
    """Return the key remainders, or the values, below a prefix across the fact's variants, first seen first."""
    members: dict[str, None] = {}
    for entries in _entries(fact_file):
        for key, value in entries.items():
            if key.startswith(key_prefix):
                members[value if values else key.removeprefix(key_prefix)] = None
    return tuple(members)


def _ordered(fact_file: str, order_key: str, excluded_key: str | None = None) -> tuple[str, ...]:
    """Return one declared order across the fact's variants, first seen first."""
    with bundled_path("registry", "aeat", "facts", fact_file).open("rb") as handle:
        fact = tomllib.load(handle)["fact"]
    members: dict[str, None] = {}
    for variant in fact["variants"]:
        entries = {entry["key"]: entry["value"] for entry in variant["payload"]["entries"]}
        excluded = (
            {token.strip() for token in entries.get(excluded_key, "").split(",")}
            if excluded_key is not None and excluded_key != ""
            else set()
        )
        members |= dict.fromkeys(
            token.strip()
            for token in entries.get(order_key, "").split(",")
            if token.strip() and token.strip() not in excluded
        )
    return tuple(members)


#: Every family of words the entry vocabularies use, as ``prefix -> members``.
ENTRY_OPTION_FAMILIES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        f"{ENTRY_OPTION_LABEL_PREFIX}deduction_fact_kind.": _ordered(_DEDUCTION_FACT, "kind.order", "kind.owner_only"),
        f"{ENTRY_OPTION_LABEL_PREFIX}m210_payer_mode.": _ordered(_M210_FACT, "m210.payer_mode_order"),
        f"{ENTRY_OPTION_LABEL_PREFIX}m210_income_concept.": _ordered(_M210_FACT, "m210.tipo_renta.order"),
        f"{ENTRY_OPTION_LABEL_PREFIX}gasto_capital_inmobiliario.": _ordered(_GASTO_INMOBILIARIO_FACT, "concept_order"),
        f"{ENTRY_OPTION_LABEL_PREFIX}withholding_certificate_figure.": tuple(
            dict.fromkeys(
                figure.value for income_class in RetencionSoportadaClase for figure in certificate_figures(income_class)
            )
        ),
    }
)

#: Every entry option key the desktop words, each family member spelled out.
ENTRY_OPTION_KEYS: Final[frozenset[str]] = frozenset(
    f"{prefix}{member}" for prefix, members in ENTRY_OPTION_FAMILIES.items() for member in members
)

#: The certificate figure words a withholding form shows from the ``label_key`` the operation
#: serves with each figure, so the shell translates them as they come and never names them.
WITHHOLDING_CERTIFICATE_FIGURE_KEYS: Final[frozenset[str]] = frozenset(
    key for key in ENTRY_OPTION_KEYS if key.startswith(f"{ENTRY_OPTION_LABEL_PREFIX}withholding_certificate_figure.")
)


#: The chrome words of the served registry tokens, as ``prefix -> members``. The window words
#: a served token with its chrome key and shows the token itself when the chrome has none.
ENTRY_TOKEN_WORD_FAMILIES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "desktop.ledger.iva_category.": _ordered(_IVA_CATEGORY_FACT, "category.order"),
        "desktop.ledger.irpf_category.": _ordered(_IRPF_TAXONOMY_FACT, "catalogue.ids"),
        "desktop.ledger.category.": _ordered(_CATEGORIES_FACT, "spending_category.order"),
        "desktop.ledger.category_keywords.": _ordered(_CATEGORIES_FACT, "spending_category.order"),
        "desktop.ledger.category_family.": _under(_CATEGORIES_FACT, "spending_category.family."),
        "desktop.ledger.invoices.class.": tuple(
            token.lower() for token in _ordered(_INVOICE_CLASS_FACT, "invoice_class.order")
        ),
        "desktop.ledger.invoices.situacion.s": _under(_PREMISES_FACT, "situacion_inmueble.", values=True),
        "desktop.ledger.prorrata.provenance.": _ordered(_PRORRATA_FACT, "prorrata.provisional_provenance_order"),
        "desktop.ledger.prorrata.letra.": _ordered(_PRORRATA_FACT, "prorrata.sector_diferenciado_letra_order"),
        "desktop.ledger.capital.kind.": _ordered(_CAPITAL_FACT, "kind.order"),
        "desktop.ledger.capital.disposal.": _ordered(_CAPITAL_FACT, "disposal_regime.order"),
        # Every format the import knows; an installation serves those whose parser it carries.
        "desktop.ledger.import.provider.": tuple(provider.value for provider in LedgerProviderID),
    }
)

#: Every chrome key that words a served registry token.
ENTRY_TOKEN_WORD_KEYS: Final[frozenset[str]] = frozenset(
    f"{prefix}{member}" for prefix, members in ENTRY_TOKEN_WORD_FAMILIES.items() for member in members
)
