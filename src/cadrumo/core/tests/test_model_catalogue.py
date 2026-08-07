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

from ...core import (
    DEFAULT_MODEL_BY_ROLE,
    MODEL_CATALOGUE,
    DeploymentLicencePosture,
    LicenceVerification,
    ModelLicence,
    ModelRole,
    candidates_for_role,
    default_model_runtime_id,
    model_candidate,
)
from ...core.config import load_settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_every_role_has_at_least_one_commercially_licensed_candidate() -> None:
    """A commercial deployment must be servable for every role without an override."""
    for role in ModelRole:
        eligible = [
            candidate
            for candidate in candidates_for_role(role)
            if candidate.permitted_under(DeploymentLicencePosture.COMMERCIAL)
        ]
        assert eligible, f"role {role.value} has no commercially-licensed candidate"


def test_no_default_candidate_in_any_role_bars_commercial_use() -> None:
    """The licence gate: every shipped per-role default permits commercial use.

    Asserted over the catalogue's declared defaults, which are also the source
    of the ``Settings`` field defaults, so a flip made in either place is
    visible here.
    """
    barred = [
        (role, runtime_id)
        for role, runtime_id in DEFAULT_MODEL_BY_ROLE.items()
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
    for field_value, role in (
        (settings.cadrumo_llm_ollama_vision_model, ModelRole.VISION_TRANSCRIPTION),
        (settings.cadrumo_llm_ollama_text_model, ModelRole.TEXT_EXTRACTION),
        (settings.cadrumo_llm_ollama_mapping_model, ModelRole.COLUMN_ROLE_MAPPING),
    ):
        candidate = model_candidate(field_value)
        assert candidate is not None, f"settings default {field_value!r} is not in the catalogue"
        assert candidate.serves(role), f"settings default {field_value!r} does not serve {role.value}"
        assert candidate.licence.commercial_use_permitted, (
            f"settings default {field_value!r} carries a commercial-use bar"
        )


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
        requirements = [candidate.memory_requirement_bytes for candidate in ordered]
        assert requirements == sorted(requirements)
        assert all(candidate.serves(role) for candidate in ordered)


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
    for role in ModelRole:
        candidate = model_candidate(default_model_runtime_id(role))
        assert candidate is not None
        assert candidate.serves(role)


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
    assert mapping.memory_requirement_bytes <= text.memory_requirement_bytes


def test_model_candidate_returns_none_for_an_uncatalogued_id() -> None:
    """An unknown id is 'no claim made', never a fabricated permissive record."""
    assert model_candidate("not-a-real-model:0b") is None
