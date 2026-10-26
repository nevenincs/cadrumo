"""Detector teeth for live zero-target unconsumed-export coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..unconsumed_export_coverage import UnconsumedExportVerdict, find_unconsumed

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_EXPORTED = '__all__ = ["widget"]\n\n\ndef widget() -> None: ...\n'


def _tree(tmp_path: Path, package: str = "pkg", **modules: str) -> Path:
    root = tmp_path / package
    root.mkdir()
    for name, source in modules.items():
        (root / f"{name}.py").write_text(source, encoding="utf-8")
    return root


def _unused(root: Path, module: str, name: str) -> set[tuple[str, str]]:
    return {(f"{root.name}/{module}.py", name)}


def test_an_exact_unused_export_without_a_production_importer_is_reported(tmp_path: Path) -> None:
    root = _tree(tmp_path, lonely=_EXPORTED)
    assert [
        (finding.path, finding.name) for finding in find_unconsumed((root,), _unused(root, "lonely", "widget"))
    ] == [
        ("pkg/lonely.py", "widget"),
    ]


def test_a_production_importer_consumes_the_export(tmp_path: Path) -> None:
    root = _tree(tmp_path, lonely=_EXPORTED, user="from .lonely import widget\n")
    assert find_unconsumed((root,), _unused(root, "lonely", "widget")) == ()


def test_an_unreadable_module_refuses_to_claim_zero(tmp_path: Path) -> None:
    root = _tree(tmp_path, lonely=_EXPORTED, broken="def nope(:\n")
    with pytest.raises(RuntimeError, match=r"broken\.py"):
        find_unconsumed((root,), _unused(root, "lonely", "widget"))


def test_a_same_named_module_in_another_package_does_not_consume_the_export(tmp_path: Path) -> None:
    root = _tree(tmp_path, lonely=_EXPORTED, user="from other.lonely import widget\n")

    assert [
        (finding.path, finding.name) for finding in find_unconsumed((root,), _unused(root, "lonely", "widget"))
    ] == [("pkg/lonely.py", "widget")]


def test_every_subject_package_is_measured_and_named(tmp_path: Path) -> None:
    """A second subject package's unused export is reported under its own name."""
    first = _tree(tmp_path, lonely=_EXPORTED)
    second = _tree(tmp_path, "runtime", alone=_EXPORTED)
    unused = _unused(first, "lonely", "widget") | _unused(second, "alone", "widget")

    assert [(finding.path, finding.name) for finding in find_unconsumed((first, second), unused)] == [
        ("pkg/lonely.py", "widget"),
        ("runtime/alone.py", "widget"),
    ]


def test_a_sibling_subject_package_consumes_across_the_boundary(tmp_path: Path) -> None:
    """A subject package is also a consumer: its production import clears another package's export."""
    first = _tree(tmp_path, lonely=_EXPORTED)
    second = _tree(tmp_path, "runtime", user="from pkg.lonely import widget\n")

    assert find_unconsumed((first, second), _unused(first, "lonely", "widget")) == ()


def test_a_companion_production_import_counts_but_its_test_import_does_not(tmp_path: Path) -> None:
    root = _tree(tmp_path, lonely=_EXPORTED)
    companion = tmp_path / "client"
    companion.mkdir()
    (companion / "test_user.py").write_text("from pkg.lonely import widget\n", encoding="utf-8")
    unused = _unused(root, "lonely", "widget")
    assert len(find_unconsumed((root,), unused, consumer_roots=(companion,))) == 1

    (companion / "user.py").write_text("from pkg.lonely import widget\n", encoding="utf-8")
    assert find_unconsumed((root,), unused, consumer_roots=(companion,)) == ()


def test_a_consumer_only_root_is_never_a_subject(tmp_path: Path) -> None:
    """An unused export inside a consumer-only root is not this gate's finding."""
    root = _tree(tmp_path, lonely=_EXPORTED, user="from .lonely import widget\n")
    companion = _tree(tmp_path, "client", alone=_EXPORTED)

    assert find_unconsumed((root,), _unused(companion, "alone", "widget"), consumer_roots=(companion,)) == ()


def test_an_unavailable_companion_refuses_to_claim_zero(tmp_path: Path) -> None:
    root = _tree(tmp_path, lonely=_EXPORTED)
    with pytest.raises(RuntimeError, match="consumer root is unavailable"):
        find_unconsumed((root,), _unused(root, "lonely", "widget"), consumer_roots=(tmp_path / "missing",))


def test_the_report_names_every_measured_package_even_when_clean() -> None:
    verdict = UnconsumedExportVerdict((), ("cadrumo", "cadrumo_runtime"))
    assert verdict.report() == "unconsumed-export coverage: no findings (cadrumo=0, cadrumo_runtime=0)"
