"""Offline unit tests for the public-reacquisition verification tooling.

Every test drives the real verification and refusal functions against real
on-disk fixtures — no network, and no mocks of first-party code. The heavy
install flows (real venvs, brew, scoop, uv) are exercised only by the
live release pipeline; here we prove the fail-closed cores those flows depend
on: digest verification accepts matching bytes and refuses tampered bytes, and
an unpublished endpoint yields an instructive :class:`SystemExit` naming the
endpoint and version.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from .. import (
    acquire_github_release,
    acquire_homebrew,
    acquire_pypi,
)
from .._acquire_common import (
    AcquisitionError,
    refuse_unavailable,
    require_command_succeeded,
    verify_artifact_digest,
    verify_python_cohort_download,
    verify_release_download,
)
from ..cohort_manifest import (
    REQUIRED_ARTIFACT_KINDS,
    BuildIdentity,
    LoadedReleaseCohort,
    SourceIdentity,
    create_manifest,
    load_release_cohort,
    write_manifest,
)
from ..python_cohort import PythonCohort

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_VERSION = "0.99.0.dev1"
_COMMIT = "a" * 40


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_python_cohort(tmp_path: Path) -> tuple[PythonCohort, Path]:
    """Create three real cohort wheels in a download dir and a matching cohort."""
    download = tmp_path / "downloads"
    download.mkdir()
    wheel_payloads = {
        "cadrumo": (f"cadrumo-{_VERSION}-py3-none-any.whl", b"cadrumo wheel bytes"),
        "cadrumo-data-manuals": (f"cadrumo_data_manuals-{_VERSION}-py3-none-any.whl", b"manuals wheel bytes"),
        "cadrumo-data-official": (f"cadrumo_data_official-{_VERSION}-py3-none-any.whl", b"official wheel bytes"),
    }
    sha256: dict[str, str] = {}
    for name, (filename, payload) in wheel_payloads.items():
        (download / filename).write_bytes(payload)
        sha256[name] = hashlib.sha256(payload).hexdigest()
    # Sdist digests are not backed by files here; the Homebrew formula check
    # compares declared checksums only, so deterministic placeholders suffice.
    sha256["cadrumo-sdist"] = hashlib.sha256(b"cadrumo sdist").hexdigest()
    sha256["cadrumo-data-manuals-sdist"] = hashlib.sha256(b"manuals sdist").hexdigest()
    sha256["cadrumo-data-official-sdist"] = hashlib.sha256(b"official sdist").hexdigest()

    cohort = PythonCohort(
        directory=tmp_path,
        manifest=tmp_path / "python-cohort.json",
        source_commit=_COMMIT,
        version=_VERSION,
        root_wheel=download / wheel_payloads["cadrumo"][0],
        root_sdist=tmp_path / f"cadrumo-{_VERSION}.tar.gz",
        source_archive=tmp_path / "cadrumo-source.zip",
        runtime_wheelhouse=tmp_path / "cadrumo-runtime-wheelhouse-py313.zip",
        runtime_wheelhouse_manifest={},
        manuals_wheel=download / wheel_payloads["cadrumo-data-manuals"][0],
        manuals_sdist=tmp_path / f"cadrumo_data_manuals-{_VERSION}.tar.gz",
        official_wheel=download / wheel_payloads["cadrumo-data-official"][0],
        official_sdist=tmp_path / f"cadrumo_data_official-{_VERSION}.tar.gz",
        sha256=sha256,
    )
    return cohort, download


def _make_release_cohort(tmp_path: Path) -> tuple[LoadedReleaseCohort, Path]:
    """Build and load a complete release cohort with real files."""
    root = tmp_path / "release-cohort"
    (root / "python").mkdir(parents=True)
    filenames = {name: f"artifacts/{name}.bin" for name in REQUIRED_ARTIFACT_KINDS}
    artifacts = []
    for name, relative in filenames.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"{name} bytes".encode())
        artifacts.append((name, REQUIRED_ARTIFACT_KINDS[name], path))
    manifest = create_manifest(
        root=root,
        version="0.99.0",
        source=SourceIdentity(commit=_COMMIT, tag="v0.99.0"),
        created_at=datetime.now(UTC),
        builder=BuildIdentity(
            implementation="dev.packaging.release_cohort",
            format_version=1,
            python="3.13.0",
            uv="0.5.0",
            platform="linux",
            architecture="x86_64",
            build_constraints_sha256="b" * 64,
        ),
        artifacts=artifacts,
    )
    write_manifest(root, manifest)
    return load_release_cohort(root), root


def _release_download_dir(cohort: LoadedReleaseCohort, tmp_path: Path) -> Path:
    """Copy every declared cohort artifact into a fresh download directory."""
    download = tmp_path / "assets"
    download.mkdir()
    for record in cohort.manifest.artifacts:
        source = cohort.directory / record.path
        (download / Path(record.path).name).write_bytes(source.read_bytes())
    return download


# ---------------------------------------------------------------------------
# _acquire_common: refusals
# ---------------------------------------------------------------------------


def test_refuse_unavailable_names_endpoint_and_version() -> None:
    """The instructive refusal carries the mechanism, endpoint, and version."""
    with pytest.raises(SystemExit) as caught:
        refuse_unavailable(
            mechanism="pip download",
            endpoint="https://pypi.org/simple",
            version="1.2.3",
            reason="the version is not on the index",
            next_step="publish it",
        )
    message = str(caught.value)
    assert "https://pypi.org/simple" in message
    assert "1.2.3" in message
    assert "publish it" in message


def test_require_command_succeeded_passes_on_zero() -> None:
    """A successful command returns without raising."""
    require_command_succeeded(
        returncode=0,
        stderr="",
        mechanism="gh release download",
        endpoint="nevenincs/cadrumo@v1.2.3",
        version="1.2.3",
        next_step="n/a",
    )


def test_require_command_succeeded_refuses_on_nonzero() -> None:
    """A non-zero command exit becomes an instructive refusal."""
    with pytest.raises(AcquisitionError) as caught:
        require_command_succeeded(
            returncode=1,
            stderr="release not found: v1.2.3",
            mechanism="gh release download",
            endpoint="nevenincs/cadrumo@v1.2.3",
            version="1.2.3",
            next_step="publish the v1.2.3 release",
        )
    message = str(caught.value)
    assert "nevenincs/cadrumo@v1.2.3" in message
    assert "1.2.3" in message
    assert "release not found" in message


# ---------------------------------------------------------------------------
# _acquire_common: digest verification
# ---------------------------------------------------------------------------


def test_verify_artifact_digest_accepts_matching_bytes(tmp_path: Path) -> None:
    """Matching bytes return the verified digest without raising."""
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"promoted bytes")
    expected = hashlib.sha256(b"promoted bytes").hexdigest()
    assert (
        verify_artifact_digest(
            mechanism="release download",
            endpoint="https://example/cadrumo.bin",
            name="cadrumo",
            path=artifact,
            expected_sha256=expected,
        )
        == expected
    )


def test_verify_artifact_digest_refuses_tampered_bytes(tmp_path: Path) -> None:
    """Drifted bytes fail closed with a digest-mismatch refusal."""
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"tampered bytes")
    with pytest.raises(AcquisitionError, match="digest mismatch"):
        verify_artifact_digest(
            mechanism="release download",
            endpoint="https://example/cadrumo.bin",
            name="cadrumo",
            path=artifact,
            expected_sha256="c" * 64,
        )


def test_verify_python_cohort_download_accepts_matching_wheels(tmp_path: Path) -> None:
    """A complete, byte-matching wheel download verifies every distribution."""
    cohort, download = _make_python_cohort(tmp_path)
    resolved = verify_python_cohort_download(
        download,
        cohort,
        mechanism="pip download",
        endpoint="https://pypi.org/simple",
    )
    assert set(resolved) == {
        "cadrumo",
        "cadrumo-data-manuals",
        "cadrumo-data-official",
    }


def test_verify_python_cohort_download_refuses_tampered_wheel(tmp_path: Path) -> None:
    """A drifted wheel served by the index is refused as a digest mismatch."""
    cohort, download = _make_python_cohort(tmp_path)
    cohort.root_wheel.write_bytes(b"different bytes than promoted")
    with pytest.raises(AcquisitionError, match="digest mismatch"):
        verify_python_cohort_download(
            download,
            cohort,
            mechanism="pip download",
            endpoint="https://pypi.org/simple",
        )


def test_verify_python_cohort_download_refuses_missing_distribution(tmp_path: Path) -> None:
    """An index missing one distribution yields a not-yet-published refusal."""
    cohort, download = _make_python_cohort(tmp_path)
    cohort.official_wheel.unlink()
    with pytest.raises(AcquisitionError) as caught:
        verify_python_cohort_download(
            download,
            cohort,
            mechanism="pip download",
            endpoint="https://pypi.org/simple",
        )
    message = str(caught.value)
    assert "cadrumo-data-official" in message
    assert _VERSION in message


def test_verify_release_download_accepts_complete_cohort(tmp_path: Path) -> None:
    """Every declared release asset present with matching bytes verifies."""
    cohort, _root = _make_release_cohort(tmp_path)
    download = _release_download_dir(cohort, tmp_path)
    resolved = verify_release_download(
        cohort,
        download,
        mechanism="gh release download",
        endpoint="nevenincs/cadrumo@v0.99.0",
    )
    assert set(resolved) == set(REQUIRED_ARTIFACT_KINDS)


def test_verify_release_download_refuses_missing_asset(tmp_path: Path) -> None:
    """A release missing one asset is an instructive not-yet-published refusal."""
    cohort, _root = _make_release_cohort(tmp_path)
    download = _release_download_dir(cohort, tmp_path)
    missing = next(iter(download.iterdir()))
    missing.unlink()
    with pytest.raises(AcquisitionError) as caught:
        verify_release_download(
            cohort,
            download,
            mechanism="gh release download",
            endpoint="nevenincs/cadrumo@v0.99.0",
        )
    assert missing.name in str(caught.value)


def test_verify_release_download_refuses_tampered_asset(tmp_path: Path) -> None:
    """A release asset served with drifted bytes fails closed."""
    cohort, _root = _make_release_cohort(tmp_path)
    download = _release_download_dir(cohort, tmp_path)
    next(iter(download.iterdir())).write_bytes(b"tampered release bytes of a different length")
    with pytest.raises(AcquisitionError):
        verify_release_download(
            cohort,
            download,
            mechanism="gh release download",
            endpoint="nevenincs/cadrumo@v0.99.0",
        )


# ---------------------------------------------------------------------------
# Homebrew formula digest verification
# ---------------------------------------------------------------------------


def _homebrew_formula(cohort: PythonCohort) -> dict[str, Any]:
    """Build a brew-info formula object whose digests match the cohort sdists."""
    return {
        "urls": {"stable": {"url": "https://example/cadrumo.tar.gz", "checksum": cohort.sha256["cadrumo-sdist"]}},
        "resources": [
            {"name": "cadrumo-data-manuals", "checksum": cohort.sha256["cadrumo-data-manuals-sdist"]},
            {"name": "cadrumo-data-official", "checksum": cohort.sha256["cadrumo-data-official-sdist"]},
        ],
    }


def test_verify_homebrew_formula_digests_accepts_matching(tmp_path: Path) -> None:
    """A formula declaring the exact cohort sdist digests verifies cleanly."""
    cohort, _download = _make_python_cohort(tmp_path)
    verified = acquire_homebrew.verify_homebrew_formula_digests(_homebrew_formula(cohort), cohort)
    assert set(verified) == {"cadrumo", "cadrumo-data-manuals", "cadrumo-data-official"}


def test_verify_homebrew_formula_digests_refuses_drift(tmp_path: Path) -> None:
    """A formula whose source digest drifts from the cohort is refused."""
    cohort, _download = _make_python_cohort(tmp_path)
    formula = _homebrew_formula(cohort)
    formula["urls"]["stable"]["checksum"] = "d" * 64
    with pytest.raises(AcquisitionError, match="digest mismatch"):
        acquire_homebrew.verify_homebrew_formula_digests(formula, cohort)


def test_verify_homebrew_formula_digests_refuses_missing_resource(tmp_path: Path) -> None:
    """A formula missing a data-distribution resource fails closed."""
    cohort, _download = _make_python_cohort(tmp_path)
    formula = _homebrew_formula(cohort)
    formula["resources"] = [formula["resources"][0]]
    with pytest.raises(AcquisitionError, match="missing"):
        acquire_homebrew.verify_homebrew_formula_digests(formula, cohort)


# ---------------------------------------------------------------------------
# Argument contracts
# ---------------------------------------------------------------------------


def test_pypi_parser_defaults_to_public_index() -> None:
    """The PyPI script defaults its index to the public PyPI simple endpoint."""
    args = acquire_pypi._parser().parse_args(["--cohort-dir", "c", "--evidence-dir", "e"])
    assert args.index_url == "https://pypi.org/simple"
    assert args.cohort_dir == Path("c")


def test_github_release_parser_defaults_to_canonical_repo() -> None:
    """The GitHub release script defaults to the canonical repository slug."""
    args = acquire_github_release._parser().parse_args(["--cohort-dir", "c", "--evidence-dir", "e"])
    assert args.repo == "nevenincs/cadrumo"


def test_homebrew_parser_defaults_to_public_tap() -> None:
    """The Homebrew script defaults to the public tap."""
    args = acquire_homebrew._parser().parse_args(["--cohort-dir", "c", "--evidence-dir", "e"])
    assert args.tap == "nevenincs/tap"


@pytest.mark.parametrize(
    "parser_factory",
    [
        acquire_pypi._parser,
        acquire_github_release._parser,
        acquire_homebrew._parser,
    ],
)
def test_parsers_require_cohort_and_evidence_dirs(parser_factory) -> None:
    """Every acquisition script requires --cohort-dir and --evidence-dir."""
    with pytest.raises(SystemExit):
        parser_factory().parse_args([])


# ---------------------------------------------------------------------------
# Scoop PowerShell contract
# ---------------------------------------------------------------------------


def test_scoop_script_declares_public_acquisition_contract() -> None:
    """The Scoop lane exposes a public bucket source, container mode, and oracles."""
    script = (Path(__file__).resolve().parents[1] / "acquire_scoop.ps1").read_text(encoding="utf-8")
    assert "$BucketSource" in script
    assert '[string]$Mode = "Container"' in script
    assert "Assert-InstalledCohortDigests" in script
    assert "dev.packaging.installed_tax_oracle" in script
    assert "public reacquisition" in script
    assert "public reacquisition digest mismatch" in script
