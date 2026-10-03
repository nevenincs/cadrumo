"""Canonical profile stage for installed export-parity seeding."""

from __future__ import annotations

import json

from dev.acceptance.installed_cli import profile_create_args

from .scenario import (
    YEARS,
)
from .seed_contracts import (
    _PROFILE,
)
from .seed_state import SeedState


class ProfileSeedStage(SeedState):
    """Own the installed seed profile behavior."""

    def profile(self) -> None:
        """Create the synthetic campaign profile only when its stage is pending."""
        if not self._stage("profile"):
            return
        payload = json.dumps({"passphrase": self.cli.passphrase, "passphrase_confirmation": self.cli.passphrase})
        self.cli.run(
            profile_create_args(YEARS[0]), authenticated=False, stdin_payload=payload, command="config profile create"
        )
        self._result(
            (
                "config",
                "profile",
                "edit",
                _PROFILE,
                "--quiet",
                "--accept-defaults",
                "--pays-professionals-with-retencion",
                "--pays-rent-with-retencion",
                "--no-pays-capital-income-with-retencion",
                "--no-colegio-concertado",
                "--third-party-transactions-above-347-threshold",
            ),
            stage="profile.edit",
        )
        self._result(("config", "profile", "complete-setup"), stage="profile.complete_setup")
        self._done("profile")
