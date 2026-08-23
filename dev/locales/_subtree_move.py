"""Value-preserving relocation of a dotted key SUBTREE across every catalogue.

The catalogues carry one family of keys whose dotted path is not authored by a
call site but DERIVED from registry data: the Modelo schema keys, whose path
embeds the revision id
(``modelo.schema.<modelo>.revision.<revision>.casilla.<casilla>.label``). When
the registry renames or splits a revision, every one of those paths changes
while every value stays correct -- and no verb existed for that shape.

``scaffold`` cannot express it. It reconciles the catalogues against the
codebase key set, so a rename reads as an unrelated removal plus an unrelated
addition: the removal drops four authored translations, and the addition
reserves a slot the honesty ratchet refuses to see filled with a placeholder.
The values are the expensive part and they were never wrong, so the operation
that fits is a MOVE.

Planning lives here, apart from the writer, because the decisions a move makes
-- which destination receives a leaf, what happens when the destination already
holds one, whether a leaf no destination claims may be dropped -- are answered
identically for every locale and must be, or the four catalogues diverge in the
one operation that most looks like it cannot diverge. The manager applies the
plan through the shared write guard.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from ._errors import LocaleError

_MODELO_SCHEMA_PREFIX = "modelo.schema."


class LocaleMoveConflict(StrEnum):
    """What a move does when a destination key already carries a value."""

    REFUSE = "refuse"
    SKIP = "skip"
    OVERWRITE = "overwrite"


class LocaleMoveDisposition(StrEnum):
    """The decision a plan reached for one source leaf in one locale."""

    WRITE = "write"
    IDENTICAL = "identical"
    SKIPPED = "skipped"
    OVERWRITTEN = "overwritten"
    CONFLICT = "conflict"


#: Dispositions that put a value at the destination key.
_WRITING_DISPOSITIONS = frozenset({LocaleMoveDisposition.WRITE, LocaleMoveDisposition.OVERWRITTEN})

#: Dispositions under which some destination ends up holding a value for the
#: leaf, so the source leaf has been carried and may be released. ``SKIPPED``
#: belongs here: the destination already carries authored prose the operator
#: chose to keep, which supersedes the source rather than losing it. Only a
#: refused conflict leaves the leaf uncarried, and a refused conflict aborts
#: the move before anything is written.
_CARRIED_DISPOSITIONS = _WRITING_DISPOSITIONS | {LocaleMoveDisposition.IDENTICAL, LocaleMoveDisposition.SKIPPED}


@dataclass(frozen=True)
class LocaleMoveEntry:
    """One source leaf's fate at one destination in one locale."""

    locale: str
    source_key: str
    destination_key: str
    disposition: LocaleMoveDisposition
    value: str | None


@dataclass(frozen=True)
class LocaleSubtreeMovePlan:
    """Every leaf edit a subtree move performs, decided before anything is written."""

    source_prefix: str
    destination_prefixes: tuple[str, ...]
    keep_source: bool
    drop_undistributed: bool
    entries: tuple[LocaleMoveEntry, ...]
    undistributed: tuple[tuple[str, str], ...]
    removals: tuple[tuple[str, str], ...]

    @property
    def conflicts(self) -> tuple[LocaleMoveEntry, ...]:
        """Return the entries whose destination already holds a different value."""
        return tuple(entry for entry in self.entries if entry.disposition is LocaleMoveDisposition.CONFLICT)

    @property
    def writes(self) -> tuple[LocaleMoveEntry, ...]:
        """Return the entries that put a value at their destination key."""
        return tuple(entry for entry in self.entries if entry.disposition in _WRITING_DISPOSITIONS)

    def edits_for(self, locale: str) -> dict[str, str | None]:
        """Return the destination leaves this plan writes in one locale."""
        return {entry.destination_key: entry.value for entry in self.writes if entry.locale == locale}

    def removals_for(self, locale: str) -> tuple[str, ...]:
        """Return the source leaves this plan releases in one locale."""
        return tuple(key for entry_locale, key in self.removals if entry_locale == locale)


@dataclass(frozen=True)
class LocaleSubtreeMoveResult:
    """A planned subtree move together with the catalogue files it rewrote."""

    plan: LocaleSubtreeMovePlan
    dry_run: bool
    written_paths: tuple[str, ...]


def normalise_key_prefix(prefix: str) -> str:
    """Return a validated dotted namespace prefix, without its trailing dot.

    A prefix is addressed as a namespace, so the trailing dot is accepted and
    normalised away rather than refused: an operator who copies a key path out
    of a report gets the same behaviour either way.
    """
    candidate = prefix.strip().rstrip(".")
    parts = candidate.split(".")
    if not candidate or any(not part for part in parts):
        raise LocaleError(f"Invalid locale key prefix: {prefix!r}")
    return candidate


