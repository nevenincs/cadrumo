"""Detector teeth for live zero-target unreachable-module coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.audit.unreachable_code import scan_unreachable_code
from dev.audit.unreachable_models import ModuleFinding, ModuleReach, UnreachableCodeResult
from dev.audit.unreachable_tree import EntryPoint, OutsideCorpus, ShippedTreeSpec

from ..unreachable_module_coverage import evaluate

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _result(*findings: ModuleFinding) -> UnreachableCodeResult:
    return UnreachableCodeResult.from_findings(
        roots=("pkg.cli:main",),
        shipped_modules=len(findings) + 1,
        reachable_modules=1,
        modules=tuple(findings),
        symbols=(),
    )


@pytest.mark.parametrize("reach", tuple(ModuleReach))
def test_every_non_command_reached_category_stays_red(reach: ModuleReach) -> None:
    finding = ModuleFinding(
        path="src/pkg/stranded.py",
        module="pkg.stranded",
        reach=reach,
        spanned_modules=1,
        used_by=(),
    )

    verdict = evaluate(_result(finding))

    assert not verdict.is_clean
    assert "pkg.stranded" in verdict.report()
    assert reach.value in verdict.report()


def test_an_empty_live_set_is_green() -> None:
    result = UnreachableCodeResult.clean(
        roots=("pkg.cli:main",),
        shipped_modules=1,
        reachable_modules=1,
    )

    verdict = evaluate(result)

    assert verdict.is_clean
    assert verdict.report() == "unreachable-module coverage: no findings"


def _write(root: Path, relative: str, text: str = "") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_a_dev_imported_module_is_in_use_and_a_test_only_module_is_not(tmp_path: Path) -> None:
    """``dev/`` use clears a module and what it imports; in-source and ``dev/`` tests never do."""
    _write(tmp_path, "src/pkg/__init__.py")
    _write(tmp_path, "src/pkg/cli.py", "def main() -> None: ...\n")
    _write(tmp_path, "src/pkg/devonly.py", "from .devhelper import help_\n")
    _write(tmp_path, "src/pkg/devhelper.py", "def help_() -> None: ...\n")
    _write(tmp_path, "src/pkg/testonly.py", "VALUE = 1\n")
    _write(tmp_path, "src/pkg/tests/__init__.py")
    _write(tmp_path, "src/pkg/tests/test_testonly.py", "from pkg.testonly import VALUE\n")
    _write(tmp_path, "dev/tool.py", "import pkg.devonly\n")
    _write(tmp_path, "dev/tests/test_tool.py", "from pkg.testonly import VALUE\n")
    spec = ShippedTreeSpec(
        repo_root=tmp_path,
        src_root=tmp_path / "src",
        packages=("pkg",),
        entry_points=(EntryPoint("pkg.cli", "main"),),
        exclude_globs=("src/pkg/tests", "src/pkg/tests/**"),
        outside=(
            OutsideCorpus(label="tests", root=tmp_path / "src" / "pkg", test_modules_only=True),
            OutsideCorpus(label="dev", root=tmp_path / "dev"),
        ),
    )

    verdict = evaluate(scan_unreachable_code(spec))

    assert [(finding.module, finding.used_by) for finding in verdict.findings] == [("pkg.testonly", ("tests",))]
