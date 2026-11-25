"""End-to-end CLI verification of when ``work file`` finds a pending obligation.

A period whose plazo closed and was never filed is still owed: Ley 58/2003
art. 27.1 charges a recargo on a return presented after its plazo rather than
extinguishing it, so the late period files locally as extemporánea with its
served lateness. A period whose window has not opened, or a modelo the
profile rules out, has no pending obligation, and the refusal happens before
any effect.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from click.testing import Result

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_fact_strings
from cadrumo.core.time.clock import today_madrid
from cadrumo.domain.calculations.registry.tests.legal_text import legal_text_match
from cadrumo.domain.calculations.registry.tests.published_authority import (
    PublishedGovernedFactSource,
    published_selected_revision_id,
)
from cadrumo.entrypoints.cli.tests.cli_fixture_worlds import invoke_joined_cli
from cadrumo.entrypoints.cli.tests.modelo_cli import create_modelo_work_unit_via_cli
from cadrumo.entrypoints.cli.tests.modelo_work_scenarios import (
    capture_m115_invoice_withholding,
    create_calculable_modelo_work_unit,
    invoke_modelo_scenario_cli,
    operator_profile_facts,
)
from cadrumo.tests.cli_envelope import require_error_document, unwrap_envelope_notices, unwrap_schema_envelope

from .modelo_profile_seed import ProfileSeeder, seed_profile

__all__ = ["seed_profile"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _work(verb: str, modelo: str, filing_year: int, period: str, *extra: str) -> Result:
    """Invoke one ``app modelo work`` verb in JSON on a model, year and period target."""
    return invoke_joined_cli(
        [
            "--format", "json",
            "app", "modelo", "work", verb,
            "--modelo", modelo, "--year", str(filing_year), "--period", period,
            *extra,
        ],
    )  # fmt: skip


def _calculate_and_verify(modelo: str, filing_year: int, period: str) -> Result:
    """Calculate and verify the target's current revision; return the calculation's CLI result."""
    calculated = _work("calculate", modelo, filing_year, period)
    assert calculated.exit_code == 0, calculated.output
    verified = _work("verify", modelo, filing_year, period)
    assert verified.exit_code == 0, verified.output
    verification = unwrap_schema_envelope(verified.output)
    assert verification["granted_verificado_completo"] is True
    status = _work("status", modelo, filing_year, period)
    assert status.exit_code == 0, status.output
    current = unwrap_schema_envelope(status.output)["current_calculation_revision_id"]
    assert current == verification["calculation_revision_id"]
    return calculated


def _assert_refused_before_any_effect(result: Result, *, abort_code: str) -> None:
    """The workflow gate refused before the filing wrote anything, so the settled effect is none."""
    assert result.exit_code != 0
    context = require_error_document(result.output)["error"]["context"]
    assert context["abort_code"] == abort_code
    assert context["effect"] == "none"


def test_work_file_refuses_no_pending_obligation_for_a_filing_window_not_yet_open(
    seed_profile: ProfileSeeder,
) -> None:
    """`work file` reports NO_PENDING_OBLIGATION, in Catalan, for a quarter whose filing window has not opened.

    This target genuinely has no pending obligation for a reason true on every
    run date: a 4T window always opens on 1 January of the following filing
    year (authored rows in
    ``.../modelo-111/.../deadline_windows/0001-declarations.toml``, each
    ``opens_on`` one day into the next year), so the *current calendar year's
    own* 4T window cannot have opened yet on any day of that year. ``work
    file`` resolves ``obligation.opens_on > today`` and the workflow aborts at
    ``COMPUTING_DEADLINES`` with ``WorkflowAbortReason.NO_PENDING_OBLIGATION``
    (``application/workflow/deadline_decisions.py::decide_filing_deadline``),
    never reaching the overdue/extemporánea branch. The filing year is read
    from the clock, never a literal; the registry declares no ceiling above
    its authored horizon (``.../legal/supported-filing-years.toml``), so a
    year at or beyond the horizon still resolves through projection
    (``domain/deadlines/filing_window_projection.py``) rather than refusing.
    Calculation, ``ledger invoice add`` and ``modelo aggregate`` accept a
    date inside a not-yet-elapsed quarter, so a quarter that has not finished
    yet still produces one real, calculable percepción. Verification treats
    a filing window as informational and never aborts on it. The refusal
    happens before the filing writes anything: the refused attempt's own run
    record is not an effect of the filing.
    """
    filing_year = today_madrid().year
    period = "4T"
    seed_profile(label="operator", facts=operator_profile_facts())
    create_calculable_modelo_work_unit(filing_year=filing_year, period=period, paid_on=date(filing_year, 11, 15))
    _calculate_and_verify("111", filing_year, period)

    result = invoke_modelo_scenario_cli(
        [
            "app", "modelo", "work", "file",
            "--modelo", "111", "--year", str(filing_year), "--period", period,
            "--output-language", "ca",
        ],
    )  # fmt: skip
    assert result.exit_code != 0
    assert "file requires a verified-complete revision" not in result.output
    assert "No pending filing obligation" not in result.output
    assert "No hi ha cap obligació de presentació pendent" in result.output
    assert "NO_PENDING_OBLIGATION" in result.output

    _assert_refused_before_any_effect(_work("file", "111", filing_year, period), abort_code="NO_PENDING_OBLIGATION")


def _filed_more_than_twelve_months_late_year() -> int:
    """Return the newest supported year whose first-quarter plazo closed over twelve months before today.

    A first-quarter window closes in the spring of its own filing year, so two
    calendar years back is past the Art. 27.2 LGT twelve-month boundary on any
    run date. The year comes from the registry envelope, never a literal.
    """
    support = PublishedGovernedFactSource().supported_filing_years()
    return max(year for year in support.years if year <= today_madrid().year - 2)


def _rent_withholding_revision(filing_year: int) -> str:
    """Return the Modelo 115 first-quarter edition the canonical temporal selector admits."""
    return published_selected_revision_id("115", filing_year=filing_year, period="1T")


def _verify_rent_withholding_quarter(filing_year: int) -> str:
    """Create, calculate and verify one Modelo 115 first quarter; return the plazo close the calculation served."""
    create_modelo_work_unit_via_cli(
        modelo="115", filing_year=filing_year, period="1T", revision=_rent_withholding_revision(filing_year)
    )
    capture_m115_invoice_withholding(filing_year=filing_year)
    calculated = _calculate_and_verify("115", filing_year, "1T")
    served_close = unwrap_schema_envelope(calculated.output)["deadline"]["closes_on"]
    assert isinstance(served_close, str), calculated.output
    return served_close


def _assert_served_twelve_month_recargo(filed: Result, *, calculated_close: str) -> None:
    """The late filing serves its plazo close, days overdue and the Art. 27.2 over-twelve-months rate."""
    deadline = unwrap_schema_envelope(filed.output)["deadline"]
    assert deadline["closes_on"] == calculated_close
    assert deadline["days_overdue"] == (today_madrid() - date.fromisoformat(calculated_close)).days
    assert deadline["days_remaining"] is None
    preview = deadline["conditional_recargo_preview"]
    statutory_pct = legal_text_match("ley-58-2003:art-27.2", r"el recargo sera del (\d+) por ciento").group(1)
    assert Decimal(preview["surcharge_pct"]) == Decimal(statutory_pct)
    assert preview["interest_applies"] is True
    assert preview["legal_ref"] == "ley-58-2003:art-27.2"
    assert preview["assessment_status"] == "unassessed"
    _assert_late_filing_notice_repeats(filed, days_overdue=deadline["days_overdue"], pct=preview["surcharge_pct"])


def _assert_late_filing_notice_repeats(filed: Result, *, days_overdue: object, pct: object) -> None:
    """The extemporánea notice carries the same served days overdue and recargo rate as the result."""
    notice = next(
        item for item in unwrap_envelope_notices(filed.output) if item["code"] == "modelo.work.file.extemporanea"
    )
    assert notice["context"]["days_overdue"] == str(days_overdue)
    assert notice["context"]["conditional_recargo_preview_pct"] == pct


def _assert_filed_period_is_not_refiled(filing_year: int) -> None:
    """The period is now presentado, so filing it again is refused before any write."""
    status = _work("status", "115", filing_year, "1T")
    assert status.exit_code == 0, status.output
    assert unwrap_schema_envelope(status.output)["state"] == "presentado"
    refiled = _work("file", "115", filing_year, "1T")
    assert refiled.exit_code != 0
    refusal = require_error_document(refiled.output)["error"]
    assert refusal["code"] == "REFUSED_MODELO_CALCULATION_REVISION_SELECTOR_STATE"
    assert refusal["context"]["state"] == "presentado"
    assert refusal["context"]["effect"] == "none"


@pytest.mark.parametrize(
    "rent_answer",
    (
        pytest.param({}, id="unanswered"),
        pytest.param({"withholding.pays_rent_with_retencion": "true"}, id="declared-yes"),
    ),
)
def test_work_file_records_a_late_unfiled_period_with_its_served_recargo(
    seed_profile: ProfileSeeder, rent_answer: dict[str, str]
) -> None:
    """A period past its plazo is still owed, so `work file` records it locally as extemporánea.

    Ley 58/2003 art. 27.1 makes the recargo an accessory charge on a return
    presented "fuera de plazo": the late return remains owed. The filing serves
    its lateness on the day it is recorded -- the effective plazo close, the
    days overdue, and the Art. 27.2 rate preview -- and the rate is the one the
    provision prints for a presentation more than twelve months late. An
    unanswered rent-withholding question rules nothing out: the work unit was
    created and verified on the taxpayer's own figures.
    """
    filing_year = _filed_more_than_twelve_months_late_year()
    seed_profile(
        label="operator",
        facts=persona_fact_strings(
            {"withholding.pays_professionals_with_retencion": "true", **rent_answer},
            without=() if rent_answer else ("withholding.pays_rent_with_retencion",),
        ),
    )
    calculated_close = _verify_rent_withholding_quarter(filing_year)

    filed = _work("file", "115", filing_year, "1T")

    assert filed.exit_code == 0, filed.output
    payload = unwrap_schema_envelope(filed.output)
    filed_as = (payload["filing_timeliness"], payload["declaration_kind"], payload["aeat_accepted"])
    assert filed_as == ("extemporanea", "original", False)
    _assert_served_twelve_month_recargo(filed, calculated_close=calculated_close)
    _assert_filed_period_is_not_refiled(filing_year)


def test_work_file_refuses_a_modelo_the_profile_rules_out(seed_profile: ProfileSeeder) -> None:
    """A declared "no" to paying rent with retención leaves no Modelo 115 obligation, so no work to file exists."""
    filing_year = _filed_more_than_twelve_months_late_year()
    seed_profile(label="operator", facts=operator_profile_facts())
    assert operator_profile_facts()["withholding.pays_rent_with_retencion"] == "false"

    created = _work("create", "115", filing_year, "1T", "--revision", _rent_withholding_revision(filing_year))

    assert created.exit_code != 0
    assert "Traceback" not in created.output
    error = require_error_document(created.output)["error"]
    assert error["context"]["refusal_code"] == "REFUSED_MODELO_WORK_CREATE_APPLICABILITY", error
    assert error["context"]["effect"] == "none"
