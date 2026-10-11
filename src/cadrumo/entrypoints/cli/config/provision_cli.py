"""``aeat config provision`` — explicit local-inference lifecycle verbs.

The boundaries between the actions are the design:

* **browser** — downloads the Chromium build browser automation launches, when missing.
* **status** — runtime installation, reachability and each reader role's model. Reads only.
* **probe** — the status, with the text model's fitness checked now; loads that model.
* **report** — measured machine and model-selection state. Reads only.
* **install** — installs the runtime through the platform package manager, only with ``--confirm``.
* **start** — starts an installed local runtime that is not answering.
* **pull** — an explicit model-acquisition operation, every role's model by default.
* **load** — loads pulled models into memory so the first read does not pay the cold start.
* **verify** — a model readiness observation, every role's model by default.
* **remove** — deletes a Cadrumo-selected model from the runtime's store.
* **setup** — install (only with ``--confirm``), start, pull, load and verify as one run.

Every verb runs, in this process, the application function its registered
operation runs for the terminal interface and an agent, and renders the public
result that operation publishes. The work and the result therefore cannot
differ between the three; this module only binds the host adapters, parses the
verb's options and projects the result. Provisioning the machine's runtime
needs no profile session.

**Nothing here is implicit.** No inference path reaches these verbs; an operator
runs them. A model acquisition or runtime install is explicit, never a side
effect of first use. The only process this family starts is the runtime server,
and only when the configured endpoint is this machine.

The pre-fetch admission check is the point of ``pull``. A refusal carries its
typed condition and evidence. Cadrumo never touches a process it does not own.

Core types:
:class:`~cadrumo.core.json_contract.OutputSchema`.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable
from typing import TYPE_CHECKING

import typer

from ....application.provisioning_contracts import ProvisioningPreconditionCondition
from ....core.json_contract import Notice, NoticeSeverity, ResolvedPreconditionAction
from ....core.model_catalogue import ModelRole
from ..common import emit_envelope, resolve_cli_precondition_action
from .provision_payloads import (
    ProvisionBrowserResult,
    ProvisionContentionPayload,
    ProvisionInstallResult,
    ProvisionLastPullPayload,
    ProvisionLoadItemPayload,
    ProvisionLoadResult,
    ProvisionModelPayload,
    ProvisionProbeResult,
    ProvisionPullItemPayload,
    ProvisionPullResult,
    ProvisionRemoveItemPayload,
    ProvisionRemoveResult,
    ProvisionReportResult,
    ProvisionRoleStatusPayload,
    ProvisionRuntimePayload,
    ProvisionSetupModelPayload,
    ProvisionSetupResult,
    ProvisionSetupStepPayload,
    ProvisionStartResult,
    ProvisionStatusResult,
    ProvisionVerifyItemPayload,
    ProvisionVerifyResult,
)
from .status_rendering import precondition_action_lines

if TYPE_CHECKING:
    from ....application.browser_runtime_operation import BrowserRuntimeProvisionPublicResultV1
    from ....application.local_reader_contracts import (
        LocalReaderContentionV1,
        LocalReaderFactV1,
        LocalReaderModelOutcomeV2,
        LocalReaderProvisionPublicResultV2,
        LocalReaderProvisionRequest,
    )
    from ....application.local_reader_report import LocalReaderReportPublicResultV1
    from ....application.local_reader_status_operation import (
        LocalReaderRoleStatusV1,
        LocalReaderStatusPublicResultV1,
    )
    from ....application.operations.models import OperationRequest
    from ....application.operator_actions.models import PreconditionVerdict

__all__ = [
    "emit_provision_browser",
    "emit_provision_install",
    "emit_provision_load",
    "emit_provision_pull",
    "emit_provision_remove",
    "emit_provision_report",
    "emit_provision_setup",
    "emit_provision_start",
    "emit_provision_status",
    "emit_provision_verify",
    "provision_browser",
    "provision_install",
    "provision_load",
    "provision_probe",
    "provision_pull",
    "provision_remove",
    "provision_report",
    "provision_setup",
    "provision_start",
    "provision_status",
    "provision_verify",
]


def provision_status(ctx: typer.Context) -> None:
    """Report the local runtime and each reader role's model from recorded verdicts."""
    emit_provision_status(
        ctx, _read_status(probe=False), command="config.provision.status", result_type=ProvisionStatusResult
    )


