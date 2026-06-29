"""Modelo export output-path and fichero emission tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core import Period
from ....domain.buckets import BucketEventType
from ....domain.deadlines import TaxpayerProfile
from ....domain.deadlines._models import IVARegime
from .._export import ModeloExportCommand, ModeloExportOutputPathError, export_modelo_revision
from ._export_modelo_303_support import _build_verified_modelo_303_revision
from ._export_test_support import isolated_backend_context

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_backend_context(tmp_path):
        yield


def test_export_modelo_303_wallet_only_revision_writes_fichero_with_redacted_wallet_provenance(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = _build_verified_modelo_303_revision()

    output_path = tmp_path / "modelo-303-wallet-only.txt"
    result = export_modelo_revision(
        ModeloExportCommand(
            calculation_revision_id=verified.calculation_revision_id,
            output_path=output_path,
            actor="operator",
        ),
        workflow_profile=TaxpayerProfile(tax_id=taxpayer_nif, iva_regime=IVARegime.GENERAL),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        bucket_event_repository=event_repo,
        clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
    )

    assert output_path.exists()
    assert result.modelo == "303"
    assert result.byte_size == output_path.stat().st_size
    assert result.file_sha256
    assert result.casilla_provenance
    provenance = result.iva_wallet_decision_provenance
    assert provenance is not None
    assert provenance.selected_authority == "aeat_wallet"
    assert provenance.divergence == "wallet_only"
    assert provenance.target_year == 2026
    assert provenance.target_period == Period.from_year_and_code(2026, "2T")
    assert provenance.decision_ref.startswith("sha256:")
    assert provenance.authority_source_kinds == ("aeat_wallet",)
    assert provenance.authority_source_refs[0].startswith("sha256:")

    event = event_repo.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,))[-1]
    assert event.payload["period"] == "2T"
    assert event.payload["iva_wallet_selected_authority"] == "aeat_wallet"
    assert event.payload["iva_wallet_divergence"] == "wallet_only"
    assert event.payload["iva_wallet_target_period"] == "2T"
    result_json = result.model_dump_json()
    event_json = event.model_dump_json()
    exported_text = output_path.read_text(encoding="utf-8")
    assert taxpayer_nif in exported_text
    assert taxpayer_nif not in result_json
    assert taxpayer_nif not in event_json
    assert "1200" not in result_json
    assert "1200" not in event_json
    assert "synthetic-modelo-303-export" not in result_json
    assert "synthetic-modelo-303-export" not in event_json


def test_export_refuses_existing_directory_output_and_leaves_no_tmp_orphan(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """EDGE-MED-1: exporting onto an existing directory is a clean typed refusal.

    The pre-fix behaviour wrote the fichero-BOE bytes to a sibling ``.tmp``,
    committed the event, then raised a raw ``OSError`` at the atomic rename
    onto the directory — surfacing a traceback AND stranding ~946 B of
    cleartext financial data in the orphaned ``.tmp`` file. Assert both the
    typed refusal and that no ``.tmp`` orphan remains on disk.
    """
    taxpayer_nif, _bucket_id, verified, work_repo, calc_repo, event_repo = _build_verified_modelo_303_revision()

    existing_dir = tmp_path / "already-a-directory"
    existing_dir.mkdir()
    tmp_sibling = existing_dir.with_name(existing_dir.name + ".tmp")

    with pytest.raises(ModeloExportOutputPathError):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=verified.calculation_revision_id,
                output_path=existing_dir,
                actor="operator",
            ),
            workflow_profile=TaxpayerProfile(tax_id=taxpayer_nif, iva_regime=IVARegime.GENERAL),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
        )

    assert existing_dir.is_dir()
    assert not tmp_sibling.exists(), "orphaned .tmp with cleartext financial bytes must not remain"
    assert not any(p.suffix == ".tmp" for p in tmp_path.rglob("*")), "no .tmp orphan anywhere under output root"


def test_export_refuses_empty_output_path(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """An empty / current-directory ``--output`` is refused before any write."""
    taxpayer_nif, _bucket_id, verified, work_repo, calc_repo, event_repo = _build_verified_modelo_303_revision()

    with pytest.raises(ModeloExportOutputPathError):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=verified.calculation_revision_id,
                output_path=Path(""),
                actor="operator",
            ),
            workflow_profile=TaxpayerProfile(tax_id=taxpayer_nif, iva_regime=IVARegime.GENERAL),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
        )
    assert not any(p.suffix == ".tmp" for p in tmp_path.rglob("*"))


def test_export_success_path_is_idempotent_overwrite(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """A valid file destination still exports, and a second export overwrites it cleanly."""
    taxpayer_nif, _bucket_id, verified, work_repo, calc_repo, event_repo = _build_verified_modelo_303_revision()
    output_path = tmp_path / "modelo-303.txt"
    profile = TaxpayerProfile(tax_id=taxpayer_nif, iva_regime=IVARegime.GENERAL)

    first = export_modelo_revision(
        ModeloExportCommand(
            calculation_revision_id=verified.calculation_revision_id,
            output_path=output_path,
            actor="operator",
        ),
        workflow_profile=profile,
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        bucket_event_repository=event_repo,
        clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
    )
    assert output_path.exists()
    assert first.byte_size == output_path.stat().st_size

    second = export_modelo_revision(
        ModeloExportCommand(
            calculation_revision_id=verified.calculation_revision_id,
            output_path=output_path,
            actor="operator",
        ),
        workflow_profile=profile,
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        bucket_event_repository=event_repo,
        clock=datetime(2026, 5, 21, 12, 4, tzinfo=UTC),
    )
    assert output_path.exists()
    assert second.file_sha256 == first.file_sha256
    assert not (output_path.with_name(output_path.name + ".tmp")).exists()
