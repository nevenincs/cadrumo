"""Agent-rule corpus lint: a rule that cites project code must cite code that exists.

The rule corpus is loaded into every agent session at start, so a citation
naming a symbol or module that no longer exists misdirects every reader of that
rule until someone happens to notice. Two live instances were found the same
day, and neither was found by reading the rules:

- ``aeat-registry-bindings`` named a carve-out constant
  under its pre-rename spelling, in a module it had since been extracted out of.
- ``aeat-agent-orchestration`` told an audit axis to ground its read against a
  policy gate that had been deleted, so the axis instruction was unexecutable
  and an agent following it would report a cleared inventory it never consulted.

The mechanism this gate exists to catch is NOT an authoring slip. A citation
naming something that never existed is caught by the first reader who follows
it. What nothing catches is a citation that was ACCURATE WHEN WRITTEN and
decays later, at a rename or deletion in unrelated code -- and both known
instances decayed inside bulk snapshot commits, where the rename is not
reviewed as a rename by anybody. The reference direction is deliberately
one-way (documents cite code by locator so code need not cite documents), which
means nothing on the code side has any reason to notice.

Why ``## How`` is excluded
--------------------------

``## How`` is where a rule teaches by contrast. Its bullets name things that
SHOULD NOT exist -- a shim to avoid, a misplaced test path, a pre-rename
setting -- so an unresolvable citation there is the rule working, not rotting.
Measured against the five unresolvable citations in the corpus when this gate
was written, the section boundary separated them 3-for-3 and 2-for-2.

Polarity is deliberately NOT the discriminator, though it looks like the
obvious one. A first attempt at this gate proposed excluding ``Bad:`` bullets;
that would have kept a false positive, because
``aeat-naming`` names the pre-rename
``AEAT_WALLET_...DUMP_DIR`` setting inside a **Good:** bullet -- the good act
being to rename it away. Presence-versus-absence is a semantic property of the
sentence and cannot be read off the bullet's label, whereas the section heading
is structural and needs no per-citation annotation to maintain. An allowlist
would have been the third option and was rejected outright: an allowlist of
citations would rot in exactly the way the citations do.

Accepted residual risk: a rot landing inside a ``## How`` bullet is invisible
here. That is the section where a stale name does least harm, because the
reader is already being told the named thing is wrong.

Vacuity
-------

The ``.vaultspec/`` harness is removable development scaffolding, so a checkout
without it is legitimate and this gate passes truthfully there -- it asserts
nothing about a corpus that is not present. That makes a silent no-op
indistinguishable from a real pass, so when the directory IS present the corpus
is separately asserted non-empty. Skipping is not an option (the project bars
skip and xfail outright) and would carry the same defect anyway: a skip and a
vacuous pass are equally uninformative.
"""

from __future__ import annotations

import re
import subprocess

import pytest

from cadrumo.core.directory_scan import scan_directory
from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT
_RULES_DIR = _REPO_ROOT / ".vaultspec" / "rules"

# A citation is a backticked token. Two shapes carry locators precise enough to
# resolve: a module path ending in `.py`, and a SCREAMING_SNAKE constant. Both
# are unambiguous enough that a miss is a real miss. Prose identifiers
# (`snake_case` functions, `CamelCase` classes) are deliberately out of scope:
# they collide with English words and ordinary nouns often enough that the
# finding set would be dominated by noise, which is how a gate stops being read.
_PY_PATH = re.compile(r"`([A-Za-z0-9_./-]+\.py)`")
_CONSTANT = re.compile(r"`([A-Z][A-Z0-9_]{5,})`")

_EXCLUDED_SECTION = "## How"

# A rule's `## Why` narrates history, and history names things that no longer
# exist -- legitimately, when it says so. These markers are the author's
# explicit declaration that the cited locator is a former home rather than a
# place to go, so the citation is exempt within two lines of one.
#
# The compound forms are deliberate. A bare "retired" appears throughout the
# corpus about enums, verbs, and campaigns, and would exempt far more than
# intended; these phrases can only be read as a claim about the thing just
# named. The exemption is also self-policing in a way an allowlist is not: it
# lives in the sentence a reader reads, so writing "since-retired" about a live
# module is a visible falsehood, whereas a distant allowlist entry is invisible.
_RETIREMENT_MARKERS = (
    "since-retired",
    "since retired",
    "since-deleted",
    "since deleted",
    "since-removed",
    "since removed",
    "now-deleted",
    "now deleted",
    "no longer exists",
    "formerly",
)
_RETIREMENT_LOOKBEHIND = 2


