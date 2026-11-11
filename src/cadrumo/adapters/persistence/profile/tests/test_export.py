"""Real-behavior tests for ``export_modelo_revision``.

Covers the application-service safety gates (active-bucket required,
revision must exist, revision state must be exportable, work unit must
belong to the active bucket). Happy-path file emission is covered by
the CLI surface tests, which exercise the full registry-backed draft
build through a typer invocation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.modelo_export_support import isolated_backend
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

__all__ = ["isolated_backend"]
from pydantic import ValidationError

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.calculation_catalogue_tamper_support import (
    plant_calculation_revision_unchecked,
)
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import (
    empty_modelo_export_ports_for_test,
    modelo_export_ports_for_test,
)
from cadrumo.adapters.persistence.profile.tests.modelo_export_support import (
    M130_RENDIMIENTO_NETO_CASILLA,
    casilla_id_from_payload,
    export_taxpayer_profile,
    seed_profile,
    seed_revision,
)
from cadrumo.application.filing.export import export_layout_renderability_reason
from cadrumo.application.modelo.action_errors import (
    CalculationRevisionNotFoundError,
    ModeloCrossPeriodCleanStateError,
    ModeloRevisionNotSealedError,
)
from cadrumo.application.modelo.export import export_modelo_revision
from cadrumo.application.modelo.export_contracts import (
    ModeloExportCommand,
    ModeloExportCrossBucketRefusedError,
    ModeloExportNoActiveBucketError,
    ModeloExportResult,
    ModeloIvaWalletDecisionProvenance,
)
from cadrumo.application.operations.error_detail import build_operation_error_detail
from cadrumo.application.operations.next_step import OperationVerifyWorkStepV1
from cadrumo.core.config import override_settings
from cadrumo.core.errors.error_codes import ErrorCategory, get_registered_error_code
from cadrumo.core.period import Period
from cadrumo.domain.filing.schema import ModeloCasillaProvenance
from cadrumo.domain.modelos.calculation_repository import (
    CalculationRevisionPersistenceError,
)
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.errors import ModeloExportError

from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon


def test_export_readiness_reason_declares_an_unrenderable_layout() -> None:
    """The registry export contract identifies a missing layout explicitly."""
    reason = export_layout_renderability_reason("303", None)

    assert reason == "the registry snapshot has no complete export_layouts definition"


def test_export_result_json_surfaces_casilla_provenance(tmp_path: Path) -> None:
    result = ModeloExportResult(
        calculation_revision_id="a" * 64,
        work_unit_id="b" * 64,
        bucket_id="bucket-operator",
        modelo="130",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "1T"),
        output_path=tmp_path / "modelo-130.txt",
        byte_size=128,
        file_sha256="a" * 64,
        format="fichero-boe",
        exported_at=datetime(_YEAR, 5, 21, 12, 0, tzinfo=UTC),
        actor="operator",
        bucket_event_id="event-1",
        casilla_provenance=(
            ModeloCasillaProvenance(
                casilla_id=M130_RENDIMIENTO_NETO_CASILLA,
                legal_refs=("ley-35-2006:art-101",),
                source_refs=("aeat-modelo-130-manual-2026",),
            ),
        ),
    )

    payload = result.model_dump(mode="json")

    assert payload["period"] == {"filing_year": _YEAR, "code": "1T"}
    assert payload["local_evidence_status"] == "local_export_not_official_aeat_filing_evidence"
    assert "not official AEAT filing evidence" in payload["official_evidence_message"]
    assert "justificante" in payload["official_evidence_message"]
    assert "consulta de declaraciones presentadas" in payload["official_evidence_message"]
    assert "CSV cotejo" in payload["official_evidence_message"]
    assert "official_evidence_next_action" not in payload
    [provenance] = payload["casilla_provenance"]
    assert casilla_id_from_payload(provenance["casilla_id"]) == M130_RENDIMIENTO_NETO_CASILLA
    assert provenance["formula_id"] is None
    assert provenance["legal_refs"] == ["ley-35-2006:art-101"]
    assert provenance["source_refs"] == ["aeat-modelo-130-manual-2026"]


def test_export_result_json_surfaces_redacted_iva_wallet_decision_provenance(tmp_path: Path) -> None:
    result = ModeloExportResult(
        calculation_revision_id="a" * 64,
        work_unit_id="b" * 64,
        bucket_id="bucket-operator",
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "2T"),
        output_path=tmp_path / "modelo-303.txt",
        byte_size=128,
        file_sha256="a" * 64,
        format="fichero-boe",
        exported_at=datetime(_YEAR, 5, 21, 12, 0, tzinfo=UTC),
        actor="operator",
        bucket_event_id="event-1",
        iva_wallet_decision_provenance=ModeloIvaWalletDecisionProvenance(
            decision_ref="sha256:" + "1" * 64,
            selected_authority="aeat_wallet",
            divergence="wallet_only",
            target_year=_YEAR,
            target_period=Period.from_year_and_code(_YEAR, "2T"),
            authority_source_kinds=("aeat_wallet",),
            authority_source_refs=("sha256:" + "2" * 64,),
        ),
    )

    payload = result.model_dump(mode="json")

    assert payload["period"] == {"filing_year": _YEAR, "code": "2T"}
    assert payload["iva_wallet_decision_provenance"] == {
        "decision_ref": "sha256:" + "1" * 64,
        "selected_authority": "aeat_wallet",
        "divergence": "wallet_only",
        "target_year": _YEAR,
        "target_period": {"filing_year": _YEAR, "code": "2T"},
        "authority_source_kinds": ["aeat_wallet"],
        "authority_source_refs": ["sha256:" + "2" * 64],
    }


def test_iva_wallet_export_provenance_rejects_malformed_redacted_refs() -> None:
    with pytest.raises(ValidationError) as raised:
        ModeloIvaWalletDecisionProvenance(
            decision_ref="sha256:" + "1" * 64,
            selected_authority="aeat_wallet",
            divergence="wallet_only",
            target_year=_YEAR,
            target_period=Period.from_year_and_code(_YEAR, "2T"),
            authority_source_kinds=("aeat_wallet",),
            authority_source_refs=(" ",),
        )

    assert "authority_source_refs" in str(raised.value)


def test_export_refuses_when_no_active_bucket(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """Without an active profile bucket the service cannot scope the
    MODELO_EXPORTED event and must refuse cleanly."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        with pytest.raises(ModeloExportNoActiveBucketError) as exc_info, override_settings(cadrumo_active_profile=None):
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id="0" * 64,
                    output_path=tmp_path / "out.txt",
                    actor="operator",
                ),
                workflow_profile=export_taxpayer_profile(),
                export_ports=empty_modelo_export_ports_for_test(),
                operation=_authority_operation_for_test,
            )
        assert exc_info.value.translated_message == "application.modelo.errors.export_no_active_bucket"
        assert exc_info.value.context is None


