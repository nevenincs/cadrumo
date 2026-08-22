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

from decimal import Decimal
from typing import Annotated

import typer

from ...application.modelo import (
    AmendmentComplementariaLiabilityDecreaseError,
    AmendmentEvidenceMissingError,
    AmendmentKindNotPermittedError,
    AmendmentM303RectificativaMotiveError,
    AmendmentTargetStateError,
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
    WorkUnitNotFoundError,
    amend_modelo_revision,
    declared_modelo_period_tokens,
    get_work_unit,
    guard_active_profile_foral_ccaa,
    lifecycle_continuation_for_work_history,
    modelo_work_address_from_operator_target,
    registry_bindings_for_scope,
    resolve_modelo_revision_for_operator_target,
    resolve_modelo_work_unit_for_operator_target,
)
from ...core import CasillaId, Modelo, Period, PeriodError, validated_casilla_id
from ...core.aggregation import LEDGER_BINDING_SOURCE_KINDS
from ...core.decimal import try_parse_canonical_decimal
from ...core.errors import CadrumoError
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ...core.logging import get_logger
from ...domain.calculations.registry import RegistryValidationError
from ...domain.modelos import (
    CalculationRevision,
    CalculationRevisionAmendmentKind,
    M303RectificativaMotive,
    WorkUnit,
)
from ._command_policy import command_execution_policy
from ._common import (
    MODELO_CODE_CHOICE,
    activate_subcommand_output_language,
    active_bucket_id_or_refuse,
)
from ._modelo_aggregate_cli import register_aggregate_commands
from ._modelo_amend_wizard_cli import register_amend_wizard_commands
from ._modelo_audit_cli import audit_app as audit_app
from ._modelo_audit_cli import register_audit_commands
from ._modelo_cli_support import MISSING_INPUT_TRANSLATED_MESSAGES
from ._modelo_cli_support import (
    bad_parameter_from_error as _bad_parameter_from_error,
)
from ._modelo_cli_support import (
    bad_parameter_from_localized_context as _bad_parameter_from_localized_context,
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
    resolve_actor_option as _resolve_actor_option,
)
from ._modelo_cli_support import (
    resolve_default_actor as _resolve_default_actor,
)
from ._modelo_cli_support import (
    selector_bad_parameter as _selector_bad_parameter,
)
from ._modelo_cli_support import (
    unsupported_local_work_period_refusal as _unsupported_local_work_period_refusal,
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
from ._modelo_execution_policies import CALCULATION_READ, CALCULATION_WRITE, MODEL_READ, declare_metadata_group
from ._modelo_export_cli import register_export_commands
from ._modelo_iva_wallet_cli import register_iva_wallet_commands
from ._modelo_m036_cli import register_m036_commands
from ._modelo_m145_cli import register_m145_communication_commands
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
from ._modelo_review_package_cli import register_review_package_commands
from ._modelo_work import create_work_app
from ._modelo_work_calculate_cli import register_work_calculate_commands
from ._modelo_work_lifecycle_cli import register_work_lifecycle_commands
from ._modelo_work_options import (
    _ActorOpt,
    _BucketIdOpt,
    _ModeloOpt,
    _PeriodOpt,
    _RevisionOpt,
    _WorkUnitIdArg,
    _YearOpt,
)
from ._modelo_work_review_cli import register_work_review_command
from ._modelo_work_revision_cli import register_work_revision_commands
from ._modelo_work_runs_cli import register_work_run_commands
from ._modelo_work_verification_cli import register_work_verification_commands
from ._modelo_work_wizard_cli import register_work_wizard_commands

_log = get_logger(__name__)
_HEX_DIGITS = frozenset("0123456789abcdef")


app = typer.Typer(
    name="modelo",
    help=tr("cli.app.modelo.app_help"),
    no_args_is_help=True,
)
declare_metadata_group(app)


def _validate_work_unit_lookup_id(value: str) -> str:
    """Validate one full work-unit id or lowercase-hex prefix."""
    normalized = value.strip().lower()
    if not normalized or len(normalized) > 64 or not _HEX_DIGITS.issuperset(normalized):
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_work_unit_lookup_id",
            ),
        )
    return normalized


