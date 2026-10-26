"""Fresh-process guards for work the sign-in surface does not use."""

from __future__ import annotations

import subprocess
import sys
from textwrap import dedent

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_sign_in_chrome_does_not_load_calendar_execution_or_installation_forms() -> None:
    """Real screen imports and projection schemas remain usable without execution code."""
    completed = subprocess.run(  # noqa: S603 -- current interpreter and a fixed import-only probe; no shell.
        [
            sys.executable,
            "-c",
            dedent(
                """
                import sys
                from cadrumo.entrypoints.tui.account import AccountRecomposeReasonV1
                from cadrumo.entrypoints.tui.installation.destination import InstallationScreen
                from cadrumo.application.overview.home import HomeProjectionV1
                from cadrumo.application.overview.agenda import OverviewAgenda

                assert AccountRecomposeReasonV1.CHANGE_USER
                assert InstallationScreen.__name__ == 'InstallationScreen'
                assert HomeProjectionV1.model_json_schema()['properties']
                assert OverviewAgenda.model_json_schema()['properties']['next_due']
                forbidden = (
                    'cadrumo.application.overview.calendar',
                    'cadrumo.application.overview._calendar_evidence_sources',
                    'cadrumo.entrypoints.tui.installation.act_screen',
                )
                assert not [name for name in forbidden if name in sys.modules]
                print('projection-and-screen-imports-ready')
                """
            ),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "projection-and-screen-imports-ready"
