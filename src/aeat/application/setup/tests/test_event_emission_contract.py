"""Setup-event emission contract tests.

Required bucket events must be wired from the operator-facing setup
paths that create profiles, activate profiles, update profile values,
and configure authentication providers. This gate pins the file:symbol
identity of each required emission site so a future refactor cannot
silently drop one.

If this test fails because a production module renamed a symbol,
update the expected file or move the emission to a new module — do
NOT delete the assertion. The contract is that these events surface
on every operator action they describe.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....domain.buckets import BucketEventType

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_AEAT_ROOT = Path(__file__).resolve().parents[3]


_REQUIRED_EMISSION_SITES: tuple[tuple[BucketEventType, Path, str], ...] = (
    (
        BucketEventType.PROFILE_BUCKET_CREATED,
        _AEAT_ROOT / "application" / "user_profile" / "_lifecycle.py",
        "BucketEventType.PROFILE_BUCKET_CREATED",
    ),
    (
        BucketEventType.PROFILE_ACTIVATED,
        _AEAT_ROOT / "application" / "user_profile" / "_orchestration.py",
        "BucketEventType.PROFILE_ACTIVATED",
    ),
    (
        BucketEventType.PROFILE_VALUES_UPDATED,
        _AEAT_ROOT / "application" / "user_profile" / "_lifecycle.py",
        "BucketEventType.PROFILE_VALUES_UPDATED",
    ),
    (
        BucketEventType.AUTH_PROVIDER_CONFIGURED,
        _AEAT_ROOT / "application" / "auth" / "_operator.py",
        "BucketEventType.AUTH_PROVIDER_CONFIGURED",
    ),
)


@pytest.mark.parametrize(
    ("event_type", "module_path", "needle"),
    _REQUIRED_EMISSION_SITES,
    ids=[event.value for event, _, _ in _REQUIRED_EMISSION_SITES],
)
def test_required_setup_event_has_emission_site(event_type: BucketEventType, module_path: Path, needle: str) -> None:
    """Each required setup event must appear in its declared production module."""
    text = module_path.read_text(encoding="utf-8")
    assert needle in text, (
        f"{event_type.value} emission site missing from {module_path.name}; "
        f"expected token {needle!r} but it was not found. Either restore the "
        f"emission or update the setup-event contract in this gate."
    )


# The PROFILE_BUCKET_CREATED event covers both bucket.created and
# profile.created semantics. The same setup operation writes the bucket
# directory and the inaugural profile record in one atomic create
# span, so a single event captures the pair. Documented here so a
# future change does not add a duplicate PROFILE_CREATED slot.
_RESERVED_EVENTS_WITHOUT_OPERATOR_PATHS: tuple[BucketEventType, ...] = (
    BucketEventType.CONFIG_ENV_UPDATED,
    BucketEventType.SETUP_STATE_MIGRATED,
)


def test_reserved_events_remain_in_the_closed_catalogue() -> None:
    """Reserved setup events keep stable catalogue slots until operator paths exist."""
    for event in _RESERVED_EVENTS_WITHOUT_OPERATOR_PATHS:
        assert event.value, f"{event.name} is missing its catalogue value"
