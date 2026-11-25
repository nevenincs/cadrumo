"""The desktop Stock panel words every token the inventory operations serve.

The options operation serves every closed choice a form offers, each with the key of its word, and the
kinds of change a book's history holds among them. The canonical catalogues hold one word for
each, and the desktop reads them through its generated strings; a refusal arrives as a catalogue
key under ``application.inventory.service.errors`` with the facts that fill it in, and an advisory
as a key under ``application.inventory.advisories`` filled in with its year. Each test below fails
when a backend token has no word in a locale, when the declaration drifts from the enums, or when a
typed refusal reason has no sentence in the backend's catalogue.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.contribuyente.inventory.closing_foundations import (
    InventoryClosingAuthority,
    InventoryClosingDecisionEvidenceRole,
    InventoryClosingValuationBasis,
    PhysicalClosingEvidenceRole,
)
from cadrumo.domain.contribuyente.inventory.records import (
    InventoryAcquisitionEvidenceKind,
    InventoryAttributableCostKind,
    InventoryCorrectionReason,
    InventoryHistoryKind,
    InventoryRetirementReason,
    MovementKind,
    PurchaseLedgerRow,
    ValuationMethod,
)

from ..desktop_assets_keys import (
    INVENTORY_ADVISORY_FAMILY,
    INVENTORY_ENUM_FAMILIES,
    INVENTORY_FAMILIES,
    INVENTORY_KEYS,
    INVENTORY_LABEL_NAMESPACE,
)
from ..desktop_chrome import DESKTOP_CHROME_KEYS, DESKTOP_LOCALES, desktop_chrome_strings
from ..paths import LOCALES_DIR

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Each family and the enum the operations serve its tokens from, written out here so the declaration
#: cannot agree with itself while drifting from the backend.
_SERVED = {
    "acquisition_evidence_kind": InventoryAcquisitionEvidenceKind,
    "attributable_cost_kind": InventoryAttributableCostKind,
    "closing_authority": InventoryClosingAuthority,
    "closing_valuation_basis": InventoryClosingValuationBasis,
    "correction_reason": InventoryCorrectionReason,
    "decision_evidence_role": InventoryClosingDecisionEvidenceRole,
    "history_kind": InventoryHistoryKind,
    "movement_kind": MovementKind,
    "physical_evidence_role": PhysicalClosingEvidenceRole,
    "purchase_ledger_row": PurchaseLedgerRow,
    "retirement_reason": InventoryRetirementReason,
    "valuation_method": ValuationMethod,
}


def test_the_declared_families_are_exactly_the_enums_and_reasons_the_backend_serves() -> None:
    declared = {
        prefix.removeprefix(INVENTORY_LABEL_NAMESPACE).rstrip("."): members
        for prefix, members in INVENTORY_FAMILIES.items()
        if prefix != INVENTORY_ADVISORY_FAMILY
    }

    assert declared == {family: tuple(sorted(member.value for member in enum)) for family, enum in _SERVED.items()}
    assert set(INVENTORY_ENUM_FAMILIES.values()) == set(_SERVED.values())
    assert INVENTORY_FAMILIES[INVENTORY_ADVISORY_FAMILY]
    assert INVENTORY_KEYS <= DESKTOP_CHROME_KEYS


@pytest.mark.parametrize("locale", DESKTOP_LOCALES)
def test_every_token_the_backend_serves_has_a_word_in_every_locale(locale: str) -> None:
    words = desktop_chrome_strings(LOCALES_DIR, keys=INVENTORY_KEYS, locales=(locale,))[locale]

    missing = sorted(
        f"{INVENTORY_LABEL_NAMESPACE}{family}.{member.value}"
        for family, enum in _SERVED.items()
        for member in enum
        if not words.get(f"{INVENTORY_LABEL_NAMESPACE}{family}.{member.value}", "").strip()
    )

    assert missing == []


@pytest.mark.parametrize("locale", DESKTOP_LOCALES)
def test_every_advisory_the_backend_serves_reaches_the_shell_with_its_year(locale: str) -> None:
    words = desktop_chrome_strings(LOCALES_DIR, keys=INVENTORY_KEYS, locales=(locale,))[locale]
    advisories = {key: text for key, text in words.items() if key.startswith(INVENTORY_ADVISORY_FAMILY)}

    assert advisories
    for key, text in advisories.items():
        assert "{year}" in text, key
        assert "%{" not in text, key


def test_the_options_the_backend_serves_are_exactly_the_families_declared() -> None:
    from cadrumo.application.inventory.registered_options_operation import INVENTORY_OPTION_FAMILIES

    served = {family: enum for family, enum in INVENTORY_OPTION_FAMILIES}

    assert set(served) == set(_SERVED)
    for family, enum in served.items():
        assert _SERVED[family] is enum
