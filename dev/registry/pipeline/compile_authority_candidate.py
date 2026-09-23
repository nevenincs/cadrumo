"""Compile, validate and stage one authority candidate in a fresh interpreter.

Every publication runs this module as its own process, so the compiler closure
the candidate records is exactly what compiling it imports. Whatever the
launching tool had already loaded cannot reach the record, which keeps the
logical generation a function of the sources and the compiler alone.

The candidate is written as a complete descriptor and content-addressed
database pair into an output directory the parent owns; the parent admits it
and decides whether to publish it. The process ends early, with its own exit
status, if the parent that launched it goes away.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from .authority_publication import stage_authority_candidate, validate_authority_candidate
from .candidate_compile_process import exit_when_parent_exits


def main(argv: Sequence[str] | None = None) -> int:
    """Stage the validated candidate, or report the refusal on stderr and exit 1."""
    exit_when_parent_exits()
    parser = argparse.ArgumentParser(prog="compile_authority_candidate")
    parser.add_argument("--registry-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--profile-schema", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--eager-baseline", type=Path)
    arguments = parser.parse_args(argv)
    try:
        candidate = validate_authority_candidate(
            registry_root=arguments.registry_root,
            source_root=arguments.source_root,
            profile_schema_path=arguments.profile_schema,
        )
        stage_authority_candidate(candidate.artifact, arguments.output)
    except RegistryValidationError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if arguments.eager_baseline is not None:
        # Loaded after the closure was observed: the baseline is a measurement
        # of the artifact, not part of the code that produced it.
        from ..eager_authority_baseline import write_eager_authority_baseline

        write_eager_authority_baseline(arguments.eager_baseline, candidate.artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
