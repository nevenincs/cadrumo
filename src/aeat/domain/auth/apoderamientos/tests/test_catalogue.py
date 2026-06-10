"""Tests for the apoderamientos scope catalogue and parser."""

from __future__ import annotations

import pytest

from .. import (
    ALL_TOKEN,
    ApoderamientosCatalogue,
    UnknownScopeError,
    expand_all_token,
    load_default_catalogue,
    parse_scope_tokens,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture
def catalogue() -> ApoderamientosCatalogue:
    return load_default_catalogue()


class TestCatalogueLoad:
    def test_default_catalogue_loads_from_registry(self, catalogue: ApoderamientosCatalogue) -> None:
        assert catalogue.catalogue_version.startswith("2026")
        assert len(catalogue.scopes) >= 5
        codes = catalogue.code_set()
        assert "IVA" in codes
        assert "RENT" in codes
        assert "CENSO" in codes

    def test_catalogue_codes_are_uppercase(self, catalogue: ApoderamientosCatalogue) -> None:
        for scope in catalogue.scopes:
            assert scope.code == scope.code.upper()

    def test_catalogue_iva_scope_binds_modelo_303_390(self, catalogue: ApoderamientosCatalogue) -> None:
        iva = catalogue.get("IVA")
        assert iva is not None
        assert "303" in iva.modelo_codes
        assert "390" in iva.modelo_codes


class TestParseScopeTokens:
    def test_known_code_passes_through(self, catalogue: ApoderamientosCatalogue) -> None:
        assert parse_scope_tokens(("IVA",), catalogue) == ("IVA",)

    def test_multiple_known_codes_preserve_order(self, catalogue: ApoderamientosCatalogue) -> None:
        assert parse_scope_tokens(("IVA", "RENT", "CENSO"), catalogue) == ("IVA", "RENT", "CENSO")

    def test_duplicates_are_deduplicated(self, catalogue: ApoderamientosCatalogue) -> None:
        assert parse_scope_tokens(("IVA", "RENT", "IVA"), catalogue) == ("IVA", "RENT")

    def test_unknown_code_refuses(self, catalogue: ApoderamientosCatalogue) -> None:
        with pytest.raises(UnknownScopeError, match="not in catalogue"):
            parse_scope_tokens(("BOGUS",), catalogue)

    def test_lowercase_token_refuses(self, catalogue: ApoderamientosCatalogue) -> None:
        with pytest.raises(UnknownScopeError, match="must be uppercase"):
            parse_scope_tokens(("iva",), catalogue)

    def test_comma_separated_refuses(self, catalogue: ApoderamientosCatalogue) -> None:
        with pytest.raises(UnknownScopeError, match="contains a comma"):
            parse_scope_tokens(("IVA,RENT",), catalogue)


class TestAllTokenExpansion:
    def test_all_token_expands_to_every_code(self, catalogue: ApoderamientosCatalogue) -> None:
        expanded = expand_all_token(catalogue)
        assert set(expanded) == catalogue.code_set()
        # Sorted alphabetically per the contract.
        assert list(expanded) == sorted(expanded)

    def test_parse_with_all_expands_in_place(self, catalogue: ApoderamientosCatalogue) -> None:
        result = parse_scope_tokens((ALL_TOKEN,), catalogue)
        assert set(result) == catalogue.code_set()

    def test_parse_with_all_plus_extras_dedups(self, catalogue: ApoderamientosCatalogue) -> None:
        # ALL expands first; subsequent explicit codes already present are deduped.
        result = parse_scope_tokens((ALL_TOKEN, "IVA"), catalogue)
        assert set(result) == catalogue.code_set()
        # IVA must appear exactly once.
        assert result.count("IVA") == 1
