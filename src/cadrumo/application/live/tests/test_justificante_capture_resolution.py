"""Period-aware expediente resolution.

The procedure-tree expediente carries no period, so a quarterly work unit
must resolve through the period-bearing declarations register. These tests
pin the primary risk of the feature: a 1T and a 2T work unit MUST resolve to
distinct expedientes and never silently reconcile against the wrong quarter.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede.declarations_schema import Declaracion
from ....adapters.outbound.aeat.sede.schema import Expediente
from ....core import Modelo, Period
from ....core.config import Settings
from ..errors import LiveApplicationInputError
from ..justificante import resolve_period_expediente

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = Modelo.M130.value
_YEAR = 2026
_EXP_1T = "202613000010001A"
_EXP_2T = "202613000020002B"
_PERIOD_1T = Period.from_year_and_code(_YEAR, "1T")
_PERIOD_2T = Period.from_year_and_code(_YEAR, "2T")
_PERIOD_3T = Period.from_year_and_code(_YEAR, "3T")
_AEAT = Settings.external_constants().aeat


def _declaration(
    *,
    period: Period,
    expediente_id: str,
    presented_at: datetime,
    estado: str = "ALTA",
) -> Declaracion:
    return Declaracion(
        modelo=_MODELO,
        ejercicio=_YEAR,
        period=period,
        expediente_id=expediente_id,
        estado=estado,
        presented_at=presented_at,
    )


def _expediente(*, expediente_id: str) -> Expediente:
    return Expediente(
        expediente_id=expediente_id,
        modelo=_MODELO,
        ejercicio=_YEAR,
        category_path=("AEAT", "Modelo 130. IRPF. Pago fraccionado."),
        detail_url=AnyHttpUrl(
            f"{_AEAT.domains.sede}{_AEAT.sede_paths.expediente_detail_template.format(expediente_id=expediente_id)}",
        ),
    )


_DECLARATIONS = (
    _declaration(period=_PERIOD_1T, expediente_id=_EXP_1T, presented_at=datetime(2026, 4, 18, 9, 0, tzinfo=UTC)),
    _declaration(period=_PERIOD_2T, expediente_id=_EXP_2T, presented_at=datetime(2026, 7, 18, 9, 0, tzinfo=UTC)),
)
_EXPEDIENTES = (_expediente(expediente_id=_EXP_1T), _expediente(expediente_id=_EXP_2T))


def test_resolves_first_quarter_to_its_own_expediente() -> None:
    resolved = resolve_period_expediente(
        declarations=_DECLARATIONS,
        expedientes=_EXPEDIENTES,
        modelo=_MODELO,
        period=_PERIOD_1T,
    )
    assert resolved.expediente_id == _EXP_1T


def test_resolves_second_quarter_to_a_distinct_expediente() -> None:
    resolved = resolve_period_expediente(
        declarations=_DECLARATIONS,
        expedientes=_EXPEDIENTES,
        modelo=_MODELO,
        period=_PERIOD_2T,
    )
    assert resolved.expediente_id == _EXP_2T
    # The primary-risk invariant: the two quarters never collapse to one.
    first = resolve_period_expediente(
        declarations=_DECLARATIONS,
        expedientes=_EXPEDIENTES,
        modelo=_MODELO,
        period=_PERIOD_1T,
    )
    assert resolved.expediente_id != first.expediente_id


def test_missing_period_declaration_refuses_rather_than_falls_back() -> None:
    with pytest.raises(
        LiveApplicationInputError,
        match=r"application\.live\.justificante\.errors\.no_filed_declaration",
    ):
        resolve_period_expediente(
            declarations=_DECLARATIONS,
            expedientes=_EXPEDIENTES,
            modelo=_MODELO,
            period=_PERIOD_3T,
        )


def test_declaration_with_expediente_absent_from_tree_refuses() -> None:
    with pytest.raises(
        LiveApplicationInputError,
        match=r"application\.live\.justificante\.errors\.expediente_not_in_tree",
    ):
        resolve_period_expediente(
            declarations=_DECLARATIONS,
            expedientes=(_expediente(expediente_id=_EXP_1T),),  # tree missing the 2T expediente
            modelo=_MODELO,
            period=_PERIOD_2T,
        )


def test_refiled_period_resolves_to_the_latest_active_filing() -> None:
    early = _declaration(period=_PERIOD_1T, expediente_id=_EXP_1T, presented_at=datetime(2026, 4, 18, 9, 0, tzinfo=UTC))
    refile_exp = "202613000010099Z"
    late = _declaration(
        period=_PERIOD_1T,
        expediente_id=refile_exp,
        presented_at=datetime(2026, 5, 2, 11, 0, tzinfo=UTC),
    )
    resolved = resolve_period_expediente(
        declarations=(early, late),
        expedientes=(_expediente(expediente_id=_EXP_1T), _expediente(expediente_id=refile_exp)),
        modelo=_MODELO,
        period=_PERIOD_1T,
    )
    assert resolved.expediente_id == refile_exp


def test_later_cancellation_does_not_win_over_earlier_active_filing() -> None:
    """A later non-ALTA (cancelled/corrected) row must not outrank the ALTA filing.

    Without the estado-aware tiebreak this would pick the later cancellation
    row's expediente and pull the wrong-state receipt.
    """
    accepted = _declaration(
        period=_PERIOD_1T,
        expediente_id=_EXP_1T,
        presented_at=datetime(2026, 4, 18, 9, 0, tzinfo=UTC),
        estado="ALTA",
    )
    cancelled_exp = "202613000010088Y"
    cancelled = _declaration(
        period=_PERIOD_1T,
        expediente_id=cancelled_exp,
        presented_at=datetime(2026, 5, 10, 9, 0, tzinfo=UTC),
        estado="Anulada",
    )
    resolved = resolve_period_expediente(
        declarations=(accepted, cancelled),
        expedientes=(_expediente(expediente_id=_EXP_1T), _expediente(expediente_id=cancelled_exp)),
        modelo=_MODELO,
        period=_PERIOD_1T,
    )
    assert resolved.expediente_id == _EXP_1T
