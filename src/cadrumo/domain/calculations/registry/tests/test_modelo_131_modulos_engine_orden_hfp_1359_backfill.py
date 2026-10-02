"""Modelo 131 estimación-objetiva módulos engine — Orden HFP/1359/2023 back-fill.

The 2024 revision's módulos engine (fase 1ª rendimiento neto previo, fase 2ª
rendimiento neto minorado, fase 3ª rendimiento neto de módulos, fase 4ª
reducción general) was authored after the 2025 and 2026 revisions already
carried it. Orden HFP/1359/2023 (the 2024 filing year's applicable Orden)
reproduces the same euro figures as Orden HAC/1347/2024 for every currently
tabled activity, the same reducción general (5 por ciento), the same
incentivos-al-empleo coeficiente/tramos, and the same índice corrector de
exceso (1,30) with matching cuantías (confirmed by a full numeric diff of the
bundled corpus text at authoring time).

Non-tautological: the expected figures below are transcribed independently
from the bundled ``corpus/normatives/html/orden-hfp-1359-2023.html`` — the
2024 filing year's own applicable Orden — and the fase 2ª/3ª/4ª arithmetic is
reproduced by an independent helper (not the registry formula under test)
before being compared against the engine's output. A dedicated date-axis
section proves the year-scoped coefficient parameters do not leak across
revision boundaries.

See Also:
    :mod:`~domain.calculations.registry._formula_runtime_m131`
        Runtime evaluators for the M131 table-driven módulos operations.
    :func:`~domain.calculations.registry.calculate_registry_snapshot`
        Public registry calculation entry point exercised by the parity cases.
    :mod:`~domain.calculations.registry.tests.test_modelo_131_modulos_engine`
        Baseline 2025 módulos-engine behavior this back-fill must reproduce.
    :mod:`~domain.calculations.registry.tests.test_modelo_131_modulos_engine_orden_hac_1425_rollforward`
        Sibling roll-forward proof for the 2026 revision.
    ``src/cadrumo/_data/registry/aeat/modelos/131/revisions/2024/formulas/``
        Registry-authored 2024 formula chain under test.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.money.rounding import round_to_cents
from ..formula_runtime import calculate_registry_snapshot
from ..temporal import select_revision
from .published_authority import published_legal_reference, published_snapshot
from .registry_tree import bundled_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

# Orden HFP/1359/2023 fixes the módulos for the exercise it is in force, and Orden
# HAC/1347/2024 for the next; both Ordenes are the transcription sources cited below.
_ORDEN_HFP_1359_2023_EXERCISE = published_legal_reference("orden-hfp-1359-2023:art-4").effective_from.year
_ORDEN_HAC_1347_2024_EXERCISE = published_legal_reference("orden-hac-1347-2024:art-4").effective_from.year

# Rendimiento anual por unidad antes de amortización (Orden HFP/1359/2023
# Anexo II, filing year 2024), independently transcribed from the 2024 Orden
# corpus text for cross-check — a discrepancy between these literals and the
# registry parameter values would fail the assertions below, proving the 2024
# coefficient table is grounded (not merely copy-pasted from 2025 without
# re-verification).
_PELUQUERIA_972_1 = {
    1: Decimal("3161.90"),  # personal asalariado (persona)
    2: Decimal("9649.47"),  # personal no asalariado (persona)
    3: Decimal("94.48"),  # superficie del local (m2)
    4: Decimal("81.88"),  # consumo de energía eléctrica (100 kWh)
}
_AUTOTAXI_721_2 = {
    1: Decimal("1346.27"),  # personal asalariado (persona)
    2: Decimal("7656.89"),  # personal no asalariado (persona)
    3: Decimal("45.08"),  # distancia recorrida (1.000 km)
}

_REDUCCION_GENERAL = Decimal("0.05")

# Fase 2ª — coeficiente por tramos del número de unidades del módulo
# "personal asalariado" (Orden HFP/1359/2023 Anexo II, instrucción 2.2.a),
# independently transcribed for cross-check against the registry's
# m131-modulos-coeficiente-tramos-asalariados-2024 bracket_table parameter.
_COEFICIENTE_INCREMENTO_ASALARIADOS = Decimal("0.40")
_TRAMOS_ASALARIADOS = (
    (Decimal("0"), Decimal("1.00"), Decimal("0.10")),
    (Decimal("1.00"), Decimal("3.00"), Decimal("0.15")),
    (Decimal("3.00"), Decimal("5.00"), Decimal("0.20")),
    (Decimal("5.00"), Decimal("8.00"), Decimal("0.25")),
    (Decimal("8.00"), None, Decimal("0.30")),
)

# Fase 3ª — índice corrector de exceso (Orden HFP/1359/2023 Anexo II,
# instrucción 2.3.b.3): índice 1,30 applied to the excess over the tabled
# cuantía. Independently transcribed from the 2024 Orden Anexo II table,
# matching the registry's m131-modulos-cuantia-exceso-2024 parameter.
_INDICE_EXCESO = Decimal("1.30")
_CUANTIA_EXCESO_972_1 = Decimal("18051.81")


def _coeficiente_tramos(base: Decimal) -> Decimal:
    """Reproduce the coeficiente-por-tramos progressive-bracket lookup.

    Mirrors the registry's ``m131-modulos-coeficiente-tramos-asalariados-2024``
    bracket_table (cumulative fixed_addition + marginal_rate x remainder),
    independently transcribed here rather than re-derived from the formula
    under test.
    """
    if base <= Decimal("0"):
        return Decimal("0")
    for lower, upper, rate in _TRAMOS_ASALARIADOS:
        if upper is None or base <= upper:
            cumulative = Decimal("0")
            for prior_lower, prior_upper, prior_rate in _TRAMOS_ASALARIADOS:
                if prior_upper is not None and prior_upper <= lower:
                    cumulative += prior_rate * (prior_upper - prior_lower)
            return cumulative + rate * (base - lower)
    raise AssertionError("unreachable: open-ended top tramo always matches")


def _expected_minorado_no_inversion(previo: Decimal, *, modulo_1: Decimal, modulo_1_coefficient: Decimal) -> Decimal:
    """Reproduce Fase 2ª (minoración por incentivos al empleo only; no anterior/inversión)."""
    coeficiente_tramos = _coeficiente_tramos(modulo_1)
    minoracion_empleo = coeficiente_tramos * modulo_1_coefficient
    return round_to_cents(previo - minoracion_empleo)


def _expected_modulos(minorado: Decimal, *, cuantia: Decimal | None) -> Decimal:
    """Reproduce Fase 3ª (índice corrector de exceso only)."""
    if cuantia is None or minorado <= cuantia:
        return minorado
    return round_to_cents(cuantia + _INDICE_EXCESO * (minorado - cuantia))


def _run_hfp_1359_engine(
    epigrafe: str | None,
    *,
    modulo_1: Decimal = Decimal("0"),
    modulo_2: Decimal = Decimal("0"),
    modulo_3: Decimal = Decimal("0"),
    modulo_4: Decimal = Decimal("0"),
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    snapshot = published_snapshot(
        "131", filing_year=_ORDEN_HFP_1359_2023_EXERCISE, period="1T", grade=RegistryAuthorityGrade.CALCULATION
    )
    assert snapshot.filing_period is not None
    text_inputs = {"modulos-epigrafe": epigrafe} if epigrafe else {}
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "modulos-1-unidades": modulo_1,
            "modulos-2-unidades": modulo_2,
            "modulos-3-unidades": modulo_3,
            "modulos-4-unidades": modulo_4,
            "modulos-5-unidades": Decimal("0"),
            "modulos-6-unidades": Decimal("0"),
            "modulos-7-unidades": Decimal("0"),
            "modulos-1-unidades-anterior": Decimal("0"),
            "modulos-minoracion-inversion": Decimal("0"),
        },
        text_inputs=text_inputs,
        date_context={"filing_period": snapshot.filing_period.end_date},
    )
    values = result.values
    return (
        values["modulos-rendimiento-neto-previo"],
        values["modulos-rendimiento-neto-minorado"],
        values["modulos-rendimiento-neto-modulos"],
        values["modulos-rendimiento-neto-actividad"],
    )


class TestPeluqueria9721EstimacionObjetivaHfp1359Orden:
    """Epígrafe IAE 972.1 (Servicios de peluquería) on the Orden HFP/1359/2023 revision."""

    def test_fase_1_rendimiento_neto_previo_matches_hfp_1359_orden_coefficients(self) -> None:
        # 2 personal asalariado, 1 personal no asalariado, 50 m2 local, 30 (100 kWh).
        previo, _minorado, _modulos, _actividad = _run_hfp_1359_engine(
            "972.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("50"),
            modulo_4=Decimal("30"),
        )
        expected_previo = round_to_cents(
            Decimal("2") * _PELUQUERIA_972_1[1]
            + Decimal("1") * _PELUQUERIA_972_1[2]
            + Decimal("50") * _PELUQUERIA_972_1[3]
            + Decimal("30") * _PELUQUERIA_972_1[4],
        )
        assert previo == expected_previo == Decimal("23153.67")

    def test_fases_2_3_4_reproduce_independent_computation_on_hfp_1359_orden(self) -> None:
        previo, minorado, modulos, actividad = _run_hfp_1359_engine(
            "972.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("50"),
            modulo_4=Decimal("30"),
        )
        expected_minorado = _expected_minorado_no_inversion(
            previo,
            modulo_1=Decimal("2"),
            modulo_1_coefficient=_PELUQUERIA_972_1[1],
        )
        expected_modulos = _expected_modulos(expected_minorado, cuantia=_CUANTIA_EXCESO_972_1)
        expected_actividad = round_to_cents(expected_modulos - expected_modulos * _REDUCCION_GENERAL)
        assert minorado == expected_minorado == Decimal("22363.20")
        assert modulos == expected_modulos == Decimal("23656.62")
        assert actividad == expected_actividad == Decimal("22473.79")


class TestAutotaxi7212EstimacionObjetivaHfp1359Orden:
    """Epígrafe IAE 721.2 (Transporte por autotaxis) on the Orden HFP/1359/2023 revision."""

    def test_fase_1_rendimiento_neto_previo_matches_hfp_1359_orden_coefficients(self) -> None:
        # 0 personal asalariado, 1 personal no asalariado (titular), 40 (1.000 km).
        previo, _minorado, _modulos, _actividad = _run_hfp_1359_engine(
            "721.2",
            modulo_1=Decimal("0"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("40"),
        )
        expected_previo = round_to_cents(Decimal("1") * _AUTOTAXI_721_2[2] + Decimal("40") * _AUTOTAXI_721_2[3])
        assert previo == expected_previo == Decimal("9460.09")


class TestHfp1359OrdenPartialTableCoverageDoesNotSilentlyMisattribute:
    """An Orden HFP/1359/2023 activity absent from the phased dataset resolves to zero, not a fabricated figure."""

    def test_untabled_epigrafe_resolves_to_zero_on_hfp_1359_orden_revision(self) -> None:
        previo, minorado, modulos, actividad = _run_hfp_1359_engine(
            "699.9",  # not an Orden Anexo II épigrafe — remains untabled
            modulo_1=Decimal("5"),
            modulo_2=Decimal("3"),
        )
        assert previo == Decimal("0")
        assert minorado == Decimal("0")
        assert modulos == Decimal("0")
        assert actividad == Decimal("0")

    def test_hfp_1359_and_hac_1347_orden_engines_agree_for_the_same_tabled_activity(self) -> None:
        """Cross-revision parity proof.

        The 2024 and 2025 engines must produce the same rendimiento-neto-de-la-
        actividad figure for the same declared units on an épigrafe whose Orden
        coefficients are byte-identical across both years — an independent check
        that the 2024 back-fill did not silently drift from its 2025 source
        (aeat-calculation-aggregation).
        """
        successor_snapshot = published_snapshot(
            "131", filing_year=_ORDEN_HAC_1347_2024_EXERCISE, period="1T", grade=RegistryAuthorityGrade.CALCULATION
        )
        assert successor_snapshot.filing_period is not None
        successor_result = calculate_registry_snapshot(
            successor_snapshot,
            inputs={
                "modulos-1-unidades": Decimal("2"),
                "modulos-2-unidades": Decimal("1"),
                "modulos-3-unidades": Decimal("50"),
                "modulos-4-unidades": Decimal("30"),
                "modulos-5-unidades": Decimal("0"),
                "modulos-6-unidades": Decimal("0"),
                "modulos-7-unidades": Decimal("0"),
                "modulos-1-unidades-anterior": Decimal("0"),
                "modulos-minoracion-inversion": Decimal("0"),
            },
            text_inputs={"modulos-epigrafe": "972.1"},
            date_context={"filing_period": successor_snapshot.filing_period.end_date},
        )
        _previo, _minorado, _modulos, actividad = _run_hfp_1359_engine(
            "972.1",
            modulo_1=Decimal("2"),
            modulo_2=Decimal("1"),
            modulo_3=Decimal("50"),
            modulo_4=Decimal("30"),
        )
        successor_actividad = successor_result.values["modulos-rendimiento-neto-actividad"]
        assert actividad == successor_actividad == Decimal("22473.79")


class TestHfp1359OrdenDateAxisBoundaries:
    """Historical date-axis boundaries: the Orden HFP/1359/2023 revision and its
    módulos coefficient table are scoped to their calendar year and do not leak into
    neighbouring revisions.
    """

    def test_hfp_1359_orden_exercise_selects_its_revision_across_the_calendar_year(self) -> None:
        exercise = _ORDEN_HFP_1359_2023_EXERCISE
        modelos, _catalogues = bundled_registry_tree()
        modelo_131 = next(modelo for modelo in modelos if modelo.id == "131")
        revision = select_revision(modelo_131, filing_year=exercise, period="1T", on=date(exercise, 1, 1))
        assert revision.id == str(exercise)
        revision = select_revision(modelo_131, filing_year=exercise, period="4T", on=date(exercise, 12, 31))
        assert revision.id == str(exercise)

    def test_neighbouring_exercises_do_not_cross_into_the_hfp_1359_orden_revision(self) -> None:
        exercise = _ORDEN_HFP_1359_2023_EXERCISE
        modelos, _catalogues = bundled_registry_tree()
        modelo_131 = next(modelo for modelo in modelos if modelo.id == "131")
        # The last day before the revision's valid_from resolves to the flatter historical
        # revision the registry authors immediately before it.
        authored_before = max(
            (revision for revision in modelo_131.revisions.values() if revision.valid_from.year < exercise),
            key=lambda revision: revision.valid_from,
        )
        preceding = select_revision(modelo_131, filing_year=exercise - 1, period="4T", on=date(exercise - 1, 12, 31))
        assert preceding.id == authored_before.id
        # The first day after its valid_to resolves to the Orden HAC/1347/2024 revision.
        successor = _ORDEN_HAC_1347_2024_EXERCISE
        following = select_revision(modelo_131, filing_year=successor, period="1T", on=date(successor, 1, 1))
        assert following.id == str(successor)

    def test_hfp_1359_orden_coefficient_parameters_cover_its_calendar_year(self) -> None:
        """Orden HFP/1359/2023's figures are in force on every day of its exercise.

        A figure an earlier Orden already fixed at the same amount runs open from
        that Orden's exercise, and a figure the next Orden restates unchanged runs
        open past this one, so neither end of an unchanged row is this Orden's to
        fix. The reducción general differs from the previous exercise's rate, so
        the row this Orden fixes starts on its exercise's first day.
        """
        exercise = _ORDEN_HFP_1359_2023_EXERCISE
        first_day, last_day = date(exercise, 1, 1), date(exercise, 12, 31)
        snapshot = published_snapshot(
            "131", filing_year=_ORDEN_HFP_1359_2023_EXERCISE, period="1T", grade=RegistryAuthorityGrade.CALCULATION
        )
        coeficientes = next(
            parameter for parameter in snapshot.revision.parameters if parameter.id == "m131-modulos-coeficientes"
        )
        reduccion_general = next(
            parameter for parameter in snapshot.revision.parameters if parameter.id == "m131-modulos-reduccion-general"
        )
        in_force = [
            row
            for row in (*coeficientes.keyed_brackets, *reduccion_general.values)
            if row.valid_from <= last_day and (row.valid_to is None or row.valid_to >= first_day)
        ]
        assert in_force
        for row in in_force:
            assert row.valid_from <= first_day
            assert row.valid_to is None or row.valid_to >= last_day
        (reduccion_row,) = [row for row in reduccion_general.values if row in in_force]
        assert reduccion_row.valid_from == first_day

    def test_hfp_1359_and_hac_1347_orden_coefficient_tables_are_in_force_across_each_year(self) -> None:
        """The two Ordenes' revisions share the coefficient parameter's identity,
        and each revision's snapshot carries only rows in force on every day of
        its own exercise -- none that ended before it or starts within it."""
        for year in (_ORDEN_HFP_1359_2023_EXERCISE, _ORDEN_HAC_1347_2024_EXERCISE):
            snapshot = published_snapshot(
                "131", filing_year=year, period="1T", grade=RegistryAuthorityGrade.CALCULATION
            )
            coeficientes = next(
                parameter for parameter in snapshot.revision.parameters if parameter.id == "m131-modulos-coeficientes"
            )
            assert coeficientes.keyed_brackets, year
            for row in coeficientes.keyed_brackets:
                assert row.valid_from is not None
                assert row.valid_from <= date(year, 1, 1)
                assert row.valid_to is None or row.valid_to >= date(year, 12, 31)
