# ruff: noqa: E501
"""Behavior for modelo work calculation commands.

This CLI module is a transport boundary around
:func:`calculate_modelo_work_revision`. It resolves the
operator target, builds a public
:class:`WorkCalculateInputBundle`, calls the application
service, and serializes the resulting
:class:`ModeloWorkCalculationServiceResult` into a
:class:`WorkCalculateResult` envelope.

The emitted confirmation is centered on the persisted
:class:`CalculationRevision` and parent
:class:`WorkUnit`;
advisory material such as backend authorization and non-blocking source
diagnostics is carried on the uniform
:class:`Notice` channel instead of bespoke payload
fields.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from pydantic import ValidationError

from ...application.modelo._action_errors import (
    CalculationRegistryUnavailableError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
)
from ...application.modelo._calculate_input import calculate_modelo_work_revision
from ...application.modelo._iva_wallet_gate import ModeloIvaWalletReconciliationBlocked
from ...application.modelo.borrador_binding import Modelo100BorradorBindingError
from ...core.external_constants import OutputLanguage
from ...core.i18n._render import tr
from ...core.irnr import M210GrossIncomeSourceMode
from ...core.json_contract import Notice
from ...core.rescate_type import RescateType
from ...domain.calculations.registry.errors import RegistryValidationError
from ._common import activate_subcommand_output_language, emit_envelope
from ._m303_filing_evidence_input import m303_filing_instance_evidence_from_cli
from ._modelo_behavior_support import require_active_profile, resolve_work_unit_for_cli
from ._modelo_cli_support import (
    bad_parameter_from_error,
    resolve_actor_option,
    work_calculate_input_bundle_from_cli,
)
from ._modelo_payloads import WorkCalculateResult
from ._modelo_rendering import (
    advisory_notice,
    calculation_revision_lines,
    calculation_revision_payload,
    calculation_revision_state_label,
    m210_plazo_notice,
    source_diagnostic_notice,
    source_diagnostic_notice_text,
    work_unit_deadline_output,
    work_unit_plazo_lines,
)
from .errors import CliOutboundPayloadBoundaryError

if TYPE_CHECKING:
    from ...application.aggregation import CalculationSourceDiagnostic
    from ...application.modelo._calculate_input import ModeloWorkCalculationServiceResult
    from ...domain.modelos.calculation_revision import CalculationRevision
    from ...domain.modelos.work_unit import WorkUnit


@dataclass(frozen=True, slots=True)
class _CalculateDeps:
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None]
    require_active_profile: Callable[[], None]
    resolve_work_unit_for_cli: Callable[..., Any]
    resolve_actor_option: Callable[[str | None], str]
    calculate_input_bundle_from_cli: Callable[..., Any]
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter]


def _calculate_dependencies() -> _CalculateDeps:
    return _CalculateDeps(
        activate_output_language=activate_subcommand_output_language,
        require_active_profile=require_active_profile,
        resolve_work_unit_for_cli=resolve_work_unit_for_cli,
        resolve_actor_option=resolve_actor_option,
        calculate_input_bundle_from_cli=work_calculate_input_bundle_from_cli,
        bad_parameter_from_error=bad_parameter_from_error,
    )


def _run_work_calculate(
    *,
    deps: _CalculateDeps,
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
    m303_filing_evidence: Path | None,
    output_language: OutputLanguage | None,
) -> None:
    deps.activate_output_language(ctx, output_language)
    deps.require_active_profile()
    unit = deps.resolve_work_unit_for_cli(
        work_unit_id=work_unit_id, modelo=modelo, year=year, period=period, revision=revision, bucket_id=bucket_id
    )
    resolved_work_unit_id = unit.work_unit_id
    filing_instance_evidence = m303_filing_instance_evidence_from_cli(
        modelo=str(unit.modelo), period=unit.period, evidence_file=m303_filing_evidence
    )
    calculation_inputs = deps.calculate_input_bundle_from_cli(
        work_unit_id=resolved_work_unit_id,
        casilla=casilla,
        binding=binding,
        relation=relation,
        row=row,
        borrador_snapshot_id=borrador_snapshot_id,
        m210_gross_income_source_mode=m210_gross_income_source,
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
        filing_instance_evidence=filing_instance_evidence,
    )
    resolved_actor = deps.resolve_actor_option(actor)
    try:
        calculation_result = calculate_modelo_work_revision(
            work_unit_id=resolved_work_unit_id, actor=resolved_actor, inputs=calculation_inputs
        )
    except RegistryValidationError as exc:
        raise deps.bad_parameter_from_error(exc) from exc
    except WorkUnitMutationRefusedError:
        raise
    except (
        WorkUnitNotFoundError,
        CalculationRegistryUnavailableError,
        Modelo100BorradorBindingError,
        ModeloIvaWalletReconciliationBlocked,
    ) as exc:
        raise deps.bad_parameter_from_error(exc) from exc
    except ValidationError as exc:
        raise CliOutboundPayloadBoundaryError(exc) from exc
    try:
        calculation_revision = calculation_result.revision
        unit_for_modality = calculation_result.work_unit
        saved_confirmation = _work_calculate_saved_confirmation(calculation_revision, unit_for_modality)
        modality_payload, modality_lines = _work_calculate_modality_output(calculation_result)
        authorization_payload, authorization_notices, authorization_lines = _work_calculate_authorization_output(
            calculation_result, work_unit=unit_for_modality
        )
        source_advisory_notices, source_advisory_lines = _work_calculate_source_advisory_output(
            calculation_result.source_diagnostics
        )
        deadline_payload, deadline_notices = work_unit_deadline_output(unit_for_modality)
        result = WorkCalculateResult.model_validate(
            {
                "saved": True,
                "saved_confirmation": saved_confirmation,
                **calculation_revision_payload(calculation_revision).model_dump(
                    mode="python",
                    exclude={"source_provenance"},
                ),
                **modality_payload,
                **authorization_payload,
                "deadline": deadline_payload.model_dump(mode="python") if deadline_payload is not None else None,
            }
        )
    except ValidationError as exc:
        raise CliOutboundPayloadBoundaryError(exc, record=WorkCalculateResult) from exc
    lines = [
        "operation\tmodelo.work.calculate",
        *calculation_revision_lines(calculation_revision),
        *modality_lines,
        *work_unit_plazo_lines(unit_for_modality),
        *authorization_lines,
        *source_advisory_lines,
        saved_confirmation,
    ]
    emit_envelope(
        ctx,
        command="modelo.work.calculate",
        result=result,
        lines=lines,
        notices=[
            *authorization_notices,
            *source_advisory_notices,
            *(m210_plazo_notice(resolution) for resolution in calculation_result.plazo_resolutions),
            *deadline_notices,
        ],
    )


def _work_calculate_saved_confirmation(revision: CalculationRevision, work_unit: WorkUnit) -> str:
    return tr(
        "cli.app.modelo.work.calculate_saved",
        revision_id=revision.calculation_revision_id,
        state=calculation_revision_state_label(revision.state.value),
        modelo=work_unit.modelo,
        year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )


def _work_calculate_modality_output(
    calculation_result: ModeloWorkCalculationServiceResult,
) -> tuple[dict[str, object], list[str]]:
    modality = calculation_result.modality
    if modality is None:
        return ({}, [])
    return ({"modality": modality.modality, "modality_reason": modality.reason}, [f"modality\t{modality.modality}"])


def _work_calculate_authorization_output(
    calculation_result: ModeloWorkCalculationServiceResult, *, work_unit: WorkUnit
) -> tuple[dict[str, object], list[Notice], list[str]]:
    """Project the unauthorized-backend advisory onto a notice + payload state + lines.

    ``authorization_state`` remains structured result data (the backend's
    authorization lifecycle state); the advisory prose moves onto the
    uniform :class:`Notice` channel so it is no longer a
    bespoke ``authorization_advisory`` payload field. The text lines are
    unchanged.
    """
    advisory = calculation_result.authorization_advisory
    if advisory is None:
        return ({}, [], [])
    advisory_text = tr(
        "cli.app.modelo.work.calculate_unauthorized_advisory",
        modelo=str(work_unit.modelo),
        default="ADVISORY: modelo %{modelo} calculation backend is UNAUTHORIZED - it has not yet been proven by an end-to-end test across at least two renta years (multi-year-renta authorization gate). The result was computed and saved, but treat it as provisional until the modelo is authorized.",
    )
    return (
        {"authorization_state": advisory.state},
        [
            advisory_notice(
                "modelo.work.calculate.unauthorized_backend",
                advisory_text,
                context={"authorization_state": str(advisory.state)},
            )
        ],
        [f"authorization_state\t{advisory.state}", advisory_text],
    )


def _work_calculate_source_advisory_output(
    diagnostics: tuple[CalculationSourceDiagnostic, ...],
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
        notice = source_diagnostic_notice(diagnostic, code="modelo.work.calculate.source_advisory")
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
    m303_filing_evidence: Path | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Persist a new draft :class:`CalculationRevision` for the resolved work unit."""
    _run_work_calculate(
        deps=_calculate_dependencies(),
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
        m303_filing_evidence=m303_filing_evidence,
        output_language=output_language,
    )