def provision_probe(ctx: typer.Context) -> None:
    """Report the local reader with the text model's fitness checked now, loading that model."""
    emit_provision_status(
        ctx, _read_status(probe=True), command="config.provision.probe", result_type=ProvisionProbeResult
    )


def provision_install(ctx: typer.Context, confirm: bool = False) -> None:
    """Install the local runtime through the platform package manager when ``--confirm`` is given."""
    from ....application.local_reader_contracts import build_local_reader_install_request

    emit_provision_install(ctx, _provision(build_local_reader_install_request(consent=confirm)))


def provision_browser(ctx: typer.Context) -> None:
    """Download the Chromium build browser automation launches when it is missing."""
    from ....adapters.outbound.browser_runtime.installer import run_browser_installer
    from ....application.browser_runtime_operation import browser_runtime_public_result
    from ....application.provisioning_browser import install_playwright_browser

    emit_provision_browser(ctx, browser_runtime_public_result(install_playwright_browser(run=run_browser_installer)))


def provision_start(ctx: typer.Context) -> None:
    """Start the installed local runtime when it is not already answering."""
    from ....application.local_reader_contracts import build_local_reader_start_request

    emit_provision_start(ctx, _provision(build_local_reader_start_request()))


def provision_remove(
    ctx: typer.Context,
    model: str | None = None,
    role: ModelRole | None = None,
) -> None:
    """Remove the named model, or the named role's model, from the local runtime's store."""
    from ....application.local_reader_contracts import build_local_reader_remove_request

    if model is None and role is None:
        raise typer.BadParameter("--model or --role is required", param_hint="--model/--role")
    emit_provision_remove(ctx, _provision(build_local_reader_remove_request(role, model)))


def provision_report(ctx: typer.Context) -> None:
    """Report the measured hardware, the per-role model selection, and admission."""
    from ....application.local_reader_report import local_reader_report_public_result, read_local_reader_report

    emit_provision_report(ctx, local_reader_report_public_result(read_local_reader_report()))


def provision_pull(
    ctx: typer.Context,
    model: str | None = None,
    role: ModelRole | None = None,
) -> None:
    """Fetch a model, refusing before any bytes move when the load is not admitted."""
    from ....application.local_reader_contracts import build_local_reader_pull_request

    emit_provision_pull(ctx, _provision(build_local_reader_pull_request(role, model)))


def provision_verify(
    ctx: typer.Context,
    model: str | None = None,
    role: ModelRole | None = None,
) -> None:
    """Confirm a model is resident and answers a trivial prompt within a bound."""
    from ....application.local_reader_contracts import build_local_reader_verify_request

    emit_provision_verify(ctx, _provision(build_local_reader_verify_request(role, model)))


def provision_load(
    ctx: typer.Context,
    model: str | None = None,
    role: ModelRole | None = None,
) -> None:
    """Load pulled models into memory, refusing before the load when it is not admitted."""
    from ....application.local_reader_contracts import build_local_reader_load_request

    emit_provision_load(ctx, _provision(build_local_reader_load_request(role, model)))


def provision_setup(ctx: typer.Context, confirm: bool = False) -> None:
    """Install (with ``--confirm``), start, pull, load and verify the local reader in one run."""
    from ....application.local_reader_contracts import build_local_reader_setup_request

    emit_provision_setup(ctx, _provision(build_local_reader_setup_request(consent=confirm)), install_consented=confirm)


