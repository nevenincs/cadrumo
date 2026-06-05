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
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import click
import typer
from pydantic import BaseModel, TypeAdapter, ValidationError

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
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorAmbiguousError,
    ModeloCalculationRevisionSelectorNotFoundError,
    ModeloCalculationRevisionSelectorStateError,
    ModeloRecordNotFoundError,
    ModeloWorkAddress,
    ModeloWorkAddressNotFoundError,
    ModeloWorkCalculationServiceResult,
    ModeloWorkRevisionConflictError,
    ModeloWorkSelectorContradictionError,
    ModeloWorkUnitNotFoundError,
    ModeloWorkVisibleTargetAmbiguousError,
    VerificationReportNotFoundError,
    WorkCalculateInputBundle,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    amend_modelo_revision,
    build_work_calculate_input_bundle,
    calculate_modelo_work_revision,
    declared_modelo_period_tokens,
    file_modelo_revision,
    get_filing_record,
    get_verification_report,
    get_work_unit,
    guard_active_profile_foral_ccaa,
    list_calculation_revisions,
    list_filing_records,
    list_verification_reports,
    modelo_202_modality_for_work_unit,
    resolve_exportable_modelo_calculation_revision_address,
    resolve_fileable_modelo_calculation_revision_address,
    resolve_modelo_calculation_revision_address,
    resolve_modelo_work_address_unit,
    resolve_verifiable_modelo_calculation_revision_address,
    verify_modelo_revision,
)
from ...core.errors import AeatError
from ...core.external_constants import OutputLanguage
from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES, tr
from ...core.logging import get_logger
from ...domain.calculations.registry import (
    BindingId,
    CasillaId,
    RegistryValidationError,
    parse_modelo_period,
)
from ...domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionAmendmentKind,
)
from ...domain.modelos._row_models import (
    Modelo184MemberRow,
    Modelo232VinculadaRow,
    Modelo347ContraparteRow,
    Modelo349OperadorRow,
    ModeloDetailRow,
    validate_m349_nif_format,
)
from ...domain.modelos._work_unit import WorkUnit
from ._common import _profile_to_taxpayer, activate_subcommand_output_language
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
    validate_work_unit_id as _validate_work_unit_id,
)
from ._modelo_discovery_cli import register_discovery_commands
from ._modelo_export_cli import register_export_commands
from ._modelo_iva_wallet_cli import register_iva_wallet_commands
from ._modelo_m036_cli import register_m036_commands
from ._modelo_maritime_cli import register_maritime_commands
from ._modelo_projection_cli import register_projection_commands
from ._modelo_readiness_cli import register_readiness_commands
from ._modelo_rendering import (
    calculation_revision_lines as _calculation_revision_lines,
)
from ._modelo_rendering import (
    calculation_revision_payload as _calculation_revision_payload,
)
from ._modelo_rendering import (
    filing_record_lines as _filing_record_lines,
)
from ._modelo_rendering import (
    filing_record_payload as _filing_record_payload,
)
from ._modelo_rendering import (
    short_id as _short_id,
)
from ._modelo_rendering import (
    verification_report_lines as _verification_report_lines,
)
from ._modelo_rendering import (
    verification_report_payload as _verification_report_payload,
)
from ._modelo_rendering import (
    work_unit_plazo_lines as _work_unit_plazo_lines,
)
from ._modelo_work import create_work_app
from ._modelo_work_lifecycle_cli import register_work_lifecycle_commands
from ._modelo_work_runs_cli import register_work_run_commands

_log = get_logger(__name__)

if TYPE_CHECKING:
    from ...application.modelo import ModeloReconciliationReport

_CASILLA_MAX_LEN = 64
_BINDING_MAX_LEN = 128
_BINDING_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(BindingId)
_CASILLA_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(CasillaId)

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
) -> ModeloWorkAddress:
    exact_id = _validate_work_unit_id(work_unit_id) if work_unit_id is not None else None
    if modelo is not None and year is not None and period is not None:
        year, period = _resolve_year_period(year, period, modelo=modelo)
    elif exact_id is None:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.natural_target_required",
                default=(
                    "Pass an exact work-unit id, or address the filing with "
                    "--modelo, --year, and --period."
                ),
            )
        )
    return ModeloWorkAddress(
        work_unit_id=exact_id,
        modelo=modelo,
        filing_year=year,
        period=period,
        registry_revision_id=revision,
        bucket_id=bucket_id,
    )


def _resolve_work_unit_for_cli(
    *,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    bucket_id: str | None = None,
) -> WorkUnit:
    try:
        return resolve_modelo_work_address_unit(
            _work_address_for_cli(
                work_unit_id=work_unit_id,
                modelo=modelo,
                year=year,
                period=period,
                revision=revision,
                bucket_id=bucket_id,
            )
        )
    except (
        ModeloWorkUnitNotFoundError,
        ModeloWorkSelectorContradictionError,
        ModeloWorkVisibleTargetAmbiguousError,
        ModeloWorkRevisionConflictError,
        ModeloWorkAddressNotFoundError,
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
    default_for: str | None = None,
) -> CalculationRevision:
    try:
        if (
            calculation_revision_id is not None
            and work_unit_id is None
            and modelo is None
            and year is None
            and period is None
            and registry_revision is None
            and bucket_id is None
        ):
            address = ModeloWorkAddress()
        else:
            address = _work_address_for_cli(
                work_unit_id=work_unit_id,
                modelo=modelo,
                year=year,
                period=period,
                revision=registry_revision,
                bucket_id=bucket_id,
            )
        parsed_selector = _parse_revision_selector(selector)
        validated_revision_id = (
            _validate_calculation_revision_id(calculation_revision_id)
            if calculation_revision_id is not None
            else None
        )
        if default_for == "verify":
            return resolve_verifiable_modelo_calculation_revision_address(
                address=address,
                calculation_revision_id=validated_revision_id,
                selector=parsed_selector,
            )
        if default_for == "file":
            return resolve_fileable_modelo_calculation_revision_address(
                address=address,
                calculation_revision_id=validated_revision_id,
                selector=parsed_selector,
            )
        if default_for == "export":
            return resolve_exportable_modelo_calculation_revision_address(
                address=address,
                calculation_revision_id=validated_revision_id,
                selector=parsed_selector,
            )
        return resolve_modelo_calculation_revision_address(
            address=address,
            calculation_revision_id=validated_revision_id,
            selector=parsed_selector,
        )
    except (
        ModeloWorkAddressNotFoundError,
        ModeloCalculationRevisionSelectorNotFoundError,
        ModeloCalculationRevisionSelectorStateError,
        ModeloCalculationRevisionSelectorAmbiguousError,
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


def _guard_foral_profile_ccaa() -> None:
    """Render the application foral-profile refusal for work creation."""
    guard_active_profile_foral_ccaa()


register_readiness_commands(app)


def _parse_kv_spec[T](
    spec: str,
    *,
    flag: str,
    key_label: str = "KEY",
    value_label: str = "VALUE",
    transform: Callable[[str], T],
    key_validator: Callable[[str, str], None] | None = None,
) -> tuple[str, T]:
    """Parse a ``KEY=VALUE`` CLI spec into ``(key, transform(value))``.

    Centralises the shape every override flag shares: split on the
    first ``=``, require a non-empty key, hand the right-hand side to
    a flag-specific transform. ``flag``/``key_label``/``value_label``
    feed the :class:`typer.BadParameter` messages so each call site
    keeps its own operator-facing wording.

    If ``key_validator`` is provided it receives ``(key, spec)`` and
    must raise :class:`typer.BadParameter` if the key is malformed.
    """
    if "=" not in spec:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.kv_format_error",
                flag=flag,
                key_label=key_label,
                value_label=value_label,
                spec=spec,
            )
        )
    key, _, value = spec.partition("=")
    key = key.strip()
    if not key:
        raise typer.BadParameter(tr("cli.app.modelo.work.kv_empty_key_error", flag=flag, spec=spec))
    if key_validator is not None:
        key_validator(key, spec)
    return key, transform(value)


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


