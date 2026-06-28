"""Typer registration for modelo work calculation commands.

Renders the operator-facing confirmation for a persisted
:class:`CalculationRevision` once a work unit's calculation is saved.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any

import typer

from ...application.modelo import (
    CalculationRegistryUnavailableError,
    Modelo100BorradorBindingError,
    ModeloIvaWalletReconciliationBlocked,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    calculate_modelo_work_revision,
)
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ...core.json_contract import Notice
from ...domain.calculations.registry import RegistryValidationError
from ._common import _emit_envelope
from ._modelo_cli_support import OutputLanguageOpt
from ._modelo_payloads import WorkCalculateResult
from ._modelo_rendering import (
    advisory_notice,
    calculation_revision_lines,
    calculation_revision_payload,
    work_unit_deadline_output,
    work_unit_plazo_lines,
)

if TYPE_CHECKING:
    # Annotation-only imports: ``from __future__ import annotations`` keeps these
    # as lazy strings so the state-free CLI surface (test_lazy_command_tree) pays
    # no runtime registry-import cost, while pyright and the any-param ratchet see
    # the concrete result/record types instead of a bare ``Any``.
    from ...application.modelo import ModeloWorkCalculationServiceResult, WorkUnit
    from ...domain.modelos import CalculationRevision


@dataclass(frozen=True, slots=True)
class _CalculateDeps:
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None]
    require_active_profile: Callable[[], None]
    resolve_work_unit_for_cli: Callable[..., Any]
    resolve_default_actor: Callable[[], str]
    calculate_input_bundle_from_cli: Callable[..., Any]
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter]
    missing_binding_guidance: Callable[[RegistryValidationError, str], str]


_WorkUnitIdArg = Annotated[str | None, typer.Argument(help=tr("cli.app.modelo.work.work_unit_id_help"))]
_ModeloOpt = Annotated[str | None, typer.Option("--modelo", help=tr("cli.app.modelo.work.modelo_help"))]
_YearOpt = Annotated[int | None, typer.Option("--year", help=tr("cli.app.modelo.work.year_help"))]
_PeriodOpt = Annotated[str | None, typer.Option("--period", help=tr("cli.app.modelo.work.period_help"))]
_RevisionOpt = Annotated[str | None, typer.Option("--revision", help=tr("cli.app.modelo.work.revision_help"))]
_BucketIdOpt = Annotated[str | None, typer.Option("--bucket-id", help=tr("cli.app.modelo.work.bucket_id_help"))]
_CasillaOpt = Annotated[
    list[str] | None,
    typer.Option("--casilla", help=tr("cli.app.modelo.work.casilla_help")),
]
_BindingOpt = Annotated[
    list[str] | None,
    typer.Option("--binding", help=tr("cli.app.modelo.work.override_help")),
]
_BorradorSnapshotOpt = Annotated[
    str | None,
    typer.Option(
        "--borrador",
        help=tr(
            "cli.app.modelo.work.borrador_help",
            default=(
                "Modelo 100 borrador snapshot id (full or unambiguous prefix). "
                "Snapshot binding values flow into the calculation for registry "
                "bindings marked aeat_prefilled; caller --binding overrides always take precedence."
            ),
        ),
    ),
]
_ActorOpt = Annotated[str | None, typer.Option("--by", help=tr("cli.app.modelo.work.actor_help"))]
_RelationOpt = Annotated[
    list[str] | None,
    typer.Option(
        "--relation",
        help=tr(
            "cli.app.modelo.work.relation_help",
            default=(
                "Registry relation value as KEY=VALUE (repeatable). KEY is a registry relation id, "
                "not a binding id; use this for cross-period or cross-modelo relation inputs. "
                "Run `aeat app modelo bindings list --missing` for scoped relation guidance. "
                "For Modelo 200 M202 pagos fraccionados, use the mutually exclusive 40.3 casilla 34 "
                "and 40.2 casilla 03 relation channels, setting the unused modality to 0 when "
                "entering manual values."
            ),
        ),
    ),
]
_RowOpt = Annotated[
    list[str] | None,
    typer.Option(
        "--row",
        help=tr(
            "cli.app.modelo.work.row_help",
            default=(
                "Typed detail row for multi-record informational modelos. Format: TYPE FIELD=value "
                "[FIELD=value ...]. TYPE is 'miembro' (M184 atribución member) or 'vinculada' "
                "(M232 operación vinculada). Repeat to add multiple rows. M184 example: "
                "--row 'miembro nif=12345678A porcentaje=40 importe=10000'. M232 example: "
                "--row 'vinculada nif=A12345678 tipo_operacion=01 importe=50000'."
            ),
        ),
    ),
]
_PrestacionInssExentaOpt = Annotated[
    str | None,
    typer.Option(
        "--prestacion-inss-exenta",
        help=tr(
            "cli.app.modelo.work.prestacion_inss_exenta_help",
            default=(
                "Importe íntegro de prestaciones INSS maternidad/paternidad exentas "
                "(Art. 7.h LIRPF). Se registra en casilla 0058 (rev. 2024) o 0059 (rev. 2025) "
                "y se descuenta del total de ingresos computables. Introduce el importe bruto "
                "recibido de la Seguridad Social por baja de maternidad o paternidad. "
                "NO lo incluyas en --casilla 0003."
            ),
        ),
    ),
]
_MesesTrabajoHijoOpt = Annotated[
    list[str] | None,
    typer.Option(
        "--meses-trabajo-con-hijo-menor-3",
        help=tr(
            "cli.app.modelo.work.meses_trabajo_con_hijo_menor_3_help",
            default=(
                "Meses trabajados mientras el hijo menor de 3 años estaba en la unidad familiar "
                "(Art. 81 LIRPF deducción maternidad). Formato: HIJO_ID=MESES. Repetible por "
                "cada hijo. HIJO_ID es un identificador libre. Se calcula sum(min(MESES x 100, 1200)) "
                "y se inyecta en casilla 0611."
            ),
        ),
    ),
]
_RescateCapitalOpt = Annotated[
    str | None,
    typer.Option(
        "--rescate-plan-pensiones-capital",
        help=tr(
            "cli.app.modelo.work.rescate_plan_pensiones_capital_help",
            default=(
                "Importe bruto del rescate del plan de pensiones en forma de capital "
                "(DT 12a LIRPF). Usalo junto con --rescate-plan-pensiones-aportaciones-pre-2007 "
                "y --rescate-plan-pensiones-aportaciones-totales."
            ),
        ),
    ),
]
_RescatePre2007Opt = Annotated[
    str | None,
    typer.Option(
        "--rescate-plan-pensiones-aportaciones-pre-2007",
        help=tr(
            "cli.app.modelo.work.rescate_plan_pensiones_aportaciones_pre_2007_help",
            default=(
                "Aportaciones realizadas al plan de pensiones hasta el 31-dic-2006 (base prorrateo DT 12a LIRPF)."
            ),
        ),
    ),
]
_RescateTotalesOpt = Annotated[
    str | None,
    typer.Option(
        "--rescate-plan-pensiones-aportaciones-totales",
        help=tr(
            "cli.app.modelo.work.rescate_plan_pensiones_aportaciones_totales_help",
            default="Total de aportaciones al plan de pensiones (denominador del prorrateo DT 12a LIRPF).",
        ),
    ),
]
_SalBeneficioOpt = Annotated[
    str | None,
    typer.Option(
        "--sal-beneficio-neto",
        help=tr(
            "cli.app.modelo.work.sal_beneficio_neto_help",
            default=("Beneficio neto del ejercicio de la Sociedad Laboral (SAL/SLL) (Ley 44/2015 Art. 14)."),
        ),
    ),
]
_SalReservaOpt = Annotated[
    str | None,
    typer.Option(
        "--sal-reserva-dotada",
        help=tr(
            "cli.app.modelo.work.sal_reserva_dotada_help",
            default="Reserva especial acumulada en ejercicios anteriores (Ley 44/2015 Art. 14).",
        ),
    ),
]
_SalCapitalOpt = Annotated[
    str | None,
    typer.Option(
        "--sal-capital-social",
        help=tr(
            "cli.app.modelo.work.sal_capital_social_help",
            default="Capital social de la Sociedad Laboral (Ley 44/2015 Art. 14).",
        ),
    ),
]
_AutoconsumoPromotorOpt = Annotated[
    str | None,
    typer.Option(
        "--autoconsumo-promotor-base",
        help=tr(
            "cli.app.modelo.work.autoconsumo_promotor_base_help",
            default=(
                "Base imponible del autoconsumo del promotor inmobiliario "
                "(Art. 9.1.c + Art. 79.4 LISIVA). Solo aplicable a Modelo 303."
            ),
        ),
    ),
]


# KWARGS-ANY-RATIONALE-CLI-DI-RESOLVERS: resolve_work_unit_for_cli and
# calculate_input_bundle_from_cli are injected resolver callables whose concrete
# return type varies by call site; Callable[..., Any] is the DI composition seam.
def register_work_calculate_commands(
    work_app: typer.Typer,
    *,
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None],
    require_active_profile: Callable[[], None],
    resolve_work_unit_for_cli: Callable[..., Any],
    resolve_default_actor: Callable[[], str],
    calculate_input_bundle_from_cli: Callable[..., Any],
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter],
    missing_binding_guidance: Callable[[RegistryValidationError, str], str],
) -> None:
    """Register work calculation commands on the modelo work app."""
    deps = _CalculateDeps(
        activate_output_language=activate_output_language,
        require_active_profile=require_active_profile,
        resolve_work_unit_for_cli=resolve_work_unit_for_cli,
        resolve_default_actor=resolve_default_actor,
        calculate_input_bundle_from_cli=calculate_input_bundle_from_cli,
        bad_parameter_from_error=bad_parameter_from_error,
        missing_binding_guidance=missing_binding_guidance,
    )

    @work_app.command("calculate", help=tr("cli.app.modelo.work.calculate_help"))
    def work_calculate(
        ctx: typer.Context,
        work_unit_id: _WorkUnitIdArg = None,
        modelo: _ModeloOpt = None,
        year: _YearOpt = None,
        period: _PeriodOpt = None,
        revision: _RevisionOpt = None,
        bucket_id: _BucketIdOpt = None,
        casilla: _CasillaOpt = None,
        binding: _BindingOpt = None,
        borrador_snapshot_id: _BorradorSnapshotOpt = None,
        actor: _ActorOpt = None,
        relation: _RelationOpt = None,
        row: _RowOpt = None,
        prestacion_inss_exenta: _PrestacionInssExentaOpt = None,
        meses_trabajo_con_hijo_menor_3: _MesesTrabajoHijoOpt = None,
        rescate_plan_pensiones_capital: _RescateCapitalOpt = None,
        rescate_plan_pensiones_aportaciones_pre_2007: _RescatePre2007Opt = None,
        rescate_plan_pensiones_aportaciones_totales: _RescateTotalesOpt = None,
        sal_beneficio_neto: _SalBeneficioOpt = None,
        sal_reserva_dotada: _SalReservaOpt = None,
        sal_capital_social: _SalCapitalOpt = None,
        autoconsumo_promotor_base: _AutoconsumoPromotorOpt = None,
        output_language: OutputLanguageOpt = None,
    ) -> None:
        """Persist a new draft calculation revision for the work unit."""
        _run_work_calculate(
            deps=deps,
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
            actor=actor,
            relation=relation,
            row=row,
            prestacion_inss_exenta=prestacion_inss_exenta,
            meses_trabajo_con_hijo_menor_3=meses_trabajo_con_hijo_menor_3,
            rescate_plan_pensiones_capital=rescate_plan_pensiones_capital,
            rescate_plan_pensiones_aportaciones_pre_2007=rescate_plan_pensiones_aportaciones_pre_2007,
            rescate_plan_pensiones_aportaciones_totales=rescate_plan_pensiones_aportaciones_totales,
            sal_beneficio_neto=sal_beneficio_neto,
            sal_reserva_dotada=sal_reserva_dotada,
            sal_capital_social=sal_capital_social,
            autoconsumo_promotor_base=autoconsumo_promotor_base,
            output_language=output_language,
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
    actor: str | None,
    relation: list[str] | None,
    row: list[str] | None,
    prestacion_inss_exenta: str | None,
    meses_trabajo_con_hijo_menor_3: list[str] | None,
    rescate_plan_pensiones_capital: str | None,
    rescate_plan_pensiones_aportaciones_pre_2007: str | None,
    rescate_plan_pensiones_aportaciones_totales: str | None,
    sal_beneficio_neto: str | None,
    sal_reserva_dotada: str | None,
    sal_capital_social: str | None,
    autoconsumo_promotor_base: str | None,
    output_language: OutputLanguage | None,
) -> None:
    deps.activate_output_language(ctx, output_language)
    deps.require_active_profile()
    unit = deps.resolve_work_unit_for_cli(
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )
    resolved_work_unit_id = unit.work_unit_id
    calculation_inputs = deps.calculate_input_bundle_from_cli(
        work_unit_id=resolved_work_unit_id,
        casilla=casilla,
        binding=binding,
        relation=relation,
        row=row,
        borrador_snapshot_id=borrador_snapshot_id,
        prestacion_inss_exenta=prestacion_inss_exenta,
        meses_trabajo_con_hijo_menor_3=meses_trabajo_con_hijo_menor_3,
        rescate_plan_pensiones_capital=rescate_plan_pensiones_capital,
        rescate_plan_pensiones_aportaciones_pre_2007=rescate_plan_pensiones_aportaciones_pre_2007,
        rescate_plan_pensiones_aportaciones_totales=rescate_plan_pensiones_aportaciones_totales,
        sal_beneficio_neto=sal_beneficio_neto,
        sal_reserva_dotada=sal_reserva_dotada,
        sal_capital_social=sal_capital_social,
        autoconsumo_promotor_base=autoconsumo_promotor_base,
    )

    try:
        calculation_result = calculate_modelo_work_revision(
            work_unit_id=resolved_work_unit_id,
            actor=actor or deps.resolve_default_actor(),
            inputs=calculation_inputs,
        )
    except RegistryValidationError as exc:
        raise typer.BadParameter(deps.missing_binding_guidance(exc, resolved_work_unit_id)) from exc
    except (
        WorkUnitNotFoundError,
        WorkUnitMutationRefusedError,
        CalculationRegistryUnavailableError,
        Modelo100BorradorBindingError,
        ModeloIvaWalletReconciliationBlocked,
    ) as exc:
        raise deps.bad_parameter_from_error(exc) from exc

    calculation_revision = calculation_result.revision
    unit_for_modality = calculation_result.work_unit
    saved_confirmation = _work_calculate_saved_confirmation(calculation_revision, unit_for_modality)
    modality_payload, modality_lines = _work_calculate_modality_output(calculation_result)
    authorization_payload, authorization_notices, authorization_lines = _work_calculate_authorization_output(
        calculation_result,
        work_unit=unit_for_modality,
    )
    source_advisory_notices, source_advisory_lines = _work_calculate_source_advisory_output(calculation_result)
    deadline_payload, deadline_notices = work_unit_deadline_output(unit_for_modality)
    result = WorkCalculateResult.model_validate(
        {
            "saved": True,
            "saved_confirmation": saved_confirmation,
            **calculation_revision_payload(calculation_revision).model_dump(mode="python"),
            **modality_payload,
            **authorization_payload,
            "deadline": deadline_payload.model_dump(mode="python") if deadline_payload is not None else None,
        },
    )
    lines = [
        "operation\tmodelo.work.calculate",
        *calculation_revision_lines(calculation_revision),
        *modality_lines,
        *work_unit_plazo_lines(unit_for_modality),
        *authorization_lines,
        *source_advisory_lines,
        saved_confirmation,
    ]
    _emit_envelope(
        ctx,
        command="modelo.work.calculate",
        result=result,
        lines=lines,
        notices=[*authorization_notices, *source_advisory_notices, *deadline_notices],
    )


def _work_calculate_saved_confirmation(revision: CalculationRevision, work_unit: WorkUnit) -> str:
    return tr(
        "cli.app.modelo.work.calculate_saved",
        default=(
            "Saved as draft calculation revision %{revision_id} "
            "(state: %{state}). It is persisted and can be resumed later; "
            "list revisions with "
            "`aeat app modelo work revisions --modelo %{modelo} --year %{year} --period %{period}` "
            "and re-inspect this one with `aeat app modelo work revision %{revision_id}`."
        ),
        revision_id=revision.calculation_revision_id,
        state=revision.state.value,
        modelo=work_unit.modelo,
        year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )


def _work_calculate_modality_output(
    calculation_result: ModeloWorkCalculationServiceResult,
) -> tuple[dict[str, object], list[str]]:
    modality = calculation_result.modality
    if modality is None:
        return {}, []
    return (
        {
            "modality": modality.modality,
            "modality_reason": modality.reason,
        },
        [f"modality\t{modality.modality}"],
    )


def _work_calculate_authorization_output(
    calculation_result: ModeloWorkCalculationServiceResult,
    *,
    work_unit: WorkUnit,
) -> tuple[dict[str, object], list[Notice], list[str]]:
    """Project the unauthorized-backend advisory onto a notice + payload state + lines.

    ``authorization_state`` remains structured result data (the backend's
    authorization lifecycle state); the advisory prose moves onto the
    uniform notices channel so it is no longer a bespoke
    ``authorization_advisory`` payload field. The text lines are unchanged.
    """
    advisory = calculation_result.authorization_advisory
    if advisory is None:
        return {}, [], []
    advisory_text = tr(
        "cli.app.modelo.work.calculate_unauthorized_advisory",
        modelo=str(work_unit.modelo),
        default=(
            "ADVISORY: modelo %{modelo} calculation backend is UNAUTHORIZED - it has not "
            "yet been proven by an end-to-end test across at least two renta years "
            "(multi-year-renta authorization gate). The result was computed and saved, "
            "but treat it as provisional until the modelo is authorized."
        ),
    )
    return (
        {"authorization_state": advisory.state},
        [
            advisory_notice(
                "modelo.work.calculate.unauthorized_backend",
                advisory_text,
                context={"authorization_state": str(advisory.state)},
            ),
        ],
        [f"authorization_state\t{advisory.state}", advisory_text],
    )


def _work_calculate_source_advisory_output(
    calculation_result: ModeloWorkCalculationServiceResult,
) -> tuple[list[Notice], list[str]]:
    """Project NON-blocking source diagnostics into notices + human lines.

    Each diagnostic the source mesh raised while resolving the bucket ledger
    (notably the unconsumed-declarable-IVA advisory) becomes one
    warning-severity :class:`Notice` on the envelope ``notices`` channel and
    one human-facing ADVISORY line. The structured provenance (``reason`` /
    ``source_kind`` / ``resolver_id``) rides on the notice ``context`` so no
    machine-queryable field is lost relative to the former bespoke
    ``source_advisories`` payload list. The calculation succeeded; these
    advisories keep an unrouted declarable observation from being silently
    under-declared (no-silent-under-declaration). The diagnostic ``message``
    already carries the observation's category / rate / flow provenance.
    """
    diagnostics = calculation_result.source_diagnostics
    if not diagnostics:
        return [], []
    notices = [
        advisory_notice(
            "modelo.work.calculate.source_advisory",
            diagnostic.message,
            context={
                "reason": str(diagnostic.reason),
                "source_kind": diagnostic.source_kind,
                **({"resolver_id": diagnostic.resolver_id} if diagnostic.resolver_id else {}),
            },
        )
        for diagnostic in diagnostics
    ]
    lines = [
        tr(
            "cli.app.modelo.work.calculate_source_advisory",
            message=diagnostic.message,
            default="ADVISORY: %{message}",
        )
        for diagnostic in diagnostics
    ]
    return (notices, lines)


__all__ = ["register_work_calculate_commands"]
