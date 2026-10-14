"""Each ``config provision`` leaf and the operation that serves the same work return the same result.

The command line runs its work in process and needs no session. The terminal
interface reaches the same work through a registered operation.
Each case runs the leaf through its real handler, then submits the equivalent
request to the real executor and supervisor, composed with the adapters
production binds, against the same real loopback runtime state, and compares
the leaf's JSON envelope with the operation's result rendered the way the
command line renders it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import typer
from pydantic import BaseModel

from ....adapters.persistence.operations.tests.local_reader_operation_support import (
    TEXT_MODEL,
    VISION_MODEL,
    loopback_model_runtime,
    run_supervised_in,
)
from ....application.browser_runtime_operation import BrowserRuntimeProvisionPublicResultV1
from ....application.local_reader_contracts import (
    LocalReaderProvisionPublicResultV2,
    build_local_reader_install_request,
    build_local_reader_load_request,
    build_local_reader_pull_request,
    build_local_reader_remove_request,
    build_local_reader_setup_request,
    build_local_reader_start_request,
    build_local_reader_verify_request,
)
from ....application.local_reader_report import LocalReaderReportPublicResultV1
from ....application.local_reader_status_operation import LocalReaderStatusPublicResultV1
from ....application.operations.models import OperationRequest
from ....application.operations.registry import OperationRegistry
from ....application.provisioning_browser import required_browser_builds
from ....application.provisioning_runtime import forget_runtime_unreachable
from ....application.tests.local_reader_operation_requests import (
    build_browser_runtime_provision_request,
    build_local_reader_report_request,
    build_local_reader_status_request,
)
from ....core.config import override_settings
from ....core.model_catalogue import ModelRole
from ...local_reader_operation_composition import build_local_reader_operations
from ..command_specs import COMMAND_GRAPH
from ..config import provision_cli
from ..config.provision_payloads import ProvisionProbeResult, ProvisionStatusResult
from .provision_rendering_support import RenderedLeaf, render_leaf

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BEYOND_ANY_HOST_BYTES = 1 << 60

#: Readings taken at the moment of each run: how long a call took and how much
#: memory was free. Two runs of one function never agree on them.
_MEASURED_AT_RUN_TIME = frozenset(
    {
        "elapsed_ms",
        "free_vram_bytes",
        "free_system_memory_bytes",
        "binding_free_bytes",
        "shortfall_bytes",
        "peer_attributed_bytes",
    }
)


@dataclass(frozen=True, slots=True)
class _Case:
    """One leaf invocation and the operation request that asks for the same work."""

    leaf: str
    arguments: Mapping[str, Any]
    request: Callable[[], OperationRequest[Any]]
    result_type: type[BaseModel]
    emit: Callable[[typer.Context, Any], None]
    installed: frozenset[str] = frozenset()
    residents: frozenset[str] = frozenset()
    runtime: Mapping[str, Any] = field(default_factory=dict)


def _emit_status(ctx: typer.Context, result: Any) -> None:
    provision_cli.emit_provision_status(
        ctx, result, command="config.provision.status", result_type=ProvisionStatusResult
    )


def _emit_probe(ctx: typer.Context, result: Any) -> None:
    provision_cli.emit_provision_status(ctx, result, command="config.provision.probe", result_type=ProvisionProbeResult)


def _emit_setup(ctx: typer.Context, result: Any) -> None:
    provision_cli.emit_provision_setup(ctx, result, install_consented=False)


_TEXT = ModelRole.TEXT_EXTRACTION
_VISION = ModelRole.VISION_TRANSCRIPTION
_PROVISION = LocalReaderProvisionPublicResultV2
_CASES: dict[str, _Case] = {
    "status": _Case(
        "status",
        {},
        lambda: build_local_reader_status_request(probe=False),
        LocalReaderStatusPublicResultV1,
        _emit_status,
        installed=frozenset({TEXT_MODEL}),
    ),
    "probe": _Case(
        "probe",
        {},
        lambda: build_local_reader_status_request(probe=True),
        LocalReaderStatusPublicResultV1,
        _emit_probe,
        installed=frozenset({TEXT_MODEL, VISION_MODEL}),
    ),
    "report": _Case(
        "report",
        {},
        build_local_reader_report_request,
        LocalReaderReportPublicResultV1,
        provision_cli.emit_provision_report,
        installed=frozenset({TEXT_MODEL}),
        residents=frozenset({TEXT_MODEL}),
    ),
    "install": _Case(
        "install",
        {"confirm": False},
        lambda: build_local_reader_install_request(consent=False),
        _PROVISION,
        provision_cli.emit_provision_install,
    ),
    "start": _Case("start", {}, build_local_reader_start_request, _PROVISION, provision_cli.emit_provision_start),
    "pull": _Case("pull", {}, build_local_reader_pull_request, _PROVISION, provision_cli.emit_provision_pull),
    "pull-model": _Case(
        "pull",
        {"model": VISION_MODEL, "role": _TEXT},
        lambda: build_local_reader_pull_request(_TEXT, VISION_MODEL),
        _PROVISION,
        provision_cli.emit_provision_pull,
    ),
    "pull-refused-admission": _Case(
        "pull",
        {"model": TEXT_MODEL, "role": _TEXT},
        lambda: build_local_reader_pull_request(_TEXT, TEXT_MODEL),
        _PROVISION,
        provision_cli.emit_provision_pull,
        runtime={"required_headroom_bytes": _BEYOND_ANY_HOST_BYTES},
    ),
    "load": _Case(
        "load",
        {"role": _TEXT},
        lambda: build_local_reader_load_request(_TEXT),
        _PROVISION,
        provision_cli.emit_provision_load,
        installed=frozenset({TEXT_MODEL}),
    ),
    "load-absent": _Case(
        "load",
        {"role": _TEXT},
        lambda: build_local_reader_load_request(_TEXT),
        _PROVISION,
        provision_cli.emit_provision_load,
    ),
    "verify": _Case(
        "verify",
        {"role": _VISION},
        lambda: build_local_reader_verify_request(_VISION),
        _PROVISION,
        provision_cli.emit_provision_verify,
        installed=frozenset({VISION_MODEL}),
        residents=frozenset({VISION_MODEL}),
    ),
    "verify-model": _Case(
        "verify",
        {"model": VISION_MODEL, "role": _VISION},
        lambda: build_local_reader_verify_request(_VISION, VISION_MODEL),
        _PROVISION,
        provision_cli.emit_provision_verify,
        installed=frozenset({VISION_MODEL}),
    ),
    "verify-every-role": _Case(
        "verify",
        {},
        build_local_reader_verify_request,
        _PROVISION,
        provision_cli.emit_provision_verify,
        installed=frozenset({TEXT_MODEL}),
        residents=frozenset({TEXT_MODEL}),
    ),
    "remove": _Case(
        "remove",
        {"role": _TEXT},
        lambda: build_local_reader_remove_request(_TEXT),
        _PROVISION,
        provision_cli.emit_provision_remove,
        installed=frozenset({TEXT_MODEL}),
    ),
    "remove-unselected": _Case(
        "remove",
        {"model": "someone-elses:7b"},
        lambda: build_local_reader_remove_request(model="someone-elses:7b"),
        _PROVISION,
        provision_cli.emit_provision_remove,
        installed=frozenset({TEXT_MODEL}),
    ),
    "setup": _Case(
        "setup",
        {"confirm": False},
        lambda: build_local_reader_setup_request(consent=False),
        _PROVISION,
        _emit_setup,
    ),
    "setup-pull-fails": _Case(
        "setup",
        {"confirm": False},
        lambda: build_local_reader_setup_request(consent=False),
        _PROVISION,
        _emit_setup,
        runtime={"pull_fails": True},
    ),
    "browser": _Case(
        "browser",
        {},
        build_browser_runtime_provision_request,
        BrowserRuntimeProvisionPublicResultV1,
        provision_cli.emit_provision_browser,
    ),
}


def _production_registry() -> OperationRegistry:
    operations = build_local_reader_operations()
    return OperationRegistry(
        definitions=tuple(sorted(operations.definitions, key=lambda item: item.definition_id)),
        public_registrations=tuple(sorted(operations.registrations, key=lambda item: item.contract.definition_id)),
    )


def _stable(value: object) -> object:
    """Return ``value`` with every reading taken at run time replaced by a marker of its presence."""
    if isinstance(value, dict):
        return {
            key: ("<measured>" if key in _MEASURED_AT_RUN_TIME and item is not None else _stable(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_stable(item) for item in value]
    return value


@pytest.fixture
def browser_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Give both runs one complete browser cache of their own, off the host's real one."""
    builds = required_browser_builds()
    assert builds is not None
    cache = tmp_path / "browsers"
    for build in builds:
        (cache / build.directory_name).mkdir(parents=True)
        (cache / build.directory_name / "INSTALLATION_COMPLETE").write_bytes(b"")
    monkeypatch.setenv("CADRUMO_PLAYWRIGHT_BROWSERS_DIR", str(cache))
    return cache


