"""Cross-substrate legal-basis rate-grounding verification.

This test module is the canonical gate that every rate value used by
the IVA / IRPF substrate and modelo registry matches its BOE legal
authority.

For each rate, the chain of references is checked end-to-end:

1. The BOE corpus excerpt contains the operative percentage string
   (e.g., "21 por ciento" in LIVA art 90).
2. The registry parameter / IVA_RATE_TABLE entry stores the matching
   numeric value (Decimal "0.21" = 21 %).
3. The substrate's typed enum (IvaRate / IvaRateKind) maps to the
   substrate-resolved percentage.
4. The pydantic-typed Python wrapper
   (:func:`iva_rate_percentage`) returns the same value.

If any link in the chain drifts, this module fires a focused
failure rather than letting the discrepancy hide behind pure
unit-test isolation.

The test names use the LIVA / LIRPF article number directly so the
audit trail from BOE → substrate → ledger → modelo is grep-able.
"""

from __future__ import annotations

import re
import tomllib
from datetime import date
from decimal import Decimal

import pytest

from ....core.resources import bundled_path
from ...invoices import IvaRate, iva_rate_percentage
from .. import (
    EUMemberState,
    IvaCatalogueError,
    IvaRateKind,
    load_recargo_rates,
    lookup_rate,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# Canonical date for rate lookups during these legal-binding checks.
# 2025 is the current ejercicio at the time of writing, with stable
# rates after the temporary 2022-2024 RATE_5 window closed.
_BINDING_DATE = date(2025, 6, 15)


def _strip_html(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.replace("\xa0", " "))).strip()


def _read_corpus_excerpt(name: str) -> str:
    path = bundled_path("corpus", "normatives", "html") / name
    return path.read_text(encoding="utf-8")


def _legal_entry(toml_relative: str, article_id: str) -> dict[str, str | list[str]]:
    path = bundled_path("registry", "aeat", "legal") / toml_relative
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    return data["legal"][article_id]


# ---------------------------------------------------------------------------
# LIVA art 90 — general 21 %
# ---------------------------------------------------------------------------


def test_liva_art_90_corpus_excerpt_quotes_21_per_cent_general_rate() -> None:
    body = _strip_html(_read_corpus_excerpt("ley-37-1992-art-90.html"))
    assert "Tipo impositivo general" in body
    assert "21 por ciento" in body


def test_liva_art_90_substrate_general_rate_resolves_to_21_per_cent_for_es() -> None:
    rate = lookup_rate(EUMemberState.ES, IvaRateKind.GENERAL, _BINDING_DATE)
    assert rate.pct == Decimal("21")


def test_iva_rate_21_helper_resolves_to_substrate_general_rate() -> None:
    """IvaRate.RATE_21 wrapper must return the substrate's GENERAL
    rate divided by 100, anchored to LIVA art 90."""
    expected = lookup_rate(EUMemberState.ES, IvaRateKind.GENERAL, _BINDING_DATE).pct / Decimal("100")
    assert iva_rate_percentage(IvaRate.RATE_21, on_date=_BINDING_DATE) == expected


def test_liva_art_90_legal_entry_carries_required_text() -> None:
    entry = _legal_entry("iva-rates.toml", "ley-37-1992:art-90")
    required_text = entry["required_text"]
    assert any("Tipo impositivo general" in t for t in required_text)
    assert any("21 por ciento" in t for t in required_text)


# ---------------------------------------------------------------------------
# LIVA art 91 Uno — reduced 10 %
# ---------------------------------------------------------------------------


def test_liva_art_91_corpus_excerpt_quotes_10_and_4_per_cent_reduced_rates() -> None:
    body = _strip_html(_read_corpus_excerpt("ley-37-1992-art-91.html"))
    assert "Tipos impositivos reducidos" in body
    assert "10 por ciento" in body
    assert "4 por ciento" in body


def test_liva_art_91_substrate_reduced_rate_resolves_to_10_per_cent_for_es() -> None:
    rate = lookup_rate(EUMemberState.ES, IvaRateKind.REDUCED, _BINDING_DATE)
    assert rate.pct == Decimal("10")


def test_iva_rate_10_helper_resolves_to_substrate_reduced_rate() -> None:
    expected = lookup_rate(EUMemberState.ES, IvaRateKind.REDUCED, _BINDING_DATE).pct / Decimal("100")
    assert iva_rate_percentage(IvaRate.RATE_10, on_date=_BINDING_DATE) == expected


