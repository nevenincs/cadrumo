"""Interactive descendant flow over one runtime-bound profile revision."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import typer

from ....application.flows.line_frontend import LineFlowFrontend
from ....application.flows.resume import resume_flow
from ....application.flows.review import assert_submit_eligible
from ....application.wizard.descendant_door import build_descendant_door_definition
from ....application.wizard.persistence import descendant_answers_from_values, descendant_facts_from_answers
from ....core.flows import FlowMode
from ....domain.contribuyente.descendant import DescendantInfo
from ....domain.contribuyente.descendant_facts import descendant_facts_from_list, descendant_list_from_facts
from ..runtime_profile_binding import require_profile_client
from ..state_projection_support import authority_operation
from ._profile_support import require_active_profile_pointer
from ._runtime_profile_mutation import mutation_deadline
from .runtime_descendants import read_runtime_descendants, replace_runtime_descendants

if TYPE_CHECKING:
    from prompt_toolkit.input import Input
    from prompt_toolkit.output import Output


def run_runtime_descendant_door(
    ctx: typer.Context, *, input: Input | None = None, output: Output | None = None
) -> tuple[DescendantInfo, ...]:
    """Seed the existing flow from authorized facts and publish its reviewed set.

    The initial revision remains the write baseline throughout human input.
    Prompting cannot silently adopt a concurrent edit or extend authentication;
    the registered executor rechecks both when the operator submits.
    """
    pointer = require_active_profile_pointer()
    client = require_profile_client(ctx, expected_profile_id=UUID(str(pointer.bucket_id)))
    operation = authority_operation(ctx)
    baseline, existing = read_runtime_descendants(client, operation=operation, deadline=mutation_deadline())
    definition = build_descendant_door_definition(operation=operation)
    values = dict(descendant_facts_from_list(existing, authority=operation))
    seed = descendant_answers_from_values(values, operation=operation)
    state, _projection = LineFlowFrontend(definition, input=input, output=output).run(
        mode=FlowMode.MODIFY,
        resume_state=resume_flow(definition, seed, mode=FlowMode.MODIFY),
    )
    assert_submit_eligible(definition, state)
    replacements = descendant_list_from_facts(
        dict(descendant_facts_from_answers(state.answers, operation=operation)), authority=operation
    )
    return replace_runtime_descendants(
        client,
        baseline=baseline,
        descendants=replacements,
        operation=operation,
        deadline=mutation_deadline(),
    )
