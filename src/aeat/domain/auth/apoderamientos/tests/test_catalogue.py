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


def test_default_catalogue_loads_registry_invariants(catalogue: ApoderamientosCatalogue) -> None:
    assert catalogue.catalogue_version.startswith("2026")
    assert len(catalogue.scopes) >= 5
    codes = catalogue.code_set()
    assert {"IVA", "RENT", "CENSO"} <= codes
    for scope in catalogue.scopes:
        assert scope.code == scope.code.upper(), scope.code
    iva = catalogue.get("IVA")
    assert iva is not None
    assert {"303", "390"} <= set(iva.modelo_codes)


def test_parse_scope_tokens_accepts_known_tokens_and_deduplicates(catalogue: ApoderamientosCatalogue) -> None:
    cases = (
        (("IVA",), ("IVA",)),
        (("IVA", "RENT", "CENSO"), ("IVA", "RENT", "CENSO")),
        (("IVA", "RENT", "IVA"), ("IVA", "RENT")),
    )

    for raw_tokens, expected in cases:
        assert parse_scope_tokens(raw_tokens, catalogue) == expected, raw_tokens


def test_parse_scope_tokens_rejects_invalid_operator_tokens(catalogue: ApoderamientosCatalogue) -> None:
    cases = (
        (("BOGUS",), "not in catalogue"),
        (("iva",), "must be uppercase"),
        (("IVA,RENT",), "contains a comma"),
    )

    for raw_tokens, expected_match in cases:
        with pytest.raises(UnknownScopeError, match=expected_match):
            parse_scope_tokens(raw_tokens, catalogue)


def test_all_token_expansion_is_sorted_and_deduplicated(catalogue: ApoderamientosCatalogue) -> None:
    expanded = expand_all_token(catalogue)
    assert set(expanded) == catalogue.code_set()
    assert list(expanded) == sorted(expanded)

    for raw_tokens in ((ALL_TOKEN,), (ALL_TOKEN, "IVA")):
        result = parse_scope_tokens(raw_tokens, catalogue)
        assert set(result) == catalogue.code_set(), raw_tokens
        assert result.count("IVA") == 1, raw_tokens
