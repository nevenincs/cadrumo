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
``2024`` revision declares both an enum-channel binding
(``modelo-200-2024-profile-legal-entity-form``, an ``args[1]`` enum-key argument
of a dispatch op) and decimal-channel bindings (e.g.
``modelo-200-2024-pagos-fraccionados-anuales``), so the channel discriminator is
proven against genuine registry data rather than a synthetic shape.
"""

from __future__ import annotations

import pytest

from ....core.errors import CadrumoError, build_error_envelope
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.runtime_graph import enum_consumed_binding_ids, revision_date_binding_ids
from .._calculate_input import (
    ModeloCalculateBindingInputError,
    _validated_binding_input_channel,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "200"
_REVISION = "2024"
_ENUM_BINDING: BindingId = "modelo-200-2024-profile-legal-entity-form"
_DECIMAL_BINDING: BindingId = "modelo-200-2024-pagos-fraccionados-anuales"

# Modelo 100 declares a date-valued binding (taxpayer birth date) consumed by
# the ``age_at_year_end`` op; it is profile-sourced, not a --binding channel.
_M100_DATE_BINDING: BindingId = "renta-2024-profile-taxpayer-birth-date"


def _revision():
    return bundled_authority().validate_modelo(_MODELO).revisions[_REVISION]


def _channel_inputs():
    revision = _revision()
    known = {binding.id for binding in revision.bindings}
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
    key, channel = _validated_binding_input_channel(_ENUM_BINDING, revision, known, enum_ids)
    assert key == _ENUM_BINDING
    assert channel == "enum"


def test_decimal_consumed_binding_routes_to_decimal_channel() -> None:
    """A declared, non-enum-consumed binding is the ``decimal`` channel."""
    revision, known, enum_ids = _channel_inputs()
    assert _DECIMAL_BINDING in known
    assert _DECIMAL_BINDING not in enum_ids
    key, channel = _validated_binding_input_channel(_DECIMAL_BINDING, revision, known, enum_ids)
    assert key == _DECIMAL_BINDING
    assert channel == "decimal"


def test_unknown_binding_id_refuses_with_accepted_set() -> None:
    """An unknown ``--binding`` id refuses with the revision's accepted ids."""
    revision, known, enum_ids = _channel_inputs()
    with pytest.raises(ModeloCalculateBindingInputError) as exc_info:
        _validated_binding_input_channel("no-such-binding-id", revision, known, enum_ids)

    error = exc_info.value
    assert isinstance(error, CadrumoError)
    assert error.translated_message == "application.modelo.errors.calculate_binding_unknown"
    assert error.context is not None
    assert error.context["key"] == "no-such-binding-id"
    # The refusal names the offending id and the accepted set, not a bare
    # "value invalid" — the instructive-refusal CLI-boundary contract.
    assert _DECIMAL_BINDING in str(error.context["accepted"])
    assert "no-such-binding-id" in str(error)
    assert _DECIMAL_BINDING in str(error)
    assert build_error_envelope(error).code == "REFUSED_MODELO_CALCULATE_BINDING_INPUT"


def test_date_sourced_binding_is_detected_as_a_date_channel() -> None:
    """A date-valued profile binding is the ``date`` channel, not decimal/enum.

    The calculate path uses :func:`revision_date_binding_ids` to refuse a
    date-valued ``--binding`` override with an actionable "set it on the profile"
    message, instead of the misleading "is not a decimal" coercion failure. The
    fixture is anti-tautological: it first confirms M100 declares the birth-date
    date binding in the live registry, so a regression that stops detecting it
    fails here rather than passing vacuously.
    """
    snapshot = bundled_authority().snapshot("100", filing_year=2024, period="0A")
    revision = snapshot.revision
    date_ids = revision_date_binding_ids(revision)
    assert _M100_DATE_BINDING in date_ids
    # A date binding is neither an enum nor a plain decimal override channel.
    assert _M100_DATE_BINDING not in enum_consumed_binding_ids(revision)
