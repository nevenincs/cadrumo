"""Registered-executor conformance scenarios for the setup status, setup and verify operations.

No scenario may download, install, launch a browser or reach the internet. The
model program's endpoint is closed, and the proxy setting names a scheme the
preflight refuses before connecting, so any network check answers at once as
blocked. The setup scenario names no item, which plans nothing and settles
without a review.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from cadrumo_client.contracts.operation_ids import DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID

from ...application.dependency_contracts import DependencyCheckMode, DependencyState
from ...application.dependency_registry import dependency_item_declarations
from ...application.dependency_setup_operation import (
    DEPENDENCIES_OPERATION_SUBJECT,
    DEPENDENCIES_SETUP_PLAN_PHASE,
    DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID,
    DEPENDENCIES_VERIFY_OPERATION_DEFINITION_ID,
    DependencySetupOutcome,
    DependencySetupRequest,
    DependencySetupResultV1,
    DependencyStatusRequest,
    DependencyStatusResultV1,
    DependencyVerifyRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...tests.env_scope import scoped_env_var
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_EVERY_ITEM = tuple(declaration.item_id for declaration in dependency_item_declarations())


@contextmanager
def _no_network() -> Generator[None]:
    with scoped_env_var("CADRUMO_PROXY_URL", "socks5://conformance.invalid:1"):
        yield


def _prepare_status() -> ConformancePreparation:
    def verify(outcome: ConformanceOutcome) -> None:
        status = outcome.resolve_result(DependencyStatusResultV1)
        assert status.mode is DependencyCheckMode.QUICK
        assert tuple(row.item_id for row in status.rows) == _EVERY_ITEM
        assert all(row.mode is DependencyCheckMode.QUICK for row in status.rows)

    return ConformancePreparation(
        subject_ref=DEPENDENCIES_OPERATION_SUBJECT, request=DependencyStatusRequest(), verify=verify
    )


def _prepare_setup() -> ConformancePreparation:
    def verify(outcome: ConformanceOutcome) -> None:
        result = outcome.resolve_result(DependencySetupResultV1)
        assert result.outcome is DependencySetupOutcome.NOTHING_TO_DO
        assert result.items == ()
        assert tuple(row.item_id for row in result.rows) == _EVERY_ITEM

    return ConformancePreparation(
        subject_ref=DEPENDENCIES_OPERATION_SUBJECT, request=DependencySetupRequest(item_ids=()), verify=verify
    )


def _prepare_verify() -> ConformancePreparation:
    def verify(outcome: ConformanceOutcome) -> None:
        status = outcome.resolve_result(DependencyStatusResultV1)
        assert status.mode is DependencyCheckMode.FULL
        (row,) = status.rows
        assert row.item_id == "local_ai"
        assert row.state is not DependencyState.READY, "a closed endpoint is never a working local AI"

    return ConformancePreparation(
        subject_ref=DEPENDENCIES_OPERATION_SUBJECT,
        request=DependencyVerifyRequest(item_ids=("local_ai",)),
        verify=verify,
    )


_PREPARATIONS = {
    DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID: _prepare_status,
    DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID: _prepare_setup,
    DEPENDENCIES_VERIFY_OPERATION_DEFINITION_ID: _prepare_verify,
}


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    prepare = _PREPARATIONS.get(context.definition.definition_id)
    if prepare is None:
        raise AssertionError(f"no setup conformance scenario for {context.definition.definition_id}")
    return prepare()


DEPENDENCY_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (DEPENDENCIES_SETUP_PLAN_PHASE,),
        ),
        RegisteredExecutorConformanceCase(
            DEPENDENCIES_VERIFY_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (DEPENDENCIES_VERIFY_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
    closes_model_runtime=True,
    host_environment=_no_network,
)
