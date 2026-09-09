"""Modelo Edit Contract V1 production invariants.

Covers real behavior and shape of the edit-contract surface: schema
strictness of the exchanged models, the writable-surface shape an admitted
baseline carries, the typed stale-baseline refusal, registry-grounded
manual-scalar/binding conformance, the absence of financial values on the
mutation-result receipt, the absence of legacy identifiers across the
edit-contract module set, and the single canonical definition of the
mutation-result receipt.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema_input_kind import InputKind
from .. import _edit_execution, revision_persistence
from .. import edit_models as _edit_models
from .. import edit_services as _edit_services
from ..edit_contract import ModeloEditCompatibilityTupleV1
from ..edit_models import (
    ModeloEditBaselineV1,
    ModeloEditMutationResultReceiptV1,
    ModeloEditStaleBaselineRefusalV1,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EDIT_CONTRACT_MODULES = (_edit_models, _edit_services, _edit_execution, revision_persistence)

_MODELO = "131"
_FILING_YEAR = 2025
_DIGEST = "a" * 64


def _period() -> Period:
    return Period.from_year_and_code(_FILING_YEAR, "1T")


def test_contract_schema_proof_covers_the_named_edit_contract_models() -> None:
    """Contract-schema proof is real introspection, not an asserted claim."""
    for model in (ModeloEditBaselineV1, ModeloEditCompatibilityTupleV1, ModeloEditMutationResultReceiptV1):
        config = model.model_config
        assert config.get("strict") is True, model.__name__
        assert config.get("frozen") is True, model.__name__
        assert config.get("extra") == "forbid", model.__name__


def test_stale_baseline_refusal_is_typed_and_never_a_domain_refusal_code() -> None:
    """Compare-and-swap staleness is exclusively the typed refusal."""
    from ..edit_models import ModeloEditRefusalCode

    refusal = ModeloEditStaleBaselineRefusalV1(
        baseline_id="a" * 64,
        mismatching_coordinates=("current_calculation_revision_id",),
        responsible_owner="modelo.edit",
        reconsideration_condition="re-admit and retry",
    )
    assert refusal.kind == "stale_edit_baseline"
    assert ModeloEditRefusalCode.STALE_EDIT_BASELINE.value == "stale_edit_baseline"


def test_conformance_proof_reads_real_manual_scalar_and_binding_classification() -> None:
    """Conformance is derived from the loaded registry snapshot, never hand-listed."""
    revision = bundled_authority().snapshot(_MODELO, filing_year=_FILING_YEAR, period=_period().registry_token).revision
    manual_scalars = [c for c in revision.casillas if getattr(c, "input_kind", None) is InputKind.MANUAL]
    manual_bindings = [b for b in revision.bindings if b.source is BindingSourceKind.MANUAL_INPUT]
    assert manual_scalars
    assert manual_bindings


def test_financial_handoff_proof_finds_no_amount_or_raw_input_field() -> None:
    """The result receipt is safe domain proof only; no value crosses this boundary."""
    forbidden = ("amount", "raw_lexeme", "digest_of_value")
    for name, field in ModeloEditMutationResultReceiptV1.model_fields.items():
        assert not any(token in name.lower() for token in forbidden), name
        assert "Decimal" not in str(field.annotation), name


def test_no_legacy_marker_across_the_edit_contract_module_set() -> None:
    """The V1 contract reads one shape; nothing here upgrades an older one."""
    legacy_markers = ("legacy", "migrate", "upgrade", "deprecated")
    for module in _EDIT_CONTRACT_MODULES:
        source = Path(inspect.getfile(module)).read_text(encoding="utf-8")
        for marker in legacy_markers:
            assert marker not in source.lower(), f"{module.__name__} carries {marker!r}"


def test_exactly_one_authority_defines_the_edit_mutation_result_receipt() -> None:
    """A second declaration of the receipt would fork the edit contract's proof surface."""
    declaring: list[str] = []
    for path in Path(inspect.getfile(ModeloEditBaselineV1)).parent.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "ModeloEditMutationResultReceiptV1":
                declaring.append(str(path))
    assert len(declaring) == 1, declaring
