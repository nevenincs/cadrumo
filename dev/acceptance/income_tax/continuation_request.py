"""Validate and dispatch installed parent and child continuation requests."""

from __future__ import annotations

import argparse

from .continuation_contracts import InstalledContinuationError, InstalledContinuationEvidence
from .continuation_directions import run_installed_tui_continuations
from .continuation_tui_child import run_tui_continuation_child
from .installed_tui_child import (
    read_passphrase_from_stdin,
)


def _requested_continuation_evidence(args: argparse.Namespace) -> dict[str, object] | InstalledContinuationEvidence:
    """Validate and dispatch the parent or stdin-credentialed child request."""
    if args.child_direction:
        if args.year is None or args.output_root is not None:
            raise InstalledContinuationError("continuation child requires --year and no --output-root")
        if args.scratch is None:
            raise InstalledContinuationError("continuation child requires --scratch")
        evidence = run_tui_continuation_child(
            direction=args.child_direction,
            workspace_root=args.workspace_root,
            profile_label="income-continuation",
            passphrase=read_passphrase_from_stdin(),
            year=args.year,
            scratch=args.scratch,
        )
    else:
        if None in (args.cli, args.python, args.authority_root, args.output_root, args.year):
            raise InstalledContinuationError(
                "parent continuation driver requires CLI, Python, authority, output root and year"
            )
        evidence = run_installed_tui_continuations(
            cli_executable=args.cli,
            python_executable=args.python,
            workspace_root=args.workspace_root,
            authority_root=args.authority_root,
            output_root=args.output_root,
            year=args.year,
            only_direction=args.only_direction,
        )
    return evidence
