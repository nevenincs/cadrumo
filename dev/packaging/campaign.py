"""Run the packaging flavor lanes concurrently against one built cohort.

The serial `just` aggregates ran every flavor lane back-to-back; on the
Windows runner the host-portable campaign measured 26.3 minutes because each
lane provisions a fresh venv and re-installs the same wheel cohort, and venv
installs there are disk-bound. Every lane already writes into its own
prefixed work directory under ``var/packaging-smoke/`` and consumes the
cohort directory read-only, so the lanes are disk-disjoint and safe to run
concurrently. This driver builds the cohort exactly once, fans the flavor
lanes out across a bounded worker pool, streams each lane's captured log on
completion (no interleaving), and finishes with the isolation-sensitive
installed-oracles pytest pass, which must stay serial (``-n0 -m "integration
and serial"``).

Profiles mirror the two workflow aggregates:

- ``portable``: the host-portable lane set every OS leg runs
  (core / pip-core / sdist-core / extras / split / browser).
- ``ci``: the Ubuntu superset (adds the dev-environment lane, the
  ``--with-deps`` browser variant instead of the portable one, and the two
  Docker lanes).
- ``quick``: the single per-push probe (core only) used by the quick
  workflow; it exists here so the lane registry is the one source of truth
  for what each profile proves.

This registry is the single authority for what each profile proves; the
profiles below are the only supported lane groupings.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT, UTF_8
from . import proof_cache

_UTF_8: Final[str] = UTF_8
_QUICK_PROOF_KIND: Final[str] = "quick-core-install"
_COHORT_DIR: Final[str] = "var/packaging-smoke-cohort/python"
# Lane concurrency is sized against the PHYSICAL MACHINE, not "a runner": the
# fleet is six runners on two machines (three per box), so a CI leg must
# assume two co-resident jobs. Workflows pass the per-leg value via the env
# below; the default serves an uncontended local run.
_DEFAULT_WORKERS: Final[int] = 3
_WORKERS_ENV: Final[str] = "CADRUMO_PACKAGING_LANE_CONCURRENCY"
# Explicit xdist worker count for the preflight pytest pass. Unset means the
# local default (pyproject addopts' -n auto); CI legs MUST set it because
# -n auto grabs every logical CPU of a machine shared by up to three jobs.
_TEST_WORKERS_ENV: Final[str] = "CADRUMO_TEST_WORKERS"


@dataclass(frozen=True)
class Form:
    """One executable unit of a lane: its invariant reached by one varied axis.

    A form is the thing a profile actually selects and the campaign actually
    runs. Forms of the same lane differ along exactly one axis — the installer,
    the artifact kind, the extras closure, the cohort assertions, or the
    environment — so what a form uniquely proves is what varying that axis
    catches.
    """

    name: str
    module: str
    extra_args: tuple[str, ...] = ()
    takes_cohort: bool = True

    def command(self) -> list[str]:
        """Return the subprocess argv for this form."""
        argv = [sys.executable, "-m", self.module]
        if self.takes_cohort:
            argv += ["--cohort-dir", _COHORT_DIR]
        argv += list(self.extra_args)
        return argv


@dataclass(frozen=True)
class Lane:
    """One invariant, plus every form that reaches it.

    The lane owns the invariant; a form owns one way of reaching it. A proof
    belongs to a lane when it is a property of the product (does the shipped
    cohort install and do grounded tax work), and to a form when it is a
    property of one route to that product state.
    """

    name: str
    invariant: str
    forms: tuple[Form, ...]
    # The lane's BEHAVIOURAL proof and the form that carries it. This is the one
    # class that legitimately runs once per lane: it proves a property of the
    # product, not of one route to it, so running it per form was triplication.
    # Install-level invariants are the opposite and stay per-form — the installed
    # virtualenv is exactly what a form produces, so asserting those once would
    # leave the other installers unproven.
    behavioural_proof: str | None = None
    reference_form: str | None = None

    def form(self, name: str) -> Form:
        """Return this lane's form by name, refusing an unregistered one."""
        for form in self.forms:
            if form.name == name:
                return form
        raise KeyError(f"lane {self.name!r} has no form {name!r}: {[f.name for f in self.forms]}")

    def reference(self) -> Form | None:
        """Return the form carrying this lane's behavioural proof, if it has one."""
        if self.reference_form is None:
            return None
        return self.form(self.reference_form)


