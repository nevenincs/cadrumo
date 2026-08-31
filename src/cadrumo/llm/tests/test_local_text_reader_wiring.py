"""A text-layer document classifies on-host, with no cloud transport.

This is the gate that must be green **before** any cloud read path is
deleted. The sequencing is a constraint rather than a preference: delete the
cloud path first and there is a window in which text-layer PDFs cannot be
classified at all, which is a capability regression shipped to operators for
however long the window lasts.

The proof is deliberately run against the real wiring rather than against a
hand-built classifier. A test that constructed ``LocalTextLLMClassifier``
itself would prove the class works and say nothing about whether the classify
path reaches it -- which is precisely the failure mode this module's own
research records: three deliverables that shipped correct, tested, and
unreferenced, because a unit test passes whether or not anything calls the
code.

No model runs here. The transport is asserted structurally and through an
injected client, because running local inference crashed a development host and
terminated four concurrent agent sessions; nothing here requires a
live model.
"""

from __future__ import annotations

import inspect

import pytest

from ..models import LLMProvider
from ..text_classifier import LocalTextLLMClassifier

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_the_classify_path_reaches_the_local_text_reader() -> None:
    """The core classify path constructs the local reader when no cloud provider is given.

    Enrolment gate, not a unit test. Reads the classify seam's own source, so
    it fails if the wiring is removed even while ``LocalTextLLMClassifier``
    itself stays perfectly functional.

    Before this wiring the same branch raised ``_TEXT_PATH_NEEDS_PROVIDER``,
    making a cloud provider mandatory for any text-layer document.
    """
    # Import the defining module directly rather than through the package
    # namespace: ledger's `__init__` is inert, and a `from <pkg> import
    # <module>` edge reads as a package facade import.
    from ...application.ledger.llm_classification import classify_with_evidence

    source = inspect.getsource(classify_with_evidence)

    assert "LocalTextLLMClassifier" in source, (
        "the classify path must reach the local text reader; without it a text-layer "
        "document has no on-host route and requires a cloud transport"
    )
    assert "_TEXT_PATH_NEEDS_PROVIDER" not in source, "the text path must no longer refuse for want of a cloud provider"


def test_the_local_text_reader_requests_the_local_provider_and_carries_no_images() -> None:
    """Its request pins the LOCAL provider and sends text only.

    Two properties, and the second is the one that matters for privacy: a
    request carrying images would mean a text document was being rasterised and
    routed as a vision read, and a request without the provider override could
    fall through to whatever the settings default happens to be -- which is how
    a document ends up leaving the host by accident rather than by decision.
    """
    from ...domain.transactions.llm import prompt_spec_with_every_spending_category

    reader = LocalTextLLMClassifier(spec=prompt_spec_with_every_spending_category(year=2025))
    request = reader._request("classify this")

    assert request.provider_override is LLMProvider.LOCAL
    assert not request.images, "a text read must carry no images"
    assert request.prompt == "classify this"


def test_the_provenance_stamp_names_the_local_text_transport() -> None:
    """A persisted record can say which on-host transport read it.

    Distinct from both the vision stamp and the retired subprocess stamps, so
    the two on-host transports remain distinguishable from each other.

    This reader is on-host by CONSTRUCTION rather than by the axis having
    collapsed: its constructor declares no provider parameter, so no call site
    can ask it for an off-host read. The axis itself did not stay collapsed --
    off-host reading returned behind a consent gate -- and the readers that took
    a provider back are held to stamping the transport they actually used.
    """
    from ...domain.transactions.llm import prompt_spec_with_every_spending_category

    reader = LocalTextLLMClassifier(
        spec=prompt_spec_with_every_spending_category(year=2025),
        model="qwen2.5:3b",
    )

    assert reader.decided_by == "llm:local-text:qwen2.5:3b"
    assert reader.decided_by.startswith("llm:local-")


def test_the_text_model_default_sits_under_the_declared_hardware_floor() -> None:
    """The model is chosen under the hardware constraint, not beside it.

    The floor exists because a model that does not fit does not refuse -- it
    loads and thrashes, or is killed mid-read, and the operator sees an
    unexplained timeout. A default that exceeded its own declared floor would
    make the probe report a capable machine for a model it cannot run.

    Asserted as the PROPERTY, read from the catalogue, rather than against
    pinned model names. The pinned form reddened the moment the defaults moved
    for an unrelated reason (a licence correction), which taught nothing about
    the floor and had to be swept by hand; the property survives any default
    that still respects it.
    """
    from ...core.config import load_settings
    from ...core.model_catalogue import ModelRole, model_candidate

    settings = load_settings()
    floor = settings.cadrumo_llm_model_runtime_memory_floor_bytes

    for configured, role in (
        (settings.cadrumo_llm_ollama_text_model, ModelRole.TEXT_EXTRACTION),
        (settings.cadrumo_llm_ollama_vision_model, ModelRole.VISION_TRANSCRIPTION),
        (settings.cadrumo_llm_ollama_mapping_model, ModelRole.COLUMN_ROLE_MAPPING),
    ):
        candidate = model_candidate(configured)
        assert candidate is not None, f"the {role.value} default {configured!r} is not catalogued"
        assert candidate.serves(role)
        # The requirement is optional on the catalogue entry, and an undeclared
        # one has already fail-opened twice elsewhere -- read as zero, it makes
        # a contention check report admitted on evidence nobody has. A shipped
        # default must declare it, so that is asserted here rather than assumed.
        requirement = candidate.memory_requirement_bytes
        assert requirement is not None, f"the {role.value} default {configured!r} declares no memory requirement"
        assert requirement < floor, (
            f"the {role.value} default {configured!r} declares {requirement} bytes against a floor of {floor}"
        )

    # The text roles must stay hostable on a machine provisioned for the vision
    # default, so neither may be the heavier model.
    vision = model_candidate(settings.cadrumo_llm_ollama_vision_model)
    text = model_candidate(settings.cadrumo_llm_ollama_text_model)
    mapping = model_candidate(settings.cadrumo_llm_ollama_mapping_model)
    assert vision is not None and text is not None and mapping is not None
    vision_bytes, text_bytes, mapping_bytes = (
        vision.memory_requirement_bytes,
        text.memory_requirement_bytes,
        mapping.memory_requirement_bytes,
    )
    assert vision_bytes is not None and text_bytes is not None and mapping_bytes is not None
    assert text_bytes <= vision_bytes
    assert mapping_bytes <= text_bytes
