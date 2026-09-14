"""Persistence adapter for the application profile path projection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import override

from pydantic import ValidationError

from ....application.persistence_errors import PersistenceDegradationError
from ....application.user_profile.profile_read_ports import ProfilePathValuesReadPort
from ....application.user_profile.profile_record_repository import ProfileRecordRepository
from ....application.user_profile.projections import record_to_path_values
from ....domain.user_profile.errors import ProfileNotFoundError, UserProfileError
from ..storage.errors import StorageError


class ProfilePathValuesPersistenceAdapter(ProfilePathValuesReadPort):
    """Translate the authenticated profile-record repository into path values."""

    def __init__(self, *, repository: ProfileRecordRepository) -> None:
        """Bind the already composed, session-bound profile record authority."""
        self._repository = repository

    @override
    def load_path_values(self, *, bucket_id: str) -> Mapping[str, str] | None:
        """Read one profile projection and translate persistence failures inward."""
        try:
            record = self._repository.load(bucket_id)
        except ProfileNotFoundError:
            return None
        except (StorageError, OSError, UserProfileError, ValidationError, UnicodeDecodeError) as exc:
            raise PersistenceDegradationError("profile_path_values_load") from exc
        return record_to_path_values(record)


__all__ = ["ProfilePathValuesPersistenceAdapter"]
