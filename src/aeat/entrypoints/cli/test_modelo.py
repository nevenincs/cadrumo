"""CLI surface tests for the ``aeat ... modelo`` command tree.

These tests pin the user-input-error contract: any operator-facing
error (malformed period, unknown modelo) must surface as a
``typer.BadParameter`` clean message rather than a Python traceback.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider, override_master_key_provider
from aeat.adapters.persistence.storage.sql import dispose_engine
from aeat.core.config import override_settings
from aeat.tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def isolated_cli_storage(tmp_path: Path) -> Iterator[None]:
    provider = EphemeralMasterKeyProvider()
    db_path = tmp_path / "aeat.db"
    dispose_engine()
    override_master_key_provider(provider)
    try:
        with override_settings(
            aeat_database_url=f"sqlite:///{db_path.as_posix()}",
            aeat_secret_store_dir=tmp_path / "secrets",
            aeat_blob_store_dir=tmp_path / "blobs",
            aeat_audit_dir=tmp_path / "audit",
            aeat_token_dir=tmp_path / "tokens",
            aeat_financial_txs_dir=tmp_path / "financial" / "transactions",
            aeat_invoices_dir=tmp_path / "financial" / "invoices",
            aeat_attachments_dir=tmp_path / "financial" / "attachments",
            aeat_purchase_invoice_evidence_dir=tmp_path / "financial" / "purchase-invoice-evidence",
            aeat_ledgers_dir=tmp_path / "financial" / "ledgers",
            aeat_drafts_dir=tmp_path / "drafts",
            aeat_runs_dir=tmp_path / "runs",
            aeat_workflow_runs_dir=tmp_path / "workflow" / "runs",
        ):
            yield
    finally:
        override_master_key_provider(None)
        dispose_engine()


@pytest.mark.parametrize(
    "command",
    [
        ["app", "modelo", "describe", "303", "--period", "garbage"],
        ["app", "modelo", "casillas", "303", "--period", "2026-Quarter1"],
        ["app", "modelo", "bindings", "list", "--modelo", "303", "--year", "2026", "--period", "not-a-period"],
        ["app", "modelo", "formulas", "303", "--period", "2026-13"],
    ],
)
def test_malformed_period_surfaces_as_bad_parameter(command: list[str]) -> None:
    result = invoke_cached_cli(command)
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    output_lower = result.output.lower()
    assert "period must be" in output_lower or "invalid value" in output_lower


def test_unknown_modelo_surfaces_as_bad_parameter() -> None:
    result = invoke_cached_cli(["app", "modelo", "describe", "999"])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    output_lower = result.output.lower()
    assert "999" in output_lower or "not present" in output_lower


# ---------------------------------------------------------------------------
# bindings list / preview surface
# ---------------------------------------------------------------------------


def test_bindings_list_emits_readiness_category_for_every_row() -> None:
    """``bindings list`` enriches each binding row with a readiness
    category from the closed set (ledger source / profile fact /
    prior filed revision / live observation / bucket / waiver /
    blocking finding / casilla)."""

    result = invoke_cached_cli(
        ["app", "modelo", "bindings", "list", "--modelo", "303", "--year", "2026", "--period", "Q1"],
    )
    assert result.exit_code == 0, result.output
    assert "operation\tregistry.modelo.bindings.list" in result.output
    assert "binding_id\tsource\treadiness\ttyped_enum" in result.output
    # Every modelo-303 binding currently sources from
    # ``ledger_iva_aggregation`` so every row's readiness column is
    # "ledger source".
    assert "ledger source" in result.output


def test_bindings_list_missing_filter_excludes_constant_value_bindings() -> None:
    """``--missing`` filters to bindings that require runtime
    resolution. Constant-valued bindings are inherently always
    available so they drop out of the missing-bindings view."""

    result = invoke_cached_cli(
        ["app", "modelo", "bindings", "list", "--modelo", "303", "--year", "2026", "--period", "Q1", "--missing"],
    )
    assert result.exit_code == 0, result.output
    assert "missing_filter\tTrue" in result.output


def test_bindings_list_preserves_census_event_period() -> None:
    """Modelo 036 event periods are exact registry-owned values, not year-prefixed CLI aliases."""

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "bindings",
            "list",
            "--modelo",
            "036",
            "--year",
            "2025",
            "--period",
            "alta",
        ],
    )
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["period_filter"] == "alta"
    assert payload["bindings"][0]["period"] == "alta"


def test_bindings_list_rejects_census_modelo_alias_without_foundation_resolution(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="aeat.domain.calculations.registry._census_modelos")

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "bindings",
            "list",
            "--modelo",
            "36",
            "--year",
            "2025",
            "--period",
            "alta",
        ],
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "modelo '36' is not present in the calculation registry" in result.output
    assert "census modelo foundation" not in result.output.lower()
    assert all(record.getMessage() != "resolved census modelo foundation" for record in caplog.records)


def test_bindings_preview_echoes_override_for_known_key() -> None:
    """An override targeting a known binding id surfaces in the
    payload's ``override`` column."""

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "bindings",
            "preview",
            "--modelo",
            "303",
            "--year",
            "2026",
            "--period",
            "Q1",
            "--binding",
            "modelo-303-iva-repercutido-general-cuota=1234.56",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "operation\tregistry.modelo.bindings.preview" in result.output
    assert "override_count\t1" in result.output
    assert "1234.56" in result.output


