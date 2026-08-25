"""Scripted-vs-interactive parity over the one shared flow definition.

The non-interactive wizard paths (``--quiet`` / ``--accept-defaults``) and
the interactive frontends now drive the SAME projected
:class:`~cadrumo.application.flows.definition.FlowDefinition` through the SAME engine.
These tests prove the two drivers cannot diverge: the scripted intent
driver (:func:`~cadrumo.application.flows.scripted.run_scripted_flow`) and a
page-by-page :func:`~cadrumo.application.flows.engine.answer` walk over the same
definition and the same intended answers produce byte-identical answer maps
and the same submit eligibility. The refusal contract is pinned too — a
starved required page and a trailing unconsumed token both raise
:class:`~cadrumo.application.flows.errors.FlowAnswerError`.

No mocks: the real ``SETUP_FLOW`` descriptor, the real substrate bridge and
decorators (through the production
:func:`~cadrumo.application.wizard._commands.setup_flow_definition`), and
the real engine transitions. The intended answers are the specification
(operator inputs), never a copy of a driver's output.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from ....core.flows import FlowMode
from ...flows.definition import FlowDefinition
from ...flows.engine import FlowState, answer, jump_to, next_page, start_flow, visible_sequence
from ...flows.errors import FlowAnswerError
from ...flows.review import review
from ...flows.scripted import run_scripted_flow
from .._catalogue import SETUP_FLOW
from .._commands import _project_scripted_answers, setup_flow_definition

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# An autónomo: a natural person whose declared income categories include
# ``actividad_economica``, which GATE-REVEALS the ``activity`` page, and who
# leaves the optional ``notes`` page unset so it falls to its descriptor
# default — one gate-revealed page and one optional-page default.
_INDIVIDUAL_CANONICAL: dict[str, str] = {
    "output-language": "en",
    "entity-type": "natural_person",
    "tax-id": "12345678Z",
    "name": "Operator",
    "surnames": "Doe",
    "fiscal-residency": "resident_irpf",
    "tax-residence-ccaa": "madrid",
    "address-postcode": "28001",
    "irpf-income-categories": "actividad_economica,capital_inmobiliario",
    "activity": "Software development",
    "iva-regime": "GENERAL",
    "taxation-type": "1",
    "situacion-familiar": "soltero",
    "irpf-estimation-regime": "directa_normal",
    "irpf-special-regime": "general",
}

# A legal entity: ``entity-type == legal_entity`` GATE-REVEALS the
# intra-section ``legal-entity-form`` page and hides every natural-person /
# spouse / IRPF-personal page. ``incn-prior-12-months`` is left unset.
_LEGAL_ENTITY_CANONICAL: dict[str, str] = {
    "output-language": "en",
    "entity-type": "legal_entity",
    "legal-entity-form": "sl",
    "tax-id": "B66012345",
    "legal-name": "Acme SL",
    "activity": "Consultoria",
    "fiscal-residency": "resident_irpf",
    "tax-residence-ccaa": "madrid",
    "address-postcode": "28001",
    "iva-regime": "GENERAL",
    "irpf-estimation-regime": "directa_normal",
}


def _drive_interactive(definition: FlowDefinition, intended: Mapping[str, str], *, mode: FlowMode) -> FlowState:
    """Drive the engine page-by-page like an interactive frontend would.

    Walks the visible sequence from the top, committing each page's intended
    answer through :func:`answer` exactly as a live frontend commits an
    operator's keystrokes, re-reading the sequence after every commit so a
    gate-revealed page is picked up the moment it appears.
    """
    state = start_flow(definition, mode=mode)
    while True:
        target = next(
            (entry for entry in visible_sequence(definition, state) if entry.key not in state.answers),
            None,
        )
        if target is None:
            return state
        raw = intended.get(target.key, target.page.default or "")
        state = answer(definition, jump_to(definition, state, target.key), target.key, raw)
        state = next_page(definition, state)


@pytest.mark.parametrize(
    "canonical",
    [_INDIVIDUAL_CANONICAL, _LEGAL_ENTITY_CANONICAL],
    ids=["individual", "legal_entity"],
)
def test_scripted_and_interactive_walks_agree(canonical: dict[str, str]) -> None:
    """The scripted driver and a page-by-page walk agree on answers and eligibility."""
    definition = setup_flow_definition(SETUP_FLOW)
    tokens, intended = _project_scripted_answers(definition, canonical, mode=FlowMode.CREATE)

    scripted_state, scripted_projection = run_scripted_flow(definition, tokens, mode=FlowMode.CREATE)
    interactive_state = _drive_interactive(definition, intended, mode=FlowMode.CREATE)
    interactive_projection = review(definition, interactive_state)

    assert dict(scripted_state.answers) == dict(interactive_state.answers)
    assert scripted_projection.submit_eligible == interactive_projection.submit_eligible
    # A valid answer set submits from both drivers; a driver that silently
    # produced a half-answered state would flip this and fail.
    assert scripted_projection.submit_eligible is True
    # The gate-revealed page was actually walked, proving the parity is not
    # vacuous over an empty branch.
    gate_revealed = "activity" if canonical is _INDIVIDUAL_CANONICAL else "legal-entity-form"
    assert gate_revealed in scripted_state.answers


def test_scripted_walk_refuses_a_starved_required_page() -> None:
    """An empty queue that reaches a required page raises the underflow refusal."""
    definition = setup_flow_definition(SETUP_FLOW)

    with pytest.raises(FlowAnswerError) as caught:
        # ``tax-id`` is the first unconditionally-required page and carries no
        # default; the empty queue starves it once the optional openers blank.
        run_scripted_flow(definition, [], mode=FlowMode.CREATE)

    assert caught.value.translated_message == "application.flows.errors.scripted_queue_underflow"
    assert caught.value.context is not None
    assert caught.value.context["page_key"] == "tax-id"


def test_scripted_walk_refuses_trailing_unconsumed_tokens() -> None:
    """A queue longer than the visible sequence raises the overflow refusal."""
    definition = setup_flow_definition(SETUP_FLOW)
    tokens, _intended = _project_scripted_answers(definition, _INDIVIDUAL_CANONICAL, mode=FlowMode.CREATE)

    with pytest.raises(FlowAnswerError) as caught:
        run_scripted_flow(definition, [*tokens, "orphan-token"], mode=FlowMode.CREATE)

    assert caught.value.translated_message == "application.flows.errors.scripted_queue_overflow"
    assert caught.value.context is not None
    assert caught.value.context["remaining_count"] == 1
    # Counts only — a canonical token can carry a secret and must never ride
    # in the diagnostic.
    assert "orphan-token" not in str(caught.value.context)
