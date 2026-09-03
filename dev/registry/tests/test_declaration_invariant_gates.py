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

import collections
import pathlib
from collections.abc import Iterable
from typing import Final

import pytest

from cadrumo.application.modelo.registry_discovery import registry_modelo_codes
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..analysis.casilla_id_grammar import screen_authority as grammar_screen
from ..analysis.continuity_integrity import screen_authority as continuity_screen
from ..analysis.export_ref_symmetry import screen_authority as export_ref_screen

_BINDING_DERIVATION = "derive_export_layouts_from_bindings"

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Named once per module, as this tree requires, rather than repeated at each
#: read site where a typo would be a silent decode change.
_UTF_8: Final[str] = "utf-8"


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
    from ..analysis.screens import CORPUS_SCREENS, SCREENS, screen_module_names

    # The walk is the analysis package's own, not a copy kept here. Five gates
    # each carried their own, every one written when only `screen_authority`
    # existed, and every one silently stopped covering a whole class of screen
    # the day `screen_corpus` appeared. One declaration widens them together.
    defining = set(screen_module_names())
    # Both tables. A corpus screen is a screen a reader must be able to find,
    # and documenting only the authority ones would leave two undiscoverable.
    enrolled = {entry.name for entry in SCREENS} | {entry.name for entry in CORPUS_SCREENS}
    assert defining == enrolled, (
        f"screens not enrolled in a runner table: {sorted(defining - enrolled)}; "
        f"enrolled but no longer defining a screen: {sorted(enrolled - defining)}"
    )


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

    from ..analysis.screens import CORPUS_SCREENS, SCREENS

    readme = (pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text(encoding=_UTF_8)
    documented = set(re.findall(r"^\| `([a-z_]+)` \| ", readme, re.MULTILINE))
    # Both tables. A corpus screen is a screen a reader must be able to find,
    # and documenting only the authority ones would leave two undiscoverable.
    enrolled = {entry.name for entry in SCREENS} | {entry.name for entry in CORPUS_SCREENS}
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
            documented.update(re.findall(r"`((?:cadrumo|dev)\.[A-Za-z0-9_.]+)`", readme.read_text(encoding=_UTF_8)))
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

    It covers the populations that can be named as a count, listed below, and
    not one per screen: several screens share a population and a few have none
    separable from the authority itself. The gate's name says "every screen" and
    its body checks a handful, which is a claim wider than the evidence - said
    here rather than left for a reader to discover, because the same overclaim
    in a screen's own docstring is a finding this campaign has recorded twice.
    The design-transcription row is the one that matters most for being easy to
    lose: it is a filesystem walk, and a corpus moved or renamed would return an
    empty tuple, which reads exactly like a corpus with nothing to report.
    """
    from cadrumo.domain.calculations.registry.export import resolved_export_endpoints

    from ..analysis.casilla_id_grammar import screen_authority as grammar
    from ..analysis.continuity_integrity import continuity_census
    from ..analysis.footnote_pointer_notes import sheet_note_definitions
    from ..analysis.note_label_scope import transcription_paths
    from ..analysis.wire_type_compatibility import screen_authority as wire_types

    transcriptions = transcription_paths()

    populations: dict[str, int] = {
        "identifier grammar": sum(count for use in grammar(authority, modelo_ids) for _, count in use.counts),
        "wire type transitions": len(wire_types(authority, modelo_ids)),
        "continuity casillas": continuity_census(authority, modelo_ids).casillas,
        "resolved export endpoints": sum(
            len(resolved_export_endpoints(revision))
            for modelo_id in modelo_ids
            for revision in authority.modelo(modelo_id).revisions.values()
        ),
        "design transcriptions": len(transcriptions),
        # Not merely that files were found, but that they parse into the notes
        # the corpus screens read. A transcription set that loaded and yielded
        # no note at all would leave both corpus screens silent and healthy.
        "sheets defining a note": sum(
            len(sheet_note_definitions(path.read_text(encoding=_UTF_8))) for path in transcriptions
        ),
    }
    empty = sorted(name for name, size in populations.items() if not size)
    assert not empty, f"screens searching an empty population, so their silence proves nothing: {empty}"


def test_the_runners_between_them_run_every_enrolled_screen() -> None:
    """No enrolled screen is left without a runner that executes it.

    Enrolment and execution are separate facts, and the gap between them is
    where this suite has repeatedly lost coverage: a table gains a row, a runner
    is written for one table, and a gate asserts against that runner's table.
    Everything passes and a whole class of screen goes unrun.

    This closes the gap at its narrowest point. The names the runners actually
    emit must equal the names enrolled, so a third table added without a runner
    fails here, and a runner that silently stops emitting a screen fails here
    too. It asserts names rather than counts, because two tables of the same
    size can still disagree about which screens they hold.

    Run for the names only. What the screens FIND is asserted by the whole-corpus
    gate, and duplicating it here would double the slowest work in the suite to
    check something already checked.
    """
    from ..analysis.screens import (
        CORPUS_SCREENS,
        SCREENS,
        run_corpus_screens,
        screen_module_names,
    )

    enrolled = {entry.name for entry in SCREENS} | {entry.name for entry in CORPUS_SCREENS}
    assert enrolled == set(screen_module_names()), "enrolment and the module walk disagree"

    # The corpus runner is cheap enough to execute; the authority runner needs
    # the built authority, so its names are taken from the table it iterates -
    # which is exactly what `run_screens` does, and the whole-corpus gate proves
    # it executes them.
    emitted = {name for name, _, _ in run_corpus_screens()} | {entry.name for entry in SCREENS}
    assert emitted == enrolled, (
        f"enrolled but no runner emits them: {sorted(enrolled - emitted)}; "
        f"emitted by a runner but not enrolled: {sorted(emitted - enrolled)}"
    )


def test_every_screen_module_has_a_test_module() -> None:
    """A screen with no test of its own has no proven detection.

    The gate module above states that detector teeth live in each screen's own
    test. That claim was untrue for one of nine screens for several days: it was
    enrolled in the runner, two of its conditions were gated as invariants, and
    nothing anywhere showed it could detect either. A gate over a clean corpus
    passes whether or not the screen behind it works.
    """
    import pathlib

    from ..analysis.screens import screen_module_names

    registry_root = pathlib.Path(__file__).resolve().parent.parent
    # The shared walk, so a screen presenting either entry point is required to
    # carry a test. This gate kept its own copy looking for `screen_authority`
    # alone, and two corpus screens passed it without being seen.
    screens = set(screen_module_names())
    untested = sorted(name for name in screens if not (registry_root / "tests" / f"test_{name}.py").is_file())

    # The discovered set must be proved non-empty before its emptiness means
    # anything: a moved analysis package would leave `screens` empty and this
    # assertion would pass having checked no screen at all.
    assert screens, "the analysis package walk found no screen module, so this gate checked nothing"
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
    from ..analysis.screens import CORPUS_SCREENS, SCREENS, run_corpus_screens, run_screens

    # Both runners. Asserting against the authority table alone left the corpus
    # screens unexercised by the gate whose whole purpose is that a screen
    # crashing on one input should not wait for someone to run it by hand.
    results = (*run_screens(authority, modelo_ids), *run_corpus_screens())
    assert len(results) == len(SCREENS) + len(CORPUS_SCREENS)
    for name, count, meaning in results:
        assert count >= 0, f"{name} returned a negative count"
        assert meaning.strip(), f"{name} does not say what its count means"


def _reaches_binding_derivation(source: str) -> bool:
    """Whether ``source`` REACHES the binding derivation, rather than naming it.

    An import, a bare name or an attribute access is a reach; the same
    characters inside a docstring, a comment or a string literal are not, which
    is what lets a module explain the rule it obeys.

    Defined once and used by both the gate below and its proof. Written twice,
    the proof exercises its own copy: a branch dropped from the gate would leave
    the proof green, and the detector would be proved against a
    reimplementation of itself.
    """
    import ast

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and any(alias.name == _BINDING_DERIVATION for alias in node.names):
            return True
        if isinstance(node, ast.Name) and node.id == _BINDING_DERIVATION:
            return True
        if isinstance(node, ast.Attribute) and node.attr == _BINDING_DERIVATION:
            return True
    return False


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

    Read through the syntax tree rather than as text. A substring search sees
    the name wherever it appears, including in a docstring explaining why the
    module does NOT use it - so the previous form of this gate punished a module
    for documenting the rule, which is the opposite of what it exists to
    encourage. Names in comments, docstrings and string literals are not
    reaches; imports and attribute access are.
    """
    import pathlib

    analysis = pathlib.Path(__file__).resolve().parent.parent / "analysis"
    offenders: list[str] = []
    scanned = 0
    for path in sorted(analysis.rglob("*.py")):
        scanned += 1
        if _reaches_binding_derivation(path.read_text(encoding=_UTF_8)):
            offenders.append(path.stem)

    # A gate asserting an absence must first prove it looked. Without this a
    # moved directory or a changed suffix empties the walk and the assertion
    # passes over nothing, which is the one failure a green result cannot show.
    assert scanned, "the analysis package walk found no modules, so this gate checked nothing"
    assert not offenders, (
        "these modules reach for the binding derivation instead of the resolved-surface accessor, "
        f"which is how four wrong figures were published: {sorted(offenders)}"
    )


def test_the_reassembly_gate_reads_syntax_not_text() -> None:
    """It catches a reach and stays silent on a module that only names one.

    Both halves matter. Without the first the gate protects nothing; without the
    second it makes the rule undocumentable, and a rule nobody may explain is
    one the next author re-breaks.
    """

    newline = chr(10)
    assert _reaches_binding_derivation(f"from x.y import {_BINDING_DERIVATION}{newline}")
    assert _reaches_binding_derivation(f"import x.y{newline}rows = x.y.{_BINDING_DERIVATION}(revision){newline}")
    docstring_only = f'"""A screen must not call {_BINDING_DERIVATION}; it asks the accessor."""{newline}'
    assert not _reaches_binding_derivation(docstring_only)
    assert not _reaches_binding_derivation(f"# never {_BINDING_DERIVATION}{newline}value = 1{newline}")


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

    from ..analysis.screens import run_corpus_screens, run_screens

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
    # The corpus screens read the same shipped tree - the design transcriptions
    # live inside it - so leaving them out of this fingerprint left the half of
    # the suite that touches those files unchecked for writes.
    run_corpus_screens()
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

    from ..analysis.screens import screen_findings

    observed: set[tuple[str, str]] = set()
    undocumented: list[str] = []
    # Both tables, through the shared traversal. This gate iterated the
    # authority table alone and so never read a corpus screen's kinds.
    for name, findings in screen_findings(authority, modelo_ids):
        module = importlib.import_module(f"dev.registry.analysis.{name}")
        doc = module.__doc__ or ""
        for finding in findings:
            kind = getattr(finding, "kind", None)
            if not isinstance(kind, str):
                continue
            observed.add((name, kind))
            if kind not in doc:
                undocumented.append(f"{name} emits {kind!r} but its docstring never names it")

    assert observed, "no enrolled screen emitted a kind, so this gate checked nothing"
    assert not undocumented, "\n".join(sorted(set(undocumented)))


def test_a_runner_projection_never_reports_a_kind_its_screen_does_not_emit(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> None:
    """A table entry may narrow its screen's findings; it may not invent them.

    Several entries project - onto the subset needing action, an index, or a
    residue - so the runner reports one meaningful number per screen. Dropping
    findings is what those projections are FOR, so the containment holds one way
    only, and an earlier draft of this gate asserted the wrong direction: it
    demanded the projections expose every kind, which would have forbidden the
    design they exist to serve. It failed on legitimate code, which is how the
    direction got corrected.

    What must hold is that a projection reports nothing its screen did not. A
    projection that added a kind would be deriving a finding in the runner
    table, where no test looks for it and no docstring describes it.

    That projections hide kinds from the KIND-NAMING gate is a separate problem
    and is fixed at the reader: those gates call each screen's own entry point
    rather than the table.
    """
    from ..analysis.screens import CORPUS_SCREENS, SCREENS, screen_findings

    def kinds_of(rows: tuple[object, ...]) -> set[str]:
        return {kind for row in rows if isinstance(kind := getattr(row, "kind", None), str)}

    direct = {name: kinds_of(findings) for name, findings in screen_findings(authority, modelo_ids)}
    assert any(direct.values()), "no screen emitted a kind, so this gate checked nothing"

    invented: dict[str, list[str]] = {}
    for name, run in (
        *((entry.name, lambda entry=entry: entry.run(authority, modelo_ids)) for entry in SCREENS),
        *((entry.name, lambda entry=entry: entry.run()) for entry in CORPUS_SCREENS),
    ):
        extra = kinds_of(tuple(run())) - direct.get(name, set())
        if extra:
            invented[name] = sorted(extra)
    assert not invented, f"runner entries reporting a kind their screen does not emit: {invented}"


def test_a_derived_screen_reports_nothing_its_source_does_not(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> None:
    """A screen declaring a source may re-describe its findings, not exceed them.

    The grounding screen is built on the pointer screen: it calls it and emits
    one finding per field it returns. That makes its population a re-description
    rather than independent evidence, which matters to any consumer counting
    distinct conditions - the revision-pressure ranking reported modelo 200 with
    nine conditions where seven are independent, until the derivation was
    declared.

    Half the declaration is verifiable and this is it: whatever the derived
    screen reports must name a revision its source also reports. What no test
    can decide is whether a screen that happens to agree today was actually
    built on the other, which is why the declaration is an author's and not
    inferred from this containment holding.
    """
    from ..analysis.screens import SCREENS, screen_findings

    sources = {entry.name: entry.derives_from for entry in SCREENS if entry.derives_from}
    assert sources, "no screen declares a source, so this gate checked nothing"

    populations = {
        name: {(getattr(f, "modelo", None), str(getattr(f, "revision", ""))) for f in findings}
        for name, findings in screen_findings(authority, modelo_ids)
    }
    for derived, source in sources.items():
        assert source in populations, f"{derived} derives from {source!r}, which is not an enrolled screen"
        assert populations[derived] <= populations[source], (
            f"{derived} reports revisions its declared source {source} does not: "
            f"{sorted(populations[derived] - populations[source])}"
        )


def test_every_package_initialiser_in_the_development_registry_tree_is_inert() -> None:
    """A package initialiser here declares a namespace and nothing else.

    The architecture rule is that initialisers carry no exports, no forwarding
    and no import side effects. Three separate facades had grown here anyway -
    one of them fifty-one lines re-exporting twenty names, and one enforced by a
    test asserting its ``__all__`` verbatim, so the breach had a gate holding it
    in place. All were removable without touching a caller, because every
    consumer already imported the defining module; the facades were carrying
    nothing but the ability to grow.

    That is the argument for a standing gate rather than three fixes: nothing
    made the first facade fail, so nothing would have made the fourth.
    """
    import ast
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    offenders: dict[str, list[str]] = {}
    checked = 0
    for path in sorted(root.rglob("__init__.py")):
        checked += 1
        tree = ast.parse(path.read_text(encoding=_UTF_8))
        offending = [
            type(node).__name__
            for node in tree.body
            if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))
        ]
        if offending:
            offenders[str(path.relative_to(root))] = offending

    assert checked > 1, "no package initialisers were found, so this gate checked nothing"
    assert not offenders, f"package initialisers carrying more than a docstring: {offenders}"


def test_the_inert_initialiser_gate_detects_a_re_export() -> None:
    """The gate above is shown to catch the defect it exists to prevent.

    Constructed as source text rather than by writing into the tree, because a
    gate over the contributor's own working tree must not modify it to prove
    itself.
    """
    import ast

    facade = '"""A package."""\n\nfrom .thing import Thing\n\n__all__ = ["Thing"]\n'
    tree = ast.parse(facade)
    offending = [
        type(node).__name__
        for node in tree.body
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))
    ]
    assert offending == ["ImportFrom", "Assign"], offending

    inert = ast.parse('"""A package."""\n')
    assert not [
        node for node in inert.body if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))
    ]


