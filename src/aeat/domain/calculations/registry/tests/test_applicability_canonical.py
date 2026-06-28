"""Regression tests asserting single canonical definition of applicability rules.

Pins the applicability collapse to the single domain
source): ``_MODELO_APPLICABILITY_RULES`` and ``derive_modelo_applicability``
must be defined exactly once in the codebase (in the domain module) and
every access path must resolve to the same object in memory.

Three assertions:
- The domain ``_applicability`` module is the only file that defines
  ``_MODELO_APPLICABILITY_RULES`` as an assignment (not a re-export).
- The function object imported via the application overview re-export is
  identity-equal to the domain implementation.
- The function object imported via the domain facade is identity-equal to
  the domain implementation.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SRC_ROOT = Path(__file__).parent.parent.parent.parent  # src/aeat
_DOMAIN_CANONICAL = Path(__file__).parent.parent / "_applicability.py"


def _assignment_targets(tree: ast.AST) -> set[str]:
    """Return names that appear as assignment targets at module scope."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def test_rules_dict_defined_exactly_once() -> None:
    """``_MODELO_APPLICABILITY_RULES`` is assigned in exactly one source file.

    Any file that merely re-exports the name via ``from … import …`` does
    not count as a definition; only direct assignment (``name = …``) does.
    The only allowed definition site is
    ``domain/calculations/registry/_applicability.py``.
    """
    defining_files: list[Path] = []
    for module_path in _SRC_ROOT.rglob("*.py"):
        if module_path.stem.startswith("test_"):
            continue
        try:
            source = module_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        try:
            tree = ast.parse(source, filename=str(module_path))
        except SyntaxError:
            continue
        if "_MODELO_APPLICABILITY_RULES" in _assignment_targets(tree):
            defining_files.append(module_path)

    assert defining_files == [_DOMAIN_CANONICAL], (
        f"_MODELO_APPLICABILITY_RULES must be defined only in "
        f"{_DOMAIN_CANONICAL.relative_to(_SRC_ROOT.parent)}; "
        f"found additional definition(s) in: "
        f"{[str(p.relative_to(_SRC_ROOT.parent)) for p in defining_files if p != _DOMAIN_CANONICAL]}"
    )


def test_application_overview_applicability_shim_is_absent() -> None:
    """The application.overview._applicability re-export shim must not exist.

    The cross-domain continuity contract ratified the
    removal of ``aeat.application.overview._applicability`` — the
    application layer consumes the domain rules through the public
    registry surface directly (``aeat.domain.calculations.registry``)
    and the standalone re-export shim has no remaining caller. This
    test replaces the old identity-re-export check: a recurrence of
    the shim (an accidental restore) must be flagged at the structural
    boundary, not silently re-introduced.
    """
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("aeat.application.overview._applicability")


def test_facade_reexport_is_identity_equal_to_domain() -> None:
    """The domain facade re-export resolves to the same object as the implementation."""
    domain_mod = importlib.import_module("aeat.domain.calculations.registry._applicability")
    facade_mod = importlib.import_module("aeat.domain.calculations.registry.applicability")
    assert facade_mod.derive_modelo_applicability is domain_mod.derive_modelo_applicability, (
        "domain facade applicability.derive_modelo_applicability is not the same object as the domain implementation"
    )


def test_annual_withholding_summary_applicability_uses_art_108_not_art_109() -> None:
    """M180/M190 filing duty is RIRPF art. 108, not pago-fraccionado art. 109."""
    domain_mod = importlib.import_module("aeat.domain.calculations.registry._applicability")
    core_mod = importlib.import_module("aeat.core")
    rules_by_modelo = {rule.modelo: rule for rule in domain_mod.iter_modelo_applicability_rules()}

    for modelo in (core_mod.Modelo.M180, core_mod.Modelo.M190):
        legal_refs = rules_by_modelo[modelo].legal_refs
        assert "rd-439-2007:art-108" in legal_refs
        assert "rd-439-2007:art-109" not in legal_refs
