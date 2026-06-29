"""Public application facade for registry-backed filing drafts.

This package builds, reviews, approves, exports, verifies, imports, and
summarises local filing artefacts. All draft creation and validation consume
a :class:`aeat.domain.calculations.registry.RegistrySnapshot` to resolve the
active modelo revision, its casilla schema, relation inputs, and formula graph.

Major entry points:

* :func:`build_draft` constructs a validated
  :class:`aeat.domain.filing.ModeloDraft` from registry-backed inputs.
* :func:`approve_draft`, :func:`unapprove_draft`, and
  :func:`refresh_review_status` manage local review state and approval basis.
* :func:`export_draft` writes a local fichero-BOE artefact, and
  :func:`verify_export` re-reads that file through the registry export parser.
* :func:`import_filing_from_justificante` reconstructs a draft-level local
  receipt baseline from a justificante PDF without treating the receipt as a
  casilla-value authority.
* :func:`build_complementaria`, :func:`list_amendments`, and
  :func:`load_amendment` build and read governed
  :class:`aeat.domain.filing.ModeloComplementaria` and
  :class:`aeat.domain.filing.ModeloSustitutiva` amendment records.
* :class:`ModeloHistoryRepository` persists encrypted lightweight
  :class:`ModeloHistory` summaries for local filing-history views.
* :func:`build_runtime_schema_provider` supplies the runtime registry view used
  by draft construction, review, export, and verification.

The facade deliberately separates local filing state from live submission.
Remote AEAT submission is not exposed here; attempted live writes are refused
by :class:`aeat.core.access_gate.LiveSubmitForbiddenError`.

Work-unit filing records for calculation revisions live in
:mod:`aeat.application.modelo` and :mod:`aeat.domain.modelos`. This package owns
draft-level construction, review, export, verification, justificante import,
local amendment construction, and lightweight local history; it does not create
:class:`aeat.domain.modelos.ModeloRecord` entries or stamp
:class:`aeat.domain.modelos.ExternalEvidence`.

See Also:
    :mod:`aeat.application.modelo`
        Operator-facing modelo facade that carries calculation revisions into
        this filing surface.
    :func:`aeat.application.modelo._filing_actions.file_modelo_revision`
        Work-unit action that records a verified calculation revision as a
        current local :class:`aeat.domain.modelos.ModeloRecord`.
    :func:`aeat.application.modelo._external_import_actions.import_external_filing_evidence`
        External-evidence import path that creates an evidenced
        :class:`aeat.domain.modelos.ModeloRecord` baseline for amendments.
    :mod:`aeat.domain.filing`
        Canonical draft records, values, provenance, validation findings, and
        review helpers.
    :mod:`aeat.domain.calculations.registry`
        Registry authority, snapshots, export layouts, and formula execution
        used by this application facade.
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
    BindingId as _BindingId,
)
from ...domain.calculations.registry import (
    CasillaId as _CasillaId,
)
from ...domain.calculations.registry import (
    InputKind as _InputKind,
)
from ...domain.calculations.registry import (
    LegalRefId as _LegalRefId,
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
    RelationId as _RelationId,
)
from ...domain.calculations.registry import (
    SourceRefId as _SourceRefId,
)
from ...domain.calculations.registry import (
    calculate_registry_snapshot as _calculate_registry_snapshot,
)
from ...domain.calculations.registry import (
    casilla_noncanonical_reference_tokens as _casilla_noncanonical_reference_tokens,
)
from ...domain.calculations.registry import (
    declared_casilla_ids as _declared_casilla_ids,
)
from ...domain.calculations.registry import (
    enum_consumed_binding_ids as _enum_consumed_binding_ids,
)
from ...domain.calculations.registry import (
    revision_date_binding_ids as _revision_date_binding_ids,
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
    export_layout_renderability_reason,
    render_layout,
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
    casilla_ids = set(_declared_casilla_ids(snapshot.revision))
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}
    calculation_binding_ids = _formula_binding_ids(snapshot) | _bound_casilla_binding_ids(snapshot)
    enum_binding_ids = _enum_consumed_binding_ids(snapshot.revision)
    date_binding_ids = _date_binding_ids(snapshot)
    relation_ids = _relation_ids(snapshot)
    # Date and relation ids ride dedicated engine channels; never coerce their
    # values through the Decimal binding channel (an ISO date is not a Decimal).
    decimal_binding_ids = calculation_binding_ids - enum_binding_ids - date_binding_ids - relation_ids
    _validate_filing_input_keys(
        inputs,
        accepted_ids=casilla_ids | set(bindings) | relation_ids,
        snapshot=snapshot,
    )
    casilla_inputs = _decimal_inputs_for_ids(inputs, casilla_ids)
    binding_inputs = _decimal_inputs_for_ids(inputs, decimal_binding_ids)
    enum_binding_inputs = _string_inputs_for_ids(inputs, enum_binding_ids)
    # Date bindings (e.g. taxpayer birth_date for age_at_year_end) and period
    # relations (e.g. prior pagos fraccionados) travel on dedicated engine
    # channels, not the Decimal binding channel. Replay callers merge the
    # calculation revision's BindingId and RelationId snapshots into this flat
    # input map; extract them here by their registry id-sets and route them.
    date_binding_inputs = _date_inputs_for_ids(inputs, date_binding_ids)
    relation_inputs = _decimal_inputs_for_ids(inputs, relation_ids)
    filing_binding_values = _filing_binding_values(
        inputs,
        bindings,
        enum_binding_ids,
        frozenset(date_binding_ids),
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
    entries = {entry.target_casilla_id: entry for entry in result.entries}
    # A computed casilla's formula_trace_casilla_ids documents the static casilla inputs its
    # formula declares (the validator checks the trace against
    # ``CasillaSchema.formula_input_casilla_ids``). It must NOT be the branch-dependent
    # runtime operand set: ``if_then_else`` short-circuits, so a conditional
    # formula (e.g. M303 ``iva.prorrata-porcentaje``) emits operand_casilla_refs
    # for only the branch actually taken — a subset of the declared inputs —
    # which the formula-divergence rule then rejects, leaving the draft in
    # BORRADOR. Read the deterministic declared input set from the schema
    # collection instead.
    formula_input_casilla_ids_by_casilla = {
        schema.casilla_id: tuple(schema.formula_input_casilla_ids)
        for schema in collection.all()
        if schema.formula is not None
    }
    values: list[ModeloValue] = []
    for casilla in snapshot.revision.casillas:
        if casilla.input_kind == _InputKind.COMPUTED:
            entry = entries[casilla.id]
            trace = formula_input_casilla_ids_by_casilla.get(casilla.id)
            if trace is None:
                trace = entry.operand_casilla_refs
            values.append(
                ModeloValue(
                    casilla_id=casilla.id,
                    value=result.values[casilla.id],
                    kind=ModeloValueKind.COMPUTED,
                    source=f"registry formula {entry.formula_id}",
                    formula_trace_casilla_ids=trace,
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


def _registry_period(period: object) -> tuple[int, str]:
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


def _formula_binding_ids(snapshot: _RegistrySnapshot) -> set[_BindingId]:
    binding_ids: set[_BindingId] = set()
    for formula in snapshot.revision.formulas:
        _collect_formula_binding_ids(formula.expression, binding_ids)
    return binding_ids


def _bound_casilla_binding_ids(snapshot: _RegistrySnapshot) -> set[_BindingId]:
    return {
        casilla.binding
        for casilla in snapshot.revision.casillas
        if casilla.input_kind == _InputKind.BOUND and casilla.binding is not None
    }


def _date_binding_ids(snapshot: _RegistrySnapshot) -> set[_BindingId]:
    """Collect every date_binding id referenced by the revision's formulas.

    Date bindings (date-valued profile facts such as ``birth_date``,
    consumed by ``age_at_year_end``) travel on the engine's
    ``date_binding_values`` channel, distinct from the Decimal binding
    channel. A draft replay must supply them or the formula runtime
    refuses the calculation. Delegates to the canonical
    :func:`revision_date_binding_ids` registry query (single source of truth).
    """
    return set(_revision_date_binding_ids(snapshot.revision))


def _relation_ids(snapshot: _RegistrySnapshot) -> set[_RelationId]:
    """Collect the cross-model relation ids declared on the revision.

    Period relations (e.g. prior pagos fraccionados aggregated into the
    annual settlement) are supplied to the engine on the dedicated
    ``relation_values`` channel. A draft replay extracts them from the
    persisted inputs by this id-set; relations not present in the inputs
    are simply absent from the resolved relation map.
    """
    return {relation.id for relation in snapshot.revision.relations}


def _validate_filing_input_keys(
    inputs: ModeloInputs,
    *,
    accepted_ids: set[_BindingId | _CasillaId | _RelationId],
    snapshot: _RegistrySnapshot,
) -> None:
    """Reject input keys that are not canonical registry input ids."""
    non_string = tuple(repr(key) for key in inputs if type(key) is not str)
    if non_string:
        raise ModeloBuilderError(
            "filing input keys must be string registry ids; "
            f"non-string keys are not accepted: {', '.join(sorted(non_string))}",
        )

    padded = tuple(key for key in inputs if key != key.strip())
    if padded:
        raise ModeloBuilderError(
            "filing input keys must be exact registry ids without leading or trailing whitespace: "
            f"{', '.join(repr(key) for key in sorted(padded))}",
        )

    noncanonical_tokens = _casilla_noncanonical_reference_tokens(snapshot.revision)
    supplied_noncanonical = tuple(key for key in inputs if key in noncanonical_tokens)
    if supplied_noncanonical:
        details = "; ".join(
            _format_noncanonical_casilla_reference(key, noncanonical_tokens[key])
            for key in sorted(supplied_noncanonical)
        )
        raise ModeloBuilderError(
            "filing input keys must use canonical casilla.id values; "
            f"non-canonical casilla reference tokens are not accepted: {details}",
        )

    unknown = tuple(key for key in inputs if key not in accepted_ids)
    if unknown:
        raise ModeloBuilderError(
            "filing input keys must be declared casilla.id, binding, or relation ids for "
            f"registry:{snapshot.modelo.id}:{snapshot.revision.id}; unknown keys: "
            f"{', '.join(repr(key) for key in sorted(unknown))}",
        )


def _format_noncanonical_casilla_reference(token: str, targets: tuple[_CasillaId, ...]) -> str:
    rendered_targets = ", ".join(targets)
    if len(targets) > 1:
        return f"{token!r} is ambiguous; candidate casilla.id values: {rendered_targets}"
    return f"{token!r} -> {rendered_targets}"


def _date_inputs_for_ids(inputs: ModeloInputs, input_ids: set[_BindingId]) -> dict[_BindingId, date]:
    """Extract ISO-date-shaped inputs for ``input_ids`` as ``date`` values."""
    date_inputs: dict[_BindingId, date] = {}
    for binding_id in input_ids:
        value = inputs.get(binding_id)
        if value is None:
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


def _collect_formula_binding_ids(expression: object, binding_ids: set[_BindingId]) -> None:
    binding = getattr(expression, "binding", None)
    if binding is not None:
        if not isinstance(binding, str):
            raise ModeloBuilderError(f"formula binding reference must be a canonical binding id string: {binding!r}")
        binding_ids.add(binding)
    for arg in getattr(expression, "args", ()):
        _collect_formula_binding_ids(arg, binding_ids)


def _decimal_inputs_for_ids[InputId: str](
    inputs: ModeloInputs,
    input_ids: set[InputId],
) -> dict[InputId, Decimal]:
    decimal_inputs: dict[InputId, Decimal] = {}
    for input_id in input_ids:
        value = inputs.get(input_id)
        if value is None:
            continue
        decimal_inputs[input_id] = _decimal_input(input_id, value)
    return decimal_inputs


def _string_inputs_for_ids(inputs: ModeloInputs, input_ids: frozenset[_BindingId]) -> dict[_BindingId, str]:
    # Enum-channel bindings carry string values; skip None and non-string entries.
    string_inputs: dict[_BindingId, str] = {}
    for binding_id in input_ids:
        value = inputs.get(binding_id)
        if value is None:
            continue
        if not isinstance(value, str):
            continue
        string_inputs[binding_id] = value
    return string_inputs


def _binding_provenance(
    binding: object,
) -> tuple[_BindingSourceKind, tuple[_LegalRefId, ...], tuple[_SourceRefId, ...]]:
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
    bindings: Mapping[_BindingId, object],
    enum_binding_ids: frozenset[_BindingId] = frozenset(),
    non_decimal_binding_ids: frozenset[_BindingId] = frozenset(),
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


def _binding_row_index(binding_id: _BindingId, row_key: object) -> int:
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


_ROW_FIELD_DATA_TYPES: dict[str, str] = {
    "base_imponible": "money",
    "rectified_base_previous": "money",
    "rectified_year": "text",
    "rectified_period": "text",
    "country_code": "text",
    "party_tax_id": "text",
    "party_legal_name": "text",
    "clave": "text",
}


def _binding_data_type(binding: object) -> str:
    selector = getattr(binding, "selector", None)
    raw_data_type = selector.get("data_type") if isinstance(selector, Mapping) else getattr(selector, "data_type", None)
    if raw_data_type is not None:
        return str(raw_data_type)
    row_field = selector.get("row_field") if isinstance(selector, Mapping) else getattr(selector, "row_field", None)
    if isinstance(row_field, str) and row_field in _ROW_FIELD_DATA_TYPES:
        return _ROW_FIELD_DATA_TYPES[row_field]
    return "decimal"


def _binding_input(binding_id: _BindingId, value: object, binding: object) -> ModeloScalar:
    data_type = _binding_data_type(binding)
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
    "export_layout_renderability_reason",
    "filing_profile_from_taxpayer",
    "import_filing_from_justificante",
    "iter_findings",
    "list_amendments",
    "load_amendment",
    "load_default_filing_profile",
    "make_amendment_id",
    "refresh_review_status",
    "render_layout",
    "summarise_calculation",
    "unapprove_draft",
    "verify_export",
]
