"""Dev-path isolation gate: the one-way ``src/`` -> ``dev/`` boundary, absolute.

The development tooling tree ships in neither the wheel nor the sdist. By
operator ruling the boundary is ABSOLUTE: no module under ``src/`` -- shipped
or test, ``cadrumo`` or ``cadrumo-harness`` -- may have ANY awareness of the
dev tree. Family 5 detects an import of ``dev.*`` (static or dynamic), Family
6 detects a module building a path into ``dev/``, and Family 10 detects prose
awareness -- a comment, docstring or multi-line string naming the dev tree.
A test that needs dev tooling lives under ``dev/`` itself, where this gate
now lives too.

Single detector authority
-------------------------
All three detectors live in ``dev/quality/import_hygiene_scan.py`` and this
gate ASSERTS against them rather than carrying its own copy. What stays local
here is the PROOF, not the detection: every firing and silence proof below
plants a synthetic module under an injectable root and asserts what the shared
detector returns for it. That is the right division -- the detector is shared
so it cannot fork, and the proofs are local so this gate cannot pass while
blind.

Anti-tautology coverage
-----------------------
Each check is proven by injecting a deliberate violation into a temporary
tree and asserting the scanner returns it. Every detected *form* has its own
firing proof, and every near-miss the detector must stay silent on (a POSIX
``/dev/tty`` device node, a ``devengada`` Spanish stem, another tree's ``dev``
directory, a bare word ``dev``) has its own silence proof -- a firing proof
alone cannot show the difference between a precise detector and one that fires
on everything. A vacuity floor asserts the live scan visited a realistic
number of src modules so an empty-scan false-pass can never read as a clean
tree.

The former shipped-only scope of Families 5/6 was widened by ruling: a planted
test-named module importing ``dev.*`` must now FIRE, because the ruling is
awareness, not installed-user breakage. That flip has its own regression proof
below.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from cadrumo.core import scan_directory
from dev._paths import REPO_ROOT
from dev.quality.import_hygiene_scan import (
    DevPathForm,
    find_dev_path_reach_violations,
    find_dev_prose_violations,
    find_dev_tooling_import_violations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# ---------------------------------------------------------------------------
# Repo layout constants
# ---------------------------------------------------------------------------

_SRC_ROOT: Final[Path] = REPO_ROOT / "src"
_PKG_ROOT: Final[Path] = _SRC_ROOT / "cadrumo"
_HARNESS_ROOT: Final[Path] = _SRC_ROOT / "cadrumo-harness" / "src"

_UTF_8: Final[str] = "utf-8"

# The boundary sweep must visit at least this many modules before a hard-zero
# result is accepted. Keeps an accidental empty-scan from reading as clean.
_VACUITY_FLOOR: Final[int] = 4000


# ---------------------------------------------------------------------------
# Live-tree inputs
# ---------------------------------------------------------------------------


def _live_boundary_files() -> list[Path]:
    """Return every ``.py`` module under ``src/``, both distributions included."""
    files = list(scan_directory(_PKG_ROOT, pattern="*.py", recursive=True, prune_directories=("__pycache__",)))
    if _HARNESS_ROOT.is_dir():
        files += scan_directory(_HARNESS_ROOT, pattern="*.py", recursive=True, prune_directories=("__pycache__",))
    return files


def _assert_not_vacuous(files: list[Path]) -> None:
    assert len(files) >= _VACUITY_FLOOR, (
        f"vacuity check: fewer than {_VACUITY_FLOOR} modules were found under {_SRC_ROOT}; "
        "a hard-zero result from a collapsed scan reads as clean without being one"
    )


# ---------------------------------------------------------------------------
# Planted-module helpers
# ---------------------------------------------------------------------------


def _planted_module(root: Path, rel: str, body: str) -> Path:
    """Write ``body`` at ``root/rel`` and return the path."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding=_UTF_8)
    return path


