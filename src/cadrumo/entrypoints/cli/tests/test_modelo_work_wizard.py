"""Contract coverage for ``aeat app modelo work wizard``.

The wizard is a guided front end over the flow substrate: on a real
terminal it renders the full-screen or line-mode frontend, and a
non-interactive host with outstanding questions refuses with the
substrate's typed unsupported-console error rather than blocking. So these
tests exercise the wizard at the two contract surfaces a non-terminal test
process can honestly reach:

* the non-interactive refusal (a piped caller with outstanding steps), and
* the substrate's scripted driver
  (:func:`~cadrumo.application.flows.run_scripted_flow`) walking the wizard's
  own discovered steps and projected definition, then feeding those answers
  through the identical ``work calculate`` composition the wizard uses.

Nothing is mocked, stubbed, or patched: the real registry engine, ledger
aggregation, and bucket-scoped storage answer behind the scripted drive and
the CLI calculate, and the oracle Modelo 130 draft is asserted against
real ledger-seeded income/expense rows.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....application.flows import run_scripted_flow
from ....core import resolve_active_bucket_id
from ....core.flows import FlowMode
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401
from ....tests.user_profile import register_cli_profile
from .._modelo_behavior_support import resolve_work_unit_for_cli
from .._modelo_work_wizard_cli import (
    _ACTIVE_RUNS,
    _binding_grounding_lookup,
    _definition_from_steps,
    _outstanding_wizard_steps,
    _page_key,
    _WizardStep,
)
from .._modelo_work_wizard_payloads import WizardPromptedCasillaPayload
from ._m130_source_support import seed_m130_expense_transaction, seed_m130_income_transaction
from ._modelo_work_ux_support import _create_m130_work_unit

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# Oracle: AEAT DR 130 Instrucciones, casilla 03 (rendimiento neto = ingresos -
# gastos) and casilla 04 (pago fraccionado = 20% del rendimiento neto,
# art-110 RD 439/2007). Casillas 01/02 are ledger-derived, so the oracle inputs
# are real seeded transactions rather than hand-typed casilla overrides.
_INGRESOS = Decimal("3000.00")
_GASTOS = Decimal("600.00")
_RENDIMIENTO_NETO = _INGRESOS - _GASTOS
_PAGO_FRACCIONADO = (_RENDIMIENTO_NETO * Decimal("20") / Decimal("100")).quantize(Decimal("0.01"))

# The M130 1T manual-input surface (registry ``input_kind = "manual"``) is
# casillas 06/08/10/16/18 (see ``_MANUAL_CASILLAS``), all zero for this oracle
# (no withholdings, not an agrarian activity, no vivienda deduction, first
# filing of the ejercicio).
#
# The one ``previous_filing`` binding whose selector has no local prior M100
# filing to auto-resolve at 1T with a blank bucket. It is not absent-by-design
# (unlike the M130-internal same-ejercicio carries, which are), so the
# calculation engine's own refusal drives the wizard's one follow-up prompt.
_PREV_YEAR_INCOME_ANSWER = "13000"


_MANUAL_CASILLAS = ["06", "08", "10", "16", "18"]
_PREV_YEAR_BINDING_KEY = "irpf.previous_year_economic_activity_net_income"


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _scripted_manual_answers(work_unit_id: str) -> list[tuple[_WizardStep, str]]:
    """Walk the wizard's outstanding manual pages through the scripted substrate.

    Reproduces exactly what the wizard does — resolve the unit, discover its
    outstanding manual steps, project them into a flow definition — then drives
    that definition through :func:`run_scripted_flow` (the substrate's
    frontend-free scripted driver) instead of the interactive frontend a
    non-terminal test process cannot host. Returns ``(step, canonical_value)``
    pairs in flow order, read back off the engine state exactly as the wizard
    reads them.
    """
    run_token = "test-scripted-wizard"  # noqa: S105 - a copy-table run token, not a credential
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    # Step discovery reads the registry and the bucket-scoped profile, so it
    # runs inside a real profile storage session — the same session the CLI
    # command opens per invocation.
    with open_test_profile_session(bucket_id):
        unit = resolve_work_unit_for_cli(work_unit_id=work_unit_id)
        steps = _outstanding_wizard_steps(unit)
        _ACTIVE_RUNS[run_token] = {}
        try:
            definition = _definition_from_steps(steps, run_token=run_token)
            tokens = ["0"] * len(steps)
            state, projection = run_scripted_flow(definition, tokens, mode=FlowMode.CREATE)
            assert projection.submit_eligible
            answers: list[tuple[_WizardStep, str]] = []
            for step in steps:
                answers.append((step, (state.answers.get(_page_key(step)) or "").strip()))
            return answers
        finally:
            _ACTIVE_RUNS.pop(run_token, None)


def _calculate_flags(overrides: list[str]) -> list[str]:
    flags: list[str] = []
    for override in overrides:
        flags += ["--casilla", override]
    flags += ["--binding", f"{_PREV_YEAR_BINDING_KEY}={_PREV_YEAR_INCOME_ANSWER}"]
    return flags


def _create_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "identity.tax_id": "12345678Z",
            "identity.name": "Operator",
            "identity.surnames": "Wizard",
            "activities.description": "design",
        },
    )


def _seed_m130_ledger(source_key: str) -> None:
    seed_m130_income_transaction(amount=_INGRESOS, filing_year=2025, source_key=source_key)
    seed_m130_expense_transaction(amount=_GASTOS, filing_year=2025, source_key=source_key)


def test_wizard_scripted_path_walks_the_manual_sequence_and_lands_the_m130_draft() -> None:
    """The wizard's discovered steps, driven scripted, produce the oracle M130 draft.

    The substrate's scripted driver walks the wizard's own outstanding-step
    definition (every registry-declared manual casilla), and those answers plus
    the one engine-discovered previous-filing binding, fed through the identical
    ``work calculate`` composition the wizard uses, land the oracle draft:
    ledger-bound 01/02, computed rendimiento neto 03 and pago fraccionado 04/19.
    """
    _create_profile()
    _seed_m130_ledger("wizard-scripted-sequence")
    work_unit_id = _create_m130_work_unit()

    answers = _scripted_manual_answers(work_unit_id)

    # The full manual-input sequence: exactly the registry-declared manual
    # casillas, each answered through the scripted substrate path.
    assert all(step.channel == "casilla" for step, _ in answers)
    assert sorted(step.key for step, _ in answers) == _MANUAL_CASILLAS
    assert all(value == "0" for _, value in answers)
    for step, _ in answers:
        assert step.legal_refs, f"casilla {step.key} must carry legal_refs"
        assert step.source_refs, f"casilla {step.key} must carry source_refs"

    overrides = [f"{step.key}={value}" for step, value in answers]
    result = _invoke(
        ["--format", "json", "app", "modelo", "work", "calculate", work_unit_id, *_calculate_flags(overrides)],
    )
    assert result.exit_code == 0, result.output

    payload = _payload(result.output)
    assert payload["state"] == "borrador"
    casillas = payload["casilla_values"]
    assert Decimal(casillas["01"]) == _INGRESOS
    assert Decimal(casillas["02"]) == _GASTOS
    assert Decimal(casillas["03"]) == _RENDIMIENTO_NETO
    assert Decimal(casillas["04"]) == _PAGO_FRACCIONADO
    assert Decimal(casillas["19"]) == _PAGO_FRACCIONADO


def test_wizard_scripted_inputs_compose_the_same_calculate_as_work_calculate() -> None:
    """The scripted-wizard inputs assemble the same overrides and draft as ``work calculate``.

    The wizard is a guided front end over the shared calculate path
    (``aeat-architecture-boundaries``), not a second surface: its
    scripted-derived casilla overrides are byte-identical to the override set a
    hand-typed ``work calculate`` receives, and both compose the identical draft.
    """
    _create_profile()
    _seed_m130_ledger("wizard-scripted-parity")
    work_unit_id = _create_m130_work_unit()

    answers = _scripted_manual_answers(work_unit_id)
    scripted_overrides = sorted(f"{step.key}={value}" for step, value in answers)

    # The wizard's inputs are exactly the override set work calculate receives.
    assert scripted_overrides == [f"{casilla}=0" for casilla in _MANUAL_CASILLAS]

    scripted_draft = _payload(
        _invoke(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "work",
                "calculate",
                work_unit_id,
                *_calculate_flags(scripted_overrides),
            ],
        ).output,
    )["casilla_values"]
    canonical_draft = _payload(
        _invoke(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "work",
                "calculate",
                work_unit_id,
                *_calculate_flags([f"{casilla}=0" for casilla in _MANUAL_CASILLAS]),
            ],
        ).output,
    )["casilla_values"]

    assert scripted_draft == canonical_draft


def test_wizard_non_interactive_host_with_steps_refuses_with_the_typed_console_error() -> None:
    """A non-TTY caller with outstanding steps gets the substrate's typed refusal.

    The test process is non-interactive, so the wizard — which has outstanding
    manual casillas to prompt for — must refuse through the flow substrate's
    unsupported-console error rather than block. Asserted structurally on the
    envelope error code, never on localized prose.
    """
    _create_profile()
    _seed_m130_ledger("wizard-non-interactive")
    work_unit_id = _create_m130_work_unit()

    result = _invoke(["--format", "json", "app", "modelo", "work", "wizard", work_unit_id])

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    error = json.loads(result.output)["error"]
    assert error["code"] == "REFUSED_FLOW_UNSUPPORTED_CONSOLE"


def _valid_prompted_casilla_kwargs() -> dict[str, object]:
    return {
        "casilla_id": "01",
        "number": "01",
        "label": "Ingresos",
        "channel": "casilla",
        "key": "01",
        "value": "0",
        "legal_refs": ("ley-35-2006:art-27",),
        "source_refs": ("aeat-modelo-130-instrucciones-2026",),
        "help_text": None,
    }


def test_wizard_prompted_casilla_payload_round_trips_valid_row() -> None:
    row = WizardPromptedCasillaPayload.model_validate(_valid_prompted_casilla_kwargs())

    assert row.channel == "casilla"
    assert row.legal_refs == ("ley-35-2006:art-27",)


@pytest.mark.parametrize(
    ("field", "bad_value"),
    (
        ("channel", "bogus"),
        ("label", ""),
        ("key", ""),
        ("value", ""),
        ("legal_refs", ()),
        ("source_refs", ()),
    ),
)
def test_wizard_prompted_casilla_payload_refuses_malformed_field(field: str, bad_value: object) -> None:
    """A malformed channel, blank display field, or empty grounding is refused.

    A permissive bare-``str`` shell (the defect this finding reported) would
    have accepted every one of these.
    """
    kwargs = {**_valid_prompted_casilla_kwargs(), field: bad_value}

    with pytest.raises(ValidationError):
        WizardPromptedCasillaPayload.model_validate(kwargs)


def test_binding_grounding_lookup_covers_a_real_m130_binding() -> None:
    """The follow-up-step grounding lookup resolves real registry grounding.

    ``_follow_up_step_for_missing_input`` used to leave ``legal_refs`` /
    ``source_refs`` empty for a retry-discovered binding/relation step, which
    the now-required grounding on ``WizardPromptedCasillaPayload`` would
    refuse. This proves the lookup actually finds non-empty grounding for a
    real registry binding on a real work unit, not just that it type-checks.
    """
    _create_profile()
    _seed_m130_ledger("wizard-binding-grounding-lookup")
    work_unit_id = _create_m130_work_unit()
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None

    with open_test_profile_session(bucket_id):
        unit = resolve_work_unit_for_cli(work_unit_id=work_unit_id)
        lookup = _binding_grounding_lookup(unit)

    assert lookup, "expected at least one registry binding for the M130 1T scope"
    for legal_refs, source_refs in lookup.values():
        assert legal_refs, "every looked-up binding must carry legal_refs"
        assert source_refs, "every looked-up binding must carry source_refs"
