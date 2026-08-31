"""Real model-boundary coverage for the Modelo 303 evidence arrivals."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.period import Period
from ....core.prorrata_register import (
    ProrrataEspecialTransitionKind,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from ....core.resources._boundary import bundled_path
from ....domain.calculations.registry.ledger_bindings import IvaLedgerObservation
from ....domain.iva.flow import IvaFlowDirection
from ....domain.iva.schema import IvaCashAccountingTreatment, IvaCategory, IvaLedgerObservationRole, IvaRateKind
from ....domain.prorrata_register.register import (
    ProrrataEspecialTransitionEvidence,
    ProrrataRegister,
    ProrrataRegisterEntry,
    SectorDefinition,
)
from .. import (
    AggregationValidationError,
    IvaLedgerAggregation,
    M303ProrrataTransitionArrival,
    M303SupplierRegimeArrival,
    resolve_m303_prorrata_transition_arrival,
    resolve_m303_supplier_regime_arrival,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_Q1_2026 = Period.from_year_and_code(2026, "1T")
_Q2_2026 = Period.from_year_and_code(2026, "2T")
_Q4_2026 = Period.from_year_and_code(2026, "4T")
_DECEMBER_2026 = Period.from_year_and_code(2026, "12")


def _observation(
    ledger_id: str,
    *,
    transaction_date: date = date(2026, 2, 11),
    cash_accounting_treatment: IvaCashAccountingTreatment = IvaCashAccountingTreatment.NONE,
) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=transaction_date,
        category=IvaCategory.DOMESTIC_GENERAL,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=IvaFlowDirection.REPERCUTIDO,
        base_amount=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        cash_accounting_treatment=cash_accounting_treatment,
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def test_supplier_regime_arrival_uses_only_in_period_canonical_iva_observations() -> None:
    aggregation = IvaLedgerAggregation(
        period=_Q1_2026,
        observations=(
            _observation("ordinary-sale"),
            _observation(
                "supplier-regime-purchase",
                cash_accounting_treatment=IvaCashAccountingTreatment.SUPPLIER_REGIME,
            ),
        ),
    )

    arrival = resolve_m303_supplier_regime_arrival(period=_Q1_2026, iva_aggregation=aggregation)

    assert arrival.period == _Q1_2026
    assert arrival.recipient_of_cash_accounting_operations is True
    assert arrival.source_ledger_ids == ("supplier-regime-purchase",)


def test_supplier_regime_arrival_refuses_mismatched_or_out_of_period_canonical_evidence() -> None:
    aggregation = IvaLedgerAggregation(period=_Q1_2026, observations=(_observation("supplier-regime"),))

    with pytest.raises(
        AggregationValidationError,
        match=r"aggregation\.m303_arrivals\.errors\.supplier_regime_aggregation_period_mismatch",
    ):
        resolve_m303_supplier_regime_arrival(period=_Q2_2026, iva_aggregation=aggregation)

    malformed_aggregation = IvaLedgerAggregation(
        period=_Q1_2026,
        observations=(
            _observation(
                "outside-period",
                transaction_date=date(2026, 4, 1),
                cash_accounting_treatment=IvaCashAccountingTreatment.SUPPLIER_REGIME,
            ),
        ),
    )
    with pytest.raises(
        AggregationValidationError,
        match=r"aggregation\.m303_arrivals\.errors\.supplier_regime_observations_outside_period",
    ):
        resolve_m303_supplier_regime_arrival(period=_Q1_2026, iva_aggregation=malformed_aggregation)


def test_prorrata_transition_arrival_carries_option_register_evidence() -> None:
    option = ProrrataEspecialTransitionEvidence(
        kind=ProrrataEspecialTransitionKind.OPCION,
        evidence_reference="modelo-303-2026-1t-prorrata-opcion",
    )
    entry = ProrrataRegisterEntry(
        ejercicio=2026,
        regime=ProrrataRegisterRegime.ESPECIAL,
        especial_transition=option,
    )

    arrival = resolve_m303_prorrata_transition_arrival(
        period=_Q4_2026,
        prorrata_register=ProrrataRegister(entries=(entry,)),
    )

    assert arrival.period == _Q4_2026
    assert arrival.is_applicable is True
    assert arrival.transition is ProrrataEspecialTransitionKind.OPCION
    assert arrival.register_evidence == (entry,)


def test_prorrata_transition_arrival_is_blank_before_the_modelo_303_final_period() -> None:
    entry = ProrrataRegisterEntry(
        ejercicio=2026,
        regime=ProrrataRegisterRegime.ESPECIAL,
        especial_transition=ProrrataEspecialTransitionEvidence(
            kind=ProrrataEspecialTransitionKind.OPCION,
            evidence_reference="modelo-303-2026-prorrata-opcion",
        ),
    )
    register = ProrrataRegister(entries=(entry,))

    arrival = resolve_m303_prorrata_transition_arrival(period=_Q1_2026, prorrata_register=register)

    assert arrival.is_applicable is False
    assert arrival.transition is None
    assert arrival.register_evidence == ()


def test_prorrata_transition_applicability_matches_the_official_2026_note_6() -> None:
    source = bundled_path(
        "corpus",
        "aeat_official",
        "disenos_registro",
        "modelo_303",
        "files",
        "01-303-ejercicio-2026-y-siguientes-actualizado-28-01-26-378-kb-xlsx.xlsx.extracted.md",
    ).read_text(encoding="utf-8")

    assert "Nota 6:" in source
    assert "SI para el último periodo (12 y 4T)" in source
    assert "Blanco para periodos distintos del último (12 y 4T)" in source
    assert (
        M303ProrrataTransitionArrival(
            period=_DECEMBER_2026,
            transition=None,
            register_evidence=(),
        ).is_applicable
        is True
    )


def test_prorrata_register_rejects_both_option_and_revocation_for_one_ejercicio() -> None:
    option_entry = ProrrataRegisterEntry(
        ejercicio=2026,
        sector_id="retail",
        regime=ProrrataRegisterRegime.ESPECIAL,
        especial_transition=ProrrataEspecialTransitionEvidence(
            kind=ProrrataEspecialTransitionKind.OPCION,
            evidence_reference="modelo-303-2026-retail-opcion",
        ),
    )
    revocation_entry = ProrrataRegisterEntry(
        ejercicio=2026,
        sector_id="wholesale",
        regime=ProrrataRegisterRegime.GENERAL,
        especial_transition=ProrrataEspecialTransitionEvidence(
            kind=ProrrataEspecialTransitionKind.REVOCACION,
            evidence_reference="modelo-303-2026-wholesale-revocacion",
        ),
    )

    with pytest.raises(ValidationError, match="contradictory prorrata especial option and revocation evidence"):
        ProrrataRegister(
            entries=(
                ProrrataRegisterEntry(
                    ejercicio=2025,
                    sector_id="wholesale",
                    regime=ProrrataRegisterRegime.ESPECIAL,
                    especial_transition=None,
                ),
                option_entry,
                revocation_entry,
            )
        )


def test_prorrata_transition_arrival_does_not_infer_an_option_from_an_existing_especial_state() -> None:
    register = ProrrataRegister(
        entries=(
            ProrrataRegisterEntry(
                ejercicio=2026,
                regime=ProrrataRegisterRegime.ESPECIAL,
                especial_transition=None,
            ),
        ),
    )

    arrival = resolve_m303_prorrata_transition_arrival(period=_Q4_2026, prorrata_register=register)

    assert arrival.is_applicable is True
    assert arrival.transition is None
    assert arrival.register_evidence == ()


def test_prorrata_register_refuses_a_revocation_without_a_prior_especial_state() -> None:
    entry = ProrrataRegisterEntry(
        ejercicio=2026,
        regime=ProrrataRegisterRegime.GENERAL,
        especial_transition=ProrrataEspecialTransitionEvidence(
            kind=ProrrataEspecialTransitionKind.REVOCACION,
            evidence_reference="modelo-303-2026-revocacion",
        ),
    )

    with pytest.raises(ValidationError, match="prior-year especial register state"):
        ProrrataRegister(entries=(entry,))


def test_prorrata_transition_arrival_accepts_a_revocation_after_the_prior_especial_state() -> None:
    revocation_entry = ProrrataRegisterEntry(
        ejercicio=2026,
        regime=ProrrataRegisterRegime.GENERAL,
        especial_transition=ProrrataEspecialTransitionEvidence(
            kind=ProrrataEspecialTransitionKind.REVOCACION,
            evidence_reference="modelo-303-2026-revocacion",
        ),
    )
    register = ProrrataRegister(
        entries=(
            ProrrataRegisterEntry(
                ejercicio=2025,
                regime=ProrrataRegisterRegime.ESPECIAL,
                especial_transition=None,
            ),
            revocation_entry,
        ),
    )

    arrival = resolve_m303_prorrata_transition_arrival(period=_Q4_2026, prorrata_register=register)

    assert arrival.is_applicable is True
    assert arrival.transition is ProrrataEspecialTransitionKind.REVOCACION
    assert arrival.register_evidence == (revocation_entry,)


def test_prorrata_transition_arrival_requires_complete_current_year_register_coverage() -> None:
    """A final-period artifact never treats missing sector declarations as NO."""
    current = ProrrataRegisterEntry(
        ejercicio=2026,
        sector_id="retail",
        regime=ProrrataRegisterRegime.GENERAL,
        especial_transition=None,
    )
    register = ProrrataRegister(
        entries=(current,),
        sector_definitions=(
            SectorDefinition(
                sector_id="retail",
                letra=SectorDiferenciadoLetra.A,
                member_activity_codes=("471",),
            ),
            SectorDefinition(
                sector_id="leasing",
                letra=SectorDiferenciadoLetra.A,
                member_activity_codes=("649",),
            ),
        ),
    )

    with pytest.raises(
        AggregationValidationError,
        match=r"aggregation\.m303_arrivals\.errors\.prorrata_register_incomplete_current_year_declaration",
    ):
        resolve_m303_prorrata_transition_arrival(period=_Q4_2026, prorrata_register=register)

    assert resolve_m303_prorrata_transition_arrival(period=_Q1_2026, prorrata_register=register).transition is None

    complete_register = ProrrataRegister(
        entries=(
            ProrrataRegisterEntry(
                ejercicio=2026,
                regime=ProrrataRegisterRegime.GENERAL,
                especial_transition=None,
            ),
            current,
            ProrrataRegisterEntry(
                ejercicio=2026,
                sector_id="leasing",
                regime=ProrrataRegisterRegime.GENERAL,
                especial_transition=None,
            ),
        ),
        sector_definitions=register.sector_definitions,
    )

    arrival = resolve_m303_prorrata_transition_arrival(period=_Q4_2026, prorrata_register=complete_register)
    assert arrival.transition is None
    assert arrival.register_evidence == ()


def test_prorrata_transition_arrival_refuses_an_empty_final_period_register() -> None:
    with pytest.raises(
        AggregationValidationError,
        match=r"aggregation\.m303_arrivals\.errors\.prorrata_register_incomplete_current_year_declaration",
    ):
        resolve_m303_prorrata_transition_arrival(period=_Q4_2026, prorrata_register=ProrrataRegister())


def test_arrival_evidence_axes_are_required_and_explicit_empty_or_null_values_remain_valid() -> None:
    assert M303SupplierRegimeArrival.model_fields["source_ledger_ids"].is_required()
    assert M303ProrrataTransitionArrival.model_fields["transition"].is_required()
    assert M303ProrrataTransitionArrival.model_fields["register_evidence"].is_required()

    assert (
        M303SupplierRegimeArrival(
            period=_Q1_2026,
            recipient_of_cash_accounting_operations=False,
            source_ledger_ids=(),
        ).source_ledger_ids
        == ()
    )
    assert (
        M303ProrrataTransitionArrival(
            period=_Q1_2026,
            transition=None,
            register_evidence=(),
        ).transition
        is None
    )

    with pytest.raises(ValidationError):
        M303SupplierRegimeArrival.model_validate(
            {"period": _Q1_2026, "recipient_of_cash_accounting_operations": False},
        )
    with pytest.raises(ValidationError):
        M303ProrrataTransitionArrival.model_validate({"period": _Q1_2026, "register_evidence": ()})
    with pytest.raises(ValidationError):
        M303ProrrataTransitionArrival.model_validate({"period": _Q1_2026, "transition": None})
