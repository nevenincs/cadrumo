"""Test-only construction of a cryptographically self-consistent cohort attestation."""

from __future__ import annotations

import io
import json
import tarfile
import zipfile
from pathlib import Path

from .._hashing import sha256_path
from ..python_cohort import _artifact_command_projection, _projection_digest


def add_test_source_archive(
    directory: Path, artifacts: dict[str, str], digests: dict[str, str]
) -> Path:
    """Add the mandatory retained Git-archive stand-in to a test cohort."""
    path = directory / f"cadrumo-source-{'a' * 40}.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("pyproject.toml", "[project]\nname='cadrumo'\n")
    artifacts["source-archive"] = path.name
    digests["source-archive"] = sha256_path(path)
    return path


def make_test_command_spec_attestation(
    directory: Path,
    artifacts: dict[str, str],
    *,
    source_commit: str,
) -> dict[str, object]:
    """Build the strict envelope around real planted fixture artifacts."""
    root_wheel = directory / artifacts["cadrumo"]
    root_sdist = directory / artifacts["cadrumo-sdist"]
    try:
        member_digest = _projection_digest(
            _artifact_command_projection(
                root_wheel, root_sdist, directory / artifacts["source-archive"]
            )
        )
    except (OSError, tarfile.TarError, zipfile.BadZipFile):
        member_digest = "0" * 64
    value: dict[str, object] = {
        "schema": "cadrumo.command-spec-cohort.v1",
        "node_count": 1,
        "source_commit": source_commit,
        "forbidden_artifacts_absent": True,
        "root_wheel_sha256": sha256_path(root_wheel),
        "root_sdist_sha256": sha256_path(root_sdist),
        "source_archive_sha256": sha256_path(directory / artifacts["source-archive"]),
        "artifact_members_sha256": member_digest,
        "origins_sha256": "1" * 64,
        "identities_sha256": "b" * 64,
        "locales_sha256": "c" * 64,
        "policies_sha256": "d" * 64,
        "schemas_sha256": "e" * 64,
        "import_budgets_sha256": "f" * 64,
    }
    value["envelope_sha256"] = _projection_digest(value)
    return value


def make_minimal_test_python_cohort(
    directory: Path,
    *,
    version: str,
    source_commit: str = "a" * 40,
) -> dict[str, str]:
    """Write six minimal valid archives plus their strict cohort manifest."""
    directory.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}
    digests: dict[str, str] = {}
    for distribution in ("cadrumo", "cadrumo-data-manuals", "cadrumo-data-official"):
        normalized = distribution.replace("-", "_")
        requires = (
            (f"cadrumo-data-manuals=={version}", f"cadrumo-data-official=={version}")
            if distribution == "cadrumo"
            else ()
        )
        metadata = "\n".join(
            (f"Name: {distribution}", f"Version: {version}", *(f"Requires-Dist: {item}" for item in requires), "")
        ).encode()
        wheel_name = f"{normalized}-{version}-py3-none-any.whl"
        with zipfile.ZipFile(directory / wheel_name, "w") as archive:
            archive.writestr(f"{normalized}-{version}.dist-info/METADATA", metadata)
        wheel_key = distribution
        artifacts[wheel_key] = wheel_name
        digests[wheel_key] = sha256_path(directory / wheel_name)

        sdist_name = f"{normalized}-{version}.tar.gz"
        with tarfile.open(directory / sdist_name, "w:gz") as archive:
            info = tarfile.TarInfo(f"{normalized}-{version}/PKG-INFO")
            info.size = len(metadata)
            archive.addfile(info, io.BytesIO(metadata))
        sdist_key = f"{distribution}-sdist"
        artifacts[sdist_key] = sdist_name
        digests[sdist_key] = sha256_path(directory / sdist_name)
    add_test_source_archive(directory, artifacts, digests)
    manifest = {
        "artifacts": artifacts,
        "sha256": digests,
        "source_commit": source_commit,
        "version": version,
        "command_spec_attestation": make_test_command_spec_attestation(
            directory, artifacts, source_commit=source_commit
        ),
    }
    (directory / "python-cohort.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )
    return digests
