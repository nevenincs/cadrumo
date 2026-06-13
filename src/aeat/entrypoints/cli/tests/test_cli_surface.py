"""Integration tests for the user-facing ``aeat`` CLI.

These tests assert that every command namespace exists, that the thin
transport handlers route into the application layer, and that the
JSON envelope matches the typed records the backend exposes. They
do NOT exercise live AEAT, certificate auth, or any network surface.

Each test isolates storage state through ``isolated_profile_storage_root``
which provisions a real file-backend storage root per test without a
pre-existing active profile.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from ....core.config import override_settings
from ....core.redaction import CLI_BUCKET_ID_PLACEHOLDER, CLI_PROFILE_ID_PLACEHOLDER
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _json(result) -> dict[str, Any]:
    """Parse a CLI JSON result, unwrapping the emit-envelope when present.

    ``_emit_envelope`` (the schema-envelope and ledger.import migrations)
    wraps typed CLI payloads in ``{"schema_version", "command", "result",
    "warnings"}``. Tests that assert against the typed payload should
    read the inner ``result`` directly; legacy ``_emit`` callers emit a
    bare payload, which this helper passes through unchanged. Pattern
    mirrors the equivalent ``_json`` in test_cli_workflow_verification.py
    (commit e707fe8a8, #83).
    """
    payload = json.loads(result.output)
    if isinstance(payload, dict) and "result" in payload and "schema_version" in payload:
        inner = payload["result"]
        if isinstance(inner, dict):
            return inner
    return payload


def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Clear ambient auth env vars for tests that interact with auth CLI surfaces."""
    for name in (
        "AEAT_AUTH_PROVIDER",
        "AEAT_CERTIFICATE_PATH",
        "AEAT_CERTIFICATE_PASSWORD_SECRET",
        "AEAT_CLAVE_MOVIL_DNI_NIE",
        "AEAT_CLAVE_MOVIL_DNI_FECHA",
        "AEAT_CLAVE_MOVIL_NIE_SOPORTE",
    ):
        monkeypatch.delenv(name, raising=False)


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _active_bucket_id() -> str:
    """Resolve the active profile's bucket id — a generated ``profile_id`` UUID.

    Profile identity is the decoupled ``profile_id`` UUID, not the
    operator-facing label passed to ``profile create``. Ledger and
    evidence records key on this UUID, so seeds and assertions must
    resolve it at runtime rather than assume the human label.

    Reads the real UUID via the application-layer resolver rather than
    the CLI ``profile status`` surface, because centralized CLI
    redaction (``redact_structured_for_cli_output``) rewrites the
    ``profile_id`` field to ``<profile-id>`` and the ``bucket_id``
    field to ``<bucket-id>``. Test-side seeders (``_seed_purchase_invoice_evidence``)
    require the un-redacted UUID to persist matching bucket records.
    """
    from ....core import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None, "no active profile bucket resolved"
    return bucket_id


def _create_manual_ledger_row(description: str, *, amount: str = "25.00", key: str) -> dict[str, object]:
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-05-03",
            "--amount",
            amount,
            "--direction",
            "OUTGOING",
            "--description",
            description,
            "--idempotency-key",
            key,
        ],
    )
    assert result.exit_code == 0, result.output
    return _json(result)


# ---------------------------------------------------------------------
# Namespace surface
# ---------------------------------------------------------------------


def test_root_help_lists_config_and_app() -> None:
    result = _invoke(["--help"])
    assert result.exit_code == 0
    assert "config" in result.output
    assert "app" in result.output


def test_app_help_lists_singular_domains() -> None:
    result = _invoke(["app", "--help"])
    assert result.exit_code == 0
    for token in ("overview", "ledger", "live", "modelo", "registry", "review"):
        assert token in result.output
    for retired_command in ("aeat app invoice", "aeat app declaration", "aeat app archive"):
        assert retired_command not in result.output
    for plural_namespace in ("workspaces", "audits"):
        assert plural_namespace not in result.output


