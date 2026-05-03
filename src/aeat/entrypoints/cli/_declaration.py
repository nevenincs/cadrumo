from __future__ import annotations

from pathlib import Path

import typer

from ...application.filing import (
    DeclarationCalculateSummary,
    DeclarationVerifyVerdict,
    FilingDraft,
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
    EditParseError,
    FilterParseError,
)
from ...application.user_cli import (
    declaration_key,
    state_repository,
    update_declaration_pointer,
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

app = typer.Typer(
    name="declaration",
    help="Declaration drafts: calculate, review, edit, approve, validate, export, verify.",
    no_args_is_help=True,
)


@app.command("calculate", help="Compute a declaration draft from local ledger and invoice records.")
def declaration_calculate(
    ctx: typer.Context,
    period: str = typer.Option(..., "--period"),
    modelo: str = typer.Option(..., "--modelo"),
) -> None:
    canonical_period = _canonical_period(period)
    canonical_modelo = modelo.strip()
    state = _state()
    record = state.active_profile_record()
    if record is None:
        raise _bad("activate a profile first: aeat setup init --name NAME")
    operator = FilingOperatorProfile(
        tax_id=record.values.get("tax.id", "00000000T") or "00000000T",
        display_name=state.active_profile or "operator",
        applicable_modelos=(canonical_modelo,),
    )
    schema_provider = build_runtime_schema_provider()
    inputs = _aggregate_filing_inputs(canonical_modelo, canonical_period, state)
    draft = build_draft(
        modelo=canonical_modelo,
        period=canonical_period,
        profile=operator,
        inputs=inputs,
        schema_provider=schema_provider,
    )
    summary: DeclarationCalculateSummary = summarise_calculation(
        draft,
        repair_hints=tuple(f.message for f in draft.findings if f.severity is FilingFindingSeverity.ERROR),
    )
    _draft_repo().save(draft)
    state_repository().update(
        lambda current: update_declaration_pointer(
            current,
            modelo=canonical_modelo,
            period=canonical_period,
            draft_id=draft.draft_id,
            status=draft.status.value,
        )
    )
    payload = {"draft": draft, "summary": summary}
    _emit(
        ctx,
        payload,
        [
            f"draft_id\t{draft.draft_id}",
            f"status\t{draft.status.value}",
            f"blockers\t{summary.blocker_count}",
            f"warnings\t{summary.warning_count}",
            f"next\t{summary.next_action.value}",
        ],
    )


@app.command("review", help="Show the calculated draft for a (modelo, period) pair.")
def declaration_review(
    ctx: typer.Context,
    period: str | None = typer.Option(None, "--period"),
    modelo: str | None = typer.Option(None, "--modelo"),
    draft_id: str | None = typer.Option(None, "--id"),
    format_: str = typer.Option(_FORMAT_TABLE, "--format", help="text | table | json (alias for root --format)."),
) -> None:
    if draft_id is not None:
        draft = _draft_by_id(draft_id)
    else:
        if period is None or modelo is None:
            raise _bad("either --id or (--period and --modelo) must be provided")
        canonical_period = _canonical_period(period)
        canonical_modelo = modelo.strip()
        state = _state()
        pointer = state.declarations.get(declaration_key(canonical_modelo, canonical_period))
        if pointer is None:
            raise _bad("no draft for that period; run aeat app declaration calculate")
        draft = _draft_by_id(pointer.draft_id)
    if format_.lower() == _FORMAT_JSON or _format_of(ctx) == _FORMAT_JSON:
        ctx.ensure_object(dict)["format"] = _FORMAT_JSON
    payload = {"draft": draft, "values": list(draft.values), "findings": list(draft.findings)}
    lines: list[str] = [f"draft_id\t{draft.draft_id}", f"status\t{draft.status.value}", f"values\t{len(draft.values)}"]
    for value in draft.values:
        lines.append(f"casilla.{value.casilla_id}\t{value.value}\t{value.kind.value}")
    _emit(ctx, payload, lines)


@app.command("status", help="Show declaration draft status filtered by --filter.")
def declaration_status(
    ctx: typer.Context,
    period: str = typer.Option(..., "--period"),
    modelo: str = typer.Option(..., "--modelo"),
    filters: list[str] = typer.Option([], "--filter", help="--filter status=…"),
) -> None:
    try:
        DeclarationReviewFilterSpec.from_strings(filters)
    except FilterParseError as exc:
        raise _bad(f"--filter parse error ({exc.reason}): {exc.raw_token}") from exc
    canonical_period = _canonical_period(period)
    canonical_modelo = modelo.strip()
    state = _state()
    pointer = state.declarations.get(declaration_key(canonical_modelo, canonical_period))
    if pointer is None:
        _emit(ctx, {"present": False}, ["status\tabsent"])
        _exit(2)
    assert pointer is not None
    payload = {
        "draft_id": pointer.draft_id,
        "status": pointer.status,
        "modelo": canonical_modelo,
        "period": canonical_period,
    }
    _emit(ctx, payload, [f"draft_id\t{pointer.draft_id}", f"status\t{pointer.status}"])


@app.command("edit", help="Override casilla values on a draft (--set casilla.NN=DECIMAL).")
def declaration_edit(
    ctx: typer.Context,
    draft_id: str = typer.Option(..., "--id", help="Draft id."),
    sets: list[str] = typer.Option([], "--set", help="--set casilla.NN=DECIMAL."),
    reason: str = typer.Option(..., "--reason"),
) -> None:
    from ...application.review._edit import DeclarationEditSpec

    try:
        edit_spec = DeclarationEditSpec.from_strings(sets)
    except EditParseError as exc:
        raise _bad(f"--set parse error ({exc.reason}): {exc.raw_token}") from exc
    if not edit_spec.casilla_edits:
        raise _bad("declaration edit requires at least one --set casilla.NN=DECIMAL")
    draft = _draft_by_id(draft_id)
    operator = FilingOperatorProfile(
        tax_id=draft.profile_tax_id,
        display_name=draft.profile_tax_id,
        applicable_modelos=(draft.modelo,),
    )
    schema_provider = build_runtime_schema_provider()
    inputs: dict[str, object] = {entry.casilla_id: entry.value for entry in draft.values if entry.value is not None}
    inputs.update(edit_spec.casilla_edits)
    fresh = build_draft(
        modelo=draft.modelo,
        period=draft.period,
        profile=operator,
        inputs=inputs,
        schema_provider=schema_provider,
    )
    _draft_repo().save(fresh)
    state_repository().update(
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
        [f"draft_id\t{fresh.draft_id}", f"status\t{fresh.status.value}", f"edits\t{len(edit_spec.casilla_edits)}"],
    )


@app.command("approve", help="Mark a draft as human-approved.")
def declaration_approve(
    ctx: typer.Context,
    draft_id: str = typer.Option(..., "--id"),
    reviewer: str = typer.Option(..., "--by"),
    reason: str = typer.Option(..., "--reason"),
) -> None:
    draft = _draft_by_id(draft_id)
    schema_provider = build_runtime_schema_provider()
    approved = approve_draft(draft, approved_by=reviewer, schema_provider=schema_provider)
    _draft_repo().save(approved)
    state_repository().update(
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
    _emit(ctx, payload, [f"draft_id\t{approved.draft_id}", f"status\t{approved.status.value}", f"by\t{reviewer}"])


@app.command("validate", help="Re-validate a draft (post-approval).")
def declaration_validate(
    ctx: typer.Context,
    draft_id: str = typer.Option(..., "--id"),
    output: Path | None = typer.Option(None, "--output", help="Write a JSON validation report to PATH."),
) -> None:
    draft = _draft_by_id(draft_id)
    schema_provider = build_runtime_schema_provider()
    refreshed = validate_draft(draft, schema_provider=schema_provider)
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
            f"draft_id\t{refreshed.draft_id}",
            f"status\t{refreshed.status.value}",
            f"findings\t{len(refreshed.findings)}",
        ],
    )