def plan_locale_subtree_move(
    leaves_by_locale: Mapping[str, Mapping[str, str | None]],
    source_prefix: str,
    destination_prefixes: Sequence[str],
    *,
    keep_source: bool,
    drop_undistributed: bool,
    on_conflict: LocaleMoveConflict,
    permitted_destination_keys: Mapping[str, frozenset[str]] | None = None,
) -> LocaleSubtreeMovePlan:
    """Decide every leaf edit a subtree move performs, writing nothing.

    Args:
        leaves_by_locale: Flattened dotted-key leaf values per locale code.
        source_prefix: The namespace whose leaves are relocated.
        destination_prefixes: One namespace for a rename, several for a split.
        keep_source: Leave the source subtree in place (a copy).
        drop_undistributed: Release a source leaf no destination accepted.
        on_conflict: What to do where the destination already holds a value.
        permitted_destination_keys: Per-destination allowlist of destination
            keys. A registry-aware caller passes the key set the target
            revision actually declares, which is what routes a split: each
            leaf lands where its own revision declares it rather than being
            duplicated into both halves.

    Returns:
        The full plan, including the leaves no destination accepted.
    """
    source = normalise_key_prefix(source_prefix)
    destinations = tuple(normalise_key_prefix(prefix) for prefix in destination_prefixes)
    if not destinations:
        raise LocaleError("At least one destination prefix is required")
    if len(set(destinations)) != len(destinations):
        raise LocaleError(f"Duplicate destination prefix in {destinations!r}")
    if source in destinations:
        raise LocaleError(f"Cannot move {source!r} onto itself")
    for destination in destinations:
        if destination.startswith(f"{source}.") or source.startswith(f"{destination}."):
            raise LocaleError(f"Cannot move {source!r} into its own subtree at {destination!r}")

    entries: list[LocaleMoveEntry] = []
    undistributed: list[tuple[str, str]] = []
    removals: list[tuple[str, str]] = []

    for locale in sorted(leaves_by_locale):
        leaves = leaves_by_locale[locale]
        source_keys = sorted(key for key in leaves if key.startswith(f"{source}."))
        for source_key in source_keys:
            value = leaves[source_key]
            tail = source_key[len(source) :]
            carried = False
            for destination in destinations:
                destination_key = f"{destination}{tail}"
                permitted = permitted_destination_keys.get(destination) if permitted_destination_keys else None
                if permitted is not None and destination_key not in permitted:
                    continue
                if value is None and not destination_key.startswith(_MODELO_SCHEMA_PREFIX):
                    raise LocaleError(
                        f"Cannot move an absent value to {destination_key!r}: "
                        "only Modelo schema keys may carry an absent locale value",
                    )
                disposition = _decide(leaves, destination_key, value, on_conflict)
                entries.append(LocaleMoveEntry(locale, source_key, destination_key, disposition, value))
                carried = carried or disposition in _CARRIED_DISPOSITIONS
            if not carried:
                undistributed.append((locale, source_key))
            if not keep_source and (carried or drop_undistributed):
                removals.append((locale, source_key))

    return LocaleSubtreeMovePlan(
        source_prefix=source,
        destination_prefixes=destinations,
        keep_source=keep_source,
        drop_undistributed=drop_undistributed,
        entries=tuple(entries),
        undistributed=tuple(undistributed),
        removals=tuple(removals),
    )


def _decide(
    leaves: Mapping[str, str | None],
    destination_key: str,
    value: str | None,
    on_conflict: LocaleMoveConflict,
) -> LocaleMoveDisposition:
    """Classify one destination leaf against what the catalogue already holds."""
    if destination_key not in leaves:
        return LocaleMoveDisposition.WRITE
    existing = leaves[destination_key]
    if existing == value:
        return LocaleMoveDisposition.IDENTICAL
    if existing is None:
        # An explicitly absent Modelo leaf is a reserved slot, not authored
        # prose: filling it is the whole point of the move, never a clash.
        return LocaleMoveDisposition.WRITE
    if on_conflict is LocaleMoveConflict.OVERWRITE:
        return LocaleMoveDisposition.OVERWRITTEN
    if on_conflict is LocaleMoveConflict.SKIP:
        return LocaleMoveDisposition.SKIPPED
    return LocaleMoveDisposition.CONFLICT


__all__ = [
    "LocaleMoveConflict",
    "LocaleMoveDisposition",
    "LocaleMoveEntry",
    "LocaleSubtreeMovePlan",
    "LocaleSubtreeMoveResult",
    "normalise_key_prefix",
    "plan_locale_subtree_move",
]
