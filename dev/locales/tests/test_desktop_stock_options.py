"""The choices the desktop Stock panel offers reflect the backend's enums, and each has its words.

The backend serves no list of valuation methods, movement kinds, extra-cost kinds or kinds of
proof, so the panel keeps a list of each beside its forms. A list that drifted from its enum would
offer a choice the backend refuses or leave one out, so each is held to the enum it is named for,
and every member to the words the chrome declares for it.
"""

from __future__ import annotations

import re
from enum import StrEnum

import pytest

from cadrumo.domain.contribuyente.inventory.records import (
    InventoryAcquisitionEvidenceKind,
    InventoryAttributableCostKind,
    MovementKind,
    ValuationMethod,
)
from dev._paths import REPO_ROOT

from ..desktop_chrome import DESKTOP_CHROME_KEYS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODEL = REPO_ROOT / "native" / "desktop" / "frontend" / "src" / "components" / "ledger" / "assets" / "stockModel.ts"


def _list(name: str) -> list[str]:
    """The members of one exported list in the panel's model, in order."""
    found = re.search(rf"export const {name} = \[(.*?)\]", _MODEL.read_text(encoding="utf-8"), re.DOTALL)
    assert found is not None, f"the panel's model names no list {name}"
    return [str(value) for value in re.findall(r'"([^"]+)"', found.group(1))]


def _constant(name: str) -> str:
    found = re.search(rf'export const {name} = "([^"]+)"', _MODEL.read_text(encoding="utf-8"))
    assert found is not None, f"the panel's model names no constant {name}"
    return str(found.group(1))


@pytest.mark.parametrize(
    ("name", "enum"),
    [
        ("METHODS", ValuationMethod),
        ("KINDS", MovementKind),
        ("COST_KINDS", InventoryAttributableCostKind),
    ],
)
def test_a_list_the_panel_offers_is_its_enum(name: str, enum: type[StrEnum]) -> None:
    offered = _list(name)

    assert len(offered) == len(set(offered)), f"{name} offers a choice twice"
    assert sorted(offered) == sorted(member.value for member in enum)


def test_the_kinds_of_proof_are_the_enum_less_the_two_checks_a_purchase_states() -> None:
    offered = [*_list("PROOF_KINDS"), _constant("COST_CHECK_KIND"), _constant("IVA_CHECK_KIND")]

    assert len(offered) == len(set(offered))
    assert sorted(offered) == sorted(member.value for member in InventoryAcquisitionEvidenceKind)


@pytest.mark.parametrize(
    ("name", "family"),
    [
        ("METHODS", "desktop.ledger.inventory.method."),
        ("KINDS", "desktop.ledger.inventory.kind."),
        ("COST_KINDS", "desktop.ledger.stock.cost_kind."),
        ("PROOF_KINDS", "desktop.ledger.stock.proof_kind."),
    ],
)
def test_every_choice_the_panel_offers_has_its_words_declared(name: str, family: str) -> None:
    declared = {key for key in DESKTOP_CHROME_KEYS if key.startswith(family)}

    assert declared == {f"{family}{token}" for token in _list(name)}
