"""Installed local MCP stdio entry point."""

from __future__ import annotations

import argparse
import io
import os
import sys
from importlib.metadata import version
from typing import BinaryIO, TextIO, cast
from uuid import UUID


def _held_secret_command(args: argparse.Namespace) -> int | None:
    """Run the option that enters, reads, lists or deletes a held secret, and return its exit status.

    These options are for the person at a terminal of their own and serve no
    connection. ``None`` means none of them was given.
    """
    chosen = args.hold_secret or args.list_held_secrets
    if not chosen and args.show_held_secret is None and args.delete_held_secret is None:
        return None
    from .held_secrets import delete_held_secret, hold_secret, list_held_secrets, show_held_secret

    # The standard streams' stdlib annotations include Any; the text stream contract is stable.
    terminal, answers, errors = cast(TextIO, sys.stdout), cast(TextIO, sys.stdin), cast(TextIO, sys.stderr)
    if args.hold_secret:
        return hold_secret(single_use=args.once, terminal=terminal, answers=answers, errors=errors)
    if args.list_held_secrets:
        return list_held_secrets(terminal=terminal, errors=errors)
    if args.show_held_secret is not None:
        return show_held_secret(args.show_held_secret, terminal=terminal, answers=answers, errors=errors)
    return delete_held_secret(args.delete_held_secret, terminal=terminal, answers=answers, errors=errors)


def main() -> None:
    """Serve the person's sign-in on the selected profile, or one profile's enrolled key."""
    os.environ.setdefault("PYDANTIC_DISABLE_PLUGINS", "__all__")
    if isinstance(sys.stderr, io.TextIOWrapper):
        # The generic form is for static analysis; TextIOWrapper is not subscriptable at runtime.
        cast("io.TextIOWrapper[BinaryIO]", sys.stderr).reconfigure(newline="\n")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile-id",
        type=UUID,
        help="the profile of the enrolled key; given alone, its sign-in is resumed only while it is selected",
    )
    parser.add_argument(
        "--credential-reference",
        type=lambda value: UUID(value) if value else None,
        help="the protected reference of an enrolled key; requires --profile-id",
    )
    parser.add_argument("--surface", help="the named surface to serve; every tool and operation when omitted")
    held = parser.add_mutually_exclusive_group()
    held.add_argument(
        "--hold-secret",
        action="store_true",
        help=(
            "serve nothing: ask you, at this terminal and without showing it, for a secret a tool needs, hold it in "
            "this machine's protected credential store, and print only the reference a tool call names it by"
        ),
    )
    held.add_argument(
        "--show-held-secret",
        type=UUID,
        metavar="REFERENCE",
        help=(
            "serve nothing: show, at this terminal, the secret a tool result said is held under this reference, "
            "and delete the stored copy once you confirm you have kept it"
        ),
    )
    held.add_argument(
        "--list-held-secrets",
        action="store_true",
        help="serve nothing: list, at this terminal, each held reference and what it is held for; no secret",
    )
    held.add_argument(
        "--delete-held-secret",
        type=UUID,
        metavar="REFERENCE",
        help="serve nothing: delete, at this terminal, the secret held under this reference without showing it",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="with --hold-secret: the first tool call that presents the reference deletes the secret",
    )
    args = parser.parse_args()
    if args.once and not args.hold_secret:
        parser.error("--once belongs with --hold-secret")
    held_status = _held_secret_command(args)
    if held_status is not None:
        raise SystemExit(held_status)
    if args.credential_reference is not None and args.profile_id is None:
        parser.error("--credential-reference names the key of one profile; give that profile with --profile-id")
    required_version = os.environ.get("CADRUMO_MCP_REQUIRED_VERSION")
    if required_version is not None and version("cadrumo") != required_version:
        parser.error("installed Cadrumo cohort does not match the required version")
    from cadrumo.application.operations.mcp_surfaces import DEFAULT_MCP_SURFACE, MCP_SURFACES, mcp_surface

    try:
        surface = mcp_surface(DEFAULT_MCP_SURFACE if args.surface is None else args.surface)
    except KeyError:
        known = ", ".join(sorted(MCP_SURFACES))
        parser.error(f"unknown surface {args.surface!r}; the surfaces this version serves are: {known}")
    from cadrumo.core.logging import configure_logging

    configure_logging()
    try:
        from .server import serve

        serve(profile_id=args.profile_id, credential_reference=args.credential_reference, surface=surface)
    except ModuleNotFoundError as error:
        if error.name != "mcp":
            raise
        # stderr's platform-dependent stdlib annotation includes Any; the text stream contract is stable.
        cast(TextIO, sys.stderr).write("Cadrumo MCP requires the MCP SDK installed with cadrumo.\n")
        raise SystemExit(3) from None
