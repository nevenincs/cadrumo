"""CI gate: no modelo-named field on a generic registry type, and no modelo
branch in generic authority construction.

A modelo-named field on a shared type makes every consumer of that type carry
one modelo's vocabulary, and a modelo branch in generic construction means a
second such modelo edits the shared code path instead of registering a compiler.

Both properties are derived rather than listed. A class whose own name carries a
modelo code (:class:`M303FilingEnvelopeDefinition`) is a per-modelo type and its
fields are its own business; a generically named one must declare no
modelo-named field. The modules building a :class:`ValidatedRegistryAuthority`
and its :class:`RegistrySnapshot` values must reference no ``Modelo.M###``
member at all.

The code set comes from the :class:`~cadrumo.core.Modelo` enum, so a new modelo
widens the gate with no edit here. A stale allowlist entry fails.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from .....core import Modelo
from .....tests import SRC_CADRUMO, aeat_relative, production_ast_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Canonical modelo-code value set, derived from the enum.
_CODES: frozenset[str] = frozenset(modelo.value for modelo in Modelo)

#: Registry package whose generic types this gate governs.
_REGISTRY_PACKAGE = "domain/calculations/registry"

#: The two modules that construct the generic authority and its snapshots.
_GENERIC_CONSTRUCTION_MODULES: frozenset[str] = frozenset(
    {
        f"{_REGISTRY_PACKAGE}/authority.py",
        f"{_REGISTRY_PACKAGE}/snapshot.py",
    },
)

#: Deferred sites, keyed by (``src/cadrumo``-relative path, class, field) -> reason.
#: Every entry must still name a live violation; a stale one fails below.
_ALLOWLIST: dict[tuple[str, str, str], str] = {}

#: Matches a modelo code appearing as a name segment: ``m303``, ``modelo_303``.
_NAME_CODE = re.compile(r"(?:^|_)(?:modelo_?|m_?)(\d{3})(?=$|_|[a-z])", re.IGNORECASE)


def _modelo_codes_in_name(name: str) -> frozenset[str]:
    """Return the canonical modelo codes a snake_case or CamelCase name carries."""
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", name)
    return frozenset(match.group(1) for match in _NAME_CODE.finditer(spaced)) & _CODES


def _registry_items() -> tuple[tuple[Path, ast.AST], ...]:
    return tuple(
        (path, tree) for path, tree in production_ast_items() if aeat_relative(path).startswith(_REGISTRY_PACKAGE)
    )


def _modelo_named_fields_on_generic_types(
    items: tuple[tuple[Path, ast.AST], ...] | None = None,
) -> dict[tuple[str, str, str], str]:
    """Return every modelo-named annotated field declared on a generically named class."""
    found: dict[tuple[str, str, str], str] = {}
    for path, tree in _registry_items() if items is None else items:
        relative = aeat_relative(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or _modelo_codes_in_name(node.name):
                continue
            for statement in node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue
                codes = _modelo_codes_in_name(statement.target.id)
                if codes:
                    found[(relative, node.name, statement.target.id)] = ", ".join(sorted(codes))
    return found


def _modelo_branches_in_generic_construction(
    items: tuple[tuple[Path, ast.AST], ...] | None = None,
) -> dict[str, tuple[str, ...]]:
    """Return every ``Modelo.M###`` member referenced by generic construction."""
    found: dict[str, list[str]] = {}
    for path, tree in _registry_items() if items is None else items:
        relative = aeat_relative(path)
        if relative not in _GENERIC_CONSTRUCTION_MODULES:
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "Modelo"
                and _modelo_codes_in_name(node.attr)
            ):
                found.setdefault(relative, []).append(f"Modelo.{node.attr}")
    return {relative: tuple(members) for relative, members in found.items()}


def test_the_registry_package_is_actually_scanned() -> None:
    """Prove the scan reaches real modules, so a green verdict is not vacuous."""
    scanned = {aeat_relative(path) for path, _ in _registry_items()}
    assert f"{_REGISTRY_PACKAGE}/schema.py" in scanned
    assert scanned >= _GENERIC_CONSTRUCTION_MODULES
    assert (SRC_CADRUMO / _REGISTRY_PACKAGE / "_supplementary_orden.py").is_file()


def test_no_modelo_named_field_on_a_generic_registry_type() -> None:
    """Refuse a modelo-named field on a registry type that is not itself per-modelo."""
    violations = {key: codes for key, codes in _modelo_named_fields_on_generic_types().items() if key not in _ALLOWLIST}
    assert not violations, (
        "generic registry schema types must not declare modelo-named fields; "
        "register per-modelo material in a dispatch table instead:\n"
        + "\n".join(f"  {path}::{cls}.{field} names modelo {codes}" for (path, cls, field), codes in violations.items())
    )


def test_no_modelo_branch_in_generic_authority_construction() -> None:
    """Refuse a modelo branch in the modules that build the generic authority."""
    branches = _modelo_branches_in_generic_construction()
    assert not branches, (
        "generic authority construction must not branch on a modelo id; register the "
        "modelo's compiler in the supplementary-Orden dispatch tables instead:\n"
        + "\n".join(f"  {path} references {', '.join(members)}" for path, members in branches.items())
    )


def test_every_allowlisted_site_is_still_a_live_violation() -> None:
    """Fail a stale exemption, so the allowlist cannot outlive the defect it covers."""
    live = set(_modelo_named_fields_on_generic_types())
    stale = sorted(key for key in _ALLOWLIST if key not in live)
    assert not stale, (
        "these allowlist entries no longer name a live modelo-named field and must be deleted:\n"
        + "\n".join(f"  {path}::{cls}.{field}" for path, cls, field in stale)
    )


def test_the_field_detector_sees_a_planted_violation() -> None:
    """Prove the field scan bites, on a planted tree rather than on the real one.

    The detectors are fed synthetic ASTs directly, so nothing tracked is
    mutated and the proof survives in the suite instead of living in a
    throwaway script.
    """
    planted = ast.parse("class TotallyGenericThing:\n    m303_planted: int = 0\n")
    found = _modelo_named_fields_on_generic_types(((SRC_CADRUMO / _REGISTRY_PACKAGE / "schema.py", planted),))

    assert any(cls == "TotallyGenericThing" and field == "m303_planted" for _path, cls, field in found)


def test_a_per_modelo_class_keeps_its_own_modelo_named_fields() -> None:
    """The control: without this, the test above could be firing on every field."""
    exempt = ast.parse("class M303Envelope:\n    m303_thing: int = 0\n")

    assert _modelo_named_fields_on_generic_types(((SRC_CADRUMO / _REGISTRY_PACKAGE / "schema.py", exempt),)) == {}


def test_the_branch_detector_sees_a_planted_modelo_branch() -> None:
    """Prove the branch scan bites, and only inside generic construction."""
    planted = ast.parse("def _construct_authority():\n    return modelo.id == Modelo.M303\n")
    generic = SRC_CADRUMO / _REGISTRY_PACKAGE / "authority.py"
    per_modelo = SRC_CADRUMO / _REGISTRY_PACKAGE / "_m303_orden_resolution.py"

    assert _modelo_branches_in_generic_construction(((generic, planted),))
    assert _modelo_branches_in_generic_construction(((per_modelo, planted),)) == {}


def test_every_allowlisted_site_states_a_reason() -> None:
    """Require a stated reason on every exemption, since judgement moves to the list."""
    unreasoned = sorted(key for key, reason in _ALLOWLIST.items() if len(reason.strip()) < 40)
    assert not unreasoned, f"allowlist entries without a stated reason: {unreasoned!r}"
