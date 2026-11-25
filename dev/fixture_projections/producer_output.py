"""The one way a fixture producer writes, checks or redirects what it rendered.

Every producer renders its outputs in memory first. Without options it writes
them in place; ``--check`` writes nothing and fails naming each output that
differs from the rendered text; ``--output DIR`` writes the same bytes into
``DIR`` instead, which is how a determinism proof builds a family twice without
touching the stored outputs.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProducerOptions:
    """What a producer was asked to do: check, redirect into ``output``, or write in place."""

    check: bool
    output: Path | None


def producer_arguments(description: str | None, argv: Sequence[str] | None = None) -> ProducerOptions:
    """Parse the producer options every fixture producer takes: ``--check`` or ``--output DIR``."""
    parser = argparse.ArgumentParser(description=description)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true", help="Write nothing; fail when a stored output is stale.")
    modes.add_argument("--output", help="Write the outputs into this existing directory instead.")
    parsed = parser.parse_args(argv)
    output = str(parsed.output) if parsed.output is not None else None
    return ProducerOptions(check=bool(parsed.check), output=None if output is None else Path(output))


def emit(rendered: Mapping[Path, str], arguments: ProducerOptions, *, remedy: str) -> None:
    """Write, check or redirect each rendered output, keyed by its stored path.

    Raises:
        SystemExit: Under ``--check`` when an output is absent or differs, naming each and ``remedy``.
    """
    if arguments.check:
        stale = [
            path.name
            for path, text in rendered.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != text
        ]
        if stale:
            raise SystemExit(f"Stale fixture output: {', '.join(stale)}; run {remedy}")
        return
    output = arguments.output
    if output is not None and not output.is_dir():
        raise SystemExit(f"--output {output} is not an existing directory")
    for path, text in rendered.items():
        target = path if output is None else output / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
