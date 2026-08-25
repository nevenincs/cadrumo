"""Shared modelo CLI support helpers.

These helpers stay at the Typer boundary: they validate operator token shape,
translate application refusals into ``BadParameter`` messages, and choose the
default audit actor. Filing selection and revision eligibility remain delegated
to application services by the caller.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import TYPE_CHECKING, cast

import typer
from pydantic import TypeAdapter, ValidationError

from ...application.modelo._action_errors import WorkUnitNotFoundError
from ...application.modelo._calculate_input import (
    WorkCalculateInputBundle,
    build_work_calculate_input_bundle,
    is_detail_casilla_override_key,
)
from ...application.modelo._registry_discovery import declared_modelo_period_tokens
from ...application.modelo._selectors import (
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorAmbiguousError,
)
from ...application.modelo._work_create_policy import modelo_work_create_refusal_locale_key
from ...application.modelo._work_lifecycle import get_work_unit
from ...domain.modelos import (
    Modelo184MemberRow,
    Modelo232VinculadaRow,
    Modelo347ContraparteRow,
    Modelo349CountryPrefixContextError,
    Modelo349OperadorRow,
    Modelo349RectificacionRow,
    ModeloDetailRow,
    validate_m349_country_prefix_context,
    validate_m349_nif_format,
)
from ...application.modelo.work_addressing import (
    ModeloWorkAddressNotFoundError,
    ModeloWorkRevisionConflictError,
    ModeloWorkUnitCandidate,
    ModeloWorkVisibleTargetAmbiguousError,
)
from ...core import (
    HEX_PATTERN_64,
    CasillaId,
    M210GrossIncomeSourceMode,
    Modelo,
    RescateType,
    validated_casilla_id,
)
from ...core.decimal import try_parse_canonical_decimal
from ...core.errors import CadrumoError, resolve_error_message
from ...core.i18n import tr
from ...core.identity import CalculationRevisionId
from ...core.logging import get_logger
from ...domain.buckets import BUCKET_ACTOR_LABEL_MAX_LENGTH
from ...domain.calculations.registry import BindingId, RelationId
from ._common import active_bucket_id_or_refuse, active_profile_label
from ._modelo_rendering import short_id
from .errors import CliRefusedBoundaryError

if TYPE_CHECKING:
    from ...domain.modelos import FilingInstanceEvidence

_log = get_logger(__name__)

#: Registry-validation translated-message keys that signal an unsatisfied
#: calculation input the operator can supply with ``--binding`` / ``--relation``
#: (or, on the guided ``work wizard`` path, an interactive follow-up prompt).
#: Shared by ``_modelo.py`` (the ``work calculate`` missing-binding guidance)
#: and ``_modelo_work_wizard_cli.py`` (the wizard's retry-on-missing-input
#: loop), so the two surfaces agree on exactly which registry refusals are
#: "ask the operator for one more value" versus every other refusal.
MISSING_INPUT_TRANSLATED_MESSAGES: frozenset[str] = frozenset(
    {
        "errors.calc.binding_value_missing",
        "errors.calc.bound_casilla_binding_value_missing",
        "errors.calc.date_binding_value_missing",
        "errors.calc.enum_binding_value_missing",
        "errors.calc.relation_value_missing",
    },
)

_BINDING_MAX_LEN = 128
_CASILLA_MAX_LEN = 64
_BINDING_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(BindingId)
_RELATION_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(RelationId)
_ROW_TYPES_SUPPORTED: frozenset[str] = frozenset({"miembro", "vinculada", "operador", "rectificacion", "contraparte"})
_ROW_DECIMAL_FIELDS: frozenset[str] = frozenset(
    {
        "porcentaje",
        "importe",
        "importe_Q1",
        "importe_Q2",
        "importe_Q3",
        "importe_Q4",
        "base_rectificada",
        "base_anterior",
    },
)


def validate_work_unit_id(value: str) -> str:
    """Validate that *value* is a 64-character lowercase hex string."""
    stripped = value.strip()
    if not re.fullmatch(HEX_PATTERN_64, stripped):
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_work_unit_id",
                value=value,
            ),
        )
    return stripped


def validate_calculation_revision_id(value: str) -> CalculationRevisionId:
    """Validate that *value* is a 64-character lowercase hex string."""
    stripped = value.strip()
    if not re.fullmatch(HEX_PATTERN_64, stripped):
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_calculation_revision_id",
                value=value,
            ),
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
    strip_key: bool = True,
) -> tuple[str, T]:
    """Parse a ``KEY=VALUE`` CLI token into ``(key, transform(value))``."""
    if "=" not in spec:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.kv_format_error",
                default=(
                    "{flag} must be written as {key_label}={value_label}. "
                    "This is a key-value entry: put the field name on the left of one equals sign "
                    "and the value on the right. Received {spec}."
                ),
                flag=flag,
                key_label=key_label,
                value_label=value_label,
                spec=spec,
            ),
        )
    key, _, value = spec.partition("=")
    key = key.strip() if strip_key else key
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
            ),
        ) from exc


def parse_binding_override(spec: str) -> tuple[BindingId, str]:
    """Parse a ``--binding KEY=VALUE`` spec into a ``(key, value)`` pair."""
    key, value = parse_kv_spec(
        spec,
        flag="--binding",
        transform=lambda value: value,
        key_validator=validate_binding_key,
    )
    return _BINDING_ID_ADAPTER.validate_python(key), value


def unsupported_local_work_period_refusal(
    *,
    modelo: str | None,
    token: str | None,
) -> CliRefusedBoundaryError | None:
    """Return the central :class:`CliRefusedBoundaryError` for declared non-Period tokens.

    Some registry-visible modelos declare non-core event tokens such as census
    event names that are valid registry metadata but cannot become a local typed
    :class:`Period`. Commands that require a local filing period must
    not report those tokens as both valid and invalid. If the modelo is
    centrally marked unsupported for local work, reuse that refusal.
    """
    if modelo is None or token is None:
        return None
    modelo_code = modelo.strip()
    period_token = token.strip()
    if not modelo_code or not period_token:
        return None

    locale_key = modelo_work_create_refusal_locale_key(modelo_code)
    if locale_key is None:
        return None

    try:
        declared = declared_modelo_period_tokens(modelo_code)
    except CadrumoError:
        return None
    except Exception:
        _log.debug(
            "unsupported_local_work_period_refusal: unexpected period lookup failure for modelo=%r",
            modelo_code,
            exc_info=True,
        )
        return None

    if not any(period_token.casefold() == declared_token.casefold() for declared_token in declared):
        return None
    return CliRefusedBoundaryError(translated_message=locale_key, context={"modelo": modelo_code})


def validate_relation_key(key: str, spec: str) -> None:
    """Validate a ``--relation`` key against :data:`RelationId` constraints."""
    try:
        _RELATION_ID_ADAPTER.validate_python(key)
    except ValidationError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_relation_key",
                default=(
                    f"--relation key {key!r} is not a valid RelationId "
                    f"(max {_BINDING_MAX_LEN} chars, lowercase kebab/dotted ref); "
                    f"got {spec!r}"
                ),
            ),
        ) from exc


def parse_relation_override(spec: str) -> tuple[RelationId, str]:
    """Parse a ``--relation KEY=VALUE`` spec into a ``(key, value)`` pair."""
    key, value = parse_kv_spec(
        spec,
        flag="--relation",
        transform=lambda value: value,
        key_validator=validate_relation_key,
    )
    return _RELATION_ID_ADAPTER.validate_python(key), value


def validate_casilla_key(key: str, spec: str) -> None:
    """Validate a ``--casilla`` key against :data:`CasillaId` constraints."""
    try:
        validated_casilla_id(key, surface="--casilla key")
    except ValueError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_casilla_key",
                default=(
                    f"--casilla key {key!r} is not a valid CasillaId "
                    f"(max {_CASILLA_MAX_LEN} chars, alphanumeric/dotted ref); "
                    f"got {spec!r}"
                ),
            ),
        ) from exc


def parse_casilla_override(spec: str) -> tuple[CasillaId, str]:
    """Parse a ``--casilla ID=VALUE`` spec into a validated key/value pair."""
    key, value = parse_kv_spec(
        spec,
        flag="--casilla",
        key_label="ID",
        transform=str.strip,
        key_validator=validate_casilla_key,
        strip_key=False,
    )
    return validated_casilla_id(key, surface="--casilla key"), value


def parse_work_calculate_casilla_override(spec: str) -> tuple[str, str]:
    """Parse a work-calculate ``--casilla`` spec, preserving reserved detail aliases."""
    key, value = parse_kv_spec(
        spec,
        flag="--casilla",
        key_label="ID",
        transform=str.strip,
        key_validator=validate_work_calculate_casilla_key,
        strip_key=False,
    )
    if is_detail_casilla_override_key(key):
        return key, value
    return validated_casilla_id(key, surface="--casilla key"), value


def validate_work_calculate_casilla_key(key: str, spec: str) -> None:
    """Validate a work-calculate ``--casilla`` key or pass reserved detail aliases through."""
    if is_detail_casilla_override_key(key):
        return
    validate_casilla_key(key, spec)


def parse_row_spec(spec: str) -> ModeloDetailRow:
    """Parse a ``--row TYPE FIELD=value ...`` spec into a typed row model."""
    try:
        parts = shlex.split(spec)
    except ValueError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.row_validation_error",
                default=f"--row 'spec' failed validation: {exc}",
                row_type="spec",
                error=str(exc),
            ),
        ) from exc
    if not parts:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.row_empty_spec",
                default="--row spec cannot be empty; expected TYPE FIELD=value [...]",
            ),
        )
    row_type = parts[0].lower()
    if row_type not in _ROW_TYPES_SUPPORTED:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.row_unknown_type",
                default=(f"--row type {row_type!r} is not recognised; supported types: {sorted(_ROW_TYPES_SUPPORTED)}"),
                row_type=row_type,
                supported=", ".join(sorted(_ROW_TYPES_SUPPORTED)),
            ),
        )
    kv_raw: dict[str, str] = {}
    for token in parts[1:]:
        if "=" not in token:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.work.row_kv_format_error",
                    default=(
                        "--row field {token} must be written as KEY=VALUE. "
                        "This is a key-value entry: put the row field name on the left of one equals sign "
                        "and its value on the right."
                    ),
                    token=token,
                ),
            )
        key, _, value = token.partition("=")
        if not key:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.work.row_empty_key",
                    default=f"--row field key cannot be empty in {token!r}",
                    token=token,
                ),
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
                    ),
                )
            return row_m349
        if row_type == "rectificacion":
            row_m349_rect = Modelo349RectificacionRow.model_validate({"row_type": "rectificacion", **kv_pairs})
            nif = str(kv_pairs.get("nif_comunitario", ""))
            pais = str(kv_pairs.get("codigo_pais", ""))
            if nif and pais and not validate_m349_nif_format(nif, pais):
                raise typer.BadParameter(
                    tr(
                        "cli.app.modelo.work.row_m349_invalid_nif",
                        default=(
                            f"--row rectificacion: nif_comunitario {nif!r} does not match "
                            f"the expected NIF-IVA format for country {pais!r} "
                            f"(Council Directive 2006/112/EC Annex XI)"
                        ),
                        nif=nif,
                        pais=pais,
                    ),
                )
            return row_m349_rect
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
            ),
        ) from exc


def optional_decimal_option(raw: str | None, *, translation_key: str, default: str) -> Decimal | None:
    """Parse an optional hand-typed euro amount carrying a per-field refusal message.

    The single home for the "optional operator-typed amount whose refusal names
    its own field" shape. Every caller supplies its own ``translation_key`` /
    ``default`` pair, which is the only axis they differ on; the accepted grammar
    is shared and enforced here once.

    Conformance is the canonical euro-amount grammar
    (:func:`~cadrumo.core.decimal.try_parse_canonical_decimal` with a
    two-fractional-digit cap): a dot decimal separator, at most euro-cent
    precision, no thousands grouping, no comma decimal, no scientific notation,
    no leading ``+``, and no ``NaN``/``Infinity``. The cap is what makes the
    Spanish thousands shape ``1.000`` refuse rather than silently becoming
    ``Decimal("1.0")`` — a one-euro figure where the operator meant one
    thousand. A leading ``-`` still conforms, so a field whose domain forbids a
    negative amount keeps reporting that through its own validator rather than
    changing which surface refuses.
    """
    if raw is None:
        return None
    parsed = try_parse_canonical_decimal(raw, max_fraction_digits=2)
    if parsed is None:
        raise typer.BadParameter(
            tr(
                translation_key,
                value=raw,
                default=default,
            ),
        )
    return parsed


def work_calculate_input_bundle_from_cli(
    *,
    work_unit_id: str,
    casilla: list[str] | None,
    binding: list[str] | None,
    relation: list[str] | None,
    row: list[str] | None,
    borrador_snapshot_id: str | None,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode = M210GrossIncomeSourceMode.MANUAL,
    prestacion_inss_exenta: str | None,
    rescate_plan_pensiones_capital: str | None,
    rescate_plan_pensiones_aportaciones_pre_2007: str | None,
    rescate_plan_pensiones_aportaciones_totales: str | None,
    rescate_type: RescateType | None = None,
    contingencia_year: int | None = None,
    rescate_year: int | None = None,
    sal_beneficio_neto: str | None,
    sal_reserva_dotada: str | None,
    sal_capital_social: str | None,
    autoconsumo_promotor_base: str | None,
    filing_instance_evidence: FilingInstanceEvidence | None = None,
) -> WorkCalculateInputBundle:
    """Build a :class:`WorkCalculateInputBundle` from raw Typer option values."""
    casilla_pairs = dict(parse_work_calculate_casilla_override(spec) for spec in (casilla or ()))
    binding_pairs = dict(parse_binding_override(spec) for spec in (binding or ()))
    relation_pairs = dict(parse_relation_override(spec) for spec in relation or ())
    detail_rows: tuple[ModeloDetailRow, ...] = tuple(parse_row_spec(spec) for spec in (row or ()))
    try:
        _validate_m349_detail_rows_for_work_unit(work_unit_id, detail_rows)
        return build_work_calculate_input_bundle(
            work_unit_id=work_unit_id,
            casilla_overrides=casilla_pairs,
            binding_overrides=binding_pairs,
            relation_overrides=relation_pairs,
            detail_rows=detail_rows,
            borrador_snapshot_id=borrador_snapshot_id,
            m210_gross_income_source_mode=m210_gross_income_source_mode,
            prestacion_inss_exenta=optional_decimal_option(
                prestacion_inss_exenta,
                translation_key="cli.app.modelo.work.prestacion_inss_exenta_not_decimal",
                default=(
                    "--prestacion-inss-exenta must be a decimal amount; received: {value}. "
                    "Use a dot decimal separator with no thousands grouping, e.g. 1234.56."
                ),
            ),
            rescate_plan_pensiones_capital=optional_decimal_option(
                rescate_plan_pensiones_capital,
                translation_key="cli.app.modelo.work.rescate_plan_pensiones_not_decimal",
                default=(
                    "--rescate-plan-pensiones-* values must be decimal amounts; received: {value}. "
                    "Use a dot decimal separator with no thousands grouping, e.g. 1234.56."
                ),
            ),
            rescate_plan_pensiones_aportaciones_pre_2007=optional_decimal_option(
                rescate_plan_pensiones_aportaciones_pre_2007,
                translation_key="cli.app.modelo.work.rescate_plan_pensiones_not_decimal",
                default=(
                    "--rescate-plan-pensiones-* values must be decimal amounts; received: {value}. "
                    "Use a dot decimal separator with no thousands grouping, e.g. 1234.56."
                ),
            ),
            rescate_plan_pensiones_aportaciones_totales=optional_decimal_option(
                rescate_plan_pensiones_aportaciones_totales,
                translation_key="cli.app.modelo.work.rescate_plan_pensiones_not_decimal",
                default=(
                    "--rescate-plan-pensiones-* values must be decimal amounts; received: {value}. "
                    "Use a dot decimal separator with no thousands grouping, e.g. 1234.56."
                ),
            ),
            rescate_plan_pensiones_tipo=rescate_type,
            rescate_plan_pensiones_contingencia_year=contingencia_year,
            rescate_plan_pensiones_rescate_year=rescate_year,
            sal_beneficio_neto=optional_decimal_option(
                sal_beneficio_neto,
                translation_key="cli.app.modelo.work.sal_reserva_not_decimal",
                default=(
                    "--sal-* values must be decimal amounts; received: {value}. "
                    "Use a dot decimal separator with no thousands grouping, e.g. 1234.56."
                ),
            ),
            sal_reserva_dotada=optional_decimal_option(
                sal_reserva_dotada,
                translation_key="cli.app.modelo.work.sal_reserva_not_decimal",
                default=(
                    "--sal-* values must be decimal amounts; received: {value}. "
                    "Use a dot decimal separator with no thousands grouping, e.g. 1234.56."
                ),
            ),
            sal_capital_social=optional_decimal_option(
                sal_capital_social,
                translation_key="cli.app.modelo.work.sal_reserva_not_decimal",
                default=(
                    "--sal-* values must be decimal amounts; received: {value}. "
                    "Use a dot decimal separator with no thousands grouping, e.g. 1234.56."
                ),
            ),
            autoconsumo_promotor_base=optional_decimal_option(
                autoconsumo_promotor_base,
                translation_key="cli.app.modelo.work.autoconsumo_promotor_base_not_decimal",
                default=(
                    "--autoconsumo-promotor-base must be a decimal amount; received: {value}. "
                    "Use a dot decimal separator with no thousands grouping, e.g. 1234.56."
                ),
            ),
            filing_instance_evidence=filing_instance_evidence,
        )
    except CadrumoError:
        raise
    except (LookupError, ValueError, WorkUnitNotFoundError) as exc:
        raise typer.BadParameter(str(exc)) from exc


def _validate_m349_detail_rows_for_work_unit(work_unit_id: str, rows: tuple[ModeloDetailRow, ...]) -> None:
    operador_rows = tuple(row for row in rows if isinstance(row, Modelo349OperadorRow))
    rectification_rows = tuple(row for row in rows if isinstance(row, Modelo349RectificacionRow))
    if not operador_rows and not rectification_rows:
        return
    unit = get_work_unit(work_unit_id)
    if str(unit.modelo) != Modelo.M349.value:
        return
    for row in operador_rows:
        try:
            validate_m349_country_prefix_context(
                country_code=row.codigo_pais,
                clave_operacion=row.clave_operacion,
                filing_year=unit.filing_year,
                period=unit.period.registry_token,
            )
        except Modelo349CountryPrefixContextError as exc:
            raise bad_parameter_from_error(exc) from exc
    for row in rectification_rows:
        try:
            validate_m349_country_prefix_context(
                country_code=row.codigo_pais,
                clave_operacion=row.clave_operacion,
                filing_year=unit.filing_year,
                period=unit.period.registry_token,
                is_rectification=True,
                rectified_year=int(row.ejercicio),
                rectified_period=row.periodo,
            )
        except Modelo349CountryPrefixContextError as exc:
            raise bad_parameter_from_error(exc) from exc


def bad_parameter_from_error(exc: BaseException) -> typer.BadParameter:
    """Render registered domain errors before crossing the Typer boundary."""
    return typer.BadParameter(resolve_error_message(exc))


def bad_parameter_from_localized_context(exc: BaseException) -> typer.BadParameter:
    """Render local projection refusals that intentionally are not error-code registered."""
    key = getattr(exc, "translated_message", None)
    raw_context = getattr(exc, "context", None)
    context = (
        {key: value for key, value in cast("Mapping[str, object]", raw_context).items()}
        if isinstance(raw_context, Mapping)
        else {}
    )
    if isinstance(key, str) and key:
        return typer.BadParameter(tr(key, **context))
    return typer.BadParameter(str(exc))


def work_candidate_lines(candidates: tuple[ModeloWorkUnitCandidate, ...]) -> str:
    """Return tabular candidate guidance for ambiguous visible filing targets."""
    rows = [
        "candidates:",
        "short_id\tmodelo\tyear\tperiod\trevision_id\tstate\tcurrent\tfiled\tfull_work_unit_id",
    ]
    for candidate in candidates:
        rows.append(
            "\t".join(
                (
                    candidate.short_work_unit_id,
                    str(candidate.modelo),
                    str(candidate.filing_year),
                    candidate.period.registry_token,
                    candidate.revision_id,
                    candidate.state.value,
                    short_id(candidate.current_calculation_revision_id) or "",
                    short_id(candidate.filed_calculation_revision_id) or "",
                    candidate.work_unit_id,
                ),
            ),
        )
    return "\n".join(rows)


def selector_bad_parameter(exc: BaseException) -> typer.BadParameter:
    """Translate visible-target and revision selector refusals for Typer."""
    if isinstance(exc, ModeloWorkVisibleTargetAmbiguousError):
        if exc.selector is not None:
            return typer.BadParameter(
                tr(
                    "cli.app.modelo.work.id_selector_ambiguous",
                    selector=exc.selector,
                    candidates=work_candidate_lines(exc.candidates),
                ),
            )
        return typer.BadParameter(
            tr(
                "cli.app.modelo.work.selector_ambiguous",
                candidates=work_candidate_lines(exc.candidates),
            ),
        )
    if isinstance(exc, ModeloWorkRevisionConflictError):
        return typer.BadParameter(
            tr(
                "cli.app.modelo.work.selector_revision_conflict",
                existing_revision=exc.existing.revision_id,
                requested_revision=exc.requested_revision_id,
            ),
        )
    if isinstance(exc, ModeloCalculationRevisionSelectorAmbiguousError):
        candidates = "\n".join(
            f"{candidate.short_calculation_revision_id}\t{candidate.state.value}\t{candidate.created_at}"
            for candidate in exc.candidates
        )
        return typer.BadParameter(
            tr(
                "cli.app.modelo.work.revision_selector_ambiguous",
                candidates=candidates,
            ),
        )
    if isinstance(exc, ModeloWorkAddressNotFoundError):
        return typer.BadParameter(
            tr(
                "cli.app.modelo.work.selector_not_found",
            ),
        )
    return bad_parameter_from_localized_context(exc)


def parse_revision_selector(value: str) -> ModeloCalculationRevisionSelector:
    """Parse a command-line revision selector token and return a :class:`ModeloCalculationRevisionSelector`."""
    try:
        return ModeloCalculationRevisionSelector(value)
    except ValueError as exc:
        choices = ", ".join(selector.value for selector in ModeloCalculationRevisionSelector)
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_revision_selector",
                value=value,
                choices=choices,
            ),
        ) from exc


def resolve_explicit_or_active_bucket_id(bucket_id: str | None) -> str:
    """Return an explicit ``--bucket-id``, or the active profile bucket when unset.

    Single canonical home for the modelo CLI's ``--bucket-id`` fallback: an
    explicit override lets an accountant scope the command to one profile bucket
    on a shared machine, while omitting it addresses the active profile, which is
    the common single-operator case. A blank explicit value is treated as unset so
    an empty option never reaches storage scoping as a bucket id.

    The refusal is the operator-facing no-active-profile refusal rather than the
    domain error raised by :func:`~core.bucket_pointer.resolve_repository_bucket_id`, because a
    cold-start CLI invocation must distinguish "no profile registered" from
    "registered but logged out" in its suggested next command.

    Args:
        bucket_id: The operator-supplied bucket id, or ``None`` to address the
            active profile bucket.

    Returns:
        The resolved bucket id, trimmed.
    """
    if bucket_id is not None and bucket_id.strip():
        return bucket_id.strip()
    return active_bucket_id_or_refuse()


def resolve_actor_option(actor: str | None) -> str:
    """Resolve the ``--by`` actor label, refusing an over-long operator value here.

    The label becomes the ``actor`` on the bucket event the verb emits, and that
    field is bound by :data:`BUCKET_ACTOR_LABEL_MAX_LENGTH`. Left unchecked, the
    bound is reached only once the event is constructed -- after the calculation
    has run -- and the generic CLI validation boundary reports it as "the command
    input failed validation, check the command's arguments" without naming
    ``--by`` or the bound. The option's own help text does state the bound, so
    the operator could in principle find it; what they could not do is learn from
    the refusal which of a dozen options it was about. Refusing here names the
    option and quotes the accepted length at parse time, and it keeps an
    operator-supplied value from reaching the internal-fault classification
    downstream, where it would be reported as a defect in the application.

    A label resolved from application state rather than from the operator is
    deliberately NOT bounded here: it is not the operator's to correct, and
    silently trimming it would hide a real contract mismatch behind a shortened
    audit label.
    """
    if actor is None or not actor.strip():
        return resolve_default_actor()
    candidate = actor.strip()
    if len(candidate) > BUCKET_ACTOR_LABEL_MAX_LENGTH:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.actor_too_long",
                limit=BUCKET_ACTOR_LABEL_MAX_LENGTH,
                length=len(candidate),
            ),
        )
    return candidate


def resolve_default_actor() -> str:
    """Return the active profile label, or a permanent fallback label."""
    try:
        from ...core.bucket_pointer import resolve_active_bucket_id

        label = active_profile_label()
        if label:
            return label
        active = resolve_active_bucket_id()
        if active:
            return active
    except Exception:
        _log.debug("default actor lookup failed; falling back to operator label", exc_info=True)
    return "operator"


__all__ = [
    "MISSING_INPUT_TRANSLATED_MESSAGES",
    "bad_parameter_from_error",
    "bad_parameter_from_localized_context",
    "optional_decimal_option",
    "parse_binding_override",
    "parse_casilla_override",
    "parse_kv_spec",
    "parse_relation_override",
    "parse_revision_selector",
    "parse_row_spec",
    "resolve_actor_option",
    "resolve_default_actor",
    "resolve_explicit_or_active_bucket_id",
    "selector_bad_parameter",
    "validate_binding_key",
    "validate_calculation_revision_id",
    "validate_casilla_key",
    "validate_relation_key",
    "validate_work_unit_id",
    "work_calculate_input_bundle_from_cli",
    "work_candidate_lines",
]
