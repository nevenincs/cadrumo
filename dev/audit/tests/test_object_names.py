"""Contract tests for the repository object-name audit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..object_names import (
    ObjectNameFindingKind,
    ObjectNameKind,
    analyse,
    declarations_in_source,
    exit_code,
    scan,
    to_json,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write(root: Path, relative: str, source: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_clean_distinct_singular_public_declarations_pass() -> None:
    declarations = declarations_in_source(
        "class Invoice: pass\nclass FilingKind(Enum): pass\ndef load_invoice(): pass\n",
        "src/cadrumo/clean.py",
    )

    result = analyse(declarations)

    assert result.findings == ()
    assert [item.kind for item in declarations] == [
        ObjectNameKind.ENUM,
        ObjectNameKind.CLASS,
        ObjectNameKind.FUNCTION,
    ]


def test_duplicate_public_name_across_kinds_and_modules_fails() -> None:
    left = declarations_in_source("class Verdict: pass\n", "src/cadrumo/left.py")
    right = declarations_in_source("def Verdict(): pass\n", "dev/right.py")

    result = analyse(left + right)

    finding = result.enforced_findings[0]
    assert finding.kind is ObjectNameFindingKind.DUPLICATE
    assert finding.name == "Verdict"
    assert finding.sites == (
        "dev/right.py:1 (function)",
        "src/cadrumo/left.py:1 (class)",
    )


def test_duplicate_private_and_test_names_are_advisory() -> None:
    private = declarations_in_source("def _seed(): pass\n", "dev/one.py")
    test = declarations_in_source("def _seed(): pass\n", "dev/tests/test_two.py", test=True)

    result = analyse(private + test)

    assert len(result.findings) == 1
    assert result.findings[0].enforced is False
    assert result.enforced_findings == ()


def test_one_public_declaration_and_one_test_double_are_advisory() -> None:
    public = declarations_in_source("class Invoice: pass\n", "src/cadrumo/invoice.py")
    test = declarations_in_source("class Invoice: pass\n", "src/cadrumo/tests/test_invoice.py", test=True)

    result = analyse(public + test)

    assert len(result.findings) == 1
    assert result.findings[0].enforced is False


def test_overloads_in_one_module_are_one_object_name() -> None:
    declarations = declarations_in_source(
        "from typing import overload\n"
        "@overload\ndef coerce(value: str): ...\n"
        "@overload\ndef coerce(value: int): ...\n"
        "def coerce(value): ...\n",
        "src/cadrumo/coercion.py",
    )

    assert analyse(declarations).findings == ()
    assert {item.binding_occurrence for item in declarations} == {1}


def test_same_module_redeclaration_is_not_mistaken_for_an_overload() -> None:
    declarations = declarations_in_source(
        "class Invoice: pass\nclass Invoice: pass\n",
        "src/cadrumo/invoice.py",
    )

    result = analyse(declarations)

    assert len(result.enforced_findings) == 1
    assert len(result.enforced_findings[0].sites) == 2
    assert result.enforced_findings[0].qualified_sites == (
        "class:cadrumo.invoice.Invoice#binding=1",
        "class:cadrumo.invoice.Invoice#binding=2",
    )


def test_conditional_module_declarations_are_enrolled() -> None:
    declarations = declarations_in_source(
        "if WINDOWS:\n    class Backend: pass\nelse:\n    class Backend: pass\n",
        "src/cadrumo/backend.py",
    )

    result = analyse(declarations)

    assert len(declarations) == 2
    assert len(result.enforced_findings) == 1


def test_methods_nested_functions_and_main_are_not_collisions() -> None:
    left = declarations_in_source(
        "class Left:\n    def load(self): pass\ndef outer():\n    def nested(): pass\ndef main(): pass\n",
        "src/cadrumo/left.py",
    )
    right = declarations_in_source(
        "class Right:\n    def load(self): pass\ndef main(): pass\n",
        "dev/right.py",
    )

    assert analyse(left + right).findings == ()


@pytest.mark.parametrize(
    ("source", "name"),
    [
        ("class Invoices: pass\n", "Invoices"),
        ("class FilingKinds(Enum): pass\n", "FilingKinds"),
        ("def transactions(): pass\n", "transactions"),
    ],
)
def test_plural_looking_public_declarations_fail(source: str, name: str) -> None:
    result = analyse(declarations_in_source(source, "src/cadrumo/plural.py"))

    assert [(finding.kind, finding.name) for finding in result.enforced_findings] == [
        (ObjectNameFindingKind.PLURAL, name)
    ]


def test_action_function_and_non_plural_s_suffix_are_not_flagged() -> None:
    declarations = declarations_in_source(
        "def load_transactions(): pass\ndef exists(): pass\ndef requires(): pass\n"
        "class FilingStatus: pass\nclass Corpus: pass\nclass TermAlias: pass\n"
        "class TransportLocus: pass\nclass OrthogonalAxis: pass\n",
        "src/cadrumo/accepted.py",
    )

    assert analyse(declarations).findings == ()


def test_async_module_function_is_enrolled() -> None:
    declarations = declarations_in_source("async def fetch_invoice(): pass\n", "src/cadrumo/async_io.py")

    assert len(declarations) == 1
    assert declarations[0].kind is ObjectNameKind.FUNCTION


def test_scan_enrols_src_and_dev_and_fails_closed_on_syntax_error(tmp_path: Path) -> None:
    _write(tmp_path, "src/cadrumo/one.py", "class Invoice: pass\n")
    _write(tmp_path, "dev/two.py", "class Invoice: pass\n")
    _write(tmp_path, "dev/broken.py", "def broken(:\n")

    result = scan((tmp_path / "src", tmp_path / "dev"), tmp_path)

    assert {item.path for item in result.declarations} == {
        "dev/broken.py",
        "dev/two.py",
        "src/cadrumo/one.py",
    }
    assert sum(item.kind is ObjectNameKind.MODULE for item in result.declarations) == 3
    assert {finding.kind for finding in result.enforced_findings} == {
        ObjectNameFindingKind.DUPLICATE,
        ObjectNameFindingKind.SOURCE_ERROR,
    }


def test_duplicate_public_module_stems_fail(tmp_path: Path) -> None:
    _write(tmp_path, "src/cadrumo/invoice.py", "")
    _write(tmp_path, "dev/export/invoice.py", "")

    result = scan((tmp_path / "src", tmp_path / "dev"), tmp_path)

    finding = next(item for item in result.enforced_findings if item.name == "invoice")
    assert finding.kind is ObjectNameFindingKind.DUPLICATE
    assert finding.sites == (
        "dev/export/invoice.py:1 (module)",
        "src/cadrumo/invoice.py:1 (module)",
    )


def test_main_function_exemption_does_not_hide_main_modules(tmp_path: Path) -> None:
    _write(tmp_path, "src/cadrumo/main.py", "def main(): pass\n")
    _write(tmp_path, "dev/tool/main.py", "def main(): pass\n")

    result = scan((tmp_path / "src", tmp_path / "dev"), tmp_path)

    finding = next(item for item in result.enforced_findings if item.name == "main")
    assert finding.sites == (
        "dev/tool/main.py:1 (module)",
        "src/cadrumo/main.py:1 (module)",
    )


def test_main_function_exemption_does_not_hide_module_object_collision(tmp_path: Path) -> None:
    _write(tmp_path, "src/cadrumo/main.py", "class main: pass\n")
    (tmp_path / "dev").mkdir()

    result = scan((tmp_path / "src", tmp_path / "dev"), tmp_path)

    finding = next(item for item in result.enforced_findings if item.name == "main")
    assert finding.sites == (
        "src/cadrumo/main.py:1 (class)",
        "src/cadrumo/main.py:1 (module)",
    )


def test_plural_public_module_stem_fails(tmp_path: Path) -> None:
    _write(tmp_path, "src/cadrumo/invoices.py", "")
    (tmp_path / "dev").mkdir()

    result = scan((tmp_path / "src", tmp_path / "dev"), tmp_path)

    assert any(
        item.kind is ObjectNameFindingKind.PLURAL and item.name == "invoices" for item in result.enforced_findings
    )


def test_plural_module_holding_several_declarations_is_accurate(tmp_path: Path) -> None:
    """A module named for what it contains is named correctly, not defectively.

    ``errors.py`` holding eleven error classes is the ordinary Python
    convention, and renaming it to ``error.py`` would make the name lie in the
    other direction. A class promises one instance and so cannot be plural; a
    module is a namespace and can be.
    """
    _write(
        tmp_path,
        "src/cadrumo/errors.py",
        "class ParseError(Exception):\n    pass\n\n\nclass WriteError(Exception):\n    pass\n",
    )
    (tmp_path / "dev").mkdir()

    result = scan((tmp_path / "src", tmp_path / "dev"), tmp_path)

    assert not any(
        item.kind is ObjectNameFindingKind.PLURAL and item.name == "errors" for item in result.enforced_findings
    )


def test_plural_module_holding_one_declaration_still_fails(tmp_path: Path) -> None:
    """The exemption is about accuracy, so a single-occupant plural still lies."""
    _write(tmp_path, "src/cadrumo/invoices.py", "class Invoice:\n    pass\n")
    (tmp_path / "dev").mkdir()

    result = scan((tmp_path / "src", tmp_path / "dev"), tmp_path)

    assert any(
        item.kind is ObjectNameFindingKind.PLURAL and item.name == "invoices" for item in result.enforced_findings
    )


def test_private_and_test_module_stems_are_advisory(tmp_path: Path) -> None:
    _write(tmp_path, "src/cadrumo/_support.py", "")
    _write(tmp_path, "dev/tests/_support.py", "")

    result = scan((tmp_path / "src", tmp_path / "dev"), tmp_path)

    finding = next(item for item in result.findings if item.name == "_support")
    assert finding.enforced is False


def test_scan_fails_closed_when_a_required_root_is_missing(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()

    result = scan((tmp_path / "src", tmp_path / "dev"), tmp_path)

    assert [(finding.kind, finding.name) for finding in result.enforced_findings] == [
        (ObjectNameFindingKind.SOURCE_ERROR, "dev")
    ]


def test_exit_code_fails_only_for_enforced_findings() -> None:
    clean = analyse(declarations_in_source("class Invoice: pass\n", "src/cadrumo/invoice.py"))
    advisory = analyse(
        declarations_in_source("class Invoice: pass\n", "dev/tests/test_one.py", test=True)
        + declarations_in_source("class Invoice: pass\n", "dev/tests/test_two.py", test=True)
    )
    failing = analyse(
        declarations_in_source("class Invoice: pass\n", "src/cadrumo/one.py")
        + declarations_in_source("class Invoice: pass\n", "dev/two.py")
    )

    assert exit_code(clean) == 0
    assert exit_code(advisory) == 0
    assert exit_code(failing) == 1


def test_json_is_deterministic_and_contains_every_site() -> None:
    declarations = declarations_in_source("class Invoice: pass\n", "src/cadrumo/z.py") + declarations_in_source(
        "class Invoice: pass\n", "dev/a.py"
    )

    first = json.dumps(to_json(analyse(declarations)), sort_keys=True)
    second = json.dumps(to_json(analyse(tuple(reversed(declarations)))), sort_keys=True)

    assert first == second
    payload = json.loads(first)
    assert payload["summary"]["enforced_findings"] == 1
    assert len(payload["findings"][0]["sites"]) == 2


def test_inventory_serialises_complete_module_and_symbol_records(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/cadrumo/invoice.py",
        "from enum import StrEnum\n"
        "class Invoice: pass\n"
        "class FilingKind(StrEnum):\n    ORIGINAL = 'original'\n"
        "def load_invoice(): pass\n"
        "async def fetch_invoice(): pass\n",
    )
    (tmp_path / "dev").mkdir()

    payload = to_json(scan((tmp_path / "src", tmp_path / "dev"), tmp_path))
    records = {record["qualified_locator"]: record for record in payload["declarations"]}

    assert set(records) == {
        "module:cadrumo.invoice#binding=1",
        "class:cadrumo.invoice.Invoice#binding=1",
        "enum:cadrumo.invoice.FilingKind#binding=1",
        "function:cadrumo.invoice.load_invoice#binding=1",
        "function:cadrumo.invoice.fetch_invoice#binding=1",
    }
    expected_identity = {
        "module:cadrumo.invoice#binding=1": ("invoice", "module", 1),
        "class:cadrumo.invoice.Invoice#binding=1": ("Invoice", "class", 2),
        "enum:cadrumo.invoice.FilingKind#binding=1": ("FilingKind", "enum", 3),
        "function:cadrumo.invoice.load_invoice#binding=1": ("load_invoice", "function", 5),
        "function:cadrumo.invoice.fetch_invoice#binding=1": ("fetch_invoice", "function", 6),
    }
    for locator, record in records.items():
        name, kind, line = expected_identity[locator]
        assert set(record) == {
            "binding_occurrence",
            "kind",
            "line",
            "name",
            "overload",
            "path",
            "public",
            "qualified_locator",
            "source_hash",
            "test",
        }
        assert record == {
            "binding_occurrence": 1,
            "kind": kind,
            "line": line,
            "name": name,
            "overload": False,
            "path": "src/cadrumo/invoice.py",
            "public": True,
            "qualified_locator": locator,
            "source_hash": record["source_hash"],
            "test": False,
        }
        assert record["source_hash"].startswith("sha256:")
    assert payload["schema_version"] == 1
    assert payload["inventory_digest"].startswith("sha256:")


def test_inventory_is_repeatable_and_raw_byte_drift_changes_only_execution_identity(tmp_path: Path) -> None:
    left = "class Invoice: pass\n"
    _write(tmp_path, "src/cadrumo/left.py", left)
    _write(tmp_path, "dev/right.py", left)

    first = to_json(scan((tmp_path / "src", tmp_path / "dev"), tmp_path))
    repeated = to_json(scan((tmp_path / "src", tmp_path / "dev"), tmp_path))

    assert repeated == first
    duplicate_before = next(finding for finding in first["findings"] if finding["name"] == "Invoice")
    left_before = next(record for record in first["declarations"] if record["path"] == "src/cadrumo/left.py")

    _write(tmp_path, "src/cadrumo/left.py", left + "# unrelated trailing bytes\n")
    drifted = to_json(scan((tmp_path / "src", tmp_path / "dev"), tmp_path))
    duplicate_after = next(finding for finding in drifted["findings"] if finding["name"] == "Invoice")
    left_after = next(record for record in drifted["declarations"] if record["path"] == "src/cadrumo/left.py")

    assert left_after["source_hash"] != left_before["source_hash"]
    assert drifted["inventory_digest"] != first["inventory_digest"]
    assert duplicate_after["id"] == duplicate_before["id"]
    assert duplicate_after["sites"] == duplicate_before["sites"]
    assert duplicate_after["qualified_sites"] == duplicate_before["qualified_sites"]