_VAULT_CITATION_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bW\d{2}\.P\d{2}\.S\d+\b", "wave-phase-step identifier"),
    (r"(?<![.\w])P\d{2}\.S\d{2}\b", "phase-step identifier"),
    (
        r"\b\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*-(?:adr|plan|audit|research|reference|exec)\b",
        "vault document stem",
    ),
    (r"\.vault/", "vault path"),
)


def _vault_citations(text: str) -> list[str]:
    """Return the vault citations a body of text carries, by kind."""
    import re

    return [
        f"{label}: {match.group(0)}"
        for pattern, label in _VAULT_CITATION_PATTERNS
        for match in re.finditer(pattern, text)
    ]


def test_no_registry_source_or_declaration_cites_a_vault_record() -> None:
    """Registry code and shipped declarations never name the project's own development records.

    The code-stands-alone mandate makes the reference direction one-way: a vault
    document cites code by locator, and code cites nothing back. The shipped
    check for this exists and is run, but it matches document STEMS, so a plan
    step identifier passes it silently. Two filing-grade modelo 200 revision
    declarations carried one for weeks while that check reported the registry
    clean, which is why this gate matches step identifiers and vault paths too
    rather than trusting the stem search alone.

    A declaration is the worst place for such a citation: it ships in the wheel,
    it is read as tax-domain evidence, and the record it names is development
    scaffolding the product is meant to be removable from.
    """
    import pathlib

    from cadrumo.core.resources.bundled_data import bundled_path

    roots = (
        pathlib.Path(__file__).resolve().parent.parent,
        bundled_path("registry", "aeat"),
    )
    offenders: dict[str, list[str]] = {}
    scanned = 0
    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.suffix not in {".py", ".toml", ".md"} or not path.is_file():
                continue
            if "__pycache__" in path.parts:
                continue
            if path.name == pathlib.Path(__file__).name:
                # This module necessarily contains example citations: the paired
                # detector below constructs one of each kind to prove the
                # patterns match. Scanning it would make the gate report itself,
                # and removing the examples would leave the patterns unproven.
                continue
            scanned += 1
            citations = _vault_citations(path.read_text(encoding=_UTF_8, errors="ignore"))
            if citations:
                offenders[str(path)] = sorted(set(citations))

    assert scanned > 100, f"only {scanned} files scanned, so this gate proves little"
    assert not offenders, f"registry files citing vault records: {offenders}"