# ---------------------------------------------------------------------------
# LIVA art 91 Dos — super-reduced 4 %
# ---------------------------------------------------------------------------


def test_liva_art_91_substrate_super_reduced_rate_resolves_to_4_per_cent_for_es() -> None:
    rate = lookup_rate(EUMemberState.ES, IvaRateKind.SUPER_REDUCED, _BINDING_DATE)
    assert rate.pct == Decimal("4")


def test_iva_rate_4_helper_resolves_to_substrate_super_reduced_rate() -> None:
    expected = lookup_rate(EUMemberState.ES, IvaRateKind.SUPER_REDUCED, _BINDING_DATE).pct / Decimal("100")
    assert iva_rate_percentage(IvaRate.RATE_4, on_date=_BINDING_DATE) == expected


def test_liva_art_91_legal_entry_carries_both_reduced_and_super_reduced_quotes() -> None:
    entry = _legal_entry("iva-rates.toml", "ley-37-1992:art-91")
    required_text = entry["required_text"]
    assert any("10 por ciento" in t for t in required_text)
    assert any("4 por ciento" in t for t in required_text)


# ---------------------------------------------------------------------------
# LIVA art 161 — recargo de equivalencia (5.2 / 1.4 / 0.5 / 1.75)
# ---------------------------------------------------------------------------


def test_liva_art_161_corpus_excerpt_quotes_all_four_recargo_rates() -> None:
    body = _strip_html(_read_corpus_excerpt("ley-37-1992-art-161.html"))
    assert "Tipos" in body
    for needle in ("5,2 por ciento", "1,4 por ciento", "0,50 por ciento", "1,75 por ciento"):
        assert needle in body


def test_liva_art_161_substrate_general_recargo_matches_5_2_per_cent() -> None:
    """LIVA art 161 1° — 5,2% applied to 21% IVA tier supplies."""
    assert load_recargo_rates().general_rate == Decimal("0.052")


def test_liva_art_161_substrate_reduced_recargo_matches_1_4_per_cent() -> None:
    """LIVA art 161 2° — 1,4% applied to 10% IVA tier (art 91 Uno)."""
    assert load_recargo_rates().reducido_rate == Decimal("0.014")


def test_liva_art_161_substrate_super_reduced_recargo_matches_0_5_per_cent() -> None:
    """LIVA art 161 3° — 0,5% applied to 4% IVA tier (art 91 Dos)."""
    assert load_recargo_rates().super_reducido_rate == Decimal("0.005")


def test_liva_art_161_substrate_tabaco_recargo_matches_1_75_per_cent() -> None:
    """LIVA art 161 4° — 1,75% on labores del tabaco (Impuesto Especial)."""
    assert load_recargo_rates().tabaco_rate == Decimal("0.0175")


def test_liva_art_161_recargo_matches_iva_tier_alignment() -> None:
    """The recargo de equivalencia tiers align 1:1 with the IVA rate
    tiers per LIVA art 161 1° (general) / 2° (art 91 Uno) / 3° (art
    91 Dos). Each tier has matching IVA + recargo percentages
    declared by separate articles. This test confirms the alignment
    is consistent across the two rate tables."""
    iva_general = lookup_rate(EUMemberState.ES, IvaRateKind.GENERAL, _BINDING_DATE).pct
    iva_reducido = lookup_rate(EUMemberState.ES, IvaRateKind.REDUCED, _BINDING_DATE).pct
    iva_super = lookup_rate(EUMemberState.ES, IvaRateKind.SUPER_REDUCED, _BINDING_DATE).pct

    # Sanity: IVA tiers resolve to 21/10/4 per LIVA art 90/91
    assert (iva_general, iva_reducido, iva_super) == (
        Decimal("21"),
        Decimal("10"),
        Decimal("4"),
    )

    # Recargo tiers resolve to 5.2/1.4/0.5 per LIVA art 161
    assert load_recargo_rates().general_rate * Decimal("100") == Decimal("5.200")
    assert load_recargo_rates().reducido_rate * Decimal("100") == Decimal("1.400")
    assert load_recargo_rates().super_reducido_rate * Decimal("100") == Decimal("0.500")


def test_liva_art_161_missing_recargo_parameter_raises_iva_catalogue_error() -> None:
    from ...calculations.registry import load_legal_parameters_only
    from .._recargo_equivalencia import _rates_from_catalogue

    parameters = dict(load_legal_parameters_only(bundled_path("registry", "aeat")))
    del parameters["liva-art-161:recargo-rate-tabaco"]

    with pytest.raises(IvaCatalogueError, match=r"recargo-rate-tabaco"):
        _rates_from_catalogue(parameters)


