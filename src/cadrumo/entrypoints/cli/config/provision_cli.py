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

Install, load, remove and setup run :func:`provision_local_reader`, the same
implementation the TUI's supervised operation wraps, so this module only binds
the host adapters and projects the outcome. Provisioning the machine's runtime
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
from typing import TYPE_CHECKING

import typer

from ....application.provisioning_contracts import ProvisioningPreconditionCondition
from ....core.json_contract import ResolvedPreconditionAction
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
    from ....application.local_reader import LocalReaderRoleStatus, RoleModelTarget
    from ....application.local_reader_operation import (
        LocalReaderModelOutcome,
        LocalReaderProvisionOutcome,
        LocalReaderProvisionRequest,
    )
    from ....application.operations.models import OperationRequest
    from ....application.operator_actions.models import PreconditionVerdict
    from ....application.provisioning import HardwareProfile

__all__ = [
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


def _contention_payload(snapshot: object | None) -> ProvisionContentionPayload | None:
    """Project a contention verdict onto its payload, preserving the cause set."""
    if snapshot is None:
        return None
    from ....application.provisioning_runtime import ContentionSnapshot

    if not isinstance(snapshot, ContentionSnapshot):  # pragma: no cover - defensive
        return None
    return ProvisionContentionPayload(
        model=snapshot.model,
        admitted=snapshot.admitted,
        causes=list(snapshot.causes),
        required_bytes=snapshot.required_bytes,
        free_vram_bytes=snapshot.free_vram_bytes,
        free_system_memory_bytes=snapshot.free_system_memory_bytes,
        shortfall_bytes=snapshot.shortfall_bytes,
        unloadable_models=list(snapshot.unloadable_models),
        facts=snapshot.facts,
        precondition_action=(
            resolve_cli_precondition_action(snapshot.precondition_verdict)
            if snapshot.precondition_verdict is not None
            else None
        ),
    )


def _action(verdict: PreconditionVerdict | None) -> ResolvedPreconditionAction | None:
    """Resolve an optional verdict through the shared action resolver."""
    return resolve_cli_precondition_action(verdict) if verdict is not None else None


def _targets(role: ModelRole | None, model: str | None) -> tuple[RoleModelTarget, ...]:
    """Resolve ``--role``/``--model`` into provisioning targets, every role by default.

    An explicit ``--model`` is honoured as the target for the named role (or
    every role), with the catalogue's requirement used for the admission check,
    because the operator naming a model does not tell us how much memory it
    needs -- the catalogue does.
    """
    from ....application.local_reader import role_model_targets

    return role_model_targets(None if role is None else (role,), explicit_model=model)


def _selection_refusal(target: RoleModelTarget) -> PreconditionVerdict:
    """Return the verdict of a target whose selection refused."""
    if target.selection_verdict is None:  # pragma: no cover - guarded by ModelSelection validation
        raise AssertionError
    return target.selection_verdict


def provision_status(ctx: typer.Context) -> None:
    """Report the local runtime and each reader role's model from recorded verdicts."""
    _emit_local_reader_status(ctx, command="config.provision.status", result_type=ProvisionStatusResult, probe=False)


def provision_probe(ctx: typer.Context) -> None:
    """Report the local reader with the text model's fitness checked now, loading that model."""
    _emit_local_reader_status(ctx, command="config.provision.probe", result_type=ProvisionProbeResult, probe=True)


def provision_install(ctx: typer.Context, confirm: bool = False) -> None:
    """Install the local runtime through the platform package manager when ``--confirm`` is given."""
    _emit_provision_install(ctx, confirm=confirm)


def provision_browser(ctx: typer.Context) -> None:
    """Download the Chromium build browser automation launches when it is missing."""
    _emit_provision_browser(ctx)


def provision_start(ctx: typer.Context) -> None:
    """Start the installed local runtime when it is not already answering."""
    _emit_provision_start(ctx)


def provision_remove(
    ctx: typer.Context,
    model: str | None = None,
    role: ModelRole | None = None,
) -> None:
    """Remove the named model, or the named role's model, from the local runtime's store."""
    _emit_provision_remove(ctx, model=model, role=role)


def provision_report(ctx: typer.Context) -> None:
    """Report the measured hardware, the per-role model selection, and admission."""
    _emit_provision_report(ctx)


def provision_pull(
    ctx: typer.Context,
    model: str | None = None,
    role: ModelRole | None = None,
) -> None:
    """Fetch a model, refusing before any bytes move when the load is not admitted."""
    _emit_provision_pull(ctx, model=model, role=role)


def provision_verify(
    ctx: typer.Context,
    model: str | None = None,
    role: ModelRole | None = None,
) -> None:
    """Confirm a model is resident and answers a trivial prompt within a bound."""
    _emit_provision_verify(ctx, model=model, role=role)


def provision_load(
    ctx: typer.Context,
    model: str | None = None,
    role: ModelRole | None = None,
) -> None:
    """Load pulled models into memory, refusing before the load when it is not admitted."""
    _emit_provision_load(ctx, model=model, role=role)


def provision_setup(ctx: typer.Context, confirm: bool = False) -> None:
    """Install (with ``--confirm``), start, pull, load and verify the local reader in one run."""
    _emit_provision_setup(ctx, confirm=confirm)


def _provision(request: OperationRequest[LocalReaderProvisionRequest]) -> LocalReaderProvisionOutcome:
    """Run one provisioning request with the host's process and fitness adapters."""
    from ....adapters.outbound.llm.role_fitness import probe_text_extraction_fitness
    from ....adapters.outbound.model_runtime.process_control import run_runtime_installer, spawn_runtime_server
    from ....application.local_reader_operation import provision_local_reader

    return asyncio.run(
        provision_local_reader(
            request.payload,
            spawn=spawn_runtime_server,
            run_installer=run_runtime_installer,
            text_probe=probe_text_extraction_fitness,
        )
    )


def _roles(item: LocalReaderModelOutcome) -> list[str]:
    return [role.value for role in item.roles]


def _emit_provision_load(ctx: typer.Context, *, model: str | None, role: ModelRole | None) -> None:
    """Load every resolved model and emit the envelope, exiting 2 unless all are loaded."""
    from ....application.local_reader_operation import (
        build_local_reader_load_request,
    )

    outcome = _provision(build_local_reader_load_request(role, model))
    items = [
        ProvisionLoadItemPayload(
            model=item.model,
            roles=_roles(item),
            loaded=item.succeeded,
            already_loaded=item.already_satisfied,
            elapsed_ms=item.elapsed_ms,
            facts=item.facts,
            precondition_action=_action(item.precondition_verdict),
        )
        for item in outcome.models
    ]
    result = ProvisionLoadResult(loaded=outcome.succeeded, models=items)
    emit_envelope(ctx, command="config.provision.load", result=result, lines=_provision_result_lines(result))
    if not result.loaded:
        raise typer.Exit(code=2)


def _emit_provision_setup(ctx: typer.Context, *, confirm: bool) -> None:
    """Run the one-shot setup and emit its per-step envelope, exiting 2 when a step stopped it."""
    from ....application.local_reader_operation import (
        build_local_reader_setup_request,
    )

    outcome = _provision(build_local_reader_setup_request(consent=confirm))
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
        install_consented=confirm,
        models=[
            ProvisionSetupModelPayload(
                step=item.step.value,
                model=item.model,
                roles=_roles(item),
                succeeded=item.succeeded,
                already_satisfied=item.already_satisfied,
                bytes_fetched=item.bytes_fetched,
                elapsed_ms=item.elapsed_ms,
                facts=item.facts,
                precondition_action=_action(item.precondition_verdict),
            )
            for item in outcome.models
            if item.step is not None
        ],
        facts=outcome.facts,
        precondition_action=_action(outcome.precondition_verdict),
    )
    emit_envelope(ctx, command="config.provision.setup", result=result, lines=_provision_result_lines(result))
    if not result.succeeded:
        raise typer.Exit(code=2)


