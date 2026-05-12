from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path

import typer

from ...application.filing import (
    DeclarationCalculateSummary,
    DeclarationVerifyVerdict,
    FilingBuilderError,
    FilingDraftStatus,
    FilingFindingSeverity,
    FilingOperatorProfile,
    approve_draft,
    build_draft,
    build_runtime_schema_provider,
    summarise_calculation,
    validate_draft,
)
from ...application.filing._export import export_draft, verify_export
from ...application.review import (
    DeclarationReviewFilterSpec,
    DeclarationReviewStatus,
    EditParseError,
    FilterParseError,
)
from ...application.workflow import (
    declaration_key,
    update_declaration_pointer,
    workflow_state_repository,
)
from ._common import (
    _FORMAT_JSON,
    _FORMAT_TABLE,
    _aggregate_filing_inputs,
    _bad,
    _canonical_period,
    _draft_by_id,
    _draft_repo,
    _emit,
    _exit,
    _format_of,
    _json_default,
    _state,
    _translate,
)
from ._i18n import tr

app = typer.Typer(
    name="declaration",
    help=tr("cli.declaration.app_help"),
    no_args_is_help=True,
)


def _resolve_draft_id(modelo: str | None, period: str | None, draft_id: str | None) -> str:
    """Resolve a draft id from either --id or (--modelo, --period).

    Every declaration verb accepts both flag forms. The helper raises a
    typed CLI usage error when:

    - --id is supplied alongside --modelo or --period
      (ambiguous selector);
    - none of the three flags is supplied (no selector);
    - one of --modelo / --period is supplied without the other
      (incomplete selector); or
    - the resolved (modelo, period) lookup has no matching draft pointer
      in the active profile's user-cli state.

    Args:
        modelo: Optional --modelo argument.
        period: Optional --period argument.
        draft_id: Optional --id argument.

    Returns:
        The resolved canonical draft id.
    """

    if draft_id is not None and (modelo is not None or period is not None):
        raise _bad(tr("cli.declaration.errors.draft_selector_ambiguous"))
    if draft_id is not None:
        return draft_id
    if modelo is None or period is None:
        raise _bad(tr("cli.declaration.errors.missing_id_or_period_modelo"))
    canonical_period = _canonical_period(period)
    canonical_modelo = modelo.strip()
    state = _state()
    pointer = state.declarations.get(declaration_key(canonical_modelo, canonical_period))
    if pointer is None or pointer.draft_id is None:
        raise _bad(tr("cli.declaration.errors.no_draft_for_period"))
    return pointer.draft_id


def _parse_binding_assignment(raw: str) -> tuple[str, Decimal]:
    """Parse one KEY=VALUE token from --binding into a typed pair.

    Args:
        raw: The exact string the operator passed after --binding.

    Returns:
        A two-tuple (key, value) where key is the binding's
        canonical id and value is a Decimal.

    Raises:
        typer.BadParameter (via _bad): If the assignment is
            malformed (no =, blank key, blank value) or the value
            does not parse as a decimal number.
    """

    if "=" not in raw:
        raise _bad(tr("cli.declaration.errors.binding_assignment", value=raw))
    key, value = raw.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key or not value:
        raise _bad(tr("cli.declaration.errors.binding_assignment", value=raw))
    try:
        decimal_value = Decimal(value)
    except InvalidOperation as exc:
        raise _bad(tr("cli.declaration.errors.binding_value_not_decimal", value=value)) from exc
    return key, decimal_value


