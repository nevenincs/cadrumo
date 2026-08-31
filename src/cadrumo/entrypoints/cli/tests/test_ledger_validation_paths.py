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
from pathlib import Path

import pytest
from click.testing import Result

from ._ledger_validation_fixtures import _open_bucket_session, bucket
from ._ledger_validation_support import (
    _add_eligible_mixed_expense,
    _assert_pipeline_managed_state_refusal,
    _flatten_box,
    _invoke,
    import_validation_transaction,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _assert_negative_amount_refusal(result: Result) -> None:
    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert "non-negative magnitude" in combined, combined
    assert "--direction" in combined, combined


__all__ = ["_open_bucket_session", "bucket"]

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

    result = _invoke(
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
    result = _invoke(
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
    # Instructive: names the accepted non-negative form and the --direction axis.
    _assert_negative_amount_refusal(result)


def test_ledger_add_gross_mismatch_surfaces_clean_refusal_not_pydantic_repr(
    tmp_path: Path,
) -> None:
    """``ledger add`` with ``taxable_base + iva_amount != amount`` surfaces a
    one-line typed refusal — never the raw ``RawTransaction(...)`` pydantic repr.

    The gross-invariant validator
    (``Transaction._enforce_gross_equals_base_plus_iva_plus_recargo``)
    fires inside ``create_manual_transaction``, *after* the
    ``ManualLedgerTransactionCommand`` construction. Before the fix the leaked
    ``pydantic.ValidationError`` reached the generic CLI boundary, dumping the
    whole ``RawTransaction(...)`` repr (~30 lines). The CLI handler must catch it
    and route the human-readable validator message through ``_ledger_validation_bad``.
    """
    result = _invoke(
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
        env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
    )

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    # The clean validator message is surfaced (Click's Rich box may wrap the
    # line at the box border, so assert on a fragment that stays on one line).
    assert "taxable_base + iva_amount + recargo_amount must equal the gross to the cent" in combined, combined
    # ... and the raw pydantic model repr is NOT dumped to the operator.
    assert "RawTransaction(" not in combined, combined
    assert "RawProvenance(" not in combined, combined
    assert "mappingproxy(" not in combined, combined


def test_ledger_add_gross_mismatch_above_substrate_hints_recargo_amount(
    tmp_path: Path,
) -> None:
    """A cash movement above the declared base+IVA substrate, with no recargo
    recorded, must hint ``--recargo-amount`` rather than a bare arithmetic
    mismatch.

    ``_gross_mismatch_detail`` (``domain/transactions/models.py``) names the
    one field that would legitimately explain this direction of the gap: a
    supply to or from a comerciante minorista under recargo de equivalencia
    (LIVA art. 161) charges the surcharge on top of the cuota, so the cash the
    operator recorded can legitimately exceed base+IVA alone.
    """
    result = _invoke(
        [
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "150.00",
            "--direction",
            "OUTGOING",
            "--description",
            "supplier purchase",
            "--classification",
            "BUSINESS",
            "--category-id",
            "material_oficina",
            "--taxable-base",
            "100.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "21.00",
        ],
        env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
    )

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert "taxable_base + iva_amount + recargo_amount must equal the gross to the cent" in combined, combined
    assert "--recargo-amount" in combined, combined
    assert "recargo de equivalencia" in combined, combined


def test_ledger_classify_persists_professional_income_net_of_irpf_withholding(
    tmp_path: Path,
) -> None:
    """A net bank receipt can still carry the invoice base and IVA facts.

    Persona repro: professional invoice 2000 + 420 IVA, 300 IRPF withheld,
    bank receipt 2120. The operator first records the bank movement and then
    classifies it with the invoice substrate. The production CLI path must
    persist those facts so Modelo 303 and Renta aggregation can read them.
    """
    added = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2025-07-15",
            "--amount",
            "2120.00",
            "--direction",
            "INCOMING",
            "--description",
            "Factura profesional neta de retencion",
        ],
    )
    assert added.exit_code == 0, added.output
    transaction_id = json.loads(added.output)["result"]["transaction_id"]

    classified = _invoke(
        [
            "app",
            "ledger",
            "classify",
            transaction_id,
            "--classification",
            "BUSINESS",
            "--taxable-base",
            "2000.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "420.00",
            "--irpf-category",
            "actividad_economica",
        ],
        env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
    )
    assert classified.exit_code == 0, classified.output

    viewed = _invoke(["--format", "json", "app", "ledger", "view", transaction_id])
    assert viewed.exit_code == 0, viewed.output
    transaction = json.loads(viewed.output)["result"]["transaction"]

    assert transaction["amount"] == "2120"
    assert transaction["taxable_base"] == "2000"
    assert transaction["iva_amount"] == "420"
    assert transaction["iva_rate"] == "0.21"
    assert transaction["irpf_category"] == "actividad_economica"


def test_ledger_classify_refuses_activity_income_when_base_cash_would_be_iva_sized_withholding(
    tmp_path: Path,
) -> None:
    """A base-only professional cash receipt must not persist as IVA-sized retencion."""
    added = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2025-07-15",
            "--amount",
            "2000.00",
            "--direction",
            "INCOMING",
            "--description",
            "Factura profesional introducida por base",
        ],
    )
    assert added.exit_code == 0, added.output
    transaction_id = json.loads(added.output)["result"]["transaction_id"]

    classified = _invoke(
        [
            "app",
            "ledger",
            "classify",
            transaction_id,
            "--classification",
            "BUSINESS",
            "--taxable-base",
            "2000.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "420.00",
            "--irpf-category",
            "actividad_economica",
        ],
        env={"CADRUMO_OUTPUT_LANGUAGE": "en", "COLUMNS": "120"},
    )

    assert classified.exit_code != 0
    assert "inferred IRPF withholding exceeds" in classified.output


