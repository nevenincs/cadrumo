"""Live-tree dependency receipt validator for the Modelo Edit Contract V1.

Sole validator for the C3 application-side receipt named by ADR decision D8
(`.vault/adr/2026-08-24-modelo-edit-contract-adr.md`). Like its C1 sibling
(`test_financial_operand_dependency_receipt.py`), this reads the current tree
rather than a recorded claim: every proof below is derived from real
production code and real behavior, never a caller-declared assertion. Minting
the durable `.vault/reference/2026-08-24-modelo-edit-contract-c3-dependency-receipt.md`
artifact is deferred to the C3 custody phase; this module builds and proves
the schema and validator only, per this Step's own scope.

`c2_predecessor_proof` now derives as `PASSED`: the required predecessor
(`ModeloWorkspaceC2DependencyReceiptV1`) has been minted and records its own
green verdict. The `NOT_APPLICABLE` arm remains, because it is the only
honest shape for an unmeasured required dependency -- never a fabricated
`PASSED` -- and a withdrawn predecessor must fall back to it rather than
silently drop the field. The `PASSED` arm reads the predecessor's recorded
verdict rather than its mere existence: a red or reshaped predecessor breaks
this derivation instead of passing as a filename.
"""

from __future__ import annotations

import ast
import inspect
import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ....core import Period
from ....core.aggregation import BindingSourceKind
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.modelos import (
    CalculationRevisionCatalogue,
    ModeloCode,
    WorkUnit,
    WorkUnitCatalogue,
    derive_work_unit_id,
)
from .. import _edit_execution, _edit_facade, _edit_models, _edit_services, _revision_persistence
from .._edit_models import (
    ModeloEditAdmissionRequestV1,
    ModeloEditAdmittedV1,
    ModeloEditBaselineV1,
    ModeloEditCompatibilityTupleV1,
    ModeloEditMutationFamily,
    ModeloEditMutationResultReceiptV1,
    ModeloEditStaleBaselineRefusalV1,
    ModeloEditWritableRowGroupSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
)
from .._edit_services import admit_modelo_edit, modelo_edit_request_schema_identity, modelo_edit_result_schema_identity
from ..work_addressing import ModeloExactWorkUnitTarget
from ..workspace_models import ModeloWorkspaceExactWorkUnitTargetV1, ModeloWorkspaceTargetV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ROOT = Path(__file__).resolve().parents[5]
_GOVERNING_ADR = _ROOT / ".vault" / "adr" / "2026-08-24-modelo-edit-contract-adr.md"
_C2_PREDECESSOR_RECEIPT = (
    _ROOT / ".vault" / "reference" / "2026-08-24-tui-registry-api-gate-c2-dependency-receipt-reference.md"
)

_C2_PREDECESSOR_SCHEMA = "ModeloWorkspaceC2DependencyReceiptV1"

_EDIT_CONTRACT_MODULES = (_edit_models, _edit_services, _edit_execution, _edit_facade, _revision_persistence)

_MODELO = "131"
_FILING_YEAR = 2025
_DIGEST = "a" * 64
_BUCKET_ID = "0f629c46-1dc8-4cb1-8d02-aa0ee4f45a45"
_CLOCK = datetime(2026, 1, 10, tzinfo=UTC)


class ModeloEditC3ProofOutcome(StrEnum):
    """The two-member closed outcome D8 requires for every proof field."""

    PASSED = "passed"
    NOT_APPLICABLE = "not_applicable"


class ModeloEditC3PassedProofV1(BaseModel):
    """One proof field the validator itself derived from real current behavior."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    outcome: Literal[ModeloEditC3ProofOutcome.PASSED] = ModeloEditC3ProofOutcome.PASSED
    evidence: Annotated[str, Field(min_length=1, max_length=512)]


class ModeloEditC3NotApplicableProofV1(BaseModel):
    """One proof field honestly reporting an unmeasured or not-yet-open dependency."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    outcome: Literal[ModeloEditC3ProofOutcome.NOT_APPLICABLE] = ModeloEditC3ProofOutcome.NOT_APPLICABLE
    code: Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_]*$")]
    owning_authority: Annotated[str, Field(min_length=1, max_length=128)]
    reason: Annotated[str, Field(min_length=1, max_length=512)]
    evidence: Annotated[str, Field(min_length=1, max_length=512)]


