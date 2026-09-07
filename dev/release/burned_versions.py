"""The burned-version ledger: version numbers no release may ever mint again.

A version is *burned* once the world may hold bytes under it. That is a
different fact from "some destination currently owns it", and the difference is
what this module exists to carry.

The floor recorded in the release-please manifest already refuses a candidate
below the highest version reached, and that is the right guard for the ordinary
case. It cannot express this one. After a disposition that deletes published
releases and resets the declarations, the floor drops with them -- the
destination-side evidence of exposure is exactly what the deletion erased --
and every number below the new floor becomes minttable again. The
protected fact is set membership, not ordering, and no ordering invariant
encodes set membership.

Two rules govern the ledger, and both are load-bearing:

*Append-only.* An entry is never removed. Public exposure cannot be revoked:
somebody may hold those bytes, and no later act makes that untrue. There is no
unburn, silent or otherwise.

*Deletion-burns.* Every outward deletion of a release, a tag, or an index
version adds that version here in the same change. Disposing of an artefact and
burning its number are one act, never two, so the burn cannot be forgotten as a
follow-up nobody scheduled.

The seeded entries are the two partial releases this project deleted rather
than delivered. Neither ever reached a package index, but both were downloadable
from the source forge for weeks, so both are burned.

See Also:
    :func:`read_ledger`
        The reader, as a pure function of the ledger file it is handed.
    :func:`burned_versions`
        The shipped ledger's contents, parsed and validated.
    :func:`is_burned`
        The membership question the identity guard asks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Final

from packaging.version import InvalidVersion, Version

from .._paths import UTF_8

_UTF_8: Final[str] = UTF_8

#: The committed ledger, beside this module so the data and its reader move
#: together and neither can be deployed without the other.
LEDGER_PATH: Final[Path] = Path(__file__).resolve().parent / "burned_versions.json"


class BurnedVersionLedgerError(RuntimeError):
    """The ledger is missing, malformed, or self-inconsistent."""


@dataclass(frozen=True, slots=True)
class BurnedVersion:
    """One burned version and the evidence for why it can never return.

    ``version`` is the spelling the ledger author wrote, kept verbatim because
    it is what a refusal shows an operator. ``canonical`` is the same number
    under :func:`canonical_version`, and it is the field every membership test
    compares.

    ``canonical`` is a parsed :class:`~packaging.version.Version` rather than a
    canonical string, because the identity being asserted is release identity
    and PEP 440 does not express that as string equality: ``0.2.1.0`` and
    ``0.2.1`` are one release, and each is its own canonical spelling, so a
    comparison over canonical strings answers "different" for two spellings of
    the same number. That answer is the same silent pass a raw-string
    comparison gives, arrived at one step later.
    """

    version: str
    burned_on: date
    reason: str
    canonical: Version


def canonical_version(version: str) -> Version | None:
    """Return the release ``version`` names, or ``None`` if it names none.

    Version identity is the rule this ledger turns on, so it is implemented
    here, at the boundary that owns the question, rather than at each caller. A
    resolver treats every spelling of a number as the same release -- ``0.02.1``
    and ``0.2.1`` are one release to an index -- while the ledger records one
    spelling per number. A membership test over raw strings therefore answers
    "not burned" for every spelling the file does not happen to hold, and that
    answer is indistinguishable from a number nobody ever published: exactly
    the silent pass this ledger exists to make impossible.

    The parsed number is returned rather than its canonical string, because the
    canonical string is not the identity. PEP 440 keeps a trailing release zero
    in the canonical spelling while comparing it away, so ``0.2.1.0`` and
    ``0.2.1`` are one release wearing two canonical spellings, and a ledger
    comparing spellings passes the second while burning the first. Returning
    the number moves the comparison onto the rule the resolvers actually apply.

    ``None`` rather than a refusal, because asking whether an unparseable
    string is burned is a question with an answer -- no ledger entry can be
    that string, since :func:`read_ledger` refuses one -- and raising here
    would turn a membership query into an error path its callers do not have.
    """
    try:
        return Version(version)
    except InvalidVersion:
        return None


def _parse_entry(raw: object, *, index: int) -> BurnedVersion:
    """Return one validated entry, refusing anything under-specified.

    Every field is required. A burn with no date or no reason is an assertion
    nobody can audit later, and an unauditable burn is the shape that invites a
    future reader to delete it as noise.
    """
    if not isinstance(raw, dict):
        raise BurnedVersionLedgerError(f"ledger entry {index} is not an object: {raw!r}")
    missing = sorted({"version", "burned_on", "reason"} - set(raw))
    if missing:
        raise BurnedVersionLedgerError(f"ledger entry {index} is missing {missing}")
    version = raw["version"]
    reason = raw["reason"]
    if not isinstance(version, str) or not version.strip():
        raise BurnedVersionLedgerError(f"ledger entry {index} has an empty version")
    if not isinstance(reason, str) or not reason.strip():
        raise BurnedVersionLedgerError(f"ledger entry {index} has an empty reason")
    canonical = canonical_version(version)
    if canonical is None:
        raise BurnedVersionLedgerError(f"ledger entry {index} has an unparseable version: {version!r}")
    try:
        burned_on = date.fromisoformat(str(raw["burned_on"]))
    except ValueError as exc:
        raise BurnedVersionLedgerError(
            f"ledger entry {index} has an unparseable burned_on: {raw['burned_on']!r}",
        ) from exc
    return BurnedVersion(version=version, burned_on=burned_on, reason=reason, canonical=canonical)


def read_ledger(path: Path) -> tuple[BurnedVersion, ...]:
    """Return every burned version recorded at ``path``, in ledger order.

    The reader is a pure function of the file it is handed: which ledger to read
    is the caller's decision, so refusing a malformed ledger can be exercised
    against a real file rather than by re-pointing a module global.

    Refuses a duplicate version outright. A number appearing twice means two
    different burns claim the same version with different evidence, and there is
    no safe way to choose between them.

    Args:
        path: The ledger JSON document to parse.

    Returns:
        Every :class:`BurnedVersion` in ``path``, in the order the file lists
        them.

    Raises:
        BurnedVersionLedgerError: If the ledger is absent, is not valid JSON,
            does not carry a ``burned`` list, holds an under-specified entry, or
            names one version more than once.
    """
    try:
        payload = json.loads(path.read_text(encoding=_UTF_8))
    except FileNotFoundError as exc:
        raise BurnedVersionLedgerError(f"burned-version ledger is absent at {path}") from exc
    except json.JSONDecodeError as exc:
        raise BurnedVersionLedgerError(f"burned-version ledger is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("burned"), list):
        raise BurnedVersionLedgerError("burned-version ledger must be an object carrying a 'burned' list")
    entries = tuple(_parse_entry(raw, index=index) for index, raw in enumerate(payload["burned"]))
    seen: set[Version] = set()
    for entry in entries:
        if entry.canonical in seen:
            raise BurnedVersionLedgerError(f"burned-version ledger lists {entry.version} more than once")
        seen.add(entry.canonical)
    return entries


@lru_cache(maxsize=1)
def burned_versions() -> tuple[BurnedVersion, ...]:
    """Return every version the shipped ledger burns, in ledger order.

    Returns:
        The parsed contents of :data:`LEDGER_PATH`.
    """
    return read_ledger(LEDGER_PATH)


def is_burned(version: str) -> bool:
    """Return whether ``version`` may never be minted again.

    Compared as numbers rather than as strings: see :func:`canonical_version`
    for why a spelling-sensitive answer here is a burned release shipping.
    """
    canonical = canonical_version(version)
    if canonical is None:
        return False
    return any(entry.canonical == canonical for entry in burned_versions())


def burn_reason(version: str) -> str | None:
    """Return why ``version`` is burned, or ``None`` when it is not.

    The identity guard names this in its refusal: an operator told only that a
    version is refused will reach for the ledger to find out why, and a refusal
    that carries its own evidence saves that round trip.
    """
    canonical = canonical_version(version)
    if canonical is None:
        return None
    for entry in burned_versions():
        if entry.canonical == canonical:
            return entry.reason
    return None
