"""Contract coverage for ``aeat app modelo work wizard``.

The wizard is a guided front end over the flow substrate: on a real
terminal it renders the line-mode frontend, and a non-interactive host
with outstanding questions refuses with the
substrate's typed unsupported-console error rather than blocking. So these
tests exercise the wizard at the two contract surfaces a non-terminal test
process can honestly reach:

* the non-interactive refusal (a piped caller with outstanding steps), and
* the substrate's scripted driver
  (:func:`~cadrumo.application.flows.scripted.run_scripted_flow`) walking the wizard's
  own discovered steps and projected definition, then feeding those answers
  through the identical ``work calculate`` composition the wizard uses.

The scripted-drive coverage uses the real registry engine, ledger aggregation,
and bucket-scoped storage. The registered CLI success test binds that same real
line frontend to prompt-toolkit's headless IO adapters; it does not replace the
flow implementation or alter the production non-interactive refusal.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator, Sequence
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest
from click.testing import Result
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output.plain_text import PlainTextOutput
from pydantic import ValidationError

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session

from ....adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend as _isolated_cli_backend,
)
from ....application.flows import line_frontend as _line_frontend
from ....application.flows.copy import assemble_page_copy
from ....application.flows.definition import FlowDefinition, FlowPage
from ....application.flows.errors import FlowCopyResolutionError
from ....application.flows.scripted import run_scripted_flow
from ....application.modelo.action_errors import modelo_work_wizard_retry_exhausted_precondition
from ....application.modelo.work_wizard import ModeloWorkWizardStep, open_modelo_work_wizard
from ....application.user_profile.login_session import login_profile, resolve_login_target
from ....core.flows import FlowMode
from ....core.operator_action_enums import ActionConditionality, NoRecoveryOutcome
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from .. import _modelo_work_wizard_cli
from .._modelo_work_wizard_payloads import WizardPromptedCasillaPayload
from ._m130_source_support import seed_m130_expense_transaction, seed_m130_income_transaction
from ._modelo_work_ux_support import _create_m130_work_unit, load_work_unit_by_id
from .cli_runner import invoke_cached_cli
from .modelo_cli import create_modelo_work_unit_via_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

__all__ = ["_isolated_cli_backend"]

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


def test_wizard_retry_exhaustion_has_a_declared_no_recovery_outcome() -> None:
    """The retry cap neither infers a command nor leaves its terminal state implicit."""
    failure = modelo_work_wizard_retry_exhausted_precondition(work_unit_id="a" * 64, retry_limit=3)

    verdict = failure.verdict
    assert verdict.action is None
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


def _invoke(fixture: NativeCliProfileFixture, args: Sequence[str]) -> Result:
    """Run one protected command through the fixture's installed profile worker."""
    if fixture.label is None:
        raise AssertionError("the native profile fixture has not registered a subject")
    close_active_bucket_session()
    result = invoke_cached_cli(
        (
            "--format",
            "json",
            "--profile",
            fixture.label,
            "--profile-secrets-stdin",
            *args,
        ),
        input=json.dumps({"profile_passphrase": fixture.passphrase}),
    )
    if fixture.passphrase in result.output:
        pytest.fail("profile credential appeared in CLI output", pytrace=False)
    return result


def _scripted_manual_answers(
    work_unit_id: str, *, fixture: NativeCliProfileFixture, operation: PinnedAuthorityOperation
) -> list[tuple[ModeloWorkWizardStep, str]]:
    """Walk the wizard's outstanding manual pages through the scripted substrate.

    Reproduces exactly what the wizard does — resolve the unit, discover its
    outstanding manual steps, project them into a flow definition — then drives
    that definition through :func:`run_scripted_flow` (the substrate's
    frontend-free scripted driver) instead of the interactive frontend a
    non-terminal test process cannot host. Returns ``(step, canonical_value)``
    pairs in flow order, read back off the engine state exactly as the wizard
    reads them.
    """
    bucket_id = _login_for_oracle(fixture, operation=operation)
    # Step discovery reads the registry and the bucket-scoped profile, so it
    # runs inside a real profile storage session — the same session the CLI
    # command opens per invocation.
    with open_test_profile_session(bucket_id):
        unit = load_work_unit_by_id(work_unit_id)
        with open_modelo_work_wizard(unit, operation=operation) as wizard:
            definition = wizard.definition_for()
            tokens = ["0"] * len(wizard.steps)
            state, projection = run_scripted_flow(definition, tokens, mode=FlowMode.CREATE)
            assert projection.submit_eligible
            return list(wizard.answer_pairs(state))


