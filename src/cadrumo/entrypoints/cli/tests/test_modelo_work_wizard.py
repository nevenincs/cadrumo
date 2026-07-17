"""Real terminal-boundary coverage for ``aeat app modelo work wizard``.

Drives the full prompt sequence for a Modelo 130 draft against real
ledger-seeded income/expense rows and asserts the wizard composes the exact
same :func:`~cadrumo.application.modelo.calculate_modelo_work_revision` path
``work calculate`` uses -- never a parallel calculation surface
(``composition-service-no-parallel-write-path``).

The prompts are driven through ``prompt_toolkit``'s own IO-injection contract:
:func:`~prompt_toolkit.input.create_pipe_input` supplies the keystrokes and
:func:`~prompt_toolkit.application.current.create_app_session` declares that
pipe as the ambient session's IO, which is what the production
:meth:`~cadrumo.application.wizard.QuestionaryPrompter.from_ambient_app_session`
construction reads. Nothing is mocked, stubbed, or patched: the real
``questionary`` widgets render against the pipe and the real registry engine,
ledger aggregation, and bucket-scoped storage answer behind them. The keystrokes
are the only thing supplied -- exactly what an operator would type.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from io import StringIO

import pytest
from prompt_toolkit.application.current import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output.plain_text import PlainTextOutput

from ....application.wizard import QuestionaryPrompter, WizardUnsupportedConsoleError
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401
from ._m130_source_support import seed_m130_expense_transaction, seed_m130_income_transaction
from ._modelo_work_ux_support import _create_m130_work_unit
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# Oracle: AEAT DR 130 Instrucciones, casilla 03 (rendimiento neto = ingresos -
# gastos) and casilla 04 (pago fraccionado = 20% del rendimiento neto,
# art-110 RD 439/2007). Casillas 01/02 are ledger-derived, so the oracle inputs
# are real seeded transactions rather than hand-typed casilla overrides.
_INGRESOS = Decimal("3000.00")
_GASTOS = Decimal("600.00")
_RENDIMIENTO_NETO = _INGRESOS - _GASTOS
_PAGO_FRACCIONADO = (_RENDIMIENTO_NETO * Decimal("20") / Decimal("100")).quantize(Decimal("0.01"))

# The M130 1T manual-input surface (registry ``input_kind = "manual"``):
# 06 retenciones, 08 volumen ingresos agrarias, 10 retenciones agrarias,
# 16 deduccion vivienda, 18 resultado anteriores autoliquidaciones. All zero
# for this oracle (no withholdings, not an agrarian activity, no vivienda
# deduction, first filing of the ejercicio).
_ZERO_MANUAL_ANSWERS = ("0", "0", "0", "0", "0")
# The one ``previous_filing`` binding whose selector has no local prior M100
# filing to auto-resolve at 1T with a blank bucket. It is not absent-by-design
# (unlike the M130-internal same-ejercicio carries, which are), so the
# calculation engine's own refusal drives the wizard's one follow-up prompt.
_PREV_YEAR_INCOME_ANSWER = "13000"

_EXPECTED_QUESTION_COUNT = len(_ZERO_MANUAL_ANSWERS) + 1


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _keystrokes(answers: tuple[str, ...]) -> str:
    """Render ``answers`` as the keystrokes an operator would type, one Enter each."""
    return "".join(f"{answer}\r" for answer in answers)


def _invoke_with_typed_answers(args: list[str], answers: tuple[str, ...]):
    """Run the CLI with ``answers`` queued as real keystrokes on a pipe.

    The whole answer sequence is buffered up front because the CLI call is
    synchronous: each ``questionary`` prompt reads up to its Enter and leaves
    the remainder for the next one.
    """
    with create_pipe_input() as pipe:
        pipe.send_text(_keystrokes(answers))
        with create_app_session(input=pipe, output=PlainTextOutput(StringIO())):
            return _invoke(args)


def _create_profile() -> None:
    result = _invoke(
        [
            "config",
            "profile",
            "create",
            "operator",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "natural_person",
            "--irpf-income-categories",
            "actividad_economica",
            "--tax-id",
            "12345678Z",
            "--name",
            "Operator",
            "--surnames",
            "Wizard",
            "--activity",
            "design",
        ],
    )
    assert result.exit_code == 0, result.output


def _seed_m130_ledger(source_key: str) -> None:
    seed_m130_income_transaction(amount=_INGRESOS, filing_year=2025, source_key=source_key)
    seed_m130_expense_transaction(amount=_GASTOS, filing_year=2025, source_key=source_key)


def test_wizard_drives_m130_draft_through_full_prompt_sequence() -> None:
    """The wizard walks every outstanding M130 1T question and produces the oracle draft.

    Answers only the registry-declared manual casillas plus the one
    previous-filing binding the engine reports missing; every other casilla
    (ledger-bound 01/02, computed 03/04/07/12-15/17/19) is populated by the
    shared calculation path with zero wizard involvement.
    """
    _create_profile()
    _seed_m130_ledger("wizard-full-sequence")
    work_unit_id = _create_m130_work_unit()

    result = _invoke_with_typed_answers(
        ["--format", "json", "app", "modelo", "work", "wizard", work_unit_id],
        (*_ZERO_MANUAL_ANSWERS, _PREV_YEAR_INCOME_ANSWER),
    )
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output

    # Prompt copy renders on the prompter's own device, never stdout: under
    # `--format json` stdout carries the envelope alone, or a machine caller
    # cannot parse what it just drove.
    assert result.output.lstrip().startswith("{"), result.output

    payload = _payload(result.output)
    assert payload["work_unit_id"] == work_unit_id
    assert payload["state"] == "borrador"
    assert payload["saved"] is True

    casillas = payload["casilla_values"]
    assert Decimal(casillas["01"]) == _INGRESOS
    assert Decimal(casillas["02"]) == _GASTOS
    assert Decimal(casillas["03"]) == _RENDIMIENTO_NETO
    assert Decimal(casillas["04"]) == _PAGO_FRACCIONADO
    assert Decimal(casillas["19"]) == _PAGO_FRACCIONADO

    # The wizard asked exactly the expected questions -- no more, no fewer.
    prompted = payload["prompted_casillas"]
    assert len(prompted) == _EXPECTED_QUESTION_COUNT

    by_key = {row["key"]: row for row in prompted}
    for manual_casilla in ("06", "08", "10", "16", "18"):
        row = by_key[manual_casilla]
        assert row["channel"] == "casilla"
        assert row["value"] == "0"
        assert row["legal_refs"], f"casilla {manual_casilla} must carry legal_refs"
        assert row["source_refs"], f"casilla {manual_casilla} must carry source_refs"

    binding_row = by_key["irpf.previous_year_economic_activity_net_income"]
    assert binding_row["channel"] == "binding"
    assert binding_row["value"] == _PREV_YEAR_INCOME_ANSWER


def test_wizard_composes_shared_calculate_path_not_a_parallel_one() -> None:
    """A wizard-built draft and a hand-built ``work calculate`` draft agree exactly.

    Recalculating the same work unit with the exact inputs the wizard supplied
    must land on the same casilla values -- proof the wizard is a guided front
    end over the existing calculate path
    (``composition-service-no-parallel-write-path``), not a second,
    independently-derived calculation surface.
    """
    _create_profile()
    _seed_m130_ledger("wizard-parity")
    work_unit_id = _create_m130_work_unit()

    wizard_result = _invoke_with_typed_answers(
        ["--format", "json", "app", "modelo", "work", "wizard", work_unit_id],
        (*_ZERO_MANUAL_ANSWERS, _PREV_YEAR_INCOME_ANSWER),
    )
    assert wizard_result.exit_code == 0, wizard_result.output
    wizard_casillas = _payload(wizard_result.output)["casilla_values"]

    calculate_result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "06=0",
            "--casilla", "08=0",
            "--casilla", "10=0",
            "--casilla", "16=0",
            "--casilla", "18=0",
            "--binding", f"irpf.previous_year_economic_activity_net_income={_PREV_YEAR_INCOME_ANSWER}",
        ],
    )  # fmt: skip
    assert calculate_result.exit_code == 0, calculate_result.output
    calculate_casillas = _payload(calculate_result.output)["casilla_values"]

    assert wizard_casillas == calculate_casillas


def test_wizard_non_interactive_host_refuses_with_instructive_message() -> None:
    """A real non-TTY invocation refuses before attempting an interactive prompt."""
    _create_profile()
    _seed_m130_ledger("wizard-non-interactive")
    work_unit_id = _create_m130_work_unit()

    result = _invoke(["--format", "json", "app", "modelo", "work", "wizard", work_unit_id])

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "interactive" in result.output.lower() or "console" in result.output.lower()


def test_wizard_prompter_translates_a_host_console_failure_that_is_not_an_oserror() -> None:
    """A Windows no-console host gets the translated refusal, never a raw traceback.

    Reproduces the real condition rather than simulating it. The prompter is
    built exactly as the wizard command builds it -- through
    ``from_ambient_app_session`` inside a session declaring only an input -- so
    the prompt renders against this process's genuine stdout handle. Under a
    redirected (non-console) stdout, that is precisely the Windows
    "attached to a terminal, but no console screen buffer" state git-bash
    produces, and real ``prompt_toolkit`` raises the real
    :class:`~prompt_toolkit.output.win32.NoConsoleScreenBufferError` from it.

    The regression this pins: that error derives from ``Exception``, *not*
    ``OSError``, so the CLI's former ``except OSError`` handler could not catch
    it and the operator saw a raw traceback. The assertion below on the cause's
    type is what makes an ``OSError``-only handler unable to pass this test
    again.

    POSIX has no console-screen-buffer concept -- a redirected stdout is simply
    a valid output there -- so the same call legitimately answers from the pipe
    instead of refusing. Both branches assert that platform's real behavior.
    """
    with create_pipe_input() as pipe:
        pipe.send_text("42\r")
        with create_app_session(input=pipe):
            prompter = QuestionaryPrompter.from_ambient_app_session()

            if sys.platform != "win32":
                assert prompter.ask_text("Casilla 06 (Retenciones e ingresos a cuenta)") == "42"
                return

            with pytest.raises(WizardUnsupportedConsoleError) as excinfo:
                prompter.ask_text("Casilla 06 (Retenciones e ingresos a cuenta)")

    from prompt_toolkit.output.win32 import NoConsoleScreenBufferError

    cause = excinfo.value.__cause__
    assert isinstance(cause, NoConsoleScreenBufferError), f"expected the real host failure, got {cause!r}"
    assert not isinstance(cause, OSError), (
        "NoConsoleScreenBufferError is not an OSError; an `except OSError` handler "
        "would let it escape to the operator as a raw traceback"
    )
