"""Off-load-path record-design coverage and calculation-closure derivations.

:func:`calculation_closure_casilla_ids` and
:func:`calculation_closure_legal_refs` derive bounded closure projections from
a :class:`ModeloRevision`; :class:`DisenoCoverageReport` remains the advisory
full-Dise�o inventory.
"""

from __future__ import annotations

from collections.abc import Callable

from ....core.casilla_id import CasillaId
from .bindings import binding_source_casilla_ids, binding_source_modelo
from .runtime_graph import expression_casilla_refs
from .schema import DataBindingDefinition, ModeloRevision
from .schema_surfaces import CasillaDefinition

# ---------------------------------------------------------------------------
# Calculation-completeness manifest derivation and Dise�o extraction
# (off-load-path)
# ---------------------------------------------------------------------------
#
# The derivations below run off the snapshot-build hot path; they are
# called only by manifest-authoring scripts, the off-load-path coverage
# report, and the drift re-verification test.
#
# - ``calculation_closure_casilla_ids`` enumerates a revision's calculation
#   closure as canonical ``casilla.id`` values only. Reference tokens that do
#   not name a declared casilla id remain unresolved and fail the manifest
#   derivation instead of being reinterpreted as display metadata.
#
# - ``calculation_closure_record_design_metadata`` projects that canonical
#   closure through each closure casilla's own registry ``(segmento, number)``
#   metadata. This metadata is reviewed against Dise�o where needed, while
#   the manifest row also carries the canonical ``casilla.id`` that consumers
#   resolve.
#
# - ``derive_calculation_completeness_casillas`` derives the
#   *calculation-completeness manifest* casilla set from that closure:
#   the modelo's calculation surface keyed on canonical ``casilla.id`` and
#   carrying the registry metadata each closure casilla declares. For a multi-segment modelo it optionally
#   verifies the derived record segments against the AEAT Dise�o de
#   Registros. This is the set the load-blocking completeness gate
#   enforces.
#
# - ``derive_diseno_coverage_casillas`` extracts the *full* Dise�o
#   casilla set � every five-digit casilla tag AEAT embeds in a field
#   description, accounting-statement data-entry fields included. It
#   parses the multi-megabyte Dise�o corpus and is the input to the
#   off-load-path advisory coverage report that inventories form-level
#   data coverage; it is NOT a load-blocking gate.

"""Matches the bracketed casilla tag AEAT embeds in Dise�o field text.

The official AEAT Dise�o de Registros workbooks annotate every casilla
field with its casilla number in square brackets within the field
description, validation or content text (e.g. ``Liquidaci�n III - ... -
Base imponible [00552]``). This regex extracts those tags so a derivation
can enumerate the ``(segmento, number)`` casilla set.

**The tag width is NOT five digits across AEAT.** It was written as
``\\d{5}``, which is the Impuesto sobre Sociedades convention that Modelo
200 and Modelo 220 use. Every other modelo family brackets its box number
at its natural width -- Modelo 303 writes ``[01]`` and ``[150]``, Modelo
390 ``[01]``, Modelo 036 two and three digits. A fixed five-digit pattern
therefore matched nothing on them, and because a matchless sweep yields an
empty Dise�o set rather than an error, the coverage report said
``0 casillas, 0 gap`` for 36 of the 38 revisions that bundle an official
record design. Reading as fully covered is the worst available failure for
an instrument whose whole job is to find what the registry has not
authored.

Widening it takes the population that extracts anything from 2 revisions
to 24. The remaining 14 annotate their casillas outside bracketed field
text entirely and are inventoried, not silently zeroed, by
:func:`build_diseno_coverage_report`.

Bounded at five digits rather than open-ended: an unbounded ``\\d+`` would
admit amounts, NIF fragments and position offsets that appear bracketed in
the same columns.
"""


def _binding_is_cross_modelo(binding: DataBindingDefinition, modelo_id: str) -> bool:
    """Return whether a binding names a foreign source modelo.

    A binding is *cross-modelo* when its typed selector helper reports a
    ``source_modelo`` that is not the modelo whose closure is being derived.
    A binding with no source modelo, or one set to ``modelo_id``, is a
    *within-modelo* binding: its ``source_casilla_ids`` / ``source_casilla_id``
    name casillas on the modelo being derived, and those casillas belong in
    the modelo's own calculation closure.
    """
    source_modelo = binding_source_modelo(binding)
    if source_modelo is None:
        return False
    return source_modelo != modelo_id


def _visit_formula_closure_tokens(
    revision: ModeloRevision,
    visit_token: Callable[[CasillaId], None],
) -> None:
    for formula in revision.formulas:
        visit_token(formula.target_casilla_id)
        for ref in expression_casilla_refs(formula.expression):
            visit_token(ref)


