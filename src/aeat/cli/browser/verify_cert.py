"""``aeat browser verify-cert`` — read-only live certificate verification."""

from __future__ import annotations

import asyncio
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import typer
from playwright.async_api import async_playwright
from pydantic import BaseModel, ConfigDict

from aeat.auth import (
    CertificateBackend,
    CertificateError,
    CertificateLoadError,
    HandshakeResult,
    load_certificate_from_settings,
    verify_handshake,
)
from aeat.browser.profile import Profile
from aeat.browser.session import BrowserError, BrowserSession
from aeat.config import Settings
from aeat.status import StatusCache, StatusReader, StatusReaderError


class CertificateVerificationResult(BaseModel):
    """Structured outcome for the live certificate verification flow."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    subject: str
    handshake_status_code: int
    handshake_url: str
    expedientes_count: int
    sample_expediente_ids: tuple[str, ...]
    verified_at: datetime


class VerifierLike(Protocol):
    """Structural protocol used by the CLI command and its tests."""

    async def verify(self) -> CertificateVerificationResult | HandshakeResult:
        """Run the verification flow."""
        ...


class _RealVerifier:
    """Real read-only verifier: handshake first, expedientes second."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def verify(self) -> CertificateVerificationResult | HandshakeResult:
        _require_browser_certificate_backend(self._settings)
        cert = load_certificate_from_settings(self._settings)
        handshake = verify_handshake(cert, self._settings.aeat_certificate_verify_url)
        if not handshake.success:
            return handshake

        async with async_playwright() as playwright:
            with tempfile.TemporaryDirectory(prefix="aeat-live-cert-auth-") as cache_dir:
                profile = Profile(
                    name=self._settings.aeat_default_profile_name,
                    storage_state_path=(
                        self._settings.aeat_token_dir / f"{self._settings.aeat_default_profile_name}.json"
                    ),
                )
                session = BrowserSession(
                    playwright=playwright,
                    settings=self._settings,
                    profile=profile,
                    auth_backend=cert,
                )
                reader = StatusReader(
                    browser_session=session,
                    cert_backend=cert,
                    cache=StatusCache(Path(cache_dir), ttl_s=self._settings.aeat_status_cache_ttl_s),
                    settings=self._settings,
                    tax_id=cert.sha256_thumbprint,
                )
                async with reader:
                    expedientes = await reader.fetch_expedientes(use_cache=False)

        return CertificateVerificationResult(
            subject=cert.subject,
            handshake_status_code=handshake.status_code,
            handshake_url=self._settings.aeat_certificate_verify_url,
            expedientes_count=len(expedientes),
            sample_expediente_ids=tuple(item.expediente_id for item in expedientes[:5]),
            verified_at=datetime.now(UTC),
        )


VERIFY_FACTORY = _RealVerifier
"""Factory seam for tests: returns a concrete verifier implementation."""


def _require_browser_certificate_backend(settings: Settings) -> None:
    """Reject verify-only backends before opening a browser session."""
    if settings.aeat_certificate_backend is not CertificateBackend.PLAYWRIGHT_CONTEXT:
        raise CertificateLoadError("AEAT_CERTIFICATE_BACKEND must be PLAYWRIGHT_CONTEXT for `aeat browser verify-cert`")


def _render_human(result: CertificateVerificationResult) -> str:
    sample = ", ".join(result.sample_expediente_ids) if result.sample_expediente_ids else "(none)"
    return (
        f"subject={result.subject} handshake_status={result.handshake_status_code} "
        f"expedientes_count={result.expedientes_count} sample_ids=[{sample}]"
    )


def verify_cert_cmd(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit JSON instead of a human summary.",
    ),
) -> None:
    """Run the sanctioned read-only live certificate verification flow."""
    settings = Settings()

    async def _run() -> CertificateVerificationResult | HandshakeResult:
        verifier = VERIFY_FACTORY(settings)
        return await verifier.verify()

    try:
        result = asyncio.run(_run())
    except CertificateError as exc:
        typer.echo(f"certificate verification failed before handshake: {exc.__class__.__name__}: {exc}")
        raise typer.Exit(code=2) from exc
    except (BrowserError, StatusReaderError, RuntimeError) as exc:
        typer.echo(f"certificate verification failed during authenticated read: {exc.__class__.__name__}: {exc}")
        raise typer.Exit(code=4) from exc

    if isinstance(result, HandshakeResult):
        typer.echo(f"certificate verification failed during handshake: {result.error_message or 'unknown error'}")
        raise typer.Exit(code=3)

    if json_output:
        typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        typer.echo(_render_human(result))
    raise typer.Exit(code=0)


__all__ = ["VERIFY_FACTORY", "CertificateVerificationResult", "verify_cert_cmd"]