def _planted_files(root: Path, *rels: str) -> list[Path]:
    return [root / rel for rel in rels]


# ---------------------------------------------------------------------------
# Hard-zero live assertions
# ---------------------------------------------------------------------------


def test_no_src_module_imports_dev_tooling() -> None:
    """Every module under ``src/`` -- shipped, test, harness alike -- imports nothing from dev."""
    files = _live_boundary_files()
    _assert_not_vacuous(files)
    offenders = find_dev_tooling_import_violations(files, src_root=_SRC_ROOT)
    assert offenders == [], (
        "modules under src/ import the dev tree (absolute boundary, tests included):\n"
        + "\n".join(f"  {v.importer_path}:{v.lineno} -> {v.target_mod}" for v in offenders)
    )


def test_no_src_module_reaches_a_dev_path() -> None:
    """Every module under ``src/`` is free of constructed paths into the dev tree."""
    files = _live_boundary_files()
    _assert_not_vacuous(files)
    offenders = find_dev_path_reach_violations(files, src_root=_SRC_ROOT)
    assert offenders == [], (
        "modules under src/ build paths into the dev tree (absolute boundary):\n"
        + "\n".join(f"  [{v.form}] {v.module_path}:{v.lineno} -> {v.detail!r}" for v in offenders)
    )


def test_no_src_prose_names_the_dev_tree() -> None:
    """No comment, docstring or multi-line string under ``src/`` names the dev tree."""
    files = _live_boundary_files()
    _assert_not_vacuous(files)
    offenders = find_dev_prose_violations(files, src_root=_SRC_ROOT)
    assert offenders == [], (
        "prose under src/ names the dev tree (absolute boundary: awareness in any form):\n"
        + "\n".join(f"  [{v.source_kind}] {v.module_path}:{v.lineno} -> {v.detail!r}" for v in offenders)
    )


# ---------------------------------------------------------------------------
# Family 5 firing proofs
# ---------------------------------------------------------------------------


def test_import_scanner_catches_planted_static_dev_import(tmp_path: Path) -> None:
    path = _planted_module(tmp_path, "cadrumo/core/_planted.py", "import dev.quality.import_hygiene_scan\n")
    violations = find_dev_tooling_import_violations([path], src_root=tmp_path)
    assert [v.target_mod for v in violations] == ["dev.quality.import_hygiene_scan"]
    assert violations[0].is_dynamic is False


def test_import_scanner_catches_planted_test_module_dev_import(tmp_path: Path) -> None:
    """The ruling flip: a wheel-excluded TEST module importing dev is a violation too."""
    path = _planted_module(tmp_path, "cadrumo/tests/test_planted.py", "from dev.locales import LocaleManager\n")
    violations = find_dev_tooling_import_violations([path], src_root=tmp_path)
    assert [v.target_mod for v in violations] == ["dev.locales"]


def test_import_scanner_catches_planted_dynamic_dev_import(tmp_path: Path) -> None:
    path = _planted_module(
        tmp_path,
        "cadrumo/core/_planted.py",
        "import importlib\nimportlib.import_module('dev.quality.import_hygiene_scan')\n",
    )
    violations = find_dev_tooling_import_violations([path], src_root=tmp_path)
    assert [v.target_mod for v in violations] == ["dev.quality.import_hygiene_scan"]
    assert violations[0].is_dynamic is True


def test_import_scanner_does_not_fire_on_cadrumo_import(tmp_path: Path) -> None:
    path = _planted_module(tmp_path, "cadrumo/core/_planted.py", "from cadrumo.core import Period\n")
    violations = find_dev_tooling_import_violations([path], src_root=tmp_path)
    assert violations == [], f"the import scanner fired on a legitimate cadrumo.* import: {violations!r}"


# ---------------------------------------------------------------------------
# Family 6 firing proofs
# ---------------------------------------------------------------------------