def _selected_provision_models(
    profile: HardwareProfile,
    resident_names: list[str],
) -> tuple[list[ProvisionModelPayload], tuple[str, int] | None]:
    """Select a model per role, returning the payload rows and the first assessable load.

    Built as payloads rather than as dicts splatted in later. The intermediate
    mapping had no other use, and an inferred dict widens every value to the union
    of all of them -- so the splat read as passing a str where a bool was expected,
    and checked nothing.
    """
    from ....application.provisioning import select_model_for_role
    from ....application.provisioning_runtime import runtime_model_names_match
    from ....core.model_catalogue import ModelRole

    models: list[ProvisionModelPayload] = []
    primary = None
    for role in ModelRole:
        selection = select_model_for_role(role, profile=profile)
        runtime_id = selection.runtime_id
        resident = runtime_id is not None and any(
            runtime_model_names_match(name, runtime_id) for name in resident_names
        )
        models.append(
            ProvisionModelPayload(
                role=role.value,
                model=selection.runtime_id,
                selected=selection.selected,
                resident=resident,
                facts=selection.facts,
                precondition_action=(
                    resolve_cli_precondition_action(selection.precondition_verdict)
                    if selection.precondition_verdict is not None
                    else None
                ),
            ),
        )
        if primary is None:
            primary = selection.assessable_load
    return models, primary


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


