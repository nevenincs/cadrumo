"""Tests for the apoderamientos scope catalogue and parser."""

from __future__ import annotations

import pytest

from ..catalogue import (
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


@pytest.mark.parametrize(
    ("raw_tokens", "expected"),
    (
        (("IVA",), ("IVA",)),
        (("IVA", "RENT", "CENSO"), ("IVA", "RENT", "CENSO")),
        (("IVA", "RENT", "IVA"), ("IVA", "RENT")),
    ),
)
def test_parse_scope_tokens_accepts_known_tokens_and_deduplicates(
    catalogue: ApoderamientosCatalogue,
    raw_tokens: tuple[str, ...],
    expected: tuple[str, ...],
) -> None:
    assert parse_scope_tokens(raw_tokens, catalogue) == expected


@pytest.mark.parametrize(
    ("raw_tokens", "expected_context"),
    (
        (
            ("BOGUS",),
            {"scope_token": "BOGUS", "validation_rule": "declared_catalogue_code"},
        ),
        (("iva",), {"scope_token": "iva", "validation_rule": "uppercase"}),
        (
            ("IVA,RENT",),
            {"scope_token": "IVA,RENT", "validation_rule": "no_comma_separated_values"},
        ),
    ),
)
def test_parse_scope_tokens_rejects_invalid_operator_tokens(
    catalogue: ApoderamientosCatalogue,
    raw_tokens: tuple[str, ...],
    expected_context: dict[str, str],
) -> None:
    # The validation_rule fact distinguishes the three refusals; the sentence
    # that used to carry that distinction is catalogue-rendered now.
    with pytest.raises(UnknownScopeError) as excinfo:
        parse_scope_tokens(raw_tokens, catalogue)

    expected_context_with_version = expected_context.copy()
    if expected_context["validation_rule"] == "declared_catalogue_code":
        expected_context_with_version["catalogue_version"] = catalogue.catalogue_version
    assert excinfo.value.context == expected_context_with_version
    assert not hasattr(excinfo.value, "suggestion")


def test_all_token_expansion_is_sorted_and_deduplicated(catalogue: ApoderamientosCatalogue) -> None:
    expanded = expand_all_token(catalogue)
    assert set(expanded) == catalogue.code_set()
    assert list(expanded) == sorted(expanded)


@pytest.mark.parametrize("raw_tokens", ((ALL_TOKEN,), (ALL_TOKEN, "IVA")))
def test_parse_scope_tokens_expands_all_token_without_duplicates(
    catalogue: ApoderamientosCatalogue,
    raw_tokens: tuple[str, ...],
) -> None:
    result = parse_scope_tokens(raw_tokens, catalogue)
    assert set(result) == catalogue.code_set()
    assert result.count("IVA") == 1
