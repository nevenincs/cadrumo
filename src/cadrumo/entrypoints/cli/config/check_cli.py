"""``aeat config check`` — the authenticated workstation report presenter.

The workstation report runs inside the profile worker, which does not read
component state, so its setup rows are read here: one quick check of the
native component engine's ``components`` role, rendered as one
``setup:<item>`` preflight row per row the role reports. When the role cannot
be started or breaks its protocol, the report says so in one typed notice and
shows no setup rows. A build without the role reads every item as not in this
build.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

import typer

from cadrumo_client.commands.errors import CliOperationStillRunningError, CliRefusedBoundaryError
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from ....application.dependency_contracts import DependencyStatusRow
from ....application.operator_actions.models import PreconditionVerdict
from ....application.preflight import PreflightCheck, dependency_preflight_checks
from ....application.provisioning import DependencyStatus
from ....application.workstation_check_operation import WorkstationCheckProjection
from ....core.i18n.render import tr
from ....core.json_contract import Notice, NoticeSeverity, ResolvedPreconditionAction
from ....core.output_rendering import OutputFormat
from ..common import emit_envelope, format_of, resolve_cli_precondition_action
from ..component_recovery_text import component_recovery_notice
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


def read_setup_rows(ctx: typer.Context) -> tuple[DependencyStatusRow, ...] | None:
    """Read every setup item's quick check from the components role, or ``None`` when the role cannot answer."""
    from .provision_cli import read_quick_setup_rows

    try:
        return read_quick_setup_rows(ctx)
    except (RefusalError, CliOperationStillRunningError, CliRefusedBoundaryError) as error:
        if any(
            error.__dict__.get(field) is not None
            for field in ("async_cleanup_error", "cleanup_error", "_transport_cleanup")
        ):
            raise
        return None


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
    if format_of(ctx) is OutputFormat.JSON:
        for row in result.preflight:
            if not row.check.startswith("setup:"):
                continue
            recovery = component_recovery_notice(row.precondition_action)
            if recovery is not None:
                item = row.check.removeprefix("setup:")
                code = (
                    "config.provision.local_ai_desktop" if item == "local_ai" else "config.provision.browser_recovery"
                )
                notices += (recovery.model_copy(update={"code": code}),)
    emit_envelope(ctx, command="config.check", result=result, lines=lines, notices=notices)
    if not result.ok:
        raise typer.Exit(code=2)


__all__ = ["config_check", "dependency_payload", "dependency_text_lines", "read_setup_rows"]
