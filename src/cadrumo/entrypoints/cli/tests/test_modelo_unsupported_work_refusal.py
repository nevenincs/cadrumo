"""Unsupported modelo work-create refusal coverage.

The CLI must refuse unsupported local ``work create`` surfaces with legally
grounded operator copy instead of producing an unknown-modelo error, a crash, or
an active-profile error. These tests use the real CLI, registry, locale system,
and Settings override context; no mocks, patches, or monkeypatches are involved.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ....core.config import Settings, override_settings
from ....domain.calculations.registry.authority import bundled_authority
from ....tests.aeat_literal_fixtures import aeat_host
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from .._modelo_work_lifecycle_cli import guard_unsupported_work_modelo
from ..errors import CliRefusedBoundaryError

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SEDE_HOST = aeat_host("sede")


@dataclass(frozen=True)
class UnsupportedWorkCase:
    modelo: str
    year: int
    period: str
    revision: str
    required_groups: tuple[tuple[str, ...], ...]


_UNSUPPORTED_WORK_CASES = (
    UnsupportedWorkCase(
        modelo="151",
        year=2024,
        period="0A",
        revision="2024-y-siguientes",
        required_groups=(("93",), ("EHA/2887/2008", "2887"), (_SEDE_HOST, "Sede")),
    ),
    UnsupportedWorkCase(
        modelo="210",
        year=2024,
        period="1T",
        revision="anual",
        required_groups=(("5/2004", "TRLIRNR"), ("G320", _SEDE_HOST)),
    ),
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
    UnsupportedWorkCase(
        modelo="714",
        year=2024,
        period="0A",
        revision="2021-y-siguientes",
        required_groups=(("19/1991", "1991"), ("HAC/1023/2021", "1023"), (_SEDE_HOST, "Sede")),
    ),
    UnsupportedWorkCase(
        modelo="721",
        year=2024,
        period="0A",
        revision="2023-y-siguientes",
        required_groups=(("HFP/886/2023",), ("50",), (_SEDE_HOST, "Sede")),
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

    result = invoke_cached_cli(_work_create_args(case))
    output = result.output or ""

    assert result.exit_code != 0, output
    assert "Traceback" not in output
    for required_group in case.required_groups:
        assert any(token in output for token in required_group), (
            f"modelo {case.modelo} output did not contain any of {required_group!r}: {output!r}"
        )
    if case.modelo == "721":
        assert "HFP/887/2023" not in output, "M721 must not cite the custodian-side 172/173 order"
    assert "Modelo desconocido" not in output
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


def test_m210_engine_live_flag_only_bypasses_m210_guard() -> None:
    """The M210 live-engine flag must not disable other unsupported-model refusals."""

    with override_settings(cadrumo_m210_engine_live=True):
        guard_unsupported_work_modelo("210")
        for other in ("151", "600", "620", "650", "660", "714", "721"):
            with pytest.raises(CliRefusedBoundaryError):
                guard_unsupported_work_modelo(other)


def test_m210_guard_refuses_when_engine_live_flag_is_unset() -> None:
    """By default, M210 still refuses with a typed refusal carrying modelo context."""

    assert Settings().cadrumo_m210_engine_live is False, (
        "M210 engine-live must default False until full local-work support is accepted"
    )

    with pytest.raises(CliRefusedBoundaryError) as exc_info:
        guard_unsupported_work_modelo("210")

    assert exc_info.value.translated_message is not None
    assert exc_info.value.context is not None
    assert exc_info.value.context.get("modelo") == "210"


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
