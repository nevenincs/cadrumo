"""Public behavior support shared by deferred Modelo command handlers."""

from __future__ import annotations

import typer

from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...application.modelo._selectors import (
    ModeloCalculationRevisionDefault,
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorAmbiguousError,
    ModeloCalculationRevisionSelectorNotFoundError,
    ModeloCalculationRevisionSelectorStateError,
)
from ...application.modelo.registry_discovery import declared_modelo_period_tokens
from ...application.modelo.work_addressing import (
    ModeloWorkAddressNotFoundError,
    ModeloWorkPeriodTokenError,
    ModeloWorkRevisionConflictError,
    ModeloWorkSelectorContradictionError,
    ModeloWorkUnitNotFoundError,
    ModeloWorkVisibleTargetAmbiguousError,
    modelo_work_address_from_operator_target,
    resolve_modelo_revision_for_operator_target,
    resolve_modelo_work_unit_for_operator_target,
)
from ...core import Period, PeriodError
from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.errors.hierarchy import CadrumoError
from ...core.i18n import tr
from ...core.logging import get_logger
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from ...domain.modelos.calculation_revision import CalculationRevision
from ._common import _no_active_profile_refusal
from ._modelo_cli_support import (
    bad_parameter_from_localized_context,
    parse_revision_selector,
    selector_bad_parameter,
    unsupported_local_work_period_refusal,
    validate_calculation_revision_id,
    validate_work_unit_id,
)

_log = get_logger(__name__)


def _captured_work_catalogue(bucket_id: str | None) -> tuple[WorkUnitCatalogue, str]:
    """Capture the caller-owned work catalogue under one explicit bucket."""
    resolved_bucket_id = bucket_id or resolve_active_bucket_id()
    if resolved_bucket_id is None:
        require_active_profile()
        raise AssertionError("require_active_profile must refuse without a bucket")
    return (WorkUnitCatalogueRepository(bucket_id=resolved_bucket_id).load(), resolved_bucket_id)


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
    catalogue, resolved_bucket_id = _captured_work_catalogue(bucket_id)
    try:
        return resolve_modelo_work_unit_for_operator_target(
            work_unit_id=exact_id,
            modelo=modelo,
            year=year,
            period=typed_period,
            registry_revision_id=revision,
            bucket_id=bucket_id,
            catalogue=catalogue,
            resolved_bucket_id=resolved_bucket_id,
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
    period: str | Period | None,
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
    typed_period = (
        period if isinstance(period, Period) else resolve_optional_cli_period(year=year, period=period, modelo=modelo)
    )
    catalogue, resolved_bucket_id = _captured_work_catalogue(bucket_id)
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
            catalogue=catalogue,
            resolved_bucket_id=resolved_bucket_id,
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

    from ...application.modelo._data_inventory import profile_requirements_for_binding

    return (
        profile_requirements_for_binding(
            modelo=str(unit.modelo),
            filing_year=unit.filing_year,
            period=unit.period,
            binding_id=binding_id,
        )
        or binding_id
    )


__all__ = [
    "bare_period_error",
    "require_active_profile",
    "resolve_optional_cli_period",
    "resolve_revision_for_cli",
    "resolve_work_unit_for_cli",
    "resolve_year_period",
    "work_address_for_cli",
]
