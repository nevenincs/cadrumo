"""Cotejo-authenticity stamping on persisted live justificante captures.

Drives the real read-only AEAT CSV verifier through the credential-free local
HTTP boundary -- a real Chromium over real HTTP, never the live Sede -- and
witnesses that each verdict reaches the encrypted secure-object store and
comes back as itself.

The load-bearing property is that the verdicts stay four distinct states.
``UNAVAILABLE`` ("the check could not be completed") and ``NOT_CHECKED``
("the check was never run") are not denials, and a receipt in either state
must never read back as ``DENIED`` or as a plain boolean false.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import pytest

from ....adapters.outbound.aeat.browser.tests.real_http_boundary import (
    LocalHttpBoundary,
    open_real_browser_session,
    opened_http_boundary,
)
from ....adapters.outbound.aeat.verify.contract import VerifyBrowserSessionLike
from ....core.config import Settings
from ....core.modelo import Modelo
from ....core.period import Period
from ....tests.secure_sql import isolated_runtime_profile
from ..justificante import (
    JustificanteAuthenticity,
    JustificanteCaptureSnapshot,
    JustificanteCaptureSnapshotRepository,
    JustificanteCaptureSnapshotService,
    verify_capture_authenticity,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Canonical UUIDv4 profile identity; a readable label cannot address a bucket.
_BUCKET_ID = "1a5c0000-0000-4000-8000-000000000042"
_CSV = "ABCD1234EFGH5678"
_AEAT = Settings.external_constants().aeat
_CAPTURED_AT = datetime(2026, 7, 18, 10, 5, 0, tzinfo=UTC)

_DENIAL_HTML = (
    "<html><p>No se ha podido recuperar ningun documento catalogado con ese CSV "
    "(Codigo Seguro de Verificacion).</p></html>"
)


def _viewer_html(csv: str) -> str:
    """Return AEAT's CSV-bound document viewer, the only shape that means valid."""
    source = f"{_AEAT.domains.www2}{_AEAT.sede_paths.cotejo_document}?CSV={csv}"
    return f'<title>Visualizacion de documentos</title><iframe id="iframe-visualiza" src="{source}"></iframe>'


def _pdf_bytes(marker: bytes) -> bytes:
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Mark(" + marker + b")>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


def _capture(
    service: JustificanteCaptureSnapshotService,
    *,
    period_code: str,
    marker: bytes,
) -> JustificanteCaptureSnapshot:
    """Persist one real capture on its own work-unit axis and return it."""
    payload = _pdf_bytes(marker)
    return service.capture(
        modelo=Modelo.M130.value,
        filing_year=2026,
        period=Period.from_year_and_code(2026, period_code),
        expediente_id="202613000522456T",
        csv=_CSV,
        pdf_bytes=payload,
        pdf_sha256=hashlib.sha256(payload).hexdigest(),
        captured_at=_CAPTURED_AT,
    )


def _reread(snapshot: JustificanteCaptureSnapshot) -> JustificanteCaptureSnapshot:
    """Load ``snapshot`` back through a freshly constructed real repository."""
    return JustificanteCaptureSnapshotRepository(bucket_id=snapshot.bucket_id).load(snapshot.snapshot_id)


async def _verify_over_boundary(
    *,
    boundary: LocalHttpBoundary,
    service: JustificanteCaptureSnapshotService,
    snapshot: JustificanteCaptureSnapshot,
    profile_name: str,
) -> JustificanteCaptureSnapshot:
    """Run one real cotejo round trip over ``boundary`` and stamp the verdict.

    A fresh production browser session is opened per round trip because
    :class:`BrowserSession` owns a single live browser and refuses a second
    context after the verifier closes the first.
    """
    playwright, session = await open_real_browser_session(
        boundary=boundary,
        settings=Settings(),
        profile_name=profile_name,
    )
    try:
        return await verify_capture_authenticity(
            snapshot=snapshot,
            service=service,
            browser=cast("VerifyBrowserSessionLike", session),
        )
    finally:
        await session.close()
        await playwright.stop()


