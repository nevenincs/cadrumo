"""Unit tests for :mod:`aeat.filing.reconciliation._narrative`.

Asserts that every :class:`FilingDivergenceKind` variant produces a
non-empty trilingual narrative for the per-delta builder, and that
every :class:`ReconciliationStatus` member produces a non-empty
trilingual narrative for the report-level builder.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._kind import FilingDivergenceKind
from ._narrative import compose_delta_narrative, compose_report_narrative
from ._schema import ReconciliationStatus

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


_REQUIRED_LANGUAGES: tuple[str, ...] = ("es", "en", "hu")


def _as_dict(narrative: object) -> dict[str, str]:
    """Coerce a :class:`Translatable` :class:`TypedDict` to a runtime ``dict``.

    The TypedDict shape is too rigid for dynamic-key iteration in tests
    that walk the language set; pydantic-style cast through ``dict``
    preserves the runtime semantics without confusing the type checker.
    """
    from typing import cast

    return cast(dict[str, str], narrative)


@pytest.mark.parametrize("kind", list(FilingDivergenceKind))
def test_compose_delta_narrative_covers_every_variant(kind: FilingDivergenceKind) -> None:
    narrative = _as_dict(
        compose_delta_narrative(
            casilla_id="46",
            kind=kind,
            local_value="1234.56",
            remote_value="1235.56",
            delta=Decimal("-1.00"),
        )
    )
    for lang in _REQUIRED_LANGUAGES:
        assert lang in narrative
        assert narrative[lang]


@pytest.mark.parametrize("status", list(ReconciliationStatus))
def test_compose_report_narrative_covers_every_status(status: ReconciliationStatus) -> None:
    narrative = _as_dict(
        compose_report_narrative(
            status=status,
            modelo="303",
            period="2026-1T",
            delta_count=2,
        )
    )
    for lang in _REQUIRED_LANGUAGES:
        assert lang in narrative
        assert narrative[lang]


def test_delta_narrative_embeds_casilla_for_casilla_scoped_kinds() -> None:
    narrative = _as_dict(
        compose_delta_narrative(
            casilla_id="46",
            kind=FilingDivergenceKind.CASILLA_VALUE_MISMATCH,
            local_value="1234.56",
            remote_value="1235.56",
            delta=Decimal("-1.00"),
        )
    )
    for lang in _REQUIRED_LANGUAGES:
        assert "46" in narrative[lang]


def test_delta_narrative_handles_missing_local_value() -> None:
    narrative = compose_delta_narrative(
        casilla_id="07",
        kind=FilingDivergenceKind.CASILLA_MISSING_LOCAL,
        local_value=None,
        remote_value="2500.00",
        delta=None,
    )
    assert narrative["es"]
    assert "2500.00" in narrative["en"]


def test_delta_narrative_handles_missing_remote_value() -> None:
    narrative = compose_delta_narrative(
        casilla_id="07",
        kind=FilingDivergenceKind.CASILLA_EXTRA_LOCAL,
        local_value="500.00",
        remote_value=None,
        delta=None,
    )
    assert "500.00" in narrative["en"]


def test_report_narrative_embeds_modelo_and_period() -> None:
    narrative = _as_dict(
        compose_report_narrative(
            status=ReconciliationStatus.DIVERGENT,
            modelo="130",
            period="2026-2T",
            delta_count=3,
        )
    )
    for lang in _REQUIRED_LANGUAGES:
        assert "130" in narrative[lang]
        assert "2026-2T" in narrative[lang]


def test_unknown_kind_raises() -> None:
    """Defensive guard: unhandled enum members surface programming errors."""
    from typing import cast

    fake_kind = cast(FilingDivergenceKind, object())
    with pytest.raises(ValueError):
        compose_delta_narrative(
            casilla_id="*",
            kind=fake_kind,
            local_value=None,
            remote_value=None,
            delta=None,
        )


def test_unknown_status_raises() -> None:
    from typing import cast

    fake_status = cast(ReconciliationStatus, object())
    with pytest.raises(ValueError):
        compose_report_narrative(
            status=fake_status,
            modelo="303",
            period="2026-1T",
            delta_count=0,
        )
