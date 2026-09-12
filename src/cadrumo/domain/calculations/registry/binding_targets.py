"""Canonical target relationships for registry data bindings.

Binding declarations name the factual source that can populate a casilla.
This module owns both directions of that relationship so registry consumers do
not reconstruct the ``BOUND`` predicate independently.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from ....core.casilla_id import CasillaId
from .errors import RegistryValidationError
from .ids import BindingId
from .schema_input_kind import InputKind
from .schema_surfaces import CasillaDefinition

if TYPE_CHECKING:
    from .schema import ModeloRevision

__all__ = [
    "BindingConsumerKind",
    "BindingConsumerRef",
    "binding_consumers",
    "bound_casilla_binding_ids",
    "casillas_by_binding",
]


def bound_casilla_binding_ids(casilla: CasillaDefinition) -> tuple[BindingId, ...]:
    """Return primary plus reviewed equivalent bindings for one bound casilla."""
    if casilla.input_kind != InputKind.BOUND:
        return ()
    if casilla.binding is None:
        raise RegistryValidationError(f"bound casilla {casilla.id!r} has no binding")
    return (casilla.binding, *casilla.alternate_bindings)


def casillas_by_binding(revision: ModeloRevision) -> Mapping[BindingId, tuple[CasillaId, ...]]:
    """Return every binding id mapped to its declaration-ordered target casillas."""
    mapping: dict[BindingId, list[CasillaId]] = {}
    for casilla in revision.casillas:
        for binding_id in bound_casilla_binding_ids(casilla):
            populated_by = mapping.setdefault(binding_id, [])
            if casilla.id not in populated_by:
                populated_by.append(casilla.id)
    return {binding_id: tuple(casilla_ids) for binding_id, casilla_ids in mapping.items()}


class BindingConsumerKind(StrEnum):
    """The typed consumer surfaces that can name a binding in one revision."""

    CASILLA_PRIMARY = "casilla_primary"
    """A ``BOUND`` casilla names the binding as its primary source."""

    CASILLA_ALTERNATE = "casilla_alternate"
    """A ``BOUND`` casilla names the binding as a reviewed equivalent."""

    FORMULA_OPERAND = "formula_operand"
    """A formula expression reads the binding through a ``binding`` leaf."""

    FORMULA_DATE_OPERAND = "formula_date_operand"
    """A formula expression reads the binding through a ``date_binding`` leaf."""

    EXPORT_FIELD = "export_field"
    """An export field renders the binding value directly."""

    EXPORT_BINDING_RECORD = "export_binding_record"
    """An export record materialises its rows from the binding's export selector."""


@dataclass(frozen=True, slots=True)
class BindingConsumerRef:
    """One typed consumer of a binding, named by surface and owning identifier."""

    kind: BindingConsumerKind
    owner: str


def binding_consumers(revision: ModeloRevision) -> Mapping[BindingId, tuple[BindingConsumerRef, ...]]:
    """Return every declared binding mapped to its typed consumers in one revision.

    The reverse of the forward references the compiler already closes: a
    binding is *referenced* when a bound casilla, a formula operand, an export
    field or record. Bindings with no entry at all are
    returned as an empty tuple rather than omitted, so an orphan is a value in
    the mapping rather than a missing key a caller has to infer.
    """
    consumers: dict[BindingId, list[BindingConsumerRef]] = {binding.id: [] for binding in revision.bindings}

    def record(binding_id: BindingId, kind: BindingConsumerKind, owner: str) -> None:
        refs = consumers.get(binding_id)
        if refs is None:
            return
        ref = BindingConsumerRef(kind=kind, owner=owner)
        if ref not in refs:
            refs.append(ref)

    for casilla in revision.casillas:
        if casilla.input_kind is not InputKind.BOUND:
            continue
        if casilla.binding is not None:
            record(casilla.binding, BindingConsumerKind.CASILLA_PRIMARY, str(casilla.id))
        for alternate in casilla.alternate_bindings:
            record(alternate, BindingConsumerKind.CASILLA_ALTERNATE, str(casilla.id))
    # Deferred: ``runtime_graph`` and ``binding_selector_utils`` both reach
    # ``schema``, which reaches the provider union, which reaches this module.
    # The cycle is real at import time only; by call time every module is built.
    from .runtime_graph import expression_binding_refs, expression_date_binding_refs

    for formula in revision.formulas:
        for binding_id in expression_binding_refs(formula.expression):
            record(binding_id, BindingConsumerKind.FORMULA_OPERAND, str(formula.id))
        for binding_id in expression_date_binding_refs(formula.expression):
            record(binding_id, BindingConsumerKind.FORMULA_DATE_OPERAND, str(formula.id))
    _record_export_consumers(revision, record)
    return {binding_id: tuple(refs) for binding_id, refs in consumers.items()}


def _record_export_consumers(
    revision: ModeloRevision,
    record: Callable[[BindingId, BindingConsumerKind, str], None],
) -> None:
    """Record export-field and binding-record consumers for one revision.

    ``binding_record`` names a record family rather than a binding id, so the
    join runs the other way: each binding's own typed export projection states
    the record it materialises. A binding whose projection is malformed is not
    silently dropped from the index -- the export validators own that refusal
    and report it -- so it simply earns no export consumer here.
    """
    from .binding_selector_utils import binding_export_selector

    if not revision.export_layouts:
        return
    record_names: dict[str, list[str]] = {}
    for layout in revision.export_layouts:
        for export_record in layout.records:
            if export_record.binding_record is not None:
                record_names.setdefault(export_record.binding_record, []).append(str(export_record.id))
            for field in export_record.fields:
                if field.binding is not None:
                    record(field.binding, BindingConsumerKind.EXPORT_FIELD, f"{export_record.id}.{field.id}")
    if not record_names:
        return
    for binding in revision.bindings:
        try:
            selector = binding_export_selector(binding, revision=revision)
        except RegistryValidationError:
            continue
        if selector is None:
            continue
        for owner in record_names.get(selector.record, ()):
            record(binding.id, BindingConsumerKind.EXPORT_BINDING_RECORD, owner)
