"""Inward contract tests for explicit configuration-reset confirmation."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.application.config_reset import (
    ConfigResetConfirmationRequiredError,
    resume_config_reset,
    start_config_reset,
)
from cadrumo.application.user_profile.custody_ports import (
    ProfileBucketStoragePathsPort,
    ProfileBucketStoragePort,
)

from ._operator_scope_fakes import build_inward_operator_scope_ports_for_active_route

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _NeverReachedBucketStorage:
    """Inward fake proving confirmation is checked before storage access."""

    def resolve(self, root: Path, bucket_id: str) -> ProfileBucketStoragePathsPort:
        del root, bucket_id
        raise AssertionError("confirmation refusal must precede bucket resolution")

    def acquire_lock(self, paths: ProfileBucketStoragePathsPort, *, wait_seconds: float) -> None:
        del paths, wait_seconds
        raise AssertionError("confirmation refusal must precede bucket locking")

    def release_lock(self, paths: ProfileBucketStoragePathsPort) -> None:
        del paths
        raise AssertionError("confirmation refusal must precede bucket unlocking")


def test_start_and_resume_require_explicit_confirmation() -> None:
    """Both reset doors reject an unconfirmed destructive operation inwardly."""
    certificate_secret_backend_factory = InMemoryCertificateSecretBackendFactory()
    operator_scope_ports = build_inward_operator_scope_ports_for_active_route()
    bucket_storage: ProfileBucketStoragePort = _NeverReachedBucketStorage()

    with pytest.raises(ConfigResetConfirmationRequiredError):
        start_config_reset(
            confirmed=False,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=operator_scope_ports,
            bucket_storage=bucket_storage,
        )
    with pytest.raises(ConfigResetConfirmationRequiredError):
        resume_config_reset(
            "a" * 64,
            confirmed=False,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=operator_scope_ports,
            bucket_storage=bucket_storage,
        )
