"""Contract tests for the six detail-record observation types.

Validates pydantic field constraints, validator semantics, and the
deterministic row-builder helpers for the observation surfaces feeding
the per-record tipo-2 row-producer bindings on the IRPF retencion
modelos (190 / 193 perceptors), the IS related-party operations modelo
(232), the foreign-asset informative modelo (720), the régimen de
atribución de rentas modelo (184), the IVA refund operations modelo
(360), and the donativos/donaciones/aportaciones informativa modelo
(182).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError

from .....core import M720AssetClassCode
from .....core.aggregation import RetencionClave
from .._bindings import (
    AtributionMemberObservation,
    DonativoDonorObservation,
    Modelo720RowObservation,
    RefundOperationObservation,
    RelatedPartyOperationObservation,
)
from .._detail_record_bindings import _build_related_party_rows
from .._donativo_bindings import _build_donativo_rows
from .._withholding_bindings import (
    WithholdingObservation,
    _build_withholding_rows,
)
from .._errors import RegistryValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# ---------------------------------------------------------------------------
# WithholdingObservation
# ---------------------------------------------------------------------------


def test_withholding_observation_country_code_must_be_uppercase_alphabetic() -> None:
    with pytest.raises(ValidationError, match="country_code must be uppercase alphabetic"):
        WithholdingObservation(
            source_id="p1",
            perceptor_tax_id="12345678A",
            country_code="es",
            transaction_date=date(2025, 3, 15),
            clave=RetencionClave.A,
        )
    with pytest.raises(ValidationError, match="country_code must be uppercase alphabetic"):
        WithholdingObservation(
            source_id="p1",
            perceptor_tax_id="12345678A",
            country_code="E1",
            transaction_date=date(2025, 3, 15),
            clave=RetencionClave.A,
        )


def test_withholding_observation_clave_must_be_a_valid_retencion_clave() -> None:
    """A lowercase / out-of-set clave is refused: ``clave`` is the typed
    :class:`RetencionClave` (Modelo 190/193 A-L), so ``"a"`` (lowercase) is not a
    member.
    """
    with pytest.raises(ValidationError, match="not a valid RetencionClave"):
        WithholdingObservation.model_validate(
            {
                "source_id": "p1",
                "perceptor_tax_id": "12345678A",
                "transaction_date": date(2025, 3, 15),
                "clave": "a",
            }
        )


def test_withholding_observation_amounts_reject_negative() -> None:
    with pytest.raises(ValidationError, match="amounts must be non-negative"):
        WithholdingObservation(
            source_id="p1",
            perceptor_tax_id="12345678A",
            transaction_date=date(2025, 3, 15),
            clave=RetencionClave.A,
            retencion_practicada=Decimal("-1"),
        )


def test_withholding_observation_amounts_must_be_decimal_not_bool() -> None:
    with pytest.raises(ValidationError):
        WithholdingObservation(
            source_id="p1",
            perceptor_tax_id="12345678A",
            transaction_date=date(2025, 3, 15),
            clave=RetencionClave.A,
            retencion_practicada=cast(Decimal, True),
        )


def test_build_withholding_rows_per_perceptor_sums_amounts() -> None:
    a_dinerario_q1 = Decimal("10000")
    a_dinerario_q2 = Decimal("5000")
    a_retencion_q1 = Decimal("1500")
    a_retencion_q2 = Decimal("750")
    z_dinerario = Decimal("30000")
    obs = (
        WithholdingObservation(
            source_id="p1a",
            perceptor_tax_id="12345678A",
            perceptor_legal_name="P One",
            transaction_date=date(2025, 3, 15),
            clave=RetencionClave.A,
            percibido_dinerario=a_dinerario_q1,
            retencion_practicada=a_retencion_q1,
        ),
        WithholdingObservation(
            source_id="p1b",
            perceptor_tax_id="12345678A",
            perceptor_legal_name="P One",
            transaction_date=date(2025, 6, 15),
            clave=RetencionClave.A,
            percibido_dinerario=a_dinerario_q2,
            retencion_practicada=a_retencion_q2,
        ),
        WithholdingObservation(
            source_id="p2",
            perceptor_tax_id="87654321Z",
            perceptor_legal_name="P Two",
            transaction_date=date(2025, 4, 1),
            clave=RetencionClave.G,
            percibido_dinerario=z_dinerario,
            retencion_practicada=Decimal("5500"),
        ),
    )

    rows = _build_withholding_rows("per_perceptor", obs)

    assert len(rows) == 2
    by_nif = {row["perceptor_tax_id"]: row for row in rows}
    assert by_nif["12345678A"]["percibido_dinerario"] == a_dinerario_q1 + a_dinerario_q2
    assert by_nif["12345678A"]["retencion_practicada"] == a_retencion_q1 + a_retencion_q2
    assert by_nif["87654321Z"]["percibido_dinerario"] == z_dinerario


def test_build_withholding_rows_per_perceptor_clave_distinguishes_clave_tuples() -> None:
    obs = (
        WithholdingObservation(
            source_id="p1a",
            perceptor_tax_id="12345678A",
            transaction_date=date(2025, 3, 15),
            clave=RetencionClave.A,
            percibido_dinerario=Decimal("100"),
        ),
        WithholdingObservation(
            source_id="p1b",
            perceptor_tax_id="12345678A",
            transaction_date=date(2025, 4, 15),
            clave=RetencionClave.G,
            percibido_dinerario=Decimal("200"),
        ),
    )

    rows = _build_withholding_rows("per_perceptor_clave", obs)

    assert len(rows) == 2
    keys = {(row["perceptor_tax_id"], row["clave"]) for row in rows}
    assert keys == {("12345678A", "A"), ("12345678A", "G")}


def test_build_withholding_rows_omits_the_key_for_an_unstated_country() -> None:
    """Absence propagates as an absent KEY, so a binding needing it refuses.

    The payload carries decimals and strings and cannot hold a null, and the
    shipped resolver already raises a not-produced error naming the binding when
    a row_field is missing. So the absence surfaces there -- visibly, with the
    binding named -- instead of as a silent country nobody stated.
    """

    def _observation(country: str | None) -> WithholdingObservation:
        return WithholdingObservation(
            source_id=f"row-{country}",
            perceptor_tax_id="12345678A",
            perceptor_legal_name="Perceptor One",
            country_code=country,
            transaction_date=date(2025, 12, 31),
            clave=RetencionClave.A,
        )

    stated = _build_withholding_rows("per_perceptor", (_observation("FR"),))[0]
    unstated = _build_withholding_rows("per_perceptor", (_observation(None),))[0]

    assert stated["country_code"] == "FR"
    assert "country_code" not in unstated


# ---------------------------------------------------------------------------
# Withholding row design-completion rules (Modelo 190 Tipo 2)
# ---------------------------------------------------------------------------


_M190_DECLARED_FIELDS = frozenset(
    {
        "perceptor_tax_id",
        "perceptor_legal_name",
        "clave",
        "subclave",
        "percibido_dinerario",
        "percibido_especie",
        "retencion_practicada",
        "ingreso_a_cuenta",
        "country_code",
        "province_code",
        "territorial_deduction_clave",
        "perceptor_birth_year",
        "perceptor_situacion_familiar",
        "representative_tax_id",
        "spouse_or_unit_titular_tax_id",
        "disability_clave",
        "contract_relation_clave",
        "unit_convivencia_titular_clave",
        "geographic_mobility_clave",
        "ingreso_a_cuenta_repercutido",
        "accrual_year",
        "reducciones_aplicables",
        "gastos_deducibles",
        "pension_compensatoria",
        "anualidades_alimentos",
        "descendants_under_3_total",
        "descendants_under_3_whole",
        "descendants_rest_total",
        "descendants_rest_whole",
        "descendants_disabled_33_65_total",
        "descendants_disabled_33_65_whole",
        "descendants_disabled_mobility_total",
        "descendants_disabled_mobility_whole",
        "descendants_disabled_65_plus_total",
        "descendants_disabled_65_plus_whole",
        "ascendants_under_75_total",
        "ascendants_under_75_whole",
        "ascendants_75_plus_total",
        "ascendants_75_plus_whole",
        "ascendants_disabled_33_65_total",
        "ascendants_disabled_33_65_whole",
        "ascendants_disabled_mobility_total",
        "ascendants_disabled_mobility_whole",
        "ascendants_disabled_65_plus_total",
        "ascendants_disabled_65_plus_whole",
        "first_child_compute",
        "second_child_compute",
        "third_child_compute",
        "housing_loan_communication_clave",
        "incapacity_cash_perception",
        "incapacity_cash_withholding",
        "incapacity_kind_value",
        "incapacity_kind_ingreso_a_cuenta",
        "incapacity_kind_repercutido",
        "complemento_infancia_clave",
        "emerging_stock_excess_clave",
        "foral_retention_estatal",
        "foral_retention_navarra",
        "foral_retention_araba",
        "foral_retention_gipuzkoa",
        "foral_retention_bizkaia",
        "startup_fund_rendimientos_clave",
        "pension_prestacion_jubilacion",
        "pension_prestacion_viudedad",
        "pension_prestacion_incapacidad",
        "pension_prestacion_no_contributiva",
        "pension_prestacion_resto",
    }
)

#: The complete fact set the design mandates for a clave A row.
_COMPLETE_CLAVE_A = {
    "perceptor_birth_year": 1985,
    "perceptor_situacion_familiar": 1,
    "disability_clave": 0,
    "contract_relation_clave": 1,
    "geographic_mobility_clave": 0,
    "housing_loan_communication_clave": 0,
}


def _observation(**overrides: object) -> WithholdingObservation:
    base: dict[str, object] = {
        "source_id": "row-1",
        "perceptor_tax_id": "12345678A",
        "perceptor_legal_name": "Perceptor One",
        "transaction_date": date(2025, 12, 31),
        "clave": RetencionClave.A,
    }
    base.update(overrides)
    return WithholdingObservation(**base)


def _build(*observations: WithholdingObservation, declared: bool = True) -> tuple[dict[str, object], ...]:
    fields = _M190_DECLARED_FIELDS if declared else frozenset()
    return tuple(
        dict(row)
        for row in _build_withholding_rows("per_perceptor_clave", observations, required_fields=fields)
    )


def test_build_withholding_rows_completes_a_declared_clave_a_row() -> None:
    rows = _build(_observation(**_COMPLETE_CLAVE_A))

    assert len(rows) == 1
    row = rows[0]
    assert row["perceptor_birth_year"] == "1985"
    assert row["perceptor_situacion_familiar"] == "1"
    assert row["disability_clave"] == "0"
    assert row["contract_relation_clave"] == "1"
    assert row["geographic_mobility_clave"] == "0"
    assert row["representative_tax_id"] == " " * 9
    assert row["spouse_or_unit_titular_tax_id"] == " " * 9
    assert row["unit_convivencia_titular_clave"] == " "
    assert row["accrual_year"] == "0000"
    assert row["ingreso_a_cuenta_repercutido"] == Decimal("0")


def test_build_withholding_rows_refuses_clave_a_without_contract_or_mobility() -> None:
    """The design records a contract type and a mobility flag on every clave-A
    row -- clave 0/1 are recorded facts, never a default -- so an eligible row
    whose observation carries neither refuses instead of filing a silent blank."""
    with pytest.raises(RegistryValidationError, match="contract_relation_clave"):
        _build(
            _observation(
                **{key: value for key, value in _COMPLETE_CLAVE_A.items() if key != "contract_relation_clave"}
            )
        )
    with pytest.raises(RegistryValidationError, match="geographic_mobility_clave"):
        _build(
            _observation(
                **{key: value for key, value in _COMPLETE_CLAVE_A.items() if key != "geographic_mobility_clave"}
            )
        )


def test_build_withholding_rows_refuses_eligible_row_without_birth_situation_disability() -> None:
    for missing in ("perceptor_birth_year", "perceptor_situacion_familiar", "disability_clave"):
        with pytest.raises(RegistryValidationError, match=missing):
            _build(
                _observation(
                    **{key: value for key, value in _COMPLETE_CLAVE_A.items() if key != missing}
                )
            )


def test_build_withholding_rows_writes_design_no_content_for_ineligible_claves() -> None:
    """A clave G row is outside the design's datos-adicionales block: the numeric
    slots carry the design's own zeros and the clave-restricted one-digit slots
    carry spaces, with no refusal."""
    rows = _build(_observation(clave=RetencionClave.G, subclave="01"))

    row = rows[0]
    assert row["perceptor_birth_year"] == "0000"
    assert row["perceptor_situacion_familiar"] == "0"
    assert row["disability_clave"] == " "
    assert row["contract_relation_clave"] == " "
    assert row["unit_convivencia_titular_clave"] == " "
    assert row["geographic_mobility_clave"] == " "
    assert row["accrual_year"] == "0000"


def test_build_withholding_rows_does_not_enforce_undeclared_fields() -> None:
    """Modelo 193 rows share this observation class but declare none of the
    datos-adicionales fields, so a fact-less clave-A row must not refuse when the
    resolving revision never asked for those fields."""
    rows = _build(_observation(), declared=False)
    assert len(rows) == 1


def test_build_withholding_rows_refuses_out_of_context_facts() -> None:
    """A fact the design restricts to certain claves arriving on a row outside
    those claves is contradictory input, not data to silently drop."""
    with pytest.raises(RegistryValidationError, match="contract_relation_clave"):
        _build(_observation(clave=RetencionClave.G, contract_relation_clave=1))
    with pytest.raises(RegistryValidationError, match="disability_clave"):
        _build(_observation(clave=RetencionClave.D, disability_clave=0))
    with pytest.raises(RegistryValidationError, match="perceptor_birth_year"):
        _build(_observation(clave=RetencionClave.G, perceptor_birth_year=1990))


def test_build_withholding_rows_spouse_nif_follows_situacion_and_differs_from_perceptor() -> None:
    spouse = "98765432B"
    with pytest.raises(RegistryValidationError, match="spouse_or_unit_titular_tax_id"):
        # Situacion familiar 2 obligates the spouse NIF.
        _build(
            _observation(
                **{
                    **_COMPLETE_CLAVE_A,
                    "perceptor_situacion_familiar": 2,
                }
            )
        )
    with pytest.raises(RegistryValidationError, match="equals the perceptor's own NIF"):
        _build(
            _observation(
                **{
                    **_COMPLETE_CLAVE_A,
                    "perceptor_situacion_familiar": 2,
                    "spouse_or_unit_titular_tax_id": "12345678A",
                }
            )
        )
    with pytest.raises(RegistryValidationError, match="declares only when"):
        # Situacion familiar 1 declares no spouse: the fact contradicts the design.
        _build(_observation(**_COMPLETE_CLAVE_A, spouse_or_unit_titular_tax_id=spouse))
    row = _build(
        _observation(
            **{
                **_COMPLETE_CLAVE_A,
                "perceptor_situacion_familiar": 2,
                "spouse_or_unit_titular_tax_id": spouse,
            }
        )
    )[0]
    assert row["spouse_or_unit_titular_tax_id"] == spouse


def test_build_withholding_rows_l29_requires_titular_clave_and_spouse_when_titular_two() -> None:
    titular_nif = "98765432B"
    l29 = {
        "clave": RetencionClave.L,
        "subclave": "29",
        "complemento_infancia_clave": 1,
    }
    with pytest.raises(RegistryValidationError, match="unit_convivencia_titular_clave"):
        _build(_observation(**l29))
    with pytest.raises(RegistryValidationError, match="spouse_or_unit_titular_tax_id"):
        _build(_observation(**l29, unit_convivencia_titular_clave=2))
    row = _build(_observation(**l29, unit_convivencia_titular_clave=1))[0]
    assert row["unit_convivencia_titular_clave"] == "1"
    assert row["spouse_or_unit_titular_tax_id"] == " " * 9
    row = _build(
        _observation(**l29, unit_convivencia_titular_clave=2, spouse_or_unit_titular_tax_id=titular_nif)
    )[0]
    assert row["spouse_or_unit_titular_tax_id"] == titular_nif


def test_build_withholding_rows_merges_a_fact_carried_only_by_a_later_observation() -> None:
    """First observation carries no contract type, the second does: the cohort's
    row must end with the fact, not with the first-touch absence."""
    rows = _build(
        _observation(**{key: value for key, value in _COMPLETE_CLAVE_A.items() if key != "contract_relation_clave"}),
        _observation(**_COMPLETE_CLAVE_A, source_id="row-2", percibido_dinerario=Decimal("100")),
    )
    assert len(rows) == 1
    assert rows[0]["contract_relation_clave"] == "1"
    assert rows[0]["percibido_dinerario"] == Decimal("100")


def test_build_withholding_rows_still_refuses_a_contradicting_later_observation() -> None:
    def _with_contract(clave: int, **extra: object) -> WithholdingObservation:
        facts = {key: value for key, value in _COMPLETE_CLAVE_A.items() if key != "contract_relation_clave"}
        return _observation(**facts, contract_relation_clave=clave, **extra)

    with pytest.raises(RegistryValidationError, match="disagree on 'contract_relation_clave'"):
        _build(
            _with_contract(1),
            _with_contract(2, source_id="row-2"),
        )


def test_build_withholding_rows_sums_repercutido_and_defaults_accrual_year() -> None:
    rows = _build(
        _observation(
            **_COMPLETE_CLAVE_A,
            emerging_stock_excess_clave=0,
            ingreso_a_cuenta_repercutido=Decimal("300"),
            source_id="row-1",
        ),
        _observation(
            **_COMPLETE_CLAVE_A,
            emerging_stock_excess_clave=0,
            ingreso_a_cuenta_repercutido=Decimal("200"),
            accrual_year=2023,
            source_id="row-2",
        ),
    )
    row = rows[0]
    assert row["ingreso_a_cuenta_repercutido"] == Decimal("500")
    assert row["accrual_year"] == "2023"
    assert _build(_observation(**_COMPLETE_CLAVE_A))[0]["accrual_year"] == "0000"


def test_build_withholding_rows_sums_deduction_side_amounts() -> None:
    """The four deduction-side money campos accumulate across observations and
    default to the design's own zeros when no observation carries an amount."""
    rows = _build(
        _observation(
            **_COMPLETE_CLAVE_A,
            reducciones_aplicables=Decimal("1000"),
            gastos_deducibles=Decimal("2000"),
            pension_compensatoria=Decimal("3000"),
            anualidades_alimentos=Decimal("4000"),
        ),
        _observation(
            **_COMPLETE_CLAVE_A,
            source_id="row-2",
            reducciones_aplicables=Decimal("500"),
            gastos_deducibles=Decimal("250"),
        ),
    )
    row = rows[0]
    assert row["reducciones_aplicables"] == Decimal("1500")
    assert row["gastos_deducibles"] == Decimal("2250")
    assert row["pension_compensatoria"] == Decimal("3000")
    assert row["anualidades_alimentos"] == Decimal("4000")

    empty = _build(_observation(**_COMPLETE_CLAVE_A))[0]
    assert empty["reducciones_aplicables"] == Decimal("0")
    assert empty["gastos_deducibles"] == Decimal("0")
    assert empty["pension_compensatoria"] == Decimal("0")
    assert empty["anualidades_alimentos"] == Decimal("0")