@app.command("preview", help="Render a non-filing preview of the draft's casilla values.")
def declaration_preview(ctx: typer.Context, draft_id: str = typer.Option(..., "--id")) -> None:
    draft = _draft_by_id(draft_id)
    payload = {
        "draft_id": draft.draft_id,
        "modelo": draft.modelo,
        "period": draft.period,
        "values": list(draft.values),
    }
    lines: list[str] = [f"draft_id\t{draft.draft_id}", f"modelo\t{draft.modelo}", f"period\t{draft.period}"]
    for value in draft.values:
        lines.append(f"casilla.{value.casilla_id}\t{value.value}")
    _emit(ctx, payload, lines)


@app.command("export", help="Write the AEAT-compatible payload to PATH (declaration must be APPROVED).")
def declaration_export(
    ctx: typer.Context,
    draft_id: str = typer.Option(..., "--id"),
    output: Path = typer.Option(..., "--output"),
) -> None:
    draft = _draft_by_id(draft_id)
    if draft.status is not FilingDraftStatus.APPROVED:
        raise _bad(f"draft must be APPROVED before export; current status {draft.status.value}")
    headers = _headers_from_draft(draft)
    receipt = export_draft(draft, output_path=output, headers=headers)
    state_repository().update(
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
            f"draft_id\t{receipt.draft_id}",
            f"path\t{receipt.output_path}",
            f"sha256\t{receipt.file_sha256}",
            f"bytes\t{receipt.byte_size}",
        ],
    )


