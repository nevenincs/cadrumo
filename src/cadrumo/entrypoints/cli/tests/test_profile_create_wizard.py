"""Real terminal-boundary coverage for an interactive ``aeat config profile create``.

``config profile create`` is the operator's first contact with Cadrumo: an
interactive walk of the whole setup flow, section by section, that ends in a
persisted taxpayer profile. Every other profile-creating test in the suite
drives it through ``--quiet`` / ``--accept-defaults``, which bypass the
prompting branch entirely and construct a
:class:`~cadrumo.application.wizard.CanonicalAnswerPrompter` from flags. This
module covers the branch an actual first-run operator takes.

The prompts are driven through ``prompt_toolkit``'s own IO-injection contract:
:func:`~prompt_toolkit.input.create_pipe_input` supplies the keystrokes and
:func:`~prompt_toolkit.application.current.create_app_session` declares that
pipe as the ambient session's IO, which is what the production
:meth:`~cadrumo.application.wizard.QuestionaryPrompter.from_ambient_app_session`
construction reads. Nothing is mocked, stubbed, or patched: the real
``questionary`` widgets render against the pipe and real bucket-scoped
encrypted storage answers behind them. The keystrokes are the only thing
supplied -- exactly what an operator would type.
"""

from __future__ import annotations

from io import StringIO

import pytest
from prompt_toolkit.application.current import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output.plain_text import PlainTextOutput

from ....application.user_profile import fact_value, profile_storage_session
from ....application.workflow import workflow_state_repository
from ....core import read_pointer
from ....core.config import load_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# The answers the operator types. Each is supplied as a `--flag`, which the
# runtime hands the prompter as that question's *default* -- the value the
# widget renders pre-filled and a bare Enter accepts. This is the real
# operator gesture for "the suggested value is right"; the assertions below
# read the persisted facts back, so a question that failed to carry its
# default through to storage fails the test.
_PROFILE_NAME = "Primer Contacto"
_TAX_ID = "00000000T"
_NAME = "Ada"
_SURNAMES = "Operadora"
_ACTIVITY = "Servicios de diseno"

# `irpf-income-categories` is the flow's one visible CHECKBOX, and
# `QuestionaryPrompter._ask_checkbox` deliberately takes no default: a
# checkbox's answer is the operator's selection, so it cannot be pre-filled
# by a flag the way every other widget can. Space toggles the highlighted
# choice (`actividad_economica`, the first) and Enter confirms it. Selecting
# it is what makes the `activity` question visible downstream.
_CHECKBOX_SELECT_FIRST = " \r"

# Every other visible question is accepted with a bare Enter. The flow has
# ~44 visible questions for a natural person; the surplus is deliberate --
# unread keystrokes simply stay in the pipe, whereas too few would starve a
# prompt. The test asserts the persisted result, not the keystroke count.
_ACCEPT_REMAINING = "\r" * 60

_KEYSTROKES = f"\r{_CHECKBOX_SELECT_FIRST}{_ACCEPT_REMAINING}"

_CREATE_ARGS = [
    "config", "profile", "create", _PROFILE_NAME,
    "--entity-type", "natural_person",
    "--tax-id", _TAX_ID,
    "--name", _NAME,
    "--surnames", _SURNAMES,
    "--activity", _ACTIVITY,
]  # fmt: skip


def _invoke_interactive_create(args: list[str]):
    """Run the CLI with the operator's keystrokes queued on a real pipe.

    The whole keystroke sequence is buffered up front because the CLI call is
    synchronous: each ``questionary`` prompt reads up to its Enter and leaves
    the remainder for the next one.
    """
    with create_pipe_input() as pipe:
        pipe.send_text(_KEYSTROKES)
        with create_app_session(input=pipe, output=PlainTextOutput(StringIO())):
            return invoke_cached_cli(args)


def _active_profile_record():
    """Return the record the active-profile pointer resolves to."""
    pointer = read_pointer(load_settings().cadrumo_local_storage_root)
    assert pointer is not None, "the interactive create left no active-profile pointer"
    with profile_storage_session(pointer.bucket_id):
        return workflow_state_repository().load().active_profile_record()


def test_interactive_create_persists_the_profile_the_operator_answered() -> None:
    """A first-run operator walks the setup flow and lands a live, readable profile.

    The contract: the answers typed at the real prompts reach encrypted
    storage. Asserting the persisted facts (rather than the emitted summary)
    is what makes this cover the whole path -- prompt, validate, project,
    persist -- instead of only the echo.
    """
    result = _invoke_interactive_create(_CREATE_ARGS)

    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output

    record = _active_profile_record()
    assert record is not None, "the interactive create persisted no profile record"

    assert fact_value(record, "taxpayer_type.entity_type") == "natural_person"
    assert fact_value(record, "identity.tax_id") == _TAX_ID
    assert fact_value(record, "identity.name") == _NAME
    assert fact_value(record, "identity.surnames") == _SURNAMES

    # The CHECKBOX answer is the one value no flag could pre-fill: it exists
    # in storage only because the space keystroke genuinely toggled the
    # widget. Its presence also proves the gated `activity` question was
    # revealed and answered downstream.
    assert fact_value(record, "taxpayer_type.irpf_income_categories") == "actividad_economica"
    assert fact_value(record, "activities.description") == _ACTIVITY

    # The flow's other widget kinds were driven by the same keystrokes, and
    # each lands a distinct value -- so a widget that silently failed to
    # answer could not leave this spread behind. CONFIRM carries its
    # declared default either way; SELECT takes the highlighted first choice
    # when no flag supplies one.
    assert fact_value(record, "capabilities.llm_vision") == "True"
    assert fact_value(record, "capabilities.cloud_evidence_upload") == "False"
    assert fact_value(record, "irpf.estimation_regime") == "directa_normal"


def test_interactive_create_under_json_keeps_stdout_parseable() -> None:
    """Prompt copy renders on the prompter's device, never stdout.

    Under ``--format json`` stdout must carry the envelope alone, or a machine
    caller cannot parse the run it just drove. The ~44 prompts this flow
    renders are exactly the noise that would break it.
    """
    result = _invoke_interactive_create(["--format", "json", *_CREATE_ARGS])

    assert result.exit_code == 0, result.output
    assert result.output.lstrip().startswith("{"), result.output
