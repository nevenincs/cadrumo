"""Formula and parameter schema models for the registry."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from itertools import pairwise
from typing import Literal

from pydantic import Field, model_validator

from ._errors import RegistryValidationError
from ._ids import BindingId, CasillaId, ParameterId, RelationId
from ._schema_base import DateAxis, FormulaOperator, LegalRefs, RegistryModel, SourceCitation, SourceRefs
from ._schema_scalars import DecimalValue

__all__ = [
    "BracketEntry",
    "DatedValue",
    "FormulaExpression",
    "KeyedBracketEntry",
    "ParameterDefinition",
]


def _normalise_dispatch_table_entries(value: object) -> object:
    if not isinstance(value, Mapping) or "dispatch_table_entries" not in value:
        return value
    mapping = _string_keyed_mapping(value, surface="formula")
    if "dispatch_table" in mapping:
        raise RegistryValidationError("formula leaf must use dispatch_table or dispatch_table_entries, not both")

    raw_entries = mapping["dispatch_table_entries"]
    if not isinstance(raw_entries, tuple | list):
        raise RegistryValidationError("dispatch_table_entries must be an array")

    dispatch_table: dict[str, object] = {}
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, Mapping):
            raise RegistryValidationError("dispatch_table_entries entries must be tables")
        entry = _string_keyed_mapping(raw_entry, surface="dispatch_table_entries entry")
        if set(entry) != {"key", "parameter"}:
            raise RegistryValidationError("dispatch_table_entries entries must declare key and parameter")
        key = entry["key"]
        if not isinstance(key, str):
            raise RegistryValidationError("dispatch_table_entries key must be a string")
        if key in dispatch_table:
            raise RegistryValidationError(f"dispatch_table_entries duplicate key {key!r}")
        dispatch_table[key] = entry["parameter"]

    normalised = dict(mapping)
    normalised.pop("dispatch_table_entries")
    normalised["dispatch_table"] = dispatch_table
    return normalised


def _string_keyed_mapping(value: object, *, surface: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise RegistryValidationError(f"{surface} must be a table")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise RegistryValidationError(f"{surface} keys must be strings")
        result[key] = item
    return result


class FormulaExpression(RegistryModel):
    op: FormulaOperator | None = None
    args: tuple[FormulaExpression, ...] = ()
    casilla_id: CasillaId | None = None
    binding: BindingId | None = None
    date_binding: BindingId | None = None
    parameter: ParameterId | None = None
    relation: RelationId | None = None
    literal: DecimalValue | None = None
    dispatch_table: Mapping[str, ParameterId] | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalise_dispatch_table_entries(cls, value: object) -> object:
        return _normalise_dispatch_table_entries(value)

    @model_validator(mode="after")
    def _validate_expression(self) -> FormulaExpression:
        populated_leaves = [
            self.casilla_id is not None,
            self.binding is not None,
            self.date_binding is not None,
            self.parameter is not None,
            self.relation is not None,
            self.literal is not None,
            self.dispatch_table is not None,
        ]
        if self.op is None:
            if self.args:
                raise RegistryValidationError("formula leaf must not declare args")
            if sum(populated_leaves) != 1:
                raise RegistryValidationError("formula leaf must declare exactly one source")
            if self.dispatch_table is not None and not self.dispatch_table:
                raise RegistryValidationError("dispatch_table leaf must declare at least one entry")
            return self
        if sum(populated_leaves):
            raise RegistryValidationError("formula operator must not declare leaf sources")
        if not self.args:
            raise RegistryValidationError("formula operator must declare args")
        return self


class DatedValue(RegistryModel):
    value: DecimalValue
    date_axis: DateAxis
    valid_from: date
    valid_to: date | None = None

    @model_validator(mode="after")
    def _validate_window(self) -> DatedValue:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise RegistryValidationError("dated value valid_to must be on or after valid_from")
        return self


class BracketEntry(RegistryModel):
    """One row of a piecewise-linear bracket schedule (e.g. an IRPF escala).

    Each entry encodes a half-open base-amount interval ``[lower_bound, upper_bound]``
    plus the cuota previously accumulated up to ``lower_bound`` (``fixed_addition``)
    and the marginal rate applied to the slice above ``lower_bound``. A ``None``
    ``upper_bound`` declares the open-ended top bracket.

    Cuota for a base amount ``base`` resolved by `lookup_bracket`:
        cuota = fixed_addition + marginal_rate * (base - lower_bound)
    """

    lower_bound: DecimalValue
    upper_bound: DecimalValue | None = None
    fixed_addition: DecimalValue
    marginal_rate: DecimalValue
    valid_from: date
    valid_to: date | None = None

    @model_validator(mode="after")
    def _validate_bracket(self) -> BracketEntry:
        if self.upper_bound is not None and self.upper_bound < self.lower_bound:
            raise RegistryValidationError("bracket upper_bound must be on or after lower_bound")
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise RegistryValidationError("bracket valid_to must be on or after valid_from")
        if self.lower_bound < Decimal("0"):
            raise RegistryValidationError("bracket lower_bound must be non-negative")
        if self.marginal_rate < Decimal("0"):
            raise RegistryValidationError("bracket marginal_rate must be non-negative")
        return self


class KeyedBracketEntry(RegistryModel):
    """One row of a string-keyed rate-lookup table.

    Sister shape to :class:`BracketEntry` for parameters that dispatch on
    a categorical enum value rather than a piecewise-linear numeric
    interval. Each row binds a ``key`` (e.g. an IRNR ``tipo_renta`` code:
    ``general`` / ``ue_residente`` / ``ganancia_patrimonial`` /
    ``inmobiliaria``) to a ``value`` (typically a Decimal rate) within a
    ``valid_from``/``valid_to`` window. Lookup is exact-match on
    ``(key, year)`` — there is no notion of interval overlap because the
    domain is enum-discrete, not numeric-continuous.

    First consumer: M210 IRNR ``m210-tipo-gravamen-2025``.
    """

    key: str = Field(min_length=1, max_length=64)
    value: DecimalValue
    valid_from: date
    valid_to: date | None = None

    @model_validator(mode="after")
    def _validate_keyed_bracket(self) -> KeyedBracketEntry:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise RegistryValidationError("keyed_bracket valid_to must be on or after valid_from")
        return self


def _brackets_overlap_in_same_window(prev: BracketEntry, current: BracketEntry) -> bool:
    """Return True when two adjacent brackets share a valid_from window and overlap.

    The pre-sorted iteration walks ``(valid_from, lower_bound)``
    order so two brackets only need to be compared when they share
    the ``valid_from`` key. Overlap is defined against a closed-
    open interval: ``prev.upper_bound`` is exclusive, so
    ``current.lower_bound`` reaching strictly below it is the
    violation. A ``prev.upper_bound`` of ``None`` (open-ended)
    short-circuits to "no overlap" — the open right edge is the
    caller's escape hatch.
    """
    if prev.valid_from != current.valid_from:
        return False
    if prev.upper_bound is None:
        return False
    return current.lower_bound < prev.upper_bound


def _brackets_overlap_across_windows(first: BracketEntry, second: BracketEntry) -> bool:
    """Return True when two differently-dated brackets are both live and collide.

    ``_brackets_overlap_in_same_window`` only compares rows sharing a
    ``valid_from``, so two rows declared in different windows could cover the
    same numeric interval on a date both windows contain. ``resolve_bracket``
    gathers every date-valid row, sorts by ``lower_bound`` alone, and returns the
    first base match, so declaration order -- not the registry -- decided the
    fixed addition and the tax result.

    Overlap requires both axes to collide: the validity windows must share at
    least one date, and the numeric intervals must intersect. Rows for
    consecutive filing years reuse the same tranches by design and stay legal
    because their windows are disjoint. ``None`` is unbounded on both axes.
    """
    if first.valid_from == second.valid_from:
        return False
    if first.valid_to is not None and first.valid_to < second.valid_from:
        return False
    if second.valid_to is not None and second.valid_to < first.valid_from:
        return False
    if first.upper_bound is not None and second.lower_bound >= first.upper_bound:
        return False
    return not (second.upper_bound is not None and first.lower_bound >= second.upper_bound)


class ParameterDefinition(RegistryModel):
    id: ParameterId
    data_type: Literal[
        "decimal",
        "money",
        "integer",
        "ratio",
        "text",
        "boolean",
        "bracket_table",
        "keyed_bracket_table",
    ]
    unit: str
    values: tuple[DatedValue, ...] = Field(default_factory=tuple)
    brackets: tuple[BracketEntry, ...] = Field(default_factory=tuple)
    keyed_brackets: tuple[KeyedBracketEntry, ...] = Field(default_factory=tuple)
    bracket_axis: DateAxis | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs
    source_citations: tuple[SourceCitation, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_bracket_table(self) -> ParameterDefinition:
        if self.data_type == "bracket_table":
            self._validate_bracket_table_shape()
        elif self.data_type == "keyed_bracket_table":
            self._validate_keyed_bracket_table_shape()
        else:
            self._validate_non_bracket_table_shape()
        return self

    def _validate_bracket_table_shape(self) -> None:
        """Verify a bracket_table parameter has brackets, no values, an axis, and no overlaps.

        Four contracts:
        * non-empty ``brackets`` tuple
        * no ``values`` (dated scalar map is mutually exclusive)
        * ``bracket_axis`` declared
        * no two brackets sharing the same ``valid_from`` window
          overlap on their ``lower_bound`` / ``upper_bound``
          interval (closed-open)
        """
        if not self.brackets:
            raise RegistryValidationError(f"parameter {self.id!r} declares bracket_table but has no brackets")
        if self.values:
            raise RegistryValidationError(f"parameter {self.id!r} cannot mix bracket_table and dated values")
        if self.keyed_brackets:
            raise RegistryValidationError(f"parameter {self.id!r} cannot mix bracket_table and keyed_brackets")
        if self.bracket_axis is None:
            raise RegistryValidationError(f"parameter {self.id!r} bracket_table requires a bracket_axis")
        sorted_brackets = sorted(self.brackets, key=lambda b: (b.valid_from, b.lower_bound))
        for prev, current in pairwise(sorted_brackets):
            if _brackets_overlap_in_same_window(prev, current):
                raise RegistryValidationError(
                    f"parameter {self.id!r} brackets {prev.lower_bound}-{prev.upper_bound} "
                    f"and {current.lower_bound}-{current.upper_bound} overlap within the same window",
                )
        for index, first in enumerate(sorted_brackets):
            for second in sorted_brackets[index + 1 :]:
                if _brackets_overlap_across_windows(first, second):
                    raise RegistryValidationError(
                        f"parameter {self.id!r} brackets {first.lower_bound}-{first.upper_bound} "
                        f"(valid from {first.valid_from.isoformat()}) and "
                        f"{second.lower_bound}-{second.upper_bound} "
                        f"(valid from {second.valid_from.isoformat()}) have overlapping validity "
                        f"windows and overlapping bounds, so bracket resolution would depend on "
                        f"declaration order",
                    )

    def _validate_keyed_bracket_table_shape(self) -> None:
        """Verify a keyed_bracket_table parameter has a valid keyed shape.

        Four contracts mirror the numeric ``bracket_table`` shape:
        * non-empty ``keyed_brackets`` tuple
        * no ``values`` (dated scalar map is mutually exclusive)
        * no ``brackets`` (numeric-interval table is mutually exclusive)
        * no two ``keyed_brackets`` share the same ``(key, valid_from)``
          pair (exact-match lookup requires a unique row per key per
          window; duplicates would make the lookup non-deterministic)
        """
        if not self.keyed_brackets:
            raise RegistryValidationError(
                f"parameter {self.id!r} declares keyed_bracket_table but has no keyed_brackets",
            )
        if self.values:
            raise RegistryValidationError(f"parameter {self.id!r} cannot mix keyed_bracket_table and dated values")
        if self.brackets:
            raise RegistryValidationError(f"parameter {self.id!r} cannot mix keyed_bracket_table and numeric brackets")
        seen: set[tuple[str, date]] = set()
        for row in self.keyed_brackets:
            pair = (row.key, row.valid_from)
            if pair in seen:
                raise RegistryValidationError(
                    f"parameter {self.id!r} keyed_brackets contains duplicate (key, valid_from) pair {pair!r}",
                )
            seen.add(pair)

    def _validate_non_bracket_table_shape(self) -> None:
        """Reject brackets / keyed_brackets / bracket_axis on a non-bracket-table parameter."""
        if self.brackets:
            raise RegistryValidationError(
                f"parameter {self.id!r} declares brackets but data_type is {self.data_type!r}; use 'bracket_table'",
            )
        if self.keyed_brackets:
            raise RegistryValidationError(
                f"parameter {self.id!r} declares keyed_brackets but data_type is {self.data_type!r}; "
                "use 'keyed_bracket_table'",
            )
        if self.bracket_axis is not None:
            raise RegistryValidationError(f"parameter {self.id!r} declares bracket_axis but is not a bracket_table")
