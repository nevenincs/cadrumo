"""Shape tests for the ``aeat config init`` skeleton (P05.S01).

Verifies the typer command signature carries the two new flags mandated
by :doc:`.vault/plan/2026-05-14-secure-backend-passkey-bucket-plan`
P05.S01 (``--accept-data-loss-risk`` and ``--persist-recovery-wrap``),
rejects the legacy ``--profile`` option that previously aliased the
bucket on the silent-mint path being retired in P06.S01, and refuses
the non-interactive mint unless both the ``AEAT_SECRET_PASSPHRASE``
environment variable AND ``--accept-data-loss-risk`` are present.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_init_help_advertises_both_new_flags(runner: CliRunner) -> None:
    """``--accept-data-loss-risk`` and ``--persist-recovery-wrap`` appear in --help."""
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0, result.stdout
    assert "--accept-data-loss-risk" in result.stdout
    assert "--persist-recovery-wrap" in result.stdout


def test_init_rejects_legacy_profile_option(runner: CliRunner) -> None:
    """``--profile`` is the retired silent-mint alias and MUST be unknown on init."""
    result = runner.invoke(app, ["init", "--profile", "any-name"])
    # Typer / click emit exit code 2 for unknown options. The exact
    # error text is click-controlled; the contract is "option not
    # recognised on the init verb", which the non-zero exit + the
    # absent option signal together.
    assert result.exit_code != 0
    assert "--profile" in (result.output or "")


def test_init_refuses_without_passphrase_env(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No AEAT_SECRET_PASSPHRASE in env -> refused with exit 2."""
    monkeypatch.delenv("AEAT_SECRET_PASSPHRASE", raising=False)
    result = runner.invoke(app, ["init", "--accept-data-loss-risk"])
    assert result.exit_code == 2
    assert "non-interactive mint refused" in (result.output or "")


def test_init_refuses_without_accept_data_loss_risk_flag(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AEAT_SECRET_PASSPHRASE alone is not enough; the flag is also required."""
    monkeypatch.setenv("AEAT_SECRET_PASSPHRASE", "any-passphrase")
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 2
    assert "non-interactive mint refused" in (result.output or "")


def test_init_passes_two_key_gate_then_falls_through_to_p06_pending(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both preconditions satisfied -> falls through to the P06-pending notice (exit 2).

    The wizard / mint body lands in P06.S01; until then the only behaviour after
    the two-key gate is to emit the pending notice and exit non-zero, so
    callers cannot mistake the skeleton for a working mint.
    """
    monkeypatch.setenv("AEAT_SECRET_PASSPHRASE", "any-passphrase")
    result = runner.invoke(app, ["init", "--accept-data-loss-risk"])
    assert result.exit_code == 2
    assert "P06.S01" in (result.output or "")