def test_build_withholding_rows_refuses_deduction_amounts_outside_their_claves() -> None:
    """A nonzero deduction-side amount on a row whose clave the design does not
    declare is contradictory input; a zero amount is the design's no-content."""
    with pytest.raises(RegistryValidationError, match="reducciones_aplicables"):
        _build(_observation(clave=RetencionClave.D, reducciones_aplicables=Decimal("100")))
    with pytest.raises(RegistryValidationError, match="gastos_deducibles"):
        _build(_observation(clave=RetencionClave.D, gastos_deducibles=Decimal("100")))
    with pytest.raises(RegistryValidationError, match="pension_compensatoria"):
        _build(_observation(clave=RetencionClave.G, pension_compensatoria=Decimal("100")))
    with pytest.raises(RegistryValidationError, match="anualidades_alimentos"):
        _build(_observation(clave=RetencionClave.G, anualidades_alimentos=Decimal("100")))
    # E.02 declares gastos; G.06 declares reducciones: eligible rows pass.
    row = _build(
        _observation(clave=RetencionClave.E, subclave="02", gastos_deducibles=Decimal("120"))
    )[0]
    assert row["gastos_deducibles"] == Decimal("120")
    row = _build(
        _observation(clave=RetencionClave.G, subclave="06", reducciones_aplicables=Decimal("120"))
    )[0]
    assert row["reducciones_aplicables"] == Decimal("120")


