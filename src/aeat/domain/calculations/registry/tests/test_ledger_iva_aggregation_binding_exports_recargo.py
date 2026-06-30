"""Export, domestic-base, and recargo ledger IVA aggregation binding tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.resources import resources
from ....iva import (
    IvaCategory,
    IvaFlowDirection,
    IvaRateKind,
)
from .. import (
    resolve_bound_inputs_by_casilla_id,
    resolve_ledger_iva_aggregation_binding_values,
)
from .._binding_selector_utils import selector_as_dict
from ._ledger_iva_aggregation_support import (
    _M303_REPERCUTIDO_GENERAL_BASE_CASILLA,
    _M303_REPERCUTIDO_GENERAL_CUOTA_CASILLA,
    _M303_REPERCUTIDO_REDUCIDO_BASE_CASILLA,
    _M303_REPERCUTIDO_SUPER_REDUCIDO_BASE_CASILLA,
    _M303_SOPORTADO_INTERIORES_BASE_CASILLA,
    _M303_SOPORTADO_INTERIORES_CUOTA_CASILLA,
    _calculate_303_from_observations,
    _observation,
)
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _m303_revision(revision_id: str):
    modelo, _catalogues = _committed_modelo("303")
    return modelo.revisions[revision_id]


def test_box_59_carries_substantive_intra_community_supply_grounding() -> None:
    """Box 59: substantive ground is LIVA art. 25, not the generic art. 88/92.

    Casilla 59 reports the base of exempt intra-community supplies; its
    substantive legal_ref is ``ley-37-1992:art-25`` (exención entregas
    intracomunitarias). The former repercusión/deducción articles 88/92 (which do
    not apply to an exempt entrega) must be gone. Asserted against the loaded
    registry revision, both 2009 and 2023.
    """
    for revision_id in ("2009-y-siguientes", "2023-y-siguientes"):
        revision = _m303_revision(revision_id)
        casilla_59 = next(casilla for casilla in revision.casillas if casilla.number == "59")
        refs = tuple(casilla_59.legal_refs)
        assert "ley-37-1992:art-25" in refs, f"{revision_id}: box 59 must cite art-25"
        assert "ley-37-1992:art-88" not in refs, f"{revision_id}: box 59 must drop art-88"
        assert "ley-37-1992:art-92" not in refs, f"{revision_id}: box 59 must drop art-92"


def test_box_60_carries_substantive_export_grounding() -> None:
    """Box 60: substantive grounds are LIVA art. 21 + art. 22.

    Casilla 60 reports the base of exempt exports and operations treated as
    exports; its substantive legal_refs are ``ley-37-1992:art-21`` (exenciones
    exportaciones) and ``ley-37-1992:art-22`` (exenciones asimiladas a las
    exportaciones), the latter matching the casilla label's "operaciones
    asimiladas" leg. Asserted against the loaded registry revision, both 2009
    and 2023.
    """
    for revision_id in ("2009-y-siguientes", "2023-y-siguientes"):
        revision = _m303_revision(revision_id)
        casilla_60 = next(casilla for casilla in revision.casillas if casilla.number == "60")
        refs = tuple(casilla_60.legal_refs)
        assert "ley-37-1992:art-21" in refs, f"{revision_id}: box 60 must cite art-21"
        assert "ley-37-1992:art-22" in refs, f"{revision_id}: box 60 must cite art-22"


def test_box_60_binding_selects_export_and_assimilated_export_categories() -> None:
    """The casilla 60 source binding must implement both legal legs in its selector."""
    expected = {
        IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED,
    }
    for revision_id in ("2009-y-siguientes", "2023-y-siguientes"):
        revision = _m303_revision(revision_id)
        binding = next(item for item in revision.bindings if item.id == "modelo-303-casilla-60-exportaciones-base")
        assert set(selector_as_dict(binding)["categories"]) == expected
        assert "ley-37-1992:art-21" in binding.legal_refs, f"{revision_id}: binding must cite art-21"
        assert "ley-37-1992:art-22" in binding.legal_refs, f"{revision_id}: binding must cite art-22"


def test_modelo_303_2024_domestic_base_aggregates_from_ledger() -> None:
    """Regression: casillas 07/28 (base imponible) aggregate the ledger base.

    Before the domestic base bindings landed, casillas 01/04/07/28 were
    ``input_kind = "manual"`` with no binding, so the base imponible stayed 0
    while the cuota (09/29) resolved from the ledger — a structurally
    inconsistent M303 (cuota without base) that nonetheless passed verify. The
    base now aggregates via ``fact = "base_amount_sum"``, mirroring the existing
    59/60 export / intra-community base bindings.

    Expected values are the declared observation base sums (ground truth from the
    inputs, not a re-run of the registry formula), so a regression to the manual
    no-binding state (base -> 0) fails this test loudly.
    """
    repercutido = _observation(
        category=IvaCategory.DOMESTIC_GENERAL_21,
        rate_kind=IvaRateKind.GENERAL,
        flow=IvaFlowDirection.REPERCUTIDO,
        base=Decimal("6500"),
        iva=Decimal("1365"),
    )
    soportado = _observation(
        category=IvaCategory.DOMESTIC_GENERAL_21,
        rate_kind=IvaRateKind.GENERAL,
        flow=IvaFlowDirection.SOPORTADO,
        base=Decimal("300"),
        iva=Decimal("63"),
    )
    result = _calculate_303_from_observations(
        filing_year=2024,
        period="2T",
        observations=(repercutido, soportado),
    )
    # Base imponible boxes now carry the ledger base sum (the regression target).
    assert result.values[_M303_REPERCUTIDO_GENERAL_BASE_CASILLA] == Decimal("6500")
    assert result.values[_M303_SOPORTADO_INTERIORES_BASE_CASILLA] == Decimal("300")
    # Cuota boxes are unchanged — the base binding is independent of the cuota
    # binding (casilla 09 is not base x tipo here, it is its own aggregation).
    assert result.values[_M303_REPERCUTIDO_GENERAL_CUOTA_CASILLA] == Decimal("1365")
    assert result.values[_M303_SOPORTADO_INTERIORES_CUOTA_CASILLA] == Decimal("63")
    # No reduced / super-reduced operations -> those base boxes resolve to zero.
    assert result.values[_M303_REPERCUTIDO_SUPER_REDUCIDO_BASE_CASILLA] == Decimal("0")
    assert result.values[_M303_REPERCUTIDO_REDUCIDO_BASE_CASILLA] == Decimal("0")


def test_modelo_303_2009_revision_domestic_base_aggregates_from_ledger() -> None:
    """#15 regression: the 2009-y-siguientes revision (filing years 2009-2022)
    now aggregates the domestic base imponible from the ledger.

    The 2009 revision (inline-declared) carried the cuota ledger bindings (and the
    compensación carry + verification) but lacked the domestic-base bindings that
    the 2023-y-siguientes revision has, so casillas 01/04/07/28 were
    ``input_kind = "manual"`` and a ledger-driven 2009-2022 M303 left the base at 0
    while the cuota resolved — a "cuota without base" under-declaration. This fixes
    that by back-filling the four base bindings (``fact = "base_amount_sum"``,
    selectors mirroring the 2023 revision). filing_year=2022 resolves to the
    2009-y-siguientes revision; this test fails loudly if the base regresses to the
    unbound manual state (0). Expected values are the seeded observation base sums
    (ground truth from inputs, not a re-run of the registry formula).
    """
    snapshot = resources().modelos.authority.snapshot("303", filing_year=2022, period="2T")
    assert snapshot.revision.id == "2009-y-siguientes"  # filing_year 2022 resolves to the older revision
    observations = (
        _observation(
            category=IvaCategory.DOMESTIC_GENERAL_21,
            rate_kind=IvaRateKind.GENERAL,
            flow=IvaFlowDirection.REPERCUTIDO,
            base=Decimal("6500"),
            iva=Decimal("1365"),
        ),
        _observation(
            category=IvaCategory.DOMESTIC_GENERAL_21,
            rate_kind=IvaRateKind.GENERAL,
            flow=IvaFlowDirection.SOPORTADO,
            base=Decimal("300"),
            iva=Decimal("63"),
        ),
    )
    values = resolve_ledger_iva_aggregation_binding_values(snapshot.revision, observations)
    binding_values = {
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        **values,
    }
    # The back-filled base bindings now aggregate the ledger base on the 2009
    # revision (the #15 regression target). Before the fix these binding ids did
    # not exist, so the base never resolved and the numbered boxes stayed 0.
    assert values["modelo-303-iva-repercutido-general-base"] == Decimal("6500")
    assert values["modelo-303-iva-soportado-interiores-base"] == Decimal("300")
    assert values["modelo-303-iva-repercutido-super-reducido-base"] == Decimal("0")
    assert values["modelo-303-iva-repercutido-reducido-base"] == Decimal("0")
    # The pre-existing cuota bindings still aggregate — base and cuota coexist, no
    # regression on the 2009 revision's existing capability.
    assert values["modelo-303-iva-repercutido-general-cuota"] == Decimal("1365")
    assert values["modelo-303-iva-soportado-interiores-cuota"] == Decimal("63")
    # The new base bindings map to the numbered base casillas (01/04/07/28).
    inputs = resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    assert inputs[_M303_REPERCUTIDO_GENERAL_BASE_CASILLA] == Decimal("6500")
    assert inputs[_M303_SOPORTADO_INTERIORES_BASE_CASILLA] == Decimal("300")


def test_iva_ledger_observation_is_strict_and_frozen() -> None:
    obs = _observation()
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        obs.iva_amount = Decimal("999")


def test_recargo_equivalencia_cuota_aggregates_by_tier_from_recargo_amount() -> None:
    """A supplier's recargo charged on a repercutido sale aggregates into the M303
    recargo cuota casillas by IVA tier (LIVA art. 161), instead of reporting zero.

    Expected values derive from the recargo amounts placed on the observations,
    routed by category to the matching tier binding — not from re-running the sum
    under test. Proves the recargo_amount_sum fact closes the recargo silent zero.
    """
    revision = _m303_revision("2023-y-siguientes")
    general = _observation(
        ledger_id="rec-general",
        category=IvaCategory.DOMESTIC_GENERAL_21,
        rate_kind=IvaRateKind.GENERAL,
        flow=IvaFlowDirection.REPERCUTIDO,
        base=Decimal("1000"),
        iva=Decimal("210"),
        recargo=Decimal("52.00"),
    )
    reduced = _observation(
        ledger_id="rec-reduced",
        category=IvaCategory.DOMESTIC_REDUCED_10,
        rate_kind=IvaRateKind.REDUCED,
        flow=IvaFlowDirection.REPERCUTIDO,
        base=Decimal("1000"),
        iva=Decimal("100"),
        recargo=Decimal("14.00"),
    )
    # A normal sale with no recargo contributes zero to the recargo cuota.
    plain = _observation(
        ledger_id="plain-general",
        category=IvaCategory.DOMESTIC_GENERAL_21,
        rate_kind=IvaRateKind.GENERAL,
        flow=IvaFlowDirection.REPERCUTIDO,
        base=Decimal("2000"),
        iva=Decimal("420"),
        recargo=Decimal("0"),
    )

    resolved = resolve_ledger_iva_aggregation_binding_values(revision, (general, reduced, plain))

    assert resolved["modelo-303-recargo-equivalencia-general-cuota"] == Decimal("52.00")
    assert resolved["modelo-303-recargo-equivalencia-reducido-cuota"] == Decimal("14.00")
    assert resolved["modelo-303-recargo-equivalencia-super-reducido-cuota"] == Decimal("0")


def test_modelo_303_2009_revision_recargo_and_intracom_export_aggregate_from_ledger() -> None:
    """#41 regression: the 2009-y-siguientes revision also aggregates recargo de
    equivalencia (casillas 21/24/158) and the intra-community / export base
    (casillas 59/60) from the ledger — the rest of the 2009 coverage tail behind #15.

    These casillas existed but were input_kind="manual" with no binding, so a
    ledger-driven 2009-2022 M303 reported zero recargo (even when a supplier charged
    it) and zero intra-community / export base. The recargo cuotas now aggregate by
    tier via recargo_amount_sum (LIVA art. 161); 59/60 via base_amount_sum — mirroring
    the 2023 revision. filing_year=2022 resolves to the 2009 revision; expected values
    derive from the seeded amounts, not a formula re-run.
    """
    revision = resources().modelos.authority.snapshot("303", filing_year=2022, period="2T").revision
    assert revision.id == "2009-y-siguientes"
    rec_general = _observation(
        category=IvaCategory.DOMESTIC_GENERAL_21,
        rate_kind=IvaRateKind.GENERAL,
        flow=IvaFlowDirection.REPERCUTIDO,
        base=Decimal("1000"),
        iva=Decimal("210"),
        recargo=Decimal("52.00"),
    )
    rec_reduced = _observation(
        category=IvaCategory.DOMESTIC_REDUCED_10,
        rate_kind=IvaRateKind.REDUCED,
        flow=IvaFlowDirection.REPERCUTIDO,
        base=Decimal("1000"),
        iva=Decimal("100"),
        recargo=Decimal("14.00"),
    )
    rec_super = _observation(
        category=IvaCategory.DOMESTIC_SUPER_REDUCED_4,
        rate_kind=IvaRateKind.SUPER_REDUCED,
        flow=IvaFlowDirection.REPERCUTIDO,
        base=Decimal("1000"),
        iva=Decimal("40"),
        recargo=Decimal("5.00"),
    )
    intracom = _observation(
        category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        rate_kind=IvaRateKind.ZERO,
        flow=IvaFlowDirection.REPERCUTIDO,
        base=Decimal("2000"),
        iva=Decimal("0"),
    )
    export = _observation(
        category=IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        rate_kind=IvaRateKind.ZERO,
        flow=IvaFlowDirection.REPERCUTIDO,
        base=Decimal("3000"),
        iva=Decimal("0"),
    )
    values = resolve_ledger_iva_aggregation_binding_values(
        revision,
        (rec_general, rec_reduced, rec_super, intracom, export),
    )
    # Recargo cuotas now aggregate by tier (0 before the back-fill).
    assert values["modelo-303-recargo-equivalencia-general-cuota"] == Decimal("52.00")
    assert values["modelo-303-recargo-equivalencia-reducido-cuota"] == Decimal("14.00")
    assert values["modelo-303-recargo-equivalencia-super-reducido-cuota"] == Decimal("5.00")
    # Intra-community / export base now aggregate (0 before the back-fill).
    assert values["modelo-303-casilla-59-entregas-intracomunitarias-base"] == Decimal("2000")
    assert values["modelo-303-casilla-60-exportaciones-base"] == Decimal("3000")