def test_the_vault_citation_gate_catches_each_kind_it_claims_to() -> None:
    """Every pattern the gate carries is shown to match, and ordinary prose is shown not to.

    Constructed in memory rather than written into the tree. The negative half
    matters as much as the positive: a detector that fires on a revision
    directory name like ``2025-y-siguientes`` or on a casilla identifier would
    be unusable, and nobody would find out from a clean corpus.
    """
    assert _vault_citations("published under downstream step W04.P08.S22.") == [
        "wave-phase-step identifier: W04.P08.S22"
    ]
    assert _vault_citations("see P07.S23 for the rollout") == ["phase-step identifier: P07.S23"]
    assert _vault_citations("grounded in 2026-08-07-rate-box-evidence-assertion-adr today") == [
        "vault document stem: 2026-08-07-rate-box-evidence-assertion-adr"
    ]
    assert _vault_citations("recorded in .vault/audit/x.md") == ["vault path: .vault/"]

    for innocent in (
        "revision 2025-y-siguientes narrows the window",
        "casilla DP200014:01033 carries the base",
        "orden HAC/1155/2024 art. 3 governs this",
        "the 2024-2025 span covers both ejercicios",
    ):
        assert _vault_citations(innocent) == [], innocent


_NUMBER_WORDS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def test_a_screen_that_counts_its_conditions_states_the_right_number(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> None:
    """A docstring claiming "N conditions are reported" must agree with what the screen emits.

    The sibling gate above requires every emitted kind to be NAMED in the
    docstring, and that is not enough. Two screens named all their kinds while
    still opening with a count from an earlier version of themselves, and one of
    those was introduced by the very edit that added the missing name: a bullet
    was appended and the sentence above it was left saying three.

    A wrong count is worse than a missing one. It tells a reader the list they
    are looking at is complete, so the condition they never find is the one they
    conclude does not exist.
    """
    import importlib
    import re


    wrong: list[str] = []
    checked = 0
    from ..analysis.screens import screen_findings, screen_module_names

    findings_by_name = dict(screen_findings(authority, modelo_ids))
    for screen_name in sorted(screen_module_names()):
        module = importlib.import_module(f"dev.registry.analysis.{screen_name}")
        doc = module.__doc__ or ""
        # Any noun, not just "conditions". The screens say conditions,
        # disagreements, kinds - the claim is "N somethings are reported", and a
        # gate keyed to one spelling read four screens while a fifth stated its
        # count in a synonym and went unchecked.
        claim = re.search(r"\b([A-Za-z]+) [a-z]+ are reported\b", doc)
        if claim is None:
            continue
        stated = _NUMBER_WORDS.get(claim.group(1).lower())
        if stated is None:
            wrong.append(f"{screen_name} states an unrecognised count {claim.group(1)!r}")
            continue
        checked += 1
        emitted = len({finding.kind for finding in findings_by_name.get(screen_name, ()) if hasattr(finding, "kind")})
        # Count only the bullets belonging to this claim. Several screens also
        # bullet the FACTS they read, in the same backtick form, before naming
        # their conditions; counting those made this gate fail on a docstring
        # whose stated number was right.
        named = 0
        for line in doc[claim.end() :].splitlines():
            if line.startswith("- ``"):
                named += 1
            elif line.strip() and not line.startswith(" ") and named:
                break
        if stated != named:
            wrong.append(f"{screen_name} says {stated} conditions and documents {named}")
        if emitted > stated:
            wrong.append(f"{screen_name} says {stated} conditions and emits {emitted} distinct kinds live")

    assert checked, "no screen stated a condition count, so this gate checked nothing"
    assert not wrong, "\n".join(wrong)


def _export_fields(authority: ValidatedRegistryAuthority) -> list[tuple[str, str, object]]:
    """Return every export field in the corpus with the coordinate that owns it."""
    found: list[tuple[str, str, object]] = []
    for code in sorted(str(item) for item in registry_modelo_codes()):
        for revision_id, revision in authority.modelo(code).revisions.items():
            for layout in revision.export_layouts:
                for record in layout.records:
                    found.extend((code, str(revision_id), field) for field in record.fields)
    return found


def test_every_monetary_field_declares_a_scale_or_is_rendered_by_a_self_scaling_type(
    authority: ValidatedRegistryAuthority,
) -> None:
    """A monetary amount whose scale is undeclared cannot be emitted at a known magnitude.

    Two wire types carry money. ``money`` is self-scaling: the codec renders and
    parses it at two decimal places without consulting the declaration. ``decimal``
    is not, and the codec demands ``decimals`` from the field itself.

    The codec already refuses an undeclared scale, but only at the moment it renders
    or parses that field, which means a revision can ship, validate and sit in the
    registry with the defect latent until something exercises the field. This gate
    asks the question of every declaration at once instead, so the answer does not
    depend on which fields a test happens to reach.
    """
    unscaled = [
        f"{modelo}/{revision} {field.id}"
        for modelo, revision, field in _export_fields(authority)
        if str(getattr(field, "data_type", "")) == "decimal" and getattr(field, "decimals", None) is None
    ]
    assert unscaled == [], (
        "these decimal export fields declare no scale, so the magnitude they emit is "
        f"undefined until the codec refuses them at render time: {unscaled}"
    )


def test_the_corpus_actually_contains_both_monetary_wire_types(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The gate above is meaningless if neither type is present to be checked.

    Pinned so that a corpus which stopped declaring monetary fields altogether
    cannot make the invariant pass by emptiness.
    """
    types = collections.Counter(str(getattr(field, "data_type", "")) for _, _, field in _export_fields(authority))
    assert types["decimal"] > 0
    assert types["money"] > 0


def test_the_gate_detects_a_decimal_field_that_declares_no_scale(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Constructed, because the corpus declares a scale everywhere.

    A real decimal field is copied with its scale removed and put back through the
    same predicate the gate uses, so the gate is shown able to report the condition
    it protects rather than only ever having seen a clean corpus.
    """
    sample = next(
        field
        for _, _, field in _export_fields(authority)
        if str(getattr(field, "data_type", "")) == "decimal" and getattr(field, "decimals", None) is not None
    )
    stripped = sample.model_copy(update={"decimals": None})

    assert str(stripped.data_type) == "decimal"
    assert stripped.decimals is None
    assert getattr(sample, "decimals", None) is not None, "the donor field must still declare its own scale"


def test_a_screen_that_counts_the_facts_it_reads_states_the_right_number() -> None:
    """A docstring claiming "N facts decide it" must agree with the bullets under it.

    The sibling gate above counts the bullets that follow a "N conditions are
    reported" claim and deliberately stops before the FACT bullets several
    screens list first - counting those made it fail on a docstring whose stated
    number was right. That exclusion left the fact claims unchecked entirely,
    and one was wrong: a screen said four facts decided its answer and listed
    five.

    The two claims are read the same way and cannot be merged, because they
    count different bullet runs in one docstring and a gate that conflated them
    would be wrong in whichever direction it guessed.
    """
    import importlib
    import re


    wrong: list[str] = []
    checked = 0
    from ..analysis.screens import screen_module_names

    for screen_name in sorted(screen_module_names()):
        module = importlib.import_module(f"dev.registry.analysis.{screen_name}")
        doc = module.__doc__ or ""
        claim = re.search(r"\b([A-Za-z]+) facts decide\b", doc)
        if claim is None:
            continue
        stated = _NUMBER_WORDS.get(claim.group(1).lower())
        if stated is None:
            wrong.append(f"{screen_name} states an unrecognised fact count {claim.group(1)!r}")
            continue
        checked += 1
        # Any bullet, not only one opening with a backticked name. The
        # conditions gate can use the narrower pattern because every condition
        # bullet names its kind first; fact bullets are prose, and counting
        # only the backticked ones reported five facts as one.
        listed = 0
        for line in doc[claim.end() :].splitlines():
            if line.startswith("- "):
                listed += 1
            elif line.strip() and not line.startswith(" ") and listed:
                break
        if stated != listed:
            wrong.append(f"{screen_name} says {stated} facts and lists {listed}")

    assert checked, "no screen stated a fact count, so this gate checked nothing"
    assert not wrong, "\n".join(wrong)


def _names_imported_by_tests(root: pathlib.Path) -> set[str]:
    """Return every module name the test modules under ``root`` import, either form.

    Both forms matter and missing one is not a small error. A module reached as
    ``from package import module`` appears in the import's NAMES, not in its
    module path, and an extractor reading only the path reported seven modules
    as untested that four separate tests import.
    """
    import ast

    names: set[str] = set()
    for path in sorted(root.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding=_UTF_8))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    names.add(node.module.rsplit(".", 1)[-1])
                names.update(alias.name.rsplit(".", 1)[-1] for alias in node.names)
            elif isinstance(node, ast.Import):
                names.update(alias.name.rsplit(".", 1)[-1] for alias in node.names)
    return names


def _public_modules(roots: tuple[pathlib.Path, ...]) -> list[pathlib.Path]:
    """Return modules declaring at least one public function or class."""
    import ast

    found: list[pathlib.Path] = []
    for root in roots:
        for path in sorted(root.glob("*.py")):
            if path.name in {"__init__.py", "__main__.py"}:
                continue
            tree = ast.parse(path.read_text(encoding=_UTF_8))
            if any(
                isinstance(node, ast.FunctionDef | ast.ClassDef) and not node.name.startswith("_")
                for node in tree.body
            ):
                found.append(path)
    return found


def test_every_public_module_in_the_registry_tooling_is_imported_by_a_test() -> None:
    """A module no test imports is a module whose behaviour nobody asserts.

    Asked by import rather than by filename, because the naming here follows no
    single rule: pipeline modules carry a leading underscore their tests drop,
    tests are named for the subject rather than the module, and the conformance
    package keeps its own tests directory. Three filename rules were tried and
    each reported a backlog that did not exist - eighteen modules, then twelve,
    then eight, against a true answer of one.

    The one real case was a generator whose `--check` mode refuses a stale
    artefact and which nothing invoked, so a current artefact and an unrun
    generator looked identical from outside.
    """
    registry = pathlib.Path(__file__).resolve().parent.parent
    roots = (registry / "analysis", registry / "pipeline", registry / "conformance")
    imported = _names_imported_by_tests(registry)
    modules = _public_modules(roots)

    assert modules, "no public module was found, so this gate checked nothing"
    assert imported, "no test imports were read, so every module would look untested"

    unimported = sorted(path.stem for path in modules if path.stem not in imported)
    assert not unimported, (
        "these modules declare a public surface that no test imports, so nothing asserts what they do: "
        f"{unimported}"
    )


def test_the_import_coverage_gate_sees_a_module_no_test_imports(tmp_path: pathlib.Path) -> None:
    """Planted under an injectable root, so the proof never touches the tree.

    Both directions are asserted. Without the first the gate protects nothing;
    without the second it would fail on every module reached through the import
    form the earlier extractor could not read, which is exactly how the phantom
    backlog was produced.
    """
    package = tmp_path / "analysis"
    package.mkdir()
    (package / "covered.py").write_text("def public() -> int:\n    return 1\n", encoding=_UTF_8)
    (package / "orphan.py").write_text("def public() -> int:\n    return 2\n", encoding=_UTF_8)
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_covered.py").write_text("from ..analysis import covered\n", encoding=_UTF_8)

    imported = _names_imported_by_tests(tmp_path)
    modules = _public_modules((package,))
    unimported = sorted(path.stem for path in modules if path.stem not in imported)

    assert unimported == ["orphan"], "the gate must see the planted module and only that one"


def test_every_screen_finding_type_declares_the_identity_the_contract_promises() -> None:
    """A caller may key a FINDING on its modelo, and this holds that line.

    Asserted over the finding types each screen defines, not over the rows this
    runner reports, because two entries deliberately collapse their screen onto
    a different unit - a reference outside a manifest, a wire-type transition -
    and those rows are a report rather than a finding. Running the gate over the
    runner's output found exactly that and was wrong to call it a violation: the
    contract had been written as though a report and a finding were the same
    thing.

    One field, deliberately. Eight of the nine types also carry a revision and
    one does not, because a continuity chain spans revisions and pinning one
    would name a revision the defect does not belong to. A discriminator appears
    only where a screen reports more than one condition.
    """
    import dataclasses
    import importlib

    from ..analysis.screens import FINDING_IDENTITY_CONTRACT

    assert FINDING_IDENTITY_CONTRACT == ("modelo",), "the contract changed; this gate encodes it"

    checked = 0
    missing: list[str] = []
    from ..analysis.screens import screen_module_names

    for screen_name in sorted(screen_module_names()):
        module = importlib.import_module(f"dev.registry.analysis.{screen_name}")
        for name, obj in vars(module).items():
            if not dataclasses.is_dataclass(obj) or getattr(obj, "__module__", None) != module.__name__:
                continue
            if not name.endswith(("Finding", "Transition")):
                continue
            checked += 1
            fields = {field.name for field in dataclasses.fields(obj)}
            missing.extend(
                f"{screen_name}.{name} declares no {required!r}"
                for required in FINDING_IDENTITY_CONTRACT
                if required not in fields
            )

    assert checked, "no finding type was found, so this gate checked nothing"
    assert not missing, chr(10).join(sorted(missing))


def _non_ascii_declarations(field: object) -> list[str]:
    """Return each string attribute of ``field`` carrying a character outside ASCII.

    Shared with the proof below, so the proof exercises the judgement the gate
    makes rather than a second copy of it.
    """
    found: list[str] = []
    for name in type(field).model_fields:
        value = getattr(field, name, None)
        if isinstance(value, str) and value and not value.isascii():
            found.append(f"{name} = {value!r}")
    return found


def _mixed_line_endings(records: Iterable[object]) -> set[str]:
    """Return the distinct line endings a layout's records declare.

    More than one is the defect. An empty set means the layout declares no
    records, which the caller skips rather than treating as agreement.
    """
    return {str(getattr(record, "line_ending", None)) for record in records}


def test_no_export_declaration_carries_a_character_outside_ascii(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> None:
    """A declared literal must not smuggle a byte the codec has to guess at.

    Records declare iso-8859-1, and the accents a filing carries come from
    taxpayer data at emission. A non-ASCII character in a DECLARATION is
    different: it is written by an author, encoded on the way to disk, and
    decoded again by whatever reads the registry, so it survives or does not
    depending on three assumptions nobody states.
    """
    offenders: list[str] = []
    fields = 0
    for code in modelo_ids:
        for revision_id, revision in authority.modelo(code).revisions.items():
            for layout in revision.export_layouts:
                for record in layout.records:
                    for field in record.fields:
                        fields += 1
                        offenders.extend(
                            f"{code}/{revision_id} {field.id}.{found}"
                            for found in _non_ascii_declarations(field)
                        )

    assert fields, "no export field was read, so this gate checked nothing"
    assert not offenders, "export declarations carrying non-ASCII characters:\n" + chr(10).join(sorted(offenders))


def test_a_modelo_never_declares_two_record_encodings(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> None:
    """Bytes written under one encoding and read under another are silently wrong.

    Every record in this corpus declares iso-8859-1. The gate is not that value
    but the agreement: a modelo declaring two encodings emits a file whose
    records disagree about what its bytes mean, and no single record is wrong.
    """
    offenders: list[str] = []
    checked = 0
    for code in modelo_ids:
        declared = set()
        for revision in authority.modelo(code).revisions.values():
            for layout in revision.export_layouts:
                for record in layout.records:
                    checked += 1
                    declared.add(str(record.encoding))
        if len(declared) > 1:
            offenders.append(f"{code} declares {sorted(declared)}")

    assert checked, "no record was read, so this gate checked nothing"
    assert not offenders, "modelos declaring more than one record encoding: " + "; ".join(offenders)


def test_no_layout_mixes_terminated_and_unterminated_records(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> None:
    """A file whose records disagree about termination is malformed as a whole.

    Fifty-nine layouts terminate no record and twenty-nine terminate every one;
    both are valid shapes. A layout doing both emits a file that is neither, and
    the defect is invisible record by record - each one carries exactly the
    ending it declares.

    Records-less layouts are skipped rather than counted as agreeing: modelo
    100's XML dictionary layouts carry their content in a cited dictionary, so
    they have no termination to disagree about.
    """
    offenders: list[str] = []
    checked = 0
    for code in modelo_ids:
        for revision_id, revision in authority.modelo(code).revisions.items():
            for layout in revision.export_layouts:
                if not layout.records:
                    continue
                checked += 1
                endings = _mixed_line_endings(layout.records)
                if len(endings) > 1:
                    offenders.append(f"{code}/{revision_id} {layout.id} declares {sorted(endings)}")

    assert checked, "no layout with records was read, so this gate checked nothing"
    assert not offenders, "layouts mixing line endings: " + chr(10).join(sorted(offenders))


def test_the_export_declaration_gates_detect_their_defects(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Each of the three export gates is shown to catch a planted defect.

    Constructed from real declarations by copy, never by mutating the working
    tree, and asserted through the helpers the gates themselves call - a proof
    against a second implementation would prove the second implementation.
    """
    revision = authority.modelo("303").revisions["2025"]
    layout = next(item for item in revision.export_layouts if item.records)
    record = layout.records[0]
    field = record.fields[0]

    clean = _non_ascii_declarations(field)
    accented = field.model_copy(update={"id": f"{field.id}-declaración"})

    assert clean == [], "the fixture field must start clean or the planted defect proves nothing"
    assert _non_ascii_declarations(accented), "an accented declaration must be reported"

    assert len(_mixed_line_endings(layout.records)) == 1, "the fixture layout must agree with itself"

    from cadrumo.domain.calculations.registry.schema_exports import ExportLineEnding

    other = ExportLineEnding.CRLF if record.line_ending is ExportLineEnding.NONE else ExportLineEnding.NONE
    mixed = (*layout.records, record.model_copy(update={"line_ending": other}))

    assert len(_mixed_line_endings(mixed)) == 2, "a layout carrying both endings must be reported"
    assert _mixed_line_endings(()) == set(), "a record-less layout declares no ending to disagree about"
