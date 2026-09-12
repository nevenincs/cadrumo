"""Authored retirement and replacement declarations for identifier-keyed families."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from ..identifier_evolutions import (
    IdentifierEvolution,
    ReplacedIdentifierEvolution,
    RetiredIdentifierEvolution,
)
from ..schema import ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ADAPTER = TypeAdapter(IdentifierEvolution)
_REFS = {"legal_refs": ("ley-35-2006:art-50",), "source_refs": ("aeat-manual",)}


def test_retired_round_trips_through_discriminator() -> None:
    evolution = _ADAPTER.validate_python(
        {"kind": "retired", "identifier": "renta-anterior", "to_revision": "2025", **_REFS}
    )
    assert isinstance(evolution, RetiredIdentifierEvolution)
    assert _ADAPTER.validate_python(evolution.model_dump()) == evolution


def test_replaced_names_both_identifiers() -> None:
    evolution = _ADAPTER.validate_python(
        {"kind": "replaced", "identifier": "old", "replaced_by": "new", "to_revision": "2025", **_REFS},
    )
    assert isinstance(evolution, ReplacedIdentifierEvolution)
    assert evolution.replaced_by == "new"


def test_replacement_by_itself_is_refused() -> None:
    with pytest.raises(ValidationError, match="cannot be replaced by itself"):
        ReplacedIdentifierEvolution(identifier="same", replaced_by="same", to_revision="2025", **_REFS)


def test_unknown_kind_is_refused() -> None:
    with pytest.raises(ValidationError):
        _ADAPTER.validate_python({"kind": "renamed", "identifier": "x", "to_revision": "2025", **_REFS})


def test_revision_enrolls_binding_and_formula_evolution_sections() -> None:
    for family in ("binding_evolutions", "formula_evolutions"):
        assert family in ModeloRevision.model_fields
