"""Record which stored profile facts a calculation reads, whoever reads them.

A Modelo calculation reads the profile through more than its profile resolver:
the ledger sources, the advisories, the applicability and eligibility gates and
the derived-fact injectors each read the stored record. While
:func:`recording_profile_reads` is open, the canonical projections in
:mod:`application.user_profile.projections` hand out mappings that note each
path read, and a reader that walks the record's facts itself notes the path or
section it walks through :func:`note_profile_path_read` or
:func:`profile_facts_under`. Outside a recording nothing changes: the
projections return plain dictionaries.

A read that enumerates a whole projection without naming a section is noted as
the empty prefix, which every edit moves, so an unscoped enumeration can only
over-report staleness, never hide it. A reader that enumerates only some
sections is handed :func:`profile_view_under`, whose enumeration notes just
those sections. A projection of the whole record is noted by its result through
:func:`note_profile_projection_read`.
"""

from __future__ import annotations

from _collections_abc import dict_items, dict_keys, dict_values
from collections.abc import Generator, Iterable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import overload, override

from ...core.identity.hex_ids import SnapshotId
from ...domain.modelos.profile_read_fingerprint import (
    ProfileReadEntry,
    ProfileReadScope,
    profile_projection_read_entry,
    profile_record_read_entry,
)
from ...domain.user_profile.values import UserProfileFact

_WHOLE_PROFILE_PREFIX = ""


class ProfileReadRecorder:
    """The stored-record paths and sections read while one calculation ran."""

    def __init__(self) -> None:
        """Start with nothing read."""
        self._paths: set[str] = set()
        self._prefixes: set[str] = set()
        self._projections: dict[str, SnapshotId] = {}

    def note_path(self, path: str) -> None:
        """Note a read of one stored path."""
        self._paths.add(path)

    def note_prefix(self, prefix: str) -> None:
        """Note a read of every stored path under ``prefix``."""
        self._prefixes.add(prefix)

    def note_projection(self, selector: str, fingerprint: SnapshotId) -> None:
        """Note a whole-record projection by its selector and the digest of what it produced."""
        self._projections.setdefault(selector, fingerprint)

    def entries(self, facts: Iterable[UserProfileFact]) -> tuple[ProfileReadEntry, ...]:
        """Digest every noted read over ``facts``, the stored record's facts."""
        stored = tuple(facts)
        return (
            *(profile_record_read_entry(stored, ProfileReadScope.PATH, path) for path in sorted(self._paths)),
            *(profile_record_read_entry(stored, ProfileReadScope.PREFIX, prefix) for prefix in sorted(self._prefixes)),
            *(
                profile_projection_read_entry(selector, fingerprint)
                for selector, fingerprint in sorted(self._projections.items())
            ),
        )


_ACTIVE: ContextVar[ProfileReadRecorder | None] = ContextVar("cadrumo_profile_read_recorder", default=None)


@contextmanager
def recording_profile_reads() -> Generator[ProfileReadRecorder]:
    """Record the profile reads made inside the block; a nested block shares the open recorder."""
    open_recorder = _ACTIVE.get()
    if open_recorder is not None:
        yield open_recorder
        return
    recorder = ProfileReadRecorder()
    token = _ACTIVE.set(recorder)
    try:
        yield recorder
    finally:
        _ACTIVE.reset(token)


def active_profile_read_recorder() -> ProfileReadRecorder | None:
    """Return the recorder of the calculation running now, if one is."""
    return _ACTIVE.get()


def note_profile_path_read(path: str) -> None:
    """Note a direct read of one stored path, when a calculation is recording."""
    recorder = _ACTIVE.get()
    if recorder is not None:
        recorder.note_path(path)


def note_profile_projection_read(selector: str, fingerprint: SnapshotId) -> None:
    """Note a whole-record projection's result, when a calculation is recording."""
    recorder = _ACTIVE.get()
    if recorder is not None:
        recorder.note_projection(selector, fingerprint)


def profile_facts_under(facts: Iterable[UserProfileFact], prefix: str) -> tuple[UserProfileFact, ...]:
    """Return the stored facts whose path starts with ``prefix``, noting the section read."""
    recorder = _ACTIVE.get()
    if recorder is not None:
        recorder.note_prefix(prefix)
    return tuple(fact for fact in facts if fact.path.startswith(prefix))


def profile_facts_at(facts: Iterable[UserProfileFact], path: str) -> tuple[UserProfileFact, ...]:
    """Return the stored facts at ``path``, every dated one, noting the path read."""
    note_profile_path_read(path)
    return tuple(fact for fact in facts if fact.path == path)


