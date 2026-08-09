"""Modelo export output-path and fichero emission tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core import PaymentElection, Period, ResultDisposition
from ....domain.buckets import BucketEventType
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.user_profile import UserProfileFact
from ...user_profile import projection_for_taxpayer, set_active_fields
from ...workflow import workflow_state_repository
from .._action_errors import ModeloChargeAccountMissingError, ModeloPaymentElectionCapabilityRefusedError
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
    assert result.resolved_result_disposition is ResultDisposition.NEGATIVA
    assert result.payment_election is None
    assert result.refund_election is None
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
    assert event.payload["resolved_result_disposition"] == ResultDisposition.NEGATIVA.value
    assert "refund_election" not in event.payload
    assert "payment_election" not in event.payload
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


def _project_persisted_charge_profile(*, charge_iban: str | None) -> TaxpayerProfile:
    """Project the stored active profile through its canonical taxpayer boundary."""
    facts = [
        UserProfileFact(path="filing_export.iban", value="ES9121000418450200051332"),
        UserProfileFact(path="filing_export.swift_bic", value="CHASUS33XXX"),
        UserProfileFact(path="filing_export.bank_name", value="Refund Only Bank"),
        UserProfileFact(path="filing_export.bank_address", value="Refund Street 1"),
        UserProfileFact(path="filing_export.bank_city", value="New York"),
        UserProfileFact(path="filing_export.bank_country_code", value="US"),
    ]
    if charge_iban is not None:
        facts.append(UserProfileFact(path="filing_export.charge_iban", value=charge_iban))
    workflow_state_repository().update(lambda state: set_active_fields(state, tuple(facts)))
    persisted = workflow_state_repository().load().active_profile_record()
    assert persisted is not None
    profile = projection_for_taxpayer(persisted)
    assert profile.iva.refund_account is not None
    assert profile.iva.refund_account.iban == "ES9121000418450200051332"
    if charge_iban is None:
        assert profile.iva.charge_account is None
    else:
        assert profile.iva.charge_account is not None
        assert profile.iva.charge_account.iban == charge_iban
    return profile


def test_public_domiciliacion_export_projects_persisted_charge_iban_to_did_only(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """Public export reaches S18's charge-only DID composer from persisted facts."""
    _taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = _build_verified_modelo_303_revision(
        positive_result=True,
    )
    charge_iban = "ES7921000813610123456789"
    output_path = tmp_path / "modelo-303-direct-debit.txt"

    result = export_modelo_revision(
        ModeloExportCommand(
            calculation_revision_id=verified.calculation_revision_id,
            output_path=output_path,
            actor="operator",
            payment_election=PaymentElection.DOMICILIACION,
        ),
        workflow_profile=_project_persisted_charge_profile(charge_iban=charge_iban),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        bucket_event_repository=event_repo,
        clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
    )

    exported = output_path.read_bytes().decode("latin-1")
    did_start = exported.index("<T303DID00>")
    did = exported[did_start : did_start + 823]
    assert did[22:56].rstrip() == charge_iban
    assert did[11:22].strip() == ""
    assert did[56:126].strip() == ""
    assert did[126:161].strip() == ""
    assert did[161:191].strip() == ""
    assert did[191:193].strip() == ""
    assert "ES9121000418450200051332" not in exported
    assert "CHASUS33XXX" not in exported
    assert "Refund Only Bank" not in exported

    assert result.resolved_result_disposition is ResultDisposition.DOMICILIACION
    assert result.payment_election is PaymentElection.DOMICILIACION
    assert result.refund_election is None
    event = event_repo.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,))[-1]
    assert event.payload["resolved_result_disposition"] == ResultDisposition.DOMICILIACION.value
    assert event.payload["payment_election"] == PaymentElection.DOMICILIACION.value
    assert "refund_election" not in event.payload
    result_json = result.model_dump_json()
    event_json = event.model_dump_json()
    assert charge_iban not in result_json
    assert charge_iban not in event_json
    assert "ES9121000418450200051332" not in result_json
    assert "ES9121000418450200051332" not in event_json


def test_public_domiciliacion_without_persisted_charge_account_refuses(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """A persisted refund account never becomes a public U debit fallback."""
    _taxpayer_nif, _bucket_id, verified, work_repo, calc_repo, event_repo = _build_verified_modelo_303_revision(
        positive_result=True,
    )
    output_path = tmp_path / "missing-charge-account.txt"

    with pytest.raises(ModeloChargeAccountMissingError):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=verified.calculation_revision_id,
                output_path=output_path,
                actor="operator",
                payment_election=PaymentElection.DOMICILIACION,
            ),
            workflow_profile=_project_persisted_charge_profile(charge_iban=None),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
        )

    assert not output_path.exists()


def test_public_cuenta_corriente_payment_election_is_capability_refused(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """G remains a typed but unavailable capability and never reads a charge account."""
    _taxpayer_nif, _bucket_id, verified, work_repo, calc_repo, event_repo = _build_verified_modelo_303_revision(
        positive_result=True,
    )
    output_path = tmp_path / "cuenta-corriente.txt"

    with pytest.raises(ModeloPaymentElectionCapabilityRefusedError):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=verified.calculation_revision_id,
                output_path=output_path,
                actor="operator",
                payment_election=PaymentElection.CUENTA_CORRIENTE,
            ),
            workflow_profile=_project_persisted_charge_profile(charge_iban="ES7921000813610123456789"),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
        )

    assert not output_path.exists()


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
