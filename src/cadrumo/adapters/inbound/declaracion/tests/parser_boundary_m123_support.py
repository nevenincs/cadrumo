"""Shared Modelo 123 parser boundary corpus expectations."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from .....core.casilla_id import CasillaId
from .....domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    filing_year_envelope,
    revision_covering,
    revision_last_exercise,
)
from .parser_boundary_support import (
    MODELO_123_2023_SYNTHETIC_FIXTURE,
    MODELO_123_2024_SYNTHETIC_FIXTURE,
    MODELO_123_CURRENT_EXPECTED_TARGETS,
    MODELO_123_HISTORICAL_EXPECTED_TARGETS,
    expected_casilla_values,
    specimen_period,
)

_CURRENT_EXERCISE = filing_year_envelope().horizon
(_CLOSED_REVISION,) = (revision for revision in authored_revisions("123") if revision.valid_to is not None)
_CLOSED_REVISION_LAST_EXERCISE = revision_last_exercise("123", str(_CLOSED_REVISION.id))
_FIXTURE_2024_EXERCISE = specimen_period(MODELO_123_2024_SYNTHETIC_FIXTURE).filing_year
_FIXTURE_2023_EXERCISE = specimen_period(MODELO_123_2023_SYNTHETIC_FIXTURE).filing_year
_FIXTURE_2024_REVISION = str(revision_covering("123", _FIXTURE_2024_EXERCISE).id)
_FIXTURE_2023_REVISION = str(revision_covering("123", _FIXTURE_2023_EXERCISE).id)

M123_PROFILE_TARGET_CASES: tuple[tuple[str, int, str, str, tuple[CasillaId, ...]], ...] = (
    ("current", _CURRENT_EXERCISE, "1T", "modelo-123-declaracion-pdf", MODELO_123_CURRENT_EXPECTED_TARGETS),
    (
        "historical",
        _CLOSED_REVISION_LAST_EXERCISE,
        "4T",
        "modelo-123-declaracion-pdf",
        MODELO_123_HISTORICAL_EXPECTED_TARGETS,
    ),
)
M123_PROFILE_TARGET_CASE_IDS: tuple[str, ...] = tuple(
    case_id for case_id, _year, _period, _profile_id, _targets in M123_PROFILE_TARGET_CASES
)

M123_CORPUS_CASES: tuple[
    tuple[str, Path, int, str, str, tuple[CasillaId, ...], dict[CasillaId, Decimal]],
    ...,
] = (
    (
        _FIXTURE_2024_REVISION,
        MODELO_123_2024_SYNTHETIC_FIXTURE,
        _FIXTURE_2024_EXERCISE,
        "1T",
        _FIXTURE_2024_REVISION,
        MODELO_123_CURRENT_EXPECTED_TARGETS,
        expected_casilla_values(
            {
                "01": Decimal("5.00"),
                "02": Decimal("3.00"),
                "03": Decimal("8.00"),
                "04": Decimal("10000.00"),
                "05": Decimal("5000.00"),
                "06": Decimal("15000.00"),
                "07": Decimal("1900.00"),
                "08": Decimal("950.00"),
                "09": Decimal("2850.00"),
                "10": Decimal("0.00"),
                "11": Decimal("0.00"),
                "12": Decimal("2850.00"),
                "13": Decimal("0.00"),
                "14": Decimal("2850.00"),
            },
        ),
    ),
    (
        _FIXTURE_2023_REVISION,
        MODELO_123_2023_SYNTHETIC_FIXTURE,
        _FIXTURE_2023_EXERCISE,
        "1T",
        _FIXTURE_2023_REVISION,
        MODELO_123_HISTORICAL_EXPECTED_TARGETS,
        expected_casilla_values(
            {
                "01": Decimal("4.00"),
                "02": Decimal("8000.00"),
                "03": Decimal("1520.00"),
                "04": Decimal("0.00"),
                "05": Decimal("0.00"),
                "06": Decimal("1520.00"),
                "07": Decimal("0.00"),
                "08": Decimal("1520.00"),
            },
        ),
    ),
)
M123_CORPUS_CASE_IDS: tuple[str, ...] = tuple(
    case_id for case_id, _fixture, _year, _period, _revision, _targets, _values in M123_CORPUS_CASES
)
