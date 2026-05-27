"""Real-CLI tests: ledger verb validation-error paths (S13).

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
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.entrypoints.cli import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _create_profile_and_import(tmp_path: Path) -> str:
    """Provision a profile with one imported transaction; return transaction_id."""
    created = _RUNNER.invoke(
        app,
        [
            "config", "profile", "create", "tester", "--quiet",
            "--tax-id", "00000001R", "--activity", "freelance",
        ],
    )
    assert created.exit_code == 0, created.output

    statement = tmp_path / "statement.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,-50.00,EUR,n26-001\n",
        encoding="utf-8",
    )
    imported = _RUNNER.invoke(
        app, ["app", "ledger", "import", str(statement), "--provider", "csv"]
    )
    assert imported.exit_code == 0, imported.output

    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    rows = payload if isinstance(payload, list) else payload.get(
        "transactions", payload.get("rows", [])
    )
    assert rows, listed.output
    return rows[0]["transaction_id"]


# ---------------------------------------------------------------------------
# S13.1  ledger add — business_pct set without MIXED classification
# ---------------------------------------------------------------------------


def test_ledger_add_rejects_business_pct_on_non_mixed_classification(tmp_path: Path) -> None:
    """``ledger add`` must surface the field validator message when
    ``--business-pct`` is supplied alongside a non-MIXED classification.

    The ``ManualLedgerTransactionCommand._validate_business_percentage``
    validator raises "business_pct must be None unless classification is
    MIXED".  ``_ledger_validation_bad`` must route this through the CLI
    refusal rather than letting it bubble to the generic boundary."""

    _RUNNER.invoke(
        app,
        [
            "config", "profile", "create", "tester", "--quiet",
            "--tax-id", "00000001R", "--activity", "freelance",
        ],
    )

    result = _RUNNER.invoke(
        app,
        [
            "app", "ledger", "add",
            "--date", "2026-04-15",
            "--amount", "-50.00",
            "--direction", "OUTGOING",
            "--description", "office supplies",
            "--classification", "BUSINESS",
            "--business-pct", "0.75",
        ],
    )

    # CLI boundary converts the ValidationError; exit code must not be 0.
    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert "business_pct" in combined or "MIXED" in combined, combined


# ---------------------------------------------------------------------------
# S13.2  ledger update — patch with no fields (empty-patch validator)
# ---------------------------------------------------------------------------


def test_ledger_update_rejects_empty_patch(tmp_path: Path) -> None:
    """``ledger update`` called with only ``--id`` and no mutable options must
    surface the patch validator message "manual ledger patch must carry at
    least one field".

    The ``ManualLedgerTransactionPatch._require_change`` validator fires when
    no option besides the id is supplied.  The CLI must not crash silently."""

    txn_id = _create_profile_and_import(tmp_path)

    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "update", "--id", txn_id],
    )

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert "at least one field" in combined or "patch" in combined, combined


# ---------------------------------------------------------------------------
# S13.3  ledger allocate — business_pct out of range for MIXED
# ---------------------------------------------------------------------------


def test_ledger_allocate_rejects_out_of_range_business_pct(tmp_path: Path) -> None:
    """``ledger allocate`` with ``--business-pct 1.5`` exceeds the 0..1 bound.

    The ``ManualLedgerTransactionCommand._validate_business_percentage``
    validator raises "business_pct must be within 0..1 when classification is
    MIXED".  ``_ledger_validation_bad`` must extract and surface this."""

    txn_id = _create_profile_and_import(tmp_path)

    result = _RUNNER.invoke(
        app,
        [
            "app", "ledger", "allocate",
            "--id", txn_id,
            "--business-pct", "1.5",
        ],
    )

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert "business_pct" in combined or "0..1" in combined or "within" in combined, combined


# ---------------------------------------------------------------------------
# S13.4  ledger split — blank description on a child slice
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
            "app", "ledger", "split",
            "--id", txn_id,
            "--yes",
            "--child-amount", "-25.00",
            "--child-description", "   ",          # blank after strip
            "--child-amount", "-25.00",
            "--child-description", "valid slice",
        ],
    )

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert "description" in combined or "blank" in combined, combined


# ---------------------------------------------------------------------------
# S13.5  ledger classify — business_pct requires MIXED (pre-pydantic guard)
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
            "app", "ledger", "classify",
            "--id", txn_id,
            "--classification", "BUSINESS",
            "--business-pct", "0.5",
        ],
    )

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    # The guard surfaces a tr() refusal key; the English text contains
    # either "business_pct" or "MIXED".
    assert "business_pct" in combined or "MIXED" in combined or "mixed" in combined, combined


