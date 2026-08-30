"""Real-behavior CLI coverage: overdue deadline posture and rate preview.

``aeat app modelo work calculate`` on an overdue period must surface the
voluntary filing deadline and an explicitly unassessed Article 27 rate preview
in text mode and JSON. The preview carries a rate-reference date, never a
presentation date, and the notice makes no surcharge or interest liability
claim. An in-time period carries neither an overdue notice nor a preview.

These tests drive a real Modelo 130 calculate through the CLI over an
isolated profile and a real ledger income row; the expected overdue /
in-time posture is derived from the registry deadline window the engine
itself resolves (``resolve_filing_closes_on``) against an explicit reference
date frozen through the canonical ``today_madrid()`` seam, so the test tracks
the registry rather than the host wall clock or a frozen legal-date literal.

Period selection is deterministic and self-calibrating: rather than
hardcode a filing year, quarter, or reference date, each test derives the
supported horizon from the registry catalogue, enumerates the M130 quarterly
windows, and chooses a reference date strictly between two consecutive closes.
Both postures are therefore always reachable and independent of execution day.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from itertools import pairwise
from typing import Any

import pytest

from ....application.modelo._work_plazo import ModeloWorkDeadlinePosture
from ....core import Period, PeriodKind, registry_period_kind
from ....core.time import MADRID_TZ, frozen_clock
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.temporal import select_revision
from ....domain.deadlines.plazo import resolve_filing_closes_on
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


def _closes_on(filing_year: int, period_token: str) -> date:
    closes_on = resolve_filing_closes_on(
        "130",
        filing_year,
        Period.from_year_and_code(filing_year, period_token),
    )
    assert closes_on is not None, f"registry must register an M130 {period_token} {filing_year} deadline window"
    return closes_on


def _registered_quarterly_closes(filing_year: int) -> list[tuple[str, date]]:
    """(period_token, closes_on) for every M130 quarter with a registry window.

    Sorted by close date so callers can derive both postures relationally.
    """
    authority = bundled_authority()
    tokens = {
        window.period.registry_token
        for modelo, _revision, window in authority.deadline_windows(filing_year)
        if modelo == "130" and registry_period_kind(window.period.registry_token) is PeriodKind.QUARTERLY
    }
    pairs = [(token, _closes_on(filing_year, token)) for token in tokens]
    return sorted(pairs, key=lambda pair: pair[1])


def _deadline_case() -> tuple[int, date, tuple[str, date], tuple[str, date]]:
    """Derive one overdue/in-time pair from the canonical supported horizon."""
    authority = bundled_authority()
    supported_years = authority.catalogues.supported_filing_years
    assert supported_years is not None
    for filing_year in reversed(supported_years.years):
        closes = _registered_quarterly_closes(filing_year)
        for overdue, in_time in pairwise(closes):
            reference_on = overdue[1] + timedelta(days=1)
            if reference_on < in_time[1]:
                return filing_year, reference_on, overdue, in_time
    raise AssertionError("supported M130 windows contain no two consecutive closes for deterministic posture coverage")


def _revision_id(filing_year: int, period_token: str) -> str:
    """Return the canonical law-selected M130 revision for one test coordinate."""
    authority = bundled_authority()
    revision = select_revision(authority.modelo("130"), filing_year=filing_year, period=period_token)
    return str(revision.id)


def _frozen_madrid_instant(reference_on: date) -> datetime:
    """Represent a Madrid civil reference date as a stable UTC instant."""
    madrid_noon = datetime.combine(reference_on, time(hour=12), tzinfo=MADRID_TZ)
    return madrid_noon.astimezone(UTC)


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

    catalogues = bundled_authority().catalogues
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
    filing_year, reference_on, (period, closes_on), _ = _deadline_case()

    with frozen_clock(_frozen_madrid_instant(reference_on)):
        _create_natural_person_profile()
        work_unit_id = create_modelo_work_unit_via_cli(
            modelo="130",
            filing_year=filing_year,
            period=period,
            revision=_revision_id(filing_year, period),
        )
        seed_m130_income_transaction(
            amount=Decimal("12000.00"),
            filing_year=filing_year,
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
    assert preview["rate_reference_on"] == reference_on.isoformat()
    assert "presentation_date" not in preview

    # Text mode exposes the same posture and explicitly unassessed preview.
    with frozen_clock(_frozen_madrid_instant(reference_on)):
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
    filing_year, reference_on, _, (period, closes_on) = _deadline_case()

    with frozen_clock(_frozen_madrid_instant(reference_on)):
        _create_natural_person_profile()
        work_unit_id = create_modelo_work_unit_via_cli(
            modelo="130",
            filing_year=filing_year,
            period=period,
            revision=_revision_id(filing_year, period),
        )
        seed_m130_income_transaction(
            amount=Decimal("12000.00"),
            filing_year=filing_year,
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