def _resolve_year_period(year: int, period: str, *, modelo: str | None = None) -> tuple[int, str]:
    """Normalise CLI ``--year/--period`` into ``(filing_year, registry_period)``.

    Operators pass user-facing tokens (``Q1``, ``annual``, ``01``); the
    registry expects ``1T``/``0A``/``01``. Bridge that by reconstructing
    the canonical ``YYYY[Qn|-MM]`` string and delegating to the
    registry parser.

    ``--year`` and ``--period`` are composed internally; a token that is
    itself a four-digit year (the common ``--period 2024`` confusion)
    would compose to ``2024-2024`` and fail with an opaque message. When
    ``modelo`` is supplied the error instead explains the composition
    and enumerates the registry-declared period tokens for that modelo.
    """
    token = period.strip()
    if not token:
        raise typer.BadParameter(tr("cli.common.errors.period_empty"))
    lowered = token.lower()
    # When the token matches a registry-declared period for the modelo
    # verbatim (case-insensitively) it is already the registry period —
    # return it directly. This is the only path that resolves the
    # non-date censo / event tokens ("alta", "modificacion", "baja",
    # "AD-HOC") declared by censo modelos (036, 308, ...); for quarterly
    # / annual modelos it short-circuits to the same value the
    # composition branches below would produce.
    declared = _declared_period_tokens(modelo)
    declared_match = next((d for d in declared if d.lower() == lowered), None)
    if declared_match is not None:
        return year, declared_match
    if lowered in {"annual", "anual", "0a"}:
        composed = f"{year}"
    elif lowered in {"q1", "1t", "1"}:
        composed = f"{year}Q1"
    elif lowered in {"q2", "2t", "2"}:
        composed = f"{year}Q2"
    elif lowered in {"q3", "3t", "3"}:
        composed = f"{year}Q3"
    elif lowered in {"q4", "4t", "4"}:
        composed = f"{year}Q4"
    elif lowered.isdigit() and len(lowered) == 2:
        composed = f"{year}-{lowered}"
    elif lowered.isdigit() and len(lowered) == 4:
        # A bare four-digit token is itself a year — the operator
        # likely repeated the filing year into --period. Composing it
        # would yield "<year>-<token>"; refuse with a clear hint.
        raise typer.BadParameter(_period_token_error(year, token, modelo))
    else:
        composed = f"{year}{token}" if token.upper().startswith("Q") else f"{year}-{token}"
    try:
        return parse_modelo_period(composed)
    except RegistryValidationError as exc:
        raise typer.BadParameter(_period_token_error(year, token, modelo, fallback=str(exc))) from exc


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


def _bare_period_error(modelo: str, period: str, *, fallback: str) -> str:
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


def _validate_binding_key(key: str, spec: str) -> None:
    """Validate a ``--binding`` key against :data:`BindingId` constraints."""
    try:
        _BINDING_ID_ADAPTER.validate_python(key)
    except ValidationError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_binding_key",
                default=(
                    f"--binding key {key!r} is not a valid BindingId "
                    f"(max {_BINDING_MAX_LEN} chars, lowercase kebab/dotted ref); "
                    f"got {spec!r}"
                ),
            )
        ) from exc


def _parse_binding_override(spec: str) -> tuple[str, str]:
    """Parse a ``--binding KEY=VALUE`` spec into a ``(key, value)`` pair.

    The key is validated against :data:`BindingId` constraints at the
    CLI boundary; the value is passed through unchanged so the
    bindings-resolution layer can coerce it per source type.
    """
    return _parse_kv_spec(
        spec,
        flag="--binding",
        transform=lambda value: value,
        key_validator=_validate_binding_key,
    )


register_discovery_commands(
    app,
    resolve_year_period=_resolve_year_period,
    bare_period_error=_bare_period_error,
    parse_binding_override=_parse_binding_override,
    bad_parameter_from_error=_bad_parameter_from_error,
)


# ---------------------------------------------------------------------------
# --row TYPE FIELD=value FIELD=value parsing helpers
#
# Supports multi-row entry for informational modelos whose filing
# content is a list of records rather than scalar casilla values.
# Supported types: miembro (M184 atribución member), vinculada (M232
# operación vinculada).  Each ``--row`` flag takes a string of the
# form ``TYPE FIELD=value [FIELD=value ...]``.
# ---------------------------------------------------------------------------

_ROW_TYPES_SUPPORTED: frozenset[str] = frozenset({"miembro", "vinculada", "operador", "contraparte"})
_ROW_DECIMAL_FIELDS: frozenset[str] = frozenset(
    {"porcentaje", "importe", "importe_Q1", "importe_Q2", "importe_Q3", "importe_Q4"}
)


def _parse_row_spec(spec: str) -> ModeloDetailRow:
    """Parse a ``--row TYPE FIELD=value ...`` spec into a typed row model.

    The first whitespace-separated token is the row type (``miembro`` or
    ``vinculada``). Remaining tokens are ``KEY=VALUE`` pairs.  Raises
    :class:`typer.BadParameter` on any parse or validation error.
    """
    parts = spec.split()
    if not parts:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.row_empty_spec",
                default="--row spec cannot be empty; expected TYPE FIELD=value [...]",
            )
        )
    row_type = parts[0].lower()
    if row_type not in _ROW_TYPES_SUPPORTED:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.row_unknown_type",
                default=(f"--row type {row_type!r} is not recognised; supported types: {sorted(_ROW_TYPES_SUPPORTED)}"),
                row_type=row_type,
                supported=", ".join(sorted(_ROW_TYPES_SUPPORTED)),
            )
        )
    kv_raw: dict[str, str] = {}
    for token in parts[1:]:
        if "=" not in token:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.work.row_kv_format_error",
                    default=f"--row field {token!r} must be in KEY=VALUE format",
                    token=token,
                )
            )
        key, _, value = token.partition("=")
        if not key:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.work.row_empty_key",
                    default=f"--row field key cannot be empty in {token!r}",
                    token=token,
                )
            )
        kv_raw[key] = value
    try:
        kv_pairs: dict[str, str | Decimal] = {
            k: Decimal(v) if k in _ROW_DECIMAL_FIELDS else v for k, v in kv_raw.items()
        }
        # kv_pairs is dict[str, str|Decimal]; the splat matches each row dataclass's
        # fields after decimal coercion at the parse boundary. type: ignore[arg-type]
        # documents the splat-to-field-types narrowing; per-splat CAST-RATIONALE token
        # sits inline on each return below for the W26.P59 marker-count gate.
        if row_type == "miembro":
            return Modelo184MemberRow(row_type="miembro", **kv_pairs)  # type: ignore[arg-type]  # TYPE-IGNORE-RATIONALE-MODELO-ROW-SPLAT  # CAST-RATIONALE-WIRE-PAYLOAD-MODELO-ROW-SPLAT
        elif row_type == "vinculada":
            return Modelo232VinculadaRow(row_type="vinculada", **kv_pairs)  # type: ignore[arg-type]  # TYPE-IGNORE-RATIONALE-MODELO-ROW-SPLAT  # CAST-RATIONALE-WIRE-PAYLOAD-MODELO-ROW-SPLAT
        elif row_type == "operador":
            row_m349 = Modelo349OperadorRow(row_type="operador", **kv_pairs)  # type: ignore[arg-type]  # TYPE-IGNORE-RATIONALE-MODELO-ROW-SPLAT  # CAST-RATIONALE-WIRE-PAYLOAD-MODELO-ROW-SPLAT
            # NIF format check is advisory at parse time — invalid format raises BadParameter.
            nif = str(kv_pairs.get("nif_comunitario", ""))
            pais = str(kv_pairs.get("codigo_pais", ""))
            if nif and pais and not validate_m349_nif_format(nif, pais):
                raise typer.BadParameter(
                    tr(
                        "cli.app.modelo.work.row_m349_invalid_nif",
                        default=(
                            f"--row operador: nif_comunitario {nif!r} does not match "
                            f"the expected NIF-IVA format for country {pais!r} "
                            f"(Council Directive 2006/112/EC Annex XI)"
                        ),
                        nif=nif,
                        pais=pais,
                    )
                )
            return row_m349
        else:
            # Same splat-to-field-types narrowing rationale as the rows above.
            return Modelo347ContraparteRow(row_type="contraparte", **kv_pairs)  # type: ignore[arg-type]  # TYPE-IGNORE-RATIONALE-MODELO-ROW-SPLAT  # CAST-RATIONALE-WIRE-PAYLOAD-MODELO-ROW-SPLAT
    except typer.BadParameter:
        raise
    except (ValidationError, TypeError, ValueError, ArithmeticError) as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.row_validation_error",
                default=f"--row {row_type!r} failed validation: {exc}",
                row_type=row_type,
                error=str(exc),
            )
        ) from exc


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
                )
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
        period=result.period,
        provider=result.provider.value,
        observation_count=result.log_fields.observation_count,
        source_kinds=[sk.value for sk in result.source_kinds],
        result_row_count=result.log_fields.result_row_count,
    )
    lines = [
        "operation\tmodelo.aggregate",
        f"modelo\t{result.modelo}",
        f"period\t{result.period}",
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
    }
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


