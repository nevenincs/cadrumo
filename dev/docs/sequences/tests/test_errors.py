"""Canonical ownership tests for the sequence-engine errors."""

from __future__ import annotations

from importlib import import_module

import pytest

from .. import errors
from ..errors import (
    SequenceEngineError,
    SequenceExecutionError,
    SequenceGoldenError,
    SequenceGoldenMismatchError,
    SequenceParseError,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

sequences_package = import_module("..", __package__)


def test_errors_live_in_public_defining_module_without_facade_reexports() -> None:
    """The public module owns every sequence error and the package forwards nothing.

    The assertion used to scan the package's ``__all__`` for names ending in
    ``Error``, which assumed an ``__all__`` existed to scan - true only while the
    initialiser forwarded sixty other names. The property it was after survives
    and is stated directly: the initialiser exports nothing, so no name can be
    absent from a list that no longer exists.

    The last of three siblings written this way, and the only one whose package
    also had to have its library moved out of ``__main__`` first.
    """
    error_types = (
        SequenceEngineError,
        SequenceExecutionError,
        SequenceGoldenError,
        SequenceGoldenMismatchError,
        SequenceParseError,
    )
    assert errors.__name__ == "dev.docs.sequences.errors"
    assert {error_type.__module__ for error_type in error_types} == {errors.__name__}
    assert not hasattr(sequences_package, "__all__"), "an inert initialiser declares no exports"
    assert not hasattr(sequences_package, "SequenceEngineError")
    assert not hasattr(sequences_package, "SequenceParseError")
    # Nothing but submodules, which is what importing a package leaves behind
    # and the only thing an inert initialiser may carry.
    public = [name for name in vars(sequences_package) if not name.startswith("_")]
    assert all(getattr(sequences_package, name).__name__.startswith("dev.docs.sequences.") for name in public), (
        f"the initialiser still forwards non-module names: {public}"
    )
