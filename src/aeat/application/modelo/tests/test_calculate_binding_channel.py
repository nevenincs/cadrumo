"""Real-behavior proof that ``--binding`` coercion is registry-data-type driven.

The pre-hardening classification was a ``try Decimal/except`` heuristic: a
malformed numeric override silently fell through to the enum channel. The
bindings-interface hardening replaced that with a
registry-declared coercion: a binding the revision's formulas consume as a
string enum key routes to the ``enum`` channel verbatim; every other declared
binding routes to the ``decimal`` channel whose override MUST parse as a
Decimal, so a malformed amount REFUSES instead of silently reclassifying. An
unknown binding id refuses with the accepted set.

These tests exercise the real registry authority (no mocks): the Modelo 200
``2024-y-siguientes`` revision declares both an enum-channel binding
(``modelo-200-2024-profile-legal-entity-form``, an ``args[1]`` enum-key argument
of a dispatch op) and decimal-channel bindings (e.g.
``modelo-200-2024-pagos-fraccionados-anuales``), so the channel discriminator is
proven against genuine registry data rather than a synthetic shape.
"""

from __future__ import annotations

import pytest

from ....core.errors import AeatError, build_error_envelope
from ....core.resources import resources
from ....domain.calculations.registry import enum_consumed_binding_ids
from .._calculate_input import (
    ModeloCalculateBindingInputError,
    _binding_input_channel,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "200"
_REVISION = "2024-y-siguientes"
_ENUM_BINDING = "modelo-200-2024-profile-legal-entity-form"
_DECIMAL_BINDING = "modelo-200-2024-pagos-fraccionados-anuales"


def _revision():
    return resources().modelos.authority.validate_modelo(_MODELO).revisions[_REVISION]


def _channel_inputs():
    revision = _revision()
    known = {str(binding.id) for binding in revision.bindings}
    enum_ids = enum_consumed_binding_ids(revision)
    return revision, known, enum_ids


def test_enum_consumed_binding_routes_to_enum_channel() -> None:
    """A formula-consumed enum-key binding is the ``enum`` channel.

    The fixture is anti-tautological: the test first confirms the binding is a
    declared enum-consumed id in the live registry, so a regression that stops
    classifying it as enum fails here rather than passing vacuously.
    """
    revision, known, enum_ids = _channel_inputs()
    assert _ENUM_BINDING in known
    assert _ENUM_BINDING in enum_ids
    assert _binding_input_channel(_ENUM_BINDING, revision, known, enum_ids) == "enum"


def test_decimal_consumed_binding_routes_to_decimal_channel() -> None:
    """A declared, non-enum-consumed binding is the ``decimal`` channel."""
    revision, known, enum_ids = _channel_inputs()
    assert _DECIMAL_BINDING in known
    assert _DECIMAL_BINDING not in enum_ids
    assert _binding_input_channel(_DECIMAL_BINDING, revision, known, enum_ids) == "decimal"


def test_unknown_binding_id_refuses_with_accepted_set() -> None:
    """An unknown ``--binding`` id refuses with the revision's accepted ids."""
    revision, known, enum_ids = _channel_inputs()
    with pytest.raises(ModeloCalculateBindingInputError) as exc_info:
        _binding_input_channel("no-such-binding-id", revision, known, enum_ids)

    error = exc_info.value
    assert isinstance(error, AeatError)
    assert error.translated_message == "application.modelo.errors.calculate_binding_unknown"
    assert error.context is not None
    assert error.context["key"] == "no-such-binding-id"
    # The refusal names the offending id and the accepted set, not a bare
    # "value invalid" — the instructive-refusal CLI-boundary contract.
    assert _DECIMAL_BINDING in str(error.context["accepted"])
    assert "no-such-binding-id" in str(error)
    assert _DECIMAL_BINDING in str(error)
    assert build_error_envelope(error).code == "REFUSED_MODELO_CALCULATE_BINDING_INPUT"
