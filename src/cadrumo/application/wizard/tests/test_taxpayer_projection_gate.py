"""End-to-end receipts that the setup flow blocks a legally invalid taxpayer.

The three construction invariants on the deadline-domain taxpayer profile
(Art. 93 LIRPF / RIRPF Art. 116, TRLIRNR Art. 2, Art. 47 LGT / TRLIRNR
Art. 10) are enforced at the review surface by the flow-scope
taxpayer-construction validator the setup definition names. These tests
drive the REAL projected setup definition through the real engine — no
mocks — and assert that an impatriado election without its start date and
a non-EU/EEA non-resident without a fiscal representative both surface a
blocking verdict at review and refuse submission, while the same answer
sets completed legally reach submit.

Assertions read verdict structure and catalogue keys only. The localized
rendering is proven by resolving the verdict's key through the real i18n
backend, never by asserting shipped prose.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from ....core.flows import FlowMode
from ....core.i18n import tr
from ...flows.definition import FlowDefinition
from ...flows.engine import FlowState, answer, first_unanswered_key, jump_to, next_page, start_flow
from ...flows.errors import FlowSubmitError
from ...flows.review import ReviewProjection, review
from ...flows.scripted import run_scripted_flow
from ..catalogue import SETUP_FLOW
from ..commands import _project_scripted_answers, setup_flow_definition
from ..flow_validators import TAXPAYER_PROJECTION_VALIDATOR_ID
from .test_setup_runtime import _default_tokens, _individual_declaration_canonical

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_IMPATRIADO_KEY = "wizard.setup.verifier.impatriado_requires_start_date"
_REPRESENTANTE_KEY = "wizard.setup.verifier.non_resident_requires_representante"


def _canonical(**overrides: str) -> dict[str, str]:
    """Return the shared individual-declaration answer set with overrides applied."""
    canonical = _individual_declaration_canonical()
    canonical.update(overrides)
    return canonical


def _walk(canonical: Mapping[str, str]) -> tuple[FlowDefinition, FlowState]:
    """Walk the live setup definition to completion through the real engine.

    Mirrors the production non-interactive projection (each visible page
    consumes its canonical token, visibility re-evaluated after every
    commit) but stops short of the submit assertion, so the review
    projection can be inspected for a blocked run as well as a passing one.
    """
    definition = setup_flow_definition(SETUP_FLOW)
    _tokens, intended = _project_scripted_answers(definition, canonical, mode=FlowMode.CREATE)
    state = start_flow(definition, mode=FlowMode.CREATE)
    while True:
        target = first_unanswered_key(definition, state)
        if target is None:
            return definition, state
        state = jump_to(definition, state, target)
        state = answer(definition, state, target, intended.get(target, ""))
        state = next_page(definition, state)


def _review(canonical: Mapping[str, str]) -> ReviewProjection:
    definition, state = _walk(canonical)
    return review(definition, state)


def _submit_refusal(canonical: Mapping[str, str]) -> FlowSubmitError:
    """Drive the production scripted path and return its submit refusal."""
    definition = setup_flow_definition(SETUP_FLOW)
    tokens, _intended = _project_scripted_answers(definition, canonical, mode=FlowMode.CREATE)
    with pytest.raises(FlowSubmitError) as caught:
        run_scripted_flow(definition, tokens, mode=FlowMode.CREATE, defaults=_default_tokens())
    return caught.value


def _blocking_keys(projection: ReviewProjection) -> set[str]:
    return {verdict.message_key for verdict in projection.blocking if verdict.message_key}


def test_setup_definition_names_the_taxpayer_projection_validator() -> None:
    """The composed definition carries the flow-scope validator id."""
    definition = setup_flow_definition(SETUP_FLOW)
    assert TAXPAYER_PROJECTION_VALIDATOR_ID in definition.flow_validator_ids


def test_impatriado_without_start_date_blocks_review_and_submit() -> None:
    """An impatriado election with no start date cannot be persisted through setup."""
    canonical = _canonical(**{"irpf-special-regime": "impatriado", "irpf-special-regime-start-date": ""})
    projection = _review(canonical)
    assert not projection.submit_eligible
    assert _IMPATRIADO_KEY in _blocking_keys(projection)
    row = next(v for v in projection.blocking if v.message_key == _IMPATRIADO_KEY)
    assert row.context["check"] == "impatriado_requires_start_date"
    refusal = _submit_refusal(canonical)
    assert refusal.translated_message == "application.flows.errors.submit_blocked"


def test_non_eea_non_resident_without_representante_blocks_review_and_submit() -> None:
    """A non-EU/EEA non-resident with no fiscal representative is refused at submit."""
    canonical = _canonical(
        **{
            "fiscal-residency": "non_resident_irnr",
            "country-of-fiscal-residence": "US",
            "representante-fiscal-nif": "",
            "representante-fiscal-nombre": "",
        },
    )
    projection = _review(canonical)
    assert not projection.submit_eligible
    assert _REPRESENTANTE_KEY in _blocking_keys(projection)
    row = next(v for v in projection.blocking if v.message_key == _REPRESENTANTE_KEY)
    assert row.context["check"] == "non_resident_requires_representante"
    refusal = _submit_refusal(canonical)
    assert refusal.translated_message == "application.flows.errors.submit_blocked"


def test_legally_complete_profiles_still_reach_submit() -> None:
    """The gate has teeth without false positives: three valid profiles submit.

    The resident baseline, the same impatriado election carrying its start
    date, and the same non-resident carrying a fiscal representative all
    construct cleanly, so the review surface stays submit-eligible and the
    production scripted path completes.
    """
    valid_sets = (
        _canonical(),
        _canonical(**{"irpf-special-regime": "impatriado", "irpf-special-regime-start-date": "2024-01-15"}),
        _canonical(
            **{
                "fiscal-residency": "non_resident_irnr",
                "country-of-fiscal-residence": "US",
                "representante-fiscal-nif": "12345678Z",
                "representante-fiscal-nombre": "Representante",
            },
        ),
    )
    for canonical in valid_sets:
        projection = _review(canonical)
        assert projection.submit_eligible, sorted(_blocking_keys(projection))
        definition = setup_flow_definition(SETUP_FLOW)
        tokens, _intended = _project_scripted_answers(definition, canonical, mode=FlowMode.CREATE)
        run_scripted_flow(definition, tokens, mode=FlowMode.CREATE, defaults=_default_tokens())


@pytest.mark.parametrize("message_key", [_IMPATRIADO_KEY, _REPRESENTANTE_KEY])
@pytest.mark.parametrize("locale", ["es", "en", "ca", "hu"])
def test_blocking_verdict_key_resolves_to_localized_prose(message_key: str, locale: str) -> None:
    """Every blocking verdict key resolves in every shipped catalogue.

    The verdict carries a catalogue key, so the surface renders localized
    prose rather than the raw pydantic message the model validator raises.
    A missing key would resolve back to itself.
    """
    rendered = tr(message_key, locale=locale)
    assert rendered != message_key
    assert "special_regime_start_date is required" not in rendered
    assert "TRLIRNR" not in rendered
