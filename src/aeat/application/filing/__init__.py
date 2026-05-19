"""Typed filing draft API guarded by registry-backed runtime providers."""

from __future__ import annotations

from ...core.errors import BaseSeverity
from collections.abc import Iterator, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from ...core.resources import resources
from ...domain.calculations.registry import (
    RegistrySnapshot,
    RegistrySnapshotError,
    RegistryValidationError,
    calculate_registry_snapshot,
)
from ...domain.calculations.registry._schema import RegistrySnapshotRef
from ...domain.filing import (
    APPROVAL_BASIS_VERSION,
    AmendmentKind,
    CasillaChange,
    CasillaCollection,
    CasillaDelta,
    CasillaInputs,
    CasillaSchema,
    CasillaSchemaProvider,
    DeadlineChecker,
    DeadlineStatus,
    FilingAmendment,
    FilingAmendmentError,
    FilingAmendmentValidationError,
    FilingApprovalBasis,
    FilingBindingValue,
    FilingBuilderError,
    FilingComputationError,
    FilingDraft,
    FilingDraftError,
    ModeloDraftStatus,
    FilingImportError,
    FilingInputs,
    FilingProfile,
    FilingScalar,
    FilingValidationError,
    FilingValidationFinding,
    FilingValidator,
    FilingValue,
    FilingValueKind,
    ModeloCode,
    ModeloIdentity,
    apply_validation,
    compute_draft_id,
    derive_validation_status,
    make_amendment_id,
)
from ...domain.period import (
    PeriodValidationError,
    parse_canonical_period,
    period_end_date,
)
from ._calculate import (
    DeclaracionCalculateNextAction,
    DeclaracionCalculateSummary,
    summarise_calculation,
)
from ._complementaria import build_complementaria, list_amendments, load_amendment
from ._export import (
    DeclaracionExportFormat,
    DeclaracionExportResult,
    DeclaracionVerifyResult,
    DeclaracionVerifyVerdict,
    export_draft,
    verify_export,
)
from ._history_models import FilingHistory, FilingHistoryEntry
from ._import import JustificanteImportResult, import_filing_from_justificante
from ._review import (
    FilingApprovalStaleReason,
    approval_stale_reasons,
    approve_draft,
    compute_current_approval_basis,
    compute_review_checksum,
    describe_stale_reason,
    refresh_review_status,
    unapprove_draft,
)
from .errors import FilingApplicationError, FilingCalculateError
from .runtime import (
    FilingOperatorProfile,
    build_runtime_schema_provider,
    filing_profile_from_autonomo,
    load_default_filing_profile,
)