def _provision(request: OperationRequest[LocalReaderProvisionRequest]) -> LocalReaderProvisionPublicResultV2:
    """Run one provisioning request with the host's process and fitness adapters and publish its outcome."""
    from ....adapters.outbound.llm.role_fitness import probe_text_extraction_fitness
    from ....adapters.outbound.model_runtime.process_control import run_runtime_installer, spawn_runtime_server
    from ....application.local_reader_contracts import local_reader_public_result
    from ....application.local_reader_provisioning import provision_local_reader

    return local_reader_public_result(
        asyncio.run(
            provision_local_reader(
                request.payload,
                spawn=spawn_runtime_server,
                run_installer=run_runtime_installer,
                text_probe=probe_text_extraction_fitness,
            )
        )
    )


def _read_status(*, probe: bool) -> LocalReaderStatusPublicResultV1:
    """Measure the local reader and publish the measurement. Records nothing.

    Without ``probe`` text-model fitness is the verdict ``verify`` recorded for
    the model's current weights, so ``status`` never spends a model load.
    ``probe`` runs the check now and reports it without recording it.
    """
    from ....application.local_reader import read_local_reader_status
    from ....application.local_reader_status_operation import local_reader_status_public_result

    if probe:
        from ....adapters.outbound.llm.role_fitness import probe_text_extraction_fitness

        return local_reader_status_public_result(read_local_reader_status(text_probe=probe_text_extraction_fitness))
    return local_reader_status_public_result(read_local_reader_status())


def _licence_notices(advisories: Iterable[str]) -> tuple[Notice, ...]:
    return tuple(
        Notice(severity=NoticeSeverity.WARNING, code="provisioning.model.licence.non_commercial", message=message)
        for message in dict.fromkeys(advisories)
    )


def _model_licence_notices(result: LocalReaderProvisionPublicResultV2) -> tuple[Notice, ...]:
    return _licence_notices(message for item in result.models for message in item.licence_advisories)


def _action(verdict: PreconditionVerdict | None) -> ResolvedPreconditionAction | None:
    """Resolve an optional verdict through the shared action resolver."""
    return resolve_cli_precondition_action(verdict) if verdict is not None else None


def _reader_action(
    condition_id: str | None, verdict_facts: tuple[LocalReaderFactV1, ...]
) -> ResolvedPreconditionAction | None:
    """Resolve the refusal a reader result names by its condition and evidence facts."""
    from ....application.local_reader_contracts import local_reader_public_verdict

    return _action(local_reader_public_verdict(condition_id, verdict_facts))


def _reader_facts(facts: tuple[LocalReaderFactV1, ...]) -> dict[str, str | int | bool]:
    from ....application.local_reader_contracts import local_reader_fact_mapping

    return local_reader_fact_mapping(facts)


def _contention_payload(contention: LocalReaderContentionV1 | None) -> ProvisionContentionPayload | None:
    """Project a contention verdict onto its payload, preserving the cause set."""
    if contention is None:
        return None
    return ProvisionContentionPayload(
        model=contention.model,
        admitted=contention.admitted,
        causes=list(contention.causes),
        required_bytes=contention.required_bytes,
        free_vram_bytes=contention.free_vram_bytes,
        free_system_memory_bytes=contention.free_system_memory_bytes,
        shortfall_bytes=contention.shortfall_bytes,
        unloadable_models=list(contention.unloadable_models),
        facts=_reader_facts(contention.facts),
        precondition_action=_reader_action(contention.verdict_condition_id, contention.verdict_facts),
    )


def _roles(item: LocalReaderModelOutcomeV2) -> list[str]:
    return [role.value for role in item.roles]


def _item_action(item: LocalReaderModelOutcomeV2) -> ResolvedPreconditionAction | None:
    return _reader_action(item.verdict_condition_id, item.verdict_facts)


