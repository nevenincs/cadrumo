"""Registry-coded enum members: cleared only by a code the registry declares."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..unreachable_code import scan_unreachable_code
from ..unreachable_models import UnreachableCodeResult
from ..unreachable_reporting import render_console_report, result_as_json
from ..unreachable_tree import EntryPoint, ShippedTreeSpec

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CODES_BASE = """
from enum import StrEnum


class RegistryCodedEnum(StrEnum):
    @classmethod
    def _form_code_source(cls) -> tuple[str, str]:
        raise NotImplementedError
"""

_CLI = """
from .codes import Level, Plain
from .facts import FACT_ID


def main() -> object:
    return Level.USED, Plain.USED, FACT_ID
"""

_CODES = """
from enum import StrEnum

from .base import RegistryCodedEnum
from .facts import FACT_ID


class Level(RegistryCodedEnum):
    USED = "used"
    DECLARED = "declared"
    UNDECLARED = "undeclared"

    @classmethod
    def _form_code_source(cls) -> tuple[str, str]:
        return FACT_ID, "level"


class Plain(StrEnum):
    USED = "used"
    DECLARED = "declared"
"""

_FACTS = 'FACT_ID = "demo-codes"\n'

_FACT_TOML = """
[fact]
fact_id = "demo-codes"

[[fact.variants]]
variant_id = "demo-codes:design"

[fact.variants.payload]
kind = "mapping"
entries = [
  { key = "level.used", value = "1" },
  { key = "level.declared", value = "2" },
  { key = "plain.declared", value = "3" },
]
"""


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _scan(root: Path, fact_toml: str = _FACT_TOML) -> UnreachableCodeResult:
    _write(root, "src/pkg/__init__.py", "")
    _write(root, "src/pkg/cli.py", _CLI)
    _write(root, "src/pkg/base.py", _CODES_BASE)
    _write(root, "src/pkg/codes.py", _CODES)
    _write(root, "src/pkg/facts.py", _FACTS)
    _write(root, "src/pkg/_data/facts.toml", fact_toml)
    spec = ShippedTreeSpec(
        repo_root=root,
        src_root=root / "src",
        packages=("pkg",),
        entry_points=(EntryPoint("pkg.cli", "main"),),
        data_globs=("_data/**/*.toml",),
    )
    return scan_unreachable_code(spec)


def test_a_declared_member_clears_and_an_undeclared_sibling_stays_reported(tmp_path: Path) -> None:
    result = _scan(tmp_path)

    reported = {finding.qualname for finding in result.symbols}
    assert "Level.DECLARED" not in reported
    assert "Level.UNDECLARED" in reported
    assert result.registry_cleared == 1


def test_a_plain_enum_is_not_cleared_by_a_same_valued_declaration(tmp_path: Path) -> None:
    """``Plain`` is not registry-coded, so a ``plain.declared`` key proves nothing about it."""
    result = _scan(tmp_path)

    assert "Plain.DECLARED" in {finding.qualname for finding in result.symbols}


def test_the_declaration_is_read_live_from_the_registry_source(tmp_path: Path) -> None:
    """Dropping the entry from the fact reports the member again."""
    without = _FACT_TOML.replace('  { key = "level.declared", value = "2" },\n', "")

    result = _scan(tmp_path, without)

    assert "Level.DECLARED" in {finding.qualname for finding in result.symbols}
    assert result.registry_cleared == 0


def test_a_code_declared_under_another_fact_does_not_clear_the_member(tmp_path: Path) -> None:
    other = _FACT_TOML.replace('fact_id = "demo-codes"', 'fact_id = "other-codes"')

    result = _scan(tmp_path, other)

    assert "Level.DECLARED" in {finding.qualname for finding in result.symbols}


def test_the_clearance_is_visible_in_console_and_json(tmp_path: Path) -> None:
    result = _scan(tmp_path)

    assert "1 enum member(s) cleared because the registry declares their form code" in render_console_report(result)
    assert json.loads(result_as_json(result))["registry_cleared"] == 1


def test_the_symbol_section_splits_test_only_from_unreferenced_symbols(tmp_path: Path) -> None:
    _write(tmp_path, "src/pkg/__init__.py", "")
    _write(
        tmp_path,
        "src/pkg/cli.py",
        "def main() -> None: ...\n\n\ndef tested_only() -> None: ...\n\n\ndef nobody() -> None: ...\n",
    )
    _write(tmp_path, "src/pkg/tests/__init__.py", "")
    _write(
        tmp_path,
        "src/pkg/tests/test_cli.py",
        "from ..cli import tested_only\n\n\ndef test_it() -> None:\n    tested_only()\n",
    )
    from ..unreachable_tree import OutsideCorpus

    spec = ShippedTreeSpec(
        repo_root=tmp_path,
        src_root=tmp_path / "src",
        packages=("pkg",),
        entry_points=(EntryPoint("pkg.cli", "main"),),
        exclude_globs=("src/pkg/tests", "src/pkg/tests/**"),
        outside=(OutsideCorpus(label="tests", root=tmp_path / "src" / "pkg", test_modules_only=True),),
    )

    result = scan_unreachable_code(spec)

    payload = json.loads(result_as_json(result))
    assert payload["symbol_use_split"] == {"tests_only": 1, "no_reference": 1, "other_labels": 0}
    assert "1 used only by tests, 1 with no reference anywhere" in render_console_report(result)