filing_record_app = typer.Typer(
    name="filing-record",
    help=tr("cli.app.modelo.filing_record.app_help"),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(filing_record_app, name="filing-record")


def _validate_casilla_key(key: str, spec: str) -> None:
    """Validate a ``--casilla`` key against :data:`CasillaId` constraints."""
    try:
        _CASILLA_ID_ADAPTER.validate_python(key)
    except ValidationError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_casilla_key",
                default=(
                    f"--casilla key {key!r} is not a valid CasillaId "
                    f"(max {_CASILLA_MAX_LEN} chars, alphanumeric/dotted ref); "
                    f"got {spec!r}"
                ),
            )
        ) from exc


# Casilla data_types that accept a Decimal override via --casilla.
# Non-numeric types (text, boolean, nif, date, etc.) must be supplied
# through --binding or profile sources, not as raw decimal overrides.
_NUMERIC_CASILLA_DATA_TYPES: frozenset[str] = frozenset({"decimal", "money", "integer", "ratio"})


def _guard_casilla_data_type(casilla_id: str, revision: object) -> None:
    """Raise BadParameter when the casilla is non-numeric.

    Supplying a decimal value for a text, boolean, or identifier casilla
    silently produces wrong results because the engine stores the Decimal
    but the casilla's formula chain treats its absence as zero.  Surface
    the misuse early with the label and the correct input channel.
    """
    casilla_def = next(
        (c for c in revision.casillas if str(c.id) == casilla_id),
        None,
    )
    if casilla_def is None:
        return  # unknown casilla will fail later in the engine
    if casilla_def.data_type not in _NUMERIC_CASILLA_DATA_TYPES:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.casilla_non_numeric_data_type",
                key=casilla_id,
                data_type=casilla_def.data_type,
                label=casilla_def.label,
            )
        )


def _parse_casilla_override(spec: str) -> tuple[str, str]:
    return _parse_kv_spec(
        spec,
        flag="--casilla",
        key_label="ID",
        transform=str.strip,
        key_validator=_validate_casilla_key,
    )


def _parse_meses_trabajo_hijo_spec(spec: str) -> tuple[str, int]:
    """Parse one ``HIJO_ID=MESES`` token from ``--meses-trabajo-con-hijo-menor-3``.

    Returns ``(hijo_id_str, meses_int)``.  Raises :exc:`typer.BadParameter` on
    malformed input or out-of-range meses (must be 0–12).
    """
    if "=" not in spec:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.meses_trabajo_hijo_bad_format",
                spec=spec,
                default="--meses-trabajo-con-hijo-menor-3 requires HIJO_ID=MESES format; got: {spec}",
            )
        )
    hijo_id, _, meses_raw = spec.partition("=")
    hijo_id = hijo_id.strip()
    meses_raw = meses_raw.strip()
    try:
        meses = int(meses_raw)
    except ValueError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.meses_trabajo_hijo_not_integer",
                spec=spec,
                default="--meses-trabajo-con-hijo-menor-3 MESES must be an integer 0–12; got: {spec}",
            )
        ) from exc
    if not (0 <= meses <= 12):
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.meses_trabajo_hijo_out_of_range",
                spec=spec,
                meses=meses,
                default="--meses-trabajo-con-hijo-menor-3 MESES must be 0–12; got {meses} in: {spec}",
            )
        )
    return hijo_id, meses


def _optional_decimal_option(raw: str | None, *, translation_key: str, default: str) -> Decimal | None:
    if raw is None:
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise typer.BadParameter(
            tr(
                translation_key,
                value=raw,
                default=default,
            )
        ) from exc


def _work_calculate_input_bundle_from_cli(
    *,
    work_unit_id: str,
    casilla: list[str] | None,
    binding: list[str] | None,
    relation: list[str] | None,
    row: list[str] | None,
    borrador_snapshot_id: str | None,
    prestacion_inss_exenta: str | None,
    meses_trabajo_con_hijo_menor_3: list[str] | None,
    rescate_plan_pensiones_capital: str | None,
    rescate_plan_pensiones_aportaciones_pre_2007: str | None,
    rescate_plan_pensiones_aportaciones_totales: str | None,
    sal_beneficio_neto: str | None,
    sal_reserva_dotada: str | None,
    sal_capital_social: str | None,
    autoconsumo_promotor_base: str | None,
) -> WorkCalculateInputBundle:
    casilla_pairs = dict(_parse_casilla_override(spec) for spec in (casilla or ()))
    binding_pairs = dict(_parse_binding_override(spec) for spec in (binding or ()))
    relation_pairs = dict(
        _parse_kv_spec(spec, flag="--relation", transform=lambda value: value) for spec in relation or ()
    )
    detail_rows: tuple[ModeloDetailRow, ...] = tuple(_parse_row_spec(spec) for spec in (row or ()))
    meses_pairs: tuple[tuple[str, int], ...] = tuple(
        _parse_meses_trabajo_hijo_spec(spec) for spec in (meses_trabajo_con_hijo_menor_3 or ())
    )
    try:
        return build_work_calculate_input_bundle(
            work_unit_id=work_unit_id,
            casilla_overrides=casilla_pairs,
            binding_overrides=binding_pairs,
            relation_overrides=relation_pairs,
            detail_rows=detail_rows,
            borrador_snapshot_id=borrador_snapshot_id,
            prestacion_inss_exenta=_optional_decimal_option(
                prestacion_inss_exenta,
                translation_key="cli.app.modelo.work.prestacion_inss_exenta_not_decimal",
                default="--prestacion-inss-exenta must be a decimal amount; received: {value}",
            ),
            meses_trabajo_con_hijo_menor_3=meses_pairs,
            rescate_plan_pensiones_capital=_optional_decimal_option(
                rescate_plan_pensiones_capital,
                translation_key="cli.app.modelo.work.rescate_plan_pensiones_not_decimal",
                default="--rescate-plan-pensiones-* values must be decimals.",
            ),
            rescate_plan_pensiones_aportaciones_pre_2007=_optional_decimal_option(
                rescate_plan_pensiones_aportaciones_pre_2007,
                translation_key="cli.app.modelo.work.rescate_plan_pensiones_not_decimal",
                default="--rescate-plan-pensiones-* values must be decimals.",
            ),
            rescate_plan_pensiones_aportaciones_totales=_optional_decimal_option(
                rescate_plan_pensiones_aportaciones_totales,
                translation_key="cli.app.modelo.work.rescate_plan_pensiones_not_decimal",
                default="--rescate-plan-pensiones-* values must be decimals.",
            ),
            sal_beneficio_neto=_optional_decimal_option(
                sal_beneficio_neto,
                translation_key="cli.app.modelo.work.sal_reserva_not_decimal",
                default="--sal-* values must be decimals.",
            ),
            sal_reserva_dotada=_optional_decimal_option(
                sal_reserva_dotada,
                translation_key="cli.app.modelo.work.sal_reserva_not_decimal",
                default="--sal-* values must be decimals.",
            ),
            sal_capital_social=_optional_decimal_option(
                sal_capital_social,
                translation_key="cli.app.modelo.work.sal_reserva_not_decimal",
                default="--sal-* values must be decimals.",
            ),
            autoconsumo_promotor_base=_optional_decimal_option(
                autoconsumo_promotor_base,
                translation_key="cli.app.modelo.work.autoconsumo_promotor_base_not_decimal",
                default="--autoconsumo-promotor-base must be a decimal amount; received: {value}",
            ),
        )
    except (LookupError, ValueError, WorkUnitNotFoundError) as exc:
        raise typer.BadParameter(str(exc)) from exc


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
        period=work_unit.period,
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
) -> tuple[dict[str, object], list[str]]:
    advisory = calculation_result.authorization_advisory
    if advisory is None:
        return {}, []
    advisory_text = tr(
        "cli.app.modelo.work.calculate_unauthorized_advisory",
        modelo=str(work_unit.modelo),
        default=(
            "ADVISORY: modelo %{modelo} calculation backend is UNAUTHORIZED — it has not "
            "yet been proven by an end-to-end test across at least two renta years "
            "(multi-year-renta authorization gate). The result was computed and saved, "
            "but treat it as provisional until the modelo is authorized."
        ),
    )
    return (
        {
            "authorization_advisory": advisory_text,
            "authorization_state": advisory.state,
        },
        [f"authorization_state\t{advisory.state}", advisory_text],
    )


