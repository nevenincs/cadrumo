"""Google outbound adapters: Drive, Sheets and the credential boundary.

Inert namespace. Every contract is reached at its own defining module:
``active_profile``, ``api``, ``calc_sheets_apply``, ``calc_sheets_pull``,
``document_link_resolver``, ``errors``, ``impersonation``, ``oauth_flow``, ``records``,
``session_store``.

This package re-exported its surface through the namespace. The map is
retired: a consumer names the module that defines what it imports.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
