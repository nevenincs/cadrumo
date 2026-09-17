"""Amending an in-force pending correction chains to the latest confirmed declaration."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.tests.import_flow_support import (
    _IMPORT_EXPENSE_CASILLA,
    _IMPORT_INCOME_CASILLA,
    _T1,
    _T2,
    _T3,
    _TAX_ID,
    _import_external_filing,
    _persist_matching_justificante,
    _Repos,
    _seed_work_unit,
    repos,
)
from cadrumo.application.calculations.observations_repository import ObservationSourceKind
from cadrumo.application.modelo.action_errors import AmendmentEvidenceMissingError
from cadrumo.application.modelo.amendment_actions import amend_modelo_revision
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind
from cadrumo.domain.modelos.filing_record import AeatConfirmationState, FilingDeclarationKind, ModeloRecordStatus
from cadrumo.entrypoints.adapter_composition import build_amendment_action_ports

__all__ = ["repos"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _amend(work_unit_bucket_id: str, record_id: str, income: str, *, operation: PinnedAuthorityOperation, clock):
    return amend_modelo_revision(
        ports=build_amendment_action_ports(bucket_id=work_unit_bucket_id, operation=operation),
        from_filing_record_id=record_id,
        overrides={_IMPORT_INCOME_CASILLA: Decimal(income)},
        amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        reason="revenue correction",
        actor="operator-A",
        clock=clock,
        operation=operation,
    )


def test_amending_a_pending_correction_discards_it_and_amends_the_confirmed_declaration(
    repos: _Repos, *, operation: PinnedAuthorityOperation
) -> None:
    wu_repo, _cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo, bv_repo, operation=operation)
    _persist_matching_justificante("JUSTCHAIN0001", work_unit, captured_at=_T1)
    imported = _import_external_filing(
        repos,
        work_unit,
        casilla_values={_IMPORT_INCOME_CASILLA: Decimal("1500"), _IMPORT_EXPENSE_CASILLA: Decimal("300")},
        evidence_reference_id="JUSTCHAIN0001",
        expected_tax_id=_TAX_ID,
        clock=_T1,
    )

    first = _amend(work_unit.bucket_id, imported.filing_record_id, "1600", operation=operation, clock=_T2)
    second = _amend(work_unit.bucket_id, first.filing_record_id, "1700", operation=operation, clock=_T3)

    catalogue = fr_repo.load()
    discarded = catalogue.records[first.filing_record_id]
    confirmed = catalogue.records[imported.filing_record_id]
    in_force = catalogue.records[second.filing_record_id]
    assert discarded.confirmation is AeatConfirmationState.DESCARTADA
    assert discarded.status is ModeloRecordStatus.SUPERSEDIDO
    assert discarded.superseded_by_filing_record_id == second.filing_record_id
    assert in_force.status is ModeloRecordStatus.VIGENTE
    assert in_force.confirmation is AeatConfirmationState.PENDIENTE
    assert in_force.declaration_kind is FilingDeclarationKind.COMPLEMENTARIA
    assert in_force.amends_filing_record_id == imported.filing_record_id
    assert confirmed.superseded_by_filing_record_id == second.filing_record_id
    assert (
        catalogue.latest_confirmed_for(
            bucket_id=work_unit.bucket_id,
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
        )
        == confirmed
    )

    layers = CalculationObservationRepository().load_observation_layers(work_unit.modelo, work_unit.period)
    assert layers.pending_local is not None
    assert layers.pending_local.source_kind is ObservationSourceKind.APP_FILING
    assert layers.pending_local.observation.casilla_values[_IMPORT_INCOME_CASILLA] == Decimal("1700")


def test_amending_without_a_confirmed_declaration_is_refused(
    repos: _Repos, *, operation: PinnedAuthorityOperation
) -> None:
    wu_repo, _cr_repo, fr_repo, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo, bv_repo, operation=operation)
    _persist_matching_justificante("JUSTCHAIN0002", work_unit, captured_at=_T1)
    imported = _import_external_filing(
        repos,
        work_unit,
        casilla_values={_IMPORT_INCOME_CASILLA: Decimal("1500")},
        evidence_reference_id="JUSTCHAIN0002",
        expected_tax_id=_TAX_ID,
        clock=_T1,
    )
    pending = _amend(work_unit.bucket_id, imported.filing_record_id, "1600", operation=operation, clock=_T2)
    catalogue = fr_repo.load()
    unconfirmed = catalogue.records[imported.filing_record_id].model_copy(
        update={
            "origin": catalogue.records[pending.filing_record_id].origin,
            "confirmation": AeatConfirmationState.DESCARTADA,
            "external_evidence": None,
            "aeat_register": None,
        },
    )
    fr_repo.save(
        catalogue.model_copy(update={"records": {**catalogue.records, unconfirmed.filing_record_id: unconfirmed}})
    )

    with pytest.raises(AmendmentEvidenceMissingError):
        _amend(work_unit.bucket_id, pending.filing_record_id, "1700", operation=operation, clock=_T3)
