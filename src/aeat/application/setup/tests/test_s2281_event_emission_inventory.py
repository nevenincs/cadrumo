"""Closure gate for W83.P400.S2281 setup-event emission inventory.

The plan Step W83.P400.S2281 names five required events that MUST be
wired from operator-facing setup paths, plus two optional events
deferred until an env-management / setup-migration verb exists. This
gate pins the file:symbol identity of each required emission site so
a future refactor cannot silently drop one; the optional pair is
documented as dormant with no current operator path.

If this test fails because a production module renamed a symbol,
update the expected file or move the emission to a new module — do
NOT delete the assertion. The Step's contract is that these five
events surface on every operator action they describe.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....domain.buckets import BucketEventType

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_AEAT_ROOT = Path(__file__).resolve().parents[2]


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
def test_required_setup_event_has_emission_site(
    event_type: BucketEventType, module_path: Path, needle: str
) -> None:
    """Each required S2281 event MUST appear in its declared production module."""
    text = module_path.read_text(encoding="utf-8")
    assert needle in text, (
        f"{event_type.value} emission site missing from {module_path.name}; "
        f"expected token {needle!r} but it was not found. Either restore the "
        f"emission or update the S2281 inventory in this gate."
    )


# The PROFILE_BUCKET_CREATED event covers both bucket.created and
# profile.created semantics — the same Step writes the bucket
# directory and the inaugural profile record in one atomic create
# span, so a single event captures the pair. The plan row names
# them as two events for plan readability; the implementation
# consolidates them in the lifecycle service. Documented here so a
# future agent does not look for a separate PROFILE_CREATED slot
# and add a duplicate.
_DORMANT_OPTIONAL_EVENTS: tuple[BucketEventType, ...] = (
    BucketEventType.CONFIG_ENV_UPDATED,
    BucketEventType.SETUP_STATE_MIGRATED,
)


def test_dormant_optional_events_remain_in_the_closed_catalogue() -> None:
    """The two optional S2281 events have no operator path today but the
    closed catalogue keeps their slots reserved so a future
    env-management or setup-migration verb can wire them without
    re-litigating the enum design. Audit-trail note lives at
    ``.vault/audit/2026-06-03-cli-workflow-redesign-S2281-emission-inventory-audit.md``.
    """
    for event in _DORMANT_OPTIONAL_EVENTS:
        assert event.value, f"{event.name} is missing its catalogue value"
