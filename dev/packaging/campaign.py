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

The lane registry is conformance-pinned by ``tests/test_campaign.py`` so the
profiles cannot silently drift from the per-lane ``just`` recipes.
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

from . import proof_cache

_UTF_8: Final[str] = "utf-8"
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
class Lane:
    """One flavor lane: a module invocation proving one install surface."""

    name: str
    module: str
    extra_args: tuple[str, ...] = ()
    takes_cohort: bool = True

    def command(self) -> list[str]:
        """Return the subprocess argv for this lane."""
        argv = [sys.executable, "-m", self.module]
        if self.takes_cohort:
            argv += ["--cohort-dir", _COHORT_DIR]
        argv += list(self.extra_args)
        return argv


_LANES: Final[dict[str, Lane]] = {
    "core": Lane("core", "dev.packaging.smoke_core"),
    "pip-core": Lane("pip-core", "dev.packaging.smoke_pip_core"),
    "sdist-core": Lane("sdist-core", "dev.packaging.smoke_sdist_core"),
    "extras": Lane("extras", "dev.packaging.smoke_extras"),
    "split": Lane("split", "dev.packaging.smoke_split_install"),
    "browser": Lane("browser", "dev.packaging.smoke_browser"),
    "browser-linux": Lane("browser-linux", "dev.packaging.smoke_browser", ("--with-deps",)),
    "dev": Lane("dev", "dev.packaging.smoke_dev", takes_cohort=False),
    "docker-core": Lane("docker-core", "dev.packaging.smoke_docker"),
    "docker-browser": Lane("docker-browser", "dev.packaging.smoke_docker", ("--browser",)),
}

_PROFILES: Final[dict[str, tuple[str, ...]]] = {
    "portable": ("core", "pip-core", "sdist-core", "extras", "split", "browser"),
    "ci": (
        "dev",
        "core",
        "pip-core",
        "sdist-core",
        "extras",
        "split",
        "browser-linux",
        "docker-core",
        "docker-browser",
    ),
    "quick": ("core",),
}


def _run_step(argv: list[str], repo_root: Path, label: str) -> None:
    """Run one serial pipeline step, echoing through to the console."""
    print(f"[campaign] {label}: {' '.join(argv)}", flush=True)
    result = subprocess.run(argv, cwd=repo_root, check=False)
    if result.returncode != 0:
        raise SystemExit(f"campaign step failed ({label}): exit {result.returncode}")


def _run_lane(lane: Lane, repo_root: Path, log_dir: Path) -> tuple[Lane, int, float, Path]:
    """Run one lane to a captured log; return (lane, exit, seconds, log path)."""
    log_path = log_dir / f"{lane.name}.log"
    started = time.monotonic()
    with log_path.open("wb") as sink:
        result = subprocess.run(lane.command(), cwd=repo_root, stdout=sink, stderr=subprocess.STDOUT, check=False)
    return lane, result.returncode, time.monotonic() - started, log_path


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

    repo_root = Path(__file__).resolve().parents[2]
    lane_names = _PROFILES[args.profile]
    lanes = [_LANES[name] for name in lane_names]
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
        preflight_argv = [sys.executable, "-m", "pytest", "dev/packaging/tests", "-q", "--timeout=900"]
        test_workers = _test_worker_count(args.test_workers)
        if test_workers is not None:
            preflight_argv += ["-n", str(test_workers)]
        _run_step(
            # The dev tree's real install/harness tests legitimately exceed
            # the product suite's 300 s ini ceiling; 900 s still kills a
            # genuine wedge in minutes.
            preflight_argv,
            repo_root,
            "preflight-tests",
        )

    # Fail before any wheel or venv work if a git-tracked shipped data file is
    # missing from the worktree (seconds; runs in every profile, quick included).
    _run_step([sys.executable, "-m", "dev.packaging.source_preflight"], repo_root, "source-preflight")

    _run_step(
        [sys.executable, "-m", "dev.packaging.python_cohort", "build", "--output", _COHORT_DIR],
        repo_root,
        "build-cohort",
    )

    log_dir = repo_root / "var" / "packaging-smoke" / "lane-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    print(f"[campaign] profile={args.profile} lanes={', '.join(lane_names)} workers={workers}", flush=True)

    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_run_lane, lane, repo_root, log_dir) for lane in lanes]
        for future in futures:
            lane, exit_code, seconds, log_path = future.result()
            verdict = "ok" if exit_code == 0 else f"FAILED exit {exit_code}"
            print(f"[campaign] lane {lane.name}: {verdict} in {seconds / 60:.1f} min", flush=True)
            sys.stdout.write(log_path.read_text(encoding=_UTF_8, errors="replace"))
            sys.stdout.flush()
            if exit_code != 0:
                failures.append(lane.name)

    if failures:
        raise SystemExit(f"packaging lanes failed: {', '.join(sorted(failures))}")

    if args.profile == "quick":
        # The per-push probe ends here: the installed-oracles pytest pass is
        # a release-campaign proof and stays out of the ten-minute budget.
        if source_fp is not None:
            path = proof_cache.record(proof_cache.default_cache_dir(), _QUICK_PROOF_KIND, source_fp, env_fp, repo_root)
            print(f"[campaign] proof recorded: {path}", flush=True)
        return 0

    _run_step(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-n0",
            "-m",
            "integration and serial",
            "dev/packaging/tests/test_installed_oracles.py",
        ],
        repo_root,
        "installed-oracles",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
