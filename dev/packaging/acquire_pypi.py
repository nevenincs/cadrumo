"""Reacquire the Cadrumo Python cohort from PyPI and repeat installed tax work.

This post-publication check installs the complete Python cohort (``cadrumo``,
``cadrumo-harness``, and both mandatory data distributions) FROM a public
package index (no local wheels), proves the
cohort's installed wheel bytes match the promoted cohort digest byte-for-byte,
and then repeats the grounded installed CLI and MCP tax-work oracles from that
index-only environment. The harness remains independently versioned, but its
exact wheel bytes and declared version are pinned by the cohort manifest.
It refuses instructively when the index does not yet serve the promoted
version (implements post-release-distribution plan row P03.S14).
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from dev._paths import UTF_8

from ._acquire_common import (
    HARNESS_DISTRIBUTION,
    PYTHON_COHORT_WHEEL_NAMES,
    AcquisitionError,
    require_command_succeeded,
    run_installed_behavior_oracles,
    venv_executable,
    verify_python_cohort_download,
)
from ._command import CommandResult, run_command
from .cohort_manifest import load_release_cohort
from .distribution_evidence_emit import emit_installed_oracle_evidence
from .evidence import AcquisitionIdentity, DestinationIdentity
from .python_cohort import PythonCohort, load_python_cohort

_UTF_8: Final[str] = UTF_8
_DEFAULT_INDEX_URL: Final[str] = "https://pypi.org/simple"
_DEFAULT_DISTRIBUTION_EVIDENCE_DIR: Final[Path] = Path("var/distribution-install-readiness")


def _resolve_executable(name: str, override: Path | None) -> Path:
    """Resolve a required build executable from an override or PATH."""
    if override is not None:
        return override.expanduser().resolve(strict=True)
    found = shutil.which(name)
    if found is None:
        raise AcquisitionError(f"required executable not found on PATH: {name}")
    return Path(found).resolve(strict=True)


def _run(argv: list[str], *, cwd: Path, log: Path) -> CommandResult:
    """Run one acquisition subprocess, retaining its full output to a log file."""
    completed = run_command(argv, cwd=cwd, errors="replace")
    log.write_text(
        f"argv={json.dumps(argv)}\ncwd={cwd}\nexit_code={completed.returncode}\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}\n",
        encoding=_UTF_8,
        newline="\n",
    )
    return completed


def _download_cohort_wheels(
    venv_python: Path,
    *,
    cohort: PythonCohort,
    index_url: str,
    download_dir: Path,
    run_root: Path,
    logs: Path,
) -> None:
    """Download every cohort distribution wheel from the public index.

    Refuses instructively (never a bare traceback) when the index does not yet
    serve the promoted version for any distribution.
    """
    download_dir.mkdir(parents=True, exist_ok=True)
    for distribution in PYTHON_COHORT_WHEEL_NAMES:
        version = cohort.harness_version if distribution == HARNESS_DISTRIBUTION else cohort.version
        completed = _run(
            [
                str(venv_python),
                "-m",
                "pip",
                "download",
                "--no-deps",
                "--only-binary=:all:",
                "--index-url",
                index_url,
                "--dest",
                str(download_dir),
                f"{distribution}=={version}",
            ],
            cwd=run_root,
            log=logs / f"pip-download-{distribution}.log",
        )
        require_command_succeeded(
            returncode=completed.returncode,
            stderr=completed.stderr,
            mechanism="pip download",
            endpoint=index_url,
            version=version,
            next_step=f"publish {distribution}=={version} to {index_url} and rerun",
        )


def run_pypi_acquisition(
    *,
    cohort_dir: Path,
    evidence_dir: Path,
    index_url: str,
    python: str,
    uv_executable: Path | None,
    timeout_seconds: float,
    release_cohort_dir: Path | None = None,
    row_id: str | None = None,
    distribution_evidence_dir: Path | None = None,
) -> Path:
    """Install from PyPI, verify cohort digests, and repeat installed oracles.

    Args:
        cohort_dir: The promoted Python cohort directory (expected digests).
        evidence_dir: The directory retaining per-run evidence.
        index_url: The public package index to install and download from.
        python: The interpreter version/identifier for the fresh venv.
        uv_executable: An explicit ``uv`` path, or ``None`` to resolve from PATH.
        timeout_seconds: Per-command timeout for the installed oracles.
        release_cohort_dir: The full release-cohort directory to bind a sanctioned
            flat :class:`~dev.packaging.evidence.DistributionEvidence` record to.
            When omitted, only the per-run acquisition document is written.
        row_id: The distribution row this run proves (required to emit the flat
            record, e.g. ``python-linux-x86-64``).
        distribution_evidence_dir: Where the flat record lands; defaults to
            ``var/distribution-install-readiness`` (the directory both the
            release-readiness and docs-claims gates scan).

    Returns:
        The path to the retained JSON evidence document.

    Raises:
        AcquisitionError: If the index lacks the version or bytes drift.
    """
    cohort = load_python_cohort(cohort_dir)
    uv = _resolve_executable("uv", uv_executable)
    evidence_root = evidence_dir.resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    run_root = evidence_root / f"run-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}"
    run_root.mkdir()
    logs = run_root / "logs"
    logs.mkdir()
    venv = run_root / "venv"
    download_dir = run_root / "downloads"

    create = _run(
        [str(uv), "venv", str(venv), "--python", python, "--seed"],
        cwd=run_root,
        log=logs / "uv-venv.log",
    )
    if create.returncode != 0:
        raise AcquisitionError(f"could not create the acquisition virtualenv: {create.stderr.strip()[:200]}")
    venv_python = venv_executable(venv, "python")

    _download_cohort_wheels(
        venv_python,
        cohort=cohort,
        index_url=index_url,
        download_dir=download_dir,
        run_root=run_root,
        logs=logs,
    )
    verified = verify_python_cohort_download(
        download_dir,
        cohort,
        mechanism="pip download",
        endpoint=index_url,
    )

    harness_pin = cohort.harness_version
    install = _run(
        [
            str(uv),
            "pip",
            "install",
            "--python",
            str(venv_python),
            "--index-url",
            index_url,
            f"cadrumo=={cohort.version}",
            f"{HARNESS_DISTRIBUTION}=={harness_pin}",
            f"cadrumo-data-manuals=={cohort.version}",
            f"cadrumo-data-official=={cohort.version}",
        ],
        cwd=run_root,
        log=logs / "uv-pip-install.log",
    )
    require_command_succeeded(
        returncode=install.returncode,
        stderr=install.stderr,
        mechanism="uv pip install",
        endpoint=index_url,
        version=cohort.version,
        next_step=(
            f"publish cadrumo=={cohort.version} and {HARNESS_DISTRIBUTION}=={harness_pin} to {index_url} and rerun"
        ),
    )

    aeat = venv_executable(venv, "aeat")
    mcp = venv_executable(venv, "cadrumo-mcp")
    tax_evidence, mcp_evidence = run_installed_behavior_oracles(
        cli=aeat,
        mcp_server=mcp,
        storage_root=run_root / "oracle-state",
        work_dir=run_root / "oracle-work",
        cohort=cohort,
        timeout_seconds=timeout_seconds,
    )

    evidence = {
        "schema": "cadrumo.packaging.acquire-pypi.v1",
        "status": "passed",
        "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "index_url": index_url,
        "cohort": {
            "source_commit": cohort.source_commit,
            "version": cohort.version,
            "sha256": {name: cohort.sha256[name] for name in PYTHON_COHORT_WHEEL_NAMES},
        },
        "verified_wheels": {name: str(path) for name, path in verified.items()},
        "installed_tax_oracle": tax_evidence.to_jsonable(),
        "installed_mcp_oracle": mcp_evidence.to_jsonable(),
    }
    evidence_path = run_root / "acquire-pypi-evidence.json"
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
            mcp_evidence=mcp_evidence,
            acquisition=AcquisitionIdentity(mechanism="pip", source=index_url),
            destination=DestinationIdentity(
                kind="pypi-index-install",
                locator=str(venv),
                version=release_cohort.manifest.version,
            ),
        )

    return evidence_path


def _parser() -> argparse.ArgumentParser:
    """Return the argument parser for the PyPI reacquisition check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-dir", required=True, type=Path, help="Promoted Python cohort directory.")
    parser.add_argument("--evidence-dir", required=True, type=Path, help="Directory retaining per-run evidence.")
    parser.add_argument("--index-url", default=_DEFAULT_INDEX_URL, help="Public package index to acquire from.")
    parser.add_argument("--python", default="3.13", help="Interpreter version for the fresh venv.")
    parser.add_argument("--uv", type=Path, default=None, help="Explicit uv executable (defaults to PATH).")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
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
    """Run the PyPI reacquisition verification from the command line."""
    args = _parser().parse_args(argv)
    evidence = run_pypi_acquisition(
        cohort_dir=args.cohort_dir,
        evidence_dir=args.evidence_dir,
        index_url=args.index_url,
        python=args.python,
        uv_executable=args.uv,
        timeout_seconds=args.timeout_seconds,
        release_cohort_dir=args.release_cohort_dir,
        row_id=args.row_id,
        distribution_evidence_dir=args.distribution_evidence_dir,
    )
    print(evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
