"""Typed filing draft API guarded by registry-backed runtime providers.

All draft creation, input validation, and calculation entry points consume
a :class:`RegistrySnapshot` to resolve the active revision, its casilla
schema, and its formula graph.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from ...core import BindingSourceKind as _BindingSourceKind
from ...core import Period as _Period
from ...core.errors import BaseSeverity as _BaseSeverity
from ...core.parsing import parse_iso8601_date as _parse_iso8601_date
from ...core.resources import resources as _resources
from ...core.time import now as _utc_now
from ...domain.calculations.registry import (
    InputKind as _InputKind,
)
from ...domain.calculations.registry import (
    RegistrySnapshot as _RegistrySnapshot,
)
from ...domain.calculations.registry import (
    RegistrySnapshotError as _RegistrySnapshotError,
)
from ...domain.calculations.registry import (
    RegistrySnapshotRef as _RegistrySnapshotRef,
)
from ...domain.calculations.registry import (
    RegistryValidationError as _RegistryValidationError,
)
from ...domain.calculations.registry import (
    calculate_registry_snapshot as _calculate_registry_snapshot,
)
from ...domain.calculations.registry import (
    enum_consumed_binding_ids as _enum_consumed_binding_ids,
)
from ...domain.calculations.registry import (
    expression_date_binding_refs as _expression_date_binding_refs,
)
from ...domain.filing import (
    APPROVAL_BASIS_VERSION,
    CasillaDelta,
    CasillaInputs,
    CasillaSchemaProvider,
    DeadlineChecker,
    ModeloBindingValue,
    ModeloBuilderError,
    ModeloCasillaProvenance,
    ModeloCode,
    ModeloDraft,
    ModeloInputs,
    ModeloProfile,
    ModeloScalar,
    ModeloValidationFinding,
    ModeloValidator,
    ModeloValue,
    ModeloValueKind,
    apply_validation,
    compute_modelo_draft_id,
    derive_validation_status,
    make_amendment_id,
)
from ...domain.submission import ModeloDraftStatus
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
from ._history_models import ModeloHistory, ModeloHistoryEntry
from ._history_repository import ModeloHistoryRepository
from ._import import JustificanteImportResult, import_filing_from_justificante
from ._review import (
    ModeloApprovalStaleReason,
    approval_stale_reasons,
    approve_draft,
    compute_current_approval_basis,
    compute_review_checksum,
    describe_stale_reason,
    refresh_review_status,
    unapprove_draft,
)
from .errors import ModeloApplicationError, ModeloCalculateError
from .runtime import (
    ModeloOperatorProfile,
    build_runtime_schema_provider,
    filing_profile_from_taxpayer,
    load_default_filing_profile,
)


def build_draft(
    *,
    modelo: str,
    period: _Period,
    profile: ModeloProfile,
    inputs: ModeloInputs,
    schema_provider: CasillaSchemaProvider,
    deadline_checker: DeadlineChecker | None = None,
    fail_on_warning: bool = False,
) -> ModeloDraft:
    """Build and validate a filing draft from a registry snapshot.

    Args:
        modelo: Stable modelo string ID.
        period: Typed filing period built from a filing year and bare registry
            token.
        profile: Taxpayer profile the draft would be built for.
        inputs: Raw filing inputs.
        schema_provider: Registry-backed casilla schema provider.
        deadline_checker: Optional deadline checker.
        fail_on_warning: Raise when validation produces any warning or error.

    Returns:
        A fully constructed and validated :class:`ModeloDraft`.

    Raises:
        ModeloBuilderError: If the registry has no matching snapshot,
            inputs are malformed, or strict validation fails.
    """
    snapshot = _load_registry_snapshot(modelo=modelo, period=period)
    filing_year, registry_period = _registry_period(period)
    snapshot_ref = _RegistrySnapshotRef(
        modelo=snapshot.modelo.id,
        revision_id=snapshot.revision.id,
        modelo_year=filing_year,
        period=registry_period,
    )
    collection = schema_provider.get_collection(modelo)
    if collection.schema_version != f"registry:{snapshot.modelo.id}:{snapshot.revision.id}":
        raise ModeloBuilderError(
            f"schema provider version {collection.schema_version!r} does not match registry snapshot "
            f"{snapshot.revision.id!r}",
        )
    casilla_ids = {casilla.id for casilla in snapshot.revision.casillas}
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}
    calculation_binding_ids = _formula_binding_ids(snapshot) | _bound_casilla_binding_ids(snapshot)
    enum_binding_ids = _enum_consumed_binding_ids(snapshot.revision)
    date_binding_ids = _date_binding_ids(snapshot)
    relation_ids = _relation_ids(snapshot)
    # Date and relation ids ride dedicated engine channels; never coerce their
    # values through the Decimal binding channel (an ISO date is not a Decimal).
    decimal_binding_ids = calculation_binding_ids - enum_binding_ids - date_binding_ids - relation_ids
    casilla_inputs = _decimal_inputs_for_ids(inputs, casilla_ids)
    binding_inputs = _decimal_inputs_for_ids(inputs, decimal_binding_ids)
    enum_binding_inputs = _string_inputs_for_ids(inputs, enum_binding_ids)
    # Date bindings (e.g. taxpayer birth_date for age_at_year_end) and period
    # relations (e.g. prior pagos fraccionados) travel on dedicated engine
    # channels, not the Decimal binding channel. They are persisted on the
    # calculation revision's ``binding_overrides`` snapshot so a verify/file
    # replay can reconstruct the identical draft without re-resolving the live
    # profile; extract them here by their registry id-sets and route them.
    date_binding_inputs = _date_inputs_for_ids(inputs, date_binding_ids)
    relation_inputs = _decimal_inputs_for_ids(inputs, relation_ids)
    filing_binding_values = _filing_binding_values(
        inputs,
        bindings,
        enum_binding_ids,
        frozenset(date_binding_ids | relation_ids),
    )
    try:
        result = _calculate_registry_snapshot(
            snapshot,
            inputs=casilla_inputs,
            date_context={"filing_period": _filing_period_date(period)},
            binding_values=binding_inputs,
            enum_binding_values=enum_binding_inputs or None,
            relation_values=relation_inputs or None,
            date_binding_values=date_binding_inputs or None,
        )
    except _RegistryValidationError as exc:
        raise ModeloBuilderError(f"registry calculation failed: {exc}") from exc
    entries = {entry.target: entry for entry in result.entries}
    schema_ids = {casilla.id for casilla in collection.all()}
    # A computed casilla's formula_trace documents the static casilla inputs its
    # formula declares (the validator checks the trace against
    # ``CasillaSchema.formula_inputs``). It must NOT be the branch-dependent
    # runtime operand set: ``if_then_else`` short-circuits, so a conditional
    # formula (e.g. M303 ``iva.prorrata-porcentaje``) emits operand_refs for only
    # the branch actually taken — a subset of the declared inputs — which the
    # formula-divergence rule then rejects, leaving the draft in BORRADOR. Read
    # the deterministic declared input set from the schema collection instead.
    formula_inputs_by_casilla = {
        schema.id: tuple(schema.formula_inputs) for schema in collection.all() if schema.formula is not None
    }
    values: list[ModeloValue] = []
    for casilla in snapshot.revision.casillas:
        if casilla.input_kind == _InputKind.COMPUTED:
            entry = entries[casilla.id]
            trace = formula_inputs_by_casilla.get(casilla.id)
            if trace is None:
                trace = tuple(ref for ref in entry.operand_refs if ref in schema_ids)
            values.append(
                ModeloValue(
                    casilla_id=casilla.id,
                    value=result.values[casilla.id],
                    kind=ModeloValueKind.COMPUTED,
                    source=f"registry formula {entry.formula_id}",
                    formula_trace=trace,
                ),
            )
            continue
        if casilla.input_kind == _InputKind.BOUND:
            value = result.values.get(casilla.id)
            if value is not None:
                values.append(
                    ModeloValue(
                        casilla_id=casilla.id,
                        value=value,
                        kind=ModeloValueKind.INHERITED,
                        source=f"registry binding {casilla.binding}",
                    ),
                )
                continue
        if casilla.id in casilla_inputs:
            values.append(
                ModeloValue(
                    casilla_id=casilla.id,
                    value=casilla_inputs[casilla.id],
                    kind=ModeloValueKind.LITERAL,
                    source="registry input",
                ),
            )
            continue
        values.append(
            ModeloValue(
                casilla_id=casilla.id,
                value=None,
                kind=ModeloValueKind.EMPTY,
                source="registry schema",
            ),
        )
    created_at = _utc_now()
    value_tuple = tuple(sorted(values, key=lambda value: value.casilla_id))
    binding_value_tuple = tuple(sorted(filing_binding_values, key=lambda value: value.binding_id))
    casilla_provenance = tuple(
        ModeloCasillaProvenance(
            casilla_id=casilla.id,
            formula_id=casilla.formula,
            legal_refs=tuple(casilla.legal_refs),
            source_refs=tuple(casilla.source_refs),
        )
        for casilla in sorted(snapshot.revision.casillas, key=lambda item: item.id)
    )
    # Propagate identity from the validated profile substrate into the
    # draft. ``profile.tax_id`` is already validated against the AEAT
    # checksum via ``SubjectTaxId`` on the profile model, so the
    # post-validation result type-checks at the ModeloDraft boundary
    # and survives every downstream encrypted-persistence roundtrip.
    draft = ModeloDraft(
        draft_id=compute_modelo_draft_id(
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
        status=ModeloDraftStatus.BORRADOR,
        values=value_tuple,
        binding_values=binding_value_tuple,
        casilla_provenance=casilla_provenance,
        created_at=created_at,
        updated_at=created_at,
        schema_version=collection.schema_version,
    )
    validator = ModeloValidator(schema_provider=schema_provider, deadline_checker=deadline_checker)
    findings = validator.validate(draft)
    if fail_on_warning and findings:
        raise ModeloBuilderError("draft validation produced findings under fail_on_warning")
    return apply_validation(draft, findings)


@lru_cache(maxsize=128)
def _load_registry_snapshot(*, modelo: str, period: _Period) -> _RegistrySnapshot:
    filing_year, registry_period = _registry_period(period)
    try:
        authority = _resources().modelos.authority
        return authority.snapshot(
            modelo,
            filing_year=filing_year,
            period=registry_period,
        )
    except _RegistrySnapshotError as exc:
        raise ModeloBuilderError(
            f"registry snapshot is not available for modelo={modelo} period={period}: {exc}",
        ) from exc


def _registry_period(period: _Period) -> tuple[int, str]:
    if not isinstance(period, _Period):
        raise ModeloBuilderError(
            "filing period must be an aeat.core.Period built from a filing year and bare registry token",
        )
    return period.filing_year, period.registry_token


def _filing_period_date(period: _Period) -> date:
    filing_year, registry_period = _registry_period(period)
    if registry_period.startswith("EXT-") and registry_period.endswith("T"):
        return _Period.from_year_and_code(filing_year, registry_period.removeprefix("EXT-")).end_date
    if period.has_date_span():
        return period.end_date
    return date(filing_year, 12, 31)


def _formula_binding_ids(snapshot: _RegistrySnapshot) -> set[str]:
    binding_ids: set[str] = set()
    for formula in snapshot.revision.formulas:
        _collect_formula_binding_ids(formula.expression, binding_ids)
    return binding_ids


def _bound_casilla_binding_ids(snapshot: _RegistrySnapshot) -> set[str]:
    return {
        casilla.binding
        for casilla in snapshot.revision.casillas
        if casilla.input_kind == _InputKind.BOUND and casilla.binding is not None
    }


def _date_binding_ids(snapshot: _RegistrySnapshot) -> set[str]:
    """Collect every date_binding id referenced by the revision's formulas.

    Date bindings (date-valued profile facts such as ``birth_date``,
    consumed by ``age_at_year_end``) travel on the engine's
    ``date_binding_values`` channel, distinct from the Decimal binding
    channel. A draft replay must supply them or the formula runtime
    refuses the calculation.
    """
    date_binding_ids: set[str] = set()
    for formula in snapshot.revision.formulas:
        date_binding_ids.update(_expression_date_binding_refs(formula.expression))
    return date_binding_ids


def _relation_ids(snapshot: _RegistrySnapshot) -> set[str]:
    """Collect the cross-model relation ids declared on the revision.

    Period relations (e.g. prior pagos fraccionados aggregated into the
    annual settlement) are supplied to the engine on the dedicated
    ``relation_values`` channel. A draft replay extracts them from the
    persisted inputs by this id-set; relations not present in the inputs
    are simply absent from the resolved relation map.
    """
    return {str(relation.id) for relation in snapshot.revision.relations}


def _date_inputs_for_ids(inputs: ModeloInputs, input_ids: set[str]) -> dict[str, date]:
    """Extract ISO-date-shaped inputs for ``input_ids`` as ``date`` values."""
    date_inputs: dict[str, date] = {}
    for binding_id, value in inputs.items():
        if binding_id not in input_ids or value is None:
            continue
        if isinstance(value, date):
            date_inputs[binding_id] = value
            continue
        if isinstance(value, str):
            try:
                parsed = _parse_iso8601_date(value)
            except ValueError as exc:
                raise ModeloBuilderError(f"date binding {binding_id!r} has a non-ISO date value {value!r}") from exc
            if parsed is None:
                raise ModeloBuilderError(f"date binding {binding_id!r} has a non-ISO date value {value!r}")
            date_inputs[binding_id] = parsed
    return date_inputs


def _collect_formula_binding_ids(expression: object, binding_ids: set[str]) -> None:
    binding = getattr(expression, "binding", None)
    if binding is not None:
        binding_ids.add(str(binding))
    for arg in getattr(expression, "args", ()):
        _collect_formula_binding_ids(arg, binding_ids)


def _decimal_inputs_for_ids(inputs: ModeloInputs, input_ids: set[str]) -> dict[str, Decimal]:
    decimal_inputs: dict[str, Decimal] = {}
    for casilla_id, value in inputs.items():
        if casilla_id not in input_ids:
            continue
        if value is None:
            continue
        decimal_inputs[casilla_id] = _decimal_input(casilla_id, value)
    return decimal_inputs


def _string_inputs_for_ids(inputs: ModeloInputs, input_ids: frozenset[str]) -> dict[str, str]:
    # Enum-channel bindings carry string values; skip None and non-string entries.
    string_inputs: dict[str, str] = {}
    for binding_id, value in inputs.items():
        if binding_id not in input_ids:
            continue
        if value is None:
            continue
        if not isinstance(value, str):
            continue
        string_inputs[binding_id] = value
    return string_inputs


def _binding_provenance(binding: object) -> tuple[_BindingSourceKind, tuple[str, ...], tuple[str, ...]]:
    """Extract the typed source kind and grounding from a binding definition.

    The ``binding`` is the registry ``DataBindingDefinition`` already held by
    the filing builder; its ``source`` is a typed
    :class:`~aeat.core.BindingSourceKind` and its ``legal_refs`` / ``source_refs``
    carry the binding's regulatory grounding. Carrying them onto every
    :class:`ModeloBindingValue` brings bound values to provenance parity with
    casillas (the casilla half already populates
    :class:`~aeat.domain.filing.ModeloCasillaProvenance`).
    """
    source = getattr(binding, "source", None)
    if not isinstance(source, _BindingSourceKind):
        raise ModeloBuilderError(
            f"registry binding {getattr(binding, 'id', binding)!r} carries a non-typed "
            f"source {source!r}; expected a BindingSourceKind member",
        )
    legal_refs = tuple(getattr(binding, "legal_refs", ()) or ())
    source_refs = tuple(getattr(binding, "source_refs", ()) or ())
    return source, legal_refs, source_refs


def _filing_binding_values(
    inputs: ModeloInputs,
    bindings: Mapping[str, object],
    enum_binding_ids: frozenset[str] = frozenset(),
    non_decimal_binding_ids: frozenset[str] = frozenset(),
) -> list[ModeloBindingValue]:
    values: list[ModeloBindingValue] = []
    for binding_id, binding in bindings.items():
        if binding_id in enum_binding_ids or binding_id in non_decimal_binding_ids:
            # Enum-channel bindings, date bindings, and period relations flow
            # through _calculate_registry_snapshot's dedicated channels
            # (enum_binding_values / date_binding_values / relation_values);
            # they carry no fichero-BOE addressing and must not be coerced to
            # Decimal here.
            continue
        if binding_id not in inputs or inputs[binding_id] is None:
            continue
        source, legal_refs, source_refs = _binding_provenance(binding)
        raw_value = inputs[binding_id]
        if isinstance(raw_value, list | tuple):
            values.extend(
                ModeloBindingValue(
                    binding_id=binding_id,
                    value=_binding_input(binding_id, row_value, binding),
                    kind=ModeloValueKind.LITERAL,
                    source=source,
                    legal_refs=legal_refs,
                    source_refs=source_refs,
                    row_index=index,
                )
                for index, row_value in enumerate(raw_value, start=1)
            )
            continue
        if isinstance(raw_value, Mapping):
            values.extend(
                ModeloBindingValue(
                    binding_id=binding_id,
                    value=_binding_input(binding_id, row_value, binding),
                    kind=ModeloValueKind.LITERAL,
                    source=source,
                    legal_refs=legal_refs,
                    source_refs=source_refs,
                    row_index=_binding_row_index(binding_id, row_key),
                )
                for row_key, row_value in raw_value.items()
            )
            continue
        values.append(
            ModeloBindingValue(
                binding_id=binding_id,
                value=_binding_input(binding_id, raw_value, binding),
                kind=ModeloValueKind.LITERAL,
                source=source,
                legal_refs=legal_refs,
                source_refs=source_refs,
            ),
        )
    return values


def _binding_row_index(binding_id: str, row_key: object) -> int:
    if isinstance(row_key, bool):
        raise ModeloBuilderError(f"binding input {binding_id!r} row key must be a positive integer")
    if isinstance(row_key, int):
        index = row_key
    elif isinstance(row_key, str):
        try:
            index = int(row_key)
        except ValueError as exc:
            raise ModeloBuilderError(f"binding input {binding_id!r} row key must be a positive integer") from exc
    else:
        raise ModeloBuilderError(f"binding input {binding_id!r} row key must be a positive integer")
    if index < 1:
        raise ModeloBuilderError(f"binding input {binding_id!r} row key must be a positive integer")
    return index


def _binding_input(binding_id: str, value: object, binding: object) -> ModeloScalar:
    selector = getattr(binding, "selector", None)
    raw_data_type = selector.get("data_type") if isinstance(selector, Mapping) else getattr(selector, "data_type", None)
    data_type = str(raw_data_type or "decimal")
    if data_type == "text":
        return str(value)
    if data_type == "integer":
        decimal_value = _decimal_input(binding_id, value)
        if decimal_value != decimal_value.to_integral_value():
            raise ModeloBuilderError(f"binding input {binding_id!r} must be an integer value")
        return int(decimal_value)
    if data_type == "boolean":
        return _boolean_input(binding_id, value)
    if data_type in {"decimal", "money"}:
        return _decimal_input(binding_id, value)
    raise ModeloBuilderError(f"binding input {binding_id!r} declares unsupported data type {data_type!r}")


def _decimal_input(input_id: str, value: object) -> Decimal:
    if isinstance(value, bool):
        raise ModeloBuilderError(f"input {input_id!r} must be a Decimal value")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | str):
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ModeloBuilderError(f"input {input_id!r} must be a Decimal value") from exc
    raise ModeloBuilderError(f"input {input_id!r} must be a Decimal value")


def _boolean_input(input_id: str, value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "s", "si", "yes"}:
            return True
        if normalized in {"0", "false", "n", "no"}:
            return False
    raise ModeloBuilderError(f"binding input {input_id!r} must be a boolean value")


def validate_draft(
    draft: ModeloDraft,
    *,
    bucket_id: str,
    schema_provider: CasillaSchemaProvider,
    deadline_checker: DeadlineChecker | None = None,
) -> ModeloDraft:
    """Re-run validation against an existing draft.

    The returned draft preserves ``draft_id`` because the hash
    excludes findings, status, ``updated_at`` and ``notes``.

    Args:
        draft: The draft to re-validate.
        bucket_id: Stable bucket identifier; forwarded to
            :func:`refresh_review_status` after validation.
        schema_provider: Resolves the casilla collection for the
            draft's modelo.
        deadline_checker: Optional deadline check Protocol implementation.

    Returns:
        A new :class:`ModeloDraft` with refreshed findings, status
        and ``updated_at``.
    """
    validator = ModeloValidator(
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
    _BaseSeverity.INFO: 0,
    _BaseSeverity.WARNING: 1,
    _BaseSeverity.ERROR: 2,
}


def iter_findings(
    draft: ModeloDraft,
    *,
    severity_at_least: str = "WARNING",
) -> Iterator[ModeloValidationFinding]:
    """Yield findings filtered by minimum severity.

    Args:
        draft: The :class:`ModeloDraft` to scan for validation findings.
        severity_at_least: Minimum severity to yield, one of
            ``"INFO"``, ``"WARNING"``, ``"ERROR"``. Defaults to
            ``"WARNING"``.

    Yields:
        Each :class:`ModeloValidationFinding` whose severity meets
        or exceeds the threshold, in declaration order.

    Raises:
        ModeloCalculateError: When ``severity_at_least`` is not a known
            severity name (``"INFO"``, ``"WARNING"``, or ``"ERROR"``).
    """
    try:
        threshold = _SEVERITY_RANK[_BaseSeverity[severity_at_least]]
    except KeyError as exc:
        raise ModeloCalculateError(f"Unknown severity {severity_at_least!r}; expected INFO, WARNING, or ERROR") from exc
    for finding in draft.findings:
        if _SEVERITY_RANK[finding.severity] >= threshold:
            yield finding


__all__ = [
    "APPROVAL_BASIS_VERSION",
    "CasillaDelta",
    "CasillaInputs",
    "DeclaracionCalculateNextAction",
    "DeclaracionCalculateSummary",
    "DeclaracionExportFormat",
    "DeclaracionExportResult",
    "DeclaracionVerifyResult",
    "DeclaracionVerifyVerdict",
    "JustificanteImportResult",
    "ModeloApplicationError",
    "ModeloApprovalStaleReason",
    "ModeloCalculateError",
    "ModeloCode",
    "ModeloHistory",
    "ModeloHistoryEntry",
    "ModeloHistoryRepository",
    "ModeloInputs",
    "ModeloOperatorProfile",
    "ModeloScalar",
    "apply_validation",
    "approval_stale_reasons",
    "approve_draft",
    "build_complementaria",
    "build_draft",
    "build_runtime_schema_provider",
    "compute_current_approval_basis",
    "compute_modelo_draft_id",
    "compute_review_checksum",
    "derive_validation_status",
    "describe_stale_reason",
    "export_draft",
    "filing_profile_from_taxpayer",
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