@app.command("calculate", help=tr("cli.declaration.calculate_help"))
def declaration_calculate(
    ctx: typer.Context,
    period: str = typer.Option(..., "--period", help=tr("cli.declaration.opts.period")),
    modelo: str = typer.Option(..., "--modelo", help=tr("cli.declaration.opts.modelo")),
    binding: list[str] = typer.Option(
        [],
        "--binding",
        help=tr("cli.declaration.opts.binding"),
    ),
) -> None:
    canonical_period = _canonical_period(period)
    canonical_modelo = modelo.strip()
    state = _state()
    record = state.active_profile_record()
    if record is None:
        raise _bad(tr("cli.declaration.errors.activate_profile"))
    tax_id = (record.values.get("tax.id") or "").strip()
    if not tax_id:
        raise _bad(tr("cli.declaration.errors.profile_tax_id_required"))
    operator = FilingOperatorProfile(
        tax_id=tax_id,
        display_name=state.active_profile or "operator",
    )
    inputs = dict(_aggregate_filing_inputs(canonical_modelo, canonical_period, state))
    for raw_binding in binding:
        key, value = _parse_binding_assignment(raw_binding)
        inputs[key] = value
    try:
        schema_provider = build_runtime_schema_provider(modelos=(canonical_modelo,))
        draft = build_draft(
            modelo=canonical_modelo,
            period=canonical_period,
            profile=operator,
            inputs=inputs,
            schema_provider=schema_provider,
        )
    except FilingBuilderError as exc:
        raise _bad(str(exc)) from exc
    blockers = tuple(f for f in draft.findings if f.severity is FilingFindingSeverity.ERROR)
    summary: DeclarationCalculateSummary = summarise_calculation(
        draft,
        repair_hints=tuple(_translate(f.message) for f in blockers),
    )
    _draft_repo().save(draft)
    workflow_state_repository().update(
        lambda current: update_declaration_pointer(
            current,
            modelo=canonical_modelo,
            period=canonical_period,
            draft_id=draft.draft_id,
            status=draft.status.value,
        )
    )
    next_pointer = _next_action_command(summary.next_action.value, canonical_modelo, canonical_period)
    payload = {"draft": draft, "summary": summary}
    lines: list[str] = [
        f"{tr('cli.declaration.labels.draft_id')}\t{draft.draft_id}",
        f"{tr('cli.declaration.labels.status')}\t{draft.status.value}",
        f"{tr('cli.declaration.labels.blockers')}\t{summary.blocker_count}",
        f"{tr('cli.declaration.labels.warnings')}\t{summary.warning_count}",
    ]
    for finding in blockers:
        lines.append(f"blocker\tcasilla.{finding.casilla_id}\t{_translate(finding.message)}")
    lines.append(f"{tr('cli.declaration.labels.next')}\t{next_pointer}")
    _emit(ctx, payload, lines)


def _next_action_command(next_action: str, modelo: str, period: str) -> str:
    """Translate a ``DeclarationCalculateNextAction`` into a runnable CLI hint.

    The audit (UX-021) flagged ``Siguiente: resolve-blockers`` as an
    opaque recipe token. Each next-action value now maps to a literal
    command the operator can copy and run, parameterised on the
    current modelo and period.
    """

    if next_action == "resolve-blockers":
        return f"aeat app declaration review --modelo {modelo} --period {period}"
    if next_action == "review":
        return f"aeat app declaration review --modelo {modelo} --period {period}"
    if next_action == "approve":
        return f"aeat app declaration approve --modelo {modelo} --period {period} --by NAME --reason TEXT"
    if next_action == "export":
        return f"aeat app declaration export --modelo {modelo} --period {period} --output PATH"
    if next_action == "refresh-approval":
        return f"aeat app declaration approve --modelo {modelo} --period {period} --by NAME --reason TEXT"
    return next_action


@app.command("review", help=tr("cli.declaration.review_help"))
def declaration_review(
    ctx: typer.Context,
    period: str | None = typer.Option(None, "--period", help=tr("cli.declaration.opts.period")),
    modelo: str | None = typer.Option(None, "--modelo", help=tr("cli.declaration.opts.modelo")),
    draft_id: str | None = typer.Option(None, "--id", help=tr("cli.declaration.opts.draft_id")),
    format_: str = typer.Option(_FORMAT_TABLE, "--format", help=tr("cli.declaration.format_help")),
) -> None:
    if draft_id is not None:
        draft = _draft_by_id(draft_id)
    else:
        if period is None or modelo is None:
            raise _bad(tr("cli.declaration.errors.missing_id_or_period_modelo"))
        canonical_period = _canonical_period(period)
        canonical_modelo = modelo.strip()
        state = _state()
        pointer = state.declarations.get(declaration_key(canonical_modelo, canonical_period))
        if pointer is None or pointer.draft_id is None:
            raise _bad(tr("cli.declaration.errors.no_draft_for_period"))
        draft = _draft_by_id(pointer.draft_id)
    if format_.lower() == _FORMAT_JSON or _format_of(ctx) == _FORMAT_JSON:
        ctx.ensure_object(dict)["format"] = _FORMAT_JSON
    payload = {"draft": draft, "values": list(draft.values), "findings": list(draft.findings)}
    lines: list[str] = [
        f"{tr('cli.declaration.labels.draft_id')}\t{draft.draft_id}",
        f"{tr('cli.declaration.labels.status')}\t{draft.status.value}",
        f"{tr('cli.declaration.labels.values')}\t{len(draft.values)}",
    ]
    for value in draft.values:
        lines.append(f"casilla.{value.casilla_id}\t{value.value}\t{value.kind.value}")
    _emit(ctx, payload, lines)


