"""A shared scan is computed once per distinct input, follows its input, and is served immutable."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from pathlib import Path
from types import MappingProxyType

import pytest
from pydantic import BaseModel, ConfigDict

from dev.quality import shared_scan
from dev.quality.shared_scan import (
    SourceSnapshot,
    require_immutable,
    scanner_identity,
    shared_scan_result,
    shared_snapshot_scan_result,
    take_snapshot,
)

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


def test_a_published_result_naming_paths_is_read_back_by_a_later_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "a.py").write_text("x = 1\n", encoding="utf-8")

    def scan() -> tuple[Path, ...]:
        return shared_scan_result(
            "path-scan",
            root=tree,
            inputs=lambda: sorted(tree.glob("*.py")),
            scanner="scanner-a",
            compute=lambda: tuple(sorted(tree.glob("*.py"))),
            cache_root=tmp_path / "cache",
        )

    first = scan()
    monkeypatch.setattr(shared_scan, "_memo", {})

    assert scan() == first == (tree / "a.py",)


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


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    values: tuple[int, ...]


class _ThawedModel(BaseModel):
    values: tuple[int, ...]


@pytest.mark.parametrize(
    ("value", "accepted"),
    [
        ((1, "a", frozenset({Path("p")})), True),
        (MappingProxyType({"k": (1,)}), True),
        (_Lines(MappingProxyType({"a": 1})), True),
        ((1, [2]), False),
        (MappingProxyType({"k": {1}}), False),
        (_Thawed(1), False),
        (_FrozenModel(values=(1,)), True),
        (_ThawedModel(values=(1,)), False),
    ],
)
def test_immutability_is_judged_through_every_nested_value(value: object, *, accepted: bool) -> None:
    if accepted:
        require_immutable(value)
    else:
        with pytest.raises(TypeError):
            require_immutable(value)


def test_a_snapshot_scan_keys_on_the_bytes_it_read_not_a_later_edit(tmp_path: Path) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    source = tree / "a.py"
    source.write_text("x = 1\n", encoding="utf-8")

    def racing(snapshot: SourceSnapshot) -> int:
        source.write_text("x = 1\ny = 2\n", encoding="utf-8")
        return len(snapshot.read_text(source).splitlines())

    def scan(compute: Callable[[SourceSnapshot], int]) -> int:
        return shared_snapshot_scan_result(
            "snapshot-scan",
            root=tree,
            inputs=lambda: sorted(tree.glob("*.py")),
            scanner="scanner-a",
            compute=compute,
            cache_root=tmp_path / "cache",
        )

    assert scan(racing) == 1, "the scan must see the bytes its key names"
    assert scan(lambda snapshot: len(snapshot.read_text(source).splitlines())) == 2
    assert len(list((tmp_path / "cache" / "snapshot-scan").glob("*/result.pickle"))) == 2


def test_an_unreadable_input_is_kept_as_a_refusal_the_scan_can_report(tmp_path: Path) -> None:
    present = tmp_path / "present.py"
    present.write_bytes(b"x = 1\n")
    missing = tmp_path / "missing.py"

    snapshot = take_snapshot([missing, present])

    assert snapshot.paths == (missing, present), "enumeration order survives a refusal"
    assert snapshot.read_text(present) == "x = 1\n"
    with pytest.raises(OSError, match="FileNotFoundError"):
        snapshot.read_bytes(missing)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (("a.py", "b.py"), ("b.py", "a.py")),
        (("a.py", "b.py"), ("a.py", "a.py", "b.py")),
        (("a.py", "missing.py"), ("missing.py", "a.py")),
    ],
)
def test_a_snapshot_scan_distinguishes_the_order_and_multiplicity_of_every_input(
    tmp_path: Path, before: tuple[str, ...], after: tuple[str, ...]
) -> None:
    """Readable and refused paths retain their positions in both memory and disk cache identities."""
    for name in ("a.py", "b.py"):
        (tmp_path / name).write_text(name, encoding="utf-8")
    calls: list[None] = []

    def report(snapshot: SourceSnapshot) -> tuple[tuple[str, str], ...]:
        calls.append(None)
        return tuple(
            (path.name, "unreadable" if path in snapshot.unreadable else snapshot.read_text(path))
            for path in snapshot.paths
        )

    def scan(names: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
        return shared_snapshot_scan_result(
            "ordered-snapshot",
            root=tmp_path,
            inputs=lambda: (tmp_path / name for name in names),
            scanner="ordered-report",
            compute=report,
            cache_root=tmp_path / "cache",
        )

    initial = scan(before)
    assert scan(before) == initial
    changed = scan(after)
    assert changed == tuple((name, "unreadable" if name == "missing.py" else name) for name in after)
    assert len(calls) == 2, "a changed input sequence must compute its own result"
    shared_scan._memo.clear()
    assert scan(before) == initial
    assert scan(after) == changed
    assert len(calls) == 2, "each sequence must also retrieve its own disk artifact"
