"""Revision-local inventory of what produces each casilla's value.

The inventory classifies every casilla's production path and keeps the real
formula and binding declarations that ground it, so conformance and validation
can read a producer's own provenance without restating it on the casilla.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Final

from pydantic import BeforeValidator

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.casilla_id import CasillaId
from cadrumo.domain.calculations.registry.ids import BindingId, FormulaId, LegalRefId, SourceRefId
from cadrumo.domain.calculations.registry.schema import BindingDefinition, FormulaDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_base import coerce_enum_member
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition


def _freeze_index[K, V](index: Mapping[K, Sequence[V]]) -> dict[K, tuple[V, ...]]:
    return {key: tuple(values) for key, values in index.items()}


class CasillaProducerKind(StrEnum):
    """What produces a casilla's value in the compiled registry."""

    FORMULA = "formula"
    """A grounded formula computes it."""

    MANUAL = "manual"
    """The taxpayer supplies it directly."""

    UPSTREAM = "upstream"
    """It arrives from another modelo's output."""

    RELATION = "relation"
    """A declared relation prefills it."""

    INFORMATIONAL = "informational"
    """It is carried for information and settles nothing."""

    PROJECTION_ONLY = "projection_only"
    """It exists only in a projection, with no producer of its own."""


CasillaProducerKindField = Annotated[CasillaProducerKind, BeforeValidator(coerce_enum_member(CasillaProducerKind))]
"""Registry ``producer_kind`` token hydrated into a member."""


@dataclass(frozen=True, slots=True)
class CasillaProducerProvenance:
    """One lossless producer path for a revision-local casilla.

    The record retains the real schema declarations instead of copying or
    flattening their legal/source provenance, so a producer's own grounding
    stays visible rather than being restated on the casilla.
    """

    casilla: CasillaDefinition
    producer_kind: CasillaProducerKindField
    reason: str
    formula: FormulaDefinition | None = None
    binding: BindingDefinition | None = None

    @property
    def producer_legal_refs(self) -> tuple[LegalRefId, ...]:
        """Return the existing legal refs on this path's producer declaration."""
        if self.binding is not None:
            return tuple(self.binding.legal_refs)
        if self.formula is not None:
            return tuple(self.formula.legal_refs)
        if self.producer_kind in _CASILLA_GROUNDED_PRODUCER_KINDS:
            return tuple(self.casilla.legal_refs)
        return ()

    @property
    def producer_source_refs(self) -> tuple[SourceRefId, ...]:
        """Return the existing source refs on this path's producer declaration."""
        if self.binding is not None:
            return tuple(self.binding.source_refs)
        if self.formula is not None:
            return tuple(self.formula.source_refs)
        if self.producer_kind in _CASILLA_GROUNDED_PRODUCER_KINDS:
            return tuple(self.casilla.source_refs)
        return ()


#: Producer kinds whose grounding lives on the CASILLA itself. None of them has a
#: producer declaration of its own to carry legal or source refs: a manual value
#: is operator-supplied, an informational casilla produces nothing, and a
#: projection-only casilla is populated from its canonical typed row, which is a
#: runtime projection rather than a registry row with provenance. Omitting
#: projection_only dropped the grounding of 366 Modelo 303 casillas -- every one
#: of which declares legal_refs -- from their producer trace.
_CASILLA_GROUNDED_PRODUCER_KINDS: Final[frozenset[CasillaProducerKind]] = frozenset(
    {
        CasillaProducerKind.MANUAL,
        CasillaProducerKind.INFORMATIONAL,
        CasillaProducerKind.PROJECTION_ONLY,
    },
)


