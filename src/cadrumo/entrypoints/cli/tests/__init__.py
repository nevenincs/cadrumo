"""Inert namespace for CLI test support.

Real-CLI invocation support is declared in
:mod:`cadrumo.entrypoints.cli.tests.cli_fixture_worlds`; profile-world
fixtures are defined in
:mod:`cadrumo.entrypoints.cli.tests.profile_world_fixtures`. Consumers import
each helper from its defining module; the package initializer exports no
symbols.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