def test_top_level_auth_is_not_user_facing() -> None:
    result = _invoke(["auth", "--help"])
    assert result.exit_code != 0


def test_retired_invoice_declaration_and_archive_surfaces_are_not_user_facing() -> None:
    for command in (["app", "invoice"], ["app", "declaration"], ["app", "archive"]):
        result = _invoke([*command, "--help"])
        assert result.exit_code != 0, command


# ---------------------------------------------------------------------
# App namespace — overview / ledger
# ---------------------------------------------------------------------


def test_app_overview_status_bare_renders_counts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = _invoke(["--format", "json", "app", "overview", "status"])
    assert result.exit_code == 0
    payload = _json(result)
    assert payload["transactions"] == 0
    assert payload["invoices"] == 0
    assert payload["drafts"] == 0


def test_app_ledger_import_dry_run_does_not_persist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    statement = tmp_path / "n26.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n",
        encoding="utf-8",
    )
    dry = _invoke(["--format", "json", "app", "ledger", "import", str(statement), "--provider", "csv", "--dry-run"])
    assert dry.exit_code == 0
    result = _json(dry)
    assert result["dry_run"] is True
    # The dry run previews what a real import would add - one row here -
    # but persists nothing: the overview still reports zero transactions.
    assert result["imported"] == 1
    after = _invoke(["--format", "json", "app", "overview", "status"])
    assert _json(after)["transactions"] == 0


def _run_ledger_cli_json(args: list[str]) -> dict[str, Any]:
    """Invoke the CLI with ``--format json`` prefixed, assert exit-0, return parsed JSON."""
    result = _invoke(["--format", "json", *args])
    assert result.exit_code == 0, result.output
    return _json(result)


