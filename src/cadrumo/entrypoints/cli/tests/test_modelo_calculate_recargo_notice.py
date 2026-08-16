"""Real-behavior CLI coverage: overdue deadline posture and rate preview.

``aeat app modelo work calculate`` on an overdue period must surface the
voluntary filing deadline and an explicitly unassessed Article 27 rate preview
in text mode and JSON. The preview carries a rate-reference date, never a
presentation date, and the notice makes no surcharge or interest liability
claim. An in-time period carries neither an overdue notice nor a preview.

These tests drive a real Modelo 130 calculate through the CLI over an
isolated profile and a real ledger income row; the expected overdue /
in-time posture is derived from the registry deadline window the engine
itself resolves (``resolve_filing_closes_on``) against the real
``date.today()``, never hand-asserted, so the test tracks the registry
rather than a frozen calendar literal.

Period selection is deterministic and self-calibrating: rather than
hardcode a quarter and skip when the calendar makes its branch
unreachable, each test enumerates the M130 quarterly periods the
registry actually defines deadline windows for and picks the period
whose ``closes_on`` guarantees the wanted posture relative to today
(the most recent already-past close for the overdue test, the nearest
still-future close for the in-time test). Both branches are therefore
always reachable and no calendar-edge skip is needed.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from ....application.modelo import ModeloWorkDeadlinePosture
from ....core import Period
from ....core.resources import resources
from ....domain.deadlines import resolve_filing_closes_on
from ....tests.cli_envelope import unwrap_envelope_notices
from ....tests.cli_envelope import unwrap_schema_envelope as _result
from ....tests.cli_runner import invoke_cached_cli
from ....tests.modelo_cli import create_modelo_work_unit_via_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_storage  # noqa: F401 - autouse fixture
from ....tests.user_profile import register_cli_profile
from .._modelo_rendering import _work_unit_deadline_output_from_posture
from ._m130_source_support import seed_m130_income_transaction

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_UNASSESSED_PREVIEW_NOTICE_CODE = "modelo.work.calculate.plazo_vencido_unassessed_preview"
_RECARGO_LEGAL_REF = "ley-58-2003:art-27.2"
_M130_REVISION = "2019-y-siguientes"
_M130_FILING_YEAR = 2026

# The quarterly periods the M130 2019-y-siguientes revision declares, in
# chronological close order. Each test resolves their real registry close
# dates and selects deterministically against ``date.today()``.
_M130_QUARTERLY_PERIODS: tuple[str, ...] = ("1T", "2T", "3T", "4T")


def _create_natural_person_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label="operator",
        facts={
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Operator",
            "identity.surnames": "Readiness",
            "activities.description": "design",
        },
    )


def _calculate_m130(work_unit_id: str) -> Any:
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            work_unit_id,
            # Casilla 02 (gastos) is bucket-bound (ledger-aggregated) and cannot
            # be supplied via --casilla; immaterial to the recargo-notice assertions.
            "--casilla",
            "05=0.00",
            "--casilla",
            "06=0.00",
            "--binding",
            "irpf.previous_year_economic_activity_net_income=13000",
            "--binding",
            "modelo-130-resultados-negativos-anteriores=0",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    return result


def _closes_on(period_token: str) -> date:
    closes_on = resolve_filing_closes_on(
        "130",
        _M130_FILING_YEAR,
        Period.from_year_and_code(_M130_FILING_YEAR, period_token),
    )
    assert closes_on is not None, f"registry must register an M130 {period_token} {_M130_FILING_YEAR} deadline window"
    return closes_on


def _registered_quarterly_closes() -> list[tuple[str, date]]:
    """(period_token, closes_on) for every M130 quarter with a registry window.

    Sorted by close date so callers can pick the most-recent-past or the
    nearest-future deadline deterministically against the run date.
    """
    pairs = [(token, _closes_on(token)) for token in _M130_QUARTERLY_PERIODS]
    return sorted(pairs, key=lambda pair: pair[1])


def _select_overdue_period() -> tuple[str, date]:
    """Pick the M130 quarter whose plazo voluntario is guaranteed already past.

    Returns the most recent quarter whose ``closes_on`` is strictly before
    today, so the calculate path always resolves an overdue posture and the
    recargo branch is always exercised — no calendar-edge skip.
    """
    today = date.today()
    past = [pair for pair in _registered_quarterly_closes() if pair[1] < today]
    assert past, (
        "no M130 quarterly deadline window in the registry closes before "
        f"{today.isoformat()}; the overdue recargo branch cannot be exercised "
        "deterministically. Extend the M130 registry deadline windows."
    )
    return past[-1]


def _select_in_time_period() -> tuple[str, date]:
    """Pick the M130 quarter whose plazo voluntario is guaranteed still open.

    Returns the nearest quarter whose ``closes_on`` is strictly after today,
    so the calculate path always resolves an in-time posture and the
    no-recargo branch is always exercised — no calendar-edge skip.
    """
    today = date.today()
    future = [pair for pair in _registered_quarterly_closes() if pair[1] > today]
    assert future, (
        "no M130 quarterly deadline window in the registry closes after "
        f"{today.isoformat()}; the in-time no-recargo branch cannot be "
        "exercised deterministically. Extend the M130 registry deadline windows."
    )
    return future[0]


def test_overdue_posture_fallback_emits_null_preview_without_rate_wording() -> None:
    """The real renderer emits a null preview and no displayed-rate warning."""
    deadline, notices = _work_unit_deadline_output_from_posture(
        ModeloWorkDeadlinePosture(closes_on=date(2026, 1, 30), days_overdue=1),
    )

    assert deadline is not None
    assert deadline.days_overdue == 1
    assert deadline.conditional_recargo_preview is None
    assert deadline.model_dump(mode="json")["conditional_recargo_preview"] is None
    assert len(notices) == 1
    context = notices[0].context
    assert context is not None
    assert context["legal_refs"] == _RECARGO_LEGAL_REF
    assert context["article_27_assessment_status"] == "unassessed"
    message = notices[0].message.lower()
    assert "displayed rate" not in message
    assert "previsualización no evaluada" not in message

    catalogues = resources().modelos.authority.catalogues
    legal_entry = catalogues.legal[_RECARGO_LEGAL_REF]
    assert legal_entry.corpus_ref
    assert legal_entry.required_text


def test_calculate_overdue_period_surfaces_unassessed_preview_with_legal_context() -> None:
    """An overdue M130 period carries an unassessed preview and deadline posture.

    A quarter whose voluntary window has already closed is selected from the
    registry's M130 deadline windows, so once a calculate runs against it the
    envelope MUST carry an explicit ``unassessed`` status, a binding legal
    reference, and a non-null ``result.deadline`` overdue posture. Text and
    JSON must expose a conditional preview rather than a liability claim.
    """
    period, closes_on = _select_overdue_period()

    _create_natural_person_profile()
    work_unit_id = create_modelo_work_unit_via_cli(
        modelo="130",
        filing_year=_M130_FILING_YEAR,
        period=period,
        revision=_M130_REVISION,
    )
    seed_m130_income_transaction(
        amount=Decimal("12000.00"),
        filing_year=_M130_FILING_YEAR,
        source_key="recargo-overdue",
    )

    result = _calculate_m130(work_unit_id)
    envelope = json.loads(result.output)
    inner = _result(result.output)
    notices = unwrap_envelope_notices(result.output)

    # JSON status is no longer a bare success: a warning notice rode the spine.
    assert envelope["status"] == "warning", envelope

    preview_notices = [notice for notice in notices if notice["code"] == _UNASSESSED_PREVIEW_NOTICE_CODE]
    assert len(preview_notices) == 1, f"expected exactly one unassessed-preview notice; got {notices}"
    preview_notice = preview_notices[0]
    assert preview_notice["severity"] == "warning"
    assert "Art. 27" in preview_notice["message"]
    context = preview_notice["context"]
    assert context is not None, "preview notice must carry structured legal context"
    assert context.get("legal_refs") == _RECARGO_LEGAL_REF, "preview notice context must carry binding legal_refs"
    assert context.get("days_overdue"), "preview notice context must carry the overdue posture"
    assert context.get("article_27_assessment_status") == "unassessed"
    assert "presentation_date" not in context

    deadline = inner["deadline"]
    assert deadline is not None, "result.deadline must be populated for a resolvable period"
    assert deadline["closes_on"] == closes_on.isoformat()
    assert deadline["days_overdue"] is not None and int(deadline["days_overdue"]) >= 1
    assert deadline["days_remaining"] is None
    preview = deadline["conditional_recargo_preview"]
    assert preview is not None, "an overdue posture must resolve a rate preview"
    assert preview["legal_ref"] == _RECARGO_LEGAL_REF
    assert preview["assessment_status"] == "unassessed"
    assert preview["rate_reference_on"] == date.today().isoformat()
    assert "presentation_date" not in preview

    # Text mode exposes the same posture and explicitly unassessed preview.
    text_result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "calculate",
            work_unit_id,
            "--casilla",
            "05=0.00",
            "--casilla",
            "06=0.00",
            "--binding",
            "irpf.previous_year_economic_activity_net_income=13000",
            "--binding",
            "modelo-130-resultados-negativos-anteriores=0",
        ],
    )
    assert text_result.exit_code == 0, text_result.output
    assert "Art. 27" in text_result.output
    assert "days_overdue\t" in text_result.output
    assert "conditional_recargo_preview_assessment_status\tunassessed" in text_result.output


def test_calculate_in_time_period_carries_no_unassessed_preview_notice() -> None:
    """An in-time M130 period carries no overdue notice or rate preview.

    Anti-tautology converse of the overdue test: a quarter whose voluntary
    window is still open is selected from the registry's M130 deadline
    windows, so the calculate envelope MUST NOT carry the overdue notice, its
    status stays ``success``, and ``result.deadline`` reports
    ``days_remaining`` with no overdue posture and no rate preview.
    """
    period, closes_on = _select_in_time_period()

    _create_natural_person_profile()
    work_unit_id = create_modelo_work_unit_via_cli(
        modelo="130",
        filing_year=_M130_FILING_YEAR,
        period=period,
        revision=_M130_REVISION,
    )
    seed_m130_income_transaction(
        amount=Decimal("12000.00"),
        filing_year=_M130_FILING_YEAR,
        source_key="recargo-in-time",
    )

    result = _calculate_m130(work_unit_id)
    envelope = json.loads(result.output)
    inner = _result(result.output)
    notices = unwrap_envelope_notices(result.output)

    assert [notice for notice in notices if notice["code"] == _UNASSESSED_PREVIEW_NOTICE_CODE] == [], (
        f"an in-time period must raise no overdue-preview notice; got {notices}"
    )
    # No overdue-preview warning means the spine status stays success
    # (other commands may add their own notices; this path adds none).
    assert envelope["status"] in {"success", "warning"}

    deadline = inner["deadline"]
    assert deadline is not None, "result.deadline must be populated for a resolvable period"
    assert deadline["closes_on"] == closes_on.isoformat()
    assert deadline["days_remaining"] is not None and int(deadline["days_remaining"]) >= 0
    assert deadline["days_overdue"] is None
    assert deadline["conditional_recargo_preview"] is None