@app.command("status", help=tr("cli.declaration.status_help"))
def declaration_status(
    ctx: typer.Context,
    period: str = typer.Option(..., "--period", help=tr("cli.declaration.opts.period")),
    modelo: str = typer.Option(..., "--modelo", help=tr("cli.declaration.opts.modelo")),
    filters: list[str] = typer.Option([], "--filter", help=tr("cli.declaration.opts.filter")),
) -> None:
    try:
        spec = DeclarationReviewFilterSpec.from_strings(filters)
    except FilterParseError as exc:
        raise _bad(tr("cli.declaration.errors.filter_parse_error", reason=exc.reason, token=exc.raw_token)) from exc
    canonical_period = _canonical_period(period)
    canonical_modelo = modelo.strip()
    state = _state()
    pointer = state.declarations.get(declaration_key(canonical_modelo, canonical_period))
    if pointer is None:
        _emit(
            ctx,
            {"present": False},
            [f"{tr('cli.declaration.labels.status')}\t{tr('cli.declaration.status.absent')}"],
        )
        _exit(2)
    assert pointer is not None
    status_text = pointer.status or ""
    matches_filter = _declaration_status_matches(status_text, spec.status)
    matches_filter_label = tr("cli.declaration.labels.yes") if matches_filter else tr("cli.declaration.labels.no")
    payload = {
        "draft_id": pointer.draft_id,
        "status": pointer.status,
        "modelo": canonical_modelo,
        "period": canonical_period,
        "matches_filter": matches_filter,
        "filters": list(spec.clauses),
    }
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.declaration.labels.draft_id')}\t{pointer.draft_id}",
            f"{tr('cli.declaration.labels.status')}\t{pointer.status}",
            f"{tr('cli.declaration.labels.matches_filter')}\t{matches_filter_label}",
        ],
    )


def _declaration_status_matches(status: str, wanted: DeclarationReviewStatus | None) -> bool:
    if wanted is None:
        return True
    normalized = status.strip().upper()
    if wanted is DeclarationReviewStatus.PENDING:
        return normalized in {"DRAFT", "VALIDATED", "READY_TO_SUBMIT"}
    if wanted is DeclarationReviewStatus.APPROVED:
        return normalized == "APPROVED"
    if wanted is DeclarationReviewStatus.STALE:
        return normalized == "APPROVAL_STALE"
    if wanted is DeclarationReviewStatus.SUBMITTED:
        return normalized == "SUBMITTED"
    if wanted is DeclarationReviewStatus.ACKNOWLEDGED:
        return normalized == "ACKNOWLEDGED"
    return False


@app.command("edit", help=tr("cli.declaration.edit_help"))
def declaration_edit(
    ctx: typer.Context,
    sets: list[str] = typer.Option([], "--set", help=tr("cli.declaration.opts.set")),
    reason: str = typer.Option(..., "--reason", help=tr("cli.declaration.opts.reason")),
    draft_id: str | None = typer.Option(None, "--id", help=tr("cli.declaration.opts.draft_id")),
    modelo: str | None = typer.Option(None, "--modelo", help=tr("cli.declaration.opts.modelo")),
    period: str | None = typer.Option(None, "--period", help=tr("cli.declaration.opts.period")),
) -> None:
    from ...application.review._edit import DeclarationEditSpec

    try:
        edit_spec = DeclarationEditSpec.from_strings(sets)
    except EditParseError as exc:
        raise _bad(tr("cli.declaration.errors.set_parse_error", reason=exc.reason, token=exc.raw_token)) from exc
    if not edit_spec.casilla_edits:
        raise _bad(tr("cli.declaration.errors.at_least_one_edit"))
    resolved_id = _resolve_draft_id(modelo, period, draft_id)
    draft = _draft_by_id(resolved_id)
    operator = FilingOperatorProfile(
        tax_id=draft.profile_tax_id,
        display_name=draft.profile_tax_id,
    )
    schema_provider = build_runtime_schema_provider(modelos=(draft.modelo,))
    inputs: dict[str, object] = {entry.casilla_id: entry.value for entry in draft.values if entry.value is not None}
    inputs.update(edit_spec.casilla_edits)
    try:
        fresh = build_draft(
            modelo=draft.modelo,
            period=draft.period,
            profile=operator,
            inputs=inputs,
            schema_provider=schema_provider,
        )
    except FilingBuilderError as exc:
        raise _bad(str(exc)) from exc
    _draft_repo().save(fresh)
    workflow_state_repository().update(
        lambda current: update_declaration_pointer(
            current,
            modelo=fresh.modelo,
            period=fresh.period,
            draft_id=fresh.draft_id,
            status=fresh.status.value,
        )
    )
    payload = {
        "draft_id": fresh.draft_id,
        "status": fresh.status.value,
        "edits": edit_spec.casilla_edits,
        "reason": reason,
    }
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.declaration.labels.draft_id')}\t{fresh.draft_id}",
            f"{tr('cli.declaration.labels.status')}\t{fresh.status.value}",
            f"{tr('cli.declaration.labels.edits')}\t{len(edit_spec.casilla_edits)}",
        ],
    )


