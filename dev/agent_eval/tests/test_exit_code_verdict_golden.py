"""Exit-code-as-verdict golden gate for the operator eval.

Guards against an exit code being misread as a crash: a non-zero CLI process
exit code paired with a well-formed JSON envelope is a domain VERDICT the operator
must read and act on, not a crash to abort on or retry blindly.

This module dispatches a REAL ``modelo work verify`` on a real M130 draft that
legitimately fails cross-period clean-state (the same reproduction as
``test_modelo_130_verify_by_natural_key_refuses_without_clean_cross_period_state``
in ``entrypoints/cli/tests/test_modelo_work_natural_key.py``: an M130 quarter with
no prior filed M100 for the preceding year), decodes the real stdout envelope, and
feeds the real exit code plus the real envelope into
:func:`dev.agent_eval.check_exit_code_scenario`. No mocks: the exit code, the
envelope shape, the ``status``, and the continuation-command citation are all
real CLI/registry output.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.core import resolve_active_bucket_id
from cadrumo.core.json_contract import EnvelopeStatus
from cadrumo.domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from cadrumo.tests.cli_envelope import require_schema_envelope
from cadrumo.tests.cli_runner import invoke_cached_cli
from cadrumo.tests.profile_capsule import open_test_profile_session
from cadrumo.tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture

from .. import ExitCodeScenario, check_exit_code_scenario
from ._real_cli_support import valid_cli_commands

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FILING_YEAR = 2025
_PERIOD = "1T"


def _create_profile() -> None:
    result = invoke_cached_cli(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--entity-type", "natural_person",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--surnames", "Exit Code Golden Eval",
            "--activity", "design",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _seed_m130_income_transaction(*, amount: Decimal, filing_year: int) -> None:
    """Seed one real actividad-economica income row for source-bound M130 casilla 01.

    Deliberately local to this module rather than importing
    ``entrypoints.cli.tests._m130_source_support`` (a private helper module scoped
    to the ``entrypoints.cli.tests`` package) across a package boundary, mirroring
    the pattern in ``test_response_provenance_golden.py``. Writes a genuine row
    through the real ``TransactionCatalogueRepository`` - no expense is seeded, so
    the scenario reproduces the same cross-period clean-state gap the natural-key
    CLI test exercises.
    """
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None, "test profile must install an active bucket pointer"
    value_date = date(filing_year, 2, 15)
    income = Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=f"exit-code-golden-income-{filing_year}",
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
                currency="EUR",
                counterparty="Cliente SA",
                description="exit-code golden eval income",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="f" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=datetime(filing_year, 2, 16, 12, 0, tzinfo=UTC),
                    provider_name="manual-ledger",
                ),
                raw_fields={"source_kind": "m130_exit_code_golden_income", "source_key": "exit-code-golden"},
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "business_pct": None,
            "category_id": None,
            "taxable_base": amount,
            "iva_rate": None,
            "iva_amount": None,
            "irpf_category": "actividad_economica",
            "purchase_invoice_evidence_id": None,
            "classified_at": datetime(filing_year, 2, 16, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )
    with open_test_profile_session(bucket_id):
        existing = TransactionCatalogueRepository(bucket_id=bucket_id).load()
        transactions = (*tuple(existing.transactions.values()), income)
        TransactionCatalogueRepository(bucket_id=bucket_id).save(
            TransactionCatalogue.from_transactions(transactions),
        )


def _dispatch_m130_verify_with_cross_period_finding() -> tuple[int, dict[str, Any]]:
    """Dispatch a REAL M130 create -> calculate -> verify that legitimately exits 1.

    No prior filed M100 exists for the preceding year, so the real
    ``verify_modelo_revision`` action refuses ``granted_verificado_completo`` on a
    real ``cross_period_dependency_unclean`` finding and the CLI raises
    ``typer.Exit(code=1)`` - the same reproduction as
    ``test_modelo_130_verify_by_natural_key_refuses_without_clean_cross_period_state``.

    Returns:
        The real process exit code and the fully decoded stdout JSON envelope
        (the top-level document, not just its ``result`` sub-mapping).
    """
    _create_profile()
    _seed_m130_income_transaction(amount=Decimal("12000.00"), filing_year=_FILING_YEAR)

    created = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", str(_FILING_YEAR), "--period", _PERIOD,
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output

    # Casilla 02 (gastos) is bucket-bound (aggregated from deductible ledger rows)
    # and resolves to 0 with no expense seeded; immaterial to the cross-period
    # clean-state check this scenario exercises.
    calculated = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate",
            "--modelo", "130", "--year", str(_FILING_YEAR), "--period", _PERIOD,
            "--binding", "irpf.previous_year_economic_activity_net_income=13000",
            "--binding", "modelo-130-resultados-negativos-anteriores=0",
        ],
    )  # fmt: skip
    assert calculated.exit_code == 0, calculated.output

    verified = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "verify",
            "--modelo", "130", "--year", str(_FILING_YEAR), "--period", _PERIOD,
        ],
    )  # fmt: skip
    payload = require_schema_envelope(verified.output)
    assert payload["granted_verificado_completo"] is False, verified.output
    assert payload["findings"][0]["kind"] == "cross_period_dependency_unclean", verified.output

    envelope: dict[str, Any] = json.loads(verified.output)
    return verified.exit_code, envelope


def _strip_notice_suggestions(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of ``envelope`` with every notice ``suggestion`` cleared.

    Reproduces the historical exit-code-as-crash confusion this scenario closes:
    a non-zero exit whose JSON body carries no continuation guidance would read
    as a dead end, not an actionable verdict.
    """
    notices = envelope.get("notices")
    stripped_notices = (
        [{**notice, "suggestion": None} if isinstance(notice, Mapping) else notice for notice in notices]
        if isinstance(notices, list)
        else notices
    )
    return {**envelope, "notices": stripped_notices}


