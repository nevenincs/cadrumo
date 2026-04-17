"""Strict pydantic model describing which taxpayer profiles owe a modelo."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ._categories import TaxpayerProfile


class ModeloApplicability(BaseModel):
    """Per-profile applicability partition for a single modelo.

    Every :class:`TaxpayerProfile` must appear in exactly one of the
    three frozen sets. The invariant is enforced by a
    ``model_validator(mode="after")`` on construction, so any malformed
    entry fails fast during registry assembly.

    Attributes:
        mandatory_profiles: Profiles that must file this modelo.
        optional_profiles: Profiles that may file this modelo when a
            threshold or opt-in is triggered.
        exempt_profiles: Profiles for which this modelo does not
            apply. Computed by callers as ``set(TaxpayerProfile) -
            mandatory - optional``.
        trigger_notes_es: Free-form Spanish explanation of the
            thresholds, opt-ins, or cross-references that gate the
            applicability. Never empty.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    mandatory_profiles: frozenset[TaxpayerProfile]
    optional_profiles: frozenset[TaxpayerProfile]
    exempt_profiles: frozenset[TaxpayerProfile]
    trigger_notes_es: str = Field(min_length=1)

    @field_validator("trigger_notes_es")
    @classmethod
    def _trigger_notes_not_blank(cls, value: str) -> str:
        """Reject whitespace-only ``trigger_notes_es``."""
        if not value.strip():
            raise ValueError("trigger_notes_es must not be empty or whitespace-only")
        return value

    @model_validator(mode="after")
    def _check_partition(self) -> Self:
        """Enforce that the three profile buckets partition the profile space."""
        all_profiles: frozenset[TaxpayerProfile] = frozenset(TaxpayerProfile)
        mandatory = self.mandatory_profiles
        optional = self.optional_profiles
        exempt = self.exempt_profiles
        mo = mandatory & optional
        if mo:
            raise ValueError(f"profiles appear in both mandatory and optional buckets: {sorted(p.value for p in mo)}")
        me = mandatory & exempt
        if me:
            raise ValueError(f"profiles appear in both mandatory and exempt buckets: {sorted(p.value for p in me)}")
        oe = optional & exempt
        if oe:
            raise ValueError(f"profiles appear in both optional and exempt buckets: {sorted(p.value for p in oe)}")
        union = mandatory | optional | exempt
        if union != all_profiles:
            missing = sorted(p.value for p in all_profiles - union)
            extra = sorted(p.value for p in union - all_profiles)
            raise ValueError(f"profile buckets must partition TaxpayerProfile; missing={missing} extra={extra}")
        return self