def test_build_withholding_rows_completes_family_composition_counts() -> None:
    """Each count slot carries the design's own zero when no observation records
    it, and the recorded count otherwise; the prestamos-vivienda clave is a
    recorded fact on every eligible row."""
    rows = _build(
        _observation(
            **{
                **_COMPLETE_CLAVE_A,
                "descendants_under_3_total": 1,
                "descendants_under_3_whole": 1,
                "descendants_rest_total": 2,
                "descendants_rest_whole": 0,
                "descendants_disabled_33_65_total": 1,
                "descendants_disabled_33_65_whole": 1,
                "descendants_disabled_mobility_total": 0,
                "descendants_disabled_mobility_whole": 0,
                "descendants_disabled_65_plus_total": 0,
                "descendants_disabled_65_plus_whole": 0,
                "ascendants_under_75_total": 2,
                "ascendants_under_75_whole": 1,
                "ascendants_75_plus_total": 0,
                "ascendants_75_plus_whole": 0,
                "ascendants_disabled_33_65_total": 0,
                "ascendants_disabled_33_65_whole": 0,
                "ascendants_disabled_mobility_total": 0,
                "ascendants_disabled_mobility_whole": 0,
                "ascendants_disabled_65_plus_total": 0,
                "ascendants_disabled_65_plus_whole": 0,
                "first_child_compute": 1,
                "second_child_compute": 2,
                "third_child_compute": 1,
                "housing_loan_communication_clave": 1,
            }
        )
    )
    row = rows[0]
    assert row["descendants_under_3_total"] == "1"
    assert row["descendants_rest_total"] == "2"
    assert row["descendants_disabled_65_plus_total"] == "0"
    assert row["first_child_compute"] == "1"
    assert row["second_child_compute"] == "2"
    assert row["housing_loan_communication_clave"] == "1"

    empty = _build(_observation(**_COMPLETE_CLAVE_A))[0]
    for field in (
        "descendants_under_3_total",
        "descendants_rest_total",
        "descendants_disabled_65_plus_total",
        "ascendants_under_75_total",
        "first_child_compute",
    ):
        assert empty[field] == "0"
    assert empty["housing_loan_communication_clave"] == "0"


