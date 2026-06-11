"""Regression tests for Modelo 620 Path-B refusal stub.

``aeat app modelo work create --modelo 620`` must return a legally-grounded
refusal payload rather than a generic crash or a "Modelo desconocido 620"
error.

Modelo 620 is the self-assessment for ITP-AJD on specific transfers of used
motor vehicles under Ley 28/1990 (ITPyAJD).  The tax is cedido (devolved)
to the Autonomous Communities; the autoliquidación must be filed at the
Hacienda of the CCAA where the transferred asset is located.  The national
AEAT CLI cannot route this filing to the correct autonomic authority.

No mocks: the guard runs against the real stub set and locale system.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_cli_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def test_work_create_620_refuses_with_legal_authority_message(
    _isolated_cli_backend: Path,
) -> None:
    """work create --modelo 620 is refused with a legally-grounded message
    citing Ley 28/1990 (ITPyAJD) and the autonomic Hacienda redirect.

    The CLI must NOT return a generic crash, a silent empty result, or
    ``Modelo desconocido 620``.  The refusal message must cite the governing
    statute and redirect to the CCAA Hacienda.

    Anti-tautology: the assertions target legal citation strings ("28/1990"
    or "ITPyAJD") that cannot appear in the humanised-key fallback
    ("Create stub modelo 620 refused"), so the test fails if the locale key
    is missing or untranslated.
    """

    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "620",
            "--year", "2024",
            "--period", "0A",
            "--revision", "actual",
        ],
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    # Must cite the governing statute (Ley 28/1990 / ITPyAJD).
    assert "28/1990" in result.output or "ITPyAJD" in result.output
    # Must redirect to the autonomic Hacienda (CCAA).
    assert "Hacienda" in result.output or "CCAA" in result.output
    # Generic crash / unknown-modelo messages are forbidden.
    assert "Modelo desconocido" not in result.output
    assert "could not evaluate" not in result.output


def test_work_create_620_refusal_fires_before_profile_check(
    _isolated_cli_backend: Path,
) -> None:
    """The stub guard fires before the active-profile requirement.

    An operator without an active profile still gets the M620 refusal
    message (not a ``no active profile`` error), proving the guard runs
    on the stub set alone, independent of registry or profile state.
    """

    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "620",
            "--year", "2024",
            "--period", "0A",
            "--revision", "actual",
        ],
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    assert "28/1990" in result.output or "ITPyAJD" in result.output or "Hacienda" in result.output