def _visit_expectation_closure_tokens(
    revision: ModeloRevision,
    visit_token: Callable[[CasillaId], None],
) -> None:
    for expectation in revision.verification_expectations:
        for ref in expectation.computed_casilla_ids:
            visit_token(ref)
        for ref in expectation.reconciliation_total_casilla_ids.values():
            visit_token(ref)


def _visit_binding_closure_tokens(
    revision: ModeloRevision,
    modelo_id: str,
    visit_token: Callable[[CasillaId], None],
) -> None:
    for binding in revision.bindings:
        if _binding_is_cross_modelo(binding, modelo_id):
            continue
        for token in binding_source_casilla_ids(binding):
            visit_token(token)


def _visit_relation_closure_tokens(
    revision: ModeloRevision,
    modelo_id: str,
    visit_token: Callable[[CasillaId], None],
) -> None:
    for relation in revision.relations:
        if relation.source_modelo == modelo_id:
            visit_token(relation.source_casilla_id)


def _walk_calculation_closure(
    revision: ModeloRevision,
    modelo_id: str,
    *,
    visit_token: Callable[[CasillaId], None],
    visit_endpoint: Callable[[CasillaDefinition], None],
) -> None:
    """Walk the within-modelo calculation closure, dispatching each member.

    Shared by :func:`calculation_closure_casilla_ids` and
    :func:`calculation_closure_record_design_metadata`; ``visit_endpoint`` receives every
    formula/binding endpoint casilla and ``visit_token`` every referenced
    casilla token (formula targets, transitive expression refs,
    verification-expectation operands, and within-modelo binding/relation
    selectors).
    """
    for casilla in revision.casillas:
        if casilla.formula is not None or casilla.binding is not None:
            visit_endpoint(casilla)
    _visit_formula_closure_tokens(revision, visit_token)
    _visit_expectation_closure_tokens(revision, visit_token)
    _visit_binding_closure_tokens(revision, modelo_id, visit_token)
    _visit_relation_closure_tokens(revision, modelo_id, visit_token)


def calculation_closure_casilla_ids(revision: ModeloRevision, modelo_id: str) -> frozenset[CasillaId]:
    """Return canonical casilla ids in a revision's calculation closure.

    The *calculation closure* is the set of casillas the cross-connecting
    calculation engine traverses **within this modelo revision**:

    - every ``formula.target_casilla_id`` casilla;
    - every casilla referenced inside any ``formula.expression``, walked
      transitively via the runtime-graph ``expression_casilla_refs``
      walker;
    - every casilla that declares a ``formula`` (a computed endpoint) or
      a ``binding`` (a bound endpoint) � the engine-visible casillas;
    - every verification-expectation operand casilla
      (``computed_casilla_ids`` and the ``reconciliation_total_casilla_ids`` targets);
    - every *within-modelo* binding ``source_casilla_ids`` / ``source_casilla_id``
      selector casilla, and every *within-modelo*
      ``RelationDefinition.source_casilla_id``.

    A binding ``source_casilla_ids`` / ``source_casilla_id`` selector � and a
    ``RelationDefinition.source_casilla_id`` � is excluded from this closure
    **only when it is genuinely cross-modelo**: when the selector
    explicitly names a ``source_modelo`` that differs from ``modelo_id``.
    A cross-modelo selector's ``source_casilla_ids`` / ``source_casilla_id``
    name casillas on that *foreign* modelo, not on the modelo whose
    closure is being derived; the cross-modelo edge enters the current
    modelo through the *bound* casilla � the current-modelo casilla that
    declares the binding (or, for a relation, ``relation.target_binding``)
    � which is already counted above as a binding endpoint. Folding a
    foreign-modelo casilla id into this closure would make the
    completeness gate demand it from the wrong modelo's registry.

    A selector that omits ``source_modelo`` or sets it equal to
    ``modelo_id`` is a *within-modelo* selector: a ``previous_filing``
    self-binding or a ``previous_period`` self-relation names a casilla
    on the modelo being derived, so that casilla is a genuine closure
    member and is kept.

    References are not normalised through record-design metadata. A formula,
    binding, relation, or verification token must already be the canonical
    ``casilla.id`` for this revision. A reference token that matches no
    declared casilla id is kept verbatim so the manifest derivation and
    registry validation fail loudly on the unresolved canonical reference.

    Args:
        revision: The :class:`ModeloRevision` whose formula and binding graph
            is walked to derive the closure.
        modelo_id: The AEAT modelo identifier used to exclude cross-modelo
            selector casillas from the closure.
    """
    closure: set[CasillaId] = set()
    _walk_calculation_closure(
        revision,
        modelo_id,
        visit_token=closure.add,
        visit_endpoint=lambda casilla: closure.add(casilla.id),
    )
    return frozenset(closure)


__all__ = [
    "calculation_closure_casilla_ids",
]
