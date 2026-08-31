"""Tests for the IVA flow-direction and settlement-side codification.

The suite pins :class:`~domain.iva.IvaFlowDirection`,
:class:`~domain.iva.IvaSettlementSide`,
:func:`~domain.iva.derive_flow_for_classification`, and the Modelo 303
devengada binding formula against the LIVA-backed flow taxonomy. It verifies
that repercutido, soportado, and inversión del sujeto pasivo stay aligned across
the domain substrate, registry legal excerpts, and modelo aggregation bindings.

See Also:
    :mod:`~domain.iva._flow`
        Flow-direction enum, settlement-side mapping, and canonical predicates
        under test.
    :mod:`~application.aggregation._iva_ledger`
        Ledger aggregation consumer that recomputes effective IVA flow for
        modelo observations.
    :mod:`~domain.calculations.registry._bindings`
        Registry binding resolver layer that consumes typed IVA aggregation
        dimensions.
"""

from __future__ import annotations

import tomllib

import pytest

from ....core.resources import bundled_path
from ...calculations.registry.authority import bundled_authority
from ...calculations.registry.binding_selector_utils import selector_as_dict
from .. import (
    InvoiceKind,
    IvaCategory,
    IvaFlowDirection,
    derive_flow_for_classification,
    is_deducible_flow,
    is_devengada_flow,
    settlement_sides_for_flow,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_iva_flow_direction_enum_has_four_closed_members() -> None:
    """The axis carries both sides of a reverse-charge operation, not just one.

    The fourth member is the SUPPLIER's side. Before it existed the axis could
    not express "turnover bearing no cuota on either side", so a supplier's own
    reverse-charge invoice was routed to the recipient's member and self-assessed
    as though the supplier owed the cuota it had deliberately not charged.
    """
    assert {m for m in IvaFlowDirection} == {
        IvaFlowDirection.REPERCUTIDO,
        IvaFlowDirection.SOPORTADO,
        IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        IvaFlowDirection.OPERACION_CON_INVERSION,
    }


def test_iva_flow_direction_string_values_are_kebab_case() -> None:
    assert IvaFlowDirection.REPERCUTIDO.value == "repercutido"
    assert IvaFlowDirection.SOPORTADO.value == "soportado"
    assert IvaFlowDirection.INVERSION_SUJETO_PASIVO.value == "inversion_sujeto_pasivo"
    assert IvaFlowDirection.OPERACION_CON_INVERSION.value == "operacion_con_inversion"


@pytest.mark.parametrize(
    ("category", "direction", "expected"),
    (
        pytest.param(
            IvaCategory.DOMESTIC_GENERAL,
            InvoiceKind.ISSUED,
            IvaFlowDirection.REPERCUTIDO,
            id="issued-general",
        ),
        pytest.param(
            IvaCategory.DOMESTIC_REDUCED,
            InvoiceKind.ISSUED,
            IvaFlowDirection.REPERCUTIDO,
            id="issued-reduced",
        ),
        pytest.param(
            IvaCategory.DOMESTIC_SUPER_REDUCED,
            InvoiceKind.ISSUED,
            IvaFlowDirection.REPERCUTIDO,
            id="issued-super-reduced",
        ),
        pytest.param(
            IvaCategory.DOMESTIC_ZERO,
            InvoiceKind.ISSUED,
            IvaFlowDirection.REPERCUTIDO,
            id="issued-zero",
        ),
        pytest.param(
            IvaCategory.DOMESTIC_EXEMPT,
            InvoiceKind.ISSUED,
            IvaFlowDirection.REPERCUTIDO,
            id="issued-exempt",
        ),
        pytest.param(
            IvaCategory.RECARGO_EQUIVALENCIA,
            InvoiceKind.ISSUED,
            IvaFlowDirection.REPERCUTIDO,
            id="issued-recargo",
        ),
        pytest.param(
            IvaCategory.INTRA_COMMUNITY_SUPPLY,
            InvoiceKind.ISSUED,
            IvaFlowDirection.REPERCUTIDO,
            id="issued-intracom-supply",
        ),
        pytest.param(
            IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
            InvoiceKind.ISSUED,
            IvaFlowDirection.REPERCUTIDO,
            id="issued-export-third-country",
        ),
        pytest.param(
            IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED,
            InvoiceKind.ISSUED,
            IvaFlowDirection.REPERCUTIDO,
            id="issued-export-assimilated",
        ),
        pytest.param(
            IvaCategory.DOMESTIC_GENERAL,
            InvoiceKind.RECEIVED,
            IvaFlowDirection.SOPORTADO,
            id="received-general",
        ),
        pytest.param(
            IvaCategory.DOMESTIC_REDUCED,
            InvoiceKind.RECEIVED,
            IvaFlowDirection.SOPORTADO,
            id="received-reduced",
        ),
        pytest.param(
            IvaCategory.DOMESTIC_SUPER_REDUCED,
            InvoiceKind.RECEIVED,
            IvaFlowDirection.SOPORTADO,
            id="received-super-reduced",
        ),
        pytest.param(
            IvaCategory.IMPORT_THIRD_COUNTRY,
            InvoiceKind.RECEIVED,
            IvaFlowDirection.SOPORTADO,
            id="received-import-third-country",
        ),
        pytest.param(
            IvaCategory.RECARGO_EQUIVALENCIA,
            InvoiceKind.RECEIVED,
            IvaFlowDirection.SOPORTADO,
            id="received-recargo",
        ),
    ),
)
def test_derive_flow_classifies_non_reverse_charge_categories(
    category: IvaCategory,
    direction: InvoiceKind,
    expected: IvaFlowDirection,
) -> None:
    assert derive_flow_for_classification(category=category, invoice_direction=direction) is expected


def test_received_domestic_reverse_charge_self_assesses() -> None:
    """The RECIPIENT of a domestic art. 84.Uno.2 operation is the sujeto pasivo."""
    assert (
        derive_flow_for_classification(
            category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
            invoice_direction=InvoiceKind.RECEIVED,
        )
        is IvaFlowDirection.INVERSION_SUJETO_PASIVO
    )


def test_issued_domestic_reverse_charge_is_the_suppliers_side_not_a_self_assessment() -> None:
    """A domestic RC supply the taxpayer MADE settles on neither side.

    This assertion previously held the OPPOSITE — that both directions route to
    INVERSION_SUJETO_PASIVO — and encoded a live mis-declaration as the contract.
    A Spanish construction subcontractor invoicing under LIVA art. 84.Uno.2.f
    charges no IVA and bears none; the recipient self-assesses. Booking the
    supplier's own invoice as a self-assessment inflated Modelo 303 box [13] and
    both cuota totals, and claimed a deduction of input IVA the supplier never
    bore. The two errors cancel in the resultado, which is why nothing caught it.
    """
    assert (
        derive_flow_for_classification(
            category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
            invoice_direction=InvoiceKind.ISSUED,
        )
        is IvaFlowDirection.OPERACION_CON_INVERSION
    )


def test_a_supplier_side_reverse_charge_operation_reaches_no_settlement_side() -> None:
    """The tripwire for the whole ruling: neither cuota total may claim it.

    Routing this flow to DEVENGADA invents an output cuota never charged; routing
    it to DEDUCIBLE invents a deduction of input IVA never borne. Both are money
    the taxpayer would file. This test reds if a later change puts the supplier's
    side back on either side of the settlement.
    """
    assert settlement_sides_for_flow(IvaFlowDirection.OPERACION_CON_INVERSION) == frozenset()
    assert not is_devengada_flow(IvaFlowDirection.OPERACION_CON_INVERSION)
    assert not is_deducible_flow(IvaFlowDirection.OPERACION_CON_INVERSION)


@pytest.mark.parametrize(
    "direction",
    (
        pytest.param(InvoiceKind.ISSUED, id="issued"),
        pytest.param(InvoiceKind.RECEIVED, id="received"),
    ),
)
def test_derive_flow_classifies_intracomm_acquisition_rc_as_autorepercutido(direction: InvoiceKind) -> None:
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


@pytest.mark.parametrize(
    "direction",
    (
        pytest.param(InvoiceKind.ISSUED, id="issued"),
        pytest.param(InvoiceKind.RECEIVED, id="received"),
    ),
)
def test_derive_flow_classifies_intracomm_service_acquisition_rc_as_autorepercutido(
    direction: InvoiceKind,
) -> None:
    """A B2B service received from an EU supplier self-assesses like the goods case.

    Art. 69.Uno.1.o locates the service in Spain because the recipient is
    established here, and art. 84.Uno.2.o makes that recipient the sujeto
    pasivo -- the same position as the intra-community goods acquisition
    above, so the same flow.
    """
    assert (
        derive_flow_for_classification(
            category=IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
            invoice_direction=direction,
        )
        is IvaFlowDirection.INVERSION_SUJETO_PASIVO
    )


def test_received_eu_service_reaches_the_devengada_side_not_only_the_deducible() -> None:
    """The under-declaration this guards is silent, so name it explicitly.

    Falling through to SOPORTADO would reach DEDUCIBLE alone, so the taxpayer
    would deduct the input IVA while the matching self-assessed output IVA
    never lands on the devengada side at all. That is a structural
    under-declaration on Modelo 303, not a casilla mix-up, and it is invisible
    from the value of any single casilla.
    """
    from .. import IvaSettlementSide, is_deducible_flow, is_devengada_flow, settlement_sides_for_flow

    flow = derive_flow_for_classification(
        category=IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
        invoice_direction=InvoiceKind.RECEIVED,
    )
    assert settlement_sides_for_flow(flow) == frozenset(
        {IvaSettlementSide.DEVENGADA, IvaSettlementSide.DEDUCIBLE},
    )
    assert is_devengada_flow(flow), "the self-assessed cuota must be declared, not only deducted"
    assert is_deducible_flow(flow)


def test_intracomm_service_supply_is_not_a_reverse_charge_for_the_spanish_supplier() -> None:
    """The supply counterpart must NOT self-assess, and the asymmetry is the point.

    Sweeping both service categories into the reverse-charge set would be the
    obvious over-correction: here the operation is not located in Spain at all
    (art. 69.Uno.1.o places it where the recipient is established), so no
    Spanish cuota arises for the supplier to self-assess. The recipient
    self-assesses in their own Member State.
    """
    assert (
        derive_flow_for_classification(
            category=IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY,
            invoice_direction=InvoiceKind.ISSUED,
        )
        is IvaFlowDirection.REPERCUTIDO
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
        # corpus ships under the bundled data root (src/cadrumo/_data/);
        # resolve via bundled_path, not a CWD-relative path.
        excerpt = bundled_path("corpus", "normatives", "html", f"ley-37-1992-art-{art}.html")
        assert excerpt.exists()
        body = excerpt.read_text(encoding="utf-8")
        assert f"Artículo {art}." in body or f"Artículo&nbsp;{art}." in body


def test_iva_flow_load_registry_recognises_three_articles() -> None:
    """The registry tree loader must surface the three LIVA articles in
    the catalogue."""
    catalogues = bundled_authority().catalogues
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


def test_devengada_and_deducible_flow_sets_union_to_every_settling_flow() -> None:
    """The two cornerstone sets cover every flow that settles at all.

    This asserted coverage of the WHOLE taxonomy until the supplier's side of a
    reverse-charge operation was given its own member. That operation is turnover
    bearing no cuota, so belonging to neither set is the fact being recorded
    rather than a gap — and the old form would have forced it onto a side,
    which is the mis-declaration the member exists to end.

    The guard the original really provided — no flow falls through unclassified —
    is preserved and sharpened in the mapping-totality test below, which checks
    membership of the mapping rather than non-emptiness of its values.
    """
    from .. import (
        DEDUCIBLE_FLOW_DIRECTIONS,
        DEVENGADA_FLOW_DIRECTIONS,
    )

    settling = set(IvaFlowDirection) - {IvaFlowDirection.OPERACION_CON_INVERSION}
    assert settling == DEVENGADA_FLOW_DIRECTIONS | DEDUCIBLE_FLOW_DIRECTIONS


def test_settlement_sides_mapping_is_total_over_flow_directions() -> None:
    """Every member is a KEY of the mapping — no flow falls through unclassified.

    Totality is asserted over the mapping's KEYS, not over the non-emptiness of
    its values. Those are different guarantees and only the first is the one
    worth having: a member missing from the mapping raises ``KeyError`` at a
    caller, while a member mapped to the empty set has been consciously declared
    to settle on neither side. Asserting non-emptiness conflated the two and
    would forbid ever recording an operation that bears no cuota.
    """
    from .. import settlement_sides_for_flow

    assert len(list(IvaFlowDirection)) > 0
    for flow in IvaFlowDirection:
        settlement_sides_for_flow(flow)  # raises KeyError if the member is unmapped
    sideless = {flow for flow in IvaFlowDirection if not settlement_sides_for_flow(flow)}
    assert sideless == {IvaFlowDirection.OPERACION_CON_INVERSION}, (
        "exactly one flow settles on neither side — the supplier's own reverse-charge "
        f"supply. A second one appearing here is unreviewed: {sorted(f.value for f in sideless)}"
    )


def test_modelo_303_devengada_formula_matches_devengada_flow_set() -> None:
    """Modelo 303 cuota-devengada-total formula sums repercutido (3 rate
    tiers) + INVERSION_SUJETO_PASIVO — the same flows as DEVENGADA_FLOW_DIRECTIONS.
    This test is a contract gate: if the substrate's devengada set ever
    changes, this test fires unless 303's formula updates in lockstep."""
    from .. import (
        DEVENGADA_FLOW_DIRECTIONS,
        IvaFlowDirection,
    )

    m303 = bundled_authority().modelo("303")
    revision = m303.revisions["2022"]

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
        flow_value = selector_as_dict(binding)["flow_direction"]
        binding_flows.add(IvaFlowDirection(flow_value))

    assert binding_flows == DEVENGADA_FLOW_DIRECTIONS