def _work_address_for_cli(
    *,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None = None,
) -> object:
    exact_id = _validate_work_unit_lookup_id(work_unit_id) if work_unit_id is not None else None
    typed_period = _resolve_optional_cli_period(year=year, period=period, modelo=modelo)
    try:
        return modelo_work_address_from_operator_target(
            work_unit_id=exact_id,
            modelo=modelo,
            year=year,
            period=typed_period,
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
    exact_id = _validate_work_unit_lookup_id(work_unit_id) if work_unit_id is not None else None
    typed_period = _resolve_optional_cli_period(year=year, period=period, modelo=modelo)
    try:
        return resolve_modelo_work_unit_for_operator_target(
            work_unit_id=exact_id,
            modelo=modelo,
            year=year,
            period=typed_period,
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
    exact_work_id = _validate_work_unit_lookup_id(work_unit_id) if work_unit_id is not None else None
    typed_period = _resolve_optional_cli_period(year=year, period=period, modelo=modelo)
    try:
        return resolve_modelo_revision_for_operator_target(
            calculation_revision_id=validated_revision_id,
            work_unit_id=exact_work_id,
            modelo=modelo,
            year=year,
            period=typed_period,
            registry_revision_id=registry_revision,
            bucket_id=bucket_id,
            selector=parsed_selector,
            default_for=default_for,
        )
    except ModeloWorkAddressNotFoundError as exc:
        if exc.precondition_failure is not None:
            raise
        raise _selector_bad_parameter(exc) from exc
    except (
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
    (``cadrumo_database_url is empty``) or a low-level ``no active bucket
    session`` message — both leak internal plumbing. This guard fires
    first so every cold-start work command produces the same clean,
    translated ``profile create`` guidance that the ledger surface
    already gives.
    """
    from ...core import resolve_active_bucket_id
    from ._common import _no_active_profile_refusal

    if resolve_active_bucket_id() is None:
        raise _no_active_profile_refusal()


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
    except CadrumoError:
        return ()
    except Exception:
        _log.debug(
            "_declared_period_tokens: unexpected non-CadrumoError suppressed for modelo=%r",
            modelo,
            exc_info=True,
        )
        return ()


def _resolve_year_period(year: int, period: str, *, modelo: str | None = None) -> Period:
    """Normalise CLI ``--year/--period`` into a typed :class:`Period`.

    Operators pass AEAT registry tokens (``1T``, ``0A``, ``01``); the
    backend expects one typed filing period. Registry-only callers should
    project the returned value with ``period.filing_year`` and
    ``period.registry_token`` at the registry boundary.

    ``--year`` and ``--period`` are composed internally; a token that is
    itself a four-digit year (the common ``--period 2024`` confusion)
    would compose to ``2024-2024`` and fail with an opaque message. When
    ``modelo`` is supplied the error instead explains the composition
    and enumerates the registry-declared period tokens for that modelo.
    """
    try:
        return Period.from_year_and_code(year, period.strip())
    except PeriodError as exc:
        if refusal := _unsupported_local_work_period_refusal(modelo=modelo, token=period):
            raise refusal from exc
        raise typer.BadParameter(_period_token_error(year, period, modelo, fallback=str(exc))) from exc


def _resolve_optional_cli_period(*, year: int | None, period: str | None, modelo: str | None) -> Period | None:
    """Resolve a raw CLI period string when enough year context was supplied."""
    if period is None:
        return None
    if year is None:
        raise typer.BadParameter(tr("cli.common.errors.period_missing_year", token=period))
    return _resolve_year_period(year, period, modelo=modelo)


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
            f"filing year and a period token (0A for annual, 1T-4T for quarters, "
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


register_aggregate_commands(app, resolve_year_period=_resolve_year_period)


work_app = create_work_app()
app.add_typer(work_app, name="work")
declare_metadata_group(work_app)


_M200_M202_PAGOS_RELATION_IDS: frozenset[str] = frozenset(
    {
        "modelo-200-2024-rel-202-pagos-fraccionados",
        "modelo-200-2024-rel-202-pagos-fraccionados-40-2",
    },
)


def _bindings_discovery_command(unit: WorkUnit | None) -> str:
    """Return the ``bindings list --missing`` discovery command for the refusal.

    When the work unit resolves, the command is scoped to its modelo / year /
    period. The period is rendered as its bare registry token (e.g. ``1T``):
    ``WorkUnit.period`` is a :class:`Period` whose ``__str__`` is the combined
    ``"2026 1T"`` display form, which would pass the year into the single-token
    ``--period`` option and produce a non-runnable command. The year is a
    distinct ``--year`` axis, so only the token belongs after ``--period``.
    """
    if unit is None:
        return "aeat app modelo bindings list --missing"
    return (
        f"aeat app modelo bindings list --modelo {unit.modelo} "
        f"--year {unit.filing_year} --period {unit.period.registry_token} --missing"
    )


def _date_binding_profile_requirements(unit: WorkUnit | None, binding_id: str) -> str:
    """Name the profile facts an unsatisfied date binding consumes.

    The operator is being told to set something on their profile, so the
    instruction has to name a PROFILE FACT. A binding id names the registry's
    internal consumer of that fact and appears nowhere in the profile editor.

    The resolution itself lives in the application layer, because it reads
    registry binding definitions and this module is budgeted to hold no
    registry-authority reads at all. Here it is a transport: address the work
    unit, delegate, and fall back to the binding id when nothing resolves.
    """
    if unit is None:
        return binding_id
    from ...application.modelo import profile_requirements_for_binding

    return (
        profile_requirements_for_binding(
            modelo=str(unit.modelo),
            filing_year=unit.filing_year,
            period=unit.period,
            binding_id=binding_id,
        )
        or binding_id
    )


def _ledger_sourced_missing_binding(error: RegistryValidationError, unit: WorkUnit | None) -> bool:
    """Return ``True`` when the unsatisfied binding is ledger-aggregation-sourced.

    A ledger-aggregation binding (``LEDGER_BINDING_SOURCE_KINDS``) reads its
    value from the bucket-scoped ledger and REFUSES a caller ``--binding``
    override (``errors.error.error_modelo_aggregation_binding``: "Los bindings
    de agregación derivados del bucket entran en conflicto con los datos
    indicados"). The generic ``--binding KEY=VALUE`` guidance would therefore
    steer the operator straight into that refusal, so such bindings need the
    add-ledger-rows guidance instead.

    The binding's typed ``source`` is resolved from the registry bindings report
    for the work unit's exact filing scope. This is best-effort: a missing work
    unit, no active session, or a binding id that does not match a known row
    (e.g. a ``relation_value_missing`` whose context key is ``relation_id``)
    degrades to ``False`` so the caller keeps the ``--binding`` guidance.
    """
    if unit is None:
        return False
    binding_id = (error.context or {}).get("binding_id")
    if not isinstance(binding_id, str):
        return False
    try:
        report = registry_bindings_for_scope(
            str(unit.modelo),
            period=unit.period,
        )
    except Exception:
        _log.debug("missing-binding guidance source lookup failed", exc_info=True)
        return False
    ledger_values = {kind.value for kind in LEDGER_BINDING_SOURCE_KINDS}
    for row in report.rows:
        if str(row.binding_id) == binding_id:
            return str(row.source) in ledger_values
    return False


def _missing_relation_guidance(
    *,
    base: str,
    error: RegistryValidationError,
    discover_command: str,
) -> str:
    relation_id = (error.context or {}).get("relation_id")
    if isinstance(relation_id, str) and relation_id in _M200_M202_PAGOS_RELATION_IDS:
        return tr(
            "cli.app.modelo.work.missing_relation_guidance_m200_m202",
            default=(
                "{base} Supply Modelo 200 pagos fraccionados from Modelo 202 with --relation "
                "RELATION_ID=VALUE, not --binding. DP200014B:00611 subtracts two mutually "
                "exclusive M202 payment relation channels: modelo-200-2024-rel-202-pagos-fraccionados "
                "for 40.3 casilla 34 and modelo-200-2024-rel-202-pagos-fraccionados-40-2 "
                "for 40.2 casilla 03. When entering manual values, set the unused modality to 0. "
                "Run `{discover}` to list the relation guidance and remaining bindings."
            ),
            base=base,
            discover=discover_command,
        )
    return tr(
        "cli.app.modelo.work.missing_relation_guidance",
        default=(
            "{base} Supply the value with --relation KEY=VALUE on this command; KEY is a "
            "registry relation id, not a binding id. Run `{discover}` to list relation "
            "guidance and the remaining bindings the calculation still needs."
        ),
        base=base,
        discover=discover_command,
    )


def _missing_binding_guidance(error: RegistryValidationError, work_unit_id: str) -> str:
    """Return the missing-binding refusal enriched with operator guidance.

    The registry engine names the unsatisfied binding / relation but
    leaves the operator with no path forward. When the failure is a
    missing-input class, the guidance is routed by the binding's typed
    ``source``:

    * a ledger-aggregation binding (``LEDGER_BINDING_SOURCE_KINDS``) reads from
      the bucket-scoped ledger and rejects a caller ``--binding``, so the
      operator is told to add / classify the relevant ledger rows and run
      ``ledger preflight`` — never to pass ``--binding`` (which the app refuses);
    * relation operands are supplied with ``--relation RELATION_ID=VALUE``.
      Modelo 200's M202 pagos-fraccionados fold-in gets extra wording because
      its relation-prefill target bindings are visible in ``bindings list`` but
      the manual override channel is the relation id, not the binding id;
    * every other ``--binding``-accepting source (``previous_filing`` carries,
      enum / profile bindings) keeps the ``--binding KEY=VALUE`` guidance.

    Both forms append a concrete ``bindings list --missing`` command scoped to
    the work unit's modelo / year / period so the next attempt can succeed.
    Non-input registry-validation errors fall through unchanged.
    """
    base = tr(error.translated_message, **(error.context or {})) if error.translated_message is not None else str(error)
    if error.translated_message not in MISSING_INPUT_TRANSLATED_MESSAGES:
        return base

    # Loading the work unit refines the discovery command with the concrete
    # modelo / year / period AND lets the source-kind router resolve the
    # binding's typed source. It is best-effort enrichment: any failure
    # (missing unit, no active session) degrades to the generic bindings-list
    # command and the --binding guidance rather than masking the original
    # refusal.
    try:
        unit: WorkUnit | None = get_work_unit(work_unit_id)
    except Exception:
        _log.debug("missing-binding guidance work-unit lookup failed", exc_info=True)
        unit = None
    discover_command = _bindings_discovery_command(unit)
    if error.translated_message == "errors.calc.relation_value_missing":
        return _missing_relation_guidance(
            base=base,
            error=error,
            discover_command=discover_command,
        )
    if error.translated_message == "errors.calc.date_binding_value_missing":
        binding_id = (error.context or {}).get("binding_id")
        if not isinstance(binding_id, str):
            binding_id = "the missing date binding"
        return tr(
            "cli.app.modelo.work.missing_date_binding_guidance",
            default=(
                "{base} Set {requirements} on the active profile, then rerun calculate. "
                "Date-valued profile facts cannot be supplied with --binding. "
                "Run `{discover}` to list every binding the calculation still needs."
            ),
            base=base,
            requirements=_date_binding_profile_requirements(unit, binding_id),
            discover=discover_command,
        )
    if _ledger_sourced_missing_binding(error, unit):
        return tr(
            "cli.app.modelo.work.missing_binding_guidance_ledger",
            default=(
                "{base} This value is aggregated from the bucket ledger and "
                "cannot be supplied with --binding. Add or classify the "
                "relevant ledger rows, run `aeat app ledger preflight`, then "
                "rerun calculate. Run `{discover}` to list every binding the "
                "calculation still needs."
            ),
            base=base,
            discover=discover_command,
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
    resolve_actor_option=_resolve_actor_option,
    calculate_input_bundle_from_cli=_work_calculate_input_bundle_from_cli,
    bad_parameter_from_error=_bad_parameter_from_error,
    missing_binding_guidance=_missing_binding_guidance,
)


register_work_wizard_commands(
    work_app,
    activate_output_language=activate_subcommand_output_language,
    require_active_profile=_require_active_profile,
    resolve_work_unit_for_cli=_resolve_work_unit_for_cli,
    resolve_actor_option=_resolve_actor_option,
    bad_parameter_from_error=_bad_parameter_from_error,
)


@work_app.command(
    "compare-taxation",
    help=tr("cli.app.modelo.work.compare_taxation_help"),
)
@command_execution_policy(CALCULATION_READ)
def work_compare_taxation(
    ctx: typer.Context,
    work_unit_id: _WorkUnitIdArg = None,
    modelo: _ModeloOpt = None,
    year: _YearOpt = None,
    period: _PeriodOpt = None,
    revision: _RevisionOpt = None,
    bucket_id: _BucketIdOpt = None,
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
        modelo=Modelo(comparison.modelo),
        revision=comparison.revision,
        conjunta_cuota_resultante=str(comparison.conjunta_cuota_resultante),
        individual_cuota_resultante=str(comparison.individual_cuota_resultante),
        conjunta_resultado=str(comparison.conjunta_resultado),
        individual_resultado=str(comparison.individual_resultado),
        delta_resultado=str(comparison.delta_resultado),
        recommendation=comparison.recommendation,
        recommendation_reason=comparison.recommendation_reason,
        individual_branch_single_earner_only=comparison.individual_branch_single_earner_only,
    )
    from ._modelo_rendering import advisory_notice

    # Honesty caveat: the individual branch is faithful only for
    # a single-earner unidad familiar. Surface it on the typed notices channel so
    # an operator is never misled into trusting a two-earner individual figure the
    # comparator cannot compute.
    caveat_notice = (
        advisory_notice(
            "modelo.work.compare_taxation.individual_single_earner_only",
            comparison.individual_branch_caveat,
            context={"individual_branch_single_earner_only": "true"},
        )
        if comparison.individual_branch_single_earner_only
        else None
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
    if caveat_notice is not None:
        lines.append(f"WARNING\t{comparison.individual_branch_caveat}")
    _emit_envelope(
        ctx,
        command="modelo.work.compare_taxation",
        result=result,
        lines=lines,
        notices=[caveat_notice] if caveat_notice is not None else None,
    )


register_work_revision_commands(
    work_app,
    activate_output_language=activate_subcommand_output_language,
    require_active_profile=_require_active_profile,
    resolve_work_unit_for_cli=_resolve_work_unit_for_cli,
    resolve_revision_for_cli=_resolve_revision_for_cli,
    bad_parameter_from_error=_bad_parameter_from_error,
    selector_bad_parameter=_selector_bad_parameter,
)


register_work_review_command(
    work_app,
    activate_output_language=activate_subcommand_output_language,
    require_active_profile=_require_active_profile,
    resolve_work_unit_for_cli=_resolve_work_unit_for_cli,
)


@work_app.command(
    "history",
    help=tr("cli.app.modelo.work.history_help"),
)
@command_execution_policy(MODEL_READ)
def work_history(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str | None,
        typer.Argument(
            help=tr("cli.app.modelo.work.history_work_unit_id_help"),
        ),
    ] = None,
    modelo: _ModeloOpt = None,
    year: _YearOpt = None,
    period: _PeriodOpt = None,
    revision: _RevisionOpt = None,
    bucket_id: _BucketIdOpt = None,
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
    from ._common import _emit_envelope, resolve_lifecycle_continuation_notice
    from ._modelo_payloads import WorkHistoryResult, WorkUnitHistoryEventPayload

    result = WorkHistoryResult(
        bucket_id=history.bucket_id,
        work_unit_id=history.work_unit_id,
        event_count=len(history.events),
        events=[
            WorkUnitHistoryEventPayload(
                event_id=event.event_id,
                occurred_at=event.occurred_at,
                event_type=event.event_type,
                object_type=event.object_type,
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
    next_step = resolve_lifecycle_continuation_notice(lifecycle_continuation_for_work_history(unit))
    _emit_envelope(ctx, command="modelo.work.history", result=result, lines=lines, notices=[next_step])


register_work_verification_commands(
    work_app,
    activate_output_language=activate_subcommand_output_language,
    require_active_profile=_require_active_profile,
    resolve_revision_for_cli=_resolve_revision_for_cli,
    resolve_default_actor=_resolve_default_actor,
    bad_parameter_from_error=_bad_parameter_from_error,
)


register_work_run_commands(
    work_app,
    activate_output_language=activate_subcommand_output_language,
    bad_parameter_from_error=_bad_parameter_from_error,
    resolve_optional_cli_period=_resolve_optional_cli_period,
)


def _parse_amendment_casilla(spec: str) -> tuple[CasillaId, Decimal]:
    def _to_decimal(value: str) -> Decimal:
        # An amendment restates a casilla on an already-filed declaration, so the
        # canonical euro-amount grammar applies at full strength: a bare Decimal
        # call admitted ``1e3``, ``+140000``, ``1_000``, ``.5``, and the
        # non-finite ``NaN``/``Infinity`` — and a NaN amount compares False to
        # every threshold, so an under-declaration advisory keyed on ``> 0``
        # would never fire for it.
        parsed = try_parse_canonical_decimal(value, max_fraction_digits=2)
        if parsed is None:
            raise typer.BadParameter(tr("cli.app.modelo.work.set_not_decimal", value=value))
        return parsed

    key, value = _parse_kv_spec(
        spec,
        flag="--set",
        key_label="CASILLA",
        value_label="DECIMAL",
        transform=_to_decimal,
        key_validator=_validate_casilla_key,
        strip_key=False,
    )
    return validated_casilla_id(key, surface="--set casilla"), value


def _required_amendment_inputs(
    *,
    from_filing_record_id: str | None,
    kind: CalculationRevisionAmendmentKind | None,
    reason: str | None,
    set_overrides: list[str] | None,
) -> tuple[str, CalculationRevisionAmendmentKind, str, tuple[str, ...]]:
    """Return raw amendment CLI inputs or raise one combined option error."""
    missing: list[str] = []
    if not from_filing_record_id or not from_filing_record_id.strip():
        missing.append("--from-filing-record")
    if kind is None:
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


def _parse_amendment_overrides(set_overrides: tuple[str, ...]) -> dict[CasillaId, Decimal]:
    """Parse ``--set`` values into validated ``CasillaId`` decimal overrides."""
    overrides: dict[CasillaId, Decimal] = {}
    for spec in set_overrides:
        key, value = _parse_amendment_casilla(spec)
        overrides[key] = value
    if not overrides:
        raise typer.BadParameter(tr("cli.app.modelo.work.amend_set_required"))
    return overrides


@work_app.command("amend", help=tr("cli.app.modelo.work.amend_help"))
@command_execution_policy(CALCULATION_WRITE)
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
        CalculationRevisionAmendmentKind | None,
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
    m303_rectificativa_motive: Annotated[
        M303RectificativaMotive | None,
        typer.Option(
            "--m303-rectificativa-motive",
            help=tr("cli.app.modelo.work.m303_rectificativa_motive_help"),
        ),
    ] = None,
    actor: _ActorOpt = None,
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
    invocation at a time. The command then parses the requested
    :class:`CalculationRevisionAmendmentKind`, validates each override as a
    ``CasillaId`` decimal, delegates to
    :func:`amend_modelo_revision`, and emits a
    :class:`WorkAmendResult`.

    The application service requires the source
    :class:`ModeloRecord` to carry
    :class:`ExternalEvidence`; locally filed records cannot
    enter this path. The new record is an internal filing envelope and does not
    submit anything to AEAT.
    """
    from_filing_record_id, kind, reason, set_specs = _required_amendment_inputs(
        from_filing_record_id=from_filing_record_id,
        kind=kind,
        reason=reason,
        set_overrides=set_overrides,
    )
    _require_active_profile()
    overrides = _parse_amendment_overrides(set_specs)

    try:
        from ...adapters.persistence.profile.justificante import JustificanteRepository

        record = amend_modelo_revision(
            from_filing_record_id=from_filing_record_id,
            overrides=overrides,
            amendment_kind=kind,
            m303_rectificativa_motive=m303_rectificativa_motive,
            reason=reason,
            actor=actor or _resolve_default_actor(),
            justificante_repository=JustificanteRepository(),
        )
    except (
        ModeloRecordNotFoundError,
        AmendmentEvidenceMissingError,
        AmendmentTargetStateError,
        AmendmentKindNotPermittedError,
        AmendmentM303RectificativaMotiveError,
        AmendmentComplementariaLiabilityDecreaseError,
        CalculationRevisionNotFoundError,
        CalculationRevisionStateError,
        WorkUnitNotFoundError,
    ) as exc:
        raise _bad_parameter_from_error(exc) from exc

    from ._common import _emit_envelope
    from ._modelo_payloads import WorkAmendResult

    result = WorkAmendResult.model_validate(
        {
            "amendment_kind": kind.value,
            "m303_rectificativa_motive": m303_rectificativa_motive,
            "amends_filing_record_id": from_filing_record_id,
            **_filing_record_payload(record).model_dump(mode="python"),
        },
    )
    lines = [
        "operation\tmodelo.work.amend",
        f"amendment_kind\t{kind.value}",
        f"m303_rectificativa_motive\t{m303_rectificativa_motive.value if m303_rectificativa_motive else ''}",
        f"amends_filing_record_id\t{from_filing_record_id}",
        *_filing_record_lines(record),
    ]
    lines.append("filing_disambiguation\t(internal only — does not submit to AEAT)")
    _emit_envelope(ctx, command="modelo.work.amend", result=result, lines=lines)


register_amend_wizard_commands(
    work_app,
    activate_output_language=activate_subcommand_output_language,
    require_active_profile=_require_active_profile,
    resolve_work_unit_for_cli=_resolve_work_unit_for_cli,
    resolve_default_actor=_resolve_default_actor,
    bad_parameter_from_error=_bad_parameter_from_error,
)


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
@command_execution_policy(MODEL_READ)
def modelo_history(
    ctx: typer.Context,
    modelo: Annotated[
        str,
        typer.Option(
            "--modelo",
            click_type=MODELO_CODE_CHOICE,
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
    from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ...domain.buckets import BucketEvent, BucketEventType

    def _event_filing_year(payload: dict[str, str]) -> str:
        return (payload.get("filing_year") or payload.get("year") or "").strip()

    repo = BucketEventHistoryRepository()
    catalogue = repo.load()
    modelo_event_types = {
        BucketEventType.MODELO_CALCULATION_CREATED,
        BucketEventType.MODELO_VERIFICATION_PASSED,
        BucketEventType.MODELO_VERIFICATION_REFUSED,
        BucketEventType.MODELO_EXPORTED,
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
        if year is not None and _event_filing_year(payload_map) != str(year):
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
                event_type=e.event_type,
                occurred_at=e.occurred_at,
                actor=e.actor,
                object_type=e.object_type,
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
    active_bucket_id=active_bucket_id_or_refuse,
)


register_audit_commands(app)


register_review_package_commands(app)


register_export_commands(
    app,
    bad_parameter_from_error=_bad_parameter_from_error,
    selector_bad_parameter=_selector_bad_parameter,
    resolve_default_actor=_resolve_default_actor,
    resolve_optional_cli_period=_resolve_optional_cli_period,
)


register_projection_commands(
    app,
    require_active_profile=_require_active_profile,
    parse_casilla_override=_parse_casilla_override,
    parse_binding_override=_parse_binding_override,
    bad_parameter_from_error=_bad_parameter_from_error,
    bad_parameter_from_localized_context=_bad_parameter_from_localized_context,
)


register_iva_wallet_commands(app, active_bucket_id=active_bucket_id_or_refuse)


register_maritime_commands(
    work_app,
    require_active_profile=_require_active_profile,
    activate_output_language=activate_subcommand_output_language,
    bad_parameter_from_error=_bad_parameter_from_error,
)


register_m036_commands(
    app,
    require_active_profile=_require_active_profile,
    active_bucket_id=active_bucket_id_or_refuse,
)


register_m145_communication_commands(
    app,
    require_active_profile=_require_active_profile,
    active_bucket_id=active_bucket_id_or_refuse,
    parse_casilla_override=_parse_casilla_override,
    resolve_default_actor=_resolve_default_actor,
)


__all__ = [
    "_verification_report_lines",
    "_verification_report_payload",
    "app",
    "audit_app",
    "filing_record_app",
    "verification_report_app",
]
