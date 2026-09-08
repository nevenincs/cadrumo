"""Unsupported modelo work-create refusal coverage.

The CLI must refuse unsupported local ``work create`` surfaces with legally
grounded operator copy instead of producing an unknown-modelo error, a crash, or
an active-profile error. These tests use the real CLI, registry, locale system,
and Settings override context; no mocks, patches, or monkeypatches are involved.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from .._modelo_work_lifecycle_cli import guard_unsupported_work_modelo

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@dataclass(frozen=True)
class UnsupportedWorkCase:
    modelo: str
    year: int
    period: str
    revision: str
    required_groups: tuple[tuple[str, ...], ...]


_UNSUPPORTED_WORK_CASES = (
    UnsupportedWorkCase(
        modelo="600",
        year=2024,
        period="0A",
        revision="actual",
        required_groups=(("28/1990", "ITPyAJD"), ("Hacienda", "CCAA")),
    ),
    UnsupportedWorkCase(
        modelo="620",
        year=2024,
        period="0A",
        revision="actual",
        required_groups=(("28/1990", "ITPyAJD"), ("Hacienda", "CCAA")),
    ),
    UnsupportedWorkCase(
        modelo="650",
        year=2024,
        period="0A",
        revision="actual",
        required_groups=(("29/1987", "LISyD"), ("Art. 67 RISD", "67 RISD", "6 mes"), ("Hacienda",)),
    ),
    UnsupportedWorkCase(
        modelo="660",
        year=2024,
        period="0A",
        revision="actual",
        required_groups=(("29/1987", "LISyD"), ("Hacienda",)),
    ),
)


def _work_create_args(case: UnsupportedWorkCase) -> list[str]:
    return [
        "app",
        "modelo",
        "work",
        "create",
        "--modelo",
        case.modelo,
        "--year",
        str(case.year),
        "--period",
        case.period,
        "--revision",
        case.revision,
    ]


@pytest.mark.parametrize("case", _UNSUPPORTED_WORK_CASES, ids=[case.modelo for case in _UNSUPPORTED_WORK_CASES])
def test_work_create_unsupported_modelo_refuses_with_legal_authority(case: UnsupportedWorkCase) -> None:
    """Each unsupported modelo refuses before active-profile resolution and names its legal route."""

    result = invoke_cached_cli(["--language", "en", *_work_create_args(case)])
    output = result.output or ""

    assert result.exit_code != 0, output
    assert "Traceback" not in output
    for required_group in case.required_groups:
        assert any(token in output for token in required_group), (
            f"modelo {case.modelo} output did not contain any of {required_group!r}: {output!r}"
        )
    assert "could not evaluate" not in output


def test_registry_entries_for_unsupported_local_work_are_legally_grounded() -> None:
    """Manual-casilla registry entries for unsupported work-create modelos cite their legal corpus."""

    expected = {
        "151": ("ley-35-2006:art-93", "boe-modelo-151-layout"),
        "714": ("ley-19-1991:art-28", "boe-modelo-714-layout"),
        "721": ("ley-11-2021:da-10", "boe-modelo-721-2023-layout"),
    }
    modelos = bundled_authority().modelos
    catalogues = bundled_authority().catalogues
    modelo_ids = {modelo.id for modelo in modelos}

    for modelo, (legal_id, source_id) in expected.items():
        assert modelo in modelo_ids
        assert legal_id in catalogues.legal
        assert source_id in catalogues.sources


def test_aeat_modelos_are_not_classified_by_a_rollout_census() -> None:
    """Every AEAT modelo proceeds to its real capability-owning boundary."""

    for modelo in ("151", "210", "714", "721"):
        guard_unsupported_work_modelo(modelo)


@pytest.mark.parametrize(
    ("causante_ccaa", "expected_tokens"),
    (
        pytest.param(
            "pais_vasco",
            ("foral", "Concierto", "Ley 12/2002", "Hacienda Foral", "Pais Vasco", "País Vasco"),
            id="pais-vasco",
        ),
        pytest.param(
            "navarra",
            ("foral", "Convenio", "Ley 28/1990", "Navarra", "Hacienda Foral"),
            id="navarra",
        ),
    ),
)
def test_m650_foral_causante_ccaa_refuses_before_unsupported_modelo_guard(
    causante_ccaa: str,
    expected_tokens: tuple[str, ...],
) -> None:
    """Foral causante CCAA errors are more specific than the generic M650 refusal."""

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "650",
            "--year",
            "2024",
            "--period",
            "0A",
            "--revision",
            "actual",
            "--causante-ccaa",
            causante_ccaa,
        ],
    )
    output = result.output or ""

    assert result.exit_code != 0, output
    assert "Traceback" not in output
    assert any(token in output for token in expected_tokens), (
        f"expected foral-regime message for {causante_ccaa}, got: {output!r}"
    )
