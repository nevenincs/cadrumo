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

from ....core import scan_directory
from ....domain.buckets import BucketEventType

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_AEAT_ROOT = Path(__file__).resolve().parents[3]


_REQUIRED_EMISSION_SITES: tuple[tuple[BucketEventType, Path, str], ...] = (
    (
        BucketEventType.PROFILE_BUCKET_CREATED,
        _AEAT_ROOT / "application" / "user_profile" / "_capsule_record.py",
        "BucketEventType.PROFILE_BUCKET_CREATED",
    ),
    (
        BucketEventType.PROFILE_ACTIVATED,
        _AEAT_ROOT / "application" / "user_profile" / "_login_session.py",
        "BucketEventType.PROFILE_ACTIVATED",
    ),
    (
        BucketEventType.AUTH_PROVIDER_CONFIGURED,
        _AEAT_ROOT / "application" / "auth" / "_operator.py",
        "BucketEventType.AUTH_PROVIDER_CONFIGURED",
    ),
)


def test_required_setup_events_have_emission_sites() -> None:
    """Each required setup event must appear in its declared production module."""
    for event_type, module_path, needle in _REQUIRED_EMISSION_SITES:
        assert module_path.is_file(), (
            f"{event_type.value} declares emission site {module_path} which does not exist; "
            "a declared site that is gone reads as a stale contract, not a passing one."
        )
        text = module_path.read_text(encoding="utf-8")
        assert needle in text, (
            f"{event_type.value} emission site missing from {module_path.name}; "
            f"expected token {needle!r} but it was not found. Either restore the "
            f"emission or update the setup-event contract in this gate."
        )


_PRODUCTION_ROOTS: tuple[Path, ...] = (
    _AEAT_ROOT / "application",
    _AEAT_ROOT / "adapters",
    _AEAT_ROOT / "entrypoints",
    _AEAT_ROOT / "domain",
)

_EVENTS_WITH_NO_PRODUCTION_EMITTER: tuple[BucketEventType, ...] = (BucketEventType.PROFILE_VALUES_UPDATED,)
"""Catalogue members no production path emits today.

``PROFILE_VALUES_UPDATED`` names the operator action "profile values were
updated", and the operator-facing edit path does write facts — but it stamps
its own un-catalogued event-type strings (``profile.wizard.answers.applied``,
``profile.wizard.patch.applied``) rather than this member, so the catalogued
event never reaches a bucket. The only writer left is test seeding.

Asserting the gap rather than deleting the row keeps it visible: the test below
FAILS the moment a production emitter appears, which is the prompt to promote
the row back into ``_REQUIRED_EMISSION_SITES`` with its real site.
"""


def _production_files() -> tuple[Path, ...]:
    return tuple(
        path
        for root in _PRODUCTION_ROOTS
        for path in scan_directory(root, pattern="*.py", recursive=True)
        if "tests" not in path.parts
    )


def test_events_with_no_production_emitter_are_still_unemitted() -> None:
    """A tracked emission gap must stay tracked, or be promoted when it closes."""
    files = _production_files()
    # Floor the corpus: a package relocation would empty this walk and make the
    # gap assertion pass by scanning nothing.
    assert len(files) > 200, (
        f"scanned only {len(files)} production modules under {_PRODUCTION_ROOTS}; "
        "the scan corpus collapsed, so 'no emitter found' would mean 'nothing was checked'"
    )
    for event_type in _EVENTS_WITH_NO_PRODUCTION_EMITTER:
        needle = f"BucketEventType.{event_type.name}"
        emitters = [str(path) for path in files if needle in path.read_text(encoding="utf-8")]
        assert emitters == [], (
            f"{event_type.value} now has production emitter(s) {emitters}; the gap closed. "
            f"Move {event_type.name} out of _EVENTS_WITH_NO_PRODUCTION_EMITTER and into "
            "_REQUIRED_EMISSION_SITES naming that module, so the emission is pinned."
        )


# The PROFILE_BUCKET_CREATED event covers both bucket.created and
# profile.created semantics. The same setup operation writes the bucket
# directory and the inaugural profile record in one atomic create
# span, so a single event captures the pair. Documented here so a
# future change does not add a duplicate PROFILE_CREATED slot.
_RESERVED_EVENTS_WITHOUT_OPERATOR_PATHS: tuple[BucketEventType, ...] = (BucketEventType.CONFIG_ENV_UPDATED,)


def test_reserved_events_remain_in_the_closed_catalogue() -> None:
    """Reserved setup events keep stable catalogue slots until operator paths exist."""
    for event in _RESERVED_EVENTS_WITHOUT_OPERATOR_PATHS:
        assert event.value, f"{event.name} is missing its catalogue value"
