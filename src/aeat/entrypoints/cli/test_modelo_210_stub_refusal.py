"""Regression tests for Modelo 210 Path-B refusal stub.

``aeat app modelo work create --modelo 210`` must return a legally-grounded
refusal payload rather than a generic crash or a "Modelo desconocido 210"
error.

Modelo 210 is the self-assessment for the Impuesto sobre la Renta de No
Residentes (IRNR) under RD Legislativo 5/2004 (TRLIRNR).  Key provisions:
Art. 28 TRLIRNR governs quarterly filing deadlines (1T/2T/3T/4T); the
general rate is 19 % for EU/EEA residents and 24 % for others.  The
declaration is filed via AEAT Sede Electrónica G320.  The CLI cannot model
the full non-resident income taxonomy and redirects to the operative AEAT
surface.

No mocks: the guard runs against the real registry authority and locale
system.
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


def test_work_create_210_refuses_with_legal_authority_message(
    _isolated_cli_backend: Path,
) -> None:
    """work create --modelo 210 is refused with a legally-grounded message
    citing RD Legislativo 5/2004 (TRLIRNR) and the AEAT Sede G320 redirect.

    The CLI must NOT return a generic crash, a silent empty result, or
    ``Modelo desconocido 210``.  The refusal message must cite the governing
    statute and redirect to the operative AEAT surface.

    Anti-tautology: the assertions target legal citation strings that cannot
    appear in the humanised-key fallback
    ("Create stub modelo 210 refused"), so the test fails if the locale key
    is missing or untranslated.
    """

    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "210",
            "--year", "2024",
            "--period", "1T",
            "--revision", "anual",
        ]
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    # Must cite the governing statute (TRLIRNR / RD 5/2004).
    assert "5/2004" in result.output or "TRLIRNR" in result.output
    # Must redirect to AEAT Sede G320 procedure, not imply local-CLI support.
    assert "G320" in result.output or "sede.agenciatributaria.gob.es" in result.output
    # Generic crash / unknown-modelo messages are forbidden.
    assert "Modelo desconocido" not in result.output
    assert "could not evaluate" not in result.output


def test_work_create_210_refusal_fires_before_profile_check(
    _isolated_cli_backend: Path,
) -> None:
    """The stub guard fires before the active-profile requirement.

    An operator without an active profile still gets the M210 refusal
    message (not a ``no active profile`` error), proving the guard runs
    on the stub set alone, independent of registry or profile state.
    """

    # No profile created — no active session.
    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "210",
            "--year", "2024",
            "--period", "1T",
            "--revision", "anual",
        ]
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    # Refusal must contain legal citation, not a profile-missing message.
    assert "5/2004" in result.output or "TRLIRNR" in result.output or "G320" in result.output
