"""Versioned, non-financial inputs for the PROFILE-01 row-lifecycle journey.

This scenario deliberately uses the schema's repeatable ``activities`` section:
it has one required fact, one fact that can be explicitly cleared, and one
declared selector-backed fact.  That lets every frontend prove the distinction
between add, edit, clear, removal, and the surviving consumer-facing meaning
without inventing filing-time profile semantics.
"""

from __future__ import annotations

from dataclasses import dataclass

BRIEF_ID = "PROFILE-01"
BRIEF_REVISION = "0.1"
PATTERN_ID = "ACCEPTANCE-01"
PATTERN_REVISION = "1.6"
SCENARIO_VERSION = "profile-repeatable-row-lifecycle-v1"


@dataclass(frozen=True, slots=True)
class ProfileRowLifecycleScenario:
    """One public-input row case shared by CLI and installed-TUI drivers."""

    section: str
    required_field: str
    clearable_field: str
    selector_field: str
    description: str
    initial_cnae: str
    amended_cnae: str
    iae_epigraph: str

    def path(self, row_key: str, field: str) -> str:
        """Return the canonical path for a numeric repeatable-row identity."""
        if not row_key.isdecimal():
            raise ValueError("PROFILE-01 acceptance row identity must be numeric")
        if field not in {self.required_field, self.clearable_field, self.selector_field}:
            raise ValueError("PROFILE-01 acceptance requested an undeclared activity field")
        return f"{self.section}.{int(row_key)}.{field}"

    def add_values(self) -> tuple[tuple[str, str], ...]:
        """Return explicit public CLI/TUI values, never receipt payload data."""
        return (
            (self.required_field, self.description),
            (self.clearable_field, self.initial_cnae),
            (self.selector_field, self.iae_epigraph),
        )


def build_profile_row_lifecycle_scenario() -> ProfileRowLifecycleScenario:
    """Build the single current-profile scenario authorized by PROFILE-01."""
    return ProfileRowLifecycleScenario(
        section="activities",
        required_field="description",
        clearable_field="cnae",
        selector_field="iae_epigraph",
        description="Synthetic acceptance activity",
        initial_cnae="6201",
        amended_cnae="6202",
        iae_epigraph="765",
    )


__all__ = [
    "BRIEF_ID",
    "BRIEF_REVISION",
    "PATTERN_ID",
    "PATTERN_REVISION",
    "SCENARIO_VERSION",
    "ProfileRowLifecycleScenario",
    "build_profile_row_lifecycle_scenario",
]
