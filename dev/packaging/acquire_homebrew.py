"""Reacquire Cadrumo through the public Homebrew tap and repeat installed work.

This post-publication check taps the public Homebrew tap, installs ``cadrumo``,
proves the formula's declared source digests match the promoted cohort sdists,
and repeats the grounded installed CLI tax-work oracle against the
tap-installed command. The formula is CLI-only by scope: ``cadrumo-mcp`` ships
in the sibling ``cadrumo-harness`` distribution, which Homebrew does not carry.
It refuses instructively when ``brew`` is unavailable or the public tap does
not yet carry the formula (implements post-release-distribution plan row
P03.S17).
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from .._paths import UTF_8
from ._acquire_common import (
    EXPECTED_ORACLE_TARGET_VALUE,
    AcquisitionError,
    require_command_succeeded,
)
from ._command import CommandResult, run_command
from ._hashing import sha256_path
from .cohort_manifest import load_release_cohort
from .distribution_evidence_emit import emit_installed_oracle_evidence
from .evidence import AcquisitionIdentity, DestinationIdentity
from .installed_tax_oracle import run_installed_tax_oracle
from .python_cohort import PythonCohort, load_python_cohort

_UTF_8: Final[str] = UTF_8
# The account-scoped tap (repo `nevenincs/homebrew-tap`) serving every product
# published under this account, not a per-product tap.
_DEFAULT_TAP: Final[str] = "nevenincs/tap"
_FORMULA_NAME: Final[str] = "cadrumo"
_DEFAULT_DISTRIBUTION_EVIDENCE_DIR: Final[Path] = Path("var/distribution-install-readiness")

# Homebrew formula source-archive name -> promoted cohort sdist digest name.
# The formula ships the root as its stable archive and both data distributions
# as named resources; every one is a source distribution in the cohort.
_FORMULA_SOURCE_TO_COHORT: Final[dict[str, str]] = {
    "cadrumo": "cadrumo-sdist",
    "cadrumo-data-manuals": "cadrumo-data-manuals-sdist",
    "cadrumo-data-official": "cadrumo-data-official-sdist",
}


def _formula_checksum(record: dict[str, Any]) -> str:
    """Return a Homebrew url record's SHA-256, tolerating the checksum/sha256 keys."""
    for key in ("checksum", "sha256"):
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    raise AcquisitionError(f"Homebrew source record carries no checksum: {record!r}")


def verify_homebrew_formula_digests(formula: dict[str, Any], cohort: PythonCohort) -> dict[str, str]:
    """Verify a ``brew info --json`` formula's source digests against the cohort.

    Args:
        formula: One formula object from ``brew info --json=v2`` (``formulae[0]``).
        cohort: The promoted Python cohort carrying the expected sdist digests.

    Returns:
        A mapping of formula source name to its verified SHA-256.

    Raises:
        AcquisitionError: On a missing source, a missing digest, or any drift.
    """
    stable = formula.get("urls", {}).get("stable")
    if not isinstance(stable, dict):
        raise AcquisitionError("Homebrew formula declares no stable source archive")
    observed: dict[str, dict[str, Any]] = {"cadrumo": stable}
    for resource in formula.get("resources", []):
        if isinstance(resource, dict) and resource.get("name") in _FORMULA_SOURCE_TO_COHORT:
            observed[str(resource["name"])] = resource

    verified: dict[str, str] = {}
    for source_name, cohort_key in _FORMULA_SOURCE_TO_COHORT.items():
        record = observed.get(source_name)
        if record is None:
            raise AcquisitionError(f"Homebrew formula is missing the {source_name!r} source archive")
        actual = _formula_checksum(record)
        expected = cohort.sha256[cohort_key]
        if actual != expected:
            raise AcquisitionError(
                f"public reacquisition digest mismatch: Homebrew formula {source_name!r} declares sha256 "
                f"{actual} but the promoted cohort sdist declares {expected}; refusing",
            )
        verified[source_name] = actual
    return verified


