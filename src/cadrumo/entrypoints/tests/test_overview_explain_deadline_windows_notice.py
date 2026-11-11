"""An explanation with no deadline windows says so rather than reading as on time."""

from __future__ import annotations

from typing import NoReturn, override
from uuid import UUID

import pytest

from ...application.overview import explain as explain_module
from ...application.overview.applicability_evidence import FilingYearApplicabilityEvidence
from ...application.overview.read_request import OverviewReadKind, OverviewReadRequest
from ...application.overview.tests.calendar_test_support import profile
from ...core.external_constants import OutputLanguage
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.tests.authored_editions import newest_authored_edition
from ...domain.deadlines.engine import DeadlineEngine
from ...domain.deadlines.errors import NoDeadlineWindowsError
from ..overview_read_composition import _OverviewReadPorts

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MODELO = "100"
_YEAR = newest_authored_edition(_MODELO)
_NOTICE_CODE = "deadline.windows_unavailable.explain"


class _Windowless(DeadlineEngine):
    @override
    def deadline_windows(self, year: int) -> NoReturn:
        raise NoDeadlineWindowsError(
            translated_message="application.overview.calendar.shift.modelo_exception",
            context={"filing_year": year},
        )


def _explain_notices() -> tuple[tuple[str, str | None], ...]:
    request = OverviewReadRequest(
        profile_id=UUID(int=1),
        kind=OverviewReadKind.EXPLAIN,
        output_language=OutputLanguage.EN,
        modelo=_MODELO,
        year=_YEAR,
    )
    with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
        taxpayer = profile()
        evidence = FilingYearApplicabilityEvidence(
            profile_for_year=lambda _year: taxpayer,
            ledger_payer_facts_for_year=lambda _year: {},
        )
        read = _OverviewReadPorts(bucket_id=str(UUID(int=1)))._explain(
            request, operation=operation, record=None, taxpayer=taxpayer, evidence=evidence
        )
    return tuple((notice.code, notice.action_id) for notice in read.notices)


def test_a_windowless_year_adds_one_unavailable_notice_with_the_status_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(explain_module, "DeadlineEngine", _Windowless)

    notices = _explain_notices()

    assert [notice for notice in notices if notice[0] == _NOTICE_CODE] == [(_NOTICE_CODE, "operator.overview.status")]


def test_a_year_with_windows_adds_no_unavailable_notice() -> None:
    assert all(code != _NOTICE_CODE for code, _action in _explain_notices())
