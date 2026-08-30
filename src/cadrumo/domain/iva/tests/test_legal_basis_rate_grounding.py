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
from typing import cast

import pytest

from ....core.resources import bundled_path
from ...calculations.registry.authority import bundled_authority
from ...invoices.enums import IvaRate, iva_rate_kind, iva_rate_percentage
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
    return cast(dict[str, str | list[str]], data["legal"][article_id])


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
    from .._recargo_equivalencia import _rates_from_catalogue

    parameters = dict(bundled_authority().catalogues.parameters)
    del parameters["liva-art-161:recargo-rate-tabaco"]

    with pytest.raises(IvaCatalogueError, match=r"recargo-rate-tabaco"):
        _rates_from_catalogue(parameters)


# ---------------------------------------------------------------------------
# LIVA art 103.Dos.2.º — mandatory prorrata especial margin (20 % → 10 %)
# ---------------------------------------------------------------------------


def test_liva_art_103_legal_entry_quotes_the_current_ten_per_cent_inclusive_margin() -> None:
    """The catalogue entry must carry the operative sentence verbatim, "o más" included.

    The registry's corpus verification proves the sentence is present in the
    bundled consolidated Ley 37/1992, so this assertion binds the catalogue to
    the BOE wording rather than to a paraphrase.
    """
    required_text = _legal_entry("iva.toml", "ley-37-1992:art-103")["required_text"]
    assert any("exceda en un 10 por ciento o más" in t for t in required_text)


def test_liva_art_103_corpus_records_the_ley_28_2014_amendment_of_apartado_dos() -> None:
    """The bundled consolidated text dates the current redaction, so the year split is grounded, not assumed.

    The amendment note names Ley 28/2014 art. 1.26 as the modifier of apartado
    Dos number 2 — the very subapartado the mandatory-especial predicate reads —
    which is the evidence that a filing year before the amendment is governed by
    a different text.
    """
    required_text = _legal_entry("iva.toml", "ley-37-1992:art-103")["required_text"]
    assert any("art. 1.26 de la Ley 28/2014" in t for t in required_text)
    assert any("apartado 2.2º" in t for t in required_text)


def test_liva_art_103_substrate_margins_match_the_two_boe_redactions() -> None:
    """Both margins and the cutover year must match the BOE figures, not a single blended constant.

    The current figure (10) is the one the bundled corpus quotes; the original
    figure (20) is the one the Ley 37/1992 publication as enacted carried before
    Ley 28/2014 lowered it, and 2015 is that law's stated entry into force.
    """
    from ....core.external_constants import (
        PRORRATA_ESPECIAL_MANDATORY_LEY_28_2014_FIRST_YEAR,
        PRORRATA_ESPECIAL_MANDATORY_MULTIPLE_FROM_2015,
        PRORRATA_ESPECIAL_MANDATORY_MULTIPLE_UNTIL_2014,
    )
    from .._prorrata import especial_mandatory_rule

    declared = (
        PRORRATA_ESPECIAL_MANDATORY_MULTIPLE_FROM_2015,
        PRORRATA_ESPECIAL_MANDATORY_MULTIPLE_UNTIL_2014,
        PRORRATA_ESPECIAL_MANDATORY_LEY_28_2014_FIRST_YEAR,
    )
    assert declared == (Decimal("1.10"), Decimal("1.20"), 2015)

    # The margin the predicate reports is the percentage the provision names.
    assert especial_mandatory_rule(2014).margin_percentage == Decimal("20")
    assert especial_mandatory_rule(2015).margin_percentage == Decimal("10")
    # Only the post-amendment text carries "o más", so only it is inclusive.
    assert especial_mandatory_rule(2015).inclusive is True
    assert especial_mandatory_rule(2014).inclusive is False


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
    from ...fincas.imputacion_parameters import load_imputacion_parameters

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
    assert {
        rate: iva_rate_kind(rate)
        for rate in (
            IvaRate.RATE_0,
            IvaRate.RATE_4,
            IvaRate.RATE_10,
            IvaRate.RATE_21,
            IvaRate.EXEMPT,
            IvaRate.NOT_SUBJECT,
        )
    } == {
        IvaRate.RATE_0: IvaRateKind.ZERO,
        IvaRate.RATE_4: IvaRateKind.SUPER_REDUCED,
        IvaRate.RATE_10: IvaRateKind.REDUCED,
        IvaRate.RATE_21: IvaRateKind.GENERAL,
        IvaRate.EXEMPT: IvaRateKind.EXEMPT,
        IvaRate.NOT_SUBJECT: None,
    }

    for rate, kind in (
        (IvaRate.RATE_4, IvaRateKind.SUPER_REDUCED),
        (IvaRate.RATE_10, IvaRateKind.REDUCED),
        (IvaRate.RATE_21, IvaRateKind.GENERAL),
    ):
        assert lookup_rate(EUMemberState.ES, kind, _BINDING_DATE) is not None
        assert iva_rate_percentage(rate, on_date=_BINDING_DATE) is not None


