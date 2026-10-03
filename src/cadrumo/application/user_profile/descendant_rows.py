"""Atomic replacement of a profile's declared descendant family."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field, field_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import GovernedFactSource, validating_governed_facts
from ...domain.contribuyente.descendant import DescendantInfo
from ...domain.contribuyente.descendant_facts import descendant_facts_from_list, descendant_list_from_facts
from ...domain.user_profile.errors import UserProfileValidationError
from ...domain.user_profile.values import UserProfileFact, UserProfileRecord
from .capsule_record import ProfileRecordConflictError
from .fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
from .profile_record_repository import ProfileRecordRepository


class ProfileDescendantFact(BaseModel):
    """One canonical descendant field token and private textual value."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    field_key: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=96)
    value: str = Field(min_length=1, max_length=4096, repr=False)


class ProfileDescendantRow(BaseModel):
    """A complete row whose vocabulary is validated by the execution authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    facts: tuple[ProfileDescendantFact, ...] = Field(min_length=1, max_length=96, repr=False)

    @field_validator("facts")
    @classmethod
    @pydantic_validation_boundary
    def _distinct_fields(cls, facts: tuple[ProfileDescendantFact, ...]) -> tuple[ProfileDescendantFact, ...]:
        if len({fact.field_key for fact in facts}) != len(facts):
            raise ValueError("descendant row must not repeat a field")
        return facts


def encode_descendant_rows(
    descendants: tuple[DescendantInfo, ...], *, authority: GovernedFactSource
) -> tuple[ProfileDescendantRow, ...]:
    """Project canonical domain records to strict public operation row values."""
    return tuple(
        ProfileDescendantRow(
            facts=tuple(
                ProfileDescendantFact(field_key=path.removeprefix("renta_family.descendiente.0."), value=value)
                for path, value in descendant_facts_from_list((row,), authority=authority)
                if path.startswith("renta_family.descendiente.0.")
            )
        )
        for row in descendants
    )


@dataclass(frozen=True, slots=True)
class DescendantFamilyMutation:
    """Published revision and actual change, without duplicating private rows."""

    record: UserProfileRecord
    total: int
    changed: bool


def replace_profile_descendants(
    *,
    profile_id: str,
    descendants: tuple[ProfileDescendantRow, ...],
    expected_revision: int,
    expected_content_digest: ContentDigest,
    operation: PinnedAuthorityOperation,
) -> DescendantFamilyMutation:
    """Validate and replace the whole family against one exact custody revision.

    The count and orphaned optional/indexed fields belong to the same write.
    Revalidation uses the execution owner's authority even when the frontend
    has already constructed domain records under another publication.
    """
    decode = operation.profile_decode_context()
    current = ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=decode).load(profile_id)
    if current.record_revision != expected_revision or current.content_digest != expected_content_digest:
        raise ProfileRecordConflictError("descendant family replacement baseline is stale")
    with validating_governed_facts(operation):
        supplied = {
            f"renta_family.descendiente.{index}.{fact.field_key}": fact.value
            for index, row in enumerate(descendants)
            for fact in row.facts
        }
        validated = descendant_list_from_facts(supplied, authority=operation)
        pairs = dict(descendant_facts_from_list(validated, authority=operation))
        # Unknown fields, omitted birth dates and noncanonical values must not
        # disappear when the domain decoder constructs its supported record.
        if len(validated) != len(descendants) or any(pairs.get(path) != value for path, value in supplied.items()):
            raise UserProfileValidationError("descendant replacement contains unsupported or noncanonical facts")
        stale_paths = {
            fact.path
            for fact in current.facts
            if fact.path.startswith("renta_family.descendiente.") or fact.path == "renta_family.descendientes_count"
        }
        changes = (
            *(UserProfileFact(path=path, value=None) for path in sorted(stale_paths - pairs.keys())),
            *(UserProfileFact(path=path, value=value) for path, value in pairs.items()),
        )
        published = apply_profile_fact_changes(
            profile_id=profile_id,
            changes=changes,
            door=ProfileFactWriteDoor.MANAGER_DESCENDANTS,
            expected_record=current,
            profile_decode_context=decode,
        )
    return DescendantFamilyMutation(
        record=published,
        total=len(validated),
        changed=published.record_revision != current.record_revision,
    )
