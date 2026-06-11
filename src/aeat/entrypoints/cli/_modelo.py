"""User-facing modelo registry introspection commands.

These commands read the registry spine and render it for operators: the
:class:`ModeloDefinition` and its :class:`ModeloRevision` revisions for
structure and deadlines, and the :class:`CalculationRevision` produced when a
modelo is evaluated against a profile. Filed declarations are represented by
:class:`ModeloRecord` instances; lifecycle events are recorded to the profile
audit trail through :class:`BucketEventHistoryRepository`. The CLI surfaces
detailed :class:`CasillaObservation` data on command output.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Annotated

import click
import typer
from pydantic import BaseModel, ValidationError

from ...application.aggregation import (
    CounterpartObservation,
    ForeignAssetIngestObservation,
    PerModeloAggregationCommand,
    RetencionObservation,
    aggregate_per_modelo,
)
from ...application.modelo import (
    AmendmentEvidenceMissingError,
    AmendmentTargetStateError,
    CalculationRevision,
    CalculationRevisionAmendmentKind,
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloCalculationRevisionDefault,
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorAmbiguousError,
    ModeloCalculationRevisionSelectorNotFoundError,
    ModeloCalculationRevisionSelectorStateError,
    ModeloRecordNotFoundError,
    ModeloWorkAddressNotFoundError,
    ModeloWorkPeriodTokenError,
    ModeloWorkRevisionConflictError,
    ModeloWorkSelectorContradictionError,
    ModeloWorkUnitNotFoundError,
    ModeloWorkVisibleTargetAmbiguousError,
    WorkUnit,
    WorkUnitNotFoundError,
    amend_modelo_revision,
    declared_modelo_period_tokens,
    get_work_unit,
    guard_active_profile_foral_ccaa,
    modelo_work_address_from_operator_target,
    normalize_modelo_work_period,
    resolve_modelo_revision_for_operator_target,
    resolve_modelo_work_unit_for_operator_target,
)
from ...core import Period
from ...core.errors import AeatError
from ...core.external_constants import OutputLanguage
from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES, tr
from ...core.logging import get_logger
from ...domain.calculations.registry import RegistryValidationError
from ._common import activate_subcommand_output_language
from ._modelo_audit_cli import audit_app as audit_app
from ._modelo_audit_cli import register_audit_commands
from ._modelo_cli_support import (
    bad_parameter_from_error as _bad_parameter_from_error,
)
from ._modelo_cli_support import (
    bad_parameter_from_localized_context as _bad_parameter_from_localized_context,
)
from ._modelo_cli_support import (
    calculation_revision_not_found_bad_parameter as _calculation_revision_not_found_bad_parameter,
)
from ._modelo_cli_support import (
    parse_binding_override as _parse_binding_override,
)
from ._modelo_cli_support import (
    parse_casilla_override as _parse_casilla_override,
)
from ._modelo_cli_support import (
    parse_kv_spec as _parse_kv_spec,
)
from ._modelo_cli_support import (
    parse_revision_selector as _parse_revision_selector,
)
from ._modelo_cli_support import (
    resolve_default_actor as _resolve_default_actor,
)
from ._modelo_cli_support import (
    selector_bad_parameter as _selector_bad_parameter,
)
from ._modelo_cli_support import (
    validate_calculation_revision_id as _validate_calculation_revision_id,
)
from ._modelo_cli_support import (
    validate_casilla_key as _validate_casilla_key,
)
from ._modelo_cli_support import (
    validate_work_unit_id as _validate_work_unit_id,
)
from ._modelo_cli_support import (
    work_calculate_input_bundle_from_cli as _work_calculate_input_bundle_from_cli,
)
from ._modelo_discovery_cli import register_discovery_commands
from ._modelo_export_cli import register_export_commands
from ._modelo_iva_wallet_cli import register_iva_wallet_commands
from ._modelo_m036_cli import register_m036_commands
from ._modelo_maritime_cli import register_maritime_commands
from ._modelo_projection_cli import register_projection_commands
from ._modelo_readiness_cli import register_readiness_commands
from ._modelo_reconcile_cli import register_reconcile_commands
from ._modelo_records_cli import (
    filing_record_app as filing_record_app,
)
from ._modelo_records_cli import (
    register_record_commands,
)
from ._modelo_records_cli import (
    verification_report_app as verification_report_app,
)
from ._modelo_rendering import (
    filing_record_lines as _filing_record_lines,
)
from ._modelo_rendering import (
    filing_record_payload as _filing_record_payload,
)
from ._modelo_rendering import (
    verification_report_lines as _verification_report_lines,
)
from ._modelo_rendering import (
    verification_report_payload as _verification_report_payload,
)
from ._modelo_work import create_work_app
from ._modelo_work_calculate_cli import register_work_calculate_commands
from ._modelo_work_lifecycle_cli import register_work_lifecycle_commands
from ._modelo_work_revision_cli import register_work_revision_commands
from ._modelo_work_runs_cli import register_work_run_commands
from ._modelo_work_verification_cli import register_work_verification_commands

_log = get_logger(__name__)

_OUTPUT_LANGUAGE_CLI = click.Choice(SUPPORTED_OUTPUT_LANGUAGES)


app = typer.Typer(
    name="modelo",
    help=tr("cli.app.modelo.app_help"),
    no_args_is_help=True,
)


def _work_address_for_cli(
    *,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None = None,
) -> object:
    exact_id = _validate_work_unit_id(work_unit_id) if work_unit_id is not None else None
    try:
        return modelo_work_address_from_operator_target(
            work_unit_id=exact_id,
            modelo=modelo,
            year=year,
            period=period,
            registry_revision_id=revision,
            bucket_id=bucket_id,
        )
    except ModeloWorkPeriodTokenError as exc:
        raise _bad_parameter_from_localized_context(exc) from exc


def _resolve_work_unit_for_cli(
    *,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    bucket_id: str | None = None,
) -> WorkUnit:
    exact_id = _validate_work_unit_id(work_unit_id) if work_unit_id is not None else None
    try:
        return resolve_modelo_work_unit_for_operator_target(
            work_unit_id=exact_id,
            modelo=modelo,
            year=year,
            period=period,
            registry_revision_id=revision,
            bucket_id=bucket_id,
        )
    except (
        ModeloWorkUnitNotFoundError,
        ModeloWorkSelectorContradictionError,
        ModeloWorkVisibleTargetAmbiguousError,
        ModeloWorkRevisionConflictError,
        ModeloWorkAddressNotFoundError,
        ModeloWorkPeriodTokenError,
    ) as exc:
        raise _selector_bad_parameter(exc) from exc


def _resolve_revision_for_cli(
    *,
    calculation_revision_id: str | None,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    registry_revision: str | None,
    bucket_id: str | None = None,
    selector: str = ModeloCalculationRevisionSelector.CURRENT.value,
    default_for: ModeloCalculationRevisionDefault | None = None,
) -> CalculationRevision:
    parsed_selector = _parse_revision_selector(selector)
    validated_revision_id = (
        _validate_calculation_revision_id(calculation_revision_id) if calculation_revision_id is not None else None
    )
    exact_work_id = _validate_work_unit_id(work_unit_id) if work_unit_id is not None else None
    try:
        return resolve_modelo_revision_for_operator_target(
            calculation_revision_id=validated_revision_id,
            work_unit_id=exact_work_id,
            modelo=modelo,
            year=year,
            period=period,
            registry_revision_id=registry_revision,
            bucket_id=bucket_id,
            selector=parsed_selector,
            default_for=default_for,
        )
    except (
        ModeloWorkAddressNotFoundError,
        ModeloCalculationRevisionSelectorNotFoundError,
        ModeloCalculationRevisionSelectorStateError,
        ModeloCalculationRevisionSelectorAmbiguousError,
        ModeloWorkPeriodTokenError,
    ) as exc:
        raise _selector_bad_parameter(exc) from exc


def _require_active_profile() -> None:
    """Refuse cold-start work commands with the clean no-active-profile message.

    Work commands open the active profile's encrypted bucket database.
    Without an active profile that path raises a raw ``StorageError``
    (``aeat_database_url is empty``) or a low-level ``no active bucket
    session`` message — both leak internal plumbing. This guard fires
    first so every cold-start work command produces the same clean,
    translated ``profile create`` guidance that the ledger surface
    already gives.
    """
    from ...core import resolve_active_bucket_id
    from ...core.i18n import tr as _tr
    from ._errors import CliRefusedBoundaryError

    if resolve_active_bucket_id() is None:
        raise CliRefusedBoundaryError(_tr("cli.config.errors.no_active_profile"))


def _active_bucket_id() -> str:
    from ...core import require_active_bucket_id

    try:
        return require_active_bucket_id()
    except Exception as exc:
        raise typer.BadParameter(tr("cli.config.errors.no_active_profile")) from exc


def _guard_foral_profile_ccaa() -> None:
    """Render the application foral-profile refusal for work creation."""
    guard_active_profile_foral_ccaa()


register_readiness_commands(app)


def _declared_period_tokens(modelo: str | None) -> tuple[str, ...]:
    """Return the registry-declared period tokens for one modelo.

    Pulls ``period_selector.periods`` from every revision of the modelo
    so the CLI period-validation error can enumerate exactly the tokens
    AEAT accepts for that form (``0A`` for an annual modelo, ``1T``..``4T``
    for a quarterly one, etc.). Returns an empty tuple when the modelo is
    unknown or unspecified — the caller falls back to the generic shape
    hint.
    """
    if not modelo or not modelo.strip():
        return ()
    try:
        return declared_modelo_period_tokens(modelo)
    except AeatError:
        return ()
    except Exception:
        _log.debug(
            "_declared_period_tokens: unexpected non-AeatError suppressed for modelo=%r",
            modelo,
            exc_info=True,
        )
        return ()


def _resolve_year_period(year: int, period: str, *, modelo: str | None = None) -> Period:
    """Normalise CLI ``--year/--period`` into a typed :class:`~aeat.core.Period`.

    Operators pass user-facing tokens (``Q1``, ``annual``, ``01``); the
    backend expects one typed filing period. Registry-only callers should
    project the returned value with ``period.year`` and
    ``period.registry_token`` at the registry boundary.

    ``--year`` and ``--period`` are composed internally; a token that is
    itself a four-digit year (the common ``--period 2024`` confusion)
    would compose to ``2024-2024`` and fail with an opaque message. When
    ``modelo`` is supplied the error instead explains the composition
    and enumerates the registry-declared period tokens for that modelo.
    """
    try:
        return normalize_modelo_work_period(year, period, modelo=modelo)
    except ModeloWorkPeriodTokenError as exc:
        raise _bad_parameter_from_localized_context(exc) from exc


def _period_token_error(
    year: int,
    token: str,
    modelo: str | None,
    *,
    fallback: str | None = None,
) -> str:
    """Build an operator-facing period-token error.

    Explains that ``--year`` and ``--period`` are composed and lists the
    registry-declared period tokens for the modelo when known. Falls
    back to ``fallback`` (the raw registry message) only when no
    modelo-specific token set is available.
    """
    declared = _declared_period_tokens(modelo)
    if declared:
        return tr(
            "cli.app.modelo.work.period_token_invalid",
            default=(
                f"--period {token!r} is not a valid period token for modelo "
                f"{modelo}. --year and --period are composed separately: pass "
                f"--year {year} for the filing year and one of the declared "
                f"period tokens for --period. Valid tokens: {', '.join(declared)}."
            ),
            token=token,
            modelo=modelo or "",
            year=year,
            tokens=", ".join(declared),
        )
    if fallback is not None:
        return fallback
    return tr(
        "cli.app.modelo.work.period_token_unrecognised",
        default=(
            f"--period {token!r} is not a recognised period token. --year and "
            f"--period are composed separately: pass --year {year} for the "
            f"filing year and a period token (0A for annual, Qn for a quarter, "
            f"or MM for a month) for --period."
        ),
        token=token,
        year=year,
    )


def _bare_period_error(modelo: str, period: str, *, fallback: str = "") -> str:
    """Build an operator-facing error for an invalid bare ``--period`` token.

    Used by surfaces (``describe``, ``casillas``) that take a bare
    period rather than a composed ``--year/--period`` pair. When the
    modelo's declared period tokens are known the error enumerates them;
    otherwise it falls back to the raw registry shape hint.
    """
    declared = _declared_period_tokens(modelo)
    if not declared:
        return fallback
    return tr(
        "cli.app.modelo.describe.period_token_invalid",
        default=(
            f"--period {period!r} is not a valid period token for modelo {modelo}. Valid tokens: {', '.join(declared)}."
        ),
        period=period,
        modelo=modelo,
        tokens=", ".join(declared),
    )


register_discovery_commands(
    app,
    resolve_year_period=_resolve_year_period,
    bare_period_error=_bare_period_error,
    parse_binding_override=_parse_binding_override,
    bad_parameter_from_error=_bad_parameter_from_error,
)


def _parse_typed_cli_observations[ObservationT: BaseModel](
    values: list[str] | None,
    *,
    model: type[ObservationT],
    flag: str,
) -> tuple[ObservationT, ...]:
    """Parse a list of raw JSON strings into typed observation models.

    Each string must be a JSON object conforming to *model*'s schema.
    ``typer.BadParameter`` is raised on JSON syntax errors, non-object
    JSON, or pydantic validation failures so the CLI error boundary
    presents a clear operator-facing refusal instead of an opaque
    traceback.
    """
    parsed: list[ObservationT] = []
    for raw in values or ():
        try:
            top = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(tr("cli.app.modelo.aggregate.json_parse_error", flag=flag, pos=exc.pos)) from exc
        if not isinstance(top, dict):
            raise typer.BadParameter(tr("cli.app.modelo.aggregate.json_not_object", flag=flag))
        try:
            # model_validate_json uses pydantic's JSON-mode coercions (string →
            # Decimal, string → StrEnum) even when the model declares strict=True
            # at the Python-object boundary.
            parsed.append(model.model_validate_json(raw))
        except ValidationError as exc:
            details = "; ".join(f"{'.'.join(str(s) for s in e['loc'])}: {e['msg']}" for e in exc.errors())
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.aggregate.json_validation_error",
                    flag=flag,
                    details=details,
                ),
            ) from exc
    return tuple(parsed)


@app.command(
    "aggregate",
    help=tr(
        "cli.app.modelo.aggregate_help",
        default=(
            "Run the backend per-modelo aggregation service from explicit canonical observations "
            "(ledger_transaction, purchase_invoice_evidence, payable_invoice, collectible_invoice)."
        ),
    ),
)
def aggregate_modelo(
    ctx: typer.Context,
    modelo: Annotated[str, typer.Option("--modelo", help=tr("cli.app.modelo.aggregate.modelo_help"))],
    period: Annotated[str, typer.Option("--period", help=tr("cli.app.modelo.aggregate.period_help"))],
    retencion_observation: Annotated[
        list[str] | None,
        typer.Option(
            "--retencion-observation",
            help=tr("cli.app.modelo.aggregate.retencion_observation_help"),
        ),
    ] = None,
    counterpart_observation: Annotated[
        list[str] | None,
        typer.Option(
            "--counterpart-observation",
            help=tr("cli.app.modelo.aggregate.counterpart_observation_help"),
        ),
    ] = None,
    foreign_asset_observation: Annotated[
        list[str] | None,
        typer.Option(
            "--foreign-asset-observation",
            help=tr("cli.app.modelo.aggregate.foreign_asset_observation_help"),
        ),
    ] = None,
) -> None:
    """Delegate per-modelo aggregation execution to the backend service."""
    command = PerModeloAggregationCommand(
        modelo=modelo,
        period=period,
        retencion_observations=_parse_typed_cli_observations(
            retencion_observation,
            model=RetencionObservation,
            flag="--retencion-observation",
        ),
        counterpart_observations=_parse_typed_cli_observations(
            counterpart_observation,
            model=CounterpartObservation,
            flag="--counterpart-observation",
        ),
        foreign_asset_observations=_parse_typed_cli_observations(
            foreign_asset_observation,
            model=ForeignAssetIngestObservation,
            flag="--foreign-asset-observation",
        ),
    )
    result = aggregate_per_modelo(command)
    from ._common import _emit_envelope
    from ._modelo_payloads import ModeloAggregateResult

    source_kinds = ", ".join(source_kind.value for source_kind in result.source_kinds) or "-"
    aggregate_result = ModeloAggregateResult(
        modelo=result.modelo,
        period=result.period.registry_token,
        provider=result.provider.value,
        observation_count=result.log_fields.observation_count,
        source_kinds=[sk.value for sk in result.source_kinds],
        result_row_count=result.log_fields.result_row_count,
    )
    lines = [
        "operation\tmodelo.aggregate",
        f"modelo\t{result.modelo}",
        f"period\t{result.period.registry_token}",
        f"provider\t{result.provider.value}",
        f"observation_count\t{result.log_fields.observation_count}",
        f"source_kinds\t{source_kinds}",
        f"result_row_count\t{result.log_fields.result_row_count}",
    ]
    _emit_envelope(ctx, command="modelo.aggregate", result=aggregate_result, lines=lines)


work_app = create_work_app()
app.add_typer(work_app, name="work")


#: Registry-validation translated-message keys that signal an
#: unsatisfied calculation input the operator can supply with
#: ``--binding`` / ``--relation``. The first ``work calculate`` of a
#: modelo that consumes a binding fails with one of these; the guidance
#: helper turns the bare refusal into a self-correcting message.
_MISSING_INPUT_TRANSLATED_MESSAGES: frozenset[str] = frozenset(
    {
        "errors.calc.binding_value_missing",
        "errors.calc.bound_casilla_binding_value_missing",
        "errors.calc.enum_binding_value_missing",
        "errors.calc.relation_value_missing",
    },
)


def _missing_binding_guidance(error: RegistryValidationError, work_unit_id: str) -> str:
    """Return the missing-binding refusal enriched with operator guidance.

    The registry engine names the unsatisfied binding / relation but
    leaves the operator with no path forward. When the failure is a
    missing-input class, append the ``--binding KEY=VALUE`` syntax and a
    concrete ``bindings list --missing`` command scoped to the work
    unit's modelo / year / period so the next attempt can succeed.
    Non-input registry-validation errors fall through unchanged.
    """
    base = tr(error.translated_message, **(error.context or {})) if error.translated_message is not None else str(error)
    if error.translated_message not in _MISSING_INPUT_TRANSLATED_MESSAGES:
        return base

    discover_command = "aeat app modelo bindings list --missing"
    # Loading the work unit only refines the discovery command with the
    # concrete modelo / year / period. It is best-effort enrichment: any
    # failure (missing unit, no active session) degrades to the generic
    # bindings-list command rather than masking the original refusal.
    try:
        unit: WorkUnit | None = get_work_unit(work_unit_id)
    except Exception:
        _log.debug("missing-binding guidance work-unit lookup failed", exc_info=True)
        unit = None
    if unit is not None:
        discover_command = (
            f"aeat app modelo bindings list --modelo {unit.modelo} "
            f"--year {unit.filing_year} --period {unit.period} --missing"
        )
    return tr(
        "cli.app.modelo.work.missing_binding_guidance",
        default=(
            "{base} Supply the value with --binding KEY=VALUE on this "
            "command, or run `{discover}` to list every binding the "
            "calculation still needs."
        ),
        base=base,
        discover=discover_command,
    )


register_work_lifecycle_commands(
    work_app,
    activate_output_language=activate_subcommand_output_language,
    require_active_profile=_require_active_profile,
    guard_foral_profile_ccaa=_guard_foral_profile_ccaa,
    resolve_year_period=_resolve_year_period,
    resolve_work_unit_for_cli=_resolve_work_unit_for_cli,
    resolve_default_actor=_resolve_default_actor,
    bad_parameter_from_error=_bad_parameter_from_error,
    selector_bad_parameter=_selector_bad_parameter,
)


register_work_calculate_commands(
    work_app,
    activate_output_language=activate_subcommand_output_language,
    require_active_profile=_require_active_profile,
    resolve_work_unit_for_cli=_resolve_work_unit_for_cli,
    resolve_default_actor=_resolve_default_actor,
    calculate_input_bundle_from_cli=_work_calculate_input_bundle_from_cli,
    bad_parameter_from_error=_bad_parameter_from_error,
    missing_binding_guidance=_missing_binding_guidance,
)


@work_app.command(
    "compare-taxation",
    help=tr("cli.app.modelo.work.compare_taxation_help"),
)
def work_compare_taxation(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str | None,
        typer.Argument(help=tr("cli.app.modelo.work.work_unit_id_help")),
    ] = None,
    modelo: Annotated[
        str | None,
        typer.Option("--modelo", help=tr("cli.app.modelo.work.modelo_help")),
    ] = None,
    year: Annotated[
        int | None,
        typer.Option("--year", help=tr("cli.app.modelo.work.year_help")),
    ] = None,
    period: Annotated[
        str | None,
        typer.Option("--period", help=tr("cli.app.modelo.work.period_help")),
    ] = None,
    revision: Annotated[
        str | None,
        typer.Option("--revision", help=tr("cli.app.modelo.work.revision_help")),
    ] = None,
    bucket_id: Annotated[
        str | None,
        typer.Option("--bucket-id", help=tr("cli.app.modelo.work.bucket_id_help")),
    ] = None,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        help=tr(
            "cli.app.modelo.work.output_language_help",
            default="Override the output language (e.g. es, en, ca).",
        ),
    ),
) -> None:
    """Compare conjunta vs. individual IRPF cuota for an existing Modelo 100 work unit.

    Runs the registry formula engine twice — once with
    ``declaration_type=2`` (tributación conjunta) and once with
    ``declaration_type=1`` (tributación individual) — over the
    same casilla inputs and profile bindings derived from the stored
    work unit. Outputs the cuota resultante autoliquidación (0595)
    and cuota diferencial (0610) for each mode plus the delta and a
    recommendation.

    This is an ephemeral operation: no revision is persisted.
    """
    from ._common import _emit_envelope, activate_subcommand_output_language

    activate_subcommand_output_language(ctx, output_language)

    from ...application.modelo import (
        TaxationComparisonError,
        WorkUnitNotFoundError,
        compare_taxation_for_work_address,
    )

    try:
        address = _work_address_for_cli(
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            revision=revision,
            bucket_id=bucket_id,
        )
        comparison = compare_taxation_for_work_address(address)
    except (
        ModeloWorkAddressNotFoundError,
        ModeloWorkVisibleTargetAmbiguousError,
        ModeloWorkRevisionConflictError,
        ModeloWorkSelectorContradictionError,
        ModeloWorkUnitNotFoundError,
    ) as exc:
        raise _selector_bad_parameter(exc) from exc
    except WorkUnitNotFoundError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.compare_taxation_work_unit_not_found",
                work_unit_id=work_unit_id or "",
                default="Work unit {work_unit_id} not found; check 'aeat app modelo work list'.",
            ),
        ) from exc
    except TaxationComparisonError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.compare_taxation_error",
                detail=str(exc),
                default="Taxation comparison failed: {detail}",
            ),
        ) from exc

    from ._modelo_payloads import WorkCompareTaxationResult

    result = WorkCompareTaxationResult(
        filing_year=comparison.filing_year,
        modelo=comparison.modelo,
        revision=comparison.revision,
        conjunta_cuota_resultante=str(comparison.conjunta_cuota_resultante),
        individual_cuota_resultante=str(comparison.individual_cuota_resultante),
        conjunta_resultado=str(comparison.conjunta_resultado),
        individual_resultado=str(comparison.individual_resultado),
        delta_resultado=str(comparison.delta_resultado),
        recommendation=comparison.recommendation.value,
        recommendation_reason=comparison.recommendation_reason,
    )
    lines = [
        "operation\tmodelo.work.compare_taxation",
        f"filing_year\t{comparison.filing_year}",
        f"modelo\t{comparison.modelo}",
        f"revision\t{comparison.revision}",
        f"conjunta_cuota_resultante\t{comparison.conjunta_cuota_resultante}",
        f"individual_cuota_resultante\t{comparison.individual_cuota_resultante}",
        f"conjunta_resultado\t{comparison.conjunta_resultado}",
        f"individual_resultado\t{comparison.individual_resultado}",
        f"delta_resultado\t{comparison.delta_resultado}",
        f"recommendation\t{comparison.recommendation.value}",
        tr(
            "cli.app.modelo.work.compare_taxation_recommendation_line",
            recommendation=comparison.recommendation.value,
            reason=comparison.recommendation_reason,
            default="RECOMENDACIÓN: {recommendation} — {reason}",
        ),
    ]
    _emit_envelope(ctx, command="modelo.work.compare_taxation", result=result, lines=lines)


register_work_revision_commands(
    work_app,
    activate_output_language=activate_subcommand_output_language,
    require_active_profile=_require_active_profile,
    resolve_work_unit_for_cli=_resolve_work_unit_for_cli,
    resolve_revision_for_cli=_resolve_revision_for_cli,
    bad_parameter_from_error=_bad_parameter_from_error,
    selector_bad_parameter=_selector_bad_parameter,
)


@work_app.command(
    "history",
    help=tr(
        "cli.app.modelo.work.history_help",
        default="Show every bucket event scoped to one work unit's full lifecycle.",
    ),
)
def work_history(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str | None,
        typer.Argument(
            help=tr(
                "cli.app.modelo.work.history_work_unit_id_help",
                default="Work unit id whose lifecycle to render.",
            ),
        ),
    ] = None,
    modelo: Annotated[
        str | None,
        typer.Option("--modelo", help=tr("cli.app.modelo.work.modelo_help")),
    ] = None,
    year: Annotated[
        int | None,
        typer.Option("--year", help=tr("cli.app.modelo.work.year_help")),
    ] = None,
    period: Annotated[
        str | None,
        typer.Option("--period", help=tr("cli.app.modelo.work.period_help")),
    ] = None,
    revision: Annotated[
        str | None,
        typer.Option("--revision", help=tr("cli.app.modelo.work.revision_help")),
    ] = None,
    bucket_id: Annotated[
        str | None,
        typer.Option("--bucket-id", help=tr("cli.app.modelo.work.bucket_id_help")),
    ] = None,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Assemble the chronological event stream for one work unit.

    Read-only aggregate over the bucket-event history catalogue and
    the four catalogues (work unit, calculation revision, verification
    report, filing record). Emits no bucket event.
    """
    activate_subcommand_output_language(ctx, output_language)
    from ...application.modelo import assemble_work_unit_history

    _require_active_profile()
    unit = _resolve_work_unit_for_cli(
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )
    history = assemble_work_unit_history(unit.work_unit_id)
    from ._common import _emit_envelope
    from ._modelo_payloads import WorkHistoryResult, WorkUnitHistoryEventPayload

    result = WorkHistoryResult(
        bucket_id=history.bucket_id,
        work_unit_id=history.work_unit_id,
        event_count=len(history.events),
        events=[
            WorkUnitHistoryEventPayload(
                event_id=event.event_id,
                occurred_at=event.occurred_at.isoformat(),
                event_type=event.event_type.value,
                object_type=event.object_type.value,
                object_id=event.object_id,
                actor=event.actor,
                payload=event.payload,
            )
            for event in history.events
        ],
    )
    lines = [
        "operation\tmodelo.work.history",
        f"bucket_id\t{history.bucket_id}",
        f"work_unit_id\t{history.work_unit_id}",
        f"event_count\t{len(history.events)}",
        "occurred_at\tevent_type\tobject_type\tobject_id\tactor",
    ]
    lines.extend(
        "\t".join(
            (
                event.occurred_at.isoformat(),
                event.event_type.value,
                event.object_type.value,
                event.object_id,
                event.actor,
            ),
        )
        for event in history.events
    )
    _emit_envelope(ctx, command="modelo.work.history", result=result, lines=lines)


