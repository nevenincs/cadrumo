"""Domiciliation cutoff coverage at the application export seam."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from pathlib import Path

import pytest

from ....core.errors.error_codes import (
    build_error_envelope,
    get_registered_error_code,
    resolve_error_message,
)
from ....core.payment_election import PaymentElection
from ....core.period import Period, PeriodKind, accepted_filing_period_codes
from ....core.result_disposition import ResultDisposition
from ....core.time.clock import MADRID_TZ
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.legal_text import legal_effective_to
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.deadlines.domiciliation_cutoff import UnavailablePaymentCutoff, resolve_payment_cutoff
from ....domain.deadlines.errors import DeadlineValidationError
from ....domain.deadlines.festivos import holiday_calendar_from_authority
from ....domain.deadlines.plazo import resolve_filing_window
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..action_errors import ModeloDomiciliationPastCutoffError
from ..export_accounts import require_domiciliation_before_cutoff
from ..export_contracts import ModeloExportCommand

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOCK = datetime(1980, 1, 1, tzinfo=UTC)
# The exercise is the one whose fourth quarter closes in the year of the newest
# published holiday calendar, so every quarter of it resolves a cutoff.
_EXERCISE = legal_effective_to("resolucion-dgt-2026-10-08-fiestas-laborales-2027:anexo").year - 1
_BUCKET_ID = "6e84e19e-58f8-4241-b2d1-6ab9bcc3dd7b"


# Modelo 303 monthly period 01 of the exercise authors its payment cutoff on its
# window. The quarterly 3T window authors none, and the rule derives the Anexo II
# day of Orden EHA/1658/2009 for the third quarter in October. The 4T window
# closes in the next January, after the weekend that precedes the 1 February
# close, so the Anexo II day runs on to a business day. Clocks are UTC; the gate
# compares the Europe/Madrid civil date, so the last admitted minute is 23:59 in
# Madrid and the first refused one is the following Madrid midnight.
@pytest.mark.parametrize(
    ("period_code", "payment_cutoff_source", "expects_refusal"),
    (
        ("01", "authored", False),
        ("01", "authored", True),
        ("3T", "derived", False),
        ("3T", "derived", True),
        ("4T", "derived", False),
        ("4T", "derived", True),
    ),
    ids=(
        "on-the-authored-madrid-cutoff-day",
        "after-the-authored-madrid-cutoff-day",
        "on-the-derived-madrid-cutoff-day",
        "after-the-derived-madrid-cutoff-day",
        "on-the-derived-year-end-madrid-cutoff-day",
        "after-the-derived-year-end-madrid-cutoff-day",
    ),
)
def test_domiciliation_is_refused_after_the_window_payment_cutoff_in_madrid(
    period_code: str,
    payment_cutoff_source: str,
    expects_refusal: bool,
    operation: PinnedAuthorityOperation,
) -> None:
    """The gate closes on the authored or derived cutoff alike."""
    period = Period.from_year_and_code(_EXERCISE, period_code)
    work_unit = _work_unit_for(period, operation)
    resolution = resolve_filing_window("303", period.filing_year, period, authority=operation)
    assert resolution is not None
    assert resolution.dated_window is not None
    cutoff = resolve_payment_cutoff("303", resolution.dated_window, operation=operation)
    assert not isinstance(cutoff, UnavailablePaymentCutoff)
    assert cutoff.source.value == payment_cutoff_source
    cutoff_on = cutoff.cutoff_on
    export_on = cutoff_on + timedelta(days=1)
    if period_code == "4T":
        assert cutoff_on.year == _EXERCISE + 1, "the fourth quarter closes in January of the next year"
    if payment_cutoff_source == "derived":
        assert cutoff_on.weekday() < 5, "the derived cutoff is a business day"
    exported_at = (
        datetime.combine(export_on, time(0, 0), tzinfo=MADRID_TZ)
        if expects_refusal
        else datetime.combine(cutoff_on, time(23, 59), tzinfo=MADRID_TZ)
    ).astimezone(UTC)
    command = ModeloExportCommand(
        calculation_revision_id="a" * 64,
        output_path=Path("unused.txt"),
        actor="operator",
        payment_election=PaymentElection.DOMICILIACION,
    )

    def gate(disposition: ResultDisposition | None) -> bool:
        return require_domiciliation_before_cutoff(
            command,
            work_unit=work_unit,
            resolved_result_disposition=disposition,
            exported_at=exported_at,
            operation=operation,
        )

    assert gate(ResultDisposition.INGRESO) is False
    if expects_refusal:
        with pytest.raises(ModeloDomiciliationPastCutoffError) as refused:
            gate(ResultDisposition.DOMICILIACION)
        assert get_registered_error_code(refused.value).code == "REFUSED_MODELO_DOMICILIATION_PAST_CUTOFF"
        expected_context = {
            "calculation_revision_id": "a" * 64,
            "modelo": "303",
            "filing_year": str(_EXERCISE),
            "period": period_code,
        }
        if period_code == "01":
            expected_context |= {
                "payment_cutoff_on": cutoff_on.isoformat(),
                "payment_cutoff_source": "authored",
                "payment_cutoff_legal_refs": "rd-1624-1992:art-71",
                "export_on": export_on.isoformat(),
            }
        else:
            clause = "quarterly:4t" if period_code == "4T" else "quarterly:1t-3t"
            expected_context |= {
                "payment_cutoff_on": cutoff_on.isoformat(),
                "payment_cutoff_source": "derived",
                "export_on": export_on.isoformat(),
                "payment_cutoff_rule": (
                    f"domiciliation-cutoff-clause:303:{clause}, domiciliation-procedure:aeat-practice-2026"
                ),
                "payment_cutoff_legal_refs": (
                    "orden-eha-1658-2009:anexo-ii, rd-1624-1992:art-71, "
                    "orden-eha-1658-2009:art-3, orden-hac-241-2025:art-2"
                ),
            }
        assert refused.value.context == expected_context
        envelope = build_error_envelope(refused.value)
        assert envelope.context is not None
        assert dict(envelope.context) == expected_context
        message = resolve_error_message(refused.value, locale="en")
        assert f"closed on {expected_context['payment_cutoff_on']}" in message
        assert str(expected_context["payment_cutoff_legal_refs"]) in message
        if period_code == "01":
            assert "the filing window itself sets" in message
            assert "derived" not in message
        else:
            assert "derived from the direct-debit rule" in message
            assert str(expected_context["payment_cutoff_rule"]) in message
    else:
        assert gate(ResultDisposition.DOMICILIACION) is False


def _work_unit_for(period: Period, operation: PinnedAuthorityOperation) -> WorkUnit:
    snapshot = operation.snapshot("303", filing_year=period.filing_year, period=period.registry_token)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=period.filing_year,
            period=period,
            revision_id=snapshot.revision.id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=period.filing_year,
        period=period,
        revision_id=snapshot.revision.id,
        name=f"303-{period.filing_year}-{period.registry_token}",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _supported_quarterly_periods() -> tuple[Period, ...]:
    support = published_supported_filing_years()
    assert support is not None, "the published authority declares no support envelope"
    first_year = support.years[0]
    quarterly_codes = tuple(
        code
        for code in accepted_filing_period_codes()
        if Period.from_year_and_code(first_year, code).kind is PeriodKind.QUARTERLY
    )
    return tuple(Period.from_year_and_code(year, code) for year in support.years for code in quarterly_codes)


_QUARTERLY_PERIODS = _supported_quarterly_periods()


@pytest.mark.parametrize("period", _QUARTERLY_PERIODS, ids=[str(period) for period in _QUARTERLY_PERIODS])
def test_domiciliation_closes_at_the_resolved_cutoff_of_every_supported_quarter(
    period: Period, operation: PinnedAuthorityOperation
) -> None:
    """Every quarterly 303 window refuses from the day after its cutoff, derived or authored alike.

    The periods are the registry's: its supported filing years and the quarterly
    codes it accepts. A quarter whose cutoff the registry cannot yet resolve must
    advise rather than refuse, so a quarter that regains a cutoff is never left
    ungated and none is silently skipped.
    """
    resolution = resolve_filing_window("303", period.filing_year, period, authority=operation)
    assert resolution is not None, f"no 303 window for {period}"
    window = resolution.dated_window
    assert window is not None, f"the 303 window of {period} has no known close"
    work_unit = _work_unit_for(period, operation)
    command = ModeloExportCommand(
        calculation_revision_id="a" * 64,
        output_path=Path("unused.txt"),
        actor="operator",
        payment_election=PaymentElection.DOMICILIACION,
    )

    def gate(exported_on: datetime) -> bool:
        return require_domiciliation_before_cutoff(
            command,
            work_unit=work_unit,
            resolved_result_disposition=ResultDisposition.DOMICILIACION,
            exported_at=exported_on,
            operation=operation,
        )

    cutoff = resolve_payment_cutoff("303", window, operation=operation)
    if isinstance(cutoff, UnavailablePaymentCutoff):
        assert gate(datetime.combine(window.closes_on, time(12), tzinfo=MADRID_TZ)) is True
        return

    cutoff_on = cutoff.cutoff_on
    assert window.opens_on <= cutoff_on < window.closes_on
    assert gate(datetime.combine(cutoff_on, time(23, 59), tzinfo=MADRID_TZ)) is False
    day_after = datetime.combine(cutoff_on + timedelta(days=1), time(0, 0), tzinfo=MADRID_TZ)
    with pytest.raises(ModeloDomiciliationPastCutoffError) as refused:
        gate(day_after)
    context = refused.value.context
    assert context is not None
    assert context["payment_cutoff_on"] == cutoff_on.isoformat()
    assert context["payment_cutoff_source"] == cutoff.source.value
    assert context["period"] == period.registry_token
    assert context["filing_year"] == str(period.filing_year)


def test_a_year_end_quarter_closing_in_an_unpublished_calendar_year_advises_instead_of_refusing(
    operation: PinnedAuthorityOperation,
) -> None:
    """The 4T window after the last published holiday calendar has no cutoff yet, so the gate advises.

    The fourth quarter of a year closes in January of the next year; when that
    year's días inhábiles are not published the cutoff cannot be resolved, and
    domiciliación is admitted with an advisory rather than refused on a guess.
    """
    last_published = _last_published_holiday_calendar_year(operation)
    period = Period.from_year_and_code(last_published, "4T")
    command = ModeloExportCommand(
        calculation_revision_id="a" * 64,
        output_path=Path("unused.txt"),
        actor="operator",
        payment_election=PaymentElection.DOMICILIACION,
    )
    exported_at = datetime(last_published + 1, 1, 10, 12, 0, tzinfo=MADRID_TZ)
    assert (
        require_domiciliation_before_cutoff(
            command,
            work_unit=_work_unit_for(period, operation),
            resolved_result_disposition=ResultDisposition.DOMICILIACION,
            exported_at=exported_at,
            operation=operation,
        )
        is True
    )


def _last_published_holiday_calendar_year(operation: PinnedAuthorityOperation) -> int:
    """The latest year whose días inhábiles calendar the authority publishes."""
    support = published_supported_filing_years()
    assert support is not None, "the published authority declares no support envelope"
    year = support.years[-1]
    holiday_calendar_from_authority(year, operation=operation)
    while True:
        try:
            holiday_calendar_from_authority(year + 1, operation=operation)
        except DeadlineValidationError:
            return year
        year += 1
