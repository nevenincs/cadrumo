"""End-to-end tests for the paged-flow interactive wizard path.

These drive the real bridge + engine + answer projection + persistence
headlessly: the wizard command is built with an injected frontend runner
that walks the bridged :class:`FlowDefinition` through the substrate's
scripted intent driver (``run_scripted_flow``) and returns the submitted
flow state — exactly the seam the CLI entrypoint fills with the
capability-selecting Textual/line runner. Assertions read the persisted
facts back through the real profile repository, never a mock.

The full-screen Textual rendering itself is covered by the adapter's
Pilot suite; this module proves the application-layer rewiring persists
the same facts a scripted walk collects, and that an edit walk changes
only the facts the operator actually altered.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
import typer

from ....core.flows import FlowMode
from ....tests.secure_sql import isolated_profile_storage_root
from ...flows import FlowDefinition, FlowState, run_scripted_flow
from ...user_profile import profile_storage_session, record_to_path_values
from ...workflow import read_profile_bucket, workflow_state_repository
from .._catalogue import SETUP_FLOW
from .._commands import build_wizard_command
from .._persistence import WizardPersistMode
from .test_setup_runtime import _scripted_answers_for_individual_declaration

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def _isolated_backend(tmp_path: Path) -> Iterator[Path]:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


def _scripted_runner(tokens: Sequence[str]):
    """A frontend runner that drives the flow through the scripted intent driver.

    Stands in for the entrypoint's capability-selecting runner: it walks
    the bridged, seeded :class:`FlowDefinition` the wizard prepared with a
    pre-supplied canonical-token queue and returns the submitted state,
    exercising every substrate transition a live frontend would.
    """

    def _runner(
        definition: FlowDefinition,
        *,
        mode: FlowMode,
        registered_values: object = None,
        on_language_activated: object = None,
    ) -> FlowState:
        del registered_values, on_language_activated
        state, _projection = run_scripted_flow(definition, tokens, mode=mode)
        return state

    return _runner


def _invoke_interactive(
    mode: WizardPersistMode,
    tokens: Sequence[str],
    args: Sequence[str],
) -> None:
    """Invoke the wizard command interactively with an injected scripted runner."""
    command = build_wizard_command(SETUP_FLOW, mode=mode, interactive_flow_runner=_scripted_runner(tokens))
    app = typer.Typer()
    app.command()(command)
    typer.main.get_command(app).main(args=list(args), standalone_mode=False)


def _persisted_path_values(profile_name: str) -> dict[str, str]:
    """Read the named profile's on-record facts as a schema-path value map."""
    pointer = read_profile_bucket(profile_name)
    assert pointer is not None
    with profile_storage_session(pointer.bucket_id):
        record = workflow_state_repository().load().active_profile_record()
    return record_to_path_values(record)


def test_interactive_create_persists_the_scripted_facts(_isolated_backend: Path) -> None:
    """A full scripted create walk persists the same facts the scripted answers declare.

    Expected values are the script's own inputs (the specification), not
    a copy of the engine's output: the tax id, activity, comunidad
    autónoma, and output language the deque supplies must reach the
    persisted profile through the bridge → engine → projection →
    ``persist_answers`` chain unchanged.
    """
    tokens = list(_scripted_answers_for_individual_declaration())

    _invoke_interactive("create", tokens, ["operator"])

    values = _persisted_path_values("operator")
    assert values["identity.tax_id"] == "12345678Z"
    assert values["identity.name"] == "Operator"
    assert values["activities.description"] == "Software development"
    assert values["tax_residence.ccaa"] == "madrid"
    assert values["preferences.output_language"] == "en"


def test_interactive_edit_changes_only_the_altered_facts(_isolated_backend: Path) -> None:
    """An edit walk that alters two answers changes exactly those two facts.

    The profile is created from the scripted answers, then re-walked with
    an edit script identical except for the activity and output-language
    tokens. Every other on-record fact must retain its created value while
    the two altered facts take their new values.
    """
    create_tokens = list(_scripted_answers_for_individual_declaration())
    _invoke_interactive("create", create_tokens, ["operator"])
    before = _persisted_path_values("operator")

    edit_tokens = _tokens_with_substitutions(
        _scripted_answers_for_individual_declaration(),
        activity="Barbería",
        output_language="es",
    )
    _invoke_interactive("edit", edit_tokens, ["operator"])

    after = _persisted_path_values("operator")
    assert after["activities.description"] == "Barbería"
    assert after["preferences.output_language"] == "es"
    # Every other fact carried over from the created profile unchanged.
    assert after["identity.tax_id"] == before["identity.tax_id"]
    assert after["identity.name"] == before["identity.name"]
    assert after["tax_residence.ccaa"] == before["tax_residence.ccaa"]


def _tokens_with_substitutions(base: deque[str], *, activity: str, output_language: str) -> list[str]:
    """Return the individual-declaration token list with two answers replaced.

    Positional substitution keeps the scripted queue aligned with the
    flow's visible sequence; the activity token (a free-text answer) and
    the output-language token (the first SELECT of the identidad section,
    now the opening page of the flow) are the two the edit walk alters.
    """
    tokens = list(base)
    tokens[tokens.index("Software development")] = activity
    # ``en`` appears once, as the output-language answer at the head of the
    # flow; replace that occurrence.
    tokens[tokens.index("en")] = output_language
    return tokens
