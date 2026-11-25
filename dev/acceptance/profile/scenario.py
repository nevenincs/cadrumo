"""Versioned, non-financial inputs for the PROFILE-01 row-lifecycle journey.

This scenario deliberately uses the schema's repeatable ``activities`` section:
it has one required fact and one fact that can be explicitly cleared and that a
registry selector reads.  That lets every frontend prove the distinction
between add, edit, clear, removal, and the surviving required fact without
inventing filing-time profile semantics.
"""

from __future__ import annotations

from dataclasses import dataclass

BRIEF_ID = "PROFILE-01"
BRIEF_REVISION = "0.1"
PATTERN_ID = "ACCEPTANCE-01"
PATTERN_REVISION = "1.6"
SCENARIO_VERSION = "profile-repeatable-row-lifecycle-v2"


@dataclass(frozen=True, slots=True)
class ProfileRowLifecycleScenario:
    """One public-input row case shared by CLI and installed-TUI drivers."""

    section: str
    required_field: str
    clearable_field: str
    description: str
    initial_epigraph: str
    amended_epigraph: str

    def path(self, row_key: str, field: str) -> str:
        """Return the canonical path for a numeric repeatable-row identity."""
        if not row_key.isdecimal():
            raise ValueError("PROFILE-01 acceptance row identity must be numeric")
        if field not in {self.required_field, self.clearable_field}:
            raise ValueError("PROFILE-01 acceptance requested an undeclared activity field")
        return f"{self.section}.{int(row_key)}.{field}"

    def add_values(self) -> tuple[tuple[str, str], ...]:
        """Return explicit public CLI/TUI values in schema field order, never receipt payload data."""
        return (
            (self.required_field, self.description),
            (self.clearable_field, self.initial_epigraph),
        )


def build_profile_row_lifecycle_scenario() -> ProfileRowLifecycleScenario:
    """Build the single current-profile scenario authorized by PROFILE-01."""
    return ProfileRowLifecycleScenario(
        section="activities",
        required_field="description",
        clearable_field="iae_epigraph",
        description="Synthetic acceptance activity",
        initial_epigraph="765",
        amended_epigraph="766",
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
