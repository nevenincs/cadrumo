"""Calculation registry recovery facts stay domain-owned and command-free."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .._applicability_modelo202 import Modelo202Modality, modelo_202_modality_from_inputs
from .._errors import RegistryFailureCondition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_PACKAGE = Path(__file__).resolve().parent.parent
_RECOVERY_PROSE_MODULES = (
    "_applicability.py",
    "_applicability_modelo202.py",
    "_queries.py",
    "_snapshot.py",
    "_loader.py",
    "_loader_cache.py",
    "_loader_fingerprints.py",
)
_FORBIDDEN_RECOVERY_FRAGMENTS = (
    "aeat config profile edit",
    "retry after concurrent registry writes settle",
    "before retrying",
    "before requesting a snapshot",
    "before requesting a filing-grade snapshot",
    "run 'aeat app modelo casillas",
    "resolve with an explicit filing year",
)


def _recovery_prose_fragments(root: Path) -> dict[str, tuple[str, ...]]:
    """Return prohibited recovery strings authored by the scoped domain modules."""
    observed: dict[str, tuple[str, ...]] = {}
    for name in _RECOVERY_PROSE_MODULES:
        source = (root / name).read_text(encoding="utf-8").casefold()
        matches = tuple(fragment for fragment in _FORBIDDEN_RECOVERY_FRAGMENTS if fragment in source)
        if matches:
            observed[name] = matches
    return observed


def test_recovery_prose_domain_roster_is_command_free() -> None:
    """The domain records conditions/facts; application and CLI own recovery projection."""
    assert _recovery_prose_fragments(_REGISTRY_PACKAGE) == {}


@pytest.mark.parametrize("fragment", _FORBIDDEN_RECOVERY_FRAGMENTS)
def test_recovery_prose_scan_rejects_each_reintroduced_directive(tmp_path: Path, fragment: str) -> None:
    """Mutation proof: none of the exact retired directives can evade the census."""
    for name in _RECOVERY_PROSE_MODULES:
        (tmp_path / name).write_text("pass\n", encoding="utf-8")
    (tmp_path / "_queries.py").write_text(f"directive = {fragment!r}\n", encoding="utf-8")

    with pytest.raises(AssertionError):
        assert _recovery_prose_fragments(tmp_path) == {}


def test_modelo_202_missing_incn_exposes_domain_facts_without_a_command() -> None:
    """The calculation rule keeps the missing fact while withholding action policy."""
    from ....deadlines import EntityType

    verdict = modelo_202_modality_from_inputs(
        entity_type=EntityType.LEGAL_ENTITY,
        incn_prior_12_months=None,
    )

    assert verdict.modality is Modelo202Modality.INCOMPLETE
    assert verdict.failure is not None
    assert verdict.failure.condition is RegistryFailureCondition.MODELO_202_INCN_DECLARED
    assert verdict.failure.facts == {
        "modelo": "202",
        "incn_prior_12_months_declared": False,
        "entity_type_legal": True,
    }
    assert "aeat" not in verdict.reason.casefold()


def test_domain_registry_modules_do_not_import_application_policy() -> None:
    """The domain classification never crosses inward to application ownership."""
    imports = []
    for name in _RECOVERY_PROSE_MODULES:
        tree = ast.parse((_REGISTRY_PACKAGE / name).read_text(encoding="utf-8"))
        imports.extend(node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))
    assert not any("application" in module for module in imports)