def test_path_scanner_catches_planted_dev_path_literal(tmp_path: Path) -> None:
    path = _planted_module(
        tmp_path, "cadrumo/core/_planted.py", 'BASELINE = "dev/quality/import_hygiene_baseline.json"\n'
    )
    violations = find_dev_path_reach_violations([path], src_root=tmp_path)
    assert [(v.form, v.detail) for v in violations] == [
        (DevPathForm.LITERAL, "dev/quality/import_hygiene_baseline.json")
    ]


def test_path_scanner_catches_relative_and_windows_separator_forms(tmp_path: Path) -> None:
    path = _planted_module(
        tmp_path,
        "cadrumo/core/_planted.py",
        r'A = "./dev/some_config.json"' '\n' r'B = "..\dev\other.json"' '\n',
    )
    violations = find_dev_path_reach_violations([path], src_root=tmp_path)
    details = [v.detail for v in violations]
    assert "./dev/some_config.json" in details
    assert "..\\dev\\other.json" in details


def test_path_scanner_catches_project_root_anchored_join(tmp_path: Path) -> None:
    path = _planted_module(
        tmp_path, "cadrumo/core/_planted.py", 'from pathlib import Path\nX = Path(root) / "dev" / "baseline.json"\n'
    )
    violations = find_dev_path_reach_violations([path], src_root=tmp_path)
    assert any(v.form is DevPathForm.PATH_JOIN for v in violations)


def test_path_scanner_catches_the_reversed_join_operand(tmp_path: Path) -> None:
    path = _planted_module(
        tmp_path, "cadrumo/core/_planted.py", 'from pathlib import Path\nX = "dev" / root\n'
    )
    violations = find_dev_path_reach_violations([path], src_root=tmp_path)
    assert any(v.form is DevPathForm.PATH_JOIN for v in violations)


def test_path_scanner_catches_call_assembled_dev_segment(tmp_path: Path) -> None:
    path = _planted_module(
        tmp_path, "cadrumo/core/_planted.py", 'import os\nX = os.path.join(root, "dev", "x.json")\n'
    )
    violations = find_dev_path_reach_violations([path], src_root=tmp_path)
    assert any(v.form is DevPathForm.CALL_JOIN for v in violations)


def test_path_scanner_catches_fstring_composed_dev_path(tmp_path: Path) -> None:
    path = _planted_module(
        tmp_path, "cadrumo/core/_planted.py", 'X = f"{root}/dev/conformance_baseline.json"\n'
    )
    violations = find_dev_path_reach_violations([path], src_root=tmp_path)
    assert any(v.form is DevPathForm.FSTRING for v in violations)


def test_path_scanner_does_not_fire_on_posix_device_paths(tmp_path: Path) -> None:
    path = _planted_module(
        tmp_path, "cadrumo/core/_planted.py", 'import sys\nT = "CONOUT$" if sys.platform == "win32" else "/dev/tty"\n'
    )
    violations = find_dev_path_reach_violations([path], src_root=tmp_path)
    assert violations == [], f"the scanner fired on a POSIX device path, which is not the dev tree: {violations!r}"


def test_path_scanner_does_not_fire_on_an_fstring_device_path(tmp_path: Path) -> None:
    path = _planted_module(tmp_path, "cadrumo/core/_planted.py", 'N = f"/dev/null"\n')
    violations = find_dev_path_reach_violations([path], src_root=tmp_path)
    assert violations == [], f"the scanner fired on an f-string POSIX device path: {violations!r}"


def test_path_scanner_does_not_fire_on_a_mid_path_dev_segment_after_an_interpolation(
    tmp_path: Path,
) -> None:
    path = _planted_module(
        tmp_path, "cadrumo/core/_planted.py", 'X = f"{root}-sandbox/dev/notes.json"\n'
    )
    violations = find_dev_path_reach_violations([path], src_root=tmp_path)
    assert violations == [], f"another tree's dev directory must stay silent: {violations!r}"