@work_app.command("calculate", help=tr("cli.app.modelo.work.calculate_help"))
def work_calculate(
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
    casilla: Annotated[
        list[str] | None,
        typer.Option(
            "--casilla",
            help=tr("cli.app.modelo.work.casilla_help"),
        ),
    ] = None,
    binding: Annotated[
        list[str] | None,
        typer.Option(
            "--binding",
            help=tr("cli.app.modelo.work.override_help"),
        ),
    ] = None,
    borrador_snapshot_id: Annotated[
        str | None,
        typer.Option(
            "--borrador",
            help=tr(
                "cli.app.modelo.work.borrador_help",
                default=(
                    "Modelo 100 borrador snapshot id (full or unambiguous "
                    "prefix). Snapshot binding values flow into the calculation "
                    "for registry bindings marked aeat_prefilled; caller --binding "
                    "overrides always take precedence."
                ),
            ),
        ),
    ] = None,
    actor: Annotated[
        str | None,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = None,
    relation: Annotated[
        list[str] | None,
        typer.Option(
            "--relation",
            help=tr(
                "cli.app.modelo.work.relation_help",
                default=(
                    "Prior-period relation value as KEY=VALUE. "
                    "The KEY is a registry relation id; the VALUE is a "
                    "decimal. Repeat to supply multiple relations."
                ),
            ),
        ),
    ] = None,
    row: Annotated[
        list[str] | None,
        typer.Option(
            "--row",
            help=tr(
                "cli.app.modelo.work.row_help",
                default=(
                    "Typed detail row for multi-record informational modelos. "
                    "Format: TYPE FIELD=value [FIELD=value ...]. "
                    "TYPE is 'miembro' (M184 atribución member) or "
                    "'vinculada' (M232 operación vinculada). "
                    "Repeat to add multiple rows. "
                    "M184 example: --row 'miembro nif=12345678A porcentaje=40 importe=10000'. "
                    "M232 example: --row 'vinculada nif=A12345678 tipo_operacion=01 importe=50000'."
                ),
            ),
        ),
    ] = None,
    prestacion_inss_exenta: Annotated[
        str | None,
        typer.Option(
            "--prestacion-inss-exenta",
            help=tr(
                "cli.app.modelo.work.prestacion_inss_exenta_help",
                default=(
                    "Importe íntegro de prestaciones INSS maternidad/paternidad "
                    "exentas (Art. 7.h LIRPF). Se registra en casilla 0058 (rev. 2024) "
                    "o 0059 (rev. 2025) y se descuenta del total de ingresos computables. "
                    "Introduce el importe bruto recibido de la Seguridad Social por "
                    "baja de maternidad o paternidad. NO lo incluyas en --casilla 0003."
                ),
            ),
        ),
    ] = None,
    meses_trabajo_con_hijo_menor_3: Annotated[
        list[str] | None,
        typer.Option(
            "--meses-trabajo-con-hijo-menor-3",
            help=tr(
                "cli.app.modelo.work.meses_trabajo_con_hijo_menor_3_help",
                default=(
                    "Meses trabajados mientras el hijo menor de 3 años estaba en la unidad "
                    "familiar (Art. 81 LIRPF deducción maternidad). Formato: HIJO_ID=MESES. "
                    "Repetible por cada hijo. HIJO_ID es un identificador libre (p. ej. 0, 1, 'laia'). "
                    "Se calcula sum(min(MESES × 100, 1200)) y se inyecta en casilla 0611. "
                    "Ejemplo: --meses-trabajo-con-hijo-menor-3 0=12 --meses-trabajo-con-hijo-menor-3 1=6 "
                    "→ 0611 = 1800."
                ),
            ),
        ),
    ] = None,
    rescate_plan_pensiones_capital: Annotated[
        str | None,
        typer.Option(
            "--rescate-plan-pensiones-capital",
            help=tr(
                "cli.app.modelo.work.rescate_plan_pensiones_capital_help",
                default=(
                    "Importe bruto del rescate del plan de pensiones en forma de capital "
                    "(DT 12ª LIRPF). Úsalo junto con "
                    "--rescate-plan-pensiones-aportaciones-pre-2007 y "
                    "--rescate-plan-pensiones-aportaciones-totales para que el asistente "
                    "calcule automáticamente la reducción del 40% y la inyecte en casilla 0011."
                ),
            ),
        ),
    ] = None,
    rescate_plan_pensiones_aportaciones_pre_2007: Annotated[
        str | None,
        typer.Option(
            "--rescate-plan-pensiones-aportaciones-pre-2007",
            help=tr(
                "cli.app.modelo.work.rescate_plan_pensiones_aportaciones_pre_2007_help",
                default=(
                    "Aportaciones realizadas al plan de pensiones hasta el 31-dic-2006 "
                    "(base prorrateo DT 12ª LIRPF). Necesario junto con "
                    "--rescate-plan-pensiones-capital y "
                    "--rescate-plan-pensiones-aportaciones-totales."
                ),
            ),
        ),
    ] = None,
    rescate_plan_pensiones_aportaciones_totales: Annotated[
        str | None,
        typer.Option(
            "--rescate-plan-pensiones-aportaciones-totales",
            help=tr(
                "cli.app.modelo.work.rescate_plan_pensiones_aportaciones_totales_help",
                default=(
                    "Total de aportaciones al plan de pensiones (denominador del prorrateo "
                    "DT 12ª LIRPF). Necesario junto con "
                    "--rescate-plan-pensiones-capital y "
                    "--rescate-plan-pensiones-aportaciones-pre-2007."
                ),
            ),
        ),
    ] = None,
    sal_beneficio_neto: Annotated[
        str | None,
        typer.Option(
            "--sal-beneficio-neto",
            help=tr(
                "cli.app.modelo.work.sal_beneficio_neto_help",
                default=(
                    "Beneficio neto del ejercicio de la Sociedad Laboral (SAL/SLL) "
                    "(Ley 44/2015 Art. 14). Se aplica el 10% para calcular la dotación "
                    "obligatoria a la reserva especial, limitada por el umbral del 50% del "
                    "capital social. Úsalo junto con --sal-reserva-dotada y --sal-capital-social."
                ),
            ),
        ),
    ] = None,
    sal_reserva_dotada: Annotated[
        str | None,
        typer.Option(
            "--sal-reserva-dotada",
            help=tr(
                "cli.app.modelo.work.sal_reserva_dotada_help",
                default=(
                    "Reserva especial acumulada en ejercicios anteriores (Ley 44/2015 Art. 14). "
                    "Se usa para comprobar si ya se ha alcanzado el límite del 50% del capital social. "
                    "Necesario junto con --sal-beneficio-neto y --sal-capital-social."
                ),
            ),
        ),
    ] = None,
    sal_capital_social: Annotated[
        str | None,
        typer.Option(
            "--sal-capital-social",
            help=tr(
                "cli.app.modelo.work.sal_capital_social_help",
                default=(
                    "Capital social de la Sociedad Laboral (Ley 44/2015 Art. 14). "
                    "Denominador del test del 50%: la dotación se anula cuando la reserva "
                    "acumulada alcanza el 50% del capital social. "
                    "Necesario junto con --sal-beneficio-neto y --sal-reserva-dotada."
                ),
            ),
        ),
    ] = None,
    autoconsumo_promotor_base: Annotated[
        str | None,
        typer.Option(
            "--autoconsumo-promotor-base",
            help=tr(
                "cli.app.modelo.work.autoconsumo_promotor_base_help",
                default=(
                    "Base imponible del autoconsumo del promotor inmobiliario "
                    "(Art. 9.1.c + Art. 79.4 LISIVA): coste de construcción o "
                    "rehabilitación de inmuebles afectados al patrimonio de arrendamiento. "
                    "El asistente aplica automáticamente el 21% (Art. 90 LISIVA) para "
                    "calcular la cuota devengada. Sólo aplicable a Modelo 303."
                ),
            ),
        ),
    ] = None,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Persist a new draft calculation revision for the work unit."""
    activate_subcommand_output_language(ctx, output_language)
    _require_active_profile()
    unit = _resolve_work_unit_for_cli(
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )
    work_unit_id = unit.work_unit_id
    from ...application.modelo import (
        CalculationRegistryUnavailableError,
        Modelo100BorradorBindingError,
        ModeloIvaWalletReconciliationBlocked,
    )

    calculation_inputs = _work_calculate_input_bundle_from_cli(
        work_unit_id=work_unit_id,
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
            work_unit_id=work_unit_id,
            actor=actor or _resolve_default_actor(),
            inputs=calculation_inputs,
        )
    except RegistryValidationError as exc:
        # A formula that consumes an unsatisfied binding / enum-binding /
        # relation raises RegistryValidationError. The bare message names
        # the missing key but gives the operator no path forward; append
        # the --binding KEY=VALUE syntax and the bindings-list discovery
        # command so the first calculate failure is self-correcting.
        raise typer.BadParameter(_missing_binding_guidance(exc, work_unit_id)) from exc
    except (
        WorkUnitNotFoundError,
        WorkUnitMutationRefusedError,
        CalculationRegistryUnavailableError,
        Modelo100BorradorBindingError,
        ModeloIvaWalletReconciliationBlocked,
    ) as exc:
        raise _bad_parameter_from_error(exc) from exc

    # The casilla table alone gives the operator no signal that the
    # result was persisted. Each calculate writes a `borrador` revision
    # that survives the session; the confirmation line states that
    # explicitly and names the verbs to resume or re-inspect it.
    calculation_revision = calculation_result.revision
    unit_for_modality = calculation_result.work_unit
    saved_confirmation = _work_calculate_saved_confirmation(calculation_revision, unit_for_modality)
    modality_payload, modality_lines = _work_calculate_modality_output(calculation_result)
    authorization_payload, authorization_lines = _work_calculate_authorization_output(
        calculation_result,
        work_unit=unit_for_modality,
    )

    from ._common import _emit_envelope
    from ._modelo_payloads import WorkCalculateResult

    result = WorkCalculateResult.model_validate(
        {
            "saved": True,
            "saved_confirmation": saved_confirmation,
            **_calculation_revision_payload(calculation_revision).model_dump(mode="python"),
            **modality_payload,
            **authorization_payload,
        }
    )
    plazo_lines = _work_unit_plazo_lines(unit_for_modality)
    lines = [
        "operation\tmodelo.work.calculate",
        *_calculation_revision_lines(calculation_revision),
        *modality_lines,
        *plazo_lines,
        *authorization_lines,
        saved_confirmation,
    ]
    _emit_envelope(ctx, command="modelo.work.calculate", result=result, lines=lines)


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
            )
        ) from exc
    except TaxationComparisonError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.compare_taxation_error",
                detail=str(exc),
                default="Taxation comparison failed: {detail}",
            )
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


@work_app.command("revisions", help=tr("cli.app.modelo.work.revisions_help"))
def work_revisions(
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
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """List calculation revisions, optionally filtered to one work unit."""
    activate_subcommand_output_language(ctx, output_language)
    _require_active_profile()
    resolved_work_unit_id = work_unit_id
    if work_unit_id is not None or modelo is not None or year is not None or period is not None:
        unit = _resolve_work_unit_for_cli(
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            revision=revision,
            bucket_id=bucket_id,
        )
        resolved_work_unit_id = unit.work_unit_id
    revisions = list_calculation_revisions(work_unit_id=resolved_work_unit_id)
    from ._common import _emit_envelope
    from ._modelo_payloads import WorkRevisionsResult

    result = WorkRevisionsResult.model_validate(
        {
            "work_unit_id_filter": resolved_work_unit_id,
            "revision_count": len(revisions),
            "revisions": [_calculation_revision_payload(rev) for rev in revisions],
        }
    )
    lines = [
        "operation\tmodelo.work.revisions",
        f"work_unit_id_filter\t{resolved_work_unit_id or ''}",
        f"revision_count\t{len(revisions)}",
        "short_calculation_revision_id\tcalculation_revision_id\tshort_work_unit_id\twork_unit_id\tstate\tcreated_at",
    ]
    lines.extend(
        "\t".join(
            (
                _short_id(rev.calculation_revision_id) or "",
                rev.calculation_revision_id,
                _short_id(rev.work_unit_id) or "",
                rev.work_unit_id,
                rev.state.value,
                rev.created_at.isoformat(),
            )
        )
        for rev in revisions
    )
    _emit_envelope(ctx, command="modelo.work.revisions", result=result, lines=lines)


@work_app.command("revision", help=tr("cli.app.modelo.work.revision_show_help"))
def work_revision(
    ctx: typer.Context,
    calculation_revision_id: Annotated[
        str | None,
        typer.Argument(help=tr("cli.app.modelo.work.calculation_revision_id_help")),
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
    registry_revision: Annotated[
        str | None,
        typer.Option("--registry-revision", help=tr("cli.app.modelo.work.revision_help")),
    ] = None,
    work_unit_id: Annotated[
        str | None,
        typer.Option("--work-unit-id", help=tr("cli.app.modelo.work.work_unit_id_help")),
    ] = None,
    select: Annotated[
        str,
        typer.Option("--select", help=tr("cli.app.modelo.work.revision_selector_help", default="Revision selector.")),
    ] = ModeloCalculationRevisionSelector.CURRENT.value,
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
    """Show one stored calculation revision's persisted casilla values.

    Read-only: the persisted revision is rendered as-is, never
    recomputed. Use ``work revisions`` to discover a revision id.
    """
    activate_subcommand_output_language(ctx, output_language)
    _require_active_profile()
    try:
        revision = _resolve_revision_for_cli(
            calculation_revision_id=calculation_revision_id,
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            registry_revision=registry_revision,
            bucket_id=bucket_id,
            selector=select,
        )
    except CalculationRevisionNotFoundError as exc:
        if calculation_revision_id is not None:
            raise _bad_parameter_from_error(exc) from exc
        raise _selector_bad_parameter(exc) from exc
    modality_payload_r: dict[str, object] = {}
    modality_lines_r: list[str] = []
    unit_for_modality_r = get_work_unit(revision.work_unit_id)
    modality_summary_r = modelo_202_modality_for_work_unit(unit_for_modality_r)
    if modality_summary_r is not None:
        modality_payload_r = {
            "modality": modality_summary_r.modality,
            "modality_reason": modality_summary_r.reason,
        }
        modality_lines_r = [f"modality\t{modality_summary_r.modality}"]

    from ._common import _emit_envelope
    from ._modelo_payloads import WorkRevisionResult

    result = WorkRevisionResult.model_validate(
        {
            **_calculation_revision_payload(revision).model_dump(mode="python"),
            **modality_payload_r,
        }
    )
    lines = [
        "operation\tmodelo.work.revision",
        *_calculation_revision_lines(revision),
        *modality_lines_r,
    ]
    _emit_envelope(ctx, command="modelo.work.revision", result=result, lines=lines)


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


@work_app.command("verify", help=tr("cli.app.modelo.work.verify_help"))
def work_verify(
    ctx: typer.Context,
    calculation_revision_id: Annotated[
        str | None,
        typer.Argument(help=tr("cli.app.modelo.work.calculation_revision_id_help")),
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
    work_unit_id: Annotated[
        str | None,
        typer.Option("--work-unit-id", help=tr("cli.app.modelo.work.work_unit_id_help")),
    ] = None,
    select: Annotated[
        str,
        typer.Option("--select", help=tr("cli.app.modelo.work.revision_selector_help", default="Revision selector.")),
    ] = ModeloCalculationRevisionSelector.CURRENT.value,
    bucket_id: Annotated[
        str | None,
        typer.Option("--bucket-id", help=tr("cli.app.modelo.work.bucket_id_help")),
    ] = None,
    actor: Annotated[
        str | None,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = None,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Verify a draft calculation revision against the verified-complete contract.

    Produces a structured verification report. On success, the
    revision transitions to ``verificado_completo``. On failure, the
    revision is not mutated and the report explains the missing
    inputs or blocking findings.
    """
    activate_subcommand_output_language(ctx, output_language)
    _require_active_profile()
    # ModeloWorkflowGateError is intentionally NOT wrapped in
    # typer.BadParameter: it is a workflow-state refusal (e.g.
    # NO_PENDING_OBLIGATION), not a user-input error. Letting it
    # propagate to the command error boundary renders it through its
    # registered REFUSED code rather than a Click "Invalid value:"
    # header that misframes a workflow gate as a bad CLI argument.
    try:
        from ...application.workflow import workflow_state_repository

        selected_revision = _resolve_revision_for_cli(
            calculation_revision_id=calculation_revision_id,
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            registry_revision=revision,
            bucket_id=bucket_id,
            selector=select,
            default_for="verify",
        )
        workflow_profile = _profile_to_taxpayer(workflow_state_repository().load())
        report = verify_modelo_revision(
            selected_revision.calculation_revision_id,
            actor=actor or _resolve_default_actor(),
            workflow_profile=workflow_profile,
        )
    except CalculationRevisionNotFoundError as exc:
        if calculation_revision_id is not None:
            raise _calculation_revision_not_found_bad_parameter(calculation_revision_id, exc) from exc
        raise _bad_parameter_from_error(exc) from exc
    except (
        CalculationRevisionStateError,
        WorkUnitNotFoundError,
    ) as exc:
        raise _bad_parameter_from_error(exc) from exc

    from ._common import _emit_envelope
    from ._modelo_payloads import WorkVerifyResult

    result = WorkVerifyResult.model_validate(_verification_report_payload(report).model_dump(mode="python"))
    lines = ["operation\tmodelo.work.verify", *_verification_report_lines(report)]
    _emit_envelope(ctx, command="modelo.work.verify", result=result, lines=lines)

    if not report.granted_verificado_completo:
        raise typer.Exit(code=1)


@work_app.command("file", help=tr("cli.app.modelo.work.file_help"))
def work_file(
    ctx: typer.Context,
    calculation_revision_id: Annotated[
        str | None,
        typer.Argument(help=tr("cli.app.modelo.work.calculation_revision_id_help")),
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
    work_unit_id: Annotated[
        str | None,
        typer.Option("--work-unit-id", help=tr("cli.app.modelo.work.work_unit_id_help")),
    ] = None,
    select: Annotated[
        str,
        typer.Option("--select", help=tr("cli.app.modelo.work.revision_selector_help", default="Revision selector.")),
    ] = ModeloCalculationRevisionSelector.CURRENT.value,
    bucket_id: Annotated[
        str | None,
        typer.Option("--bucket-id", help=tr("cli.app.modelo.work.bucket_id_help")),
    ] = None,
    actor: Annotated[
        str | None,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = None,
    notes: Annotated[
        str | None,
        typer.Option("--notes", help=tr("cli.app.modelo.work.notes_help")),
    ] = None,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Mark a verified modelo revision as internally filed. Does NOT submit to AEAT."""
    activate_subcommand_output_language(ctx, output_language)
    _require_active_profile()
    # ModeloWorkflowGateError is a workflow-state refusal, not a
    # user-input error — it propagates to the command error boundary
    # so it renders through its registered REFUSED code rather than a
    # Click "Invalid value:" header.
    try:
        from ...application.workflow import workflow_state_repository

        selected_revision = _resolve_revision_for_cli(
            calculation_revision_id=calculation_revision_id,
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            registry_revision=revision,
            bucket_id=bucket_id,
            selector=select,
            default_for="file",
        )
        workflow_profile = _profile_to_taxpayer(workflow_state_repository().load())
        record = file_modelo_revision(
            selected_revision.calculation_revision_id,
            actor=actor or _resolve_default_actor(),
            workflow_profile=workflow_profile,
            notes=notes,
        )
    except CalculationRevisionNotFoundError as exc:
        if calculation_revision_id is not None:
            raise _calculation_revision_not_found_bad_parameter(calculation_revision_id, exc) from exc
        raise _bad_parameter_from_error(exc) from exc
    except (
        CalculationRevisionStateError,
        WorkUnitNotFoundError,
    ) as exc:
        raise _bad_parameter_from_error(exc) from exc

    from ._common import _emit_envelope
    from ._modelo_payloads import WorkFileResult

    result = WorkFileResult.model_validate(_filing_record_payload(record).model_dump(mode="python"))
    lines = ["operation\tmodelo.work.file", *_filing_record_lines(record)]
    lines.append("filing_disambiguation\t(internal only — does not submit to AEAT)")
    _emit_envelope(ctx, command="modelo.work.file", result=result, lines=lines)


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
            )
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
            )
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
        }
    )
    lines = [
        "operation\tmodelo.work.amend",
        f"amendment_kind\t{amendment_kind.value}",
        f"amends_filing_record_id\t{from_filing_record_id}",
        *_filing_record_lines(record),
    ]
    lines.append("filing_disambiguation\t(internal only — does not submit to AEAT)")
    _emit_envelope(ctx, command="modelo.work.amend", result=result, lines=lines)


@filing_record_app.command("list", help=tr("cli.app.modelo.filing_record.list_help"))
def filing_record_list(
    ctx: typer.Context,
    bucket_id: Annotated[
        str | None,
        typer.Option("--bucket-id", help=tr("cli.app.modelo.filing_record.bucket_id_help")),
    ] = None,
    include_superseded: Annotated[
        bool,
        typer.Option(
            "--include-superseded",
            help=tr("cli.app.modelo.filing_record.include_superseded_help"),
        ),
    ] = False,
) -> None:
    """List filing records. Superseded records are excluded unless asked."""
    records = list_filing_records(bucket_id=bucket_id, include_superseded=include_superseded)
    from ._common import _emit_envelope
    from ._modelo_payloads import ModeloRecordListResult

    result = ModeloRecordListResult(
        bucket_id_filter=bucket_id,
        include_superseded=include_superseded,
        record_count=len(records),
        records=[_filing_record_payload(record) for record in records],
    )
    lines = [
        "operation\tmodelo.filing_record.list",
        f"bucket_id_filter\t{bucket_id or ''}",
        f"include_superseded\t{include_superseded}",
        f"record_count\t{len(records)}",
        "filing_record_id\tbucket_id\tmodelo\tyear\tperiod\tstatus\tfiled_at\tfiled_by",
    ]
    lines.extend(
        "\t".join(
            (
                record.filing_record_id,
                record.bucket_id,
                str(record.modelo),
                str(record.filing_year),
                record.period,
                record.status.value,
                record.filed_at.isoformat(),
                record.filed_by,
            )
        )
        for record in records
    )
    _emit_envelope(ctx, command="modelo.filing_record.list", result=result, lines=lines)


verification_report_app = typer.Typer(
    name="verification-report",
    help=tr("cli.app.modelo.verification_report.app_help"),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(verification_report_app, name="verification-report")


@verification_report_app.command("list", help=tr("cli.app.modelo.verification_report.list_help"))
def verification_report_list(
    ctx: typer.Context,
    calculation_revision_id: Annotated[
        str | None,
        typer.Option(
            "--calculation-revision-id",
            help=tr("cli.app.modelo.work.calculation_revision_id_help"),
        ),
    ] = None,
) -> None:
    """List verification reports, optionally filtered to one revision."""
    reports = list_verification_reports(calculation_revision_id=calculation_revision_id)
    from ._common import _emit_envelope
    from ._modelo_payloads import VerificationReportListResult

    result = VerificationReportListResult(
        calculation_revision_id_filter=calculation_revision_id,
        report_count=len(reports),
        reports=[_verification_report_payload(r) for r in reports],
    )
    lines = [
        "operation\tmodelo.verification_report.list",
        f"calculation_revision_id_filter\t{calculation_revision_id or ''}",
        f"report_count\t{len(reports)}",
        "verification_report_id\tcalculation_revision_id\tcompleteness_status\tgranted\trun_at\tverified_by",
    ]
    lines.extend(
        "\t".join(
            (
                r.verification_report_id,
                r.calculation_revision_id,
                r.completeness_status.value,
                str(r.granted_verificado_completo).lower(),
                r.run_at.isoformat(),
                r.verified_by,
            )
        )
        for r in reports
    )
    _emit_envelope(ctx, command="modelo.verification_report.list", result=result, lines=lines)


@verification_report_app.command("view", help=tr("cli.app.modelo.verification_report.view_help"))
def verification_report_show(
    ctx: typer.Context,
    verification_report_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.verification_report.verification_report_id_help")),
    ],
) -> None:
    """View one verification report by id."""
    try:
        report = get_verification_report(verification_report_id)
    except VerificationReportNotFoundError as exc:
        raise _bad_parameter_from_error(exc) from exc

    from ._common import _emit_envelope
    from ._modelo_payloads import VerificationReportShowResult

    result = VerificationReportShowResult.model_validate(_verification_report_payload(report).model_dump(mode="python"))
    lines = ["operation\tmodelo.verification_report.show", *_verification_report_lines(report)]
    _emit_envelope(ctx, command="modelo.verification_report.view", result=result, lines=lines)


@filing_record_app.command("view", help=tr("cli.app.modelo.filing_record.view_help"))
def filing_record_show(
    ctx: typer.Context,
    filing_record_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.filing_record.filing_record_id_help")),
    ],
) -> None:
    """View one filing record by id."""
    try:
        record = get_filing_record(filing_record_id)
    except ModeloRecordNotFoundError as exc:
        raise _bad_parameter_from_error(exc) from exc

    from ._common import _emit_envelope
    from ._modelo_payloads import ModeloRecordShowResult

    result = ModeloRecordShowResult.model_validate(_filing_record_payload(record).model_dump(mode="python"))
    lines = ["operation\tmodelo.filing_record.show", *_filing_record_lines(record)]
    _emit_envelope(ctx, command="modelo.filing_record.view", result=result, lines=lines)


@filing_record_app.command("import", help=tr("cli.app.modelo.filing_record.import_help"))
def filing_record_import(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.work.work_unit_id_help")),
    ],
    evidence_kind: Annotated[
        str,
        typer.Option(
            "--evidence-kind",
            help=tr("cli.app.modelo.filing_record.evidence_kind_help"),
        ),
    ],
    evidence_reference_id: Annotated[
        str,
        typer.Option(
            "--evidence-id",
            help=tr("cli.app.modelo.filing_record.evidence_reference_id_help"),
        ),
    ],
    actor: Annotated[
        str,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = "aeat-import",
    set_overrides: Annotated[
        list[str] | None,
        typer.Option(
            "--set",
            help=tr("cli.app.modelo.filing_record.import_casilla_help"),
        ),
    ] = None,
) -> None:
    """Persist an externally-filed return as a baseline filing record."""
    work_unit_id = _validate_work_unit_id(work_unit_id)
    from ...application.modelo import (
        ExternalModeloImportError,
        import_external_filing_evidence,
    )
    from ...domain.modelos._filing_record import ExternalEvidenceKind

    try:
        kind = ExternalEvidenceKind(evidence_kind)
    except ValueError as exc:
        canonical = ", ".join(repr(k.value) for k in ExternalEvidenceKind)
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.filing_record.invalid_evidence_kind",
                canonical=canonical,
                kind=evidence_kind,
            )
        ) from exc

    casilla_values: dict[str, Decimal] = {}
    for spec in set_overrides or ():
        key, value = _parse_amendment_casilla(spec)
        casilla_values[key] = value
    if not casilla_values:
        raise typer.BadParameter(tr("cli.app.modelo.filing_record.import_set_required"))

    try:
        record = import_external_filing_evidence(
            work_unit_id=work_unit_id,
            casilla_values=casilla_values,
            evidence_kind=kind,
            evidence_reference_id=evidence_reference_id,
            actor=actor or _resolve_default_actor(),
        )
    except (
        WorkUnitNotFoundError,
        WorkUnitMutationRefusedError,
        ExternalModeloImportError,
    ) as exc:
        raise _bad_parameter_from_error(exc) from exc

    from ._common import _emit_envelope
    from ._modelo_payloads import FilingRecordImportResult

    result = FilingRecordImportResult.model_validate(
        {
            "evidence_kind": kind.value,
            "evidence_reference_id": evidence_reference_id,
            **_filing_record_payload(record).model_dump(mode="python"),
        }
    )
    lines = [
        "operation\tmodelo.filing_record.import",
        f"evidence_kind\t{kind.value}",
        f"evidence_reference_id\t{evidence_reference_id}",
        *_filing_record_lines(record),
    ]
    lines.append("filing_disambiguation\t(imported AEAT-attested baseline)")
    _emit_envelope(ctx, command="modelo.filing_record.import", result=result, lines=lines)


# ─────────────────────────────────────────────────────────────────────────
# Evidence bundle audit
# ─────────────────────────────────────────────────────────────────────────


audit_app = typer.Typer(
    name="audit",
    help=tr(
        "cli.app.modelo.audit.group_help",
        default="Evidence bundle audit verbs (show/check/export/replay).",
    ),
    no_args_is_help=True,
)
app.add_typer(audit_app, name="audit")


def _evidence_bundle_service():
    from ...application.evidence import EvidenceBundleService

    return EvidenceBundleService()


def _active_bucket_id() -> str:
    from ...core import require_active_bucket_id

    try:
        return require_active_bucket_id()
    except Exception as exc:
        raise typer.BadParameter(tr("cli.config.errors.no_active_profile")) from exc


@audit_app.command(
    "show",
    help=tr(
        "cli.app.modelo.audit.show_help",
        default="Render an evidence bundle's manifest and referenced records.",
    ),
)
def audit_show(
    ctx: typer.Context,
    bundle_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.audit.bundle_id_help", default="Evidence bundle id.")),
    ],
) -> None:
    """Render an evidence bundle's manifest and referenced record list."""
    bucket_id = _active_bucket_id()
    bundle = _evidence_bundle_service().show(bucket_id=bucket_id, bundle_id=bundle_id)
    from ._common import _emit_envelope
    from ._modelo_payloads import EvidenceRecordRefPayload, ModeloAuditShowResult

    result = ModeloAuditShowResult(
        bundle_id=bundle.bundle_id,
        manifest_version=bundle.manifest_version,
        bucket_id=bundle.bucket_id,
        work_unit_id=bundle.work_unit_id,
        calculation_revision_id=bundle.calculation_revision_id,
        filing_record_id=bundle.filing_record_id,
        verification_state=bundle.verification_state.value,
        completeness_ratio=bundle.completeness_ratio,
        records=[
            EvidenceRecordRefPayload(
                object_type=rec.object_type.value,
                object_id=rec.object_id,
                content_sha256=rec.content_sha256,
                payload_size_bytes=rec.payload_size_bytes,
            )
            for rec in bundle.records
        ],
        created_at=bundle.created_at.isoformat(),
        notes=bundle.notes,
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"bundle_id\t{bundle.bundle_id}",
        f"work_unit_id\t{bundle.work_unit_id}",
        f"manifest_version\t{bundle.manifest_version}",
        f"verification_state\t{bundle.verification_state.value}",
        f"records\t{len(bundle.records)}",
    ]
    _emit_envelope(ctx, command="modelo.audit.show", result=result, lines=lines)


@audit_app.command(
    "check",
    help=tr(
        "cli.app.modelo.audit.check_help",
        default="Re-verify the evidence bundle's integrity (report-only).",
    ),
)
def audit_check(
    ctx: typer.Context,
    bundle_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.audit.bundle_id_help", default="Evidence bundle id.")),
    ],
) -> None:
    """Re-verify the evidence bundle's integrity without mutating state."""
    bucket_id = _active_bucket_id()
    report = _evidence_bundle_service().check(bucket_id=bucket_id, bundle_id=bundle_id)
    from ._common import _emit_envelope
    from ._modelo_payloads import EvidenceBundleCheckFindingPayload, ModeloAuditCheckResult

    result = ModeloAuditCheckResult(
        bundle_id=report.bundle_id,
        verification_state=report.verification_state.value,
        completeness_ratio=report.completeness_ratio,
        findings=[
            EvidenceBundleCheckFindingPayload(
                check=f.check.value,
                passed=f.passed,
                detail=f.detail,
            )
            for f in report.findings
        ],
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"bundle_id\t{report.bundle_id}",
        f"verification_state\t{report.verification_state.value}",
        f"completeness_ratio\t{report.completeness_ratio}",
        f"findings\t{len(report.findings)}",
    ]
    _emit_envelope(ctx, command="modelo.audit.check", result=result, lines=lines)


@audit_app.command(
    "export",
    help=tr(
        "cli.app.modelo.audit.export_help",
        default="Write a ZIP archive of the bundle (manifest emitted last).",
    ),
)
def audit_export(
    ctx: typer.Context,
    bundle_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.audit.bundle_id_help", default="Evidence bundle id.")),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            help=tr("cli.app.modelo.audit.output_help", default="Output ZIP path."),
        ),
    ],
    force_incomplete: Annotated[
        bool,
        typer.Option(
            "--force-incomplete",
            help=tr(
                "cli.app.modelo.audit.force_incomplete_help",
                default="Allow export when verification is incomplete.",
            ),
        ),
    ] = False,
) -> None:
    """Write the evidence bundle as a ZIP archive to ``--output``."""
    bucket_id = _active_bucket_id()
    service = _evidence_bundle_service()
    output_path = service.export(
        bucket_id=bucket_id,
        bundle_id=bundle_id,
        output_path=output,
        force_incomplete=force_incomplete,
    )
    bundle = service.show(bucket_id=bucket_id, bundle_id=bundle_id)
    from ._common import _emit_envelope
    from ._modelo_payloads import ModeloAuditExportResult

    result = ModeloAuditExportResult(
        bucket_id=bucket_id,
        bundle_id=bundle.bundle_id,
        output=str(output_path),
        verification_state=bundle.verification_state.value,
        records=len(bundle.records),
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"bundle_id\t{bundle.bundle_id}",
        f"output\t{output_path}",
        f"verification_state\t{bundle.verification_state.value}",
    ]
    _emit_envelope(ctx, command="modelo.audit.export", result=result, lines=lines)


@audit_app.command(
    "replay",
    help=tr(
        "cli.app.modelo.audit.replay_help",
        default="Replay the bundle's evidence case (never contacts AEAT).",
    ),
)
def audit_replay(
    ctx: typer.Context,
    bundle_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.audit.bundle_id_help", default="Evidence bundle id.")),
    ],
) -> None:
    """Replay the evidence bundle's case assertions without contacting AEAT."""
    bucket_id = _active_bucket_id()
    report = _evidence_bundle_service().replay(bucket_id=bucket_id, bundle_id=bundle_id)
    from ._common import _emit_envelope
    from ._modelo_payloads import EvidenceBundleCheckFindingPayload, ModeloAuditReplayResult

    result = ModeloAuditReplayResult(
        bundle_id=report.bundle_id,
        verification_state=report.verification_state.value,
        completeness_ratio=report.completeness_ratio,
        findings=[
            EvidenceBundleCheckFindingPayload(
                check=f.check.value,
                passed=f.passed,
                detail=f.detail,
            )
            for f in report.findings
        ],
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"bundle_id\t{report.bundle_id}",
        f"verification_state\t{report.verification_state.value}",
        f"completeness_ratio\t{report.completeness_ratio}",
        f"findings\t{len(report.findings)}",
    ]
    _emit_envelope(ctx, command="modelo.audit.replay", result=result, lines=lines)


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
                default="Optional period filter (e.g. Q1, annual).",
            ),
        ),
    ] = None,
) -> None:
    """Stream the bucket-event history for one modelo across all lifecycle stages."""
    from ...domain.buckets import BucketEventHistoryRepository, BucketEventType

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
    matches: list = []
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


