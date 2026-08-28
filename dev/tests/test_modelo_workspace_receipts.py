"""Prove every Modelo Workspace exit-receipt validator genuinely rejects.

This is the anti-vacuity proof for ``dev/quality/modelo_workspace_receipts.py``:
each test builds a REAL pydantic receipt (or attempts to and catches the real
``ValidationError``) and runs it through the real
``validate_modelo_workspace_c{n}_exit_receipt`` function, never a stub or a
hand-rolled double. Every test starts from one known-good fixture per cohort
and mutates exactly one fact, so a passing test proves the mutated fact is
what triggered the rejection rather than something else being broken.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from pydantic import ValidationError

from ..quality.modelo_workspace_receipts import (
    COHORT_CONSUMED_AXES,
    REQUIRED_CHECKLIST_ITEMS,
    REQUIRED_PREDECESSOR_SCHEMA_NAMES,
    AcceptedGoverningRecordV1,
    ModeloWorkspaceC1ExitReceiptV1,
    ModeloWorkspaceC2ExitReceiptV1,
    ModeloWorkspaceCohort,
    ModeloWorkspaceCompatibilityAxis,
    ModeloWorkspaceReceiptProofKind,
    ModeloWorkspaceReceiptProofV1,
    PredecessorReceiptDigestV1,
    validate_modelo_workspace_c1_exit_receipt,
    validate_modelo_workspace_c2_exit_receipt,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_HEAD_COMMIT = "a" * 40
_COMPANION_STEM = "2026-08-24-tui-modelo-workspace-interface-adr"


def _passed(identity: str) -> ModeloWorkspaceReceiptProofV1:
    return ModeloWorkspaceReceiptProofV1(
        kind=ModeloWorkspaceReceiptProofKind.PASSED,
        evidence_identity=identity,
        evidence_digest=f"sha256:{identity}",
    )


def _not_applicable(code: str) -> ModeloWorkspaceReceiptProofV1:
    return ModeloWorkspaceReceiptProofV1(
        kind=ModeloWorkspaceReceiptProofKind.NOT_APPLICABLE,
        not_applicable_code=code,
        owning_authority="tui-architecture",
        reason=f"{code} is out of scope for this cohort",
        evidence_reference="the accepted Modelo Workspace interface decision's C1-C4 cohort disposition framing",
        reopening_condition="a future accepted amendment enrolls this axis",
    )


def _compatibility(
    cohort: ModeloWorkspaceCohort,
) -> Mapping[ModeloWorkspaceCompatibilityAxis, ModeloWorkspaceReceiptProofV1]:
    consumed = COHORT_CONSUMED_AXES[cohort]
    return {
        axis: _passed(f"{cohort}-{axis}") if axis in consumed else _not_applicable(f"{cohort}-{axis}-unconsumed")
        for axis in ModeloWorkspaceCompatibilityAxis
    }


def _checklist(cohort: ModeloWorkspaceCohort) -> Mapping[str, ModeloWorkspaceReceiptProofV1]:
    return {item: _passed(f"{cohort}-{item}") for item in REQUIRED_CHECKLIST_ITEMS[cohort]}


def _governing_records(*stems: str) -> tuple[AcceptedGoverningRecordV1, ...]:
    return tuple(
        AcceptedGoverningRecordV1(
            stem=stem,
            status="accepted",
            accepting_commit=_HEAD_COMMIT,
            body_hash=f"sha256:{stem}",
        )
        for stem in stems
    )


def _predecessor_digests(cohort: ModeloWorkspaceCohort) -> tuple[PredecessorReceiptDigestV1, ...]:
    return tuple(
        PredecessorReceiptDigestV1(schema_name=name, receipt_stem=f"receipt-{name}", digest=f"sha256:{name}")
        for name in REQUIRED_PREDECESSOR_SCHEMA_NAMES[cohort]
    )


def _c1_receipt(**overrides: object) -> ModeloWorkspaceC1ExitReceiptV1:
    fields: dict[str, object] = {
        "schema_version": 1,
        "current_head_commit": _HEAD_COMMIT,
        "governing_records": _governing_records(_COMPANION_STEM),
        "predecessor_digests": _predecessor_digests(ModeloWorkspaceCohort.C1),
        "compatibility": _compatibility(ModeloWorkspaceCohort.C1),
        "checklist": _checklist(ModeloWorkspaceCohort.C1),
    }
    fields.update(overrides)
    return ModeloWorkspaceC1ExitReceiptV1.model_validate(fields)


def _c2_receipt(**overrides: object) -> ModeloWorkspaceC2ExitReceiptV1:
    fields: dict[str, object] = {
        "schema_version": 1,
        "current_head_commit": _HEAD_COMMIT,
        "governing_records": _governing_records(_COMPANION_STEM),
        "predecessor_digests": _predecessor_digests(ModeloWorkspaceCohort.C2),
        "compatibility": _compatibility(ModeloWorkspaceCohort.C2),
        "checklist": _checklist(ModeloWorkspaceCohort.C2),
    }
    fields.update(overrides)
    return ModeloWorkspaceC2ExitReceiptV1.model_validate(fields)


def test_c1_receipt_constructs_and_validates_clean() -> None:
    receipt = _c1_receipt()
    assert (
        validate_modelo_workspace_c1_exit_receipt(
            receipt,
            action_denominator_validator=lambda: [],
        )
        == []
    )


def test_c1_rejects_missing_companion_governing_record() -> None:
    with pytest.raises(ValidationError, match="companion ADR stem"):
        _c1_receipt(governing_records=_governing_records("some-other-adr"))


def test_c1_rejects_non_accepted_authority_at_construction() -> None:
    with pytest.raises(ValidationError):
        ModeloWorkspaceC1ExitReceiptV1.model_validate(
            {
                "schema_version": 1,
                "current_head_commit": _HEAD_COMMIT,
                "governing_records": (
                    {
                        "stem": _COMPANION_STEM,
                        "status": "proposed",
                        "accepting_commit": _HEAD_COMMIT,
                        "body_hash": f"sha256:{_COMPANION_STEM}",
                    },
                ),
                "predecessor_digests": (),
                "compatibility": _compatibility(ModeloWorkspaceCohort.C1),
                "checklist": _checklist(ModeloWorkspaceCohort.C1),
            },
        )


def test_c1_rejects_unsupported_compatibility_axis_marked_passed() -> None:
    compatibility = dict(_compatibility(ModeloWorkspaceCohort.C1))
    compatibility[ModeloWorkspaceCompatibilityAxis.FINANCIAL_PROTOCOL] = _passed("smuggled")
    with pytest.raises(ValidationError, match="not consumed"):
        _c1_receipt(compatibility=compatibility)


def test_c1_rejects_consumed_axis_marked_not_applicable() -> None:
    compatibility = dict(_compatibility(ModeloWorkspaceCohort.C1))
    compatibility[ModeloWorkspaceCompatibilityAxis.REVIEW] = _not_applicable("dodging-review")
    with pytest.raises(ValidationError, match="cannot be NOT_APPLICABLE"):
        _c1_receipt(compatibility=compatibility)


def test_c1_rejects_placeholder_not_applicable_reason() -> None:
    with pytest.raises(ValidationError):
        ModeloWorkspaceReceiptProofV1(
            kind=ModeloWorkspaceReceiptProofKind.NOT_APPLICABLE,
            not_applicable_code="x",
            owning_authority="y",
            reason="n/a",
            evidence_reference="z",
            reopening_condition="w",
        )


def test_c1_rejects_checklist_item_marked_not_applicable() -> None:
    checklist = dict(_checklist(ModeloWorkspaceCohort.C1))
    checklist["no_legacy_production_import"] = _not_applicable("skip-legacy-check")
    with pytest.raises(ValidationError, match="can never be NOT_APPLICABLE"):
        _c1_receipt(checklist=checklist)


def test_c1_has_no_predecessor_digests() -> None:
    with pytest.raises(ValidationError):
        _c1_receipt(
            predecessor_digests=(
                PredecessorReceiptDigestV1(
                    schema_name="ShouldNotExist",
                    receipt_stem="phantom",
                    digest="sha256:phantom",
                ),
            ),
        )


def test_c2_rejects_availability_before_predecessor_exit_is_green() -> None:
    receipt = _c2_receipt()
    violations = validate_modelo_workspace_c2_exit_receipt(
        receipt,
        predecessor_available={"ModeloWorkspaceC1ExitReceiptV1": True, "ModeloWorkspaceC2DependencyReceiptV1": False},
        action_denominator_validator=lambda: [],
    )
    assert any(
        "ModeloWorkspaceC2DependencyReceiptV1" in message and "not proven green" in message for message in violations
    )


def test_c2_rejects_drifted_predecessor_digest() -> None:
    receipt = _c2_receipt()
    violations = validate_modelo_workspace_c2_exit_receipt(
        receipt,
        predecessor_available={name: True for name in REQUIRED_PREDECESSOR_SCHEMA_NAMES[ModeloWorkspaceCohort.C2]},
        expected_predecessor_digests={"ModeloWorkspaceC1ExitReceiptV1": "sha256:authoritative-different-digest"},
        action_denominator_validator=lambda: [],
    )
    assert any("drifted" in message for message in violations)


def test_c2_rejects_reordered_predecessor_digests() -> None:
    reordered = tuple(reversed(_predecessor_digests(ModeloWorkspaceCohort.C2)))
    with pytest.raises(ValidationError, match="canonical order"):
        _c2_receipt(predecessor_digests=reordered)


def test_c2_rejects_missing_required_predecessor() -> None:
    only_first = _predecessor_digests(ModeloWorkspaceCohort.C2)[:1]
    with pytest.raises(ValidationError, match="must declare exactly"):
        _c2_receipt(predecessor_digests=only_first)


def test_c2_delegated_dependency_validator_failure_propagates() -> None:
    receipt = _c2_receipt()

    def failing_delegate() -> list[str]:
        return ["native-owner surface inventory is missing an enrolled owner"]

    violations = validate_modelo_workspace_c2_exit_receipt(
        receipt,
        predecessor_available={name: True for name in REQUIRED_PREDECESSOR_SCHEMA_NAMES[ModeloWorkspaceCohort.C2]},
        dependency_validators={"ModeloWorkspaceC2DependencyReceiptV1": failing_delegate},
        action_denominator_validator=lambda: [],
    )
    assert any(
        "delegated validation of ModeloWorkspaceC2DependencyReceiptV1 failed" in message for message in violations
    )
    assert any("native-owner surface inventory" in message for message in violations)


def test_c2_rejects_unclassified_action_from_denominator_delegate() -> None:
    receipt = _c2_receipt()

    def rejecting_denominator() -> list[str]:
        return ["route modelo.work.amend_wizard has no classified disposition"]

    violations = validate_modelo_workspace_c2_exit_receipt(
        receipt,
        predecessor_available={name: True for name in REQUIRED_PREDECESSOR_SCHEMA_NAMES[ModeloWorkspaceCohort.C2]},
        action_denominator_validator=rejecting_denominator,
    )
    assert any("action denominator rejected" in message and "amend_wizard" in message for message in violations)


def test_exit_receipt_never_returns_green_without_action_denominator_validator() -> None:
    receipt = _c1_receipt()
    violations = validate_modelo_workspace_c1_exit_receipt(receipt)
    assert any("no action-denominator validator supplied" in message for message in violations)


def test_wrong_cohort_receipt_passed_to_wrong_validator_type_errors() -> None:
    receipt = _c1_receipt()
    with pytest.raises(TypeError, match="expected a c2 exit receipt"):
        validate_modelo_workspace_c2_exit_receipt(receipt)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # reason: passing the wrong cohort type IS the refusal under test
