"""Inward contract tests for explicit configuration-reset confirmation."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.application.config_reset import (
    ConfigResetConfirmationRequiredError,
    ConfigResetRequestProblem,
    ConfigResetRequestRefusedError,
    normalise_retention_override,
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


@pytest.mark.parametrize(
    ("acknowledged", "reason", "expected"),
    [
        (False, None, (False, None)),
        (False, "   ", (False, None)),
        (True, "  Court order.  ", (True, "Court order.")),
    ],
)
def test_a_retention_override_is_accepted_only_with_its_reason_and_the_reason_is_trimmed(
    acknowledged: bool, reason: str | None, expected: tuple[bool, str | None]
) -> None:
    assert (
        tuple(
            normalise_retention_override(acknowledge_retention_override=acknowledged, retention_override_reason=reason)
        )
        == expected
    )


@pytest.mark.parametrize(
    ("acknowledged", "reason", "problem"),
    [
        (True, None, ConfigResetRequestProblem.OVERRIDE_REASON_REQUIRED),
        (True, "   ", ConfigResetRequestProblem.OVERRIDE_REASON_REQUIRED),
        (False, "Court order.", ConfigResetRequestProblem.OVERRIDE_REASON_WITHOUT_OVERRIDE),
    ],
)
def test_an_override_without_a_reason_and_a_reason_without_an_override_are_refused(
    acknowledged: bool, reason: str | None, problem: ConfigResetRequestProblem
) -> None:
    with pytest.raises(ConfigResetRequestRefusedError) as refused:
        normalise_retention_override(acknowledge_retention_override=acknowledged, retention_override_reason=reason)

    assert refused.value.problem is problem
