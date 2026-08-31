"""Real-behavior gates for the local-model catalogue and its licence claims.

Three properties are asserted, and only the first is about internal
consistency. The second is the licence gate: **no shipped default in any role
may carry a commercial-use bar.** It is the reason the catalogue exists -- the
tree previously shipped a research-licensed vision model as the default of a
commercial tax product -- so it is written to fail loudly on the exact state it
was built to correct, and is mutation-proven against that state.

The third guards the claim's *provenance* rather than its value: a licence that
asserts commercial use must name the publisher URL and quote the text that was
read, so the assertion can be re-checked by opening one link rather than by
trusting the author. Nothing here reaches a network, loads a model, or asserts
localized prose.
"""

from __future__ import annotations

import pytest

from ...core.config import load_settings
from ..model_catalogue import (
    DEFAULT_MODEL_BY_RUNTIME_AND_ROLE,
    MODEL_CATALOGUE,
    DeploymentLicencePosture,
    LicenceVerification,
    ModelCandidate,
    ModelLicence,
    ModelRole,
    ModelRuntime,
    candidates_for_role,
    default_model_runtime_id,
    model_candidate,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_every_role_and_runtime_has_a_commercially_licensed_candidate() -> None:
    """A commercial deployment must be servable for every role on every runtime."""
    for runtime in ModelRuntime:
        for role in ModelRole:
            eligible = [
                c for c in candidates_for_role(role, runtime) if c.permitted_under(DeploymentLicencePosture.COMMERCIAL)
            ]
            assert eligible, f"{runtime.value}/{role.value} has no commercially-licensed candidate"


def test_no_default_candidate_in_any_role_bars_commercial_use() -> None:
    """The licence gate: every shipped per-role default permits commercial use.

    Asserted over the catalogue's declared defaults, which are also the source
    of the ``Settings`` field defaults, so a flip made in either place is
    visible here.
    """
    barred = [
        (runtime, role, runtime_id)
        for runtime, defaults in DEFAULT_MODEL_BY_RUNTIME_AND_ROLE.items()
        for role, runtime_id in defaults.items()
        if not (candidate := model_candidate(runtime_id)) or not candidate.licence.commercial_use_permitted
    ]
    assert not barred, f"a shipped default carries a commercial-use bar: {barred}"


def test_shipped_settings_defaults_are_the_catalogued_commercial_defaults() -> None:
    """The live settings defaults resolve to catalogued, commercially-licensed models.

    Closes the gap the gate above cannot see on its own: the catalogue could be
    correct while a settings field still carried a hand-typed literal. Reads the
    real ``Settings`` defaults through the production loader.
    """
    settings = load_settings()
    local, cloud = ModelRuntime.LOCAL_OLLAMA, ModelRuntime.CLOUD_ANTHROPIC
    for field_value, role, runtime in (
        (settings.cadrumo_llm_ollama_vision_model, ModelRole.VISION_TRANSCRIPTION, local),
        (settings.cadrumo_llm_ollama_text_model, ModelRole.TEXT_EXTRACTION, local),
        (settings.cadrumo_llm_ollama_mapping_model, ModelRole.COLUMN_ROLE_MAPPING, local),
        (settings.cadrumo_llm_cloud_vision_model, ModelRole.VISION_TRANSCRIPTION, cloud),
        (settings.cadrumo_llm_cloud_text_model, ModelRole.TEXT_EXTRACTION, cloud),
        (settings.cadrumo_llm_cloud_mapping_model, ModelRole.COLUMN_ROLE_MAPPING, cloud),
    ):
        candidate = model_candidate(field_value)
        assert candidate is not None, f"settings default {field_value!r} is not in the catalogue"
        assert candidate.serves(role), f"settings default {field_value!r} does not serve {role.value}"
        assert candidate.runtime is runtime, f"settings default {field_value!r} is not a {runtime.value} candidate"
        assert candidate.licence.commercial_use_permitted, (
            f"settings default {field_value!r} carries a commercial-use bar"
        )


def test_the_global_model_floor_is_the_weakest_catalogued_cloud_candidate() -> None:
    """The last-resort fallback must not be where a frontier tier sneaks in.

    ``cadrumo_llm_model`` is what every request naming no model and belonging to
    no declared role falls through to. It previously carried a hand-typed
    frontier-tier identifier, which made adding a consumer and forgetting to
    route it the cheapest way to reach the most expensive model in the product.
    """
    settings = load_settings()
    candidate = model_candidate(settings.cadrumo_llm_model)
    assert candidate is not None, f"the global model floor {settings.cadrumo_llm_model!r} is not catalogued"
    assert candidate.runtime is ModelRuntime.CLOUD_ANTHROPIC
    assert candidate.licence.commercial_use_permitted
    weakest = candidates_for_role(ModelRole.TEXT_EXTRACTION, ModelRuntime.CLOUD_ANTHROPIC)[0]
    assert candidate.runtime_id == weakest.runtime_id


def test_every_runtime_default_is_the_weakest_candidate_for_its_role() -> None:
    """Bounded from below, on BOTH runtimes — the property, not just the local half.

    Ranked by the axis each runtime actually has: declared memory on-host,
    published input price off-host. Without a price the hosted ordering silently
    degrades to alphabetical, and a frontier-tier default sorts as "weakest"
    because of its name — a mutation that added exactly that passed every other
    gate in this file.
    """
    required_context = load_settings().cadrumo_llm_ollama_num_ctx
    for runtime in ModelRuntime:
        for role in ModelRole:
            ordered = candidates_for_role(role, runtime)
            assert ordered, f"{runtime.value}/{role.value} has no candidates"
            default = model_candidate(default_model_runtime_id(role, runtime))
            assert default is not None
            # Both bars selection applies, so a candidate legitimately excluded
            # on capability is not mistaken for a default that ranks too high.
            eligible = [
                c
                for c in ordered
                if c.permitted_under(DeploymentLicencePosture.COMMERCIAL) and c.max_context_tokens >= required_context
            ]
            assert eligible, f"{runtime.value}/{role.value} has no eligible candidate"
            assert default.runtime_id == eligible[0].runtime_id, (
                f"the {runtime.value} default for {role.value} is {default.runtime_id!r}, "
                f"but {eligible[0].runtime_id!r} ranks weaker and clears the same bars"
            )


def test_price_presence_tracks_the_runtime() -> None:
    """The hosted ordering axis exists exactly where memory does not."""
    for candidate in MODEL_CATALOGUE:
        if candidate.runtime is ModelRuntime.LOCAL_OLLAMA:
            assert candidate.input_price_per_mtok_usd is None, candidate.runtime_id
        else:
            assert candidate.input_price_per_mtok_usd is not None, candidate.runtime_id


def test_a_hosted_candidate_without_a_price_is_refused() -> None:
    """No ordering axis means selection cannot be bounded from below — refuse it."""
    hosted = next(c for c in MODEL_CATALOGUE if c.runtime is ModelRuntime.CLOUD_ANTHROPIC)
    payload = hosted.model_dump() | {"input_price_per_mtok_usd": None}
    with pytest.raises(ValueError, match="no ordering axis"):
        ModelCandidate.model_validate(payload)


def test_memory_requirement_presence_tracks_the_runtime() -> None:
    """The runtime axis is load-bearing: a hosted model has no on-host footprint."""
    for candidate in MODEL_CATALOGUE:
        if candidate.runtime is ModelRuntime.LOCAL_OLLAMA:
            assert candidate.memory_requirement_bytes is not None, candidate.runtime_id
        else:
            assert candidate.memory_requirement_bytes is None, candidate.runtime_id


def test_a_hosted_candidate_may_not_claim_a_local_memory_requirement() -> None:
    """A figure that would be compared against this machine's free memory is refused."""
    hosted = next(c for c in MODEL_CATALOGUE if c.runtime is ModelRuntime.CLOUD_ANTHROPIC)
    payload = hosted.model_dump() | {"memory_requirement_bytes": 1_000_000}
    with pytest.raises(ValueError, match="never run on this machine"):
        ModelCandidate.model_validate(payload)


def test_a_local_candidate_must_declare_a_memory_requirement() -> None:
    """The same validator in the other direction, so neither branch passes vacuously."""
    local = next(c for c in MODEL_CATALOGUE if c.runtime is ModelRuntime.LOCAL_OLLAMA)
    payload = local.model_dump() | {"memory_requirement_bytes": None}
    with pytest.raises(ValueError, match="declares no memory requirement"):
        ModelCandidate.model_validate(payload)


def test_both_runtimes_accept_their_own_valid_shape() -> None:
    """Positive control for the two refusals above."""
    for candidate in MODEL_CATALOGUE:
        assert ModelCandidate.model_validate(candidate.model_dump()).runtime_id == candidate.runtime_id


def test_the_catalogue_still_carries_a_commercial_use_barred_candidate() -> None:
    """A fixture anchor: the gate above is not passing vacuously.

    If every catalogued model were permissively licensed, the licence gate would
    pass no matter how it were written. This asserts the discriminating case is
    still present, so the gate stays capable of failing.
    """
    barred = [c for c in MODEL_CATALOGUE if not c.licence.commercial_use_permitted]
    assert barred, "the catalogue no longer describes any commercial-use-barred model"
    assert all(c.licence.verification is not LicenceVerification.UNVERIFIED for c in barred)


def test_every_commercial_use_claim_names_its_publisher_source_and_quote() -> None:
    """A licence claim must be re-checkable from the record it ships with."""
    for candidate in MODEL_CATALOGUE:
        licence = candidate.licence
        assert licence.verification is not LicenceVerification.UNVERIFIED, (
            f"{candidate.runtime_id} ships an unverified licence"
        )
        assert licence.source_url.startswith("https://"), f"{candidate.runtime_id} names no publisher URL"
        assert licence.verified_quote.strip(), f"{candidate.runtime_id} quotes no publisher text"


def test_an_unverified_licence_may_not_claim_commercial_use() -> None:
    """Unverified is a refusal input, not a permissive default."""
    with pytest.raises(ValueError, match="must not assert commercial use"):
        ModelLicence(
            spdx_id="LicenseRef-Unknown",
            name="An unread licence",
            commercial_use_permitted=True,
            verification=LicenceVerification.UNVERIFIED,
        )


def test_an_unverified_licence_that_claims_nothing_is_accepted() -> None:
    """Positive control for the refusal above: the honest shape passes the same path."""
    licence = ModelLicence(
        spdx_id="LicenseRef-Unknown",
        name="An unread licence",
        commercial_use_permitted=False,
        verification=LicenceVerification.UNVERIFIED,
    )
    assert licence.commercial_use_permitted is False


def test_a_verified_licence_without_its_source_is_refused() -> None:
    """Claiming a verification source obliges naming it."""
    with pytest.raises(ValueError, match="omits the source URL or the verified quote"):
        ModelLicence(
            spdx_id="Apache-2.0",
            name="Apache License 2.0",
            commercial_use_permitted=True,
            verification=LicenceVerification.PUBLISHER_MODEL_CARD,
        )


def test_candidates_for_role_are_ordered_weakest_first() -> None:
    """Selection order is ascending memory requirement, which is what bounds it from below."""
    for role in ModelRole:
        ordered = candidates_for_role(role)
        assert ordered, f"role {role.value} has no candidates"
        requirements = [c.memory_requirement_bytes or 0 for c in ordered]
        assert requirements == sorted(requirements)
        assert all(c.serves(role) and c.runtime is ModelRuntime.LOCAL_OLLAMA for c in ordered)


def test_the_catalogue_carries_a_candidate_excluded_on_context_capability() -> None:
    """A fixture anchor for the capability floor being a real, exercised filter.

    The smallest vision candidate must be one the default request window
    excludes; without it the selection matrix's capability dimension would be
    untested by construction, and 'weakest first' would degenerate into 'first'.
    """
    required = load_settings().cadrumo_llm_ollama_num_ctx
    vision = candidates_for_role(ModelRole.VISION_TRANSCRIPTION)
    assert vision[0].max_context_tokens < required, (
        "no vision candidate is excluded by the configured context window; the capability floor is untested"
    )
    assert any(candidate.max_context_tokens >= required for candidate in vision)


def test_default_runtime_ids_resolve_and_serve_their_role() -> None:
    """Every role's default is a catalogued candidate eligible for that role."""
    for runtime in ModelRuntime:
        for role in ModelRole:
            candidate = model_candidate(default_model_runtime_id(role, runtime))
            assert candidate is not None
            assert candidate.serves(role)
            assert candidate.runtime is runtime


def test_column_role_mapping_is_served_only_by_text_candidates() -> None:
    """The mapper reads header strings, so a vision model is the wrong tier for it.

    A delimited export already IS text. Admitting a vision candidate to this
    role would let selection resolve the easiest job in the product to the
    heaviest model class it knows, which is the exact direction the operator
    directive bars.
    """
    mapping = candidates_for_role(ModelRole.COLUMN_ROLE_MAPPING)
    assert mapping
    for candidate in mapping:
        assert not candidate.serves(ModelRole.VISION_TRANSCRIPTION), (
            f"{candidate.runtime_id} serves column-role mapping and vision transcription; "
            f"the mapper must not be able to resolve to a vision-tier model"
        )


def test_the_mapping_default_is_no_heavier_than_the_text_default() -> None:
    """Column-role mapping is the easier job, so it must never cost more.

    Pins the sizing argument itself rather than the model name: mapping is a
    selection over a short closed vocabulary, text extraction is a document
    read, and a mapping default above the text default would mean the easier
    task had silently been sized up.
    """
    mapping = model_candidate(default_model_runtime_id(ModelRole.COLUMN_ROLE_MAPPING))
    text = model_candidate(default_model_runtime_id(ModelRole.TEXT_EXTRACTION))
    assert mapping is not None and text is not None
    assert mapping.memory_requirement_bytes is not None
    assert text.memory_requirement_bytes is not None
    assert mapping.memory_requirement_bytes <= text.memory_requirement_bytes


def test_model_candidate_returns_none_for_an_uncatalogued_id() -> None:
    """An unknown id is 'no claim made', never a fabricated permissive record."""
    assert model_candidate("not-a-real-model:0b") is None
