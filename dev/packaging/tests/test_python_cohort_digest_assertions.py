"""Digest-assertion fail-closed tests for the cohort installer-verification loop.

Tests drive :func:`dev.packaging.python_cohort._verify_direct_urls` and
:func:`dev.packaging.python_cohort.digest_install_target` directly with real
on-disk artifact files and synthetic ``direct_url.json`` documents, avoiding
the subprocess ``_INSTALLED_PROBE`` dependency while exercising the same
branch paths the live install path takes.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ..python_cohort import (
    PythonCohort,
    _verify_direct_urls,
    digest_install_target,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_VERSION = "0.99.0.dev1"
_SAMPLE_COMMIT = "a" * 40


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_artifacts(tmp_path: Path) -> tuple[PythonCohort, Path]:
    """Create minimal real on-disk artifacts and a matching :class:`PythonCohort`.

    The files contain only raw bytes — not valid wheel or sdist archives —
    because :func:`_verify_direct_urls` reads bytes for hashing but does not
    parse wheel metadata.
    """
    payloads: dict[str, bytes] = {
        "cadrumo": b"cadrumo wheel bytes",
        "cadrumo-sdist": b"cadrumo sdist bytes",
        "cadrumo-data-manuals": b"manuals wheel bytes",
        "cadrumo-data-official": b"official wheel bytes",
    }
    paths: dict[str, Path] = {
        "cadrumo": tmp_path / f"cadrumo-{_VERSION}-py3-none-any.whl",
        "cadrumo-sdist": tmp_path / f"cadrumo-{_VERSION}.tar.gz",
        "cadrumo-data-manuals": tmp_path / f"cadrumo_data_manuals-{_VERSION}-py3-none-any.whl",
        "cadrumo-data-official": tmp_path / f"cadrumo_data_official-{_VERSION}-py3-none-any.whl",
    }
    sha256: dict[str, str] = {}
    for name, data in payloads.items():
        paths[name].write_bytes(data)
        sha256[name] = hashlib.sha256(data).hexdigest()

    cohort = PythonCohort(
        directory=tmp_path,
        manifest=tmp_path / "python-cohort.json",
        source_commit=_SAMPLE_COMMIT,
        version=_VERSION,
        root_wheel=paths["cadrumo"],
        root_sdist=paths["cadrumo-sdist"],
        source_archive=tmp_path / "cadrumo-source.zip",
        runtime_wheelhouse=tmp_path / "cadrumo-runtime-wheelhouse-py313.zip",
        runtime_wheelhouse_manifest={},
        manuals_wheel=paths["cadrumo-data-manuals"],
        manuals_sdist=tmp_path / f"cadrumo_data_manuals-{_VERSION}.tar.gz",
        official_wheel=paths["cadrumo-data-official"],
        official_sdist=tmp_path / f"cadrumo_data_official-{_VERSION}.tar.gz",
        sha256=sha256,
    )
    return cohort, paths["cadrumo"]  # root_artifact = root wheel


def _uv_direct_urls(cohort: PythonCohort, root_artifact: Path) -> dict[str, dict[str, object]]:
    """Build a direct_urls doc in uv style: empty archive_info, hash in URL fragment."""
    root_resolved = root_artifact.resolve()
    return {
        "cadrumo": {
            "url": f"{root_resolved.as_uri()}#sha256={cohort.sha256['cadrumo']}",
            "archive_info": {},
        },
        "cadrumo-data-manuals": {
            "url": f"{cohort.manuals_wheel.as_uri()}#sha256={cohort.sha256['cadrumo-data-manuals']}",
            "archive_info": {},
        },
        "cadrumo-data-official": {
            "url": f"{cohort.official_wheel.as_uri()}#sha256={cohort.sha256['cadrumo-data-official']}",
            "archive_info": {},
        },
    }


def _pip_direct_urls(cohort: PythonCohort, root_artifact: Path) -> dict[str, dict[str, object]]:
    """Build a direct_urls doc in pip style: hash in archive_info, bare file URL."""
    root_resolved = root_artifact.resolve()
    return {
        "cadrumo": {
            "url": root_resolved.as_uri(),
            "archive_info": {"hashes": {"sha256": cohort.sha256["cadrumo"]}},
        },
        "cadrumo-data-manuals": {
            "url": cohort.manuals_wheel.as_uri(),
            "archive_info": {"hashes": {"sha256": cohort.sha256["cadrumo-data-manuals"]}},
        },
        "cadrumo-data-official": {
            "url": cohort.official_wheel.as_uri(),
            "archive_info": {"hashes": {"sha256": cohort.sha256["cadrumo-data-official"]}},
        },
    }


# ---------------------------------------------------------------------------
# Tests for _verify_direct_urls
# ---------------------------------------------------------------------------


def test_uv_style_url_fragment_passes(tmp_path: Path) -> None:
    """Uv's empty archive_info + fragment channel is accepted for every member."""
    cohort, root_artifact = _make_artifacts(tmp_path)
    urls = _uv_direct_urls(cohort, root_artifact)
    _verify_direct_urls(urls, cohort, root_artifact)  # must not raise


