"""Semantic-plus-exact census over every operand and edit authority the production registry composes.

The denominator here is the live package source tree, walked from disk without
consulting version-control state, so a new source file enters the census
immediately.
"""

from __future__ import annotations

import pytest

from ...tests.inventory import package_python_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _source_files() -> tuple[str, ...]:
    """Return every package Python file in the census denominator."""
    return tuple(path.as_posix() for path in package_python_files(include_data=True))


def test_the_source_denominator_is_nonempty_and_reproducible() -> None:
    """Anchors the census to a real, non-vacuous, re-derivable file set."""
    files = _source_files()
    assert len(files) > 1000, f"Python source denominator looks too small: {len(files)}"
    assert files == _source_files(), "the source-file denominator must be stable within one run"


def test_no_two_production_definitions_declare_the_same_financial_operand_kind() -> None:
    """Every declared operand_kind is a unique custody authority across the whole registry.

    Two operations declaring the same operand_kind would mean either one is
    redundant or the broker cannot tell which operation a mid-flight amount
    belongs to - the exact ambiguity a declared, unique operand_kind exists
    to rule out.
    """
    from ..operation_composition import build_production_operation_registry

    registry = build_production_operation_registry()
    kinds_by_definition: dict[str, list[str]] = {}
    for definition in registry.definitions:
        for declaration in definition.transient_financial_operands:
            kinds_by_definition.setdefault(declaration.operand_kind, []).append(definition.definition_id)

    duplicated = {kind: owners for kind, owners in kinds_by_definition.items() if len(owners) > 1}
    assert not duplicated, f"one financial operand kind declared by more than one definition: {duplicated}"


def test_exactly_one_production_definition_owns_the_edit_contract_apply_authority() -> None:
    """The Edit Contract's guarded compare-and-swap apply has exactly one owning operation.

    Checking `definition_id` uniqueness alone would be near-vacuous: the
    registry already structurally enforces unique ids
    (`OperationRegistry._canonical_definitions`), so that would only ever
    catch a bug the type system already refuses. The real risk is a SECOND,
    differently-named definition whose EXECUTOR also delegates to
    `apply_modelo_edit` - two supervised entry points racing to be the
    single writer's caller, the exact torn-write shape a single-writer
    primitive exists to prevent. Inspecting executor source is the same
    technique `test_lifecycle_operation_conformance.py`'s
    `_KNOWN_AUTHORITIES` census already uses for this reason.
    """
    import inspect

    from ..operation_composition import build_production_operation_registry

    registry = build_production_operation_registry()
    owners = [
        definition.definition_id
        for definition in registry.definitions
        if "apply_modelo_edit" in inspect.getsource(definition.executor_factory.executor_type)
    ]
    assert owners == ["modelo.edit.apply"], (
        f"expected exactly one production definition delegating to apply_modelo_edit, found: {owners}"
    )