def test_iva_rate_zero_resolves_to_zero_percent_inside_its_statutory_window() -> None:
    """RATE_0 maps to the ZERO tier, and its percentage is the slot's own zero.

    The number comes from the SLOT, never from a tier lookup: `iva_rate_percentage`
    reads `RATE_0`'s own zero and consults the registry only to CONFIRM a 0 % tipo
    was legally usable that day. Keeping those apart is what stops a declared rate
    being silently replaced by whatever its tier happens to mean -- the defect that
    made a 2 % foodstuffs line compute the super-reducido 4 %.

    So the date must sit INSIDE the statutory window. It previously used the
    module's 2025 `_BINDING_DATE`, which asserted that a 0 % declared in 2025 still
    resolves -- and from 2025-01-01 no general domestic 0 % tipo is in force (the
    basic-foods list returned to 4 % super-reducido). That is a refusal the design
    intends, not a regression: declaring 0 % outside a 0 % window is a claim about
    the law, and `iva_rate_percentage` is the guard that refuses it.
    """
    in_window = date(2024, 8, 20)  # RDL 4/2024 art. 1.Dos.1: 0 % from 07-01 to 09-30
    assert iva_rate_kind(IvaRate.RATE_0) is IvaRateKind.ZERO
    assert iva_rate_percentage(IvaRate.RATE_0, on_date=in_window) == Decimal("0")


def test_iva_rate_zero_resolves_outside_the_food_window_because_zero_rating_outlives_it() -> None:
    """0 % resolves on any date: the registry's zero coverage is partial by design.

    This assertion previously held the OPPOSITE -- that a 0 % outside the RD-ley
    4/2024 food window must refuse -- on the stated premise that the only
    permanent domestic 0 % is LIVA art. 91.Cuatro (donativos to Ley 49/2002
    entities) and that it is "unreachable today".

    That premise is false, and not narrowly. An EXPORT to a third country is
    zero-rated under LIVA art. 21, permanently, and it is reachable through a
    dedicated category the tree already ships and exercises:
    ``IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED``. Three invoice-decomposition
    tests build exactly that invoice, and the refusal broke all three -- an
    export invoice became unrecordable at any date outside one 2024 quarter,
    while the CLI still offered the slot. Intra-community supplies (art. 25) sit
    in the same position.

    The root cause is that ``rates.toml`` models only the food window on the flat
    ``kind = "zero"`` axis, and says so itself: the art. 91.Cuatro tipo is left
    unregistered because a flat record cannot be bounded to donativos. Export and
    intra-EU zero-rating are likewise not expressible there. So the absence of a
    zero record means "this registry cannot say", and testing in-force against a
    knowingly partial authority manufactures refusals for lawful supplies.

    Anti-vacuity is preserved by the sibling above, which pins the resolved VALUE
    inside the window, and by the dated in-force checks on every other tier --
    where registry coverage IS complete and the guard stays sound.
    """
    for on_date in (date(2024, 3, 15), _BINDING_DATE):
        assert iva_rate_percentage(IvaRate.RATE_0, on_date=on_date) == Decimal("0")


def test_iva_rate_exempt_and_not_subject_resolve_to_none() -> None:
    """EXEMPT has a classification tier but no numeric percentage;
    NOT_SUBJECT has neither a rate tier nor a numeric percentage."""
    assert iva_rate_kind(IvaRate.EXEMPT) is IvaRateKind.EXEMPT
    assert iva_rate_kind(IvaRate.NOT_SUBJECT) is None
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
    catalogues = bundled_authority().catalogues
    assert "ley-37-1992:art-90" in catalogues.legal
    assert "ley-37-1992:art-91" in catalogues.legal
    assert "ley-37-1992:art-161" in catalogues.legal
    assert "ley-35-2006:art-85" in catalogues.legal
