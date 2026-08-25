"""Hard gate: no TEST may sit outside every declared pytest lane.

An unreachable test is worse than a missing one. It reports nothing while
looking like coverage, so its rot is invisible until somebody happens to read
it. That state is not hypothetical here: the fourteen channel-generator tests
sat in it long enough for two independent breakages to accumulate, and the
author of the second had no signal at all.

The unit of the finding is the TEST, not the file. A file-level verdict is both
too noisy and too quiet at once, and this repository has one file proving each
half: ``test_secure_sql.py`` was reported entirely unreachable because a single
``os_keychain`` test dragged the flattened marker set out of every lane (too
noisy), while the genuine defect underneath -- that one test really is selected
by no lane -- is invisible to any model that answers only "does SOME test in
this file run" (too quiet). Reporting per test resolves both.

No stored baseline and no allowlist. The worklist is recomputed from the tree on
every run, so coverage can only ratchet up: a new test outside every lane fails
immediately rather than being absorbed into an accepted set that nobody revisits.

THIS MODULE'S LOCATION IS LOAD-BEARING. It lives under ``src/cadrumo/tests`` and
is marked ``unit`` deliberately: a guard against unreachable tests must itself
sit inside the selection every lane already runs, or it is unreachable by
exactly the defect it exists to catch. Measured, not assumed -- from here it is
run by NINE lanes (four justfile recipes plus five workflow invocations across
``ci.yml``, ``ci-full.yml``, ``aeat-drift-detector.yml``, and
``agent-harness-eval.yml``). Its predecessor lived under ``dev/ci/tests``, which
only ``ci.yml`` reached, so the strongest reachability model in the tree was
itself among the weakest-reached files in it. Do not move this back under
``dev/``.

It replaces two gates that asked overlapping questions, and it deliberately
kept the weaker one's only advantage. The retired ``dev/``-only gate was
path-only and could not see marker exclusion; this one asks BOTH questions, so
it strictly subsumes it -- verified before deletion at 178 ``dev/`` test files,
with zero findings the retired gate would have caught and this one misses.

Two questions, not one, and the second exists because the first has blind spots:

* Per-test: does some lane's path scope cover this file AND its marker
  expression select this test's own effective markers?
* Path-level: does ANY lane name this file at all? Cheap, weaker, and retained
  because the per-test question is blind to a module holding no test functions
  and to a tracked file absent from disk. Both classes are empty in this tree
  today; neither is impossible, and a consolidation that silently drops the
  check would be a regression wearing a consolidation's clothes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .._paths import REPO_ROOT
from ..ci.lane_reachability import (
    Lane,
    analyse_reachability,
    ci_invoked_lanes,
    ci_invoked_recipes,
    configured_testpaths,
    declared_lanes,
    discover_test_files,
    expression_selects,
    marker_sets_in,
    tracked_test_files,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ROOT: Path = REPO_ROOT

#: The markers whose tests CI genuinely cannot run, each because a PRECONDITION
#: is absent from a headless runner rather than because nobody wired a lane.
#: Every one is documented with its reason in pyproject's marker table, and
#: every one has a justfile recipe that enrolls it for the environment that can.
#: This is the honest holdout set, and it is the only accepted answer to "why
#: does CI never run this test".
_CI_INCAPABLE_MARKERS: frozenset[str] = frozenset(
    {
        # Needs LibreOffice for binary .xls conversion; not in the dependency set.
        "external_tool",
        # Reads a real external service; opt-in, and never enabled on CI.
        "aeat_live",
        # Asserts on the OS credential store, which is a property of an
        # interactive logon session a headless runner does not have.
        "os_keychain",
        # Queries the resident vaultspec-rag service, a separate product this
        # project does not install.
        "resident_service",
    },
)


def _synthetic_repository(root: Path, *, lane: str) -> None:
    """Write a minimal tree carrying one declared lane and no tests yet."""
    (root / "pyproject.toml").write_text('testpaths = ["src"]\n', encoding="utf-8")
    (root / "justfile").write_text(f"check:\n    {lane}\n", encoding="utf-8")


def _write_test(path: Path, body: str) -> None:
    """Write a test module, creating its parents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_every_test_is_selected_by_some_declared_lane() -> None:
    """The gate itself. Hard-cut: no baseline, no allowlist, no exceptions."""
    report = analyse_reachability(_ROOT)

    assert report.unreachable == (), (
        "these tests are selected by no declared lane, so nothing runs them:\n  "
        + "\n  ".join(entry.describe() for entry in report.unreachable)
        + "\n\nEither add a lane that names the path AND accepts the marker, or "
        "change the marker. A test nobody runs reads as coverage and is not."
    )


