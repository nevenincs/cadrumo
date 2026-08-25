"""The scenario contract for a casilla the registry produces rather than takes.

A casilla declared ``input_kind = "bound"`` carries a value the engine PRODUCES:
substrate is aggregated, a binding is resolved, and the result lands in the box.
A scenario that supplies one as an ``inputs`` entry hand-types that value and
steps over both links, so whatever it goes on to assert says nothing about how
the casilla is populated — while its name, its evidence locator and any oracle
grounding declared for it keep reading as end-to-end coverage.

That is not hypothetical. It shipped: the Modelo 100 2024 estimación-directa
worked example hand-typed NINE bound casillas — the ingresos leg and the whole
ledger-expense leg — while presenting as a grounded oracle for that chain. It
was found by accident, and nothing would have found the next one.

Why the check lives in the runner, not in a scan of the sources
--------------------------------------------------------------

The obvious shape is a static scan of the test tree for scenarios whose
``inputs`` include a bound casilla. That was built and measured first: it
resolved thirteen of twenty-six scenario constructions. The other thirteen pass
their ``inputs`` through factory parameters or indirection the scan cannot
follow, and it reported them clean — which is worse than not checking, because
a gate that lies about its own coverage is trusted. Extending it to follow
factory parameters back to their call sites recovered one module and left
thirteen sites blind.

:func:`run_registry_calculation_scenario` is the one point every scenario
passes through, and it already holds the resolved revision beside the inputs.
The check there is exact and complete by construction, with no parsing and no
blind sites.

Why two declaration channels
----------------------------

The harness has a single channel for casilla values, so a bound value the
caller obtained by RUNNING the aggregation and the binding resolver arrives
indistinguishable from one typed into a literal. Collapsing both into one
"hand-typed" declaration would force the honest case to record the precise
opposite of what happened, in the field a later reader would trust. So the two
opposite claims carry two names, and a casilla may satisfy exactly one.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core import CasillaId, scan_directory, validated_casilla_id
from .....tests.registry_tree import bundled_registry_tree
from .. import ModeloRevision, build_snapshot
from ..errors import RegistryValidationError
from .._schema_input_kind import InputKind
from ._registry_schema_support import _committed_modelo
from ._scenarios import bound_casilla_ids, run_registry_calculation_scenario
from .test_m100_2024_estimacion_directa_manual_worked_example import (
    _REGISTRY_ROOT,
    _SOURCE_ROOT,
)
from .test_m100_2024_estimacion_directa_manual_worked_example import (
    _scenario as _m100_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Anti-vacuity floor for the one revision every case below builds on. If the
#: M100 2024 revision ever declared no bound casillas, every refusal case would
#: pass by refusing nothing and the contract would read as enforced while
#: enforcing nothing. Nine are known bound today (the ingresos leg plus the
#: eight ledger-expense boxes); the floor sits below that so ordinary registry
#: growth does not trip it, and far enough above zero to catch the surface
#: vanishing.
_MINIMUM_BOUND_CASILLAS_ON_M100_2024 = 5

#: Anti-vacuity floors for the registry-wide surface this contract governs. One
#: revision happening to carry bound casillas would not establish that the
#: contract has anything to protect across the tree. Measured at 34 revisions
#: across 19 modelos; the floors sit below that so ordinary registry growth and
#: revision retirement do not trip them, and far enough above zero to catch the
#: surface vanishing or the traversal being mis-rooted.
_MINIMUM_REVISIONS_WITH_BOUND_CASILLAS = 20
_MINIMUM_MODELOS_WITH_BOUND_CASILLAS = 10

#: Anti-vacuity floors for the population the runner actually inspects. The two
#: floors above pin the REGISTRY surface; these pin the SCENARIO surface, and
#: they are the sharper pair. A refactor that routed scenarios around
#: :func:`run_registry_calculation_scenario` would leave the registry floors
#: untouched and satisfied while the contract inspected nothing at all — the
#: failure mode where a gate reports clean because it stopped looking.
#:
#: Measured at 26 constructions across 17 modules, spanning six revisions.
_MINIMUM_SCENARIO_CONSTRUCTIONS = 20
_MINIMUM_REVISIONS_UNDER_SCENARIO = 4

#: The scenario harness targets Modelo 100 exclusively today — all 26
#: constructions resolve to a `100/<year>` pair. So a "spans more than one
#: modelo" floor cannot be asserted without inventing a passing variant of a
#: property the tree does not have. The revision span stands in for it, and the
#: absence is recorded here rather than papered over: if the harness ever grows
#: a second modelo, a modelo-span floor becomes the stronger check and should
#: replace this note.
_SCENARIO_MODELOS_TODAY = frozenset({"100"})


def _m100_2024_revision() -> ModeloRevision:
    modelo, catalogues = _committed_modelo("100")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=_SOURCE_ROOT,
        filing_year=2024,
        period="0A",
    ).revision


def _run(scenario) -> None:
    run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=_SOURCE_ROOT)


def _declared_scenario():
    """A real, currently-passing scenario carrying its bound-casilla declarations."""
    return _m100_scenario(
        es_normal=Decimal("0"),
        expected_0226=Decimal("58100.00"),
        scenario_id="bound-input-contract-baseline",
    )


def test_the_bound_surface_this_contract_protects_actually_exists() -> None:
    """Anti-vacuity: the revision under test declares a real bound surface.

    Every refusal case below asserts that supplying a bound casilla is refused.
    All of them would pass vacuously against a revision with no bound casillas
    at all, because the intersection driving the refusal would be empty and the
    scenario would simply run. This pins the surface rather than assuming it.
    """
    revision = _m100_2024_revision()

    bound = bound_casilla_ids(revision)

    assert len(bound) >= _MINIMUM_BOUND_CASILLAS_ON_M100_2024, (
        f"M100 2024 declares only {len(bound)} bound casillas; the bound surface this contract governs has "
        "shrunk or the revision is mis-resolved, and every refusal case below would pass by refusing nothing"
    )
    assert bound == {casilla.id for casilla in revision.casillas if casilla.input_kind is InputKind.BOUND}, (
        "bound_casilla_ids must read the classification off the revision, not from anywhere else"
    )


def test_the_bound_surface_spans_the_registry_not_one_revision() -> None:
    """Anti-vacuity, registry-wide: many modelos and revisions carry bound casillas.

    Establishes that this contract governs a real cross-registry surface rather
    than one revision's local quirk, so a future reader can tell the difference
    between "the check found nothing" and "there was nothing to find".
    """
    modelos, _catalogues = bundled_registry_tree()
    assert modelos, "the registry tree yielded no modelos"

    revisions_with_bound = 0
    modelos_with_bound: set[str] = set()
    for modelo in modelos:
        for revision in modelo.revisions.values():
            if any(casilla.input_kind is InputKind.BOUND for casilla in revision.casillas):
                revisions_with_bound += 1
                modelos_with_bound.add(modelo.id)

    assert revisions_with_bound >= _MINIMUM_REVISIONS_WITH_BOUND_CASILLAS, (
        f"only {revisions_with_bound} revisions declare a bound casilla; the surface this contract governs has "
        "collapsed or the traversal is mis-rooted"
    )
    assert len(modelos_with_bound) >= _MINIMUM_MODELOS_WITH_BOUND_CASILLAS, (
        f"only {len(modelos_with_bound)} modelos declare a bound casilla anywhere"
    )


def _scenario_module_facts() -> tuple[dict[Path, int], set[Path], set[tuple[str, str]]]:
    """Walk the test tree for scenario construction, runner calls and targets.

    Static analysis is the right instrument HERE, and the wrong one for the
    inputs check the runner performs. The difference is measured rather than
    assumed: every one of the twenty-six constructions resolves its ``modelo``
    and ``revision`` from a literal, so target reading is exact, while ``inputs``
    resolution reached only half the sites. This walk reads only what it can
    read exactly.
    """
    package_root = Path(__file__).resolve().parents[4]
    builders: dict[Path, int] = {}
    runners: set[Path] = set()
    targets: set[tuple[str, str]] = set()
    for path in scan_directory(package_root, pattern="*.py", recursive=True):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        constructions = 0
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id == "run_registry_calculation_scenario":
                runners.add(path)
            if node.func.id != "RegistryCalculationScenario":
                continue
            constructions += 1
            keywords = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg}
            modelo, revision = keywords.get("modelo"), keywords.get("revision")
            if isinstance(modelo, ast.Constant) and isinstance(revision, ast.Constant):
                targets.add((str(modelo.value), str(revision.value)))
        if constructions:
            builders[path] = constructions
    return builders, runners, targets


def test_the_scenario_population_the_runner_inspects_has_not_collapsed() -> None:
    """Anti-vacuity: scenarios still exist, in number, across several revisions.

    Every refusal case in this module proves the contract fires when a scenario
    reaches the runner. None of them would notice if scenarios stopped reaching
    it. This pins the population instead, so a refactor that emptied or bypassed
    the harness fails here rather than reporting a clean contract over nothing.
    """
    builders, _runners, targets = _scenario_module_facts()

    assert sum(builders.values()) >= _MINIMUM_SCENARIO_CONSTRUCTIONS, (
        f"only {sum(builders.values())} scenario constructions found across {len(builders)} modules; the "
        "population this contract governs has collapsed or the walk is mis-rooted"
    )
    assert targets, "no scenario resolved a literal (modelo, revision) target"
    revisions = {revision for _modelo, revision in targets}
    assert len(revisions) >= _MINIMUM_REVISIONS_UNDER_SCENARIO, (
        f"scenarios span only {sorted(revisions)}; the contract is being exercised against too narrow a slice "
        "of the registry to mean much"
    )
    assert {modelo for modelo, _revision in targets} == _SCENARIO_MODELOS_TODAY, (
        "the scenario harness gained or lost a modelo; a modelo-span floor is now available (or the recorded "
        "single-modelo fact is stale) and this module's anti-vacuity note needs revisiting"
    )


def test_every_module_building_scenarios_is_reachable_from_the_runner() -> None:
    """No scenario may be built on a path that never reaches the runner.

    The contract lives in :func:`run_registry_calculation_scenario`, so a
    scenario executed some other way is outside it entirely — the exact bypass
    that would make every case in this module pass while real scenarios went
    unchecked.

    A module may legitimately BUILD scenarios without running them: the shared
    fixture module does, and the modules that consume it run them. So the
    property asserted is reachability — every builder either calls the runner
    or is imported by something that does — rather than an allowlist naming the
    one exception, which would need editing every time the split changed and
    would rot the way the bypass it guards rotted.
    """
    builders, runners, _targets = _scenario_module_facts()
    assert builders, "no module builds a registry calculation scenario"
    assert runners, "no module calls the scenario runner"

    runner_imports: set[str] = set()
    for path in runners:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                runner_imports.add(node.module.lstrip("."))
            elif isinstance(node, ast.Import):
                runner_imports.update(alias.name for alias in node.names)

    unreachable = sorted(path.name for path in builders if path not in runners and path.stem not in runner_imports)
    assert not unreachable, (
        f"these modules build registry scenarios but neither run them nor are imported by a module that does, "
        f"so their scenarios never reach the bound-input contract: {unreachable}"
    )


def test_a_real_scenario_with_its_declarations_intact_runs() -> None:
    """The contract admits the honest case rather than blocking every scenario.

    A refusal that fired on everything would be indistinguishable from a broken
    runner, and the cases below would prove nothing about discrimination.
    """
    _run(_declared_scenario())


def test_stripping_the_declarations_from_that_same_scenario_refuses() -> None:
    """The discriminating case: the ONLY difference is the declaration.

    Same scenario, same inputs, same expected outputs — the declarations
    removed. If this passed, the contract would be inert on exactly the defect
    it exists to catch, and the case above would be passing for an unrelated
    reason.
    """
    stripped = _declared_scenario().model_copy(
        update={"hand_typed_bound_casillas": {}, "chain_resolved_bound_casillas": {}},
    )

    with pytest.raises(RegistryValidationError) as excinfo:
        _run(stripped)

    message = str(excinfo.value)
    assert "supplies casillas the registry declares bound" in message
    assert "0171" in message, "the refusal must name the offending casilla, not merely report that one exists"
    assert "renta-2024-ledger-income-0171" in message, (
        "the refusal must name the binding that was stepped over, so the reader can find what to drive instead"
    )


def test_declaring_only_some_of_the_bound_inputs_still_refuses() -> None:
    """A partial declaration is refused, naming exactly the ones left undeclared.

    The failure mode a per-casilla declaration invites: declare the casilla you
    were thinking about and leave the rest. The refusal must be per casilla,
    not a single boolean about the scenario.
    """
    baseline = _declared_scenario()
    kept: CasillaId = validated_casilla_id("0171", surface="kept")
    partial = baseline.model_copy(
        update={
            "hand_typed_bound_casillas": {},
            "chain_resolved_bound_casillas": {kept: baseline.chain_resolved_bound_casillas.get(kept, "kept")}
            if kept in baseline.inputs
            else {},
        },
    )

    with pytest.raises(RegistryValidationError) as excinfo:
        _run(partial)

    message = str(excinfo.value)
    assert "0186" in message, "an undeclared ledger-expense casilla must still be named"


def test_a_declaration_for_a_casilla_the_registry_does_not_bind_refuses() -> None:
    """A stale excuse is refused rather than silently tolerated.

    The other direction, and the one that rots: a casilla stops being bound,
    the declaration outlives it, and the next reader is told a binding is being
    stepped over when none exists. 0181 is an ordinary input on this revision.
    """
    not_bound: CasillaId = validated_casilla_id("0181", surface="not_bound")
    baseline = _declared_scenario()
    assert not_bound in baseline.inputs, "the case needs a supplied casilla that is NOT bound"
    assert not_bound not in bound_casilla_ids(_m100_2024_revision())

    stale = baseline.model_copy(
        update={
            "hand_typed_bound_casillas": {**baseline.hand_typed_bound_casillas, not_bound: "stale excuse"},
        },
    )

    with pytest.raises(RegistryValidationError) as excinfo:
        _run(stale)

    assert "does not declare bound" in str(excinfo.value)
    assert "0181" in str(excinfo.value)


def test_an_empty_reason_is_refused_at_construction() -> None:
    """A blank reason is the silence the declaration exists to prevent.

    Refused when the scenario is built rather than when it runs, because an
    empty string satisfies "declared" while carrying none of the information
    the declaration is for.
    """
    baseline = _declared_scenario()
    blank = {casilla_id: "   " for casilla_id in baseline.hand_typed_bound_casillas}

    payload = baseline.model_dump()
    payload["hand_typed_bound_casillas"] = blank

    with pytest.raises(ValidationError, match="no stated reason"):
        type(baseline).model_validate(payload)


def test_a_casilla_cannot_be_both_hand_typed_and_chain_resolved() -> None:
    """The two channels carry opposite claims, so no casilla may satisfy both.

    Without this, a scenario could file the same casilla under both and satisfy
    whichever a reader consulted.
    """
    baseline = _declared_scenario()
    contested: CasillaId = validated_casilla_id("0186", surface="contested")
    payload = baseline.model_dump()
    payload["hand_typed_bound_casillas"] = {contested: "hand typed"}
    payload["chain_resolved_bound_casillas"] = {contested: "chain resolved"}

    with pytest.raises(ValidationError, match="BOTH hand-typed and chain-resolved"):
        type(baseline).model_validate(payload)


def test_declaring_a_casilla_the_scenario_does_not_supply_is_refused() -> None:
    """A declaration must describe an input that exists.

    Otherwise the map drifts into a wish list, and a reader counting
    declarations would overstate how much of the scenario is accounted for.
    """
    baseline = _declared_scenario()
    absent: CasillaId = validated_casilla_id("9999", surface="absent")
    payload = baseline.model_dump()
    payload["hand_typed_bound_casillas"] = {absent: "not supplied at all"}

    with pytest.raises(ValidationError, match="does not supply as inputs"):
        type(baseline).model_validate(payload)
