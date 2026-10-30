"""Inventory correction refusals and tokens reach operators in every supported locale.

The reasons and tokens are derived from their owning definitions, so a new refusal
reason or enum token without catalogue entries fails here.
"""

from __future__ import annotations

from typing import get_args

import pytest

from cadrumo.application.inventory.registered_requests import InventoryRefusalReason
from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from cadrumo.domain.contribuyente.inventory.corrections import inventory_refusal_key
from cadrumo.domain.contribuyente.inventory.records import (
    InventoryCorrectionReason,
    InventoryHistoryKind,
    InventoryRetirementReason,
)

from .._paths import LOCALES_DIR, SRC_DIR
from ..manager import LocaleManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LABELS = "application.inventory.labels"


def _required_keys() -> frozenset[str]:
    return frozenset(
        (
            *(inventory_refusal_key(reason) for reason in get_args(InventoryRefusalReason)),
            *(f"{_LABELS}.correction_reason.{token.value}" for token in InventoryCorrectionReason),
            *(f"{_LABELS}.retirement_reason.{token.value}" for token in InventoryRetirementReason),
            *(f"{_LABELS}.history_kind.{token.value}" for token in InventoryHistoryKind),
        )
    )


def test_every_correction_refusal_and_token_resolves_in_every_locale() -> None:
    manager = LocaleManager(SRC_DIR, LOCALES_DIR)
    required = _required_keys()
    assert len(required) > len(get_args(InventoryRefusalReason))
    missing = sorted(
        f"{locale}: {key}"
        for locale in SUPPORTED_OUTPUT_LANGUAGES
        for key in required - set(manager.locale_catalogue_keys(locale))
    )
    assert not missing, "\n".join(missing)
