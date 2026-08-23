"""Real wheel-member tests for the compact command-bearing artifact boundary."""

from __future__ import annotations

import hashlib
import json
import shutil
import tomllib
import zipfile
from pathlib import Path

import pytest

from cadrumo.core import iter_directory, scan_directory
from dev._paths import REPO_ROOT

from .._distribution_limits import PYPI_FILE_CAP_BYTES
from .._smoke_common import (
    _CORPUS_SOURCE_PREFIX,
    _configured_corpus_binary_suffixes,
    _is_corpus_source_binary,
    build_companion_wheels,
    build_sdist,
    build_wheel,
    commit_defined_build_root,
    expected_wheel_data_paths,
    run_checked,
    tracked_source_data_paths,
)
from ..python_cohort import load_python_cohort
from ..smoke_core import _assert_complete_wheel_cohort
from ..smoke_sdist_core import _assert_sdist_contains_expected_data
from ._cohort_attestation import add_test_source_archive, make_test_command_spec_attestation

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT
_REVIEW_FOUND_PATHS = {
    "src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_349/files/"
    "02-349-orden-eha-769-2010-modificada-por-orden-eha-1721-2011-43-9-kb-docx.docx",
    "src/cadrumo/_data/corpus/aeat_official/instructions/modelo_289/files/289_XSD_2.0_WSDL_2.0.1.zip",
}


# The dirty-tree branch of `commit_defined_build_root` extracts roughly forty
# thousand files before any build starts, measured at three minutes on the
# Windows build host. CI checks out clean and never pays it, but the shared
# factory worktree always does, and the 300 s project ceiling would kill the
# worker mid-extraction with an opaque "node down" instead of a result.
@pytest.mark.timeout(900)
def test_core_wheel_contains_every_runtime_member_and_no_split_owned_binary(tmp_path: Path) -> None:
    """Build the wheel and prove tracked-data parity against companion ownership."""
    uv = shutil.which("uv")
    assert uv is not None
    tracked = tracked_source_data_paths(_REPO_ROOT)
    suffixes = _configured_corpus_binary_suffixes(_REPO_ROOT)
    split_owned = {path for path in tracked if "/tests/" not in path and _is_corpus_source_binary(path, suffixes)}
    assert split_owned >= _REVIEW_FOUND_PATHS

    # Build every artifact from a tree that corresponds to a commit, never from
    # a dirty working tree: the expectations above come from `git ls-files` at
    # HEAD, and in the shared factory worktree a tree build can snapshot a torn
    # peer edit, producing an artifact that matches no commit and failing this
    # test as if it were a packaging regression (issue 613). On a clean checkout
    # this is the tree itself, so CI pays nothing. One root serves all six builds.
    build_root = commit_defined_build_root(_REPO_ROOT, tmp_path / "build-source")

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
        path
        for path in tracked
        if not (
            path.startswith("src/cadrumo/_data/corpus/")
            and path.lower().endswith((".docx", ".pdf", ".xls", ".xlsm", ".xlsx", ".zip"))
        )
        and "/tests/" not in path
    }
    sdist = build_sdist(tmp_path, uv, build_root=build_root)
    _assert_sdist_contains_expected_data(sdist, expected_sdist_data)
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
        digests[name] = hashlib.sha256(retained.read_bytes()).hexdigest()
    add_test_source_archive(cohort_dir, filenames, digests)
    (cohort_dir / "python-cohort.json").write_text(
        json.dumps(
            {
                "artifacts": filenames,
                "sha256": digests,
                "source_commit": "a" * 40,
                "version": expected_version,
                "command_spec_attestation": make_test_command_spec_attestation(
                    cohort_dir, filenames, source_commit="a" * 40
                ),
            },
        ),
        encoding="utf-8",
    )
    cohort = load_python_cohort(cohort_dir)
    assert cohort.version == expected_version
    assert cohort.sha256 == digests


def test_commit_defined_build_root_excludes_uncommitted_working_tree_state(tmp_path: Path) -> None:
    """A dirty tree yields a HEAD extract; a clean tree is used directly.

    This is the property the payload build above depends on. If the resolver
    degraded into always returning the working tree, uncommitted peer edits
    would flow into the artifacts while the expectations still came from HEAD,
    which is the torn-snapshot failure issue 613 observed live. If it always
    extracted, CI would pay three minutes per run for a byte-identical copy.

    Exercised against a real throwaway repository rather than this one: the
    property is about Git, and archiving the full corpus tree to assert it
    costs minutes for no extra discrimination.
    """
    origin = tmp_path / "origin"
    (origin / "packaging").mkdir(parents=True)
    run_checked(["git", "init", "--quiet"], cwd=origin)
    run_checked(["git", "config", "user.email", "probe@example.invalid"], cwd=origin)
    run_checked(["git", "config", "user.name", "probe"], cwd=origin)
    (origin / "committed.txt").write_text("committed content\n", encoding="utf-8")
    (origin / "packaging" / "kept.txt").write_text("nested committed\n", encoding="utf-8")
    run_checked(["git", "add", "committed.txt", "packaging/kept.txt"], cwd=origin)
    run_checked(["git", "commit", "--quiet", "-m", "probe commit"], cwd=origin)

    # Clean tree: the tree already IS the commit, so it is used as-is.
    assert commit_defined_build_root(origin, tmp_path / "clean-work") == origin

    # Dirty the tree exactly as a mid-sweep peer would: one edit to a tracked
    # file and one entirely new untracked file.
    (origin / "committed.txt").write_text("TORN EDIT\n", encoding="utf-8")
    (origin / "untracked.txt").write_text("never committed\n", encoding="utf-8")

    build_root = commit_defined_build_root(origin, tmp_path / "dirty-work")

    assert build_root != origin
    extracted = {
        path.relative_to(build_root).as_posix() for path in scan_directory(build_root, recursive=True) if path.is_file()
    }
    assert extracted == {"committed.txt", "packaging/kept.txt"}, sorted(extracted)
    assert (build_root / "committed.txt").read_text(encoding="utf-8") == "committed content\n"
    assert not (build_root / ".git").exists()
