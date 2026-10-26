"""Syntax-only retención-scheme value behavior at the core boundary."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from ..aggregation import RetencionScheme
from ..errors.hierarchy import CoreValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _SchemeCarrier(BaseModel):
    model_config = ConfigDict(strict=True)

    scheme: RetencionScheme


def test_retencion_scheme_preserves_distinct_valid_wire_tokens() -> None:
    empleado = RetencionScheme("rendimientos_trabajo")
    administrador = RetencionScheme("rendimientos_trabajo_administrador")

    assert empleado.value == "rendimientos_trabajo"
    assert administrador.value == "rendimientos_trabajo_administrador"
    assert empleado != administrador
    assert hash(empleado) == hash("rendimientos_trabajo")


@pytest.mark.parametrize("token", ["", "UPPER", "contains-hyphen", " leading"])
def test_retencion_scheme_rejects_invalid_wire_syntax(token: str) -> None:
    with pytest.raises(CoreValidationError, match="invalid retencion scheme token"):
        RetencionScheme(token)


def test_retencion_scheme_validates_and_serializes_through_pydantic() -> None:
    carrier = _SchemeCarrier.model_validate({"scheme": "rendimientos_trabajo"})

    assert carrier.scheme == RetencionScheme("rendimientos_trabajo")
    assert carrier.model_dump(mode="json") == {"scheme": "rendimientos_trabajo"}
    with pytest.raises(ValidationError):
        _SchemeCarrier.model_validate({"scheme": "invalid-token"})
