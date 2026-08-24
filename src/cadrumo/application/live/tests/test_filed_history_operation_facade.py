"""Public-facade contract for the recorded filed-history operation."""

from __future__ import annotations

import importlib
import subprocess
import sys
import textwrap
from types import ModuleType

import pytest

from ....adapters.persistence.profile.sync_runs import SyncRunRecordRepository
from .. import (
    FILED_HISTORY_OPERATION_DEFINITION_ID,
    FiledHistoryOnboardingRun,
    FiledHistoryOperationRequest,
    build_filed_history_operation_definition,
)
from .. import __all__ as public_names

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_filed_history_operation_contract_resolves_from_the_public_facade() -> None:
    """The facade exposes the request contract and composed definition factory."""

    live = importlib.import_module("..", package=__package__)
    definition = build_filed_history_operation_definition(sync_run_repository=SyncRunRecordRepository())

    assert FILED_HISTORY_OPERATION_DEFINITION_ID == "live.filed-history.pull"
    assert definition.definition_id == FILED_HISTORY_OPERATION_DEFINITION_ID
    assert definition.request_type is FiledHistoryOperationRequest
    assert definition.result_type is FiledHistoryOnboardingRun
    assert definition.executor_factory.request_type is FiledHistoryOperationRequest
    assert definition.executor_factory.executor_type.__module__.endswith("._filed_history_operation")
    assert definition.executor_factory.build().__class__.__module__.endswith("._filed_history_operation")
    assert build_filed_history_operation_definition.__module__.endswith("._filed_history_operation")
    assert FiledHistoryOperationRequest.__module__.endswith("._filed_history_operation")
    assert live.FILED_HISTORY_OPERATION_DEFINITION_ID is FILED_HISTORY_OPERATION_DEFINITION_ID
    assert live.FiledHistoryOperationRequest is FiledHistoryOperationRequest
    assert live.build_filed_history_operation_definition is build_filed_history_operation_definition


def test_filed_history_operation_facade_does_not_publish_executor_or_phase_internals() -> None:
    """The executable implementation and phase codes remain owner-private."""

    live = importlib.import_module("..", package=__package__)

    assert "FiledHistoryOperationExecutor" not in public_names
    assert "FiledHistoryPull" not in public_names
    assert "FILED_HISTORY_PHASE_EXECUTION" not in public_names
    assert not hasattr(live, "FiledHistoryOperationExecutor")
    assert not hasattr(live, "FiledHistoryPull")
    assert not hasattr(live, "FILED_HISTORY_PHASE_EXECUTION")


def test_filed_history_operation_public_names_are_unique_and_resolvable() -> None:
    """Every promised facade member resolves to a value rather than a module."""

    live = importlib.import_module("..", package=__package__)

    assert len(public_names) == len(set(public_names))
    assert all(not name.startswith("_") for name in public_names)
    assert all(hasattr(live, name) for name in public_names)
    assert all(not isinstance(getattr(live, name), ModuleType) for name in public_names)

    operation_names = [
        "FILED_HISTORY_OPERATION_DEFINITION_ID",
        "FiledHistoryOperationRequest",
        "build_filed_history_operation_definition",
    ]
    assert operation_names == sorted(operation_names)


def test_importing_live_keeps_filed_history_operation_lazy() -> None:
    """Importing the live facade does not load the operation implementation."""

    completed = subprocess.run(  # noqa: S603 - fixed interpreter and inline code under test
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import sys
                import cadrumo.application.live

                assert "cadrumo.application.live._filed_history_operation" not in sys.modules
                """,
            ),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