def test_build_withholding_rows_refuses_eligible_row_without_housing_clave() -> None:
    with pytest.raises(RegistryValidationError, match="housing_loan_communication_clave"):
        _build(
            _observation(
                **{key: value for key, value in _COMPLETE_CLAVE_A.items() if key != "housing_loan_communication_clave"}
            )
        )


def test_build_withholding_rows_refuses_family_counts_outside_their_claves() -> None:
    """A nonzero family count on a row outside claves A/B/C contradicts the
    design; a zero count is the design's no-content."""
    with pytest.raises(RegistryValidationError, match="descendants_under_3_total"):
        _build(_observation(clave=RetencionClave.D, descendants_under_3_total=2))
    with pytest.raises(RegistryValidationError, match="first_child_compute"):
        _build(_observation(clave=RetencionClave.G, first_child_compute=1))
    with pytest.raises(RegistryValidationError, match="housing_loan_communication_clave"):
        _build(_observation(clave=RetencionClave.G, housing_loan_communication_clave=1))
    # Zero counts are the design's no-content on any row.
    row = _build(_observation(clave=RetencionClave.G, descendants_rest_total=0))[0]
    assert row["descendants_rest_total"] == "0"
    assert row["housing_loan_communication_clave"] == " "


def test_build_withholding_rows_incapacidad_parts_file_on_their_claves() -> None:
    """The incap blocks are the design's own split of the row's magnitudes:
    cash parts on claves A/B.01, in-kind parts on clave A, zeros elsewhere."""
    row = _build(
        _observation(
            **_COMPLETE_CLAVE_A,
            incapacity_cash_perception=Decimal("3000"),
            incapacity_cash_withholding=Decimal("450"),
            incapacity_kind_value=Decimal("1200"),
            incapacity_kind_ingreso_a_cuenta=Decimal("200"),
            incapacity_kind_repercutido=Decimal("200"),
        )
    )[0]
    assert row["incapacity_cash_perception"] == Decimal("3000")
    assert row["incapacity_cash_withholding"] == Decimal("450")
    assert row["incapacity_kind_value"] == Decimal("1200")
    # B.01 declares the dineraria block only.
    row_b01 = _build(
        _observation(
            clave=RetencionClave.B,
            subclave="01",
            perceptor_birth_year=1960,
            perceptor_situacion_familiar=1,
            disability_clave=0,
            housing_loan_communication_clave=0,
            pension_prestacion_jubilacion=0,
            pension_prestacion_viudedad=0,
            pension_prestacion_incapacidad=1,
            pension_prestacion_no_contributiva=0,
            pension_prestacion_resto=0,
            incapacity_cash_perception=Decimal("900"),
        )
    )[0]
    assert row_b01["incapacity_cash_perception"] == Decimal("900")
    with pytest.raises(RegistryValidationError, match="incapacity_cash_perception"):
        _build(_observation(clave=RetencionClave.G, incapacity_cash_perception=Decimal("1")))
    with pytest.raises(RegistryValidationError, match="incapacity_kind_value"):
        _build(
            _observation(
                clave=RetencionClave.B,
                subclave="01",
                perceptor_birth_year=1960,
                perceptor_situacion_familiar=1,
                disability_clave=0,
                housing_loan_communication_clave=0,
                pension_prestacion_jubilacion=0,
                pension_prestacion_viudedad=0,
                pension_prestacion_incapacidad=0,
                pension_prestacion_no_contributiva=0,
                pension_prestacion_resto=0,
                incapacity_kind_value=Decimal("1"),
            )
        )
    with pytest.raises(RegistryValidationError, match="incapacity_kind_ingreso_a_cuenta"):
        _build(_observation(clave=RetencionClave.G, incapacity_kind_ingreso_a_cuenta=Decimal("1")))


