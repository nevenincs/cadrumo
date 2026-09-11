"""Canonical flow for read-only identifier-checker oracles.

The shared checker contract owns one observation shape, driver protocol,
deterministic replay driver, declarative operation plan, and verification
orchestrator.  Concrete GROI and NIF-IVA modules declare only their AEAT
endpoint policy, catalogue identity, and surface classification.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ....core.identity.tax_id import tax_id_identity_token
from ....core.models import STRICT_FROZEN_CONFIG
from .errors import RegistryValidationError


class CheckerDriverMode(StrEnum):
    """Whether a checker driver reaches AEAT or replays captured evidence."""

    LIVE = "live"
    """Executes against the live AEAT surface."""

    REPLAY = "replay"
    """Replays previously captured evidence and performs no network operation."""


CheckerDriverModeValue = Literal[CheckerDriverMode.LIVE, CheckerDriverMode.REPLAY]
"""Both modes, for the Protocol property a driver of either kind satisfies.

The concrete drivers narrow this to the single member they actually are, rooted as
`Literal[CheckerDriverMode.LIVE]` or `Literal[CheckerDriverMode.REPLAY]`. Those
narrowings are contracts -- a live driver may never report itself as a replay -- and
are deliberately not widened to this alias.
"""


class CheckerObservation(BaseModel):
    """Normalized verdicts and raw-evidence locator from a checker surface."""

    model_config = STRICT_FROZEN_CONFIG

    values: dict[str, str] = Field(default_factory=dict)
    raw_evidence_locator: str | None = Field(default=None, max_length=512)

    @field_validator("values")
    @classmethod
    def _normalize_values(cls, value: dict[str, str]) -> dict[str, str]:
        return normalize_verdict_mapping(
            value,
            blank_message="Checker observations must not contain blank keys or values",
        )


def normalize_verdict_mapping(values: Mapping[str, str], *, blank_message: str) -> dict[str, str]:
    """Normalize identifier/verdict mappings and reject blank entries."""
    cleaned: dict[str, str] = {}
    for identifier, verdict in values.items():
        normalized_identifier = tax_id_identity_token(identifier)
        normalized_verdict = verdict.strip().lower()
        if not normalized_identifier or not normalized_verdict:
            raise RegistryValidationError(blank_message)
        cleaned[normalized_identifier] = normalized_verdict
    return cleaned