def _resolve_brew(override: Path | None) -> Path:
    """Resolve the ``brew`` executable, refusing instructively when absent."""
    if override is not None:
        return override.expanduser().resolve(strict=True)
    found = shutil.which("brew")
    if found is None:
        raise AcquisitionError(
            "brew (Homebrew) not found on PATH; run this reacquisition on macOS or Linux with Homebrew installed",
        )
    return Path(found).resolve(strict=True)


def _run(brew: Path, arguments: list[str], *, cwd: Path, log: Path, timeout: float) -> CommandResult:
    """Run one brew subprocess, retaining its full output to a log file."""
    completed = run_command([str(brew), *arguments], cwd=cwd, timeout_seconds=timeout, errors="replace")
    log.write_text(
        f"argv={json.dumps([str(brew), *arguments])}\nexit_code={completed.returncode}\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}\n",
        encoding=_UTF_8,
        newline="\n",
    )
    return completed


def run_homebrew_acquisition(
    *,
    cohort_dir: Path,
    evidence_dir: Path,
    tap: str,
    brew_executable: Path | None,
    timeout_seconds: float,
    release_cohort_dir: Path | None = None,
    row_id: str | None = None,
    distribution_evidence_dir: Path | None = None,
) -> Path:
    """Tap, install, verify formula digests, and repeat installed oracles.

    Args:
        cohort_dir: The promoted Python cohort directory (expected sdist digests).
        evidence_dir: The directory retaining per-run evidence.
        tap: The public ``owner/name`` Homebrew tap hosting the formula.
        brew_executable: An explicit ``brew`` path, or ``None`` to resolve PATH.
        timeout_seconds: Per-command timeout for brew and the installed oracles.
        release_cohort_dir: The full release-cohort directory to bind a sanctioned
            flat :class:`~dev.packaging.evidence.DistributionEvidence` record to.
            When omitted, only the per-run acquisition document is written.
        row_id: The distribution row this run proves (required to emit the flat
            record, e.g. ``homebrew-macos-arm64``).
        distribution_evidence_dir: Where the flat record lands; defaults to
            ``var/distribution-install-readiness`` (the directory both the
            release-readiness and docs-claims gates scan).

    Returns:
        The path to the retained JSON evidence document.

    Raises:
        AcquisitionError: If brew is absent, the tap lacks the formula, or bytes
            drift from the promoted cohort.
    """
    if platform.system() not in {"Darwin", "Linux"}:
        raise AcquisitionError(f"Homebrew reacquisition requires macOS or Linux; got {platform.system()}")
    cohort = load_python_cohort(cohort_dir)
    brew = _resolve_brew(brew_executable)
    qualified = f"{tap}/{_FORMULA_NAME}"
    evidence_root = evidence_dir.resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    run_root = evidence_root / f"run-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}"
    run_root.mkdir()
    logs = run_root / "logs"
    logs.mkdir()

    tap_result = _run(brew, ["tap", tap], cwd=run_root, log=logs / "brew-tap.log", timeout=timeout_seconds)
    require_command_succeeded(
        returncode=tap_result.returncode,
        stderr=tap_result.stderr,
        mechanism="brew tap",
        endpoint=tap,
        version=cohort.version,
        next_step=f"publish the public Homebrew tap {tap} and rerun",
    )
    install = _run(
        brew,
        ["install", qualified],
        cwd=run_root,
        log=logs / "brew-install.log",
        timeout=timeout_seconds,
    )
    require_command_succeeded(
        returncode=install.returncode,
        stderr=install.stderr,
        mechanism="brew install",
        endpoint=qualified,
        version=cohort.version,
        next_step=f"publish cadrumo {cohort.version} to the public tap {tap} and rerun",
    )

    info = _run(
        brew,
        ["info", "--json=v2", qualified],
        cwd=run_root,
        log=logs / "brew-info.log",
        timeout=timeout_seconds,
    )
    if info.returncode != 0:
        raise AcquisitionError(f"brew info failed for {qualified}: {info.stderr.strip()[:200]}")
    document = json.loads(info.stdout)
    formulae = document.get("formulae") if isinstance(document, dict) else None
    if not isinstance(formulae, list) or not formulae:
        raise AcquisitionError(f"brew info returned no formula object for {qualified}")
    verified_digests = verify_homebrew_formula_digests(formulae[0], cohort)

    prefix = _run(
        brew,
        ["--prefix", qualified],
        cwd=run_root,
        log=logs / "brew-prefix.log",
        timeout=timeout_seconds,
    )
    if prefix.returncode != 0:
        raise AcquisitionError(f"brew --prefix failed for {qualified}: {prefix.stderr.strip()[:200]}")
    installed_prefix = Path(prefix.stdout.strip()).resolve(strict=True)
    aeat = (installed_prefix / "bin" / "aeat").resolve(strict=True)
    tax_evidence = run_installed_tax_oracle(
        cli=aeat,
        storage_root=run_root / "oracle-state",
        work_dir=run_root / "oracle-work",
        cohort_source_commit=cohort.source_commit,
        cohort_manifest_sha256=sha256_path(cohort.manifest),
        cohort_root_wheel_sha256=cohort.sha256["cadrumo"],
        timeout_seconds=timeout_seconds,
    )
    if tax_evidence.target_value != EXPECTED_ORACLE_TARGET_VALUE:
        raise AcquisitionError(
            f"installed CLI oracle target value drifted: expected {EXPECTED_ORACLE_TARGET_VALUE}, "
            f"got {tax_evidence.target_value!r}",
        )

    evidence = {
        "schema": "cadrumo.packaging.acquire-homebrew.v1",
        "status": "passed",
        "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "tap": tap,
        "formula": qualified,
        "platform": platform.platform(),
        "cohort": {"source_commit": cohort.source_commit, "version": cohort.version},
        "verified_formula_digests": verified_digests,
        "installed_prefix": str(installed_prefix),
        "installed_tax_oracle": tax_evidence.to_jsonable(),
        # The formula ships the CLI distribution only; cadrumo-mcp lives in the
        # sibling cadrumo-harness distribution, which Homebrew does not carry.
        "installed_mcp_oracle": None,
    }
    evidence_path = run_root / "acquire-homebrew-evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding=_UTF_8,
        newline="\n",
    )

    if release_cohort_dir is not None and row_id is not None:
        release_cohort = load_release_cohort(release_cohort_dir)
        emit_installed_oracle_evidence(
            directory=(distribution_evidence_dir or _DEFAULT_DISTRIBUTION_EVIDENCE_DIR),
            row_id=row_id,
            cohort=release_cohort,
            tax_evidence=tax_evidence,
            acquisition=AcquisitionIdentity(mechanism="brew", source=qualified),
            destination=DestinationIdentity(
                kind="homebrew-cellar",
                locator=str(installed_prefix),
                version=release_cohort.manifest.version,
            ),
        )

    return evidence_path