def test_withholding_totals_include_the_incapacidad_parts() -> None:
    """The resumen-anual magnitudes are the row's FULL totals: the design's
    split of the base and incap blocks must not under-count the summary."""
    from .._withholding_bindings import percibido_total, retencion_total

    observations = (
        _observation(
            **_COMPLETE_CLAVE_A,
            percibido_dinerario=Decimal("7000"),
            percibido_especie=Decimal("1000"),
            retencion_practicada=Decimal("1050"),
            ingreso_a_cuenta=Decimal("150"),
            incapacity_cash_perception=Decimal("3000"),
            incapacity_cash_withholding=Decimal("450"),
            incapacity_kind_value=Decimal("1200"),
            incapacity_kind_ingreso_a_cuenta=Decimal("200"),
            incapacity_kind_repercutido=Decimal("200"),
        ),
    )
    assert percibido_total(observations) == Decimal("12200")
    assert retencion_total(observations) == Decimal("1850")


def test_build_withholding_rows_l29_requires_complemento_infancia_clave() -> None:
    with pytest.raises(RegistryValidationError, match="complemento_infancia_clave"):
        _build(_observation(clave=RetencionClave.L, subclave="29", unit_convivencia_titular_clave=1))
    with pytest.raises(RegistryValidationError, match="complemento_infancia_clave"):
        _build(_observation(**_COMPLETE_CLAVE_A, complemento_infancia_clave=1))
    row = _build(
        _observation(
            clave=RetencionClave.L,
            subclave="29",
            unit_convivencia_titular_clave=1,
            complemento_infancia_clave=2,
        )
    )[0]
    assert row["complemento_infancia_clave"] == "2"


def test_build_withholding_rows_foral_split_follows_clave_e_totals() -> None:
    """Design campo 35 is declared exclusively for clave E and must sum to the
    row's retenciones practicadas plus ingresos a cuenta."""
    e_facts = {
        "clave": RetencionClave.E,
        "retencion_practicada": Decimal("3000"),
        "ingreso_a_cuenta": Decimal("200"),
    }
    with pytest.raises(RegistryValidationError, match="require foral retentions"):
        _build(_observation(**e_facts))
    with pytest.raises(RegistryValidationError, match="declares exclusively for clave E"):
        _build(_observation(**_COMPLETE_CLAVE_A, foral_retention_estatal=Decimal("1")))
    with pytest.raises(RegistryValidationError, match="requires to equal"):
        _build(
            _observation(
                **e_facts,
                foral_retention_estatal=Decimal("3000"),
                foral_retention_navarra=Decimal("300"),
            )
        )
    row = _build(
        _observation(
            **e_facts,
            foral_retention_estatal=Decimal("2500"),
            foral_retention_navarra=Decimal("700"),
        )
    )[0]
    assert row["foral_retention_estatal"] == Decimal("2500")
    assert row["foral_retention_navarra"] == Decimal("700")
    # Exclusively Estatal: the one subfield carries the full sum.
    row = _build(_observation(**e_facts, foral_retention_estatal=Decimal("3200")))[0]
    assert row["foral_retention_estatal"] == Decimal("3200")


def test_build_withholding_rows_emerging_stock_clave_follows_especie_content() -> None:
    """Design campo 36 is recorded only for clave A rows whose especie block has
    content; both claves are recorded facts, and the field is spaces when the
    design says not to complete it."""
    with_especie = {**_COMPLETE_CLAVE_A, "percibido_especie": Decimal("12000")}
    row = _build(_observation(**with_especie, emerging_stock_excess_clave=0))[0]
    assert row["emerging_stock_excess_clave"] == "0"
    with pytest.raises(RegistryValidationError, match="emerging_stock_excess_clave"):
        # Especie content obligates the clave.
        _build(_observation(**with_especie))
    with pytest.raises(RegistryValidationError, match="especie block has content"):
        # The clave without in-kind percepciones contradicts the design.
        _build(_observation(**_COMPLETE_CLAVE_A, emerging_stock_excess_clave=0))
    with pytest.raises(RegistryValidationError, match="declares only for clave A"):
        _build(_observation(clave=RetencionClave.G, emerging_stock_excess_clave=1))
    assert _build(_observation(**_COMPLETE_CLAVE_A))[0]["emerging_stock_excess_clave"] == " "


def test_build_withholding_rows_2025_b01_prestacion_flags_are_mandatory() -> None:
    """Each of the five 2025-edition prestacion flags is an always-recorded 0/1
    fact on clave B.01 rows; elsewhere the field carries spaces."""
    b01 = {
        "clave": RetencionClave.B,
        "subclave": "01",
        "perceptor_birth_year": 1955,
        "perceptor_situacion_familiar": 1,
        "disability_clave": 0,
        "housing_loan_communication_clave": 0,
    }
    with pytest.raises(RegistryValidationError, match="pension_prestacion_jubilacion"):
        _build(_observation(**b01))
    row = _build(
        _observation(
            **b01,
            pension_prestacion_jubilacion=1,
            pension_prestacion_viudedad=0,
            pension_prestacion_incapacidad=0,
            pension_prestacion_no_contributiva=0,
            pension_prestacion_resto=0,
        )
    )[0]
    assert row["pension_prestacion_jubilacion"] == "1"
    assert row["pension_prestacion_viudedad"] == "0"
    with pytest.raises(RegistryValidationError, match="pension_prestacion_jubilacion"):
        _build(_observation(**_COMPLETE_CLAVE_A, pension_prestacion_jubilacion=1))
    assert _build(_observation(**_COMPLETE_CLAVE_A))[0]["pension_prestacion_jubilacion"] == " "


