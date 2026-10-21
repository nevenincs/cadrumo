"""Installed local MCP stdio entry point."""

from __future__ import annotations

import argparse
import io
import os
import sys
from importlib.metadata import version
from typing import BinaryIO, TextIO, cast
from uuid import UUID


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
        help="the protected reference of a key the person issued with config automation; requires --profile-id",
    )
    parser.add_argument("--surface", help="the named surface to serve; every tool and operation when omitted")
    args = parser.parse_args()
    if args.credential_reference is not None and args.profile_id is None:
        parser.error("--credential-reference names the key of one profile; give that profile with --profile-id")
    required_version = os.environ.get("CADRUMO_MCP_REQUIRED_VERSION")
    if required_version is not None and version("cadrumo") != required_version:
        parser.error("installed Cadrumo cohort does not match the required version")
    from .surfaces import DEFAULT_MCP_SURFACE, MCP_SURFACES, mcp_surface

    try:
        surface = mcp_surface(DEFAULT_MCP_SURFACE if args.surface is None else args.surface)
    except KeyError:
        known = ", ".join(sorted(MCP_SURFACES))
        parser.error(f"unknown surface {args.surface!r}; the surfaces this version serves are: {known}")
    from cadrumo.core.logging import configure_logging, register_first_party_logger

    register_first_party_logger("cadrumo_harness")
    configure_logging()
    from cadrumo.core.diagnostic_log import diagnostic_process

    try:
        from .server import serve

        with diagnostic_process("external_client"):
            serve(profile_id=args.profile_id, credential_reference=args.credential_reference, surface=surface)
    except ModuleNotFoundError as error:
        if error.name != "mcp":
            raise
        # stderr's platform-dependent stdlib annotation includes Any; the text stream contract is stable.
        cast(TextIO, sys.stderr).write("Cadrumo MCP requires the MCP SDK installed with cadrumo.\n")
        raise SystemExit(3) from None
