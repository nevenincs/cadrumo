"""Real-behavior tests for ``export_modelo_revision``.

Covers the application-service safety gates (active-bucket required,
revision must exist, revision state must be exportable, work unit must
belong to the active bucket). Happy-path file emission is covered by
the CLI surface tests, which exercise the full registry-backed draft
build through a typer invocation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ._export_test_support import isolated_backend

__all__ = ["isolated_backend"]
from pydantic import ValidationError

from ....core import Period
from ....core.config import override_settings
from ....domain.filing import ModeloCasillaProvenance
from ....domain.iva_compensation import (
    IvaCompensationAuthoritySource,
    IvaCompensationReconciliationDecision,
)
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.modelos.errors import ModeloExportError
from .._action_errors import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloCrossPeriodCleanStateError,
)
from .._export import (
    ModeloExportCommand,
    ModeloExportCrossBucketRefusedError,
    ModeloExportNoActiveBucketError,
    ModeloExportResult,
    ModeloIvaWalletDecisionProvenance,
    _modelo_export_layout_readiness_refusal,
    export_modelo_revision,
    iva_wallet_decision_export_provenance,
)
from ._export_test_support import (
    _M130_RENDIMIENTO_NETO_CASILLA,
    _casilla_id_from_payload,
    _profile,
    _seed_profile,
    _seed_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_export_readiness_refusal_declares_and_binds_the_catalogue_action() -> None:
    """The application projects an unrenderable layout; the CLI only resolves it."""
    refusal = _modelo_export_layout_readiness_refusal(modelo="303", layout=None)

    assert refusal is not None
    assert refusal.reason == "the registry snapshot has no complete export_layouts definition"
    verdict = refusal.precondition_failure.verdict
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.describe"
    assert verdict.no_recovery_outcome is None
    assert verdict.argument_bindings[0].value == "303"


def test_export_result_json_surfaces_casilla_provenance(tmp_path: Path) -> None:
    result = ModeloExportResult(
        calculation_revision_id="a" * 64,
        work_unit_id="b" * 64,
        bucket_id="bucket-operator",
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        output_path=tmp_path / "modelo-130.txt",
        byte_size=128,
        file_sha256="a" * 64,
        format="fichero-boe",
        exported_at=datetime(2026, 5, 21, 12, 0, tzinfo=UTC),
        actor="operator",
        bucket_event_id="event-1",
        casilla_provenance=(
            ModeloCasillaProvenance(
                casilla_id=_M130_RENDIMIENTO_NETO_CASILLA,
                legal_refs=("ley-35-2006:art-101",),
                source_refs=("aeat-modelo-130-manual-2026",),
            ),
        ),
    )

    payload = result.model_dump(mode="json")

    assert payload["period"] == {"filing_year": 2026, "code": "1T"}
    assert payload["local_evidence_status"] == "local_export_not_official_aeat_filing_evidence"
    assert "not official AEAT filing evidence" in payload["official_evidence_message"]
    assert "justificante" in payload["official_evidence_message"]
    assert "consulta de declaraciones presentadas" in payload["official_evidence_message"]
    assert "CSV cotejo" in payload["official_evidence_message"]
    assert "official_evidence_next_action" not in payload
    [provenance] = payload["casilla_provenance"]
    assert _casilla_id_from_payload(provenance["casilla_id"]) == _M130_RENDIMIENTO_NETO_CASILLA
    assert provenance["formula_id"] is None
    assert provenance["legal_refs"] == ["ley-35-2006:art-101"]
    assert provenance["source_refs"] == ["aeat-modelo-130-manual-2026"]


def test_export_result_json_surfaces_redacted_iva_wallet_decision_provenance(tmp_path: Path) -> None:
    result = ModeloExportResult(
        calculation_revision_id="a" * 64,
        work_unit_id="b" * 64,
        bucket_id="bucket-operator",
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "2T"),
        output_path=tmp_path / "modelo-303.txt",
        byte_size=128,
        file_sha256="a" * 64,
        format="fichero-boe",
        exported_at=datetime(2026, 5, 21, 12, 0, tzinfo=UTC),
        actor="operator",
        bucket_event_id="event-1",
        iva_wallet_decision_provenance=ModeloIvaWalletDecisionProvenance(
            decision_ref="sha256:" + "1" * 64,
            selected_authority="aeat_wallet",
            divergence="wallet_only",
            target_year=2026,
            target_period=Period.from_year_and_code(2026, "2T"),
            authority_source_kinds=("aeat_wallet",),
            authority_source_refs=("sha256:" + "2" * 64,),
        ),
    )

    payload = result.model_dump(mode="json")

    assert payload["period"] == {"filing_year": 2026, "code": "2T"}
    assert payload["iva_wallet_decision_provenance"] == {
        "decision_ref": "sha256:" + "1" * 64,
        "selected_authority": "aeat_wallet",
        "divergence": "wallet_only",
        "target_year": 2026,
        "target_period": {"filing_year": 2026, "code": "2T"},
        "authority_source_kinds": ["aeat_wallet"],
        "authority_source_refs": ["sha256:" + "2" * 64],
    }


def test_iva_wallet_export_provenance_rejects_malformed_redacted_refs() -> None:
    with pytest.raises(ValidationError) as raised:
        ModeloIvaWalletDecisionProvenance(
            decision_ref="sha256:" + "1" * 64,
            selected_authority="aeat_wallet",
            divergence="wallet_only",
            target_year=2026,
            target_period=Period.from_year_and_code(2026, "2T"),
            authority_source_kinds=("aeat_wallet",),
            authority_source_refs=(" ",),
        )

    assert "authority_source_refs" in str(raised.value)


def test_iva_wallet_export_provenance_redacts_taxpayer_amounts_and_source_locators() -> None:
    decided_at = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    decision = IvaCompensationReconciliationDecision(
        taxpayer_nif="synthetic-sensitive-marker",
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
        selected_authority="aeat_wallet",
        selected_amount=Decimal("1200.00"),
        wallet_amount=Decimal("1200.00"),
        local_recurrence_amount=None,
        override_amount=None,
        divergence="wallet_only",
        blocked=False,
        stale_wallet=False,
        reason_identity="aeat_wallet_uncrosschecked",
        wallet_captured_at=decided_at,
        authority_sources=(
            IvaCompensationAuthoritySource(
                source_kind="aeat_wallet",
                amount=Decimal("1200.00"),
                source_locator="aeat-wallet-reference-containing-synthetic-sensitive-marker",
                captured_at=decided_at,
            ),
        ),
        decided_at=decided_at,
    )

    provenance = iva_wallet_decision_export_provenance(decision)

    assert provenance is not None
    payload_text = provenance.model_dump_json()
    assert provenance.selected_authority == "aeat_wallet"
    assert provenance.divergence == "wallet_only"
    assert provenance.decision_ref.startswith("sha256:")
    assert provenance.authority_source_refs[0].startswith("sha256:")
    assert "synthetic-sensitive-marker" not in payload_text
    assert "1200" not in payload_text
    assert "aeat-wallet-reference" not in payload_text


def test_export_refuses_when_no_active_bucket(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """Without an active profile bucket the service cannot scope the
    MODELO_EXPORTED event and must refuse cleanly."""

    with pytest.raises(ModeloExportNoActiveBucketError) as exc_info, override_settings(cadrumo_active_profile=None):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id="0" * 64,
                output_path=tmp_path / "out.txt",
                actor="operator",
            ),
            workflow_profile=_profile(),
        )
    assert exc_info.value.translated_message == "application.modelo.errors.export_no_active_bucket"
    assert exc_info.value.context is None


def test_export_refuses_unknown_revision(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """An addressed calculation revision id that is not in the
    catalogue surfaces as CalculationRevisionNotFoundError."""

    _seed_profile()

    with pytest.raises(CalculationRevisionNotFoundError) as exc_info:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id="f" * 64,
                output_path=tmp_path / "out.txt",
                actor="operator",
            ),
            workflow_profile=_profile(),
        )
    assert exc_info.value.translated_message == "application.modelo.errors.calculation_revision_not_found"
    assert exc_info.value.context == {"calculation_revision_id": "f" * 64}


def test_export_refuses_borrador_revision(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """A revision still in BORRADOR state cannot be exported; only
    verificado-completo or filed revisions are legal export sources.

    The export artefact must reflect a revision the operator has
    already verified, not a work-in-progress."""

    bucket_id = _seed_profile()
    _, calc_rev_id = _seed_revision(bucket_id=bucket_id, state=CalculationRevisionState.BORRADOR)

    with pytest.raises(CalculationRevisionStateError) as exc_info:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=calc_rev_id,
                output_path=tmp_path / "out.txt",
                actor="operator",
            ),
            workflow_profile=_profile(),
        )
    assert exc_info.value.translated_message == "application.modelo.errors.export_revision_state_refused"
    assert exc_info.value.context == {
        "calculation_revision_id": calc_rev_id,
        "state": CalculationRevisionState.BORRADOR.value,
    }


def test_export_reaches_modelo_100_xml_dictionary_path_before_later_readiness_gate(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    bucket_id = _seed_profile()
    _, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="100",
        filing_year=2025,
        period="0A",
    )
    out = tmp_path / "modelo-100.xml"

    with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=calc_rev_id,
                output_path=out,
                actor="operator",
            ),
            workflow_profile=_profile(),
        )

    assert exc_info.value.translated_message == "application.modelo.errors.cross_period_clean_state_incomplete"
    assert "export_unsupported" not in str(exc_info.value.context)
    assert "fixed_width" not in str(exc_info.value.context)
    assert not out.exists()
    assert not out.with_name(out.name + ".tmp").exists()


def test_export_refuses_cross_bucket_revision(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """A revision whose parent work unit lives in a non-active bucket
    is refused. Allowing the service to emit the MODELO_EXPORTED
    event into a foreign bucket would let any caller pollute another
    operator's history."""

    _seed_profile()
    foreign_bucket_id = "other-bucket-7" * 4
    _, calc_rev_id = _seed_revision(
        bucket_id=foreign_bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
    )

    with pytest.raises(ModeloExportCrossBucketRefusedError) as exc_info:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=calc_rev_id,
                output_path=tmp_path / "out.txt",
                actor="operator",
            ),
            workflow_profile=_profile(),
        )
    assert exc_info.value.translated_message == "application.modelo.errors.export_cross_bucket_refused"
    assert isinstance(exc_info.value.context, dict)
    assert "work_unit_id" in exc_info.value.context


def test_m303_export_refuses_revision_missing_filing_evidence(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    bucket_id = _seed_profile()
    _, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="303",
        filing_year=2026,
        period="1T",
    )
    output = tmp_path / "modelo-303.txt"

    with pytest.raises(ModeloExportError) as exc_info:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=calc_rev_id,
                output_path=output,
                actor="operator",
            ),
            workflow_profile=_profile(),
        )

    assert isinstance(exc_info.value.context, dict)
    # The cause is identified by its registered error type, not by prose: the
    # producer now carries a declared precondition failure instead of a
    # sentence this assertion could match on.
    assert exc_info.value.context["cause_type"] == "M303FilingEvidenceError"
    assert not output.exists()
    assert not output.with_name(output.name + ".tmp").exists()