def test_build_withholding_rows_2025_startup_fund_clave_is_recorded_when_applicable() -> None:
    """The 2025-edition startup-fund rendimientos clave is recorded-when-applicable:
    spaces when the payer did not record it, refused outside clave A."""
    row = _build(_observation(**_COMPLETE_CLAVE_A, startup_fund_rendimientos_clave=1))[0]
    assert row["startup_fund_rendimientos_clave"] == "1"
    assert _build(_observation(**_COMPLETE_CLAVE_A))[0]["startup_fund_rendimientos_clave"] == " "
    with pytest.raises(RegistryValidationError, match="startup_fund_rendimientos_clave"):
        _build(_observation(clave=RetencionClave.G, startup_fund_rendimientos_clave=0))


_M193_DECLARED_FIELDS = frozenset(
    {
        "perceptor_tax_id",
        "perceptor_legal_name",
        "clave",
        "percibido_dinerario",
        "retencion_practicada",
        "perceptor_mediador_flag",
        "clave_codigo",
        "codigo_emisor",
        "naturaleza",
        "pago",
        "tipo_codigo",
        "codigo_cuenta",
        "pendiente_flag",
        "tipo_percepcion",
        "reducciones",
        "base_retenciones",
        "porcentaje_retencion",
        "penalizaciones",
        "isin_code",
        "naturaleza_declarante",
        "fecha_inicio_prestamo",
        "fecha_vencimiento_prestamo",
        "compensaciones",
        "garantias",
        "nif_pagador_anterior",
        "fecha_devengo",
        "clave_mercado",
        "numero_orden",
    }
)

#: The always-recorded 193 perceptor facts for a clave A row (the 193 clave
#: vocabulary replaces the 190 one: A-D capital-mobiliario claves).
_COMPLETE_CLAVE_A_193 = {
    "naturaleza": "02",
    "tipo_percepcion": 1,
    "clave_codigo": 4,
    "codigo_emisor": "A28015865",
    "pago": 1,
    "tipo_codigo": "C",
    "clave_mercado": "D",
}


def _build193(*observations: WithholdingObservation) -> tuple[dict[str, object], ...]:
    return tuple(
        dict(row)
        for row in _build_withholding_rows("per_perceptor_clave", observations, required_fields=_M193_DECLARED_FIELDS)
    )


def test_build_withholding_rows_193_requires_the_always_recorded_facts() -> None:
    """The 193 design records naturaleza, tipo de percepcion and the A/B/D
    identification block on every eligible row; a missing fact refuses."""
    for missing in ("naturaleza", "tipo_percepcion", "clave_codigo", "codigo_emisor", "pago", "tipo_codigo", "clave_mercado"):
        with pytest.raises(RegistryValidationError, match=missing):
            _build193(
                _observation(
                    **{key: value for key, value in _COMPLETE_CLAVE_A_193.items() if key != missing}
                )
            )
    row = _build193(_observation(**_COMPLETE_CLAVE_A_193))[0]
    assert row["naturaleza"] == "02"
    assert row["tipo_percepcion"] == "1"
    assert row["clave_codigo"] == "4"
    assert row["codigo_emisor"] == "A28015865"
    assert row["pago"] == "1"
    assert row["tipo_codigo"] == "C"
    assert row["clave_mercado"] == "D"
    assert row["numero_orden"] == "1"


def test_build_withholding_rows_193_out_of_context_facts_refuse() -> None:
    """The 193 A/B/D identification facts refuse outside their claves, and the
    prestamo-de-valores block refuses without tipo codigo P."""
    with pytest.raises(RegistryValidationError, match="clave_codigo"):
        _build193(_observation(clave=RetencionClave.C, naturaleza="01", tipo_percepcion=1, clave_codigo=4))
    with pytest.raises(RegistryValidationError, match="clave_mercado"):
        _build193(_observation(clave=RetencionClave.C, naturaleza="01", tipo_percepcion=1, clave_mercado="D"))
    with pytest.raises(RegistryValidationError, match="fecha_inicio_prestamo"):
        _build193(_observation(**_COMPLETE_CLAVE_A_193, fecha_inicio_prestamo="20240101"))
    with pytest.raises(RegistryValidationError, match="compensaciones"):
        _build193(_observation(**_COMPLETE_CLAVE_A_193, compensaciones=Decimal("1")))
    prestamo = {key: value for key, value in _COMPLETE_CLAVE_A_193.items() if key != "tipo_codigo"}
    row = _build193(_observation(**prestamo, tipo_codigo="P", fecha_inicio_prestamo="20240101", fecha_vencimiento_prestamo="20250101"))[0]
    assert row["fecha_inicio_prestamo"] == "20240101"
    assert _build193(_observation(**_COMPLETE_CLAVE_A_193))[0]["fecha_inicio_prestamo"] == "0" * 8


def test_build_withholding_rows_193_naturaleza_s_cascade_overrides() -> None:
    """Naturaleza del declarante 'S' zeroes the identification block per the
    design's cascade; a present fact the cascade forbids refuses."""
    row = _build193(_observation(**_COMPLETE_CLAVE_A_193, naturaleza_declarante="S"))[0]
    assert row["clave_codigo"] == "0"
    assert row["codigo_emisor"] == " " * 12
    assert row["pago"] == "0"
    assert row["tipo_codigo"] == " "
    assert row["naturaleza_declarante"] == "S"
    with pytest.raises(RegistryValidationError, match="cascade declares a ceros"):
        _build193(_observation(clave=RetencionClave.B, naturaleza="01", tipo_percepcion=1, naturaleza_declarante="S", penalizaciones=Decimal("5")))