def test_ledger_classify_persists_professional_service_paid_net_of_irpf_withholding(
    tmp_path: Path,
) -> None:
    """A professional-service bank payment can keep supplier invoice facts.

    Javier repro: 1000.00 + 210.00 IVA - 150.00 IRPF withholding = 1060.00
    paid. The CLI path must not rewrite cash to 1210.00 and must persist the
    category axes that explain the net payment.
    """
    added = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2025-07-15",
            "--amount",
            "1060.00",
            "--direction",
            "OUTGOING",
            "--description",
            "Factura asesoria fiscal neta de retencion",
        ],
    )
    assert added.exit_code == 0, added.output
    transaction_id = json.loads(added.output)["result"]["transaction_id"]

    classified = _invoke(
        [
            "app",
            "ledger",
            "classify",
            transaction_id,
            "--classification",
            "BUSINESS",
            "--category-id",
            "asesoria_fiscal",
            "--taxable-base",
            "1000.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "210.00",
            "--iva-category",
            "domestic_general",
            "--irpf-category",
            "actividad_economica",
            "--actor",
            "Javier",
        ],
        env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
    )
    assert classified.exit_code == 0, classified.output

    viewed = _invoke(["--format", "json", "app", "ledger", "view", transaction_id])
    assert viewed.exit_code == 0, viewed.output
    transaction = json.loads(viewed.output)["result"]["transaction"]

    assert transaction["amount"] == "1060"
    assert transaction["direction"] == "OUTGOING"
    assert transaction["category_id"] == "asesoria_fiscal"
    assert transaction["taxable_base"] == "1000"
    assert transaction["iva_amount"] == "210"
    assert transaction["iva_rate"] == "0.21"
    assert transaction["iva_category"] == "domestic_general"
    assert transaction["irpf_category"] == "actividad_economica"


def test_ledger_classify_persists_rent_paid_net_of_withholding(
    tmp_path: Path,
) -> None:
    """A rent bank payment net of withholding can keep full invoice IVA facts.

    Persona repro: commercial rent 2700 + 567 IVA - 513 withholding = 2754 paid.
    The CLI path must persist the full rent invoice substrate so Modelo 303 can
    aggregate the 567 IVA soportado instead of rejecting the row at classify time.
    """
    added = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2025-04-05",
            "--amount",
            "2754.00",
            "--direction",
            "OUTGOING",
            "--description",
            "Alquiler local neto de retencion",
        ],
    )
    assert added.exit_code == 0, added.output
    transaction_id = json.loads(added.output)["result"]["transaction_id"]

    classified = _invoke(
        [
            "app",
            "ledger",
            "classify",
            transaction_id,
            "--classification",
            "BUSINESS",
            "--category-id",
            "arrendamiento_local",
            "--taxable-base",
            "2700.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "567.00",
            "--iva-category",
            "domestic_general",
            "--irpf-category",
            "arrendamiento_local",
            "--actor",
            "Javier",
        ],
        env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
    )
    assert classified.exit_code == 0, classified.output

    viewed = _invoke(["--format", "json", "app", "ledger", "view", transaction_id])
    assert viewed.exit_code == 0, viewed.output
    transaction = json.loads(viewed.output)["result"]["transaction"]

    assert transaction["amount"] == "2754"
    assert transaction["direction"] == "OUTGOING"
    assert transaction["category_id"] == "arrendamiento_local"
    assert transaction["taxable_base"] == "2700"
    assert transaction["iva_amount"] == "567"
    assert transaction["iva_rate"] == "0.21"
    assert transaction["iva_category"] == "domestic_general"
    assert transaction["irpf_category"] == "arrendamiento_local"