def emit_provision_load(ctx: typer.Context, outcome: LocalReaderProvisionPublicResultV2) -> None:
    """Emit the load envelope, exiting 2 unless every resolved model is loaded."""
    items = [
        ProvisionLoadItemPayload(
            model=item.model,
            roles=_roles(item),
            loaded=item.succeeded,
            already_loaded=item.already_satisfied,
            elapsed_ms=item.elapsed_ms,
            facts=_reader_facts(item.facts),
            precondition_action=_item_action(item),
        )
        for item in outcome.models
    ]
    result = ProvisionLoadResult(loaded=outcome.succeeded, models=items)
    emit_envelope(
        ctx,
        command="config.provision.load",
        result=result,
        lines=_provision_result_lines(result),
        notices=_model_licence_notices(outcome),
    )
    if not result.loaded:
        raise typer.Exit(code=2)


def emit_provision_setup(
    ctx: typer.Context, outcome: LocalReaderProvisionPublicResultV2, *, install_consented: bool
) -> None:
    """Emit the one-shot setup's per-step envelope, exiting 2 when a step stopped it."""
    result = ProvisionSetupResult(
        succeeded=outcome.succeeded,
        stopped_step=None if outcome.stopped_step is None else outcome.stopped_step.value,
        steps=[
            ProvisionSetupStepPayload(
                step=step.step.value,
                state=step.state.value,
                failed_condition_id=step.failed_condition_id,
            )
            for step in outcome.steps
        ],
        runtime_started=outcome.runtime_started,
        install_consented=install_consented,
        models=[
            ProvisionSetupModelPayload(
                step=item.step.value,
                model=item.model,
                roles=_roles(item),
                succeeded=item.succeeded,
                already_satisfied=item.already_satisfied,
                bytes_fetched=item.bytes_fetched,
                elapsed_ms=item.elapsed_ms,
                facts=_reader_facts(item.facts),
                precondition_action=_item_action(item),
            )
            for item in outcome.models
            if item.step is not None
        ],
        facts=_reader_facts(outcome.facts),
        precondition_action=_reader_action(outcome.verdict_condition_id, outcome.verdict_facts),
    )
    emit_envelope(
        ctx,
        command="config.provision.setup",
        result=result,
        lines=_provision_result_lines(result),
        notices=_model_licence_notices(outcome),
    )
    if not result.succeeded:
        raise typer.Exit(code=2)


def _provision_result_lines(result: object) -> tuple[str, ...]:
    """Render the exact graph-resolved result DTO without recovery prose.

    The field names are schema identities, not human-authored guidance. Every
    value comes from the exact object emitted in JSON, so the text path cannot
    retain a second English detail or command hint.
    """
    from ....core.json_contract import OutputSchema, ResolvedPreconditionAction

    if not isinstance(result, OutputSchema):  # pragma: no cover - defensive boundary guard
        raise TypeError("provisioning text rendering requires a graph-declared output schema")
    document = result.model_dump(mode="json")
    lines: list[str] = []
    for field_name, value in document.items():
        if field_name != "precondition_action":
            lines.append(
                f"{field_name}\t{json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}",
            )
            continue
        if value is not None:
            action = getattr(result, "precondition_action", None)
            if not isinstance(action, ResolvedPreconditionAction):  # pragma: no cover - defensive boundary guard
                raise TypeError("provisioning precondition action does not match the graph-resolved result DTO")
            lines.extend(precondition_action_lines(action))
    return tuple(lines)


def emit_provision_report(ctx: typer.Context, report: LocalReaderReportPublicResultV1) -> None:
    """Emit the measured hardware, the per-role model selection and the admission verdict."""
    result = ProvisionReportResult(
        accelerator=report.accelerator.value,
        total_vram_bytes=report.total_vram_bytes,
        free_vram_bytes=report.free_vram_bytes,
        total_system_memory_bytes=report.total_system_memory_bytes,
        free_system_memory_bytes=report.free_system_memory_bytes,
        runtime_reachable=report.runtime_reachable,
        residents=list(report.residents),
        models=[
            ProvisionModelPayload(
                role=row.role.value,
                model=row.model,
                selected=row.selected,
                resident=row.resident,
                facts=_reader_facts(row.facts),
                precondition_action=_reader_action(row.verdict_condition_id, row.verdict_facts),
            )
            for row in report.models
        ],
        contention=_contention_payload(report.contention),
    )
    emit_envelope(
        ctx,
        command="config.provision.report",
        result=result,
        lines=_provision_result_lines(result),
    )