def build_draft(
    *,
    modelo: str,
    period: str,
    profile: FilingProfile,
    inputs: FilingInputs,
    schema_provider: CasillaSchemaProvider,
    deadline_checker: DeadlineChecker | None = None,
    fail_on_warning: bool = False,
) -> FilingDraft:
    """Build and validate a filing draft from a registry snapshot.

    Args:
        modelo: Stable modelo string ID.
        period: Period identifier.
        profile: Taxpayer profile the draft would be built for.
        inputs: Raw filing inputs.
        schema_provider: Registry-backed casilla schema provider.
        deadline_checker: Optional deadline checker.
        fail_on_warning: Raise when validation produces any warning or error.

    Raises:
        FilingBuilderError: If the registry has no matching snapshot,
            inputs are malformed, or strict validation fails.
    """

    snapshot = _load_registry_snapshot(modelo=modelo, period=period)
    filing_year, registry_period = _registry_period(period)
    snapshot_ref = RegistrySnapshotRef(
        modelo=snapshot.modelo.id,
        revision_id=snapshot.revision.id,
        filing_year=filing_year,
        period=registry_period,
    )
    collection = schema_provider.get_collection(modelo)
    if collection.schema_version != f"registry:{snapshot.modelo.id}:{snapshot.revision.id}":
        raise FilingBuilderError(
            f"schema provider version {collection.schema_version!r} does not match registry snapshot "
            f"{snapshot.revision.id!r}"
        )
    casilla_ids = {casilla.id for casilla in snapshot.revision.casillas}
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}
    calculation_binding_ids = _formula_binding_ids(snapshot)
    casilla_inputs = _decimal_inputs_for_ids(inputs, casilla_ids)
    binding_inputs = _decimal_inputs_for_ids(inputs, calculation_binding_ids)
    filing_binding_values = _filing_binding_values(inputs, bindings)
    try:
        result = calculate_registry_snapshot(
            snapshot,
            inputs=casilla_inputs,
            date_context={"filing_period": _filing_period_date(period)},
            binding_values=binding_inputs,
        )
    except RegistryValidationError as exc:
        raise FilingBuilderError(f"registry calculation failed: {exc}") from exc
    entries = {entry.target: entry for entry in result.entries}
    schema_ids = {casilla.id for casilla in collection.all()}
    values: list[FilingValue] = []
    for casilla in snapshot.revision.casillas:
        if casilla.input_kind == "computed":
            entry = entries[casilla.id]
            trace = tuple(ref for ref in entry.operand_refs if ref in schema_ids)
            values.append(
                FilingValue(
                    casilla_id=casilla.id,
                    value=result.values[casilla.id],
                    kind=FilingValueKind.COMPUTED,
                    source=f"registry formula {entry.formula_id}",
                    formula_trace=trace,
                )
            )
            continue
        if casilla.id in casilla_inputs:
            values.append(
                FilingValue(
                    casilla_id=casilla.id,
                    value=casilla_inputs[casilla.id],
                    kind=FilingValueKind.LITERAL,
                    source="registry input",
                )
            )
            continue
        values.append(
            FilingValue(
                casilla_id=casilla.id,
                value=None,
                kind=FilingValueKind.EMPTY,
                source="registry schema",
            )
        )
    created_at = utc_now()
    value_tuple = tuple(sorted(values, key=lambda value: value.casilla_id))
    binding_value_tuple = tuple(sorted(filing_binding_values, key=lambda value: value.binding_id))
    # Propagate identity from the validated profile substrate into the
    # draft. ``profile.tax_id`` is already validated against the AEAT
    # checksum via ``SubjectTaxId`` on the profile model, so the
    # post-validation result type-checks at the FilingDraft boundary
    # and survives every downstream encrypted-persistence roundtrip.
    draft = FilingDraft(
        draft_id=compute_draft_id(
            modelo=modelo,
            period=period,
            profile_tax_id=profile.tax_id,
            schema_version=collection.schema_version,
            values=value_tuple,
            binding_values=binding_value_tuple,
        ),
        modelo=modelo,
        period=period,
        profile_tax_id=profile.tax_id,
        subject_tax_id=profile.tax_id,
        snapshot_ref=snapshot_ref,
        status=ModeloDraftStatus.DRAFT,
        values=value_tuple,
        binding_values=binding_value_tuple,
        created_at=created_at,
        updated_at=created_at,
        schema_version=collection.schema_version,
    )
    validator = FilingValidator(schema_provider=schema_provider, deadline_checker=deadline_checker)
    findings = validator.validate(draft)
    if fail_on_warning and findings:
        raise FilingBuilderError("draft validation produced findings under fail_on_warning")
    return apply_validation(draft, findings)


@lru_cache(maxsize=128)
def _load_registry_snapshot(*, modelo: str, period: str) -> RegistrySnapshot:
    filing_year, registry_period = _registry_period(period)
    try:
        authority = resources().modelos.authority
        return authority.snapshot(
            modelo,
            filing_year=filing_year,
            period=registry_period,
        )
    except RegistrySnapshotError as exc:
        raise FilingBuilderError(
            f"registry snapshot is not available for modelo={modelo} period={period}: {exc}"
        ) from exc


def _registry_period(period: str) -> tuple[int, str]:
    try:
        return parse_canonical_period(period)
    except PeriodValidationError as exc:
        raise FilingBuilderError(str(exc)) from exc


def _filing_period_date(period: str) -> date:
    filing_year, registry_period = _registry_period(period)
    return period_end_date(filing_year, registry_period)


def _formula_binding_ids(snapshot: RegistrySnapshot) -> set[str]:
    binding_ids: set[str] = set()
    for formula in snapshot.revision.formulas:
        _collect_formula_binding_ids(formula.expression, binding_ids)
    return binding_ids


