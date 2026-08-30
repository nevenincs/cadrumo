"""Facade export-integrity gate: every name a package facade promises exists at HEAD.

Wires :mod:`dev.quality.facade_export_scan` into the pytest/CI surface. The defect it
pins broke ``cadrumo.core`` -- imported by every package -- for over three hours
on 2026-08-01 without a single failing test, because of an asymmetry worth
stating plainly:

    A facade that exports a symbol whose definition is uncommitted imports
    perfectly in every agent's working tree, and only fails on a clean
    checkout.

Each agent held the missing half locally. Local suites were green, CI was not,
and no worktree-reading check could have told the difference. That is why this
gate reads the git object store at a pinned revision instead of the filesystem,
and why running it against a working tree is refused rather than merely
discouraged: a working-tree run would have passed on the day of the outage.

Both directions are checked, because a facade breaks in two ways that share no
code path (a symbol exported but never defined; a symbol imported by committed
consumers that the facade never provides) -- and each direction carries its own
control. During development a forward-only control passed happily while the
mirror direction was structurally blind, so a control validates one direction of
one instrument, never "the scan".

The anti-tautology proof is :func:`test_scanner_recovers_the_known_historical_breaks`:
the scan is run against the commit preceding the repairs and must recover all
five real breaks. A parser regression that makes the scan silently vacuous --
mis-reading ``__all__: list[str] = [...]``, ``type X = ...``, or a lazy
``__getattr__`` -- turns the clean HEAD result into a false all-clear, and every
one of those was a real miss during this gate's own construction. That test is
what makes the zero mean *repaired* rather than *blind*.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ..quality.facade_export_scan import REPO_ROOT, ScanResult, scan

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Parent of the first repair commit, when ``cadrumo.core`` was broken in both
#: directions. Pinned as the scanner's anti-tautology fixture: an instrument that
#: cannot recover these cannot be trusted to report their absence.
_BROKEN_REV = "abffef56d36aa953aea39554ebbdff914c839ca4"

#: The four forward breaks live at ``_BROKEN_REV`` -- each a name ``cadrumo.core``
#: re-exported from a submodule that did not define it.
_KNOWN_FORWARD_BREAKS = frozenset(
    {
        "CorpusAnchorResolutionError",
        "RegistrySelectorPeriodCode",
        "normalise_product_identity_references",
        "resolve_anchored_extracted_unit",
    },
)

#: The mirror break: defined nowhere in the facade, imported by committed
#: consumers. Invisible to the forward direction, which is the point.
_KNOWN_MIRROR_BREAK = "foreign_asset_declaration_threshold"


def _rev_is_available(rev: str) -> bool:
    """Whether ``rev`` exists in this clone.

    A shallow clone legitimately lacks history. The fixture test then cannot
    run, and saying so is honest; asserting against an absent object would fail
    for a reason that has nothing to do with facade integrity.
    """
    return (
        subprocess.run(  # noqa: S603 - resolved executable, fixed argv, no shell
            ["git", "cat-file", "-e", f"{rev}^{{commit}}"],  # noqa: S607 - fixed argv resolved by the platform PATH
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


@pytest.fixture(scope="module")
def head_scan() -> ScanResult:
    """Scan the resolved HEAD commit once for every check in this module."""
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],  # noqa: S607 - fixed argv resolved by the platform PATH
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return scan(head)


def test_no_facade_exports_a_symbol_that_does_not_exist(head_scan: ScanResult) -> None:
    """Forward direction: every name a facade imports or exports is defined at HEAD."""
    assert head_scan.forward == [], (
        "facade(s) name a symbol that does not exist at HEAD -- a clean checkout "
        "will fail to import these packages even though every working tree "
        "resolves them:\n  " + "\n  ".join(b.describe() for b in head_scan.forward)
    )


def test_no_consumer_imports_a_symbol_its_facade_does_not_provide(
    head_scan: ScanResult,
) -> None:
    """Mirror direction: every committed cross-package import resolves at HEAD."""
    assert head_scan.mirror == [], (
        "committed consumer(s) import a name their facade does not provide at "
        "HEAD:\n  " + "\n  ".join(b.describe() for b in head_scan.mirror)
    )


def test_head_has_no_unparseable_modules(head_scan: ScanResult) -> None:
    """A module the scanner cannot parse is a hole in both directions above."""
    assert head_scan.syntax_errors == [], (
        "module(s) at HEAD do not parse, so the facade scan could not inspect "
        "them:\n  " + "\n  ".join(head_scan.syntax_errors)
    )


def test_scan_population_is_non_trivial(head_scan: ScanResult) -> None:
    """A scan over nothing reports zero breaks.

    Guards the clean results above against the failure mode where the revision
    resolves but the listing comes back empty, which would make every assertion
    in this module vacuously true.
    """
    assert head_scan.module_count > 1000, head_scan.module_count
    assert head_scan.facade_count > 100, head_scan.facade_count


def test_scanner_recovers_the_known_historical_breaks() -> None:
    """Anti-tautology proof: the scan finds five real breaks at a known-broken revision.

    This is the check that gives the clean HEAD result its meaning. Both
    directions are asserted separately because each was independently blind at
    some point during development: the annotated ``__all__`` form and the lazy
    ``__getattr__`` pattern each, on their own, made the mirror direction skip
    ``cadrumo.core`` while the forward direction stayed healthy and green.
    """
    if not _rev_is_available(_BROKEN_REV):
        pytest.fail(
            f"the pinned anti-tautology fixture commit {_BROKEN_REV} is not present "
            "in this clone, so the facade scanner is unproven here. Fetch full "
            "history (this gate's clean result is meaningless without it).",
        )

    broken = scan(_BROKEN_REV)

    forward_symbols = {b.symbol for b in broken.forward}
    assert forward_symbols == set(_KNOWN_FORWARD_BREAKS), (
        "the scanner no longer recovers exactly the known forward breaks at "
        f"{_BROKEN_REV}; a parser regression makes the HEAD result a false "
        f"all-clear. got={sorted(forward_symbols)}"
    )
    assert {b.facade for b in broken.forward} == {"cadrumo.core"}

    mirror_symbols = {b.symbol for b in broken.mirror}
    assert mirror_symbols == {_KNOWN_MIRROR_BREAK}, (
        "the scanner no longer recovers the known mirror break at "
        f"{_BROKEN_REV}; the mirror direction is blind. got={sorted(mirror_symbols)}"
    )
    assert {b.target for b in broken.mirror} == {"cadrumo.core"}


def _run_git(args: list[str], *, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)  # noqa: S603,S607 - test-owned argv, no shell


def _init_fixture_repo(root: Path) -> str:
    """Create a throwaway repo holding one sound facade, and return its commit."""
    pkg = root / "src" / "cadrumo" / "zzz_probe"
    pkg.mkdir(parents=True)
    (pkg / "_models.py").write_text("class Present:\n    pass\n", encoding="utf-8")
    (pkg / "__init__.py").write_text(
        'from .models import Present\n\n__all__ = ["Present"]\n',
        encoding="utf-8",
    )
    _run_git(["init", "-q"], cwd=root)
    _run_git(["config", "user.email", "gate@example.invalid"], cwd=root)
    _run_git(["config", "user.name", "facade gate fixture"], cwd=root)
    _run_git(["add", "-A"], cwd=root)
    _run_git(["commit", "-q", "-m", "sound facade"], cwd=root)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],  # noqa: S607 - fixed argv resolved by the platform PATH
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def test_scanner_reads_git_not_the_working_tree(tmp_path: Path) -> None:
    """The scan must not consult the filesystem for module content.

    Runs entirely inside a throwaway repository. An earlier version of this test
    planted the break in this project's own ``cadrumo.core.observability``
    facade and restored it in a ``finally``, which was a genuine fleet hazard:
    concurrent agents importing that module during the window hit an
    ImportError they could not attribute, a hard kill would have left the module
    broken, and a peer's pathspec commit of that path inside the window would
    have committed the planted break to HEAD -- a pathspec commit takes
    working-tree content. Never mutate a tracked, shared, imported file to make
    a test's point.

    The isolated repo also makes the assertion stronger rather than weaker.
    Planting an *untracked* file here would prove nothing: the scanner
    enumerates through ``git ls-tree``, so an untracked path is invisible to a
    filesystem-reading implementation too, and the check would pass vacuously.
    The property under test is whether module CONTENT comes from the blob or
    from disk, so the planted change has to live in a file the scan already
    enumerates.
    """
    rev = _init_fixture_repo(tmp_path)
    before = scan(rev, repo_root=tmp_path)
    assert before.forward == [], "the fixture facade should start sound"

    facade = tmp_path / "src" / "cadrumo" / "zzz_probe" / "__init__.py"
    facade.write_text(
        'from .models import Present, ZzzPlantedAbsentSymbol\n\n__all__ = ["Present"]\n',
        encoding="utf-8",
    )

    after = scan(rev, repo_root=tmp_path)
    assert after.forward == before.forward, (
        "the scan changed when the working tree changed, so it is reading the "
        "filesystem rather than the pinned revision"
    )

    # Non-vacuity: the planted break must be detectable at all. Committing it
    # and re-scanning the NEW revision has to surface it -- otherwise the
    # unchanged result above would prove nothing about where content is read
    # from, only that the break was undetectable either way.
    _run_git(["add", "-A"], cwd=tmp_path)
    _run_git(["commit", "-q", "-m", "plant an absent symbol"], cwd=tmp_path)
    committed_rev = subprocess.run(
        ["git", "rev-parse", "HEAD"],  # noqa: S607 - fixed argv resolved by the platform PATH
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    once_committed = scan(committed_rev, repo_root=tmp_path)
    assert [b.symbol for b in once_committed.forward] == ["ZzzPlantedAbsentSymbol"], (
        "the planted break is not detected even once committed, so the unchanged-on-disk assertion above is vacuous"
    )


def test_planted_break_is_detected_in_each_direction() -> None:
    """Both directions detect a synthetic break, independent of git history.

    Complements the historical fixture: this runs even in a shallow clone, and
    proves the two checks can fire at all. It is deliberately not a substitute
    -- a synthetic control shows the instrument fires somewhere, while the
    historical fixture shows it fires on the real defect shape.
    """
    import ast

    from ..quality.facade_export_scan import module_facts

    facts = module_facts(
        ast.parse(
            "from .models import RunTrace\ntype SomeAlias = int\n__all__: list[str] = ['RunTrace', 'SomeAlias']\n",
        ),
    )
    # Annotated __all__ parsed, PEP 695 alias bound: both were real misses.
    assert facts.exported == ["RunTrace", "SomeAlias"]
    assert "SomeAlias" in facts.bound
    assert "RunTrace" in facts.bound
    assert "ZzzAbsent" not in facts.bound

    lazy_facts = module_facts(
        ast.parse(
            "def __getattr__(name):\n"
            "    if name == 'LazilyResolved':\n"
            "        from .x import LazilyResolved\n"
            "        return LazilyResolved\n"
            "    raise AttributeError(name)\n",
        ),
    )
    assert lazy_facts.has_lazy_getattr
    assert "LazilyResolved" in lazy_facts.lazy
    assert "ZzzAbsent" not in lazy_facts.lazy


def test_no_committed_import_targets_a_module_absent_at_head(head_scan: ScanResult) -> None:
    """Every ``cadrumo`` module a committed import names exists at HEAD.

    The untracked-module variant of the same outage: a module present in every
    working tree but never added to git makes its importers look committed and
    sound while a clean checkout cannot resolve them. The symbol-level checks
    are blind to it, because there is no target module against which to compare
    a name -- so this is reported separately rather than folded in.
    """
    assert head_scan.missing_modules == [], (
        "committed import(s) name a module that does not exist at HEAD -- most "
        "likely a module that is still untracked, which resolves in every "
        "worktree and fails only on a clean checkout:\n  "
        + "\n  ".join(b.describe() for b in head_scan.missing_modules)
    )


def test_explicit_dunder_init_targets_are_not_reported_missing(head_scan: ScanResult) -> None:
    """``from ..__init__ import x`` addresses the package, not a module named ``__init__``.

    Without that normalisation the scan reports a real, working import as a
    missing module. Pinned because the false positive is indistinguishable from
    a genuine untracked-module break in the gate's output, and would train a
    reader to dismiss the check.
    """
    assert not any(b.target.endswith(".__init__") for b in head_scan.missing_modules)
