"""Initial routing uses explicit setup state and refuses a foreign profile view."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Never, cast
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.overview import ProfileOverview
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.user_profile.values import ProfileSetupState
from cadrumo.entrypoints.tui.app import RootBindingV1
from cadrumo.entrypoints.tui.tests.home_fixtures import HomeFixtureScenario, build_home_projection_fixture
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient

from ....frontend.tui import runtime_initial_root
from ....frontend.tui.runtime_initial_root import RuntimeInitialRoot

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("state", list(ProfileSetupState))
@pytest.mark.parametrize("foreign_profile", [False, True])
def test_initial_route_uses_explicit_state_and_exact_profile(
    monkeypatch: pytest.MonkeyPatch, state: ProfileSetupState, *, foreign_profile: bool
) -> None:
    profile_id = uuid4()
    client = cast(
        FrontendClient,
        SimpleNamespace(
            profile_id=profile_id,
            session_id=uuid4(),
            frontend=OperationFrontendProjection.TUI,
            subscribe_session_retirement=None,
            subscribe_lifecycle_notices=None,
        ),
    )
    overview = ProfileOverview(
        profile_id=str(uuid4() if foreign_profile else profile_id),
        record_revision=1,
        content_digest="a" * 64,
        label="Test profile",
        setup_state=state,
        sections=(),
        missing_required=(),
    )
    monkeypatch.setattr(runtime_initial_root, "read_profile_overview", lambda *_args, **_kwargs: overview)
    monkeypatch.setattr(
        RuntimeInitialRoot,
        "_session",
        lambda _self: build_home_projection_fixture(HomeFixtureScenario.READY).account,
    )
    workbench_reads: list[bool] = []
    full_binding = cast(RootBindingV1, object())

    def workbench(_self: RuntimeInitialRoot, initial_profile: ProfileOverview | None = None) -> RootBindingV1:
        assert initial_profile is overview
        workbench_reads.append(True)
        return full_binding

    monkeypatch.setattr(RuntimeInitialRoot, "_workbench", workbench)

    async def recovery() -> FrontendClient:
        raise AssertionError("routing must not open another client")

    def operations() -> Never:
        raise AssertionError("routing must not compose operations")

    root = RuntimeInitialRoot(
        client,
        profile_label="Test profile",
        output_language=OutputLanguage.ES,
        open_recovery_client=recovery,
        operation_registry=operations,
    )
    if foreign_profile:
        with pytest.raises(RefusalError) as refused:
            root.load()
        assert refused.value.reason is RefusalCode.INVALID_FRAME
        assert workbench_reads == []
    elif state is ProfileSetupState.COMPLETE:
        assert root.load() is full_binding
        assert workbench_reads == [True]
    else:
        binding = root.load()
        assert binding.initial_destination is not None
        assert binding.initial_destination.destination == "workbench.profile"
        assert binding.initial_account_session is not None
        assert workbench_reads == []
        assert overview.complete  # Missing-field counts never complete setup implicitly.


@pytest.mark.parametrize("changed", [None, "profile_id", "record_revision", "content_digest", "setup_state"])
def test_complete_profile_reuse_requires_current_provenance(
    monkeypatch: pytest.MonkeyPatch, changed: str | None
) -> None:
    from ....frontend.tui import runtime_workbench

    profile_id = uuid4()
    overview = ProfileOverview(
        profile_id=str(profile_id),
        record_revision=1,
        content_digest="a" * 64,
        label="Test profile",
        setup_state=ProfileSetupState.COMPLETE,
        sections=(),
    )
    current = SimpleNamespace(
        profile_id=profile_id, record_revision=1, content_digest="a" * 64, setup_state=ProfileSetupState.COMPLETE
    )
    if changed is not None:
        setattr(
            current,
            changed,
            {
                "profile_id": uuid4(),
                "record_revision": 2,
                "content_digest": "b" * 64,
                "setup_state": ProfileSetupState.INCOMPLETE,
            }[changed],
        )
    status_reads: list[bool] = []
    full_reads: list[bool] = []

    def status(*_args: object, **_kwargs: object) -> SimpleNamespace:
        status_reads.append(True)
        return current

    client = cast(
        FrontendClient,
        SimpleNamespace(
            profile_id=profile_id,
            session_id=uuid4(),
            frontend=OperationFrontendProjection.TUI,
            read_profile_view=status,
        ),
    )
    fresh = overview.model_copy(update={"record_revision": 2})

    def read(*_args: object, **_kwargs: object) -> ProfileOverview:
        full_reads.append(True)
        return fresh

    monkeypatch.setattr(runtime_workbench, "read_profile_overview", read)
    monkeypatch.setattr(
        runtime_workbench,
        "read_workbench_generation",
        lambda *_args, **_kwargs: SimpleNamespace(home=SimpleNamespace(projection=object())),
    )
    monkeypatch.setattr(runtime_workbench, "read_runtime_account_session", lambda *_args, **_kwargs: None)

    async def recovery() -> FrontendClient:
        raise AssertionError("capture must not open another client")

    def operations() -> Never:
        raise AssertionError("capture must not compose operations")

    root = runtime_workbench.RuntimeWorkbenchRoot(
        client,
        profile_label="Test profile",
        output_language=OutputLanguage.ES,
        open_recovery_client=recovery,
        operation_registry=operations,
    )
    assert root._read(initial_profile=overview).profile is (overview if changed is None else fresh)
    assert status_reads == [True]
    assert full_reads == ([] if changed is None else [True])
    assert root._read().profile is fresh  # Later Home refreshes always read afresh.
