"""``aeat config check`` — the authenticated workstation report presenter.

The workstation report runs inside the profile worker, which holds no runtime
connection, so its setup rows are read here: one quick ``dependencies.status``
read through this command's own runtime connection, rendered as one
``setup:<item>`` preflight row per registry row. When that read is refused or
the runtime cannot be reached, the report says so in one typed notice and
shows no setup rows; nothing here starts or manages the runtime.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

import typer

from cadrumo_client.commands.errors import CliOperationStillRunningError, CliRefusedBoundaryError
from cadrumo_client.commands.profile_binding import bound_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ....application.dependency_contracts import DependencyCheckMode, DependencyStatusRow
from ....application.dependency_setup_operation import (
    DEPENDENCIES_OPERATION_SUBJECT,
    DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID,
    DependencyStatusRequest,
    DependencyStatusResultV1,
)
from ....application.operator_actions.models import PreconditionVerdict
from ....application.preflight import PreflightCheck, dependency_preflight_checks
from ....application.provisioning import DependencyStatus
from ....application.workstation_check_operation import WorkstationCheckProjection
from ....core.i18n.render import tr
from ....core.json_contract import Notice, NoticeSeverity, ResolvedPreconditionAction
from ....core.operations import OperationTerminalCondition
from ..common import emit_envelope, resolve_cli_precondition_action
from .check_payloads import (
    CheckCapabilityPayload,
    CheckDependencyPayload,
    CheckPreflightPayload,
    ConfigCheckResult,
)
from .operation_workstation_check import read_workstation_check_for_cli
from .status_rendering import precondition_action_lines


def _restore_facts(values: Mapping[str, object]) -> dict[str, str | int | bool]:
    """Restore only the legacy CLI's closed scalar facts, rejecting new kinds."""
    facts: dict[str, str | int | bool] = {}
    for key, value in values.items():
        if not isinstance(value, (str, int, bool)):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        facts[key] = value
    return facts


def _precondition_action(
    verdict: PreconditionVerdict | None,
) -> ResolvedPreconditionAction | None:
    if verdict is None:
        return None
    return resolve_cli_precondition_action(verdict)


def dependency_payload(status: DependencyStatus) -> CheckDependencyPayload:
    """Project one canonical dependency row through the existing CLI action resolver."""
    return CheckDependencyPayload(
        service=status.service,
        available=status.available,
        facts=_restore_facts(status.facts),
        precondition_action=_precondition_action(status.precondition_verdict),
    )


def _preflight_payload(status: PreflightCheck) -> CheckPreflightPayload:
    """Project one canonical preflight row without changing its health meaning."""
    return CheckPreflightPayload(
        check=status.check,
        healthy=status.healthy,
        severity=status.severity,
        facts=_restore_facts(status.facts),
        precondition_action=_precondition_action(status.precondition_verdict),
    )


def dependency_text_lines(payload: CheckDependencyPayload) -> tuple[str, ...]:
    """Render one dependency DTO from its facts and resolved outcome."""
    mark = tr("cli.config.check.available" if payload.available else "cli.config.check.missing")
    lines = [f"{tr('cli.config.check.dependency_label')}\t{payload.service}\t{mark}"]
    lines.extend(
        f"{payload.service}.facts.{key}\t{json.dumps(value, ensure_ascii=False, sort_keys=True)}"
        for key, value in sorted(payload.facts.items())
    )
    lines.extend(f"{payload.service}.{line}" for line in precondition_action_lines(payload.precondition_action))
    return tuple(lines)


def _check_text_lines(
    *,
    profile_id: str,
    capabilities: list[CheckCapabilityPayload],
    dependencies: tuple[CheckDependencyPayload, ...],
    preflight: list[CheckPreflightPayload],
    issues: list[str],
) -> tuple[str, ...]:
    """Keep the established human-readable row ordering and labels."""
    lines = [f"{tr('cli.config.check.profile_label')}\t{profile_id}"]
    capability_label = tr("cli.config.check.capability_label")
    preflight_label = tr("cli.config.check.preflight_label")
    for cap in capabilities:
        state = tr(
            "cli.config.profile.capabilities.enabled" if cap.enabled else "cli.config.profile.capabilities.disabled"
        )
        lines.append(f"{capability_label}\t{cap.capability}\t{state}\t{cap.source}")
    for dependency in dependencies:
        lines.extend(dependency_text_lines(dependency))
    for row in preflight:
        lines.append(f"{preflight_label}\t{row.check}\t{row.severity}")
        if row.precondition_action is not None:
            lines.extend(f"{row.check}.{line}" for line in precondition_action_lines(row.precondition_action))
    for issue in issues:
        lines.append(f"{tr('cli.config.check.issue_label')}\t{issue}")
    return tuple(lines)


_SETUP_STATUS_TIMEOUT_S = 60.0


def read_setup_rows(ctx: typer.Context) -> tuple[DependencyStatusRow, ...] | None:
    """Read every setup item's quick check through the runtime, or ``None`` when the runtime refuses or is gone."""
    try:
        completed = run_registered_operation(
            bound_profile_client(ctx),
            DependencyStatusRequest(mode=DependencyCheckMode.QUICK),
            definition_id=DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID,
            subject_ref=DEPENDENCIES_OPERATION_SUBJECT,
            result_type=DependencyStatusResultV1,
            request_version=1,
            result_version=1,
            timeout=_SETUP_STATUS_TIMEOUT_S,
            settlement_timeout=_SETUP_STATUS_TIMEOUT_S,
        )
    except (RefusalError, FrontendRefusedError, CliRefusedBoundaryError, CliOperationStillRunningError):
        return None
    if completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
        return None
    return completed.projection.rows


def _setup_unavailable_notice() -> Notice:
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="config.check.setup_unavailable",
        message=tr("cli.config.check.setup_unavailable"),
    )


def _present_report(
    projection: WorkstationCheckProjection, setup_rows: tuple[DependencyStatusRow, ...] | None = ()
) -> tuple[ConfigCheckResult, tuple[str, ...]]:
    report = projection.to_report()
    if len({row.capability for row in report.capabilities}) != len(report.capabilities):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    capabilities = [
        CheckCapabilityPayload(
            capability=row.capability.value,
            enabled=row.enabled,
            source=row.source.value,
        )
        for row in report.capabilities
    ]
    dependencies = tuple(dependency_payload(row) for row in report.dependencies)
    setup = dependency_preflight_checks(setup_rows or ())
    preflight = [_preflight_payload(row) for row in (*report.preflight, *setup)]
    issues = list(report.issues)
    result = ConfigCheckResult.model_validate(
        {
            "profile_id": str(report.profile_id),
            "ok": not issues,
            "capabilities": capabilities,
            "dependencies": list(dependencies),
            "preflight": preflight,
            "issues": issues,
        },
    )
    lines = _check_text_lines(
        profile_id=str(report.profile_id),
        capabilities=capabilities,
        dependencies=dependencies,
        preflight=preflight,
        issues=issues,
    )
    return result, lines


def config_check(ctx: typer.Context) -> None:
    """Report the authenticated profile's canonical workstation health facts."""
    projection = read_workstation_check_for_cli(ctx)
    setup_rows = read_setup_rows(ctx)
    result, lines = _present_report(projection, setup_rows)
    notices = () if setup_rows is not None else (_setup_unavailable_notice(),)
    emit_envelope(ctx, command="config.check", result=result, lines=lines, notices=notices)
    if not result.ok:
        raise typer.Exit(code=2)


__all__ = ["config_check", "dependency_payload", "dependency_text_lines", "read_setup_rows"]
