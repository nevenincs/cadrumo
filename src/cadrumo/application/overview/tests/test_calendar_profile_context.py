"""Missing saved facts accompany every affected deadline, without changing the engine's dates."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ....core.config import override_settings
from ....core.i18n.render import I18N_STRICT_MISSING_KEYS, tr
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.deadlines.models import ObligationStatus
from ..agenda import build_overview_agenda
from ..backlog import build_overview_backlog
from ..calendar import build_overview_calendar
from ..calendar_models import OverviewCalendarRange
from ..calendar_warnings import _PROFILE_FIELD_WARNING_META
from ..read_calendar_projection import OverviewAgendaSnapshot, OverviewBacklogSnapshot, OverviewCalendarSnapshot
from .calendar_test_support import profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("answered", [False, True])
def test_saved_false_and_unknown_are_distinct_on_calendar_agenda_and_backlog_rows(
    authority_operation: PinnedAuthorityOperation, answered: bool
) -> None:
    raw: dict[str, object] = {
        "iva.regime": "GENERAL",
        "tax_residence.jurisdiction_scope": "common_regime",
        "iva.m303_regime_composition": "general",
        "iva.redeme_enrolled": False,
        "iva.cash_accounting_regime_enrolled": False,
        "iva.voluntary_sii_enrolled": False,
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": False,
        "irpf.estimation_regime": "directa_normal",
        "has_employees": False,
        "pays_professionals_with_retencion": False,
        "pays_rent_with_retencion": False,
        "pays_capital_income_with_retencion": False,
        "does_intracomunitario": False,
        "third_party_transactions_above_347_threshold": False,
    }
    if answered:
        raw["art109_activity_income_withholding_ge_70pct"] = False
    today = date(2026, 10, 19)
    with override_settings(cadrumo_output_language="en"):
        calendar = build_overview_calendar(
            profile(),
            OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2027, 2, 1)),
            operation=authority_operation,
            today=today,
            raw_values=raw,
        )
        agenda = build_overview_agenda(profile(), as_of=today, operation=authority_operation, raw_values=raw)
        backlog = build_overview_backlog(profile(), as_of=today, operation=authority_operation, raw_values=raw)
        captured = OverviewCalendarSnapshot.from_calendar(calendar)
        agenda_capture = OverviewAgendaSnapshot.from_agenda(agenda)
        backlog_capture = OverviewBacklogSnapshot.from_backlog(backlog)

    for rows in (captured.entries, (*agenda_capture.due_soon, *agenda_capture.overdue), backlog_capture.items):
        target = [row for row in rows if row.modelo == "130"]
        assert target
        for row in target:
            assert row.profile_confirmation_required is not answered
            assert bool(row.missing_profile_information) is not answered
            assert all(not text.startswith("cli.") for text in row.missing_profile_information)
            if not answered:
                assert "70" in " ".join(row.missing_profile_information)
                assert row.missing_profile_information[0].startswith("Your profile does not yet record")
        assert all(not row.profile_confirmation_required for row in rows if row.modelo == "303")

    assert captured.to_calendar() == calendar
    assert agenda_capture.to_agenda() == agenda
    assert backlog_capture.to_backlog() == backlog
    assert captured.late_count == sum(row.status is ObligationStatus.OVERDUE for row in calendar.entries)
    assert any(row.status is ObligationStatus.DUE_SOON for row in captured.entries)
    data = captured.model_dump(mode="python")
    data["late_count"] = len(captured.entries)
    with pytest.raises(ValidationError, match="late_count"):
        OverviewCalendarSnapshot.model_validate(data)


@pytest.mark.parametrize(
    ("language", "prefix"),
    [("en", "Your profile"), ("es", "En tu perfil"), ("ca", "Al teu perfil"), ("hu", "A profilodban")],
)
def test_every_profile_gap_has_real_prose_in_every_supported_language(language: str, prefix: str) -> None:
    token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        for message_key, _action in _PROFILE_FIELD_WARNING_META.values():
            assert tr(message_key, locale=language).startswith(prefix)
    finally:
        I18N_STRICT_MISSING_KEYS.reset(token)
