"""Inert namespace for CLI test support.

The real-CLI profile-minting helpers are defined in
:mod:`cadrumo.entrypoints.cli.tests._profile_cli_support`. Consumers import
them from that module; the package initializer exports no symbols.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
