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

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId
from .errors import RegistryValidationError
from .ids import BindingId
from .schema_input_kind import InputKind
from .schema_surfaces import CasillaDefinition

if TYPE_CHECKING:
    from .binding_selector_utils import BindingExportSelector
    from .schema import BindingDefinition, ModeloRevision

__all__ = [
    "BindingConsumerKind",
    "BindingConsumerRef",
    "binding_consumers",
    "bound_casilla_binding_ids",
    "casillas_by_binding",
    "revision_bindings_by_id",
    "sole_bound_casilla",
]


def revision_bindings_by_id(revision: ModeloRevision) -> dict[BindingId, BindingDefinition]:
    """Return the revision's binding declarations keyed by their id.

    Revision identity validation already refuses a duplicate registry id, so the
    index is lossless.
    """
    return {binding.id: binding for binding in revision.bindings}


def bound_casilla_binding_ids(casilla: CasillaDefinition) -> tuple[BindingId, ...]:
    """Return primary plus reviewed equivalent bindings for one bound casilla."""
    if casilla.input_kind != InputKind.BOUND:
        return ()
    if casilla.binding is None:
        raise RegistryValidationError(f"bound casilla {casilla.id!r} has no binding")
    return (casilla.binding, *casilla.alternate_bindings)


def casillas_by_binding(revision: ModeloRevision) -> Mapping[BindingId, tuple[CasillaId, ...]]:
    """Return every binding id mapped to its declaration-ordered target casillas.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    mapping: dict[BindingId, list[CasillaId]] = {}
    for casilla in revision.casillas:
        for binding_id in bound_casilla_binding_ids(casilla):
            populated_by = mapping.setdefault(binding_id, [])
            if casilla.id not in populated_by:
                populated_by.append(casilla.id)
    return {binding_id: tuple(casilla_ids) for binding_id, casilla_ids in mapping.items()}


def sole_bound_casilla(revision: ModeloRevision, binding_id: BindingId) -> CasillaId | None:
    """The one casilla ``binding_id`` populates in ``revision``, or ``None`` when it populates none or several.

    A diagnostic about a binding names this box, so the box it could not work
    out is reported once, by its box, and never also as a box-less binding.

    See Also:
        :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
            The registry declaration supplying casillas, formulas, bindings and layout metadata.
    """
    owners = casillas_by_binding(revision).get(binding_id, ())
    return owners[0] if len(owners) == 1 else None


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

    RELATION_EVIDENCE = "relation_evidence"
    """Relation prefill resolves the binding and carries it as reconciliation evidence.

    A ``factual_evidence`` relation evidences a fact without entering the
    arithmetic, so no casilla, formula or export reads it; the calculation still
    resolves it for a declared period and records it on the revision.
    """

    APPLICATION_ROW_VALUE = "application_row_value"
    """The application carries a provider's indexed source rows into the calculation revision."""


@dataclass(frozen=True, slots=True)
class BindingConsumerRef:
    """One typed consumer of a binding, named by surface and owning identifier."""

    kind: BindingConsumerKind
    owner: str


def binding_consumers(revision: ModeloRevision) -> Mapping[BindingId, tuple[BindingConsumerRef, ...]]:
    """Return every declared binding mapped to its typed consumers in one revision.

    The reverse of the forward references the compiler already closes: a
    binding is *referenced* when a bound casilla, formula operand, export field
    or record, relation evidence, or the enrolled foreign-asset application
    row route consumes it. Bindings with no entry at all are returned as an
    empty tuple rather than omitted, so an orphan is a value in the mapping
    rather than a missing key a caller has to infer.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
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
    _record_relation_evidence_consumers(revision, record)
    _record_foreign_asset_row_consumers(revision, record)
    return {binding_id: tuple(refs) for binding_id, refs in consumers.items()}


def _record_foreign_asset_row_consumers(
    revision: ModeloRevision,
    record: Callable[[BindingId, BindingConsumerKind, str], None],
) -> None:
    """Index the row source that ``foreign_assets._row_resolution`` persists.

    That application route calls ``resolve_foreign_asset_binding_row_values``;
    the domain resolver emits every valid foreign-asset row binding, including
    fields that are not independent slots of the AEAT type-2 export record.
    The shared typed row selector admits exactly the rows this route can carry.
    Other row providers do not acquire a consumer from this rule.
    """
    from .binding_selector_utils import binding_row_set_selector

    for binding in revision.bindings:
        if binding.source is not BindingSourceKind.FOREIGN_ASSET:
            continue
        try:
            selector = binding_row_set_selector(binding)
        except RegistryValidationError:
            # The provider validator reports the malformed declaration. It
            # cannot earn a consumer by failing to name a usable row field.
            continue
        if selector is not None:
            record(
                binding.id, BindingConsumerKind.APPLICATION_ROW_VALUE, f"foreign_asset_row_values.{selector.row_field}"
            )


def _record_relation_evidence_consumers(
    revision: ModeloRevision,
    record: Callable[[BindingId, BindingConsumerKind, str], None],
) -> None:
    """Record each factual-evidence relation binding a declared period selects."""
    # Deferred for the same schema import cycle as ``runtime_graph`` above.
    from .relation_dependency import RelationDependencyRole
    from .relations import relation_prefill_bindings_for_period

    owners = {
        binding_id: str(classification.id)
        for classification in revision.dependency_classifications
        for binding_id in classification.binding_refs
    }
    for period in revision.period_selector.declared_periods:
        for binding, provider in relation_prefill_bindings_for_period(revision, period=period):
            if provider.dependency_role is RelationDependencyRole.FACTUAL_EVIDENCE:
                record(binding.id, BindingConsumerKind.RELATION_EVIDENCE, owners.get(binding.id, "relation_prefill"))


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
    if not revision.export_layouts:
        return
    record_names = _record_export_field_consumers(revision, record)
    if not record_names:
        return
    _record_export_binding_consumers(revision, record_names, record)


def _record_export_field_consumers(
    revision: ModeloRevision,
    record: Callable[[BindingId, BindingConsumerKind, str], None],
) -> dict[str, list[str]]:
    record_names: dict[str, list[str]] = {}
    for layout in revision.export_layouts:
        for export_record in layout.records:
            if export_record.binding_record is not None:
                record_names.setdefault(export_record.binding_record, []).append(str(export_record.id))
            for field in export_record.fields:
                if field.binding is not None:
                    record(field.binding, BindingConsumerKind.EXPORT_FIELD, f"{export_record.id}.{field.id}")
    return record_names


def _record_export_binding_consumers(
    revision: ModeloRevision,
    record_names: Mapping[str, list[str]],
    record: Callable[[BindingId, BindingConsumerKind, str], None],
) -> None:
    for binding in revision.bindings:
        selector = _binding_export_selector_or_none(binding, revision)
        if selector is None:
            continue
        for owner in record_names.get(selector.record, ()):
            record(binding.id, BindingConsumerKind.EXPORT_BINDING_RECORD, owner)


def _binding_export_selector_or_none(
    binding: BindingDefinition,
    revision: ModeloRevision,
) -> BindingExportSelector | None:
    from .binding_selector_utils import binding_export_selector

    try:
        return binding_export_selector(binding, revision=revision)
    except RegistryValidationError:
        return None
