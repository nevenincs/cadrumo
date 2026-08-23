"""Recognising a Modelo revision RENAME inside the catalogues' drift report.

Drift is reported as two sets: keys the codebase requires that no catalogue
carries, and keys a catalogue carries that the codebase does not require. That
partition is right for a call site added or deleted, and wrong for the one
family whose paths are derived rather than authored. When the registry renames
a revision -- ``2008-2024`` becoming ``2011-2024`` -- or splits one into two,
every affected key appears in BOTH sets, hundreds of lines apart, wearing the
shape of unrelated work. Three such splits landed unnoticed exactly that way,
and the labels they orphaned resolved to nothing for every operator.

The signal is available and cheap: a missing key and an extra key that agree on
their modelo and on everything after their revision segment, and differ only in
that segment, are the same string in two places. This module names that pair a
MOVE, so the report distinguishes "translate this" from "relocate this", and
prints the verb that performs it.

The same parse answers the parity question a gate needs -- which revision ids
the catalogues reference, and which the registry declares -- so both readings
of a revision segment come from one place rather than from two regexes that can
disagree.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

_REVISION_KEY = re.compile(r"^modelo\.schema\.(?P<modelo>[^.]+)\.revision\.(?P<revision>[^.]+)\.(?P<tail>.+)$")

_CASILLA_SEGMENT = "casilla."


@dataclass(frozen=True)
class RevisionMoveCandidate:
    """One source revision whose catalogue keys belong under other revision ids."""

    locale_file: str
    modelo: str
    source_revision: str
    destination_revisions: tuple[str, ...]
    key_count: int

    @property
    def invocation(self) -> str:
        """Return the CLI invocation that performs this move."""
        destinations = " ".join(self.destination_revisions)
        return f"python -m dev.locales move-revision {self.modelo} {self.source_revision} {destinations}"

    def render(self) -> str:
        """Return one greppable report row for this move."""
        destinations = ", ".join(self.destination_revisions)
        shape = "split" if len(self.destination_revisions) > 1 else "rename"
        return (
            f"move {shape} file={self.locale_file} modelo={self.modelo} "
            f"revision={self.source_revision} -> {destinations} keys={self.key_count} "
            f"run: {self.invocation}"
        )


@dataclass(frozen=True)
class RevisionMoveReport:
    """Every revision move one catalogue's drift explains, and the keys it covers."""

    candidates: tuple[RevisionMoveCandidate, ...]
    accounted_missing: frozenset[str]
    accounted_extra: frozenset[str]


def classify_revision_moves(
    locale_file: str,
    codebase_missing: Iterable[str],
    codebase_extra: Iterable[str],
) -> RevisionMoveReport:
    """Recognise the drift rows that are one revision rename or split.

    Args:
        locale_file: The catalogue the drift belongs to, for the report row.
        codebase_missing: Keys the codebase requires and the catalogue lacks.
        codebase_extra: Keys the catalogue carries and the codebase does not
            require.

    Returns:
        The recognised moves plus the missing and extra keys they explain, so
        a caller can report those keys once as a move rather than twice as
        unrelated additions and removals.
    """
    missing_by_identity: dict[tuple[str, str], set[str]] = {}
    missing_keys_by_identity: dict[tuple[str, str, str], str] = {}
    for key in codebase_missing:
        parsed = _REVISION_KEY.match(key)
        if parsed is None:
            continue
        identity = (parsed["modelo"], parsed["tail"])
        missing_by_identity.setdefault(identity, set()).add(parsed["revision"])
        missing_keys_by_identity[(parsed["modelo"], parsed["tail"], parsed["revision"])] = key

    destinations_by_source: dict[tuple[str, str], set[str]] = {}
    sources_seen: dict[tuple[str, str], set[str]] = {}
    accounted_missing: set[str] = set()
    accounted_extra: set[str] = set()

    for key in codebase_extra:
        parsed = _REVISION_KEY.match(key)
        if parsed is None:
            continue
        modelo, revision, tail = parsed["modelo"], parsed["revision"], parsed["tail"]
        destinations = missing_by_identity.get((modelo, tail), set()) - {revision}
        if not destinations:
            continue
        source = (modelo, revision)
        destinations_by_source.setdefault(source, set()).update(destinations)
        sources_seen.setdefault(source, set()).add(key)
        accounted_extra.add(key)
        for destination in destinations:
            accounted_missing.add(missing_keys_by_identity[(modelo, tail, destination)])

    candidates = tuple(
        RevisionMoveCandidate(
            locale_file=locale_file,
            modelo=modelo,
            source_revision=revision,
            destination_revisions=tuple(sorted(destinations_by_source[(modelo, revision)])),
            key_count=len(sources_seen[(modelo, revision)]),
        )
        for modelo, revision in sorted(destinations_by_source)
    )
    return RevisionMoveReport(candidates, frozenset(accounted_missing), frozenset(accounted_extra))


def revision_pairs(keys: Iterable[str]) -> frozenset[tuple[str, str]]:
    """Return every ``(modelo, revision)`` pair a key set references."""
    pairs: set[tuple[str, str]] = set()
    for key in keys:
        parsed = _REVISION_KEY.match(key)
        if parsed is not None:
            pairs.add((parsed["modelo"], parsed["revision"]))
    return frozenset(pairs)


def casilla_revision_pairs(keys: Iterable[str]) -> frozenset[tuple[str, str]]:
    """Return the ``(modelo, revision)`` pairs that declare at least one casilla key.

    A revision declaring no casilla carries nothing an operator reads through a
    casilla label, so demanding catalogue keys for it would fail a revision
    that is legitimately title-only.
    """
    pairs: set[tuple[str, str]] = set()
    for key in keys:
        parsed = _REVISION_KEY.match(key)
        if parsed is not None and parsed["tail"].startswith(_CASILLA_SEGMENT):
            pairs.add((parsed["modelo"], parsed["revision"]))
    return frozenset(pairs)


@dataclass(frozen=True)
class RevisionParityFindings:
    """The two directions in which catalogue and registry revision ids disagree."""

    stale: tuple[tuple[str, str], ...]
    absent: tuple[tuple[str, str], ...]

    @property
    def ok(self) -> bool:
        """Return whether every referenced revision id exists on both sides."""
        return not (self.stale or self.absent)


def classify_revision_parity(
    registry_keys: Iterable[str],
    locale_keys: Iterable[str],
) -> RevisionParityFindings:
    """Compare the revision ids a catalogue references against the registry's.

    Args:
        registry_keys: The Modelo schema keys the registry derives.
        locale_keys: The keys one catalogue carries.

    Returns:
        ``stale`` names the revision ids the catalogue references and the
        registry does not declare; ``absent`` names the registry revisions that
        carry casillas and for which the catalogue holds no key at all.
    """
    registry_pairs = revision_pairs(registry_keys)
    catalogue_pairs = revision_pairs(locale_keys)
    required_pairs = casilla_revision_pairs(registry_keys)
    return RevisionParityFindings(
        stale=tuple(sorted(catalogue_pairs - registry_pairs)),
        absent=tuple(sorted(required_pairs - catalogue_pairs)),
    )


__all__ = [
    "RevisionMoveCandidate",
    "RevisionMoveReport",
    "RevisionParityFindings",
    "casilla_revision_pairs",
    "classify_revision_moves",
    "classify_revision_parity",
    "revision_pairs",
]
