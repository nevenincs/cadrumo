"""The leaf facts of an activity-asset model, and how a reader words each one.

A frontend shows a fact as text, a number, a date, a flag, a share, a table
class or a token of a closed enum.  The kind of each leaf comes from the
model's own annotations, so a field added to a model is classified by its type
and a type no reader can word is refused rather than shown raw.
"""

from __future__ import annotations

import types
import typing
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel
from pydantic.fields import FieldInfo

SEQUENCE_STEP = "[]"
"""The suffix of a path step that stands for any one row of a repeated fact."""


class FactKind(StrEnum):
    """How a fact is stated and shown."""

    TEXT = "text"
    DATE = "date"
    WHOLE = "whole"
    FLAG = "flag"
    CHOICE = "choice"
    CLASS = "class"
    AMOUNT = "amount"
    SHARE = "share"
    DECIMAL = "decimal"
    ROWS = "rows"


Amount = typing.Annotated[Decimal, FactKind.AMOUNT]
"""A money amount in euros."""

Share = typing.Annotated[Decimal, FactKind.SHARE]
"""A fraction of a whole, stated as a share between zero and one."""

ClassKey = typing.Annotated[str, FactKind.CLASS]
"""A key of the amortization table's classes, worded by the table's own name for it."""


@dataclass(frozen=True, slots=True)
class FactLeaf:
    """One leaf fact of a model.

    ``path`` names the field from the model's root; a step that passes through a
    repeated fact ends in ``SEQUENCE_STEP``.  ``optional`` says the leaf itself may be absent and
    ``in_optional_group`` that a group above it may be.
    """

    path: tuple[str, ...]
    kind: FactKind
    tokens: type[StrEnum] | None
    optional: bool
    in_optional_group: bool

    @property
    def dotted(self) -> str:
        """Return the path as one dotted name, as a record's flattened fields are named."""
        return ".".join(self.path)


@dataclass(frozen=True, slots=True)
class _Unwrapped:
    base: object
    markers: tuple[FactKind, ...]
    optional: bool


def _unwrap(annotation: object, markers: tuple[FactKind, ...] = ()) -> _Unwrapped:
    optional = False
    collected_markers: list[FactKind] = list(markers)
    while True:
        if isinstance(annotation, typing.TypeAliasType):
            annotation = annotation.__value__
            continue
        origin = typing.get_origin(annotation)
        if origin is typing.Annotated:
            args: tuple[object, ...] = typing.get_args(annotation)
            annotation, *metadata = args
            collected_markers.extend(item for item in metadata if isinstance(item, FactKind))
            continue
        if origin in {typing.Union, types.UnionType}:
            annotation, union_optional = _unwrap_union(annotation)
            optional = optional or union_optional
            continue
        return _Unwrapped(annotation, tuple(collected_markers), optional)


def _unwrap_union(annotation: object) -> tuple[object, bool]:
    args = typing.get_args(annotation)
    members = [member for member in args if member is not type(None)]
    if len(members) != 1:
        raise TypeError(f"a fact of several types cannot be worded: {annotation!r}")
    return members[0], len(members) != len(args)


def _field_markers(field: FieldInfo) -> tuple[FactKind, ...]:
    return tuple(item for item in field.metadata if isinstance(item, FactKind))


def _kind_of(base: object, markers: tuple[FactKind, ...], path: str) -> tuple[FactKind, type[StrEnum] | None]:
    if isinstance(base, type) and issubclass(base, StrEnum):
        return FactKind.CHOICE, base
    for primitive, kind in ((bool, FactKind.FLAG), (int, FactKind.WHOLE), (date, FactKind.DATE)):
        if base is primitive:
            return kind, None
    if base is Decimal:
        return (markers[0] if markers else FactKind.DECIMAL), None
    if isinstance(base, type) and issubclass(base, str):
        return (markers[0] if markers else FactKind.TEXT), None
    raise TypeError(f"{path} has a type no reader words: {base!r}")


def fact_leaves(
    model: type[BaseModel],
    *,
    descend_rows: bool = True,
    _prefix: tuple[str, ...] = (),
    _in_optional_group: bool = False,
) -> tuple[FactLeaf, ...]:
    """List every leaf fact of a model, in field order.

    Args:
        model: The model whose fields are walked.
        descend_rows: Whether a repeated group of facts is walked row-wise, through
            steps ending in ``SEQUENCE_STEP``; otherwise it is one leaf of kind ``ROWS``.

    Raises:
        TypeError: When a field has a type no reader can word.
    """
    leaves: list[FactLeaf] = []
    for name, field in model.model_fields.items():
        leaves.extend(_field_leaves(name, field, descend_rows, _prefix, _in_optional_group))
    return tuple(leaves)


def _field_leaves(
    name: str,
    field: FieldInfo,
    descend_rows: bool,
    prefix: tuple[str, ...],
    in_optional_group: bool,
) -> tuple[FactLeaf, ...]:
    path = (*prefix, name)
    unwrapped = _unwrap(field.annotation, _field_markers(field))
    base: object = unwrapped.base
    optional = unwrapped.optional or not field.is_required()
    if isinstance(base, type) and issubclass(base, BaseModel):
        return fact_leaves(
            base, descend_rows=descend_rows, _prefix=path, _in_optional_group=in_optional_group or optional
        )
    if typing.get_origin(base) is tuple:
        item = _unwrap(typing.get_args(base)[0])
        if descend_rows and isinstance(item.base, type) and issubclass(item.base, BaseModel):
            return fact_leaves(
                item.base,
                descend_rows=descend_rows,
                _prefix=(*prefix, f"{name}{SEQUENCE_STEP}"),
                _in_optional_group=in_optional_group or optional,
            )
        return (FactLeaf(path, FactKind.ROWS, None, optional, in_optional_group),)
    kind, tokens = _kind_of(unwrapped.base, unwrapped.markers, ".".join(path))
    return (FactLeaf(path, kind, tokens, optional, in_optional_group),)


def indexed_to_step_path(path: str) -> str:
    """Return a flattened field name with every row index replaced by ``SEQUENCE_STEP``."""
    out: list[str] = []
    for part in path.split("."):
        stem, bracket, _ = part.partition("[")
        out.append(f"{stem}{SEQUENCE_STEP}" if bracket else stem)
    return ".".join(out)


__all__ = [
    "SEQUENCE_STEP",
    "Amount",
    "ClassKey",
    "FactKind",
    "FactLeaf",
    "Share",
    "fact_leaves",
    "indexed_to_step_path",
]
