"""Single authority for CLI paths that diverge from result-schema keys.

Most result-schema keys are derived mechanically from their live CLI path.
This module owns the exceptional path mapping and the group-callback schema
inventory so documentation, conformance gates, and MCP projection cannot drift
into separate allowlists.
"""

from __future__ import annotations

from types import MappingProxyType

GROUP_CALLBACK_SCHEMA_KEYS: frozenset[str] = frozenset(
    {
        "root.status",
        "root.app",
        "root.config",
        "config.repair",
        "ledger.participation",
        "contract",
        "agent",
        "quickfile",
    },
)

ROOT_LANDING_SCHEMA_KEYS: frozenset[str] = frozenset(
    key for key in GROUP_CALLBACK_SCHEMA_KEYS if key.startswith("root.")
)

# The operator-facing history verb moved from ``config bucket history`` to
# ``config profile history``. Its result-schema key is a stable machine contract
# and therefore remains ``config.bucket.history``.
SCHEMA_KEY_BY_CLI_PATH = MappingProxyType(
    {
        "config.profile.history": "config.bucket.history",
    },
)
CLI_PATH_BY_SCHEMA_KEY = MappingProxyType(
    {schema_key: tuple(cli_path.split(".")) for cli_path, schema_key in SCHEMA_KEY_BY_CLI_PATH.items()},
)

__all__ = [
    "CLI_PATH_BY_SCHEMA_KEY",
    "GROUP_CALLBACK_SCHEMA_KEYS",
    "ROOT_LANDING_SCHEMA_KEYS",
    "SCHEMA_KEY_BY_CLI_PATH",
]
