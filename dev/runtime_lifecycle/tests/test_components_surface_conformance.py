"""Registered component contracts and desktop vocabulary share the native engine's rows.

Profile-bound runtime surface integration belongs to test_components_review;
these checks cover the public operation catalogue, typed status rows and TUI
presentation, and the native desktop wire vocabulary. MCP has no direct setup
or approval tools. No recorded role conversation is treated as human authority.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Final

import pytest
from textual.widgets import Button

from cadrumo.adapters.outbound.components import client as components_client
from cadrumo.adapters.outbound.components.protocol import ComponentsResultLine, decode_components_line
from cadrumo.application.components_operations import (
    COMPONENTS_SETUP_DEFINITION_ID,
    ProvisionResult,
)
from cadrumo.application.dependency_contracts import (
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyRecoveryAction,
    DependencyStaleReason,
    DependencyState,
)
from cadrumo.application.dependency_wording import dependency_failure_key
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.core.config import override_settings
from cadrumo.core.i18n.render import tr
from cadrumo.core.storage_environment import DEVELOPMENT_ROLE_IMAGE_VARIABLE
from cadrumo.entrypoints.components_operation_composition import build_components_operations, read_component_status
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.setup.screen import SetupScreen
from cadrumo.entrypoints.tui.tests.settling import settle_until
from cadrumo.tests.components_role_dispatch import RoleReplay
from cadrumo.tests.components_role_replay import transcript_lines
from cadrumo_client.contracts.failure_categories import DependencyFailureCategory
from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.hex_entrypoint]
_DESKTOP_WIRE: Final = REPO_ROOT / "native" / "desktop" / "src-tauri" / "src" / "shell" / "setup" / "wire.rs"


@pytest.fixture(name="replay")
def replay_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., RoleReplay]:
    """Replace only the role process while preserving its real protocol parser."""
    image = tmp_path / "cadrumo.exe"
    image.write_bytes(b"")
    monkeypatch.setattr(sys, "_xoptions", {}, raising=False)
    monkeypatch.setenv(DEVELOPMENT_ROLE_IMAGE_VARIABLE, str(image))
    monkeypatch.setenv("CADRUMO_LOCAL_STORAGE_ROOT", str(tmp_path / "root"))

    def answer(**transcripts: Sequence[str]) -> RoleReplay:
        replay = RoleReplay(transcripts)
        monkeypatch.setattr(components_client, "launch_components_role", replay)
        return replay

    return answer


class StatusProjection:
    """Feed the application projection into the renderer without asserting admission."""

    async def read_status(self) -> ProvisionResult:
        return read_component_status()

    async def submit(self, *, verify: bool, items: tuple[object, ...]) -> None:
        raise AssertionError("row presentation must not submit setup")


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "recording", ["status_quick", "status_quick_browser_ready", "status_refused_blocked_by_network"]
)
async def test_registered_status_projection_keeps_native_rows_and_refusal_wording(
    replay: Callable[..., RoleReplay], recording: str
) -> None:
    from typing import cast

    from cadrumo.entrypoints.tui.setup.screen import SetupOperationsPort

    replay(status=[recording])
    (recorded,) = [
        line
        for line in map(decode_components_line, transcript_lines(recording))
        if isinstance(line, ComponentsResultLine)
    ]
    screen = SetupScreen(cast(SetupOperationsPort, StatusProjection()))
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
            await settle_until(pilot, lambda: not screen.query_one("#btn-setup-check", Button).disabled, "typed status")
            assert screen.rows == recorded.status_rows()
            if recorded.failure_category is not None:
                assert tr(dependency_failure_key(recorded.failure_category)) in screen.status_text


@pytest.mark.unit
def test_all_surfaces_share_the_registered_component_contracts() -> None:
    group = build_components_operations()
    registry = OperationRegistry(definitions=group.definitions, public_registrations=group.registrations)
    assert {definition.definition_id for definition in registry.public_contract_set.definitions} == {
        "config.provision.status",
        "config.provision.verify",
        "config.provision.setup",
        "config.provision.remove",
    }
    setup = registry.lookup_public_contract(COMPONENTS_SETUP_DEFINITION_ID)
    assert setup.review_projection_schema is not None
    assert setup.interaction_response_schema is not None


def _wire_enum(source: str, name: str) -> frozenset[str]:
    """The serialised values of one ``snake_case`` serde enum in the desktop host's wire source."""
    match = re.search(rf"pub enum {name} \{{(?P<body>[^}}]*)\}}", source)
    assert match is not None, f"the desktop wire source declares no enum {name}"
    variants = re.findall(r"^\s*([A-Z][A-Za-z0-9]*)\s*[,(]", match.group("body"), flags=re.MULTILINE)
    return frozenset(re.sub(r"(?<!^)(?=[A-Z])", "_", variant).lower() for variant in variants)


@pytest.mark.unit
def test_the_desktop_wire_contract_admits_every_code_a_row_carries() -> None:
    source = _DESKTOP_WIRE.read_text(encoding="utf-8")
    families: dict[str, type[StrEnum]] = {
        "CheckMode": DependencyCheckMode,
        "State": DependencyState,
        "BlockedReason": DependencyBlockedReason,
        "StaleReason": DependencyStaleReason,
        "Failure": DependencyFailureCategory,
        "Recovery": DependencyRecoveryAction,
    }
    # The desktop's own engine is always admitted to provision the local AI, so its rows
    # never carry the recovery that sends a read-only surface to the desktop.
    never_on_the_desktop = {DependencyRecoveryAction.SET_UP_IN_DESKTOP.value}
    for name, family in families.items():
        engine = frozenset(member.value for member in family) - never_on_the_desktop
        assert _wire_enum(source, name) == engine, name


@pytest.mark.unit
def test_the_wire_reader_names_a_code_the_desktop_would_not_admit() -> None:
    fixture = "pub enum State {\n    Absent,\n    Ready,\n}\n"
    assert _wire_enum(fixture, "State") == {"absent", "ready"}
    assert _wire_enum(fixture, "State") != frozenset(member.value for member in DependencyState)