def _calculation_revision_not_found_bad_parameter_wide(
    calculation_revision_id: str, exc: BaseException,
) -> typer.BadParameter:
    """Widen the exc parameter to BaseException for the register_work_verification_commands contract."""
    assert isinstance(exc, CalculationRevisionNotFoundError)
    return _calculation_revision_not_found_bad_parameter(calculation_revision_id, exc)


register_work_verification_commands(
    work_app,
    activate_output_language=activate_subcommand_output_language,
    require_active_profile=_require_active_profile,
    resolve_revision_for_cli=_resolve_revision_for_cli,
    resolve_default_actor=_resolve_default_actor,
    bad_parameter_from_error=_bad_parameter_from_error,
    calculation_revision_not_found_bad_parameter=_calculation_revision_not_found_bad_parameter_wide,
)


register_work_run_commands(
    work_app,
    activate_output_language=activate_subcommand_output_language,
    bad_parameter_from_error=_bad_parameter_from_error,
)


def _parse_amendment_casilla(spec: str) -> tuple[str, Decimal]:
    def _to_decimal(value: str) -> Decimal:
        try:
            return Decimal(value.strip())
        except (InvalidOperation, ValueError) as exc:
            raise typer.BadParameter(tr("cli.app.modelo.work.set_not_decimal", value=value)) from exc

    return _parse_kv_spec(
        spec,
        flag="--set",
        key_label="CASILLA",
        value_label="DECIMAL",
        transform=_to_decimal,
        key_validator=_validate_casilla_key,
    )


