"""Real adapter exports for review-package persistence tests."""

from __future__ import annotations

from ..adapters.persistence.storage import (
    MODELO_REVIEW_PACKAGE_RECIPIENT_ENCRYPTION_KEY_NAMESPACE,
    MODELO_REVIEW_PACKAGE_RECIPIENT_FINGERPRINT_REGISTRY_NAMESPACE,
    MODELO_REVIEW_PACKAGE_RECIPIENT_REPLAY_GUARD_NAMESPACE,
    MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE,
    DecryptionError,
    SensitivityClass,
)
from ..adapters.persistence.storage.sql import SecureObjectRow
from ..adapters.persistence.storage.sql.session import session_scope

__all__ = [
    "MODELO_REVIEW_PACKAGE_RECIPIENT_ENCRYPTION_KEY_NAMESPACE",
    "MODELO_REVIEW_PACKAGE_RECIPIENT_FINGERPRINT_REGISTRY_NAMESPACE",
    "MODELO_REVIEW_PACKAGE_RECIPIENT_REPLAY_GUARD_NAMESPACE",
    "MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE",
    "DecryptionError",
    "SecureObjectRow",
    "SensitivityClass",
    "session_scope",
]
