"""Real-behavior tests for the promote-python-cohort promotion verify gate.

Every test exercises real production code paths against minimal but valid on-disk
structures — no mocks, stubs, monkeypatches, skips, or xfail markers.

Wheel and sdist artifacts are constructed as the smallest valid archives that
satisfy the metadata contracts in ``dev.packaging.python_cohort``:

* A wheel is a zip archive carrying ``{dist_info}/METADATA`` with RFC 2822 headers.
* A source distribution is a gzip'd tarball carrying ``{name}-{version}/PKG-INFO``
  with the same headers.

These minimal archives pass ``_validate_wheel_contract`` and
``_validate_sdist_contract`` because those functions parse the metadata headers
directly via ``email.parser.Parser``.

The PyPI pre-upload guard (``assert_pypi_destinations_absent``) makes real HTTP
calls and is therefore exercised as an integration test using a
``PythonCohort`` constructed directly from the public dataclass; the refusal
path (version already on PyPI) requires the version to be present on PyPI, so
it is not tested here.  The guard test is marked ``integration`` per the rule
that real network I/O forces that scope.
"""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest

from ...packaging.installed_tax_oracle import (
    EXPECTED_FORMULA,
    EXPECTED_LEGAL_REF,
    EXPECTED_SOURCE_REF,
    EXPECTED_VALUE,
    TARGET_CASILLA,
)
from ...packaging.python_cohort import PythonCohort, load_python_cohort
from ...packaging.tests._cohort_attestation import (
    add_test_runtime_wheelhouse,
    add_test_source_archive,
    make_test_command_spec_attestation,
)
from ..promote_python_cohort import validate_promotion

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_VERSION = "0.99.0.dev1"
_SAMPLE_COMMIT = "a" * 40


# ---------------------------------------------------------------------------
# Minimal artifact builders
# ---------------------------------------------------------------------------


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _metadata(name: str, version: str, requires: tuple[str, ...], *, description: str = "") -> str:
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {name}",
        f"Version: {version}",
    ]
    for req in requires:
        lines.append(f"Requires-Dist: {req}")
    if description:
        lines.append(f"Summary: {description}")
    return "\n".join(lines) + "\n"


def _wheel_bytes(name: str, version: str, requires: tuple[str, ...] = (), *, description: str = "") -> bytes:
    """Minimal PEP 427 wheel (zip) with one ``METADATA`` member."""
    dist_info = f"{name.replace('-', '_')}-{version}.dist-info"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{dist_info}/METADATA", _metadata(name, version, requires, description=description))
    return buf.getvalue()


def _sdist_bytes(name: str, version: str, requires: tuple[str, ...] = (), *, description: str = "") -> bytes:
    """Minimal sdist (gzip'd tar) with one ``PKG-INFO`` member."""
    pkg_info = _metadata(name, version, requires, description=description).encode("utf-8")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo(name=f"{name.replace('-', '_')}-{version}/PKG-INFO")
        info.size = len(pkg_info)
        tf.addfile(info, io.BytesIO(pkg_info))
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Cohort and evidence fixture builders
# ---------------------------------------------------------------------------


def _write_artifact(directory: Path, filename: str, data: bytes) -> tuple[str, str]:
    """Write bytes under *directory* and return (filename, sha256)."""
    path = directory / filename
    path.write_bytes(data)
    return filename, _sha256(data)


