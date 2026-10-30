"""The desktop Stock panel holds no list of the choices its forms offer, and names only what it must.

The options operation serves every closed choice a form offers, and marks with a role the members a
form treats apart from the rest, so the panel keeps no list of methods, kinds, reasons or bases beside
its forms and names none of their values. A panel source that quoted a served value would be keeping
a list of its own.
"""

from __future__ import annotations

import re

import pytest

from cadrumo.application.inventory.registered_options_operation import INVENTORY_OPTION_FAMILIES
from dev._paths import REPO_ROOT

from ..desktop_chrome import DESKTOP_CHROME_KEYS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ASSETS = REPO_ROOT / "native" / "desktop" / "frontend" / "src" / "components" / "ledger" / "assets"
_SOURCES = [_ASSETS / "stockModel.ts", _ASSETS / "StockPane.tsx"]


def test_the_panel_quotes_no_served_value_it_could_read_from_the_options() -> None:
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
    assert sorted((served & quoted) - {"physical_count"}) == []


def test_the_roles_a_form_reads_belong_to_the_families_that_serve_them() -> None:
    from uuid import uuid4

    from cadrumo.application.inventory.registered_options_operation import inventory_options

    roles = {
        (family.family, option.role)
        for family in inventory_options(uuid4()).families
        for option in family.options
        if option.role is not None
    }

    assert roles == {
        ("acquisition_evidence_kind", "cost_check"),
        ("acquisition_evidence_kind", "iva_check"),
        ("closing_authority", "count_authority"),
        ("movement_kind", "purchase"),
    }


@pytest.mark.parametrize("family", [family for family, _ in INVENTORY_OPTION_FAMILIES])
def test_every_choice_served_has_its_words_declared_for_the_shell(family: str) -> None:
    prefix = f"application.inventory.labels.{family}."
    members = {member.value for name, enum in INVENTORY_OPTION_FAMILIES if name == family for member in enum}

    assert {key.removeprefix(prefix) for key in DESKTOP_CHROME_KEYS if key.startswith(prefix)} == members
