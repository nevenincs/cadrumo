"""Which fichero "Tipo de declaración" a negative Modelo 303 resolves to, and when a refund is refused.

LIVA art. 115.Uno asks the refund "en la autoliquidación correspondiente al
último período de liquidación de dicho año"; art. 115.Dos extends it to the end
of every period only for the taxpayers of art. 116, inscribed in the Registro
de devolución mensual (RIVA art. 30). One resolver answers that for the served
words, the export's refund choice and the cross-period carry, so the gate is
asserted here at the disposition boundary and not only at the words.

The periods that open the annual refund are read from the registry's
refund-eligibility policy, never listed here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....core.refund_election import RefundElection
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.calculations.registry.refund_eligibility import resolve_refund_eligibility_policy_for_period
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.deadlines.models import (
    IVARegime,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloIVAProfile,
    TaxpayerProfile,
)
from ....domain.iva.refund_eligibility import RefundEligibilityBasis, RefundEligibilityOutcome
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..action_errors import ModeloProfileReadinessError, ModeloRefundElectionNotEligibleError
from ..result_disposition_resolution import resolve_modelo_result_disposition

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_BUCKET_ID = "915b0469-91b1-4787-a650-9aad55564dd3"
_MODELO = "303"
_FILING_YEAR = 2025
#: The settlement box of the periodic IVA declaration, "Resultado final".
_RESULT_CASILLA: CasillaId = validated_casilla_id("71", surface="m303 refund election disposition test")
_NEGATIVE = Decimal("-325.50")


def _final_period_tokens(period_code: str) -> frozenset[str]:
    period = Period.from_year_and_code(_FILING_YEAR, period_code)
    return resolve_refund_eligibility_policy_for_period(period).final_period_tokens


def _non_final_quarter() -> str:
    final = _final_period_tokens("1T")
    return next(code for code in ("3T", "2T", "1T") if code not in final)


def _final_quarter() -> str:
    final = _final_period_tokens("4T")
    return next(code for code in ("4T", "3T", "2T", "1T") if code in final)


def _profile(*, redeme: bool) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X0001500M",
        iva_regime=IVARegime("GENERAL"),
        iva=ModeloIVAProfile(
            tax_territory=M303TaxTerritory.from_registry("common_regime"),
            regime_composition=M303RegimeComposition.from_registry("general"),
            redeme_enrolled=redeme,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=False,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
        ),
    )


def _negative_declaration(period_code: str) -> tuple[WorkUnit, CalculationRevision]:
    period = Period.from_year_and_code(_FILING_YEAR, period_code)
    revision_id = published_snapshot(_MODELO, filing_year=_FILING_YEAR, period=period.registry_token).revision.id
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=_MODELO,
            filing_year=_FILING_YEAR,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(_MODELO),
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=revision_id,
        name=f"{_MODELO}-{_FILING_YEAR}-{period.registry_token}",
        created_at=_NOW,
        updated_at=_NOW,
    )
    values = {_RESULT_CASILLA: _NEGATIVE}
    revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values=values,
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=revision_id,
            modelo_year=_FILING_YEAR,
            period=period.registry_token,
        ),
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        casilla_values=values,
        observations=tuple(
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                legal_refs=("ley-37-1992:art-115",),
                source_refs=("aeat-modelo-disposition-fixture",),
            )
            for casilla_id, value in values.items()
        ),
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return work_unit, revision


def _disposition(period_code: str, *, redeme: bool, refund_election: RefundElection) -> ResultDisposition | None:
    work_unit, revision = _negative_declaration(period_code)
    return resolve_modelo_result_disposition(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=_profile(redeme=redeme),
        period=work_unit.period,
        refund_election=refund_election,
    )


def test_a_negative_non_final_quarter_carries_forward_for_a_filer_outside_redeme() -> None:
    """Compensación is the only disposition the period admits, so that is what is written."""
    assert (
        _disposition(_non_final_quarter(), redeme=False, refund_election=RefundElection.COMPENSAR)
        is ResultDisposition.COMPENSACION
    )


def test_a_refund_elected_outside_the_last_period_is_refused_not_filed() -> None:
    """An unlawful refund is neither written as D nor quietly downgraded to C, and the refusal says why."""
    code = _non_final_quarter()
    with pytest.raises(ModeloRefundElectionNotEligibleError) as raised:
        _disposition(code, redeme=False, refund_election=RefundElection.DEVOLVER)

    context = raised.value.context or {}
    assert context["period"] == code
    assert context["refund_eligibility"] == RefundEligibilityOutcome.CARRY_FORWARD_ONLY.value
    assert context["refund_eligibility_basis"] == RefundEligibilityBasis.NON_FINAL_PERIOD.value


def test_the_last_period_of_the_year_admits_the_elected_refund() -> None:
    """LIVA art. 115.Uno: the annual refund needs no inscription, and the carry stays available."""
    code = _final_quarter()
    assert _disposition(code, redeme=False, refund_election=RefundElection.DEVOLVER) is ResultDisposition.DEVOLUCION
    assert _disposition(code, redeme=False, refund_election=RefundElection.COMPENSAR) is ResultDisposition.COMPENSACION


def test_a_redeme_filer_resolves_to_devolucion_in_every_period() -> None:
    """The inscription is the standing monthly-refund policy, so it does not wait on the per-filing flag."""
    for code in (_non_final_quarter(), _final_quarter()):
        assert (
            _disposition(code, redeme=True, refund_election=RefundElection.COMPENSAR) is ResultDisposition.DEVOLUCION
        ), code


def test_an_unanswered_iva_block_is_refused_rather_than_read_as_outside_redeme() -> None:
    """An inscription nobody stated must not settle the disposition: the readiness gap is reported instead."""
    work_unit, revision = _negative_declaration(_non_final_quarter())

    with pytest.raises(ModeloProfileReadinessError) as raised:
        resolve_modelo_result_disposition(
            work_unit=work_unit,
            revision=revision,
            workflow_profile=TaxpayerProfile(tax_id="X0001500M", iva_regime=IVARegime("GENERAL")),
            period=work_unit.period,
            refund_election=RefundElection.COMPENSAR,
        )

    assert (raised.value.context or {})["iva_profile_present"] is False