@dataclass(frozen=True, slots=True)
class CasillaProducerInventory:
    """Revision-local inventory of casilla producers and declarations.

    Formula targets are indexed in both directions without collapsing duplicate
    declarations.  The ``producer_kind_by_casilla`` and
    ``producer_reason_by_casilla`` maps keep intentional non-formula rows
    visible: manual rows are operator-supplied, bound rows are upstream
    producers, and relation-prefill bindings are cross-model handoffs.  Their
    legal/source provenance remains on the casilla and binding definitions;
    this inventory only names the declared production path and its reason.
    """

    formula_ids_by_target: Mapping[CasillaId, tuple[FormulaId, ...]]
    formula_ids_by_id: Mapping[FormulaId, tuple[FormulaDefinition, ...]]
    formula_ids_by_casilla: Mapping[CasillaId, tuple[FormulaId, ...]]
    computed_casilla_ids: frozenset[CasillaId]
    producer_kind_by_casilla: Mapping[CasillaId, CasillaProducerKindField]
    producer_reason_by_casilla: Mapping[CasillaId, str]
    producer_provenance_by_casilla: Mapping[CasillaId, tuple[CasillaProducerProvenance, ...]]


def _producer_provenance(
    casilla: CasillaDefinition,
    kind: CasillaProducerKind,
    reason: str,
    *,
    formulas: Sequence[FormulaDefinition] = (),
    binding: BindingDefinition | None = None,
) -> tuple[CasillaProducerProvenance, ...]:
    """Build the provenance records for one classified production path.

    A declaration that resolves to several real registry rows -- several formula
    declarations sharing one id -- emits one record per row, so their
    independent legal provenance stays visible. A
    declaration that resolves to none still emits a single record carrying the
    reason, which is what keeps an unresolved producer auditable instead of
    absent.
    """
    if formulas:
        return tuple(
            CasillaProducerProvenance(
                casilla=casilla,
                producer_kind=kind,
                reason=reason,
                formula=formula,
            )
            for formula in formulas
        )
    return (
        CasillaProducerProvenance(
            casilla=casilla,
            producer_kind=kind,
            reason=reason,
            binding=binding,
        ),
    )


def _bound_casilla_producer(
    casilla: CasillaDefinition,
    *,
    bindings_by_id: Mapping[BindingId, BindingDefinition],
) -> tuple[CasillaProducerKind, str, tuple[CasillaProducerProvenance, ...]]:
    """Classify a ``bound`` casilla from the binding its declaration names.

    A binding declaring :attr:`~core.BindingSourceKind.RELATION_PREFILL` is a
    relation handoff; any other binding is an ordinary upstream value. A missing
    binding declaration stays ``upstream`` and says so in its reason rather than
    silently reclassifying -- the declaration, not the resolution, is what the
    inventory reports.
    """
    binding = bindings_by_id.get(casilla.binding) if casilla.binding is not None else None
    if binding is None:
        reason = "upstream production is declared by input_kind='bound' but its binding declaration is missing"
        return CasillaProducerKind.UPSTREAM, reason, _producer_provenance(casilla, CasillaProducerKind.UPSTREAM, reason)
    if binding.source is BindingSourceKind.RELATION_PREFILL:
        reason = f"relation production uses binding {binding.id!r} with source {binding.source.value!r}"
        return (
            CasillaProducerKind.RELATION,
            reason,
            _producer_provenance(casilla, CasillaProducerKind.RELATION, reason, binding=binding),
        )
    reason = f"upstream production uses binding {binding.id!r} with source {binding.source.value!r}"
    return (
        CasillaProducerKind.UPSTREAM,
        reason,
        _producer_provenance(casilla, CasillaProducerKind.UPSTREAM, reason, binding=binding),
    )


