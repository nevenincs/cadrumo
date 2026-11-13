"""Pure records for the profile facts a calculation revision actually read.

A saved calculation states casillas the profile decided, and the profile can be
edited afterwards. These records hold which fact paths (or whole sections, for a
read that enumerated one) the calculation read, and a digest per read over the
typed value it had. No fact value is stored beside the revision, only digests.

A read is taken from one of three places. The profile resolver reads its
derived fact index, where a derived selector (the Art. 58 aggregate) is a path
of its own. Most other readers read the stored record, and a record read's
digest covers every dated fact at the path, so an edit to a fact's window is a
change as much as an edit to its value. A whole-record projection, such as the
taxpayer projection every gate and deadline reads, is digested over what it
produced, so only an edit that changes its result is a change.

The recording and the recomputation live in
:mod:`application.modelo.profile_read_recording` and
:mod:`application.user_profile.profile_read_recorder`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel

from ...core.hashing import sha256_hex
from ...core.identity.hex_ids import SnapshotId
from ...core.models import STRICT_FROZEN_CONFIG
from ..user_profile.values import UserProfileFact, UserProfileFactValue

PROFILE_READ_FIELD_SET_VERSION = 1
"""How a read's digest is formed; a stored digest is only comparable under its own version."""


class ProfileReadScope(StrEnum):
    """Whether a read named one fact path or enumerated every path under a prefix."""

    PATH = "path"
    PREFIX = "prefix"


class ProfileReadSource(StrEnum):
    """Where a read was taken: the resolver's derived fact index or the stored record."""

    INDEX = "index"
    RECORD = "record"
    PROJECTION = "projection"


class ProfileReadEntry(BaseModel):
    """One read the calculation made and the digest of what it saw."""

    model_config = STRICT_FROZEN_CONFIG

    scope: ProfileReadScope
    selector: str
    fingerprint: SnapshotId
    source: ProfileReadSource = ProfileReadSource.INDEX


class ProfileReadFingerprint(BaseModel):
    """The profile reads a revision's calculation made, each with its value digest.

    Empty ``entries`` is a real statement: the calculation read no profile fact,
    so no profile edit can make it stale. A revision whose field is ``None`` was
    calculated before reads were recorded and proves nothing either way.

    Attributes:
        profile_present: Whether a profile record existed when it was calculated.
        entries: Per-read digests, sorted by source, scope and selector.
        snapshot_fingerprint: SHA-256 hex over the sorted entries and presence.
        field_set_version: How the digests were formed.
    """

    model_config = STRICT_FROZEN_CONFIG

    profile_present: bool
    entries: tuple[ProfileReadEntry, ...] = ()
    snapshot_fingerprint: SnapshotId
    field_set_version: int


def _canonical_value(value: UserProfileFactValue) -> str:
    # ``bool`` before ``int``: a truth value is a different fact from the number one.
    if value is None:
        return "none"
    if isinstance(value, bool):
        return f"bool:{str(value).lower()}"
    if isinstance(value, Decimal):
        return f"decimal:{format(value.normalize(), 'f')}"
    if isinstance(value, int):
        return f"int:{value}"
    if isinstance(value, date):
        return f"date:{value.isoformat()}"
    return f"str:{value}"


def profile_path_read_fingerprint(facts: Mapping[str, UserProfileFactValue], path: str) -> SnapshotId:
    """Digest one path's typed value, an absent path being distinct from a ``None`` value."""
    canonical = _canonical_value(facts[path]) if path in facts else "absent"
    return sha256_hex(f"{path}={canonical}".encode())


def profile_prefix_read_fingerprint(facts: Mapping[str, UserProfileFactValue], prefix: str) -> SnapshotId:
    """Digest every path under ``prefix`` with its typed value, in path order."""
    canonical = "\n".join(
        f"{path}={_canonical_value(value)}" for path, value in sorted(facts.items()) if path.startswith(prefix)
    )
    return sha256_hex(f"{prefix}*\n{canonical}".encode())


