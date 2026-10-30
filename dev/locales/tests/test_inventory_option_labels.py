"""Every value an inventory form is offered has a word in every locale."""

from __future__ import annotations

from uuid import UUID

import pytest
import yaml

from cadrumo.application.inventory.registered_options_operation import INVENTORY_OPTION_FAMILIES, inventory_options

from .._paths import LOCALES_DIR

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("28282828-2828-4828-8828-282828282828")


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_every_option_is_worded(locale: str) -> None:
    catalogue = yaml.safe_load((LOCALES_DIR / locale / "application.yml").read_text(encoding="utf-8"))
    missing: list[str] = []
    for family in inventory_options(_PROFILE).families:
        for option in family.options:
            node = catalogue
            for part in option.label_key.split("."):
                node = node.get(part) if isinstance(node, dict) else None
            if not isinstance(node, str) or not node.strip():
                missing.append(option.label_key)

    assert missing == []


def test_the_options_are_exactly_the_canonical_vocabularies() -> None:
    served = {family.family: [item.value for item in family.options] for family in inventory_options(_PROFILE).families}

    assert served == {family: [member.value for member in enum] for family, enum in INVENTORY_OPTION_FAMILIES}