def _casilla_producer(
    casilla: CasillaDefinition,
    *,
    formulas_by_id: Mapping[FormulaId, Sequence[FormulaDefinition]],
    bindings_by_id: Mapping[BindingId, BindingDefinition],
) -> tuple[CasillaProducerKind, str, tuple[CasillaProducerProvenance, ...]]:
    """Classify one casilla's declared production path, with its reason.

    An explicit formula declaration wins over the input kind, because it is the
    narrower statement of the same fact. The classification is descriptive:
    validation still owns whether a formula direction is closed.
    """
    if casilla.formula is not None:
        reason = f"deterministic formula producer declaration {casilla.formula!r}"
        return (
            CasillaProducerKind.FORMULA,
            reason,
            _producer_provenance(
                casilla,
                CasillaProducerKind.FORMULA,
                reason,
                formulas=formulas_by_id.get(casilla.formula, ()),
            ),
        )
    if casilla.input_kind is InputKind.COMPUTED:
        reason = "computed casilla requires a deterministic formula producer"
        return CasillaProducerKind.FORMULA, reason, _producer_provenance(casilla, CasillaProducerKind.FORMULA, reason)
    if casilla.input_kind is InputKind.MANUAL:
        reason = (
            "manual production is intentional operator-supplied input; "
            "casilla legal_refs/source_refs remain its provenance"
        )
        return CasillaProducerKind.MANUAL, reason, _producer_provenance(casilla, CasillaProducerKind.MANUAL, reason)
    if casilla.input_kind is InputKind.BOUND:
        return _bound_casilla_producer(casilla, bindings_by_id=bindings_by_id)
    if casilla.input_kind is InputKind.PROJECTION_ONLY:
        reason = "projection-only casilla is populated exclusively from its canonical typed row"
        return (
            CasillaProducerKind.PROJECTION_ONLY,
            reason,
            _producer_provenance(casilla, CasillaProducerKind.PROJECTION_ONLY, reason),
        )
    reason = "informational casilla is intentionally not a calculation producer"
    return (
        CasillaProducerKind.INFORMATIONAL,
        reason,
        _producer_provenance(casilla, CasillaProducerKind.INFORMATIONAL, reason),
    )


def producer_inventory(revision: ModeloRevision) -> CasillaProducerInventory:
    """Return the typed producer/declaration inventory for this revision.

    Formula ids are retained as tuples in every index so an invalid
    duplicate cannot be hidden by a last-write-wins dictionary.  A
    non-formula casilla is classified from its existing typed declaration:
    ``manual`` is operator input, ordinary ``bound`` rows are upstream
    values, and ``relation_prefill`` rows are relation handoffs.  These
    classifications are descriptive; validation still owns whether a
    formula direction is closed.
    """
    formulas_by_target: dict[CasillaId, list[FormulaId]] = {}
    formulas_by_id: dict[FormulaId, list[FormulaDefinition]] = {}
    for formula in revision.formulas:
        formulas_by_target.setdefault(formula.target_casilla_id, []).append(formula.id)
        formulas_by_id.setdefault(formula.id, []).append(formula)

    formula_declarations_by_casilla: dict[CasillaId, list[FormulaId]] = {}
    bindings_by_id = {binding.id: binding for binding in revision.bindings}
    computed_casilla_ids: set[CasillaId] = set()
    producer_kind_by_casilla: dict[CasillaId, CasillaProducerKind] = {}
    producer_reason_by_casilla: dict[CasillaId, str] = {}
    producer_provenance_by_casilla: dict[CasillaId, list[CasillaProducerProvenance]] = {}

    for casilla in revision.casillas:
        if casilla.input_kind is InputKind.COMPUTED:
            computed_casilla_ids.add(casilla.id)
        if casilla.formula is not None:
            formula_declarations_by_casilla.setdefault(casilla.id, []).append(casilla.formula)

        kind, reason, provenance = _casilla_producer(
            casilla,
            formulas_by_id=formulas_by_id,
            bindings_by_id=bindings_by_id,
        )
        producer_kind_by_casilla[casilla.id] = kind
        producer_reason_by_casilla[casilla.id] = reason
        producer_provenance_by_casilla.setdefault(casilla.id, []).extend(provenance)

    return CasillaProducerInventory(
        formula_ids_by_target=_freeze_index(formulas_by_target),
        formula_ids_by_id=_freeze_index(formulas_by_id),
        formula_ids_by_casilla=_freeze_index(formula_declarations_by_casilla),
        computed_casilla_ids=frozenset(computed_casilla_ids),
        producer_kind_by_casilla=producer_kind_by_casilla,
        producer_reason_by_casilla=producer_reason_by_casilla,
        producer_provenance_by_casilla=_freeze_index(producer_provenance_by_casilla),
    )


__all__ = [
    "CasillaProducerInventory",
    "CasillaProducerKind",
    "CasillaProducerProvenance",
    "producer_inventory",
]
