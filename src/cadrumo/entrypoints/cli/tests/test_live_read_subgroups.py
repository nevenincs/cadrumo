"""CLI surface tests for `aeat app live {expedientes, verify, borrador} ...`."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from typer._click.core import Context as ClickContext
from typer.main import get_command

from ....adapters.persistence.storage.tests.seeded_isolated_backend_fixture import seeded_isolated_backend_fixture
from ....application.auth.operator_results import LiveAuthPreflightReport
from ....application.live.errors import LiveIvaAcquisitionFailureMode
from ....application.live.remote_state_models import (
    IvaRemoteStateAcquisitionReport,
    LiveIvaAuthOutcome,
    LiveIvaReadOutcome,
    LiveIvaReadStatus,
    LiveIvaReadSurface,
)
from ....core.config import override_settings
from ....core.period import Period
from .._app_live import (
    _iva_remote_state_capture_lines,
    _live_iva_outcome_label,
)
from .._app_live_auth_preflight import _live_auth_preflight_lines
from .._app_live_command_specs import LIVE_COMMAND_SPECS
from .._command_runtime import build_command_subtree
from .._root_command_specs import ROOT_COMMAND_SPECS
from ..command_spec import CommandSpecGraph
from ._live_read_profile_fixture import _ACTIVE_TEST_BUCKET_ID
from .cli_runner import invoke_cached_cli

#: The world every case here starts from, seeded once and copied per test.
#:
#: Publishing a capsule per test rebuilt the same empty bucket 34 times. The
#: copy keeps each test's storage root private, so the cases that persist an
#: observation or a snapshot still cannot reach the ones that assert a fresh
#: bucket.
_live_read_origin, _isolated_backend = seeded_isolated_backend_fixture(
    seed=lambda: None,
    bucket_id=_ACTIVE_TEST_BUCKET_ID,
    name="_isolated_backend",
    origin_name="_live_read_origin",
)


@pytest.fixture(autouse=True)
def _isolated_live_state(_isolated_backend: None, tmp_path: Path) -> Iterator[None]:
    """Keep the live-state directory private to each test, beside its own root."""
    live_state_dir = tmp_path / "probe-live-state"
    live_state_dir.mkdir(exist_ok=True)
    with override_settings(cadrumo_live_state_dir=live_state_dir):
        yield


__all__ = ["_isolated_backend", "_live_read_origin"]

# INTENTIONAL: integration because it exercises the live-read CLI subgroup wiring and
# error surfaces locally without contacting AEAT.
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LIVE_GRAPH = CommandSpecGraph((*ROOT_COMMAND_SPECS, *LIVE_COMMAND_SPECS))
live_app = build_command_subtree(_LIVE_GRAPH, "app_live")
filed_app = build_command_subtree(_LIVE_GRAPH, "app_live_filed")
iva_wallet_app = build_command_subtree(_LIVE_GRAPH, "app_live_iva_wallet")
notifications_app = build_command_subtree(_LIVE_GRAPH, "app_live_notifications")
portals_app = build_command_subtree(_LIVE_GRAPH, "app_live_portals")
expedientes_app = build_command_subtree(_LIVE_GRAPH, "app_live_expedientes")
justificante_app = build_command_subtree(_LIVE_GRAPH, "app_live_justificante")
verify_app = build_command_subtree(_LIVE_GRAPH, "app_live_verify")
borrador_app = build_command_subtree(_LIVE_GRAPH, "app_live_borrador")
borrador_100_app = build_command_subtree(_LIVE_GRAPH, "app_live_borrador_100")

_FORBIDDEN_LIVE_MUTATION_VERBS = frozenset(
    {
        "submit",
        "send",
        "present",
        "sign",
        "pay",
        "push",
        "modify",
        "rectify",
        "amend",
        "delete",
        "cancel",
        "acknowledge",
        "accept",
        "reject",
        "file",
        "upload",
    }
)


def _registered_cli_name(value: object) -> str:
    """Normalize Typer registration names, including enum-backed subgroup names."""
    return str(getattr(value, "value", value))


def _is_group(command: object) -> bool:
    return callable(getattr(command, "list_commands", None))


def _click_children(typer_app) -> dict[str, Any]:
    """Resolve a subtree's children through the materialized Click group.

    Groups resolve their children lazily, so the Typer registration lists are
    empty; the Click group is the authority on what a subtree contains.
    """
    command = get_command(typer_app)
    if not _is_group(command):
        return {}
    context = ClickContext(command)
    group = cast("Any", command)
    return {name: child for name in group.list_commands(context) if (child := group.get_command(context, name))}


def _click_paths(command: Any, prefix: tuple[str, ...], *, groups_only: bool) -> list[tuple[str, ...]]:
    paths: list[tuple[str, ...]] = []
    if not _is_group(command):
        return paths
    context = ClickContext(command)
    for name in command.list_commands(context):
        child = command.get_command(context, name)
        if child is None:
            continue
        path = (*prefix, name)
        if _is_group(child):
            paths.append(path)
            paths.extend(_click_paths(child, path, groups_only=groups_only))
        elif not groups_only:
            paths.append(path)
    return paths


def _live_registered_paths(typer_app, prefix: tuple[str, ...] = ("live",)) -> tuple[tuple[str, ...], ...]:
    return tuple(_click_paths(get_command(typer_app), prefix, groups_only=False))


def _live_registered_group_paths(typer_app, prefix: tuple[str, ...] = ("live",)) -> tuple[tuple[str, ...], ...]:
    return tuple(_click_paths(get_command(typer_app), prefix, groups_only=True))


def _registered_leaf_names(typer_app) -> set[str]:
    return {name for name, child in _click_children(typer_app).items() if not _is_group(child)}


def _forbidden_mutation_verbs(name: str) -> frozenset[str]:
    normalized = name.lower().replace("_", "-")
    tokens = {normalized, *normalized.split("-")}
    return frozenset(tokens & _FORBIDDEN_LIVE_MUTATION_VERBS)


def _invoke_expedientes(*args: str):
    return invoke_cached_cli(["app", "live", "expedientes", *args])


def test_live_auth_preflight_lines_redact_active_profile_identifier() -> None:
    report = LiveAuthPreflightReport(
        provider="clave_movil",
        configured=True,
        available=True,
        active_profile="operator-private-profile-id",
        active_profile_status="ready",
        persisted_session_present=True,
        persisted_session_expired=False,
        persisted_session_state="live",
    )

    lines = _live_auth_preflight_lines(report)

    assert "auth_active_profile=<profile-id>" in lines
    assert "auth_persisted_session_state=live" in lines
    assert all(not line.startswith("auth_certificate_backend=") for line in lines)
    assert all("operator-private-profile-id" not in line for line in lines)


class TestExpedientesSubgroup:
    def test_expedientes_list_is_empty_on_fresh_bucket(self) -> None:
        result = _invoke_expedientes("list")
        assert result.exit_code == 0, result.output
        assert "count\t0" in result.output

    def test_expedientes_show_refuses_unknown_snapshot(self) -> None:
        result = _invoke_expedientes("view", "no-such-id")
        assert result.exit_code != 0

    def test_expedientes_latest_is_dash_on_fresh_bucket(self) -> None:
        result = _invoke_expedientes("latest")
        assert result.exit_code == 0, result.output
        assert "snapshot_id\t-" in result.output


class TestReadOnlyStructuralInvariants:
    """Reject accidental introduction of any write/submit-style verb on the
    new live subgroups. The live-AEAT charter forbids mutation here."""

    def test_guard_reaches_every_live_read_subgroup(self) -> None:
        subgroup_paths = set(_live_registered_group_paths(live_app))

        assert subgroup_paths == {
            ("live", "filed"),
            ("live", "iva-wallet"),
            ("live", "notifications"),
            ("live", "notifications", "document"),
            ("live", "portals"),
            ("live", "expedientes"),
            ("live", "justificante"),
            ("live", "verify"),
            ("live", "borrador"),
            ("live", "borrador", "100"),
        }

    def test_no_forbidden_mutation_verb_exists_anywhere_in_live_tree(self) -> None:
        offenders: list[str] = []
        for path in _live_registered_paths(live_app):
            for component in path[1:]:
                matched = _forbidden_mutation_verbs(component)
                if matched:
                    offenders.append(f"{'.'.join(path)}:{component}=>{','.join(sorted(matched))}")

        assert offenders == []

    @pytest.mark.parametrize(
        "subgroup_app",
        [
            filed_app,
            iva_wallet_app,
            notifications_app,
            portals_app,
            expedientes_app,
            justificante_app,
            verify_app,
            borrador_app,
            borrador_100_app,
        ],
    )
    def test_no_forbidden_mutation_verb_exists_on_live_subgroup_commands(self, subgroup_app) -> None:
        registered = _registered_leaf_names(subgroup_app)
        offenders = {name: _forbidden_mutation_verbs(name) for name in registered if _forbidden_mutation_verbs(name)}
        assert offenders == {}, f"forbidden write verb on {subgroup_app.info.name}: {offenders}"


class TestIvaRemoteStateCliSurface:
    def test_every_live_iva_outcome_has_operator_label(self) -> None:
        for mode in LiveIvaAcquisitionFailureMode:
            label = _live_iva_outcome_label(mode)

            assert label
            assert "cli.app.live.iva_wallet.acquisition.outcome" not in label
            if mode is not LiveIvaAcquisitionFailureMode.UNKNOWN:
                assert label != _live_iva_outcome_label(LiveIvaAcquisitionFailureMode.UNKNOWN)

    def test_iva_wallet_combined_evidence_command_is_registered_as_read_capture(self) -> None:
        registered = _registered_leaf_names(iva_wallet_app)

        assert "pull-evidence" in registered
        assert "pull-remote-state" not in registered
        assert registered.isdisjoint({"submit", "send", "present", "sign", "pay", "modify"})

    def test_remote_state_lines_render_auth_and_surface_outcomes_with_labels(self) -> None:
        report = IvaRemoteStateAcquisitionReport(
            output_root="live/iva-read-evidence",
            year_from=2022,
            year_to=2024,
            target_year=2026,
            target_period=Period.from_year_and_code(2026, "2T"),
            auth=LiveIvaAuthOutcome(
                status=LiveIvaReadStatus.FAILED,
                outcome_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
                failure_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
                failure_type="ClaveMovilApprovalTimeoutError",
            ),
            filed_history=None,
            wallet=None,
            outcomes=(
                LiveIvaReadOutcome(
                    surface=LiveIvaReadSurface.FILED_HISTORY,
                    status=LiveIvaReadStatus.FAILED,
                    outcome_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
                    failure_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
                    failure_type="ClaveMovilApprovalTimeoutError",
                    failure_context={
                        "progress": {
                            "stage": "walk_declarations_register",
                            "modelo": "303",
                            "ejercicio": 2026,
                        },
                    },
                ),
                LiveIvaReadOutcome(
                    surface=LiveIvaReadSurface.WALLET_CARTERA,
                    status=LiveIvaReadStatus.FAILED,
                    outcome_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
                    failure_mode=LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT,
                    failure_type="ClaveMovilApprovalTimeoutError",
                ),
            ),
        )

        lines = _iva_remote_state_capture_lines(report)

        assert "auth_status=failed" in lines
        assert "auth_outcome=no_clave_prompt" in lines
        no_prompt_label = _live_iva_outcome_label(LiveIvaAcquisitionFailureMode.NO_CLAVE_PROMPT)
        assert f"auth_outcome_label={no_prompt_label}" in lines
        assert "filed_history_succeeded=False" in lines
        assert "wallet_succeeded=False" in lines
        assert any(
            line.startswith("surface_outcome=filed_history\tstatus=failed\toutcome=no_clave_prompt") for line in lines
        )
        assert any(
            "failure_context=progress={ejercicio:2026,modelo:303,stage:walk_declarations_register}" in line
            for line in lines
        )
        assert any(
            line.startswith("surface_outcome=wallet_cartera\tstatus=failed\toutcome=no_clave_prompt") for line in lines
        )
