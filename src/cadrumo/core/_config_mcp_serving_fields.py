"""MCP serving-runtime settings: concurrency and the warm-transport wedge bounds.

Split from :mod:`~core.config` to keep the central settings facade within the
line budget. :class:`~core.config.Settings` inherits these fields with their
declared validation and defaults. They tune the MCP server's off-loop dispatch
concurrency and the warm in-process transport's capture-wait and wedge-detection
ceilings; the server reads them through :func:`~core.config.load_settings`.

See Also:
    :class:`~core.config.Settings`
        Central environment facade that inherits this mixin.
    :func:`~core.config.load_settings`
        Runtime entry point the MCP server uses to read these fields.
    :mod:`~entrypoints.mcp._transport`
        Warm/subprocess transport dispatch that consumes the capture-wait and
        wedge-threshold bounds.
    :mod:`~entrypoints.mcp._stdio_lifetime`
        Client-lifetime watchdog gated by the stdio-watchdog kill switch.
"""

from __future__ import annotations

from pydantic import Field

from ._config_llm_fields import CadrumoLlmSettings


class CadrumoMcpServingSettings(CadrumoLlmSettings):
    """Settings bounding the MCP server's serving concurrency and warm transport."""

    # ── MCP serving runtime ─────────────────────────────────────────────────
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


__all__ = ["CadrumoMcpServingSettings"]
