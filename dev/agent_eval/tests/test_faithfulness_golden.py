"""Faithfulness gate wired end-to-end for the operator golden-task eval.

Guards against a hallucinated numeric - the load-bearing risk for regulated filing
narration,
since a plausible-looking but fabricated casilla value reads as authoritative
to an operator who cannot tell it apart from a real one.

This module dispatches a REAL ``modelo.work.calculate`` for M130 through the
actual CLI command handling (the identical transport
:func:`cadrumo_harness.mcp._dispatch.tool_request_argv` projects the
``cadrumo_modelo_work_calculate`` MCP tool call onto, mirroring
``test_response_provenance_golden.py``'s dispatch), seeds the exact
AEAT DR 130 Instrucciones worked-example inputs (ingresos 12.000, gastos 4.000)
so casilla 07 resolves to the same 1.600,00 EUR oracle figure
``test_modelo_130_value_oracle.py`` grounds, runs the real
``cadrumo_harness.mcp._faithfulness.faithfulness_check`` against real narration
text and the captured calculate JSON, and feeds the verdict into
:func:`dev.agent_eval._runner.run_golden_scenario` via its
``narration_faithfulness_checks`` parameter so the pass/fail composition itself
proves the two-part posture: advisory off the handoff path, hard block on it.

No mocks: every seeded row is a genuine ``TransactionCatalogueRepository``
write, every calculate value is what the real registry engine plus the real
CLI envelope serializer produced, and every faithfulness verdict is the real
regex-grounded check - not a hand-rolled boolean
(``aeat-quality-gates``, ``aeat-quality-gates``).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.core.bucket_pointer import resolve_active_bucket_id
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from cadrumo.domain.user_profile.loader import load_user_profile_schema
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from cadrumo.tests.cli_envelope import require_schema_envelope
from cadrumo.tests.cli_runner import invoke_cached_cli
from cadrumo.tests.profile_capsule import open_test_profile_session, seed_test_profile_record
from cadrumo.tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile
from cadrumo_harness.mcp import faithfulness_check

from .._models import NarrationFaithfulness
from .._runner import load_scenario, run_golden_scenario
from ._real_cli_support import create_m130_work_unit, valid_cli_commands

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "0ac1e000-0000-4000-8000-000000000097"
_SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"
_SCENARIO_PATH = _SCENARIOS_DIR / "modelo_130.toml"
_REVISION = "2019-y-siguientes"

# The SAME AEAT DR 130 Instrucciones worked example test_modelo_130_value_oracle.py
# grounds: ingresos 12.000, gastos 4.000 -> rendimiento neto 8.000 -> casilla 04 =
# 20 % x 8.000 = 1.600 -> casilla 07 = 1.600,00 EUR (IRPF Ley 35/2006 Art. 99,
# RD 439/2007 Art. 110). Real narration quoting this real figure must not be
# flagged - the false-positive proof this gate exists to close.
_GROUNDED_ORACLE_NARRATION = "La cuota del pago fraccionado (casilla 07) es de 1.600,00 EUR."
# A plausible but never-computed figure - absent from the captured tool JSON by
# construction, so a flag on it is a genuine detection, not a coincidence.
_FABRICATED_NARRATION = "La cuota del pago fraccionado (casilla 07) es de 4.242,17 EUR."


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """Real-session backend (real KEK/DEK, real SQLite per active bucket)."""
    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_PROFILE_ID,
        label="Faithfulness golden-eval test profile",
    ) as profile:
        yield profile


def _seed_natural_person_profile(runtime_profile: TestRuntimeProfile) -> None:
    """Seed a natural-person (IRPF estimacion directa) profile into the active bucket."""
    # Both identity fields come from the loaded schema rather than from
    # literals. The record pins each to exactly what the schema declares, so a
    # literal is a copy of the authority that goes stale the moment the schema
    # moves -- and reading them from one loaded object also keeps the pair
    # self-consistent, since two literals can drift into naming different
    # schemas.
    schema = load_user_profile_schema()
    record = UserProfileRecord(
        schema_id=schema.id,
        schema_version=schema.version,
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=(
            UserProfileFact(path="identity.name", value="Faithfulness Operator"),
            UserProfileFact(path="identity.surnames", value="Golden Eval"),
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="provenance.source", value="manual_cli"),
        ),
    )
    seed_test_profile_record(
        record,
        root=runtime_profile.storage_root,
        label="Faithfulness golden-eval test profile",
    )


def _seed_ledger_row(*, direction: TransactionDirection, amount: Decimal, filing_year: int, label: str) -> None:
    """Seed one real actividad-economica ledger row for a source-bound M130 casilla.

    Deliberately local to this module rather than importing across a test-module
    boundary, mirroring the established pattern in
    ``test_response_provenance_golden.py`` and ``test_exit_code_verdict_golden.py``.
    Writes a genuine row through the real ``TransactionCatalogueRepository``.
    """
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None, "test profile must install an active bucket pointer"
    value_date = date(filing_year, 2, 15)
    row = Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=f"faithfulness-{label}-{filing_year}",
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
                currency="EUR",
                counterparty="Contraparte SA",
                description=f"faithfulness golden eval {label}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256=("a" if direction == TransactionDirection.INCOMING else "b") * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=datetime(filing_year, 2, 16, 12, 0, tzinfo=UTC),
                    provider_name="manual-ledger",
                ),
                raw_fields={"source_kind": f"m130_faithfulness_{label}", "source_key": label},
            ),
            "direction": direction,
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
        transactions = (*tuple(existing.transactions.values()), row)
        TransactionCatalogueRepository(bucket_id=bucket_id).save(
            TransactionCatalogue.from_transactions(transactions),
        )


def _dispatch_real_m130_calculate_json(
    runtime_profile: TestRuntimeProfile,
    *,
    filing_year: int,
    period: str,
) -> str:
    """Dispatch a REAL ``modelo.work.calculate`` and return the raw stdout JSON text.

    Drives real command handling end to end (create work unit -> seed the AEAT
    DR 130 worked-example ledger rows -> calculate) - the same transport the
    ``cadrumo_modelo_work_calculate`` MCP tool dispatches to. Returns the raw JSON
    text (not the decoded mapping) because ``faithfulness_check`` grounds
    narration against the tool result's serialized JSON, exactly as the real
    ``PostToolUse`` hook receives it.
    """
    _seed_natural_person_profile(runtime_profile)
    work_unit_id = create_m130_work_unit(filing_year=filing_year, period=period, revision=_REVISION)
    _seed_ledger_row(
        direction=TransactionDirection.INCOMING,
        amount=Decimal("12000.00"),
        filing_year=filing_year,
        label="ingresos",
    )
    _seed_ledger_row(
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("4000.00"),
        filing_year=filing_year,
        label="gastos",
    )

    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "05=0.00",
            "--casilla", "06=0.00",
            "--binding", "irpf.previous_year_economic_activity_net_income=13000",
            "--binding", "modelo-130-resultados-negativos-anteriores=0",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    payload = require_schema_envelope(result.output)
    observations = payload["observations"]
    assert observations, "real M130 calculate response carried zero observations"
    casilla_07 = next(obs for obs in observations if obs["casilla_id"] == "07")
    assert Decimal(str(casilla_07["value"])) == Decimal("1600.00"), (
        f"fixture drift: expected the AEAT DR 130 worked-example figure 1600.00 for "
        f"casilla 07, got {casilla_07['value']!r} - the grounded-narration proof below "
        "depends on this exact figure"
    )
    return json.dumps(payload)


def test_fabricated_value_is_flagged_advisory_on_a_non_handoff_step(runtime_profile: TestRuntimeProfile) -> None:
    """A fabricated numeric in calculate-step narration is flagged but does not block.

    Advisory by default off the irreversible handoff path. Wires the real
    ``faithfulness_check`` verdict into ``run_golden_scenario`` at the
    ``modelo.work.calculate`` step and proves the scenario still passes overall -
    the flag is visible (``faithful=False``) but non-blocking (``blocks=False``).
    """
    tool_result_json = _dispatch_real_m130_calculate_json(
        runtime_profile,
        filing_year=2024,
        period="1T",
    )

    verdict = faithfulness_check(
        agent_text=_FABRICATED_NARRATION,
        tool_result_json=tool_result_json,
        blocking=False,
    )
    assert verdict.faithful is False
    assert verdict.blocking is False
    assert verdict.blocks is False
    assert any("4.242,17" in flagged for flagged in verdict.flagged_values)

    check = NarrationFaithfulness(
        step="modelo.work.calculate",
        faithful=verdict.faithful,
        blocking=verdict.blocking,
        flagged_values=verdict.flagged_values,
    )
    assert check.blocks is False

    scenario = load_scenario(_SCENARIO_PATH)
    result = run_golden_scenario(
        scenario,
        valid_commands=valid_cli_commands(),
        narration_faithfulness_checks=(check,),
    )

    assert result.passed, result.failures
    assert result.narration_faithfulness_checks == (check,)
    assert not result.narration_faithfulness_checks[0].faithful
    assert not result.narration_faithfulness_checks[0].blocks


def test_identical_fabricated_value_hard_blocks_on_the_export_handoff_step(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The SAME fabricated numeric on the export handoff step hard-blocks the scenario.

    Hard block at the export / record-marker boundary. Same narration
    text, same captured JSON, only ``blocking`` (the step) differs - proving the
    split is driven by step identity, not by the value itself.
    """
    tool_result_json = _dispatch_real_m130_calculate_json(
        runtime_profile,
        filing_year=2024,
        period="1T",
    )

    verdict = faithfulness_check(
        agent_text=_FABRICATED_NARRATION,
        tool_result_json=tool_result_json,
        blocking=True,
    )
    assert verdict.faithful is False
    assert verdict.blocking is True
    assert verdict.blocks is True

    check = NarrationFaithfulness(
        step="modelo.export",
        faithful=verdict.faithful,
        blocking=verdict.blocking,
        flagged_values=verdict.flagged_values,
    )
    assert check.blocks is True

    scenario = load_scenario(_SCENARIO_PATH)
    result = run_golden_scenario(
        scenario,
        valid_commands=valid_cli_commands(),
        narration_faithfulness_checks=(check,),
    )

    assert not result.passed
    assert any("hard-blocked" in failure and "modelo.export" in failure for failure in result.failures)


