"""Refusals that must precede construction and ownership of capture resources.

A provider refusal precedes the capture's resources, and a refused output root
precedes the provider: an executor that does not accept the host path it was
given starts no phase, checks no provider and composes nothing.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import cast, override
from uuid import UUID

import pytest
from pydantic import BaseModel

from ....core.config import override_settings
from ....core.errors.error_codes import ErrorCategory, get_registered_error_code
from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.capabilities import OperationOwnedResource
from ...operations.models import OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.tests.test_executor import EventEmitter
from ...storage.sync_runs.records import SyncRunRecordRepositoryProtocol
from ..errors import LiveApplicationInputError
from ..filed_bulk_capture_operation import (
    FILED_BULK_CAPTURE_DEFINITION_ID,
    FiledBulkCaptureExecutor,
    FiledBulkCaptureRequest,
)
from ..filed_history_operation import (
    FILED_HISTORY_OPERATION_DEFINITION_ID,
    FiledHistoryComposition,
    FiledHistoryOperationExecutor,
    FiledHistoryOperationRequest,
    require_capture_output_root,
)
from ..filed_single_capture_operation import (
    FILED_SINGLE_CAPTURE_DEFINITION_ID,
    FiledSingleCaptureExecutor,
    FiledSingleCaptureRequest,
)
from ..filed_source_capture_operation import (
    FILED_SOURCE_CAPTURE_DEFINITION_ID,
    FiledSourceCaptureExecutor,
    FiledSourceCaptureRequest,
)
from ..iva_remote_state_capture_operation import (
    IVA_REMOTE_STATE_CAPTURE_DEFINITION_ID,
    IvaRemoteStateCaptureExecutor,
    IvaRemoteStateCaptureRequest,
)
from ..iva_wallet_history_capture_operation import (
    IVA_WALLET_HISTORY_CAPTURE_DEFINITION_ID,
    IvaWalletHistoryCaptureExecutor,
    IvaWalletHistoryCaptureRequest,
)
from ..live_operation_execution import prepare_provider_capture

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Events(EventEmitter):
    def __init__(self, trace: list[str]) -> None:
        self.trace = trace

    @override
    async def phase(self, phase_code: str) -> None:
        self.trace.append(phase_code)

    @override
    async def effect(self, effect: OperationEffect) -> None:
        self.trace.append(effect.value)


class _Resources:
    @contextmanager
    def activate(self) -> Iterator[None]:
        yield

    async def close(self) -> None: ...


class _Cleanup:
    def __init__(self, trace: list[str], resource: _Resources) -> None:
        self.trace = trace
        self.resource = resource

    def own(self, resource: object, *, family: OperationOwnedResource) -> None:
        assert resource is self.resource
        assert family is OperationOwnedResource.PROCESS
        self.trace.append("owned")


@pytest.mark.parametrize("may_write", [True, False])
@pytest.mark.parametrize("refuse", [True, False])
@pytest.mark.asyncio
async def test_preflight_precedes_resource_ownership_and_preview_retains_session_accounting(
    tmp_path: Path, may_write: bool, refuse: bool
) -> None:
    trace: list[str] = []
    profile_id = UUID("11111111-1111-4111-8111-111111111111")
    resources = _Resources()
    # CAST-RATIONALE-PROVIDER-PREPARATION: the helper forwards authority and
    # composition by identity; no registry or capture-port method is invoked.
    authority = cast(PinnedAuthorityOperation, object())
    composition = cast(FiledHistoryComposition, object())
    context = cast(
        OperationExecutorContext,
        SimpleNamespace(events=_Events(trace), cleanup=_Cleanup(trace, resources), authority_operation=authority),
    )

    def preflight(target: UUID, operation: PinnedAuthorityOperation) -> None:
        assert target == profile_id and operation is authority
        trace.append("preflight")
        if refuse:
            raise OSError("provider refused")

    def compose(output_root: Path, *, operation: PinnedAuthorityOperation) -> FiledHistoryComposition:
        assert output_root == tmp_path and operation is authority
        trace.append("compose")
        return composition

    def browser() -> _Resources:
        trace.append("browser")
        return resources

    invocation = prepare_provider_capture(
        context,
        profile_id,
        tmp_path,
        compose,
        browser,
        preflight,
        preflight_phase="checking",
        acquire_phase="acquiring",
        may_write=may_write,
    )
    if refuse:
        with pytest.raises(OSError, match="provider refused"):
            await invocation
        assert trace == ["checking", "preflight"]
        return
    prepared, owned, receipt = await invocation
    assert prepared is composition and owned is resources
    assert trace == ["checking", "preflight", "compose", "browser", "owned", "acquiring"] + (
        [OperationEffect.UNKNOWN.value] if may_write else []
    )
    await receipt(OperationEffect.UPDATED)
    assert receipt.combine(OperationEffect.NONE) is OperationEffect.UPDATED


_PROFILE_ID = UUID("22222222-2222-4222-8222-222222222222")

# CAST-RATIONALE-UNREACHED-CONTEXT: a refused output root must stop the executor
# before it touches its context, so the context has no attribute to touch. An
# executor that admits the root fails on the first one it reads.
_UNREACHED_CONTEXT = cast(OperationExecutorContext, SimpleNamespace())


def _request[PayloadT: BaseModel](definition_id: str, payload: PayloadT) -> OperationRequest[PayloadT]:
    return OperationRequest(
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE_ID)),
        payload=payload,
    )


class _Capabilities:
    """Worker capabilities that record any use a refused request must never reach."""

    def __init__(self) -> None:
        self.trace: list[str] = []

    def compose(self, output_root: Path, *, operation: PinnedAuthorityOperation) -> FiledHistoryComposition:
        del output_root, operation
        self.trace.append("compose")
        return cast(FiledHistoryComposition, object())

    def browser(self) -> _Resources:
        self.trace.append("browser")
        return _Resources()

    def preflight(self, profile_id: UUID, operation: PinnedAuthorityOperation) -> None:
        del profile_id, operation
        self.trace.append("preflight")

    def sync_runs(self) -> SyncRunRecordRepositoryProtocol:
        self.trace.append("sync-runs")
        return cast(SyncRunRecordRepositoryProtocol, object())


def _run_filed_single(capabilities: _Capabilities, output_root: Path) -> Awaitable[object]:
    executor = FiledSingleCaptureExecutor(capabilities.compose, capabilities.browser, capabilities.preflight)
    payload = FiledSingleCaptureRequest(
        profile_id=_PROFILE_ID, output_root=output_root, modelo="303", year=2025, period="1T"
    )
    return executor.execute(_request(FILED_SINGLE_CAPTURE_DEFINITION_ID, payload), _UNREACHED_CONTEXT)


def _run_filed_bulk(capabilities: _Capabilities, output_root: Path) -> Awaitable[object]:
    executor = FiledBulkCaptureExecutor(
        capabilities.compose, capabilities.browser, capabilities.preflight, capabilities.sync_runs
    )
    payload = FiledBulkCaptureRequest(profile_id=_PROFILE_ID, output_root=output_root, year_from=2025, year_to=2025)
    return executor.execute(_request(FILED_BULK_CAPTURE_DEFINITION_ID, payload), _UNREACHED_CONTEXT)


def _run_filed_source(capabilities: _Capabilities, output_root: Path) -> Awaitable[object]:
    executor = FiledSourceCaptureExecutor(capabilities.compose, capabilities.browser, capabilities.preflight)
    payload = FiledSourceCaptureRequest(
        profile_id=_PROFILE_ID, output_root=output_root, modelo="303", year=2025, period="1T"
    )
    return executor.execute(_request(FILED_SOURCE_CAPTURE_DEFINITION_ID, payload), _UNREACHED_CONTEXT)


def _run_filed_history(capabilities: _Capabilities, output_root: Path) -> Awaitable[object]:
    executor = FiledHistoryOperationExecutor(
        sync_run_repository=cast(SyncRunRecordRepositoryProtocol, object()),
        composition_factory=capabilities.compose,
        browser_resources_factory=capabilities.browser,
        provider_preflight=capabilities.preflight,
    )
    payload = FiledHistoryOperationRequest(profile_id=_PROFILE_ID, output_root=output_root)
    return executor.execute(_request(FILED_HISTORY_OPERATION_DEFINITION_ID, payload), _UNREACHED_CONTEXT)


def _run_iva_history(capabilities: _Capabilities, output_root: Path) -> Awaitable[object]:
    executor = IvaWalletHistoryCaptureExecutor(capabilities.compose, capabilities.browser, capabilities.preflight)
    payload = IvaWalletHistoryCaptureRequest(
        profile_id=_PROFILE_ID, output_root=output_root, year_from=2025, year_to=2025
    )
    return executor.execute(_request(IVA_WALLET_HISTORY_CAPTURE_DEFINITION_ID, payload), _UNREACHED_CONTEXT)


def _run_iva_evidence(capabilities: _Capabilities, output_root: Path) -> Awaitable[object]:
    executor = IvaRemoteStateCaptureExecutor(capabilities.compose, capabilities.browser, capabilities.preflight)
    payload = IvaRemoteStateCaptureRequest(
        profile_id=_PROFILE_ID,
        output_root=output_root,
        year_from=2025,
        year_to=2025,
        target_year=2025,
        target_period="1T",
    )
    return executor.execute(_request(IVA_REMOTE_STATE_CAPTURE_DEFINITION_ID, payload), _UNREACHED_CONTEXT)


_OUTPUT_ROOT_OPERATIONS: dict[str, Callable[[_Capabilities, Path], Awaitable[object]]] = {
    FILED_SINGLE_CAPTURE_DEFINITION_ID: _run_filed_single,
    FILED_BULK_CAPTURE_DEFINITION_ID: _run_filed_bulk,
    FILED_SOURCE_CAPTURE_DEFINITION_ID: _run_filed_source,
    FILED_HISTORY_OPERATION_DEFINITION_ID: _run_filed_history,
    IVA_WALLET_HISTORY_CAPTURE_DEFINITION_ID: _run_iva_history,
    IVA_REMOTE_STATE_CAPTURE_DEFINITION_ID: _run_iva_evidence,
}


def _link_directory(link: Path, target: Path) -> None:
    """Create the kind of directory link any account on this platform may create."""
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link, target_is_directory=True)


def _storage_with_redirected_capture_root(tmp_path: Path) -> tuple[Path, Path]:
    """Return a storage root and a capture root inside it that a link sends elsewhere."""
    storage = tmp_path / "storage"
    storage.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _link_directory(storage / "filed-declarations", elsewhere)
    return storage, storage / "filed-declarations" / "captures"


def test_the_six_output_root_operations_are_all_enrolled() -> None:
    assert set(_OUTPUT_ROOT_OPERATIONS) == {
        "live.filed-capture.single",
        "live.filed-capture.bulk",
        "live.filed-capture.source",
        "live.filed-history.pull",
        "live.iva-wallet.history-capture",
        "live.iva-wallet.evidence-capture",
    }


@pytest.mark.parametrize("definition_id", sorted(_OUTPUT_ROOT_OPERATIONS))
@pytest.mark.asyncio
async def test_an_output_root_that_leaves_its_allowed_place_is_refused_before_any_capture_begins(
    tmp_path: Path, definition_id: str
) -> None:
    run = _OUTPUT_ROOT_OPERATIONS[definition_id]
    storage, redirected = _storage_with_redirected_capture_root(tmp_path)
    refused = {
        "relative_path": Path("captures"),
        "parent_traversal": storage / "captures" / ".." / ".." / "elsewhere",
        "redirected_by_link": redirected,
    }

    with override_settings(cadrumo_active_profile=str(_PROFILE_ID), cadrumo_local_storage_root=storage):
        for reason, output_root in refused.items():
            capabilities = _Capabilities()
            with pytest.raises(LiveApplicationInputError) as refusal:
                await run(capabilities, output_root)

            assert refusal.value.context == {"field": "output_root", "reason": reason}
            assert get_registered_error_code(refusal.value).category is ErrorCategory.REFUSED
            assert get_registered_error_code(refusal.value).code == "REFUSED_APPLICATION_LIVE_INPUT"
            assert capabilities.trace == []

    assert list((tmp_path / "elsewhere").iterdir()) == []


@pytest.mark.parametrize("definition_id", sorted(_OUTPUT_ROOT_OPERATIONS))
@pytest.mark.asyncio
async def test_an_output_root_really_inside_storage_or_named_outside_it_reaches_the_executor(
    tmp_path: Path, definition_id: str
) -> None:
    run = _OUTPUT_ROOT_OPERATIONS[definition_id]
    storage = tmp_path / "storage"
    (storage / "filed-declarations").mkdir(parents=True)
    admitted = (
        storage / "filed-declarations",
        storage / "live" / "not-created-yet",
        tmp_path / "a directory the operator named",
    )

    with override_settings(cadrumo_active_profile=str(_PROFILE_ID), cadrumo_local_storage_root=storage):
        for output_root in admitted:
            capabilities = _Capabilities()
            # The context has nothing to read: reaching it is the proof the root was admitted.
            with pytest.raises(AttributeError):
                await run(capabilities, output_root)
            assert capabilities.trace == []

    assert not (storage / "live").exists()
    assert not (tmp_path / "a directory the operator named").exists()


def test_the_output_root_refusal_does_not_repeat_the_path(tmp_path: Path) -> None:
    storage, redirected = _storage_with_redirected_capture_root(tmp_path)

    with (
        override_settings(cadrumo_active_profile=str(_PROFILE_ID), cadrumo_local_storage_root=storage),
        pytest.raises(LiveApplicationInputError) as refusal,
    ):
        require_capture_output_root(redirected)

    rendered = f"{refusal.value} {refusal.value.context} {refusal.value.translated_message}"
    assert str(redirected) not in rendered
    assert str(tmp_path) not in rendered
    assert refusal.value.context == {"field": "output_root", "reason": "redirected_by_link"}