def profile_read_entry(
    facts: Mapping[str, UserProfileFactValue], scope: ProfileReadScope, selector: str
) -> ProfileReadEntry:
    """Return the entry for one recorded read of the derived fact index."""
    fingerprint = (
        profile_path_read_fingerprint(facts, selector)
        if scope is ProfileReadScope.PATH
        else profile_prefix_read_fingerprint(facts, selector)
    )
    return ProfileReadEntry(scope=scope, selector=selector, fingerprint=fingerprint)


def _window_bound(bound: date | None) -> str:
    return "-" if bound is None else bound.isoformat()


def _canonical_fact(fact: UserProfileFact) -> str:
    window = f"{_window_bound(fact.valid_from)}..{_window_bound(fact.valid_to)}"
    return f"{fact.path}@{window}={_canonical_value(fact.value)}"


def _covers(scope: ProfileReadScope, selector: str, path: str) -> bool:
    return path == selector if scope is ProfileReadScope.PATH else path.startswith(selector)


def profile_record_read_fingerprint(
    facts: Iterable[UserProfileFact], scope: ProfileReadScope, selector: str
) -> SnapshotId:
    """Digest every stored fact a record read covers, each with its window, in a stable order."""
    canonical = "\n".join(sorted(_canonical_fact(fact) for fact in facts if _covers(scope, selector, fact.path)))
    return sha256_hex(f"{scope.value}:{selector}\n{canonical}".encode())


def profile_record_read_entry(
    facts: Iterable[UserProfileFact], scope: ProfileReadScope, selector: str
) -> ProfileReadEntry:
    """Return the entry for one recorded read of the stored record."""
    return ProfileReadEntry(
        scope=scope,
        selector=selector,
        fingerprint=profile_record_read_fingerprint(facts, scope, selector),
        source=ProfileReadSource.RECORD,
    )


def profile_projection_read_entry(selector: str, fingerprint: SnapshotId) -> ProfileReadEntry:
    """Return the entry for one whole-record projection, digested over what it produced."""
    return ProfileReadEntry(
        scope=ProfileReadScope.PATH,
        selector=selector,
        fingerprint=fingerprint,
        source=ProfileReadSource.PROJECTION,
    )


def _entry_key(entry: ProfileReadEntry) -> tuple[str, str, str]:
    return (entry.source.value, entry.scope.value, entry.selector)


def profile_read_fingerprint(*, profile_present: bool, entries: tuple[ProfileReadEntry, ...]) -> ProfileReadFingerprint:
    """Seal the entries into one order-independent fingerprint."""
    ordered = tuple(sorted({_entry_key(entry): entry for entry in entries}.values(), key=_entry_key))
    canonical = "\n".join(
        (
            f"present={profile_present}",
            *(f"{entry.source.value}:{entry.scope.value}:{entry.selector}={entry.fingerprint}" for entry in ordered),
        )
    )
    return ProfileReadFingerprint(
        profile_present=profile_present,
        entries=ordered,
        snapshot_fingerprint=sha256_hex(canonical.encode()),
        field_set_version=PROFILE_READ_FIELD_SET_VERSION,
    )


def changed_profile_reads(recorded: ProfileReadFingerprint, current: ProfileReadFingerprint) -> tuple[str, ...]:
    """Return the selectors whose digest moved, or every recorded selector when presence moved."""
    if recorded.profile_present != current.profile_present:
        return tuple(dict.fromkeys(entry.selector for entry in recorded.entries)) or ("",)
    now = {_entry_key(entry): entry.fingerprint for entry in current.entries}
    return tuple(
        dict.fromkeys(entry.selector for entry in recorded.entries if now.get(_entry_key(entry)) != entry.fingerprint)
    )


__all__ = [
    "PROFILE_READ_FIELD_SET_VERSION",
    "ProfileReadEntry",
    "ProfileReadFingerprint",
    "ProfileReadScope",
    "ProfileReadSource",
    "changed_profile_reads",
    "profile_path_read_fingerprint",
    "profile_prefix_read_fingerprint",
    "profile_projection_read_entry",
    "profile_read_entry",
    "profile_read_fingerprint",
    "profile_record_read_entry",
    "profile_record_read_fingerprint",
]