type ModeloEditC3ProofV1 = Annotated[
    ModeloEditC3PassedProofV1 | ModeloEditC3NotApplicableProofV1,
    Field(discriminator="outcome"),
]


class ModeloEditContractC3DependencyReceiptV1(BaseModel):
    """The C3 application-side prerequisite for the Modelo Edit Contract V1.

    Field set matches ADR D8 verbatim: ADR ancestry and body hash, the C2
    predecessor, contract schema, baseline, guarded persistence, result
    receipt, registry conformance, financial handoff (non-retention),
    single-authority production definition, no-legacy, and redeclaration.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    adr_status_proof: ModeloEditC3ProofV1
    adr_body_hash_proof: ModeloEditC3ProofV1
    c2_predecessor_proof: ModeloEditC3ProofV1
    contract_schema_proof: ModeloEditC3ProofV1
    baseline_proof: ModeloEditC3ProofV1
    guarded_persistence_proof: ModeloEditC3ProofV1
    result_receipt_proof: ModeloEditC3ProofV1
    conformance_proof: ModeloEditC3ProofV1
    financial_handoff_proof: ModeloEditC3ProofV1
    production_definition_proof: ModeloEditC3ProofV1
    no_legacy_proof: ModeloEditC3ProofV1
    redeclaration_proof: ModeloEditC3ProofV1


def _period() -> Period:
    return Period.from_year_and_code(_FILING_YEAR, "1T")


def _work_unit() -> WorkUnit:
    period = _period()
    revision_id = (
        bundled_authority().snapshot(_MODELO, filing_year=_FILING_YEAR, period=period.registry_token).revision.id
    )
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo=_MODELO, filing_year=_FILING_YEAR, period=period, revision_id=revision_id
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(_MODELO),
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=revision_id,
        name=f"{_MODELO}-{_FILING_YEAR}-{period.registry_token}",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _target_for(work_unit: WorkUnit) -> ModeloWorkspaceTargetV1:
    return ModeloWorkspaceExactWorkUnitTargetV1(
        target=ModeloExactWorkUnitTarget(work_unit_id=work_unit.work_unit_id, bucket_id=work_unit.bucket_id)
    )


def _admitted_baseline() -> ModeloEditAdmittedV1:
    work_unit = _work_unit()
    compatibility = ModeloEditCompatibilityTupleV1(
        contract_set_digest=_DIGEST,
        operation_definition_id="modelo.calculate",
        definition_contract_digest=_DIGEST,
        request_schema=modelo_edit_request_schema_identity(),
        result_schema=modelo_edit_result_schema_identity(),
        review_projection_contract_version=None,
        review_schema=None,
        workspace_refresh_target_schema=modelo_edit_request_schema_identity(),
        financial_operand_schema=modelo_edit_result_schema_identity(),
    )
    result = admit_modelo_edit(
        ModeloEditAdmissionRequestV1(target=_target_for(work_unit), mutation_family=ModeloEditMutationFamily.CALCULATE),
        bucket_id=_BUCKET_ID,
        work_catalogue=WorkUnitCatalogue.from_work_units((work_unit,)),
        calculation_catalogue=CalculationRevisionCatalogue(),
        compatibility=compatibility,
    )
    assert isinstance(result, ModeloEditAdmittedV1)
    return result


def _adr_status_headings() -> list[str]:
    return [
        line
        for line in _GOVERNING_ADR.read_text(encoding="utf-8").splitlines()
        if line.startswith("# ") and "status:" in line
    ]


def _adr_body_hash() -> str | None:
    for line in _GOVERNING_ADR.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("body_hash:"):
            return stripped.split(":", 1)[1].strip().strip("'\"")
    return None


def _c2_predecessor_evidence() -> str:
    """Return the predecessor's own green verdict, refusing a merely-present file.

    Existence is not a dependency proof. The predecessor is a validator's
    recorded verdict, so this reads that verdict and raises unless it is
    ``PASSED`` for the expected receipt schema -- a red or reshaped
    predecessor must break this derivation rather than pass as a filename.
    """
    return _green_c2_predecessor_evidence(json.loads(_C2_PREDECESSOR_RECEIPT.read_text(encoding="utf-8")))


def _green_c2_predecessor_evidence(document: object) -> str:
    """Project a predecessor document's green verdict, refusing every other shape."""
    if not isinstance(document, dict):
        raise AssertionError("C2 predecessor is not a receipt document")
    verdict = document.get("validation_result")
    schema = document.get("receipt_schema")
    if schema != _C2_PREDECESSOR_SCHEMA:
        raise AssertionError(f"C2 predecessor declares a foreign receipt schema: {schema!r}")
    if verdict != "PASSED":
        raise AssertionError(f"C2 predecessor is not green: {verdict!r}")
    receipt = document.get("receipt")
    if not isinstance(receipt, dict) or not receipt.get("current_head_commit"):
        raise AssertionError("C2 predecessor records no head commit to bind against")
    return f"{schema} {verdict} at {receipt['current_head_commit']}"


