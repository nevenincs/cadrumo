"""The mandatory normative companion participates in every cohort refusal."""

from __future__ import annotations

import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest

from .. import python_cohort as owner
from ..cohort_attestation import make_minimal_test_python_cohort
from ..smoke_core import _assert_complete_wheel_cohort

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_VERSION = "1.0.0"


def _cohort(directory: Path) -> owner.PythonCohort:
    make_minimal_test_python_cohort(directory, version=_VERSION)
    cohort = owner.load_python_cohort(directory)
    assert cohort.companion_wheels == (cohort.manuals_wheel, cohort.official_wheel, cohort.normatives_wheel)
    return cohort


def _replace_metadata(artifact: Path, *, version: str, requirements: tuple[str, ...] = (), padding: int = 0) -> None:
    distribution = "cadrumo" if artifact.name.startswith("cadrumo-") else "cadrumo-data-normatives"
    metadata = "\n".join(
        (f"Name: {distribution}", f"Version: {version}", *(f"Requires-Dist: {row}" for row in requirements), "")
    ).encode()
    prefix = f"{distribution.replace('-', '_')}-{version}"
    if artifact.suffix == ".whl":
        with zipfile.ZipFile(artifact, "w") as archive:
            archive.writestr(f"{prefix}.dist-info/METADATA", metadata)
            if padding:
                archive.writestr("cadrumo_data/corpus/normatives/evidence.pdf", b"x" * padding)
    else:
        with tarfile.open(artifact, "w:gz") as archive:
            info = tarfile.TarInfo(f"{prefix}/PKG-INFO")
            info.size = len(metadata)
            archive.addfile(info, io.BytesIO(metadata))
            if padding:
                info = tarfile.TarInfo(f"{prefix}/evidence.pdf")
                info.size = padding
                # Distinct byte values avoid turning the cap probe into a tiny
                # compressed repeated-byte fixture.
                archive.addfile(info, io.BytesIO(bytes(range(256)) * (padding // 256)))


def _validate(cohort: owner.PythonCohort, kind: str) -> None:
    if kind == "wheel":
        assert owner._validate_wheel_contract(*cohort.product_wheels) == _VERSION
    else:
        owner._validate_sdist_contract(
            cohort.root_sdist,
            cohort.manuals_sdist,
            cohort.official_sdist,
            cohort.normatives_sdist,
            expected_version=_VERSION,
        )


@pytest.mark.parametrize(
    "removed",
    [
        ("cadrumo-data-normatives",),
        ("cadrumo-data-normatives-sdist",),
        ("cadrumo-data-normatives", "cadrumo-data-normatives-sdist"),
    ],
)
def test_missing_normative_artifacts_refuse_old_or_partial_cohorts(tmp_path: Path, removed: tuple[str, ...]) -> None:
    cohort = _cohort(tmp_path)
    document = json.loads(cohort.manifest.read_text(encoding="utf-8"))
    for name in removed:
        (tmp_path / document["artifacts"].pop(name)).unlink()
        del document["sha256"][name]
    cohort.manifest.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(SystemExit, match="manifest keys drifted"):
        owner.load_python_cohort(tmp_path)


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_normative_version_drift_refuses_the_whole_cohort(tmp_path: Path, kind: str) -> None:
    cohort = _cohort(tmp_path)
    _validate(cohort, kind)
    artifact = cohort.normatives_wheel if kind == "wheel" else cohort.normatives_sdist
    _replace_metadata(artifact, version="2.0.0")
    with pytest.raises(SystemExit, match="identities or versions drifted"):
        _validate(cohort, kind)


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_normative_cap_is_strict_at_the_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    cohort = _cohort(tmp_path)
    artifact = cohort.normatives_wheel if kind == "wheel" else cohort.normatives_sdist
    _replace_metadata(artifact, version=_VERSION, padding=8192)
    assert owner.PYPI_FILE_CAP_BYTES == 100_000_000
    # Exercise the actual archive size boundary without retaining a 100 MB
    # synthetic archive. The real-build distribution gate keeps the real cap.
    monkeypatch.setattr(owner, "PYPI_FILE_CAP_BYTES", artifact.stat().st_size + 1)
    _validate(cohort, kind)
    monkeypatch.setattr(owner, "PYPI_FILE_CAP_BYTES", artifact.stat().st_size)
    with pytest.raises(SystemExit, match=r"cadrumo_data_normatives.*exceeds"):
        _validate(cohort, kind)


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
@pytest.mark.parametrize(
    "normative_pin",
    [
        None,
        "cadrumo-data-normatives==2.0.0",
        "cadrumo-data-normatives[optional]==1.0.0",
        'cadrumo-data-normatives==1.0.0; python_version >= "3.13"',
    ],
)
def test_root_requires_an_unconditional_exact_normative_pin(
    tmp_path: Path, kind: str, normative_pin: str | None
) -> None:
    cohort = _cohort(tmp_path)
    requirements = ("cadrumo-data-manuals==1.0.0", "cadrumo-data-official==1.0.0")
    if normative_pin is not None:
        requirements += (normative_pin,)
    _replace_metadata(
        cohort.root_wheel if kind == "wheel" else cohort.root_sdist, version=_VERSION, requirements=requirements
    )
    with pytest.raises(SystemExit, match="cadrumo-data-normatives"):
        _validate(cohort, kind)
    if kind == "wheel":
        with pytest.raises(SystemExit, match="cadrumo-data-normatives"):
            _assert_complete_wheel_cohort(
                cohort.root_wheel,
                data_wheel_manuals=cohort.manuals_wheel,
                data_wheel_official=cohort.official_wheel,
                data_wheel_normatives=cohort.normatives_wheel,
            )


def test_normative_install_target_binds_local_origin_and_digest(tmp_path: Path) -> None:
    cohort = _cohort(tmp_path)
    targets = owner.install_targets(cohort, root_artifact=cohort.root_wheel)
    assert len(targets) == 4
    assert targets[-1] == (
        f"cadrumo-data-normatives @ {cohort.normatives_wheel.as_uri()}"
        f"#sha256={cohort.sha256['cadrumo-data-normatives']}"
    )


@pytest.mark.parametrize("mutation", ["missing", "recorded_digest", "origin_bytes"])
def test_normative_installed_origin_is_mandatory_and_digest_bound(tmp_path: Path, mutation: str) -> None:
    cohort = _cohort(tmp_path)
    urls = {
        name: {"url": artifact.as_uri(), "archive_info": {"hashes": {"sha256": cohort.sha256[name]}}}
        for name, artifact in zip(
            ("cadrumo", "cadrumo-data-manuals", "cadrumo-data-official", "cadrumo-data-normatives"),
            cohort.product_wheels,
            strict=True,
        )
    }
    owner._verify_direct_urls(urls, cohort, cohort.root_wheel)
    if mutation == "missing":
        del urls["cadrumo-data-normatives"]
    elif mutation == "recorded_digest":
        urls["cadrumo-data-normatives"]["archive_info"] = {"hashes": {"sha256": "0" * 64}}
    else:
        cohort.normatives_wheel.write_bytes(b"substituted after installation")
    with pytest.raises(SystemExit, match="cadrumo-data-normatives"):
        owner._verify_direct_urls(urls, cohort, cohort.root_wheel)