def _calculate_flags(overrides: list[str]) -> list[str]:
    flags: list[str] = []
    for override in overrides:
        flags += ["--casilla", override]
    flags += ["--binding", f"{_PREV_YEAR_BINDING_KEY}={_PREV_YEAR_INCOME_ANSWER}"]
    return flags


def _create_profile(fixture: NativeCliProfileFixture) -> None:
    """Register a profile served by the test-owned native worker."""
    fixture.register(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "identity.tax_id": "12345678Z",
            "identity.name": "Operator",
            "identity.surnames": "Wizard",
            "activities.description": "design",
            "censo.activity_start_date": "2025-01-01",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.regime": "GENERAL",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
    )


def _login_for_oracle(fixture: NativeCliProfileFixture, *, operation: PinnedAuthorityOperation) -> str:
    """Open the real password-registered profile before encrypted local assertions."""
    if fixture.label is None:
        raise AssertionError("the native profile fixture has not registered a subject")
    close_active_bucket_session()
    login = login_profile(
        name=fixture.label,
        passphrase_callback=lambda: fixture.passphrase,
        profile_decode_context=operation.profile_decode_context(),
    )
    assert login.bucket_id == resolve_login_target(fixture.label).bucket_id
    return login.bucket_id


@pytest.fixture
def wizard_profile(tmp_path: Path) -> Iterator[NativeCliProfileFixture]:
    """Provide one password-registered profile served by its real worker."""
    with native_cli_profile_scope(tmp_path) as fixture:
        _create_profile(fixture)
        yield fixture


def _seed_m130_ledger(
    source_key: str, *, fixture: NativeCliProfileFixture, operation: PinnedAuthorityOperation
) -> None:
    _login_for_oracle(fixture, operation=operation)
    seed_m130_income_transaction(amount=_INGRESOS, filing_year=2025, source_key=source_key)
    seed_m130_expense_transaction(amount=_GASTOS, filing_year=2025, source_key=source_key)


def _create_m123_work_unit(*, operation: PinnedAuthorityOperation) -> str:
    """Create the real 2025 2T work unit used by the no-prompt wizard path."""
    revision = operation.snapshot("123", filing_year=2025, period="2T").revision
    return create_modelo_work_unit_via_cli(
        modelo="123",
        filing_year=2025,
        period="2T",
        revision=revision.id,
    )


