"""Evidence for multilingual inventory and the real duplication instrument."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..duplication import DuplicationOutcome, DuplicationResult
from ..native_health import LanguageScope, inventory, scan
from ..report import Status, audit_native_language

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("suffix", "format_name", "line"),
    [
        (".ts", "typescript", "const value{n}: number = input + {n};"),
        (".tsx", "tsx", "const value{n}: number = input + {n};"),
        (".css", "css", ".item{n} {{ padding: {n}px; margin: {n}px; color: red; }}"),
        (".rs", "rust", "let value{n}: i32 = input + {n};"),
    ],
)
def test_real_scanner_finds_copies_and_inventory_excludes_build_output(
    tmp_path: Path, suffix: str, format_name: str, line: str
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    source = "\n".join(line.format(n=n) for n in range(30)) + "\n"
    (root / f"first{suffix}").write_text(source, encoding="utf-8")
    (root / f"second{suffix}").write_text(source, encoding="utf-8")
    if suffix == ".tsx":
        (root / "other.ts").write_text(source, encoding="utf-8")
    ignored = root / "target"
    ignored.mkdir()
    (ignored / f"generated{suffix}").write_text(source, encoding="utf-8")
    suffixes = (".ts", ".tsx") if suffix == ".tsx" else (suffix,)
    scope = LanguageScope(format_name, Path("source"), suffixes, format_name)

    files = inventory(tmp_path, scope)
    result = scan(tmp_path, scope, files)

    expected_count = 3 if suffix == ".tsx" else 2
    assert len(files) == expected_count
    assert result.outcome is DuplicationOutcome.CLONES, result.reason
    assert 2 <= result.files_analyzed <= expected_count
    assert result.raw_groups


def test_missing_or_empty_source_is_unavailable(tmp_path: Path) -> None:
    scope = LanguageScope("rust", Path("source"), (".rs",), "rust")
    assert audit_native_language(tmp_path, scope).available is False
    (tmp_path / "source").mkdir()
    result = audit_native_language(tmp_path, scope)
    assert result.status is Status.AMBER
    assert result.available is False


def test_unexpected_scanner_population_is_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from .. import native_health

    scope = LanguageScope("rust", Path("source"), (".rs",), "rust")
    monkeypatch.setattr(
        native_health, "run_duplication_scan", lambda *args, **kwargs: DuplicationResult.observed_zero(2)
    )
    result = scan(tmp_path, scope, (Path("source/first.rs"),))
    assert result.outcome is DuplicationOutcome.UNAVAILABLE
    assert "inventory has 1 files" in result.reason


def test_partial_scan_keeps_evidence_but_never_reports_green(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from .. import report

    scope = LanguageScope("rust", Path("source"), (".rs",), "rust")
    root = tmp_path / "source"
    root.mkdir()
    (root / "one.rs").write_text("fn one() {}", encoding="utf-8")
    (root / "two.rs").write_text("fn two() {}", encoding="utf-8")
    monkeypatch.setattr(report, "scan", lambda *_args: DuplicationResult.observed_zero(1))
    dimension = audit_native_language(tmp_path, scope)
    assert dimension.status is Status.AMBER
    assert not dimension.available
    assert "2 files inventoried; 1 analysed" in dimension.headline
