"""Real-tool proof that the complexity scan measures one complete population.

Runs the real Radon and Complexipy analyzers over planted trees. All three
detectors must report the same planted hotspots in every root, including files
a detector's own discovery or decoding would have missed; nested definitions
must be scored individually; and a file any detector cannot measure must make
the scan incomplete rather than clean.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from radon.complexity import add_inner_blocks, cc_visit

from ..complexity import IncompleteScanError, cyclomatic_hits, scan_complexity

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

# Hot for all three detectors: cyclomatic rank F, cognitive far above 20, and a
# maintainability index of rank B even with a coding-cookie line added.
_HOT_SOURCE = (
    "def hot(x, y, z):\n    total = 0\n"
    + "".join(
        f"    if x == {i} and y > {i} or z < {i}:\n        total = total * {i} + x - y // {i + 1}\n" for i in range(45)
    )
    + "    return total\n"
)
_ADMITTED = ("pkg/hot.py", "test_runs/hot.py", ".hidden/hot.py", "pkg/bom.py", "pkg/latin.py")
_REFUSED = ("tests/hot.py", "pkg/test_hot.py", "pkg/_test_hot.py", "pkg/conftest.py", "_data/hot.py")

_TWELVE_BRANCHES = "".join(f"{{indent}}if x == {i}:\n{{indent}}    return {i}\n" for i in range(12))
_NESTED_SOURCE = (
    "def outer(x):\n"
    "    def inner(x):\n" + _TWELVE_BRANCHES.format(indent="        ") + "        return -1\n"
    "    return inner(x)\n"
    "\n"
    "class Service:\n"
    "    def handle(self, x):\n"
    "        def branch(x):\n" + _TWELVE_BRANCHES.format(indent="            ") + "            return -1\n"
    "        return branch(x)\n"
    "\n"
    "    class Nested:\n"
    "        def deep(self, x):\n" + _TWELVE_BRANCHES.format(indent="            ") + "            return -1\n"
)


def _plant(root: Path) -> None:
    for relative in (*_ADMITTED, *_REFUSED):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative == "pkg/bom.py":
            path.write_bytes(b"\xef\xbb\xbf" + _HOT_SOURCE.encode("utf-8"))
        elif relative == "pkg/latin.py":
            path.write_bytes(("# -*- coding: latin-1 -*-\n" + _HOT_SOURCE + 'LABEL = "café"\n').encode("latin-1"))
        else:
            path.write_text(_HOT_SOURCE, encoding="utf-8")


def test_all_three_detectors_measure_one_identical_population(tmp_path: Path) -> None:
    """A hidden directory, a BOM, and a coding cookie must not drop a file from any detector."""
    roots = (tmp_path / "product", tmp_path / "harness", tmp_path / "tooling")
    for root in roots:
        _plant(root)

    scan = scan_complexity(roots=tuple(root.as_posix() for root in roots))

    expected = {f"{root.as_posix()}/{relative}" for root in roots for relative in _ADMITTED}
    assert {hit.path for hit in scan.cyclomatic} == expected
    assert {hit.path for hit in scan.maintainability} == expected
    assert {hit.path for hit in scan.cognitive} == expected


def test_closures_and_nested_class_methods_are_scored_individually(tmp_path: Path) -> None:
    """Every nested block is reported once, under its dotted name, without inflating its parent."""
    (tmp_path / "nested.py").write_text(_NESTED_SOURCE, encoding="utf-8")

    scan = scan_complexity(roots=(tmp_path.as_posix(),))

    path = f"{tmp_path.as_posix()}/nested.py"
    assert sorted((hit.path, hit.name, hit.grade, hit.score) for hit in scan.cyclomatic) == [
        (path, "Service.Nested", "C", 14),
        (path, "Service.Nested.deep", "C", 13),
        (path, "Service.handle.branch", "C", 13),
        (path, "outer.inner", "C", 13),
    ]


def test_nested_scores_match_radons_own_closure_flattening() -> None:
    """Radon's flattened closure blocks are an independent oracle for the per-definition scores."""
    oracle = sorted(block.complexity for block in add_inner_blocks(cc_visit(_NESTED_SOURCE)) if block.complexity >= 11)

    assert sorted(hit.score for hit in cyclomatic_hits("nested.py", _NESTED_SOURCE)) == oracle == [13, 13, 13, 14]


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        pytest.param(b"def broken(:\n    pass\n", "radon cyclomatic: SyntaxError", id="syntax-error"),
        pytest.param(b"x = '\xe9'\n", "unreadable source", id="undecodable"),
    ],
)
def test_a_file_no_detector_can_measure_makes_the_scan_incomplete(tmp_path: Path, content: bytes, reason: str) -> None:
    """A partial scan must never read as clean or as a smaller count."""
    (tmp_path / "hot.py").write_text(_HOT_SOURCE, encoding="utf-8")
    broken = tmp_path / "broken.py"
    broken.write_bytes(content)

    with pytest.raises(IncompleteScanError) as caught:
        scan_complexity(roots=(tmp_path.as_posix(),))

    message = str(caught.value)
    assert isinstance(caught.value, RuntimeError)
    assert f"{broken.as_posix()} ({reason}" in message
    assert "hot.py" not in message