def _render_reconciliation_report(
    ctx: typer.Context,
    report: ModeloReconciliationReport,
    *,
    command: str,
) -> None:
    """Render a :class:`ModeloReconciliationReport` through the typed envelope."""
    from ._common import _emit_envelope
    from ._modelo_payloads import (
        ModeloReconcileResult,
        ModeloReconciliationDiffPayload,
    )

    result = ModeloReconcileResult(
        work_unit_id=report.work_unit_id,
        bucket_id=report.bucket_id,
        source_kind=report.source_kind.value,
        source_path=report.source_path,
        verdict=report.verdict.value,
        diffs=tuple(
            ModeloReconciliationDiffPayload(
                field_name=diff.field_name,
                work_unit_value=diff.work_unit_value,
                evidence_value=diff.evidence_value,
                kind=diff.kind,
            )
            for diff in report.diffs
        ),
        reconciled_at=report.reconciled_at.isoformat(),
        narrative=report.narrative,
    )
    lines = [
        f"work_unit_id\t{report.work_unit_id}",
        f"bucket\t{report.bucket_id}",
        f"source_kind\t{report.source_kind.value}",
        f"source_path\t{report.source_path}",
        f"verdict\t{report.verdict.value}",
        f"diffs\t{len(report.diffs)}",
    ]
    for diff in report.diffs:
        lines.append(
            f"diff\t{diff.field_name}\twork_unit={diff.work_unit_value}\tevidence={diff.evidence_value}",
        )
    _emit_envelope(ctx, command=command, result=result, lines=lines)


