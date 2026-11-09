"""Every registry token the ledger serves for an entry form has a word in the desktop chrome.

The window keeps no list of these tokens: it shows what the operation serves, worded by chrome keys
that are declared from the same governed facts. The operation is read on each supported year, so a
token a dated catalogue adds fails here until its word is authored.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cadrumo.application.ledger.entry_options_operation import ledger_entry_options
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

from ..desktop_chrome import DESKTOP_CHROME_FAMILIES, DESKTOP_CHROME_KEYS
from ..desktop_entry_option_keys import ENTRY_TOKEN_WORD_FAMILIES

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Where each served family is worded: the chrome prefix, and how a served value becomes the key's member.
_WORDED = {
    "iva_category": ("desktop.ledger.iva_category.", str),
    "irpf_category": ("desktop.ledger.irpf_category.", str),
    "spending_category": ("desktop.ledger.category.", str),
    "invoice_class": ("desktop.ledger.invoices.class.", str.lower),
    "premises_situation": ("desktop.ledger.invoices.situacion.s", str),
    "prorrata_provenance": ("desktop.ledger.prorrata.provenance.", str),
    "prorrata_sector_letter": ("desktop.ledger.prorrata.letra.", str),
    "capital_good_kind": ("desktop.ledger.capital.kind.", str),
    "capital_good_disposal": ("desktop.ledger.capital.disposal.", str),
    "import_format": ("desktop.ledger.import.provider.", str),
}


def test_the_chrome_declares_exactly_the_members_the_facts_declare() -> None:
    for prefix, members in ENTRY_TOKEN_WORD_FAMILIES.items():
        assert DESKTOP_CHROME_FAMILIES[prefix] == members, prefix
        assert {f"{prefix}{member}" for member in members} <= DESKTOP_CHROME_KEYS


def test_every_token_served_on_any_supported_day_has_a_chrome_word() -> None:
    with bundled_indexed_authority().operation() as operation:
        years = sorted(operation.supported_filing_years().years)
        unworded: set[str] = set()
        for year in (years[0], years[-1]):
            for family in ledger_entry_options(uuid4(), operation=operation, on_date=date(year, 6, 30)).families:
                if family.family not in _WORDED:
                    continue
                prefix, member = _WORDED[family.family]
                unworded |= {
                    f"{prefix}{member(option.value)}"
                    for option in family.options
                    if f"{prefix}{member(option.value)}" not in DESKTOP_CHROME_KEYS
                }
        served_groups = {
            option.group
            for family in ledger_entry_options(uuid4(), operation=operation).families
            if family.family == "spending_category"
            for option in family.options
        }

    assert sorted(unworded) == []
    assert {f"desktop.ledger.category_family.{group}" for group in served_groups} <= DESKTOP_CHROME_KEYS
