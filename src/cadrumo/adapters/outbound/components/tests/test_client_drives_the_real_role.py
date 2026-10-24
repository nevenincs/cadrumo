"""The client drives the real components role of a built Cadrumo binary.

``just test-components-role IMAGE`` runs these cases with the built binary
(:mod:`cadrumo.tests.components_role_package`). Each case has its own
throwaway storage root, and a local proxy stands in for the network, so
nothing reaches a publisher.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.tests import components_role_package
from cadrumo.tests.components_role_package import (
    CountingProxy,
    components_role_fixture,
    counting_proxy_fixture,
    holding_proxy_fixture,
    refusing_proxy_fixture,
    staged_components_role_fixture,
)
from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from .....application.dependency_contracts import DependencyItemKind, DependencyState
from ..client import ComponentsCancellation, ComponentsRequest, run_components_role
from ..protocol import (
    ComponentsCommand,
    ComponentsDecline,
    ComponentsEvent,
    ComponentsNoticeCode,
    ComponentsNoticeLine,
    ComponentsOutcome,
    ComponentsPhaseLine,
    ComponentsReviewLine,
)
from ..role_image import DEVELOPMENT_ROLE_IMAGE_VARIABLE

__all__ = [
    "components_role_fixture",
    "counting_proxy_fixture",
    "holding_proxy_fixture",
    "refusing_proxy_fixture",
    "staged_components_role_fixture",
]

pytestmark = [pytest.mark.integration, pytest.mark.external_tool, pytest.mark.hex_outbound_adapter]


def test_the_test_support_names_the_setting_the_client_reads() -> None:
    assert components_role_package._IMAGE_VARIABLE == DEVELOPMENT_ROLE_IMAGE_VARIABLE


@pytest.mark.usefixtures("components_role")
def test_a_quick_status_reads_every_item_from_an_empty_root() -> None:
    first = run_components_role(ComponentsRequest(ComponentsCommand.STATUS), timeout=30)
    again = run_components_role(ComponentsRequest(ComponentsCommand.STATUS), timeout=30)

    assert first.outcome is ComponentsOutcome.OK
    rows = first.status_rows()
    assert [row.kind for row in rows] == list(DependencyItemKind)
    assert {row.state for row in rows} == {DependencyState.ABSENT}
    assert [row.recovery_action_id for row in rows] == ["operator.provision.browser", "operator.provision.local_ai"]
    assert again.rows == first.rows


@pytest.mark.usefixtures("components_role")
def test_a_plan_is_the_same_plan_until_something_changes() -> None:
    request = ComponentsRequest(ComponentsCommand.PLAN, items=(DependencyItemKind.BROWSER,))
    first = run_components_role(request)
    again = run_components_role(request)

    assert first.outcome is ComponentsOutcome.OK
    assert first.plan is not None
    assert first.plan_digest is not None
    assert [entry.item_id for entry in first.plan.entries] == ["browser"]
    assert again.plan_digest == first.plan_digest


@pytest.mark.usefixtures("components_role", "refusing_proxy")
def test_a_network_that_refuses_the_tunnel_refuses_the_setup_before_asking() -> None:
    events: list[ComponentsEvent] = []
    reviews: list[ComponentsReviewLine] = []

    def decline(review: ComponentsReviewLine) -> ComponentsDecline:
        reviews.append(review)
        return ComponentsDecline()

    result = run_components_role(
        ComponentsRequest(ComponentsCommand.SETUP, items=(DependencyItemKind.BROWSER,)),
        on_event=events.append,
        review=decline,
    )

    assert reviews == []
    assert result.outcome is ComponentsOutcome.REFUSED
    assert (result.item_id, result.failure_category) == ("browser", DependencyFailureCategory.BLOCKED_BY_NETWORK)
    assert [event.step.value for event in events if isinstance(event, ComponentsPhaseLine)] == ["plan", "preflight"]


@pytest.mark.usefixtures("components_role")
def test_a_client_started_role_follows_the_proxy_and_the_credentials_in_its_address(
    counting_proxy: CountingProxy,
) -> None:
    result = run_components_role(ComponentsRequest(ComponentsCommand.SETUP, items=(DependencyItemKind.BROWSER,)))

    assert result.outcome is ComponentsOutcome.REFUSED
    assert (result.item_id, result.failure_category) == ("browser", DependencyFailureCategory.BLOCKED_BY_NETWORK)
    assert result.plan is not None
    (entry,) = result.plan.entries
    assert counting_proxy.tunnels == dict.fromkeys(entry.source_hosts, 1)
    assert counting_proxy.unauthenticated == 0


@pytest.fixture(name="shared_browser_cache")
def shared_browser_cache_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A browser cache outside the case's root, named by the run's settings as the test run's own shared one is."""
    cache = tmp_path / "shared-browsers"
    for build in ("chromium-9999", "chromium_headless_shell-9999"):
        (cache / build).mkdir(parents=True)
        (cache / build / "INSTALLATION_COMPLETE").write_bytes(b"")
    monkeypatch.setenv("CADRUMO_PLAYWRIGHT_BROWSERS_DIR", str(cache))
    return cache


@pytest.mark.usefixtures("shared_browser_cache", "components_role")
def test_the_role_works_in_the_cases_root_and_never_in_the_runs_shared_browser_cache(tmp_path: Path) -> None:
    cache = tmp_path / "shared-browsers"

    removal = run_components_role(ComponentsRequest(ComponentsCommand.REMOVE, items=(DependencyItemKind.BROWSER,)))

    assert removal.outcome is ComponentsOutcome.REMOVED
    assert sorted(path.name for path in cache.iterdir()) == ["chromium-9999", "chromium_headless_shell-9999"]
    assert (cache / "chromium-9999" / "INSTALLATION_COMPLETE").is_file()


@pytest.mark.usefixtures("components_role", "holding_proxy")
def test_a_cancellation_reaches_the_running_check_by_its_input_line() -> None:
    cancellation = ComponentsCancellation()
    cancellation.cancel()
    events: list[ComponentsEvent] = []

    result = run_components_role(
        ComponentsRequest(ComponentsCommand.VERIFY, items=(DependencyItemKind.BROWSER,)),
        on_event=events.append,
        cancellation=cancellation,
    )

    assert any(
        isinstance(event, ComponentsNoticeLine) and event.notice_code is ComponentsNoticeCode.CANCEL_REQUESTED
        for event in events
    )
    assert result.outcome is ComponentsOutcome.OK


@pytest.mark.usefixtures("components_role")
def test_cancel_and_removal_report_what_they_touched() -> None:
    cancel = run_components_role(ComponentsRequest(ComponentsCommand.CANCEL))
    removal = run_components_role(ComponentsRequest(ComponentsCommand.REMOVE, items=(DependencyItemKind.BROWSER,)))

    assert (cancel.outcome, cancel.items) == (ComponentsOutcome.NOTHING_RUNNING, ())
    assert (removal.outcome, removal.items) == (ComponentsOutcome.REMOVED, ("browser",))
