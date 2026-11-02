"""The words the invoice figures preview serves for its closed findings and rate slots.

The operation serves the key of each word beside the code or slot it names. The
codes come from the closed finding vocabulary and the slots from the governed
rate-slot fact, so a member added to either is declared here with it and
generation refuses until its word is authored.
"""

from __future__ import annotations

import tomllib
from typing import Final

from cadrumo.application.invoices.figures_preview_contracts import INVOICE_FIGURES_PREVIEW_LABEL_PREFIX
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.invoices.figures import FigureFindingCode
from cadrumo.domain.invoices.rule_findings import InvoiceRuleFindingCode

_RATE_SLOT_FACT: Final[str] = "0094-iva-rate-slot-catalogue.toml"


def _declared_slots() -> tuple[str, ...]:
    """Return every slot the governed fact declares in any variant, first seen first."""
    with bundled_path("registry", "aeat", "facts", _RATE_SLOT_FACT).open("rb") as handle:
        fact = tomllib.load(handle)["fact"]
    slots: dict[str, None] = {}
    for variant in fact["variants"]:
        entries = {entry["key"]: entry["value"] for entry in variant["payload"]["entries"]}
        slots |= dict.fromkeys(token.strip() for token in entries["slot_order"].split(",") if token.strip())
    return tuple(slots)


def rate_slot_key(slot: str) -> str:
    """Spell a slot's key as the operation serves it: lowercased, with the dot an underscore."""
    return f"{INVOICE_FIGURES_PREVIEW_LABEL_PREFIX}rate_slot.{slot.lower().replace('.', '_')}"


#: Every finding key, one per member of the closed finding vocabulary.
FINDING_KEYS: Final[frozenset[str]] = frozenset(
    f"{INVOICE_FIGURES_PREVIEW_LABEL_PREFIX}finding.{code.value}" for code in FigureFindingCode
)

#: Every rule-finding key, one per member of the closed document-rule vocabulary.
RULE_FINDING_KEYS: Final[frozenset[str]] = frozenset(
    f"{INVOICE_FIGURES_PREVIEW_LABEL_PREFIX}rule_finding.{code.value}" for code in InvoiceRuleFindingCode
)

#: Every rate-slot key, one per slot the registry declares.
RATE_SLOT_KEYS: Final[frozenset[str]] = frozenset(rate_slot_key(slot) for slot in _declared_slots())