def _collect_formula_binding_ids(expression: object, binding_ids: set[str]) -> None:
    binding = getattr(expression, "binding", None)
    if binding is not None:
        binding_ids.add(str(binding))
    for arg in getattr(expression, "args", ()):
        _collect_formula_binding_ids(arg, binding_ids)


def _decimal_inputs_for_ids(inputs: FilingInputs, input_ids: set[str]) -> dict[str, Decimal]:
    decimal_inputs: dict[str, Decimal] = {}
    for casilla_id, value in inputs.items():
        if casilla_id not in input_ids:
            continue
        if value is None:
            continue
        decimal_inputs[casilla_id] = _decimal_input(casilla_id, value)
    return decimal_inputs


def _filing_binding_values(inputs: FilingInputs, bindings: Mapping[str, object]) -> list[FilingBindingValue]:
    values: list[FilingBindingValue] = []
    for binding_id, binding in bindings.items():
        if binding_id not in inputs or inputs[binding_id] is None:
            continue
        raw_value = inputs[binding_id]
        if isinstance(raw_value, list | tuple):
            values.extend(
                FilingBindingValue(
                    binding_id=binding_id,
                    value=_binding_input(binding_id, row_value, binding),
                    kind=FilingValueKind.LITERAL,
                    source="registry binding input",
                    row_index=index,
                )
                for index, row_value in enumerate(raw_value, start=1)
            )
            continue
        if isinstance(raw_value, Mapping):
            values.extend(
                FilingBindingValue(
                    binding_id=binding_id,
                    value=_binding_input(binding_id, row_value, binding),
                    kind=FilingValueKind.LITERAL,
                    source="registry binding input",
                    row_index=_binding_row_index(binding_id, row_key),
                )
                for row_key, row_value in raw_value.items()
            )
            continue
        values.append(
            FilingBindingValue(
                binding_id=binding_id,
                value=_binding_input(binding_id, raw_value, binding),
                kind=FilingValueKind.LITERAL,
                source="registry binding input",
            )
        )
    return values


def _binding_row_index(binding_id: str, row_key: object) -> int:
    if isinstance(row_key, bool):
        raise FilingBuilderError(f"binding input {binding_id!r} row key must be a positive integer")
    if isinstance(row_key, int):
        index = row_key
    elif isinstance(row_key, str):
        try:
            index = int(row_key)
        except ValueError as exc:
            raise FilingBuilderError(f"binding input {binding_id!r} row key must be a positive integer") from exc
    else:
        raise FilingBuilderError(f"binding input {binding_id!r} row key must be a positive integer")
    if index < 1:
        raise FilingBuilderError(f"binding input {binding_id!r} row key must be a positive integer")
    return index


def _binding_input(binding_id: str, value: object, binding: object) -> FilingScalar:
    selector = getattr(binding, "selector", None)
    data_type = str(getattr(selector, "data_type", None) or "decimal")
    if data_type == "text":
        return str(value)
    if data_type == "integer":
        decimal_value = _decimal_input(binding_id, value)
        if decimal_value != decimal_value.to_integral_value():
            raise FilingBuilderError(f"binding input {binding_id!r} must be an integer value")
        return int(decimal_value)
    if data_type == "boolean":
        return _boolean_input(binding_id, value)
    if data_type in {"decimal", "money"}:
        return _decimal_input(binding_id, value)
    raise FilingBuilderError(f"binding input {binding_id!r} declares unsupported data type {data_type!r}")


def _decimal_input(input_id: str, value: object) -> Decimal:
    if isinstance(value, bool):
        raise FilingBuilderError(f"input {input_id!r} must be a Decimal value")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | str):
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise FilingBuilderError(f"input {input_id!r} must be a Decimal value") from exc
    raise FilingBuilderError(f"input {input_id!r} must be a Decimal value")


def _boolean_input(input_id: str, value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "s", "si", "yes"}:
            return True
        if normalized in {"0", "false", "n", "no"}:
            return False
    raise FilingBuilderError(f"binding input {input_id!r} must be a boolean value")