def test_exit_1_with_findings_reads_as_an_actionable_verdict_not_a_crash() -> None:
    """A real M130 verify that legitimately exits 1 passes every category-7 dimension.

    (i) the JSON body is well-formed, (ii) its ``status`` is not "success", and
    (iii) a real registry command key (``modelo.reconcile.file``) - a genuine
    continuation the operator can run next - is cited in the envelope notices.
    """
    exit_code, envelope = _dispatch_m130_verify_with_cross_period_finding()
    assert exit_code == 1

    scenario = ExitCodeScenario(
        name="m130-verify-cross-period-unclean-exit-1",
        command="modelo.work.verify",
        expected_exit_code=1,
        tool_result_status=EnvelopeStatus.WARNING,
        expected_next_action="modelo.reconcile.file",
    )

    result = check_exit_code_scenario(
        scenario,
        exit_code=exit_code,
        envelope=envelope,
        valid_commands=valid_cli_commands(),
    )

    assert result.passed, result.failures
    assert result.exit_code_matches
    assert result.envelope_well_formed
    assert result.status_is_non_success
    assert result.next_action_is_continuation
    assert envelope["status"] != EnvelopeStatus.SUCCESS.value


def test_runner_rejects_an_exit_1_with_no_continuation_guidance() -> None:
    """Anti-tautology: an exit 1 whose notices carry no continuation MUST fail.

    Takes the SAME real dispatched exit code and envelope and strips every
    notice ``suggestion`` - reproducing a verdict that reads as a dead end (the
    "treats exit 1 as terminal" case) - and proves
    ``next_action_is_continuation`` catches it. Without this proof the dimension
    could pass vacuously regardless of what the CLI actually emitted.
    """
    exit_code, envelope = _dispatch_m130_verify_with_cross_period_finding()
    stripped = _strip_notice_suggestions(envelope)

    scenario = ExitCodeScenario(
        name="m130-verify-cross-period-unclean-exit-1",
        command="modelo.work.verify",
        expected_exit_code=1,
        tool_result_status=EnvelopeStatus.WARNING,
        expected_next_action="modelo.reconcile.file",
    )

    result = check_exit_code_scenario(
        scenario,
        exit_code=exit_code,
        envelope=stripped,
        valid_commands=valid_cli_commands(),
    )

    assert not result.passed
    assert not result.next_action_is_continuation
    assert any("dead end" in failure for failure in result.failures)
    # The other real dimensions are untouched by stripping suggestions.
    assert result.exit_code_matches
    assert result.envelope_well_formed
    assert result.status_is_non_success


def test_runner_rejects_an_exit_code_mismatch() -> None:
    """Anti-tautology: a scenario expecting the wrong exit code MUST fail.

    Uses the SAME real dispatch (a genuine exit 1) but declares
    ``expected_exit_code=2``, proving ``exit_code_matches`` is a real comparison
    against the dispatched process exit code, not a vacuous pass.
    """
    exit_code, envelope = _dispatch_m130_verify_with_cross_period_finding()

    scenario = ExitCodeScenario(
        name="m130-verify-cross-period-unclean-wrong-exit",
        command="modelo.work.verify",
        expected_exit_code=2,
        tool_result_status=EnvelopeStatus.WARNING,
        expected_next_action="modelo.reconcile.file",
    )

    result = check_exit_code_scenario(
        scenario,
        exit_code=exit_code,
        envelope=envelope,
        valid_commands=valid_cli_commands(),
    )

    assert not result.passed
    assert not result.exit_code_matches


def test_exit_code_scenario_rejects_success_status_for_a_nonzero_exit() -> None:
    """Anti-tautology at the model layer: a "success" verdict for a non-zero exit is invalid.

    An ``ExitCodeScenario`` cannot even be constructed declaring
    ``tool_result_status=EnvelopeStatus.SUCCESS`` - the exact exit-code-as-crash
    confusion this category exists to catch is refused at the typed boundary,
    not just at check time.
    """
    with pytest.raises(ValueError, match=r"tool_result_status must not be EnvelopeStatus\.SUCCESS"):
        ExitCodeScenario(
            name="invalid-success-verdict",
            command="modelo.work.verify",
            expected_exit_code=1,
            tool_result_status=EnvelopeStatus.SUCCESS,
            expected_next_action="modelo.reconcile.file",
        )


def test_runner_rejects_a_fabricated_continuation_command() -> None:
    """Anti-tautology: a next-action naming a non-existent command MUST fail.

    Proves the continuation check does not just string-match arbitrary prose -
    it requires the declared ``expected_next_action`` to resolve against the
    live CLI schema registry.
    """
    exit_code, envelope = _dispatch_m130_verify_with_cross_period_finding()

    scenario = ExitCodeScenario(
        name="m130-verify-fabricated-continuation",
        command="modelo.work.verify",
        expected_exit_code=1,
        tool_result_status=EnvelopeStatus.WARNING,
        expected_next_action="modelo.work.fabricated",
    )

    result = check_exit_code_scenario(
        scenario,
        exit_code=exit_code,
        envelope=envelope,
        valid_commands=valid_cli_commands(),
    )

    assert not result.passed
    assert not result.next_action_is_continuation
    assert any("does not resolve against the live CLI surface" in failure for failure in result.failures)
