"""Persona testimonial: Marta the autónoma closes her 1T-2025 quarter.

Marta Rios Velasco is a freelance software consultant on estimación directa
simplificada filing IVA on the general regime. This suite drives the real
``aeat app ledger`` CLI end-to-end through her *first* quarterly close: import
her four bank exports, narrow the review to 1T (Q1) 2025, classify the quarter's
business income and expenses against the ground-truth oracle, then run the
readiness gates (``preflight``/``check``/``status``) and ``export`` the result.

Unlike :mod:`test_ledger_corpus_journeys`, which exercises each verb in
isolation, this is a single linear journey: the assertions track what an operator
would actually observe at each step, and the docstrings/comments capture the
operator-experience findings (the testimonial) inline.

Harness is shared with the corpus-journey suite: an isolated profile backend via
``override_settings`` + ``isolated_profile_storage_root`` +
``profile_create_storage_span`` + ``register_minimal_profile``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.config import override_settings
from ....tests import FIXTURES_DIR
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CORPUS = FIXTURES_DIR / "financial" / "ledger-corpus"
_FILES = (
    "bbva-business-eur.csv",
    "caixabank-personal.csv",
    "revolut-multi.csv",
    "n26-savings.csv",
)


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("00000000-0000-4000-8000-000000000000"),
    ):
        try:
            workflow_state_repository().update(
                lambda state: register_minimal_profile(state, profile_id="00000000-0000-4000-8000-000000000000")
            )
            yield
        finally:
            dispose_engine()


def _oracle_rules() -> list[dict[str, object]]:
    manifest = json.loads((_CORPUS / "ground-truth.manifest.json").read_text(encoding="utf-8"))
    return manifest["rules"]


def _match(description: str, rules: list[dict[str, object]]) -> dict[str, object] | None:
    for rule in rules:
        match_val = rule.get("match")
        if isinstance(match_val, str) and match_val in description:
            return rule
    return None


def _import_corpus() -> None:
    for name in _FILES:
        result = _invoke(["app", "ledger", "import", str(_CORPUS / name), "--provider", "csv"])
        assert result.exit_code == 0, f"{name}: {result.output}"


def _list_rows() -> list[dict[str, object]]:
    listed = _invoke(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    return payload.get("result", payload).get("rows", [])


def _is_q1_2025(row: dict[str, object]) -> bool:
    """Marta only wants the January-March 2025 rows for her 1T close."""
    date_val = row.get("date")
    date = str(date_val) if date_val is not None else ""
    return date.startswith("2025-01") or date.startswith("2025-02") or date.startswith("2025-03")


def test_marta_closes_1t_2025_end_to_end(tmp_path: Path) -> None:
    """Marta's full first quarterly close as she would run it."""
    rules = _oracle_rules()

    # --- Import every bank export -----------------------------------------
    # Marta downloaded one CSV from each of her four banks. She imports each in
    # turn. TESTIMONIAL: there is no "import all CSVs in a folder" affordance;
    # she must invoke the verb once per file and remember the --provider flag.
    _import_corpus()
    all_rows = _list_rows()
    assert len(all_rows) >= 500, f"expected full corpus imported, got {len(all_rows)}"

    # --- Narrow to the quarter --------------------------------------------
    # Marta tries the documented filter first: review --filter period=1T --filter year=2025.
    by_period = _invoke(["app", "ledger", "review", "--filter", "period=1T", "--filter", "year=2025"])
    assert by_period.exit_code == 0, by_period.output
    # TESTIMONIAL: `review` renders a human table but does not emit a JSON row
    # list she can drive programmatically; to actually *act* on the quarter she
    # falls back to `list` + a client-side date filter on the `date` field.
    q1_rows = [r for r in all_rows if _is_q1_2025(r)]
    assert q1_rows, "corpus must carry 1T-2025 activity for Marta to close"

    # Every freshly-imported row is unprocessed; Marta has real work to do.
    assert all(r.get("business_classification") == "NOT_YET_PROCESSED" for r in q1_rows)

    # --- Classify the quarter's business income + expenses ----------------
    # Marta builds a classify CSV resolving each Q1 row against the oracle. She
    # restricts to non-MIXED, non-gated rows (MIXED needs --business-pct, which
    # --from-csv does not carry; gated/personal rows she leaves out of scope).
    classify_lines = ["transaction_id,classification,category_id"]
    expected: dict[str, str] = {}
    for row in q1_rows:
        desc = row.get("description")
        tx_id = row.get("transaction_id")
        assert isinstance(desc, str)
        assert isinstance(tx_id, str)
        rule = _match(desc, rules)
        if rule is None:
            continue
        if rule.get("classification") == "MIXED":
            continue
        if rule.get("base_mode") == "gated":
            continue
        category = rule.get("category_id") or ""
        classification_val = rule.get("classification")
        assert isinstance(classification_val, str)
        classify_lines.append(f"{tx_id},{classification_val},{category}")
        expected[tx_id] = classification_val

    assert len(expected) >= 10, f"Marta's quarter should carry a meaningful classify workload, got {len(expected)}"

    classify_csv = tmp_path / "marta-1t-classifications.csv"
    classify_csv.write_text("\n".join(classify_lines) + "\n", encoding="utf-8")

    bulk = _invoke(["--format", "json", "app", "ledger", "classify", "--from-csv", str(classify_csv)])
    assert bulk.exit_code == 0, bulk.output
    bulk_result = json.loads(bulk.output)["result"]
    # TESTIMONIAL: bulk classify reports total/applied/skipped/failures — a
    # clear summary. It is also the known-slow path (per-row re-persist), which
    # Marta would feel on a real quarter of dozens of rows.
    assert bulk_result["applied"] == len(expected), bulk_result

    # Verify the classifications actually stuck (Marta re-lists to confirm).
    by_id = {r.get("transaction_id"): r for r in _list_rows() if isinstance(r.get("transaction_id"), str)}
    for tx_id, classification in expected.items():
        assert by_id.get(tx_id, {}).get("business_classification") == classification, tx_id

    # --- Classify one MIXED home-office expense the long way ---------------
    # `--from-csv` can't carry the business proportion, so Marta classifies her
    # mixed-use rows one at a time with --business-pct. She picks her Q1 fibra
    # internet line (oracle business_pct 0.30).
    internet = None
    for r in q1_rows:
        desc_val = r.get("description")
        if isinstance(desc_val, str) and "Factura internet fibra oficina" in desc_val:
            internet = r
            break
    if internet is not None:
        tx_id_val = internet.get("transaction_id")
        if isinstance(tx_id_val, str):
            mixed = _invoke(
                [
                    "app",
                    "ledger",
                    "classify",
                    tx_id_val,
                    "--classification",
                    "MIXED",
                    "--business-pct",
                    "0.30",
                    "--category-id",
                    "suministros_home_office_internet",
                ],
            )
            assert mixed.exit_code == 0, mixed.output

    # --- Readiness gates --------------------------------------------------
    # Marta runs preflight for the quarter to see what's still missing.
    preflight = _invoke(
        ["--format", "json", "app", "ledger", "preflight", "--period", "1T", "--year", "2025"],
    )
    assert preflight.exit_code == 0, preflight.output
    pf = json.loads(preflight.output)["result"]
    # The report carries a checked count, an issue list, and a ready flag.
    assert "issues" in pf and "ready" in pf, pf
    # TESTIMONIAL: with a quarter full of still-unprocessed personal/transfer
    # rows, preflight is expected to surface readiness gaps; the value is the
    # explicit, per-transaction issue list (reason + detail), not a bare bool.

    # `check` audits anomalies across every period the ledger touches.
    check = _invoke(["--format", "json", "app", "ledger", "check"])
    assert check.exit_code == 0, check.output
    chk = json.loads(check.output)["result"]
    assert "issues" in chk, chk

    # `status` is Marta's at-a-glance summary for the quarter.
    status = _invoke(["app", "ledger", "status", "--period", "1T", "--year", "2025"])
    assert status.exit_code == 0, status.output

    # --- Export the quarter -----------------------------------------------
    # Marta exports the whole ledger for her gestor. TESTIMONIAL: `export` has
    # no --period flag, so she cannot hand her gestor *just* the quarter; the
    # export is the entire bucket and her gestor must filter downstream.
    out_csv = tmp_path / "marta-1t-2025.csv"
    exported = _invoke(
        ["--format", "json", "app", "ledger", "export", "--output", str(out_csv), "--export-format", "csv"],
    )
    assert exported.exit_code == 0, exported.output
    assert out_csv.exists() and out_csv.stat().st_size > 0
    export_result = json.loads(exported.output)["result"]
    # The export envelope carries a row count and a sha256 — good for an
    # operator who wants a verifiable hand-off artefact.
    assert export_result.get("row_count", export_result.get("rows", 0)) > 0, export_result
