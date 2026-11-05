"""The tax identifier of the ready profile's taxpayer, read from the persona catalogue."""

from __future__ import annotations

from cadrumo.tests.personas import identity_catalogue

_READY_PROFILE_ROLE = "fontanero.titular"
"""The identity role the ready profile (the autonomo-fontanero persona) binds as its taxpayer."""


def ready_profile_tax_id() -> str:
    """Return the tax identifier the ready profile is registered under."""
    return identity_catalogue().role(_READY_PROFILE_ROLE).value
