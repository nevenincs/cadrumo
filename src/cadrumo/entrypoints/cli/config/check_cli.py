"""``aeat config check`` — the authenticated workstation report presenter."""

from __future__ import annotations

import json
from collections.abc import Mapping

import typer

from ....application.operator_actions.models import PreconditionVerdict
from ....application.preflight import PreflightCheck
from ....application.provisioning import DependencyStatus
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.workstation_check_operation import WorkstationCheckProjection
from ....core.i18n.render import tr
from ....core.json_contract import ResolvedPreconditionAction
from ..common import emit_envelope, resolve_cli_precondition_action
from .check_payloads import (
    CheckCapabilityPayload,
    CheckDependencyPayload,
    CheckPreflightPayload,
    ConfigCheckResult,
)
from .runtime_workstation_check import read_workstation_check_for_cli
from .status_rendering import precondition_action_lines


def _restore_facts(values: Mapping[str, object]) -> dict[str, str | int | bool]:
    """Restore only the legacy CLI's closed scalar facts, rejecting new kinds."""
    facts: dict[str, str | int | bool] = {}
    for key, value in values.items():
        if not isinstance(value, (str, int, bool)):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        facts[key] = value
    return facts


def _precondition_action(
    verdict: PreconditionVerdict | None,
) -> ResolvedPreconditionAction | None:
    if verdict is None:
        return None
    return resolve_cli_precondition_action(verdict)


def _dependency_payload(status: DependencyStatus) -> CheckDependencyPayload:
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


def _dependency_text_lines(payload: CheckDependencyPayload) -> tuple[str, ...]:
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
        lines.extend(_dependency_text_lines(dependency))
    for row in preflight:
        lines.append(f"{preflight_label}\t{row.check}\t{row.severity}")
        if row.precondition_action is not None:
            lines.extend(f"{row.check}.{line}" for line in precondition_action_lines(row.precondition_action))
    for issue in issues:
        lines.append(f"{tr('cli.config.check.issue_label')}\t{issue}")
    return tuple(lines)


def _present_report(projection: WorkstationCheckProjection) -> tuple[ConfigCheckResult, tuple[str, ...]]:
    report = projection.to_report()
    if len({row.capability for row in report.capabilities}) != len(report.capabilities):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    capabilities = [
        CheckCapabilityPayload(
            capability=row.capability.value,
            enabled=row.enabled,
            source=row.source.value,
        )
        for row in report.capabilities
    ]
    dependencies = tuple(_dependency_payload(row) for row in report.dependencies)
    preflight = [_preflight_payload(row) for row in report.preflight]
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
    result, lines = _present_report(projection)
    emit_envelope(ctx, command="config.check", result=result, lines=lines)
    if not result.ok:
        raise typer.Exit(code=2)


__all__ = ["config_check"]
