"""Strict public snapshots preserve canonical financial and evidence semantics."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.application.modelo.filing_projection import ModeloFilingRecordSnapshot
from cadrumo.application.modelo.verification_preconditions import (
    ModeloVerificationResult,
    build_verification_precondition_failure,
    project_verification_findings,
)
from cadrumo.application.modelo.verification_projection import ModeloVerificationSnapshot
from cadrumo.application.operations.registry import OperationSchemaBindingV1
from cadrumo.core.operator_action_enums import ActionEvidenceProvenance
from cadrumo.domain.modelos.tests.filing_record_test_support import (
    build_iva_settlement_snapshot_for_test,
    build_modelo_filing_record_for_test,
)
from cadrumo.domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingSeverity

from .test_verification_preconditions import _blocked_report, _finding

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_filing_snapshot_preserves_settlement_amounts_evidence_and_time() -> None:
    record = build_modelo_filing_record_for_test(settlement=build_iva_settlement_snapshot_for_test())
    snapshot = ModeloFilingRecordSnapshot.from_record(record)
    binding = OperationSchemaBindingV1.bind(schema_id="test.filing", schema_version=1, model_type=type(snapshot))
    assert binding.identity.schema_id == "test.filing"
    restored = ModeloFilingRecordSnapshot.model_validate_json(snapshot.model_dump_json()).to_record()
    assert restored == record
    assert restored.settlement is not None and record.settlement is not None
    assert restored.settlement.declared_liability.as_tuple() == record.settlement.declared_liability.as_tuple()
    tampered = json.loads(snapshot.model_dump_json())
    tampered["settlement"]["credit_snapshot"]["remaining_amount"] = "39.00"
    with pytest.raises(ValidationError):
        ModeloFilingRecordSnapshot.model_validate_json(json.dumps(tampered))


def test_report_snapshot_preserves_decimal_string_integer_and_boolean_facts() -> None:
    base = _finding(severity=ModeloVerificationFindingSeverity.BLOCKING)
    facts = {"amount": Decimal("1.00"), "token": "1.00", "count": 1, "allowed": True}
    finding = ModeloVerificationFinding.model_validate(base.model_dump(mode="python") | {"message_facts": facts})
    report = _blocked_report((finding,))
    failure = build_verification_precondition_failure(
        calculation_revision_id=report.calculation_revision_id,
        work_unit_id="b" * 64,
        condition_id="modelo.work.verify.registry_snapshot.available",
        scenario_id="modelo.work.verify.registry_snapshot.unavailable",
        evidence_id="modelo.work.verify.registry_snapshot",
        evidence_values=facts,
        provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
    )
    outcome = ModeloVerificationResult(
        report=report,
        published=True,
        finding_preconditions=project_verification_findings((finding,), failures_by_finding_id={id(finding): failure}),
    )
    snapshot = ModeloVerificationSnapshot.from_verification(outcome)
    binding = OperationSchemaBindingV1.bind(schema_id="test.verification", schema_version=1, model_type=type(snapshot))
    assert binding.identity.schema_id == "test.verification"
    restored = ModeloVerificationSnapshot.model_validate_json(snapshot.model_dump_json()).to_verification()
    assert restored == outcome
    assert type(restored.report.findings[0].message_facts["count"]) is int
    assert type(restored.report.findings[0].message_facts["allowed"]) is bool
    assert type(restored.report.findings[0].message_facts["token"]) is str
    amount = restored.report.findings[0].message_facts["amount"]
    assert isinstance(amount, Decimal) and amount.as_tuple() == Decimal("1.00").as_tuple()
    tampered = json.loads(snapshot.model_dump_json())
    tampered["report"]["findings"][0]["message_facts"].append(tampered["report"]["findings"][0]["message_facts"][0])
    with pytest.raises(ValidationError, match="duplicate"):
        ModeloVerificationSnapshot.model_validate_json(json.dumps(tampered))
