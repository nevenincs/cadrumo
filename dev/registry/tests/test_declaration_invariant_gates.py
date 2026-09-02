"""Standing gates over the registry declaration invariants that currently hold.

A screen reports and exits 0. A gate refuses. These are the conditions the
screens measure that are clean across the whole shipped registry today, so a
regression in any of them is a defect introduced rather than debt inherited.

Each assertion here is an INVARIANT, never a count. The distinction matters and
the project's quality rule turns on it: a baseline ratchet freezes whatever
number happens to be true and calls a smaller number progress, which proves
nothing about the condition. What these gates assert is that a named class of
defect does not occur at all. Zero is the contract, not the high-water mark, so
there is no number to move and nothing to re-baseline when the corpus grows.

Conditions still carrying findings are deliberately NOT gated here. Gating them
would require a tolerance, a tolerance is a count, and a count is the ratchet
this project retired. They are gated by their own Step once their data is
corrected: the wire-type transitions once a transition table declares which
narrowings are legitimate, the grade contradictions once grade is earned from
its prerequisites, the provenance citations once parent consistency is decided,
the deadline declarations once the temporal contract lands, and the revision
names once they are corrected.

Detector teeth for every condition live in the owning screen's own test module,
where a representative defect is constructed and shown to be caught. A gate
that only ever sees a clean corpus proves nothing on its own; the pairing is
what makes it evidence.
"""

from __future__ import annotations

import pytest

from cadrumo.application.modelo.registry_discovery import registry_modelo_codes
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from dev.registry.analysis.casilla_id_grammar import screen_authority as grammar_screen
from dev.registry.analysis.continuity_integrity import screen_authority as continuity_screen
from dev.registry.analysis.export_ref_symmetry import screen_authority as export_ref_screen

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


@pytest.fixture(scope="module")
def modelo_ids() -> tuple[str, ...]:
    return tuple(sorted(str(code) for code in registry_modelo_codes()))


