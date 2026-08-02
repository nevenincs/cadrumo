"""Strict registry revision-diff transport rows."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .._registry_diff_payloads import CasillaDiffPayload, FormulaDiffPayload, ParameterDiffPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_registry_diff_payload_rows_preserve_typed_identifiers_and_grounding() -> None:
    casilla = CasillaDiffPayload(id="iva.resultado", number="69", label="Resultado")
    formula = FormulaDiffPayload(
        id="modelo-303-iva-resultado",
        target_casilla_id="iva.resultado",
        from_expression={"op": "subtract"},
        to_expression={"op": "subtract"},
        from_legal_refs=["ley-37-1992:art-90"],
        to_legal_refs=["ley-37-1992:art-90"],
    )
    parameter = ParameterDiffPayload(
        id="modelo-303-tipo-general",
        data_type="decimal",
        from_legal_refs=["ley-37-1992:art-90"],
        to_legal_refs=["ley-37-1992:art-90"],
    )

    assert casilla.id == "iva.resultado"
    assert formula.id == "modelo-303-iva-resultado"
    assert parameter.id == "modelo-303-tipo-general"


@pytest.mark.parametrize(
    ("payload_type", "payload"),
    (
        (CasillaDiffPayload, {"id": "bad casilla", "number": "69", "label": "Resultado"}),
        (
            FormulaDiffPayload,
            {
                "id": "bad formula",
                "target_casilla_id": "iva.resultado",
                "from_expression": {},
                "to_expression": {},
                "from_legal_refs": ["ley-37-1992:art-90"],
                "to_legal_refs": ["ley-37-1992:art-90"],
            },
        ),
        (
            ParameterDiffPayload,
            {
                "id": "bad parameter",
                "data_type": "decimal",
                "from_legal_refs": ["not a legal ref"],
                "to_legal_refs": ["ley-37-1992:art-90"],
            },
        ),
    ),
)
def test_registry_diff_payload_rows_reject_malformed_identifiers(
    payload_type: type[CasillaDiffPayload | FormulaDiffPayload | ParameterDiffPayload],
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        payload_type.model_validate(payload)
