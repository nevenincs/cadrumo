"""Real wheel-member tests for the compact command-bearing artifact boundary."""

from __future__ import annotations

import hashlib
import json
import shutil
import tomllib
import zipfile
from pathlib import Path

import pytest

from dev.packaging.python_cohort import load_python_cohort
from dev.packaging.smoke_core import (
    _CORPUS_SOURCE_PREFIX,
    _assert_complete_wheel_cohort,
    _build_companion_wheels,
    _build_wheel,
    _configured_corpus_binary_suffixes,
    _expected_wheel_data_paths,
    _head_extract,
    _is_corpus_source_binary,
    _run,
    _tracked_source_data_paths,
)
from dev.packaging.smoke_sdist_core import (
    _assert_sdist_contains_expected_data,
    _build_sdist,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REVIEW_FOUND_PATHS = {
    "src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_349/files/"
    "02-349-orden-eha-769-2010-modificada-por-orden-eha-1721-2011-43-9-kb-docx.docx",
    "src/cadrumo/_data/corpus/aeat_official/instructions/modelo_289/files/289_XSD_2.0_WSDL_2.0.1.zip",
}


def test_core_wheel_contains_every_runtime_member_and_no_split_owned_binary(tmp_path: Path) -> None:
    """Build the wheel and prove tracked-data parity against companion ownership."""
    uv = shutil.which("uv")
    assert uv is not None
    tracked = _tracked_source_data_paths(_REPO_ROOT)
    suffixes = _configured_corpus_binary_suffixes(_REPO_ROOT)
    split_owned = {path for path in tracked if "/tests/" not in path and _is_corpus_source_binary(path, suffixes)}
    assert split_owned >= _REVIEW_FOUND_PATHS

    # Build every artifact from a pristine HEAD tree, never the working tree:
    # the expectations above come from `git ls-files` at HEAD, and in the shared
    # factory worktree a tree build can snapshot a torn peer edit, producing an
    # artifact that corresponds to no commit and failing this test as if it were
    # a packaging regression (issue 613). One extraction serves all three builds.
    build_root = _head_extract(_REPO_ROOT, tmp_path)

    wheel = _build_wheel(_REPO_ROOT, tmp_path, uv, build_root=build_root)
    with zipfile.ZipFile(wheel) as archive:
        members = set(archive.namelist())
    actual_runtime = {name for name in members if name.startswith("cadrumo/_data/") and not name.endswith("/")}

    independently_expected = {
        f"cadrumo/_data/{path.removeprefix('src/cadrumo/_data/')}"
        for path in tracked - split_owned
        if "/tests/" not in path
    }
    assert _expected_wheel_data_paths(_REPO_ROOT) == independently_expected
    assert actual_runtime == independently_expected
    assert not {f"cadrumo/_data/corpus/{path.removeprefix(_CORPUS_SOURCE_PREFIX)}" for path in split_owned} & members

    companions = _build_companion_wheels(tmp_path, uv, build_root=build_root)
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
    sdist = _build_sdist(tmp_path, uv, build_root=build_root)
    _assert_sdist_contains_expected_data(sdist, expected_sdist_data)
    assert sdist.stat().st_size < 100 * 1_000_000

    cohort_dir = tmp_path / "real-cohort"
    cohort_dir.mkdir()
    companion_sdists_dir = tmp_path / "companion-sdists"
    _run(
        [uv, "build", "--sdist", "--out-dir", str(companion_sdists_dir)],
        cwd=build_root / "packaging" / "cadrumo_data_manuals",
    )
    _run(
        [uv, "build", "--sdist", "--out-dir", str(companion_sdists_dir)],
        cwd=build_root / "packaging" / "cadrumo_data_official",
    )
    manuals_sdist = next(companion_sdists_dir.glob("cadrumo_data_manuals-*.tar.gz"))
    official_sdist = next(companion_sdists_dir.glob("cadrumo_data_official-*.tar.gz"))
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
    (cohort_dir / "python-cohort.json").write_text(
        json.dumps(
            {
                "artifacts": filenames,
                "sha256": digests,
                "source_commit": "a" * 40,
                "version": expected_version,
            },
        ),
        encoding="utf-8",
    )
    cohort = load_python_cohort(cohort_dir)
    assert cohort.version == expected_version
    assert cohort.sha256 == digests


def test_head_extract_excludes_uncommitted_working_tree_state(tmp_path: Path) -> None:
    """The extract carries committed content only, never the dirty working tree.

    This is the property the payload build above depends on. If the extractor
    degraded into a working-tree copy, uncommitted peer edits would flow into
    the artifacts and the build would be compared against HEAD-derived
    expectations, which is the torn-snapshot failure issue 613 observed live.

    Exercised against a real throwaway repository rather than this one: the
    property is about Git, and archiving the full corpus tree to assert it
    costs minutes for no extra discrimination.
    """
    origin = tmp_path / "origin"
    (origin / "packaging").mkdir(parents=True)
    _run(["git", "init", "--quiet"], cwd=origin)
    _run(["git", "config", "user.email", "probe@example.invalid"], cwd=origin)
    _run(["git", "config", "user.name", "probe"], cwd=origin)
    (origin / "committed.txt").write_text("committed content\n", encoding="utf-8")
    (origin / "packaging" / "kept.txt").write_text("nested committed\n", encoding="utf-8")
    _run(["git", "add", "committed.txt", "packaging/kept.txt"], cwd=origin)
    _run(["git", "commit", "--quiet", "-m", "probe commit"], cwd=origin)

    # Dirty the tree exactly as a mid-sweep peer would: one edit to a tracked
    # file and one entirely new untracked file.
    (origin / "committed.txt").write_text("TORN EDIT\n", encoding="utf-8")
    (origin / "untracked.txt").write_text("never committed\n", encoding="utf-8")

    extract_root = _head_extract(origin, tmp_path / "work")

    extracted = {path.relative_to(extract_root).as_posix() for path in extract_root.rglob("*") if path.is_file()}
    assert extracted == {"committed.txt", "packaging/kept.txt"}, sorted(extracted)
    assert (extract_root / "committed.txt").read_text(encoding="utf-8") == "committed content\n"
    assert not (extract_root / ".git").exists()