_LANES: Final[dict[str, Lane]] = {
    "core": Lane(
        name="core",
        invariant="the exact-version wheel cohort installs and the installed CLI does grounded tax work",
        forms=(
            Form("uv-venv", "dev.packaging.smoke_core"),
            Form("plain-pip", "dev.packaging.smoke_pip_core"),
            Form("sdist", "dev.packaging.smoke_sdist_core"),
            Form("extras", "dev.packaging.all_extra_smoke"),
            Form("joined-cohort", "dev.packaging.smoke_split_install"),
        ),
        behavioural_proof="installed grounded Modelo 200 tax-work oracle",
        reference_form="uv-venv",
    ),
    "browser": Lane(
        name="browser",
        invariant="the installed wheel provisions Chromium and drives a real browser session",
        forms=(
            Form("host", "dev.packaging.smoke_browser"),
            Form("host-with-deps", "dev.packaging.smoke_browser", ("--with-deps",)),
        ),
    ),
    # Standalone rather than a core form: its invariant is not shipped-artifact
    # installability and it consumes no cohort. The precedent for refusing the
    # pressure to force every proof into a form.
    "dev": Lane(
        name="dev",
        invariant="the frozen lock materialises a working developer toolchain",
        forms=(Form("frozen-lock", "dev.packaging.smoke_dev", takes_cohort=False),),
    ),
    # Standalone for the same reason as ``dev``, by a different axis: every core
    # form asks whether the product WORKS once installed, and this one asks what
    # it SAYS when a model-bearing surface is reached without the model-bearing
    # dependencies. Folding it in as a core form would file a refusal proof under
    # an installability invariant it does not test.
    #
    # It consumes the cohort (unlike ``dev``) because the absent state must be
    # reached through the SHIPPED artifact: an extra whose requirements all
    # arrive in the core closure anyway is nominal, and only the built wheel's
    # own metadata can settle that. The lane is host-portable — two stdlib venvs
    # and pip, no host package manager and no container — and the extra it
    # installs and removes is small, so it belongs in every OS leg rather than
    # in the Linux-only superset alone.
    "inference-boundary": Lane(
        name="inference-boundary",
        invariant="the inference boundary refuses instructively without the llm extra, "
        "and that refusal tracks what is installed rather than being a property of the build",
        forms=(Form("wheel", "dev.packaging.smoke_absent_llm"),),
    ),
}

# Profiles select executable units, so they name qualified ``lane/form``
# selectors. The lane, never the profile, owns the invariant.
_PROFILES: Final[dict[str, tuple[str, ...]]] = {
    "portable": (
        "core/uv-venv",
        "core/plain-pip",
        "core/sdist",
        "core/extras",
        "core/joined-cohort",
        "browser/host",
        "inference-boundary/wheel",
    ),
    "ci": (
        "dev/frozen-lock",
        "core/uv-venv",
        "core/plain-pip",
        "core/sdist",
        "core/extras",
        "core/joined-cohort",
        "browser/host-with-deps",
        "inference-boundary/wheel",
    ),
    "quick": ("core/uv-venv",),
}