def _emit_provision_report(ctx: typer.Context) -> None:
    """Measure hardware, select a model per role, and emit the provisioning report."""
    from ....application.provisioning import (
        probe_hardware_profile,
    )
    from ....application.provisioning_runtime import assess_model_load_contention, read_runtime_residents

    profile = probe_hardware_profile()
    residents = read_runtime_residents()
    resident_names = [entry.name for entry in residents] if residents is not None else []
    models, primary = _selected_provision_models(profile, resident_names)

    contention = None
    if primary is not None:
        contention = assess_model_load_contention(
            primary[0],
            primary[1],
            profile=profile,
            residents=residents,
            residents_measured=residents is not None,
        )

    result = ProvisionReportResult(
        accelerator=profile.accelerator.kind.value,
        total_vram_bytes=profile.total_vram_bytes,
        free_vram_bytes=profile.free_vram_bytes,
        total_system_memory_bytes=profile.memory.total_bytes,
        free_system_memory_bytes=profile.memory.free_bytes,
        runtime_reachable=residents is not None,
        residents=resident_names,
        models=models,
        contention=_contention_payload(contention),
    )
    emit_envelope(
        ctx,
        command="config.provision.report",
        result=result,
        lines=_provision_result_lines(result),
    )


def _emit_provision_pull(ctx: typer.Context, *, model: str | None, role: ModelRole | None) -> None:
    """Fetch every resolved model and emit the pull envelope, exiting 2 unless all pulled."""
    from ....application.provisioning_runtime import pull_runtime_model

    items: list[ProvisionPullItemPayload] = []
    for target in _targets(role, model):
        roles = [served.value for served in target.roles]
        if target.model is None or target.requirement_bytes is None:
            items.append(
                ProvisionPullItemPayload(
                    model=target.model,
                    roles=roles,
                    pulled=False,
                    facts=target.selection_facts,
                    precondition_action=resolve_cli_precondition_action(_selection_refusal(target)),
                )
            )
            continue
        outcome = pull_runtime_model(target.model, target.requirement_bytes)
        items.append(
            ProvisionPullItemPayload(
                model=outcome.model,
                roles=roles,
                pulled=outcome.pulled,
                bytes_fetched=outcome.bytes_fetched,
                contention=_contention_payload(outcome.contention),
                facts=outcome.facts,
                precondition_action=_action(outcome.precondition_verdict),
            )
        )
    result = ProvisionPullResult(pulled=bool(items) and all(item.pulled for item in items), models=items)
    emit_envelope(ctx, command="config.provision.pull", result=result, lines=_provision_result_lines(result))
    if not result.pulled:
        raise typer.Exit(code=2)


def _emit_provision_verify(ctx: typer.Context, *, model: str | None, role: ModelRole | None) -> None:
    """Verify every resolved model and emit the envelope, exiting 2 unless all are ready.

    Readiness includes each served role's fitness probe, so a model that loads
    and answers but cannot produce the text reader's answer is refused here.
    """
    from ....adapters.outbound.llm.role_fitness import probe_text_extraction_fitness
    from ....application.local_reader import verify_role_target

    items: list[ProvisionVerifyItemPayload] = []
    for target in _targets(role, model):
        roles = [served.value for served in target.roles]
        if target.model is None:
            items.append(
                ProvisionVerifyItemPayload(
                    roles=roles,
                    ready=False,
                    facts=target.selection_facts,
                    precondition_action=resolve_cli_precondition_action(_selection_refusal(target)),
                )
            )
            continue
        outcome = verify_role_target(target, text_probe=probe_text_extraction_fitness)
        items.append(
            ProvisionVerifyItemPayload(
                model=outcome.model,
                roles=roles,
                ready=outcome.ready,
                resident=outcome.resident,
                answered=outcome.answered,
                elapsed_ms=outcome.elapsed_ms,
                facts=outcome.facts,
                precondition_action=_action(outcome.precondition_verdict),
            )
        )
    result = ProvisionVerifyResult(ready=bool(items) and all(item.ready for item in items), models=items)
    emit_envelope(ctx, command="config.provision.verify", result=result, lines=_provision_result_lines(result))
    if not result.ready:
        raise typer.Exit(code=2)