def validate_draft(
    draft: FilingDraft,
    *,
    bucket_id: str,
    schema_provider: CasillaSchemaProvider,
    deadline_checker: DeadlineChecker | None = None,
) -> FilingDraft:
    """Re-run validation against an existing draft.

    The returned draft preserves ``draft_id`` because the hash
    excludes findings, status, ``updated_at`` and ``notes``.

    Args:
        draft: The draft to re-validate.
        schema_provider: Resolves the casilla collection for the
            draft's modelo.
        deadline_checker: Optional deadline check Protocol implementation.

    Returns:
        A new :class:`FilingDraft` with refreshed findings, status
        and ``updated_at``.
    """
    validator = FilingValidator(
        schema_provider=schema_provider,
        deadline_checker=deadline_checker,
    )
    findings = validator.validate(draft)
    refreshed = apply_validation(draft, findings)
    refreshed = refresh_review_status(
        refreshed,
        bucket_id=bucket_id,
        schema_provider=schema_provider,
    )
    # Defensive sanity check: re-validation must never change identity.
    assert refreshed.draft_id == draft.draft_id, "validate_draft must preserve draft_id"
    return refreshed


_SEVERITY_RANK: dict[str, int] = {
    BaseSeverity.INFO: 0,
    BaseSeverity.WARNING: 1,
    BaseSeverity.ERROR: 2,
}


def iter_findings(
    draft: FilingDraft,
    *,
    severity_at_least: str = "WARNING",
) -> Iterator[FilingValidationFinding]:
    """Yield findings filtered by minimum severity.

    Args:
        draft: The draft to scan.
        severity_at_least: Minimum severity to yield, one of
            ``"INFO"``, ``"WARNING"``, ``"ERROR"``. Defaults to
            ``"WARNING"``.

    Yields:
        Each :class:`FilingValidationFinding` whose severity meets
        or exceeds the threshold, in declaration order.

    Raises:
        ValueError: When ``severity_at_least`` is not a known
            severity name.
    """
    try:
        threshold = _SEVERITY_RANK[BaseSeverity[severity_at_least]]
    except KeyError as exc:
        raise FilingCalculateError(f"Unknown severity {severity_at_least!r}; expected INFO, WARNING, or ERROR") from exc
    for finding in draft.findings:
        if _SEVERITY_RANK[finding.severity] >= threshold:
            yield finding


def utc_now() -> datetime:
    """Return the current UTC time, used by tests for determinism hooks."""
    return datetime.now(tz=UTC)


__all__ = [
    "APPROVAL_BASIS_VERSION",
    "AmendmentKind",
    "CasillaChange",
    "CasillaCollection",
    "CasillaDelta",
    "CasillaInputs",
    "CasillaSchema",
    "CasillaSchemaProvider",
    "DeadlineChecker",
    "DeadlineStatus",
    "DeclaracionCalculateNextAction",
    "DeclaracionCalculateSummary",
    "DeclaracionExportFormat",
    "DeclaracionExportResult",
    "DeclaracionVerifyResult",
    "DeclaracionVerifyVerdict",
    "FilingAmendment",
    "FilingAmendmentError",
    "FilingAmendmentValidationError",
    "FilingApplicationError",
    "FilingApprovalBasis",
    "FilingApprovalStaleReason",
    "FilingBindingValue",
    "FilingBuilderError",
    "FilingCalculateError",
    "FilingComputationError",
    "FilingDraft",
    "FilingDraftError",
    "ModeloDraftStatus",
    "FilingHistory",
    "FilingHistoryEntry",
    "FilingImportError",
    "FilingInputs",
    "FilingOperatorProfile",
    "FilingProfile",
    "FilingScalar",
    "FilingValidationError",
    "FilingValidationFinding",
    "FilingValidator",
    "FilingValue",
    "FilingValueKind",
    "JustificanteImportResult",
    "ModeloCode",
    "ModeloIdentity",
    "apply_validation",
    "approval_stale_reasons",
    "approve_draft",
    "build_complementaria",
    "build_draft",
    "build_runtime_schema_provider",
    "compute_current_approval_basis",
    "compute_draft_id",
    "compute_review_checksum",
    "derive_validation_status",
    "describe_stale_reason",
    "export_draft",
    "filing_profile_from_autonomo",
    "import_filing_from_justificante",
    "iter_findings",
    "list_amendments",
    "load_amendment",
    "load_default_filing_profile",
    "make_amendment_id",
    "refresh_review_status",
    "summarise_calculation",
    "unapprove_draft",
    "verify_export",
]