#: The mixed-marker tree whose contracts the campaign proves on this OS.
_PACKAGING_TESTS: Final[str] = "dev/packaging/tests"
#: The installed-oracle module, owned by its own pass because it builds and
#: installs a closed-world cohort of its own and must not be paid for twice.
_INSTALLED_ORACLES_TESTS: Final[str] = f"{_PACKAGING_TESTS}/test_installed_oracles.py"
#: The one marker-grounded holdout. ``perf``'s registered policy excludes it
#: from every per-push lane and enrols it in the dispatch-only ``ci-full``
#: lane, where a quiet machine makes its CPU-time asserts and advisory wall
#: numbers meaningful; this driver fans flavor lanes across a runner shared by
#: co-resident jobs, which is the condition that policy names.
_PERF_HOLDOUT: Final[str] = "not perf"
#: Wall ceiling for a preflight pass. The dev tree's real install and harness
#: tests legitimately exceed the product suite's 300 s ini ceiling; 900 s still
#: kills a genuine wedge in minutes.
_PREFLIGHT_TIMEOUT_SECONDS: Final[int] = 900


@dataclass(frozen=True)
class PytestPass:
    """One pytest invocation the campaign runs over the packaging test tree.

    The selection is DECLARED here rather than inherited. ``dev/packaging/tests``
    is mixed-marker, and an invocation that omits ``-m`` takes the repository
    default expression, which keeps the ``unit`` cohort and drops every
    integration contract in the directory while still exiting zero -- the
    dangerous variant, because a fully deselected run reports the
    no-tests-collected status a caller notices whereas a partially deselected
    one reports a green summary.

    ``parallel`` is the marker-to-scheduler binding, not a speed knob.
    ``serial`` items read and mutate process-global state, and the collection
    hook DESELECTS them whenever xdist workers are active: a pass that selects
    any of them and runs with workers drops them from the run behind a warning
    rather than executing them.

    Attributes:
        label: The step name printed and used for the pass's basetemp.
        markers: The ``-m`` expression, always stated.
        target: The path this pass collects from.
        parallel: Whether the pass may run across xdist workers.
        ignore: Paths held out of this pass because another pass owns them.
        timeout_seconds: Per-test wall ceiling, or ``None`` for the ini default.
        pinned_basetemp: Whether to pin a repo-local basetemp for the pass.
    """

    label: str
    markers: str
    target: str
    parallel: bool
    ignore: tuple[str, ...] = ()
    timeout_seconds: int | None = None
    pinned_basetemp: bool = False

    def selection_arguments(self) -> tuple[str, ...]:
        """Return the arguments that decide WHICH tests this pass runs."""
        return ("-m", self.markers, self.target, *(f"--ignore={path}" for path in self.ignore))

    def worker_arguments(self, test_workers: int | None) -> tuple[str, ...]:
        """Return the xdist arguments binding this pass to its scheduler.

        A serial pass pins ``-n0`` unconditionally. A parallel pass takes an
        explicit width when one was resolved and otherwise leaves the local
        ``-n auto`` default in place.

        Args:
            test_workers: The resolved preflight worker count, or ``None``.

        Returns:
            The worker arguments to append.
        """
        if not self.parallel:
            return ("-n0",)
        if test_workers is None:
            return ()
        return ("-n", str(test_workers))


#: The preflight's two passes, in run order.
#:
#: Split because the directory holds both cohorts and one invocation cannot
#: carry both schedulers. Together with the installed-oracle pass below they
#: own every test in the directory except the ``perf`` holdout, which is the
#: invariant ``dev/packaging/tests/test_preflight_recipe_selection.py`` proves.
_PREFLIGHT_PASSES: Final[tuple[PytestPass, ...]] = (
    PytestPass(
        label="preflight-tests",
        markers=f"(unit or integration) and not serial and {_PERF_HOLDOUT}",
        target=_PACKAGING_TESTS,
        parallel=True,
        timeout_seconds=_PREFLIGHT_TIMEOUT_SECONDS,
        pinned_basetemp=True,
    ),
    PytestPass(
        label="preflight-serial",
        markers=f"serial and {_PERF_HOLDOUT}",
        target=_PACKAGING_TESTS,
        parallel=False,
        ignore=(_INSTALLED_ORACLES_TESTS,),
        timeout_seconds=_PREFLIGHT_TIMEOUT_SECONDS,
        pinned_basetemp=True,
    ),
)