def _emit_local_reader_status(
    ctx: typer.Context,
    *,
    command: str,
    result_type: type[ProvisionStatusResult],
    probe: bool,
) -> None:
    """Measure the local reader and emit its status envelope. Records nothing.

    Without ``probe`` text-model fitness is the verdict ``verify`` recorded for
    the model's current weights, so ``status`` never spends a model load.
    ``probe`` runs the check now and reports it without recording it.
    """
    from ....application.local_reader import read_local_reader_status

    if probe:
        from ....adapters.outbound.llm.role_fitness import probe_text_extraction_fitness

        status = read_local_reader_status(text_probe=probe_text_extraction_fitness)
    else:
        status = read_local_reader_status()
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
            facts=host.facts,
            precondition_action=_action(host.precondition_verdict),
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


def _fitness_condition_lines(rows: tuple[LocalReaderRoleStatus, ...]) -> tuple[str, ...]:
    """Render each role's failed fitness condition as its localized explanation."""
    from ....core.i18n.render import tr

    return tuple(
        f"{row.role.value}\t{tr(_FITNESS_CONDITION_LOCALE_KEYS[row.failed_condition_id], model=row.model or '-')}"
        for row in rows
        if row.failed_condition_id in _FITNESS_CONDITION_LOCALE_KEYS
    )


def _emit_provision_install(ctx: typer.Context, *, confirm: bool) -> None:
    """Install the runtime when consented and emit the envelope, exiting 2 unless installed."""
    from ....application.local_reader_operation import (
        build_local_reader_install_request,
    )

    outcome = _provision(build_local_reader_install_request(consent=confirm))
    install = outcome.install
    if install is None:  # pragma: no cover - the install action always records its outcome
        raise AssertionError
    result = ProvisionInstallResult(
        installed=install.installed,
        already_installed=install.already_installed,
        installer=install.installer.value,
        consented=install.consented,
        installer_exit_code=install.installer_exit_code,
        facts=outcome.facts,
        precondition_action=_action(outcome.precondition_verdict),
    )
    emit_envelope(ctx, command="config.provision.install", result=result, lines=_provision_result_lines(result))
    if not install.installed:
        raise typer.Exit(code=2)


def _emit_provision_start(ctx: typer.Context) -> None:
    """Start the runtime when needed and emit the envelope, exiting 2 unless it answers."""
    from ....adapters.outbound.model_runtime.process_control import spawn_runtime_server
    from ....application.provisioning_host import start_runtime

    outcome = start_runtime(spawn=spawn_runtime_server)
    result = ProvisionStartResult(
        running=outcome.running,
        already_running=outcome.already_running,
        started_pid=outcome.started_pid,
        facts=outcome.facts,
        precondition_action=_action(outcome.precondition_verdict),
    )
    emit_envelope(ctx, command="config.provision.start", result=result, lines=_provision_result_lines(result))
    if not outcome.running:
        raise typer.Exit(code=2)


def _emit_provision_remove(ctx: typer.Context, *, model: str | None, role: ModelRole | None) -> None:
    """Remove the resolved model and emit the envelope, exiting 2 unless every removal was confirmed."""
    from ....application.local_reader_operation import (
        build_local_reader_remove_request,
    )

    if model is None and role is None:
        raise typer.BadParameter("--model or --role is required", param_hint="--model/--role")
    outcome = _provision(build_local_reader_remove_request(role, model))
    items = [
        ProvisionRemoveItemPayload(
            model=item.model,
            roles=_roles(item),
            removed=item.succeeded,
            was_installed=item.was_installed,
            freed_bytes=item.freed_bytes,
            facts=item.facts,
            precondition_action=_action(item.precondition_verdict),
        )
        for item in outcome.models
    ]
    result = ProvisionRemoveResult(removed=outcome.succeeded, models=items)
    emit_envelope(ctx, command="config.provision.remove", result=result, lines=_provision_result_lines(result))
    if not result.removed:
        raise typer.Exit(code=2)


def _emit_provision_browser(ctx: typer.Context) -> None:
    """Provision the browser build and emit the envelope, exiting 2 unless it is installed."""
    from ....adapters.outbound.browser_runtime.installer import run_browser_installer
    from ....application.provisioning_browser import install_playwright_browser

    outcome = install_playwright_browser(run=run_browser_installer)
    result = ProvisionBrowserResult(
        installed=outcome.installed,
        already_installed=outcome.already_installed,
        installer_exit_code=outcome.installer_exit_code,
        facts=outcome.facts,
        precondition_action=_action(outcome.precondition_verdict),
    )
    emit_envelope(ctx, command="config.provision.browser", result=result, lines=_provision_result_lines(result))
    if not outcome.installed:
        raise typer.Exit(code=2)
