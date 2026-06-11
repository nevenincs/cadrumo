"""Tests for the core aggregation taxonomy (AggregationSourceKind).

contract — real-behaviour test suite verifying:
- AggregationSourceKind canonical home is aeat.core.aggregation.
- All members round-trip through pydantic field validation.
- No production module under src/aeat/ imports AggregationSourceKind
  from aeat.application.aggregation._source_kinds (migration inventory).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from ..aggregation import AggregationSourceKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# ---------------------------------------------------------------------------
# contract — canonical home
# ---------------------------------------------------------------------------


def test_aggregation_source_kind_canonical_module() -> None:
    """AggregationSourceKind.__module__ reports its canonical home in aeat.core.aggregation."""

    assert AggregationSourceKind.__module__ == "aeat.core.aggregation"


def test_aggregation_source_kind_importable_from_core() -> None:
    """AggregationSourceKind can be imported directly from aeat.core.aggregation."""

    import importlib

    mod = importlib.import_module("aeat.core.aggregation")
    assert hasattr(mod, "AggregationSourceKind")
    assert mod.AggregationSourceKind is AggregationSourceKind


def test_aggregation_source_kind_members_are_complete() -> None:
    """The enum carries the canonical source-kind members including the INVOICE alias."""

    expected = {
        "INVOICE",
        "LEDGER_TRANSACTION",
        "PURCHASE_INVOICE_EVIDENCE",
        "PAYABLE_INVOICE",
        "COLLECTIBLE_INVOICE",
    }
    actual = {member.name for member in AggregationSourceKind}
    assert actual == expected


def test_aggregation_source_kind_values() -> None:
    """Each member's string value matches the snake_case sentinel stored in persisted records."""

    assert AggregationSourceKind.LEDGER_TRANSACTION == "ledger_transaction"
    assert AggregationSourceKind.PURCHASE_INVOICE_EVIDENCE == "purchase_invoice_evidence"
    assert AggregationSourceKind.PAYABLE_INVOICE == "payable_invoice"
    assert AggregationSourceKind.COLLECTIBLE_INVOICE == "collectible_invoice"


# ---------------------------------------------------------------------------
# contract — pydantic roundtrip
# ---------------------------------------------------------------------------


class _SourceKindEnvelope(BaseModel):
    kind: AggregationSourceKind


@pytest.mark.parametrize("member", list(AggregationSourceKind))
def test_aggregation_source_kind_roundtrip_pydantic(member: AggregationSourceKind) -> None:
    """Every AggregationSourceKind member survives a pydantic validation roundtrip.

    Builds a model from the raw string value, validates, and asserts strict
    enum-member equality on the parsed field.  A broken StrEnum serialisation
    would produce a string, not an enum member, and fail the identity check.
    """

    raw = member.value
    envelope = _SourceKindEnvelope.model_validate({"kind": raw})
    assert envelope.kind is member
    assert isinstance(envelope.kind, AggregationSourceKind)


def test_aggregation_source_kind_rejects_unknown_value() -> None:
    """Pydantic raises ValidationError for a value not in the enum."""

    with pytest.raises(ValidationError):
        _SourceKindEnvelope.model_validate({"kind": "not_a_valid_source_kind"})


def test_aggregation_source_kind_roundtrip_json() -> None:
    """All members survive JSON serialise → deserialise via pydantic."""

    for member in AggregationSourceKind:
        envelope = _SourceKindEnvelope(kind=member)
        json_str = envelope.model_dump_json()
        restored = _SourceKindEnvelope.model_validate_json(json_str)
        assert restored.kind is member


# ---------------------------------------------------------------------------
# Structural invariant: AggregationSourceKind lives at aeat.core.aggregation
# ---------------------------------------------------------------------------

_FORBIDDEN_ABSOLUTE_PATH = "aeat.application.aggregation._source_kinds"
_FORBIDDEN_RELATIVE_MODULE = "_source_kinds"
_GUARDED_NAME = "AggregationSourceKind"


def test_aggregation_source_kind_has_a_single_canonical_import_path() -> None:
    """``AggregationSourceKind`` must only be imported from ``aeat.core.aggregation``.

    The enum is a core primitive; importing it from any private aggregation
    module re-introduces a hidden second source of truth. The AST walker below
    asserts no production module reaches for either an absolute or relative
    private alias of the enum.
    """

    repo_root = Path(__file__).parents[3]
    src_root = repo_root / "src" / "aeat"

    offenders: list[str] = []

    for py_file in src_root.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))

        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module == _FORBIDDEN_ABSOLUTE_PATH:
                for alias in node.names:
                    if alias.name == _GUARDED_NAME:
                        offenders.append(
                            f"{py_file.relative_to(repo_root)}:{node.lineno}: "
                            f"absolute import from private path '{_FORBIDDEN_ABSOLUTE_PATH}'",
                        )
            if node.module == _FORBIDDEN_RELATIVE_MODULE and node.level and node.level >= 1:
                for alias in node.names:
                    if alias.name == _GUARDED_NAME:
                        offenders.append(
                            f"{py_file.relative_to(repo_root)}:{node.lineno}: "
                            f"relative import from private module '{_FORBIDDEN_RELATIVE_MODULE}'",
                        )

    assert offenders == [], (
        f"{_GUARDED_NAME} must be imported from 'aeat.core.aggregation' only.\n"
        "Offending imports:\n" + "\n".join(offenders)
    )
