"""The refusal to run, the read-only catalogue, and the wall between product and listener."""

from __future__ import annotations

import ast
import configparser
import os
import sys
from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.config import Settings
from cadrumo.entrypoints.cli.tests.live_command_validation import resolve_path
from dev.acceptance.aeat_request_capture import __main__ as command
from dev.acceptance.aeat_request_capture import live_flows
from dev.acceptance.aeat_request_capture.flows import READ_FLOWS, UnknownFlowSelectorError, select_flows
from dev.packaging.command_execution import CommandResult, run_command
from dev.paths import REPO_ROOT, UTF_8

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SUBPROCESS_TIMEOUT_SECONDS: Final = 240
_PACKAGE: Final = "dev.acceptance.aeat_request_capture"
_LISTENER: Final = f"{_PACKAGE}.listener"
_SHIPPED_ROOTS: Final = ("cadrumo", "cadrumo_client", "cadrumo_runtime", "cadrumo_mcp")
_ALL_ROOTS: Final = (*_SHIPPED_ROOTS, "dev", "docs")
_CONTRACT: Final = "importlinter:contract:shipped-code-never-reaches-repository-only"


def _run(*arguments: str, env: dict[str, str] | None = None) -> CommandResult:
    return run_command(
        [sys.executable, *arguments],
        cwd=REPO_ROOT,
        environment=env if env is not None else dict(os.environ),
        timeout_seconds=_SUBPROCESS_TIMEOUT_SECONDS,
        errors="replace",
    )


def _capture_directories() -> set[Path]:
    return set((REPO_ROOT / ".tmp").glob("*aeat-request-capture*"))


def test_a_run_without_the_flag_refuses_before_loading_any_product_or_browser_code() -> None:
    before = _capture_directories()
    probe = (
        f"import sys\nfrom {_PACKAGE}.__main__ import main\ncode = main(['run'])\n"
        "loaded = [name for name in ('playwright', 'cadrumo') if name in sys.modules]\n"
        "assert not loaded, loaded\nsys.exit(code)\n"
    )

    result = _run("-c", probe)

    assert result.returncode == command.EXIT_REFUSED, result.stderr
    assert command.LIVE_FLAG in result.stderr
    assert "nothing was started" in result.stderr
    assert _capture_directories() == before


def test_a_flagged_run_without_credentials_refuses_before_any_browser() -> None:
    before = _capture_directories()
    env = {
        **os.environ,
        "CADRUMO_CLAVE_MOVIL_DNI_NIE": "",
        "CADRUMO_CLAVE_MOVIL_NIE_SOPORTE": "",
    }

    result = _run("-m", _PACKAGE, "run", command.LIVE_FLAG, env=env)

    assert result.returncode == command.EXIT_REFUSED, result.stderr
    assert "CADRUMO_CLAVE_MOVIL_DNI_NIE" in result.stderr
    assert _capture_directories() == before


def test_the_plan_lists_every_flow_with_its_command_and_why_it_reads_only() -> None:
    result = _run("-m", _PACKAGE, "plan")

    assert result.returncode == command.EXIT_OK, result.stderr
    for flow in READ_FLOWS:
        assert flow.flow_id in result.stdout
        assert flow.cli_command in result.stdout
        assert flow.read_only_because in result.stdout


@pytest.mark.parametrize(
    "selector",
    [
        "aeat app live notifications document pull",
        "app live notifications document pull",
        "aeat app modelo file",
        "aeat app live",
        "notification-document",
    ],
)
def test_anything_but_a_listed_read_flow_is_refused_as_a_selector(selector: str) -> None:
    with pytest.raises(UnknownFlowSelectorError):
        select_flows((selector,))
    assert command.main(["plan", "--select", selector]) == command.EXIT_REFUSED


def test_a_selector_resolves_by_id_command_or_lane_test_and_brings_the_login() -> None:
    by_id = select_flows(("notifications",))
    by_command = select_flows(("aeat app live notifications pull",))
    by_short_command = select_flows(("app live notifications pull",))
    by_lane = select_flows((READ_FLOWS[4].lane_tests[0],))

    assert [flow.flow_id for flow in by_id] == ["clave-movil-login", "notifications"]
    assert by_id == by_command == by_short_command == by_lane
    assert [flow.flow_id for flow in select_flows(("groi",))] == ["groi"]


def test_every_flow_has_a_driver_and_names_real_policies() -> None:
    known = {policy.id for policy in live_flows.guard_policies(Settings())}

    assert {flow.flow_id for flow in READ_FLOWS} == set(live_flows.LIVE_DRIVERS)
    for flow in READ_FLOWS:
        assert flow.policy_ids
        assert set(flow.policy_ids) <= known, flow.flow_id


