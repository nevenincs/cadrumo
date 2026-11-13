"""The guard that keeps a binding provider's declaration relative to the filing context.

A provider member states timeless intent and derives its source coordinate from
the target filing context at resolve time. The functions here walk a provider
model's annotations and name every field that would pin a concrete year,
revision or date. They are pure and model-agnostic; the enrolled table is
checked by the registration module that owns it.
"""

from __future__ import annotations

from datetime import date
from typing import Final, Literal, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from .binding_temporal import RelativeToFilingYear
from .ids import RevisionId

__all__ = [
    "AUTHORED_LAYOUT_INTEGER_FIELD_NAMES",
    "TEMPORAL_PROVIDER_FIELD_NAME",
    "absolute_coordinate_offenders",
]

AUTHORED_LAYOUT_INTEGER_FIELD_NAMES: Final[frozenset[str]] = frozenset({"offset", "length", "decimals"})
"""Provider field names whose integer is a record-layout fact, not a filing coordinate.

``offset``, ``length`` and ``decimals`` describe where a value sits in an
official fixed-width record and how it is written, which is authored design data
that does not change with the filing context. Every other integer on a provider
member would pin the declaration to one concrete year, revision, or date, and is
refused, unless its type carries the :class:`RelativeToFilingYear` marker, which
states a count of ejercicios before the one filed. The list is explicit so that adding a fourth is a deliberate decision
with a stated reason rather than a field that slipped through.
"""

TEMPORAL_PROVIDER_FIELD_NAME: Final[str] = "temporal"
"""The one provider field allowed to carry numbers that move with the context.

The temporal union is where a relative coordinate is *supposed* to live: its
members carry offsets and spans that are resolved against the target filing
context. The guard therefore skips this field rather than descending into it.
"""


def _absolute_coordinate_leaves(annotation: object) -> bool:
    """Return whether one resolved annotation pins a concrete filing coordinate.

    Unwraps ``Annotated``, optionals and unions, then recognises the four shapes
    that name a coordinate rather than describe one: a plain ``int``, the
    ``RevisionId`` alias, a ``date``, and a ``Literal`` whose members are ints.
    ``bool`` is a subclass of ``int`` in Python but names a flag, not a
    coordinate, so it is not treated as one.
    """
    if annotation is RevisionId:
        return True
    origin = get_origin(annotation)
    if origin is Literal:
        return any(isinstance(arg, int) and not isinstance(arg, bool) for arg in get_args(annotation))
    if origin is not None:
        return any(_absolute_coordinate_leaves(arg) for arg in get_args(annotation))
    if not isinstance(annotation, type):
        return False
    if issubclass(annotation, bool):
        return False
    return issubclass(annotation, (int, date))


def _nested_models(annotation: object) -> tuple[type[BaseModel], ...]:
    """Return every :class:`BaseModel` class reachable from one resolved annotation.

    A provider that nests its coordinate one model deep is exactly as pinned as
    one that declares it at the top level, so the walk follows the type rather
    than stopping at the first structured field.
    """
    origin = get_origin(annotation)
    if origin is Literal:
        return ()
    if origin is not None:
        return tuple(model for arg in get_args(annotation) for model in _nested_models(arg))
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return (annotation,)
    return ()


def absolute_coordinate_offenders(label: str, model: type[BaseModel]) -> tuple[str, ...]:
    """Return one diagnostic per field of ``model`` that pins a filing coordinate.

    The walk descends into nested models, reporting a dotted field path, because
    a coordinate reached through a structured field is still a coordinate: a
    provider declaring ``window: Window`` where ``Window`` carries a ``year``
    would otherwise pass a check that only ever looked one level down. The
    ``temporal`` field is skipped at every depth for the reason its own constant
    states, and each model is visited once so a self-referential shape
    terminates.

    Both exemptions -- the record-layout integer names and the ``temporal`` field
    -- are granted to the PROVIDER MODEL ITSELF and to nothing below it. Each is
    a statement about one specific declared surface: ``offset`` on a provider is
    an authored fixed-width address, and ``temporal`` on a provider is the union
    built to carry relative coordinates. A field of the same name on some nested
    model is a different field with a different contract, and an exemption that
    followed the name down would let any nested structure re-admit an absolute
    coordinate by calling it ``offset``.

    Pure and model-agnostic, so the guard can be exercised against a fabricated
    provider class without touching the enrolled table.
    """
    return _absolute_coordinate_offenders(label, model, seen=frozenset(), top_level=True)


def _coordinate_exempt(name: str, field_info: FieldInfo, *, top_level: bool) -> bool:
    """Whether an integer field is an authored layout address or a count marked relative to the filing year."""
    if top_level and name in AUTHORED_LAYOUT_INTEGER_FIELD_NAMES:
        return True
    return any(isinstance(marker, RelativeToFilingYear) for marker in field_info.metadata)


def _absolute_coordinate_offenders(
    label: str,
    model: type[BaseModel],
    *,
    seen: frozenset[type[BaseModel]],
    top_level: bool,
) -> tuple[str, ...]:
    """Walk one model's fields, recursing into nested models not already visited."""
    if model in seen:
        return ()
    visited = seen | {model}
    offenders: list[str] = []
    for name, field_info in sorted(model.model_fields.items()):
        if top_level and name == TEMPORAL_PROVIDER_FIELD_NAME:
            continue
        if not _coordinate_exempt(name, field_info, top_level=top_level) and _absolute_coordinate_leaves(
            field_info.annotation
        ):
            offenders.append(f"{label} declares absolute coordinate field {name!r}")
        for nested in _nested_models(field_info.annotation):
            offenders.extend(
                _absolute_coordinate_offenders(f"{label}.{name}", nested, seen=visited, top_level=False),
            )
    return tuple(offenders)