@app.command(
    "reconcile",
    help=tr(
        "cli.app.modelo.reconcile.help",
        default=(
            "Reconcile a modelo work unit against external evidence (justificante PDF). "
            "Local-only; never contacts AEAT."
        ),
    ),
)
def modelo_reconcile_verb(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str | None,
        typer.Argument(
            help=tr(
                "cli.app.modelo.reconcile.work_unit_id_help",
                default="Work unit id (SHA-256 or unambiguous prefix).",
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
    from_justificante: Annotated[
        Path | None,
        typer.Option(
            "--from-justificante",
            help=tr(
                "cli.app.modelo.reconcile.from_justificante_help",
                default="Path to the AEAT justificante PDF to reconcile against.",
            ),
        ),
    ] = None,
    from_declaration: Annotated[
        Path | None,
        typer.Option(
            "--from-declaration",
            help=tr(
                "cli.app.modelo.reconcile.from_declaration_help",
                default="Path to the filed declaration PDF to reconcile against.",
            ),
        ),
    ] = None,
    actor: Annotated[
        str | None,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = None,
) -> None:
    """Reconcile a modelo work unit against an external evidence source.

    Exactly one of ``--from-justificante`` or ``--from-declaration`` must be
    supplied. The CLI enforces the exclusivity here; the application
    service performs the reconciliation, emits the bucket event, and
    returns the verdict. The verb is local-only per the app-modelo-shape
    ADR amendment.
    """
    from ...application.modelo import (
        ModeloReconciliationCommand,
        ModeloReconciliationSourceKind,
        modelo_reconcile,
    )

    if from_justificante is None and from_declaration is None:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.reconcile.errors.missing_source",
                default="Supply --from-justificante PATH or --from-declaration PATH.",
            ),
        )
    if from_justificante is not None and from_declaration is not None:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.reconcile.errors.exclusive_source",
                default="--from-justificante and --from-declaration are mutually exclusive.",
            ),
        )

    source_kind = (
        ModeloReconciliationSourceKind.JUSTIFICANTE
        if from_justificante is not None
        else ModeloReconciliationSourceKind.DECLARATION
    )
    source_path = from_justificante if from_justificante is not None else from_declaration
    assert source_path is not None  # exhaustive by the exclusivity check above

    resolved_actor = actor.strip() if actor else _resolve_default_actor()
    _require_active_profile()
    unit = _resolve_work_unit_for_cli(
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )
    report = modelo_reconcile(
        ModeloReconciliationCommand(
            work_unit_id=unit.work_unit_id,
            source_kind=source_kind,
            source_path=source_path,
            actor=resolved_actor,
        ),
    )
    _render_reconciliation_report(ctx, report, command="modelo.reconcile")


