"""Structural proof for the single export semantic producer vocabulary."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....domain.calculations.registry import (
    ExportComputedKey,
    ExportDraftAttribute,
    ExportHeaderKey,
)
from ....domain.filing import FilingExportValidationError
from .._export import (
    _COMPUTED_VALUE_PRODUCERS,
    _DRAFT_VALUE_PRODUCERS,
    _normalise_export_headers,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_HEADER_PRODUCER_FUNCTIONS = frozenset(
    {
        "_compose_charge_account_block",
        "_compose_refund_account_block",
        "_compose_export_headers",
    },
)


def _enum_keys_in_header_producers(source: str) -> tuple[set[ExportHeaderKey], tuple[str, ...]]:
    """Read enum-key writes from the one production composition unit."""
    tree = ast.parse(source)
    produced: set[ExportHeaderKey] = set()
    raw_string_keys: list[str] = []
    for function in (node for node in tree.body if isinstance(node, ast.FunctionDef)):
        if function.name not in _HEADER_PRODUCER_FUNCTIONS:
            continue
        for node in ast.walk(function):
            candidates: tuple[ast.expr | None, ...] = ()
            if isinstance(node, ast.Dict):
                candidates = tuple(node.keys)
            elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store):
                candidates = (node.slice,)
            for candidate in candidates:
                if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
                    raw_string_keys.append(candidate.value)
                if (
                    isinstance(candidate, ast.Attribute)
                    and isinstance(candidate.value, ast.Name)
                    and candidate.value.id == "ExportHeaderKey"
                ):
                    produced.add(ExportHeaderKey[candidate.attr])
    return produced, tuple(sorted(raw_string_keys))


def test_every_admitted_header_key_is_written_by_the_single_production_composer() -> None:
    producer_source = Path("src/cadrumo/application/modelo/_export.py").read_text(encoding="utf-8")

    produced, raw_string_keys = _enum_keys_in_header_producers(producer_source)

    assert produced == set(ExportHeaderKey)
    assert raw_string_keys == ()


def test_draft_and_computed_vocabularies_are_total_over_their_dispatch_tables() -> None:
    assert set(_DRAFT_VALUE_PRODUCERS) == set(ExportDraftAttribute)
    assert set(_COMPUTED_VALUE_PRODUCERS) == set(ExportComputedKey)


@pytest.mark.parametrize("deleted_key", ("presenter_nif", "presenter_tax_id", "record_type"))
def test_deleted_or_unproduced_header_tokens_fail_at_the_filing_boundary(deleted_key: str) -> None:
    with pytest.raises(FilingExportValidationError, match="not recognised"):
        _normalise_export_headers({deleted_key: "value"})


def test_filing_header_boundary_retains_enum_identity_without_casefolding() -> None:
    normalized = _normalise_export_headers({ExportHeaderKey.PROGRAM_VERSION: "A001"})

    assert normalized == {ExportHeaderKey.PROGRAM_VERSION: "A001"}
    with pytest.raises(FilingExportValidationError, match="not recognised"):
        _normalise_export_headers({"PROGRAM_VERSION": "A001"})
