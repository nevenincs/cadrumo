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
    import pathlib

    from ..analysis.screens import SCREENS

    analysis = pathlib.Path(__file__).resolve().parent.parent / "analysis"
    defining = {
        path.stem
        for path in analysis.glob("*.py")
        if path.name != "screens.py" and "\ndef screen_authority(" in path.read_text(encoding=_UTF_8)
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

    from ..analysis.screens import SCREENS

    readme = (pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text(encoding=_UTF_8)
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
    """
    from cadrumo.domain.calculations.registry.export import resolved_export_endpoints

    from ..analysis.casilla_id_grammar import screen_authority as grammar
    from ..analysis.continuity_integrity import continuity_census
    from ..analysis.wire_type_compatibility import screen_authority as wire_types

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
        if path.name != "screens.py" and "\ndef screen_authority(" in path.read_text(encoding=_UTF_8)
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
    from ..analysis.screens import SCREENS, run_screens

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

    Read through the syntax tree rather than as text. A substring search sees
    the name wherever it appears, including in a docstring explaining why the
    module does NOT use it - so the previous form of this gate punished a module
    for documenting the rule, which is the opposite of what it exists to
    encourage. Names in comments, docstrings and string literals are not
    reaches; imports and attribute access are.
    """
    import ast
    import pathlib

    analysis = pathlib.Path(__file__).resolve().parent.parent / "analysis"
    offenders: list[str] = []
    for path in sorted(analysis.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding=_UTF_8))
        reached = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                reached |= any(alias.name == _BINDING_DERIVATION for alias in node.names)
            elif isinstance(node, ast.Name):
                reached |= node.id == _BINDING_DERIVATION
            elif isinstance(node, ast.Attribute):
                reached |= node.attr == _BINDING_DERIVATION
        if reached:
            offenders.append(path.stem)

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
    import ast

    def reaches(source: str) -> bool:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(a.name == _BINDING_DERIVATION for a in node.names):
                return True
            if isinstance(node, ast.Name) and node.id == _BINDING_DERIVATION:
                return True
            if isinstance(node, ast.Attribute) and node.attr == _BINDING_DERIVATION:
                return True
        return False

    newline = chr(10)
    assert reaches(f"from x.y import {_BINDING_DERIVATION}{newline}")
    assert reaches(f"import x.y{newline}rows = x.y.{_BINDING_DERIVATION}(revision){newline}")
    assert not reaches(f'"""A screen must not call {_BINDING_DERIVATION}; it asks the accessor."""{newline}')
    assert not reaches(f"# never {_BINDING_DERIVATION}{newline}value = 1{newline}")


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

    from ..analysis.screens import run_screens

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

    from ..analysis.screens import SCREENS

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

    from ..analysis.screens import SCREENS

    wrong: list[str] = []
    checked = 0
    for entry in SCREENS:
        module = importlib.import_module(f"dev.registry.analysis.{entry.name}")
        doc = module.__doc__ or ""
        claim = re.search(r"\b([A-Za-z]+) conditions are reported\b", doc)
        if claim is None:
            continue
        stated = _NUMBER_WORDS.get(claim.group(1).lower())
        if stated is None:
            wrong.append(f"{entry.name} states an unrecognised count {claim.group(1)!r}")
            continue
        checked += 1
        emitted = len({finding.kind for finding in entry.run(authority, modelo_ids) if hasattr(finding, "kind")})
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
            wrong.append(f"{entry.name} says {stated} conditions and documents {named}")
        if emitted > stated:
            wrong.append(f"{entry.name} says {stated} conditions and emits {emitted} distinct kinds live")

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