def test_every_test_ci_cannot_run_declares_why() -> None:
    """The gate that matters: DECLARED is not RUN, and only one excuse counts.

    ``test_every_test_is_selected_by_some_declared_lane`` asks whether the
    repository declares a lane, and a justfile recipe satisfies it. That is the
    right answer to its question and a dangerously reassuring answer to the one
    a reader usually means, because a recipe no workflow invokes is a lane that
    has never run. Two of them proved it at once: ``just test-integration``
    (370 integration-marked modules under ``src/`` -- every cross-layer test in
    the product) and ``just test-dev-tooling`` (ten ``dev/`` subsystems, whose
    own recipe docstring says "the gates that no other lane reaches") were both
    declared, both healthy, and named by no workflow. The declared-lane gate
    reported full coverage over tests CI had never once executed.

    So this asks the stronger question, and accepts exactly one answer for a
    test CI does not run: that a precondition is genuinely absent from a
    headless runner, declared by one of the markers in
    ``_CI_INCAPABLE_MARKERS``. "Nobody wired a lane" is not on the list.
    """
    report = analyse_reachability(_ROOT, lanes=ci_invoked_lanes(_ROOT))

    unexplained = [entry for entry in report.unreachable if not (entry.markers & _CI_INCAPABLE_MARKERS)]

    assert unexplained == [], (
        "no CI lane runs these tests, and none of them carries a marker saying why:\n  "
        + "\n  ".join(entry.describe() for entry in unexplained)
        + "\n\nA justfile recipe is NOT enough -- a recipe no workflow invokes has "
        "never run. Either invoke the owning recipe from a workflow, or carry a "
        f"marker from {sorted(_CI_INCAPABLE_MARKERS)} if the precondition truly "
        "cannot exist on a runner."
    )


def test_the_ci_invoked_model_is_strictly_stronger_than_the_declared_one() -> None:
    """The two questions must not silently collapse into one.

    If ``ci_invoked_lanes`` ever returned everything ``declared_lanes`` does,
    the gate above would still pass while asking nothing -- the exact
    false-green shape this module exists to refuse, one level up. This pins the
    gap as real: recipes exist that no workflow invokes (``test-os-keychain``,
    ``test-workbook-parity``, ``test-live``, ``test-resident-service``, the
    coverage and smoke conveniences), and they must stay excluded.
    """
    declared = declared_lanes(_ROOT)
    invoked = ci_invoked_lanes(_ROOT)

    assert set(invoked) <= set(declared), "a CI-invoked lane that is not declared is a parser fault"
    assert len(invoked) < len(declared), (
        "every declared lane now reads as CI-invoked; either the parser broke or "
        "the distinction collapsed, and the CI-reachability gate is now vacuous"
    )

    invoked_recipes = ci_invoked_recipes(_ROOT)
    # The integration lane is invoked as its two SEPARATE passes, not through the
    # combined `test-integration` convenience: CI carries an independent verdict
    # per pass, because the parallel pass is deterministic while the serial pass
    # includes wall-clock budgets that flake on a shared machine. `test-integration`
    # therefore stays declared-but-not-CI-invoked, which is correct rather than a
    # hole -- the union of the two passes covers exactly what it selects.
    expected_invoked = {
        "test-unit",
        "test-dev-ci",
        "test-integration-parallel",
        "test-integration-serial",
        "test-dev-tooling",
        "docs-check",
    }
    assert expected_invoked <= invoked_recipes
    assert not ({"test-os-keychain", "test-workbook-parity", "test-live"} & invoked_recipes)


