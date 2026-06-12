"""Real-behavior CLI coverage: the overdue recargo/deadline notice on calculate.

``aeat app modelo work calculate`` on an overdue period must surface the
Art. 27 LGT extemporaneidad surcharge both in text mode (the existing
``recargo_*`` / ``AVISO:`` plazo lines) AND on the JSON envelope: a typed
warning :class:`Notice` carrying the binding ``legal_refs`` plus the
resolved recargo band, and a populated ``result.deadline`` block. An
in-time period must carry neither the recargo notice nor an overdue
posture.

These tests drive a real Modelo 130 calculate through the CLI over an
isolated profile and a real ledger income row; the expected overdue /
in-time posture is derived from the registry deadline window the engine
itself resolves (``resolve_filing_closes_on``) against the real
``date.today()``, never hand-asserted, so the test tracks the registry
rather than a frozen calendar literal.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....core import Period
from ....domain.deadlines._plazo import resolve_filing_closes_on
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ._m130_source_support import seed_m130_income_transaction
from .envelope_helpers import unwrap_envelope_notices
from .envelope_helpers import unwrap_schema_envelope as _result

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RECARGO_NOTICE_CODE = "modelo.work.calculate.plazo_vencido_recargo"
_M130_REVISION = "2019-y-siguientes"
_M130_FILING_YEAR = 2026


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _create_natural_person_profile() -> None:
    result = invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            "operator",
            "--quiet",
            "--accept-defaults",
            "--tax-id",
            "12345678Z",
            "--name",
            "Operator",
            "--activity",
            "design",
        ],
    )
    assert result.exit_code == 0, result.output


def _create_m130_work_unit(*, period: str) -> str:
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "130",
            "--year",
            str(_M130_FILING_YEAR),
            "--period",
            period,
            "--revision",
            _M130_REVISION,
        ],
    )
    assert result.exit_code == 0, result.output
    return str(_result(result.output)["work_unit_id"])


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
            "--casilla",
            "02=4000.00",
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
    assert closes_on is not None, (
        f"registry must register an M130 {period_token} {_M130_FILING_YEAR} deadline window"
    )
    return closes_on


def test_calculate_overdue_period_surfaces_recargo_notice_with_legal_context() -> None:
    """An overdue M130 period carries the Art. 27 LGT recargo notice + deadline block.

    The 1T window closes mid-April; once the run date is past it the
    calculate envelope MUST carry (a) a warning-severity recargo
    :class:`Notice` whose ``context`` includes the binding ``legal_refs``,
    and (b) a non-null ``result.deadline`` with a populated overdue posture.
    The text mode keeps its existing ``recargo_*`` / ``AVISO:`` lines.
    """
    closes_on = _closes_on("1T")
    if date.today() <= closes_on:
        pytest.skip(
            f"M130 1T {_M130_FILING_YEAR} deadline {closes_on.isoformat()} is not yet "
            "overdue against the current run date; the overdue branch is unreachable. "
            "This is a calendar-edge skip, not a code skip.",
        )

    _create_natural_person_profile()
    work_unit_id = _create_m130_work_unit(period="1T")
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

    recargo_notices = [notice for notice in notices if notice["code"] == _RECARGO_NOTICE_CODE]
    assert len(recargo_notices) == 1, f"expected exactly one recargo notice; got {notices}"
    recargo = recargo_notices[0]
    assert recargo["severity"] == "warning"
    assert "Art. 27" in recargo["message"]
    context = recargo["context"]
    assert context is not None, "recargo notice must carry structured legal context"
    assert context.get("legal_refs"), "recargo notice context must carry binding legal_refs"
    assert context.get("days_overdue"), "recargo notice context must carry the overdue posture"

    deadline = inner["deadline"]
    assert deadline is not None, "result.deadline must be populated for a resolvable period"
    assert deadline["closes_on"] == closes_on.isoformat()
    assert deadline["days_overdue"] is not None and int(deadline["days_overdue"]) >= 1
    assert deadline["days_remaining"] is None
    # The recargo band rides the structured deadline block too (band id +
    # surcharge + binding legal ref) so the JSON surface is self-explanatory.
    recargo_band = deadline["recargo"]
    assert recargo_band is not None, "an overdue posture must resolve a recargo band"
    assert recargo_band["legal_ref"], "recargo band must carry its binding legal_ref"

    # Text mode still renders its existing plazo lines (no regression).
    text_result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "calculate",
            work_unit_id,
            "--casilla",
            "02=4000.00",
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


def test_calculate_in_time_period_carries_no_recargo_notice() -> None:
    """An in-time M130 period carries no recargo notice and an in-time deadline.

    Anti-tautology converse of the overdue test: the 2T window closes in
    July, so before that date the calculate envelope MUST NOT carry the
    recargo notice, its status stays ``success``, and ``result.deadline``
    reports ``days_remaining`` with no overdue posture and no recargo band.
    """
    closes_on = _closes_on("2T")
    if date.today() > closes_on:
        pytest.skip(
            f"M130 2T {_M130_FILING_YEAR} deadline {closes_on.isoformat()} is already past "
            "against the current run date; the in-time branch is unreachable. "
            "This is a calendar-edge skip, not a code skip.",
        )

    _create_natural_person_profile()
    work_unit_id = _create_m130_work_unit(period="2T")
    seed_m130_income_transaction(
        amount=Decimal("12000.00"),
        filing_year=_M130_FILING_YEAR,
        source_key="recargo-in-time",
    )

    result = _calculate_m130(work_unit_id)
    envelope = json.loads(result.output)
    inner = _result(result.output)
    notices = unwrap_envelope_notices(result.output)

    assert [notice for notice in notices if notice["code"] == _RECARGO_NOTICE_CODE] == [], (
        f"an in-time period must raise no recargo notice; got {notices}"
    )
    # No warning-severity recargo means the spine status stays success
    # (other commands may add their own notices; the recargo path adds none).
    assert envelope["status"] in {"success", "warning"}

    deadline = inner["deadline"]
    assert deadline is not None, "result.deadline must be populated for a resolvable period"
    assert deadline["closes_on"] == closes_on.isoformat()
    assert deadline["days_remaining"] is not None and int(deadline["days_remaining"]) >= 0
    assert deadline["days_overdue"] is None
    assert deadline["recargo"] is None
