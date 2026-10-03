"""Preview rendering of a boolean binding's decimal-encoding mapping.

The ``bindings list`` and ``bindings resolve`` surfaces render an operator-facing
hint enumerating the ``0`` / ``1`` encoding of a decimal-channel boolean binding
(the Modelo 100 estimación-directa modality flag), so the operator can read the
decimal-to-meaning mapping before attempting a calculation. These tests exercise
the production projection and text-rendering helpers directly with real
:class:`BooleanBindingEncodedValue` inputs, so no registry snapshot load is
required.
"""

from __future__ import annotations

import pytest

from .._modelo_bindings_payloads import BindingEncodedOptionPayload
from .._modelo_rendering import binding_encoded_option_lines

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_encoded_option_text_line_enumerates_the_mapping() -> None:
    """The listing hint names the binding and its decimal-to-meaning mapping."""
    payloads = (
        BindingEncodedOptionPayload(encoded_value="1", boolean_meaning=True, registry_value="N"),
        BindingEncodedOptionPayload(encoded_value="0", boolean_meaning=False, registry_value="S"),
    )

    lines = binding_encoded_option_lines("renta-modelo-100-estimacion-directa-es-normal", payloads)

    assert lines == [
        "encoded_option\trenta-modelo-100-estimacion-directa-es-normal\t1=true(N)  0=false(S)",
    ]


def test_no_encoded_option_line_for_non_boolean_binding() -> None:
    """A binding with no boolean encoding produces no hint line."""
    assert binding_encoded_option_lines("some-decimal-binding", ()) == []
