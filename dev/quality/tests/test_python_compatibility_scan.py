"""Detector-teeth tests for the Python 3.13+ compatibility census."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..python_compatibility_scan import (
    CompatibilityKind,
    scan_paths_for_python_compatibility,
    scan_python_compatibility,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _apis(source: str, *, name: str = "synthetic.py") -> tuple[tuple[str, str], ...]:
    """Return the stable ``(kind, api)`` projection of synthetic findings."""
    findings = scan_python_compatibility(Path(name), source)
    return tuple((finding.kind.value, finding.api) for finding in findings)


def test_removed_module_imports_are_detected_through_aliases() -> None:
    """A removed module remains a defect when imported under a local alias."""
    findings = scan_python_compatibility(
        Path("removed_module.py"),
        "import distutils as legacy_tools\nlegacy_tools.util\n",
    )

    assert findings
    assert all(finding.kind is CompatibilityKind.REMOVED_MODULE for finding in findings)
    assert {finding.api for finding in findings} == {"distutils"}
    assert {finding.lineno for finding in findings} == {1, 2}


def test_removed_and_deprecated_direct_imports_name_the_canonical_api() -> None:
    """Direct imports and calls identify the API rather than the local alias."""
    apis = _apis(
        "from collections import Mapping\n"
        "from importlib.resources import read_text as read_resource\n"
        "read_resource('pkg', 'data.txt')\n"
    )

    assert ("removed_api", "collections.Mapping") in apis
    assert ("deprecated_api", "importlib.resources.read_text") in apis


def test_deprecated_datetime_method_is_resolved_from_module_alias() -> None:
    """A module alias does not hide a deprecated class method."""
    findings = scan_python_compatibility(
        Path("datetime_alias.py"),
        "import datetime as dt\ndt.datetime.utcnow()\n",
    )

    assert [(finding.kind.value, finding.api, finding.lineno) for finding in findings] == [
        ("deprecated_api", "datetime.datetime.utcnow", 2)
    ]


def test_dynamic_import_literal_is_checked_without_importing_the_target() -> None:
    """A literal passed to ``import_module`` must not evade the static census."""
    findings = scan_python_compatibility(
        Path("dynamic.py"),
        "import importlib\nimportlib.import_module('cgi')\n",
    )

    assert [(finding.kind.value, finding.api, finding.lineno) for finding in findings] == [("removed_module", "cgi", 2)]


def test_private_typing_implementation_names_are_not_a_cross_version_contract() -> None:
    """Private typing classes are rejected even when reached through a module alias."""
    findings = scan_python_compatibility(
        Path("private_typing.py"),
        "import typing as typing_module\ntyping_module._GenericAlias\n",
    )

    assert [(finding.kind.value, finding.api, finding.lineno) for finding in findings] == [
        ("private_api", "typing._GenericAlias", 2)
    ]


def test_local_variables_with_removed_module_names_are_not_false_positives() -> None:
    """Only identities established by imports count as standard-library APIs."""
    findings = scan_python_compatibility(
        Path("local_name.py"),
        "chunk = object()\nchunk.write_bytes()\n",
    )

    assert findings == ()


def test_modern_public_apis_and_comments_are_clean() -> None:
    """Modern resource and typing APIs stay clean, including prose mentions."""
    source = """
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import get_args, get_origin

# from distutils import util
description = "import cgi and datetime.datetime.utcnow"
resource = files("pkg")
"""

    assert scan_python_compatibility(Path("modern.py"), source) == ()


def test_syntax_errors_are_attributable_instead_of_silently_skipped() -> None:
    """An AST census cannot certify a file whose source it cannot parse."""
    findings = scan_python_compatibility(Path("broken.py"), "def broken(:\n    pass\n")

    assert len(findings) == 1
    assert findings[0].kind is CompatibilityKind.SCAN_ERROR
    assert findings[0].api == "<syntax>"
    assert findings[0].lineno == 1


def test_path_scan_reports_read_errors_and_keeps_stable_order(tmp_path: Path) -> None:
    """The multi-file API names unreadable input and sorts findings by path."""
    clean = tmp_path / "a_clean.py"
    removed = tmp_path / "b_removed.py"
    clean.write_text("from importlib.resources import files\n", encoding="utf-8")
    removed.write_text("import imp\n", encoding="utf-8")

    findings = scan_paths_for_python_compatibility((removed, clean))

    assert [(finding.path.name, finding.api) for finding in findings] == [("b_removed.py", "imp")]


def test_module_ast_is_valid_for_the_test_source_itself() -> None:
    """Keep the representative fixtures ordinary Python syntax."""
    source = Path(__file__).read_text(encoding="utf-8")
    ast.parse(source, filename=str(__file__))