@pytest.fixture
def isolated_bucket(tmp_path: Path) -> Iterator[None]:
    """Provide a real encrypted per-bucket store for the duration of a test."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        yield


@pytest.mark.asyncio
@pytest.mark.usefixtures("isolated_bucket")
async def test_confirmed_cotejo_verdict_survives_the_encrypted_repository_roundtrip() -> None:
    """A capture AEAT confirms is persisted CONFIRMED and reloads as CONFIRMED."""
    service = JustificanteCaptureSnapshotService(bucket_id=_BUCKET_ID)
    captured = _capture(service, period_code="2T", marker=b"confirmed")
    assert captured.authenticity is JustificanteAuthenticity.NOT_CHECKED

    async with opened_http_boundary() as boundary:
        boundary.configure_html(_viewer_html(_CSV))
        stamped = await _verify_over_boundary(
            boundary=boundary,
            service=service,
            snapshot=captured,
            profile_name="justificante-authenticity-confirmed",
        )

    assert stamped.authenticity is JustificanteAuthenticity.CONFIRMED

    reloaded = _reread(captured)
    assert reloaded.authenticity is JustificanteAuthenticity.CONFIRMED
    # The verdict rides the same envelope as the receipt: neither displaces the other.
    assert reloaded.decoded_pdf_bytes() == _pdf_bytes(b"confirmed")
    assert reloaded.csv == _CSV
    assert reloaded.model_copy(update={"authenticity": JustificanteAuthenticity.NOT_CHECKED}) == captured


@pytest.mark.asyncio
@pytest.mark.usefixtures("isolated_bucket")
async def test_the_cotejo_outcomes_persist_as_distinct_states() -> None:
    """Detector teeth: an unfinished check never reads back as an AEAT denial.

    Confirmation, denial, and an unreachable cotejo surface are driven over
    one real browser against the real local HTTP boundary, and a fourth,
    never-verified capture stands alongside them. All four reload as
    themselves, and neither ``UNAVAILABLE`` nor ``NOT_CHECKED`` collapses
    into ``DENIED``.
    """
    service = JustificanteCaptureSnapshotService(bucket_id=_BUCKET_ID)
    confirmed_capture = _capture(service, period_code="1T", marker=b"yes")
    denied_capture = _capture(service, period_code="2T", marker=b"no")
    unavailable_capture = _capture(service, period_code="3T", marker=b"unknown")
    never_checked_capture = _capture(service, period_code="4T", marker=b"untouched")

    async with opened_http_boundary() as boundary:
        boundary.configure_html(_viewer_html(_CSV))
        await _verify_over_boundary(
            boundary=boundary,
            service=service,
            snapshot=confirmed_capture,
            profile_name="justificante-authenticity-confirms",
        )

        boundary.configure_html(_DENIAL_HTML)
        await _verify_over_boundary(
            boundary=boundary,
            service=service,
            snapshot=denied_capture,
            profile_name="justificante-authenticity-denies",
        )

        # A real mid-request disconnect: the boundary drops the connection, so
        # the navigation genuinely fails rather than returning a page that
        # could be read as an answer in either direction.
        boundary.configure("sensitive-error")
        await _verify_over_boundary(
            boundary=boundary,
            service=service,
            snapshot=unavailable_capture,
            profile_name="justificante-authenticity-unreachable",
        )

    verdicts = {
        "confirmed": _reread(confirmed_capture).authenticity,
        "denied": _reread(denied_capture).authenticity,
        "unavailable": _reread(unavailable_capture).authenticity,
        "never_checked": _reread(never_checked_capture).authenticity,
    }

    assert verdicts == {
        "confirmed": JustificanteAuthenticity.CONFIRMED,
        "denied": JustificanteAuthenticity.DENIED,
        "unavailable": JustificanteAuthenticity.UNAVAILABLE,
        "never_checked": JustificanteAuthenticity.NOT_CHECKED,
    }
    assert len(set(verdicts.values())) == 4
    assert verdicts["unavailable"] is not JustificanteAuthenticity.DENIED
    assert verdicts["never_checked"] is not JustificanteAuthenticity.DENIED
    # An unfinished check is not a proven negative, and the receipt is intact.
    assert _reread(unavailable_capture).decoded_pdf_bytes() == _pdf_bytes(b"unknown")


@pytest.mark.usefixtures("isolated_bucket")
def test_restamping_a_verdict_replaces_it_without_touching_the_receipt() -> None:
    """A later cotejo answer supersedes the earlier one in place."""
    service = JustificanteCaptureSnapshotService(bucket_id=_BUCKET_ID)
    captured = _capture(service, period_code="2T", marker=b"restamp")

    unavailable = service.stamp_authenticity(
        snapshot=captured,
        authenticity=JustificanteAuthenticity.UNAVAILABLE,
    )
    assert _reread(captured).authenticity is JustificanteAuthenticity.UNAVAILABLE

    confirmed = service.stamp_authenticity(
        snapshot=unavailable,
        authenticity=JustificanteAuthenticity.CONFIRMED,
    )
    reloaded = _reread(captured)
    assert confirmed.authenticity is JustificanteAuthenticity.CONFIRMED
    assert reloaded.authenticity is JustificanteAuthenticity.CONFIRMED
    assert reloaded.decoded_pdf_bytes() == captured.decoded_pdf_bytes()
    assert reloaded.pdf_sha256 == captured.pdf_sha256


@pytest.mark.usefixtures("isolated_bucket")
def test_persisted_snapshot_without_an_authenticity_key_is_not_checked() -> None:
    """A capture written before the stamp existed makes no authenticity claim."""
    service = JustificanteCaptureSnapshotService(bucket_id=_BUCKET_ID)
    captured = _capture(service, period_code="2T", marker=b"legacy")

    legacy_payload = captured.model_dump()
    del legacy_payload["authenticity"]

    restored = JustificanteCaptureSnapshot.model_validate(legacy_payload)
    assert restored.authenticity is JustificanteAuthenticity.NOT_CHECKED
    assert restored == captured
