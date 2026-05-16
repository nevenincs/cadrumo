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

import ast
from functools import lru_cache

import pytest

from aeat.core.resources import bundled_path

from . import load_registry_tree
from ._runtime_graph import expression_binding_refs, expression_parameter_refs

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


_TOP_LEVEL_CHAIN_TARGETS: frozenset[str] = frozenset(
    {
        # Mínimo personal y familiar
        "0519",
        "0520",
        "0521",
        "0522",
        "0523",
        "0524",
        # Base imponible / liquidable
        "0432",
        "0435",
        "0460",
        "0500",
        "0510",
        # Cuota íntegra
        "0532",
        "0533",
        "0545",
        "0546",
        # Cuota líquida + incrementada
        "0570",
        "0571",
        "0585",
        "0586",
    }
)

_SUPPORTED_REVISIONS: tuple[str, ...] = ("2020", "2021", "2022", "2023", "2024", "2025")


def _modelo_100():
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
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
        formula_feeding = {b.id for b in revision.bindings if b.source in ("manual_input", "previous_filing")}
        referenced: set[str] = set()
        for formula in revision.formulas:
            referenced.update(expression_binding_refs(formula.expression))
        for relation in revision.relations:
            target_binding = getattr(relation, "target_binding", None)
            if target_binding:
                referenced.add(target_binding)
        orphans = formula_feeding - referenced
        for orphan in sorted(orphans):
            offences.append(f"{revision_id}: orphan formula-feeding binding {orphan!r}")
    assert not offences, "orphan formula-feeding bindings detected:\n  " + "\n  ".join(offences)


def test_no_orphan_parameters_in_any_revision() -> None:
    """Every parameter declared in a revision must be referenced.

    A parameter counts as referenced when it is consumed either by a
    formula expression tree (``{ parameter = "..." }`` arg) or by an
    in-tree ``read_parameter("100", revision, parameter_id, ...)`` call
    in :mod:`aeat.domain.*` Python source. The latter is the
    out-of-formula consumption pattern used by the rental tier resolver
    and any future cross-module readers.

    A small allow-list (:data:`_PRE_STAGED_PARAMETERS`) covers
    parameters whose data is authoritative on disk (IRPF state-scale
    brackets) but whose consuming formula has not yet landed. Removing
    a parameter from that list is the gate that future formula work
    must clear when it begins to consume the data.
    """
    modelo, _ = _modelo_100()
    cross_module_refs = _read_parameter_refs_for_modelo("100")
    offences: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        declared = {p.id for p in revision.parameters}
        referenced: set[str] = set()
        for formula in revision.formulas:
            referenced.update(expression_parameter_refs(formula.expression))
        referenced |= cross_module_refs
        referenced |= _PRE_STAGED_PARAMETERS
        orphans = declared - referenced
        for orphan in sorted(orphans):
            offences.append(f"{revision_id}: orphan parameter {orphan!r}")
    assert not offences, "orphan parameters detected:\n  " + "\n  ".join(offences)


#: Parameters that are declared in the registry with authoritative tax
#: data (e.g. IRPF state-level progressive bracket tables, Ley 19/1994
#: RIC caps, Ley 19/1994 ZEC reduced rate, LIRPF arts. 86-89 attribution
#: pass-through, RD-Ley estimación objetiva indices) but whose consuming
#: formula has not yet been wired into the registry. Removing an entry
#: from this set is the gate that the corresponding formula work must
#: clear before this allow-list shrinks. The data is preserved on disk
#: so future formula work can land without re-entering authoritative
#: bracket values.
#:
#: Each entry below carries a one-line rationale and a pointer at the
#: tracking task that will land the consuming formula:
#:
#: * RIC trio (Ley 19/1994 art-27) — three legal-authority parameters
#:   (reduction rate cap 80 %, materialization window 3 years, holding
#:   period 5 years) cited by the 26 RIC casillas in the
#:   ``reserva_inversiones_canarias_res`` section, but the aggregation
#:   formula that applies the cap to the dotación total has not landed.
#:   See task #46 (Wire orphan RIC parameters).
#: * ZEC reduced rate (Ley 19/1994 art-43+) — Canarias special economic
#:   zone reduced corporate-tax rate cited by ZEC-eligible casillas;
#:   IRPF integration formula pending alongside the MM-7 Canarias work
#:   slice referenced by the Ley 19/1994 corpus commit.
#: * Estimación objetiva reducción general rate + corrector pequeña
#:   dimensión (Orden HFP estimación objetiva annual orders) —
#:   parameters consumed by the EO computation outside the registry
#:   evaluator. The values are authoritative for the EO module but the
#:   in-registry formula path is deferred until EO is brought under the
#:   formula evaluator.
#: * Atribución de rentas pass-through 100 % (LIRPF arts. 86-89) —
#:   parameter encodes the legal 100 % pass-through rate but the
#:   modelo-184 cross-modelo binding already returns the full attributed
#:   amount at casilla 1577 (``input_kind = "bound"``). The parameter
#:   exists for legal citation; turning it into a real consumer requires
#:   converting 1577 to ``input_kind = "computed"`` with an
#:   ``op = "percent"`` formula, which is a schema-level change tracked
#:   by task #47.
_PRE_STAGED_PARAMETERS: frozenset[str] = frozenset(
    {
        "renta-2025-ric-reduccion-rate-maximo",
        "renta-2025-ric-materializacion-plazo-anos",
        "renta-2025-ric-mantenimiento-plazo-anos",
        "renta-2025-zec-tipo-gravamen-reducido",
        "renta-2025-estimacion-objetiva-reduccion-general-rate",
        "renta-2025-estimacion-objetiva-indice-corrector-empresas-pequena-dimension-rate",
        "renta-2025-atribucion-rentas-rate-pass-through",
    }
)


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
            referenced.update(expression_binding_refs(formula.expression))
            unresolved = referenced - declared_bindings
            for ref in sorted(unresolved):
                offences.append(f"{revision_id}: formula {formula.id!r} references undeclared binding {ref!r}")
    assert not offences, "formulas referencing undeclared bindings:\n  " + "\n  ".join(offences)