def _assert_encrypted_calculation_matches_cli(
    fixture: NativeCliProfileFixture,
    *,
    operation: PinnedAuthorityOperation,
    work_unit_id: str,
    payload: dict[str, object],
    expect_ledger_sources: bool,
) -> None:
    """Compare the worker receipt with the password-opened encrypted revision."""
    bucket_id = _login_for_oracle(fixture, operation=operation)
    revision_id = payload.get("calculation_revision_id")
    assert isinstance(revision_id, str) and revision_id
    revision = CalculationRevisionCatalogueRepository().load(operation=operation).get(revision_id)
    assert revision is not None
    assert revision.work_unit_id == work_unit_id
    unit = WorkUnitCatalogueRepository(bucket_id=bucket_id).load().get(work_unit_id)
    assert unit is not None
    assert unit.current_calculation_revision_id == revision.calculation_revision_id

    public_values = payload.get("casilla_values")
    assert isinstance(public_values, dict)
    persisted_values = {key: value for key, value in revision.casilla_values.items()}
    assert set(public_values) == set(persisted_values)
    assert all(Decimal(str(public_values[key])) == persisted_values[key] for key in public_values)

    if expect_ledger_sources:
        transactions = TransactionCatalogueRepository(bucket_id=bucket_id).load().transactions
        assert len(revision.source_transaction_ids) == 2
        assert set(revision.source_transaction_ids) <= set(transactions)


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_wizard_scripted_path_walks_the_manual_sequence_and_lands_the_m130_draft(
    wizard_profile: NativeCliProfileFixture, *, operation: PinnedAuthorityOperation
) -> None:
    """The wizard's discovered steps, driven scripted, produce the oracle M130 draft.

    The substrate's scripted driver walks the wizard's own outstanding-step
    definition (every registry-declared manual casilla), and those answers plus
    the one engine-discovered previous-filing binding, fed through the identical
    ``work calculate`` composition the wizard uses, land the oracle draft:
    ledger-bound 01/02, computed rendimiento neto 03 and pago fraccionado 04/19.
    """
    _seed_m130_ledger("wizard-scripted-sequence", fixture=wizard_profile, operation=operation)
    work_unit_id = _create_m130_work_unit()

    answers = _scripted_manual_answers(work_unit_id, fixture=wizard_profile, operation=operation)

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
        wizard_profile,
        ["app", "modelo", "work", "calculate", work_unit_id, *_calculate_flags(overrides)],
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


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_wizard_scripted_inputs_compose_the_same_calculate_as_work_calculate(
    wizard_profile: NativeCliProfileFixture, *, operation: PinnedAuthorityOperation
) -> None:
    """The scripted-wizard inputs assemble the same overrides and draft as ``work calculate``.

    The wizard is a guided front end over the shared calculate path
    (``aeat-architecture-boundaries``), not a second surface: its
    scripted-derived casilla overrides are byte-identical to the override set a
    hand-typed ``work calculate`` receives, and both compose the identical draft.
    """
    _seed_m130_ledger("wizard-scripted-parity", fixture=wizard_profile, operation=operation)
    work_unit_id = _create_m130_work_unit()

    answers = _scripted_manual_answers(work_unit_id, fixture=wizard_profile, operation=operation)
    scripted_overrides = sorted(f"{step.key}={value}" for step, value in answers)

    # The wizard's inputs are exactly the override set work calculate receives.
    assert scripted_overrides == [f"{casilla}=0" for casilla in _MANUAL_CASILLAS]

    scripted_result = _invoke(
        wizard_profile,
        [
            "app",
            "modelo",
            "work",
            "calculate",
            work_unit_id,
            *_calculate_flags(scripted_overrides),
        ],
    )
    assert scripted_result.exit_code == 0, scripted_result.output
    scripted_draft = _payload(scripted_result.output)["casilla_values"]
    canonical_result = _invoke(
        wizard_profile,
        [
            "app",
            "modelo",
            "work",
            "calculate",
            work_unit_id,
            *_calculate_flags([f"{casilla}=0" for casilla in _MANUAL_CASILLAS]),
        ],
    )
    assert canonical_result.exit_code == 0, canonical_result.output
    canonical_draft = _payload(canonical_result.output)["casilla_values"]

    assert scripted_draft == canonical_draft


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_wizard_non_interactive_host_with_steps_refuses_with_the_typed_console_error(
    wizard_profile: NativeCliProfileFixture, *, operation: PinnedAuthorityOperation
) -> None:
    """A non-TTY caller with outstanding steps gets the substrate's typed refusal.

    The test process is non-interactive, so the wizard — which has outstanding
    manual casillas to prompt for — must refuse through the flow substrate's
    unsupported-console error rather than block. Asserted structurally on the
    envelope error code, never on localized prose.
    """
    _seed_m130_ledger("wizard-non-interactive", fixture=wizard_profile, operation=operation)
    work_unit_id = _create_m130_work_unit()

    result = _invoke(wizard_profile, ["app", "modelo", "work", "wizard", work_unit_id])

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    error = json.loads(result.output)["error"]
    assert error["code"] == "REFUSED_FLOW_UNSUPPORTED_CONSOLE"


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_registered_wizard_cli_interactive_flow_emits_ledger_source_provenance(
    wizard_profile: NativeCliProfileFixture,
    monkeypatch: pytest.MonkeyPatch,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """The registered wizard command carries its calculated ledger trace to JSON.

    The headless terminal is an explicit prompt-toolkit session, not a mocked
    flow: the live parser dispatches to the registered ``work wizard`` handler,
    whose real line frontend consumes the queued operator answers and then
    emits its command-owned JSON envelope. The separate non-interactive test
    above retains the production refusal for ordinary piped callers.
    """
    _seed_m130_ledger("wizard-cli-source-provenance", fixture=wizard_profile, operation=operation)
    work_unit_id = _create_m130_work_unit()

    # Five registry-discovered manual casillas, then submit from review.
    keystrokes = "0\r" * len(_MANUAL_CASILLAS) + "\r"
    with create_pipe_input() as pipe:
        pipe.send_text(keystrokes)

        def _headless_line_frontend(definition: FlowDefinition) -> _line_frontend.LineFlowFrontend:
            return _line_frontend.LineFlowFrontend(
                definition,
                input=pipe,
                output=PlainTextOutput(StringIO()),
            )

        # Bind the handler's real frontend to the substrate's documented
        # headless terminal adapters. Its prompt/engine implementation is not
        # replaced; explicit IO merely avoids claiming this test process's
        # non-TTY stdio is an operator console. The preceding refusal test
        # keeps that production guard covered independently.
        monkeypatch.setattr(_modelo_work_wizard_cli, "LineFlowFrontend", _headless_line_frontend)
        result = _invoke(wizard_profile, ["app", "modelo", "work", "wizard", work_unit_id])

    assert result.exit_code == 0, result.output
    document = json.loads(result.output)
    assert document["command"] == "modelo.work.wizard"
    payload = _payload(result.output)
    assert {row["key"] for row in payload["prompted_casillas"]} == {"06", "08", "10", "16", "18"}
    provenance = payload["source_provenance"]
    assert provenance, "the wizard CLI JSON must retain the calculated ledger source trace"
    ledger_rows = {
        row["contributor_binding_source"]: row["source_ref"]
        for row in provenance
        if row["contributor_binding_source"]
        in {
            "ledger_renta_income_aggregation",
            "ledger_renta_gastos_pago_fraccionado_aggregation",
        }
    }
    assert set(ledger_rows) == {
        "ledger_renta_income_aggregation",
        "ledger_renta_gastos_pago_fraccionado_aggregation",
    }
    assert all(source_ref.startswith("transaction:") for source_ref in ledger_rows.values())
    _assert_encrypted_calculation_matches_cli(
        wizard_profile,
        operation=operation,
        work_unit_id=work_unit_id,
        payload=payload,
        expect_ledger_sources=True,
    )


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_registered_m123_wizard_prompts_registry_pages_and_publishes(
    wizard_profile: NativeCliProfileFixture,
    monkeypatch: pytest.MonkeyPatch,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """The registered M123 2T wizard asks its nine pinned pages, then publishes."""
    work_unit_id = _create_m123_work_unit(operation=operation)
    page_ids = {"10", "11", "13", "01", "02", "04", "05", "07", "08"}
    keystrokes = "0\r" * len(page_ids) + "\r"
    with create_pipe_input() as pipe:
        pipe.send_text(keystrokes)

        def _headless_line_frontend(definition: FlowDefinition) -> _line_frontend.LineFlowFrontend:
            return _line_frontend.LineFlowFrontend(
                definition,
                input=pipe,
                output=PlainTextOutput(StringIO()),
            )

        monkeypatch.setattr(_modelo_work_wizard_cli, "LineFlowFrontend", _headless_line_frontend)
        result = _invoke(wizard_profile, ["app", "modelo", "work", "wizard", work_unit_id])

    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    assert {row["key"] for row in payload["prompted_casillas"]} == page_ids
    assert payload["saved"] is True
    _assert_encrypted_calculation_matches_cli(
        wizard_profile,
        operation=operation,
        work_unit_id=work_unit_id,
        payload=payload,
        expect_ledger_sources=False,
    )


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


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_canonical_wizard_factory_carries_real_registry_grounding(
    wizard_profile: NativeCliProfileFixture, *, operation: PinnedAuthorityOperation
) -> None:
    """The public wizard factory discovers the registry's grounded question set."""
    _seed_m130_ledger("wizard-binding-grounding-lookup", fixture=wizard_profile, operation=operation)
    work_unit_id = _create_m130_work_unit()
    bucket_id = _login_for_oracle(wizard_profile, operation=operation)

    with open_test_profile_session(bucket_id):
        unit = load_work_unit_by_id(work_unit_id)
        with open_modelo_work_wizard(unit, operation=operation) as wizard:
            steps = wizard.steps
            definition = wizard.definition_for()
            first_page = definition.sections[0].items[0]
            assert isinstance(first_page, FlowPage)
            assert assemble_page_copy(first_page).prompt

    assert steps, "expected the M130 wizard to expose registry-backed questions"
    for step in steps:
        assert step.legal_refs, f"wizard question {step.key} must carry legal_refs"
        assert step.source_refs, f"wizard question {step.key} must carry source_refs"
    with pytest.raises(FlowCopyResolutionError):
        assemble_page_copy(first_page)