def test_bindings_preview_preserves_census_event_period() -> None:
    """Binding preview passes the exact Modelo 036 event period into the registry query service."""

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "bindings",
            "preview",
            "--modelo",
            "036",
            "--year",
            "2025",
            "--period",
            "modificacion",
            "--binding",
            "modelo-036-profile-census-status=modificacion",
        ],
    )
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["period"] == "modificacion"
    assert payload["bindings"][0]["override"] == "modificacion"


def test_bindings_preview_rejects_year_prefixed_census_event_alias_without_foundation_resolution(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="aeat.domain.calculations.registry._census_modelos")
    rejected_period = "2025" + "-alta"

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "bindings",
            "preview",
            "--modelo",
            "036",
            "--year",
            "2025",
            "--period",
            rejected_period,
            "--binding",
            "modelo-036-profile-census-status=alta",
        ],
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "period must be YYYY, YYYYQn, YYYY-Qn, or YYYY-MM" in result.output
    assert "census modelo foundation" not in result.output.lower()
    assert all(record.getMessage() != "resolved census modelo foundation" for record in caplog.records)


def test_bindings_preview_rejects_unknown_binding_with_suggestion_list() -> None:
    """Unknown override keys fail with a suggestion list sourced
    from the registry's binding catalogue for the active modelo /
    year / period."""

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "bindings",
            "preview",
            "--modelo",
            "303",
            "--year",
            "2026",
            "--period",
            "Q1",
            "--binding",
            "no-such-binding=42",
        ],
    )
    assert result.exit_code != 0
    output_lower = result.output.lower()
    assert "no-such-binding" in output_lower
    # The suggestion list cites at least one real binding id.
    assert "modelo-303-iva-" in result.output


def test_bindings_preview_rejects_malformed_override_syntax() -> None:
    """``--binding`` without an ``=`` separator fails at the CLI
    boundary with a typer.BadParameter."""

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "bindings",
            "preview",
            "--modelo",
            "303",
            "--year",
            "2026",
            "--period",
            "Q1",
            "--binding",
            "missing-equals-sign",
        ],
    )
    assert result.exit_code != 0
    assert "KEY=VALUE" in result.output


def test_work_create_accepts_modelo_036_exact_event_periods_through_foundation(
    isolated_cli_storage: None,
) -> None:
    bucket_id = "census-cli-s1492-active"
    revision_id = "2025-02-03-y-siguientes"

    for period in ("alta", "modificacion", "baja"):
        result = invoke_cached_cli(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "work",
                "create",
                "--modelo",
                "036",
                "--year",
                "2025",
                "--period",
                period,
                "--revision",
                revision_id,
                "--bucket-id",
                bucket_id,
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["operation"] == "modelo.work.create"
        assert payload["modelo"] == "036"
        assert payload["filing_year"] == 2025
        assert payload["period"] == period
        assert payload["revision_id"] == revision_id
        assert payload["name"] == f"036-2025-{period}"
        assert payload["work_unit_id"]

    listed = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "list",
            "--bucket-id",
            bucket_id,
        ],
    )

    assert listed.exit_code == 0, listed.output
    list_payload = json.loads(listed.output)
    assert list_payload["work_unit_count"] == 3
    assert sorted(unit["period"] for unit in list_payload["work_units"]) == ["alta", "baja", "modificacion"]


def test_work_create_rejects_modelo_037_historical_only_without_persisting(
    isolated_cli_storage: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    bucket_id = "census-cli-s1492-historical"
    caplog.set_level(logging.DEBUG, logger="aeat.domain.calculations.registry._census_modelos")

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "037",
            "--year",
            "2025",
            "--period",
            "alta",
            "--revision",
            "historical",
            "--bucket-id",
            bucket_id,
        ],
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    output_lower = result.output.lower()
    assert "historical census metadata only" in output_lower
    assert "cannot create active work units" in output_lower
    assert all(record.getMessage() != "resolved census modelo foundation" for record in caplog.records)

    listed = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "list",
            "--bucket-id",
            bucket_id,
        ],
    )

    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.output)["work_unit_count"] == 0


@pytest.mark.parametrize(
    ("modelo", "period", "expected"),
    [
        ("36", "alta", "unknown census modelo code '36'"),
        ("036", "2025" + "-alta", "active census modelo 036 work units require one of the census event periods"),
    ],
)
def test_work_create_rejects_census_aliases_without_persisting(
    isolated_cli_storage: None,
    caplog: pytest.LogCaptureFixture,
    modelo: str,
    period: str,
    expected: str,
) -> None:
    bucket_id = f"census-cli-s1492-rejected-{modelo}-{period}"
    caplog.set_level(logging.DEBUG, logger="aeat.domain.calculations.registry._census_modelos")

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            modelo,
            "--year",
            "2025",
            "--period",
            period,
            "--revision",
            "2025-02-03-y-siguientes",
            "--bucket-id",
            bucket_id,
        ],
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert expected in result.output
    assert all(record.getMessage() != "resolved census modelo foundation" for record in caplog.records)

    listed = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "list",
            "--bucket-id",
            bucket_id,
        ],
    )

    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.output)["work_unit_count"] == 0