@app.command(
    "reconcile-from-justificante",
    help=tr(
        "cli.app.modelo.reconcile_from_justificante.help",
        default=(
            "Reconcile a modelo work unit against a justificante PDF. Sugar for "
            'operators who think "reconcile from this justificante" rather than '
            '"reconcile, source = justificante". Shares the modelo_reconcile '
            "application service entry point with the flag-based form. Local-only; "
            "never contacts AEAT."
        ),
    ),
)
def modelo_reconcile_from_justificante_verb(
    ctx: typer.Context,
    justificante_path: Annotated[
        Path,
        typer.Argument(
            help=tr(
                "cli.app.modelo.reconcile_from_justificante.justificante_path_help",
                default="Path to the AEAT justificante PDF to reconcile against.",
            ),
        ),
    ],
    work_unit_id: Annotated[
        str | None,
        typer.Argument(
            help=tr(
                "cli.app.modelo.reconcile_from_justificante.work_unit_id_help",
                default="Work unit id (SHA-256 or unambiguous prefix).",
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
) -> None:
    """Reconcile a work unit against the supplied justificante PDF."""
    from ...application.modelo import (
        ModeloReconciliationCommand,
        ModeloReconciliationSourceKind,
        modelo_reconcile,
    )

    _require_active_profile()
    unit = _resolve_work_unit_for_cli(
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )
    report = modelo_reconcile(
        ModeloReconciliationCommand(
            work_unit_id=unit.work_unit_id,
            source_kind=ModeloReconciliationSourceKind.JUSTIFICANTE,
            source_path=justificante_path,
        ),
    )
    _render_reconciliation_report(ctx, report, command="modelo.reconcile_from_justificante")


register_export_commands(
    app,
    resolve_revision_for_cli=_resolve_revision_for_cli,
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


__all__ = ["app"]