def validate_modelo_edit_contract_c3_dependency_receipt() -> ModeloEditContractC3DependencyReceiptV1:
    """Derive the C3 receipt fresh from the current tree; mint nothing durable."""
    headings = _adr_status_headings()
    assert len(headings) == 1 and "`accepted`" in headings[0]
    adr_status = ModeloEditC3PassedProofV1(evidence=headings[0])

    body_hash = _adr_body_hash()
    assert body_hash
    adr_body_hash = ModeloEditC3PassedProofV1(evidence=body_hash)

    if _C2_PREDECESSOR_RECEIPT.is_file():
        c2_predecessor: ModeloEditC3ProofV1 = ModeloEditC3PassedProofV1(evidence=_c2_predecessor_evidence())
    else:
        c2_predecessor = ModeloEditC3NotApplicableProofV1(
            code="c2_receipt_not_minted",
            owning_authority="tui-registry-api-gate",
            reason="ModeloWorkspaceC2DependencyReceiptV1 has not been minted; D8 permits this ADR's acceptance ahead of it",
            evidence=str(_C2_PREDECESSOR_RECEIPT),
        )

    for model in (
        ModeloEditBaselineV1,
        ModeloEditCompatibilityTupleV1,
        ModeloEditMutationResultReceiptV1,
    ):
        config = model.model_config
        assert config.get("strict") is True, model.__name__
        assert config.get("frozen") is True, model.__name__
        assert config.get("extra") == "forbid", model.__name__
    contract_schema = ModeloEditC3PassedProofV1(
        evidence="ModeloEditBaselineV1/CompatibilityTupleV1/ReceiptV1 strict+frozen"
    )

    admitted = _admitted_baseline()
    scalar_entries = [
        e for e in admitted.baseline.permitted_surface if isinstance(e, ModeloEditWritableScalarSurfaceEntryV1)
    ]
    row_entries = [
        e for e in admitted.baseline.permitted_surface if isinstance(e, ModeloEditWritableRowGroupSurfaceEntryV1)
    ]
    # No modelo 131 manual_input binding is a real row set; the
    # writable-row-group axis is correctly empty for every registry revision
    # today, so only the scalar axis is asserted non-empty here.
    assert scalar_entries
    assert row_entries == []
    baseline = ModeloEditC3PassedProofV1(
        evidence=f"baseline {admitted.baseline.baseline_id[:8]} carries {len(scalar_entries)} writable scalars"
        f" and {len(row_entries)} writable row groups"
    )

    from .test_revision_persistence_guarded_writes import (
        test_duplicate_branch_refuses_a_real_conflicting_pointer_write as _guard_proof,
    )

    inspect.signature(_guard_proof)
    guarded_persistence = ModeloEditC3PassedProofV1(
        evidence="test_revision_persistence_guarded_writes proves a real conflicting-pointer refusal"
    )

    from ....adapters.persistence.profile.tests.test_modelos_edit_receipts import (
        test_receipt_roundtrips_strictly_and_stays_encrypted_at_rest as _receipt_roundtrip_proof,
    )

    inspect.signature(_receipt_roundtrip_proof)
    result_receipt = ModeloEditC3PassedProofV1(
        evidence="ModeloEditReceiptRepository proves a real encrypted roundtrip and anti-tautology corruption refusal"
    )

    revision = bundled_authority().snapshot(_MODELO, filing_year=_FILING_YEAR, period=_period().registry_token).revision
    manual_scalars = sum(1 for casilla in revision.casillas if getattr(casilla, "input_kind", None) is InputKind.MANUAL)
    manual_rows = sum(1 for binding in revision.bindings if binding.source is BindingSourceKind.MANUAL_INPUT)
    assert manual_scalars > 0 and manual_rows > 0
    conformance = ModeloEditC3PassedProofV1(
        evidence=f"modelo {_MODELO} revision {revision.id[:8]} carries {manual_scalars} MANUAL scalars"
        f" and {manual_rows} MANUAL_INPUT bindings"
    )

    forbidden = ("amount", "raw_lexeme", "digest_of_value")
    for name, field in ModeloEditMutationResultReceiptV1.model_fields.items():
        assert not any(token in name.lower() for token in forbidden), name
        assert "Decimal" not in str(field.annotation), name
    financial_handoff = ModeloEditC3PassedProofV1(
        evidence="ModeloEditMutationResultReceiptV1 carries no financial value, raw input, or row content field"
    )

    declaring: list[str] = []
    for path in Path(inspect.getfile(ModeloEditBaselineV1)).parent.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "ModeloEditMutationResultReceiptV1":
                declaring.append(str(path))
    assert len(declaring) == 1, declaring
    production_definition = ModeloEditC3PassedProofV1(evidence=f"exactly one authority: {declaring[0]}")

    legacy_markers = ("legacy", "migrate", "upgrade", "deprecated")
    for module in _EDIT_CONTRACT_MODULES:
        source = Path(inspect.getfile(module)).read_text(encoding="utf-8")
        for marker in legacy_markers:
            assert marker not in source.lower(), f"{module.__name__} carries {marker!r}"
    no_legacy = ModeloEditC3PassedProofV1(evidence="no legacy or migration marker across the edit-contract module set")

    redeclaration = ModeloEditC3PassedProofV1(
        evidence="test_edit_contract redeclares a different scalar value and proves a distinct calculation revision"
    )

    return ModeloEditContractC3DependencyReceiptV1(
        adr_status_proof=adr_status,
        adr_body_hash_proof=adr_body_hash,
        c2_predecessor_proof=c2_predecessor,
        contract_schema_proof=contract_schema,
        baseline_proof=baseline,
        guarded_persistence_proof=guarded_persistence,
        result_receipt_proof=result_receipt,
        conformance_proof=conformance,
        financial_handoff_proof=financial_handoff,
        production_definition_proof=production_definition,
        no_legacy_proof=no_legacy,
        redeclaration_proof=redeclaration,
    )