def emit_provision_pull(ctx: typer.Context, outcome: LocalReaderProvisionPublicResultV2) -> None:
    """Emit the pull envelope, exiting 2 unless every resolved model was fetched."""
    items = [
        ProvisionPullItemPayload(
            model=item.model,
            roles=_roles(item),
            pulled=item.succeeded,
            bytes_fetched=item.bytes_fetched,
            contention=_contention_payload(item.contention),
            facts=_reader_facts(item.facts),
            precondition_action=_item_action(item),
        )
        for item in outcome.models
    ]
    result = ProvisionPullResult(pulled=outcome.succeeded, models=items)
    emit_envelope(
        ctx,
        command="config.provision.pull",
        result=result,
        lines=_provision_result_lines(result),
        notices=_model_licence_notices(outcome),
    )
    if not result.pulled:
        raise typer.Exit(code=2)


def emit_provision_verify(ctx: typer.Context, outcome: LocalReaderProvisionPublicResultV2) -> None:
    """Emit the verify envelope, exiting 2 unless every resolved model is ready.

    Readiness includes each served role's fitness probe, so a model that loads
    and answers but cannot produce the text reader's answer is refused here.
    """
    items = [
        ProvisionVerifyItemPayload(
            model=item.model,
            roles=_roles(item),
            ready=item.succeeded,
            resident=item.resident,
            answered=item.answered,
            elapsed_ms=item.elapsed_ms,
            facts=_reader_facts(item.facts),
            precondition_action=_item_action(item),
        )
        for item in outcome.models
    ]
    result = ProvisionVerifyResult(ready=outcome.succeeded, models=items)
    emit_envelope(
        ctx,
        command="config.provision.verify",
        result=result,
        lines=_provision_result_lines(result),
        notices=_model_licence_notices(outcome),
    )
    if not result.ready:
        raise typer.Exit(code=2)


def emit_provision_status(
    ctx: typer.Context,
    status: LocalReaderStatusPublicResultV1,
    *,
    command: str,
    result_type: type[ProvisionStatusResult],
) -> None:
    """Emit the local reader's status envelope under ``command``."""
    host = status.host
    last = status.last_pull
    result = result_type(
        runtime=ProvisionRuntimePayload(
            platform=host.platform.value,
            endpoint_url=host.endpoint_url,
            endpoint_local=host.endpoint_local,
            executable_located=host.executable_located,
            reachable=host.reachable,
            version=host.version,
            installer=host.installer.value,
            facts=_reader_facts(host.facts),
            precondition_action=_reader_action(host.verdict_condition_id, host.verdict_facts),
        ),
        roles=[
            ProvisionRoleStatusPayload(
                role=row.role.value,
                model=row.model,
                installed=row.installed,
                resident=row.resident,
                load_admitted=row.load_admitted,
                contention_causes=list(row.contention_causes),
                fitness=row.fitness,
                fit_for_role=row.fit_for_role,
                ready=row.ready,
                failed_condition_id=row.failed_condition_id,
            )
            for row in status.roles
        ],
        last_pull=(
            None
            if last is None
            else ProvisionLastPullPayload(
                model=last.model,
                pulled=last.pulled,
                attempted_at=last.attempted_at.isoformat(),
                bytes_fetched=last.bytes_fetched,
                failed_condition_id=last.failed_condition_id,
            )
        ),
        extraction_ready=status.extraction_ready,
        document_readiness=status.document_readiness,
        text_layer_model_fill_available=status.text_layer_model_fill_available,
    )
    lines = (*_provision_result_lines(result), *_fitness_condition_lines(status.roles))
    emit_envelope(ctx, command=command, result=result, lines=lines)


