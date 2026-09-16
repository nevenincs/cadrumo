"""Tests for the typed-context factories on registry error classes.

Pins the contract from the linkage-design audit decision (`registry-error-typed-context-factories`):
each
canonical raise scenario is a classmethod factory; the resulting
error carries a pinned ``context`` dict with named keys downstream
consumers (locale templates, CLI JSON emit) can rely on.

Tests assert against the EXTERNAL contract (the context dict's
keys and the translated_message identifier) rather than the
factory's internal implementation, satisfying the no-tautological-
tests rule.
"""

from __future__ import annotations

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from ..errors import RegistrySnapshotError, RegistryValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_REFERENCED_BEFORE_EVALUATION_CASILLA: CasillaId = validated_casilla_id(
    "0719",
    surface="_REFERENCED_BEFORE_EVALUATION_CASILLA",
)


def test_for_unknown_input_casilla_ids_sorts_and_joins() -> None:
    err = RegistryValidationError.for_unknown_input_casilla_ids(casilla_ids=("9999999", "0001", "0002"))
    assert err.context == {"casilla_ids": "0001,0002,9999999"}
    assert err.translated_message == "errors.calc.unknown_input_casillas"


def test_snapshot_error_factory_pins_modelo_id() -> None:
    err = RegistrySnapshotError.for_modelo_not_registered(modelo_id="999")
    assert err.context == {"modelo_id": "999"}
    assert err.translated_message == "errors.snapshot.modelo_not_registered"


def test_factories_return_correct_subclass_instances() -> None:
    """Each factory returns its declaring subclass (Self), not the base."""
    assert isinstance(
        RegistryValidationError.for_unknown_input_casilla_ids(casilla_ids=("0001",)),
        RegistryValidationError,
    )
    assert isinstance(
        RegistrySnapshotError.for_modelo_not_registered(modelo_id="999"),
        RegistrySnapshotError,
    )
