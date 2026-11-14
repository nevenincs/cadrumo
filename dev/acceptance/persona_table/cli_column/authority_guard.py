"""Refuse a CLI-column run whose authority was not published from the tree the run builds.

The profile worker of a CLI run loads the authority generation it is given, so an authority copied from another
table's run answers for another tree's registry (a run on the page-qualified registry that used the generation before it
printed the old casilla numbers). The run's own table writes the tree it ran and the generation it published beside its
rows; the authority directory names its generation in its descriptor. The two must agree before a worker starts.

Run as ``python -m dev.acceptance.persona_table.cli_column.authority_guard --authority DIR --meta FILE --tree SHA``;
the exit code is 0 when the pair matches and 2 with the reason on standard error when it does not.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

DESCRIPTOR = "authority.current.json"
"""The descriptor file an authority directory publishes its current generation in."""
_KEYS = ("database_sha256", "logical_generation")


class AuthorityMismatchError(RuntimeError):
    """The authority was not published from the tree the run builds."""


def _read(path: Path, what: str) -> Mapping[str, object]:
    try:
        document: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise AuthorityMismatchError(f"cannot read the {what} {path}: {error}") from error
    if not isinstance(document, dict):
        raise AuthorityMismatchError(f"the {what} {path} is not a JSON object")
    return cast("Mapping[str, object]", document)


def check_authority_matches_tree(authority: Path, meta: Path, tree: str) -> None:
    """Raise unless ``authority`` holds the generation the table run that built ``tree`` published.

    ``meta`` is that run's ``rows.jsonl.meta.json``: its ``tree`` must be ``tree`` and its ``database_sha256`` and
    ``logical_generation`` must equal the authority descriptor's.
    """
    published = _read(meta, "table run meta")
    if published.get("tree") != tree:
        raise AuthorityMismatchError(
            f"the table run meta {meta} was run on tree {published.get('tree')!r}, not on {tree!r}: "
            "give the authority of a table run of the same tree"
        )
    descriptor = _read(authority / DESCRIPTOR, "authority descriptor")
    for key in _KEYS:
        if not isinstance(published.get(key), str) or descriptor.get(key) != published.get(key):
            raise AuthorityMismatchError(
                f"the authority {authority} holds {key} {str(descriptor.get(key))[:16]!r}, but the table run of "
                f"tree {tree!r} published {str(published.get(key))[:16]!r}: it was published from another tree"
            )


def main(argv: Sequence[str] | None = None) -> int:
    """Check the pair named on the command line; exit 0 when it matches, 2 with the reason when it does not."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority", type=Path, required=True)
    parser.add_argument("--meta", type=Path, required=True)
    parser.add_argument("--tree", required=True)
    arguments = parser.parse_args(argv)
    try:
        check_authority_matches_tree(arguments.authority, arguments.meta, arguments.tree)
    except AuthorityMismatchError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