def _headers_from_draft(draft: FilingDraft) -> dict[str, str]:
    """Build the minimum header dictionary the fichero-BOE serialiser needs."""
    ejercicio = draft.period[:4]
    if draft.modelo == "303":
        periodo = draft.period[4:]  # Q1, Q2, etc.
        if periodo.startswith("Q"):
            periodo = f"{periodo[1]}T"

        return {
            "DP30300_F004_EJERCICIO_DE_DEVENGO": ejercicio,
            "DP30300_F008_RESERVADO_PARA_LA_ADMINISTRA": " ",
            "DP30300_F009_VERSI_N_DEL_PROGRAMA": " ",
            "DP30300_F010_RESERVADO_PARA_LA_ADMINISTRA": " ",
            "DP30300_F011_NIF_EMPRESA_DESARROLLO": " ",
            "DP30300_F012_RESERVADO_PARA_LA_ADMINISTRA": " ",
            "DP30301_F006_TIPO_DECLARACI_N": "I",  # Ingreso
            "DP30301_F007_IDENTIFICACI_N_NIF": draft.profile_tax_id,
            "DP30301_F008_IDENTIFICACI_N_APELLIDOS_Y_N": "Operator Name",
            "DP30301_F009_DEVENGO_EJERCICIO": ejercicio,
            "DP30301_F010_DEVENGO_PER_ODO": periodo,
        }

    return {
        "NIF": draft.profile_tax_id,
        "EJERCICIO": ejercicio,
    }


@app.command("verify", help="Verify a previously exported file against the approved draft.")
def declaration_verify(
    ctx: typer.Context,
    draft_id: str = typer.Option(..., "--id"),
    file: Path = typer.Option(..., "--file"),
) -> None:
    draft = _draft_by_id(draft_id)
    if not file.exists():
        raise _bad(f"file {file} does not exist")
    verdict = verify_export(draft, file_path=file)
    state_repository().update(
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
            f"draft_id\t{verdict.draft_id}",
            f"verdict\t{verdict.verdict.value}",
            f"mismatched\t{', '.join(verdict.mismatched_casillas) or '-'}",
        ],
    )