def test_every_named_aeat_command_resolves_in_the_live_cli() -> None:
    for flow in READ_FLOWS:
        executable, *tokens = flow.cli_command.split()
        if executable == "aeat":
            assert resolve_path(tuple(tokens)).resolved_path == tuple(tokens), flow.cli_command


def test_every_named_lane_test_exists_and_is_marked_live() -> None:
    for flow in READ_FLOWS:
        for lane_test in flow.lane_tests:
            relative, _, name = lane_test.partition("::")
            source = (REPO_ROOT / relative).read_text(encoding=UTF_8)
            assert f"def {name}(" in source, lane_test
            assert "pytest.mark.aeat_live" in source, lane_test


def _names_used_by(module_path: Path) -> set[str]:
    tree = ast.parse(module_path.read_text(encoding=UTF_8))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.add(node.name)
    return names


def test_the_live_drivers_cannot_reach_a_writing_or_unread_opening_call() -> None:
    used = _names_used_by(Path(live_flows.__file__))

    forbidden = {
        "fetch_notification_document",
        "assert_notification_content_readable",
        "notification_detail_url",
        "require_live_write",
        "SubmissionEngine",
        "click",
        "goto",
        "request",
        "post",
    }
    assert used.isdisjoint(forbidden), used & forbidden


def test_the_notification_reader_used_here_issues_no_post_and_clicks_no_row() -> None:
    from cadrumo.adapters.outbound.aeat.sede import notifications

    tree = ast.parse(Path(notifications.__file__).read_text(encoding=UTF_8))
    readers = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
        and node.name in {"fetch_notifications_query", "_fetch_and_parse", "navigate_and_parse"}
    }

    assert set(readers) == {"fetch_notifications_query", "_fetch_and_parse", "navigate_and_parse"}
    for reader in readers.values():
        attributes = {node.attr for node in ast.walk(reader) if isinstance(node, ast.Attribute)}
        assert attributes.isdisjoint({"click", "post", "request", "fill"}), reader.name


def test_no_product_source_names_the_capture_package() -> None:
    offenders = [
        str(path)
        for path in (REPO_ROOT / "src").rglob("*.py")
        if "aeat_request_capture" in path.read_text(encoding=UTF_8, errors="replace")
    ]

    assert offenders == []


def _plant_tree(root: Path, *, offending_module: str) -> None:
    for package in _ALL_ROOTS:
        (root / package).mkdir()
        (root / package / "__init__.py").write_text("", encoding=UTF_8)
    listener_parts = _LISTENER.split(".")
    current = root
    for part in listener_parts[:-1]:
        current = current / part
        current.mkdir(exist_ok=True)
        (current / "__init__.py").write_text("", encoding=UTF_8)
    (current / f"{listener_parts[-1]}.py").write_text("", encoding=UTF_8)
    (root / "cadrumo" / "planted.py").write_text(f"import {offending_module}\n", encoding=UTF_8)


def _gate_over(tree: Path) -> CommandResult:
    authority = configparser.ConfigParser()
    authority.read(REPO_ROOT / ".importlinter", encoding=UTF_8)
    planted = configparser.ConfigParser()
    planted["importlinter"] = {
        "root_packages": "\n".join(_ALL_ROOTS),
        "include_external_packages": "False",
        "exclude_type_checking_imports": "False",
    }
    planted[_CONTRACT] = dict(authority[_CONTRACT])
    config = tree / "gate.ini"
    with config.open("w", encoding=UTF_8) as handle:
        planted.write(handle)
    lint_imports = Path(sys.executable).with_name("lint-imports")
    env = {**os.environ, "PYTHONPATH": str(tree), "PYTHONIOENCODING": UTF_8}
    return run_command(
        [str(lint_imports), "--config", str(config), "--no-cache"],
        cwd=tree,
        environment=env,
        timeout_seconds=_SUBPROCESS_TIMEOUT_SECONDS,
        errors="replace",
    )


def test_a_product_import_of_the_listener_fails_the_real_import_contract(tmp_path: Path) -> None:
    _plant_tree(tmp_path, offending_module=_LISTENER)

    result = _gate_over(tmp_path)

    assert result.returncode != 0, result.stdout
    assert "BROKEN" in result.stdout
    assert "cadrumo.planted" in result.stdout


def test_the_same_contract_passes_without_that_import_so_the_failure_is_the_import(tmp_path: Path) -> None:
    _plant_tree(tmp_path, offending_module="os")

    result = _gate_over(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
