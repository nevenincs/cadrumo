"""Real-behaviour tests for the vision evidence read path.

A scan-only PDF is rasterised on this computer and an image is read as its own
bytes: the evidence resolves to base64 images (never inlined text) in memory,
nothing written to disk, and routes to :class:`VisionLLMClassifier`, which asks
the agent service for the vision role. A refusal from the service reaches the
operator as a typed reader refusal; no other lane or model is tried.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test
from cadrumo_client.contracts.model_runs import ModelRunRefusalCode

from ....adapters.outbound.llm.tests.model_run_support import serving_agent
from ....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from ....application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError, PurchaseInvoiceEvidenceReaderError
from ....application.ledger.llm_classification import ResolvedEvidence, classify_with_evidence, resolve_llm_evidence
from ....application.ledger.llm_classification_ports import EvidenceImage
from ....application.ledger.preconditions import LedgerPreconditionCondition
from ....core.config import Settings
from ....core.image_media_type import ImageMediaType
from ....core.model_catalogue import ModelRole
from ....domain.calculations.registry.tests.published_authority import leased_profile_create_context
from ....domain.transactions.llm import prompt_spec_with_saturation_fields
from ....domain.transactions.tests.vision_evidence_support import vision_transaction
from ....domain.user_profile.values import ProfileSetupState, create_user_profile_record
from ....tests.llm_vision_evidence_support import png_image
from ...ledger_llm_composition import compose_ledger_llm
from .persistence_vision_evidence_support import (
    add_evidence,
    scan_only_pdf,
)
from .persistence_vision_evidence_support import (
    profile as profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"

__all__ = ["profile"]


def _llm_ports(profile: TestRuntimeProfile):
    """Compose the canonical evidence and reader ports for the profile."""
    return compose_ledger_llm(bucket_id=profile.bucket_id, settings=profile.settings).ports


def test_scan_only_pdf_resolves_to_images_gestor_allowed_no_consent(
    profile: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    """A scan-only PDF is rasterised on this computer to declared PNG page images, even for a gestor."""
    evidence_id = add_evidence(profile, tmp_path, name="scan.pdf", data=scan_only_pdf())
    # Gestor mode ON and cloud upload NOT permitted: rasterisation is local, so
    # resolving the pages needs no consent -- this is the gestor read path.
    gestor: Settings = profile.settings.model_copy(
        update={"cadrumo_evidence_gestor_mode": True, "cadrumo_evidence_cloud_upload_permitted": False},
    )
    resolved = resolve_llm_evidence(
        vision_transaction(evidence_id),
        bucket_id=_BUCKET_ID,
        settings=gestor,
        ports=_llm_ports(profile),
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
    evidence_id = add_evidence(profile, tmp_path, name="receipt.png", data=png_image())
    resolved = resolve_llm_evidence(
        vision_transaction(evidence_id),
        bucket_id=_BUCKET_ID,
        settings=profile.settings,
        ports=_llm_ports(profile),
    )
    assert resolved is not None
    assert resolved.text is None
    assert [image.base64_data for image in resolved.images] == [base64.b64encode(png_image()).decode("ascii")]
    assert [image.media_type for image in resolved.images] == [ImageMediaType.PNG]


@pytest.mark.parametrize(
    ("name", "data_factory"),
    [("scan.pdf", scan_only_pdf), ("receipt.png", png_image)],
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
    from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record

    from ....domain.user_profile.values import UserProfileFact

    clock = datetime(2026, 1, 1, tzinfo=UTC)
    seed_test_profile_record(
        create_user_profile_record(
            context=leased_profile_create_context(),
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

    evidence_id = add_evidence(profile, tmp_path, name=name, data=data_factory())
    with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
        resolve_llm_evidence(
            vision_transaction(evidence_id),
            bucket_id=_BUCKET_ID,
            settings=profile.settings,
            ports=_llm_ports(profile),
        )
    assert "vision" in str(raised.value).lower()
    assert raised.value.terminal_precondition_verdict is not None
    assert raised.value.terminal_precondition_verdict.failed_condition_id == (
        LedgerPreconditionCondition.EVIDENCE_VISION_CAPABILITY_ENABLED.value
    )


@pytest.mark.parametrize(
    "code",
    [ModelRunRefusalCode.NO_SELECTION, ModelRunRefusalCode.MODEL_NOT_INSTALLED, ModelRunRefusalCode.LANE_UNAVAILABLE],
)
def test_a_refused_vision_lookup_reaches_the_operator_as_a_typed_reader_refusal(
    profile: TestRuntimeProfile, code: ModelRunRefusalCode
) -> None:
    """The service's refusal is the verdict the operator sees, with nothing run and nothing else tried."""
    evidence = ResolvedEvidence(
        reference="reader-unavailable",
        text=None,
        images=(EvidenceImage.from_base64(base64.b64encode(png_image()).decode("ascii"), ImageMediaType.PNG),),
    )
    ports = compose_ledger_llm(bucket_id=profile.bucket_id, settings=profile.settings).ports
    with (
        _indexed_authority_for_test().operation() as operation,
        serving_agent(lookup_refusal=code) as service,
        pytest.raises(PurchaseInvoiceEvidenceReaderError) as raised,
    ):
        classify_with_evidence(
            vision_transaction("reader-unavailable"),
            evidence,
            text_classifier=None,
            spec=prompt_spec_with_saturation_fields(year=2025, operation=operation),
            vision_classifier=None,
            vision_model=None,
            settings=profile.settings,
            ports=ports,
        )

    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.evidence[0].values["model_run_refusal"] == code.value
    assert verdict.evidence[0].values["model_role"] == ModelRole.VISION_TRANSCRIPTION.value
    assert service.lookups == [ModelRole.VISION_TRANSCRIPTION]
    assert service.runs == []
