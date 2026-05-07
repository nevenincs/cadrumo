"""Drift-detection guards for Modelo 100 across all 6 supported ejercicios.

Each test compares the formula / binding / parameter inventory across
revisions and surfaces gaps where a 2025 chain element was not backported
or where a prior-year revision diverged silently. The tests do not require
strict 1-to-1 parity (year-specific casillas legitimately drop some
elements) but catch:

  - top-level chain casillas (cuota chain, base imponible/liquidable,
    income aggregators) missing from any year
  - external references (binding, parameter, relation) declared but
    unreferenced
  - external references referenced but undeclared
  - revisions with formulas but no calculation application_link
"""

from __future__ import annotations

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


_TOP_LEVEL_CHAIN_TARGETS: frozenset[str] = frozenset(
    {
        # Mínimo personal y familiar
        "0519", "0520", "0521", "0522", "0523", "0524",
        # Base imponible / liquidable
        "0432", "0435", "0460", "0500", "0510",
        # Cuota íntegra
        "0532", "0533", "0545", "0546",
        # Cuota líquida + incrementada
        "0570", "0571", "0585", "0586",
    }
)

_SUPPORTED_REVISIONS: tuple[str, ...] = ("2020", "2021", "2022", "2023", "2024", "2025")


def _modelo_100():
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    return next(m for m in modelos if m.id == "100"), catalogues


def test_top_level_cuota_chain_targets_present_in_every_supported_revision() -> None:
    """Every supported ejercicio carries the top-level cuota-chain formula targets."""
    modelo, _ = _modelo_100()
    gaps: dict[str, list[str]] = {}
    for revision_id in _SUPPORTED_REVISIONS:
        revision = modelo.revisions.get(revision_id)
        if revision is None:
            gaps[revision_id] = sorted(_TOP_LEVEL_CHAIN_TARGETS)
            continue
        targets = {f.target for f in revision.formulas}
        missing = _TOP_LEVEL_CHAIN_TARGETS - targets
        if missing:
            gaps[revision_id] = sorted(missing)
    assert not gaps, f"top-level cuota chain incomplete in revisions {gaps}"


def test_every_revision_with_formulas_exposes_a_calculation_application_link() -> None:
    """Per the registry validator's contract, formula-bearing revisions need a calculation link."""
    modelo, _ = _modelo_100()
    offenders: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        if not revision.formulas:
            continue
        surfaces = {link.surface for link in revision.application_links}
        if "calculation" not in surfaces:
            offenders.append(revision_id)
    assert not offenders, f"revisions with formulas but no calculation application_link: {offenders}"


def test_every_supported_revision_carries_a_filing_application_link() -> None:
    """Every supported ejercicio is filing-grade and needs a filing application_link."""
    modelo, _ = _modelo_100()
    offenders: list[str] = []
    for revision_id in _SUPPORTED_REVISIONS:
        revision = modelo.revisions.get(revision_id)
        if revision is None:
            continue
        surfaces = {link.surface for link in revision.application_links}
        if "filing" not in surfaces:
            offenders.append(revision_id)
    assert not offenders, f"supported revisions missing filing application_link: {offenders}"


def test_no_orphan_formula_feeding_bindings_in_any_revision() -> None:
    """Every formula-feeding binding declared in a revision must be referenced.

    Profile-source bindings expose taxpayer data to the application layer
    (declaration filling, observation capture) and are not expected to be
    consumed by formulas; they are excluded from the orphan check.
    Manual_input and previous_filing bindings are formula-feeding and must
    be referenced by at least one formula or relation.
    """
    modelo, _ = _modelo_100()
    offences: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        formula_feeding = {
            b.id for b in revision.bindings if b.source in ("manual_input", "previous_filing")
        }
        referenced: set[str] = set()
        for formula in revision.formulas:
            _collect_binding_refs(formula.expression, referenced)
        for relation in revision.relations:
            target_binding = getattr(relation, "target_binding", None)
            if target_binding:
                referenced.add(target_binding)
        orphans = formula_feeding - referenced
        for orphan in sorted(orphans):
            offences.append(f"{revision_id}: orphan formula-feeding binding {orphan!r}")
    assert not offences, "orphan formula-feeding bindings detected:\n  " + "\n  ".join(offences)


def test_no_orphan_parameters_in_any_revision() -> None:
    """Every parameter declared in a revision must be referenced by at least one formula."""
    modelo, _ = _modelo_100()
    offences: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        declared = {p.id for p in revision.parameters}
        referenced: set[str] = set()
        for formula in revision.formulas:
            _collect_parameter_refs(formula.expression, referenced)
        orphans = declared - referenced
        for orphan in sorted(orphans):
            offences.append(f"{revision_id}: orphan parameter {orphan!r}")
    assert not offences, "orphan parameters detected:\n  " + "\n  ".join(offences)


def test_every_relation_references_an_existing_target_binding() -> None:
    """Each relation's target_binding must be a binding declared in the same revision."""
    modelo, _ = _modelo_100()
    offences: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        declared_bindings = {b.id for b in revision.bindings}
        for relation in revision.relations:
            target_binding = getattr(relation, "target_binding", None)
            if target_binding and target_binding not in declared_bindings:
                offences.append(
                    f"{revision_id}: relation {relation.id!r} target_binding {target_binding!r} not declared"
                )
    assert not offences, "relations with undeclared target_bindings:\n  " + "\n  ".join(offences)


def test_every_formula_binding_reference_resolves_to_a_declared_binding() -> None:
    """Formulas that reference a binding via {binding = "..."} must point at a declared binding."""
    modelo, _ = _modelo_100()
    offences: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        declared_bindings = {b.id for b in revision.bindings}
        for formula in revision.formulas:
            referenced: set[str] = set()
            _collect_binding_refs(formula.expression, referenced)
            unresolved = referenced - declared_bindings
            for ref in sorted(unresolved):
                offences.append(
                    f"{revision_id}: formula {formula.id!r} references undeclared binding {ref!r}"
                )
    assert not offences, "formulas referencing undeclared bindings:\n  " + "\n  ".join(offences)


def test_every_formula_parameter_reference_resolves_to_a_declared_parameter() -> None:
    """Formulas that reference a parameter via {parameter = "..."} must point at a declared parameter."""
    modelo, _ = _modelo_100()
    offences: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        declared = {p.id for p in revision.parameters}
        for formula in revision.formulas:
            referenced: set[str] = set()
            _collect_parameter_refs(formula.expression, referenced)
            unresolved = referenced - declared
            for ref in sorted(unresolved):
                offences.append(
                    f"{revision_id}: formula {formula.id!r} references undeclared parameter {ref!r}"
                )
    assert not offences, "formulas referencing undeclared parameters:\n  " + "\n  ".join(offences)


def _collect_binding_refs(expression, accumulator: set[str]) -> None:
    if expression is None:
        return
    binding = getattr(expression, "binding", None)
    if binding is not None:
        accumulator.add(binding)
    args = getattr(expression, "args", None)
    if args:
        for arg in args:
            _collect_binding_refs(arg, accumulator)


def _collect_parameter_refs(expression, accumulator: set[str]) -> None:
    if expression is None:
        return
    parameter = getattr(expression, "parameter", None)
    if parameter is not None:
        accumulator.add(parameter)
    args = getattr(expression, "args", None)
    if args:
        for arg in args:
            _collect_parameter_refs(arg, accumulator)
