"""Bounded agent modelo reads keep exact values and closed readiness causes."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest

from cadrumo.application.ledger.preflight import LedgerPreflightIssue, LedgerPreflightIssueReason
from cadrumo.application.modelo import mcp_query_operation as subject
from cadrumo.application.modelo.mcp_binding_validation import validate_typed_binding_value
from cadrumo.application.modelo.mcp_query_contracts import (
    ModeloBindingsResolveTypedProjection,
    ModeloBindingValueContractUnsupportedError,
    ModeloBindingValueInvalidError,
    ModeloReadinessSummaryProjection,
)
from cadrumo.application.modelo.mcp_query_operation import (
    build_modelo_bindings_resolve_typed_definition,
    build_modelo_bindings_resolve_typed_registration,
    build_modelo_readiness_summary_definition,
    build_modelo_readiness_summary_registration,
)
from cadrumo.application.modelo.query_read_operation import ModeloQueryReadPorts, ModeloReadinessOperationRequest
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.application.state_projection import (
    ModeloProfileRefusalCause,
    ProjectionModeloReadiness,
)
from cadrumo.core.aggregation import BindingTypedEnumKind
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.binding_value_contract import (
    BindingDataType,
    BindingValueChannel,
    BindingValueContract,
)
from cadrumo.domain.calculations.registry.schema_base import CasillaDataType
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaConstraints

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("11111111-1111-4111-8111-111111111111")


def _unused_ports(*, bucket_id: str) -> ModeloQueryReadPorts:
    raise AssertionError(f"unexpected ports construction for {bucket_id}")


def test_mcp_query_schemas_bind_and_human_projections_stay_separate() -> None:
    typed = build_modelo_bindings_resolve_typed_definition()
    readiness = build_modelo_readiness_summary_definition(_unused_ports)
    assert build_modelo_bindings_resolve_typed_registration(typed).contract.definition_id == typed.definition_id
    assert build_modelo_readiness_summary_registration(readiness).contract.definition_id == readiness.definition_id
    assert typed.result_type is ModeloBindingsResolveTypedProjection
    assert readiness.result_type is ModeloReadinessSummaryProjection
    assert typed.capabilities.sensitive_input.value == "secure_reference"


def test_typed_binding_value_preserves_accepted_exact_input_and_rejects_invalid_without_echo() -> None:
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("303", filing_year=2025, period="1T")
        binding = next(row for row in snapshot.revision.bindings if row.value.channel is BindingValueChannel.DECIMAL)
        value = validate_typed_binding_value(
            binding, "0.75", snapshot, operation=operation, effective_date=date(2025, 3, 31)
        )
        assert value.binding_id == binding.id
        assert value.value == "0.75"
        assert value.channel is BindingValueChannel.DECIMAL
        rejected = "not-a-decimal-secret-value"
        with pytest.raises(ModeloBindingValueInvalidError) as raised:
            validate_typed_binding_value(
                binding, rejected, snapshot, operation=operation, effective_date=date(2025, 3, 31)
            )
        assert rejected not in str(raised.value)


def test_missing_official_text_grammar_refuses_without_treating_arbitrary_text_as_typed() -> None:
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("303", filing_year=2025, period="1T")
        binding = snapshot.revision.bindings[0].model_copy(
            update={
                "id": "synthetic-unbound-text",
                "value": BindingValueContract(data_type=BindingDataType.TEXT, channel=BindingValueChannel.TEXT),
            }
        )
        rejected = "free-form-private-value"
        with pytest.raises(ModeloBindingValueContractUnsupportedError) as raised:
            validate_typed_binding_value(
                binding, rejected, snapshot, operation=operation, effective_date=date(2025, 3, 31)
            )
        assert rejected not in str(raised.value)


def test_declared_enum_rejects_outside_member_even_when_target_text_pattern_accepts_it() -> None:
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("303", filing_year=2025, period="1T")
        binding_id = "synthetic-censo-event"
        binding = snapshot.revision.bindings[0].model_copy(
            update={
                "id": binding_id,
                "value": BindingValueContract(
                    data_type=BindingDataType.ENUM,
                    channel=BindingValueChannel.ENUM,
                    typed_enum=BindingTypedEnumKind.CENSO_EVENT_KIND,
                ),
            }
        )
        target = snapshot.revision.casillas[0].model_copy(
            update={
                "binding": binding_id,
                "data_type": CasillaDataType.TEXT,
                "constraints": CasillaConstraints.model_construct(pattern="^[a-z]+$", legal_refs=(), source_refs=()),
            }
        )
        revision = snapshot.revision.model_copy(update={"casillas": (target,)})
        selected = snapshot.model_copy(update={"revision": revision})
        accepted = validate_typed_binding_value(
            binding, "alta", selected, operation=operation, effective_date=date(2025, 3, 31)
        )
        assert accepted.value == "alta"
        rejected = "rogue"
        assert target.constraints is not None
        assert target.constraints.violates_text(rejected) is None
        with pytest.raises(ModeloBindingValueInvalidError):
            validate_typed_binding_value(
                binding, rejected, selected, operation=operation, effective_date=date(2025, 3, 31)
            )


def test_readiness_summary_preserves_axes_and_typed_cause_without_diagnostic_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    period = Period.from_year_and_code(2025, "1T")
    raw = ProjectionModeloReadiness(
        profile_id=str(_PROFILE),
        modelo="303",
        revision_id="2025",
        filing_year=2025,
        period=period,
        profile_ready=False,
        per_operation_requirements_assessed=True,
        profile_refusal="private applicability prose",
        profile_refusal_cause=ModeloProfileRefusalCause.NOT_APPLICABLE,
        registry_ready=True,
        binding_ready=True,
        ledger_preflight_required=True,
        ledger_ready=False,
        ledger_period=period,
        ledger_checked_transaction_count=1,
        ledger_issues=(
            LedgerPreflightIssue(
                transaction_id="a" * 64,
                reason=LedgerPreflightIssueReason.UNSUPPORTED_PERIOD,
                detail="private arbitrary diagnostic",
            ),
        ),
        ready=False,
    )
    monkeypatch.setattr(subject, "read_modelo_readiness", lambda *args, **kwargs: raw)
    request = ModeloReadinessOperationRequest(
        profile_id=_PROFILE,
        modelo="303",
        filing_year=2025,
        period=PublicPeriod.from_period(period),
        language=OutputLanguage.ES,
    )
    with bundled_indexed_authority().operation() as operation:
        summary = subject._readiness_summary(request, _unused_ports, operation)
    assert summary.profile_refusal_cause is ModeloProfileRefusalCause.NOT_APPLICABLE
    assert summary.ledger_checked_transaction_count == 1
    assert summary.ledger_issues[0].reason is LedgerPreflightIssueReason.UNSUPPORTED_PERIOD
    public = summary.model_dump_json()
    assert "private applicability prose" not in public
    assert "private arbitrary diagnostic" not in public
    assert "detail" not in public