def test_grounded_oracle_figure_is_not_flagged_even_on_the_handoff_step(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Anti-false-positive proof: the REAL AEAT oracle figure is never flagged.

    Narration quoting the genuine casilla 07 value (1.600,00 EUR, the same AEAT
    DR 130 Instrucciones worked-example figure
    ``test_modelo_130_value_oracle.py`` grounds) must pass ``faithfulness_check``
    even at the export handoff step (``blocking=True``) - proving the check does
    not false-positive on a real, correctly-narrated value.
    """
    tool_result_json = _dispatch_real_m130_calculate_json(
        runtime_profile,
        filing_year=2024,
        period="1T",
    )

    verdict = faithfulness_check(
        agent_text=_GROUNDED_ORACLE_NARRATION,
        tool_result_json=tool_result_json,
        blocking=True,
    )
    assert verdict.faithful is True
    assert verdict.flagged_values == ()
    assert verdict.blocks is False

    check = NarrationFaithfulness(
        step="modelo.export",
        faithful=verdict.faithful,
        blocking=verdict.blocking,
        flagged_values=verdict.flagged_values,
    )

    scenario = load_scenario(_SCENARIO_PATH)
    result = run_golden_scenario(
        scenario,
        valid_commands=valid_cli_commands(),
        narration_faithfulness_checks=(check,),
    )

    assert result.passed, result.failures
    assert result.narration_faithfulness_checks[0].faithful


def test_narration_faithfulness_dimension_holds_trivially_when_not_checked() -> None:
    """No injected checks -> the dimension holds trivially, no other check regresses.

    ``run_golden_scenario`` never runs the faithfulness check itself (mirrors the
    ``response_observations`` injection pattern); this proves the new
    parameter's empty-tuple default does not silently fail every existing
    scenario run.
    """
    scenario = load_scenario(_SCENARIO_PATH)
    result = run_golden_scenario(scenario, valid_commands=valid_cli_commands())
    assert result.narration_faithfulness_checks == ()
    assert result.passed, result.failures