#: The post-lane serial pass over the installed-oracle module.
_INSTALLED_ORACLES_PASS: Final[PytestPass] = PytestPass(
    label="installed-oracles",
    markers="integration and serial",
    target=_INSTALLED_ORACLES_TESTS,
    parallel=False,
)

#: Every pytest invocation this driver runs, in campaign order.
_PYTEST_PASSES: Final[tuple[PytestPass, ...]] = (*_PREFLIGHT_PASSES, _INSTALLED_ORACLES_PASS)


def resolve_form(selector: str) -> tuple[Lane, Form]:
    """Resolve a ``lane/form`` selector to its lane and form, refusing anything else."""
    lane_name, separator, form_name = selector.partition("/")
    if not separator:
        raise KeyError(f"profile entry {selector!r} is not a qualified 'lane/form' selector")
    try:
        lane = _LANES[lane_name]
    except KeyError:
        raise KeyError(f"profile entry {selector!r} names unknown lane {lane_name!r}") from None
    return lane, lane.form(form_name)


def preflight_basetemp_root(repo_root: Path) -> Path:
    """Return the repo-local basetemp root the preflight passes write under.

    The self-hosted runners execute as the same OS user as interactive sessions
    on the same box, so pytest's default per-user root is shared: two concurrent
    runs fight over the single ``pytest-current`` symlink and one dies in
    ``cleanup_dead_symlinks`` with a permission error AFTER its tests have all
    passed. Handing pytest an explicit basetemp skips the numbered-dir rotation
    and that symlink entirely.

    Args:
        repo_root: The repository root the campaign runs from.

    Returns:
        The root each pass takes its own dedicated subdirectory under.
    """
    return repo_root / "var" / "packaging-smoke" / "pytest-basetemp"


def pytest_pass_argv(pytest_pass: PytestPass, repo_root: Path, test_workers: int | None) -> list[str]:
    """Build the exact interpreter argv the campaign runs for one pass.

    The single construction site for every pytest invocation this driver makes,
    so the selection a gate reads is the selection a lane executes; a second
    hand-built argv is how the driver drifted from its own declared contract
    before.

    Args:
        pytest_pass: The declared pass to build.
        repo_root: The repository root, used to resolve a pinned basetemp.
        test_workers: The resolved preflight worker count, or ``None``.

    Returns:
        The argv, ready for :func:`_run_step`.
    """
    argv = [sys.executable, "-m", "pytest", "-q"]
    if pytest_pass.timeout_seconds is not None:
        argv.append(f"--timeout={pytest_pass.timeout_seconds}")
    if pytest_pass.pinned_basetemp:
        # Per-pass, because pytest REMOVES whatever it is pointed at: one shared
        # directory would have the second pass delete the first pass's retained
        # failure artifacts before anyone could read them.
        argv.append(f"--basetemp={preflight_basetemp_root(repo_root) / pytest_pass.label}")
    argv += pytest_pass.selection_arguments()
    argv += pytest_pass.worker_arguments(test_workers)
    return argv


def campaign_pytest_argv(repo_root: Path, test_workers: int | None) -> tuple[tuple[str, list[str]], ...]:
    """Return every pytest invocation this driver makes, labelled, in order.

    Args:
        repo_root: The repository root the campaign runs from.
        test_workers: The resolved preflight worker count, or ``None``.

    Returns:
        One ``(label, argv)`` pair per declared pass.
    """
    return tuple(
        (pytest_pass.label, pytest_pass_argv(pytest_pass, repo_root, test_workers)) for pytest_pass in _PYTEST_PASSES
    )


