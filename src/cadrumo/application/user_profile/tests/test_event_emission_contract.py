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

from ....core.directory_scan import scan_directory
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
    (
        BucketEventType.PROFILE_VALUES_UPDATED,
        _AEAT_ROOT / "application" / "user_profile" / "_fact_write.py",
        # The needle names the EMISSION, not the bare symbol. The emitting
        # module also cross-links this member in prose, and a bare-symbol
        # needle is satisfied by that prose alone -- so reverting the stamp
        # to the surface string it used to carry left this gate green.
        "event_type=BucketEventType.PROFILE_VALUES_UPDATED,",
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

_EVENTS_WITH_NO_PRODUCTION_EMITTER: tuple[BucketEventType, ...] = ()
"""Catalogue members no production path emits today. Currently none.

``PROFILE_VALUES_UPDATED`` was tracked here, on the reading that the wizard
edit path merely stamped "un-catalogued" event-type strings
(``profile.wizard.answers.applied``, ``profile.wizard.patch.applied``) instead
of this member. That reading understated the defect and pointed at the wrong
repair. The strings were not uncatalogued-but-serviceable: ``BucketEventType``
is closed, the capsule writer coerces the command's event type through it, and
a non-member raised — so every wizard fact write refused with an internal
integrity error and NOTHING was recorded. Cataloguing those strings would have
enshrined a surface verb in a slot that holds exactly one event per record
revision and binds the row's lineage witness, which is the data-change slot.
The profile-fact write door now emits this member and carries the surface in a
``door`` payload key, so the gap is closed by repair rather than by taxonomy
growth. That door was later relocated out of the wizard into
``user_profile/_fact_write.py``, which is why the site above names that module
rather than the wizard persistence adapter the defect was first found in.

The mechanism stays for the next genuine gap: while this tuple is empty the
loop below is vacuous by design, and the corpus floor is what keeps that
vacuity honest rather than an artefact of a collapsed scan.
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
