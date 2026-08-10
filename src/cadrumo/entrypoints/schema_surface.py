"""Single authority for CLI paths that diverge from result-schema keys.

Most result-schema keys are derived mechanically from their live CLI path.
This module owns the exceptional path mapping and the group-callback schema
inventory so documentation, conformance gates, and MCP projection cannot drift
into separate allowlists.
"""

from __future__ import annotations

from types import MappingProxyType

from ..core.product_identity import PRODUCT_IDENTITY

CALLBACK_SCHEMA_KEY_BY_CLI_PATH = MappingProxyType(
    {
        (): "root.status",
        ("app",): "root.app",
        ("config",): "root.config",
        ("config", "repair"): "config.repair",
        ("app", "ledger", "participation"): "ledger.participation",
        ("app", "contract"): "contract",
        ("app", "agent"): "agent",
        ("app", "quickfile"): "quickfile",
    },
)
"""Callback paths that emit a result under their own registered schema key."""

CALLBACK_RESULT_REUSE_BY_CLI_PATH = MappingProxyType(
    {
        ("config", "profile", "descendiente"): "config.profile.descendiente.list",
    },
)
"""Callback paths that intentionally emit an already-registered leaf result."""

CALLBACK_EXCLUSION_REASON_BY_CLI_PATH = MappingProxyType(
    {
        ("app", "diagnostics"): "no_args_is_help group emits help rather than a JSON envelope",
    },
)
"""Live callback paths deliberately outside the JSON result-schema surface."""

GROUP_CALLBACK_SCHEMA_KEYS: frozenset[str] = frozenset(CALLBACK_SCHEMA_KEY_BY_CLI_PATH.values())

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

APP_NAMESPACE_FLATTEN: frozenset[str] = frozenset(
    {"diagnostics", "ledger", "modelo", "overview", "registry", "review"},
)
"""``app`` subgroups whose schema keys drop the ``app.`` prefix."""

APP_NAMESPACE_PASSTHROUGH: frozenset[str] = frozenset({"live"})
"""``app`` subgroups whose schema keys keep the ``app.`` prefix."""


def normalise_cli_path_to_schema_key(path: tuple[str, ...]) -> str:
    """Project a CLI leaf-command path onto its result-schema registry key.

    The projection is the whole convention by which a live command finds its
    schema: hyphens become underscores, the executable token is dropped, the
    ``app.`` prefix is dropped for the flattened namespaces and kept for the
    passthrough ones, and the exceptional mapping applies last.

    It lives here, beside the exception table it consults, because the
    documentation generator and the conformance gate must answer "which schema
    key does this command emit?" identically. A second copy lets the generator
    document one key while the gate enforces another, and the disagreement is
    invisible until a reader follows the docs to a key that does not exist.

    Args:
        path: Command name tokens from the root, e.g.
            ``("aeat", "app", "modelo", "work", "calculate")``.

    Returns:
        The dot-joined registry key, e.g. ``"modelo.work.calculate"``.
    """
    tokens = [token.replace("-", "_") for token in path]
    if tokens and tokens[0] == PRODUCT_IDENTITY.cli_executable:
        tokens = tokens[1:]
    if len(tokens) >= 2 and tokens[0] == "app":
        head = tokens[1]
        if head in APP_NAMESPACE_FLATTEN:
            tokens = tokens[1:]
        elif head in APP_NAMESPACE_PASSTHROUGH:
            pass  # keep the ``app.`` prefix
    normalised = ".".join(tokens)
    return SCHEMA_KEY_BY_CLI_PATH.get(normalised, normalised)


__all__ = [
    "APP_NAMESPACE_FLATTEN",
    "APP_NAMESPACE_PASSTHROUGH",
    "CALLBACK_EXCLUSION_REASON_BY_CLI_PATH",
    "CALLBACK_RESULT_REUSE_BY_CLI_PATH",
    "CALLBACK_SCHEMA_KEY_BY_CLI_PATH",
    "CLI_PATH_BY_SCHEMA_KEY",
    "GROUP_CALLBACK_SCHEMA_KEYS",
    "ROOT_LANDING_SCHEMA_KEYS",
    "SCHEMA_KEY_BY_CLI_PATH",
    "normalise_cli_path_to_schema_key",
]