def _attempt_step(argv: list[str], repo_root: Path, label: str) -> str | None:
    """Run one step and DESCRIBE its failure rather than raising on it.

    Split out so a caller can decide whether a failure ends the campaign or is
    collected and reported beside its siblings. Every step still runs through
    one execution site.

    Returns:
        A short failure description, or ``None`` when the step succeeded.
    """
    print(f"[campaign] {label}: {' '.join(argv)}", flush=True)
    result = subprocess.run(argv, cwd=repo_root, check=False)
    if result.returncode != 0:
        return f"{label} (exit {result.returncode})"
    return None


def _run_step(argv: list[str], repo_root: Path, label: str) -> None:
    """Run one serial pipeline step, echoing through to the console."""
    failure = _attempt_step(argv, repo_root, label)
    if failure is not None:
        raise SystemExit(f"campaign step failed ({failure})")


def _run_form(selector: str, repo_root: Path, log_dir: Path) -> tuple[str, int, float, Path]:
    """Run one form to a captured log; return (selector, exit, seconds, log path)."""
    _lane, form = resolve_form(selector)
    log_path = log_dir / f"{selector.replace('/', '-')}.log"
    started = time.monotonic()
    with log_path.open("wb") as sink:
        result = subprocess.run(form.command(), cwd=repo_root, stdout=sink, stderr=subprocess.STDOUT, check=False)
    return selector, result.returncode, time.monotonic() - started, log_path


def _worker_count(requested: int | None) -> int:
    """Resolve the lane worker count: CLI flag, then env, then default."""
    if requested is not None:
        return max(1, requested)
    env_value = os.environ.get(_WORKERS_ENV)
    if env_value is not None:
        return max(1, int(env_value))
    return _DEFAULT_WORKERS


def _test_worker_count(requested: int | None) -> int | None:
    """Resolve the preflight pytest worker count: CLI flag, then env, else None.

    ``None`` keeps the local default (addopts ``-n auto``); a resolved value
    becomes an explicit ``-n N`` so a machine shared by co-resident CI jobs is
    never over-subscribed.
    """
    if requested is not None:
        return max(0, requested)
    env_value = os.environ.get(_TEST_WORKERS_ENV)
    if env_value is not None:
        return max(0, int(env_value))
    return None


