"""Real wheel-member tests for the compact command-bearing artifact boundary."""

from __future__ import annotations

import io
import json
import shutil
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import iter_directory

from ..._paths import REPO_ROOT
from .._distribution_limits import PYPI_FILE_CAP_BYTES
from ..hashing import sha256_path
from ..lane_verification_core import (
    _CORPUS_SOURCE_PREFIX,
    _MANUAL_PDF_PRESENCE_FLOOR,
    _configured_corpus_binary_suffixes,
    _is_corpus_source_binary,
    _validated_source_data_inventory,
    assert_wheel_contains_tracked_data,
    build_companion_wheels,
    build_root_snapshot,
    build_sdist,
    build_source_data_paths,
    build_wheel,
    expected_wheel_data_paths,
    recorded_proofs,
    reset_proof_ledger,
    run_checked,
    tracked_source_data_paths,
)
from ..python_cohort import load_python_cohort
from ..smoke_core import _assert_complete_wheel_cohort
from ..smoke_sdist_core import _assert_sdist_contains_expected_data
from ._cohort_attestation import (
    add_test_runtime_wheelhouse,
    add_test_source_archive,
    make_test_command_spec_attestation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT
_REVIEW_FOUND_PATHS = {
    "src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_349/files/"
    "02-349-orden-eha-769-2010-modificada-por-orden-eha-1721-2011-43-9-kb-docx.docx",
    "src/cadrumo/_data/corpus/aeat_official/instructions/modelo_289/files/289_XSD_2.0_WSDL_2.0.1.zip",
}


# `build_root_snapshot` copies roughly forty thousand files before any build
# starts, measured at three minutes on the Windows build host, because every
# build now runs from an isolated snapshot rather than the live tree. The
# 300 s project ceiling would kill the worker mid-copy with an opaque "node
# down" instead of a result.
@pytest.mark.timeout(900)
def test_core_wheel_contains_every_runtime_member_and_no_split_owned_binary(tmp_path: Path) -> None:
    """Build the wheel and prove tracked-data parity against companion ownership."""
    uv = shutil.which("uv")
    assert uv is not None
    tracked = tracked_source_data_paths(_REPO_ROOT)
    suffixes = _configured_corpus_binary_suffixes(_REPO_ROOT)
    split_owned = {path for path in tracked if "/tests/" not in path and _is_corpus_source_binary(path, suffixes)}
    assert split_owned >= _REVIEW_FOUND_PATHS

    # Build every artifact from an isolated snapshot, never from the live
    # working tree: the expectations above come from the same enumeration
    # `build_root_snapshot` copies from, and in the shared factory worktree a
    # live-tree build can straddle a torn peer edit, producing an artifact
    # that matches no fixed content and failing this test as if it were a
    # packaging regression (issue 613). One root serves all six builds.
    build_root = build_root_snapshot(_REPO_ROOT, tmp_path / "build-source")

    wheel = build_wheel(_REPO_ROOT, tmp_path, uv, build_root=build_root)
    with zipfile.ZipFile(wheel) as archive:
        members = set(archive.namelist())
    actual_runtime = {name for name in members if name.startswith("cadrumo/_data/") and not name.endswith("/")}

    independently_expected = {
        f"cadrumo/_data/{path.removeprefix('src/cadrumo/_data/')}"
        for path in tracked - split_owned
        if "/tests/" not in path
    }
    assert expected_wheel_data_paths(_REPO_ROOT) == independently_expected
    assert actual_runtime == independently_expected
    assert not {f"cadrumo/_data/corpus/{path.removeprefix(_CORPUS_SOURCE_PREFIX)}" for path in split_owned} & members

    companions = build_companion_wheels(tmp_path, uv, build_root=build_root)
    with (_REPO_ROOT / "pyproject.toml").open("rb") as handle:
        expected_version = tomllib.load(handle)["project"]["version"]
    assert (
        _assert_complete_wheel_cohort(
            wheel,
            data_wheel_manuals=companions[0],
            data_wheel_official=companions[1],
        )
        == expected_version
    )
    with pytest.raises(SystemExit, match="labels do not match"):
        _assert_complete_wheel_cohort(
            wheel,
            data_wheel_manuals=companions[1],
            data_wheel_official=companions[0],
        )

    expected_sdist_data = {
        path for path in tracked if not _is_corpus_source_binary(path, suffixes) and "/tests/" not in path
    }
    sdist = build_sdist(tmp_path, uv, build_root=build_root)
    _assert_sdist_contains_expected_data(sdist, expected_sdist_data, corpus_binary_suffixes=suffixes)
    assert sdist.stat().st_size < PYPI_FILE_CAP_BYTES

    cohort_dir = tmp_path / "real-cohort"
    cohort_dir.mkdir()
    companion_sdists_dir = tmp_path / "companion-sdists"
    run_checked(
        [uv, "build", "--sdist", "--out-dir", str(companion_sdists_dir)],
        cwd=build_root / "packaging" / "cadrumo_data_manuals",
    )
    run_checked(
        [uv, "build", "--sdist", "--out-dir", str(companion_sdists_dir)],
        cwd=build_root / "packaging" / "cadrumo_data_official",
    )
    manuals_sdist = next(iter_directory(companion_sdists_dir, pattern="cadrumo_data_manuals-*.tar.gz"))
    official_sdist = next(iter_directory(companion_sdists_dir, pattern="cadrumo_data_official-*.tar.gz"))
    artifacts = {
        "cadrumo": wheel,
        "cadrumo-sdist": sdist,
        "cadrumo-data-manuals": companions[0],
        "cadrumo-data-manuals-sdist": manuals_sdist,
        "cadrumo-data-official": companions[1],
        "cadrumo-data-official-sdist": official_sdist,
    }
    filenames: dict[str, str] = {}
    digests: dict[str, str] = {}
    for name, artifact in artifacts.items():
        retained = cohort_dir / artifact.name
        shutil.copy2(artifact, retained)
        filenames[name] = retained.name
        digests[name] = sha256_path(retained)
    add_test_source_archive(cohort_dir, filenames, digests)
    add_test_runtime_wheelhouse(cohort_dir, filenames, digests)
    (cohort_dir / "python-cohort.json").write_text(
        json.dumps(
            {
                "artifacts": filenames,
                "sha256": digests,
                "source_digest": "a" * 64,
                "version": expected_version,
                "command_spec_attestation": make_test_command_spec_attestation(
                    cohort_dir, filenames, source_digest="a" * 64
                ),
            },
        ),
        encoding="utf-8",
    )
    cohort = load_python_cohort(cohort_dir)
    assert cohort.version == expected_version
    assert cohort.sha256 == digests


def _seed_shipped_data_repository(origin: Path) -> set[str]:
    """Plant a minimal shipped-data tree with one ignore rule, no version control."""
    (origin / ".gitignore").write_text(
        "__pycache__/\n/src/cadrumo/_data/registry/aeat/.*.lock\n",
        encoding="utf-8",
    )
    tracked = {"src/cadrumo/_data/registry/aeat/modelos/036/manifest.toml", *_MANUAL_PDF_PRESENCE_FLOOR}
    for relative in sorted(tracked):
        path = origin / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode("utf-8"))
    return tracked


