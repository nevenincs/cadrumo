"""Exercise the registered CENSO frontend review and terminal-result contract."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import override

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ...application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationResultV1,
    OperationObservationSuccessV1,
    OperationObservationVersionHeader,
)
from ...application.operations.observation import OperationObservationService
from ...application.user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...core.errors.hierarchy import InternalInvariantError
from ...core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from .censal_review_test_support import review_censal_with_services
from .registered_executor_case_support import _CloseWitness, _runtime

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("apply", [True, False], ids=["apply", "reject"])
def test_censal_frontend_driver_reviews_one_acquisition_and_rolls_back_rejection(
    tmp_path: Path,
    apply: bool,
    operation: PinnedAuthorityOperation,
) -> None:
    """The public frontend driver answers the encrypted exact proposal once."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    cleanup = _CloseWitness()
    with _runtime(tmp_path / f"frontend-{apply}", cleanup=cleanup) as (_driver, _registry, profile_id):
        repository = ProfileRecordRepository.for_current_session(
            profile_id, profile_decode_context=_profile_decode_context_for_test
        )
        before = repository.load(profile_id)
        decisions: list[tuple[str | None, ...]] = []

        def decide(projection) -> bool:
            decisions.append(tuple(field.observed_value for field in projection.fields))
            return apply

        result = asyncio.run(
            review_censal_with_services(
                _driver.services,
                operation=operation,
                actor_ref="operator:frontend-test",
                decide=decide,
            )
        )

        assert result.applied is apply
        assert len(decisions) == 1
        assert len(decisions[0]) == len(CENSAL_ADOPTABLE_PATHS)
        assert decisions[0][0] is not None and decisions[0][0] != ""
        assert decisions[0][1] == "28013"
        assert cleanup.closed is True
        after = repository.load(profile_id)
        if apply:
            assert after.record_revision == before.record_revision + 1
            assert after.content_digest != before.content_digest
        else:
            assert after == before


def test_censal_frontend_driver_never_reports_a_failed_terminal_as_applied(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """An accepted response followed by a failed continuation stays a failure."""
    cleanup = _CloseWitness()
    with _runtime(tmp_path / "frontend-failed", cleanup=cleanup) as (driver, _registry, _profile_id):
        delegate = driver.services.observation

        class _FailedTerminalObservation(OperationObservationService):
            @override
            async def observe(
                self, request: OperationObservationVersionHeader | OperationObservationRequestV1
            ) -> OperationObservationResultV1:
                observed = await super().observe(request)
                if (
                    isinstance(observed, OperationObservationSuccessV1)
                    and observed.projection.lifecycle is OperationLifecycle.TERMINAL
                ):
                    return observed.model_copy(
                        update={
                            "projection": observed.projection.model_copy(
                                update={
                                    "terminal_condition": OperationTerminalCondition.FAILED,
                                    "effect": OperationEffect.UNKNOWN,
                                    "result_ref": None,
                                    "diagnostic_ref": "diagnostic:censo-stale",
                                }
                            )
                        }
                    )
                return observed

        failing_services = replace(
            driver.services,
            observation=_FailedTerminalObservation(reader=delegate.reader, registry=delegate.registry),
        )
        with pytest.raises(InternalInvariantError, match="did not succeed"):
            asyncio.run(
                review_censal_with_services(
                    failing_services,
                    operation=operation,
                    actor_ref="operator:frontend-failed-test",
                    decide=lambda _projection: True,
                )
            )
