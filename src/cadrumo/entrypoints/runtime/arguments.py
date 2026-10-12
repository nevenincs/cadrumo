"""Validate runtime invocation syntax before importing application dependencies."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_runtime_arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    """Parse the explicit runtime owner binding without accessing runtime state.

    A supervisor names the root, its identity and the version it expects. A
    caller that owns the runtime itself names none of them: ``--configured-root``
    serves the root the process's storage settings select, the same root every
    client of that environment derives its endpoint from.
    """
    parser = argparse.ArgumentParser(prog="cadrumo-runtime", allow_abbrev=False)
    binding = parser.add_mutually_exclusive_group(required=True)
    binding.add_argument("--storage-root", type=Path)
    binding.add_argument(
        "--configured-root",
        action="store_true",
        help=(
            "Serve the explicit root CADRUMO_LOCAL_STORAGE_ROOT selects, for as long as standard input stays open. "
            "Prints one JSON line on standard output once clients can connect."
        ),
    )
    parser.add_argument("--storage-identity")
    parser.add_argument("--expected-version")
    parser.add_argument(
        "--supervised",
        action="store_true",
        help="Answer the launching supervisor over standard input and output.",
    )
    options = parser.parse_args(arguments)
    if options.configured_root:
        if options.storage_identity is not None or options.supervised:
            parser.error("--configured-root takes neither --storage-identity nor --supervised")
    else:
        missing = [
            flag
            for flag, value in (
                ("--storage-identity", options.storage_identity),
                ("--expected-version", options.expected_version),
            )
            if value is None
        ]
        if missing:
            parser.error("the following arguments are required: " + ", ".join(missing))
    return options
