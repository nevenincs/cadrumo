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


def test_production_edit_operations_pin_the_same_complete_typed_batch() -> None:
    """Apply and preflight consume the same canonical model without persisting its values."""
    from ...application.modelo.edit_models import ModeloEditSubmissionV1
    from ..operation_composition import build_production_operation_registry

    registry = build_production_operation_registry()
    declarations = [
        definition.transient_financial_operand
        for definition in registry.definitions
        if definition.transient_financial_operand is not None
    ]
    assert declarations
    assert all(declaration.operand_type is ModeloEditSubmissionV1 for declaration in declarations)
    assert len({declaration.operand_schema for declaration in declarations}) == 1


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
