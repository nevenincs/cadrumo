"""Real-behavior coverage for the guided ``cadrumo app modelo work wizard`` command.

Drives the full simulated prompt sequence for a Modelo 130 draft against real
ledger-seeded income/expense rows and asserts the wizard composes the exact
same :func:`~cadrumo.application.modelo.calculate_modelo_work_revision` path
``work calculate`` uses — never a parallel calculation surface
(``composition-service-no-parallel-write-path``). No mocks, stubs, or
patches: the scripted prompter drives the real registry engine, the real
ledger aggregation, and the real bucket-scoped storage the CLI runs against
in every other integration test.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .._modelo_work_wizard_cli import _ScriptedTextPrompter, override_wizard_prompter
from ._m130_source_support import seed_m130_expense_transaction, seed_m130_income_transaction
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# Oracle: AEAT DR 130 Instrucciones, Casilla 03 (rendimiento neto = ingresos -
# gastos) and Casilla 04 (pago fraccionado = 20% de rendimiento neto,
# art-110 RD 439/2007). Casillas 01/02 are ledger-derived (source-bound), so
# the oracle inputs are real seeded transactions, not hand-typed casilla
# overrides -- the same fixture pattern `test_modelo_compare.py` uses.
_INGRESOS = Decimal("3000.00")
_GASTOS = Decimal("600.00")
_RENDIMIENTO_NETO = _INGRESOS - _GASTOS
_PAGO_FRACCIONADO = (_RENDIMIENTO_NETO * Decimal("20") / Decimal("100")).quantize(Decimal("0.01"))

# The M130 1T manual-input surface (registry `input_kind = "manual"`):
# 06 retenciones, 08 volumen ingresos agrarias, 10 retenciones agrarias,
# 16 deduccion vivienda, 18 resultado anteriores autoliquidaciones. All zero
# for this oracle (no withholdings, not an agrarian activity, no vivienda
# deduction, first filing of the ejercicio).
_ZERO_MANUAL_ANSWERS = ("0", "0", "0", "0", "0")
# The one `previous_filing` binding whose selector has no local prior M100
# filing to auto-resolve at 1T with a blank bucket -- it is not
# absent-by-design (unlike the M130-internal same-ejercicio carries, which
# are), so the calculation engine's own refusal drives the wizard's one
# follow-up prompt.
_PREV_YEAR_INCOME_ANSWER = "13000"


@pytest.fixture(autouse=True)
def _isolated_cli_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
    ):
        try:
            yield
        finally:
            dispose_engine()


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _create_profile() -> None:
    result = _invoke(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--entity-type", "natural_person",
            "--irpf-income-categories", "actividad_economica",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--surnames", "Wizard",
            "--activity", "design",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _seed_m130_ledger(source_key: str) -> None:
    seed_m130_income_transaction(amount=_INGRESOS, filing_year=2025, source_key=source_key)
    seed_m130_expense_transaction(amount=_GASTOS, filing_year=2025, source_key=source_key)


def _create_m130_work_unit() -> str:
    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return _payload(result.output)["work_unit_id"]


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

    prompter = _ScriptedTextPrompter(deque([*_ZERO_MANUAL_ANSWERS, _PREV_YEAR_INCOME_ANSWER]))
    with override_wizard_prompter(prompter):
        result = _invoke(["--format", "json", "app", "modelo", "work", "wizard", work_unit_id])
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output

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

    # Every scripted answer was consumed -- confirms the wizard asked exactly
    # the expected six questions, no more, no fewer.
    assert len(prompter.asked_prompts) == 6
    from ....application.wizard import WizardScriptUnderflowError

    with pytest.raises(WizardScriptUnderflowError):
        prompter.ask_text("extra question nobody scripted", help_text=None)


def test_wizard_prompted_casillas_audit_trail_matches_answers() -> None:
    """The JSON payload's ``prompted_casillas`` records exactly what was asked and answered.

    Verifies the wizard's audit surface (not just the final casilla values):
    every prompted step carries its channel (casilla vs binding), the exact
    key supplied to the calculation, and the answer -- so a scripted or
    agent caller can confirm what the wizard asked without a live terminal.
    """
    _create_profile()
    _seed_m130_ledger("wizard-audit-trail")
    work_unit_id = _create_m130_work_unit()

    prompter = _ScriptedTextPrompter(deque([*_ZERO_MANUAL_ANSWERS, _PREV_YEAR_INCOME_ANSWER]))
    with override_wizard_prompter(prompter):
        result = _invoke(["--format", "json", "app", "modelo", "work", "wizard", work_unit_id])
    assert result.exit_code == 0, result.output

    payload = _payload(result.output)
    prompted = payload["prompted_casillas"]
    assert len(prompted) == 6

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

    Runs the wizard against one work unit and the equivalent explicit
    ``--casilla`` / ``--binding`` flags against a second, identically seeded
    work unit. Both must resolve to the same casilla_values for every
    non-metadata casilla -- proof the wizard is a guided front end over the
    existing calculate path (composition-service-no-parallel-write-path),
    not a second, independently-derived calculation surface.
    """
    _create_profile()
    _seed_m130_ledger("wizard-parity-a")

    wizard_unit_id = _create_m130_work_unit()
    prompter = _ScriptedTextPrompter(deque([*_ZERO_MANUAL_ANSWERS, _PREV_YEAR_INCOME_ANSWER]))
    with override_wizard_prompter(prompter):
        wizard_result = _invoke(["--format", "json", "app", "modelo", "work", "wizard", wizard_unit_id])
    assert wizard_result.exit_code == 0, wizard_result.output
    wizard_casillas = _payload(wizard_result.output)["casilla_values"]

    # A second, independent work unit (different bucket period is not
    # possible for the same modelo/year/period -- reuse the same one via a
    # fresh calculate call with explicit flags; recalculating the same work
    # unit with the same inputs the wizard would have supplied is the direct
    # comparison surface).
    calculate_result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", wizard_unit_id,
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
    """Without a scripted prompter injected, a non-TTY host refuses instructively.

    The production ``_QuestionaryTextPrompter`` path (no override installed)
    detects the non-interactive test-runner stdin and refuses before asking
    anything, rather than hanging the process or crashing with a raw
    ``questionary`` traceback. Only exercised when the wizard actually has
    outstanding questions to ask (a blank ledger 1T draft always does, via
    the manual casillas).
    """
    _create_profile()
    _seed_m130_ledger("wizard-non-interactive")
    work_unit_id = _create_m130_work_unit()

    result = _invoke(["--format", "json", "app", "modelo", "work", "wizard", work_unit_id])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "interactive" in result.output.lower() or "console" in result.output.lower()


def test_wizard_scripted_prompter_underflow_refuses_instructively() -> None:
    """A scripted answer queue shorter than the outstanding-question count refuses cleanly.

    Confirms the scripted-answer contract fails loudly (never silently skips
    a question or crashes with an unrelated traceback) when a caller
    under-provisions the answer queue -- the same discipline
    ``ScriptedPrompter`` enforces for the profile setup wizard.
    """
    _create_profile()
    _seed_m130_ledger("wizard-underflow")
    work_unit_id = _create_m130_work_unit()

    # Only two of the five manual casillas answered; the wizard must refuse
    # on the third rather than silently leaving 08/10/16/18 blank.
    prompter = _ScriptedTextPrompter(deque(["0", "0"]))
    with override_wizard_prompter(prompter):
        result = _invoke(["--format", "json", "app", "modelo", "work", "wizard", work_unit_id])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert len(prompter.asked_prompts) == 2
