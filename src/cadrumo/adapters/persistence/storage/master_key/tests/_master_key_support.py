from __future__ import annotations

from pathlib import Path

from ...tests.registered_bucket import publish_registration_capsule

# Stable bucket identities for the provider suites. A bucket id is a profile
# UUID: registration is proven by the published capsule named for it, so a
# non-UUID label can never name a registered bucket.
_ALPHA = "0a1a0000-0000-4000-8000-000000000001"
_TORN = "0a1a0000-0000-4000-8000-000000000002"
_CURRENT = "0a1a0000-0000-4000-8000-000000000003"
_MISSING = "0a1a0000-0000-4000-8000-000000000004"
_ORPHANED = "0a1a0000-0000-4000-8000-000000000005"
_SHORT_IDLE = "0a1a0000-0000-4000-8000-000000000006"
_SHORT_CAP = "0a1a0000-0000-4000-8000-000000000007"
_DEFAULT_CAP = "0a1a0000-0000-4000-8000-000000000008"
_PROVIDER_REOPEN = "0a1a0000-0000-4000-8000-000000000009"
_PROVIDER_READ_CONCURRENCY = "0a1a0000-0000-4000-8000-00000000000a"


def _write_registered_bucket(root: Path, bucket_id: str) -> None:
    """Register a bucket the way production does: publish its capsule, nothing else.

    This wrote a plaintext manifest beside the capsule until that format was
    retired. Nothing in production ever read it back, so provisioning one here
    handed the tests a surface the application does not have.
    """
    # Publication owns the bucket directory: it arrives by the capsule's
    # no-replace rename, never by provisioning it first.
    publish_registration_capsule(root, bucket_id)
