"""Runtime settings layered on top of timeout config.

Defines :class:`CadrumoRuntimeSettings`, which adds the document-read deadline
consumed by the LLM-backed invoice-read pipeline, the browser, lock, session and
log settings, and the fixed address of the local AI server. Cadrumo sets no model
option and admits no model load: the agent decides both.
"""

from __future__ import annotations

from typing import Final

from pydantic import Field

from .config_timeouts import CadrumoTimeoutSettings

#: The loopback address the runtime manager's local AI server listens on, which the agent
#: service hands to the agent it hosts. The package's environment declaration states the
#: same address for the native side; a package-side test keeps the two equal.
LOCAL_AI_SERVER_ADDRESS: Final = "127.0.0.1:23743"


class CadrumoRuntimeSettings(CadrumoTimeoutSettings):
    """LLM runtime tuning fields layered on top of timeouts."""

    cadrumo_llm_vision_read_timeout_s: int = Field(
        default=300,
        gt=0,
        description=(
            "Deadline, in seconds, of one agent run that reads a document; larger than "
            "the general LLM timeout because a model on consumer hardware (CPU or a "
            "modest GPU) can take one to several minutes to read an invoice"
        ),
    )
    cadrumo_browser_locale: str = Field(
        default="es-ES",
        min_length=2,
        description="Default browser locale passed to Playwright context (BCP-47 tag)",
    )
    cadrumo_browser_timezone: str = Field(
        default="Europe/Madrid",
        min_length=1,
        description="Default IANA timezone string passed to Playwright context",
    )
    cadrumo_browser_viewport_width: int = Field(
        default=1366,
        gt=0,
        description="Default Playwright viewport width (px) for AEAT sede sessions",
    )
    cadrumo_browser_viewport_height: int = Field(
        default=900,
        gt=0,
        description="Default Playwright viewport height (px) for AEAT sede sessions",
    )
    cadrumo_file_lock_timeout_s: float = Field(
        default=30.0,
        gt=0,
        description="Default exclusive file-lock acquisition timeout (seconds)",
    )
    cadrumo_file_lock_retry_backoff_s: float = Field(
        default=0.05,
        gt=0,
        description="Sleep interval (seconds) between non-blocking file-lock acquire attempts",
    )
    cadrumo_bucket_lock_poll_interval_s: float = Field(
        default=0.1,
        gt=0,
        description="Polling interval (seconds) for bucket lockfile acquisition retries",
    )
    cadrumo_bucket_default_idle_lock_minutes: int = Field(
        default=15,
        gt=0,
        description="Fallback idle-lock window (minutes) when a bucket manifest omits the value",
    )
    cadrumo_bucket_default_session_absolute_minutes: int = Field(
        default=240,
        gt=0,
        ge=60,
        le=720,
        description=(
            "Fallback absolute session-lifetime cap (minutes) when a bucket manifest omits "
            "session_absolute_minutes; fixed at login and never refreshed, so a touched-forever "
            "session still seals at this cap (default 4 h, 12 h hard ceiling)"
        ),
    )
    cadrumo_auth_clave_movil_lock_buffer_s: int = Field(
        default=90,
        gt=0,
        description="Headroom (seconds) added to ``cadrumo_clave_movil_timeout_ms`` for the acquisition lock TTL",
    )
    cadrumo_auth_certificate_lock_ttl_s: int = Field(
        default=180,
        gt=0,
        description="Acquisition lock TTL (seconds) for certificate-backed AEAT auth flows",
    )
    cadrumo_log_stderr_level: str = Field(
        default="ERROR",
        description="Log level for the stderr handler installed by ``cadrumo.core.logging``",
    )
    cadrumo_log_file_level: str = Field(
        default="DEBUG",
        description="Log level for the file handler installed by ``cadrumo.core.logging``",
    )
    cadrumo_log_file_max_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=1,
        description=("Size cap (bytes) for cadrumo.log before the rotating file handler rolls over; default 10 MiB"),
    )
    cadrumo_log_file_backup_count: int = Field(
        default=5,
        ge=0,
        description="Number of rotated cadrumo.log backups retained by the rotating file handler",
    )
    cadrumo_log_root_level: str = Field(
        default="DEBUG",
        description="Root logger level installed by ``cadrumo.core.logging``",
    )
