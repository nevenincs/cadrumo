"""A 303 calculation refused for want of an opening IVA balance names the command that records it.

The refusal settles REFUSED with no effect and no new revision. Its recorded
error detail, which another process reads, carries both the window's step to
the IVA balance and the catalogue action, so neither is left with a refusal that
names no way out. The live command leaf the action resolves to is asserted with
the command-line tests.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.tests.taxpayer_persona_support import seed_modelo_ready_profile
from ...application.modelo.work_lifecycle import create_work_unit
from ...application.operations.error_detail import OperationErrorDetailV1, operation_error_detail_schema
from ...application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.next_step import OperationOpenIvaWalletOpeningBalanceStepV1
from ...application.operator_surface.action_targets import resolve_recorded_precondition_action
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...core.operator_action_enums import ActionArgumentStatus, ActionConditionality
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.tests.cross_period_seeding import resolved_revision
from ..adapter_composition_work_ports import build_work_lifecycle_ports
from .modelo_operation_test_support import MODELO_OPERATION_TEST_ACTOR
from .profile_persistence.iva_wallet_engine_support import TARGET_YEAR
from .registered_executor_case_support import OperationRuntimeCloseWitness, conformance_operation_runtime

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CALCULATE = "modelo.work.calculate"
_PERIOD_CODE = "1T"
_PROFILE_CLOCK = datetime(TARGET_YEAR, 4, 2, 9, 0, tzinfo=UTC)
_OPENING_BALANCE_ACTION_ID = "operator.modelo.iva_wallet.seed"
_OPENING_BALANCE_COMMAND_KEY = "modelo.iva_wallet.seed"


def test_an_unseeded_wallet_refusal_names_the_opening_balance_command_to_every_consumer(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with conformance_operation_runtime(tmp_path / "runtime", cleanup=OperationRuntimeCloseWitness()) as (
        driver,
        registry,
        profile_id,
    ):
        seed_modelo_ready_profile(bucket_id=str(profile_id), at=_PROFILE_CLOCK)
        unit = create_work_unit(
            bucket_id=str(profile_id),
            modelo="303",
            filing_year=TARGET_YEAR,
            period=Period.from_year_and_code(TARGET_YEAR, _PERIOD_CODE),
            revision_id=resolved_revision(modelo="303", filing_year=TARGET_YEAR, period=_PERIOD_CODE).id,
            actor=MODELO_OPERATION_TEST_ACTOR,
            ports=build_work_lifecycle_ports(bucket_id=str(profile_id)),
            operation=operation,
        )
        revisions_before = CalculationRevisionCatalogueRepository().load()
        definition = registry.lookup(_CALCULATE)
        payload = definition.request_type.model_validate(
            {
                "work_unit_id": unit.work_unit_id,
                "actor": MODELO_OPERATION_TEST_ACTOR,
                "ordinary_m303_filing_evidence": {"joint_return_elected": False},
            },
            strict=True,
        )

        _submitted, observed = asyncio.run(
            driver.run(definition_id=_CALCULATE, subject_ref=unit.work_unit_id, payload=payload)
        )
        revisions_after = CalculationRevisionCatalogueRepository().load()
        contract = registry.lookup_public_contract(_CALCULATE)
        resolved = asyncio.run(
            driver.services.result.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=observed.projection.operation_id,
                    terminal_revision=observed.projection.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=operation_error_detail_schema(),
                ),
                OperationErrorDetailV1,
            )
        )

    projection = observed.projection
    assert projection.terminal_condition is OperationTerminalCondition.REFUSED
    assert projection.refusal_ref == "REFUSED_MODELO_IVA_WALLET_RECONCILIATION_BLOCKED"
    assert projection.effect is OperationEffect.NONE
    assert revisions_after == revisions_before

    assert isinstance(resolved, OperationResultProjectionSuccessV1), resolved
    detail = resolved.projection
    assert isinstance(detail, OperationErrorDetailV1)

    # The window's step to the IVA balance's opening-balance entry.
    assert isinstance(detail.next_step, OperationOpenIvaWalletOpeningBalanceStepV1)
    assert detail.next_step.filing_year == TARGET_YEAR
    assert detail.next_step.period_code == _PERIOD_CODE

    # The catalogue action, resolved the way a process without the command graph resolves it.
    verdict = detail.precondition_verdict()
    assert verdict is not None
    assert verdict.failed_condition_id == f"{_CALCULATE}.iva_wallet.ready"
    served = resolve_recorded_precondition_action(verdict)
    assert served.action is not None, "the refusal names no action"
    assert served.action.action_id == _OPENING_BALANCE_ACTION_ID
    assert served.action.target_command_key == _OPENING_BALANCE_COMMAND_KEY
    assert served.conditionality is ActionConditionality.REQUIRES_ARGUMENTS
    assert served.no_recovery_outcome is None
    bound = {item.argument_name: item for item in served.argument_bindings}
    assert bound["filing_year"].value == TARGET_YEAR
    assert bound["period"].value == _PERIOD_CODE
    assert bound["amount"].status is ActionArgumentStatus.MISSING
    assert served.missing_argument_names == ("amount",)