def test_withholding_observation_design_claves_are_bounded() -> None:
    with pytest.raises(ValidationError):
        _observation(disability_clave=4)
    with pytest.raises(ValidationError):
        _observation(contract_relation_clave=0)
    with pytest.raises(ValidationError):
        _observation(contract_relation_clave=5)
    with pytest.raises(ValidationError):
        _observation(unit_convivencia_titular_clave=3)
    with pytest.raises(ValidationError):
        _observation(geographic_mobility_clave=2)
    with pytest.raises(ValidationError):
        _observation(accrual_year=1899)
    with pytest.raises(ValidationError):
        _observation(representative_tax_id="1234567A")  # 8 chars, not a 9-byte NIF


# ---------------------------------------------------------------------------
# RelatedPartyOperationObservation
# ---------------------------------------------------------------------------


def test_related_party_observation_country_code_must_be_uppercase_alphabetic() -> None:
    with pytest.raises(ValidationError, match="country_code must be uppercase alphabetic"):
        RelatedPartyOperationObservation(
            source_id="op1",
            counterparty_tax_id="A12345674",
            country_code="es",
            transaction_date=date(2025, 3, 15),
            operation_kind_code="01",
            amount=Decimal("100"),
        )


def test_related_party_observation_amount_must_be_decimal() -> None:
    with pytest.raises(ValidationError):
        RelatedPartyOperationObservation(
            source_id="op1",
            counterparty_tax_id="A12345674",
            country_code="ES",
            transaction_date=date(2025, 3, 15),
            operation_kind_code="01",
            amount=cast(Decimal, True),
        )


def test_related_party_observation_requires_a_stated_country() -> None:
    """An omitted country must refuse, not resolve to Spain.

    Modelo 232 declares operations with países calificados como paraísos
    fiscales alongside operaciones vinculadas, so a default on this field
    marks a tax-haven counterparty as domestic on the exact axis the
    declaration exists to surface. The positive control is
    ``test_related_party_observation_baseline_validates``: the same payload
    with a country stated must construct.
    """
    with pytest.raises(ValidationError, match="country_code"):
        RelatedPartyOperationObservation.model_validate(
            {
                "source_id": "op1",
                "counterparty_tax_id": "A12345674",
                "transaction_date": date(2025, 3, 15),
                "operation_kind_code": "01",
                "amount": Decimal("100"),
            },
        )


def test_related_party_observation_keeps_a_tax_haven_country() -> None:
    """The declared country survives construction unaltered."""
    obs = _related_party_observation(country_code="KY")

    assert obs.country_code == "KY"


def test_build_related_party_rows_groups_by_party_country_kind_method() -> None:
    es_q1 = Decimal("1000")
    es_q2 = Decimal("500")
    de_amount = Decimal("2000")
    obs = (
        RelatedPartyOperationObservation(
            source_id="op1",
            counterparty_tax_id="A12345674",
            country_code="ES",
            transaction_date=date(2025, 3, 15),
            operation_kind_code="01",
            transfer_pricing_method_code="1A",
            amount=es_q1,
        ),
        RelatedPartyOperationObservation(
            source_id="op2",
            counterparty_tax_id="A12345674",
            country_code="ES",
            transaction_date=date(2025, 6, 15),
            operation_kind_code="01",
            transfer_pricing_method_code="1A",
            amount=es_q2,
        ),
        RelatedPartyOperationObservation(
            source_id="op3",
            counterparty_tax_id="DE12345678",
            country_code="DE",
            transaction_date=date(2025, 4, 1),
            operation_kind_code="02",
            transfer_pricing_method_code="1E",
            amount=de_amount,
        ),
    )

    rows = _build_related_party_rows(obs)

    assert len(rows) == 2
    es_row = next(row for row in rows if row["country_code"] == "ES")
    de_row = next(row for row in rows if row["country_code"] == "DE")
    assert es_row["amount"] == es_q1 + es_q2
    assert de_row["amount"] == de_amount


# ---------------------------------------------------------------------------
# Modelo720RowObservation
# ---------------------------------------------------------------------------


def test_foreign_asset_observation_iso_codes_must_be_uppercase_alphabetic() -> None:
    with pytest.raises(ValidationError, match="ISO code must be uppercase alphabetic"):
        Modelo720RowObservation(
            source_id="a1",
            asset_class_code=M720AssetClassCode.CUENTA,
            country_code="ch",
            currency_code="CHF",
            acquisition_date=date(2024, 1, 1),
            valuation_amount=Decimal("60000"),
        )
    with pytest.raises(ValidationError, match="ISO code must be uppercase alphabetic"):
        Modelo720RowObservation(
            source_id="a1",
            asset_class_code=M720AssetClassCode.CUENTA,
            country_code="CH",
            currency_code="ch1",
            acquisition_date=date(2024, 1, 1),
            valuation_amount=Decimal("60000"),
        )


def test_foreign_asset_observation_valuation_must_be_non_negative() -> None:
    with pytest.raises(ValidationError, match="valuation must be non-negative"):
        Modelo720RowObservation(
            source_id="a1",
            asset_class_code=M720AssetClassCode.CUENTA,
            country_code="CH",
            acquisition_date=date(2024, 1, 1),
            valuation_amount=Decimal("-1"),
        )


# ---------------------------------------------------------------------------
# AtributionMemberObservation
# ---------------------------------------------------------------------------


def test_atribucion_member_share_percentage_must_be_in_range() -> None:
    with pytest.raises(ValidationError, match=r"share_percentage must be within \[0, 100\]"):
        AtributionMemberObservation(
            source_id="m1",
            member_tax_id="12345678A",
            transaction_date=date(2025, 1, 1),
            share_percentage=Decimal("150"),
            base_imponible_assigned=Decimal("0"),
        )
    with pytest.raises(ValidationError, match=r"share_percentage must be within \[0, 100\]"):
        AtributionMemberObservation(
            source_id="m1",
            member_tax_id="12345678A",
            transaction_date=date(2025, 1, 1),
            share_percentage=Decimal("-1"),
            base_imponible_assigned=Decimal("0"),
        )


def test_atribucion_member_country_code_must_be_uppercase_alphabetic() -> None:
    with pytest.raises(ValidationError, match="country_code must be uppercase alphabetic"):
        AtributionMemberObservation(
            source_id="m1",
            member_tax_id="12345678A",
            country_code="es",
            transaction_date=date(2025, 1, 1),
            share_percentage=Decimal("50"),
            base_imponible_assigned=Decimal("1000"),
        )


# ---------------------------------------------------------------------------
# RefundOperationObservation
# ---------------------------------------------------------------------------


