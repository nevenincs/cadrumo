"""MCP serving-runtime settings, owned by the harness that serves them.

``cadrumo`` is the CLI implementation, not an MCP facade, so these bounds live
here rather than as a mixin on :class:`cadrumo.core.config.Settings`. Nothing in
``cadrumo`` reads them: the concurrency limiter, the warm transport and the
stdio watchdog are all harness surfaces.

The field names are unchanged, so the environment contract is unchanged too --
``CADRUMO_MCP_SERVING_CONCURRENCY`` and its siblings still name the same
setting. Only the module that declares them moved.

:func:`override_mcp_settings` mirrors ``cadrumo.core.config.override_settings``
for these four fields alone. It is deliberately much smaller: that helper also
re-derives storage roots and repairs ``model_fields_set`` because its fields
feed the storage taxonomy, and none of these do -- they are four independent
scalars with no derived consumers.
"""

from __future__ import annotations

import contextvars
from collections.abc import Generator
from contextlib import contextmanager
from functools import cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class McpServingSettings(BaseSettings):
    """Settings bounding the MCP server's serving concurrency and warm transport."""

    model_config = SettingsConfigDict(env_ignore_empty=True)

    cadrumo_mcp_serving_concurrency: int = Field(
        default=4,
        ge=1,
        description=(
            "Maximum MCP tool calls dispatched off the event loop at once. Bounds the "
            "supervised subprocess spawn and the warm in-process worker pool so a burst "
            "cannot thrash the host; the previous anyio default admitted 40. A conservative "
            "small default suits the single-operator desktop client; raise it for a "
            "multi-client host."
        ),
    )
    cadrumo_mcp_warm_capture_wait_seconds: float = Field(
        default=5.0,
        gt=0,
        description=(
            "How long a warm in-process MCP call waits for the stdout-capture lock before "
            "degrading to the supervised subprocess transport. Bounds the blast radius of a "
            "slow or hung in-process verb: a call never queues forever behind the capture. "
            "Comfortably covers a normal warm call's sub-second-to-low-single-digit hold."
        ),
    )
    cadrumo_mcp_stdio_watchdog: bool = Field(
        default=True,
        description=(
            "Whether the MCP stdio server anchors its lifetime to the client process. The "
            "stdio contract is 'exit on stdin EOF', but on Windows an inherited pipe handle "
            "can keep stdin open after the spawning client is gone, so EOF never arrives and "
            "the server runs indefinitely - holding its warm caches and never running the "
            "interpreter-exit hooks that zeroise bound bucket sessions. The watchdog reaps the "
            "server when its client dies. Disable only to diagnose the watchdog itself: with it "
            "off, stdin EOF is the sole exit path and a leaked server is unreapable."
        ),
    )
    cadrumo_mcp_wedge_threshold_seconds: float = Field(
        default=180.0,
        gt=0,
        description=(
            "When a warm in-process call has held the stdout-capture lock past this many "
            "seconds the warm transport is declared wedged and subsequent READ/MUTATE calls "
            "route straight to the supervised subprocess (a warning Notice names the wedge) "
            "until the wedged worker completes. Defaults to the MUTATE tier ceiling, the "
            "longest an in-process call may legitimately run."
        ),
    )


settings_override: contextvars.ContextVar[McpServingSettings | None] = contextvars.ContextVar(
    "mcp_serving_settings_override",
    default=None,
)


@cache
def _constructed_settings() -> McpServingSettings:
    """Build the process-wide settings once from the environment."""
    return McpServingSettings()


def load_mcp_settings() -> McpServingSettings:
    """Return the effective serving settings.

    A context-local override installed by :func:`override_mcp_settings` wins
    inside its block; otherwise this returns the process-wide instance.
    """
    override = settings_override.get()
    if override is not None:
        return override
    return _constructed_settings()


def reset_mcp_settings_cache() -> None:
    """Forget environment-derived serving settings for controlled reloading."""
    _constructed_settings.cache_clear()


@contextmanager
def override_mcp_settings(**overrides: object) -> Generator[McpServingSettings]:
    """Override one or more serving fields for the with-block.

    Routed through ``model_validate`` rather than ``model_copy(update=)``, which
    skips validators in pydantic v2, so a malformed override fails at entry
    instead of surfacing as a nonsensical bound deep in the transport.
    """
    merged = load_mcp_settings().model_dump()
    merged.update(overrides)
    replacement = McpServingSettings.model_validate(merged)
    token = settings_override.set(replacement)
    try:
        yield replacement
    finally:
        settings_override.reset(token)


__all__ = [
    "McpServingSettings",
    "load_mcp_settings",
    "override_mcp_settings",
    "reset_mcp_settings_cache",
]
