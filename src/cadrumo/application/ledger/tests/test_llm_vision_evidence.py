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

from ....core.image_media_type import ImageMediaType
from ....core.config import Settings
from ....domain.transactions.llm import prompt_spec_with_saturation_fields
from ....domain.user_profile.values import ProfileSetupState
from ....llm.models import MultimodalImageInput
from ....llm.vision_classifier import LocalVisionLLMClassifier
from ....tests.llm_vision_evidence_support import _png_image, _transaction
from ....tests.persistence_vision_evidence_support import (
    _add_evidence,
    _scan_only_pdf,
)
from ....tests.persistence_vision_evidence_support import (
    profile as profile,
)
from ....tests.secure_sql import TestRuntimeProfile
from ...provisioning import ProvisioningPreconditionCondition
from ..evidence import PurchaseInvoiceEvidenceInputError
from ..llm_classification import ResolvedEvidence, _resolve_evidence, classify_with_evidence
from ..preconditions import LedgerPreconditionCondition

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"

__all__ = ["profile"]


def test_scan_only_pdf_resolves_to_images_gestor_allowed_no_consent(
    profile: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    """A scan-only PDF resolves to declared PNG page images on-host, even for a gestor."""
    evidence_id = _add_evidence(profile, tmp_path, name="scan.pdf", data=_scan_only_pdf())
    # Gestor mode ON and cloud upload NOT permitted: the on-host vision path must
    # still resolve (no cloud consent needed) -- this is the gestor read path.
    gestor: Settings = profile.settings.model_copy(
        update={"cadrumo_evidence_gestor_mode": True, "cadrumo_evidence_cloud_upload_permitted": False},
    )
    resolved = _resolve_evidence(
        _transaction(evidence_id),
        bucket_id=_BUCKET_ID,
        settings=gestor,
    )
    assert resolved is not None
    assert resolved.text is None
    assert resolved.is_images
    page = resolved.images[0]
    assert base64.b64decode(page.base64_data)[:8] == b"\x89PNG\r\n\x1a\n"
    # The rasteriser only ever emits PNG, so the declared type is knowledge
    # rather than a sniff -- but it still has to MATCH the bytes above, which is
    # the pairing a declared media type exists to keep honest.
    assert page.media_type is ImageMediaType.PNG
    assert resolved.reference == evidence_id


def test_image_evidence_resolves_to_images(profile: TestRuntimeProfile, tmp_path: Path) -> None:
    """An image invoice resolves to its bytes AND the type those bytes actually are.

    An attachment is whatever format the operator had, so unlike a rasterised
    page its media type cannot be known by construction -- it is detected from
    the bytes. Pinning it here is what stops a PNG travelling to a vision model
    labelled as something else.
    """
    evidence_id = _add_evidence(profile, tmp_path, name="receipt.png", data=_png_image())
    resolved = _resolve_evidence(
        _transaction(evidence_id),
        bucket_id=_BUCKET_ID,
        settings=profile.settings,
    )
    assert resolved is not None
    assert resolved.text is None
    assert [image.base64_data for image in resolved.images] == [base64.b64encode(_png_image()).decode("ascii")]
    assert [image.media_type for image in resolved.images] == [ImageMediaType.PNG]


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
    """An ``llm_vision=off`` profile refuses BOTH on-host read modes.

    The capability gate sits past the text-layer early return, so it must cover
    every on-host read mode: a scan-only PDF (rasterise path) and an image
    attachment (direct-bytes path). Both reach the gate and must refuse with an
    instructive, non-silent error naming the opt-in command.
    """
    from ....domain.user_profile.values import UserProfileFact, UserProfileRecord
    from ....tests.profile_capsule import seed_test_profile_record

    clock = datetime(2026, 1, 1, tzinfo=UTC)
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
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
        )
    assert "vision" in str(raised.value).lower()
    assert raised.value.terminal_precondition_verdict is not None
    assert raised.value.terminal_precondition_verdict.failed_condition_id == (
        LedgerPreconditionCondition.EVIDENCE_VISION_CAPABILITY_ENABLED.value
    )


def test_unreachable_reader_preserves_the_provisioning_refusal(
    profile: TestRuntimeProfile,
) -> None:
    """A real reader connection failure carries its machine facts and exact verdict."""
    settings = profile.settings.model_copy(
        update={
            "cadrumo_llm_ollama_chat_url": "http://127.0.0.1:1/api/chat",
            "cadrumo_llm_vision_read_timeout_s": 1,
        },
    )
    evidence = ResolvedEvidence(
        reference="reader-unavailable",
        text=None,
        images=(
            MultimodalImageInput.from_base64(
                base64.b64encode(_png_image()).decode("ascii"),
                ImageMediaType.PNG,
            ),
        ),
    )
    reader = LocalVisionLLMClassifier(spec=prompt_spec_with_saturation_fields(year=2025), settings=settings)

    with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
        classify_with_evidence(
            _transaction("reader-unavailable"),
            evidence,
            text_classifier=None,
            spec=prompt_spec_with_saturation_fields(year=2025),
            vision_classifier=reader,
            vision_model=None,
            settings=settings,
        )

    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE.value
    assert verdict.evidence[0].values["runtime_reachable"] is False
