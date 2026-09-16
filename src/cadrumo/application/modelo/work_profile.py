"""The decrypted profile one modelo work command carries through its call chain."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext
    from ...domain.user_profile.values import UserProfileRecord


@dataclass(frozen=True, slots=True)
class ModeloWorkProfile:
    """One authenticated profile record and the decode context its session used.

    A command loads this once for its target bucket and hands the same value to
    every gate, resolver and advisory it runs, instead of each of them
    decrypting the same unchanged record again.
    """

    record: UserProfileRecord
    profile_decode_context: ProfileDecodeContext


@dataclass(frozen=True, slots=True)
class ModeloWorkProfilePathValues:
    """Serve the path-keyed projection of an already-loaded work profile.

    Satisfies :class:`~application.user_profile.profile_read_ports.ProfilePathValuesReadPort`
    with the same absence semantics as the session-bound persistence reader:
    a bucket other than the loaded profile's own has no profile here.
    """

    profile: ModeloWorkProfile

    def load_path_values(self, *, bucket_id: str) -> Mapping[str, str] | None:
        """Return the loaded record's path values, or ``None`` for any other bucket."""
        from ..user_profile.projections import record_to_path_values

        record = self.profile.record
        if UUID(str(bucket_id)) != UUID(str(record.profile_id)):
            return None
        return record_to_path_values(record)


__all__ = ["ModeloWorkProfile", "ModeloWorkProfilePathValues"]
