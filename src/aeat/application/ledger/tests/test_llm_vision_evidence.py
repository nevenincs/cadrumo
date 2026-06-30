"""Real-behaviour tests for the on-host vision evidence read path.

A scan-only PDF or an image is read in memory by a LOCAL vision model: the
evidence resolves to base64 images (never inlined text), routes to the
:class:`LocalVisionLLMClassifier`, and is sent to a loopback Ollama endpoint --
no cloud consent, gestor-allowed, nothing written to disk, no byte leaving the
host. The classifier is driven against a real local HTTP server (no mocks) and
its response is parsed through the same allow-list the subprocess path uses.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core.config import Settings
from ....tests.secure_sql import TestRuntimeProfile
from .._evidence import PurchaseInvoiceEvidenceInputError
from .._llm_classification import _resolve_evidence
from ._llm_vision_evidence_support import (
    _add_evidence,
    _png_image,
    _scan_only_pdf,
    _transaction,
)
from ._llm_vision_evidence_support import (
    profile as profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"

__all__ = ["profile"]


def test_scan_only_pdf_resolves_to_images_gestor_allowed_no_consent(
    profile: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    """A scan-only PDF resolves to base64 PNG images on-host, even for a gestor."""
    evidence_id = _add_evidence(profile, tmp_path, name="scan.pdf", data=_scan_only_pdf())
    # Gestor mode ON and cloud upload NOT permitted: the on-host vision path must
    # still resolve (no cloud consent needed) -- this is the gestor read path.
    gestor: Settings = profile.settings.model_copy(
        update={"aeat_evidence_gestor_mode": True, "aeat_evidence_cloud_upload_permitted": False},
    )
    resolved = _resolve_evidence(
        _transaction(evidence_id),
        bucket_id=_BUCKET_ID,
        settings=gestor,
        evidence_acknowledged=False,
    )
    assert resolved is not None
    assert resolved.text is None
    assert resolved.is_images
    assert base64.b64decode(resolved.images[0])[:8] == b"\x89PNG\r\n\x1a\n"
    assert resolved.reference == evidence_id


def test_image_evidence_resolves_to_images(profile: TestRuntimeProfile, tmp_path: Path) -> None:
    """An image invoice resolves to its base64 bytes for the on-host vision read."""
    evidence_id = _add_evidence(profile, tmp_path, name="receipt.png", data=_png_image())
    resolved = _resolve_evidence(
        _transaction(evidence_id),
        bucket_id=_BUCKET_ID,
        settings=profile.settings,
        evidence_acknowledged=False,
    )
    assert resolved is not None
    assert resolved.text is None
    assert resolved.images == (base64.b64encode(_png_image()).decode("ascii"),)


@pytest.mark.parametrize(
    ("name", "data_factory"),
    [("scan.pdf", _scan_only_pdf), ("receipt.png", _png_image)],
    ids=["scan-pdf", "image"],
)
def test_llm_vision_off_refuses_both_on_host_read_modes(
    profile: TestRuntimeProfile,
    tmp_path: Path,
    name: str,
    data_factory: Callable[[], bytes],
) -> None:
    """An ``llm_vision=off`` profile refuses BOTH on-host read modes (honesty review M1).

    The capability gate sits past the text-layer early return, so it must cover
    every on-host read mode: a scan-only PDF (rasterise path) and an image
    attachment (direct-bytes path). Both reach the gate and must refuse with an
    instructive, non-silent error naming the opt-in command.
    """
    from ....domain.user_profile import UserProfileFact, UserProfileRecord
    from ...user_profile import UserProfileLifecycleRepository

    clock = datetime(2026, 1, 1, tzinfo=UTC)
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID).save(
        UserProfileRecord(
            profile_id=_BUCKET_ID,
            display_name="Vision opted out",
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="capabilities.llm_vision", value=False),
            ),
            created_at=clock,
            updated_at=clock,
        ),
    )

    evidence_id = _add_evidence(profile, tmp_path, name=name, data=data_factory())
    with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
        _resolve_evidence(
            _transaction(evidence_id),
            bucket_id=_BUCKET_ID,
            settings=profile.settings,
            evidence_acknowledged=False,
        )
    assert "vision" in str(raised.value).lower()
    assert "llm_vision on" in (raised.value.suggestion or "")


