"""``aeat config provision`` — explicit local-inference lifecycle verbs.

Three actions, and the boundaries between them are the design:

* **report** — what the machine measures, which model each role resolves to,
  and whether it could be loaded right now. Reads only.
* **pull** — fetch a model, admission-checked BEFORE any bytes move.
* **verify** — confirm a model is resident and answers within a bound.

**Nothing here is implicit.** No inference path reaches these verbs; an operator
runs them. A multi-gigabyte download is an explicit action, never a side effect
of first use, and an unreachable runtime is an instructive refusal naming
``ollama serve`` -- this command family never spawns a daemon. Both are the
lifecycle boundary the provisioning decision draws, not local caution.

The pre-fetch admission check is the point of ``pull``. A refusal names which
contention cause applies, because the remediations are not interchangeable:
unloading a model Cadrumo selected is an action this product can offer, closing
a peer application is not, and Cadrumo never touches a process it does not own.
"""

from __future__ import annotations

import typer

from ....core import ModelRole
from ....core.i18n import tr
from .._common import _emit_envelope

# Eager import so the @register_schema decorators run on the CLI build path.
from ._provision_payloads import (
    ProvisionContentionPayload,
    ProvisionModelPayload,
    ProvisionPullResult,
    ProvisionReportResult,
    ProvisionVerifyResult,
)

__all__ = ["register_provision_commands"]


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
        detail=snapshot.detail,
        remediation=snapshot.remediation,
    )


def _resolve_role_model(role_value: ModelRole | None, model: str | None) -> tuple[str, int] | None:
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
        return None
    # An explicit --model is honoured as the target, but the requirement stays
    # the selected candidate's: what the operator names does not tell us how
    # much memory it needs, and inventing a number would assess against nothing.
    return (model, assessable[1]) if model else assessable


def register_provision_commands(app: typer.Typer) -> None:
    """Attach the ``config provision`` subgroup to the config ``app``."""
    provision_app = typer.Typer(
        name="provision",
        help=tr("cli.config.provision.help"),
        no_args_is_help=True,
    )

    @provision_app.command("report", help=tr("cli.config.provision.report.help"))
    def provision_report(ctx: typer.Context) -> None:
        """Report the measured hardware, the per-role model selection, and admission."""
        _emit_provision_report(ctx)

    @provision_app.command("pull", help=tr("cli.config.provision.pull.help"))
    def provision_pull(
        ctx: typer.Context,
        model: str | None = typer.Option(None, "--model", help=tr("cli.config.provision.pull.model_help")),
        role: ModelRole | None = typer.Option(None, "--role", help=tr("cli.config.provision.role_help")),
    ) -> None:
        """Fetch a model, refusing before any bytes move when the load is not admitted."""
        _emit_provision_pull(ctx, model=model, role=role)

    @provision_app.command("verify", help=tr("cli.config.provision.verify.help"))
    def provision_verify(
        ctx: typer.Context,
        model: str | None = typer.Option(None, "--model", help=tr("cli.config.provision.verify.model_help")),
        role: ModelRole | None = typer.Option(None, "--role", help=tr("cli.config.provision.role_help")),
    ) -> None:
        """Confirm a model is resident and answers a trivial prompt within a bound."""
        _emit_provision_verify(ctx, model=model, role=role)

    app.add_typer(provision_app)


def _selected_provision_models(
    profile: object,
    resident_names: list[str],
) -> tuple[list[ProvisionModelPayload], tuple[str, int] | None]:
    """Select a model per role, returning the payload rows and the first assessable load.

    Built as payloads rather than as dicts splatted in later. The intermediate
    mapping had no other use, and an inferred dict widens every value to the union
    of all of them -- so the splat read as passing a str where a bool was expected,
    and checked nothing.
    """
    from ....application.provisioning import select_model_for_role
    from ....core import ModelRole

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
                detail=selection.detail,
            ),
        )
        if primary is None:
            primary = selection.assessable_load
    return models, primary


def _provision_report_lines(
    profile: object,
    residents: object | None,
    models: list[ProvisionModelPayload],
    contention: object | None,
) -> tuple[str, ...]:
    """Render the human-readable provisioning report rows."""
    lines = [
        f"accelerator\t{profile.accelerator.kind.value}",
        f"runtime\t{'reachable' if residents is not None else 'unreachable'}",
    ]
    lines.extend(f"model\t{row.role}\t{row.model or '-'}\t{'resident' if row.resident else '-'}" for row in models)
    if contention is not None:
        lines.append(f"contention\t{'admitted' if contention.admitted else 'refused'}\t{contention.detail}")
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
    _emit_envelope(
        ctx,
        command="config.provision.report",
        result=result,
        lines=_provision_report_lines(profile, residents, models, contention),
    )


def _emit_provision_pull(ctx: typer.Context, *, model: str | None, role: ModelRole | None) -> None:
    """Fetch the resolved model and emit the pull envelope, exiting 2 when nothing pulled."""
    from ....application.provisioning import pull_runtime_model

    resolved = _resolve_role_model(role, model)
    if resolved is None:
        raise typer.BadParameter(tr("cli.config.provision.no_model"))
    target, requirement = resolved

    reports: list[str] = []

    def _on_progress(progress: object) -> None:
        percent = getattr(progress, "percent", None)
        status = getattr(progress, "status", "")
        reports.append(f"{status} {percent}%" if percent is not None else status)

    outcome = pull_runtime_model(target, requirement, on_progress=_on_progress)
    result = ProvisionPullResult(
        model=outcome.model,
        pulled=outcome.pulled,
        bytes_fetched=outcome.bytes_fetched,
        contention=_contention_payload(outcome.contention),
        detail=outcome.detail,
        remediation=outcome.remediation,
    )
    lines = [f"model\t{outcome.model}", f"pulled\t{'yes' if outcome.pulled else 'no'}"]
    if outcome.detail:
        lines.append(f"detail\t{outcome.detail}")
    if outcome.remediation:
        lines.append(f"remediation\t{outcome.remediation}")
    _emit_envelope(ctx, command="config.provision.pull", result=result, lines=tuple(lines))
    if not outcome.pulled:
        raise typer.Exit(code=2)


def _emit_provision_verify(ctx: typer.Context, *, model: str | None, role: ModelRole | None) -> None:
    """Verify the resolved model is ready and emit the envelope, exiting 2 when it is not."""
    from ....application.provisioning import verify_model_ready

    resolved = _resolve_role_model(role, model)
    if resolved is None:
        raise typer.BadParameter(tr("cli.config.provision.no_model"))
    target, _requirement = resolved

    outcome = verify_model_ready(target)
    result = ProvisionVerifyResult(
        model=outcome.model,
        ready=outcome.ready,
        resident=outcome.resident,
        answered=outcome.answered,
        elapsed_ms=outcome.elapsed_ms,
        detail=outcome.detail,
        remediation=outcome.remediation,
    )
    lines = [
        f"model\t{outcome.model}",
        f"ready\t{'yes' if outcome.ready else 'no'}",
        f"resident\t{'yes' if outcome.resident else 'no'}",
    ]
    if outcome.detail:
        lines.append(f"detail\t{outcome.detail}")
    if outcome.remediation:
        lines.append(f"remediation\t{outcome.remediation}")
    _emit_envelope(ctx, command="config.provision.verify", result=result, lines=tuple(lines))
    if not outcome.ready:
        raise typer.Exit(code=2)
