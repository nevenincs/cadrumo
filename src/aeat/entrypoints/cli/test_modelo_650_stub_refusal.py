"""Regression tests for Modelo 650 Path-B refusal stub.

``aeat app modelo work create --modelo 650`` must return a legally-grounded
refusal payload rather than a generic crash or a "Modelo desconocido 650"
error.

Modelo 650 is the self-assessment for the Impuesto sobre Sucesiones y
Donaciones (ISD) on inherited assets under Ley 29/1987 (LISyD).  Key
provisions: Art. 67 RISD sets a 6-month filing deadline from the date of
death, extendable by a further 6 months.  Ley 22/2009 Art. 32 determines
that the declaration must be filed at the Hacienda of the CCAA where the
deceased (causante) had their habitual residence.  The national AEAT CLI
cannot route this to the correct autonomic Hacienda.

No mocks: the guard runs against the real stub set and locale system.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from aeat.tests.cli_runner import invoke_cached_cli
from aeat.tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_cli_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def test_work_create_650_refuses_with_legal_authority_message(
    _isolated_cli_backend: Path,
) -> None:
    """work create --modelo 650 is refused with a legally-grounded message
    citing Ley 29/1987 (LISyD) / Art. 67 RISD and the autonomic Hacienda
    redirect.

    The CLI must NOT return a generic crash, a silent empty result, or
    ``Modelo desconocido 650``.  The refusal message must cite the governing
    statute and the CCAA redirect.

    Anti-tautology: the assertions target legal citation strings ("29/1987"
    or "Art. 67 RISD" or "Hacienda") that cannot appear in the humanised-key
    fallback ("Create stub modelo 650 refused"), so the test fails if the
    locale key is missing or untranslated.
    """

    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "650",
            "--year", "2024",
            "--period", "0A",
            "--revision", "actual",
        ]
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    # Must cite the governing statute (Ley 29/1987 / LISyD).
    assert "29/1987" in result.output or "LISyD" in result.output
    # Must cite the plazo provision (Art. 67 RISD) or the 6-month deadline.
    assert "Art. 67 RISD" in result.output or "67 RISD" in result.output or "6 mes" in result.output
    # Must redirect to the autonomic Hacienda.
    assert "Hacienda" in result.output
    # Generic crash / unknown-modelo messages are forbidden.
    assert "Modelo desconocido" not in result.output
    assert "could not evaluate" not in result.output


def test_work_create_650_refusal_fires_before_profile_check(
    _isolated_cli_backend: Path,
) -> None:
    """The stub guard fires before the active-profile requirement.

    An operator without an active profile still gets the M650 refusal
    message (not a ``no active profile`` error), proving the guard runs
    on the stub set alone, independent of registry or profile state.
    """

    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "650",
            "--year", "2024",
            "--period", "0A",
            "--revision", "actual",
        ]
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    assert "29/1987" in result.output or "LISyD" in result.output or "Hacienda" in result.output
