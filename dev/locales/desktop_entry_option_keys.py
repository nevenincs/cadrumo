"""The words the desktop shows for the ledger entry vocabularies the backend serves.

The operation serves registry tokens with the key of each word. The members are
read from the governed facts that declare them, so a token the registry adds is
declared here with it and generation refuses until its word is authored.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from cadrumo.application.ledger.entry_options_operation import ENTRY_OPTION_LABEL_PREFIX
from cadrumo.core.resources.bundled_data import bundled_path

_DEDUCTION_FACT: Final[str] = "0085-iva-deduction-applicability-catalogue.toml"
_M210_FACT: Final[str] = "0080-detail-m349-m210-catalogues.toml"


def _ordered(fact_file: str, order_key: str, excluded_key: str | None = None) -> tuple[str, ...]:
    """Return one declared order across the fact's variants, first seen first."""
    with bundled_path("registry", "aeat", "facts", fact_file).open("rb") as handle:
        fact = tomllib.load(handle)["fact"]
    members: dict[str, None] = {}
    for variant in fact["variants"]:
        entries = {entry["key"]: entry["value"] for entry in variant["payload"]["entries"]}
        excluded = {token.strip() for token in entries.get(excluded_key, "").split(",")} if excluded_key else set()
        members |= dict.fromkeys(
            token.strip() for token in entries.get(order_key, "").split(",") if token.strip() and token.strip() not in excluded
        )
    return tuple(members)


#: Every family of words the entry vocabularies use, as ``prefix -> members``.
ENTRY_OPTION_FAMILIES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        f"{ENTRY_OPTION_LABEL_PREFIX}deduction_fact_kind.": _ordered(_DEDUCTION_FACT, "kind.order", "kind.owner_only"),
        f"{ENTRY_OPTION_LABEL_PREFIX}m210_payer_mode.": _ordered(_M210_FACT, "m210.payer_mode_order"),
        f"{ENTRY_OPTION_LABEL_PREFIX}m210_income_concept.": _ordered(_M210_FACT, "m210.tipo_renta.order"),
    }
)

#: Every entry option key the desktop words, each family member spelled out.
ENTRY_OPTION_KEYS: Final[frozenset[str]] = frozenset(
    f"{prefix}{member}" for prefix, members in ENTRY_OPTION_FAMILIES.items() for member in members
)
