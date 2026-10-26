"""Action-spine coverage for modelo verification findings."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core.directory_scan import scan_directory
from ....core.operator_action_enums import OperatorActionAxis
from ..verification_report import (
    OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND,
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SRC_CADRUMO = Path(__file__).resolve().parents[3]


def _constructor_finding_kinds(source: str, *, filename: str) -> set[str]:
    """Return literal kinds passed to imported finding-constructor calls."""
    tree = ast.parse(source, filename=filename)
    constructor_name = ModeloVerificationFinding.__name__
    enum_name = ModeloVerificationFindingKind.__name__
    constructor_aliases: set[str] = set()
    enum_aliases: set[str] = set()
    module_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound_name = alias.asname or alias.name
                if alias.name == constructor_name:
                    constructor_aliases.add(bound_name)
                elif alias.name == enum_name:
                    enum_aliases.add(bound_name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname is not None and alias.name.endswith("domain.modelos"):
                    module_aliases.add(alias.asname)

    consumed: set[str] = set()
    known_members = ModeloVerificationFindingKind.__members__
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        direct_constructor = isinstance(node.func, ast.Name) and node.func.id in constructor_aliases
        qualified_constructor = (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == constructor_name
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in module_aliases
        )
        if not direct_constructor and not qualified_constructor:
            continue
        kind_keywords = [keyword.value for keyword in node.keywords if keyword.arg == "kind"]
        assert len(kind_keywords) == 1, f"{filename}:{node.lineno}: finding constructor must declare one kind="
        kind = kind_keywords[0]
        assert isinstance(kind, ast.Attribute) and isinstance(kind.value, ast.Name) and kind.value.id in enum_aliases, (
            f"{filename}:{node.lineno}: finding constructor kind= must be a literal {enum_name} member"
        )
        assert kind.attr in known_members, f"{filename}:{node.lineno}: unrecognised {enum_name}.{kind.attr}"
        consumed.add(kind.attr)
    return consumed


def _production_finding_constructor_kinds() -> set[str]:
    """Return kinds passed only to production finding constructors."""
    consumed: set[str] = set()
    for path in scan_directory(_SRC_CADRUMO, pattern="*.py", recursive=True):
        relative = path.relative_to(_SRC_CADRUMO).as_posix()
        if "/tests/" in f"/{relative}" or relative == "domain/modelos/verification_report.py":
            continue
        consumed.update(_constructor_finding_kinds(path.read_text(encoding="utf-8"), filename=relative))
    return consumed


def test_verification_finding_action_projection_is_total_and_preserves_distinct_remedies() -> None:
    assert set(OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND) == set(ModeloVerificationFindingKind)
    assert set(OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND.values()) <= set(OperatorActionAxis)
    assert (
        OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND[ModeloVerificationFindingKind.RECONCILIATION_MISMATCH]
        is OperatorActionAxis.RESOLVE_VALUE_DIVERGENCE
    )
    assert (
        OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND[
            ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN
        ]
        is OperatorActionAxis.FILE_PRIOR_PERIOD
    )
    assert (
        OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND[ModeloVerificationFindingKind.ADVISORY]
        is OperatorActionAxis.REVIEW_ADVISORY
    )


def test_every_verification_finding_kind_has_a_production_constructor() -> None:
    """A test fixture or total mapping cannot keep a dormant finding kind alive."""
    assert {member.name for member in ModeloVerificationFindingKind} == _production_finding_constructor_kinds()


def test_irrelevant_enum_reference_does_not_count_as_a_constructor() -> None:
    source = """
from cadrumo.domain.modelos import ModeloVerificationFinding, ModeloVerificationFindingKind

if candidate is ModeloVerificationFindingKind.BLOCKING_RULE:
    pass

ModeloVerificationFinding(kind=ModeloVerificationFindingKind.ADVISORY)
"""
    assert _constructor_finding_kinds(source, filename="irrelevant_reference.py") == {"ADVISORY"}
