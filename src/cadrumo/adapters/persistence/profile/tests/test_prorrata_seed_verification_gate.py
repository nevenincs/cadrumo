"""The verify gate on the provisional prorrata a Modelo 303 deducts under, over real stores.

The register is the one figure the deduction reads (LIVA art. 105.Uno), so an
apportioning entry with no figure, a figure a held prior return contradicts, a
figure the taxpayer stated, and a figure changed after a period was
calculated each reach verification as a finding, never as a default.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from .....application.aggregation.iva_ledger import sector_scoped_apportionment
from .....application.aggregation.modelo_bindings_iva import (
    iva_prorrata_apportionment_source_ref,
    prorrata_only_exempt_output_source_ref,
    recorded_prorrata_only_exempt_output,
)
from .....application.modelo.prorrata_seed_gate import (
    ModeloProrrataSeedSupersededError,
    ProrrataSeedVerificationFinding,
    prorrata_seed_verification_findings,
    require_filed_prorrata_seed_current,
)
from .....application.prorrata_register.seed import PRORRATA_DIFFERENTIATED_SECTOR
from .....application.prorrata_register.service import ProrrataRegisterService, ProrrataWholeSeedUnavailableError
from .....application.prorrata_register.settlement import (
    PRORRATA_PORCENTAJE_CASILLA,
    PRORRATA_SETTLEMENT_ESPECIAL_CONTINUATION_LOCALE_KEY,
    PRORRATA_VOLUMEN_CON_DERECHO_CASILLA,
    PRORRATA_VOLUMEN_TOTAL_CASILLA,
)
from .....core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId
from .....core.period import Period, StandardPeriodCode
from .....core.prorrata_register import SectorDiferenciadoLetra
from .....domain.calculations.registry.binding_targets import casillas_by_binding
from .....domain.calculations.registry.bindings import CasillaObservation
from .....domain.calculations.registry.form_codes import form_for_role
from .....domain.calculations.registry.prorrata_register_activity_bindings import (
    ProrrataActivityField,
    ProrrataRegisterActivityProvider,
)
from .....domain.calculations.registry.prorrata_register_catalogue import (
    carried_prior_definitiva_prorrata_provenance,
    especial_prorrata_register_regime,
    general_prorrata_register_regime,
)
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.calculations.registry.tests.registry_observations import registry_grounded_modelo_observation
from .....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .....domain.modelos.calculation_revision_sources import CalculationSourceRef
from .....domain.modelos.codes import ModeloCode
from .....domain.modelos.verification_report import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from .....domain.prorrata_register.register import ProrrataRegisterEntry, SectorDefinition
from ...tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ..calculation_observations import CalculationObservationRepository
from ..prorrata_register import ProrrataRegisterRepository
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET = "51e351e3-51e3-451e-851e-351e351e351e"
_runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET)
_YEAR = filing_year_envelope().horizon
_AT = datetime(_YEAR, 4, 20, 12, 0, tzinfo=UTC)
_LAST_RETURN_OF_THE_YEAR = StandardPeriodCode.Q4.value
_SETTLEMENT = {
    PRORRATA_VOLUMEN_TOTAL_CASILLA: Decimal("200000.00"),
    PRORRATA_VOLUMEN_CON_DERECHO_CASILLA: Decimal("150000.00"),
    PRORRATA_PORCENTAJE_CASILLA: Decimal("75"),
}
_FIRST = Decimal("58")
_SECOND = Decimal("61")


def _service() -> ProrrataRegisterService:
    return ProrrataRegisterService(repository=ProrrataRegisterRepository(), operation=published_authority_operation())


def _state(percentage: Decimal) -> None:
    _service().seed_whole_carried(
        _YEAR, observation_repository=CalculationObservationRepository(), stated_percentage=percentage
    )


def _ledger_iva_ref(source_ref: str) -> CalculationSourceRef:
    return CalculationSourceRef(
        resolver_id="ledger_iva_aggregation",
        resolved_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        contributor_source_kind="ledger_iva_aggregation",
        contributor_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref=source_ref,
        parent_source_ref=None,
    )


def _draft(
    state: CalculationRevisionState,
    *,
    exempt_output_records: int | None = None,
    period_code: str = StandardPeriodCode.Q1.value,
    casilla_values: dict[CasillaId, Decimal] | None = None,
) -> tuple[WorkUnit, CalculationRevision]:
    """A 303 calculated under the register's current apportionment, as the IVA binding records it.

    ``exempt_output_records`` records, as the binding does when no apportionment
    applied, that the period held that many records of exempt output left to the prorrata.
    ``casilla_values`` are the calculated casillas the revision holds.
    """
    operation = published_authority_operation()
    modelo = form_for_role("iva.periodic")
    period = Period.from_year_and_code(_YEAR, period_code)
    snapshot = operation.snapshot(
        modelo, filing_year=_YEAR, period=period.registry_token, grade=RegistryAuthorityGrade.CALCULATION
    )
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET, modelo=modelo, filing_year=_YEAR, period=period, revision_id=snapshot.revision.id
        ),
        bucket_id=_BUCKET,
        modelo=ModeloCode(modelo),
        filing_year=_YEAR,
        period=period,
        revision_id=snapshot.revision.id,
        name=f"{modelo}-{_YEAR}-{period.registry_token}",
        created_at=_AT,
        updated_at=_AT,
    )
    apportionment = sector_scoped_apportionment(
        ProrrataRegisterRepository().load(), _YEAR, sector_id=None, operation=operation
    )
    provenance = (
        ()
        if apportionment is None
        else (_ledger_iva_ref(iva_prorrata_apportionment_source_ref(period, apportionment)),)
    ) + (
        ()
        if exempt_output_records is None
        else (_ledger_iva_ref(prorrata_only_exempt_output_source_ref(period, exempt_output_records)),)
    )
    filed = state is CalculationRevisionState.PRESENTADO
    values = {} if casilla_values is None else casilla_values
    revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values=values,
            filing_instance_evidence=None,
            source_provenance=provenance,
            source_transaction_ids=(),
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=state,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=values,
        observations=tuple(
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                legal_refs=("ley-37-1992:art-105",),
                source_refs=("modelo-303-prorrata-seed-gate-test",),
            )
            for casilla_id, value in values.items()
        ),
        created_at=_AT,
        updated_at=_AT,
        filing_instance_evidence=None,
        source_provenance=provenance,
        source_transaction_ids=(),
        verified_at=_AT if filed else None,
        verified_by="operator" if filed else None,
        filed_at=_AT if filed else None,
        filed_by="operator" if filed else None,
    )
    return work_unit, revision


def _findings(draft: tuple[WorkUnit, CalculationRevision]) -> tuple[ProrrataSeedVerificationFinding, ...]:
    work_unit, revision = draft
    return prorrata_seed_verification_findings(
        work_unit=work_unit,
        target=revision,
        prorrata_register_repository=ProrrataRegisterRepository(),
        observation_repository=CalculationObservationRepository(),
        operation=published_authority_operation(),
    )


def _save_prior_annual_summary(percentage: Decimal) -> None:
    operation = published_authority_operation()
    modelo = form_for_role("iva.annual_summary")
    prior_year = _YEAR - 1
    revision = operation.snapshot(
        modelo,
        filing_year=prior_year,
        period=StandardPeriodCode.ANNUAL.value,
        grade=RegistryAuthorityGrade.CALCULATION,
    ).revision
    targets = casillas_by_binding(revision)
    box = next(
        targets[binding.id][0]
        for binding in revision.bindings
        if isinstance(binding.provider, ProrrataRegisterActivityProvider)
        and binding.provider.slot == 1
        and binding.provider.field is ProrrataActivityField.PORCENTAJE
    )
    repository = CalculationObservationRepository()
    repository.save(
        repository.prepare_observation_envelope(
            registry_grounded_modelo_observation(
                modelo=modelo,
                filing_year=prior_year,
                period=StandardPeriodCode.ANNUAL.value,
                casilla_values={box: percentage},
                grade=RegistryAuthorityGrade.CALCULATION,
            ),
            source_kind="aeat_sede_justificante",
            stamped_revision_id=str(revision.id),
            captured_at=datetime(_YEAR, 1, 30, 10, tzinfo=UTC),
        )
    )


def test_an_apportioning_entry_without_a_figure_blocks_with_the_seed_door() -> None:
    _service().declare(
        ProrrataRegisterEntry(
            ejercicio=_YEAR,
            regime=general_prorrata_register_regime(),
            especial_transition=None,
            sector_id=None,
            source_registry_snapshot_refs=(),
        )
    )

    findings = _findings(_draft(CalculationRevisionState.BORRADOR))

    assert len(findings) == 1
    finding, failure = findings[0].finding, findings[0].failure
    assert finding.message_locale_key == "application.modelo.findings.prorrata_seed_unsourced"
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert failure is not None
    assert failure.scenario_id == "modelo.work.verify.prorrata_seed.unsourced"
    assert failure.verdict.action is not None
    assert failure.verdict.action.action_id == "operator.ledger.prorrata.seed"


def test_the_exempt_output_reference_reads_back_its_record_count() -> None:
    period = Period.from_year_and_code(_YEAR, StandardPeriodCode.Q1.value)

    assert recorded_prorrata_only_exempt_output((prorrata_only_exempt_output_source_ref(period, 3),)) == 3
    assert recorded_prorrata_only_exempt_output(("transaction:abc", f"prorrata:{_YEAR}:rows:3")) is None
    assert recorded_prorrata_only_exempt_output(()) is None


def test_exempt_output_left_to_an_unseeded_prorrata_blocks_with_the_seed_door() -> None:
    """LIVA art. 102.Uno: exempt output without deduction right makes the prorrata apply, so none held refuses."""
    findings = _findings(_draft(CalculationRevisionState.BORRADOR, exempt_output_records=2))

    assert len(findings) == 1
    finding, failure = findings[0].finding, findings[0].failure
    assert finding.message_locale_key == "application.modelo.findings.prorrata_seed_unseeded"
    assert finding.kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert "ley-37-1992:art-102" in finding.legal_refs
    assert failure is not None
    assert failure.scenario_id == "modelo.work.verify.prorrata_seed.unseeded"
    assert failure.verdict.action is not None
    assert failure.verdict.action.action_id == "operator.ledger.prorrata.seed"


def test_exempt_output_raises_no_unseeded_finding_once_the_ejercicio_is_seeded() -> None:
    draft = _draft(CalculationRevisionState.BORRADOR, exempt_output_records=2)
    _state(_FIRST)

    keys = [item.finding.message_locale_key for item in _findings(draft)]

    assert "application.modelo.findings.prorrata_seed_unseeded" not in keys
    assert "application.modelo.findings.prorrata_seed_changed" in keys


def test_a_draft_without_exempt_output_and_an_empty_register_raises_nothing() -> None:
    assert _findings(_draft(CalculationRevisionState.BORRADOR)) == ()


def test_a_stated_figure_is_disclosed_without_blocking() -> None:
    _state(_FIRST)

    findings = _findings(_draft(CalculationRevisionState.BORRADOR))

    assert [item.finding.message_locale_key for item in findings] == [
        "application.modelo.findings.prorrata_seed_operator_stated"
    ]
    assert findings[0].finding.severity is ModeloVerificationFindingSeverity.WARNING
    assert findings[0].failure is None


def test_a_held_prior_return_contradicting_the_stated_figure_blocks_with_the_seed_door() -> None:
    _state(_FIRST)
    _save_prior_annual_summary(_SECOND)

    findings = _findings(_draft(CalculationRevisionState.BORRADOR))

    assert [item.finding.message_locale_key for item in findings] == [
        "application.modelo.findings.prorrata_seed_contradicted"
    ]
    failure = findings[0].failure
    assert failure is not None
    assert failure.scenario_id == "modelo.work.verify.prorrata_seed.contradicted"
    assert failure.verdict.action is not None
    assert failure.verdict.action.action_id == "operator.ledger.prorrata.seed"


def test_a_draft_calculated_before_the_figure_changed_is_sent_to_be_calculated_again() -> None:
    _state(_FIRST)
    draft = _draft(CalculationRevisionState.BORRADOR)
    _state(_SECOND)

    findings = _findings(draft)

    stale = [item for item in findings if item.finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION]
    assert [item.finding.message_locale_key for item in stale] == ["application.modelo.findings.prorrata_seed_changed"]
    assert stale[0].finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert stale[0].failure is not None
    assert stale[0].failure.scenario_id == "modelo.work.verify.prorrata_seed.changed"


def test_a_draft_calculated_before_any_figure_is_sent_to_be_calculated_again() -> None:
    draft = _draft(CalculationRevisionState.BORRADOR)
    _state(_FIRST)

    findings = _findings(draft)

    assert "application.modelo.findings.prorrata_seed_changed" in [item.finding.message_locale_key for item in findings]


def test_a_filed_return_under_a_superseded_figure_is_refused_with_the_amendment_door() -> None:
    _state(_FIRST)
    work_unit, filed = _draft(CalculationRevisionState.PRESENTADO)
    operation = published_authority_operation()

    require_filed_prorrata_seed_current(
        work_unit=work_unit,
        target=filed,
        prorrata_register_repository=ProrrataRegisterRepository(),
        operation=operation,
    )
    _state(_SECOND)
    with pytest.raises(ModeloProrrataSeedSupersededError) as refused:
        require_filed_prorrata_seed_current(
            work_unit=work_unit,
            target=filed,
            prorrata_register_repository=ProrrataRegisterRepository(),
            operation=operation,
        )

    failure = refused.value.precondition_failure
    assert failure is not None
    assert failure.scenario_id == "modelo.work.verify.prorrata_seed.superseded"
    assert failure.verdict.action is not None
    assert failure.verdict.action.action_id == "operator.modelo.work.amend_wizard"
    assert _findings((work_unit, filed)) == ()


def test_a_register_with_differentiated_sectors_takes_no_whole_entity_carry() -> None:
    _service().declare_sector(
        SectorDefinition(
            sector_id="comercio",
            letra=SectorDiferenciadoLetra.from_registry("a"),
            member_activity_codes=("4711",),
        )
    )

    with pytest.raises(ProrrataWholeSeedUnavailableError) as refused:
        _state(_FIRST)

    assert refused.value.reason == "source_blocked"
    assert [finding.code for finding in refused.value.findings] == [PRORRATA_DIFFERENTIATED_SECTOR]
    assert ProrrataRegisterRepository().load().entry_for(_YEAR) is None


def _last_return_findings() -> tuple[ProrrataSeedVerificationFinding, ...]:
    return _findings(
        _draft(CalculationRevisionState.BORRADOR, period_code=_LAST_RETURN_OF_THE_YEAR, casilla_values=_SETTLEMENT)
    )


def test_a_last_return_of_the_year_settles_into_the_register_without_a_prior_declaration() -> None:
    assert _last_return_findings() == ()
    assert ProrrataRegisterRepository().load().entry_for(_YEAR) is None


def test_a_last_return_after_an_especial_year_with_no_declaration_blocks_before_export() -> None:
    _service().declare(
        ProrrataRegisterEntry(
            ejercicio=_YEAR - 1,
            regime=especial_prorrata_register_regime(),
            especial_transition=None,
            sector_id=None,
            source_registry_snapshot_refs=(),
        )
    )

    (item,) = _last_return_findings()

    assert item.finding.message_locale_key == PRORRATA_SETTLEMENT_ESPECIAL_CONTINUATION_LOCALE_KEY
    assert item.finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert dict(item.finding.message_facts) == {"filing_year": _YEAR, "prior_filing_year": _YEAR - 1}
    assert item.finding.legal_refs == ("ley-37-1992:art-105",)
    assert item.failure is not None
    assert item.failure.scenario_id == "modelo.work.verify.prorrata_settlement.especial_continuation"
    assert ProrrataRegisterRepository().load().entry_for(_YEAR) is None


def test_a_last_return_with_an_undeclared_sector_blocks_before_export() -> None:
    _service().declare_sector(
        SectorDefinition(
            sector_id="comercio",
            letra=SectorDiferenciadoLetra.from_registry("a"),
            member_activity_codes=("4711",),
        )
    )

    (item,) = _last_return_findings()

    assert item.finding.message_locale_key == "application.modelo.findings.prorrata_settlement_sector_entries"
    assert item.finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert dict(item.finding.message_facts) == {"filing_year": _YEAR, "sector_ids": "comercio"}
    assert item.failure is not None
    assert item.failure.scenario_id == "modelo.work.verify.prorrata_settlement.sector_entries"
    assert _findings(_draft(CalculationRevisionState.BORRADOR, casilla_values=_SETTLEMENT)) == ()


def test_a_stated_figure_gives_way_to_the_held_prior_return_on_reseeding() -> None:
    _state(_FIRST)
    _save_prior_annual_summary(_SECOND)

    commit = _service().seed_whole_carried(_YEAR, observation_repository=CalculationObservationRepository())

    assert not commit.seed.operator_stated
    assert commit.seed.source_modelo == form_for_role("iva.annual_summary")
    entry = ProrrataRegisterRepository().load().entry_for(_YEAR)
    assert entry is not None
    assert entry.provisional_percentage == _SECOND
    assert entry.provisional_provenance == carried_prior_definitiva_prorrata_provenance()
