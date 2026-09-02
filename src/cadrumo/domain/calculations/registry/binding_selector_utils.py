"""Shared selector normalization and field-validator helpers for registry bindings."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, Field, model_validator

from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from .binding_aggregation import binding_aggregation_op
from .errors import RegistryValidationError
from .manual_input_selector import ManualInputSelector
from .schema import DataBindingDefinition, ModeloRevision
from .schema_exports import ExportFieldDataType, OneBasedExportOffset

__all__ = [
    "M347_OPERATION_CLAVES",
    "M349_OPERATION_CLAVES",
    "BindingExportDataType",
    "BindingExportSelector",
    "BindingFixedExportSelector",
    "BindingRowExportSelector",
    "BindingRowSetSelector",
    "BooleanBindingEncodedValue",
    "ManualInputRecordFieldSelector",
    "binding_export_selector",
    "binding_row_set_selector",
    "boolean_binding_encoded_values",
    "canonical_selector_key_hint",
    "intracommunity_clave_validator",
    "invariant_diagnostics",
    "manual_input_record_field_selector",
    "operation_clave_validator",
    "selector_against_model",
    "selector_as_dict",
    "unique_tuple",
    "uppercase_alpha_code",
    "validate_rectification_fields",
]


BindingExportDataType = ExportFieldDataType
"""Alias of :data:`~._schema_exports.ExportFieldDataType`, the canonical declaration.