def main(argv: list[str] | None = None) -> int:
    """Build the cohort once, run the profile's lanes concurrently, then the serial oracles."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(_PROFILES), required=True)
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument(
        "--test-workers",
        type=int,
        default=None,
        help=(
            "Explicit xdist worker count for the preflight pytest pass "
            f"(default: {_TEST_WORKERS_ENV} env, else the local -n auto)."
        ),
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip the dependency/preflight steps when the workflow already ran them as prior steps.",
    )
    args = parser.parse_args(argv)

    repo_root = REPO_ROOT
    selectors = _PROFILES[args.profile]
    # Resolve every selector up front so an unknown lane or form refuses before
    # the cohort build, not after several minutes of wheel work.
    for selector in selectors:
        resolve_form(selector)
    workers = _worker_count(args.max_workers)

    # Do-once memoization (operator directive 2026-07-20): the quick profile's
    # job is to ENSURE a proof exists for this committed source identity on
    # this toolchain, not to unconditionally re-prove it. A prior green quick
    # run for the same (source, environment) fingerprints is carried — with
    # its provenance printed, never silently re-stamped — so a push that left
    # the wheel-relevant scope untouched finishes in seconds. Dirty scope or
    # absent proof falls through to a fresh run. The full campaign's evidence
    # rows are never memoized; this cache is a runner-local speed signal only.
    source_fp: str | None = None
    env_fp = ""
    if args.profile == "quick":
        source_fp = proof_cache.source_fingerprint(repo_root)
        if source_fp is not None:
            env_fp = proof_cache.environment_fingerprint()
            carried = proof_cache.lookup(proof_cache.default_cache_dir(), _QUICK_PROOF_KIND, source_fp, env_fp)
            if carried is not None:
                print(
                    f"[campaign] carried proof: {_QUICK_PROOF_KIND} already proven for "
                    f"source {source_fp[:16]} on env {env_fp} at {carried.created_at} "
                    f"(commit {carried.origin.commit[:12]}, run {carried.origin.run_id or 'local'}); "
                    "nothing to re-prove",
                    flush=True,
                )
                return 0

    if not args.skip_preflight:
        _run_step([sys.executable, "-m", "dev.packaging.dependency_surface"], repo_root, "dependency-surface")
        # pytest mkdirs each pass's basetemp itself but does NOT create its
        # parents, so a clean checkout would die with an internal error here:
        # the campaign only creates `var/packaging-smoke/` later, for the lane
        # logs.
        preflight_basetemp_root(repo_root).mkdir(parents=True, exist_ok=True)
        test_workers = _test_worker_count(args.test_workers)
        # Every preflight pass runs even after one fails, and the campaign
        # reports all of them together. The exit status is unchanged -- any
        # failure still ends the run -- but stopping at the first one made a
        # single wedged module hide every later pass, so a campaign could
        # surface at most one defect per invocation. That is expensive
        # everywhere and ruinous on CI, where the invocation costs an hour of
        # a two-machine fleet. A gate should report what it found, not the
        # first thing it found.
        preflight_failures = [
            failure
            for pytest_pass in _PREFLIGHT_PASSES
            if (
                failure := _attempt_step(
                    pytest_pass_argv(pytest_pass, repo_root, test_workers), repo_root, pytest_pass.label
                )
            )
            is not None
        ]
        if preflight_failures:
            raise SystemExit("campaign preflight failed: " + "; ".join(preflight_failures))

    # Fail before any wheel or venv work if a git-tracked shipped data file is
    # missing from the worktree (seconds). Runs in every profile that reaches
    # here; a carried quick proof returns above, which is safe because a missing
    # tracked file dirties the proof scope and suppresses the carry.
    _run_step([sys.executable, "-m", "dev.packaging.source_preflight"], repo_root, "source-preflight")

    _run_step(
        [sys.executable, "-m", "dev.packaging.python_cohort", "build", "--output", _COHORT_DIR],
        repo_root,
        "build-cohort",
    )

    log_dir = repo_root / "var" / "packaging-smoke" / "lane-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    print(f"[campaign] profile={args.profile} forms={', '.join(selectors)} workers={workers}", flush=True)
    for lane_name in dict.fromkeys(selector.split("/", 1)[0] for selector in selectors):
        print(f"[campaign]   lane {lane_name}: {_LANES[lane_name].invariant}", flush=True)

    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_run_form, selector, repo_root, log_dir) for selector in selectors]
        for future in futures:
            selector, exit_code, seconds, log_path = future.result()
            verdict = "ok" if exit_code == 0 else f"FAILED exit {exit_code}"
            print(f"[campaign] form {selector}: {verdict} in {seconds / 60:.1f} min", flush=True)
            sys.stdout.write(log_path.read_text(encoding=_UTF_8, errors="replace"))
            sys.stdout.flush()
            if exit_code != 0:
                failures.append(selector)

    if failures:
        raise SystemExit(f"packaging forms failed: {', '.join(sorted(failures))}")

    if args.profile == "quick":
        # The per-push probe ends here: the installed-oracles pytest pass is
        # a release-campaign proof and stays out of the ten-minute budget.
        if source_fp is not None:
            path = proof_cache.record(proof_cache.default_cache_dir(), _QUICK_PROOF_KIND, source_fp, env_fp, repo_root)
            print(f"[campaign] proof recorded: {path}", flush=True)
        return 0

    _run_step(
        pytest_pass_argv(_INSTALLED_ORACLES_PASS, repo_root, test_workers=None),
        repo_root,
        _INSTALLED_ORACLES_PASS.label,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