def test_a_recipe_no_workflow_invokes_is_declared_but_not_ci_invoked(tmp_path: Path) -> None:
    """Anti-tautology for the distinction, against a synthetic tree.

    Without this the CI-reachability gate could pass because the recipe parser
    finds nothing rather than because CI genuinely reaches the lanes, and those
    two outcomes are indistinguishable from the verdict alone.
    """
    (tmp_path / "pyproject.toml").write_text('testpaths = ["src"]\n', encoding="utf-8")
    (tmp_path / "justfile").write_text(
        "wired:\n    pytest -q src -m unit\n\norphan:\n    pytest -q other/tests -m unit\n",
        encoding="utf-8",
    )
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(
        "name: Probe\njobs:\n  build:\n    steps:\n      - run: just wired\n",
        encoding="utf-8",
    )

    assert ci_invoked_recipes(tmp_path) == frozenset({"wired"})

    declared = declared_lanes(tmp_path)
    invoked = ci_invoked_lanes(tmp_path)
    assert {lane.recipe for lane in declared} == {"wired", "orphan"}
    assert {lane.recipe for lane in invoked} == {"wired"}

    # The orphan recipe's path is covered when declaration is the question, and
    # uncovered when execution is.
    module = "import pytest\n\npytestmark = [pytest.mark.unit]\n\n\ndef test_a() -> None:\n    assert True\n"
    _write_test(tmp_path / "other" / "tests" / "test_only_the_orphan_reaches.py", module)
    files = discover_test_files(tmp_path)

    assert analyse_reachability(tmp_path, lanes=declared, files=files).unreachable == ()
    stranded = analyse_reachability(tmp_path, lanes=invoked, files=files).unreachable
    assert [entry.path for entry in stranded] == ["other/tests/test_only_the_orphan_reaches.py"]


def test_recipe_discovery_reads_run_blocks_not_english_prose(tmp_path: Path) -> None:
    """ "just" is an ordinary English word, and these workflows use it as one.

    Scanning raw workflow text harvested `is`, `uses`, and `natively` as recipe
    names, from a step named "Ensure just is available" and a comment reading
    "provision just natively". Three phantom recipes is harmless only until one
    of those words IS a recipe name -- at which point an unreached lane reads as
    reached, and the gate above goes quiet about a real hole.
    """
    (tmp_path / "pyproject.toml").write_text('testpaths = ["src"]\n', encoding="utf-8")
    (tmp_path / "justfile").write_text("uses:\n    pytest -q src -m unit\n", encoding="utf-8")
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(
        "name: Probe\n"
        "jobs:\n"
        "  build:\n"
        "    steps:\n"
        "      # taiki-e mangles its path; provision just natively\n"
        '      - name: "Ensure just is available"\n'
        "        run: scoop install just\n",
        encoding="utf-8",
    )

    # `scoop install just` ends in the bare word, and the prose names a real
    # recipe. Neither is an invocation.
    assert ci_invoked_recipes(tmp_path) == frozenset()


def test_no_test_file_sits_outside_every_lane_path() -> None:
    """The path-level half, retained because the per-test half is blind to two inputs.

    A module with no test functions, and a tracked file absent from disk, both
    yield no tests -- so the per-test question reports nothing however orphaned
    they are. Both classes are empty today and neither is impossible, which is
    exactly why this is a gate and not a comment.
    """
    report = analyse_reachability(_ROOT)

    assert report.unnamed == (), (
        "these test files sit outside every lane's path scope, so no marker "
        "expression could ever reach them:\n  " + "\n  ".join(report.unnamed)
    )


def test_the_path_check_catches_what_the_per_test_check_cannot(tmp_path: Path) -> None:
    """The blind spot, proven rather than asserted.

    A ``test_*.py`` holding no test functions is invisible to the per-test
    model -- there is nothing to report unreachable. Without the path-level
    question, consolidating onto the stronger model would have dropped this
    finding silently, and nobody would have noticed for a long time.
    """
    _synthetic_repository(tmp_path, lane="pytest -q src -m unit")
    _write_test(tmp_path / "outside" / "tests" / "test_no_tests_at_all.py", "HELPER = 1\n")

    report = analyse_reachability(tmp_path, files=discover_test_files(tmp_path))

    assert report.unreachable == (), "a testless module offers no test to call unreachable"
    assert report.unnamed == ("outside/tests/test_no_tests_at_all.py",)