def _parser() -> argparse.ArgumentParser:
    """Return the argument parser for the Homebrew reacquisition check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-dir", required=True, type=Path, help="Promoted Python cohort directory.")
    parser.add_argument("--evidence-dir", required=True, type=Path, help="Directory retaining per-run evidence.")
    parser.add_argument("--tap", default=_DEFAULT_TAP, help="Public owner/name Homebrew tap.")
    parser.add_argument("--brew", type=Path, default=None, help="Explicit brew executable (defaults to PATH).")
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument(
        "--release-cohort-dir",
        type=Path,
        default=None,
        help="Full release-cohort directory to bind a sanctioned flat evidence record to.",
    )
    parser.add_argument(
        "--row-id",
        default=None,
        help="Distribution row this run proves (required to emit the flat record).",
    )
    parser.add_argument(
        "--distribution-evidence-dir",
        type=Path,
        default=None,
        help="Where the flat record lands (defaults to var/distribution-install-readiness).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the Homebrew reacquisition verification from the command line."""
    args = _parser().parse_args(argv)
    evidence = run_homebrew_acquisition(
        cohort_dir=args.cohort_dir,
        evidence_dir=args.evidence_dir,
        tap=args.tap,
        brew_executable=args.brew,
        timeout_seconds=args.timeout_seconds,
        release_cohort_dir=args.release_cohort_dir,
        row_id=args.row_id,
        distribution_evidence_dir=args.distribution_evidence_dir,
    )
    print(evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