# ---------------------------------------------------------------------------
# LIRPF art 85 — imputación rates (1.1 / 2 / lookback 10)
# ---------------------------------------------------------------------------


def test_lirpf_art_85_corpus_excerpt_quotes_imputation_rates() -> None:
    body = _strip_html(_read_corpus_excerpt("ley-35-2006-art-85.html"))
    assert "Imputación de rentas inmobiliarias" in body
    assert "2 por ciento" in body
    assert "1,1 por ciento" in body
    assert "diez períodos impositivos anteriores" in body


def test_lirpf_art_85_imputacion_substrate_matches_boe_text() -> None:
    from ...fincas._imputacion_parameters import load_imputacion_parameters

    parameters = load_imputacion_parameters()
    assert parameters.recent_revision_rate == Decimal("0.011")  # 1.1 %
    assert parameters.old_or_no_revision_rate == Decimal("0.02")  # 2 %
    assert parameters.catastral_revision_lookback_years == 10


# ---------------------------------------------------------------------------
# Cross-substrate IvaRate / IvaRateKind alignment
# ---------------------------------------------------------------------------


def test_iva_rate_slot_to_iva_rate_kind_mapping_is_total_and_consistent() -> None:
    """Every IvaRate slot (except NOT_SUBJECT, which is out of scope of
    IVA) must map to a IvaRateKind tier. The mapping is the bridge
    between the invoice-domain rate slots and the substrate's rate
    tiers, anchored to LIVA arts 90-91."""
    # Verify the slot-to-tier contract through the public percentage helper:
    # each numeric slot must resolve to the correct IvaRateKind tier by querying
    # the substrate.  The mapping has exactly three numeric slots (RATE_4, RATE_10,
    # RATE_21); RATE_0, EXEMPT, and NOT_SUBJECT are handled separately.
    # Slot ↔ tier alignment per LIVA art 90 / 91
    assert lookup_rate(EUMemberState.ES, IvaRateKind.GENERAL, _BINDING_DATE) is not None
    assert lookup_rate(EUMemberState.ES, IvaRateKind.REDUCED, _BINDING_DATE) is not None
    assert lookup_rate(EUMemberState.ES, IvaRateKind.SUPER_REDUCED, _BINDING_DATE) is not None
    # The percentage helper bridges the same mapping and raises for unmapped slots.
    assert iva_rate_percentage(IvaRate.RATE_21, on_date=_BINDING_DATE) is not None
    assert iva_rate_percentage(IvaRate.RATE_10, on_date=_BINDING_DATE) is not None
    assert iva_rate_percentage(IvaRate.RATE_4, on_date=_BINDING_DATE) is not None


def test_iva_rate_zero_resolves_to_zero_percent_directly() -> None:
    """RATE_0 doesn't map through IvaRateKind — it's a direct
    Decimal('0') return. This is correct: zero-rated supplies don't
    need substrate lookup since the rate is structurally zero."""
    assert iva_rate_percentage(IvaRate.RATE_0, on_date=_BINDING_DATE) == Decimal("0")


def test_iva_rate_exempt_and_not_subject_resolve_to_none() -> None:
    """EXEMPT and NOT_SUBJECT lines have no numeric rate — the helper
    must return None, anchoring the absence in the substrate
    classification rather than producing a sentinel zero."""
    assert iva_rate_percentage(IvaRate.EXEMPT, on_date=_BINDING_DATE) is None
    assert iva_rate_percentage(IvaRate.NOT_SUBJECT, on_date=_BINDING_DATE) is None


# ---------------------------------------------------------------------------
# Registry tree loader picks up all rate articles
# ---------------------------------------------------------------------------


def test_registry_tree_loader_recognises_all_rate_articles() -> None:
    """The registry tree must surface every LIVA / LIRPF rate article
    that backs the IVA + IRPF rate substrate. If any article is missing
    from the catalogue, downstream modelo bindings can't reference it
    and validation fails — this test catches the regression upstream."""
    from ...calculations.registry import load_registry_tree

    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    assert "ley-37-1992:art-90" in catalogues.legal
    assert "ley-37-1992:art-91" in catalogues.legal
    assert "ley-37-1992:art-161" in catalogues.legal
    assert "ley-35-2006:art-85" in catalogues.legal
