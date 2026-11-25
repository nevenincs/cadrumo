"""A cli lane is signed out only through a logout its agent declares, and every refusal is logged with its cause."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast, get_args

import pytest

from cadrumo.core.errors.hierarchy import CoreValidationError
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID

from ...adapters.agent_provider_auth_status import AgentProviderAuthStatusProbe
from ...providers.application.contracts import (
    CliObservation,
    CliState,
    ProviderSettingsStatus,
    ProviderStatusEntry,
    ServiceCause,
)
from ...providers.application.ports import AbsentProviderRecord
from ...providers.application.resolution import status_entry
from ...providers.application.service import ProviderSettingsService
from ...providers.application.tests.memory_store import MemoryProviderSettingsStore
from ...providers.application.tests.synthetic_catalog import (
    KEY_LANE,
    SIGN_IN_ONLY_LANE,
    ProvidedProviderCatalogSource,
    UnavailableCatalogSource,
    synthetic_document,
)
from ...providers.domain.catalog import ProviderCatalog, ProviderCatalogEntry, parse_provider_catalog
from ...providers.domain.record import LocalEngine
from ...service_sign_out import answer_sign_out, signed_out_refusal

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ROOT = Path("synthetic-agent-root")


def _catalog(*, logout: bool) -> ProviderCatalog:
    """The synthetic catalogue, with the sign-in-only cli lane declaring a logout when ``logout``."""
    document = json.loads(synthetic_document())
    if logout:
        for lane in document["providers"]:
            if lane["id"] == SIGN_IN_ONLY_LANE:
                lane["logout"] = True
    return parse_provider_catalog(json.dumps(document))


def _lane(catalog: ProviderCatalog, lane_id: str) -> ProviderCatalogEntry:
    entry = catalog.entry(lane_id)
    assert entry is not None
    return entry


def _logged(answer: dict[str, Any]) -> dict[str, Any]:
    """The answer without its log reference, which must be a whole UUID."""
    assert re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", answer["log_ref"])
    return {key: value for key, value in answer.items() if key != "log_ref"}


class _Agent:
    """The agent's signed-in state and its logout, observed as the probe would."""

    def __init__(self, *, logout_fails: ServiceCause | None = None) -> None:
        self.state = CliState.INSTALLED_SIGNED_IN
        self.logout_fails = logout_fails
        self.logouts: list[tuple[str, Path]] = []
        self.forgotten = 0

    def probe(self, _entry: ProviderCatalogEntry) -> CliObservation:
        return CliObservation(self.state)

    def log_out(self, provider: str, *, root: Path) -> ServiceCause | None:
        self.logouts.append((provider, root))
        if self.logout_fails is None:
            self.state = CliState.INSTALLED_SIGNED_OUT
        return self.logout_fails

    def forget(self) -> None:
        self.forgotten += 1


def _answer(
    agent: _Agent,
    *,
    catalog: ProviderCatalog,
    lane: str = SIGN_IN_ONLY_LANE,
    revision: str = ABSENT_SECURE_OBJECT_REVISION_ID,
    signed_in: bool = True,
    source: ProvidedProviderCatalogSource | UnavailableCatalogSource | None = None,
) -> dict[str, Any]:
    catalog_source = ProvidedProviderCatalogSource(catalog) if source is None else source
    providers = ProviderSettingsService(
        store=MemoryProviderSettingsStore(),
        catalog_source=catalog_source,
        selected_engine=lambda: LocalEngine.LLAMACPP,
        cli_state_probe=agent.probe,
    )
    return answer_sign_out(
        lane=lane,
        expected_revision=revision,
        catalog=catalog_source,
        providers=providers,
        login_context=lambda: (_ROOT, "synthetic-key") if signed_in else None,
        login_status=cast(AgentProviderAuthStatusProbe, agent),
        forget=agent.forget,
    )


@pytest.mark.parametrize("logout", [True, False])
@pytest.mark.parametrize("cli_state", [*list(CliState), None])
def test_sign_out_is_available_only_on_a_signed_in_cli_lane_whose_agent_declares_a_logout(
    logout: bool, cli_state: CliState | None
) -> None:
    catalog = _catalog(logout=logout)
    cli = status_entry(
        _lane(catalog, SIGN_IN_ONLY_LANE), AbsentProviderRecord(provider=SIGN_IN_ONLY_LANE), cli_state=cli_state
    )
    assert cli.sign_out_available is (logout and cli_state is CliState.INSTALLED_SIGNED_IN)
    api = status_entry(_lane(catalog, KEY_LANE), AbsentProviderRecord(provider=KEY_LANE), cli_state=cli_state)
    assert api.sign_out_available is False


