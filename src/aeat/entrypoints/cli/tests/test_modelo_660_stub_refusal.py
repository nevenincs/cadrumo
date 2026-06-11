"""Regression tests for Modelo 660 Path-B refusal stub.

``aeat app modelo work create --modelo 660`` must return a legally-grounded
refusal payload rather than a generic crash or a "Modelo desconocido 660"
error.

Modelo 660 is the informative declaration of the estate inventory (caudal
relicto) filed alongside Modelo 650 in joint or sociedades declarations
under Ley 29/1987 (LISyD).  The same provisions as Modelo 650 apply:
Art. 67 RISD (6-month deadline, extendable by 6 months) and Ley 22/2009
Art. 32 (filed at the Hacienda of the CCAA where the causante had habitual
residence).

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


def test_work_create_660_refuses_with_legal_authority_message(
    _isolated_cli_backend: Path,
) -> None:
    """work create --modelo 660 is refused with a legally-grounded message
    citing Ley 29/1987 (LISyD) and the autonomic Hacienda redirect.

    The CLI must NOT return a generic crash, a silent empty result, or
    ``Modelo desconocido 660``.  The refusal message must cite the governing
    statute and the CCAA redirect.

    Anti-tautology: the assertions target legal citation strings ("29/1987"
    or "LISyD" or "Hacienda") that cannot appear in the humanised-key fallback
    ("Create stub modelo 660 refused"), so the test fails if the locale key
    is missing or untranslated.
    """

    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "660",
            "--year", "2024",
            "--period", "0A",
            "--revision", "actual",
        ],
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    # Must cite the governing statute (Ley 29/1987 / LISyD).
    assert "29/1987" in result.output or "LISyD" in result.output
    # Must redirect to the autonomic Hacienda.
    assert "Hacienda" in result.output
    # Generic crash / unknown-modelo messages are forbidden.
    assert "Modelo desconocido" not in result.output
    assert "could not evaluate" not in result.output


def test_work_create_660_refusal_fires_before_profile_check(
    _isolated_cli_backend: Path,
) -> None:
    """The stub guard fires before the active-profile requirement.

    An operator without an active profile still gets the M660 refusal
    message (not a ``no active profile`` error), proving the guard runs
    on the stub set alone, independent of registry or profile state.
    """

    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "660",
            "--year", "2024",
            "--period", "0A",
            "--revision", "actual",
        ],
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    assert "29/1987" in result.output or "LISyD" in result.output or "Hacienda" in result.output
