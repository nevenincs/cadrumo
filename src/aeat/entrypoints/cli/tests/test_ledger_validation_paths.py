"""Real-CLI tests: ledger verb validation-error paths (contract).

Each verb that wraps command construction in a try/except ValidationError
must surface the pydantic field message through ``_ledger_validation_bad``
rather than letting the generic boundary swallow it as an opaque
"config repair" hint.  One test per verb; each drives a combination of
flags that trips a model_validator rule and asserts the field name or
message fragment appears in stderr/output.

Verbs covered: add, update, allocate, split, classify.
ledger_list and ledger_view do not construct pydantic models from operator
flags and therefore have no ValidationError path to exercise here.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.user_profile._orchestration import profile_create_storage_span, set_active_fields
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.config import override_settings
from ....domain.user_profile import UserProfileFact
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RUNNER = CliRunner()

#: Profile id every test in this module creates via the CLI inside the span.
_PROFILE_ID = "tester"


@pytest.fixture(autouse=True)
def _open_bucket_session(tmp_path: Path) -> Iterator[None]:
    """Hold an active bucket session open across this module's in-process invokes.

    The active bucket session is a per-process/per-context ContextVar opened by
    the storage master-key provider. The profile id is now an immutable bucket
    id distinct from the display label, so these tests seed the real profile
    record under the same id as the held storage span rather than creating a
    UUID-backed profile via a separate in-process CLI invoke.
    """
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_PROFILE_ID),
    ):
        workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id=_PROFILE_ID))
        try:
            yield
        finally:
            dispose_engine()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _create_profile_and_import(tmp_path: Path) -> str:
    """Provision a profile with one imported transaction; return transaction_id."""
    statement = tmp_path / "statement.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,-50.00,EUR,n26-001\n",
        encoding="utf-8",
    )
    imported = _RUNNER.invoke(app, ["app", "ledger", "import", str(statement), "--provider", "csv"])
    assert imported.exit_code == 0, imported.output

    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    rows = payload.get("result", payload).get("rows", [])
    assert rows, listed.output
    return rows[0]["transaction_id"]


# ---------------------------------------------------------------------------
# contract.1  ledger add — business_pct set without MIXED classification
# ---------------------------------------------------------------------------


def test_ledger_add_rejects_business_pct_on_non_mixed_classification(tmp_path: Path) -> None:
    """``ledger add`` must surface the field validator message when
    ``--business-pct`` is supplied alongside a non-MIXED classification.

    The ``ManualLedgerTransactionCommand._validate_business_percentage``
    validator raises "business_pct must be None unless classification is
    MIXED".  ``_ledger_validation_bad`` must route this through the CLI
    refusal rather than letting it bubble to the generic boundary."""

    result = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "50.00",
            "--direction",
            "OUTGOING",
            "--description",
            "office supplies",
            "--classification",
            "BUSINESS",
            "--business-pct",
            "0.75",
        ],
    )

    # CLI boundary converts the ValidationError; exit code must not be 0.
    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert "business_pct" in combined or "MIXED" in combined, combined


def test_ledger_add_rejects_negative_amount_with_instructive_error(tmp_path: Path) -> None:
    """``ledger add --amount=-49.99`` is refused with an instructive, localised error.

    Flow is carried by ``--direction``, not by the sign of the amount. The CLI
    boundary refuses a negative magnitude and the error names the accepted form
    (a non-negative amount plus ``--direction``), per the
    ``aeat-architecture-boundaries`` instructive-refusal rule — never a bare
    "value invalid".
    """
    result = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "-49.99",
            "--direction",
            "OUTGOING",
            "--description",
            "office supplies",
        ],
    )
    assert result.exit_code != 0, result.output
    combined = result.output or ""
    # Instructive: names the accepted non-negative form and the --direction axis.
    assert "non-negative magnitude" in combined, combined
    assert "--direction" in combined, combined


def test_ledger_add_gross_mismatch_surfaces_clean_refusal_not_pydantic_repr(
    tmp_path: Path,
) -> None:
    """``ledger add`` with ``taxable_base + iva_amount != amount`` surfaces a
    one-line typed refusal — never the raw ``RawTransaction(...)`` pydantic repr.

    The gross-invariant validator (``Transaction._enforce_gross_equals_base_plus_iva``)
    fires inside ``create_manual_transaction``, *after* the
    ``ManualLedgerTransactionCommand`` construction. Before the fix the leaked
    ``pydantic.ValidationError`` reached the generic CLI boundary, dumping the
    whole ``RawTransaction(...)`` repr (~30 lines). The CLI handler must catch it
    and route the human-readable validator message through ``_ledger_validation_bad``.
    """
    result = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "121.00",
            "--direction",
            "OUTGOING",
            "--description",
            "office supplies",
            "--classification",
            "BUSINESS",
            "--category-id",
            "material_oficina",
            "--taxable-base",
            "100.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "50.00",
        ],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    # The clean validator message is surfaced (Click's Rich box may wrap the
    # line at the box border, so assert on a fragment that stays on one line).
    assert "iva_amount must equal the gross to the cent" in combined, combined
    # ... and the raw pydantic model repr is NOT dumped to the operator.
    assert "RawTransaction(" not in combined, combined
    assert "RawProvenance(" not in combined, combined
    assert "mappingproxy(" not in combined, combined


def test_ledger_add_accepts_nonnegative_amount_with_direction(tmp_path: Path) -> None:
    """``ledger add --amount=49.99 --direction OUTGOING`` is accepted."""
    result = _RUNNER.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "49.99",
            "--direction",
            "OUTGOING",
            "--description",
            "office supplies",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["transaction"]["amount"] == "49.99"
    assert payload["transaction"]["direction"] == "OUTGOING"


# ---------------------------------------------------------------------------
# contract.2  ledger update — patch with no fields (empty-patch validator)
# ---------------------------------------------------------------------------


def test_ledger_update_rejects_empty_patch(tmp_path: Path) -> None:
    """``ledger update`` called with only the positional id and no mutable options must
    surface the patch validator message "manual ledger patch must carry at
    least one field".

    The ``ManualLedgerTransactionPatch._require_change`` validator fires when
    no option besides the id is supplied.  The CLI must not crash silently."""

    txn_id = _create_profile_and_import(tmp_path)

    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "update", txn_id],
    )

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert "at least one field" in combined or "patch" in combined, combined


def test_ledger_update_rejects_negative_amount_with_instructive_error(tmp_path: Path) -> None:
    """``ledger update --amount=-49.99`` is refused at the CLI magnitude boundary."""

    txn_id = _create_profile_and_import(tmp_path)

    result = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "update",
            txn_id,
            "--amount",
            "-49.99",
        ],
    )

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert "non-negative magnitude" in combined, combined
    assert "--direction" in combined, combined


# ---------------------------------------------------------------------------
# contract.3  ledger allocate — business_pct out of range for MIXED
# ---------------------------------------------------------------------------


def test_ledger_allocate_rejects_out_of_range_business_pct(tmp_path: Path) -> None:
    """``ledger allocate`` with ``--business-pct 1.5`` exceeds the 0..1 bound.

    The CLI boundary refuses the out-of-range share before the backend and
    surfaces the offending value WITH its percent context, so the operator
    is steered to the 0..1 share convention rather than seeing a bare
    'invalid'."""

    txn_id = _create_profile_and_import(tmp_path)

    result = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "allocate",
            txn_id,
            "--business-pct",
            "1.5",
        ],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    # The offending value and its percent translation both appear.
    assert "1.5" in combined and "150%" in combined, combined
    assert "0.5 for 50" in combined, combined


# ---------------------------------------------------------------------------
# contract.4  ledger split — blank description on a child slice
# ---------------------------------------------------------------------------


def test_ledger_split_rejects_blank_child_description(tmp_path: Path) -> None:
    """``ledger split`` with a blank ``--child-description`` must surface the
    ``SplitChildCommand`` field validator message.

    The ``SplitChildCommand._trim_description`` validator raises
    "description must not be blank".  ``_ledger_validation_bad`` wraps it
    via the pydantic ``ValidationError`` caught in the split handler."""

    txn_id = _create_profile_and_import(tmp_path)

    result = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "split",
            txn_id,
            "--yes",
            "--child-amount",
            "-25.00",
            "--child-description",
            "   ",  # blank after strip
            "--child-amount",
            "-25.00",
            "--child-description",
            "valid slice",
        ],
    )

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert "description" in combined or "blank" in combined, combined


# ---------------------------------------------------------------------------
# contract.5  ledger classify — business_pct requires MIXED (pre-pydantic guard)
# ---------------------------------------------------------------------------


def test_ledger_classify_rejects_business_pct_without_mixed_classification(
    tmp_path: Path,
) -> None:
    """``ledger classify`` refuses ``--business-pct`` when classification is
    not MIXED.

    The CLI handler applies an explicit pre-pydantic guard (lines 514-518 of
    ``_ledger.py``) that raises ``_bad(tr(...))`` before constructing the
    patch model.  The refusal must be user-facing prose, not a pydantic
    traceback, and must mention MIXED or business_pct."""

    txn_id = _create_profile_and_import(tmp_path)

    result = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "classify",
            txn_id,
            "--classification",
            "BUSINESS",
            "--business-pct",
            "0.5",
        ],
    )

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    # The guard surfaces a tr() refusal key; the English text contains
    # either "business_pct" or "MIXED".
    assert "business_pct" in combined or "MIXED" in combined or "mixed" in combined, combined


# ---------------------------------------------------------------------------
# contract  ledger add — profile-conditional source_jurisdiction (#258)
#
# Truth table per the regulatory branching:
#   - LIRPF Art. 8 (universal-base presumption): resident IRPF GENERAL
#     profiles silently default omitted --source-jurisdiction to ES.
#   - LIRPF Art. 93 (Beckham): impatriado profiles must declare the
#     jurisdiction explicitly; silent ES would mask foreign-source
#     income that the regime treats separately from Spanish-source.
#   - TRLIRNR Art. 2 / Art. 10: non-residents file IRNR and must
#     declare jurisdiction explicitly so the IRNR scope filter has
#     authoritative provenance per transaction.
# ---------------------------------------------------------------------------


def _set_profile_axis(key: str, value: str) -> None:
    """Set one profile axis through the canonical profile orchestration service."""
    workflow_state_repository().update(
        lambda state: set_active_fields(state, (UserProfileFact(path=key, value=value),)),
    )


def test_ledger_add_defaults_source_jurisdiction_to_es_for_resident_general(
    tmp_path: Path,
) -> None:
    """RESIDENT_IRPF / GENERAL: omitted --source-jurisdiction silently defaults to ES.

    LIRPF Art. 8 universal-base presumption: residents are taxed on
    worldwide income with a Spanish-source default. The default-ES path
    must not require operator action."""

    # Default profile is already RESIDENT_IRPF / GENERAL, so no fact mutation is needed.

    result = _RUNNER.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "50.00",
            "--direction",
            "OUTGOING",
            "--description",
            "office supplies",
            # NO --source-jurisdiction
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["transaction"]["source_jurisdiction"] == "ES", payload


def test_ledger_add_refuses_when_source_jurisdiction_omitted_for_impatriado(
    tmp_path: Path,
) -> None:
    """RESIDENT_IRPF / IMPATRIADO: omitted --source-jurisdiction refused (Art. 93 LIRPF).

    The Beckham regime taxes Spanish-source income at the flat IRNR rate
    while excluding foreign-source from the base. A silent ES default
    would quietly include foreign-source amounts in the IRPF base —
    Art. 93.5 LIRPF segregation. Force operator to declare.

    The test mutates the profile through the canonical profile orchestration
    service so the ledger command sees the same stored facts it would read
    after the operator wizard updates the active profile."""

    _set_profile_axis("irpf.special_regime", "impatriado")
    _set_profile_axis("irpf.special_regime_start_date", "2023-01-01")

    result = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "50.00",
            "--direction",
            "OUTGOING",
            "--description",
            "consulting",
            # NO --source-jurisdiction
        ],
    )
    assert result.exit_code != 0, result.output
    combined = result.output or ""
    # The refusal key carries Beckham / Art. 93 anchoring.
    assert (
        "source-jurisdiction" in combined
        or "source_jurisdiction" in combined
        or "Beckham" in combined
        or "Art" in combined
        or "93" in combined
    ), combined


def test_ledger_add_refuses_when_source_jurisdiction_omitted_for_non_resident(
    tmp_path: Path,
) -> None:
    """NON_RESIDENT_IRNR: omitted --source-jurisdiction refused (TRLIRNR Art. 2/10).

    Non-residents file IRNR under RDLeg 5/2004; per-row jurisdiction is
    the authoritative provenance for the IRNR scope filter. Operator
    must declare it on every ledger entry — no silent default is safe
    because the IRNR base only admits Spanish-source income.

    The test mutates the profile through the canonical profile orchestration
    service so the ledger command sees the same stored facts it would read
    after the operator wizard updates the active profile."""

    _set_profile_axis("taxpayer_type.fiscal_residency", "non_resident_irnr")
    # UE/EEE country chosen so ue_eee_status is True and the
    # TaxpayerProfile _check_representante_fiscal_required validator does
    # not fire; this lets the source-jurisdiction refusal surface cleanly
    # without provisioning the full TRLIRNR Art. 10 representante tuple.
    # The non-EU/EEA path (Argentina, Morocco) is tracked under the schema-
    # fix follow-up that resolves the representante_fiscal_nombre catalogue gap.
    _set_profile_axis("taxpayer_type.country_of_fiscal_residence", "FR")

    result = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "50.00",
            "--direction",
            "OUTGOING",
            "--description",
            "non-resident expense",
            # NO --source-jurisdiction
        ],
    )
    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert (
        "source-jurisdiction" in combined
        or "source_jurisdiction" in combined
        or "IRNR" in combined
        or "TRLIRNR" in combined
    ), combined


def test_ledger_add_honours_operator_source_jurisdiction_override_for_resident(
    tmp_path: Path,
) -> None:
    """Operator-supplied --source-jurisdiction is preserved verbatim regardless of profile.

    Resident IRPF / GENERAL operator may legitimately add a foreign-source
    row (e.g. dividendos de fuente extranjera). The default-ES rule must
    not override an explicit operator value."""

    result = _RUNNER.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "100.00",
            "--direction",
            "INCOMING",
            "--description",
            "foreign dividend",
            "--source-jurisdiction",
            "FR",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["transaction"]["source_jurisdiction"] == "FR", payload


# ---------------------------------------------------------------------------
# contract  documented mixed-use flow reaches preflight-ready
#
# A MIXED row needs a proportionality reference (``usage_ratio_id``) to pass
# preflight; ``--business-pct`` alone leaves it un-ready with reason
# ``missing_proportionality_reference``. The documented working path is:
#   ledger ratios set <category-id> <ratio>
#   ledger allocate <tx> --business-pct <ratio> --usage-ratio-id <category-id> \
#       --category-id <category-id>
# ``--usage-ratio-id`` lives on ``allocate`` (and ``add``), not on ``classify``,
# and its value is the spending-category id.
# ---------------------------------------------------------------------------


def _add_eligible_mixed_expense() -> str:
    """Add one deductible-expense row in a usage-ratio-eligible category.

    ``telefonia_movil`` is a ``USAGE_RATIO_PERSONAL`` category — eligible for a
    saved usage ratio — so the documented mixed-use flow applies to it. The row
    carries consistent IVA facts so the only outstanding preflight finding is
    the proportionality reference.
    """
    result = _RUNNER.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-02-10",
            "--amount",
            "60.50",
            "--direction",
            "OUTGOING",
            "--description",
            "phone bill",
            "--taxable-base",
            "50.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "10.50",
        ],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["result"]["transaction_id"]


def test_mixed_row_with_business_pct_alone_is_not_preflight_ready(tmp_path: Path) -> None:
    """A MIXED row classified with ``--business-pct`` alone fails preflight.

    Preflight reports ``missing_proportionality_reference`` because the row has
    no ``usage_ratio_id``. This pins the design the doc must describe: a bare
    percentage is not enough for a MIXED row to be ready.
    """
    txn_id = _add_eligible_mixed_expense()

    classified = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "classify",
            txn_id,
            "--classification",
            "MIXED",
            "--business-pct",
            "0.5",
            "--category-id",
            "telefonia_movil",
        ],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )
    assert classified.exit_code == 0, classified.output

    preflight = _RUNNER.invoke(
        app,
        ["app", "ledger", "preflight", "--year", "2026", "--period", "1T"],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )
    assert preflight.exit_code == 0, preflight.output
    assert "ready\tfalse" in preflight.output, preflight.output
    assert "missing_proportionality_reference" in preflight.output, preflight.output


def test_documented_mixed_use_flow_reaches_preflight_ready(tmp_path: Path) -> None:
    """The documented ratios-set + allocate flow makes a MIXED row preflight-ready.

    Mirrors the corrected ``docs/how-to/classify-transactions.md`` mixed-use
    steps end to end: save a category ratio, then allocate the row naming the
    same category id for both ``--usage-ratio-id`` and ``--category-id``.
    Preflight must then report zero issues and ready=true.
    """
    txn_id = _add_eligible_mixed_expense()

    ratios_set = _RUNNER.invoke(
        app,
        ["app", "ledger", "ratios", "set", "telefonia_movil", "0.5"],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )
    assert ratios_set.exit_code == 0, ratios_set.output

    allocate = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "allocate",
            txn_id,
            "--business-pct",
            "0.5",
            "--usage-ratio-id",
            "telefonia_movil",
            "--category-id",
            "telefonia_movil",
        ],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )
    assert allocate.exit_code == 0, allocate.output

    preflight = _RUNNER.invoke(
        app,
        ["app", "ledger", "preflight", "--year", "2026", "--period", "1T"],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )
    assert preflight.exit_code == 0, preflight.output
    assert "issues\t0" in preflight.output, preflight.output
    assert "ready\ttrue" in preflight.output, preflight.output


# ---------------------------------------------------------------------------
# contract  operator surfaces refuse pipeline-managed classification states
#
# BUSINESS / PERSONAL / MIXED are the only operator-assignable classifications.
# NOT_YET_PROCESSED / PROCESSED_UNCLASSIFIED / SKIPPED_BY_RULE / FAILED_VALIDATION
# are produced by the pipeline (rule apply, LLM, validation) and MUST NOT be
# assignable by hand through ``add`` or ``classify``. The doc states this
# contract ("others are set automatically by aeat"); these tests pin it.
# ---------------------------------------------------------------------------


def _flatten_box(text: str) -> str:
    """Collapse a Rich error box into a single line so a wrapped phrase matches.

    Rich word-wraps the message across box rows and inserts ``│`` borders, so a
    multi-word fragment is split. Strip the borders and collapse whitespace.
    """
    return " ".join(text.replace("│", " ").split())


@pytest.mark.parametrize("system_state", ["SKIPPED_BY_RULE", "FAILED_VALIDATION", "PROCESSED_UNCLASSIFIED"])
def test_ledger_classify_refuses_pipeline_managed_state(tmp_path: Path, system_state: str) -> None:
    """``ledger classify`` refuses a pipeline-managed state with an instructive error."""
    txn_id = _add_eligible_mixed_expense()

    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "classify", txn_id, "--classification", system_state],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )

    assert result.exit_code != 0, result.output
    flat = _flatten_box(result.output or "")
    assert "set automatically by aeat" in flat, result.output
    assert "BUSINESS, PERSONAL, MIXED" in flat, result.output


@pytest.mark.parametrize("system_state", ["SKIPPED_BY_RULE", "FAILED_VALIDATION", "PROCESSED_UNCLASSIFIED"])
def test_ledger_add_refuses_pipeline_managed_state(tmp_path: Path, system_state: str) -> None:
    """``ledger add --classification <system state>`` is refused instructively."""
    result = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "50.00",
            "--direction",
            "OUTGOING",
            "--description",
            "office supplies",
            "--classification",
            system_state,
        ],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )

    assert result.exit_code != 0, result.output
    flat = _flatten_box(result.output or "")
    assert "set automatically by aeat" in flat, result.output


def test_ledger_add_default_classification_is_accepted(tmp_path: Path) -> None:
    """``ledger add`` with no ``--classification`` keeps the NOT_YET_PROCESSED default.

    The pipeline-managed guard must not refuse the import default; only the three
    truly-internal states (PROCESSED_UNCLASSIFIED / SKIPPED_BY_RULE /
    FAILED_VALIDATION) are blocked.
    """
    result = _RUNNER.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "50.00",
            "--direction",
            "OUTGOING",
            "--description",
            "office supplies",
        ],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["transaction"]["business_classification"] == "NOT_YET_PROCESSED", payload
