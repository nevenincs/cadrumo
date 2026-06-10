"""Shared modelo CLI support helpers.

These helpers stay at the Typer boundary: they validate operator token shape,
translate application refusals into ``BadParameter`` messages, and choose the
default audit actor. Filing selection and revision eligibility remain delegated
to application services by the caller.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Annotated

import typer
from pydantic import TypeAdapter, ValidationError

from ...application.modelo import (
    CalculationRevisionNotFoundError,
    Modelo184MemberRow,
    Modelo232VinculadaRow,
    Modelo347ContraparteRow,
    Modelo349OperadorRow,
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorAmbiguousError,
    ModeloDetailRow,
    ModeloWorkAddressNotFoundError,
    ModeloWorkRevisionConflictError,
    ModeloWorkUnitCandidate,
    ModeloWorkVisibleTargetAmbiguousError,
    WorkCalculateInputBundle,
    WorkUnitNotFoundError,
    build_work_calculate_input_bundle,
    get_work_unit,
    validate_m349_nif_format,
)
from ...core.errors import resolve_error_message
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ...core.logging import get_logger
from ...domain.calculations.registry import BindingId, CasillaId
from ._modelo_rendering import short_id

_log = get_logger(__name__)

# Shared ``--output-language`` / ``--language`` option for all modelo work
# commands. Centralised here so the five-line block does not repeat across
# every command function in the _modelo_work_*_cli modules.
OutputLanguageOpt = Annotated[
    OutputLanguage | None,
    typer.Option("--output-language", "--language", help=tr("cli.config.auth.output_language_help")),
]

_WORK_UNIT_ID_RE = r"^[0-9a-f]{64}$"
"""SHA-256 hex digest expected as the canonical work-unit identifier."""

_BINDING_MAX_LEN = 128
_CASILLA_MAX_LEN = 64
_BINDING_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(BindingId)
_CASILLA_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(CasillaId)
_ROW_TYPES_SUPPORTED: frozenset[str] = frozenset({"miembro", "vinculada", "operador", "contraparte"})
_ROW_DECIMAL_FIELDS: frozenset[str] = frozenset(
    {"porcentaje", "importe", "importe_Q1", "importe_Q2", "importe_Q3", "importe_Q4"}
)


def validate_work_unit_id(value: str) -> str:
    """Validate that *value* is a 64-character lowercase hex string."""
    stripped = value.strip()
    if not re.fullmatch(_WORK_UNIT_ID_RE, stripped):
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_work_unit_id",
                default=(f"work_unit_id must be a 64-character lowercase hex string (SHA-256 digest); got {value!r}"),
            )
        )
    return stripped


def validate_calculation_revision_id(value: str) -> str:
    """Validate that *value* is a 64-character lowercase hex string."""
    stripped = value.strip()
    if not re.fullmatch(_WORK_UNIT_ID_RE, stripped):
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_calculation_revision_id",
                default=(
                    "calculation_revision_id must be a 64-character lowercase "
                    f"hex string (SHA-256 digest); got {value!r}"
                ),
            )
        )
    return stripped


def parse_kv_spec[T](
    spec: str,
    *,
    flag: str,
    key_label: str = "KEY",
    value_label: str = "VALUE",
    transform: Callable[[str], T],
    key_validator: Callable[[str, str], None] | None = None,
) -> tuple[str, T]:
    """Parse a ``KEY=VALUE`` CLI token into ``(key, transform(value))``."""
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


def validate_binding_key(key: str, spec: str) -> None:
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


def parse_binding_override(spec: str) -> tuple[str, str]:
    """Parse a ``--binding KEY=VALUE`` spec into a ``(key, value)`` pair."""
    return parse_kv_spec(
        spec,
        flag="--binding",
        transform=lambda value: value,
        key_validator=validate_binding_key,
    )


def validate_casilla_key(key: str, spec: str) -> None:
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


def parse_casilla_override(spec: str) -> tuple[str, str]:
    """Parse a ``--casilla ID=VALUE`` spec into a validated key/value pair."""
    return parse_kv_spec(
        spec,
        flag="--casilla",
        key_label="ID",
        transform=str.strip,
        key_validator=validate_casilla_key,
    )


def parse_row_spec(spec: str) -> ModeloDetailRow:
    """Parse a ``--row TYPE FIELD=value ...`` spec into a typed row model."""
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
        if row_type == "miembro":
            return Modelo184MemberRow.model_validate({"row_type": "miembro", **kv_pairs})
        if row_type == "vinculada":
            return Modelo232VinculadaRow.model_validate({"row_type": "vinculada", **kv_pairs})
        if row_type == "operador":
            row_m349 = Modelo349OperadorRow.model_validate({"row_type": "operador", **kv_pairs})
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
        return Modelo347ContraparteRow.model_validate({"row_type": "contraparte", **kv_pairs})
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


def parse_meses_trabajo_hijo_spec(spec: str) -> tuple[str, int]:
    """Parse one ``HIJO_ID=MESES`` token from ``--meses-trabajo-con-hijo-menor-3``."""
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
                default="--meses-trabajo-con-hijo-menor-3 MESES must be an integer 0-12; got: {spec}",
            )
        ) from exc
    if not (0 <= meses <= 12):
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.meses_trabajo_hijo_out_of_range",
                spec=spec,
                meses=meses,
                default="--meses-trabajo-con-hijo-menor-3 MESES must be 0-12; got {meses} in: {spec}",
            )
        )
    return hijo_id, meses


def optional_decimal_option(raw: str | None, *, translation_key: str, default: str) -> Decimal | None:
    """Parse an optional decimal CLI option."""
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


def work_calculate_input_bundle_from_cli(
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
    """Build a :class:`WorkCalculateInputBundle` from raw Typer option values."""
    casilla_pairs = dict(parse_casilla_override(spec) for spec in (casilla or ()))
    binding_pairs = dict(parse_binding_override(spec) for spec in (binding or ()))
    relation_pairs = dict(
        parse_kv_spec(spec, flag="--relation", transform=lambda value: value) for spec in relation or ()
    )
    detail_rows: tuple[ModeloDetailRow, ...] = tuple(parse_row_spec(spec) for spec in (row or ()))
    meses_pairs: tuple[tuple[str, int], ...] = tuple(
        parse_meses_trabajo_hijo_spec(spec) for spec in (meses_trabajo_con_hijo_menor_3 or ())
    )
    try:
        return build_work_calculate_input_bundle(
            work_unit_id=work_unit_id,
            casilla_overrides=casilla_pairs,
            binding_overrides=binding_pairs,
            relation_overrides=relation_pairs,
            detail_rows=detail_rows,
            borrador_snapshot_id=borrador_snapshot_id,
            prestacion_inss_exenta=optional_decimal_option(
                prestacion_inss_exenta,
                translation_key="cli.app.modelo.work.prestacion_inss_exenta_not_decimal",
                default="--prestacion-inss-exenta must be a decimal amount; received: {value}",
            ),
            meses_trabajo_con_hijo_menor_3=meses_pairs,
            rescate_plan_pensiones_capital=optional_decimal_option(
                rescate_plan_pensiones_capital,
                translation_key="cli.app.modelo.work.rescate_plan_pensiones_not_decimal",
                default="--rescate-plan-pensiones-* values must be decimals.",
            ),
            rescate_plan_pensiones_aportaciones_pre_2007=optional_decimal_option(
                rescate_plan_pensiones_aportaciones_pre_2007,
                translation_key="cli.app.modelo.work.rescate_plan_pensiones_not_decimal",
                default="--rescate-plan-pensiones-* values must be decimals.",
            ),
            rescate_plan_pensiones_aportaciones_totales=optional_decimal_option(
                rescate_plan_pensiones_aportaciones_totales,
                translation_key="cli.app.modelo.work.rescate_plan_pensiones_not_decimal",
                default="--rescate-plan-pensiones-* values must be decimals.",
            ),
            sal_beneficio_neto=optional_decimal_option(
                sal_beneficio_neto,
                translation_key="cli.app.modelo.work.sal_reserva_not_decimal",
                default="--sal-* values must be decimals.",
            ),
            sal_reserva_dotada=optional_decimal_option(
                sal_reserva_dotada,
                translation_key="cli.app.modelo.work.sal_reserva_not_decimal",
                default="--sal-* values must be decimals.",
            ),
            sal_capital_social=optional_decimal_option(
                sal_capital_social,
                translation_key="cli.app.modelo.work.sal_reserva_not_decimal",
                default="--sal-* values must be decimals.",
            ),
            autoconsumo_promotor_base=optional_decimal_option(
                autoconsumo_promotor_base,
                translation_key="cli.app.modelo.work.autoconsumo_promotor_base_not_decimal",
                default="--autoconsumo-promotor-base must be a decimal amount; received: {value}",
            ),
        )
    except (LookupError, ValueError, WorkUnitNotFoundError) as exc:
        raise typer.BadParameter(str(exc)) from exc


def bad_parameter_from_error(exc: BaseException) -> typer.BadParameter:
    """Render registered domain errors before crossing the Typer boundary."""
    return typer.BadParameter(resolve_error_message(exc))


def bad_parameter_from_localized_context(exc: BaseException) -> typer.BadParameter:
    """Render local projection refusals that intentionally are not error-code registered."""
    key = getattr(exc, "translated_message", None)
    context = getattr(exc, "context", None) or {}
    if isinstance(key, str) and key:
        return typer.BadParameter(tr(key, **context))
    return typer.BadParameter(str(exc))


def calculation_revision_not_found_bad_parameter(
    calculation_revision_id: str, exc: CalculationRevisionNotFoundError
) -> typer.BadParameter:
    """Render a not-found calc-revision id, hinting when it is really a work-unit id."""
    stripped = calculation_revision_id.strip()
    try:
        unit = get_work_unit(stripped)
    except Exception:
        _log.debug(
            "calculation revision hint lookup failed; falling back to registered error rendering",
            exc_info=True,
        )
        return bad_parameter_from_error(exc)
    return typer.BadParameter(
        tr(
            "cli.app.modelo.work.id_is_work_unit_not_calc_revision_natural",
            default=(
                "This id is a work-unit-id, but verify/file need a calculation-revision-id. "
                "For the common path, run 'aeat app modelo work calculate --modelo %{modelo} "
                "--year %{year} --period %{period}' and then rerun verify/file for that "
                "same modelo/year/period. Exact ids remain available as an advanced escape hatch."
            ),
            modelo=unit.modelo,
            year=unit.filing_year,
            period=unit.period,
        )
    )


def work_candidate_lines(candidates: tuple[ModeloWorkUnitCandidate, ...]) -> str:
    """Return tabular candidate guidance for ambiguous visible filing targets."""
    rows = [
        "candidates:",
        "short_id\tmodelo\tyear\tperiod\trevision_id\tstate\tcurrent\tfiled\tname",
    ]
    for candidate in candidates:
        rows.append(
            "\t".join(
                (
                    candidate.short_work_unit_id,
                    str(candidate.modelo),
                    str(candidate.filing_year),
                    candidate.period,
                    candidate.revision_id,
                    candidate.state.value,
                    short_id(candidate.current_calculation_revision_id) or "",
                    short_id(candidate.filed_calculation_revision_id) or "",
                    candidate.work_unit_id,
                )
            )
        )
    return "\n".join(rows)


def selector_bad_parameter(exc: BaseException) -> typer.BadParameter:
    """Translate visible-target and revision selector refusals for Typer."""
    if isinstance(exc, ModeloWorkVisibleTargetAmbiguousError):
        return typer.BadParameter(
            tr(
                "cli.app.modelo.work.selector_ambiguous",
                default=(
                    "More than one active work unit matches this modelo/year/period. "
                    "Choose a registry revision or pass an explicit work-unit id.\n{candidates}"
                ),
                candidates=work_candidate_lines(exc.candidates),
            )
        )
    if isinstance(exc, ModeloWorkRevisionConflictError):
        return typer.BadParameter(
            tr(
                "cli.app.modelo.work.selector_revision_conflict",
                default=(
                    "An active work unit already exists for this modelo/year/period with "
                    "registry revision {existing_revision}; requested {requested_revision}. "
                    "Resume the existing work unit, discard it explicitly, or pass an exact id."
                ),
                existing_revision=exc.existing.revision_id,
                requested_revision=exc.requested_revision_id,
            )
        )
    if isinstance(exc, ModeloCalculationRevisionSelectorAmbiguousError):
        candidates = "\n".join(
            f"{candidate.short_calculation_revision_id}\t{candidate.state.value}\t{candidate.created_at}"
            for candidate in exc.candidates
        )
        return typer.BadParameter(
            tr(
                "cli.app.modelo.work.revision_selector_ambiguous",
                default=(
                    "More than one calculation revision matches this selector. Choose one explicitly.\n{candidates}"
                ),
                candidates=candidates,
            )
        )
    if isinstance(exc, ModeloWorkAddressNotFoundError):
        return typer.BadParameter(
            tr(
                "cli.app.modelo.work.selector_not_found",
                default="No active work unit matches this modelo/year/period. Run `aeat app modelo work create` first.",
            )
        )
    key = getattr(exc, "translated_message", None)
    context = getattr(exc, "context", None) or {}
    if isinstance(key, str) and key:
        return typer.BadParameter(tr(key, **context))
    return typer.BadParameter(str(exc))


def parse_revision_selector(value: str) -> ModeloCalculationRevisionSelector:
    """Parse a command-line revision selector token and return a :class:`ModeloCalculationRevisionSelector`."""
    try:
        return ModeloCalculationRevisionSelector(value)
    except ValueError as exc:
        choices = ", ".join(selector.value for selector in ModeloCalculationRevisionSelector)
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_revision_selector",
                default="Unknown revision selector {value!r}; choose one of: {choices}.",
                value=value,
                choices=choices,
            )
        ) from exc


def resolve_default_actor() -> str:
    """Return the active profile display_name, or a permanent fallback label."""
    try:
        from ...application.workflow import workflow_state_repository
        from ...core import resolve_active_bucket_id

        state = workflow_state_repository().load()
        record = state.active_profile_record()
        if record is not None and record.display_name:
            return record.display_name
        active = resolve_active_bucket_id()
        if active:
            return active
    except Exception:
        _log.debug("default actor lookup failed; falling back to operator label", exc_info=True)
    return "operator"


__all__ = [
    "OutputLanguageOpt",
    "bad_parameter_from_error",
    "bad_parameter_from_localized_context",
    "calculation_revision_not_found_bad_parameter",
    "optional_decimal_option",
    "parse_binding_override",
    "parse_casilla_override",
    "parse_kv_spec",
    "parse_meses_trabajo_hijo_spec",
    "parse_revision_selector",
    "parse_row_spec",
    "resolve_default_actor",
    "selector_bad_parameter",
    "validate_binding_key",
    "validate_calculation_revision_id",
    "validate_casilla_key",
    "validate_work_unit_id",
    "work_calculate_input_bundle_from_cli",
    "work_candidate_lines",
]
