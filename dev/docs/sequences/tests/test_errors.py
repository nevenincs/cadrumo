"""Canonical ownership tests for the sequence-engine errors."""

from __future__ import annotations

import pytest

import dev.docs.sequences as sequences_package
from dev.docs.sequences import errors

from ..errors import (
    SequenceEngineError,
    SequenceExecutionError,
    SequenceGoldenError,
    SequenceGoldenMismatchError,
    SequenceParseError,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def test_errors_live_in_public_defining_module_without_facade_reexports() -> None:
    """The public module owns every sequence error and the package has no error facade."""
    error_types = (
        SequenceEngineError,
        SequenceExecutionError,
        SequenceGoldenError,
        SequenceGoldenMismatchError,
        SequenceParseError,
    )
    assert errors.__name__ == "dev.docs.sequences.errors"
    assert {error_type.__module__ for error_type in error_types} == {errors.__name__}
    assert not any(name.endswith("Error") for name in sequences_package.__all__)
    assert not hasattr(sequences_package, "SequenceEngineError")
    assert not hasattr(sequences_package, "SequenceParseError")
