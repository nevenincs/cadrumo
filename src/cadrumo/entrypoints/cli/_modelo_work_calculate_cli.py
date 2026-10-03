"""Registered runtime transport and existing CLI presentation for Modelo calculation."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import typer
from pydantic import ValidationError

from ...application.modelo.action_errors import M303FilingEvidenceError
from ...application.modelo.calculation_request_fields import ModeloCalculationInputFieldsV1, ModeloCalculationOverride
from ...application.modelo.m303_filing_evidence import m303_filing_evidence_failure
from ...application.modelo.operation_definitions import (
    ModeloWorkCalculateCallerContext,
    ModeloWorkCalculateOrdinaryM303EvidenceRequestV2,
    ModeloWorkCalculatePublicResultV2,
    ModeloWorkCalculateRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.external_constants import OutputLanguage
from ...core.hashing import canonical_json_bytes
from ...core.i18n.render import output_language as current_output_language
from ...core.i18n.render import tr
from ...core.irnr import M210GrossIncomeSourceMode
from ...core.json_contract import Notice
from ...core.rescate_type import RescateType
from ._modelo_cli_support import (
    optional_decimal_option,
    parse_work_calculate_wire_specs,
    resolve_actor_option,
)
from ._modelo_payloads import WorkCalculateResult
from ._modelo_rendering import (
    m210_plazo_notice,
    source_diagnostic_notice,
    source_diagnostic_notice_text,
    work_deadline_output_from_posture,
    work_plazo_lines_from_posture,
)
from .common import activate_subcommand_output_language, emit_envelope, no_active_profile_refusal
from .errors import CliOutboundPayloadBoundaryError
from .modelo_revision_rendering import calculation_revision_state_label
from .runtime_modelo_calculation import (
    calculation_snapshot_lines,
    calculation_snapshot_payload,
    run_modelo_work_calculation,
)
from .runtime_modelo_metadata import read_modelo_work_unit
from .runtime_profile_binding import require_profile_client

if TYPE_CHECKING:
    from ...application.aggregation.source_mesh import CalculationSourceDiagnostic
    from ...application.modelo.printed_boxes import PrintedBoxes


def _validated_amount(raw: str | None, *, translation_key: str) -> str | None:
    """Keep the existing CLI euro-cent grammar before registered submission."""
    amount = optional_decimal_option(raw, translation_key=translation_key, default="")
    return str(amount) if amount is not None else None


def _run_work_calculate(
    *,
    ctx: typer.Context,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None,
    casilla: list[str] | None,
    binding: list[str] | None,
    borrador_snapshot_id: str | None,
    m210_gross_income_source: M210GrossIncomeSourceMode,
    actor: str | None,
    relation: list[str] | None,
    row: list[str] | None,
    prestacion_inss_exenta: str | None,
    rescate_plan_pensiones_capital: str | None,
    rescate_plan_pensiones_aportaciones_pre_2007: str | None,
    rescate_plan_pensiones_aportaciones_totales: str | None,
    rescate_type: RescateType | None,
    contingencia_year: int | None,
    rescate_year: int | None,
    sal_beneficio_neto: str | None,
    sal_reserva_dotada: str | None,
    sal_capital_social: str | None,
    autoconsumo_promotor_base: str | None,
    joint_return_elected: bool | None,
    m303_exonerado_390_attachment_id: str | None,
    m303_exonerado_390_sha256: str | None,
    output_language: OutputLanguage | None,
) -> None:
    activate_subcommand_output_language(ctx, output_language)
    target = resolve_active_bucket_id()
    if target is None:
        raise no_active_profile_refusal()
    client = require_profile_client(ctx, expected_profile_id=UUID(target))
    unit = read_modelo_work_unit(
        ctx,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )
    casilla_pairs, binding_pairs, relation_pairs, detail_rows = parse_work_calculate_wire_specs(
        casilla=casilla, binding=binding, relation=relation, row=row
    )
    inputs = ModeloCalculationInputFieldsV1(
        casilla_overrides=tuple(
            ModeloCalculationOverride(key=str(key), value=value) for key, value in casilla_pairs.items()
        ),
        binding_overrides=tuple(
            ModeloCalculationOverride(key=str(key), value=value) for key, value in binding_pairs.items()
        ),
        relation_overrides=tuple(
            ModeloCalculationOverride(key=str(key), value=value) for key, value in relation_pairs.items()
        ),
        borrador_snapshot_id=borrador_snapshot_id,
        m210_gross_income_source_mode=m210_gross_income_source,
        prestacion_inss_exenta=_validated_amount(
            prestacion_inss_exenta, translation_key="cli.app.modelo.work.prestacion_inss_exenta_not_decimal"
        ),
        rescate_plan_pensiones_capital=_validated_amount(
            rescate_plan_pensiones_capital, translation_key="cli.app.modelo.work.rescate_plan_pensiones_not_decimal"
        ),
        rescate_plan_pensiones_aportaciones_pre_2007=_validated_amount(
            rescate_plan_pensiones_aportaciones_pre_2007,
            translation_key="cli.app.modelo.work.rescate_plan_pensiones_not_decimal",
        ),
        rescate_plan_pensiones_aportaciones_totales=_validated_amount(
            rescate_plan_pensiones_aportaciones_totales,
            translation_key="cli.app.modelo.work.rescate_plan_pensiones_not_decimal",
        ),
        rescate_type=rescate_type,
        contingencia_year=contingencia_year,
        rescate_year=rescate_year,
        sal_beneficio_neto=_validated_amount(
            sal_beneficio_neto, translation_key="cli.app.modelo.work.sal_reserva_not_decimal"
        ),
        sal_reserva_dotada=_validated_amount(
            sal_reserva_dotada, translation_key="cli.app.modelo.work.sal_reserva_not_decimal"
        ),
        sal_capital_social=_validated_amount(
            sal_capital_social, translation_key="cli.app.modelo.work.sal_reserva_not_decimal"
        ),
        autoconsumo_promotor_base=_validated_amount(
            autoconsumo_promotor_base, translation_key="cli.app.modelo.work.sal_reserva_not_decimal"
        ),
    )
    supplied_m303 = (
        joint_return_elected is not None
        or m303_exonerado_390_attachment_id is not None
        or m303_exonerado_390_sha256 is not None
    )
    ordinary_m303 = (
        ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(
            joint_return_elected=joint_return_elected,
            m303_exonerado_390_attachment_id=m303_exonerado_390_attachment_id,
            m303_exonerado_390_sha256=m303_exonerado_390_sha256,
        )
        if supplied_m303 and joint_return_elected is not None
        else None
    )
    if supplied_m303 and joint_return_elected is None:
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "missing", {"modelo": str(unit.modelo), "evidence_present": True}
            )
        )
    try:
        request = ModeloWorkCalculateRequest.model_validate_json(
            canonical_json_bytes(
                {
                    "work_unit_id": str(unit.work_unit_id),
                    "actor": resolve_actor_option(actor),
                    "caller_context": ModeloWorkCalculateCallerContext.EXPLICIT.value,
                    "ordinary_m303_filing_evidence": ordinary_m303.model_dump(mode="json") if ordinary_m303 else None,
                    "inputs": inputs.model_dump(mode="json"),
                    "detail_rows": [item.model_dump(mode="json") for item in detail_rows],
                }
            )
        )
    except ValidationError as exc:
        raise CliOutboundPayloadBoundaryError(exc, record=ModeloWorkCalculateRequest) from exc
    completed = run_modelo_work_calculation(client, request)
    projection = completed.projection
    if not isinstance(projection, ModeloWorkCalculatePublicResultV2):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    snapshot = projection.calculation
    advisories = projection.advisories
    language = OutputLanguage(current_output_language())
    saved_confirmation = tr(
        "cli.app.modelo.work.calculate_saved",
        revision_id=snapshot.calculation_revision_id,
        state=calculation_revision_state_label(snapshot.state.value),
    )
    modality = advisories.to_modality()
    modality_payload = {"modality": modality.modality, "modality_reason": modality.reason} if modality else {}
    modality_lines = [f"modality\t{modality.modality}"] if modality else []
    source_advisory_notices, source_advisory_lines = _work_calculate_source_advisory_output(
        advisories.to_diagnostics(), advisories.to_printed_boxes()
    )
    posture = advisories.to_deadline_posture()
    deadline_payload, deadline_notices = work_deadline_output_from_posture(
        posture, fallback_legal_ref=advisories.fallback_recargo_legal_ref
    )
    try:
        result = WorkCalculateResult.model_validate(
            {
                "saved": True,
                "saved_confirmation": saved_confirmation,
                **calculation_snapshot_payload(snapshot, language=language).model_dump(mode="python"),
                **modality_payload,
                "deadline": deadline_payload.model_dump(mode="python") if deadline_payload is not None else None,
            }
        )
    except ValidationError as exc:
        raise CliOutboundPayloadBoundaryError(exc, record=WorkCalculateResult) from exc
    emit_envelope(
        ctx,
        command="modelo.work.calculate",
        result=result,
        lines=[
            "operation\tmodelo.work.calculate",
            *calculation_snapshot_lines(snapshot, language=language),
            *modality_lines,
            *work_plazo_lines_from_posture(posture),
            *source_advisory_lines,
            saved_confirmation,
        ],
        notices=[
            *source_advisory_notices,
            *(m210_plazo_notice(item) for item in advisories.to_plazo_resolutions()),
            *deadline_notices,
        ],
    )


def _work_calculate_source_advisory_output(
    diagnostics: tuple[CalculationSourceDiagnostic, ...],
    boxes: PrintedBoxes | None = None,
) -> tuple[list[Notice], list[str]]:
    """Project NON-blocking source diagnostics into notices + human lines.

    Each diagnostic the source mesh raised while resolving the bucket ledger
    (notably the unconsumed-declarable-IVA advisory) becomes one
    warning-severity :class:`Notice` on the envelope
    ``notices`` channel and one human-facing ADVISORY line. The structured
    provenance (``reason`` / ``source_kind`` / ``resolver_id``) rides on the
    notice ``context`` so no machine-queryable field is lost relative to the
    former bespoke ``source_advisories`` payload list. The calculation succeeded;
    these advisories keep an unrouted declarable observation from being silently
    under-declared (no-silent-under-declaration). The diagnostic ``message``
    already carries the observation's category / rate / flow provenance.

    A diagnostic's free-form ``remedy`` is not an executable action and is not
    projected through the notice channel. The notice retains only its typed
    diagnostic context; the canonical calculation result remains responsible
    for any domain-specific guidance.

    The text lines are rebuilt from the notices, so their rendered diagnostic
    content and the JSON envelope cannot drift.
    """
    if not diagnostics:
        return ([], [])
    notices: list[Notice] = []
    seen_notices: set[str] = set()
    for diagnostic in diagnostics:
        notice = source_diagnostic_notice(diagnostic, code="modelo.work.calculate.source_advisory", boxes=boxes)
        notice_identity = notice.model_dump_json()
        if notice_identity in seen_notices:
            continue
        seen_notices.add(notice_identity)
        notices.append(notice)
    lines: list[str] = []
    seen_lines: set[str] = set()
    for notice in notices:
        line = source_diagnostic_notice_text(notice)
        if line not in seen_lines:
            lines.append(line)
            seen_lines.add(line)
    return (notices, lines)


__all__ = ["work_calculate"]


def work_calculate(
    ctx: typer.Context,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    bucket_id: str | None = None,
    casilla: list[str] | None = None,
    binding: list[str] | None = None,
    borrador_snapshot_id: str | None = None,
    m210_gross_income_source: M210GrossIncomeSourceMode = M210GrossIncomeSourceMode.MANUAL,
    actor: str | None = None,
    relation: list[str] | None = None,
    row: list[str] | None = None,
    prestacion_inss_exenta: str | None = None,
    rescate_plan_pensiones_capital: str | None = None,
    rescate_plan_pensiones_aportaciones_pre_2007: str | None = None,
    rescate_plan_pensiones_aportaciones_totales: str | None = None,
    rescate_type: RescateType | None = None,
    contingencia_year: int | None = None,
    rescate_year: int | None = None,
    sal_beneficio_neto: str | None = None,
    sal_reserva_dotada: str | None = None,
    sal_capital_social: str | None = None,
    autoconsumo_promotor_base: str | None = None,
    joint_return_elected: bool | None = None,
    m303_exonerado_390_attachment_id: str | None = None,
    m303_exonerado_390_sha256: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Persist a new draft :class:`CalculationRevision` for the resolved work unit."""
    _run_work_calculate(
        ctx=ctx,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
        casilla=casilla,
        binding=binding,
        borrador_snapshot_id=borrador_snapshot_id,
        m210_gross_income_source=m210_gross_income_source,
        actor=actor,
        relation=relation,
        row=row,
        prestacion_inss_exenta=prestacion_inss_exenta,
        rescate_plan_pensiones_capital=rescate_plan_pensiones_capital,
        rescate_plan_pensiones_aportaciones_pre_2007=rescate_plan_pensiones_aportaciones_pre_2007,
        rescate_plan_pensiones_aportaciones_totales=rescate_plan_pensiones_aportaciones_totales,
        rescate_type=rescate_type,
        contingencia_year=contingencia_year,
        rescate_year=rescate_year,
        sal_beneficio_neto=sal_beneficio_neto,
        sal_reserva_dotada=sal_reserva_dotada,
        sal_capital_social=sal_capital_social,
        autoconsumo_promotor_base=autoconsumo_promotor_base,
        joint_return_elected=joint_return_elected,
        m303_exonerado_390_attachment_id=m303_exonerado_390_attachment_id,
        m303_exonerado_390_sha256=m303_exonerado_390_sha256,
        output_language=output_language,
    )
