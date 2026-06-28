"""Tests for the IvaFlowDirection codification."""

from __future__ import annotations

import tomllib

import pytest

from ....core.resources import bundled_path
from .. import (
    InvoiceKind,
    IvaCategory,
    IvaFlowDirection,
    derive_flow_for_classification,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_iva_flow_direction_enum_has_three_closed_members() -> None:
    assert {m for m in IvaFlowDirection} == {
        IvaFlowDirection.REPERCUTIDO,
        IvaFlowDirection.SOPORTADO,
        IvaFlowDirection.INVERSION_SUJETO_PASIVO,
    }


def test_iva_flow_direction_string_values_are_kebab_case() -> None:
    assert IvaFlowDirection.REPERCUTIDO.value == "repercutido"
    assert IvaFlowDirection.SOPORTADO.value == "soportado"
    assert IvaFlowDirection.INVERSION_SUJETO_PASIVO.value == "inversion_sujeto_pasivo"


@pytest.mark.parametrize(
    ("category", "direction", "expected"),
    [
        (IvaCategory.DOMESTIC_GENERAL_21, InvoiceKind.ISSUED, IvaFlowDirection.REPERCUTIDO),
        (IvaCategory.DOMESTIC_REDUCED_10, InvoiceKind.ISSUED, IvaFlowDirection.REPERCUTIDO),
        (IvaCategory.DOMESTIC_SUPER_REDUCED_4, InvoiceKind.ISSUED, IvaFlowDirection.REPERCUTIDO),
        (IvaCategory.DOMESTIC_ZERO, InvoiceKind.ISSUED, IvaFlowDirection.REPERCUTIDO),
        (IvaCategory.DOMESTIC_EXEMPT, InvoiceKind.ISSUED, IvaFlowDirection.REPERCUTIDO),
        (IvaCategory.RECARGO_EQUIVALENCIA, InvoiceKind.ISSUED, IvaFlowDirection.REPERCUTIDO),
        (IvaCategory.INTRA_COMMUNITY_SUPPLY, InvoiceKind.ISSUED, IvaFlowDirection.REPERCUTIDO),
        (IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED, InvoiceKind.ISSUED, IvaFlowDirection.REPERCUTIDO),
    ],
)
def test_derive_flow_classifies_issued_non_reverse_charge_as_repercutido(
    category: IvaCategory,
    direction: InvoiceKind,
    expected: IvaFlowDirection,
) -> None:
    assert derive_flow_for_classification(category=category, invoice_direction=direction) is expected


@pytest.mark.parametrize(
    ("category", "direction", "expected"),
    [
        (IvaCategory.DOMESTIC_GENERAL_21, InvoiceKind.RECEIVED, IvaFlowDirection.SOPORTADO),
        (IvaCategory.DOMESTIC_REDUCED_10, InvoiceKind.RECEIVED, IvaFlowDirection.SOPORTADO),
        (IvaCategory.DOMESTIC_SUPER_REDUCED_4, InvoiceKind.RECEIVED, IvaFlowDirection.SOPORTADO),
        (IvaCategory.IMPORT_THIRD_COUNTRY, InvoiceKind.RECEIVED, IvaFlowDirection.SOPORTADO),
        (IvaCategory.RECARGO_EQUIVALENCIA, InvoiceKind.RECEIVED, IvaFlowDirection.SOPORTADO),
    ],
)
def test_derive_flow_classifies_received_non_reverse_charge_as_soportado(
    category: IvaCategory,
    direction: InvoiceKind,
    expected: IvaFlowDirection,
) -> None:
    assert derive_flow_for_classification(category=category, invoice_direction=direction) is expected


@pytest.mark.parametrize("direction", [InvoiceKind.ISSUED, InvoiceKind.RECEIVED])
def test_derive_flow_classifies_domestic_reverse_charge_as_autorepercutido(
    direction: InvoiceKind,
) -> None:
    """Domestic reverse-charge (LIVA art 84.Uno.2) routes to INVERSION_SUJETO_PASIVO
    irrespective of invoice direction; the recipient self-assesses."""
    assert (
        derive_flow_for_classification(
            category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
            invoice_direction=direction,
        )
        is IvaFlowDirection.INVERSION_SUJETO_PASIVO
    )


@pytest.mark.parametrize("direction", [InvoiceKind.ISSUED, InvoiceKind.RECEIVED])
def test_derive_flow_classifies_intracomm_acquisition_rc_as_autorepercutido(
    direction: InvoiceKind,
) -> None:
    """Intra-community acquisition reverse-charge (LIVA art 84.Uno.2.e)
    self-assesses both the repercutido and soportado entries on the
    same operation."""
    assert (
        derive_flow_for_classification(
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            invoice_direction=direction,
        )
        is IvaFlowDirection.INVERSION_SUJETO_PASIVO
    )


def test_iva_flow_legal_articles_present_in_registry_toml() -> None:
    """The three LIVA articles backing the flow taxonomy must be in the registry."""
    path = bundled_path("registry", "aeat", "legal", "iva-flow.toml")
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
    path = bundled_path("registry", "aeat", "legal", "iva-flow.toml")
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    legal = data["legal"]
    assert any("Sujetos pasivos" in entry for entry in legal["ley-37-1992:art-84"]["required_text"])
    assert any("Repercusión del impuesto" in entry for entry in legal["ley-37-1992:art-88"]["required_text"])
    assert any("Cuotas tributarias deducibles" in entry for entry in legal["ley-37-1992:art-92"]["required_text"])


def test_iva_flow_corpus_excerpts_present_with_boe_quotes() -> None:
    for art in ("84", "88", "92"):
        # corpus ships under the bundled data root (src/aeat/_data/);
        # resolve via bundled_path, not a CWD-relative path.
        excerpt = bundled_path("corpus", "normatives", "html", f"ley-37-1992-art-{art}.html")
        assert excerpt.exists()
        body = excerpt.read_text(encoding="utf-8")
        assert f"Artículo {art}." in body or f"Artículo&nbsp;{art}." in body


def test_iva_flow_load_registry_recognises_three_articles() -> None:
    """The registry tree loader must surface the three LIVA articles in
    the catalogue."""
    from ...calculations.registry import load_registry_tree

    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    assert "ley-37-1992:art-84" in catalogues.legal
    assert "ley-37-1992:art-88" in catalogues.legal
    assert "ley-37-1992:art-92" in catalogues.legal


# ---------------------------------------------------------------------------
# Devengada vs deducible cornerstone codification
# ---------------------------------------------------------------------------


def test_iva_settlement_side_enum_has_two_closed_members() -> None:
    """IVA settlement rests on two cornerstones — devengada (output IVA
    owed to the Treasury) and deducible (input IVA reclaimable from the
    Treasury). The enum must be closed at exactly these two members."""
    from .. import IvaSettlementSide

    assert {s for s in IvaSettlementSide} == {
        IvaSettlementSide.DEVENGADA,
        IvaSettlementSide.DEDUCIBLE,
    }


def test_iva_settlement_side_string_values_are_kebab_case() -> None:
    from .. import IvaSettlementSide

    assert IvaSettlementSide.DEVENGADA.value == "devengada"
    assert IvaSettlementSide.DEDUCIBLE.value == "deducible"


def test_repercutido_flow_contributes_to_devengada_only() -> None:
    """LIVA art 88 — repercusión charges output IVA to the customer;
    nothing on the deducible side."""
    from .. import IvaSettlementSide, settlement_sides_for_flow

    sides = settlement_sides_for_flow(IvaFlowDirection.REPERCUTIDO)
    assert sides == frozenset({IvaSettlementSide.DEVENGADA})


def test_soportado_flow_contributes_to_deducible_only() -> None:
    """LIVA art 92 — cuotas tributarias deducibles; the sujeto pasivo
    bears IVA via direct repercusión and may deduct it."""
    from .. import IvaSettlementSide, settlement_sides_for_flow

    sides = settlement_sides_for_flow(IvaFlowDirection.SOPORTADO)
    assert sides == frozenset({IvaSettlementSide.DEDUCIBLE})


def test_autorepercutido_flow_contributes_to_both_sides() -> None:
    """LIVA art 84.Uno.2 inversión del sujeto pasivo — the recipient
    self-assesses BOTH a devengada entry and a matching deducible entry
    on the same operation. The two cancel arithmetically inside Modelo
    303 but both must be booked."""
    from .. import IvaSettlementSide, settlement_sides_for_flow

    sides = settlement_sides_for_flow(IvaFlowDirection.INVERSION_SUJETO_PASIVO)
    assert sides == frozenset({IvaSettlementSide.DEVENGADA, IvaSettlementSide.DEDUCIBLE})


def test_devengada_flow_directions_set_matches_devengada_predicate() -> None:
    from .. import DEVENGADA_FLOW_DIRECTIONS, is_devengada_flow

    assert {
        IvaFlowDirection.REPERCUTIDO,
        IvaFlowDirection.INVERSION_SUJETO_PASIVO,
    } == DEVENGADA_FLOW_DIRECTIONS
    for flow in IvaFlowDirection:
        assert is_devengada_flow(flow) == (flow in DEVENGADA_FLOW_DIRECTIONS)


def test_deducible_flow_directions_set_matches_deducible_predicate() -> None:
    from .. import DEDUCIBLE_FLOW_DIRECTIONS, is_deducible_flow

    assert {
        IvaFlowDirection.SOPORTADO,
        IvaFlowDirection.INVERSION_SUJETO_PASIVO,
    } == DEDUCIBLE_FLOW_DIRECTIONS
    for flow in IvaFlowDirection:
        assert is_deducible_flow(flow) == (flow in DEDUCIBLE_FLOW_DIRECTIONS)


def test_devengada_and_deducible_flow_sets_intersect_at_autorepercutido() -> None:
    """The intersection of the two cornerstone flow sets is exactly
    INVERSION_SUJETO_PASIVO — the only flow that contributes to both sides on
    the same operation."""
    from .. import (
        DEDUCIBLE_FLOW_DIRECTIONS,
        DEVENGADA_FLOW_DIRECTIONS,
    )

    assert (
        frozenset({IvaFlowDirection.INVERSION_SUJETO_PASIVO}) == DEVENGADA_FLOW_DIRECTIONS & DEDUCIBLE_FLOW_DIRECTIONS
    )


def test_devengada_and_deducible_flow_sets_union_to_full_flow_taxonomy() -> None:
    """Every flow direction contributes to at least one settlement side —
    the union of the two cornerstone sets covers the full taxonomy."""
    from .. import (
        DEDUCIBLE_FLOW_DIRECTIONS,
        DEVENGADA_FLOW_DIRECTIONS,
    )

    assert set(IvaFlowDirection) == DEVENGADA_FLOW_DIRECTIONS | DEDUCIBLE_FLOW_DIRECTIONS


def test_settlement_sides_mapping_is_total_over_flow_directions() -> None:
    """The settlement-side mapping must cover every IvaFlowDirection
    member — no flow falls through to an unclassified state."""
    from .. import settlement_sides_for_flow

    assert len(list(IvaFlowDirection)) > 0
    covered: set[IvaFlowDirection] = set()
    for flow in IvaFlowDirection:
        sides = settlement_sides_for_flow(flow)
        assert sides, f"{flow!r} maps to empty settlement-side set"
        covered.add(flow)
    assert covered == set(IvaFlowDirection), "every flow direction must be covered"


def test_modelo_303_devengada_formula_matches_devengada_flow_set() -> None:
    """Modelo 303 cuota-devengada-total formula sums repercutido (3 rate
    tiers) + INVERSION_SUJETO_PASIVO — the same flows as DEVENGADA_FLOW_DIRECTIONS.
    This test is a contract gate: if the substrate's devengada set ever
    changes, this test fires unless 303's formula updates in lockstep."""
    from ...calculations.registry import load_registry_tree
    from .. import (
        DEVENGADA_FLOW_DIRECTIONS,
        IvaFlowDirection,
    )

    modelos, _ = load_registry_tree(bundled_path("registry", "aeat"))
    m303 = next(m for m in modelos if m.id == "303")
    revision = m303.revisions["2009-y-siguientes"]

    # Each ledger_iva_aggregation binding declares its flow direction in
    # the selector. Collect the flow directions of all bindings whose
    # cuota contributes to cuota-devengada-total via the formula.
    devengada_formula = next(f for f in revision.formulas if f.id == "modelo-303-iva-cuota-devengada-total")
    casilla_to_binding = {c.id: c.binding for c in revision.casillas if c.binding}
    binding_flows: set[IvaFlowDirection] = set()
    # Walk the formula expression to find casilla operands
    for arg in devengada_formula.expression.args or ():
        casilla_id = arg.casilla_id
        if casilla_id is None or casilla_id not in casilla_to_binding:
            continue
        binding_id = casilla_to_binding[casilla_id]
        binding = next(b for b in revision.bindings if b.id == binding_id)
        flow_value = binding.selector["flow_direction"]
        binding_flows.add(IvaFlowDirection(flow_value))

    assert binding_flows == DEVENGADA_FLOW_DIRECTIONS
