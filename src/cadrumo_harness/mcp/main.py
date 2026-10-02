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
    """Serve one explicitly bound profile and protected credential reference."""
    os.environ.setdefault("PYDANTIC_DISABLE_PLUGINS", "__all__")
    if isinstance(sys.stderr, io.TextIOWrapper):
        # The generic form is for static analysis; TextIOWrapper is not subscriptable at runtime.
        cast("io.TextIOWrapper[BinaryIO]", sys.stderr).reconfigure(newline="\n")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-id", type=UUID, required=True)
    parser.add_argument("--credential-reference", type=lambda value: UUID(value) if value else None)
    args = parser.parse_args()
    required_version = os.environ.get("CADRUMO_MCP_REQUIRED_VERSION")
    if required_version is not None and version("cadrumo") != required_version:
        parser.error("installed Cadrumo cohort does not match the required version")
    from cadrumo.core.logging import configure_logging

    configure_logging()
    try:
        from .server import serve

        serve(profile_id=args.profile_id, credential_reference=args.credential_reference)
    except ModuleNotFoundError as error:
        if error.name != "mcp":
            raise
        # stderr's platform-dependent stdlib annotation includes Any; the text stream contract is stable.
        cast(TextIO, sys.stderr).write("Cadrumo MCP requires the MCP SDK installed with cadrumo.\n")
        raise SystemExit(3) from None
