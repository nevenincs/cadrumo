"""Syntax-only identifier values do not bootstrap from governed facts."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from ..errors.hierarchy import CadrumoError, CoreValidationError
from ..modelo import Modelo
from ..tax_domain import TaxDomain

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.usefixtures("operation")]


@pytest.mark.parametrize("code", ["000", "037", "179", "999"])
def test_modelo_accepts_every_three_digit_ascii_identifier(code: str) -> None:
    modelo = Modelo(code)

    assert modelo.value == code
    assert modelo == code
    assert hash(modelo) == hash(code)


@pytest.mark.parametrize("code", ["", "37", "0037", " 037", "037 ", "M37", "\uff11\uff12\uff13"])
def test_modelo_rejects_noncanonical_syntax_with_typed_error(code: str) -> None:
    with pytest.raises(CoreValidationError) as caught:
        Modelo(code)

    assert not isinstance(caught.value, ValueError)
    assert isinstance(caught.value, CadrumoError)
    assert caught.value.code.code == "INTEGRITY_CADRUMO_CORE_VALIDATION"


@pytest.mark.parametrize("identifier", ["censo", "iva", "irpf_actividad", "future_domain_2"])
def test_tax_domain_accepts_open_canonical_identifiers(identifier: str) -> None:
    domain = TaxDomain(identifier)

    assert domain.value == identifier
    assert domain == identifier
    assert hash(domain) == hash(identifier)


@pytest.mark.parametrize(
    "identifier",
    ["", "CENSO", "iva-domain", "_iva", "iva_", "iva__general", "iva general"],
)
def test_tax_domain_rejects_noncanonical_syntax_with_typed_error(identifier: str) -> None:
    with pytest.raises(CoreValidationError) as caught:
        TaxDomain(identifier)

    assert not isinstance(caught.value, ValueError)
    assert isinstance(caught.value, CadrumoError)
    assert caught.value.code.code == "INTEGRITY_CADRUMO_CORE_VALIDATION"


def test_identifier_types_remain_distinct() -> None:
    assert isinstance(Modelo("303"), Modelo)
    assert not isinstance(Modelo("303"), TaxDomain)
    assert isinstance(TaxDomain("iva"), TaxDomain)
    assert not isinstance(TaxDomain("iva"), Modelo)


@pytest.mark.parametrize(
    ("adapter", "raw", "expected"),
    [
        (TypeAdapter(Modelo), "303", Modelo("303")),
        (TypeAdapter(TaxDomain), "iva_general", TaxDomain("iva_general")),
    ],
)
def test_pydantic_round_trip_preserves_typed_identifier(
    adapter: TypeAdapter[object],
    raw: str,
    expected: object,
) -> None:
    parsed = adapter.validate_json(f'"{raw}"')

    assert parsed == expected
    assert type(parsed) is type(expected)
    assert adapter.dump_json(parsed) == f'"{raw}"'.encode()


@pytest.mark.parametrize(
    ("adapter", "raw"),
    [
        (TypeAdapter(Modelo), "30"),
        (TypeAdapter(TaxDomain), "IVA"),
    ],
)
def test_pydantic_boundary_rejects_invalid_identifier_syntax(
    adapter: TypeAdapter[object],
    raw: str,
) -> None:
    with pytest.raises(ValidationError):
        adapter.validate_python(raw)


def test_core_identifier_modules_expose_no_authoring_source_hooks() -> None:
    import cadrumo.core.modelo as modelo_module
    import cadrumo.core.tax_domain as tax_domain_module

    for module in (modelo_module, tax_domain_module):
        assert not hasattr(module, "_FACT_PATH")
        assert not hasattr(module, "_fact_declarations")
        assert not hasattr(module, "_catalogue_codes")
