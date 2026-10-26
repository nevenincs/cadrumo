"""Export, domestic-base, and recargo ledger IVA aggregation binding tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache
from typing import Any

import pytest
from pydantic import ValidationError

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from cadrumo.domain.calculations.registry.binding_selector_utils import selector_as_dict
from cadrumo.domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.formula_runtime import RegistryCalculationResult
from cadrumo.domain.calculations.registry.ledger_iva_bindings import (
    IvaLedgerObservation,
    resolve_ledger_iva_aggregation_binding_values,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.iva.flow import IvaFlowDirection
from cadrumo.domain.iva.schema import IvaCategory, IvaRateKind
from dev.registry.compiler.authority import compiled_bundled_authority

from .ledger_iva_aggregation_support import (
    _M303_REPERCUTIDO_GENERAL_BASE_CASILLA,
    _M303_REPERCUTIDO_GENERAL_CUOTA_CASILLA,
    _M303_REPERCUTIDO_REDUCIDO_BASE_CASILLA,
    _M303_REPERCUTIDO_SUPER_REDUCIDO_BASE_CASILLA,
    _M303_SOPORTADO_INTERIORES_BASE_CASILLA,
    _M303_SOPORTADO_INTERIORES_CUOTA_CASILLA,
    _calculate_303_from_observations,
    _observation,
)
from .profile_schema_support import committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_SUPPORT = committed_supported_filing_years()
# The revision family that follows the floor exercise's older design; that design's
# back-filled base bindings are pinned separately below against its own snapshot.
_POST_FLOOR_DESIGN_YEARS = tuple(year for year in _SUPPORT.years if year > _SUPPORT.floor)


def _m303_revision(revision_id: str) -> ModeloRevision:
    authority = compiled_bundled_authority()
    modelo, _catalogues = authority.modelo("303"), authority.catalogues
    return modelo.revisions[revision_id]


@cache
def _m303_2022_2t_snapshot():
    return compiled_bundled_authority().snapshot("303", filing_year=2022, period="2T")


def test_box_59_carries_substantive_intra_community_supply_grounding() -> None:
    """Box 59: substantive ground is LIVA art. 25, not the generic art. 88/92.

    Casilla 59 reports the base of exempt intra-community supplies; its
    substantive legal_ref is ``ley-37-1992:art-25`` (exención entregas
    intracomunitarias). The former repercusión/deducción articles 88/92 (which do
    not apply to an exempt entrega) must be gone. Asserted against the loaded
    registry revision, both 2009 and 2023.
    """
    for revision_id in (
        "2022",
        "2023",
        "2024-hasta-08-y-2t",
        "2024-desde-09-y-3t",
        "2025",
        "2026-y-siguientes",
    ):
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
    for revision_id in (
        "2022",
        "2023",
        "2024-hasta-08-y-2t",
        "2024-desde-09-y-3t",
        "2025",
        "2026-y-siguientes",
    ):
        revision = _m303_revision(revision_id)
        casilla_60 = next(casilla for casilla in revision.casillas if casilla.number == "60")
        refs = tuple(casilla_60.legal_refs)
        assert "ley-37-1992:art-21" in refs, f"{revision_id}: box 60 must cite art-21"
        assert "ley-37-1992:art-22" in refs, f"{revision_id}: box 60 must cite art-22"


def test_box_60_binding_selects_export_and_assimilated_export_categories() -> None:
    """The casilla 60 source binding must implement both legal legs in its selector."""
    expected = {
        IvaCategory("export_third_country_zero_rated"),
        IvaCategory("export_assimilated_zero_rated"),
    }
    for revision_id in (
        "2022",
        "2023",
        "2024-hasta-08-y-2t",
        "2024-desde-09-y-3t",
        "2025",
        "2026-y-siguientes",
    ):
        revision = _m303_revision(revision_id)
        binding = next(item for item in revision.bindings if item.id == "modelo-303-casilla-60-exportaciones-base")
        selector_dict: Any = selector_as_dict(binding)
        assert set(selector_dict["categories"]) == expected
        assert "ley-37-1992:art-21" in binding.legal_refs, f"{revision_id}: binding must cite art-21"
        assert "ley-37-1992:art-22" in binding.legal_refs, f"{revision_id}: binding must cite art-22"


@pytest.mark.parametrize("filing_year", _POST_FLOOR_DESIGN_YEARS)
def test_modelo_303_domestic_base_aggregates_from_ledger(filing_year: int) -> None:
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
    # The transaction dates sit inside the declared 2T filing period, so the
    # date-axis parameter lookup resolves against the same revision the snapshot does.
    repercutido = _observation(
        applied_rate=Decimal("0.21"),
        txn_date=date(filing_year, 5, 15),
        category=IvaCategory("domestic_general"),
        rate_kind=IvaRateKind("general"),
        flow=IvaFlowDirection.from_registry("repercutido"),
        base=Decimal("6500"),
        iva=Decimal("1365"),
    )
    soportado = _observation(
        applied_rate=Decimal("0.21"),
        txn_date=date(filing_year, 5, 15),
        category=IvaCategory("domestic_general"),
        rate_kind=IvaRateKind("general"),
        flow=IvaFlowDirection.from_registry("soportado"),
        base=Decimal("300"),
        iva=Decimal("63"),
        deduction_fact_kind=IvaDeductionFactKind.from_registry("domestic_current"),
        deduction_authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
    )
    result = _calculate_303_from_observations(
        filing_year=filing_year,
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
    """#15 regression: the 2022 revision (filing years 2022)
    now aggregates the domestic base imponible from the ledger.

    The 2009 revision (inline-declared) carried the cuota ledger bindings (and the
    compensación carry + verification) but lacked the domestic-base bindings that
    the post-2022 revision family has, so casillas 01/04/07/28 were
    ``input_kind = "manual"`` and a ledger-driven 2022 M303 left the base at 0
    while the cuota resolved — a "cuota without base" under-declaration. This fixes
    that by back-filling the four base bindings (``fact = "base_amount_sum"``,
    selectors mirroring the 2023 revision). filing_year=2022 resolves to the
    2022 revision; this test fails loudly if the base regresses to the
    unbound manual state (0). Expected values are the seeded observation base sums
    (ground truth from inputs, not a re-run of the registry formula).
    """
    snapshot = _m303_2022_2t_snapshot()
    assert snapshot.revision.id == "2022"  # filing_year 2022 resolves to the older revision
    observations = (
        _observation(
            applied_rate=Decimal("0.21"),
            category=IvaCategory("domestic_general"),
            rate_kind=IvaRateKind("general"),
            flow=IvaFlowDirection.from_registry("repercutido"),
            base=Decimal("6500"),
            iva=Decimal("1365"),
        ),
        _observation(
            applied_rate=Decimal("0.21"),
            category=IvaCategory("domestic_general"),
            rate_kind=IvaRateKind("general"),
            flow=IvaFlowDirection.from_registry("soportado"),
            base=Decimal("300"),
            iva=Decimal("63"),
            deduction_fact_kind=IvaDeductionFactKind.from_registry("domestic_current"),
            deduction_authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
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
    # Each base binding lands on a component its numbered box adds. Box 07 is the
    # general rate row's whole base: the ledger base plus the promotor's
    # autoconsumo declared at that rate. Box 28 adds the soportado base and the
    # deducible half of a domestic inversión del sujeto pasivo. Both boxes carry
    # the ledger base through their formulas.
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    assert inputs[validated_casilla_id("iva.repercutido.general.base")] == Decimal("6500")
    assert _M303_REPERCUTIDO_GENERAL_BASE_CASILLA not in inputs
    assert inputs[validated_casilla_id("iva.soportado.interiores.base")] == Decimal("300")
    assert _M303_SOPORTADO_INTERIORES_BASE_CASILLA not in inputs
    result = _calculate_303_from_observations(filing_year=2022, period="2T", observations=observations)
    assert result.values[_M303_REPERCUTIDO_GENERAL_BASE_CASILLA] == Decimal("6500")
    assert result.values[_M303_SOPORTADO_INTERIORES_BASE_CASILLA] == Decimal("300")


def test_iva_ledger_observation_is_strict_and_frozen() -> None:
    obs = _observation(
        applied_rate=Decimal("0.21"),
    )
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        obs.iva_amount = Decimal("999")


def test_recargo_equivalencia_cuota_aggregates_by_tier_from_recargo_amount() -> None:
    """A supplier's recargo charged on a repercutido sale aggregates into the M303
    recargo cuota casillas by IVA tier (LIVA art. 161), instead of reporting zero.

    Expected values derive from the recargo amounts placed on the observations,
    routed by category to the matching tier binding — not from re-running the sum
    under test. Proves the recargo_amount_sum fact closes the recargo silent zero.
    """
    revision = _m303_revision("2025")
    general = _observation(
        applied_rate=Decimal("0.21"),
        ledger_id="rec-general",
        category=IvaCategory("domestic_general"),
        rate_kind=IvaRateKind("general"),
        flow=IvaFlowDirection.from_registry("repercutido"),
        base=Decimal("1000"),
        iva=Decimal("210"),
        recargo=Decimal("52.00"),
    )
    reduced = _observation(
        applied_rate=Decimal("0.10"),
        ledger_id="rec-reduced",
        category=IvaCategory("domestic_reduced"),
        rate_kind=IvaRateKind("reduced"),
        flow=IvaFlowDirection.from_registry("repercutido"),
        base=Decimal("1000"),
        iva=Decimal("100"),
        recargo=Decimal("14.00"),
    )
    # A normal sale with no recargo contributes zero to the recargo cuota.
    plain = _observation(
        applied_rate=Decimal("0.21"),
        ledger_id="plain-general",
        category=IvaCategory("domestic_general"),
        rate_kind=IvaRateKind("general"),
        flow=IvaFlowDirection.from_registry("repercutido"),
        base=Decimal("2000"),
        iva=Decimal("420"),
        recargo=Decimal("0"),
    )

    resolved = resolve_ledger_iva_aggregation_binding_values(revision, (general, reduced, plain))

    assert resolved["modelo-303-recargo-equivalencia-general-cuota"] == Decimal("52.00")
    assert resolved["modelo-303-recargo-equivalencia-reducido-cuota"] == Decimal("14.00")
    assert resolved["modelo-303-recargo-equivalencia-super-reducido-cuota"] == Decimal("0")


def test_modelo_303_2022_revision_recargo_and_intracom_export_aggregate_from_ledger() -> None:
    """#41 regression: the 2022 revision also aggregates recargo de
    equivalencia (casillas 18/21/24) and the intra-community / export base
    (casillas 59/60) from the ledger — the rest of the 2009 coverage tail behind #15.

    These casillas existed but were input_kind="manual" with no binding, so a
    ledger-driven 2022 M303 reported zero recargo (even when a supplier charged
    it) and zero intra-community / export base. The recargo cuotas now aggregate by
    tier via recargo_amount_sum (LIVA art. 161); 59/60 via base_amount_sum — mirroring
    the 2023 revision. filing_year=2022 resolves to the 2022 revision; expected values
    derive from the seeded amounts, not a formula re-run.
    """
    revision = _m303_2022_2t_snapshot().revision
    assert revision.id == "2022"
    rec_general = _observation(
        applied_rate=Decimal("0.21"),
        category=IvaCategory("domestic_general"),
        rate_kind=IvaRateKind("general"),
        flow=IvaFlowDirection.from_registry("repercutido"),
        base=Decimal("1000"),
        iva=Decimal("210"),
        recargo=Decimal("52.00"),
    )
    rec_reduced = _observation(
        applied_rate=Decimal("0.10"),
        category=IvaCategory("domestic_reduced"),
        rate_kind=IvaRateKind("reduced"),
        flow=IvaFlowDirection.from_registry("repercutido"),
        base=Decimal("1000"),
        iva=Decimal("100"),
        recargo=Decimal("14.00"),
    )
    rec_super = _observation(
        applied_rate=Decimal("0.04"),
        category=IvaCategory("domestic_super_reduced"),
        rate_kind=IvaRateKind("super_reduced"),
        flow=IvaFlowDirection.from_registry("repercutido"),
        base=Decimal("1000"),
        iva=Decimal("40"),
        recargo=Decimal("5.00"),
    )
    intracom = _observation(
        category=IvaCategory("intra_community_supply"),
        rate_kind=IvaRateKind("zero"),
        flow=IvaFlowDirection.from_registry("repercutido"),
        base=Decimal("2000"),
        iva=Decimal("0"),
    )
    export = _observation(
        category=IvaCategory("export_third_country_zero_rated"),
        rate_kind=IvaRateKind("zero"),
        flow=IvaFlowDirection.from_registry("repercutido"),
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
    # The 2022 design already prints [16]-[18], although it leaves [17] free.
    # LIVA art. 161.3 governs the super-reduced population's 0.50 percent recargo.
    assert values["modelo-303-recargo-equivalencia-super-reducido-cuota"] == Decimal("5.00")
    inputs = resolve_available_bound_inputs_by_casilla_id(revision, values)
    assert inputs[validated_casilla_id("18")] == Decimal("5.00")
    construct = next(member for member in revision.constructs if member.id == "modelo-303-iva-autoliquidacion")
    assert "modelo-303-recargo-equivalencia-super-reducido-cuota" in construct.bindings
    # Intra-community / export base now aggregate (0 before the back-fill).
    assert values["modelo-303-casilla-59-entregas-intracomunitarias-base"] == Decimal("2000")
    assert values["modelo-303-casilla-60-exportaciones-base"] == Decimal("3000")


_CASILLA_CUOTA_DEVENGADA_TOTAL: CasillaId = validated_casilla_id(
    "iva.cuota-devengada-total",
    surface="_CASILLA_CUOTA_DEVENGADA_TOTAL",
)
_CASILLA_RESULTADO_REGIMEN_GENERAL: CasillaId = validated_casilla_id(
    "iva.resultado-regimen-general",
    surface="_CASILLA_RESULTADO_REGIMEN_GENERAL",
)


def _calculate_303_2009_from_observations(
    *,
    filing_year: int,
    period: str,
    observations: tuple[IvaLedgerObservation, ...],
) -> RegistryCalculationResult:
    """Calculate one quarter of the edition covering ``filing_year``.

    The 2022 edition declares the same profile-sourced bindings as the later
    editions (the promotor's autoconsumo base and the State attribution
    percentage), so the shared helper, which seeds exactly the bindings an
    edition declares, serves it unchanged.
    """
    return _calculate_303_from_observations(filing_year=filing_year, period=period, observations=observations)


@pytest.mark.parametrize(
    ("tier", "applied_rate", "iva_amount", "recargo_amount"),
    [
        ("general", Decimal("0.21"), Decimal("5040.00"), Decimal("1248.00")),
        ("reduced", Decimal("0.10"), Decimal("2400.00"), Decimal("336.00")),
        ("super_reduced", Decimal("0.04"), Decimal("960.00"), Decimal("120.00")),
    ],
)
def test_modelo_303_2022_revision_cuota_devengada_total_anti_tautology_recargo_changes_total(
    tier: str, applied_rate: Decimal, iva_amount: Decimal, recargo_amount: Decimal
) -> None:
    """The 2022 casilla-27 total now includes recargo de equivalencia.

    Backport of the post-2022 casilla-27 grounding (see the comment on
    ``modelo-303-iva-cuota-devengada-total`` in this revision's
    formulas/0001-declarations.toml): the 2022 revision (filing years
    2022) summed only the five non-recargo devengado components, silently
    excluding the recargo cuota tiers (casillas 18/21/24, LIVA art. 161) a
    ledger-driven filer's supplier may have charged. filing_year=2022 resolves
    to the 2022 revision. This test grades the formula's own
    target casilla ``iva.cuota-devengada-total``, which the official box
    [27] projects through ``modelo-303-dr303-27-projection`` on this edition
    as on every later one.

    Anti-tautology: this does not hand-compute the with-recargo absolute
    figure from the registry's own formula under test. It runs the full
    :func:`calculate_registry_snapshot` engine twice — once with a recargo
    ledger observation for each legal tier, once with the identical scenario but
    recargo zeroed — and asserts the delta in the devengada total equals
    exactly the dropped recargo_amount. A formula that ignored the recargo
    terms, or always returned a constant, would fail this check — mirroring
    the post-2022 pattern in
    ``test_casilla_27_anti_tautology_recargo_changes_total_cuota_devengada``.
    """

    def _observations(*, include_recargo: bool) -> tuple[IvaLedgerObservation, ...]:
        return (
            _observation(
                applied_rate=applied_rate,
                ledger_id="op-ventas-recargo-equivalencia",
                txn_date=date(2022, 5, 15),
                category=IvaCategory(f"domestic_{tier}"),
                rate_kind=IvaRateKind(tier),
                flow=IvaFlowDirection.from_registry("repercutido"),
                base=Decimal("24000.00"),
                iva=iva_amount,
                recargo=(recargo_amount if include_recargo else Decimal("0")),
            ),
        )

    with_recargo = _calculate_303_2009_from_observations(
        filing_year=2022,
        period="2T",
        observations=_observations(include_recargo=True),
    )
    without_recargo = _calculate_303_2009_from_observations(
        filing_year=2022,
        period="2T",
        observations=_observations(include_recargo=False),
    )

    assert (
        with_recargo.values[_CASILLA_CUOTA_DEVENGADA_TOTAL] - without_recargo.values[_CASILLA_CUOTA_DEVENGADA_TOTAL]
        == recargo_amount
    )
    # Recargo is devengado-only (no matching deducible leg), so the resultado
    # side must shift by exactly the same seeded recargo amount.
    assert (
        with_recargo.values[_CASILLA_RESULTADO_REGIMEN_GENERAL]
        - without_recargo.values[_CASILLA_RESULTADO_REGIMEN_GENERAL]
        == recargo_amount
    )