def test_the_gate_measured_a_real_corpus() -> None:
    """A parser that found nothing would report perfect coverage.

    This is the gate's own failure mode: zero lanes means every test is
    unreachable, but zero *analysed files* would make the gate pass vacuously.
    Both sides are pinned so a broken reader cannot read as a clean tree.
    """
    report = analyse_reachability(_ROOT)
    lanes = declared_lanes(_ROOT)

    assert len(lanes) > 10, "lane discovery collapsed; the gate would be measuring nothing"
    assert report.analysed > 1000, f"only {report.analysed} files analysed; the reader has stopped matching"
    assert len(report.skipped) < report.analysed // 10, (
        f"{len(report.skipped)} tracked files were unreadable against {report.analysed} analysed; "
        "that is mass-skip, not a peer mid-edit"
    )


def test_tracked_discovery_ignores_untracked_scratch(tmp_path: Path) -> None:
    """Discovery is git-backed, and the real tree is the control.

    Many agents work this tree at once. An untracked path is a peer's
    uncommitted work that no lane could name and CI will never see, so counting
    it would red a SHARED gate on private state whose only remedies are both
    wrong: wire an uncommitted path into a lane, or delete a peer's work.
    """
    tracked = tracked_test_files(_ROOT)
    assert len(tracked) > 1000, "tracked discovery collapsed"

    scratch = _ROOT / "dev" / "ci" / "tests" / "test_untracked_scratch_probe.py"
    assert scratch not in tracked, "an untracked probe path must never be discovered"

    # The same filter over an on-disk walk would have to see it if it existed.
    assert all(path.name.startswith("test_") for path in tracked)


def test_a_planted_orphan_reds_the_gate(tmp_path: Path) -> None:
    """Anti-tautology, against an injectable root rather than the real tree.

    Without this the gate could pass because its discovery is broken rather than
    because the tree is clean, and those two outcomes look identical.
    """
    _synthetic_repository(tmp_path, lane="pytest -q src -m unit")
    unit_module = "import pytest\n\npytestmark = [pytest.mark.unit]\n\n\ndef test_{name}() -> None:\n    assert True\n"
    _write_test(tmp_path / "src" / "tests" / "test_covered.py", unit_module.format(name="a"))

    clean = analyse_reachability(tmp_path, files=discover_test_files(tmp_path))
    assert clean.unreachable == ()
    assert clean.analysed == 1

    _write_test(tmp_path / "outside" / "tests" / "test_orphan.py", unit_module.format(name="b"))

    dirty = analyse_reachability(tmp_path, files=discover_test_files(tmp_path))
    assert [entry.path for entry in dirty.unreachable] == ["outside/tests/test_orphan.py"]
    assert [entry.test for entry in dirty.unreachable] == ["test_b"]


def test_a_marker_only_exclusion_also_reds_the_gate(tmp_path: Path) -> None:
    """The half a path-only model would miss, proven separately."""
    _synthetic_repository(tmp_path, lane="pytest -q src -m unit")
    # In the lane's path, but carrying a marker the lane's expression rejects.
    _write_test(
        tmp_path / "src" / "tests" / "test_serial_only.py",
        "import pytest\n\n"
        "pytestmark = [pytest.mark.integration, pytest.mark.serial]\n\n\n"
        "def test_c() -> None:\n    assert True\n",
    )

    report = analyse_reachability(tmp_path, files=discover_test_files(tmp_path))
    assert [entry.path for entry in report.unreachable] == ["src/tests/test_serial_only.py"]


def test_one_excluded_test_does_not_condemn_its_reachable_siblings(tmp_path: Path) -> None:
    """The false positive that motivated per-test granularity, pinned.

    This is the exact shape of ``src/cadrumo/tests/test_secure_sql.py``: module
    marked ``unit``, one test additionally marked ``os_keychain``, and every
    lane excluding that marker. Flattening the file's markers into one set makes
    the WHOLE file read as unreachable while its unit siblings run daily.
    """
    _synthetic_repository(tmp_path, lane="pytest -q src -m 'unit and not os_keychain'")
    _write_test(
        tmp_path / "src" / "tests" / "test_mixed.py",
        "import pytest\n\n"
        "pytestmark = [pytest.mark.unit]\n\n\n"
        "def test_ordinary() -> None:\n    assert True\n\n\n"
        "@pytest.mark.os_keychain\ndef test_needs_keychain() -> None:\n    assert True\n",
    )

    report = analyse_reachability(tmp_path, files=discover_test_files(tmp_path))

    # The excluded test is reported; its sibling is not, and the file is not.
    assert [entry.test for entry in report.unreachable] == ["test_needs_keychain"]
    assert report.affected_files() == ("src/tests/test_mixed.py",)