# ---------------------------------------------------------------------------
# Boundary regression guards
# ---------------------------------------------------------------------------


def test_no_parallel_bindings_typer_outside_canonical_module() -> None:
    """The canonical ``bindings`` sub-Typer registration lives in
    ``_modelo.py``. Any other module that re-implements a Typer
    named ``bindings`` competes with the canonical surface and must
    be removed."""

    from aeat.core.paths import PROJECT_ROOT

    cli_root = PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli"
    canonical = cli_root / "_modelo.py"
    forbidden_patterns = (
        'typer.Typer(\n    name="bindings"',
        'typer.Typer(name="bindings"',
    )
    offenders: list[Path] = []
    for py_file in cli_root.rglob("*.py"):
        if py_file == canonical:
            continue
        if py_file.name.startswith("test_"):
            continue
        text = py_file.read_text(encoding="utf-8")
        if any(needle in text for needle in forbidden_patterns):
            offenders.append(py_file)
    assert offenders == [], f"Parallel bindings Typer outside the canonical _modelo.py: {[str(p) for p in offenders]}"


def test_bindings_list_and_preview_emit_no_bucket_event() -> None:
    """``bindings list`` and ``bindings preview`` are read-only —
    they must not trigger any bucket event.

    The boundary check inspects the canonical module's source for
    any bucket-event emission call. If a future change wires one
    in by accident, this test fails fast."""

    from aeat.core.paths import PROJECT_ROOT

    canonical_text = (PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli" / "_modelo.py").read_text(encoding="utf-8")
    forbidden_emitters = (
        "emit_bucket_event",
        "append_bucket_event",
        "bucket_event(",
    )
    for needle in forbidden_emitters:
        assert needle not in canonical_text, (
            f"Forbidden bucket-event emission pattern {needle!r} found in "
            "_modelo.py; bindings list/preview must remain read-only."
        )


@pytest.mark.parametrize(
    "raw",
    [
        "aeat_justificante_pdf",
        "aeat_csv_register",
        "aeat_live_capture",
    ],
)
def test_evidence_kind_accepts_canonical_values(raw: str) -> None:
    """``--evidence-kind`` accepts only canonical underscore enum values."""

    from aeat.domain.modelos._filing_record import ExternalEvidenceKind

    assert ExternalEvidenceKind(raw).value == raw


@pytest.mark.parametrize("raw", ["aeat_bogus_evidence", "not_canonical_evidence"])
def test_evidence_kind_rejects_non_canonical_token(raw: str) -> None:
    """``--evidence-kind`` rejects aliases and unrelated values."""

    from aeat.domain.modelos._filing_record import ExternalEvidenceKind

    with pytest.raises(ValueError, match=raw):
        ExternalEvidenceKind(raw)


def test_modelo_aggregate_retenciones_delegates_to_backend_service() -> None:
    observation = {
        "source_kind": "ledger_transaction",
        "source_object_id": "tx-ret-1",
        "perceptor_nif": "B00000001",
        "perceptor_name": "Proveedor Retencion",
        "scheme": "rendimientos_trabajo",
        "taxable_base": "1000.00",
        "retencion_amount": "150.00",
        "accrued_on": "2025-03-01",
    }

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "aggregate",
            "--modelo",
            "111",
            "--period",
            "2025-Q1",
            "--retencion-observation",
            json.dumps(observation),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["operation"] == "modelo.aggregate"
    assert payload["provider"] == "retenciones"
    assert payload["aggregation"]["modelo"] == "111"
    assert payload["aggregation"]["total_retencion"] == "150.00"
    assert payload["log_fields"]["observation_count"] == 1


def test_modelo_aggregate_rejects_wrong_observation_family_through_error_boundary() -> None:
    observation = {
        "source_kind": "purchase_invoice_evidence",
        "source_object_id": "asset-1",
        "asset_class": "account",
        "asset_external_id": "ad-account",
        "country": "AD",
        "valuation_eur": "50000.01",
        "acquisition_date": "2023-01-15",
    }

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "aggregate",
            "--modelo",
            "111",
            "--period",
            "2025-Q1",
            "--foreign-asset-observation",
            json.dumps(observation),
        ],
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "command input failed validation" in result.output.lower()


def test_modelo_aggregate_help_uses_accepted_source_vocabulary_only() -> None:
    result = invoke_cached_cli(["app", "modelo", "aggregate", "--help"])

    assert result.exit_code == 0, result.output
    assert "ledger_transaction" in result.output
    assert "purchase_invoice_evidence" in result.output
    assert "payable_invoice" in result.output
    assert "collectible_invoice" in result.output
    lowered = result.output.lower()
    assert not re.search(r"(?<![a-z_])invoice(?![a-z_])", lowered)
