"""Action-spine coverage for modelo verification findings."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core import OperatorActionAxis
from .. import (
    OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND,
    ModeloVerificationFindingKind,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SRC_CADRUMO = Path(__file__).resolve().parents[3]


def _production_finding_kind_consumers() -> set[str]:
    """Return finding-kind members referenced by production constructors.

    The owner is excluded because its total action projection names every member
    and therefore cannot prove that a finding kind is ever produced. Test modules
    are excluded for the same reason: a roundtrip fixture is not a producer.
    """
    consumed: set[str] = set()
    for path in sorted(_SRC_CADRUMO.rglob("*.py")):
        relative = path.relative_to(_SRC_CADRUMO).as_posix()
        if "/tests/" in f"/{relative}" or relative == "domain/modelos/_verification_report.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        owner_names = {"ModeloVerificationFindingKind"}
        owner_names.update(
            alias.asname
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
            if alias.name == "ModeloVerificationFindingKind" and alias.asname is not None
        )
        consumed.update(
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in owner_names
        )
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
    assert {member.name for member in ModeloVerificationFindingKind} == _production_finding_kind_consumers()
