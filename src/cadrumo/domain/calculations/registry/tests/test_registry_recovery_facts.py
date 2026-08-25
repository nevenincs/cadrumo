"""Calculation registry recovery facts stay domain-owned and command-free."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .....core.resources import resources
from .._applicability_modelo202 import Modelo202Modality, modelo_202_modality_from_inputs
from ..errors import RegistryFailureCondition, RegistryValidationError
from ..queries import RegistryQueryService, _casilla_detail_report
from ..snapshot import _check_snapshot_filing_capability

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


def test_unknown_casilla_exposes_exact_domain_facts_without_a_list_command() -> None:
    """The query records the absent declaration; it does not direct the operator."""
    authority = resources().modelos.authority
    context = RegistryQueryService(authority)._resolve_revision("303", period="1T", as_of=None)

    with pytest.raises(RegistryValidationError) as caught:
        _casilla_detail_report(context, "not-a-casilla")

    failure = caught.value.registry_failure
    assert failure is not None
    assert failure.condition is RegistryFailureCondition.QUERY_CASILLA_DECLARED
    assert failure.facts == {
        "modelo": str(context.definition.id),
        "revision": str(context.revision.id),
        "casilla": "not-a-casilla",
        "casilla_declared": False,
    }


def test_missing_export_layout_exposes_exact_domain_facts_without_a_layout_directive() -> None:
    """A filing capability refusal names only the observed layout facts."""
    modelo = resources().modelos.authority.modelo("182")
    revision = modelo.revisions["2025"]
    assert not revision.export_layouts, "fixture drift: select a layoutless revision"

    with pytest.raises(RegistryValidationError) as caught:
        _check_snapshot_filing_capability(modelo, revision)

    failure = caught.value.registry_failure
    assert failure is not None
    assert failure.condition is RegistryFailureCondition.SNAPSHOT_EXPORT_LAYOUT_DECLARED
    assert failure.facts == {
        "modelo": str(modelo.id),
        "revision": str(revision.id),
        "export_layout_declared": False,
        "filing_artifact_supported": False,
    }


def test_domain_registry_modules_do_not_import_application_policy() -> None:
    """The domain classification never crosses inward to application ownership."""
    imports = []
    for name in _RECOVERY_PROSE_MODULES:
        tree = ast.parse((_REGISTRY_PACKAGE / name).read_text(encoding="utf-8"))
        imports.extend(node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))
    assert not any("application" in module for module in imports)
