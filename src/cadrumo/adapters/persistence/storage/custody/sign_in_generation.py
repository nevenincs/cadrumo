"""Durable per-profile human sign-in generation, kept outside the encrypted bucket.

The generation is the revocation fence for the persisted human sign-in receipt.
A receipt is usable only while it carries the current generation, so revocation
holds even when deleting the receipt fails. The record lives in the profile's
keystore beside the receipt, needs no DEK, and holds no secret or tax data.

A generation is a pair: a random ``lineage`` and a counter within it. Advancing
keeps the lineage and increments the counter. Whenever no trustworthy record
exists (missing, unreadable, or bound to other custody), a write starts a fresh
lineage instead of guessing a counter. No earlier receipt can carry a lineage
minted after it, so recreating the record never revives one; a missing record
is never read as a starting value.

Every operation runs under the profile custody root lock, the first lock in the
custody lock order, so callers may nest the receipt lock inside it. Each write
fsyncs the record (and, on POSIX, its directory) before returning, so a caller
deletes a receipt only after the fence that revokes it is durable.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from .....application.user_profile.access_contracts import ProfileAccessBinding
from .....application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from .....core.identity.profile import canonical_profile_bucket_id
from .....core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..bucket.keystore_paths import keystore_sidecar_path
from ..storage_path_definitions import SIGN_IN_GENERATION_FILENAME
from .automation_crypto import canonical_record, parse_record
from .automation_profile import validate_automation_profile_binding
from .errors import ProfileCustodyRecordError
from .filesystem import (
    profile_custody_root_lock,
    read_optional_profile_custody_local_record,
    write_profile_custody_local_record,
)
from .filesystem_primitives import ensure_profile_custody_local_directory

MAX_SIGN_IN_GENERATION_BYTES: Final = 4096
"""Ceiling for one canonical record; a real record is a few hundred bytes."""


class SignInGeneration(BaseModel):
    """One position in a profile's sign-in sequence; a receipt binds both fields."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    lineage: UUID
    generation: Annotated[int, Field(ge=1)]


class SignInGenerationRecord(BaseModel):
    """The persisted record, bound to the custody it fences."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    schema_version: Literal[1] = 1
    binding: ProfileAccessBinding
    current: SignInGeneration


class SignInGenerationState(StrEnum):
    """What a read found; every state except ``PRESENT`` refuses receipt resume."""

    PRESENT = "present"
    MISSING = "missing"
    UNREADABLE = "unreadable"
    BINDING_MISMATCH = "binding_mismatch"


class SignInGenerationObservation(BaseModel):
    """A read outcome that carries a generation only when one was proven."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    state: SignInGenerationState
    current: SignInGeneration | None = None

    @model_validator(mode="after")
    def _generation_only_when_present(self) -> SignInGenerationObservation:
        if (self.state is SignInGenerationState.PRESENT) != (self.current is not None):
            raise ValueError("a sign-in generation is carried exactly when the record is present")
        return self


class SignInGenerationChange(StrEnum):
    """What a durable write did to the record."""

    UNCHANGED = "unchanged"
    CREATED = "created"
    ADVANCED = "advanced"
    REPLACED = "replaced"


