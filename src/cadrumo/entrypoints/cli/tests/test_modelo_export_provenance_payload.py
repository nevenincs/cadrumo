"""The CLI preserves the already public, redacted export audit join."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from cadrumo.application.modelo.export import ModeloExportResult, ModeloIvaWalletDecisionProvenance
from cadrumo.application.modelo.export_projection import ModeloFicheroBoePublicReceipt
from cadrumo.core.period import Period
from cadrumo.entrypoints.cli._modelo_payloads import ModeloExportPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("has_wallet", [True, False])
def test_cli_export_retains_canonical_redacted_wallet_join(has_wallet: bool) -> None:
    wallet = (
        ModeloIvaWalletDecisionProvenance(
            decision_ref="sha256:" + "d" * 64,
            selected_authority="official_observation",
            divergence="different_values",
            target_year=2025,
            target_period=Period.from_year_and_code(2025, "4T"),
            authority_source_kinds=("aeat_capture", "app_filing"),
            authority_source_refs=("sha256:" + "e" * 64, "sha256:" + "f" * 64),
        )
        if has_wallet
        else None
    )
    canonical = ModeloExportResult(
        calculation_revision_id="a" * 64,
        work_unit_id="b" * 64,
        bucket_id="99999999-9999-4999-8999-999999999999",
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        output_path=Path("modelo-303.boe"),
        byte_size=2948,
        file_sha256="c" * 64,
        format="fichero-boe",
        exported_at=datetime(2026, 4, 1, 9, tzinfo=UTC),
        actor="docs-sequence-sandbox",
        bucket_event_id="9" * 64,
        resolved_result_disposition=None,
        iva_wallet_decision_provenance=wallet,
    )
    payload = ModeloExportPayload.from_result(canonical)
    restored = ModeloExportPayload.model_validate_json(payload.model_dump_json())
    assert (
        restored.iva_wallet_decision_provenance
        == ModeloFicheroBoePublicReceipt.from_result(
            canonical,
        ).iva_wallet_decision_provenance
    )
    if wallet is None:
        assert restored.iva_wallet_decision_provenance is None
        return
    assert restored.iva_wallet_decision_provenance is not None
    assert restored.iva_wallet_decision_provenance.to_provenance() == wallet
    assert restored.iva_wallet_decision_provenance.model_dump(mode="json") == {
        "decision_ref": "sha256:" + "d" * 64,
        "selected_authority": "official_observation",
        "divergence": "different_values",
        "target_year": 2025,
        "target_period": {"filing_year": 2025, "code": "4T"},
        "authority_source_kinds": ["aeat_capture", "app_filing"],
        "authority_source_refs": ["sha256:" + "e" * 64, "sha256:" + "f" * 64],
    }
