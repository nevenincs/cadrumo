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

from typing import get_args

import pytest

from cadrumo.application.inventory.registered_requests import InventoryRefusalReason
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
    ValuationMethod,
)

from .._paths import LOCALES_DIR
from ..desktop_assets_keys import (
    INVENTORY_ADVISORY_FAMILY,
    INVENTORY_ENUM_FAMILIES,
    INVENTORY_FAMILIES,
    INVENTORY_KEYS,
    INVENTORY_LABEL_NAMESPACE,
    INVENTORY_REASON_FAMILY,
)
from ..desktop_chrome import DESKTOP_CHROME_KEYS, DESKTOP_LOCALES, desktop_chrome_strings

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
    "retirement_reason": InventoryRetirementReason,
    "valuation_method": ValuationMethod,
}


def test_the_declared_families_are_exactly_the_enums_and_reasons_the_backend_serves() -> None:
    declared = {
        prefix.removeprefix(INVENTORY_LABEL_NAMESPACE).rstrip("."): members
        for prefix, members in INVENTORY_FAMILIES.items()
        if prefix not in (INVENTORY_REASON_FAMILY, INVENTORY_ADVISORY_FAMILY)
    }

    assert declared == {family: tuple(sorted(member.value for member in enum)) for family, enum in _SERVED.items()}
    assert set(INVENTORY_ENUM_FAMILIES.values()) == set(_SERVED.values())
    assert INVENTORY_FAMILIES[INVENTORY_REASON_FAMILY]
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


def test_every_reason_an_inventory_change_is_refused_for_has_a_sentence_in_the_catalogue() -> None:
    sentences = {member for member in INVENTORY_FAMILIES[INVENTORY_REASON_FAMILY]}

    missing = sorted(set(get_args(InventoryRefusalReason)) - sentences)

    assert missing == []


@pytest.mark.parametrize("locale", DESKTOP_LOCALES)
def test_every_sentence_the_catalogue_has_for_a_refusal_reaches_the_shell_in_every_locale(locale: str) -> None:
    words = desktop_chrome_strings(LOCALES_DIR, keys=INVENTORY_KEYS, locales=(locale,))[locale]

    unworded = sorted(
        f"{INVENTORY_REASON_FAMILY}{member}"
        for member in INVENTORY_FAMILIES[INVENTORY_REASON_FAMILY]
        if not words.get(f"{INVENTORY_REASON_FAMILY}{member}", "").strip()
    )

    assert unworded == []
    # The shell substitutes plain ``{name}`` placeholders, never the backend's own form.
    assert not [key for key, text in words.items() if "%{" in text]


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