class SignInGenerationWrite(BaseModel):
    """A completed, fsynced write and the state it started from."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    change: SignInGenerationChange
    prior: SignInGenerationState
    current: SignInGeneration


def sign_in_generation_path(*, storage_root: Path, profile_id: UUID) -> Path:
    """Return ``<root>/keystore/<profile>/sign-in-generation.json``."""
    return keystore_sidecar_path(
        storage_root=storage_root,
        bucket_id=canonical_profile_bucket_id(profile_id),
        filename=SIGN_IN_GENERATION_FILENAME,
    )


class SignInGenerationCustody:
    """Own one profile's sign-in generation record for one custody binding."""

    def __init__(self, *, root: Path, binding: ProfileAccessBinding) -> None:
        """Bind trusted composition to one storage root and custody binding."""
        if not root.is_absolute():
            raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
        self.root = root
        self.binding = binding
        self.path = sign_in_generation_path(storage_root=root, profile_id=binding.profile_id)

    def observe(self) -> SignInGenerationObservation:
        """Read the current generation without writing anything.

        Raises:
            ProfileCustodyRecordError: When the custody root lock cannot be held.
        """
        with profile_custody_root_lock(self.root):
            return self._observe()

    def establish(self) -> SignInGenerationWrite:
        """Return the current generation, durably creating the record if needed.

        A readable record bound to this custody is returned unchanged. Any other
        state starts a fresh lineage, which also revokes every receipt bound to
        an earlier one.

        Raises:
            AutomationCustodyError: When this binding is not the committed custody.
            ProfileCustodyRecordError: When the record cannot be durably written.
        """
        with profile_custody_root_lock(self.root):
            validate_automation_profile_binding(self.binding, root=self.root)
            observed = self._observe()
            if observed.current is not None:
                return SignInGenerationWrite(
                    change=SignInGenerationChange.UNCHANGED, prior=observed.state, current=observed.current
                )
            return self._start_lineage(observed.state)

    def advance(self) -> SignInGenerationWrite:
        """Durably move past every generation issued so far, then return.

        Callers delete a receipt only after this returns.

        Raises:
            AutomationCustodyError: When this binding is not the committed custody.
            ProfileCustodyRecordError: When the record cannot be durably written.
        """
        with profile_custody_root_lock(self.root):
            validate_automation_profile_binding(self.binding, root=self.root)
            observed = self._observe()
            if observed.current is None:
                return self._start_lineage(observed.state)
            current = SignInGeneration(lineage=observed.current.lineage, generation=observed.current.generation + 1)
            self._publish(current, once=False)
            return SignInGenerationWrite(change=SignInGenerationChange.ADVANCED, prior=observed.state, current=current)

    def _observe(self) -> SignInGenerationObservation:
        try:
            raw = read_optional_profile_custody_local_record(self.path, maximum_bytes=MAX_SIGN_IN_GENERATION_BYTES)
        except ProfileCustodyRecordError:
            if not self._keystore_directory_absent():
                return SignInGenerationObservation(state=SignInGenerationState.UNREADABLE)
            raw = None
        except OSError:
            return SignInGenerationObservation(state=SignInGenerationState.UNREADABLE)
        if raw is None:
            return SignInGenerationObservation(state=SignInGenerationState.MISSING)
        try:
            record = parse_record(SignInGenerationRecord, raw)
        except AutomationCustodyError:
            return SignInGenerationObservation(state=SignInGenerationState.UNREADABLE)
        if record.binding != self.binding:
            return SignInGenerationObservation(state=SignInGenerationState.BINDING_MISMATCH)
        return SignInGenerationObservation(state=SignInGenerationState.PRESENT, current=record.current)

    def _keystore_directory_absent(self) -> bool:
        # A profile that never signed in has no keystore directory, and the
        # anchored reader refuses a missing parent rather than reporting the
        # leaf absent. Only a positively absent directory reads as MISSING;
        # anything else at that path stays UNREADABLE.
        for directory in (self.path.parent.parent, self.path.parent):
            try:
                directory.lstat()
            except FileNotFoundError:
                return True
            except OSError:
                return False
        return False

    def _start_lineage(self, prior: SignInGenerationState) -> SignInGenerationWrite:
        current = SignInGeneration(lineage=uuid4(), generation=1)
        missing = prior is SignInGenerationState.MISSING
        self._publish(current, once=missing)
        change = SignInGenerationChange.CREATED if missing else SignInGenerationChange.REPLACED
        return SignInGenerationWrite(change=change, prior=prior, current=current)

    def _publish(self, current: SignInGeneration, *, once: bool) -> None:
        ensure_profile_custody_local_directory(self.path.parent.parent)
        ensure_profile_custody_local_directory(self.path.parent)
        raw = canonical_record(SignInGenerationRecord(binding=self.binding, current=current))
        write_profile_custody_local_record(self.path, raw, publish_once=once)
