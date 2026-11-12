"""The export names the door of each operator-correctable cause it used to report as an integrity fault.

Every refusal is raised by the function that owns the check and read through the readers
the operation error detail uses, in every shipped locale.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ....core.errors.error_codes import get_registered_error_code, resolve_error_message
from ....core.external_constants import OutputLanguage
from ....core.modelo import Modelo
from ....core.operator_action_enums import NoRecoveryOutcome
from ....core.period import Period
from ....core.prorrata_register import ProrrataRegisterRegime, SectorDiferenciadoLetra
from ....core.result_disposition import ResultDisposition
from ....domain.bienes_inversion.register import BienesInversionIvaRegister, BienInversionIvaRecord
from ....domain.bienes_inversion.vocabulary import BienInversionKind
from ....domain.calculations.registry.m303_schema_vocabulary import (
    m303_regime_composition_simplified_scope,
    resolve_m303_regime_composition_catalogue,
)
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.deadlines.models import IVARegime, M303RegimeComposition, TaxpayerProfile
from ....domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry, SectorDefinition
from ...aggregation.iva_ledger import IvaLedgerAggregation
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...filing.producer_snapshot import (
    FilingProducerSnapshotError,
    GeneralFilingProfileFacts,
    Modelo111ProfileFacts,
    build_filing_producer_snapshot,
)
from ...filing.tests.producer_snapshot_support import (
    TAXPAYER_TAX_ID,
    elections,
    m303_filing_facts,
    m303_profile,
    producer_snapshot_presenter,
    taxpayer_identity,
)
from ...operations.next_step import error_next_step
from ..action_errors import M303FilingEvidenceError, ModeloProfileReadinessError
from ..export_accounts import _producer_facts_refusal
from ..export_contracts import ModeloExportCommand, ModeloExportDesignIntegrityError
from ..export_preparation import (
    require_m303_regimen_simplificado_scope_matches_profile,
    resolve_m303_export_arrivals,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = ("es", "ca", "en", "hu")
_YEAR = filing_year_envelope().horizon
_REVISION_ID = "a" * 64


def _command() -> ModeloExportCommand:
    return ModeloExportCommand(
        calculation_revision_id=_REVISION_ID,
        output_path=Path("unused.txt"),
        actor="operator",
    )


def _assert_words_in_every_locale(error: Exception) -> None:
    for locale in _LOCALES:
        message = resolve_error_message(error, locale=locale)
        assert message
        assert "%{" not in message


def _entry(sector_id: str | None, *, definitive: Decimal | None) -> ProrrataRegisterEntry:
    return ProrrataRegisterEntry(
        ejercicio=_YEAR,
        regime=ProrrataRegisterRegime.from_registry("general"),
        especial_transition=None,
        sector_id=sector_id,
        definitive_percentage=definitive,
        definitive_volume_con_derecho=None if definitive is None else Decimal("600.00"),
        definitive_volume_sin_derecho=None if definitive is None else Decimal("400.00"),
        source_registry_snapshot_refs=(published_snapshot("303", filing_year=_YEAR, period="4T").snapshot_ref,),
    )


def test_sectors_without_a_ledger_apportionment_are_an_operator_decision(operation: PinnedAuthorityOperation) -> None:
    period = Period.from_year_and_code(_YEAR, "4T")
    register = ProrrataRegister(
        entries=(_entry(None, definitive=Decimal("60")), _entry("comercio", definitive=Decimal("60"))),
        sector_definitions=(
            SectorDefinition(
                sector_id="comercio",
                letra=SectorDiferenciadoLetra.from_registry("a"),
                member_activity_codes=("4711",),
            ),
        ),
    )
    with pytest.raises(ModeloProfileReadinessError) as raised:
        resolve_m303_export_arrivals(
            period=period,
            prorrata_register=register,
            iva_aggregation=IvaLedgerAggregation(period=period),
            bienes_register=BienesInversionIvaRegister(records=()),
            operation=operation,
        )
    assert raised.value.context == {
        "filing_year": period.filing_year,
        "period": period.registry_token,
        "reason": "m303_sector_apportionment_missing",
    }
    verdict = nested_terminal_precondition_verdict(raised.value)
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert get_registered_error_code(raised.value).code == "REFUSED_MODELO_PROFILE_READINESS"
    _assert_words_in_every_locale(raised.value)


def test_capital_goods_without_a_definitive_prorrata_are_an_operator_decision(
    operation: PinnedAuthorityOperation,
) -> None:
    period = Period.from_year_and_code(_YEAR, "4T")
    good = BienInversionIvaRecord(
        identifier="bien",
        description="Bien de inversion",
        acquisition_year=_YEAR - 1,
        cuota_soportada=Decimal("5000.00"),
        prorrata_inicial_pct=Decimal("80"),
        kind=BienInversionKind.from_registry("mueble"),
        acquisition_ledger_id="ledger:bien",
    )
    with pytest.raises(ModeloProfileReadinessError) as raised:
        resolve_m303_export_arrivals(
            period=period,
            prorrata_register=ProrrataRegister(entries=()),
            iva_aggregation=IvaLedgerAggregation(period=period),
            bienes_register=BienesInversionIvaRegister(records=(good,)),
            operation=operation,
        )
    assert raised.value.context is not None
    assert raised.value.context["reason"] == "m303_definitive_prorrata_missing"
    verdict = nested_terminal_precondition_verdict(raised.value)
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    _assert_words_in_every_locale(raised.value)


@pytest.mark.usefixtures("operation")
def test_a_simplified_scope_the_profile_no_longer_states_names_the_declared_scenario() -> None:
    facts = m303_filing_facts(filing_year=_YEAR)
    own_scope = facts.regimen_simplificado.scope_decision
    catalogue = resolve_m303_regime_composition_catalogue()
    other = next(
        composition
        for composition in sorted(catalogue.all_compositions, key=str)
        if m303_regime_composition_simplified_scope(composition) != own_scope.scope
    )
    iva = m303_profile().model_copy(update={"regime_composition": M303RegimeComposition.from_registry(str(other))})
    profile = TaxpayerProfile(tax_id=TAXPAYER_TAX_ID, iva=iva, iva_regime=IVARegime("GENERAL"))
    with pytest.raises(M303FilingEvidenceError) as raised:
        require_m303_regimen_simplificado_scope_matches_profile(filing_facts=facts, workflow_profile=profile)
    failure = raised.value.precondition_failure
    assert failure is not None
    assert failure.scenario_id == "modelo.work.calculate.m303_filing_evidence.regimen_scope_profile_divergence"


@pytest.mark.usefixtures("operation")
def test_a_matching_simplified_scope_is_accepted() -> None:
    facts = m303_filing_facts(filing_year=_YEAR)
    profile = TaxpayerProfile(tax_id=TAXPAYER_TAX_ID, iva=m303_profile(), iva_regime=IVARegime("GENERAL"))
    require_m303_regimen_simplificado_scope_matches_profile(filing_facts=facts, workflow_profile=profile)


def _snapshot_error(
    modelo: str, model_profile: GeneralFilingProfileFacts | Modelo111ProfileFacts
) -> FilingProducerSnapshotError:
    with pytest.raises(FilingProducerSnapshotError) as raised:
        build_filing_producer_snapshot(
            modelo=Modelo(modelo),
            taxpayer_tax_id=TAXPAYER_TAX_ID,
            taxpayer_identity=taxpayer_identity(),
            presenter=producer_snapshot_presenter(),
            model_profile=model_profile,
            elections=elections(ResultDisposition.INGRESO),
            amendment_evidence=None,
            refund_account=None,
            charge_account=None,
            m303_filing_facts=None,
        )
    return raised.value


@pytest.mark.usefixtures("operation")
def test_an_undeclared_colegio_concertado_reaches_the_operator_with_the_profile_door() -> None:
    cause = _snapshot_error("111", Modelo111ProfileFacts(colegio_concertado=None))
    refusal = _producer_facts_refusal(_command(), cause)
    assert isinstance(refusal, ModeloProfileReadinessError)
    assert refusal.context is not None
    assert refusal.context["calculation_revision_id"] == _REVISION_ID
    assert refusal.context["reason"] == "m111_colegio_concertado_undeclared"
    verdict = nested_terminal_precondition_verdict(refusal)
    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.profile.edit"
    step = error_next_step(refusal, OutputLanguage.EN)
    assert step is not None
    assert getattr(step, "path", None) == "withholding.colegio_concertado"
    _assert_words_in_every_locale(refusal)


@pytest.mark.usefixtures("operation")
def test_a_snapshot_design_fault_reaches_the_operator_as_the_terminal_integrity_refusal() -> None:
    cause = _snapshot_error("222", GeneralFilingProfileFacts())
    refusal = _producer_facts_refusal(_command(), cause)
    assert isinstance(refusal, ModeloExportDesignIntegrityError)
    assert refusal.context == {"cause": "snapshot_inconsistent", "calculation_revision_id": _REVISION_ID}
    assert get_registered_error_code(refusal).code.startswith("INTEGRITY_")
    assert nested_terminal_precondition_verdict(refusal) is not None
