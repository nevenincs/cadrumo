"""The preview's served words are declared from the closed vocabularies that name them."""

from __future__ import annotations

import pytest
import yaml

from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from cadrumo.domain.invoices.figures import FigureFindingCode

from .._paths import LOCALES_DIR
from ..fstring_registry import get_registered_keys
from ..invoice_figures_preview_keys import FINDING_KEYS, RATE_SLOT_KEYS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PREFIX = "application.invoices.figures_preview."


def test_every_finding_code_has_exactly_one_key() -> None:
    assert {f"{_PREFIX}finding.{code.value}" for code in FigureFindingCode} == FINDING_KEYS
    assert len(FINDING_KEYS) == len(FigureFindingCode)


def test_the_rate_slots_are_spelled_lowercase_with_the_dot_an_underscore() -> None:
    # The registry declares RATE_0, RATE_2, RATE_4, RATE_5, RATE_7.5, RATE_10, RATE_21, EXEMPT and NOT_SUBJECT.
    assert {
        f"{_PREFIX}rate_slot.{token}"
        for token in ("rate_0", "rate_2", "rate_4", "rate_5", "rate_7_5", "rate_10", "rate_21", "exempt", "not_subject")
    } == RATE_SLOT_KEYS


def test_both_families_are_registered_for_scaffolding() -> None:
    registered = get_registered_keys()
    assert registered >= FINDING_KEYS | RATE_SLOT_KEYS


@pytest.mark.parametrize("language", sorted(str(language) for language in SUPPORTED_OUTPUT_LANGUAGES))
def test_every_served_word_is_authored_in_every_locale(language: str) -> None:
    catalogue = yaml.safe_load((LOCALES_DIR / language / "application.yml").read_text(encoding="utf-8"))
    node = catalogue
    for part in f"{_PREFIX}finding".rstrip(".").split("."):
        node = node[part]
    findings = set(node)
    slots = set(catalogue["application"]["invoices"]["figures_preview"]["rate_slot"])
    assert findings == {code.value for code in FigureFindingCode}
    assert {f"{_PREFIX}rate_slot.{slot}" for slot in slots} == RATE_SLOT_KEYS
