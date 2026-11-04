"""The desktop's recorded invoice figures-preview answers stay what the preview answers."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authority_lease_support import private_authority_lease
from .figures_preview_support import recorded_preview_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RECORDING: Final = (
    Path(__file__).resolve().parents[5] / "native/desktop/frontend/src/dev/fixtures/ledgerInvoicePreview.json"
)
_RECORDED: Final[dict[str, dict[str, Any]]] = json.loads(_RECORDING.read_text(encoding="utf-8"))["recordings"]


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with private_authority_lease() as leased:
        yield leased


@pytest.mark.parametrize("name", _RECORDED)
def test_every_recorded_answer_is_the_previews(name: str, operation: PinnedAuthorityOperation) -> None:
    recording = _RECORDED[name]

    assert recorded_preview_result(recording["request"], operation) == recording["result"]
