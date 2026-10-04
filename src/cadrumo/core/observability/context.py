"""Typed context variables consumed by structured event logging."""

from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime

from pydantic import BaseModel

from ..identity.digest import ContentDigest, ContentDigestOrAbsent
from ..models import STRICT_FROZEN_CONFIG
from .models import ArgumentRecord


class RunContextInfo(BaseModel):
    """Immutable bag of run-level metadata exposed to call sites.

    Carries run and step correlation metadata for structured log records.

    Attributes:
        run_id: 16-char lowercase hex identifier for this run.
        entrypoint: Stable string identifying the CLI entry point
            (e.g. ``"program workflow run"``).
        started_at: Wall-clock UTC timestamp captured at run-context
            enter.
        arguments: Tuple of :class:`ArgumentRecord` capturing CLI flags and
            positional values for diagnostic correlation.
        corpus_sha256: Fingerprint of the effective :class:`Settings`
            configuration at enter time.
        db_sha256: Fingerprint of the canonical application data root
            (``Settings.cadrumo_local_storage_root``) at enter time,
            excluding regenerable cache subdirectories.
        cert_fingerprint: SHA-256 of the configured PKCS#12 certificate,
            or ``""`` when no cert path is configured.
        initial_step_id: Step identifier emitted with the first
            ``STEP_START`` boundary event.
    """

    model_config = STRICT_FROZEN_CONFIG

    run_id: str
    entrypoint: str
    started_at: datetime
    arguments: tuple[ArgumentRecord, ...]
    corpus_sha256: ContentDigest
    db_sha256: ContentDigest
    cert_fingerprint: ContentDigestOrAbsent
    initial_step_id: str


RUN_CONTEXT_VAR: ContextVar[RunContextInfo | None] = ContextVar(
    "_aeat_run_ctx",
    default=None,
)

STEP_CONTEXT_VAR: ContextVar[str | None] = ContextVar(
    "_aeat_step_ctx",
    default=None,
)
