"""Public test-support facade for the CLI test package.

Re-exports the real-CLI profile-minting helpers so a consumer outside this
package (e.g. an application-layer integration test that needs a genuinely
minted taxpayer profile the encrypted store can load) imports them from the
package top level rather than reaching into the private
:mod:`cadrumo.entrypoints.cli.tests._profile_cli_support` module.
"""

from __future__ import annotations

from ._ledger_ux_support import _open_ledger_ux_session as open_ledger_ux_session
from ._profile_cli_support import create_quiet_profile, edit_quiet_profile, profile_rows

__all__ = [
    "create_quiet_profile",
    "edit_quiet_profile",
    "open_ledger_ux_session",
    "profile_rows",
]