def test_an_unreadable_tracked_file_is_skipped_not_reported(tmp_path: Path) -> None:
    """A peer staging a deletion must not read as an orphaned test.

    ``git ls-files`` lists a path the working tree no longer holds while a peer
    stages its removal. Treating that as "no tests, therefore unreachable" would
    red a shared gate on another agent's in-flight work; treating it as unmarked
    would be worse still. It is counted, not judged.
    """
    _synthetic_repository(tmp_path, lane="pytest -q src -m unit")
    absent = tmp_path / "src" / "tests" / "test_deleted_by_a_peer.py"

    report = analyse_reachability(tmp_path, files=[absent])

    assert report.unreachable == ()
    assert report.skipped == ("src/tests/test_deleted_by_a_peer.py",)
    assert report.analysed == 0


def test_marker_and_path_are_both_required() -> None:
    """Reachability needs both halves, which is why the real hole survived.

    The generator tests were excluded twice over: lanes reaching their path
    rejected their marker, and lanes accepting their marker did not reach their
    path. A model checking only one half calls them reachable.
    """
    right_path_wrong_marker = Lane(source="t", paths=("packaging/homebrew/tests",), marker_expression="unit")
    right_marker_wrong_path = Lane(source="t", paths=("dev/ci/tests",), marker_expression="serial")
    target = "packaging/homebrew/tests/test_homebrew_generate.py"
    markers = frozenset({"integration", "serial"})

    assert right_path_wrong_marker.covers(target)
    assert not expression_selects(right_path_wrong_marker.marker_expression, markers)
    assert expression_selects(right_marker_wrong_path.marker_expression, markers)
    assert not right_marker_wrong_path.covers(target)


def test_an_ignore_equals_form_excludes_the_file_but_not_its_sibling(tmp_path: Path) -> None:
    """``--ignore=PATH`` is one token, and must exclude exactly that file.

    Before ``Lane`` carried ``exclusions``, it had no concept of ``--ignore`` at
    all, so a lane whose scope was ``src`` covered a file its own invocation
    excludes -- the exact shape ``just test-integration`` takes for the harness
    modules, via the single-token ``{{harness_exclusions}}`` expansion.
    """
    (tmp_path / "pyproject.toml").write_text('testpaths = ["src"]\n', encoding="utf-8")
    (tmp_path / "justfile").write_text(
        "check:\n    pytest -q src -m unit --ignore=src/tests/test_excluded.py\n",
        encoding="utf-8",
    )
    module = "import pytest\n\npytestmark = [pytest.mark.unit]\n\n\ndef test_a() -> None:\n    assert True\n"
    _write_test(tmp_path / "src" / "tests" / "test_excluded.py", module)
    _write_test(tmp_path / "src" / "tests" / "test_kept.py", module)

    lanes = declared_lanes(tmp_path)
    assert len(lanes) == 1
    lane = lanes[0]
    assert lane.exclusions == ("src/tests/test_excluded.py",)
    assert lane.covers("src/tests/test_kept.py")
    assert not lane.covers("src/tests/test_excluded.py")

    report = analyse_reachability(tmp_path, files=discover_test_files(tmp_path))
    assert [entry.path for entry in report.unreachable] == ["src/tests/test_excluded.py"]


def test_an_ignore_space_form_excludes_the_file_the_same_way(tmp_path: Path) -> None:
    """``--ignore PATH`` is two tokens; the exclusion must not depend on spelling."""
    (tmp_path / "pyproject.toml").write_text('testpaths = ["src"]\n', encoding="utf-8")
    (tmp_path / "justfile").write_text(
        "check:\n    pytest -q src -m unit --ignore src/tests/test_excluded.py\n",
        encoding="utf-8",
    )
    module = "import pytest\n\npytestmark = [pytest.mark.unit]\n\n\ndef test_a() -> None:\n    assert True\n"
    _write_test(tmp_path / "src" / "tests" / "test_excluded.py", module)
    _write_test(tmp_path / "src" / "tests" / "test_kept.py", module)

    lane = declared_lanes(tmp_path)[0]
    assert lane.exclusions == ("src/tests/test_excluded.py",)
    assert lane.covers("src/tests/test_kept.py")
    assert not lane.covers("src/tests/test_excluded.py")