def _required_amendment_inputs(
    *,
    from_filing_record_id: str | None,
    kind: str | None,
    reason: str | None,
    set_overrides: list[str] | None,
) -> tuple[str, str, str, tuple[str, ...]]:
    missing: list[str] = []
    if not from_filing_record_id or not from_filing_record_id.strip():
        missing.append("--from-filing-record")
    if not kind or not kind.strip():
        missing.append("--kind")
    if not reason or not reason.strip():
        missing.append("--reason")
    if not set_overrides:
        missing.append("--set")
    if missing:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.amend_missing_options",
                missing=", ".join(missing),
            ),
        )
    assert from_filing_record_id is not None
    assert kind is not None
    assert reason is not None
    return from_filing_record_id, kind, reason, tuple(set_overrides or ())


def _parse_amendment_kind(kind: str) -> CalculationRevisionAmendmentKind:
    try:
        return CalculationRevisionAmendmentKind(kind.strip())
    except ValueError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_amendment_kind",
                choices=", ".join(repr(k.value) for k in CalculationRevisionAmendmentKind),
                kind=kind,
            ),
        ) from exc


def _parse_amendment_overrides(set_overrides: tuple[str, ...]) -> dict[str, Decimal]:
    overrides: dict[str, Decimal] = {}
    for spec in set_overrides:
        key, value = _parse_amendment_casilla(spec)
        overrides[key] = value
    if not overrides:
        raise typer.BadParameter(tr("cli.app.modelo.work.amend_set_required"))
    return overrides