def test_every_formula_parameter_reference_resolves_to_a_declared_parameter() -> None:
    """Formulas that reference a parameter via {parameter = "..."} must point at a declared parameter."""
    modelo, _ = _modelo_100()
    offences: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        declared = {p.id for p in revision.parameters}
        for formula in revision.formulas:
            referenced: set[str] = set()
            referenced.update(expression_parameter_refs(formula.expression))
            unresolved = referenced - declared
            for ref in sorted(unresolved):
                offences.append(f"{revision_id}: formula {formula.id!r} references undeclared parameter {ref!r}")
    assert not offences, "formulas referencing undeclared parameters:\n  " + "\n  ".join(offences)


@lru_cache(maxsize=8)
def _read_parameter_refs_for_modelo(modelo_id: str) -> frozenset[str]:
    """Return every parameter id consumed via ``read_parameter`` for ``modelo_id``.

    The orphan-detection test treats a parameter as referenced when
    either (a) a formula expression tree consumes it via
    ``{ parameter = "..." }`` or (b) Python source under
    ``src/aeat/domain/`` calls
    ``read_parameter(modelo_id, <revision>, <parameter_id>, ...)``.
    Branch (b) covers the rental tier resolver and any other
    cross-module reader that drives the registry's parameter index
    outside the formula evaluator.

    The scan walks the AST of every ``.py`` file under
    ``src/aeat/domain/`` and harvests:

    - constant string literals passed as the third positional argument
      to a ``read_parameter`` call whose first positional argument is
      ``modelo_id`` (or any other constant; constants are filtered to
      the requested modelo at the call site below);
    - f-strings whose template substitutes the literal ``period_year``
      placeholder. The four-digit year supported by the registry is
      iterated (2020-2030) and each substitution is added to the set,
      so the test can identify references to year-keyed parameter ids
      (e.g. ``f"renta-{period_year}-rental-prior-rent-rebaja-threshold"``).

    Calls whose arguments are not statically analysable (dynamic
    parameter ids built from variables) are ignored — those would have
    to register the orphan via the formula tree to satisfy the gate.
    """
    refs: set[str] = set()
    domain_root = PROJECT_ROOT / "src" / "aeat" / "domain"
    for path in domain_root.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name):
                func_name = func.id
            elif isinstance(func, ast.Attribute):
                func_name = func.attr
            else:
                continue
            if func_name != "read_parameter":
                continue
            if len(node.args) < 3:
                continue
            modelo_arg = node.args[0]
            if not (isinstance(modelo_arg, ast.Constant) and modelo_arg.value == modelo_id):
                continue
            param_arg = node.args[2]
            for resolved in _expand_parameter_id_node(param_arg):
                refs.add(resolved)
    return frozenset(refs)


def _expand_parameter_id_node(node: ast.expr) -> tuple[str, ...]:
    """Resolve a parameter-id AST node into the set of ids it could match.

    Constant strings expand to themselves. F-strings expand into the
    Cartesian product of every formatted placeholder against a small
    static substitution table — see :data:`_FSTRING_PLACEHOLDER_VALUES`.
    Placeholders not in the table render as ``"{}"`` so the resulting
    template no longer matches any registered parameter id; that path
    cleanly drops out of the cross-module reference set instead of
    silently widening it.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return (node.value,)
    if not isinstance(node, ast.JoinedStr):
        return ()
    static_segments: list[str] = []
    placeholder_names: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            static_segments.append(value.value)
            static_segments.append("\x00")  # sentinel: no placeholder here
        elif isinstance(value, ast.FormattedValue):
            inner = value.value
            if isinstance(inner, ast.Name):
                placeholder_names.append(inner.id)
            else:
                placeholder_names.append("__unknown__")
            static_segments.append("\x01")  # sentinel: placeholder here
        else:
            placeholder_names.append("__unknown__")
            static_segments.append("\x01")
    if not placeholder_names:
        return ("".join(s for s in static_segments if s != "\x00"),)
    placeholder_value_sets: list[tuple[str, ...]] = [
        _FSTRING_PLACEHOLDER_VALUES.get(name, ()) for name in placeholder_names
    ]
    if any(not values for values in placeholder_value_sets):
        return ()
    results: list[str] = []
    from itertools import product as _product

    for combo in _product(*placeholder_value_sets):
        rendered: list[str] = []
        combo_iter = iter(combo)
        for segment in static_segments:
            if segment == "\x00":
                continue
            if segment == "\x01":
                rendered.append(next(combo_iter))
            else:
                rendered.append(segment)
        results.append("".join(rendered))
    return tuple(results)


#: Static substitution table for f-string placeholder names that the
#: orphan-detection scan can resolve. The entries cover the rental tier
#: resolver and any other consumer whose parameter id is built from a
#: small closed set of Python locals; new placeholder names that appear
#: in future ``read_parameter`` calls must be registered here.
_FSTRING_PLACEHOLDER_VALUES: dict[str, tuple[str, ...]] = {
    "period_year": tuple(str(year) for year in range(2020, 2031)),
    "tier_id": ("tier-50", "tier-60", "tier-70", "tier-90"),
}
