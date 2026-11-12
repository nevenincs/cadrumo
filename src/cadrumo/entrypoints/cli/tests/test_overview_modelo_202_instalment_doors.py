"""Every door an undecided Modelo 202 instalment opens resolves against the live command surface.

A door that does not resolve would be dropped from the calendar payload, so the
operator would see an undecided instalment with no way forward. These tests
render real calendars through the CLI projection and require each declared door
to arrive as a resolved action, in the declared order.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

import pytest

from ....application.overview.applicability_evidence import FilingYearApplicabilityEvidence
from ....application.overview.calendar import build_overview_calendar
from ....application.overview.calendar_models import OverviewCalendarRange
from ....application.overview.modelo202_instalment import (
    Modelo202BaseSource,
    Modelo202InstalmentFacts,
)
from ....core.period import Period
from ....domain.calculations.registry.applicability_modelo202 import (
    modelo_202_incn_threshold_decimal,
    resolve_modelo_202_art_40_3_incn_threshold,
)
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.contribuyente.entity_type import EntityType
from ....domain.contribuyente.renta_codes import FiscalResidency
from ....domain.deadlines.models import IVARegime, ModeloEnrollment, TaxpayerProfile
from ..overview_rendering import overview_calendar_output

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MODELO_202 = "202"
_WORK_UNIT_ID = "b" * 64


def _year() -> int:
    return filing_year_envelope().horizon


def _facts(
    token: str,
    *,
    election: bool | None = False,
    base_source: bool = True,
    no_prior_return: bool = False,
    work_unit_id: str | None = None,
) -> Modelo202InstalmentFacts:
    return Modelo202InstalmentFacts(
        instalment=Period.from_year_and_code(_year(), token),
        election_stated=election,
        base_source=(
            Modelo202BaseSource(modelo="200", period=Period.from_year_and_code(_year() - 1, "0A"))
            if base_source
            else None
        ),
        no_prior_return=no_prior_return,
        base=None,
        work_unit_id=work_unit_id,
        calculation=None,
    )


def _legal_entity(operation: PinnedAuthorityOperation) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B00015016",
        entity_type=EntityType.from_registry("legal_entity"),
        iva_regime=IVARegime("GENERAL"),
        has_employees=False,
        pays_professionals_with_retencion=False,
        art109_activity_income_withholding_ge_70pct=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
        bienes_extranjero_above_threshold=False,
        fiscal_residency=FiscalResidency.from_registry("resident_irpf"),
        enrollment=ModeloEnrollment(large_company=False),
        incn_prior_12_months=modelo_202_incn_threshold_decimal(
            resolve_modelo_202_art_40_3_incn_threshold(effective_date=date(_year(), 12, 31), authority=operation),
        ),
    )


def _suppressed_doors(
    facts_by_token: Mapping[str, Modelo202InstalmentFacts],
    operation: PinnedAuthorityOperation,
) -> dict[str, list[dict[str, Any]]]:
    profile = _legal_entity(operation)
    rng = OverviewCalendarRange(from_date=date(_year(), 1, 1), to_date=date(_year(), 12, 31))
    calendar = build_overview_calendar(
        profile,
        rng,
        operation=operation,
        today=date(_year(), 1, 1),
        show_suppressed=True,
        applicability_evidence=FilingYearApplicabilityEvidence(
            profile_for_year=lambda _year: profile,
            ledger_payer_facts_for_year=lambda _year: {},
            modelo_202_instalment_facts=lambda instalment: facts_by_token[instalment.registry_token],
        ),
    )
    suppressed = [entry for entry in calendar.suppressed_entries if entry.modelo == _MODELO_202]
    token_by_wire_period = {
        entry.model_dump(mode="json")["period"]: entry.period.registry_token for entry in suppressed
    }
    declared = {entry.period.registry_token: [door.action.action_id for door in entry.actions] for entry in suppressed}
    result, _lines, _notices = overview_calendar_output(calendar, rng, evidence_notices=())
    payload = result.model_dump(mode="json")
    rendered = {
        token_by_wire_period[entry["period"]]: entry["actions"]
        for entry in payload["suppressed_entries"]
        if entry["modelo"] == _MODELO_202
    }
    assert {token: [action["action"]["action_id"] for action in doors] for token, doors in rendered.items()} == (
        declared
    )
    return rendered


def test_undecided_base_and_election_doors_resolve(authority_operation: PinnedAuthorityOperation) -> None:
    rendered = _suppressed_doors(
        {
            "1P": _facts("1P", election=None),
            "2P": _facts("2P", work_unit_id=_WORK_UNIT_ID),
            "3P": _facts("3P"),
        },
        authority_operation,
    )
    assert [door["action"]["action_id"] for door in rendered["1P"]] == ["operator.profile.edit"]
    assert [door["action"]["action_id"] for door in rendered["2P"]] == [
        "operator.modelo.work.create",
        "operator.live.filed.pull",
        "operator.modelo.work.verify",
    ]
    assert [door["action"]["action_id"] for door in rendered["3P"]] == [
        "operator.modelo.work.create",
        "operator.live.filed.pull",
        "operator.modelo.work.create",
    ]


def test_pending_calculation_undeclared_base_and_no_prior_return_doors_resolve(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    rendered = _suppressed_doors(
        {
            "1P": _facts("1P", election=True, work_unit_id=_WORK_UNIT_ID),
            "2P": _facts("2P", base_source=False),
            "3P": _facts("3P", no_prior_return=True),
        },
        authority_operation,
    )
    assert [door["action"]["action_id"] for door in rendered["1P"]] == ["operator.modelo.work.calculate"]
    assert [door["action"]["action_id"] for door in rendered["2P"]] == ["operator.modelo.describe"]
    assert [door["action"]["action_id"] for door in rendered["3P"]] == ["operator.profile.edit"]