def test_refund_operation_member_state_must_be_uppercase_alphabetic() -> None:
    with pytest.raises(ValidationError, match="member_state_code must be uppercase alphabetic"):
        RefundOperationObservation(
            source_id="r1",
            member_state_code="fr",
            operation_kind_code="01",
            operation_date=date(2025, 3, 15),
            supplier_tax_id="FR12345678",
            refund_amount=Decimal("100"),
        )


def test_refund_operation_amount_must_be_non_negative() -> None:
    with pytest.raises(ValidationError, match="refund_amount must be non-negative"):
        RefundOperationObservation(
            source_id="r1",
            member_state_code="FR",
            operation_kind_code="01",
            operation_date=date(2025, 3, 15),
            supplier_tax_id="FR12345678",
            refund_amount=Decimal("-1"),
        )


# ---------------------------------------------------------------------------
# DonativoDonorObservation (modelo 182)
# ---------------------------------------------------------------------------


def test_donativo_donor_amount_must_be_non_negative() -> None:
    with pytest.raises(ValidationError, match="amount_donated must be non-negative"):
        DonativoDonorObservation(
            source_id="d1",
            donor_tax_id="12345678A",
            transaction_date=date(2025, 3, 15),
            amount_donated=Decimal("-1"),
            deduction_percentage=Decimal("80"),
        )


def test_donativo_donor_deduction_percentage_must_be_in_range() -> None:
    with pytest.raises(ValidationError, match=r"deduction_percentage must be within \[0, 100\]"):
        DonativoDonorObservation(
            source_id="d1",
            donor_tax_id="12345678A",
            transaction_date=date(2025, 3, 15),
            amount_donated=Decimal("100"),
            deduction_percentage=Decimal("150"),
        )
    with pytest.raises(ValidationError, match=r"deduction_percentage must be within \[0, 100\]"):
        DonativoDonorObservation(
            source_id="d1",
            donor_tax_id="12345678A",
            transaction_date=date(2025, 3, 15),
            amount_donated=Decimal("100"),
            deduction_percentage=Decimal("-1"),
        )


def test_donativo_donor_country_code_must_be_uppercase_alphabetic() -> None:
    with pytest.raises(ValidationError, match="country_code must be uppercase alphabetic"):
        DonativoDonorObservation(
            source_id="d1",
            donor_tax_id="12345678A",
            country_code="es",
            transaction_date=date(2025, 3, 15),
            amount_donated=Decimal("100"),
            deduction_percentage=Decimal("80"),
        )


def test_build_donativo_rows_sums_per_donor_and_preserves_recurrencia() -> None:
    """A donor who gave twice in the year folds into one row; recurrencia sticks."""
    q1_amount = Decimal("100")
    q3_amount = Decimal("250")
    other_donor_amount = Decimal("500")
    obs = (
        DonativoDonorObservation(
            source_id="d1a",
            donor_tax_id="12345678A",
            donor_legal_name="Donor One",
            transaction_date=date(2025, 2, 1),
            amount_donated=q1_amount,
            deduction_percentage=Decimal("80"),
            is_recurrent=False,
        ),
        DonativoDonorObservation(
            source_id="d1b",
            donor_tax_id="12345678A",
            donor_legal_name="Donor One",
            transaction_date=date(2025, 9, 1),
            amount_donated=q3_amount,
            deduction_percentage=Decimal("80"),
            is_recurrent=True,
        ),
        DonativoDonorObservation(
            source_id="d2",
            donor_tax_id="87654321Z",
            donor_legal_name="Donor Two",
            transaction_date=date(2025, 5, 1),
            amount_donated=other_donor_amount,
            deduction_percentage=Decimal("35"),
            is_recurrent=False,
        ),
    )

    rows = _build_donativo_rows(obs)

    assert len(rows) == 2
    by_nif = {row["donor_tax_id"]: row for row in rows}
    assert by_nif["12345678A"]["amount_donated"] == q1_amount + q3_amount
    assert by_nif["12345678A"]["is_recurrent"] == "1"
    assert by_nif["87654321Z"]["amount_donated"] == other_donor_amount
    assert by_nif["87654321Z"]["is_recurrent"] == "0"


def _related_party_observation(**overrides: object) -> RelatedPartyOperationObservation:
    """Build a valid related-party observation, overriding one field per case.

    Every untouched field is a value the model accepts, so a refusal can only
    have come from the override.
    """
    return RelatedPartyOperationObservation.model_validate(
        {
            "source_id": "detalle:per_related_party_operation:row-0",
            "counterparty_tax_id": "A12345678",
            "counterparty_legal_name": "Entidad Vinculada SL",
            "country_code": "ES",
            "transaction_date": date(2026, 3, 1),
            "operation_kind_code": "01",
            "transfer_pricing_method_code": "1A",
            "amount": Decimal("50000"),
            **overrides,
        },
    )


def test_related_party_observation_baseline_validates() -> None:
    """Anti-tautology guard: the untouched fixture must VALIDATE.

    Without it a typo in an untested field would refuse every case below and
    the catalogue enforcement would be proven by nothing.
    """
    obs = _related_party_observation()
    assert obs.operation_kind_code == "01"
    assert obs.transfer_pricing_method_code == "1A"


def test_related_party_observation_refuses_off_catalogue_codes() -> None:
    """Binding-resolved codes are held to the same DR23200 tables as the CLI row.

    This is the engine-side half of the M232 coded-field contract. The values
    reach it as free-form registry text, so without the catalogue an operation
    kind or valuation method AEAT never published would resolve into a casilla.
    """
    for _case_id, overrides in (
        # DR23200 Tabla C stops at clave 11.
        ("operation-kind-above-catalogue", {"operation_kind_code": "99"}),
        ("operation-kind-unpadded", {"operation_kind_code": "1"}),
        # Tabla B codes are 1A-1E; the OECD abbreviations for the same
        # art. 18.4 methods are not AEAT's codes and do not fit the field.
        ("method-oecd-abbreviation", {"transfer_pricing_method_code": "CUP"}),
        ("method-off-catalogue", {"transfer_pricing_method_code": "ZZ"}),
    ):
        with pytest.raises(ValidationError):
            _related_party_observation(**overrides)


def test_related_party_observation_hydrates_operator_casing() -> None:
    """A lowercase token resolves to the code DR23200 spells in uppercase."""
    assert _related_party_observation(transfer_pricing_method_code="1e").transfer_pricing_method_code == "1E"