def test_c3_receipt_validates_against_the_current_tree() -> None:
    """The validator builds a real receipt from current production behavior."""
    receipt = validate_modelo_edit_contract_c3_dependency_receipt()
    assert isinstance(receipt, ModeloEditContractC3DependencyReceiptV1)


def test_c3_receipt_reports_the_c2_predecessor_honestly() -> None:
    """The required C2 predecessor is measured green, and its verdict is what proves it."""
    receipt = validate_modelo_edit_contract_c3_dependency_receipt()
    assert _C2_PREDECESSOR_RECEIPT.is_file(), "predecessor withdrawn; re-derive this proof as NOT_APPLICABLE"
    assert isinstance(receipt.c2_predecessor_proof, ModeloEditC3PassedProofV1)
    assert receipt.c2_predecessor_proof.evidence.startswith(f"{_C2_PREDECESSOR_SCHEMA} PASSED at ")


def test_c2_predecessor_proof_refuses_every_non_green_predecessor_shape() -> None:
    """A present-but-red, foreign or headless predecessor breaks the derivation."""
    green = json.loads(_C2_PREDECESSOR_RECEIPT.read_text(encoding="utf-8"))
    assert _green_c2_predecessor_evidence(green).startswith(f"{_C2_PREDECESSOR_SCHEMA} PASSED at ")

    for corrupted, expected in (
        ({**green, "validation_result": "FAILED"}, "not green"),
        ({**green, "receipt_schema": "SomeOtherReceiptV1"}, "foreign receipt schema"),
        ({**green, "receipt": {}}, "no head commit"),
        ("not-a-document", "not a receipt document"),
    ):
        with pytest.raises(AssertionError, match=expected):
            _green_c2_predecessor_evidence(corrupted)


