"""Tests for the IvaFlowDirection codification."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from aeat.core.paths import PROJECT_ROOT
from aeat.domain.vat import (
    InvoiceDirection,
    IvaFlowDirection,
    VATCategory,
    derive_flow_for_classification,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_iva_flow_direction_enum_has_three_closed_members() -> None:
    assert {m for m in IvaFlowDirection} == {
        IvaFlowDirection.REPERCUTIDO,
        IvaFlowDirection.SOPORTADO,
        IvaFlowDirection.AUTOREPERCUTIDO,
    }


def test_iva_flow_direction_string_values_are_kebab_case() -> None:
    assert IvaFlowDirection.REPERCUTIDO.value == "repercutido"
    assert IvaFlowDirection.SOPORTADO.value == "soportado"
    assert IvaFlowDirection.AUTOREPERCUTIDO.value == "autorepercutido"


@pytest.mark.parametrize(
    ("category", "direction", "expected"),
    [
        (VATCategory.DOMESTIC_GENERAL_21, InvoiceDirection.ISSUED, IvaFlowDirection.REPERCUTIDO),
        (VATCategory.DOMESTIC_REDUCED_10, InvoiceDirection.ISSUED, IvaFlowDirection.REPERCUTIDO),
        (VATCategory.DOMESTIC_SUPER_REDUCED_4, InvoiceDirection.ISSUED, IvaFlowDirection.REPERCUTIDO),
        (VATCategory.DOMESTIC_ZERO, InvoiceDirection.ISSUED, IvaFlowDirection.REPERCUTIDO),
        (VATCategory.DOMESTIC_EXEMPT, InvoiceDirection.ISSUED, IvaFlowDirection.REPERCUTIDO),
        (VATCategory.RECARGO_EQUIVALENCIA, InvoiceDirection.ISSUED, IvaFlowDirection.REPERCUTIDO),
        (VATCategory.INTRA_COMMUNITY_SUPPLY, InvoiceDirection.ISSUED, IvaFlowDirection.REPERCUTIDO),
        (VATCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED, InvoiceDirection.ISSUED, IvaFlowDirection.REPERCUTIDO),
    ],
)
def test_derive_flow_classifies_issued_non_reverse_charge_as_repercutido(
    category: VATCategory, direction: InvoiceDirection, expected: IvaFlowDirection
) -> None:
    assert derive_flow_for_classification(category=category, invoice_direction=direction) is expected


@pytest.mark.parametrize(
    ("category", "direction", "expected"),
    [
        (VATCategory.DOMESTIC_GENERAL_21, InvoiceDirection.RECEIVED, IvaFlowDirection.SOPORTADO),
        (VATCategory.DOMESTIC_REDUCED_10, InvoiceDirection.RECEIVED, IvaFlowDirection.SOPORTADO),
        (VATCategory.DOMESTIC_SUPER_REDUCED_4, InvoiceDirection.RECEIVED, IvaFlowDirection.SOPORTADO),
        (VATCategory.IMPORT_THIRD_COUNTRY, InvoiceDirection.RECEIVED, IvaFlowDirection.SOPORTADO),
        (VATCategory.RECARGO_EQUIVALENCIA, InvoiceDirection.RECEIVED, IvaFlowDirection.SOPORTADO),
    ],
)
def test_derive_flow_classifies_received_non_reverse_charge_as_soportado(
    category: VATCategory, direction: InvoiceDirection, expected: IvaFlowDirection
) -> None:
    assert derive_flow_for_classification(category=category, invoice_direction=direction) is expected


@pytest.mark.parametrize("direction", [InvoiceDirection.ISSUED, InvoiceDirection.RECEIVED])
def test_derive_flow_classifies_domestic_reverse_charge_as_autorepercutido(
    direction: InvoiceDirection,
) -> None:
    """Domestic reverse-charge (LIVA art 84.Uno.2) routes to AUTOREPERCUTIDO
    irrespective of invoice direction; the recipient self-assesses."""
    assert (
        derive_flow_for_classification(
            category=VATCategory.DOMESTIC_REVERSE_CHARGE,
            invoice_direction=direction,
        )
        is IvaFlowDirection.AUTOREPERCUTIDO
    )


@pytest.mark.parametrize("direction", [InvoiceDirection.ISSUED, InvoiceDirection.RECEIVED])
def test_derive_flow_classifies_intracomm_acquisition_rc_as_autorepercutido(
    direction: InvoiceDirection,
) -> None:
    """Intra-community acquisition reverse-charge (LIVA art 84.Uno.2.e)
    self-assesses both the repercutido and soportado entries on the
    same operation."""
    assert (
        derive_flow_for_classification(
            category=VATCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            invoice_direction=direction,
        )
        is IvaFlowDirection.AUTOREPERCUTIDO
    )


def test_iva_flow_legal_articles_present_in_registry_toml() -> None:
    """The three LIVA articles backing the flow taxonomy must be in the registry."""
    path = PROJECT_ROOT / "registry" / "aeat" / "legal" / "iva-flow.toml"
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    legal = data.get("legal", {})
    assert "ley-37-1992:art-84" in legal
    assert "ley-37-1992:art-88" in legal
    assert "ley-37-1992:art-92" in legal


def test_iva_flow_legal_articles_carry_required_text_quotes() -> None:
    """The three LIVA articles must declare required_text quotes that match
    the BOE-cited content (so the registry validator's text gate fires
    on drift)."""
    path = PROJECT_ROOT / "registry" / "aeat" / "legal" / "iva-flow.toml"
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    legal = data["legal"]
    assert any("Sujetos pasivos" in entry for entry in legal["ley-37-1992:art-84"]["required_text"])
    assert any(
        "Repercusión del impuesto" in entry
        for entry in legal["ley-37-1992:art-88"]["required_text"]
    )
    assert any(
        "Cuotas tributarias deducibles" in entry
        for entry in legal["ley-37-1992:art-92"]["required_text"]
    )


def test_iva_flow_corpus_excerpts_present_with_boe_quotes() -> None:
    for art in ("84", "88", "92"):
        excerpt = Path(f"corpus/normatives/html/ley-37-1992-art-{art}.html")
        assert excerpt.exists()
        body = excerpt.read_text(encoding="utf-8")
        assert f"Artículo {art}." in body or f"Artículo&nbsp;{art}." in body


def test_iva_flow_load_registry_recognises_three_articles() -> None:
    """The registry tree loader must surface the three LIVA articles in
    the catalogue."""
    from aeat.domain.calculations.registry import load_registry_tree

    _, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    assert "ley-37-1992:art-84" in catalogues.legal
    assert "ley-37-1992:art-88" in catalogues.legal
    assert "ley-37-1992:art-92" in catalogues.legal
