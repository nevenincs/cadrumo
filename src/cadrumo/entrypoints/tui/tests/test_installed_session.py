"""Installed sessions build public contracts only for an actual requester."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Iterator
from contextlib import asynccontextmanager, nullcontext
from typing import TYPE_CHECKING, Literal, cast, override
from uuid import UUID, uuid4

import pytest

from cadrumo_client.transport.frontend_client import FrontendClient

from ....adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from ....application.operations.registry import OperationPublicContractSetV1, OperationRegistry
from ....application.user_profile.automation_custody_port import AutomationSecretStore
from ....application.user_profile.automation_operations import (
    build_automation_operation_definitions,
    build_automation_operation_registrations,
)
from ....application.user_profile.login_interaction import (
    ProfileLoginChoice,
    ProfileLoginInventoryState,
    ProfileLoginInventoryV1,
)
from ....core.errors.hierarchy import InternalInvariantError
from ... import operation_composition
from .. import installed_session, runtime_session
from ..account import AccountRecomposeReasonV1, AccountRecomposeRequiredV1
from ..installation.destination import InstallationScreen
from ..secret import credentials
from ..secret.automation_requester import RuntimeAutomationRequesterScreen
from ..secret.automation_requester_contracts import FreshCredentialClientOpener, RequesterClientOpener
from ..secret.registration import RegistrationScreen
from ..secret.runtime_login import RuntimeRequesterFactory
from ..secret.runtime_login_contracts import RuntimeLoginHandoff, RuntimeLoginMethod
from .test_runtime_admission import _OwnedClient

if TYPE_CHECKING:
    from textual.app import AutopilotCallbackType

    from ..app import RootBindingV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _registry() -> OperationRegistry:
    definitions = build_automation_operation_definitions()
    return OperationRegistry(
        definitions=definitions,
        public_registrations=tuple(
            sorted(build_automation_operation_registrations(definitions), key=lambda row: row.contract.definition_id)
        ),
    )


def _recognized_inventory(profile_id: UUID) -> ProfileLoginInventoryV1:
    return ProfileLoginInventoryV1(
        state=ProfileLoginInventoryState.RECOGNIZED,
        choices=(ProfileLoginChoice(profile_id=str(profile_id), label="Synthetic profile"),),
        preselected_profile_id=str(profile_id),
    )


def _bootstrap(monkeypatch: pytest.MonkeyPatch, observations: Iterator[ProfileLoginInventoryV1]) -> None:
    monkeypatch.setattr(installed_session, "profile_adapter_composition", nullcontext)
    monkeypatch.setattr(installed_session, "close_active_profile_record_session", lambda: None)
    monkeypatch.setattr(installed_session, "close_active_bucket_session", lambda: None)
    monkeypatch.setattr(installed_session, "observe_profile_login_inventory", lambda: next(observations))
    monkeypatch.setattr(installed_session, "installed_automation_secret_store", MemoryNativePort)


def _session_callbacks(
    monkeypatch: pytest.MonkeyPatch,
    profile_id: UUID,
    requester: Literal["none", "login", "api", "api_reference", "human"],
) -> list[_ObservedRequester]:
    client = _OwnedClient(profile_id)
    method = (
        RuntimeLoginMethod.API_KEY
        if requester == "api"
        else RuntimeLoginMethod.API_REFERENCE
        if requester == "api_reference"
        else RuntimeLoginMethod.PASSWORD
    )
    if method is RuntimeLoginMethod.PASSWORD:
        status = client.login_password(bytearray(b"synthetic-proof"))
    else:
        client._session_id = uuid4()
        status = client.status()
    handoff = RuntimeLoginHandoff(
        profile_id=profile_id,
        profile_label="Synthetic profile",
        method=method,
        status=status,
        client=client,
    )
    screens: list[_ObservedRequester] = []

    def observe_screen(**options: object) -> _ObservedRequester:
        screen = _ObservedRequester(
            profile_id=cast(UUID, options["profile_id"]),
            contracts=cast(OperationPublicContractSetV1, options["contracts"]),
            secrets_store=cast(AutomationSecretStore, options["secrets_store"]),
            client=cast(FrontendClient | None, options.get("client")),
            open_client=cast(RequesterClientOpener | None, options.get("open_client")),
            fresh_credential_client=cast(FreshCredentialClientOpener | None, options.get("fresh_credential_client")),
            reviewer_client=cast(FrontendClient | None, options.get("reviewer_client")),
        )
        screens.append(screen)
        return screen

    @asynccontextmanager
    async def login(**options: object) -> AsyncGenerator[RuntimeLoginHandoff | None]:
        try:
            if requester == "login":
                factory = cast(RuntimeRequesterFactory, options["requester_factory"])
                factory(profile_id)
                factory(profile_id)
                yield None
            else:
                yield handoff
        finally:
            client.close()

    class Root:
        def __init__(
            self,
            bound: FrontendClient,
            *,
            requester_factory: Callable[[FrontendClient], RuntimeAutomationRequesterScreen],
            **_options: object,
        ) -> None:
            assert bound is client
            if requester == "human":
                requester_factory(client)
                requester_factory(client)

        def load(self) -> RootBindingV1:
            raise AssertionError("the contract test must not load private views")

    class Restricted:
        def __init__(
            self,
            bound: FrontendClient,
            *,
            requester_factory: Callable[[FrontendClient], RuntimeAutomationRequesterScreen],
            **_options: object,
        ) -> None:
            assert bound is client
            requester_factory(client)
            requester_factory(client)

        async def run_async(self, **_options: object) -> None:
            return None

    async def run_root(**_options: object) -> None:
        return None

    monkeypatch.setattr(installed_session, "RuntimeAutomationRequesterScreen", observe_screen)
    monkeypatch.setattr(installed_session, "runtime_login_session", login)
    monkeypatch.setattr(installed_session, "RuntimeWorkbenchRoot", Root)
    monkeypatch.setattr(installed_session, "run_precomposed_runtime_root_session", run_root)
    monkeypatch.setattr(runtime_session, "RuntimeRestrictedSessionApp", Restricted)
    return screens


class _ObservedRequester(RuntimeAutomationRequesterScreen):
    """Retain the exact supplied contract while running the real admission/setup."""

    @override
    def __init__(
        self,
        *,
        profile_id: UUID,
        contracts: OperationPublicContractSetV1,
        secrets_store: AutomationSecretStore,
        client: FrontendClient | None = None,
        open_client: RequesterClientOpener | None = None,
        fresh_credential_client: FreshCredentialClientOpener | None = None,
        reviewer_client: FrontendClient | None = None,
        journey_timeout: float = 300,
    ) -> None:
        super().__init__(
            profile_id=profile_id,
            contracts=contracts,
            secrets_store=secrets_store,
            client=client,
            open_client=open_client,
            fresh_credential_client=fresh_credential_client,
            reviewer_client=reviewer_client,
            journey_timeout=journey_timeout,
        )
        self.received_contracts = contracts


@pytest.mark.parametrize("scenario", ["empty", "registration", "headless", "human"])
def test_sessions_without_a_requester_do_not_build_the_operation_registry(
    monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    profile_id = uuid4()
    empty = ProfileLoginInventoryV1(state=ProfileLoginInventoryState.EMPTY)
    inventory = _recognized_inventory(profile_id)
    observations = (
        (empty, inventory) if scenario == "registration" else (empty,) if scenario == "empty" else (inventory,)
    )
    _bootstrap(monkeypatch, iter(observations))
    screens = _session_callbacks(monkeypatch, profile_id, "none")
    registrations = 0

    def register() -> bool:
        nonlocal registrations
        registrations += 1
        return scenario == "registration"

    def refuse_build() -> OperationRegistry:
        raise AssertionError("ordinary installed session built requester contracts")

    monkeypatch.setattr(installed_session, "_run_registration_screen", register)
    monkeypatch.setattr(operation_composition, "build_manifest_operation_registry", refuse_build)
    assert installed_session.run_installed_workbench_session(headless=scenario == "headless") == 0
    assert screens == []
    assert registrations == (1 if scenario in {"empty", "registration"} else 0)


@pytest.mark.parametrize("requester", ["login", "api", "api_reference", "human"])
def test_each_requester_receives_the_same_fully_validated_public_contract_set(
    monkeypatch: pytest.MonkeyPatch, requester: Literal["login", "api", "api_reference", "human"]
) -> None:
    profile_id = uuid4()
    _bootstrap(monkeypatch, iter((_recognized_inventory(profile_id),)))
    screens = _session_callbacks(monkeypatch, profile_id, requester)
    registry = _registry()
    builds = 0

    def build() -> OperationRegistry:
        nonlocal builds
        builds += 1
        return registry

    monkeypatch.setattr(operation_composition, "build_manifest_operation_registry", build)
    assert installed_session.run_installed_workbench_session() == 0
    assert builds == 1 and len(screens) == 2
    screen = screens[0]
    assert screen.received_contracts is registry.public_contract_set
    assert screens[1].received_contracts is screen.received_contracts
    assert screen.received_contracts.contract_set_digest == registry.public_contract_set.contract_set_digest
    assert screen._profile_id == profile_id
    if requester == "login":
        assert screen._client is None and screen._reviewer_client is None
        assert screen._open_client is installed_session._open_client
    elif requester == "human":
        assert screen._client is None and screen._reviewer_client is not None
        assert screen._open_client is installed_session._open_client
    else:
        assert screen._client is not None and screen._reviewer_client is None
        assert screen._fresh_credential_client is not None and screen._open_client is None


@pytest.mark.parametrize("state", [ProfileLoginInventoryState.DEGRADED, ProfileLoginInventoryState.CONCURRENT_CHANGE])
def test_unavailable_inventory_preserves_refusal_without_building_requester_contracts(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], state: ProfileLoginInventoryState
) -> None:
    reason = "profile.inventory.fixture_refusal"
    _bootstrap(monkeypatch, iter((ProfileLoginInventoryV1(state=state, reason_code=reason),)))
    offered: list[str] = []

    def refuse_build() -> OperationRegistry:
        raise AssertionError("unavailable inventory built requester contracts")

    def offer_installation_area(reason_code: str) -> bool:
        offered.append(reason_code)
        return False

    monkeypatch.setattr(operation_composition, "build_manifest_operation_registry", refuse_build)
    monkeypatch.setattr(installed_session, "_run_installation_area", offer_installation_area)
    assert installed_session.run_installed_workbench_session() == installed_session.SESSION_INVENTORY_UNAVAILABLE
    assert capsys.readouterr().err.strip() == reason
    # The acts that can repair an installation need no profile, so they are offered before giving up.
    assert offered == [reason]


def test_an_unlistable_inventory_is_read_again_after_the_installation_area_changed_records(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    profile_id = uuid4()
    degraded = ProfileLoginInventoryV1(
        state=ProfileLoginInventoryState.DEGRADED, reason_code="profile.inventory.fixture_refusal"
    )
    _bootstrap(monkeypatch, iter((degraded, _recognized_inventory(profile_id))))
    screens = _session_callbacks(monkeypatch, profile_id, "none")
    monkeypatch.setattr(installed_session, "_run_installation_area", lambda _reason: True)

    assert installed_session.run_installed_workbench_session() == installed_session.SESSION_COMPLETED
    assert capsys.readouterr().err == "" and screens == []


def test_a_headless_run_never_opens_the_installation_area(monkeypatch: pytest.MonkeyPatch) -> None:
    degraded = ProfileLoginInventoryV1(
        state=ProfileLoginInventoryState.DEGRADED, reason_code="profile.inventory.fixture_refusal"
    )
    _bootstrap(monkeypatch, iter((degraded,)))

    def refuse_area(_reason: str) -> bool:
        raise AssertionError("a headless run opened an interactive area")

    monkeypatch.setattr(installed_session, "_run_installation_area", refuse_area)
    assert (
        installed_session.run_installed_workbench_session(headless=True)
        == installed_session.SESSION_INVENTORY_UNAVAILABLE
    )


def test_the_profiles_are_read_again_when_the_sign_in_screen_closed_after_an_installation_act(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = uuid4()
    observed: list[ProfileLoginInventoryV1] = []
    inventories = iter((_recognized_inventory(profile_id), _recognized_inventory(profile_id)))

    def observe() -> ProfileLoginInventoryV1:
        observed.append(next(inventories))
        return observed[-1]

    _bootstrap(monkeypatch, iter(()))
    monkeypatch.setattr(installed_session, "observe_profile_login_inventory", observe)
    preselections: list[str | None] = []

    @asynccontextmanager
    async def login(**options: object) -> AsyncGenerator[RuntimeLoginHandoff | None]:
        preselections.append(cast("str | None", options["preselected"]))
        if len(preselections) == 1:
            build_area = cast("Callable[[Callable[[], None]], InstallationScreen]", options["installation_factory"])
            closed: list[bool] = []
            area = build_area(lambda: closed.append(True))
            assert isinstance(area, InstallationScreen)
            # What an act that changed records reports, from wherever it ran.
            assert area._on_records_changed is not None
            area._on_records_changed()
            assert closed == [True]
        yield None

    monkeypatch.setattr(installed_session, "runtime_login_session", login)

    assert installed_session.run_installed_workbench_session() == installed_session.SESSION_COMPLETED
    assert len(observed) == 2
    # The second sign-in starts from a choice, not from the profile remembered before the change.
    assert preselections == [str(profile_id), None]


def test_registration_reads_the_profiles_again_when_the_installation_area_changed_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(installed_session, "close_active_profile_record_session", lambda: None)
    monkeypatch.setattr(installed_session, "close_active_bucket_session", lambda: None)
    opened: list[InstallationScreen] = []

    def run_registration(screen: RegistrationScreen) -> None:
        build_area = screen._installation_factory
        assert build_area is not None
        area = build_area(lambda: None)
        assert isinstance(area, InstallationScreen)
        opened.append(area)
        if len(opened) == 2:
            assert area._on_records_changed is not None
            area._on_records_changed()

    monkeypatch.setattr(credentials, "run_credential_screen", run_registration)

    # Abandoned with nothing changed: there is still no profile to sign in to.
    assert installed_session._run_registration_screen() is False
    # Abandoned after an act that may have created or removed profiles: look again.
    assert installed_session._run_registration_screen() is True
    assert len(opened) == 2


def test_the_operation_registry_is_shared_across_recomposition_but_fresh_in_a_separate_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = uuid4()
    _bootstrap(monkeypatch, iter((_recognized_inventory(profile_id),) * 3))
    registries: list[OperationRegistry] = []
    observed: list[OperationRegistry] = []
    choices: list[bool] = []

    def build() -> OperationRegistry:
        registry = _registry()
        registries.append(registry)
        return registry

    def attempt(
        inventory: ProfileLoginInventoryV1,
        supplier: Callable[[], OperationRegistry],
        choose_profile: bool,
        headless: bool,
        auto_pilot: AutopilotCallbackType | None,
    ) -> AccountRecomposeRequiredV1 | None:
        assert inventory.preselected_profile_id == str(profile_id)
        assert not headless and auto_pilot is None
        choices.append(choose_profile)
        first = supplier()
        assert supplier() is first
        observed.append(first)
        return AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.CHANGE_USER) if len(observed) == 1 else None

    monkeypatch.setattr(operation_composition, "build_manifest_operation_registry", build)
    monkeypatch.setattr(installed_session, "_attempt_runtime_session", attempt)
    assert installed_session.run_installed_workbench_session() == 0
    assert len(registries) == 1 and observed[0] is observed[1]
    assert choices == [False, True]
    assert installed_session.run_installed_workbench_session() == 0
    assert len(registries) == 2 and observed[2] is not observed[0]
    assert observed[2].public_contract_set.contract_set_digest == observed[0].public_contract_set.contract_set_digest
    assert choices == [False, True, False]


def test_a_failed_registry_composition_propagates_and_publishes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = uuid4()
    _bootstrap(monkeypatch, iter((_recognized_inventory(profile_id),)))
    complete = _registry()
    builds = 0
    suppliers: list[Callable[[], OperationRegistry]] = []

    def build() -> OperationRegistry:
        nonlocal builds
        builds += 1
        if builds == 1:
            raise InternalInvariantError("no public contract composition")
        return complete

    def attempt(
        inventory: ProfileLoginInventoryV1,
        supplier: Callable[[], OperationRegistry],
        choose_profile: bool,
        headless: bool,
        auto_pilot: AutopilotCallbackType | None,
    ) -> None:
        suppliers.append(supplier)
        supplier()

    monkeypatch.setattr(operation_composition, "build_manifest_operation_registry", build)
    monkeypatch.setattr(installed_session, "_attempt_runtime_session", attempt)
    with pytest.raises(InternalInvariantError, match="no public contract composition"):
        installed_session.run_installed_workbench_session()
    assert builds == 1
    supplier = suppliers[0]
    assert supplier() is complete
    assert supplier() is complete
    assert builds == 2
