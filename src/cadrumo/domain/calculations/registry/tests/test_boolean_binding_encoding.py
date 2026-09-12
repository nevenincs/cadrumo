"""Decimal-encoding derivation for boolean-casilla ``manual_input`` bindings.

A ``manual_input`` binding whose selector declares ``data_type = "boolean"``
(the Modelo 100 estimación-directa modality flag) is consumed by the registry
formulas as a numeric ``1`` / ``0`` operand, yet the accepted values and their
meaning are opaque from the raw binding. :func:`boolean_binding_encoded_values`
makes the encoding explicit — one accepted decimal per boolean sense, paired
with the selector's declared ``true_value`` / ``false_value`` casilla token — so
the operator-facing listing and the ``--binding`` error can teach the mapping
without a per-form hardcoded table. These tests assert the derivation against the
registry-declared selector semantics, not a hand-copied expectation.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..binding_selector_utils import (
    BooleanBindingEncodedValue,
    boolean_binding_encoded_values,
)
from ..binding_value_contract import BindingDataType, BindingValueChannel, BindingValueContract
from ..errors import RegistryValidationError
from ..manual_input_selector import ManualInputProvider
from ..schema import BindingDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _boolean_binding() -> BindingDefinition:
    """Build the real Modelo 100 estimación-directa boolean-flag binding."""
    return BindingDefinition.model_validate(
        {
            "id": "renta-modelo-100-estimacion-directa-es-normal",
            "provider": {
                "kind": "manual_input",
                "casilla_id": "0168",
                "data_type": "boolean",
                "true_value": "N",
                "false_value": "S",
            },
            "value": {
                "data_type": "enum",
                "channel": "enum",
                "typed_enum": "EstimacionDirectaModalidad",
            },
            "aggregation": {
                "op": "copy",
            },
            "legal_refs": ("ley-35-2006:art-30",),
            "source_refs": ("aeat-dr-100-2025-dictionary",),
        },
    )


def test_boolean_binding_encodes_true_to_one_and_false_to_zero() -> None:
    """The affirmative sense encodes to ``1`` and the negative to ``0``.

    Each accepted decimal carries its boolean meaning and the underlying casilla
    token the selector declares for that sense (``true_value`` / ``false_value``),
    so the mapping is derived from the binding definition rather than hardcoded.
    """
    options = boolean_binding_encoded_values(_boolean_binding())

    assert options == (
        BooleanBindingEncodedValue(encoded_value="1", boolean_meaning=True, registry_value="N"),
        BooleanBindingEncodedValue(encoded_value="0", boolean_meaning=False, registry_value="S"),
    )


def test_non_boolean_manual_input_binding_has_no_encoded_values() -> None:
    """A scalar-money manual_input binding is not a boolean flag, so no encoding."""
    scalar = BindingDefinition.model_validate(
        {
            "id": "renta-2025-scalar-input",
            "provider": {
                "kind": "manual_input",
                "casilla_id": "0003",
                "data_type": "money",
            },
            "value": {
                "data_type": "money",
                "channel": "decimal",
            },
            "legal_refs": ("ley-35-2006:art-99",),
            "source_refs": ("aeat-dr-100-2025-dictionary",),
        },
    )

    assert boolean_binding_encoded_values(scalar) == ()


def test_non_manual_input_binding_has_no_encoded_values() -> None:
    """A profile-sourced binding is never a decimal-encoded boolean flag."""
    profile = BindingDefinition.model_validate(
        {
            "id": "renta-profile-tax-residence-ccaa",
            "provider": {
                "kind": "profile",
                "profile_model": "TaxResidenceProfile",
                "field": "ccaa",
                "xsd_attribute": "codigoCADeclaracion",
                "dictionary_field": "ZCCAD",
            },
            "value": {
                "data_type": "enum",
                "channel": "enum",
                "typed_enum": "CCAA",
            },
            "aggregation": {
                "op": "copy",
            },
            "legal_refs": ("orden-hac-277-2026:art-3",),
            "source_refs": ("aeat-dr-100-2025-dictionary",),
        },
    )

    assert boolean_binding_encoded_values(profile) == ()


def test_a_misspelled_boolean_encoding_key_is_refused_not_silently_dropped() -> None:
    """The bite proof: a selector shape the model rejects must raise, not vanish.

    ``BindingDefinition.model_validate`` already dispatches through
    ``ManualInputProvider`` at construction time, so a genuinely malformed
    selector cannot reach this function via the normal constructor -- proven
    by the companion assertion below. The residual risk this fix closes is
    DRIFT: a raw ``dict.get("true_value")`` reads a string literal with no tie
    to the model's own field names, so if ``ManualInputProvider`` ever
    renamed that field, the model's construction-time validation would keep
    passing (it would just be validating the NEW name) while a raw-dict
    reader silently, permanently stopped finding any boolean encoding at all --
    indistinguishable from "not a boolean binding" for every real one.
    ``model_construct`` bypasses the constructor's own validators, standing in
    for that drifted-schema selector so the fixed function's OWN validation
    (not the constructor's) is what is under test.
    """
    with pytest.raises(
        ValidationError,
        match=r"provider\.manual_input\.ture_value",
    ) as excinfo:
        BindingDefinition.model_validate(
            {
                "id": "renta-modelo-100-estimacion-directa-es-normal",
                "provider": {
                    "kind": "manual_input",
                    "casilla_id": "0168",
                    "data_type": "boolean",
                    "ture_value": "N",
                    "false_value": "S",
                },
                "value": {
                    "data_type": "enum",
                    "channel": "enum",
                    "typed_enum": "EstimacionDirectaModalidad",
                },
                "aggregation": {
                    "op": "copy",
                },
                "legal_refs": ("ley-35-2006:art-30",),
                "source_refs": ("aeat-dr-100-2025-dictionary",),
            },
        )
    assert "Extra inputs are not permitted" in str(excinfo.value), (
        "construction-time gate must be the one refusing the typo -- confirms the "
        "residual risk this fix closes is drift, not malformed-data construction"
    )

    drifted = BindingDefinition.model_construct(
        id="renta-modelo-100-estimacion-directa-es-normal",
        provider=ManualInputProvider.model_construct(
            casilla_id="0168",
            data_type="boolean",
            ture_value="N",  # the field ManualInputProvider no longer names "true_value"
            false_value="S",
        ),
        value=BindingValueContract(
            data_type=BindingDataType.ENUM,
            channel=BindingValueChannel.ENUM,
            typed_enum="EstimacionDirectaModalidad",
        ),
        aggregation={"op": "copy"},
        legal_refs=("ley-35-2006:art-30",),
        source_refs=("aeat-dr-100-2025-dictionary",),
    )

    with pytest.raises(RegistryValidationError, match="malformed manual_input selector"):
        boolean_binding_encoded_values(drifted)
