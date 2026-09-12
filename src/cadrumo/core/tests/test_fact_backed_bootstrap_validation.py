"""Typed validation boundaries for the fact-backed core catalogues."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from .. import modelo as modelo_module
from .. import tax_domain as tax_domain_module
from ..errors.hierarchy import CadrumoError, CoreValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _assert_core_validation(operation: object, message: str) -> None:
    with pytest.raises(CoreValidationError, match=message) as caught:
        operation()  # type: ignore[operator]
    assert isinstance(caught.value, ValueError)
    assert isinstance(caught.value, CadrumoError)
    assert caught.value.code.code == "INTEGRITY_CADRUMO_CORE_VALIDATION"


def test_empty_modelo_csv_uses_typed_core_validation() -> None:
    _assert_core_validation(lambda: modelo_module._csv(""), "must not be empty")


@pytest.mark.parametrize(
    ("declarations", "message"),
    [
        ({"catalogue.codes": "001,001"}, "must be unique"),
        ({"catalogue.codes": "01A"}, "three-digit strings"),
    ],
)
def test_modelo_catalogue_bootstrap_validation_is_typed(
    monkeypatch: pytest.MonkeyPatch,
    declarations: dict[str, str],
    message: str,
) -> None:
    monkeypatch.setattr(modelo_module, "_DECLARATIONS", declarations)
    _assert_core_validation(modelo_module._build_modelo_type, message)


def test_modelo_fact_without_variants_is_typed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fact_path = tmp_path / "modelo.toml"
    fact_path.write_text("[fact]\nvariants = []\n", encoding="utf-8")
    monkeypatch.setattr(modelo_module, "_FACT_PATH", fact_path)
    _assert_core_validation(modelo_module._fact_declarations, "has no variants")


@pytest.mark.parametrize(
    ("declarations", "message"),
    [
        (
            {"catalogue.codes": "001", "scope.group.missing_reason.codes": "001"},
            "has no reason",
        ),
        (
            {
                "catalogue.codes": "001",
                "scope.code.001.reason": "explicit",
                "scope.group.conflict.codes": "001",
                "scope.group.conflict.reason": "group",
            },
            "has conflicting reasons",
        ),
        (
            {"catalogue.codes": "001", "scope.code.999.reason": "unknown"},
            "unknown codes",
        ),
    ],
)
def test_modelo_scope_declaration_validation_is_typed(
    monkeypatch: pytest.MonkeyPatch,
    declarations: dict[str, str],
    message: str,
) -> None:
    monkeypatch.setattr(modelo_module, "_DECLARATIONS", declarations)
    _assert_core_validation(modelo_module._scope_reasons, message)


@pytest.mark.parametrize(
    ("suppressed_codes", "registry_out_of_scope_codes", "message"),
    [
        ({"001"}, set(), "suppressed Modelo codes"),
        (set(), {"001"}, "registry out-of-scope Modelo codes"),
    ],
)
def test_modelo_scope_partition_validation_is_typed(
    suppressed_codes: set[str],
    registry_out_of_scope_codes: set[str],
    message: str,
) -> None:
    _assert_core_validation(
        lambda: modelo_module._validate_scope_partitions(
            {"002": "declared"},
            suppressed_codes,
            registry_out_of_scope_codes,
        ),
        message,
    )


def _tax_fact(codes: str) -> str:
    return (
        "[fact]\n"
        "[[fact.variants]]\n"
        "[fact.variants.payload]\n"
        'entries = [{ key = "catalogue.codes", value = "'
        f"{codes}"
        '" }]\n'
    )


@pytest.mark.parametrize("codes", ["censo, censo", " , "])
def test_tax_domain_catalogue_validation_is_typed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    codes: str,
) -> None:
    fact_path = tmp_path / "tax-domain.toml"
    fact_path.write_text(_tax_fact(codes), encoding="utf-8")
    monkeypatch.setattr(tax_domain_module, "_FACT_PATH", fact_path)
    _assert_core_validation(tax_domain_module._catalogue_codes, "unique and non-empty")


def test_native_toml_errors_remain_unmasked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fact_path = tmp_path / "invalid.toml"
    fact_path.write_text("[fact\n", encoding="utf-8")
    monkeypatch.setattr(tax_domain_module, "_FACT_PATH", fact_path)
    with pytest.raises(tomllib.TOMLDecodeError):
        tax_domain_module._catalogue_codes()


def test_real_fact_backed_catalogues_remain_positive_controls() -> None:
    assert len(modelo_module.Modelo) == 149
    assert modelo_module.Modelo.M037.value == "037"
    assert modelo_module.Modelo.M179.value == "179"
    assert len(tax_domain_module.TaxDomain) == 14
    assert tax_domain_module.TaxDomain.CENSO.value == "censo"