@app.command("approve", help=tr("cli.declaration.approve_help"))
def declaration_approve(
    ctx: typer.Context,
    reviewer: str = typer.Option(..., "--by", help=tr("cli.declaration.opts.by")),
    reason: str = typer.Option(..., "--reason", help=tr("cli.declaration.opts.reason")),
    draft_id: str | None = typer.Option(None, "--id", help=tr("cli.declaration.opts.draft_id")),
    modelo: str | None = typer.Option(None, "--modelo", help=tr("cli.declaration.opts.modelo")),
    period: str | None = typer.Option(None, "--period", help=tr("cli.declaration.opts.period")),
) -> None:
    resolved_id = _resolve_draft_id(modelo, period, draft_id)
    draft = _draft_by_id(resolved_id)
    schema_provider = build_runtime_schema_provider(modelos=(draft.modelo,))
    approved = approve_draft(draft, approved_by=reviewer, schema_provider=schema_provider)
    _draft_repo().save(approved)
    workflow_state_repository().update(
        lambda current: update_declaration_pointer(
            current,
            modelo=approved.modelo,
            period=approved.period,
            draft_id=approved.draft_id,
            status=approved.status.value,
        )
    )
    payload = {
        "draft_id": approved.draft_id,
        "status": approved.status.value,
        "approved_by": reviewer,
        "reason": reason,
    }
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.declaration.labels.draft_id')}\t{approved.draft_id}",
            f"{tr('cli.declaration.labels.status')}\t{approved.status.value}",
            f"{tr('cli.declaration.labels.by')}\t{reviewer}",
        ],
    )


@app.command("validate", help=tr("cli.declaration.validate_help"))
def declaration_validate(
    ctx: typer.Context,
    output: Path | None = typer.Option(None, "--output", help=tr("cli.declaration.opts.output")),
    draft_id: str | None = typer.Option(None, "--id", help=tr("cli.declaration.opts.draft_id")),
    modelo: str | None = typer.Option(None, "--modelo", help=tr("cli.declaration.opts.modelo")),
    period: str | None = typer.Option(None, "--period", help=tr("cli.declaration.opts.period")),
) -> None:
    resolved_id = _resolve_draft_id(modelo, period, draft_id)
    draft = _draft_by_id(resolved_id)
    schema_provider = build_runtime_schema_provider(modelos=(draft.modelo,))
    refreshed = validate_draft(draft, schema_provider=schema_provider)
    _draft_repo().save(refreshed)
    workflow_state_repository().update(
        lambda current: update_declaration_pointer(
            current,
            modelo=refreshed.modelo,
            period=refreshed.period,
            draft_id=refreshed.draft_id,
            status=refreshed.status.value,
        )
    )
    payload = {
        "draft_id": refreshed.draft_id,
        "status": refreshed.status.value,
        "findings": [
            {"casilla": f.casilla_id, "severity": f.severity.value, "code": f.code, "message": _translate(f.message)}
            for f in refreshed.findings
        ],
    }
    if output is not None:
        import json as _json

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(_json.dumps(payload, default=_json_default, ensure_ascii=False, indent=2), encoding="utf-8")
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.declaration.labels.draft_id')}\t{refreshed.draft_id}",
            f"{tr('cli.declaration.labels.status')}\t{refreshed.status.value}",
            f"{tr('cli.declaration.labels.findings')}\t{len(refreshed.findings)}",
        ],
    )


