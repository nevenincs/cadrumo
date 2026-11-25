"""Profile answers shared by the native runtime tests that register a general-regime natural person."""

from __future__ import annotations

from cadrumo.adapters.persistence.profile.tests.ready_profile_support import ready_profile_fact_values


def native_general_iva_facts() -> dict[str, str]:
    """Return the taxpayer answers the autonomo-fontanero persona states, as the registration door takes them."""
    return {
        path: (str(value).lower() if isinstance(value, bool) else value)
        for path, value in ready_profile_fact_values().items()
    }
