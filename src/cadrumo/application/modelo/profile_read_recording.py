"""Record the profile facts a calculation reads, so a later edit can be shown to matter.

The profile resolver hands every binding, derived selector and applicability
predicate one fact index. :class:`RecordingFactIndex` is that index: each keyed
read names its path, and a read that enumerates a section names the section's
prefix through :func:`fact_items_under`. A read that enumerates the whole index
without a prefix records the empty prefix, which every edit moves, so an
unscoped enumeration can only over-report staleness, never hide it.

Values are digested from the index as the calculation finished with it, after
every derived selector was injected; verification recomputes the same index from
the profile as it stands and digests the same reads.
"""

from __future__ import annotations

from _collections_abc import dict_items, dict_keys, dict_values
from collections.abc import Iterator, Mapping
from typing import overload, override

from ...domain.modelos.profile_read_fingerprint import (
    ProfileReadFingerprint,
    ProfileReadScope,
    profile_read_entry,
    profile_read_fingerprint,
)
from ...domain.user_profile.values import UserProfileFactValue

_WHOLE_INDEX_PREFIX = ""


class RecordingFactIndex(dict[str, UserProfileFactValue]):
    """A profile fact index that remembers which paths and sections were read.

    Writes are not reads: an injector stating a derived path is not recorded,
    but any later read of that path is, and its digest is taken over the derived
    value, which is how a change to a derived selector's input is seen.
    """

    def __init__(self, facts: Mapping[str, UserProfileFactValue]) -> None:
        """Copy ``facts`` and start with no recorded reads."""
        super().__init__(facts)
        self._paths: set[str] = set()
        self._prefixes: set[str] = set()

    @override
    def __getitem__(self, path: str) -> UserProfileFactValue:
        """Record and return one path's value."""
        self._paths.add(path)
        return super().__getitem__(path)

    @overload
    def get(self, path: object, default: None = None, /) -> UserProfileFactValue: ...

    @overload
    def get(self, path: object, default: UserProfileFactValue, /) -> UserProfileFactValue: ...

    @overload
    def get[DefaultValue](self, path: object, default: DefaultValue, /) -> UserProfileFactValue | DefaultValue: ...

    @override
    def get(self, path: object, default: object = None, /) -> object:
        """Record and return one path's value, or ``default`` when it is absent."""
        if isinstance(path, str):
            self._paths.add(path)
        return super().get(path, default)

    @override
    def __contains__(self, path: object) -> bool:
        """Record a presence test, which reads the path as much as its value does."""
        if isinstance(path, str):
            self._paths.add(path)
        return super().__contains__(path)

    @override
    def setdefault(self, path: str, default: UserProfileFactValue = None, /) -> UserProfileFactValue:
        """Record the read a default makes of the value already present."""
        self._paths.add(path)
        return super().setdefault(path, default)

    @override
    def __iter__(self) -> Iterator[str]:
        """Record an unscoped enumeration as a read of the whole index."""
        self._prefixes.add(_WHOLE_INDEX_PREFIX)
        return super().__iter__()

    @override
    def keys(self) -> dict_keys[str, UserProfileFactValue]:
        """Record an unscoped enumeration as a read of the whole index."""
        self._prefixes.add(_WHOLE_INDEX_PREFIX)
        return super().keys()

    @override
    def items(self) -> dict_items[str, UserProfileFactValue]:
        """Record an unscoped enumeration as a read of the whole index."""
        self._prefixes.add(_WHOLE_INDEX_PREFIX)
        return super().items()

    @override
    def values(self) -> dict_values[str, UserProfileFactValue]:
        """Record an unscoped enumeration as a read of the whole index."""
        self._prefixes.add(_WHOLE_INDEX_PREFIX)
        return super().values()

    def record_prefix(self, prefix: str) -> dict[str, UserProfileFactValue]:
        """Record a read of every path under ``prefix`` and return those paths with their values."""
        self._prefixes.add(prefix)
        return {path: value for path, value in dict.items(self) if path.startswith(prefix)}

    def read_fingerprint(self) -> ProfileReadFingerprint:
        """Digest the recorded reads over the index as it stands now."""
        return digest_profile_reads(
            dict(dict.items(self)),
            paths=frozenset(self._paths),
            prefixes=frozenset(self._prefixes),
        )


def fact_items_under(facts: Mapping[str, UserProfileFactValue], prefix: str) -> dict[str, UserProfileFactValue]:
    """Return every fact whose path starts with ``prefix``, recording the section read when recorded."""
    if isinstance(facts, RecordingFactIndex):
        return facts.record_prefix(prefix)
    return {path: value for path, value in facts.items() if path.startswith(prefix)}


def digest_profile_reads(
    facts: Mapping[str, UserProfileFactValue],
    *,
    paths: frozenset[str],
    prefixes: frozenset[str],
) -> ProfileReadFingerprint:
    """Digest each path and prefix read over ``facts``."""
    return profile_read_fingerprint(
        profile_present=True,
        entries=(
            *(profile_read_entry(facts, ProfileReadScope.PATH, path) for path in paths),
            *(profile_read_entry(facts, ProfileReadScope.PREFIX, prefix) for prefix in prefixes),
        ),
    )


def redigest_profile_reads(
    recorded: ProfileReadFingerprint, facts: Mapping[str, UserProfileFactValue] | None
) -> ProfileReadFingerprint:
    """Digest the reads ``recorded`` names over ``facts``; ``None`` facts means no profile."""
    if facts is None:
        return profile_read_fingerprint(profile_present=False, entries=())
    return digest_profile_reads(
        facts,
        paths=frozenset(entry.selector for entry in recorded.entries if entry.scope is ProfileReadScope.PATH),
        prefixes=frozenset(entry.selector for entry in recorded.entries if entry.scope is ProfileReadScope.PREFIX),
    )


def absent_profile_read_fingerprint() -> ProfileReadFingerprint:
    """The fingerprint of a calculation made with no profile record to read."""
    return profile_read_fingerprint(profile_present=False, entries=())


__all__ = [
    "RecordingFactIndex",
    "absent_profile_read_fingerprint",
    "digest_profile_reads",
    "fact_items_under",
    "redigest_profile_reads",
]