A binding's export-facing ``data_type`` is the same six-member wire vocabulary
an :class:`~._schema_exports.ExportFieldDefinition` declares -- kept as a
separate name here because binding selector models predate the export schema
consolidation and callers already import ``BindingExportDataType``, not
because it is a distinct vocabulary.
"""


class BindingFixedExportSelector(BaseModel):
    """Typed fixed-width export projection carried by a binding selector."""

    model_config = STRICT_FROZEN_CONFIG

    record: str = Field(min_length=1, max_length=64)
    offset: OneBasedExportOffset
    length: int = Field(ge=1)
    data_type: BindingExportDataType
    decimals: int | None = Field(default=None, ge=0)
    field: str | None = Field(default=None, min_length=1, max_length=128)
    #: Whether the wire slot carries AEAT's sign marker in its first position.
    #:
    #: AEAT types a numeric design row ``N`` (numérico CON signo) or ``Num``
    #: (sin signo), and an ``N`` row reserves position 1 for the marker: ``N``
    #: for a negative value, a space otherwise. The two renderings differ for
    #: EVERY value, not only negatives -- a 17-byte signed slot emits a space
    #: plus 16 magnitude digits where an unsigned one emits 17 digits -- so a
    #: binding projecting into an ``N`` row must declare this or the slot is
    #: malformed on the wire and refuses outright on a negative.
    signed: bool = False

    @model_validator(mode="after")
    def _require_declared_scale(self) -> BindingFixedExportSelector:
        if self.data_type == "decimal" and self.decimals is None:
            raise RegistryValidationError(
                f"decimal binding export projection into record {self.record!r} must declare decimals",
            )
        if self.data_type != "decimal" and self.decimals is not None:
            raise RegistryValidationError(
                f"binding export projection into record {self.record!r} declares decimals "
                f"but its data_type is {str(self.data_type)!r}",
            )
        if self.signed:
            # Mirrors _fixed_width_codec._validate_signed_shape: the sign marker
            # is a real byte taken out of the magnitude, so a slot that cannot
            # spare one, or whose type has no sign to carry, cannot declare it.
            if self.data_type != "money":
                raise RegistryValidationError(
                    f"binding export projection into record {self.record!r} can declare signed "
                    f"only for money data, not {str(self.data_type)!r}",
                )
            if self.length < 2:
                raise RegistryValidationError(
                    f"signed binding export projection into record {self.record!r} requires at least two bytes",
                )
        return self


class BindingRowExportSelector(BaseModel):
    """Typed row-field export projection carried by a binding selector.

    ``data_type`` carries the same fact here as on
    :class:`BindingFixedExportSelector`: the scalar type of the value this
    binding contributes to the export. The two projections differ only in how
    the value is POSITIONED -- a fixed projection names an absolute
    ``offset``/``length``, a row projection takes its position from the repeated
    record's row layout -- so the type belongs on both and means one thing.

    Optional because the declaration is being adopted per family; absent leaves
    the consumer on whatever it used before.
    """

    model_config = STRICT_FROZEN_CONFIG

    record: str = Field(min_length=1, max_length=64)
    row_field: str = Field(min_length=1, max_length=128)
    data_type: BindingExportDataType | None = None


BindingExportSelector = BindingFixedExportSelector | BindingRowExportSelector


class BindingRowSetSelector(BaseModel):
    """Typed row-set projection carried by a row-producing binding selector."""

    model_config = STRICT_FROZEN_CONFIG

    fact: Literal["row_field"] = "row_field"
    row_field: str = Field(min_length=1, max_length=128)
    grouping: str = Field(min_length=1, max_length=64)
    record: str | None = Field(default=None, min_length=1, max_length=64)


class _BindingExportProjection(BaseModel):
    """Projection model for export-specific keys embedded in source-family selectors."""

    model_config = STRICT_FROZEN_CONFIG

    record: str | None = Field(default=None, min_length=1, max_length=64)
    row_field: str | None = Field(default=None, min_length=1, max_length=128)
    offset: OneBasedExportOffset | None = None
    length: int | None = Field(default=None, ge=1)
    data_type: BindingExportDataType | None = None
    decimals: int | None = Field(default=None, ge=0)
    field: str | None = Field(default=None, min_length=1, max_length=128)
    signed: bool | None = None

    def export_selector(self, *, binding_id: str) -> BindingExportSelector | None:
        """Return the typed export selector, or ``None`` for non-export selectors.

        Which projection a binding declares is decided by its POSITION keys,
        which are declared data: ``row_field`` names a slot in a repeated
        record's row layout, ``offset``/``length`` name an absolute span. The
        discrimination never consults a name pattern or the binding's source
        family, so a family that starts carrying row-field exports needs no
        change here.

        ``data_type`` is deliberately NOT a discriminator. It is the scalar type
        of the contributed value and is meaningful to both projections; treating
        it as a fixed-projection marker is what made a row field declaring its
        own type read as a malformed fixed field.
        """
        if self.record is None:
            if self.offset is not None or self.length is not None:
                raise RegistryValidationError(
                    f"binding {binding_id!r} export selector projection must declare record with offset or length",
                )
            return None

        if self.row_field is not None:
            if self.offset is not None or self.length is not None:
                raise RegistryValidationError(
                    f"binding {binding_id!r} export selector projection cannot declare row_field "
                    "with offset/length: a row field is positioned by the record's row layout, "
                    "not by an absolute span",
                )
            if self.decimals is not None and self.data_type != "decimal":
                raise RegistryValidationError(
                    f"binding {binding_id!r} row export projection declares decimals "
                    f"but its data_type is {str(self.data_type)!r}",
                )
            if self.signed is not None:
                raise RegistryValidationError(
                    f"binding {binding_id!r} row export projection cannot declare signed: a row "
                    "field takes its wire shape from the repeated record's row layout",
                )
            return BindingRowExportSelector(
                record=self.record,
                row_field=self.row_field,
                data_type=self.data_type,
            )

        offset = self.offset
        length = self.length
        data_type = self.data_type
        fixed_values = (offset, length, data_type)
        fixed_count = sum(value is not None for value in fixed_values)
        if offset is not None and length is not None and data_type is not None:
            return BindingFixedExportSelector(
                record=self.record,
                offset=offset,
                length=length,
                data_type=data_type,
                decimals=self.decimals,
                field=self.field,
                signed=bool(self.signed),
            )
        if fixed_count:
            missing = [
                key
                for key, value in (
                    ("offset", self.offset),
                    ("length", self.length),
                    ("data_type", self.data_type),
                )
                if value is None
            ]
            raise RegistryValidationError(
                f"binding {binding_id!r} export selector projection is missing fixed-field keys {missing!r}",
            )
        raise RegistryValidationError(
            f"binding {binding_id!r} export selector projection must declare row_field or offset/length/data_type",
        )


class _BindingRowSetProjection(BaseModel):
    """Projection model for row-set keys embedded in source-family selectors."""

    model_config = STRICT_FROZEN_CONFIG

    fact: str | None = Field(default=None, min_length=1, max_length=64)
    row_field: str | None = Field(default=None, min_length=1, max_length=128)
    grouping: str | None = Field(default=None, min_length=1, max_length=64)
    record: str | None = Field(default=None, min_length=1, max_length=64)

    def row_set_selector(self, *, binding_id: str) -> BindingRowSetSelector | None:
        """Return the typed :class:`BindingRowSetSelector`, or ``None`` for non-row selectors."""
        has_row_set_key = self.row_field is not None or self.grouping is not None
        if self.fact is None:
            if self.grouping is not None:
                raise RegistryValidationError(
                    f"binding {binding_id!r} row-set selector projection must declare fact 'row_field' with grouping",
                )
            return None
        if self.fact != "row_field":
            if has_row_set_key:
                raise RegistryValidationError(
                    f"binding {binding_id!r} row-set selector projection declares row-set keys "
                    f"with non-row fact {self.fact!r}",
                )
            return None
        if self.row_field is None:
            raise RegistryValidationError(
                f"binding {binding_id!r} row-set selector projection is missing row_field",
            )
        if self.grouping is None:
            raise RegistryValidationError(
                f"binding {binding_id!r} row-set selector projection is missing grouping",
            )
        return BindingRowSetSelector(row_field=self.row_field, grouping=self.grouping, record=self.record)


def selector_as_dict(binding: DataBindingDefinition) -> dict[str, object]:
    """Return a plain selector mapping without injected source metadata."""
    selector = binding.selector
    if isinstance(selector, BaseModel):
        return STR_KEYED_MAPPING_ADAPTER.validate_python(
            selector.model_dump(exclude={"source"}, exclude_none=True, exclude_unset=True),
        )
    return {key: value for key, value in selector.items() if key != "source"}


class BooleanBindingEncodedValue(BaseModel):
    """One accepted decimal encoding of a boolean-casilla ``manual_input`` binding.

    A ``manual_input`` binding whose selector declares ``data_type = "boolean"``
    (the Modelo 100 estimación-directa modality flag is the canonical case) is
    consumed by the registry formulas as a numeric ``1`` / ``0`` operand. The
    operator therefore supplies a decimal on the ``--binding`` channel, yet the
    accepted values and their meaning are opaque from the raw
    :class:`DataBindingDefinition`. This record makes one accepted value
    explicit: ``encoded_value`` is the decimal the operator types,
    ``boolean_meaning`` is the affirmative/negative sense it carries, and
    ``registry_value`` is the underlying casilla token the boolean maps to (the
    selector's declared ``true_value`` / ``false_value``).
    """

    model_config = STRICT_FROZEN_CONFIG

    encoded_value: str
    boolean_meaning: bool
    registry_value: str


def boolean_binding_encoded_values(
    binding: DataBindingDefinition,
) -> tuple[BooleanBindingEncodedValue, ...]:
    """Return the decimal encoding of a boolean-casilla ``manual_input`` binding.

    The result is empty for every binding that is not a boolean-casilla
    ``manual_input`` selector, so a caller can read a non-empty result as "this
    binding is a decimal-encoded boolean flag". The encoding follows the
    registry convention that a boolean operand is consumed as ``1`` (true) /
    ``0`` (false); each sense is paired with the selector's declared
    ``true_value`` / ``false_value`` casilla token, so the mapping is derived
    from the binding definition, never hardcoded per modelo.

    Returns:
        Zero or two :class:`BooleanBindingEncodedValue` rows.

    Raises:
        RegistryValidationError: When ``binding`` is a ``manual_input`` binding
            whose selector does not validate against :class:`ManualInputSelector`
            -- a malformed selector must be a named failure, not a silently
            empty "not a boolean binding" result.
    """
    if binding.source is not BindingSourceKind.MANUAL_INPUT:
        return ()
    # Read through the declared model rather than raw dict keys: a
    # renamed/misspelled ``true_value`` / ``false_value`` / ``data_type`` key
    # must raise, not silently return "not a boolean binding".
    try:
        selector = ManualInputSelector.model_validate(selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed manual_input selector: {exc}",
        ) from exc
    if selector.data_type != "boolean":
        return ()
    true_value = selector.true_value
    false_value = selector.false_value
    if not isinstance(true_value, str) or not isinstance(false_value, str):
        return ()
    return (
        BooleanBindingEncodedValue(encoded_value="1", boolean_meaning=True, registry_value=true_value),
        BooleanBindingEncodedValue(encoded_value="0", boolean_meaning=False, registry_value=false_value),
    )


class ManualInputRecordFieldSelector(BaseModel):
    """The record-field shape of a validated ``manual_input`` binding selector.

    :class:`ManualInputSelector` models both the casilla shape and the
    record-field shape on one class because the two are mutually exclusive
    and share ``data_type``; this narrower model is what a caller that only
    cares about the record-field shape (a fichero-BOE fixed-record
    projection) actually wants, with ``record``/``field``/``offset``/``length``
    as the non-optional fields the source model's own validator already
    guarantees once ``record`` is not ``None``.
    """

    model_config = STRICT_FROZEN_CONFIG

    record: str
    field: str
    offset: int
    length: int
    decimals: int | None = None


def manual_input_record_field_selector(
    binding: DataBindingDefinition,
) -> ManualInputRecordFieldSelector | None:
    """Return the record-field selector of a ``manual_input`` binding, or ``None``.

    ``None`` covers two DIFFERENT, both legitimate, cases a caller does not
    need to distinguish: ``binding`` is not a ``manual_input`` binding at all,
    or it is a ``manual_input`` binding using the CASILLA shape (the operator
    types a value straight into a registry casilla, with no record/field
    position at all) rather than the record-field shape this accessor
    projects. Neither is a defect; a caller collecting record-field
    projections across a revision's bindings is meant to skip both.

    Returns:
        The typed :class:`ManualInputRecordFieldSelector`, or ``None`` when
        ``binding`` does not declare a record-field ``manual_input`` selector.

    Raises:
        RegistryValidationError: When ``binding`` is a ``manual_input`` binding
            whose selector does not validate against ``ManualInputSelector``
            -- a malformed selector must be a named failure, not silently read
            as "not a record-field binding".
    """
    if binding.source is not BindingSourceKind.MANUAL_INPUT:
        return None
    # Read through the declared model rather than raw dict keys: a
    # renamed/misspelled ``record`` / ``field`` key must raise, not silently
    # read as "not a record-field binding".
    try:
        selector = ManualInputSelector.model_validate(selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed manual_input selector: {exc}",
        ) from exc
    if selector.record is None:
        return None
    # ManualInputSelector._validate_manual_input_shape already proved that a
    # non-None record implies field/offset/length are all non-None too -- the
    # record-field shape's four keys are required together.
    field = selector.field
    offset = selector.offset
    length = selector.length
    if field is None or offset is None or length is None:
        raise RegistryValidationError(
            f"binding {binding.id!r} manual_input selector names a record without its "
            "field, offset and length; the record-field shape requires all four keys together",
        )
    return ManualInputRecordFieldSelector(
        record=selector.record,
        field=field,
        offset=offset,
        length=length,
        decimals=selector.decimals,
    )


def _fields_owned_by(model_cls: type[BaseModel], raw: Mapping[str, object]) -> dict[str, object]:
    """Return the subset of ``raw`` whose keys ``model_cls`` itself declares.

    A binding's full selector dict carries every key its OWN source family
    declares -- export-selector keys, row-set keys, and family-specific keys
    (IVA categories, retenciones schemes, whatever the binding's actual family
    is) all live in the same table. A narrow projection like
    ``_BindingExportProjection`` only knows about its own slice, so filtering
    caller-side before validation is what lets it declare ``extra="forbid"``
    without narrowing what any binding's OWN family may declare alongside it.

    Derived from ``model_cls.model_fields`` rather than a hand-listed key
    tuple: a hand-listed set stops matching silently the moment a field is
    added to the projection, which is exactly the drift class this campaign
    exists to remove.
    """
    known = model_cls.model_fields.keys()
    return {key: value for key, value in raw.items() if key in known}


def binding_export_selector(
    binding: DataBindingDefinition,
    *,
    revision: ModeloRevision,
) -> BindingExportSelector | None:
    """Return the typed export projection embedded in ``binding.selector``.

    Binding source-family selectors remain authoritative for business facts.
    Export record resolution only needs the official record-coordinate
    projection; this helper parses that projection once into a typed fixed-field
    or row-field selector instead of letting callers probe the raw selector map.

    A binding is only export-eligible when its OWN revision declares at least
    one export layout; several unrelated source families (invoice,
    previous_filing) reuse the field name ``record`` for their own, different
    concepts, so calling this on a binding belonging to a layout-less revision
    would misread a foreign field as an incomplete export claim. Every current
    caller already checks ``revision.export_layouts`` before calling; this is
    the same precondition enforced here too, so a future caller that forgets it
    fails with a named cause instead of a misattributed completeness error.

    Raises:
        RegistryValidationError: When ``revision`` declares no export layouts
            at all, or when the export projection ``binding`` declares is
            malformed or incomplete.
    """
    if not revision.export_layouts:
        raise RegistryValidationError(
            f"binding {binding.id!r} is not export-eligible: its revision {revision.id!r} declares no export layout",
        )
    try:
        projection = _BindingExportProjection.model_validate(
            _fields_owned_by(_BindingExportProjection, selector_as_dict(binding)),
        )
    except ValueError as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed export selector projection: {exc}",
        ) from exc
    return projection.export_selector(binding_id=binding.id)


def binding_row_set_selector(binding: DataBindingDefinition) -> BindingRowSetSelector | None:
    """Return the typed row-set projection embedded in ``binding.selector``.

    Source-family selectors remain the authority for fact-specific filters.
    Row-set consumers only need the common ``fact = "row_field"`` projection
    that names the detail grouping and the emitted row field, so callers parse
    that projection once instead of probing the raw selector map.

    Only a ``BindingAggregationOp.ROWS`` binding is row-set-eligible; several
    unrelated source families (invoice, previous_filing) reuse the field names
    ``record`` / ``grouping`` / ``fact`` for their own, different concepts, so
    calling this on a non-``ROWS`` binding would misread a foreign field as an
    incomplete row-set claim. Every current caller already checks the
    aggregation op before calling; this is the same precondition enforced here
    too, so a future caller that forgets it fails with a named cause instead of
    a misattributed completeness error.

    Returns:
        The parsed :class:`BindingRowSetSelector`, or ``None`` when the binding
        selector does not declare a row-set projection.

    Raises:
        RegistryValidationError: When ``binding`` is not row-set-eligible (its
            resolved aggregation op is not ``rows``), or when the row-set
            projection it declares is malformed or incomplete.
    """
    op = binding_aggregation_op(binding)
    if op != BindingAggregationOp.ROWS:
        raise RegistryValidationError(
            f"binding {binding.id!r} is not row-set-eligible: aggregation op is {op.value!r}, "
            f"not {BindingAggregationOp.ROWS.value!r}",
        )
    try:
        projection = _BindingRowSetProjection.model_validate(
            _fields_owned_by(_BindingRowSetProjection, selector_as_dict(binding)),
        )
    except ValueError as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed row-set selector projection: {exc}",
        ) from exc
    return projection.row_set_selector(binding_id=binding.id)


def selector_against_model(
    binding: DataBindingDefinition,
    selector_model: type[BaseModel],
) -> list[str]:
    """Validate ``binding.selector`` against ``selector_model``, accumulating diagnostics.

    Projects the selector through :func:`selector_as_dict` (the same normalised
    mapping the resolve-time helpers see, so the build gate is never stricter
    than runtime), validates against the strict pydantic model, and returns the
    underlying field message verbatim in a diagnostic naming the binding id, its
    source, and the violated model. The underlying pydantic error is preserved
    rather than flattened to a generic "malformed selector", matching the shape
    the counterpart/withholding build-time lift already emits.

    Returns an empty list when the selector validates.
    """
    selector = selector_as_dict(binding)
    try:
        selector_model.model_validate(selector)
    except ValueError as exc:
        hint = canonical_selector_key_hint(selector, selector_model)
        return [
            f"binding {binding.id!r} (source={binding.source!r}) selector violates {selector_model.__name__}: "
            f"{exc}{hint}",
        ]
    return []


def canonical_selector_key_hint(selector: Mapping[str, object], selector_model: type[BaseModel]) -> str:
    """Return a canonical-key correction for a known legacy selector spelling."""
    if "source_casillas" in selector and "source_casilla_ids" in selector_model.model_fields:
        return "; use source_casilla_ids, not source_casillas"
    if "source_output" in selector and "source_casilla_id" in selector_model.model_fields:
        return "; use source_casilla_id, not source_output"
    if "target_casilla" in selector and "target_casilla_id" in selector_model.model_fields:
        return "; use target_casilla_id, not target_casilla"
    return ""


def invariant_diagnostics(
    binding: DataBindingDefinition,
    label: str,
    check: Callable[[DataBindingDefinition], object],
) -> list[str]:
    """Run a raise-style op/fact invariant ``check`` and collect its diagnostic.

    The detail-record, previous-filing, counterpart, withholding, invoice, and
    ledger families enforce their op/fact cross-invariants by raising
    :class:`RegistryValidationError`. This adapter runs the raising ``check`` and
    converts the raised message into one accumulating diagnostic string naming
    the binding id, its source, and the ``label`` family, preserving the
    underlying field message. Returns an empty list when the invariant holds.
    """
    try:
        check(binding)
    except RegistryValidationError as exc:
        return [f"binding {binding.id!r} (source={binding.source!r}) {label} invariants violated: {exc}"]
    return []


def uppercase_alpha_code(field_label: str) -> Callable[[type, str], str]:
    """Build a field validator that rejects a non-uppercase-alphabetic code.

    Shared by the binding observation models whose ISO country / member-state /
    currency codes must be uppercase alphabetic; ``field_label`` names the field
    in the raised :class:`RegistryValidationError`.
    """

    def _validate(cls: type, value: str) -> str:
        if value != value.upper() or not value.isalpha():
            raise RegistryValidationError(f"{field_label} must be uppercase alphabetic")
        return value

    return _validate


def optional_uppercase_alpha_code(field_label: str) -> Callable[[type, str | None], str | None]:
    """Build the nullable counterpart of :func:`uppercase_alpha_code`.

    Delegates to that validator for anything present, so what "uppercase
    alphabetic" MEANS keeps one home and this adds only the nullability axis.
    A separate builder rather than a flag on the shared one, because most of
    the fields it guards are genuinely required and loosening it for them would
    make an absent code representable where nothing should represent one.
    """
    validate_present = uppercase_alpha_code(field_label)

    def _validate(cls: type, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_present(cls, value)

    return _validate


M349_OPERATION_CLAVES: frozenset[str] = frozenset({"E", "M", "H", "A", "T", "S", "I", "R", "D", "C"})
#: Modelo 347's OWN clave de operacion vocabulary (RD 1065/2007 arts. 31/33,
#: RD 1619/2012 disposicion adicional cuarta), disjoint from M349's
#: intracommunity clave set above -- the letter A means a different thing in
#: each. Confirmed against every bundled M347 diseno de registro (2008-2009,
#: 2010, 2011, 2025-y-siguientes): none declares an "H" or "I" clave.
M347_OPERATION_CLAVES: frozenset[str] = frozenset({"A", "B", "C", "D", "E", "F", "G"})


def intracommunity_clave_validator() -> Callable[[type, str | None], str | None]:
    """Build the shared ``intracommunity_clave`` field validator.

    Both :class:`InvoiceObservation` and :class:`CounterpartAggregationObservation`
    carried a byte-identical ``intracommunity_clave`` field validator: a clave is
    optional, must be uppercase, and must be one of the closed AEAT clave de
    operación set. The single factory replaces both copies.
    """
    return operation_clave_validator(field_label="intracommunity_clave", claves=M349_OPERATION_CLAVES)


def operation_clave_validator(
    *,
    field_label: str,
    claves: frozenset[str],
) -> Callable[[type, str | None], str | None]:
    """Build an optional, uppercase, closed-set clave-de-operacion field validator.

    Generalises :func:`intracommunity_clave_validator` to any closed clave
    vocabulary -- a modelo's clave letters mean nothing outside their own
    modelo's set, so the closed set is a parameter, never a hand-listed
    literal at the call site.
    """

    def _validate(cls: type, value: str | None) -> str | None:
        if value is None:
            return None
        if value != value.upper():
            raise RegistryValidationError(f"{field_label} must be uppercase")
        if value not in claves:
            raise RegistryValidationError(f"{field_label} {value!r} is not an AEAT clave de operacion")
        return value

    return _validate


class _RectifiableObservation(Protocol):
    is_rectification: bool
    rectified_year: int | None
    rectified_period: str | None
    rectified_base_previous: Decimal | None


def validate_rectification_fields(observation: _RectifiableObservation) -> None:
    """Enforce the rectification-field coupling shared by the invoice families.

    A rectification observation must declare ``rectified_year``,
    ``rectified_period`` and ``rectified_base_previous``; a non-rectification
    observation must declare none of them. :class:`InvoiceObservation` and
    :class:`CounterpartAggregationObservation` carried a byte-identical
    ``_validate_rectification`` model validator; this one shared check replaces
    both, raising :class:`RegistryValidationError` on a violation.
    """
    if observation.is_rectification:
        if observation.rectified_year is None or observation.rectified_period is None:
            raise RegistryValidationError(
                "rectification observation must declare rectified_year and rectified_period",
            )
        if observation.rectified_base_previous is None:
            raise RegistryValidationError("rectification observation must declare rectified_base_previous")
        return
    if observation.rectified_year is not None or observation.rectified_period is not None:
        raise RegistryValidationError("non-rectification observation must not declare rectified_year/period")
    if observation.rectified_base_previous is not None:
        raise RegistryValidationError("non-rectification observation must not declare rectified_base_previous")


def unique_tuple(label: str) -> Callable[[type, tuple[str, ...]], tuple[str, ...]]:
    """Build a field validator that rejects duplicate entries in a tuple field.

    Shared by the binding requirement models; ``label`` names the offending
    tuple in the raised :class:`RegistryValidationError` (``"<label> entries
    must be unique"``).
    """

    def _validate(cls: type, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError(f"{label} entries must be unique")
        return value

    return _validate