@work_app.command("amend", help=tr("cli.app.modelo.work.amend_help"))
def work_amend(
    ctx: typer.Context,
    from_filing_record_id: Annotated[
        str | None,
        typer.Option(
            "--from-filing-record",
            help=tr("cli.app.modelo.work.from_filing_record_help"),
        ),
    ] = None,
    kind: Annotated[
        str | None,
        typer.Option(
            "--kind",
            help=tr("cli.app.modelo.work.amendment_kind_help"),
        ),
    ] = None,
    reason: Annotated[
        str | None,
        typer.Option(
            "--reason",
            help=tr("cli.app.modelo.work.amendment_reason_help"),
        ),
    ] = None,
    actor: Annotated[
        str | None,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = None,
    set_overrides: Annotated[
        list[str] | None,
        typer.Option("--set", help=tr("cli.app.modelo.work.set_override_help")),
    ] = None,
) -> None:
    """Build a complementaria amendment over an externally-filed return.

    The four required inputs (``--from-filing-record``, ``--kind``,
    ``--reason``, and at least one ``--set``) are batch-validated so a
    run missing several flags reports every absent one in a single
    refusal instead of forcing the operator to rediscover them one
    invocation at a time.
    """
    from_filing_record_id, kind, reason, set_specs = _required_amendment_inputs(
        from_filing_record_id=from_filing_record_id,
        kind=kind,
        reason=reason,
        set_overrides=set_overrides,
    )
    _require_active_profile()
    amendment_kind = _parse_amendment_kind(kind)
    overrides = _parse_amendment_overrides(set_specs)

    try:
        record = amend_modelo_revision(
            from_filing_record_id=from_filing_record_id,
            overrides=overrides,
            amendment_kind=amendment_kind,
            reason=reason,
            actor=actor or _resolve_default_actor(),
        )
    except (
        ModeloRecordNotFoundError,
        AmendmentEvidenceMissingError,
        AmendmentTargetStateError,
        CalculationRevisionNotFoundError,
        CalculationRevisionStateError,
        WorkUnitNotFoundError,
    ) as exc:
        raise _bad_parameter_from_error(exc) from exc

    from ._common import _emit_envelope
    from ._modelo_payloads import WorkAmendResult

    result = WorkAmendResult.model_validate(
        {
            "amendment_kind": amendment_kind.value,
            "amends_filing_record_id": from_filing_record_id,
            **_filing_record_payload(record).model_dump(mode="python"),
        },
    )
    lines = [
        "operation\tmodelo.work.amend",
        f"amendment_kind\t{amendment_kind.value}",
        f"amends_filing_record_id\t{from_filing_record_id}",
        *_filing_record_lines(record),
    ]
    lines.append("filing_disambiguation\t(internal only — does not submit to AEAT)")
    _emit_envelope(ctx, command="modelo.work.amend", result=result, lines=lines)


register_record_commands(
    app,
    validate_work_unit_id=_validate_work_unit_id,
    parse_amendment_casilla=_parse_amendment_casilla,
    resolve_default_actor=_resolve_default_actor,
    bad_parameter_from_error=_bad_parameter_from_error,
)


# ─────────────────────────────────────────────────────────────────────────
# History verb
# ─────────────────────────────────────────────────────────────────────────


@app.command(
    "history",
    help=tr(
        "cli.app.modelo.history_help",
        default="Chronological modelo lifecycle audit (calculate/verify/file/amend/...) for one modelo.",
    ),
)
def modelo_history(
    ctx: typer.Context,
    modelo: Annotated[
        str,
        typer.Option(
            "--modelo",
            help=tr("cli.app.modelo.history.modelo_help", default="Modelo code (e.g. 100, 303)."),
        ),
    ],
    year: Annotated[
        int | None,
        typer.Option(
            "--year",
            help=tr("cli.app.modelo.history.year_help", default="Optional filing year filter."),
        ),
    ] = None,
    period: Annotated[
        str | None,
        typer.Option(
            "--period",
            help=tr(
                "cli.app.modelo.history.period_help",
                default=(
                    "Optional period filter using the modelo revision token: 0A annual, 1T-4T quarters, "
                    "01-12 months; for censo modelos (036) use alta, modificacion, or baja."
                ),
            ),
        ),
    ] = None,
) -> None:
    """Stream the bucket-event history for one modelo across all lifecycle stages."""
    from ...domain.buckets import BucketEvent, BucketEventHistoryRepository, BucketEventType

    repo = BucketEventHistoryRepository()
    catalogue = repo.load()
    modelo_event_types = {
        BucketEventType.MODELO_CALCULATION_CREATED,
        BucketEventType.MODELO_VERIFICATION_PASSED,
        BucketEventType.MODELO_VERIFICATION_REFUSED,
        BucketEventType.MODELO_FILED,
        BucketEventType.MODELO_FILED_SUPERSEDED,
        BucketEventType.MODELO_AMENDED,
        BucketEventType.MODELO_FILING_IMPORTED,
        BucketEventType.MODELO_WORK_UNIT_DISCARDED,
        BucketEventType.MODELO_AUDIT_VERIFIED,
        BucketEventType.MODELO_AUDIT_EXPORTED,
    }
    matches: list[BucketEvent] = []
    for event in catalogue.events.values():
        if event.event_type not in modelo_event_types:
            continue
        payload_map = dict(event.payload)
        if payload_map.get("modelo", "") != modelo:
            continue
        if year is not None and payload_map.get("year", "").strip() != str(year):
            continue
        if period is not None and payload_map.get("period", "") != period:
            continue
        matches.append(event)
    matches.sort(key=lambda e: e.occurred_at)
    from ._common import _emit_envelope
    from ._modelo_payloads import ModeloHistoryResult, ModeloLifecycleEventPayload

    history_result = ModeloHistoryResult(
        modelo=modelo,
        year=year,
        period=period,
        count=len(matches),
        events=[
            ModeloLifecycleEventPayload(
                event_id=e.event_id,
                event_type=e.event_type.value,
                occurred_at=e.occurred_at.isoformat(),
                actor=e.actor,
                object_type=e.object_type.value,
                object_id=e.object_id,
                payload=dict(e.payload),
            )
            for e in matches
        ],
    )
    lines = [f"modelo\t{modelo}", f"count\t{len(matches)}"]
    for e in matches:
        lines.append(f"{e.occurred_at.isoformat()}\t{e.event_type.value}\t{e.object_id}\t{e.actor}")
    _emit_envelope(ctx, command="modelo.history", result=history_result, lines=lines)


register_reconcile_commands(
    app,
    require_active_profile=_require_active_profile,
    resolve_work_unit_for_cli=_resolve_work_unit_for_cli,
    resolve_default_actor=_resolve_default_actor,
    active_bucket_id=_active_bucket_id,
)


register_audit_commands(app)


register_export_commands(
    app,
    bad_parameter_from_error=_bad_parameter_from_error,
    selector_bad_parameter=_selector_bad_parameter,
    resolve_default_actor=_resolve_default_actor,
)


register_projection_commands(
    app,
    require_active_profile=_require_active_profile,
    parse_casilla_override=_parse_casilla_override,
    parse_binding_override=_parse_binding_override,
    bad_parameter_from_error=_bad_parameter_from_error,
    bad_parameter_from_localized_context=_bad_parameter_from_localized_context,
)


register_iva_wallet_commands(app, active_bucket_id=_active_bucket_id)


register_maritime_commands(
    work_app,
    require_active_profile=_require_active_profile,
    activate_output_language=activate_subcommand_output_language,
    bad_parameter_from_error=_bad_parameter_from_error,
)


register_m036_commands(
    app,
    require_active_profile=_require_active_profile,
    active_bucket_id=_active_bucket_id,
)


__all__ = [
    "_verification_report_lines",
    "_verification_report_payload",
    "app",
    "audit_app",
    "filing_record_app",
    "verification_report_app",
]