def test_justfile_variable_interpolation_resolves_before_ignore_parsing(tmp_path: Path) -> None:
    """The real defect: an unresolved ``{{name}}`` is never a valid ``--ignore`` value.

    ``just test-integration`` writes its exclusion as ``{{harness_exclusions}}``,
    a variable this module cannot see the value of by reading justfile text
    alone. A reader that tokenises the literal eight-character string
    ``{{harness_exclusions}}`` either treats it as a nonsense path or silently
    drops it -- either way the exclusion is lost and the lane reads as covering
    a file it does not run.
    """
    (tmp_path / "pyproject.toml").write_text('testpaths = ["src"]\n', encoding="utf-8")
    (tmp_path / "justfile").write_text(
        'excluded_file := "src/tests/test_excluded.py"\n\n'
        "check:\n    pytest -q src -m unit --ignore={{excluded_file}}\n",
        encoding="utf-8",
    )
    module = "import pytest\n\npytestmark = [pytest.mark.unit]\n\n\ndef test_a() -> None:\n    assert True\n"
    _write_test(tmp_path / "src" / "tests" / "test_excluded.py", module)
    _write_test(tmp_path / "src" / "tests" / "test_kept.py", module)

    lane = declared_lanes(tmp_path)[0]
    assert lane.exclusions == ("src/tests/test_excluded.py",)
    assert lane.covers("src/tests/test_kept.py")
    assert not lane.covers("src/tests/test_excluded.py")


def test_the_harness_modules_are_excluded_by_the_integration_lanes_but_covered_by_the_harness_lane() -> None:
    """The concrete defect this module was fixed to close, pinned against the real justfile.

    ``just test-integration`` writes ``{{harness_exclusions}}``, which expands
    to ``--ignore=`` for both harness modules -- so the integration lanes must
    not cover them, even though their ``paths`` scope is ``src``. They stay
    reachable regardless: ``just test-harness`` names them positionally and is
    CI-invoked from ``ci.yml``, which is what keeps them off the unreachable
    list rather than this fix accidentally orphaning them.
    """
    lanes = declared_lanes(_ROOT)
    targets = (
        "src/cadrumo/tests/test_worker_count_hook_harness.py",
        "dev/harness/test_full_corpus_collectability_harness.py",
    )

    integration_lanes = [lane for lane in lanes if lane.recipe in {"test-integration", "test-integration-parallel"}]
    assert integration_lanes, "the integration recipe(s) must still be declared"
    for lane in integration_lanes:
        for target in targets:
            assert not lane.covers(target), f"{lane.recipe} must not cover {target}, it is --ignore'd"

    harness_lanes = [lane for lane in lanes if lane.recipe == "test-harness"]
    assert harness_lanes, "test-harness must still be declared"
    for target in targets:
        assert any(lane.covers(target) for lane in harness_lanes), f"test-harness must still cover {target}"


