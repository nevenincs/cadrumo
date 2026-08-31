"""``aeat config provision`` — explicit local-inference lifecycle verbs.

Three actions, and the boundaries between them are the design:

* **report** — measured machine and model-selection state. Reads only.
* **pull** — an explicit model-acquisition operation.
* **verify** — a resident-model readiness observation.

**Nothing here is implicit.** No inference path reaches these verbs; an operator
runs them. A model acquisition is explicit, never a side effect of first use.
An unavailable runtime is represented by its typed failed condition and closed
outcome; this command family does not start external processes.

The pre-fetch admission check is the point of ``pull``. A refusal carries its
typed condition and evidence. Cadrumo never touches a process it does not own.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import typer

from ....core.model_catalogue import ModelRole
from .._common import emit_envelope, resolve_cli_precondition_action
from ._provision_payloads import (
    ProvisionContentionPayload,
    ProvisionModelPayload,
    ProvisionPullResult,
    ProvisionReportResult,
    ProvisionVerifyResult,
)
from .status_rendering import precondition_action_lines

if TYPE_CHECKING:
    from ....application.provisioning import HardwareProfile, ModelSelection

__all__ = ["provision_pull", "provision_report", "provision_verify"]


def _contention_payload(snapshot: object | None) -> ProvisionContentionPayload | None:
    """Project a contention verdict onto its payload, preserving the cause set."""
    if snapshot is None:
        return None
    from ....application.provisioning import ContentionSnapshot

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


def _resolve_role_model(
    role_value: ModelRole | None,
    model: str | None,
) -> tuple[ModelSelection, str | None, int | None]:
    """Resolve an operator's ``--role``/``--model`` into a runtime id and requirement.

    An explicit ``--model`` is honoured as given, with the selected role's
    requirement used for the admission check, because the operator naming a
    model does not tell us how much memory it needs -- the catalogue does.
    """
    from ....application.provisioning import select_model_for_role

    role = role_value if role_value is not None else ModelRole.VISION_TRANSCRIPTION
    selection = select_model_for_role(role)
    assessable = selection.assessable_load
    if assessable is None:
        return selection, None, None
    # An explicit --model is honoured as the target, but the requirement stays
    # the selected candidate's: what the operator names does not tell us how
    # much memory it needs, and inventing a number would assess against nothing.
    return selection, model or assessable[0], assessable[1]


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
    from ....core.model_catalogue import ModelRole

    models: list[ProvisionModelPayload] = []
    primary = None
    for role in ModelRole:
        selection = select_model_for_role(role, profile=profile)
        resident = any(name.startswith(selection.runtime_id or "\x00") for name in resident_names)
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
        assess_model_load_contention,
        probe_hardware_profile,
        read_runtime_residents,
    )

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
    """Fetch the resolved model and emit the pull envelope, exiting 2 when nothing pulled."""
    from ....application.provisioning import pull_runtime_model

    selection, target, requirement = _resolve_role_model(role, model)
    if target is None or requirement is None:
        if selection.precondition_verdict is None:  # pragma: no cover - guarded by ModelSelection validation
            raise AssertionError
        result = ProvisionPullResult(
            model=selection.runtime_id,
            pulled=False,
            facts=selection.facts,
            precondition_action=resolve_cli_precondition_action(selection.precondition_verdict),
        )
        emit_envelope(ctx, command="config.provision.pull", result=result, lines=_provision_result_lines(result))
        raise typer.Exit(code=2)

    outcome = pull_runtime_model(target, requirement)
    result = ProvisionPullResult(
        model=outcome.model,
        pulled=outcome.pulled,
        bytes_fetched=outcome.bytes_fetched,
        contention=_contention_payload(outcome.contention),
        facts=outcome.facts,
        precondition_action=(
            resolve_cli_precondition_action(outcome.precondition_verdict)
            if outcome.precondition_verdict is not None
            else None
        ),
    )
    emit_envelope(ctx, command="config.provision.pull", result=result, lines=_provision_result_lines(result))
    if not outcome.pulled:
        raise typer.Exit(code=2)


def _emit_provision_verify(ctx: typer.Context, *, model: str | None, role: ModelRole | None) -> None:
    """Verify the resolved model is ready and emit the envelope, exiting 2 when it is not."""
    from ....application.provisioning import verify_model_ready

    selection, target, requirement = _resolve_role_model(role, model)
    if target is None or requirement is None:
        if selection.precondition_verdict is None:  # pragma: no cover - guarded by ModelSelection validation
            raise AssertionError
        result = ProvisionVerifyResult(
            model=selection.runtime_id,
            ready=False,
            facts=selection.facts,
            precondition_action=resolve_cli_precondition_action(selection.precondition_verdict),
        )
        emit_envelope(ctx, command="config.provision.verify", result=result, lines=_provision_result_lines(result))
        raise typer.Exit(code=2)

    outcome = verify_model_ready(target)
    result = ProvisionVerifyResult(
        model=outcome.model,
        ready=outcome.ready,
        resident=outcome.resident,
        answered=outcome.answered,
        elapsed_ms=outcome.elapsed_ms,
        facts=outcome.facts,
        precondition_action=(
            resolve_cli_precondition_action(outcome.precondition_verdict)
            if outcome.precondition_verdict is not None
            else None
        ),
    )
    emit_envelope(ctx, command="config.provision.verify", result=result, lines=_provision_result_lines(result))
    if not outcome.ready:
        raise typer.Exit(code=2)
