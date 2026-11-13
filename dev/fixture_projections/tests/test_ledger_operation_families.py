"""Each family the ledger operation contract producer writes names only registered, distinct ledger definitions."""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

from cadrumo.entrypoints.operation_composition import build_production_operation_registry

from ...paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PRODUCER = REPO_ROOT / "native" / "desktop" / "frontend" / "scripts" / "ledger_operation_contract.py"
_DRIVER = _PRODUCER.with_name("ledger-operation-contract.mjs")


@pytest.fixture(scope="module")
def producer() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ledger_operation_contract", _PRODUCER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _definitions(producer: ModuleType) -> Iterator[tuple[str, str]]:
    families = cast("dict[str, tuple[str, tuple[str, ...]]]", producer.FAMILIES)
    for family, (_, definitions) in families.items():
        for definition_id in definitions:
            yield family, definition_id


def test_every_definition_is_a_registered_public_ledger_operation_with_a_result(producer: ModuleType) -> None:
    registry = build_production_operation_registry()
    for _, definition_id in _definitions(producer):
        assert definition_id.startswith("ledger.")
        assert registry.lookup_public_contract(definition_id).result_schema is not None


def test_no_definition_is_written_by_two_families(producer: ModuleType) -> None:
    named = [definition_id for _, definition_id in _definitions(producer)]
    assert len(named) == len(set(named))


def test_the_driver_names_the_module_of_each_family(producer: ModuleType) -> None:
    text = _DRIVER.read_text(encoding="utf-8")
    for family in producer.FAMILIES:
        assert f'{family}: "src/shell/ledger' in text
    assert Path(_PRODUCER).name in text