# ---------------------------------------------------------------------------
# S384  ledger add — profile-conditional source_jurisdiction (#258)
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
    """Set one profile axis via the diagnostics-app descriptor setter."""
    from aeat.diagnostics.__main__ import app as diagnostics_app

    result = _RUNNER.invoke(diagnostics_app, ["profile", "set", key, value])
    assert result.exit_code == 0, result.output


def test_ledger_add_defaults_source_jurisdiction_to_es_for_resident_general(
    tmp_path: Path,
) -> None:
    """RESIDENT_IRPF / GENERAL: omitted --source-jurisdiction silently defaults to ES.

    LIRPF Art. 8 universal-base presumption: residents are taxed on
    worldwide income with a Spanish-source default. The default-ES path
    must not require operator action."""

    _RUNNER.invoke(
        app,
        [
            "config", "profile", "create", "tester", "--quiet",
            "--tax-id", "00000001R", "--activity", "freelance",
        ],
    )
    # Default profile is already RESIDENT_IRPF / GENERAL — no diagnostics-set needed.

    result = _RUNNER.invoke(
        app,
        [
            "--format", "json",
            "app", "ledger", "add",
            "--date", "2026-04-15",
            "--amount", "-50.00",
            "--direction", "OUTGOING",
            "--description", "office supplies",
            # NO --source-jurisdiction
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["transaction"]["source_jurisdiction"] == "ES", payload


def test_ledger_add_refuses_when_source_jurisdiction_omitted_for_impatriado(
    tmp_path: Path,
) -> None:
    """RESIDENT_IRPF / IMPATRIADO: omitted --source-jurisdiction refused (Art. 93 LIRPF).

    The Beckham regime taxes Spanish-source income at the flat IRNR rate
    while excluding foreign-source from the base. A silent ES default
    would quietly include foreign-source amounts in the IRPF base —
    Art. 93.5 LIRPF segregation. Force operator to declare."""

    _RUNNER.invoke(
        app,
        [
            "config", "profile", "create", "tester", "--quiet",
            "--tax-id", "00000001R", "--activity", "freelance",
        ],
    )
    _set_profile_axis("irpf.special_regime", "impatriado")
    _set_profile_axis("irpf.special_regime_start_date", "2023-01-01")

    result = _RUNNER.invoke(
        app,
        [
            "app", "ledger", "add",
            "--date", "2026-04-15",
            "--amount", "-50.00",
            "--direction", "OUTGOING",
            "--description", "consulting",
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
    because the IRNR base only admits Spanish-source income."""

    _RUNNER.invoke(
        app,
        [
            "config", "profile", "create", "tester", "--quiet",
            "--tax-id", "00000001R", "--activity", "freelance",
        ],
    )
    _set_profile_axis("taxpayer_type.fiscal_residency", "non_resident_irnr")
    # TRLIRNR Art. 10 requires representante fiscal NIF + nombre for non-EU/EEA
    # residents; the TaxpayerProfile model-validator refuses the projection if
    # the axis tuple is partial, which would mask the source-jurisdiction
    # refusal under a generic validation error. Provision the full IRNR tuple
    # (Argentina is non-EU/EEA so the representante is mandatory).
    _set_profile_axis("taxpayer_type.country_of_fiscal_residence", "AR")
    _set_profile_axis("taxpayer_type.representante_fiscal_nif", "12345678Z")
    _set_profile_axis("taxpayer_type.representante_fiscal_nombre", "Test Representante")

    result = _RUNNER.invoke(
        app,
        [
            "app", "ledger", "add",
            "--date", "2026-04-15",
            "--amount", "-50.00",
            "--direction", "OUTGOING",
            "--description", "non-resident expense",
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

    _RUNNER.invoke(
        app,
        [
            "config", "profile", "create", "tester", "--quiet",
            "--tax-id", "00000001R", "--activity", "freelance",
        ],
    )

    result = _RUNNER.invoke(
        app,
        [
            "--format", "json",
            "app", "ledger", "add",
            "--date", "2026-04-15",
            "--amount", "100.00",
            "--direction", "INCOMING",
            "--description", "foreign dividend",
            "--source-jurisdiction", "FR",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["transaction"]["source_jurisdiction"] == "FR", payload