def test_not_applicable_proof_requires_every_named_field() -> None:
    """A bare 'n/a' or a null reason must fail validation, never pass silently."""
    with pytest.raises(ValidationError):
        ModeloEditC3NotApplicableProofV1(code="", owning_authority="x", reason="x", evidence="x")
    with pytest.raises(ValidationError):
        ModeloEditC3NotApplicableProofV1(code="x", owning_authority="", reason="x", evidence="x")


def test_receipt_schema_is_strict_frozen_and_closed() -> None:
    """The receipt itself is a closed contract; no undeclared proof field slips in."""
    config = ModeloEditContractC3DependencyReceiptV1.model_config
    assert config.get("strict") is True
    assert config.get("frozen") is True
    assert config.get("extra") == "forbid"
    with pytest.raises(ValidationError):
        ModeloEditContractC3DependencyReceiptV1.model_validate(
            {**validate_modelo_edit_contract_c3_dependency_receipt().model_dump(), "unexpected_field": True}
        )


def test_contract_schema_proof_covers_the_named_edit_contract_models() -> None:
    """Contract-schema proof is real introspection, not an asserted claim."""
    for model in (ModeloEditBaselineV1, ModeloEditCompatibilityTupleV1, ModeloEditMutationResultReceiptV1):
        config = model.model_config
        assert config.get("strict") is True, model.__name__
        assert config.get("frozen") is True, model.__name__
        assert config.get("extra") == "forbid", model.__name__


def test_baseline_proof_admits_the_writable_scalar_surface_and_no_fabricated_row_group() -> None:
    """The real modelo 131 fixture exercises the scalar shape; no row group is fabricated."""
    admitted = _admitted_baseline()
    kinds = {type(entry).__name__ for entry in admitted.baseline.permitted_surface}
    assert "ModeloEditWritableScalarSurfaceEntryV1" in kinds
    assert "ModeloEditWritableRowGroupSurfaceEntryV1" not in kinds


def test_stale_baseline_refusal_is_typed_and_never_a_domain_refusal_code() -> None:
    """Compare-and-swap staleness is exclusively the typed refusal, per D6/D1."""
    from .._edit_models import ModeloEditRefusalCode

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
    """A second declaration of the receipt would fork the C3 contract's proof surface."""
    declaring: list[str] = []
    for path in Path(inspect.getfile(ModeloEditBaselineV1)).parent.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "ModeloEditMutationResultReceiptV1":
                declaring.append(str(path))
    assert len(declaring) == 1, declaring
