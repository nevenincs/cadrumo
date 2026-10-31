"""A shared scan is computed once per distinct input, follows its input, and is served immutable."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from pathlib import Path
from types import MappingProxyType

import pytest

from dev.quality import shared_scan
from dev.quality.shared_scan import require_immutable, scanner_identity, shared_scan_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@dataclasses.dataclass(frozen=True)
class _Lines:
    by_file: MappingProxyType[str, int]


@pytest.fixture(autouse=True)
def _fresh_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts as a process that has not yet read any scan."""
    monkeypatch.setattr(shared_scan, "_memo", {})


def _line_scan(tree: Path, calls: list[None]) -> Callable[[], _Lines]:
    def compute() -> _Lines:
        calls.append(None)
        counts = {path.name: len(path.read_text(encoding="utf-8").splitlines()) for path in sorted(tree.glob("*.py"))}
        return _Lines(MappingProxyType(counts))

    return compute


def _scan(tree: Path, cache: Path, calls: list[None], *, scanner: str = "scanner-a") -> _Lines:
    return shared_scan_result(
        "line-scan",
        root=tree,
        inputs=lambda: sorted(tree.glob("*.py")),
        scanner=scanner,
        compute=_line_scan(tree, calls),
        cache_root=cache,
    )


def test_an_unchanged_input_is_scanned_once_and_read_by_every_later_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    calls: list[None] = []

    first = _scan(tree, tmp_path / "cache", calls)
    assert _scan(tree, tmp_path / "cache", calls) is first, "one process must share one result object"
    monkeypatch.setattr(shared_scan, "_memo", {})
    reread = _scan(tree, tmp_path / "cache", calls)

    assert len(calls) == 1, "a later process must read the published scan, not repeat it"
    assert reread == first
    assert reread.by_file["a.py"] == 2


def test_changing_a_scanned_file_changes_the_result(tmp_path: Path) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "a.py").write_text("x = 1\n", encoding="utf-8")
    calls: list[None] = []
    before = _scan(tree, tmp_path / "cache", calls)

    (tree / "a.py").write_text("x = 1\ny = 2\nz = 3\n", encoding="utf-8")
    after = _scan(tree, tmp_path / "cache", calls)

    assert (before.by_file["a.py"], after.by_file["a.py"]) == (1, 3)
    assert len(calls) == 2


def test_a_file_outside_the_inclusion_policy_does_not_rescan(tmp_path: Path) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "a.py").write_text("x = 1\n", encoding="utf-8")
    calls: list[None] = []
    _scan(tree, tmp_path / "cache", calls)

    (tree / "notes.txt").write_text("unrelated churn\n", encoding="utf-8")
    _scan(tree, tmp_path / "cache", calls)

    assert len(calls) == 1


def test_a_changed_scanner_rescans_an_unchanged_tree(tmp_path: Path) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "a.py").write_text("x = 1\n", encoding="utf-8")
    calls: list[None] = []

    _scan(tree, tmp_path / "cache", calls, scanner="scanner-a")
    _scan(tree, tmp_path / "cache", calls, scanner="scanner-b")

    assert len(calls) == 2


def test_the_scanner_identity_follows_the_scanner_source() -> None:
    assert scanner_identity(shared_scan) == scanner_identity(shared_scan)
    assert scanner_identity(shared_scan) != scanner_identity(dataclasses)


def test_a_scan_whose_inputs_move_while_it_reads_them_is_not_published(tmp_path: Path) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "a.py").write_text("x = 1\n", encoding="utf-8")

    def racing() -> _Lines:
        (tree / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
        return _Lines(MappingProxyType({"a.py": 1}))

    result = shared_scan_result(
        "line-scan",
        root=tree,
        inputs=lambda: sorted(tree.glob("*.py")),
        scanner="scanner-a",
        compute=racing,
        cache_root=tmp_path / "cache",
    )

    assert result.by_file["a.py"] == 1
    assert not any((tmp_path / "cache" / "line-scan").glob("*/result.pickle"))


def test_a_mutable_result_is_refused_before_it_is_shared(tmp_path: Path) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "a.py").write_text("x = 1\n", encoding="utf-8")

    with pytest.raises(TypeError, match="mutable dict"):
        shared_scan_result(
            "line-scan",
            root=tree,
            inputs=lambda: sorted(tree.glob("*.py")),
            scanner="scanner-a",
            compute=lambda: {"a.py": 1},
            cache_root=tmp_path / "cache",
        )


@dataclasses.dataclass
class _Thawed:
    value: int


@pytest.mark.parametrize(
    ("value", "accepted"),
    [
        ((1, "a", frozenset({Path("p")})), True),
        (MappingProxyType({"k": (1,)}), True),
        (_Lines(MappingProxyType({"a": 1})), True),
        ((1, [2]), False),
        (MappingProxyType({"k": {1}}), False),
        (_Thawed(1), False),
    ],
)
def test_immutability_is_judged_through_every_nested_value(value: object, *, accepted: bool) -> None:
    if accepted:
        require_immutable(value)
    else:
        with pytest.raises(TypeError):
            require_immutable(value)