def test_path_scanner_does_not_fire_on_a_bare_dev_word(tmp_path: Path) -> None:
    path = _planted_module(tmp_path, "cadrumo/core/_planted.py", 'NAME = "dev"\n')
    violations = find_dev_path_reach_violations([path], src_root=tmp_path)
    assert violations == [], f"a bare 'dev' string carries no path identity: {violations!r}"


# ---------------------------------------------------------------------------
# Family 10 firing and silence proofs
# ---------------------------------------------------------------------------


def test_prose_scanner_catches_a_comment_naming_the_dev_tree(tmp_path: Path) -> None:
    path = _planted_module(
        tmp_path,
        "cadrumo/core/_planted.py",
        "# Reads dev/quality/import_hygiene_baseline.json at scan time.\nX = 1\n",
    )
    violations = find_dev_prose_violations([path], src_root=tmp_path)
    assert [v.source_kind for v in violations] == ["comment"]


def test_prose_scanner_catches_a_docstring_naming_the_dev_tree(tmp_path: Path) -> None:
    path = _planted_module(
        tmp_path,
        "cadrumo/core/_planted.py",
        '"""Loads dev/quality/import_hygiene_baseline.json.\n\nRendered at startup.\n"""\nX = 1\n',
    )
    violations = find_dev_prose_violations([path], src_root=tmp_path)
    assert [v.source_kind for v in violations] == ["string"]


def test_prose_scanner_catches_a_one_line_docstring_naming_the_dev_tree(tmp_path: Path) -> None:
    path = _planted_module(
        tmp_path,
        "cadrumo/core/_planted.py",
        '"""Wraps dev.locales manager."""\nX = 1\n',
    )
    violations = find_dev_prose_violations([path], src_root=tmp_path)
    assert [v.source_kind for v in violations] == ["string"]


def test_prose_scanner_catches_a_multiline_non_docstring_naming_the_dev_tree(tmp_path: Path) -> None:
    path = _planted_module(
        tmp_path,
        "cadrumo/core/_planted.py",
        'MESSAGE = """Falls back to dev/audit/size_budget_baseline.json\nwhen absent."""\n',
    )
    violations = find_dev_prose_violations([path], src_root=tmp_path)
    assert [v.source_kind for v in violations] == ["string"]


def test_prose_scanner_stays_silent_on_device_paths(tmp_path: Path) -> None:
    path = _planted_module(
        tmp_path,
        "cadrumo/core/_planted.py",
        '"""Opens /dev/tty to read a secret without echo, and /dev/null as a sink."""\n',
    )
    violations = find_dev_prose_violations([path], src_root=tmp_path)
    assert violations == [], f"POSIX device nodes are not the dev tree: {violations!r}"


def test_prose_scanner_stays_silent_on_near_miss_words(tmp_path: Path) -> None:
    path = _planted_module(
        tmp_path,
        "cadrumo/core/_planted.py",
        '# A devengada stem, a bare word dev, and dev.example.com stay silent.\n',
    )
    violations = find_dev_prose_violations([path], src_root=tmp_path)
    assert violations == [], f"near-miss prose must stay silent: {violations!r}"


def test_prose_scanner_stays_silent_on_another_trees_dev_directory(tmp_path: Path) -> None:
    path = _planted_module(
        tmp_path,
        "cadrumo/core/_planted.py",
        "# Names -sandbox/dev/notes.json, another tree's dev directory.\n",
    )
    violations = find_dev_prose_violations([path], src_root=tmp_path)
    assert violations == [], f"a mid-path dev segment in another tree must stay silent: {violations!r}"


def test_prose_scanner_stays_silent_on_plain_prose(tmp_path: Path) -> None:
    path = _planted_module(
        tmp_path,
        "cadrumo/core/_planted.py",
        '"""Derives the filing period from year and code."""\n',
    )
    violations = find_dev_prose_violations([path], src_root=tmp_path)
    assert violations == [], f"plain prose must stay silent: {violations!r}"