@app.command("preview", help=tr("cli.declaration.preview_help"))
def declaration_preview(
    ctx: typer.Context,
    draft_id: str | None = typer.Option(None, "--id", help=tr("cli.declaration.opts.draft_id")),
    modelo: str | None = typer.Option(None, "--modelo", help=tr("cli.declaration.opts.modelo")),
    period: str | None = typer.Option(None, "--period", help=tr("cli.declaration.opts.period")),
) -> None:
    resolved_id = _resolve_draft_id(modelo, period, draft_id)
    draft = _draft_by_id(resolved_id)
    payload = {
        "draft_id": draft.draft_id,
        "modelo": draft.modelo,
        "period": draft.period,
        "values": list(draft.values),
    }
    lines: list[str] = [
        f"{tr('cli.declaration.labels.draft_id')}\t{draft.draft_id}",
        f"{tr('cli.declaration.labels.modelo')}\t{draft.modelo}",
        f"{tr('cli.declaration.labels.period')}\t{draft.period}",
    ]
    for value in draft.values:
        lines.append(f"casilla.{value.casilla_id}\t{value.value}")
    _emit(ctx, payload, lines)


@app.command("export", help=tr("cli.declaration.export_help"))
def declaration_export(
    ctx: typer.Context,
    output: Path = typer.Option(..., "--output", help=tr("cli.declaration.opts.output")),
    draft_id: str | None = typer.Option(None, "--id", help=tr("cli.declaration.opts.draft_id")),
    modelo: str | None = typer.Option(None, "--modelo", help=tr("cli.declaration.opts.modelo")),
    period: str | None = typer.Option(None, "--period", help=tr("cli.declaration.opts.period")),
) -> None:
    resolved_id = _resolve_draft_id(modelo, period, draft_id)
    draft = _draft_by_id(resolved_id)
    if draft.status is not FilingDraftStatus.APPROVED:
        raise _bad(tr("cli.declaration.errors.not_approved_for_export", status=draft.status.value))
    headers = _export_headers_from_active_profile()
    try:
        receipt = export_draft(draft, output_path=output, headers=headers)
    except ValueError as exc:
        raise _bad(str(exc)) from exc
    workflow_state_repository().update(
        lambda current: update_declaration_pointer(
            current,
            modelo=draft.modelo,
            period=draft.period,
            draft_id=draft.draft_id,
            status=draft.status.value,
            exported_path=str(output),
        )
    )
    payload = {"receipt": receipt}
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.declaration.labels.draft_id')}\t{receipt.draft_id}",
            f"{tr('cli.declaration.labels.path')}\t{receipt.output_path}",
            f"{tr('cli.declaration.labels.sha256')}\t{receipt.file_sha256}",
            f"{tr('cli.declaration.labels.bytes')}\t{receipt.byte_size}",
        ],
    )


def _export_headers_from_active_profile() -> dict[str, str]:
    """Return declaration-export header values explicitly stored in the active profile."""
    record = _state().active_profile_record()
    if record is None:
        return {}
    return {key.replace(".", "_"): value for key, value in record.values.items() if value}


@app.command("verify", help=tr("cli.declaration.verify_help"))
def declaration_verify(
    ctx: typer.Context,
    draft_id: str = typer.Option(..., "--id", help=tr("cli.declaration.opts.draft_id")),
    file: Path = typer.Option(..., "--file", help=tr("cli.declaration.opts.file")),
) -> None:
    draft = _draft_by_id(draft_id)
    if not file.exists():
        raise _bad(tr("cli.declaration.errors.file_not_found", path=str(file)))
    verdict = verify_export(draft, file_path=file)
    workflow_state_repository().update(
        lambda current: update_declaration_pointer(
            current,
            modelo=draft.modelo,
            period=draft.period,
            draft_id=draft.draft_id,
            status=draft.status.value,
            exported_path=str(file),
            verified=verdict.verdict is DeclarationVerifyVerdict.MATCH,
        )
    )
    payload = {"verdict": verdict}
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.declaration.labels.draft_id')}\t{verdict.draft_id}",
            f"{tr('cli.declaration.labels.verdict')}\t{verdict.verdict.value}",
            f"{tr('cli.declaration.labels.mismatched')}\t{', '.join(verdict.mismatched_casillas) or '-'}",
        ],
    )
