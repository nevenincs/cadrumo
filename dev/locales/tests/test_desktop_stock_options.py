"""The desktop Stock panel holds no list of the choices its forms offer, and names only what it must.

The options operation serves every closed choice a form offers, so the panel keeps no list of
methods, kinds, reasons or bases beside its forms. Three values are named because a form treats them
apart from the rest, and each is held here to the enum member it names; and a panel source that
quoted any other served value would be keeping a list of its own.
"""

from __future__ import annotations

import re

import pytest

from cadrumo.application.inventory.registered_options_operation import INVENTORY_OPTION_FAMILIES
from cadrumo.domain.contribuyente.inventory.closing_foundations import InventoryClosingAuthority
from cadrumo.domain.contribuyente.inventory.records import InventoryAcquisitionEvidenceKind, MovementKind
from dev._paths import REPO_ROOT

from ..desktop_chrome import DESKTOP_CHROME_KEYS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ASSETS = REPO_ROOT / "native" / "desktop" / "frontend" / "src" / "components" / "ledger" / "assets"
_SOURCES = [_ASSETS / "stockModel.ts", _ASSETS / "StockPane.tsx"]


def _constant(name: str) -> str:
    found = re.search(rf'export const {name} = "([^"]+)"', _SOURCES[0].read_text(encoding="utf-8"))
    assert found is not None, f"the panel's model names no constant {name}"
    return str(found.group(1))


def test_the_two_checks_a_purchase_states_are_kinds_of_proof_the_backend_serves() -> None:
    kinds = {member.value for member in InventoryAcquisitionEvidenceKind}

    assert _constant("COST_CHECK_KIND") in kinds
    assert _constant("IVA_CHECK_KIND") in kinds
    assert _constant("COST_CHECK_KIND") != _constant("IVA_CHECK_KIND")


def test_the_authority_a_count_settles_is_one_the_backend_serves() -> None:
    assert _constant("PHYSICAL_AUTHORITY") in {member.value for member in InventoryClosingAuthority}
    assert MovementKind.PURCHASE.value == "purchase"


def test_the_panel_quotes_no_served_value_it_does_not_name_on_purpose() -> None:
    named = {
        MovementKind.PURCHASE.value,
        _constant("COST_CHECK_KIND"),
        _constant("IVA_CHECK_KIND"),
        _constant("PHYSICAL_AUTHORITY"),
    }
    quoted = set()
    for source in _SOURCES:
        quoted |= set(re.findall(r'"([a-z][a-z_]*)"', source.read_text(encoding="utf-8")))

    served = {
        member.value
        for _, enum in INVENTORY_OPTION_FAMILIES
        for member in enum
        # A bare word such as "opening" or "count" is also an ordinary name in the panel's own code.
        if "_" in member.value or member.value in {"fifo", "pmp", "cogs", "freight"}
    }
    # ``physical_count`` is also the name of a field of the closing request.
    assert sorted((served & quoted) - named - {"physical_count"}) == []


@pytest.mark.parametrize("family", [family for family, _ in INVENTORY_OPTION_FAMILIES])
def test_every_choice_served_has_its_words_declared_for_the_shell(family: str) -> None:
    prefix = f"application.inventory.labels.{family}."
    members = {member.value for name, enum in INVENTORY_OPTION_FAMILIES if name == family for member in enum}

    assert {key.removeprefix(prefix) for key in DESKTOP_CHROME_KEYS if key.startswith(prefix)} == members