def test_an_unresolved_template_residue_does_not_silently_widen_a_lanes_paths() -> None:
    """Pins the exact shape of a real defect this module carried for hours, undetected.

    A justfile edit moved literal recipe paths behind `{{name}}` variables.
    Before template resolution existed, `_paths_of` found no positional-path
    token on the affected lines, so `_pytest_invocations` fell back to the
    configured testpaths -- and `test-harness`'s lane silently widened from two
    named files to the WHOLE `src/cadrumo` tree. Nothing reds when this
    happens: a wider lane only ever makes MORE tests look reachable, so the
    unreachable-test gate stays green throughout. The only way to catch a
    regression here is to positively pin what a lane's paths must equal, which
    is what this test does. Do not read either assertion as trivia -- deleting
    them removes the only signal this failure mode has.

    Two lanes, two different unresolved-residue shapes:

    - `test-unit` is genuinely pathless (no positional path argument at all)
      AND carries an unresolvable `{{ if durations == "" {...} else {...} }}`
      construct. Its correct behaviour is to inherit `configured_testpaths`;
      this pins that the residue does not accidentally produce a non-empty (and
      therefore narrower-than-correct) or a wrong path list.
    - `docs-check` carries three real explicit paths sitting next to an
      unresolved `{{workers}}` reference. `workers` is a RECIPE PARAMETER
      (`docs-check workers="auto":`), not a top-level justfile variable, so
      `just --evaluate` structurally cannot resolve it -- it will never appear
      in `_just_variables`'s output. This pins that the neighbouring bare
      residue token does not swallow, corrupt, or crowd out the real paths.
    """
    lanes = declared_lanes(_ROOT)

    unit_lanes = [lane for lane in lanes if lane.recipe == "test-unit"]
    assert unit_lanes, "test-unit must still be declared"
    for lane in unit_lanes:
        assert lane.paths == configured_testpaths(_ROOT), (
            "test-unit's unresolved duration-flag residue must not change its inherited "
            f"testpaths fallback; got {lane.paths!r}"
        )

    docs_check_lanes = [lane for lane in lanes if lane.recipe == "docs-check"]
    assert docs_check_lanes, "docs-check must still be declared"
    for lane in docs_check_lanes:
        assert lane.paths == (
            "dev/docs/tests",
            "dev/docs/apidocs/tests",
            "src/cadrumo/tests/test_docstring_core_struct_links.py",
        ), f"docs-check's unresolved `workers` template residue must not swallow its real paths; got {lane.paths!r}"


@pytest.mark.parametrize(
    ("expression", "markers", "selected"),
    [
        pytest.param("unit or (integration and not serial)", {"integration", "serial"}, False, id="serial-excluded"),
        pytest.param("unit or (integration and not serial)", {"integration"}, True, id="integration-included"),
        pytest.param("unit or (integration and not serial)", {"unit"}, True, id="unit-included"),
        pytest.param("serial", {"integration", "serial"}, True, id="serial-selected"),
        pytest.param("docs", {"unit", "hex_core"}, False, id="docs-lane-rejects-unit"),
        pytest.param("not integration", {"unit"}, True, id="negation"),
        pytest.param(None, {"anything"}, True, id="no-expression-selects-all"),
        pytest.param("((((", {"unit"}, False, id="unparseable-is-not-selection"),
    ],
)
def test_expression_evaluation_is_structural_not_substring(
    expression: str | None,
    markers: set[str],
    selected: bool,
) -> None:
    """``and``/``or``/``not`` and precedence decide, not string containment.

    ``unit or (integration and not serial)`` contains the substring "serial"
    while rejecting serial-marked files, so a containment check would invert the
    answer on the exact case this gate exists to catch.
    """
    assert expression_selects(expression, frozenset(markers)) is selected


def test_markers_are_collected_per_test_from_every_scope(tmp_path: Path) -> None:
    """Module, class, and function markers all reach the test that carries them."""
    module = tmp_path / "test_scopes.py"
    module.write_text(
        "import pytest\n\n"
        "pytestmark = [pytest.mark.integration]\n\n\n"
        "@pytest.mark.serial\n"
        "class TestGroup:\n"
        "    @pytest.mark.hex_core\n"
        "    def test_inner(self) -> None:\n        assert True\n\n\n"
        "def test_outer() -> None:\n    assert True\n",
        encoding="utf-8",
    )

    resolved = marker_sets_in(module)
    assert resolved is not None
    by_name = {entry.test: entry.markers for entry in resolved}

    assert by_name["test_inner"] == frozenset({"integration", "serial", "hex_core"})
    assert by_name["test_outer"] == frozenset({"integration"})


def test_marker_sets_distinguish_absent_from_testless(tmp_path: Path) -> None:
    """None means unreadable; an empty tuple means read and holding no tests.

    Collapsing the two is what would let a peer's staged deletion be reported as
    a file whose tests nothing runs.
    """
    empty = tmp_path / "test_no_tests.py"
    empty.write_text("import pytest\n\npytestmark = [pytest.mark.unit]\n", encoding="utf-8")

    assert marker_sets_in(empty) == ()
    assert marker_sets_in(tmp_path / "test_never_written.py") is None
