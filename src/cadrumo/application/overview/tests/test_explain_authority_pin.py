"""``overview explain`` reuses the caller's pinned authority for every deadline lookup."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import ClassVar, NoReturn, override

import pytest

from ....domain.calculations.registry import authority as authority_module
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition
from ....domain.deadlines.engine import DeadlineEngine
from ....domain.deadlines.errors import NoDeadlineWindowsError
from ....domain.deadlines.models import TaxpayerProfile
from .. import explain as explain_module
from ..explain import build_overview_explain, explain_out_of_plazo_warning
from .calendar_test_support import profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "100"
_YEAR = newest_authored_edition(_MODELO)
_LATE_TODAY = date(_YEAR + 8, 1, 15)


@pytest.fixture(scope="module")
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _refuse_second_authority() -> None:
    raise AssertionError("a second authority was opened although the caller pinned one")


@pytest.fixture
def no_second_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any attempt to open the default authority from the explain path."""
    monkeypatch.setattr(authority_module, "bundled_indexed_authority", _refuse_second_authority)
    monkeypatch.setattr(explain_module, "bundled_indexed_authority", _refuse_second_authority)


class _RecordingEngine(DeadlineEngine):
    """The real engine, recording the authority each instance was built with."""

    built_with: ClassVar[list[PinnedAuthorityOperation | None]] = []

    def __init__(self, *, authority: PinnedAuthorityOperation | None = None) -> None:
        super().__init__(authority=authority)
        type(self).built_with.append(authority)


def test_explain_threads_the_callers_operation_into_every_deadline_engine(
    operation: PinnedAuthorityOperation,
    no_second_authority: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _RecordingEngine.built_with = []
    monkeypatch.setattr(explain_module, "DeadlineEngine", _RecordingEngine)

    result = build_overview_explain(
        profile(),
        modelo=_MODELO,
        year=_YEAR,
        today=_LATE_TODAY,
        operation=operation,
    )

    assert result.scheduling_rationale is not None
    assert result.out_of_plazo_warning is not None
    assert len(_RecordingEngine.built_with) == 2
    assert all(built is operation for built in _RecordingEngine.built_with)


def test_out_of_plazo_warning_uses_only_the_supplied_operation(
    operation: PinnedAuthorityOperation,
    no_second_authority: None,
) -> None:
    warning = explain_out_of_plazo_warning(
        profile(),
        modelo=_MODELO,
        year=_YEAR,
        today=_LATE_TODAY,
        operation=operation,
    )

    assert warning is not None
    assert warning.startswith("out_of_plazo:")


def test_injected_engine_still_supplies_the_scheduling_rationale(
    operation: PinnedAuthorityOperation,
    no_second_authority: None,
) -> None:
    class _FixedEngine:
        def explain(self, profile: TaxpayerProfile, modelo: str, *, year: int | None = None) -> str:
            return f"fixed:{modelo}:{year}"

    result = build_overview_explain(
        profile(),
        modelo=_MODELO,
        year=_YEAR,
        today=_LATE_TODAY,
        operation=operation,
        engine=_FixedEngine(),
    )

    assert result.scheduling_rationale == f"fixed:{_MODELO}:{_YEAR}"


def test_omitted_operation_is_opened_once_for_the_whole_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[object] = []
    real = bundled_indexed_authority

    def counting() -> object:
        opened.append(object())
        return real()

    monkeypatch.setattr(explain_module, "bundled_indexed_authority", counting)
    monkeypatch.setattr(authority_module, "bundled_indexed_authority", _refuse_second_authority)

    result = build_overview_explain(profile(), modelo=_MODELO, year=_YEAR, today=_LATE_TODAY)

    assert result.out_of_plazo_warning is not None
    assert len(opened) == 1


def test_windowless_year_keeps_the_narrow_catch(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Windowless(DeadlineEngine):
        @override
        def deadline_windows(self, year: int) -> NoReturn:
            raise NoDeadlineWindowsError(
                translated_message="application.overview.calendar.shift.modelo_exception",
                context={"filing_year": year},
            )

    monkeypatch.setattr(explain_module, "DeadlineEngine", _Windowless)

    warning = explain_out_of_plazo_warning(
        profile(), modelo=_MODELO, year=_YEAR, today=_LATE_TODAY, operation=operation
    )

    assert warning is None