def _ledger_add_manual_transaction(bucket_id: str) -> dict[str, Any]:
    """Create the seed manual transaction the rest of the workflow operates on."""
    payload = _run_ledger_cli_json(
        [
            "app",
            "ledger",
            "add",
            "--date",
            "2026-05-02",
            "--amount",
            "121.00",
            "--direction",
            "OUTGOING",
            "--description",
            "cash office supplies",
            "--counterparty",
            "Proveedor SL",
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
            "--idempotency-key",
            "cash-office-2026-05-02",
        ],
    )
    assert bucket_id not in json.dumps(payload, sort_keys=True)
    assert payload["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER
    assert len(cast(str, payload["transaction_id"])) == 64
    transaction = cast(dict[str, object], payload["transaction"])
    assert transaction["business_classification"] == "BUSINESS"
    assert transaction["taxable_base"] == "100"
    assert transaction["iva_rate"] == "0.21"
    assert payload["bucket_event_ids"]
    return payload


def _ledger_list_and_view(transaction_id: str, *, bucket_id: str) -> None:
    """The list verb returns the seed row, the view verb returns its full record."""
    listed = _run_ledger_cli_json(["app", "ledger", "list"])
    assert bucket_id not in json.dumps(listed, sort_keys=True)
    assert listed["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER
    rows = cast(list[dict[str, object]], listed["rows"])
    assert [row["transaction_id"] for row in rows] == [transaction_id]
    assert rows[0]["review_status"] == "reviewed"

    read = _run_ledger_cli_json(["app", "ledger", "view", transaction_id])
    assert bucket_id not in json.dumps(read, sort_keys=True)
    assert read["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER
    assert read["transaction_id"] == transaction_id
    assert read["review_status"] == "reviewed"
    transaction = cast(dict[str, object], read["transaction"])
    assert transaction["description"] == "cash office supplies"


def _ledger_update_transaction(transaction_id: str) -> dict[str, object]:
    """Update the seed transaction's amount + description; assert the diff."""
    edited = _run_ledger_cli_json(
        [
            "app",
            "ledger",
            "update",
            transaction_id,
            "--amount",
            "121.50",
            "--taxable-base",
            "100.41",
            "--iva-amount",
            "21.09",
            "--direction",
            "OUTGOING",
            "--description",
            "cash office supplies corrected",
        ],
    )
    transaction = cast(dict[str, object], edited["transaction"])
    assert Decimal(cast(str, transaction["amount"])) == Decimal("121.50")
    assert transaction["description"] == "cash office supplies corrected"
    assert edited["bucket_event_ids"]
    return edited


def _ledger_classify_transaction(transaction_id: str) -> dict[str, object]:
    """Re-classify the updated transaction; verify BUSINESS + new category id."""
    classified = _run_ledger_cli_json(
        [
            "app",
            "ledger",
            "classify",
            transaction_id,
            "--classification",
            "BUSINESS",
            "--category-id",
            "software_suscripcion",
            "--taxable-base",
            "100.41",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "21.09",
        ],
    )
    transaction = cast(dict[str, object], classified["transaction"])
    assert transaction["business_classification"] == "BUSINESS"
    assert transaction["category_id"] == "software_suscripcion"
    assert classified["review_status"] == "reviewed"
    return classified


def _seed_usage_ratio_for_telefonia(bucket_id: str) -> None:
    """Persist a usage-ratio profile so the next allocate verb can resolve TELEFONIA_MOVIL."""
    from ....adapters.persistence.storage import (
        activate_master_key_provider,
        get_master_key_provider,
    )
    from ....domain.categories import SpendingCategory
    from ....domain.usage_ratios import UsageRatioProfile, save_usage_ratios

    with activate_master_key_provider(get_master_key_provider()):
        save_usage_ratios(
            UsageRatioProfile(ratios={SpendingCategory.TELEFONIA_MOVIL: Decimal("0.60")}),
            bucket_id=bucket_id,
        )


def _ledger_allocate_transaction(transaction_id: str) -> dict[str, object]:
    """Allocate a usage ratio to the transaction; verify MIXED classification + pct."""
    allocated = _run_ledger_cli_json(
        [
            "app",
            "ledger",
            "allocate",
            transaction_id,
            "--business-pct",
            "0.60",
            "--category-id",
            "telefonia_movil",
            "--usage-ratio-id",
            "telefonia_movil",
        ],
    )
    transaction = cast(dict[str, object], allocated["transaction"])
    assert transaction["business_classification"] == "MIXED"
    assert Decimal(cast(str, transaction["business_pct"])) == Decimal("0.60")
    assert transaction["usage_ratio_id"] == "telefonia_movil"
    return allocated


def _assert_ledger_status_one_ready_row(bucket_id: str) -> None:
    """After one reviewed transaction the status verb reports a single ready row."""
    status = _run_ledger_cli_json(["app", "ledger", "status", "--period", "05", "--year", "2026"])
    assert bucket_id not in json.dumps(status, sort_keys=True)
    assert status["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER
    assert status["total_count"] == 1
    assert status["active_count"] == 1
    assert status["reviewed_count"] == 1
    assert status["pending_review_count"] == 0
    assert status["checked_transaction_count"] == 1
    assert status["readiness_issue_count"] == 0
    assert status["ready"] is True


def _assert_ledger_track_returns_lineage(
    transaction_id: str,
    *,
    expected_created_event_id: str,
    bucket_id: str,
) -> None:
    """The track verb returns the transaction body plus its lineage triple."""
    tracked = _run_ledger_cli_json(["app", "ledger", "track", transaction_id])
    assert bucket_id not in json.dumps(tracked, sort_keys=True)
    assert tracked["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER
    transaction = cast(dict[str, object], tracked["transaction"])
    assert transaction["transaction_id"] == transaction_id
    tracking = cast(dict[str, object], tracked["tracking"])
    assert tracking["created_event_id"] == expected_created_event_id
    assert tracking["edit_lineage"]
    assert tracking["lifecycle_lineage"] == []


def _assert_ledger_review_returns_transaction(transaction_id: str) -> None:
    """The review verb returns the transaction by id with the post-update description."""
    reviewed = _run_ledger_cli_json(["app", "ledger", "review", transaction_id])
    assert reviewed["id"] == transaction_id
    assert reviewed["description"] == "cash office supplies corrected"
    assert reviewed["review_status"] == "reviewed"


def _assert_ledger_review_filtered_by_period_returns_empty(transaction_id: str) -> None:
    """Review with a period filter that doesn't match returns an empty rows list."""
    filtered_out = _run_ledger_cli_json(
        ["app", "ledger", "review", transaction_id, "--filter", "period=06", "--filter", "year=2026"],
    )
    assert filtered_out["rows"] == []
    assert filtered_out["filters"] == ["period=2026 06", f"id={transaction_id}"]


def test_app_ledger_create_manual_transaction_persists_in_active_bucket(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """End-to-end ledger CLI flow: add → list/view → update → classify → allocate → status → track → review.

    Each step is a small helper that owns its CLI invocation, JSON
    parsing, and the assertions specific to that step. The test body
    reads as a linear narrative of the workflow with the
    transaction-id and intermediate payloads threaded through.
    """
    _isolate(monkeypatch, tmp_path)
    init = _invoke(
        ["config", "profile", "create", "operator", "--quiet", "--tax-id", "12345678Z", "--activity", "Test"],
    )
    assert init.exit_code == 0, init.output
    bucket_id = _active_bucket_id()

    created = _ledger_add_manual_transaction(bucket_id)
    transaction_id = cast(str, created["transaction_id"])
    created_event_id = cast(list[str], created["bucket_event_ids"])[0]

    _ledger_list_and_view(transaction_id, bucket_id=bucket_id)
    # Each downstream verb may rewrite the transaction id because the
    # ledger row is content-addressed (changing amount/category changes
    # the SHA). Re-thread the new id between steps so the verb chain
    # tracks the same logical row.
    edited = _ledger_update_transaction(transaction_id)
    transaction_id = cast(str, edited["transaction_id"])
    classified = _ledger_classify_transaction(transaction_id)
    transaction_id = cast(str, classified["transaction_id"])
    _seed_usage_ratio_for_telefonia(bucket_id=bucket_id)
    allocated = _ledger_allocate_transaction(transaction_id)
    transaction_id = cast(str, allocated["transaction_id"])
    _assert_ledger_status_one_ready_row(bucket_id)
    _assert_ledger_track_returns_lineage(
        transaction_id,
        expected_created_event_id=created_event_id,
        bucket_id=bucket_id,
    )
    _assert_ledger_review_returns_transaction(transaction_id)
    _assert_ledger_review_filtered_by_period_returns_empty(transaction_id)


def test_app_ledger_list_reveal_identifiers_opt_in_surfaces_real_bucket_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Default ledger list JSON redacts ``bucket_id``; the reveal opt-out shows the real UUID.

    Multi-client gestors must be able to disambiguate which bucket a command
    addressed. The ``AEAT_CLI_REVEAL_IDENTIFIERS`` opt-out un-redacts the
    profile/bucket identifier surfaces while the paste-safe placeholder stays
    the default.
    """
    _isolate(monkeypatch, tmp_path)
    init = _invoke(
        ["config", "profile", "create", "operator", "--quiet", "--tax-id", "12345678Z", "--activity", "Test"],
    )
    assert init.exit_code == 0, init.output
    bucket_id = _active_bucket_id()
    _ledger_add_manual_transaction(bucket_id)

    default_listed = _run_ledger_cli_json(["app", "ledger", "list"])
    assert default_listed["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER
    assert bucket_id not in json.dumps(default_listed, sort_keys=True)

    with override_settings(aeat_cli_reveal_identifiers=True):
        revealed = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])
    assert revealed.exit_code == 0, revealed.output
    revealed_payload = _json(revealed)
    assert revealed_payload["bucket_id"] == bucket_id
    assert revealed_payload["bucket_id"] != CLI_BUCKET_ID_PLACEHOLDER


def test_config_profile_show_reveal_identifiers_opt_in_surfaces_real_profile_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Default ``config profile show`` JSON redacts ``profile_id``; the opt-out reveals it.

    ``config profile show`` is the profile inspection surface. The
    centralised-output-redaction policy rewrites the ``profile_id`` field to the
    paste-safe ``<profile-id>`` placeholder by default; the
    ``AEAT_CLI_REVEAL_IDENTIFIERS`` opt-out un-redacts the opaque profile UUID so
    a multi-client gestor's automation can key on the addressed profile.
    """
    _isolate(monkeypatch, tmp_path)
    init = _invoke(
        ["config", "profile", "create", "operator", "--quiet", "--tax-id", "12345678Z", "--activity", "Test"],
    )
    assert init.exit_code == 0, init.output
    profile_id = _active_bucket_id()

    default_shown = _run_ledger_cli_json(["config", "profile", "show"])
    assert default_shown["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER
    assert profile_id not in json.dumps(default_shown, sort_keys=True)

    with override_settings(aeat_cli_reveal_identifiers=True):
        revealed = invoke_cached_cli(["--format", "json", "config", "profile", "show"])
    assert revealed.exit_code == 0, revealed.output
    revealed_payload = _json(revealed)
    assert revealed_payload["profile_id"] == profile_id
    assert revealed_payload["profile_id"] != CLI_PROFILE_ID_PLACEHOLDER


def test_app_modelo_filing_record_list_text_header_is_well_formed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The ``filing-record list`` text column header survives the identifier redactor.

    The tab-delimited header places ``bucket_id`` immediately before the
    ``modelo`` column name. The ``label<TAB>value`` redaction heuristic must not
    rewrite the next column name into a ``<bucket-id>`` placeholder: a column
    header carries field names, never identifier values. The header row must pass
    through verbatim so automation can parse the columns.
    """
    _isolate(monkeypatch, tmp_path)
    init = _invoke(
        ["config", "profile", "create", "operator", "--quiet", "--tax-id", "12345678Z", "--activity", "Test"],
    )
    assert init.exit_code == 0, init.output

    listed = _invoke(["app", "modelo", "filing-record", "list"])
    assert listed.exit_code == 0, listed.output

    header_line = "filing_record_id\tbucket_id\tmodelo\tyear\tperiod\tstatus\tfiled_at\tfiled_by"
    assert header_line in listed.output
    # The corruption symptom was ``bucket_id<TAB><bucket-id>`` replacing the
    # ``modelo`` column name; the well-formed header keeps every column name.
    assert "\tbucket_id\tmodelo\t" in listed.output
    assert f"bucket_id\t{CLI_BUCKET_ID_PLACEHOLDER}" not in listed.output


def _json_object(value: object) -> dict[str, object]:
    """Narrow a JSON value to a string-keyed object for typed subscripting."""

    assert isinstance(value, dict), f"expected a JSON object, got {type(value).__name__}"
    return {str(key): item for key, item in value.items()}


@dataclass(frozen=True, slots=True)
class _LedgerLifecycleOutcome:
    """Bundle returned by _drive_ledger_lifecycle_round_trip.

    Captures every CLI payload + side-effect path that the focused
    tests inspect: the attach result, the archive / stash state
    transitions, the remove dry-run + final delete, the export
    payload + path, and the reset payload.
    """

    bucket_id: str
    purchase_invoice_evidence_id: str
    attached_payload: dict[str, object]
    archived_payload: dict[str, object]
    stashed_payload: dict[str, object]
    dry_remove_payload: dict[str, object]
    refused_remove_exit_code: int
    removed_payload: dict[str, object]
    export_payload: dict[str, object]
    export_path: Path
    dry_reset_payload: dict[str, object]
    refused_reset_exit_code: int
    reset_payload: dict[str, object]


def _drive_ledger_lifecycle_round_trip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> _LedgerLifecycleOutcome:
    """Drive the lifecycle round-trip: attach -> archive -> stash -> remove -> export -> reset.

    Three rows are created so the export and reset surfaces see a
    non-trivial inventory (one attached + one archived + one
    stashed; the remove and reset paths exercise the final two
    inactive rows).
    """
    _isolate(monkeypatch, tmp_path)
    init = _invoke(
        ["config", "profile", "create", "operator", "--quiet", "--tax-id", "12345678Z", "--activity", "Test"],
    )
    assert init.exit_code == 0, init.output
    bucket_id = _active_bucket_id()

    purchase_evidence_id = _seed_purchase_invoice_evidence(bucket_id)

    attached = _ledger_lifecycle_attach(purchase_invoice_evidence_id=purchase_evidence_id)
    archived = _ledger_lifecycle_lifecycle_transition("archive", reason="wrong account", key="cli-archive-row")
    stashed = _ledger_lifecycle_lifecycle_transition("stash", reason="needs review", key="cli-stash-row")

    remove_outcome = _ledger_lifecycle_remove()
    export_outcome = _ledger_lifecycle_export(tmp_path)
    reset_outcome = _ledger_lifecycle_reset()

    return _LedgerLifecycleOutcome(
        bucket_id=bucket_id,
        purchase_invoice_evidence_id=purchase_evidence_id,
        attached_payload=attached,
        archived_payload=archived,
        stashed_payload=stashed,
        dry_remove_payload=remove_outcome[0],
        refused_remove_exit_code=remove_outcome[1],
        removed_payload=remove_outcome[2],
        export_payload=export_outcome[0],
        export_path=export_outcome[1],
        dry_reset_payload=reset_outcome[0],
        refused_reset_exit_code=reset_outcome[1],
        reset_payload=reset_outcome[2],
    )


def _seed_purchase_invoice_evidence(bucket_id: str) -> str:
    """Persist one RECEIVED purchase invoice and return its id."""
    from ....adapters.persistence.storage import (
        activate_master_key_provider,
        get_master_key_provider,
    )
    from ....domain.invoices import (
        Invoice,
        InvoiceCatalogue,
        InvoiceCatalogueRepository,
        InvoiceLine,
        IvaRate,
        PaymentStatus,
    )
    from ....domain.iva import InvoiceKind

    purchase_line = InvoiceLine(
        description="Material oficina",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        iva_rate=IvaRate.RATE_21,
        iva_amount=Decimal("21.00"),
    )
    purchase_evidence = Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "bucket_id": bucket_id,
            "invoice_number": "P-2026-CLI-001",
            "issued_at": date(2026, 5, 3),
            "counterparty_name": "Proveedor SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (purchase_line,),
            "payment_status": PaymentStatus.PAID,
        },
    )
    with activate_master_key_provider(get_master_key_provider()):
        InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices((purchase_evidence,)))
    return purchase_evidence.invoice_id


def _ledger_lifecycle_attach(*, purchase_invoice_evidence_id: str) -> dict[str, object]:
    """Create a manual ledger row and attach the purchase-invoice evidence reference."""
    row = _create_manual_ledger_row("attach evidence row", amount="121.00", key="cli-attach-row")
    attached = _invoke(
        [
            "--format", "json",
            "app", "ledger", "attach",
            str(row["transaction_id"]),
            "--purchase-invoice-evidence-id", purchase_invoice_evidence_id,
        ],
    )  # fmt: skip
    assert attached.exit_code == 0, attached.output
    return _json(attached)


def _ledger_lifecycle_lifecycle_transition(verb: str, *, reason: str, key: str) -> dict[str, object]:
    """Drive one ``app ledger <verb> <id> --reason ... --yes`` lifecycle transition."""
    row = _create_manual_ledger_row(f"{verb} row", key=key)
    result = _invoke(
        [
            "--format", "json",
            "app", "ledger", verb,
            str(row["transaction_id"]),
            "--reason", reason,
            "--yes",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return _json(result)


def _ledger_lifecycle_remove() -> tuple[dict[str, object], int, dict[str, object]]:
    """Drive the three-step remove flow: --dry-run, refused (no --yes), confirmed --yes."""
    remove_row = _create_manual_ledger_row("remove row", key="cli-remove-row")
    dry = _invoke(
        ["--format", "json", "app", "ledger", "remove", str(remove_row["transaction_id"]), "--dry-run"],
    )
    assert dry.exit_code == 0, dry.output
    refused = _invoke(["--format", "json", "app", "ledger", "remove", str(remove_row["transaction_id"])])
    confirmed = _invoke(
        ["--format", "json", "app", "ledger", "remove", str(remove_row["transaction_id"]), "--yes"],
    )
    assert confirmed.exit_code == 0, confirmed.output
    return _json(dry), refused.exit_code, _json(confirmed)


def _ledger_lifecycle_export(tmp_path: Path) -> tuple[dict[str, object], Path]:
    """Drive the ledger export to a JSONL file under ``tmp_path``."""
    export_path = tmp_path / "ledger-export.jsonl"
    exported = _invoke(
        [
            "--format", "json",
            "app", "ledger", "export",
            "--output", str(export_path),
            "--export-format", "jsonl",
            "--include-inactive",
        ],
    )  # fmt: skip
    assert exported.exit_code == 0, exported.output
    return _json(exported), export_path


def _ledger_lifecycle_reset() -> tuple[dict[str, object], int, dict[str, object]]:
    """Drive the three-step reset flow: --dry-run, refused (no --yes), confirmed --yes."""
    dry = _invoke(["--format", "json", "app", "ledger", "reset", "--dry-run"])
    assert dry.exit_code == 0, dry.output
    refused = _invoke(["--format", "json", "app", "ledger", "reset", "--reason", "test cleanup"])
    confirmed = _invoke(["--format", "json", "app", "ledger", "reset", "--reason", "test cleanup", "--yes"])
    assert confirmed.exit_code == 0, confirmed.output
    return _json(dry), refused.exit_code, _json(confirmed)


def test_app_ledger_lifecycle_attach_records_purchase_invoice_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outcome = _drive_ledger_lifecycle_round_trip(monkeypatch, tmp_path)
    transaction = _json_object(outcome.attached_payload["transaction"])
    assert transaction["purchase_invoice_evidence_id"] == outcome.purchase_invoice_evidence_id
    assert outcome.attached_payload["bucket_event_ids"]


_LIFECYCLE_TRANSITION_EXPECTATIONS = (
    ("archived_payload", "ARCHIVED"),
    ("stashed_payload", "STASHED"),
)


@pytest.mark.parametrize(("attribute", "expected_state"), _LIFECYCLE_TRANSITION_EXPECTATIONS)
def test_app_ledger_lifecycle_transition_advances_lifecycle_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    attribute: str,
    expected_state: str,
) -> None:
    outcome = _drive_ledger_lifecycle_round_trip(monkeypatch, tmp_path)
    payload = getattr(outcome, attribute)
    assert payload["transaction"]["lifecycle_state"] == expected_state


def test_app_ledger_lifecycle_remove_dry_run_marks_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outcome = _drive_ledger_lifecycle_round_trip(monkeypatch, tmp_path)
    assert outcome.dry_remove_payload["dry_run"] is True


def test_app_ledger_lifecycle_remove_requires_yes_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outcome = _drive_ledger_lifecycle_round_trip(monkeypatch, tmp_path)
    assert outcome.refused_remove_exit_code != 0


def test_app_ledger_lifecycle_remove_with_yes_deletes_row(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outcome = _drive_ledger_lifecycle_round_trip(monkeypatch, tmp_path)
    assert outcome.removed_payload["removed"] is True


def test_app_ledger_lifecycle_export_targets_active_profile_bucket(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outcome = _drive_ledger_lifecycle_round_trip(monkeypatch, tmp_path)
    assert outcome.bucket_id not in json.dumps(outcome.export_payload, sort_keys=True)
    assert outcome.export_payload["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER


def test_app_ledger_lifecycle_export_records_three_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outcome = _drive_ledger_lifecycle_round_trip(monkeypatch, tmp_path)
    assert outcome.export_payload["row_count"] == 3
    assert outcome.export_path.read_text(encoding="utf-8").count("\n") == 3


def test_app_ledger_lifecycle_reset_dry_run_marks_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outcome = _drive_ledger_lifecycle_round_trip(monkeypatch, tmp_path)
    assert outcome.dry_reset_payload["dry_run"] is True


def test_app_ledger_lifecycle_reset_requires_yes_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outcome = _drive_ledger_lifecycle_round_trip(monkeypatch, tmp_path)
    assert outcome.refused_reset_exit_code != 0


def test_app_ledger_lifecycle_reset_with_yes_clears_three_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outcome = _drive_ledger_lifecycle_round_trip(monkeypatch, tmp_path)
    assert outcome.reset_payload["reset"] is True
    removed_transaction_ids = outcome.reset_payload["removed_transaction_ids"]
    assert isinstance(removed_transaction_ids, list)
    assert len(removed_transaction_ids) == 3


def test_app_ledger_import_reimport_review_round_trips_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    init = _invoke(
        [
            "config",
            "profile",
            "create",
            "operator",
            "--quiet",
            "--tax-id",
            "12345678Z",
            "--activity",
            "Test",
        ],
    )
    assert init.exit_code == 0
    statement = tmp_path / "n26.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n"
        "2026-04-16,SaaS Vendor,Subscription,-48.40,EUR,n26-002\n",
        encoding="utf-8",
    )
    imported = _invoke(["--format", "json", "app", "ledger", "import", str(statement), "--provider", "csv"])
    assert imported.exit_code == 0
    imported_payload = _json(imported)
    assert imported_payload["rows"] == 2
    assert imported_payload["imported"] == 2
    assert imported_payload["skipped"] == 0

    repeated = _invoke(["--format", "json", "app", "ledger", "import", str(statement), "--provider", "csv"])
    assert repeated.exit_code == 0
    repeated_payload = _json(repeated)
    assert repeated_payload["rows"] == 2
    assert repeated_payload["imported"] == 0
    assert repeated_payload["skipped"] == 2

    review = _invoke(["--format", "json", "app", "ledger", "review"])
    assert review.exit_code == 0
    payload = _json(review)
    rows_by_description = {row["description"]: row for row in payload["rows"]}
    assert set(rows_by_description) == {"Invoice 1", "Subscription"}
    assert {row["status"] for row in payload["rows"]} == {"pending"}
    vendor_id = rows_by_description["Subscription"]["id"]

    reviewed = _invoke(["--format", "json", "app", "ledger", "review", vendor_id])
    assert reviewed.exit_code == 0, reviewed.output
    reviewed_payload = _json(reviewed)
    assert reviewed_payload["id"] == vendor_id
    assert reviewed_payload["description"] == "Subscription"


def test_app_ledger_review_filter_rejects_unknown_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    result = _invoke(["app", "ledger", "review", "--filter", "kind=received"])
    assert result.exit_code != 0


def test_set_ratio_is_not_a_ledger_verb(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    for command in ("set-ratio",):
        result = _invoke(["app", "ledger", command, "--help"])
        assert result.exit_code != 0
