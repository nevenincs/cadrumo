"""Ratchet gate: the shipped tree's unreachable-module set matches its baseline.

Wires :mod:`dev.quality.unreachable_module_ratchet` into the pytest/CI surface.

The gate it protects is a population, not a direction, and the distinction is
why it earns a place beside the existing import-direction gate in
``cadrumo.tests.test_production_never_imports_test_support``. A test-support
helper written into a product namespace imports nothing from the test tree, so
the direction gate is structurally blind to it; what gives it away is that no
declared entrypoint can reach it. That is this gate's subject.

Both failure directions carry their own control, because they share no code
path and each was silently vacuous at some point during construction: a
regression check that cannot see a new module, and a stale check that never
fires, both look exactly like a clean tree. So the synthetic cases below prove
a planted defect IS reported and that its healthy neighbour is NOT, and the
frozen-prefix case proves the carve-out suppresses both directions rather than
only the one it was written for.

The exclusive-supplier deferral carries the same burden and more, because it
exempts by graph property rather than by declaration and so has no line
anyone must write. Its controls are what bound it: a module with a non-frozen
importer and a module with no importer at all must both stay red, and with
nothing frozen nothing may be deferred at all. Each of those would pass if
the closure were "unreachable, and only unreachable modules import it",
which would exempt the entire backlog.

The defects are planted in a throwaway ``tmp_path`` tree built from outside the
repository. No production module is monkeypatched and the contributor's working
tree is never mutated, so a crashed run leaves no residue and a peer's sweep
cannot commit the plant.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ..audit.unreachable_code import EntryPoint, ShippedTreeSpec, scan_unreachable_code
from ..quality.unreachable_module_ratchet import (
    BASELINE_PATH,
    IntentionalReachabilityDisposition,
    IntentionalReachabilityKind,
    UnreachableBaseline,
    evaluate,
    run_gate,
    unreachable_modules,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_EXCLUDES = ("src/pkg/tests", "src/pkg/tests/**", "src/pkg/**/tests", "src/pkg/**/tests/**")


def _write(root: Path, relative: str, text: str = "") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _planted_tree(root: Path) -> ShippedTreeSpec:
    """A package whose entrypoint reaches ``live`` and never reaches ``stranded``."""
    _write(root, "src/pkg/__init__.py")
    _write(root, "src/pkg/cli.py", "from .live import go\n\n\ndef main() -> None:\n    go()\n")
    _write(root, "src/pkg/live.py", "def go() -> None: ...\n")
    _write(root, "src/pkg/stranded.py", "def helper() -> None: ...\n")
    _write(root, "src/pkg/deferred/__init__.py")
    _write(root, "src/pkg/deferred/screen.py", "def render() -> None: ...\n")
    return ShippedTreeSpec(
        repo_root=root,
        src_root=root / "src",
        package="pkg",
        entry_points=(EntryPoint("pkg.cli", "main"),),
        exclude_globs=_EXCLUDES,
    )


@pytest.fixture
def planted(tmp_path: Path) -> ShippedTreeSpec:
    return _planted_tree(tmp_path)


def test_the_live_shipped_tree_matches_its_committed_baseline() -> None:
    """The real gate. A regression or a stale entry fails here with the module named."""
    verdict = run_gate()

    assert verdict.is_clean, verdict.report()


def test_address_component_vocabulary_is_a_visible_intentional_design_time_authority() -> None:
    """The vocabulary remains factual scanner output but not actionable runtime debt."""
    baseline = UnreachableBaseline.load()
    expected = IntentionalReachabilityDisposition(
        module="cadrumo.core.address_components",
        kind=IntentionalReachabilityKind.DESIGN_TIME_AUTHORITY,
        rationale=(
            "Canonical AEAT address-component vocabulary constraining producer-key declarations; "
            "it deliberately has no runtime transport caller."
        ),
    )

    assert expected in baseline.intentional
    assert expected.module not in baseline.allowed
    verdict = run_gate()
    assert expected in verdict.intentional
    assert expected.module not in verdict.regressions


def test_the_committed_baseline_names_only_modules_the_tree_still_reports() -> None:
    """A baseline entry that no longer corresponds to anything is the stale direction.

    Asserted separately from the combined verdict so a stale entry cannot be
    read as a regression when the gate fails.
    """
    verdict = run_gate()

    assert verdict.stale == (), f"paid-down entries still in {BASELINE_PATH.name}: {verdict.stale}"


def test_a_new_unreachable_module_is_reported_as_a_regression(planted: ShippedTreeSpec) -> None:
    """A module the entrypoint cannot reach, absent from the baseline, fails the gate."""
    result = scan_unreachable_code(planted)
    baseline = UnreachableBaseline(allowed=frozenset(), frozen_prefixes=())

    verdict = evaluate(result, baseline)

    assert "pkg.stranded" in verdict.regressions
    assert verdict.intentional == ()
    assert not verdict.is_clean


def test_the_reachable_neighbour_is_not_reported(planted: ShippedTreeSpec) -> None:
    """The control: the module the entrypoint DOES reach is never a finding.

    Without this the regression check above would pass just as happily if the
    scan reported every module in the tree.
    """
    result = scan_unreachable_code(planted)

    reported = unreachable_modules(result)

    assert "pkg.stranded" in reported
    assert "pkg.live" not in reported
    assert "pkg.cli" not in reported


def test_a_baselined_module_passes_while_it_remains_unreachable(planted: ShippedTreeSpec) -> None:
    """An accepted entry is not a failure; that is what makes the backlog workable."""
    result = scan_unreachable_code(planted)
    baseline = UnreachableBaseline(
        allowed=frozenset({"pkg.stranded", "pkg.deferred"}),
        frozen_prefixes=(),
    )

    verdict = evaluate(result, baseline)

    assert verdict.is_clean, verdict.report()


def test_a_listed_intentional_module_passes_but_remains_visible(planted: ShippedTreeSpec) -> None:
    """An intentional disposition is separate from an allowed actionable backlog entry."""
    result = scan_unreachable_code(planted)
    disposition = IntentionalReachabilityDisposition(
        module="pkg.stranded",
        kind=IntentionalReachabilityKind.DESIGN_TIME_AUTHORITY,
        rationale="Synthetic design-time vocabulary authority.",
    )
    baseline = UnreachableBaseline(
        allowed=frozenset({"pkg.deferred"}),
        frozen_prefixes=(),
        intentional=(disposition,),
    )

    verdict = evaluate(result, baseline)

    assert verdict.is_clean, verdict.report()
    assert verdict.intentional == (disposition,)
    assert "pkg.stranded" not in verdict.regressions


def test_an_intentional_module_does_not_exempt_an_unlisted_unreachable_neighbour(planted: ShippedTreeSpec) -> None:
    """An exact intentional disposition cannot turn the whole population into an exception."""
    _write(planted.repo_root, "src/pkg/unlisted.py", "def helper() -> None: ...\n")
    result = scan_unreachable_code(planted)
    disposition = IntentionalReachabilityDisposition(
        module="pkg.stranded",
        kind=IntentionalReachabilityKind.DESIGN_TIME_AUTHORITY,
        rationale="Synthetic design-time vocabulary authority.",
    )
    baseline = UnreachableBaseline(
        allowed=frozenset({"pkg.deferred"}),
        frozen_prefixes=(),
        intentional=(disposition,),
    )

    verdict = evaluate(result, baseline)

    assert verdict.intentional == (disposition,)
    assert verdict.regressions == ("pkg.unlisted",)
    assert not verdict.is_clean


def test_a_paid_down_baseline_entry_is_reported_as_stale(planted: ShippedTreeSpec) -> None:
    """Naming a module the tree no longer reports fails, so the baseline cannot rot."""
    result = scan_unreachable_code(planted)
    baseline = UnreachableBaseline(
        allowed=frozenset({"pkg.stranded", "pkg.deferred", "pkg.already_deleted"}),
        frozen_prefixes=(),
    )

    verdict = evaluate(result, baseline)

    assert verdict.stale == ("pkg.already_deleted",)
    assert not verdict.is_clean


def test_a_paid_down_intentional_disposition_is_reported_as_stale(planted: ShippedTreeSpec) -> None:
    """An intentional exception cannot stay after the scanner stops reporting its module."""
    result = scan_unreachable_code(planted)
    disposition = IntentionalReachabilityDisposition(
        module="pkg.already_deleted",
        kind=IntentionalReachabilityKind.DESIGN_TIME_AUTHORITY,
        rationale="Synthetic authority that has been retired.",
    )
    baseline = UnreachableBaseline(
        allowed=frozenset({"pkg.stranded", "pkg.deferred"}),
        frozen_prefixes=(),
        intentional=(disposition,),
    )

    verdict = evaluate(result, baseline)

    assert verdict.stale == ()
    assert verdict.stale_intentional == (disposition,)
    assert not verdict.is_clean


def test_a_frozen_prefix_is_excluded_in_both_directions(planted: ShippedTreeSpec) -> None:
    """A deferred cluster neither has to be baselined nor has to persist.

    Both directions are asserted together: the cluster is reported by the audit
    yet absent from ``allowed`` (which would otherwise be a regression), and
    ``allowed`` names a member that is gone (which would otherwise be stale).
    """
    result = scan_unreachable_code(planted)
    baseline = UnreachableBaseline(
        allowed=frozenset({"pkg.stranded"}),
        frozen_prefixes=("pkg.deferred",),
    )

    verdict = evaluate(result, baseline)

    assert verdict.is_clean, verdict.report()
    assert "pkg.deferred" in verdict.frozen


@pytest.mark.parametrize(
    ("contents", "message"),
    (
        (
            "allowed = []\nfrozen_prefixes = []\n"
            '[[intentional]]\nmodule = "pkg.stranded"\nkind = "unknown"\nrationale = "reason"\n',
            "unknown intentional reachability kind",
        ),
        (
            'allowed = ["pkg.stranded"]\nfrozen_prefixes = []\n'
            '[[intentional]]\nmodule = "pkg.stranded"\n'
            'kind = "design_time_authority"\nrationale = "reason"\n',
            "allowed and intentional reachability entries overlap",
        ),
        (
            'allowed = []\nfrozen_prefixes = ["pkg"]\n'
            '[[intentional]]\nmodule = "pkg.stranded"\n'
            'kind = "design_time_authority"\nrationale = "reason"\n',
            "intentional reachability entries cannot be frozen",
        ),
        (
            'allowed = ["pkg.stranded"]\nfrozen_prefixes = ["pkg"]\n',
            "allowed reachability entries cannot be frozen",
        ),
        (
            "allowed = []\nfrozen_prefixes = []\n"
            '[[intentional]]\nmodule = 1\nkind = "design_time_authority"\nrationale = "reason"\n',
            "intentional entries require string module, kind, and rationale",
        ),
        (
            "allowed = []\nfrozen_prefixes = []\n"
            '[[intentional]]\nmodule = "   "\nkind = "design_time_authority"\nrationale = "reason"\n',
            "intentional reachability disposition module must be non-empty",
        ),
        (
            "allowed = []\nfrozen_prefixes = []\n"
            '[[intentional]]\nmodule = "pkg.stranded"\nkind = "design_time_authority"\nrationale = "   "\n',
            "needs a rationale",
        ),
    ),
)
def test_malformed_or_overlapping_intentional_dispositions_are_refused(
    tmp_path: Path, contents: str, message: str
) -> None:
    """Configuration must not turn an unreviewed or out-of-scope exception into a pass."""
    baseline_path = tmp_path / "baseline.toml"
    baseline_path.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        UnreachableBaseline.load(baseline_path)


def test_an_unscannable_tree_refuses_rather_than_reporting_clean(tmp_path: Path) -> None:
    """A gate that cannot parse the tree must fail loudly, not pass by default.

    The dangerous failure is not a crash but a false all-clear: if an
    unparseable module let the scan return an empty finding set, every
    baselined entry would read as paid down and the gate would report the
    boundary repaired at the moment it stopped being able to see it.
    """
    _write(
        tmp_path,
        "pyproject.toml",
        # A complete, readable packaging config, so the refusal below is caused
        # by the unparseable module and not by a config the scan could not read.
        '[project]\nname = "cadrumo"\nversion = "0"\n'
        '[project.scripts]\ncadrumo = "cadrumo.cli:main"\n'
        "[tool.hatch.build.targets.wheel]\nexclude = []\n",
    )
    _write(tmp_path, "src/cadrumo/__init__.py")
    _write(tmp_path, "src/cadrumo/cli.py", "def main(:\n")
    baseline = tmp_path / "baseline.toml"
    baseline.write_text("allowed = []\nfrozen_prefixes = []\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="ratchet unproven"):
        run_gate(tmp_path, baseline_path=baseline)


def _supplier_tree(root: Path) -> ShippedTreeSpec:
    """A deferred cluster, its exclusive suppliers, and the shapes that must stay actionable.

    ``deferred`` is the frozen cluster. ``projection`` is the supplier only that
    cluster imports, and ``deep`` is the supplier only ``projection`` imports,
    so the two hops together decide whether the deferral is transitive.
    ``shared`` is imported by the cluster AND by the actionable ``orphan``, and
    ``lonely`` is imported by nothing at all: those two are the controls that
    prove the deferral is exclusive rather than contagious.
    """
    _write(root, "src/pkg/__init__.py")
    _write(root, "src/pkg/cli.py", "from .live import go\n\n\ndef main() -> None:\n    go()\n")
    _write(root, "src/pkg/live.py", "def go() -> None: ...\n")
    _write(root, "src/pkg/deferred/__init__.py")
    _write(
        root,
        "src/pkg/deferred/screen.py",
        "from ..projection import project\nfrom ..shared import helper\n\n\ndef render() -> None:\n"
        "    project()\n    helper()\n",
    )
    _write(root, "src/pkg/projection.py", "from .deep import compute\n\n\ndef project() -> None:\n    compute()\n")
    _write(root, "src/pkg/deep.py", "def compute() -> None: ...\n")
    _write(root, "src/pkg/shared.py", "def helper() -> None: ...\n")
    _write(root, "src/pkg/orphan.py", "from .shared import helper\n\n\ndef stray() -> None:\n    helper()\n")
    _write(root, "src/pkg/lonely.py", "def nobody() -> None: ...\n")
    return ShippedTreeSpec(
        repo_root=root,
        src_root=root / "src",
        package="pkg",
        entry_points=(EntryPoint("pkg.cli", "main"),),
        exclude_globs=_EXCLUDES,
    )


@pytest.fixture
def suppliers(tmp_path: Path) -> ShippedTreeSpec:
    return _supplier_tree(tmp_path)


@pytest.fixture
def supplier_baseline() -> UnreachableBaseline:
    """The frozen cluster declared, and every genuinely actionable module accepted."""
    return UnreachableBaseline(
        allowed=frozenset({"pkg.shared", "pkg.orphan", "pkg.lonely"}),
        frozen_prefixes=("pkg.deferred",),
    )


def test_a_supplier_only_a_frozen_cluster_imports_is_deferred_and_named(
    suppliers: ShippedTreeSpec, supplier_baseline: UnreachableBaseline
) -> None:
    """The projection a deferred cluster alone consumes is not this gate's to adjudicate.

    The deferral must be visible, so the importer that carries it is asserted
    too: a silent exemption and a reported deferral pass the gate identically,
    and only the reported one survives the cluster being abandoned.
    """
    result = scan_unreachable_code(suppliers)

    verdict = evaluate(result, supplier_baseline)

    assert verdict.is_clean, verdict.report()
    deferred = {entry.module: entry.deferring_importers for entry in verdict.derived}
    assert deferred["pkg.projection"] == ("pkg.deferred.screen",)
    assert "pkg.projection" not in verdict.regressions
    assert "pkg.projection" in verdict.report()


def test_the_deferral_reaches_a_supplier_of_a_supplier(
    suppliers: ShippedTreeSpec, supplier_baseline: UnreachableBaseline
) -> None:
    """One hop is not the boundary: what the deferred projection alone needs is deferred too.

    Stopping at the first hop would defer a module while still failing on the
    only module it depends upon, which is not a state anyone can act on.
    """
    result = scan_unreachable_code(suppliers)

    verdict = evaluate(result, supplier_baseline)

    deferred = {entry.module: entry.deferring_importers for entry in verdict.derived}
    assert deferred["pkg.deep"] == ("pkg.projection",)


def test_a_supplier_with_an_actionable_importer_stays_a_finding(suppliers: ShippedTreeSpec) -> None:
    """Teeth: one importer outside the deferred set keeps the module adjudicated.

    ``pkg.shared`` is imported by the frozen cluster, so a deferral keyed on
    "some frozen importer" would clear it. It is also imported by the
    actionable ``pkg.orphan``, and that is what must keep it red.
    """
    result = scan_unreachable_code(suppliers)
    baseline = UnreachableBaseline(
        allowed=frozenset({"pkg.orphan", "pkg.lonely"}),
        frozen_prefixes=("pkg.deferred",),
    )

    verdict = evaluate(result, baseline)

    assert "pkg.shared" in verdict.regressions
    assert "pkg.shared" not in {entry.module for entry in verdict.derived}
    assert not verdict.is_clean


def test_a_module_nothing_imports_is_never_deferred(suppliers: ShippedTreeSpec) -> None:
    """Teeth: capability that lost its last caller stays the finding this gate exists for.

    A module with no importers supplies no deferred cluster. Treating an empty
    importer set as "no importer outside the cluster" would silently clear
    every orphan in the tree, which is the exact defect the ratchet catches.
    """
    result = scan_unreachable_code(suppliers)
    baseline = UnreachableBaseline(
        allowed=frozenset({"pkg.shared", "pkg.orphan"}),
        frozen_prefixes=("pkg.deferred",),
    )

    verdict = evaluate(result, baseline)

    assert "pkg.lonely" in verdict.regressions
    assert "pkg.lonely" not in {entry.module for entry in verdict.derived}
    assert not verdict.is_clean


def test_no_deferral_is_derived_without_a_frozen_prefix(suppliers: ShippedTreeSpec) -> None:
    """The control: the closure is anchored on a declared freeze, not on unreachability itself.

    With nothing frozen, every module in the same tree is actionable. Without
    this, the tests above would pass just as happily if the closure deferred
    any unreachable module whose importers were also unreachable -- which
    would exempt the whole backlog.
    """
    result = scan_unreachable_code(suppliers)
    baseline = UnreachableBaseline(allowed=frozenset(), frozen_prefixes=())

    verdict = evaluate(result, baseline)

    assert verdict.derived == ()
    assert {"pkg.projection", "pkg.deep", "pkg.shared", "pkg.orphan", "pkg.lonely"} <= set(verdict.regressions)


def test_a_baseline_entry_the_deferral_now_covers_is_reported_as_stale(suppliers: ShippedTreeSpec) -> None:
    """A module that becomes deferred must leave the actionable list, not sit in both.

    Otherwise the backlog would keep naming modules the gate no longer
    adjudicates, and a later reader could not tell an accepted debt from a
    line the deferral quietly took over.
    """
    result = scan_unreachable_code(suppliers)
    baseline = UnreachableBaseline(
        allowed=frozenset({"pkg.shared", "pkg.orphan", "pkg.lonely", "pkg.projection"}),
        frozen_prefixes=("pkg.deferred",),
    )

    verdict = evaluate(result, baseline)

    assert verdict.stale == ("pkg.projection",)
    assert not verdict.is_clean


def test_the_live_tui_projections_are_deferred_by_their_frozen_consumers() -> None:
    """The real tree: every importer that defers a module is frozen or deferred itself.

    Asserted against the committed baseline rather than a synthetic tree, so a
    deferral that starts resting on a module outside the deferred cluster fails
    here even though the gate's set comparison would still be clean.
    """
    baseline = UnreachableBaseline.load()
    verdict = run_gate()

    assert verdict.derived, verdict.report()
    deferred_modules = {entry.module for entry in verdict.derived}
    for entry in verdict.derived:
        assert entry.deferring_importers, entry.module
        for importer in entry.deferring_importers:
            carried = baseline.is_frozen(importer) or importer in deferred_modules
            assert carried, f"{entry.module} deferred by non-deferred importer {importer}"


def test_every_intentional_rationale_names_a_reader_that_still_reads_it() -> None:
    """A disposition's justification must stay true, or the module is orphaned.

    Four of the five design-time authorities are excused because a specific
    dev-side file reads them: delete that reader and the module becomes
    genuinely unreachable while this gate stays green, because the disposition
    still says otherwise. The rationale is the evidence, so it has to be
    checkable evidence.

    Only paths a rationale actually names are checked. A disposition that
    claims no reader -- ``core.address_components`` deliberately has none --
    asserts nothing here and is left alone.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    referenced = re.compile(r"dev/[\w/]+\.py")

    unread: list[str] = []
    for disposition in UnreachableBaseline.load().intentional:
        leaf = disposition.module.rsplit(".", 1)[-1]
        for claimed in referenced.findall(disposition.rationale):
            reader = repo_root / claimed
            if not reader.is_file():
                unread.append(f"{disposition.module}: {claimed} no longer exists")
            elif leaf not in reader.read_text(encoding="utf-8"):
                unread.append(f"{disposition.module}: {claimed} no longer mentions {leaf}")

    assert not unread, "intentional dispositions whose stated reader is gone: " + "; ".join(unread)
