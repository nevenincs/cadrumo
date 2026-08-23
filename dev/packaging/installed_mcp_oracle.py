"""Run a grounded tax calculation through an installed Cadrumo MCP server.

The probe launches an absolute ``cadrumo-mcp`` executable over stdio with the
checkout and its scripts directory absent from ``PATH``. It drives only the
public MCP protocol, follows resource links for persisted observations, and
reuses the installed CLI oracle's legal-grounding assertions.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextResourceContents
from pydantic import AnyUrl

from cadrumo.core import scan_directory
from dev._paths import UTF_8

from ._installed_wheel_binding import installed_distribution_payload_sha256
from .installed_tax_oracle import (
    BINDINGS,
    CASILLAS,
    EXPECTED_NOTICE_CODES,
    EXPECTED_VALUE,
    MODEL,
    PERIOD,
    PROFILE_LABEL,
    PROFILE_TAX_ID,
    REGISTRY_REVISION,
    RELATIONS,
    TARGET_CASILLA,
    YEAR,
    assert_envelope_contract,
    assert_grounded_observations,
    assert_no_diagnostic_notices,
    checkout_imports_removed,
    isolated_product_environment,
)

_UTF_8: Final[str] = UTF_8

_REVISION_ID = re.compile(r"^[0-9a-f]{64}$")
_EXECUTE_TOOL = "execute"
_TOOLSETS_TOOL = "toolsets"
_WHOAMI_TOOL = "cadrumo_whoami"
_WORK_CALCULATE_TOOL = "cadrumo_modelo_work_calculate"
_ATTESTED_COMMAND_KEYS = frozenset(
    {
        "config.profile.create",
        "modelo.work.create",
        "modelo.work.calculate",
        "modelo.work.observations",
    },
)


class InstalledMcpOracleError(RuntimeError):
    """Raised when installed MCP behavior does not satisfy the release oracle."""


@dataclass(frozen=True)
class McpCallEvidence:
    """One public MCP tool call retained by the installed oracle."""

    tool_name: str
    command_key: str | None
    duration_seconds: float
    is_error: bool
    status: str | None


@dataclass(frozen=True)
class InstalledMcpEvidence:
    """Evidence proving installed MCP calculation and resource behavior."""

    requested_executable: str
    resolved_executable: str
    server_name: str
    storage_root: str
    work_unit_id: str
    calculation_revision_id: str
    observations_resource: str
    target_casilla: str
    target_value: str
    formula_id: str
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    notice_codes: tuple[str, ...]
    advertised_tools: tuple[str, ...]
    calls: tuple[McpCallEvidence, ...]
    invoked_cli_sha256: str
    invoked_cli_sha256_by_command: dict[str, str]
    cohort_source_commit: str
    cohort_manifest_sha256: str
    cohort_root_wheel_sha256: str
    cohort_harness_wheel_sha256: str
    server_executable_sha256: str
    runtime_server_executable: str
    runtime_project_root: str | None
    installed_cli_payload_sha256: str
    installed_harness_payload_sha256: str
    checkout_imports_removed: bool
    ambient_product_executables_removed: bool

    def to_jsonable(self) -> dict[str, Any]:
        """Return a JSON-compatible evidence mapping."""
        return asdict(self)


def minimal_runtime_path() -> str:
    """Return a platform path containing OS utilities but no product scripts."""
    if sys.platform == "win32":
        system_root = Path(os.environ.get("SYSTEMROOT", r"C:\Windows"))
        return str((system_root / "System32").resolve())
    return os.pathsep.join(("/usr/bin", "/bin"))


def isolated_mcp_environment(storage_root: Path) -> dict[str, str]:
    """Build isolated MCP state with product executable discovery disabled."""
    environment = isolated_product_environment(storage_root)
    environment.pop("CADRUMO_MCP_PERSONA", None)
    environment["PATH"] = minimal_runtime_path()
    for executable in ("aeat", "cadrumo-mcp"):
        resolved = shutil.which(executable, path=environment["PATH"])
        if resolved is not None:
            raise InstalledMcpOracleError(
                f"isolated PATH unexpectedly resolves {executable!r}: {resolved}",
            )
    return environment


def profile_create_arguments() -> dict[str, object]:
    """Return named MCP arguments for the installed profile creation."""
    return {
        "profile_name": PROFILE_LABEL,
        "quiet": True,
        "accept_defaults": True,
        "entity_type": "legal_entity",
        "legal_entity_form": "sl",
        "tax_id": PROFILE_TAX_ID,
        "legal_name": "Installed Oracle SL",
        "activity": "software services",
        "incn_prior_12_months": "500000",
        "new_entity_first_two_profit_periods": False,
        "iva_regime": "GENERAL",
        "tax_residence_ccaa": "madrid",
    }


def work_create_arguments() -> dict[str, object]:
    """Return named MCP arguments for the installed Modelo 200 work unit."""
    return {
        "modelo": MODEL,
        "year": int(YEAR),
        "period": PERIOD,
        "revision": REGISTRY_REVISION,
        "name": "Installed Modelo 200 oracle",
        "actor": "installed-mcp-oracle",
    }


def work_calculate_arguments(work_unit_id: str) -> dict[str, object]:
    """Return named MCP arguments for the installed Modelo 200 calculation."""
    return {
        "work_unit_id": work_unit_id,
        "casilla": list(CASILLAS),
        "binding": list(BINDINGS),
        "relation": list(RELATIONS),
        "actor": "installed-mcp-oracle",
    }


def _content_text(result: CallToolResult) -> str:
    return "\n".join(str(getattr(item, "text", "")) for item in result.content)


def _structured(result: CallToolResult, *, operation: str) -> dict[str, Any]:
    if result.is_error:
        raise InstalledMcpOracleError(f"{operation} failed: {_content_text(result)}")
    payload = result.structured_content
    if not isinstance(payload, dict):
        raise InstalledMcpOracleError(f"{operation} returned no structured object")
    return payload


def _assert_envelope(payload: dict[str, Any], *, command_key: str) -> dict[str, Any]:
    return assert_envelope_contract(payload, command=command_key, error=InstalledMcpOracleError)


def _assert_no_diagnostic_notices(payload: dict[str, Any], *, command_key: str) -> None:
    assert_no_diagnostic_notices(payload, command=command_key, error=InstalledMcpOracleError)


async def _call_tool(
    session: ClientSession,
    *,
    tool_name: str,
    arguments: dict[str, object],
    command_key: str | None,
    timeout_seconds: float,
) -> tuple[dict[str, Any], McpCallEvidence]:
    started = time.monotonic()
    async with asyncio.timeout(timeout_seconds):
        result = await session.call_tool(tool_name, arguments)
    payload = _structured(result, operation=command_key or tool_name)
    return (
        payload,
        McpCallEvidence(
            tool_name=tool_name,
            command_key=command_key,
            duration_seconds=round(time.monotonic() - started, 3),
            is_error=bool(result.is_error),
            status=str(payload.get("status")) if payload.get("status") is not None else None,
        ),
    )


async def _execute(
    session: ClientSession,
    command_key: str,
    arguments: dict[str, object],
    *,
    timeout_seconds: float,
) -> tuple[dict[str, Any], McpCallEvidence]:
    return await _call_tool(
        session,
        tool_name=_EXECUTE_TOOL,
        arguments={"command_key": command_key, "arguments": arguments},
        command_key=command_key,
        timeout_seconds=timeout_seconds,
    )


async def _run_protocol(
    server: Path,
    *,
    server_args: Sequence[str],
    environment_overrides: Mapping[str, str],
    storage_root: Path,
    work_dir: Path,
    timeout_seconds: float,
) -> InstalledMcpEvidence:
    environment = isolated_mcp_environment(storage_root)
    environment.update(environment_overrides)
    # Read the isolation facts back off the real environment the server ran in,
    # so the emitted evidence records what isolation actually held. isolated_mcp_environment
    # already raises if a product executable is resolvable on PATH; recompute here so a
    # PATH-restoring override cannot silently forge a clean isolation claim downstream.
    imports_removed = checkout_imports_removed(environment)
    product_executables_removed = all(
        shutil.which(executable, path=environment["PATH"]) is None for executable in ("aeat", "cadrumo-mcp")
    )
    params = StdioServerParameters(
        command=str(server),
        args=list(server_args),
        env=environment,
        cwd=str(work_dir),
        encoding=_UTF_8,
        encoding_error_handler="strict",
    )
    calls: list[McpCallEvidence] = []
    async with (
        stdio_client(params) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        async with asyncio.timeout(timeout_seconds):
            initialized = await session.initialize()
            listed = await session.list_tools()
        floor_tools = tuple(sorted(tool.name for tool in listed.tools))
        if initialized.server_info.name != "cadrumo":
            raise InstalledMcpOracleError(
                f"expected MCP server name 'cadrumo', got {initialized.server_info.name!r}",
            )
        if not {_EXECUTE_TOOL, _TOOLSETS_TOOL, _WHOAMI_TOOL} <= set(floor_tools):
            raise InstalledMcpOracleError(
                f"installed MCP floor lacks required tools: {floor_tools!r}",
            )
        _, call = await _call_tool(
            session,
            tool_name=_TOOLSETS_TOOL,
            arguments={"action": "activate", "name": "modelo-lifecycle"},
            command_key=None,
            timeout_seconds=timeout_seconds,
        )
        calls.append(call)
        async with asyncio.timeout(timeout_seconds):
            listed = await session.list_tools()
        advertised_tools = tuple(sorted(tool.name for tool in listed.tools))
        if _WORK_CALCULATE_TOOL not in advertised_tools:
            raise InstalledMcpOracleError(
                f"installed MCP modelo-lifecycle toolset lacks the direct calculation tool: {advertised_tools!r}",
            )

        profile_payload, call = await _execute(
            session,
            "config.profile.create",
            profile_create_arguments(),
            timeout_seconds=timeout_seconds,
        )
        calls.append(call)
        _assert_envelope(profile_payload, command_key="config.profile.create")
        _assert_no_diagnostic_notices(
            profile_payload,
            command_key="config.profile.create",
        )

        whoami_payload, call = await _call_tool(
            session,
            tool_name=_WHOAMI_TOOL,
            arguments={},
            command_key=None,
            timeout_seconds=timeout_seconds,
        )
        calls.append(call)
        if whoami_payload.get("active_profile") != PROFILE_LABEL:
            raise InstalledMcpOracleError(
                f"whoami returned active profile {whoami_payload.get('active_profile')!r}",
            )
        if whoami_payload.get("tax_id_present") is not True:
            raise InstalledMcpOracleError(
                f"whoami did not confirm the installed profile tax id: {whoami_payload!r}",
            )
        if whoami_payload.get("readiness") != "ready":
            raise InstalledMcpOracleError(
                f"whoami reported readiness {whoami_payload.get('readiness')!r}",
            )

        create_payload, call = await _execute(
            session,
            "modelo.work.create",
            work_create_arguments(),
            timeout_seconds=timeout_seconds,
        )
        calls.append(call)
        create_result = _assert_envelope(create_payload, command_key="modelo.work.create")
        _assert_no_diagnostic_notices(create_payload, command_key="modelo.work.create")
        work_unit_id = str(create_result.get("work_unit_id", ""))
        if not _REVISION_ID.fullmatch(work_unit_id):
            raise InstalledMcpOracleError(
                f"work creation returned an invalid work unit id: {work_unit_id!r}",
            )

        calculate_payload, call = await _call_tool(
            session,
            tool_name=_WORK_CALCULATE_TOOL,
            arguments=work_calculate_arguments(work_unit_id),
            command_key="modelo.work.calculate",
            timeout_seconds=timeout_seconds,
        )
        calls.append(call)
        calculate_result = _assert_envelope(
            calculate_payload,
            command_key="modelo.work.calculate",
        )
        if calculate_result.get("saved") is not True:
            raise InstalledMcpOracleError("calculation did not report saved=true")
        calculation_revision_id = str(calculate_result.get("calculation_revision_id", ""))
        if not _REVISION_ID.fullmatch(calculation_revision_id):
            raise InstalledMcpOracleError(
                f"calculation returned an invalid revision id: {calculation_revision_id!r}",
            )
        casilla_values = calculate_result.get("casilla_values")
        if not isinstance(casilla_values, dict) or Decimal(str(casilla_values.get(TARGET_CASILLA))) != EXPECTED_VALUE:
            raise InstalledMcpOracleError(
                f"calculation expected {TARGET_CASILLA}={EXPECTED_VALUE}, got {casilla_values!r}",
            )
        notices = calculate_payload["notices"]
        notice_codes = {str(notice.get("code")) for notice in notices}
        if notice_codes != EXPECTED_NOTICE_CODES:
            raise InstalledMcpOracleError(
                f"calculation notices expected {sorted(EXPECTED_NOTICE_CODES)!r}, got {sorted(notice_codes)!r}",
            )
        if any(notice.get("severity") != "warning" for notice in notices):
            raise InstalledMcpOracleError(f"calculation notice severity drifted: {notices!r}")
        calculate_observations_resource = str(
            calculate_result.get("observations_resource", ""),
        )
        expected_observations_resource = f"cadrumo://observations/{calculation_revision_id}"
        if calculate_observations_resource != expected_observations_resource:
            raise InstalledMcpOracleError(
                "calculation returned an observation resource for a different revision: "
                f"{calculate_observations_resource!r}",
            )
        calculate_observations_count = calculate_result.get("observations_count")
        if not isinstance(calculate_observations_count, int) or calculate_observations_count <= 0:
            raise InstalledMcpOracleError("calculation reported no persisted observations")

        observations_payload, call = await _execute(
            session,
            "modelo.work.observations",
            {"calculation_revision_id": calculation_revision_id},
            timeout_seconds=timeout_seconds,
        )
        calls.append(call)
        observations_result = _assert_envelope(
            observations_payload,
            command_key="modelo.work.observations",
        )
        _assert_no_diagnostic_notices(
            observations_payload,
            command_key="modelo.work.observations",
        )
        if observations_result.get("calculation_revision_id") != calculation_revision_id:
            raise InstalledMcpOracleError(
                "persisted observations returned a different calculation revision",
            )
        if observations_result.get("work_unit_id") != work_unit_id:
            raise InstalledMcpOracleError(
                "persisted observations returned a different work unit",
            )
        observations_resource = str(
            observations_result.get("observations_resource", ""),
        )
        if observations_resource != calculate_observations_resource:
            raise InstalledMcpOracleError(
                "calculation and persisted-observations calls returned different resources",
            )
        observations_count = observations_result.get("observations_count")
        observation_count = observations_result.get("observation_count")
        if (
            not isinstance(observations_count, int)
            or observations_count != calculate_observations_count
            or observation_count != observations_count
        ):
            raise InstalledMcpOracleError(
                f"persisted observation counts drifted: {observations_result!r}",
            )

        async with asyncio.timeout(timeout_seconds):
            resource = await session.read_resource(str(AnyUrl(observations_resource)))
        if len(resource.contents) != 1 or not isinstance(resource.contents[0], TextResourceContents):
            raise InstalledMcpOracleError(
                f"observations resource returned unexpected contents: {resource.contents!r}",
            )
        if str(resource.contents[0].uri) != expected_observations_resource:
            raise InstalledMcpOracleError(
                f"observations resource contents identified a different URI: {resource.contents[0].uri!r}",
            )
        try:
            observations = json.loads(resource.contents[0].text)
        except json.JSONDecodeError as exc:
            raise InstalledMcpOracleError("observations resource did not return JSON") from exc
        if not isinstance(observations, list):
            raise InstalledMcpOracleError("observations resource did not return a JSON array")
        if len(observations) != observations_count:
            raise InstalledMcpOracleError(
                f"observations resource count drifted: expected {observations_count}, got {len(observations)}",
            )
        persisted_result = dict(observations_result)
        persisted_result["observations"] = observations
        target = assert_grounded_observations(
            persisted_result,
            calculation_revision_id=calculation_revision_id,
            work_unit_id=work_unit_id,
        )

    return InstalledMcpEvidence(
        requested_executable=str(server),
        resolved_executable=str(server.resolve()),
        server_name=initialized.server_info.name,
        storage_root=str(storage_root.resolve()),
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        observations_resource=observations_resource,
        target_casilla=TARGET_CASILLA,
        target_value=str(EXPECTED_VALUE),
        formula_id=str(target["formula_id"]),
        legal_refs=tuple(str(value) for value in target["legal_refs"]),
        source_refs=tuple(str(value) for value in target["source_refs"]),
        notice_codes=tuple(sorted(notice_codes)),
        advertised_tools=advertised_tools,
        calls=tuple(calls),
        invoked_cli_sha256="",
        invoked_cli_sha256_by_command={},
        cohort_source_commit="",
        cohort_manifest_sha256="",
        cohort_root_wheel_sha256="",
        cohort_harness_wheel_sha256="",
        server_executable_sha256="",
        runtime_server_executable="",
        runtime_project_root=None,
        installed_cli_payload_sha256="",
        installed_harness_payload_sha256="",
        checkout_imports_removed=imports_removed,
        ambient_product_executables_removed=product_executables_removed,
    )


def _observed_cli_attestation(storage_root: Path) -> tuple[str, dict[str, str]]:
    telemetry_files = scan_directory(storage_root.resolve() / "telemetry", pattern="*.jsonl")
    if len(telemetry_files) != 1:
        raise InstalledMcpOracleError(
            f"expected one MCP telemetry session, got {[path.name for path in telemetry_files]!r}",
        )
    executable_by_command: dict[str, str] = {}
    for line in telemetry_files[0].read_text(encoding=_UTF_8).splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise InstalledMcpOracleError("MCP telemetry row is not a JSON object")
        command_key = row.get("command_key")
        if command_key not in _ATTESTED_COMMAND_KEYS:
            continue
        if command_key in executable_by_command:
            raise InstalledMcpOracleError(f"duplicate MCP telemetry attestation for {command_key!r}")
        executable_sha256 = str(row.get("executable_sha256", ""))
        if not _REVISION_ID.fullmatch(executable_sha256):
            raise InstalledMcpOracleError(
                f"MCP telemetry did not attest the child executable for {command_key!r}",
            )
        executable_by_command[command_key] = executable_sha256
    observed_command_keys = frozenset(executable_by_command)
    if observed_command_keys != _ATTESTED_COMMAND_KEYS:
        raise InstalledMcpOracleError(
            "MCP telemetry command coverage drifted: "
            f"expected {sorted(_ATTESTED_COMMAND_KEYS)!r}, got {sorted(observed_command_keys)!r}",
        )
    executable_hashes = set(executable_by_command.values())
    if len(executable_hashes) != 1:
        raise InstalledMcpOracleError(
            f"MCP calls used different child executable identities: {sorted(executable_hashes)!r}",
        )
    return executable_hashes.pop(), dict(sorted(executable_by_command.items()))


def run_installed_mcp_oracle(
    server: Path,
    *,
    server_args: Sequence[str] = (),
    environment_overrides: Mapping[str, str] | None = None,
    storage_root: Path,
    work_dir: Path,
    cohort_source_commit: str,
    cohort_manifest_sha256: str,
    cohort_root_wheel_sha256: str,
    cohort_harness_wheel_sha256: str,
    timeout_seconds: float = 180.0,
) -> InstalledMcpEvidence:
    """Execute the complete installed MCP oracle and return retained evidence."""
    requested_server = server.expanduser()
    resolved_server = requested_server.resolve(strict=True)
    if not resolved_server.is_file():
        raise InstalledMcpOracleError(f"installed MCP server is not a file: {resolved_server}")
    resolved_work_dir = work_dir.resolve()
    resolved_work_dir.mkdir(parents=True, exist_ok=True)
    evidence = asyncio.run(
        _run_protocol(
            resolved_server,
            server_args=server_args,
            environment_overrides=environment_overrides or {},
            storage_root=storage_root,
            work_dir=resolved_work_dir,
            timeout_seconds=timeout_seconds,
        ),
    )
    invoked_cli_sha256, invoked_cli_sha256_by_command = _observed_cli_attestation(storage_root)
    runtime_server = resolved_server
    runtime_project_root: str | None = None
    if resolved_server.stem.lower() != "cadrumo-mcp":
        try:
            project_index = tuple(server_args).index("--project") + 1
        project = Path(server_args[project_index]).resolve(strict=True)
        runtime_project_root = str(project)
        except (ValueError, IndexError) as exc:
            raise InstalledMcpOracleError(
                "wrapped MCP launch must declare its exact runtime project with --project",
            ) from exc
        scripts = project / ".venv" / ("Scripts" if os.name == "nt" else "bin")
        runtime_server = (scripts / ("cadrumo-mcp.exe" if os.name == "nt" else "cadrumo-mcp")).resolve(strict=True)
    sibling_cli = runtime_server.with_name("aeat.exe" if runtime_server.suffix.lower() == ".exe" else "aeat")
    return replace(
        evidence,
        invoked_cli_sha256=invoked_cli_sha256,
        invoked_cli_sha256_by_command=invoked_cli_sha256_by_command,
        cohort_source_commit=cohort_source_commit,
        cohort_manifest_sha256=cohort_manifest_sha256,
        cohort_root_wheel_sha256=cohort_root_wheel_sha256,
        cohort_harness_wheel_sha256=cohort_harness_wheel_sha256,
        server_executable_sha256=hashlib.sha256(runtime_server.read_bytes()).hexdigest(),
        runtime_server_executable=str(runtime_server),
        runtime_project_root=runtime_project_root,
        installed_cli_payload_sha256=installed_distribution_payload_sha256(sibling_cli, "cadrumo"),
        installed_harness_payload_sha256=installed_distribution_payload_sha256(
            runtime_server, "cadrumo-harness"
        ),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--server",
        required=True,
        type=Path,
        help="Absolute installed cadrumo-mcp executable.",
    )
    parser.add_argument(
        "--storage-root",
        required=True,
        type=Path,
        help="Fresh isolated product storage root.",
    )
    parser.add_argument(
        "--work-dir",
        required=True,
        type=Path,
        help="Execution cwd outside the source checkout.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--cohort-source-commit", required=True)
    parser.add_argument("--cohort-manifest-sha256", required=True)
    parser.add_argument("--cohort-root-wheel-sha256", required=True)
    parser.add_argument("--cohort-harness-wheel-sha256", required=True)
    parser.add_argument("--output", type=Path, help="Optional JSON evidence destination.")
    return parser


def main() -> int:
    """Run the installed MCP oracle from the command line."""
    args = _parser().parse_args()
    evidence = run_installed_mcp_oracle(
        args.server,
        storage_root=args.storage_root,
        work_dir=args.work_dir,
        cohort_source_commit=args.cohort_source_commit,
        cohort_manifest_sha256=args.cohort_manifest_sha256,
        cohort_root_wheel_sha256=args.cohort_root_wheel_sha256,
        cohort_harness_wheel_sha256=args.cohort_harness_wheel_sha256,
        timeout_seconds=args.timeout_seconds,
    )
    rendered = json.dumps(evidence.to_jsonable(), ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding=_UTF_8, newline="\n")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