def test_ledger_classify_rent_net_withholding_refusal_names_accepted_irpf_ids(
    tmp_path: Path,
) -> None:
    """A guessed rent withholding id is refused with discoverable accepted ids."""
    added = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2025-04-05",
            "--amount",
            "2754.00",
            "--direction",
            "OUTGOING",
            "--description",
            "Alquiler local neto de retencion",
        ],
    )
    assert added.exit_code == 0, added.output
    transaction_id = json.loads(added.output)["result"]["transaction_id"]

    classified = _invoke(
        [
            "app",
            "ledger",
            "classify",
            transaction_id,
            "--classification",
            "BUSINESS",
            "--category-id",
            "arrendamiento_local",
            "--taxable-base",
            "2700.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "567.00",
            "--iva-category",
            "domestic_general",
            "--irpf-category",
            "rental_withholding",
        ],
        env={"CADRUMO_OUTPUT_LANGUAGE": "en", "COLUMNS": "160"},
    )

    assert classified.exit_code != 0
    flat = " ".join(classified.output.split())
    assert "arrendamiento_local" in flat
    assert "arrendamiento_vivienda_afecto" in flat
    assert "aeat app ledger categories" in flat


def test_ledger_add_accepts_nonnegative_amount_with_direction(tmp_path: Path) -> None:
    """``ledger add --amount=49.99 --direction OUTGOING`` is accepted."""
    result = _invoke(
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

    txn_id = import_validation_transaction(tmp_path)

    result = _invoke(
        ["app", "ledger", "update", txn_id],
    )

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert "at least one field" in combined or "patch" in combined, combined


def test_ledger_update_rejects_negative_amount_with_instructive_error(tmp_path: Path) -> None:
    """``ledger update --amount=-49.99`` is refused at the CLI magnitude boundary."""

    txn_id = import_validation_transaction(tmp_path)

    result = _invoke(
        [
            "app",
            "ledger",
            "update",
            txn_id,
            "--amount",
            "-49.99",
        ],
    )

    _assert_negative_amount_refusal(result)


# ---------------------------------------------------------------------------
# contract.3  ledger allocate — business_pct out of range for MIXED
# ---------------------------------------------------------------------------


def test_ledger_allocate_rejects_out_of_range_business_pct(tmp_path: Path) -> None:
    """``ledger allocate`` with ``--business-pct 1.5`` exceeds the 0..1 bound.

    The CLI boundary refuses the out-of-range share before the backend and
    surfaces the offending value WITH its percent context, so the operator
    is steered to the 0..1 share convention rather than seeing a bare
    'invalid'."""

    txn_id = import_validation_transaction(tmp_path)

    result = _invoke(
        [
            "app",
            "ledger",
            "allocate",
            txn_id,
            "--business-pct",
            "1.5",
        ],
        env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
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

    txn_id = import_validation_transaction(tmp_path)

    result = _invoke(
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
    assert "description must not be blank" in combined, combined
    assert "transaction is invalid" in combined.lower(), combined


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

    txn_id = import_validation_transaction(tmp_path)

    result = _invoke(
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


def test_usage_ratio_help_points_to_configured_ratio_commands(tmp_path: Path) -> None:
    """`--usage-ratio-id` help names the configured-ratio discovery path."""

    for args in (
        ["app", "ledger", "add", "--help"],
        ["app", "ledger", "allocate", "--help"],
    ):
        result = _invoke(args, env={"CADRUMO_OUTPUT_LANGUAGE": "en", "COLUMNS": "260"})

        assert result.exit_code == 0, result.output
        flat = _flatten_box(result.output or "")
        assert "--usage-ratio-id" in flat, result.output
        assert "aeat app ledger ratios list" in flat, result.output
        assert "aeat app ledger ratios eligible" in flat, result.output
        assert "aeat app ledger ratios set" in flat, result.output
        assert "category-id" in flat, result.output
        assert any(
            phrase in flat
            for phrase in ("Not arbitrary prose", "No es texto libre", "No és text lliure", "Nem tetszőleges szöveg")
        ), result.output


def test_business_pct_help_is_mixed_only_across_public_verbs(tmp_path: Path) -> None:
    """`--business-pct` help tells operators to omit it for fully BUSINESS rows."""

    for args in (
        ["app", "ledger", "add", "--help"],
        ["app", "ledger", "classify", "--help"],
        ["app", "ledger", "allocate", "--help"],
    ):
        result = _invoke(args, env={"CADRUMO_OUTPUT_LANGUAGE": "en", "COLUMNS": "260"})

        assert result.exit_code == 0, result.output
        flat = _flatten_box(result.output or "")
        assert "--business-pct" in flat, result.output
        assert "MIXED" in flat, result.output
        assert "BUSINESS" in flat, result.output
        assert any(
            phrase in flat
            for phrase in ("fully BUSINESS", "totalmente BUSINESS", "totalment BUSINESS", "Teljesen BUSINESS")
        ), result.output


def test_mixed_row_with_business_pct_alone_is_not_preflight_ready(tmp_path: Path) -> None:
    """A MIXED row classified with ``--business-pct`` alone fails preflight.

    Preflight reports ``missing_proportionality_reference`` because the row has
    no ``usage_ratio_id``. This pins the design the doc must describe: a bare
    percentage is not enough for a MIXED row to be ready.
    """
    txn_id = _add_eligible_mixed_expense()

    classified = _invoke(
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
        env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
    )
    assert classified.exit_code == 0, classified.output

    preflight = _invoke(
        ["app", "ledger", "preflight", "--year", "2026", "--period", "1T"],
        env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
    )
    assert preflight.exit_code == 0, preflight.output
    assert "ready\tfalse" in preflight.output, preflight.output
    assert "missing_proportionality_reference" in preflight.output, preflight.output
    assert "aeat app ledger ratios list" in preflight.output, preflight.output
    assert "aeat app ledger ratios eligible" in preflight.output, preflight.output
    assert "aeat app ledger ratios set" in preflight.output, preflight.output
    assert "--usage-ratio-id <category-id>" in preflight.output, preflight.output


def test_documented_mixed_use_flow_reaches_preflight_ready(tmp_path: Path) -> None:
    """The documented ratios-set + allocate flow makes a MIXED row preflight-ready.

    Mirrors the corrected ``docs/how-to/classify-transactions.md`` mixed-use
    steps end to end: save a category ratio, then allocate the row naming the
    same category id for both ``--usage-ratio-id`` and ``--category-id``.
    Preflight must then report zero issues and ready=true.
    """
    txn_id = _add_eligible_mixed_expense()

    ratios_set = _invoke(
        ["app", "ledger", "ratios", "set", "telefonia_movil", "0.5"],
        env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
    )
    assert ratios_set.exit_code == 0, ratios_set.output

    allocate = _invoke(
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
        env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
    )
    assert allocate.exit_code == 0, allocate.output

    preflight = _invoke(
        ["app", "ledger", "preflight", "--year", "2026", "--period", "1T"],
        env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
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
# contract ("others are set automatically by the application"); these tests pin it.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("system_state", ["SKIPPED_BY_RULE", "FAILED_VALIDATION", "PROCESSED_UNCLASSIFIED"])
def test_ledger_classify_refuses_pipeline_managed_state(tmp_path: Path, system_state: str) -> None:
    """``ledger classify`` refuses a pipeline-managed state with an instructive error."""
    txn_id = _add_eligible_mixed_expense()

    result = _invoke(
        ["app", "ledger", "classify", txn_id, "--classification", system_state],
        env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
    )

    assert result.exit_code != 0, result.output
    flat = _flatten_box(result.output or "")
    _assert_pipeline_managed_state_refusal(flat, result.output)


@pytest.mark.parametrize("system_state", ["SKIPPED_BY_RULE", "FAILED_VALIDATION", "PROCESSED_UNCLASSIFIED"])
def test_ledger_add_refuses_pipeline_managed_state(tmp_path: Path, system_state: str) -> None:
    """``ledger add --classification <system state>`` is refused instructively."""
    result = _invoke(
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
        env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
    )

    assert result.exit_code != 0, result.output
    flat = _flatten_box(result.output or "")
    _assert_pipeline_managed_state_refusal(flat, result.output)
    assert "omit --classification" in flat, result.output


def test_ledger_add_default_classification_is_accepted(tmp_path: Path) -> None:
    """``ledger add`` with no ``--classification`` keeps the NOT_YET_PROCESSED default.

    The pipeline-managed guard must not refuse the import default; only the three
    truly-internal states (PROCESSED_UNCLASSIFIED / SKIPPED_BY_RULE /
    FAILED_VALIDATION) are blocked.
    """
    result = _invoke(
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
        env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["transaction"]["business_classification"] == "NOT_YET_PROCESSED", payload
