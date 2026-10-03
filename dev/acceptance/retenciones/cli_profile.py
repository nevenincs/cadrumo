"""Create the synthetic withholding profile through installed public commands."""

from __future__ import annotations

from dev.acceptance.installed_cli import InstalledCli

from .cli_contracts import RetencionesInstalledCliError
from .cli_observations import _require_result


def _create_withholding_profile(cli: InstalledCli, *, year: int) -> None:
    """Create a secure synthetic profile and explicitly activate both duties."""
    try:
        cli.create_profile(year=year)
    except Exception as exc:
        raise RetencionesInstalledCliError(
            stage="profile_create",
            diagnostic_code=f"profile_create_{type(exc).__name__}",
        ) from exc
    _require_result(
        cli,
        (
            "config",
            "profile",
            "edit",
            f"income-{year}",
            "--quiet",
            "--accept-defaults",
            "--pays-professionals-with-retencion",
            "--pays-rent-with-retencion",
            "--no-pays-capital-income-with-retencion",
            # Modelo 111 requires this filing-header attestation.  The value
            # is a synthetic operator fact, deliberately supplied through
            # the now-public profile edit surface rather than seeded.
            "--no-colegio-concertado",
        ),
        stage="profile_enable_withholding_duties",
    )
    _require_result(
        cli,
        ("config", "profile", "complete-setup"),
        stage="profile_complete_setup",
    )