#: The fitness conditions a status row can fail on, with the sentence that says
#: what each means. "Not verified" and "timed out" must never read as "unfit".
_FITNESS_CONDITION_LOCALE_KEYS: dict[str, str] = {
    ProvisioningPreconditionCondition.ROLE_MODEL_FITNESS_VERIFIED.value: (
        "provisioning.condition.role_model_fitness_verified"
    ),
    ProvisioningPreconditionCondition.ROLE_MODEL_FITNESS_WITHIN_TIMEOUT.value: (
        "provisioning.condition.role_model_fitness_within_timeout"
    ),
    ProvisioningPreconditionCondition.ROLE_MODEL_FIT_FOR_ROLE.value: "provisioning.condition.role_model_fit_for_role",
}


def _fitness_condition_lines(rows: tuple[LocalReaderRoleStatusV1, ...]) -> tuple[str, ...]:
    """Render each role's failed fitness condition as its localized explanation."""
    from ....core.i18n.render import tr

    return tuple(
        f"{row.role.value}\t{tr(_FITNESS_CONDITION_LOCALE_KEYS[row.failed_condition_id], model=row.model or '-')}"
        for row in rows
        if row.failed_condition_id in _FITNESS_CONDITION_LOCALE_KEYS
    )


def emit_provision_install(ctx: typer.Context, outcome: LocalReaderProvisionPublicResultV2) -> None:
    """Emit the install envelope, exiting 2 unless the runtime is installed."""
    install = outcome.install
    if install is None:  # pragma: no cover - the install action always records its outcome
        raise AssertionError
    result = ProvisionInstallResult(
        installed=install.installed,
        already_installed=install.already_installed,
        installer=install.installer.value,
        consented=install.consented,
        installer_exit_code=install.installer_exit_code,
        facts=_reader_facts(outcome.facts),
        precondition_action=_reader_action(outcome.verdict_condition_id, outcome.verdict_facts),
    )
    emit_envelope(ctx, command="config.provision.install", result=result, lines=_provision_result_lines(result))
    if not install.installed:
        raise typer.Exit(code=2)


def emit_provision_start(ctx: typer.Context, outcome: LocalReaderProvisionPublicResultV2) -> None:
    """Emit the start envelope, exiting 2 unless the runtime answers."""
    result = ProvisionStartResult(
        running=outcome.succeeded,
        already_running=outcome.already_running,
        started_pid=outcome.started_pid,
        facts=_reader_facts(outcome.facts),
        precondition_action=_reader_action(outcome.verdict_condition_id, outcome.verdict_facts),
    )
    emit_envelope(ctx, command="config.provision.start", result=result, lines=_provision_result_lines(result))
    if not result.running:
        raise typer.Exit(code=2)


def emit_provision_remove(ctx: typer.Context, outcome: LocalReaderProvisionPublicResultV2) -> None:
    """Emit the remove envelope, exiting 2 unless every removal was confirmed."""
    items = [
        ProvisionRemoveItemPayload(
            model=item.model,
            roles=_roles(item),
            removed=item.succeeded,
            was_installed=item.was_installed,
            freed_bytes=item.freed_bytes,
            facts=_reader_facts(item.facts),
            precondition_action=_item_action(item),
        )
        for item in outcome.models
    ]
    result = ProvisionRemoveResult(removed=outcome.succeeded, models=items)
    emit_envelope(ctx, command="config.provision.remove", result=result, lines=_provision_result_lines(result))
    if not result.removed:
        raise typer.Exit(code=2)


def emit_provision_browser(ctx: typer.Context, outcome: BrowserRuntimeProvisionPublicResultV1) -> None:
    """Emit the browser provisioning envelope, exiting 2 unless the build is installed."""
    result = ProvisionBrowserResult(
        installed=outcome.installed,
        already_installed=outcome.already_installed,
        installer_exit_code=outcome.installer_exit_code,
        facts=_reader_facts(outcome.facts),
        precondition_action=_reader_action(outcome.verdict_condition_id, outcome.verdict_facts),
    )
    emit_envelope(ctx, command="config.provision.browser", result=result, lines=_provision_result_lines(result))
    if not outcome.installed:
        raise typer.Exit(code=2)
