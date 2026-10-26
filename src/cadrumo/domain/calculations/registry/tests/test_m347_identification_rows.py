"""M347 identification slots preserve their exclusion and country-prefix contracts."""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from .....core.identity.nif_iva import NifIvaFormatSpec, NifIvaPrefix
from .. import _invoice_row_materialization as materialization
from ..invoice_bindings import M347ThirdPartyOperationProvider
from ..nif_iva_catalogue import NifIvaCatalogue, NifIvaDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture
def identification_catalogue(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide typed format facts without loading any published M347 revision."""
    definitions = []
    for country, raw_prefix in (("DE", "DE"), ("GR", "EL")):
        prefix = NifIvaPrefix.from_registry(raw_prefix)
        definitions.append(
            NifIvaDefinition(
                prefix=prefix,
                iso_country=country,
                iso_aliases=(country, raw_prefix),
                spec=NifIvaFormatSpec(
                    prefix=prefix,
                    country_name=country,
                    pattern=re.compile(rf"^{raw_prefix}[0-9]{{9}}$"),
                    description="Synthetic nine-digit format",
                    example=f"{raw_prefix}123456789",
                ),
            )
        )
    catalogue = NifIvaCatalogue(definitions=tuple(definitions))
    monkeypatch.setattr(materialization, "resolve_nif_iva_catalogue", lambda: catalogue)


@pytest.mark.parametrize(
    ("country", "identifier", "expected_number"),
    [
        ("DE", "123456789", "DE123456789"),
        ("DE", "de 123.456.789", "DE123456789"),
        ("GR", "123456789", "EL123456789"),
        ("DE", "123", ""),
        ("DE", "EL123456789", ""),
        ("US", "123456789", ""),
    ],
)
def test_nonresident_identification_uses_only_the_declared_country_format(
    identification_catalogue: None,
    country: str,
    identifier: str,
    expected_number: str,
) -> None:
    """Foreign rows leave the Spanish NIF blank and never guess a mismatched prefix."""
    row = materialization._m347_declarado_identification(identifier, country)

    assert row == {
        "declarado_tax_id": "",
        "residence_country_code": country,
        "community_iva_number": expected_number,
        "provincia_code": "99",
    }


def test_domestic_identification_does_not_require_a_foreign_format_fact(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Spanish NIF slot excludes the foreign country and community-number slots."""

    def unexpected_catalogue() -> NifIvaCatalogue:
        pytest.fail("a domestic row must not resolve foreign NIF-IVA facts")

    monkeypatch.setattr(materialization, "resolve_nif_iva_catalogue", unexpected_catalogue)

    assert materialization._m347_declarado_identification("B11111112", "ES") == {
        "declarado_tax_id": "B11111112",
        "residence_country_code": "",
        "community_iva_number": "",
        "provincia_code": "",
    }


def test_the_provider_accepts_the_canonical_community_number_column() -> None:
    """The typed selector names the same column that materialization produces."""
    provider = M347ThirdPartyOperationProvider(fact="row_field", row_field="community_iva_number")
    assert provider.row_field == "community_iva_number"


def test_the_provider_refuses_an_unknown_community_number_column() -> None:
    """A misspelled selector must fail before a row can silently lose its value."""
    with pytest.raises(ValidationError):
        M347ThirdPartyOperationProvider.model_validate({"fact": "row_field", "row_field": "community_number"})
