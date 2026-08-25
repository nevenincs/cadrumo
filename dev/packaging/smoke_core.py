"""Build and verify the core Cadrumo wheel in a fresh installed environment.

This module is the ``core`` lane only. The artifact and installed-product
checks it shares with every other lane live in :mod:`dev.packaging._smoke_common`;
what remains here is the three-wheel cohort identity rule and this lane's own
sequencing.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from email.parser import Parser
from pathlib import Path
from typing import Final

from packaging.requirements import Requirement

from .._paths import UTF_8
from ._distribution_names import normalise_distribution_name
from ._hashing import sha256_path
from ._smoke_common import (
    assert_attachment_and_llm_surfaces,
    assert_cli_smoke,
    assert_installed_data,
    assert_wheel_contains_tracked_data,
    assert_wheel_metadata_matches_pyproject,
    expected_wheel_data_paths,
    find_repo_root,
    install_wheel,
    record_proof,
    relative_manifest_path,
    require_executable,
    resolve_work_dir,
    validate_frozen_exports,
    venv_cadrumo_path,
    venv_python_path,
    wheel_metadata,
    write_smoke_manifest,
)
from .installed_tax_oracle import run_installed_tax_oracle
from .python_cohort import (
    COHORT_STAMPED_WHEEL_DATA_PATHS,
    assert_installed_cohort,
    load_python_cohort,
)

_UTF_8: Final[str] = UTF_8


def _wheel_identity(wheel: Path) -> tuple[str, str]:
    """Return the normalized distribution name and version from one wheel."""
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise SystemExit(
                f"expected one wheel METADATA member in {wheel}; got {metadata_names!r}",
            )
        metadata = Parser().parsestr(archive.read(metadata_names[0]).decode(_UTF_8))
    name = metadata.get("Name")
    version = metadata.get("Version")
    if not name or not version:
        raise SystemExit(f"wheel metadata is missing Name or Version: {wheel}")
    return normalise_distribution_name(name), version


def _assert_complete_wheel_cohort(
    wheel: Path,
    *,
    data_wheel_manuals: Path,
    data_wheel_official: Path,
) -> str:
    """Require one command wheel and both exact-version mandatory companions."""
    named_companions = {
        "cadrumo-data-manuals": data_wheel_manuals,
        "cadrumo-data-official": data_wheel_official,
    }
    identities = {expected_name: _wheel_identity(artifact) for expected_name, artifact in named_companions.items()}
    mislabeled = {
        expected_name: observed_name
        for expected_name, (observed_name, _version) in identities.items()
        if observed_name != expected_name
    }
    if mislabeled:
        raise SystemExit(
            f"supplied companion wheel labels do not match their metadata: {mislabeled!r}",
        )
    root_name, root_version = _wheel_identity(wheel)
    if root_name != "cadrumo":
        raise SystemExit(f"command wheel identity is {root_name!r}, expected 'cadrumo'")
    mismatched = {name: version for name, (_observed_name, version) in identities.items() if version != root_version}
    if mismatched:
        raise SystemExit(
            f"companion versions do not match cadrumo {root_version!r}: {mismatched!r}",
        )
    requirements, _extras = wheel_metadata(wheel)
    exact_pins = {
        normalise_distribution_name(requirement.name): str(requirement.specifier)
        for row in requirements
        if (requirement := Requirement(row)).marker is None
        and normalise_distribution_name(requirement.name) in named_companions
    }
    expected_pins = {name: f"=={root_version}" for name in named_companions}
    if exact_pins != expected_pins:
        raise SystemExit(
            f"command wheel companion pins must be exact: expected {expected_pins!r}, got {exact_pins!r}",
        )
    record_proof("complete exact-version three-wheel cohort")
    return root_version


def main(argv: list[str] | None = None) -> int:
    """Run the core installed-wheel packaging smoke gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default="3.13", help="Python interpreter/version for the fresh venv.")
    parser.add_argument("--work-dir", help="Empty directory for wheel, venv, and profile smoke artifacts.")
    parser.add_argument(
        "--cohort-dir",
        required=True,
        type=Path,
        help="Directory containing the prebuilt cadrumo and mandatory companion wheels.",
    )
    parser.add_argument(
        "--skip-export-checks",
        action="store_true",
        help="Skip frozen uv export surface checks and run only the installed-wheel smoke.",
    )
    args = parser.parse_args(argv)

    repo_root = find_repo_root()
    uv = require_executable("uv")
    work_dir = resolve_work_dir(repo_root, args.work_dir)
    print(f"packaging smoke work dir: {work_dir}", flush=True)

    if not args.skip_export_checks:
        print("validating frozen dependency exports", flush=True)
        validate_frozen_exports(repo_root, uv)

    cohort = load_python_cohort(args.cohort_dir)
    wheel = cohort.root_wheel
    data_wheel_manuals = cohort.manuals_wheel
    data_wheel_official = cohort.official_wheel
    companion_wheels = (data_wheel_manuals, data_wheel_official)
    print("using supplied complete wheel cohort", flush=True)
    assert_wheel_contains_tracked_data(
        repo_root,
        wheel,
        expected_wheel_data_paths(repo_root) | COHORT_STAMPED_WHEEL_DATA_PATHS,
    )
    assert_wheel_metadata_matches_pyproject(repo_root, wheel)
    cohort_version = _assert_complete_wheel_cohort(
        wheel,
        data_wheel_manuals=data_wheel_manuals,
        data_wheel_official=data_wheel_official,
    )

    print("installing complete wheel cohort into fresh venv", flush=True)
    venv = install_wheel(
        repo_root,
        work_dir,
        wheel,
        uv,
        args.python,
        companion_wheels=companion_wheels,
    )
    assert_installed_cohort(
        venv_python_path(venv),
        cohort,
        root_artifact=wheel,
        cwd=work_dir,
    )
    assert_installed_data(work_dir, venv)
    assert_attachment_and_llm_surfaces(work_dir, venv)
    assert_cli_smoke(work_dir, venv)
    print("running installed grounded tax-work oracle", flush=True)
    tax_evidence = run_installed_tax_oracle(
        venv_cadrumo_path(venv),
        storage_root=work_dir / "tax-oracle-state",
        work_dir=work_dir / "outside-checkout",
        cohort_source_commit=cohort.source_commit,
        cohort_manifest_sha256=sha256_path(cohort.manifest),
        cohort_root_wheel_sha256=cohort.sha256["cadrumo"],
    )
    record_proof("installed grounded Modelo 200 tax-work oracle")
    tax_evidence_path = work_dir / "installed-tax-oracle.json"
    tax_evidence_path.write_text(
        json.dumps(tax_evidence.to_jsonable(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding=_UTF_8,
        newline="\n",
    )

    # The contract this form promises. It is checked against what actually
    # recorded itself: a declared claim with no recorded assertion refuses the
    # run, and the manifest is written from the recorded set, never from this
    # declaration.
    declared = [
        "wheel tracked shipped-data payload",
        "wheel metadata dependency surface",
        "complete exact-version three-wheel cohort",
        "fresh uv virtualenv install",
        "installed bundled data resources",
        "attachment storage round-trip",
        "core LLM missing-extra boundary",
        "installed CLI config/profile smoke",
        "installed grounded Modelo 200 tax-work oracle",
    ]
    if not args.skip_export_checks:
        declared.insert(0, "frozen dependency exports")
    manifest = write_smoke_manifest(
        work_dir,
        lane="core-wheel",
        artifacts={
            "wheel": relative_manifest_path(work_dir, wheel),
            "data_wheel_manuals": relative_manifest_path(work_dir, companion_wheels[0]),
            "data_wheel_official": relative_manifest_path(work_dir, companion_wheels[1]),
            "installed_tax_oracle": relative_manifest_path(work_dir, tax_evidence_path),
            "venv": relative_manifest_path(work_dir, venv),
        },
        declared=tuple(declared),
        details={
            "cohort_version": cohort_version,
            "python": args.python,
            "target_casilla": tax_evidence.target_casilla,
            "target_value": tax_evidence.target_value,
        },
    )

    print(f"core packaging smoke passed: {wheel}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