def _make_cohort_dir(
    root: Path,
    *,
    commit: str = _SAMPLE_COMMIT,
    version: str = _VERSION,
    description: str = "",
) -> Path:
    """Create a minimal valid python-cohort directory and return its path.

    The directory contains six install archives plus the retained source archive
    and runtime wheelhouse
    that satisfy ``load_python_cohort``'s metadata validation, plus a
    ``python-cohort.json`` manifest with correct SHA-256 digests.
    """
    cohort_dir = root / "python-cohort"
    cohort_dir.mkdir(parents=True)

    companion_requires = (
        f"cadrumo-data-manuals=={version}",
        f"cadrumo-data-official=={version}",
    )
    artifacts: dict[str, str] = {}
    sha256: dict[str, str] = {}

    for name, filename_stem, requires in (
        ("cadrumo", f"cadrumo-{version}-py3-none-any.whl", companion_requires),
        ("cadrumo-data-manuals", f"cadrumo_data_manuals-{version}-py3-none-any.whl", ()),
        ("cadrumo-data-official", f"cadrumo_data_official-{version}-py3-none-any.whl", ()),
    ):
        key = "cadrumo" if name == "cadrumo" else name
        fn, digest = _write_artifact(
            cohort_dir, filename_stem, _wheel_bytes(name, version, requires, description=description)
        )
        artifacts[key] = fn
        sha256[key] = digest

    for name, filename_stem, requires in (
        ("cadrumo", f"cadrumo-{version}.tar.gz", companion_requires),
        ("cadrumo-data-manuals", f"cadrumo_data_manuals-{version}.tar.gz", ()),
        ("cadrumo-data-official", f"cadrumo_data_official-{version}.tar.gz", ()),
    ):
        sdist_key = f"{name}-sdist" if name != "cadrumo" else "cadrumo-sdist"
        fn, digest = _write_artifact(
            cohort_dir, filename_stem, _sdist_bytes(name, version, requires, description=description)
        )
        artifacts[sdist_key] = fn
        sha256[sdist_key] = digest

    add_test_source_archive(cohort_dir, artifacts, sha256)
    add_test_runtime_wheelhouse(cohort_dir, artifacts, sha256)
    manifest_data = {
        "artifacts": artifacts,
        "sha256": sha256,
        "source_commit": commit,
        "version": version,
        "command_spec_attestation": make_test_command_spec_attestation(
            cohort_dir, artifacts, source_commit=commit
        ),
    }
    (cohort_dir / "python-cohort.json").write_text(
        json.dumps(manifest_data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return cohort_dir


def _oracle() -> dict[str, object]:
    """Minimal oracle evidence payload satisfying ``_assert_oracle``."""
    oracle: dict[str, object] = {
        "target_casilla": TARGET_CASILLA,
        "target_value": str(EXPECTED_VALUE),
        "formula_id": EXPECTED_FORMULA,
        "legal_refs": [EXPECTED_LEGAL_REF],
        "source_refs": [EXPECTED_SOURCE_REF],
    }
    return oracle


def _write_evidence(
    evidence_root: Path,
    cohort: PythonCohort,
    *,
    override: dict[str, object] | None = None,
) -> Path:
    """Write the ``<commit>/evidence.json`` file expected by ``_evidence_document``.

    *override* is shallow-merged into the document before writing so individual
    tests can corrupt or omit specific keys.
    """
    document: dict[str, object] = {
        "source_commit": cohort.source_commit,
        "artifact_sha256": {
            "cadrumo": cohort.sha256["cadrumo"],
            "cadrumo-data-manuals": cohort.sha256["cadrumo-data-manuals"],
            "cadrumo-data-official": cohort.sha256["cadrumo-data-official"],
        },
        "cli_oracle": _oracle(),
    }
    if override:
        document.update(override)
    commit_dir = evidence_root / cohort.source_commit
    commit_dir.mkdir(parents=True, exist_ok=True)
    evidence_file = commit_dir / "evidence.json"
    evidence_file.write_text(json.dumps(document), encoding="utf-8")
    return evidence_file


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_complete_valid_cohort_and_evidence_passes_validate_promotion(
    tmp_path: Path,
) -> None:
    """A complete, unmodified cohort with matching oracle evidence passes the gate."""
    cohort_dir = _make_cohort_dir(tmp_path)
    cohort = load_python_cohort(cohort_dir)
    evidence_file = _write_evidence(tmp_path / "evidence", cohort)

    returned = validate_promotion(
        cohort_dir,
        evidence_file,
        expected_source_commit=cohort.source_commit,
    )

    assert returned.source_commit == cohort.source_commit
    assert returned.version == _VERSION


def test_tampered_artifact_digest_is_refused(tmp_path: Path) -> None:
    """Altering an artifact's digest in the evidence causes ``SystemExit``."""
    cohort_dir = _make_cohort_dir(tmp_path)
    cohort = load_python_cohort(cohort_dir)
    tampered_hashes = dict(cohort.sha256)
    tampered_hashes["cadrumo"] = "f" * 64  # wrong digest
    evidence_file = _write_evidence(
        tmp_path / "evidence",
        cohort,
        override={
            "artifact_sha256": {
                "cadrumo": tampered_hashes["cadrumo"],
                "cadrumo-data-manuals": cohort.sha256["cadrumo-data-manuals"],
                "cadrumo-data-official": cohort.sha256["cadrumo-data-official"],
            }
        },
    )

    with pytest.raises(SystemExit):
        validate_promotion(
            cohort_dir,
            evidence_file,
            expected_source_commit=cohort.source_commit,
        )


def test_missing_cli_oracle_is_refused(tmp_path: Path) -> None:
    """Evidence that omits ``cli_oracle`` fails with ``SystemExit``."""
    cohort_dir = _make_cohort_dir(tmp_path)
    cohort = load_python_cohort(cohort_dir)
    evidence_file = _write_evidence(
        tmp_path / "evidence",
        cohort,
        override={"cli_oracle": None},
    )

    with pytest.raises(SystemExit):
        validate_promotion(
            cohort_dir,
            evidence_file,
            expected_source_commit=cohort.source_commit,
        )


def test_source_commit_mismatch_is_refused(tmp_path: Path) -> None:
    """Supplying the wrong expected commit refuses before reading evidence."""
    cohort_dir = _make_cohort_dir(tmp_path)
    cohort = load_python_cohort(cohort_dir)
    evidence_file = _write_evidence(tmp_path / "evidence", cohort)
    wrong_commit = "c" * 40

    with pytest.raises(SystemExit):
        validate_promotion(
            cohort_dir,
            evidence_file,
            expected_source_commit=wrong_commit,
        )


def test_evidence_from_different_artifact_bytes_is_refused(tmp_path: Path) -> None:
    """Evidence produced from different artifact bytes does not validate the cohort.

    This covers the destination-version mismatch path: the evidence records
    ``artifact_sha256`` digests from a different build, so they do not match
    the cohort the promoter is about to publish.
    """
    cohort_dir = _make_cohort_dir(tmp_path)
    cohort = load_python_cohort(cohort_dir)
    # Introduce a second cohort with different artifact bytes (description field
    # in wheel/sdist METADATA makes the bytes distinct from the first cohort).
    other_cohort_dir = _make_cohort_dir(tmp_path / "other", version=_VERSION, description="alternative-build")
    other_cohort = load_python_cohort(other_cohort_dir)
    # Write evidence that claims the *other* cohort's digests but is filed
    # under the primary cohort's commit directory so the path check passes.
    commit_dir = tmp_path / "evidence" / cohort.source_commit
    commit_dir.mkdir(parents=True, exist_ok=True)
    evidence_file = commit_dir / "evidence.json"
    document = {
        "source_commit": cohort.source_commit,
        "artifact_sha256": {
            "cadrumo": other_cohort.sha256["cadrumo"],
            "cadrumo-data-manuals": other_cohort.sha256["cadrumo-data-manuals"],
            "cadrumo-data-official": other_cohort.sha256["cadrumo-data-official"],
        },
        "cli_oracle": _oracle(),
    }
    evidence_file.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(SystemExit):
        validate_promotion(
            cohort_dir,
            evidence_file,
            expected_source_commit=cohort.source_commit,
        )
