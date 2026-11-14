"""Refuse a CLI-column run whose authority was not published from the tree the run builds.

The profile worker of a CLI run loads the authority generation it is given, so an authority copied from another
table's run answers for another tree's registry (a run on the page-qualified registry that used the generation before it
printed the old casilla numbers). The run's own table writes the tree it ran and the generation it published beside its
rows; the authority directory names its generation in its descriptor. The two ``logical_generation`` values must agree
before a worker starts.

The authority's identity is that generation. ``database_sha256`` only names the SQLite file, whose bytes are not
reproducible between two builds of the same registry, so it is recorded in the returned identity and never refused on.

Run as ``python -m dev.acceptance.persona_table.cli_column.authority_guard --authority DIR --meta FILE --tree SHA``;
the exit code is 0 when the generations match (the generation and both file hashes go to standard output) and 2 with the
reason on standard error when they do not.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

DESCRIPTOR = "authority.current.json"
"""The descriptor file an authority directory publishes its current generation in."""
_GENERATION = "logical_generation"
_DATABASE = "database_sha256"


class AuthorityMismatchError(RuntimeError):
    """The authority was not published from the tree the run builds."""


@dataclass(frozen=True, slots=True)
class AuthorityIdentity:
    """The generation both sides agree on, with the SQLite file hash each side recorded."""

    logical_generation: str
    authority_database_sha256: str | None
    run_database_sha256: str | None

    @property
    def same_file(self) -> bool:
        """Whether the two file hashes are equal; informational, a different file of one generation is accepted."""
        return self.authority_database_sha256 == self.run_database_sha256


def _read(path: Path, what: str) -> Mapping[str, object]:
    try:
        document: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise AuthorityMismatchError(f"cannot read the {what} {path}: {error}") from error
    if not isinstance(document, dict):
        raise AuthorityMismatchError(f"the {what} {path} is not a JSON object")
    return cast("Mapping[str, object]", document)


def _text(document: Mapping[str, object], key: str) -> str | None:
    value = document.get(key)
    return value if isinstance(value, str) and value else None


def check_authority_matches_tree(authority: Path, meta: Path, tree: str) -> AuthorityIdentity:
    """The identity both sides share, or raise unless ``authority`` holds the generation the run of ``tree`` published.

    ``meta`` is that run's ``rows.jsonl.meta.json``: its ``tree`` must be ``tree`` and its ``logical_generation`` must
    equal the authority descriptor's. The database hashes are recorded, not compared.
    """
    published = _read(meta, "table run meta")
    if published.get("tree") != tree:
        raise AuthorityMismatchError(
            f"the table run meta {meta} was run on tree {published.get('tree')!r}, not on {tree!r}: "
            "give the authority of a table run of the same tree"
        )
    descriptor = _read(authority / DESCRIPTOR, "authority descriptor")
    expected, held = _text(published, _GENERATION), _text(descriptor, _GENERATION)
    if expected is None or held != expected:
        raise AuthorityMismatchError(
            f"the authority {authority} holds {_GENERATION} {str(held)[:16]!r}, but the table run of "
            f"tree {tree!r} published {str(expected)[:16]!r}: it was published from another tree"
        )
    return AuthorityIdentity(expected, _text(descriptor, _DATABASE), _text(published, _DATABASE))


def main(argv: Sequence[str] | None = None) -> int:
    """Check the pair named on the command line; exit 0 when it matches, 2 with the reason when it does not."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority", type=Path, required=True)
    parser.add_argument("--meta", type=Path, required=True)
    parser.add_argument("--tree", required=True)
    arguments = parser.parse_args(argv)
    try:
        identity = check_authority_matches_tree(arguments.authority, arguments.meta, arguments.tree)
    except AuthorityMismatchError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    print(
        f"authority generation {identity.logical_generation}: authority file {identity.authority_database_sha256}, "
        f"run file {identity.run_database_sha256}, {'same' if identity.same_file else 'different'} file bytes"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
