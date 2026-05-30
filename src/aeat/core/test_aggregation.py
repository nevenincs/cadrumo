"""Tests for the core aggregation taxonomy (AggregationSourceKind).

S327 — real-behaviour test suite verifying:
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

from aeat.core.aggregation import AggregationSourceKind

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


# ---------------------------------------------------------------------------
# S325 — canonical home
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
    """The enum carries exactly the four canonical source-kind members."""

    expected = {
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
# S327 — pydantic roundtrip
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
        _SourceKindEnvelope.model_validate({"kind": "invoice"})


def test_aggregation_source_kind_roundtrip_json() -> None:
    """All members survive JSON serialise → deserialise via pydantic."""

    for member in AggregationSourceKind:
        envelope = _SourceKindEnvelope(kind=member)
        json_str = envelope.model_dump_json()
        restored = _SourceKindEnvelope.model_validate_json(json_str)
        assert restored.kind is member


# ---------------------------------------------------------------------------
# S327 — migration inventory: no importer of the old location remains
# ---------------------------------------------------------------------------


def test_no_production_module_imports_from_old_source_kinds_location() -> None:
    """No .py file under src/aeat/ imports AggregationSourceKind from the old module path.

    This test parses the AST of every production Python file and asserts that
    none of them contain an import statement of the form:
        from aeat.application.aggregation._source_kinds import AggregationSourceKind
        from ._source_kinds import AggregationSourceKind   (relative, inside aggregation/)

    A missed migration would surface as a failing assertion, not a silent import
    that resolves through a shim.
    """

    repo_root = Path(__file__).parents[3]
    src_root = repo_root / "src" / "aeat"

    _OLD_ABSOLUTE = "aeat.application.aggregation._source_kinds"
    _OLD_RELATIVE_MODULE = "_source_kinds"
    _TARGET_NAME = "AggregationSourceKind"

    offenders: list[str] = []

    for py_file in src_root.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))

        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            # Absolute import: from aeat.application.aggregation._source_kinds import ...
            if node.module == _OLD_ABSOLUTE:
                for alias in node.names:
                    if alias.name == _TARGET_NAME:
                        offenders.append(
                            f"{py_file.relative_to(repo_root)}:{node.lineno}: "
                            f"absolute import from old location '{_OLD_ABSOLUTE}'"
                        )
            # Relative import: from ._source_kinds import AggregationSourceKind
            if node.module == _OLD_RELATIVE_MODULE and node.level and node.level >= 1:
                for alias in node.names:
                    if alias.name == _TARGET_NAME:
                        offenders.append(
                            f"{py_file.relative_to(repo_root)}:{node.lineno}: "
                            f"relative import from old module '{_OLD_RELATIVE_MODULE}'"
                        )

    assert offenders == [], (
        "AggregationSourceKind is still imported from the old _source_kinds location.\n"
        "Migrate these imports to 'from aeat.core.aggregation import AggregationSourceKind':\n"
        + "\n".join(offenders)
    )
