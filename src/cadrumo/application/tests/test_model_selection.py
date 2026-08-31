"""Real-behavior selection matrix over injected hardware profiles.

Every hardware figure reaching these assertions is constructed here and passed
through :func:`~application.provisioning.probe_hardware_profile`'s own
injection arguments, so the production model construction, the production
binding-arena rule and the production comparison all run -- while nothing about
this host's actual memory or device state (which changes minute to minute under
an agent fleet) can reach a result. No model is loaded, pulled or invoked.

The matrix covers four axes and their interactions: the measured tier
(unmeasured, constrained, modest, capable), the licence posture (commercial and
non-commercial), the capability floor (the configured context window), and the
operator override (catalogued, uncatalogued, and licence-barred). Every refusal
case carries a positive control asserting the accept case passes through the
same call, so a refusal cannot pass for the wrong reason. Advisory *reasons* are
asserted as typed enum members; the localized advisory prose is asserted only
for non-emptiness, never by its wording.
"""

from __future__ import annotations

import pytest

from ...core import AcceleratorKind, HardwareTier
from ...core.model_catalogue import (
    DeploymentLicencePosture,
    ModelRole,
    ModelRuntime,
    ModelSelectionAdvisory,
    candidates_for_role,
    model_candidate,
)
from ...core.config import load_settings, override_settings
from ..provisioning import (
    AcceleratorDevice,
    AcceleratorReading,
    HardwareProfile,
    SystemMemoryReading,
    binding_free_bytes,
    probe_hardware_profile,
    select_model_for_role,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_GIB = 1024**3


def _cuda_profile(free_vram_bytes: int | None) -> HardwareProfile:
    """Build a measured single-NVIDIA-device profile with the given free VRAM."""
    return probe_hardware_profile(
        memory=SystemMemoryReading(total_bytes=32 * _GIB, free_bytes=20 * _GIB),
        accelerator=AcceleratorReading(
            kind=AcceleratorKind.NVIDIA_CUDA,
            devices=(
                AcceleratorDevice(
                    index=0,
                    name="injected device",
                    total_vram_bytes=16 * _GIB,
                    free_vram_bytes=free_vram_bytes,
                ),
            ),
            detail="injected",
        ),
    )


def _cpu_profile(free_bytes: int | None) -> HardwareProfile:
    """Build a measured accelerator-absent profile bound by system memory."""
    return probe_hardware_profile(
        memory=SystemMemoryReading(total_bytes=16 * _GIB, free_bytes=free_bytes),
        accelerator=AcceleratorReading(kind=AcceleratorKind.NONE, detail="injected: no devices"),
    )


def _unmeasurable_profile() -> HardwareProfile:
    """Build a profile whose accelerator could not be read at all."""
    return probe_hardware_profile(
        memory=SystemMemoryReading(total_bytes=16 * _GIB, free_bytes=12 * _GIB),
        accelerator=AcceleratorReading(kind=AcceleratorKind.UNKNOWN, detail="injected: NVML absent"),
    )


def test_the_binding_arena_follows_the_measured_accelerator_kind() -> None:
    """Device memory binds a device, system memory binds a measured-absent one, unknown binds nothing."""
    assert binding_free_bytes(_cuda_profile(6 * _GIB)) == 6 * _GIB
    assert binding_free_bytes(_cpu_profile(6 * _GIB)) == 6 * _GIB
    assert binding_free_bytes(_unmeasurable_profile()) is None


@pytest.mark.parametrize(
    ("free_bytes", "expected"),
    [
        (None, HardwareTier.UNMEASURED),
        (2 * _GIB, HardwareTier.CONSTRAINED),
        (6 * _GIB, HardwareTier.MODEST),
        (12 * _GIB, HardwareTier.CAPABLE),
    ],
)
def test_the_reported_tier_bands_the_measured_free_figure(free_bytes: int | None, expected: HardwareTier) -> None:
    """Each band is reachable and unknown maps to UNMEASURED, never to the lowest band."""
    selection = select_model_for_role(ModelRole.VISION_TRANSCRIPTION, profile=_cuda_profile(free_bytes))
    assert selection.tier is expected


@pytest.mark.parametrize("role", list(ModelRole))
def test_a_capable_machine_still_gets_the_weakest_eligible_candidate(role: ModelRole) -> None:
    """Selection is bounded from below: headroom to spare does not buy a larger model."""
    settings = load_settings()
    selection = select_model_for_role(role, profile=_cuda_profile(14 * _GIB))
    assert selection.selected
    eligible = [
        candidate
        for candidate in candidates_for_role(role)
        if candidate.max_context_tokens >= settings.cadrumo_llm_ollama_num_ctx
        and candidate.permitted_under(DeploymentLicencePosture.COMMERCIAL)
    ]
    assert selection.runtime_id == eligible[0].runtime_id
    assert selection.advisories == ()


def test_the_context_floor_excludes_a_smaller_candidate_on_capability() -> None:
    """The smallest vision model is skipped because its window cannot hold the request.

    Proven by moving the floor rather than by naming the model: with the window
    lowered under its capacity the same call selects it, so the exclusion is
    shown to be the context comparison and not an unrelated filter.
    """
    profile = _cuda_profile(14 * _GIB)
    smallest = candidates_for_role(ModelRole.VISION_TRANSCRIPTION)[0]

    at_default = select_model_for_role(ModelRole.VISION_TRANSCRIPTION, profile=profile)
    assert at_default.runtime_id != smallest.runtime_id

    with override_settings(cadrumo_llm_ollama_num_ctx=smallest.max_context_tokens):
        lowered = select_model_for_role(ModelRole.VISION_TRANSCRIPTION, profile=profile)
    assert lowered.runtime_id == smallest.runtime_id
    assert lowered.selected


def test_a_commercial_posture_never_selects_a_licence_barred_candidate() -> None:
    """No automatic selection in any role may land on a commercial-use bar."""
    for role in ModelRole:
        selection = select_model_for_role(role, profile=_cuda_profile(14 * _GIB))
        assert selection.selected
        assert selection.candidate is not None
        assert selection.candidate.licence.commercial_use_permitted
        assert ModelSelectionAdvisory.LICENCE_COMMERCIAL_USE_BARRED not in selection.advisories


def test_the_posture_predicate_widens_eligibility_for_a_research_licensed_candidate() -> None:
    """Positive control for the licence filter: it is the posture doing the excluding.

    Exercises the production predicate the selector filters on, so the two
    postures are shown to disagree about the research-licensed candidate and to
    agree about the permissive one -- the second half being what rules out a
    predicate that simply refuses everything under a commercial posture.
    """
    vision = candidates_for_role(ModelRole.VISION_TRANSCRIPTION)
    research = next(c for c in vision if not c.licence.commercial_use_permitted)
    permissive = next(c for c in vision if c.licence.commercial_use_permitted)

    assert research.permitted_under(DeploymentLicencePosture.NON_COMMERCIAL)
    assert not research.permitted_under(DeploymentLicencePosture.COMMERCIAL)
    assert permissive.permitted_under(DeploymentLicencePosture.NON_COMMERCIAL)
    assert permissive.permitted_under(DeploymentLicencePosture.COMMERCIAL)


def test_the_weakest_eligible_candidate_in_every_role_is_permissively_licensed() -> None:
    """The structural reason automatic selection cannot differ by posture today.

    Selection takes the weakest candidate that clears the bars, and in every
    role that model is currently Apache-2.0 -- so the commercial and
    non-commercial postures resolve identically, and the licence filter is
    load-bearing only against an override. That is a property worth pinning
    rather than a coincidence to leave implicit: adding a research-licensed
    candidate *smaller* than the permissive one would silently make the posture
    decide the shipped model, and this reds when it does.
    """
    profile = _cuda_profile(14 * _GIB)
    for role in ModelRole:
        commercial = select_model_for_role(role, profile=profile, posture=DeploymentLicencePosture.COMMERCIAL)
        non_commercial = select_model_for_role(role, profile=profile, posture=DeploymentLicencePosture.NON_COMMERCIAL)
        assert commercial.selected and non_commercial.selected
        assert commercial.runtime_id == non_commercial.runtime_id, (
            f"role {role.value} now resolves differently by posture; the weakest candidate is "
            f"no longer permissively licensed"
        )
        assert non_commercial.candidate is not None
        assert non_commercial.candidate.licence.commercial_use_permitted


def test_a_constrained_machine_refuses_rather_than_naming_a_model_that_cannot_fit() -> None:
    """Measured headroom below the smallest eligible requirement is a refusal, not a fallback."""
    selection = select_model_for_role(ModelRole.VISION_TRANSCRIPTION, profile=_cuda_profile(1 * _GIB))
    assert not selection.selected
    assert selection.runtime_id is None
    assert selection.tier is HardwareTier.CONSTRAINED
    assert ModelSelectionAdvisory.FIT_EXCEEDS_MEASURED_HEADROOM in selection.advisories
    verdict = selection.precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "provisioning.selected_model.fits"
    assert verdict.evidence[0].values == selection.facts


def test_the_same_machine_with_headroom_selects_through_the_same_call() -> None:
    """Positive control for the headroom refusal above."""
    selection = select_model_for_role(ModelRole.VISION_TRANSCRIPTION, profile=_cuda_profile(8 * _GIB))
    assert selection.selected
    assert selection.runtime_id is not None
    assert ModelSelectionAdvisory.FIT_EXCEEDS_MEASURED_HEADROOM not in selection.advisories


def test_the_headroom_comparison_includes_the_configured_safety_margin() -> None:
    """Fit is requirement PLUS margin, so a zero-margin fit is not admitted as a fit."""
    chosen = select_model_for_role(ModelRole.VISION_TRANSCRIPTION, profile=_cuda_profile(14 * _GIB))
    assert chosen.candidate is not None
    exact = chosen.candidate.memory_requirement_bytes
    assert exact is not None, "the selected candidate declares no memory requirement; there is no fit to test"
    with override_settings(cadrumo_llm_contention_safety_margin_bytes=2 * _GIB):
        tight = select_model_for_role(ModelRole.VISION_TRANSCRIPTION, profile=_cuda_profile(exact))
        roomy = select_model_for_role(ModelRole.VISION_TRANSCRIPTION, profile=_cuda_profile(exact + 2 * _GIB))
    assert not tight.selected
    assert roomy.selected


def test_an_unmeasurable_machine_selects_but_says_fit_was_not_verified() -> None:
    """Selection plans; it does not admit. The load still fails closed at the contention check."""
    selection = select_model_for_role(ModelRole.VISION_TRANSCRIPTION, profile=_unmeasurable_profile())
    assert selection.selected
    assert selection.tier is HardwareTier.UNMEASURED
    assert selection.binding_free_bytes is None
    assert ModelSelectionAdvisory.FIT_UNVERIFIED in selection.advisories
    assert selection.precondition_verdict is None
    assert selection.facts["binding_free_measured"] is False
    assert selection.facts["selected_model_requirement_known"] is True


def test_an_override_of_a_licence_barred_model_is_honoured_with_a_visible_advisory() -> None:
    """The operator's explicit choice wins, and is never quiet about the licence."""
    research = next(
        candidate
        for candidate in candidates_for_role(ModelRole.VISION_TRANSCRIPTION)
        if not candidate.licence.commercial_use_permitted
    )
    selection = select_model_for_role(
        ModelRole.VISION_TRANSCRIPTION,
        profile=_cuda_profile(14 * _GIB),
        override=research.runtime_id,
    )
    assert selection.selected
    assert selection.override_applied
    assert selection.runtime_id == research.runtime_id
    assert ModelSelectionAdvisory.LICENCE_COMMERCIAL_USE_BARRED in selection.advisories
    advisory = selection.licence_advisory
    assert advisory
    assert research.runtime_id in advisory


def test_an_override_of_a_permissive_model_carries_no_licence_advisory() -> None:
    """Positive control: the advisory is the licence bar speaking, not the override itself."""
    permissive = next(
        candidate
        for candidate in candidates_for_role(ModelRole.VISION_TRANSCRIPTION)
        if candidate.licence.commercial_use_permitted
    )
    selection = select_model_for_role(
        ModelRole.VISION_TRANSCRIPTION,
        profile=_cuda_profile(14 * _GIB),
        override=permissive.runtime_id,
    )
    assert selection.selected
    assert selection.override_applied
    assert ModelSelectionAdvisory.LICENCE_COMMERCIAL_USE_BARRED not in selection.advisories
    assert selection.licence_advisory == ""


def test_the_licence_advisory_renders_in_every_shipped_locale() -> None:
    """The advisory is a real string in each catalogue, not a self-referencing placeholder.

    Asserts the key resolved and interpolated -- never the wording, which lives
    in the locale catalogues and is not a test's to pin.
    """
    research = next(
        candidate
        for candidate in candidates_for_role(ModelRole.VISION_TRANSCRIPTION)
        if not candidate.licence.commercial_use_permitted
    )
    key = "provisioning.model.licence.non_commercial_advisory"
    rendered: set[str] = set()
    for language in ("en", "es", "ca", "hu"):
        with override_settings(cadrumo_output_language=language):
            selection = select_model_for_role(
                ModelRole.VISION_TRANSCRIPTION,
                profile=_cuda_profile(14 * _GIB),
                override=research.runtime_id,
            )
            advisory = selection.licence_advisory
        assert advisory and advisory != key, f"{language} carries no real advisory value"
        assert "%{" not in advisory, f"{language} left a placeholder un-interpolated"
        assert research.runtime_id in advisory
        rendered.add(advisory)
    assert len(rendered) == 4, "two locales render identically; one is untranslated"


def test_an_uncatalogued_override_is_honoured_but_makes_no_licence_claim() -> None:
    """An unknown model is 'no claim made': honoured, flagged, never assumed permissive."""
    selection = select_model_for_role(
        ModelRole.VISION_TRANSCRIPTION,
        profile=_cuda_profile(14 * _GIB),
        override="not-a-real-model:0b",
    )
    assert selection.selected
    assert selection.override_applied
    assert selection.candidate is None
    assert selection.runtime_id == "not-a-real-model:0b"
    assert ModelSelectionAdvisory.OVERRIDE_NOT_IN_CATALOGUE in selection.advisories
    assert ModelSelectionAdvisory.LICENCE_UNVERIFIED in selection.advisories
    assert selection.licence_advisory == ""


def test_an_override_below_the_context_floor_is_honoured_with_a_capability_advisory() -> None:
    """Naming a model whose window is too small is allowed, and is said out loud."""
    smallest = candidates_for_role(ModelRole.VISION_TRANSCRIPTION)[0]
    selection = select_model_for_role(
        ModelRole.VISION_TRANSCRIPTION,
        profile=_cuda_profile(14 * _GIB),
        override=smallest.runtime_id,
    )
    assert selection.selected
    assert ModelSelectionAdvisory.OVERRIDE_BELOW_CONTEXT_FLOOR in selection.advisories


def test_an_override_that_clears_the_context_floor_carries_no_capability_advisory() -> None:
    """Positive control for the capability advisory above."""
    settings = load_settings()
    roomy = next(
        candidate
        for candidate in candidates_for_role(ModelRole.VISION_TRANSCRIPTION)
        if candidate.max_context_tokens >= settings.cadrumo_llm_ollama_num_ctx
    )
    selection = select_model_for_role(
        ModelRole.VISION_TRANSCRIPTION,
        profile=_cuda_profile(14 * _GIB),
        override=roomy.runtime_id,
    )
    assert ModelSelectionAdvisory.OVERRIDE_BELOW_CONTEXT_FLOOR not in selection.advisories


def test_the_shipped_settings_defaults_are_what_selection_resolves_to() -> None:
    """Selection and the settings defaults agree on a machine with headroom.

    Keeps the two surfaces from drifting: a default flipped in one place and not
    the other would leave the resolver and the configured model disagreeing
    about which model the product ships.
    """
    settings = load_settings()
    profile = _cuda_profile(14 * _GIB)
    vision = select_model_for_role(ModelRole.VISION_TRANSCRIPTION, profile=profile)
    text = select_model_for_role(ModelRole.TEXT_EXTRACTION, profile=profile)
    mapping = select_model_for_role(ModelRole.COLUMN_ROLE_MAPPING, profile=profile)
    assert vision.runtime_id == settings.cadrumo_llm_ollama_vision_model
    assert text.runtime_id == settings.cadrumo_llm_ollama_text_model
    assert mapping.runtime_id == settings.cadrumo_llm_ollama_mapping_model
    assert model_candidate(settings.cadrumo_llm_ollama_vision_model) is not None


def test_the_cloud_runtime_resolves_every_role_to_the_shipped_cloud_default() -> None:
    """A hosted route must land on a role-named model, not the global fallback."""
    settings = load_settings()
    profile = _cuda_profile(14 * _GIB)
    for role, configured in (
        (ModelRole.VISION_TRANSCRIPTION, settings.cadrumo_llm_cloud_vision_model),
        (ModelRole.TEXT_EXTRACTION, settings.cadrumo_llm_cloud_text_model),
        (ModelRole.COLUMN_ROLE_MAPPING, settings.cadrumo_llm_cloud_mapping_model),
    ):
        selection = select_model_for_role(role, profile=profile, runtime=ModelRuntime.CLOUD_ANTHROPIC)
        assert selection.selected
        assert selection.runtime_id == configured
        assert selection.candidate is not None
        assert selection.candidate.runtime is ModelRuntime.CLOUD_ANTHROPIC
        assert selection.candidate.licence.commercial_use_permitted


def test_a_hosted_selection_is_never_refused_for_local_headroom() -> None:
    """Nothing runs on this machine, so this machine's free memory cannot bar it.

    The discriminating case: on a profile so constrained that every local
    candidate is refused, the hosted route still resolves and carries neither
    headroom advisory. Judging a cloud model against local memory would refuse a
    route that cannot fail that way.
    """
    starved = _cuda_profile(1 * _GIB)

    local = select_model_for_role(ModelRole.VISION_TRANSCRIPTION, profile=starved)
    assert not local.selected
    assert ModelSelectionAdvisory.FIT_EXCEEDS_MEASURED_HEADROOM in local.advisories

    hosted = select_model_for_role(
        ModelRole.VISION_TRANSCRIPTION,
        profile=starved,
        runtime=ModelRuntime.CLOUD_ANTHROPIC,
    )
    assert hosted.selected
    assert ModelSelectionAdvisory.FIT_EXCEEDS_MEASURED_HEADROOM not in hosted.advisories
    assert ModelSelectionAdvisory.FIT_UNVERIFIED not in hosted.advisories


def test_an_unmeasurable_machine_does_not_flag_fit_on_a_hosted_selection() -> None:
    """FIT_UNVERIFIED means 'could not check a local fit' — there is none to check."""
    unmeasured = _unmeasurable_profile()
    assert (
        ModelSelectionAdvisory.FIT_UNVERIFIED
        in select_model_for_role(
            ModelRole.VISION_TRANSCRIPTION,
            profile=unmeasured,
        ).advisories
    )
    hosted = select_model_for_role(
        ModelRole.VISION_TRANSCRIPTION,
        profile=unmeasured,
        runtime=ModelRuntime.CLOUD_ANTHROPIC,
    )
    assert hosted.selected
    assert hosted.advisories == ()


def test_the_two_runtimes_never_resolve_to_each_others_models() -> None:
    """A runtime's selection is scoped to its own candidates, both ways."""
    profile = _cuda_profile(14 * _GIB)
    for role in ModelRole:
        local = select_model_for_role(role, profile=profile)
        hosted = select_model_for_role(role, profile=profile, runtime=ModelRuntime.CLOUD_ANTHROPIC)
        assert local.candidate is not None and hosted.candidate is not None
        assert local.candidate.runtime is ModelRuntime.LOCAL_OLLAMA
        assert hosted.candidate.runtime is ModelRuntime.CLOUD_ANTHROPIC
        assert local.runtime_id != hosted.runtime_id


def test_the_mapping_role_never_resolves_to_a_vision_tier_model() -> None:
    """On a machine with headroom for anything, the easiest job still gets the small model.

    The concrete regression this guards: the mapper shipped inheriting the
    general LLM default, a frontier-tier cloud model, for a task that reads a
    handful of header strings. Selection must not be able to reproduce that on
    the local tier either.
    """
    resolved = select_model_for_role(ModelRole.COLUMN_ROLE_MAPPING, profile=_cuda_profile(14 * _GIB))
    assert resolved.selected
    assert resolved.candidate is not None
    assert not resolved.candidate.serves(ModelRole.VISION_TRANSCRIPTION)

    text = select_model_for_role(ModelRole.TEXT_EXTRACTION, profile=_cuda_profile(14 * _GIB))
    assert text.candidate is not None
    resolved_bytes = resolved.candidate.memory_requirement_bytes
    text_bytes = text.candidate.memory_requirement_bytes
    assert resolved_bytes is not None and text_bytes is not None
    assert resolved_bytes <= text_bytes