def test_every_declared_export_ref_is_carried_by_the_resolved_surface(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> None:
    """No casilla claims an export field the resolved layouts do not provide.

    The casilla-to-export-field edge is declared from both ends and load-time
    validation walks only the layout side. This gate walks the casilla side, so
    a casilla that starts claiming a field no layout carries fails here rather
    than validating silently.
    """
    findings = export_ref_screen(authority, modelo_ids)
    assert not findings, "casillas claim export fields the resolved surface does not carry: " + ", ".join(
        f"{item.modelo}/{item.revision}/{item.casilla_id}" for item in findings[:10]
    )


def test_every_casilla_identifier_falls_in_a_named_grammar(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> None:
    """No identifier in the shipped registry has an unnamed shape.

    The declared grammar set is closed and complete for the corpus as it
    stands. A new identifier shape is not a failure of this gate to be widened
    away; it is the signal that the set, and any contract written against it,
    no longer describes the registry.
    """
    uses = grammar_screen(authority, modelo_ids)
    offenders = {use.modelo: dict(use.counts)["unclassified"] for use in uses if "unclassified" in dict(use.counts)}
    assert not offenders, f"identifiers matching no named grammar: {offenders}"


def test_every_screen_module_is_enrolled_in_the_runner() -> None:
    """A screen that exists but is not run is indistinguishable from a clean condition.

    The runner enrolls screens by an explicit table rather than by naming
    convention, which is the right choice: discovery by convention hides a
    typo. The cost of an explicit table is that an author can forget to add a
    row, and this gate is what makes forgetting fail rather than pass quietly.
    """
    import pathlib

    from dev.registry.analysis.screens import SCREENS

    analysis = pathlib.Path(__file__).resolve().parent.parent / "analysis"
    defining = {
        path.stem
        for path in analysis.glob("*.py")
        if path.name != "screens.py" and "\ndef screen_authority(" in path.read_text(encoding="utf-8")
    }
    enrolled = {entry.name for entry in SCREENS}
    assert defining == enrolled, f"screens not enrolled in the runner: {sorted(defining - enrolled)}"


def test_no_continuity_chain_asserts_identity_across_two_grammars(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> None:
    """No chain claims one casilla is another whose identifier has a different shape.

    A grammar change inside a chain is not automatically wrong, but nothing
    declares which changes are legitimate, so today the honest contract is that
    none occurs. If a revision ever needs one, this gate is where that need
    becomes an explicit decision rather than a silent precedent.
    """
    crossing = [item for item in continuity_screen(authority, modelo_ids) if item.kind == "chain_crosses_grammar"]
    assert not crossing, f"continuity chains spanning identifier grammars: {[item.detail for item in crossing]}"


def test_every_continuity_evolution_names_a_chain_that_exists(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> None:
    """No evolution record describes a transition whose endpoints no casilla carries."""
    orphans = [item for item in continuity_screen(authority, modelo_ids) if item.kind == "evolution_without_members"]
    assert not orphans, f"evolutions naming chains no casilla carries: {[item.detail for item in orphans]}"


def test_the_readme_screen_table_lists_exactly_the_enrolled_screens() -> None:
    """The contributor README names every screen that runs, and no screen that does not.

    A table of tools is the first thing to rot, and a reader has no way to tell
    a documented screen that was deleted from one that simply never ran. This
    gate makes the README a checked surface rather than a claim.
    """
    import pathlib
    import re

    from dev.registry.analysis.screens import SCREENS

    readme = (pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"^\| `([a-z_]+)` \| ", readme, re.MULTILINE))
    enrolled = {entry.name for entry in SCREENS}
    assert documented == enrolled, (
        f"README documents screens that do not run: {sorted(documented - enrolled)}; "
        f"screens that run but are undocumented: {sorted(enrolled - documented)}"
    )


def test_every_symbol_the_contributor_readmes_name_still_resolves() -> None:
    """A dotted path written in a contributor README imports, module or attribute.

    The authoring READMEs point contributors at concrete functions and modules:
    the accessor every export coverage figure must come from, and the loaders
    the authored inputs are consumed by. A rename that leaves those names behind
    turns the guidance into a wrong instruction, and a reader following it finds
    nothing and has no way to tell whether the symbol moved or never existed.

    This walks the READMEs rather than a hand-kept list, so a newly documented
    symbol is covered by writing it down.
    """
    import importlib
    import pathlib
    import re

    registry_root = pathlib.Path(__file__).resolve().parent.parent
    readmes = [registry_root / "README.md", *sorted(registry_root.glob("*/README.md"))]
    documented: set[str] = set()
    for readme in readmes:
        if readme.is_file():
            documented.update(re.findall(r"`((?:cadrumo|dev)\.[A-Za-z0-9_.]+)`", readme.read_text(encoding="utf-8")))
    assert documented, "the contributor READMEs must name at least one symbol"

    unresolved: list[str] = []
    for dotted in sorted(documented):
        try:
            importlib.import_module(dotted)
            continue
        except ImportError:
            pass
        module_path, _, attribute = dotted.rpartition(".")
        try:
            if not hasattr(importlib.import_module(module_path), attribute):
                unresolved.append(dotted)
        except ImportError:
            unresolved.append(dotted)
    assert not unresolved, f"contributor READMEs name symbols that no longer resolve: {unresolved}"


def test_every_screen_searches_a_population_that_is_not_empty(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> None:
    """No screen reports a clean corpus because it looked at nothing.

    A screen that finds nothing is indistinguishable from a screen whose subject
    has been deleted, renamed out from under it, or filtered to nothing by a
    predicate that stopped matching. Both report zero findings and both look
    healthy. The enrolment gate above catches a screen that stops RUNNING; this
    one catches a screen that runs over an empty set.

    The check is deliberately on the population rather than on the findings.
    Several of these screens SHOULD report nothing, and gating their finding
    count would freeze a defect count as a contract. What must never be empty is
    the set of things they looked at.
    """
    from cadrumo.domain.calculations.registry.export import resolved_export_endpoints
    from dev.registry.analysis.casilla_id_grammar import screen_authority as grammar
    from dev.registry.analysis.continuity_integrity import continuity_census
    from dev.registry.analysis.wire_type_compatibility import screen_authority as wire_types

    populations: dict[str, int] = {
        "identifier grammar": sum(count for use in grammar(authority, modelo_ids) for _, count in use.counts),
        "wire type transitions": len(wire_types(authority, modelo_ids)),
        "continuity casillas": continuity_census(authority, modelo_ids).casillas,
        "resolved export endpoints": sum(
            len(resolved_export_endpoints(revision))
            for modelo_id in modelo_ids
            for revision in authority.modelo(modelo_id).revisions.values()
        ),
    }
    empty = sorted(name for name, size in populations.items() if not size)
    assert not empty, f"screens searching an empty population, so their silence proves nothing: {empty}"


def test_every_screen_module_has_a_test_module() -> None:
    """A screen with no test of its own has no proven detection.

    The gate module above states that detector teeth live in each screen's own
    test. That claim was untrue for one of nine screens for several days: it was
    enrolled in the runner, two of its conditions were gated as invariants, and
    nothing anywhere showed it could detect either. A gate over a clean corpus
    passes whether or not the screen behind it works.
    """
    import pathlib

    registry_root = pathlib.Path(__file__).resolve().parent.parent
    screens = {
        path.stem
        for path in (registry_root / "analysis").glob("*.py")
        if path.name != "screens.py" and "\ndef screen_authority(" in path.read_text(encoding="utf-8")
    }
    untested = sorted(name for name in screens if not (registry_root / "tests" / f"test_{name}.py").is_file())
    assert not untested, f"screens carrying no test module, so their detection is unproven: {untested}"


def test_every_enrolled_screen_runs_over_the_whole_corpus(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> None:
    """No screen raises, and each reports a count and what that count means.

    The gates above check that a screen is enrolled, documented and tested, and
    that a handful of populations are non-empty. None of them runs every screen
    over every modelo, so a screen that crashed on one revision would surface
    only when somebody ran the runner by hand. This closes that: the runner is
    the thing a maintainer is told to use, and it is now exercised.

    It asserts nothing about the findings. Several screens should report zero,
    several report thousands, and pinning either would freeze a defect count as
    a contract. What is asserted is that each screen completes and describes
    what it counted.
    """
    from dev.registry.analysis.screens import SCREENS, run_screens

    results = run_screens(authority, modelo_ids)
    assert len(results) == len(SCREENS)
    for name, count, meaning in results:
        assert count >= 0, f"{name} returned a negative count"
        assert meaning.strip(), f"{name} does not say what its count means"


def test_no_screen_reassembles_the_resolved_export_surface() -> None:
    """A screen asks for the resolved surface; it never rebuilds one.

    Three linkage paths reach a casilla on that surface, and a walk that knows
    only some of them under-reports it. Four separate published figures in this
    campaign were wrong for exactly that reason, each correction restoring one
    path the walk had not known about. The accessor exists so the walk is
    written once.

    The rule is enforced on the import rather than on the result, because a
    result cannot show whether it was reached correctly. A module reaching for
    the binding derivation directly is rebuilding the surface, whatever it does
    with it afterwards.
    """
    import pathlib

    analysis = pathlib.Path(__file__).resolve().parent.parent / "analysis"
    offenders = sorted(
        path.stem
        for path in analysis.glob("*.py")
        if "derive_export_layouts_from_bindings" in path.read_text(encoding="utf-8")
    )
    assert not offenders, (
        "these modules reach for the binding derivation instead of the resolved-surface accessor, "
        f"which is how four wrong figures were published: {offenders}"
    )


def test_running_every_screen_leaves_the_shipped_registry_untouched(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> None:
    """The screens read the registry and never write to it.

    Every screen is documented as reporting rather than gating, and none has any
    reason to write. That is a property worth proving rather than trusting: a
    screen constructing a defect in place to measure it, or a helper caching
    something beside the data, would be mutating filing data from a read path
    and nothing else here would notice.

    The check compares a fingerprint of every file under the shipped registry
    before and after the whole suite runs. It fingerprints path, size and
    modification time rather than content, which is enough to catch a write and
    cheap enough to run over the whole tree.
    """
    import os

    from cadrumo.core.resources.bundled_data import bundled_path
    from dev.registry.analysis.screens import run_screens

    def fingerprint() -> dict[str, tuple[int, int]]:
        root = bundled_path("registry")
        seen: dict[str, tuple[int, int]] = {}
        for directory, _, names in os.walk(root):
            for name in names:
                path = os.path.join(directory, name)
                stat = os.stat(path)
                seen[path] = (stat.st_size, stat.st_mtime_ns)
        return seen

    before = fingerprint()
    assert before, "the shipped registry must contain files to fingerprint"
    run_screens(authority, modelo_ids)
    after = fingerprint()

    changed = sorted(path for path in before if path in after and before[path] != after[path])
    assert not changed, f"screens modified shipped registry files: {changed[:5]}"
    assert sorted(before) == sorted(after), "screens added or removed shipped registry files"


def test_every_kind_a_screen_emits_is_named_in_its_own_docstring(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> None:
    """A reader who sees ``kind=x`` in a screen's output can find x explained in that screen.

    The kind token is the whole of what a row says about which condition it
    reports; the rest of the row is coordinates. So a kind the owning docstring
    never names is a row nobody can act on, and that is a state this suite has
    twice found live: two screens grew a condition whose docstring was never
    extended, one of them the condition surfacing the corpus's only known
    filing-correctness defect.

    The kinds are collected by running the screens rather than by reading the
    source, because they are assigned in several shapes -- a keyword argument, a
    local variable, a typed enum -- and a static extractor silently under-reads
    every shape it does not know. Running them reads exactly what a maintainer
    would see. Kinds that occur only under a constructed defect are not covered
    here; they are covered by the detector test that constructs them.
    """
    import importlib

    from dev.registry.analysis.screens import SCREENS

    observed: set[tuple[str, str]] = set()
    undocumented: list[str] = []
    for entry in SCREENS:
        module = importlib.import_module(f"dev.registry.analysis.{entry.name}")
        doc = module.__doc__ or ""
        for finding in entry.run(authority, modelo_ids):
            kind = getattr(finding, "kind", None)
            if not isinstance(kind, str):
                continue
            observed.add((entry.name, kind))
            if kind not in doc:
                undocumented.append(f"{entry.name} emits {kind!r} but its docstring never names it")

    assert observed, "no enrolled screen emitted a kind, so this gate checked nothing"
    assert not undocumented, "\n".join(sorted(set(undocumented)))
