"""Public behavior support shared by deferred Modelo command handlers."""

from __future__ import annotations

import typer

from ...application.modelo import (
    ModeloCalculationRevisionDefault,
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorAmbiguousError,
    ModeloCalculationRevisionSelectorNotFoundError,
    ModeloCalculationRevisionSelectorStateError,
    ModeloWorkAddressNotFoundError,
    ModeloWorkPeriodTokenError,
    ModeloWorkRevisionConflictError,
    ModeloWorkSelectorContradictionError,
    ModeloWorkUnitNotFoundError,
    ModeloWorkVisibleTargetAmbiguousError,
    declared_modelo_period_tokens,
    get_work_unit,
    modelo_work_address_from_operator_target,
    profile_requirements_for_binding,
    registry_bindings_for_scope,
    resolve_modelo_revision_for_operator_target,
    resolve_modelo_work_unit_for_operator_target,
)
from ...core import Period, PeriodError, resolve_active_bucket_id
from ...core.aggregation import LEDGER_BINDING_SOURCE_KINDS
from ...core.errors import CadrumoError
from ...core.i18n import tr
from ...core.logging import get_logger
from ...domain.calculations.registry import RegistryValidationError
from ...domain.modelos import CalculationRevision, WorkUnit
from ._common import _no_active_profile_refusal
from ._modelo_cli_support import (
    MISSING_INPUT_TRANSLATED_MESSAGES,
    bad_parameter_from_localized_context,
    parse_revision_selector,
    selector_bad_parameter,
    unsupported_local_work_period_refusal,
    validate_calculation_revision_id,
    validate_work_unit_id,
)

_log = get_logger(__name__)
_M200_M202_PAGOS_RELATION_IDS = frozenset(
    {"modelo-200-2024-rel-202-pagos-fraccionados", "modelo-200-2024-rel-202-pagos-fraccionados-40-2"}
)


def work_address_for_cli(
    *,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None = None,
) -> object:
    exact_id = validate_work_unit_id(work_unit_id) if work_unit_id is not None else None
    typed_period = resolve_optional_cli_period(year=year, period=period, modelo=modelo)
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
        raise bad_parameter_from_localized_context(exc) from exc


def resolve_work_unit_for_cli(
    *,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    bucket_id: str | None = None,
) -> WorkUnit:
    exact_id = validate_work_unit_id(work_unit_id) if work_unit_id is not None else None
    typed_period = resolve_optional_cli_period(year=year, period=period, modelo=modelo)
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
        raise selector_bad_parameter(exc) from exc


def resolve_revision_for_cli(
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
    parsed_selector = parse_revision_selector(selector)
    validated_revision_id = (
        validate_calculation_revision_id(calculation_revision_id) if calculation_revision_id is not None else None
    )
    exact_work_id = validate_work_unit_id(work_unit_id) if work_unit_id is not None else None
    typed_period = resolve_optional_cli_period(year=year, period=period, modelo=modelo)
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
        raise selector_bad_parameter(exc) from exc
    except (
        ModeloCalculationRevisionSelectorNotFoundError,
        ModeloCalculationRevisionSelectorStateError,
        ModeloCalculationRevisionSelectorAmbiguousError,
        ModeloWorkPeriodTokenError,
    ) as exc:
        raise selector_bad_parameter(exc) from exc


def require_active_profile() -> None:
    """Refuse cold-start work commands with the clean no-active-profile message.

    Work commands open the active profile's encrypted bucket database.
    Without an active profile that path raises a raw ``StorageError``
    (``cadrumo_database_url is empty``) or a low-level ``no active bucket
    session`` message — both leak internal plumbing. This guard fires
    first so every cold-start work command produces the same clean,
    translated ``profile create`` guidance that the ledger surface
    already gives.
    """
    if resolve_active_bucket_id() is None:
        raise _no_active_profile_refusal()


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


def resolve_year_period(year: int, period: str, *, modelo: str | None = None) -> Period:
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
        if refusal := unsupported_local_work_period_refusal(modelo=modelo, token=period):
            raise refusal from exc
        raise typer.BadParameter(_period_token_error(year, period, modelo, fallback=str(exc))) from exc


def resolve_optional_cli_period(*, year: int | None, period: str | None, modelo: str | None) -> Period | None:
    """Resolve a raw CLI period string when enough year context was supplied."""
    if period is None:
        return None
    if year is None:
        raise typer.BadParameter(tr("cli.common.errors.period_missing_year", token=period))
    return resolve_year_period(year, period, modelo=modelo)


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


def bare_period_error(modelo: str, period: str, *, fallback: str = "") -> str:
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


def missing_binding_guidance(error: RegistryValidationError, work_unit_id: str) -> str:
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


__all__ = [
    "bare_period_error",
    "missing_binding_guidance",
    "require_active_profile",
    "resolve_optional_cli_period",
    "resolve_revision_for_cli",
    "resolve_work_unit_for_cli",
    "resolve_year_period",
    "work_address_for_cli",
]