def _declared_retired(lines: list[str], index: int) -> bool:
    r"""Whether an explicit retirement marker governs the citation on ``lines[index]``.

    The lookbehind exists because a citation regularly wraps to its own line
    after the phrase that qualifies it -- the worked example reads "The
    since-retired\\n``application/wizard/_prompter.py`` was the canonical
    authority", so a same-line-only check would report the one citation the
    corpus most clearly marks as history.
    """
    window = lines[max(0, index - _RETIREMENT_LOOKBEHIND) : index + 1]
    haystack = " ".join(window).lower()
    return any(marker in haystack for marker in _RETIREMENT_MARKERS)


def _citations_outside_the_how_section(markdown: str) -> list[tuple[str, str]]:
    """Return ``(section, token)`` for every locator citation outside ``## How``.

    The section is carried into the result so a failure message can tell the
    reader where to look, and so the exclusion itself is observable rather than
    an invisible filter.
    """
    findings: list[tuple[str, str]] = []
    section = "(no heading)"
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("## "):
            section = line.strip()
        if section == _EXCLUDED_SECTION or _declared_retired(lines, index):
            continue
        for pattern in (_PY_PATH, _CONSTANT):
            findings.extend((section, token) for token in pattern.findall(line))
    return findings


def _tracked_python_paths() -> set[str]:
    listing = subprocess.run(
        ["git", "ls-files", "*.py"],  # noqa: S607 - git resolved from PATH like every dev gate
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return {line.strip() for line in listing.stdout.splitlines() if line.strip()}


def _constants_defined_anywhere() -> set[str]:
    """Every SCREAMING_SNAKE token appearing in tracked Python source.

    One `git grep` rather than one subprocess per citation: the corpus carries
    enough constants that per-token shelling out would make this gate slow
    enough to be worth skipping, and a gate people skip is not a gate.
    """
    found = subprocess.run(
        ["git", "grep", "-h", "-o", "-E", r"[A-Z][A-Z0-9_]{5,}", "--", "*.py"],  # noqa: S607 - git resolved from PATH like every dev gate
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return {line.strip() for line in found.stdout.splitlines() if line.strip()}


def _unresolvable(
    markdown: str,
    *,
    tracked_paths: set[str],
    known_constants: set[str],
) -> list[tuple[str, str, str]]:
    """Return ``(section, token, reason)`` for citations that do not resolve."""
    basenames: dict[str, list[str]] = {}
    for path in tracked_paths:
        basenames.setdefault(path.rsplit("/", 1)[-1], []).append(path)

    misses: list[tuple[str, str, str]] = []
    for section, token in _citations_outside_the_how_section(markdown):
        if token.endswith(".py"):
            candidates = basenames.get(token.rsplit("/", 1)[-1], [])
            if not candidates:
                misses.append((section, token, "no tracked file has that name"))
            elif "/" in token and not any(c.endswith(token) for c in candidates):
                misses.append((section, token, f"that name exists, but not at that path ({len(candidates)} elsewhere)"))
        elif token not in known_constants:
            misses.append((section, token, "no tracked Python source defines or uses it"))
    return misses


def test_every_rule_citation_outside_how_resolves_against_the_tree() -> None:
    """No rule may send a reader to a module path or constant that is not there."""
    if not _RULES_DIR.is_dir():
        # The harness is removable scaffolding; there is genuinely nothing to
        # assert. See the module docstring on why this is not a skip.
        return

    rules = scan_directory(_RULES_DIR, pattern="*.md")
    assert rules, (
        f"{_RULES_DIR} exists but holds no rule files; a corpus that is present and empty "
        "would make this gate pass vacuously, which is the failure it must not have"
    )

    tracked_paths = _tracked_python_paths()
    known_constants = _constants_defined_anywhere()
    assert tracked_paths, "git ls-files returned no Python files; the resolver has nothing to resolve against"

    failures: list[str] = []
    for rule in rules:
        for section, token, reason in _unresolvable(
            rule.read_text(encoding="utf-8", errors="replace"),
            tracked_paths=tracked_paths,
            known_constants=known_constants,
        ):
            failures.append(f"  {rule.name}\n      `{token}`  in {section}  -> {reason}")

    assert not failures, (
        "rule citations that no longer resolve against the tree "
        f"({len(failures)} across {len(rules)} rules):\n" + "\n".join(sorted(failures)) + "\n\n"
        "Fix the rule on its .vaultspec/rules/ source and propagate with `vaultspec-core sync` "
        "(run `sync --dry-run` first and confirm the blast radius). Never hand-edit the generated "
        "provider copies -- the next sync reverts them. If the citation is a deliberate "
        "counter-example, it belongs in the rule's `## How` section, which this gate excludes."
    )


def test_the_resolver_reports_a_renamed_constant_and_a_moved_module() -> None:
    """Teeth: the two shapes that actually rotted must both be caught.

    Planted rather than drawn from the live corpus, because the corpus is
    expected to be clean and a gate whose only evidence is a clean corpus is
    indistinguishable from one that never inspects anything.
    """
    planted = (
        "## Why\n"
        "The carve-out (`IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS`, "
        "`domain/calculations/registry/_validate_relation_sources.py`) is the named exemption.\n"
        "Ground the read against `src/cadrumo/tests/test_lazy_import_policy.py`.\n"
    )
    misses = _unresolvable(
        planted,
        tracked_paths={"src/cadrumo/domain/calculations/registry/iva_wallet_relation_targets.py"},
        known_constants={"IVA_WALLET_OWNED_RELATION_TARGETS"},
    )
    reported = {token for _, token, _ in misses}
    assert "IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS" in reported, "a renamed constant went unreported"
    assert "src/cadrumo/tests/test_lazy_import_policy.py" in reported, "a deleted module went unreported"
    assert "domain/calculations/registry/_validate_relation_sources.py" in reported, (
        "a module that moved to another path went unreported"
    )


def test_a_counter_example_in_the_how_section_is_not_reported() -> None:
    """The exclusion must hold regardless of the bullet's Good/Bad polarity.

    Both bullets below name something absent on purpose. The `Good:` one is the
    case that defeated a polarity-based filter: renaming the old setting away is
    the good act, so the stale name is quoted approvingly.
    """
    planted = (
        "## How\n"
        "- Bad: a new `_census.py` re-exporting the Spanish-stem type for compatibility.\n"
        "- Good: rename the application-controlled `AEAT_WALLET_DIAGNOSTIC_DUMP_DIR` setting.\n"
    )
    assert not _unresolvable(planted, tracked_paths=set(), known_constants=set())


def test_the_how_exclusion_is_scoped_to_that_section_and_released_after_it() -> None:
    """A later section must not inherit the exclusion from a preceding `## How`.

    Section state is carried line by line, so an off-by-one here would silently
    disable the gate for every section a rule places after its `## How` --
    including `## Source`, where locator citations are common.
    """
    planted = "## How\n- Bad: `_census.py` is the shim to avoid.\n## Source\nAudit cites `dev/gone_module.py`.\n"
    reported = {token for _, token, _ in _unresolvable(planted, tracked_paths=set(), known_constants=set())}
    assert reported == {"dev/gone_module.py"}, f"exclusion leaked past its section: {reported}"


def test_history_is_exempt_only_when_the_rule_declares_the_locator_retired() -> None:
    """The narrated-history exemption must require the declaration, not infer it.

    Past tense alone is not enough. The rot this gate was built for was written
    in the present tense ABOUT A LIVE MODULE and only became historical when the
    module was deleted out from under it -- so a gate that exempted anything
    reading like narrative would have been blind to its own founding case.
    Only an explicit marker exempts, and its absence must still report.
    """
    declared = (
        "## Why\nThe wizard prompter proved the cost. The since-retired\n"
        "`application/wizard/_prompter.py` was the canonical authority.\n"
    )
    assert not _unresolvable(declared, tracked_paths=set(), known_constants=set()), (
        "an explicitly retirement-marked locator was reported as rot"
    )

    undeclared = (
        "## Why\nThe wizard prompter proved the cost.\n`application/wizard/_prompter.py` is the canonical authority.\n"
    )
    reported = {token for _, token, _ in _unresolvable(undeclared, tracked_paths=set(), known_constants=set())}
    assert reported == {"application/wizard/_prompter.py"}, f"an unmarked dead locator escaped the gate: {reported}"