class RecordedProfileView[Value](dict[str, Value]):
    """A projection of the stored record that notes each key read as the stored path behind it.

    ``key_paths`` names the stored paths behind a key that is not itself a path,
    such as a schema ``model_selector`` alias; any other key is its own path.
    """

    def __init__(
        self,
        values: Mapping[str, Value],
        *,
        recorder: ProfileReadRecorder,
        key_paths: Mapping[str, tuple[str, ...]],
        sections: tuple[str, ...] = (_WHOLE_PROFILE_PREFIX,),
    ) -> None:
        """Copy ``values`` without reading them as the calculation.

        ``sections`` are the prefixes an enumeration of this view reads: the
        whole profile, unless the view was cut down to some sections.
        """
        super().__init__(dict.items(values) if isinstance(values, dict) else values.items())
        self._recorder = recorder
        self._key_paths = key_paths
        self._sections = sections

    def under(self, prefixes: tuple[str, ...]) -> RecordedProfileView[Value]:
        """Return the view cut down to ``prefixes``, whose enumeration reads only them."""
        return RecordedProfileView(
            {key: value for key, value in dict.items(self) if key.startswith(prefixes)},
            recorder=self._recorder,
            key_paths=self._key_paths,
            sections=prefixes,
        )

    def _note(self, key: object) -> None:
        if isinstance(key, str):
            for path in self._key_paths.get(key, (key,)):
                self._recorder.note_path(path)

    def _note_whole(self) -> None:
        for section in self._sections:
            self._recorder.note_prefix(section)

    def items_under(self, prefix: str) -> dict[str, Value]:
        """Note a read of every path under ``prefix`` and return those keys with their values."""
        self._recorder.note_prefix(prefix)
        return {key: value for key, value in dict.items(self) if key.startswith(prefix)}

    @override
    def __getitem__(self, key: str) -> Value:
        """Note and return one key's value."""
        self._note(key)
        return super().__getitem__(key)

    @overload
    def get(self, key: object, default: None = None, /) -> Value | None: ...

    @overload
    def get(self, key: object, default: Value, /) -> Value: ...

    @overload
    def get[DefaultValue](self, key: object, default: DefaultValue, /) -> Value | DefaultValue: ...

    @override
    def get(self, key: object, default: object = None, /) -> object:
        """Note and return one key's value, or ``default`` when it is absent."""
        self._note(key)
        return super().get(key, default)

    @override
    def __contains__(self, key: object) -> bool:
        """Note a presence test, which reads the key as much as its value does."""
        self._note(key)
        return super().__contains__(key)

    @override
    def __iter__(self) -> Iterator[str]:
        """Note an unscoped enumeration as a read of the whole profile."""
        self._note_whole()
        return super().__iter__()

    @override
    def keys(self) -> dict_keys[str, Value]:
        """Note an unscoped enumeration as a read of the whole profile."""
        self._note_whole()
        return super().keys()

    @override
    def items(self) -> dict_items[str, Value]:
        """Note an unscoped enumeration as a read of the whole profile."""
        self._note_whole()
        return super().items()

    @override
    def values(self) -> dict_values[str, Value]:
        """Note an unscoped enumeration as a read of the whole profile."""
        self._note_whole()
        return super().values()


def profile_values_under[Value](values: Mapping[str, Value], prefix: str) -> dict[str, Value]:
    """Return the projected keys under ``prefix`` with their values, noting the section read when recording."""
    if isinstance(values, RecordedProfileView):
        return values.items_under(prefix)
    return {key: value for key, value in values.items() if key.startswith(prefix)}


def profile_view_under[Value](values: Mapping[str, Value], *prefixes: str) -> Mapping[str, Value]:
    """Cut ``values`` down to ``prefixes`` for a reader that enumerates only those sections."""
    if isinstance(values, RecordedProfileView):
        return values.under(prefixes)
    return {key: value for key, value in values.items() if key.startswith(prefixes)}


def recorded_profile_view[Value](
    values: dict[str, Value], *, key_paths: Mapping[str, tuple[str, ...]] | None = None
) -> dict[str, Value]:
    """Return ``values`` as a noting view while a calculation records, else unchanged."""
    recorder = _ACTIVE.get()
    if recorder is None:
        return values
    return RecordedProfileView(values, recorder=recorder, key_paths=key_paths or {})


__all__ = [
    "ProfileReadRecorder",
    "RecordedProfileView",
    "active_profile_read_recorder",
    "note_profile_path_read",
    "note_profile_projection_read",
    "profile_facts_at",
    "profile_facts_under",
    "profile_values_under",
    "profile_view_under",
    "recorded_profile_view",
    "recording_profile_reads",
]