def test_pip_style_archive_info_passes(tmp_path: Path) -> None:
    """Pip's archive_info.hashes channel is accepted for every member."""
    cohort, root_artifact = _make_artifacts(tmp_path)
    urls = _pip_direct_urls(cohort, root_artifact)
    _verify_direct_urls(urls, cohort, root_artifact)  # must not raise


def test_drifted_recorded_digest_is_refused(tmp_path: Path) -> None:
    """A stale or wrong sha256 in installer metadata is caught before origin re-hash."""
    cohort, root_artifact = _make_artifacts(tmp_path)
    urls = _uv_direct_urls(cohort, root_artifact)
    # Replace the fragment hash with a wrong value, keeping the URL path correct.
    bad_sha = "b" * 64
    root_resolved = root_artifact.resolve()
    modified = dict(urls)
    modified["cadrumo"] = {
        "url": f"{root_resolved.as_uri()}#sha256={bad_sha}",
        "archive_info": {},
    }
    with pytest.raises(SystemExit, match="installed digest drifted"):
        _verify_direct_urls(modified, cohort, root_artifact)


def test_drifted_origin_bytes_is_refused(tmp_path: Path) -> None:
    """Artifact bytes replaced on disk after recording the hash are refused."""
    cohort, root_artifact = _make_artifacts(tmp_path)
    # The recorded digest in the URL still matches cohort.sha256, but the file
    # now contains different bytes, so origin_sha != expected_sha.
    urls = _uv_direct_urls(cohort, root_artifact)
    root_artifact.write_bytes(b"tampered content replaces original wheel bytes")
    with pytest.raises(SystemExit, match="origin bytes drifted after install"):
        _verify_direct_urls(urls, cohort, root_artifact)


def test_unrelated_origin_url_is_refused(tmp_path: Path) -> None:
    """An artifact installed from a different path is refused regardless of hash."""
    cohort, root_artifact = _make_artifacts(tmp_path)
    urls = _uv_direct_urls(cohort, root_artifact)
    other = tmp_path / "other" / "cadrumo-elsewhere.whl"
    other.parent.mkdir()
    other.write_bytes(b"different origin")
    modified = dict(urls)
    modified["cadrumo"] = {
        "url": other.as_uri(),
        "archive_info": {},
    }
    with pytest.raises(SystemExit, match="unrelated origin"):
        _verify_direct_urls(modified, cohort, root_artifact)


# ---------------------------------------------------------------------------
# Tests for digest_install_target
# ---------------------------------------------------------------------------


def test_digest_install_target_emits_pinned_direct_url_requirement(tmp_path: Path) -> None:
    """digest_install_target returns name @ file://path#sha256=<real hash>."""
    artifact = tmp_path / f"cadrumo-{_VERSION}-py3-none-any.whl"
    content = b"cadrumo wheel bytes for digest test"
    artifact.write_bytes(content)
    expected_sha = hashlib.sha256(content).hexdigest()
    result = digest_install_target("cadrumo", artifact)
    assert result == f"cadrumo @ {artifact.resolve().as_uri()}#sha256={expected_sha}"


def test_digest_install_target_with_extras_brackets_the_name(tmp_path: Path) -> None:
    """Extras are bracketed between the name and the @ separator."""
    artifact = tmp_path / f"cadrumo-{_VERSION}-py3-none-any.whl"
    artifact.write_bytes(b"cadrumo wheel bytes")
    expected_sha = hashlib.sha256(b"cadrumo wheel bytes").hexdigest()
    result = digest_install_target("cadrumo", artifact, extras=("dev", "test"))
    assert result == f"cadrumo[dev,test] @ {artifact.resolve().as_uri()}#sha256={expected_sha}"


def test_digest_install_target_raises_on_missing_artifact(tmp_path: Path) -> None:
    """Resolving a non-existent artifact fails closed before hashing is attempted."""
    missing = tmp_path / "cadrumo-nonexistent.whl"
    with pytest.raises(OSError):
        digest_install_target("cadrumo", missing)