def _through_the_command_line(case: _Case, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> RenderedLeaf:
    handler = getattr(provision_cli, f"provision_{case.leaf}")
    with (
        loopback_model_runtime(installed=set(case.installed), residents=set(case.residents), **case.runtime),
        override_settings(cadrumo_local_storage_root=tmp_path / "command-line"),
    ):
        forget_runtime_unreachable()
        return render_leaf(lambda ctx: handler(ctx, **case.arguments), output_format="json", capsys=capsys)


def _through_the_operation(case: _Case, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> RenderedLeaf:
    with loopback_model_runtime(installed=set(case.installed), residents=set(case.residents), **case.runtime):
        forget_runtime_unreachable()
        settled = run_supervised_in(tmp_path / "operation", _production_registry(), case.request(), case.result_type)
    return render_leaf(lambda ctx: case.emit(ctx, settled.result), output_format="json", capsys=capsys)


def test_the_cases_cover_every_provisioning_leaf() -> None:
    leaves = {node.path[-1] for node in COMMAND_GRAPH.nodes() if node.path[1:3] == ("config", "provision")}

    assert {case.leaf for case in _CASES.values()} == leaves - {"provision"}


@pytest.mark.usefixtures("browser_cache")
@pytest.mark.parametrize("name", sorted(_CASES))
def test_a_leaf_and_its_operation_return_the_same_result(
    name: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    case = _CASES[name]
    with override_settings(cadrumo_output_language="en"):
        command_line = _through_the_command_line(case, tmp_path, capsys)
        operation = _through_the_operation(case, tmp_path, capsys)

    assert command_line.envelope["command"] == f"config.provision.{case.leaf}"
    assert command_line.exit_code == operation.exit_code
    assert _stable(command_line.envelope) == _stable(operation.envelope)
