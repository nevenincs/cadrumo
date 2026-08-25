"""Application-owned continuations for observed modelo work-unit states."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core import NoRecoveryOutcome, Period
from ....core.i18n import extract_placeholders, tr
from ....domain.modelos import WorkUnit, WorkUnitState, derive_work_unit_id
from .._work_lifecycle import (
    lifecycle_continuation_for_work_history,
    lifecycle_continuation_for_work_list,
    lifecycle_continuation_for_work_status,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "5aa00000-0000-4000-8000-0000000000aa"
_OBSERVED_AT = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
_LOCALE_KEYS = (
    "cli.app.modelo.work.list_no_active_work_summary",
    "cli.app.modelo.work.list_selection_required_summary",
    "cli.app.modelo.work.list_single_status_summary",
    "cli.app.modelo.work.history_next_action_summary",
    "cli.app.modelo.work.status_calculate_summary",
    "cli.app.modelo.work.status_discarded_summary",
)
_LOCALES = ("en", "es", "ca", "hu")


def _work_unit(*, state: WorkUnitState = WorkUnitState.BORRADOR, period_code: str = "1T") -> WorkUnit:
    period = Period.from_year_and_code(2026, period_code)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="130",
            filing_year=2026,
            period=period,
            revision_id="2019-y-siguientes",
        ),
        bucket_id=_BUCKET_ID,
        name=f"130-2026-{period_code}",
        modelo="130",
        filing_year=2026,
        period=period,
        revision_id="2019-y-siguientes",
        state=state,
        discarded_at=None if state is WorkUnitState.BORRADOR else _OBSERVED_AT,
        discarded_by=None if state is WorkUnitState.BORRADOR else "operator-1",
        created_at=_OBSERVED_AT,
        updated_at=_OBSERVED_AT,
    )


def test_work_list_continuations_bind_a_status_action_only_for_one_observed_unit() -> None:
    """List cardinality, not CLI prose, determines whether status has one target."""
    single = _work_unit()

    no_units = lifecycle_continuation_for_work_list(())
    multiple_units = lifecycle_continuation_for_work_list((single, _work_unit(period_code="2T")))
    one_unit = lifecycle_continuation_for_work_list((single,))

    for continuation, count in ((no_units, 0), (multiple_units, 2)):
        assert continuation.notice_code == "modelo.work.list.selection_required"
        assert continuation.action is None
        assert continuation.argument_bindings == ()
        assert continuation.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
        assert continuation.evidence.values == {"work_unit_count": count}

    assert one_unit.notice_code == "modelo.work.list.next_action"
    assert one_unit.action is not None
    assert one_unit.action.action_id == "operator.modelo.work.status"
    assert one_unit.no_recovery_outcome is None
    assert one_unit.evidence.values == {"work_unit_count": 1, "work_unit_id": single.work_unit_id}
    assert one_unit.argument_bindings[0].value == single.work_unit_id
    assert one_unit.argument_bindings[0].source_key == "work_unit_id"


def test_work_status_continuation_is_exhaustive_over_the_real_work_unit_state_enum() -> None:
    """Every current state is explicit; a future state makes this test fail closed."""
    expected = {
        WorkUnitState.BORRADOR: ("operator.modelo.work.calculate", None, "modelo.work.status.next_action"),
        WorkUnitState.DESCARTADO: (None, NoRecoveryOutcome.TERMINAL, "modelo.work.status.action_unavailable"),
    }
    assert set(expected) == set(WorkUnitState)

    for state, (action_id, outcome, notice_code) in expected.items():
        unit = _work_unit(state=state)
        continuation = lifecycle_continuation_for_work_status(unit)

        assert continuation.notice_code == notice_code
        assert continuation.evidence.values == {
            "work_unit_id": unit.work_unit_id,
            "work_unit_state": state.value,
        }
        assert continuation.no_recovery_outcome is outcome
        assert (None if continuation.action is None else continuation.action.action_id) == action_id
        if action_id is None:
            assert continuation.argument_bindings == ()
        else:
            assert continuation.argument_bindings[0].value == unit.work_unit_id
            assert continuation.argument_bindings[0].source_key == "work_unit_id"


def test_work_history_continuation_resolves_state_inspection_from_the_observed_unit() -> None:
    """History owns a state-inspection continuation, not a CLI-made status action."""
    work_unit = _work_unit(state=WorkUnitState.DESCARTADO)

    continuation = lifecycle_continuation_for_work_history(work_unit)

    assert continuation.notice_code == "modelo.work.history.next_action"
    assert continuation.summary_locale_key == "cli.app.modelo.work.history_next_action_summary"
    assert continuation.evidence.values == {"work_unit_id": work_unit.work_unit_id}
    assert continuation.no_recovery_outcome is None
    assert continuation.action is not None
    assert continuation.action.action_id == "operator.modelo.work.status"
    assert continuation.argument_bindings[0].value == work_unit.work_unit_id
    assert continuation.argument_bindings[0].source_key == "work_unit_id"


def test_lifecycle_summary_keys_load_in_every_supported_locale_with_placeholder_parity() -> None:
    """The stable keys render from every catalogue without hidden interpolation facts."""
    for key in _LOCALE_KEYS:
        rendered_by_locale = {locale: tr(key, locale=locale) for locale in _LOCALES}
        assert all(message for message in rendered_by_locale.values())
        assert {extract_placeholders(message) for message in rendered_by_locale.values()} == {frozenset()}
        assert len(set(rendered_by_locale.values())) == len(_LOCALES)