def test_export_refuses_unknown_revision(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """An addressed calculation revision id that is not in the
    catalogue surfaces as CalculationRevisionNotFoundError."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        seed_profile()

        with pytest.raises(CalculationRevisionNotFoundError) as exc_info:
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id="f" * 64,
                    output_path=tmp_path / "out.txt",
                    actor="operator",
                ),
                workflow_profile=export_taxpayer_profile(),
                export_ports=modelo_export_ports_for_test(),
                operation=_authority_operation_for_test,
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
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        bucket_id = seed_profile()
        work_unit_id, calc_rev_id = seed_revision(bucket_id=bucket_id, state=CalculationRevisionState.BORRADOR)

        with pytest.raises(ModeloRevisionNotSealedError) as exc_info:
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=calc_rev_id,
                    output_path=tmp_path / "out.txt",
                    actor="operator",
                ),
                workflow_profile=export_taxpayer_profile(),
                export_ports=modelo_export_ports_for_test(),
                operation=_authority_operation_for_test,
            )
        assert exc_info.value.translated_message == "application.modelo.errors.export_revision_state_refused"
        assert exc_info.value.context == {
            "calculation_revision_id": calc_rev_id,
            "state": CalculationRevisionState.BORRADOR.value,
        }
        # The filer puts it right by checking the declaration, so it is refused, effect none, with that door.
        assert get_registered_error_code(exc_info.value).category is ErrorCategory.REFUSED
        detail = build_operation_error_detail(exc_info.value)
        assert detail is not None
        assert isinstance(detail.next_step, OperationVerifyWorkStepV1)
        assert detail.next_step.work_unit_id == work_unit_id
        assert detail.next_step.words.strip() != ""


def test_export_refuses_persisted_registry_revision_divergence(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """Export cannot replay stored values against a different registry schema."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        bucket_id = seed_profile()
        _, calc_rev_id = seed_revision(bucket_id=bucket_id, state=CalculationRevisionState.BORRADOR)
        repository = CalculationRevisionCatalogueRepository()
        revision = repository.load().get(calc_rev_id)
        assert revision is not None
        stale = revision.model_copy(
            update={
                "registry_snapshot_ref": revision.registry_snapshot_ref.model_copy(
                    update={"revision_id": "persisted-stale-revision"}
                )
            }
        )
        plant_calculation_revision_unchecked(repository.load(), stale)

        # The repository read refuses the planted row before the action reaches
        # its own divergence check.
        with pytest.raises(CalculationRevisionPersistenceError, match="disagrees with its parent WorkUnit"):
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=calc_rev_id,
                    output_path=tmp_path / "out.txt",
                    actor="operator",
                ),
                workflow_profile=export_taxpayer_profile(),
                export_ports=modelo_export_ports_for_test(),
                operation=_authority_operation_for_test,
            )


def test_export_reaches_modelo_100_xml_dictionary_path_before_later_readiness_gate(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        bucket_id = seed_profile()
        _, calc_rev_id = seed_revision(
            bucket_id=bucket_id,
            state=CalculationRevisionState.VERIFICADO_COMPLETO,
            modelo="100",
            filing_year=_YEAR - 1,
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
                workflow_profile=export_taxpayer_profile(),
                export_ports=modelo_export_ports_for_test(),
                operation=_authority_operation_for_test,
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
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        seed_profile()
        foreign_bucket_id = "other-bucket-7" * 4
        _, calc_rev_id = seed_revision(
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
                workflow_profile=export_taxpayer_profile(),
                export_ports=modelo_export_ports_for_test(),
                operation=_authority_operation_for_test,
            )
        assert exc_info.value.translated_message == "application.modelo.errors.export_cross_bucket_refused"
        assert isinstance(exc_info.value.context, dict)
        assert "work_unit_id" in exc_info.value.context


def test_m303_export_refuses_revision_missing_filing_evidence(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        bucket_id = seed_profile()
        _, calc_rev_id = seed_revision(
            bucket_id=bucket_id,
            state=CalculationRevisionState.VERIFICADO_COMPLETO,
            modelo="303",
            filing_year=_YEAR,
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
                workflow_profile=export_taxpayer_profile(),
                export_ports=modelo_export_ports_for_test(),
                operation=_authority_operation_for_test,
            )

        assert isinstance(exc_info.value.context, dict)
        # The cause is identified by its registered error type, not by prose: the
        # producer now carries a declared precondition failure instead of a
        # sentence this assertion could match on.
        assert exc_info.value.context["cause_type"] == "M303FilingEvidenceError"
        assert not output.exists()
        assert not output.with_name(output.name + ".tmp").exists()