def test_shipped_data_inventory_is_identical_between_the_live_tree_and_a_snapshot(tmp_path: Path) -> None:
    """Ignored artefacts beside the sources cannot move the shipped-data inventory.

    A working tree carrying registry transaction mutexes and bytecode caches
    is filtered by the same ignore rules the wheel build's file selection
    uses, so counting them would demand payload the wheel can never contain.
    The inventory therefore reads the same on the live tree and on a snapshot
    build root taken from it.
    """
    origin = tmp_path / "origin"
    origin.mkdir()
    tracked = _seed_shipped_data_repository(origin)

    assert build_source_data_paths(origin) == tracked
    assert build_source_data_paths(build_root_snapshot(origin, tmp_path / "snapshot-before")) == tracked

    ignored_artefacts = (
        origin / "src/cadrumo/_data/registry/aeat/.publication-transaction.lock",
        origin / "src/cadrumo/_data/__pycache__/__init__.cpython-313.pyc",
    )
    for artefact in ignored_artefacts:
        artefact.parent.mkdir(parents=True, exist_ok=True)
        artefact.write_bytes(b"transient\n")
    assert all(artefact.is_file() for artefact in ignored_artefacts)

    assert build_source_data_paths(origin) == tracked
    assert build_source_data_paths(build_root_snapshot(origin, tmp_path / "snapshot-after")) == tracked


def test_shipped_data_inventory_reflects_a_deleted_tracked_file(tmp_path: Path) -> None:
    """A file removed from the source tree drops out of the derived inventory.

    The enumerated tree has no index separate from the working tree, so a
    deleted file is excluded from the inventory rather than flagged as a
    stale reference: the derivation always describes what is actually on
    disk, never what used to be.
    """
    origin = tmp_path / "origin"
    origin.mkdir()
    tracked = _seed_shipped_data_repository(origin)
    removed = "src/cadrumo/_data/registry/aeat/modelos/036/manifest.toml"
    (origin / removed).unlink()

    remaining = build_source_data_paths(origin)

    assert removed not in remaining
    assert remaining == tracked - {removed}


def test_shipped_data_inventory_refuses_a_named_path_absent_from_disk(tmp_path: Path) -> None:
    """A derived inventory naming a path that is not on disk fails closed.

    The enumerated tree only ever names files that exist, so this exercises
    the validation directly against a synthetic inventory -- the shape a
    caller would see if a named path vanished between being enumerated and
    being read.
    """
    origin = tmp_path / "origin"
    (origin / "src/cadrumo/_data").mkdir(parents=True)
    present = "src/cadrumo/_data/present.toml"
    (origin / present).write_bytes(b"present")

    with pytest.raises(SystemExit, match="are absent from"):
        _validated_source_data_inventory(
            origin,
            {present, "src/cadrumo/_data/missing.toml"},
            origin="synthetic inventory",
        )


