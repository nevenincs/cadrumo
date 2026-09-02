"""Tests for Modelo 303 autoconsumo calculations and record-design authorities."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources.bundled_data import bundled_path
from .....tests.registry_snapshot import build_snapshot
from ..bindings import resolve_available_bound_inputs_by_casilla_id
from ._modelo_303_registry_support import (
    _M303_AUTOCONSUMO_PROMOTOR_BASE_CASILLA,
    _M303_AUTOCONSUMO_PROMOTOR_CUOTA_CASILLA,
    _M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
    load_modelo_303,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_303_autoconsumo_promotor_art9_oracle_1400k_base_yields_294k_cuota() -> None:
    """Oracle: Ramón has construction cost €1,400,000 and converts the building
    to his rental estate.  Art. 9.1.c LISIVA triggers the autoconsumo; Art. 79.4
    LISIVA sets the base at cost; Art. 90 LISIVA sets the tipo at 21%.

    Expected cuota = 1,400,000 x 0.21 = 294,000.00.

    The expected value is derived from the statutory formula (Art. 90 LISIVA:
    tipo general = 21%), NOT from the registry implementation under test; this
    test would fail if the formula were mis-wired or the tipo were wrong.
    """
    from ..formula_runtime import calculate_registry_snapshot

    modelo, catalogues = load_modelo_303()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="1T")

    binding_values = {
        "modelo-303-iva-repercutido-general-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-importaciones-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-base": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-deducible-cuota": Decimal("0.00"),
        "modelo-303-casilla-59-entregas-intracomunitarias-base": Decimal("0"),
        "modelo-303-casilla-60-exportaciones-base": Decimal("0"),
        # No issued domestic reverse charge in this fixture either, so the
        # supplier-side base for casilla 122 resolves to zero. Supplied for the
        # same reason 59 and 60 are: a bound casilla demands its fact, and the
        # absence of contributing rows is stated rather than left missing.
        "modelo-303-casilla-122-inversion-sujeto-pasivo-base": Decimal("0"),
        # And no EU B2B service located outside the TAI, so the sibling
        # informacion-adicional box 120 resolves to zero for the same reason.
        "modelo-303-casilla-120-no-sujetas-localizacion-base": Decimal("0"),
        "modelo-303-iva-repercutido-general-base": Decimal("0"),
        "modelo-303-iva-repercutido-reducido-base": Decimal("0"),
        "modelo-303-iva-repercutido-super-reducido-base": Decimal("0"),
        "modelo-303-iva-soportado-interiores-base": Decimal("0"),
        "modelo-303-recargo-equivalencia-general-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-reducido-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-super-reducido-cuota": Decimal("0"),
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
        "modelo-303-autoconsumo-promotor-base": Decimal("1400000"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
        # No criterio-de-caja operations in this fixture, so the art. 163
        # decies informational bindings (casillas 62/63/74/75) resolve to zero.
        "modelo-303-criterio-caja-entregas-art75-base": Decimal("0"),
        "modelo-303-criterio-caja-entregas-art75-cuota": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-base": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-cuota": Decimal("0"),
    }
    bound_inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=bound_inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(2025, 3, 31)},
    )

    # Art. 90 LISIVA tipo general 21%: 1,400,000 x 0.21 = 294,000.00
    assert result.values[_M303_AUTOCONSUMO_PROMOTOR_BASE_CASILLA] == Decimal("1400000"), (
        "base casilla must carry the supplied construction cost"
    )
    assert result.values[_M303_AUTOCONSUMO_PROMOTOR_CUOTA_CASILLA] == Decimal("294000.00"), (
        "cuota must equal 1,400,000 x 21% = 294,000.00 per Art. 90 LISIVA"
    )
    # The autoconsumo cuota must also flow into the total devengada.
    cuota_devengada_total = result.values[_M303_CUOTA_DEVENGADA_TOTAL_CASILLA]
    assert cuota_devengada_total == Decimal("294000.00"), (
        "cuota-devengada-total must include the autoconsumo promotor cuota"
    )


def test_modelo_303_autoconsumo_promotor_cuota_proportional_to_base() -> None:
    """Anti-tautology: halving the construction base must halve the cuota.

    The assertion is derived from the statutory multiplication (Art. 90 LISIVA
    tipo 21%), not from a second call to the same formula.  If the formula
    constant were changed to, say, 0.10, this test would catch it immediately.
    """
    from ..formula_runtime import calculate_registry_snapshot

    modelo, catalogues = load_modelo_303()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="1T")

    zero_bindings: dict[str, Decimal] = {
        "modelo-303-iva-repercutido-general-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-importaciones-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-base": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-deducible-cuota": Decimal("0.00"),
        "modelo-303-casilla-59-entregas-intracomunitarias-base": Decimal("0"),
        "modelo-303-casilla-60-exportaciones-base": Decimal("0"),
        # No issued domestic reverse charge in this fixture either, so the
        # supplier-side base for casilla 122 resolves to zero. Supplied for the
        # same reason 59 and 60 are: a bound casilla demands its fact, and the
        # absence of contributing rows is stated rather than left missing.
        "modelo-303-casilla-122-inversion-sujeto-pasivo-base": Decimal("0"),
        # And no EU B2B service located outside the TAI, so the sibling
        # informacion-adicional box 120 resolves to zero for the same reason.
        "modelo-303-casilla-120-no-sujetas-localizacion-base": Decimal("0"),
        "modelo-303-iva-repercutido-general-base": Decimal("0"),
        "modelo-303-iva-repercutido-reducido-base": Decimal("0"),
        "modelo-303-iva-repercutido-super-reducido-base": Decimal("0"),
        "modelo-303-iva-soportado-interiores-base": Decimal("0"),
        "modelo-303-recargo-equivalencia-general-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-reducido-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-super-reducido-cuota": Decimal("0"),
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
        # No criterio-de-caja operations in this fixture, so the art. 163
        # decies informational bindings (casillas 62/63/74/75) resolve to zero.
        "modelo-303-criterio-caja-entregas-art75-base": Decimal("0"),
        "modelo-303-criterio-caja-entregas-art75-cuota": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-base": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-cuota": Decimal("0"),
    }

    def _run(base: Decimal) -> Decimal:
        bv = {**zero_bindings, "modelo-303-autoconsumo-promotor-base": base}
        bound = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, bv)
        r = calculate_registry_snapshot(
            snapshot,
            inputs=bound,
            binding_values=bv,
            date_context={"filing_period": date(2025, 3, 31)},
        )
        return r.values[_M303_AUTOCONSUMO_PROMOTOR_CUOTA_CASILLA]

    # Statutory expectation from Art. 90 LISIVA (tipo general 21%):
    #   700,000 x 0.21 = 147,000.00
    assert _run(Decimal("700000")) == Decimal("147000.00")
    # Cross-check: result at 1,400,000 is exactly double — if the registry formula
    # were wrong the ratio would differ.
    assert _run(Decimal("1400000")) == Decimal("2") * _run(Decimal("700000"))


def test_modelo_303_workbook_parity_ref_anchors_record_design_layout() -> None:
    modelo, _ = load_modelo_303()
    revision = modelo.revisions["2022"]
    parity = next(p for p in revision.workbook_parity_refs if p.id == "modelo-303-dr-2022")

    assert parity.workbook_source == "aeat-dr-303-2022"
    assert parity.formula_coverage == "record_design_layout"
    assert parity.fixture_id == "modelo-303-2022-record-design-layout"


def test_modelo_303_2026_cnae_width_has_a_distinct_authority_role() -> None:
    modelo, _ = load_modelo_303()
    historical = modelo.revisions["2025"]
    current = modelo.revisions["2026-y-siguientes"]

    for row, casilla_id in enumerate(("500", "505", "510", "515", "520"), start=1):
        prior = next(c for c in historical.casillas if c.id == casilla_id)
        widened = next(c for c in current.casillas if c.id == casilla_id)
        assert prior.constraints is not None and prior.constraints.min_length == prior.constraints.max_length == 3
        assert widened.constraints is not None and widened.constraints.min_length == widened.constraints.max_length == 4
        assert prior.semantic_role == f"m303_prorrata_actividad_fila_{row}_cnae"
        assert widened.semantic_role == f"m303_prorrata_actividad_fila_{row}_cnae_2026_four_digit"
        assert "aeat-dr-303-2025" in prior.source_refs
        assert "aeat-dr-303-2026" in widened.source_refs


# The defect-C2 regression that pinned the no-volume prorrata default used one
# filing-year sample. It is retired rather than widened because a dedicated
# two-revision gate now owns the claim: measured by mutation, breaking the
# branch on either live revision reds that gate. Its distinct mid-year axis was
# carried across before this test was removed.
