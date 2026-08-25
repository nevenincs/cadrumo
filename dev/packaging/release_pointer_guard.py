"""Refuse a backward version bump on a committed release-pointer manifest.

A Scoop manifest and a Homebrew formula are *release pointers*: each pins a
version and a digest that a user's package manager resolves and installs. They
live in a shared repository under ordinary git, and ordinary merge semantics can
resurrect an older pointer — a stale branch merged, a revert, a race lost and
re-applied from a stale clone. Nothing in git objects to that: the write
succeeds, the workflow reports success, and the channel has silently
un-published its current version while every gate stays green.

This guard is the monotonic backstop. It reads the pointer already committed in
the shared repository, compares it against the version about to be written, and
refuses when the write would move the channel backward. An absent pointer is the
first publication and passes; an identical version is a benign republish and
passes.

Two independently-built products in this account arrived at the same guard on
the same failure, which is what promoted it from a per-product patch to part of
the shared mechanism.

See Also:
    :func:`extract_pointer_version`
        Read the pinned version out of either pointer format.
    :func:`assert_forward_bump`
        The comparison this module exists to enforce.
"""

from __future__ import annotations

import argparse
import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Final

from packaging.version import InvalidVersion, Version

from .._paths import UTF_8

_UTF_8: Final[str] = UTF_8

#: The Homebrew formula carries no `version` stanza — the version lives in the
#: release-asset URL it pins, which is the same string a user's `brew install`
#: resolves. Anchored on the `/releases/download/v<version>/` segment so an
#: unrelated URL elsewhere in the formula (a homepage, a resource) cannot match.
_HOMEBREW_URL_VERSION: Final[re.Pattern[str]] = re.compile(
    r"""url\s+["'][^"']*/releases/download/v(?P<version>[^/"']+)/""",
)


class PointerFormat(StrEnum):
    """Closed set of committed release-pointer formats this guard reads."""

    SCOOP = "scoop"
    HOMEBREW = "homebrew"


class BackwardBumpError(RuntimeError):
    """Raised when writing the pointer would move the channel backward."""


def extract_pointer_version(text: str, pointer_format: PointerFormat) -> str:
    """Return the version a committed release pointer currently pins.

    Raises:
        ValueError: the pointer exists but carries no readable version. This is
            deliberately fatal rather than treated as "no previous version": an
            unreadable pointer means the guard cannot prove the write is
            forward, and a guard that cannot prove its invariant must refuse
            rather than wave the write through.
    """
    if pointer_format is PointerFormat.SCOOP:
        try:
            document = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"scoop manifest is not valid JSON: {exc}") from exc
        if not isinstance(document, dict):
            raise ValueError("scoop manifest is not a JSON object")
        version = document.get("version")
        if not isinstance(version, str) or not version:
            raise ValueError("scoop manifest carries no 'version' string")
        return version

    match = _HOMEBREW_URL_VERSION.search(text)
    if match is None:
        raise ValueError("homebrew formula carries no '/releases/download/v<version>/' url")
    return match.group("version")


def assert_forward_bump(*, existing: str | None, incoming: str) -> None:
    """Refuse when ``incoming`` would move a channel backward from ``existing``.

    An absent ``existing`` is the first publication into this channel. An equal
    version is a benign republish (the push is a no-op once staged). Only a
    strictly lower incoming version is refused.

    Raises:
        BackwardBumpError: the write would un-publish a newer version.
        ValueError: either version is unparseable, so monotonicity cannot be
            established.
    """
    try:
        incoming_version = Version(incoming)
    except InvalidVersion as exc:
        raise ValueError(f"incoming version {incoming!r} is not a valid version: {exc}") from exc
    if existing is None:
        return
    try:
        existing_version = Version(existing)
    except InvalidVersion as exc:
        raise ValueError(f"committed pointer version {existing!r} is not a valid version: {exc}") from exc
    if incoming_version < existing_version:
        raise BackwardBumpError(
            f"REFUSED: the committed release pointer is at {existing}, and this publication would "
            f"move it back to {incoming}. Writing it would un-publish {existing} for every user "
            "resolving this channel. Re-run the publication from the newer cohort, or correct the "
            "committed pointer first.",
        )


def check_pointer(path: Path, *, version: str, pointer_format: PointerFormat) -> str | None:
    """Prove writing ``version`` over the pointer at ``path`` moves forward.

    Returns the version the pointer currently pins, or ``None`` when no pointer
    is committed yet.
    """
    existing = None if not path.is_file() else extract_pointer_version(path.read_text(encoding=_UTF_8), pointer_format)
    assert_forward_bump(existing=existing, incoming=version)
    return existing


def main(argv: list[str] | None = None) -> int:
    """Guard one committed release pointer against a backward bump."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--existing",
        required=True,
        type=Path,
        help="Path to the pointer already committed in the shared repository (may be absent).",
    )
    parser.add_argument("--version", required=True, help="Version this publication is about to write.")
    parser.add_argument(
        "--format",
        required=True,
        dest="pointer_format",
        choices=tuple(fmt.value for fmt in PointerFormat),
        help="Pointer format to parse.",
    )
    args = parser.parse_args(argv)
    pointer_format = PointerFormat(args.pointer_format)

    try:
        existing = check_pointer(args.existing, version=args.version, pointer_format=pointer_format)
    except (BackwardBumpError, ValueError) as exc:
        print(str(exc), flush=True)
        return 1

    if existing is None:
        print(f"no committed {pointer_format.value} pointer yet; {args.version} is the first publication", flush=True)
    else:
        print(f"{pointer_format.value} pointer moves forward: {existing} -> {args.version}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
