"""Install one immutable release cohort, run the installed oracles, emit its row.

This is the per-OS proof that THE immutable release cohort - the exact bytes the
publish authority promotes - installs and performs grounded tax work on this
operating system, and it mints the sanctioned flat ``python-<os>`` distribution
row bound to that one cohort. Every OS leg of the packaging-smoke workflow runs
this against the same downloaded ``cadrumo-release-cohort`` artifact, so all the
Python rows bind one cohort id (no per-OS rebuild, which would diverge the id).

It installs the cohort's three digest-pinned Python wheels plus the sibling
``cadrumo-harness`` wheel into a fresh isolated virtualenv, resolves the
installed ``aeat`` and ``cadrumo-mcp`` executables, runs the canonical
installed CLI and MCP behaviour oracles against them, and emits the record
through :func:`~dev.packaging.distribution_evidence_emit.emit_installed_oracle_evidence`.

The harness is NOT a member of the retained three-wheel Python cohort — it is
versioned independently (see
:func:`dev.packaging._acquire_common.harness_version`), mirroring the ruling
already encoded in the MCPB bundle builder (``packaging/mcpb/build.py``) — so
the release cohort carries no embedded harness wheel or digest pin for it.
This builds the harness wheel fresh from the EXACT immutable source commit the
cohort itself was built from (never the ambient checkout), so the MCP launcher
proved here corresponds to the same commit as the cohort under proof.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path
from typing import Final

from dev._paths import REPO_ROOT, UTF_8

from ._acquire_common import (
    HARNESS_DISTRIBUTION,
    PYTHON_COHORT_WHEEL_NAMES,
    AcquisitionError,
    run_installed_behavior_oracles,
    venv_executable,
)
from ._smoke_common import build_harness_wheel, extract_source_commit
from .cohort_manifest import load_release_cohort
from .distribution_evidence_emit import emit_installed_oracle_evidence
from .evidence import AcquisitionIdentity, DestinationIdentity
from .python_cohort import load_python_cohort

_UTF_8: Final[str] = UTF_8
_DEFAULT_DISTRIBUTION_EVIDENCE_DIR: Final[Path] = Path("var/distribution-install-readiness")


def _resolve_uv(override: Path | None) -> Path:
    """Resolve the ``uv`` executable, refusing instructively when absent."""
    if override is not None:
        return override.expanduser().resolve(strict=True)
    found = shutil.which("uv")
    if found is None:
        raise AcquisitionError("uv not found on PATH; pass --uv to install the cohort")
    return Path(found).resolve(strict=True)


def run_oracle_emit_cohort(
    *,
    release_cohort_dir: Path,
    row_id: str,
    work_dir: Path,
    python: str,
    uv_executable: Path | None,
    timeout_seconds: float,
    distribution_evidence_dir: Path | None = None,
) -> Path:
    """Install the cohort, run the installed oracles, and emit the row record.

    Args:
        release_cohort_dir: The full release-cohort directory (its ``python``
            subdirectory holds the wheels; the manifest binds the evidence).
        row_id: The distribution row this OS proves (e.g. ``python-linux-x86-64``).
        work_dir: A fresh working directory for the venv and oracle state.
        python: The interpreter version for the fresh venv.
        uv_executable: An explicit ``uv`` path, or ``None`` to resolve from PATH.
        timeout_seconds: Per-command timeout for the installed oracles.
        distribution_evidence_dir: Where the flat record lands; defaults to
            ``var/distribution-install-readiness``.

    Returns:
        The path to the emitted flat distribution-evidence record.

    Raises:
        AcquisitionError: If uv is absent or the install/venv fails.
    """
    cohort = load_release_cohort(release_cohort_dir)
    python_cohort = load_python_cohort(release_cohort_dir / "python")
    uv = _resolve_uv(uv_executable)
    work = work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    venv = work / "venv"

    create = subprocess.run(  # noqa: S603 - resolved uv executable and declarative argv
        [str(uv), "venv", str(venv), "--python", python, "--seed"],
        cwd=work,
        capture_output=True,
        text=True,
        encoding=_UTF_8,
        errors="replace",
        check=False,
    )
    if create.returncode != 0:
        raise AcquisitionError(f"could not create the cohort virtualenv: {create.stderr.strip()[:200]}")
    venv_python = venv_executable(venv, "python")

    wheels = {name: python_cohort.sha256[name] for name in PYTHON_COHORT_WHEEL_NAMES}
    root_wheel = python_cohort.root_wheel
    manuals_wheel, official_wheel = python_cohort.companion_wheels
    # The harness is not a cohort member and has no embedded wheel here; build
    # it fresh from the exact commit the cohort was built from.
    harness_build_root = extract_source_commit(REPO_ROOT, work, cohort.manifest.source.commit)
    harness_wheel = build_harness_wheel(work, str(uv), build_root=harness_build_root)
    install = subprocess.run(  # noqa: S603 - resolved uv executable and cohort file paths
        [
            str(uv),
            "pip",
            "install",
            "--python",
            str(venv_python),
            f"cadrumo @ {root_wheel.resolve().as_uri()}",
            f"{HARNESS_DISTRIBUTION} @ {harness_wheel.resolve().as_uri()}",
            f"cadrumo-data-manuals @ {manuals_wheel.resolve().as_uri()}",
            f"cadrumo-data-official @ {official_wheel.resolve().as_uri()}",
        ],
        cwd=work,
        capture_output=True,
        text=True,
        encoding=_UTF_8,
        errors="replace",
        check=False,
    )
    if install.returncode != 0:
        raise AcquisitionError(
            f"could not install the immutable cohort ({sorted(wheels)}) plus the sibling "
            f"{HARNESS_DISTRIBUTION} wheel: {install.stderr.strip()[:200]}"
        )

    aeat = venv_executable(venv, "aeat")
    mcp_server = venv_executable(venv, "cadrumo-mcp")
    tax_evidence, mcp_evidence = run_installed_behavior_oracles(
        cli=aeat,
        mcp_server=mcp_server,
        storage_root=work / "oracle-state",
        work_dir=work / "oracle-work",
        cohort=python_cohort,
        timeout_seconds=timeout_seconds,
    )

    return emit_installed_oracle_evidence(
        directory=(distribution_evidence_dir or _DEFAULT_DISTRIBUTION_EVIDENCE_DIR),
        row_id=row_id,
        cohort=cohort,
        tax_evidence=tax_evidence,
        mcp_evidence=mcp_evidence,
        acquisition=AcquisitionIdentity(mechanism="immutable-release-cohort", source=str(release_cohort_dir)),
        destination=DestinationIdentity(
            kind="isolated-python-venv", locator=str(venv), version=cohort.manifest.version
        ),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-cohort-dir", required=True, type=Path, help="Full release-cohort directory.")
    parser.add_argument("--row-id", required=True, help="Distribution row this OS proves (e.g. python-linux-x86-64).")
    parser.add_argument("--work-dir", required=True, type=Path, help="Fresh working directory for the venv/oracles.")
    parser.add_argument("--python", default="3.13", help="Interpreter version for the fresh venv.")
    parser.add_argument("--uv", type=Path, default=None, help="Explicit uv executable (defaults to PATH).")
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--distribution-evidence-dir", type=Path, default=None, help="Where the flat record lands.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Install the immutable cohort, run the installed oracles, and emit its row."""
    args = _parser().parse_args(argv)
    path = run_oracle_emit_cohort(
        release_cohort_dir=args.release_cohort_dir,
        row_id=args.row_id,
        work_dir=args.work_dir,
        python=args.python,
        uv_executable=args.uv,
        timeout_seconds=args.timeout_seconds,
        distribution_evidence_dir=args.distribution_evidence_dir,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