def test_the_served_field_is_required_and_an_undeclared_logout_reads_as_none() -> None:
    assert ProviderStatusEntry.model_fields["sign_out_available"].is_required()
    assert not any(entry.logout for entry in _catalog(logout=False).providers)


@pytest.mark.parametrize("lane_id", [KEY_LANE, "local_api", "third_cli"])
def test_only_a_cli_lane_that_takes_its_providers_sign_in_may_declare_a_logout(lane_id: str) -> None:
    document = json.loads(synthetic_document())
    for lane in document["providers"]:
        if lane["id"] == lane_id:
            lane["logout"] = True
    with pytest.raises(CoreValidationError):
        parse_provider_catalog(json.dumps(document))


def test_a_declared_logout_runs_the_agent_and_answers_with_the_refreshed_entry() -> None:
    agent = _Agent()
    answer = _answer(agent, catalog=_catalog(logout=True))
    entry = ProviderStatusEntry.model_validate(answer["entry"], strict=False)
    assert entry.id == SIGN_IN_ONLY_LANE
    assert entry.cli_state is CliState.INSTALLED_SIGNED_OUT
    assert entry.sign_out_available is False
    assert agent.logouts == [("example", _ROOT)]
    assert agent.forgotten == 1


def test_a_lane_whose_agent_declares_no_logout_is_refused_before_anything_runs() -> None:
    agent = _Agent()
    for lane in (SIGN_IN_ONLY_LANE, KEY_LANE, "no_such_lane"):
        answer = _answer(agent, catalog=_catalog(logout=False), lane=lane)
        assert _logged(answer) == {"kind": "refused", "code": "sign_in_unavailable", "cause": "lane_not_signable"}
    assert agent.logouts == []


def test_a_signed_out_profile_is_refused_with_its_cause() -> None:
    agent = _Agent()
    answer = _answer(agent, catalog=_catalog(logout=True), signed_in=False)
    assert _logged(answer) == {"kind": "refused", "code": "signed_out", "cause": "profile_signed_out"}
    assert _logged(signed_out_refusal("sign_out")) == {
        "kind": "refused",
        "code": "signed_out",
        "cause": "profile_signed_out",
    }
    assert signed_out_refusal("turn_on") == {"kind": "refused", "code": "signed_out"}
    assert agent.logouts == []


def test_a_stale_revision_is_refused_as_a_conflict_before_the_agent_runs() -> None:
    agent = _Agent()
    answer = _answer(agent, catalog=_catalog(logout=True), revision="f" * 64)
    assert _logged(answer) == {"code": "revision_conflict", "cause": "settings_refused"}
    assert agent.logouts == []


@pytest.mark.parametrize("cause", get_args(ServiceCause)[-3:])
def test_a_failed_logout_is_a_logged_service_failure_with_its_cause_and_reads_back_nothing(cause: ServiceCause) -> None:
    assert cause.startswith("logout_")
    agent = _Agent(logout_fails=cause)
    answer = _answer(agent, catalog=_catalog(logout=True))
    assert _logged(answer) == {"kind": "refused", "code": "service_failed", "cause": cause}
    assert agent.logouts == [("example", _ROOT)]
    assert agent.forgotten == 1


def test_an_unreadable_catalogue_is_a_logged_service_failure() -> None:
    agent = _Agent()
    answer = _answer(agent, catalog=_catalog(logout=True), source=UnavailableCatalogSource())
    assert _logged(answer) == {"kind": "refused", "code": "service_failed", "cause": "settings_change_failed"}
    assert agent.logouts == []


def test_the_status_read_serves_the_field_for_every_lane() -> None:
    agent = _Agent()
    providers = ProviderSettingsService(
        store=MemoryProviderSettingsStore(),
        catalog_source=ProvidedProviderCatalogSource(_catalog(logout=True)),
        selected_engine=lambda: LocalEngine.LLAMACPP,
        cli_state_probe=agent.probe,
    )
    status = providers.status(reads_pending=lambda _lanes: False)
    assert isinstance(status, ProviderSettingsStatus)
    served = {entry.id: entry.sign_out_available for entry in status.providers}
    assert served[SIGN_IN_ONLY_LANE] is True
    assert not any(available for lane, available in served.items() if lane != SIGN_IN_ONLY_LANE)