def test_tracked_source_data_paths_refuses_a_missing_manual_pdf_floor_member(tmp_path: Path) -> None:
    """A deleted manual PDF named by the presence floor still fails the preflight, by name.

    General shipped-data deletion is no longer detectable without a git index
    (see the sibling "reflects a deleted tracked file" test), but this
    specific, enumerated floor is checked by membership rather than by
    comparing the inventory to itself, so a deletion inside it still fails
    closed -- the property `source_preflight` still has teeth for.
    """
    origin = tmp_path / "origin"
    origin.mkdir()
    _seed_shipped_data_repository(origin)
    removed = next(iter(sorted(_MANUAL_PDF_PRESENCE_FLOOR)))
    (origin / removed).unlink()

    with pytest.raises(SystemExit, match="missing required manual PDFs"):
        tracked_source_data_paths(origin)


def _write_data_wheel(path: Path, members: set[str]) -> Path:
    """Write a minimal archive carrying exactly the named wheel data members."""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("cadrumo/__init__.py", "")
        for member in sorted(members):
            archive.writestr(member, member)
    return path


def test_wheel_data_gate_detects_both_absent_and_surplus_payload(tmp_path: Path) -> None:
    """The payload gate still fails closed on a genuinely incomplete or padded wheel.

    Deriving the expectation from the enumerated tree rather than from a naive
    filesystem walk must not blunt the gate it feeds, so both directions are proven here against
    synthetic archives: a wheel that omits expected data, and a wheel that
    carries an ignored artefact the source tree never tracked. The complete
    archive is asserted to pass in the same test, so a gate that stopped
    comparing could not read as green.
    """
    expected = {
        "cadrumo/_data/registry/aeat/modelos/036/manifest.toml",
        "cadrumo/_data/registry/cadrumo/user_profile/schema.toml",
    }
    reset_proof_ledger()

    complete = _write_data_wheel(tmp_path / "complete.whl", expected)
    assert_wheel_contains_tracked_data(_REPO_ROOT, complete, expected)
    assert "wheel tracked shipped-data payload" in recorded_proofs()

    absent = _write_data_wheel(tmp_path / "absent.whl", {next(iter(sorted(expected)))})
    with pytest.raises(SystemExit, match="missing="):
        assert_wheel_contains_tracked_data(_REPO_ROOT, absent, expected)

    surplus = _write_data_wheel(
        tmp_path / "surplus.whl",
        expected | {"cadrumo/_data/registry/aeat/.m200-2024-source-rebind.lock.lock"},
    )
    with pytest.raises(SystemExit, match="unexpected="):
        assert_wheel_contains_tracked_data(_REPO_ROOT, surplus, expected)
    reset_proof_ledger()


def _write_corpus_sdist(path: Path, corpus_members: set[str]) -> Path:
    """Write a minimal ``.tar.gz`` sdist carrying only the named corpus members."""
    with tarfile.open(path, "w:gz") as archive:
        for member in sorted(corpus_members):
            name = f"cadrumo-0.0.0/src/cadrumo/_data/corpus/{member}"
            info = tarfile.TarInfo(name)
            info.size = 1
            archive.addfile(info, io.BytesIO(b"x"))
    return path


def test_sdist_leak_check_screens_the_configured_suffixes_and_only_those(tmp_path: Path) -> None:
    """Prove the companion-binary leak check reads its population from the build config.

    The check used to carry its own literal suffix tuple. That made it a screen
    over a population it never read: the root wheel's ``exclude`` configuration
    is what actually splits a corpus binary out of the sdist, so a suffix added
    there would be split out and arrive in the sdist unmeasured, and the check
    would report clean having never looked for it. Both directions are proved
    here -- a configured suffix is caught, an unconfigured one is not -- and the
    widened set proves the population is the parameter rather than a constant.
    """
    configured = _configured_corpus_binary_suffixes(_REPO_ROOT)
    assert ".docx" in configured
    assert ".doc" not in configured
    reset_proof_ledger()

    # A member whose suffix the configuration excludes must be caught.
    leaked = _write_corpus_sdist(tmp_path / "leaked.tar.gz", {"aeat_official/a.docx"})
    with pytest.raises(SystemExit, match="companion-owned corpus binaries"):
        _assert_sdist_contains_expected_data(leaked, set(), corpus_binary_suffixes=configured)

    # Corpus members the configuration does not exclude are not leaks, and the
    # archive that carries only those must pass rather than be flagged.
    clean = _write_corpus_sdist(
        tmp_path / "clean.tar.gz",
        {"aeat_official/b.json", "aeat_official/c.html", "aeat_official/d.doc"},
    )
    _assert_sdist_contains_expected_data(clean, set(), corpus_binary_suffixes=configured)
    assert "sdist tracked shipped-data payload" in recorded_proofs()

    # The same archive read against a configuration that DOES exclude ``.doc``
    # is a leak. A literal tuple in the assertion could not produce this answer.
    with pytest.raises(SystemExit, match="companion-owned corpus binaries"):
        _assert_sdist_contains_expected_data(clean, set(), corpus_binary_suffixes=(*configured, ".doc"))
    reset_proof_ledger()
