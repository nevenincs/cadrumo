"""Modelo export output-path and fichero emission tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ._export_test_support import isolated_backend

__all__ = ["isolated_backend"]

from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....application.calculations import (
    CalculationObservationRepository,
    ObservationSourceKind,
    ResultDispositionProjection,
)
from ....core import (
    ObservedHeaderFact,
    PaymentElection,
    Period,
    PriorDomiciliationElection,
    ResultDisposition,
)
from ....core.directory_scan import (
    iter_directory,
)
from ....domain.buckets import BucketEventType
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.deadlines import (
    ChargeAccount,
    IVARegime,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloIVAProfile,
    RefundAccount,
    TaxpayerProfile,
)
from ....domain.modelos import (
    CalculationRevisionAmendmentIdentity,
    CalculationRevisionAmendmentKind,
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordStatus,
    derive_calculation_revision_id_from_revision,
    derive_filing_record_id,
    upsert_calculation_revision,
    upsert_filing_record,
)
from .._action_errors import (
    ModeloChargeAccountMissingError,
    ModeloPaymentElectionCapabilityRefusedError,
    ModeloPaymentElectionIncompatibleError,
    ModeloRefundAccountMissingError,
)
from .._export import ModeloExportCommand, ModeloExportOutputPathError, export_modelo_revision
from .._revision_persistence import persist_filed_revision
from ._export_modelo_303_support import _build_verified_modelo_303_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


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
    assert "<T303DID00>" not in exported_text
    assert taxpayer_nif not in result_json
    assert taxpayer_nif not in event_json
    assert "1200" not in result_json
    assert "1200" not in event_json
    assert "synthetic-modelo-303-export" not in result_json
    assert "synthetic-modelo-303-export" not in event_json


def _typed_profile_with_charge_account(*, taxpayer_nif: str, charge_iban: str | None) -> TaxpayerProfile:
    """Build the real typed account input consumed by the export snapshot.

    Account selection is transient filing input.  It is not reconstructed from
    a persisted user-profile export namespace.
    """
    return TaxpayerProfile(
        tax_id=taxpayer_nif,
        iva_regime=IVARegime.GENERAL,
        iva=ModeloIVAProfile(
            tax_territory=M303TaxTerritory.COMMON_REGIME,
            regime_composition=M303RegimeComposition.GENERAL,
            redeme_enrolled=False,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=False,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
            charge_account=ChargeAccount(iban=charge_iban) if charge_iban is not None else None,
        ),
    )


def test_public_domiciliacion_export_selects_typed_charge_account_for_did_only(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """Public export reaches DID only through the typed selected-account snapshot."""
    taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = _build_verified_modelo_303_revision(
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
        workflow_profile=_typed_profile_with_charge_account(taxpayer_nif=taxpayer_nif, charge_iban=charge_iban),
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


def _with_rederived_id(revision):
    """Re-stamp a copied revision with the id its new content derives to.

    `model_copy` changes content without touching calculation_revision_id, and
    the id is content addressed over the amendment identity, so a copy that adds
    one carries an id the catalogue rejects as not matching its own content.
    """
    return revision.model_copy(
        update={"calculation_revision_id": derive_calculation_revision_id_from_revision(revision)},
    )


def _rectificativa_with_nota_three(verified):
    amended = verified.model_copy(
        update={
            "amendment_identity": CalculationRevisionAmendmentIdentity(
                kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
                amends_filing_record_id="a" * 64,
                m303_rectificativa_motive=None,
            ),
            "amendment_reason": "correct bank-transfer credit declared in casilla 111",
        }
    )
    return _with_rederived_id(amended)


def _nota_three_profile(*, taxpayer_nif: str, refund_account: RefundAccount | None) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=taxpayer_nif,
        iva_regime=IVARegime.GENERAL,
        iva=ModeloIVAProfile(
            tax_territory=M303TaxTerritory.COMMON_REGIME,
            regime_composition=M303RegimeComposition.GENERAL,
            redeme_enrolled=False,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=False,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
            refund_account=refund_account,
            charge_account=ChargeAccount(iban="ES7921000813610123456789"),
        ),
    )


def test_public_rectificativa_nota_three_keep_exports_full_refund_account_not_charge_account(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """A C rectificativa with stated c111 writes a refund destination under Nota 3."""
    taxpayer_nif, _bucket_id, verified, work_repo, calc_repo, event_repo = _build_verified_modelo_303_revision(
        negative_result=True,
        casilla_111=Decimal("0"),
    )
    assert verified.casilla_values["111"] == Decimal("0")
    rectificativa = _rectificativa_with_nota_three(verified)
    calc_repo.save(upsert_calculation_revision(calc_repo.load(), rectificativa))
    refund_account = RefundAccount(
        swift_bic="CHASUS33XXX",
        bank_name="Nota Three Refund Bank",
        bank_address="1 Refund Plaza",
        bank_city="New York",
        bank_country_code="US",
    )
    output_path = tmp_path / "modelo-303-n3-keep.txt"

    result = export_modelo_revision(
        ModeloExportCommand(
            calculation_revision_id=rectificativa.calculation_revision_id,
            output_path=output_path,
            actor="operator",
        ),
        workflow_profile=_nota_three_profile(taxpayer_nif=taxpayer_nif, refund_account=refund_account),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        bucket_event_repository=event_repo,
        clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
    )

    exported = output_path.read_text(encoding="latin-1")
    did_start = exported.index("<T303DID00>")
    did = exported[did_start : did_start + 823]
    assert did[11:22].rstrip() == refund_account.swift_bic
    assert did[22:56].strip() == ""
    assert did[56:126].rstrip() == refund_account.bank_name
    assert did[126:161].rstrip() == refund_account.bank_address
    assert did[161:191].rstrip() == refund_account.bank_city
    assert did[191:193].rstrip() == refund_account.bank_country_code
    assert did[193:194] == "3"
    assert "ES7921000813610123456789" not in exported
    assert result.resolved_result_disposition is ResultDisposition.COMPENSACION
    assert result.prior_domiciliation_election.election is PriorDomiciliationElection.KEEP


def test_public_rectificativa_nota_three_keep_refuses_without_refund_account_before_bytes_or_event(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """Nota 3 cannot emit an empty DID account block on a C rectificativa."""
    taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = _build_verified_modelo_303_revision(
        negative_result=True,
        casilla_111=Decimal("0"),
    )
    rectificativa = _rectificativa_with_nota_three(verified)
    calc_repo.save(upsert_calculation_revision(calc_repo.load(), rectificativa))
    output_path = tmp_path / "modelo-303-n3-missing-refund.txt"

    with pytest.raises(ModeloRefundAccountMissingError):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=rectificativa.calculation_revision_id,
                output_path=output_path,
                actor="operator",
            ),
            workflow_profile=_nota_three_profile(taxpayer_nif=taxpayer_nif, refund_account=None),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
        )

    assert not output_path.exists()
    assert not event_repo.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,))


def test_public_rectificativa_nota_three_remains_incompatible_with_current_domiciliacion(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """The pre-existing result-sign gate refuses c111 plus a current U election."""
    taxpayer_nif, _bucket_id, verified, work_repo, calc_repo, event_repo = _build_verified_modelo_303_revision(
        negative_result=True,
        casilla_111=Decimal("0"),
    )
    rectificativa = _rectificativa_with_nota_three(verified)
    calc_repo.save(upsert_calculation_revision(calc_repo.load(), rectificativa))
    output_path = tmp_path / "modelo-303-n3-current-u.txt"

    with pytest.raises(ModeloPaymentElectionIncompatibleError):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=rectificativa.calculation_revision_id,
                output_path=output_path,
                actor="operator",
                payment_election=PaymentElection.DOMICILIACION,
            ),
            workflow_profile=_nota_three_profile(taxpayer_nif=taxpayer_nif, refund_account=None),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
        )

    assert not output_path.exists()


def test_prior_domiciliation_export_and_filing_events_keep_the_safe_baseline_u_proof(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """Actual export and filing event ledgers retain proof coordinates, never accounts."""
    taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = _build_verified_modelo_303_revision(
        negative_result=True,
        casilla_111=Decimal("0"),
    )
    work_unit = work_repo.load().get(verified.work_unit_id)
    assert work_unit is not None
    filing_repository = ModeloRecordCatalogueRepository()
    baseline_evidence_reference = "CSV-303-2026-2T-S21"
    baseline_filing_record_id = derive_filing_record_id(
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id="a" * 64,
        filed_by="aeat-import",
    )
    baseline = ModeloRecord(
        filing_record_id=baseline_filing_record_id,
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id="a" * 64,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=datetime(2026, 5, 21, 11, 58, tzinfo=UTC),
        filed_by="aeat-import",
        aeat_accepted=True,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            reference_id=baseline_evidence_reference,
            imported_at=datetime(2026, 5, 21, 11, 58, tzinfo=UTC),
        ),
    )
    filing_repository.save(upsert_filing_record(filing_repository.load(), baseline))

    source_header_locator = "modelo-303-fichero-boe:modelo-303-page-01:declaration-type:13:1"
    CalculationObservationRepository().save(
        CalculationObservationRepository().prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="303",
                filing_year=work_unit.filing_year,
                period=work_unit.period.registry_token,
            ),
            source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            captured_at=datetime(2026, 5, 21, 11, 59, tzinfo=UTC),
            source_metadata={"aeat_justificante_csv": baseline_evidence_reference},
            source_headers=(
                ObservedHeaderFact(
                    header_key="declaration_type",
                    value=ResultDisposition.DOMICILIACION.value,
                    source_artefact_kind="submitted_file",
                    source_locator=source_header_locator,
                ),
            ),
            result_disposition=ResultDispositionProjection(
                disposition=ResultDisposition.DOMICILIACION,
                provenance_kind="source_header",
                provenance_locator=source_header_locator,
            ),
        )
    )
    _amended = verified.model_copy(
        update={
            "amendment_identity": CalculationRevisionAmendmentIdentity(
                kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
                amends_filing_record_id=baseline.filing_record_id,
                m303_rectificativa_motive=None,
            ),
            "amendment_reason": "correct prior direct-debit election",
        },
    )
    rectificativa = _with_rederived_id(_amended)
    calc_repo.save(upsert_calculation_revision(calc_repo.load(), rectificativa))

    output_path = tmp_path / "modelo-303-prior-domiciliation.txt"
    result = export_modelo_revision(
        ModeloExportCommand(
            calculation_revision_id=rectificativa.calculation_revision_id,
            output_path=output_path,
            actor="operator",
            prior_domiciliation_election=PriorDomiciliationElection.CANCEL_OR_MODIFY,
        ),
        workflow_profile=TaxpayerProfile(tax_id=taxpayer_nif, iva_regime=IVARegime.GENERAL),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        filing_repository=filing_repository,
        bucket_event_repository=event_repo,
        clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
    )
    export_event = event_repo.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,))[-1]
    expected_event_proof = {
        "prior_domiciliation_election": PriorDomiciliationElection.CANCEL_OR_MODIFY.value,
        "prior_domiciliation_baseline_filing_record_id": baseline.filing_record_id,
        "prior_domiciliation_baseline_evidence_reference_id": baseline_evidence_reference,
        "prior_domiciliation_baseline_result_disposition": ResultDisposition.DOMICILIACION.value,
        "prior_domiciliation_baseline_source_header_locator": source_header_locator,
    }
    assert {key: export_event.payload[key] for key in expected_event_proof} == expected_event_proof
    assert result.prior_domiciliation_election.baseline_source_header_locator == source_header_locator
    assert "<T303DID00>" not in output_path.read_text(encoding="latin-1")
    assert "iban" not in export_event.model_dump_json().casefold()

    filing = persist_filed_revision(
        target=rectificativa,
        work_unit=work_unit,
        work_units=work_repo.load(),
        notes=None,
        actor="operator",
        now=datetime(2026, 5, 21, 12, 4, tzinfo=UTC),
        calculation_repository=calc_repo,
        filing_repository=filing_repository,
        work_unit_repository=work_repo,
        bucket_event_repository=event_repo,
        result_disposition=result.resolved_result_disposition,
        prior_domiciliation_election=result.prior_domiciliation_election,
        taxpayer_nif=taxpayer_nif,
    )
    filed_event = event_repo.load().for_bucket(
        bucket_id,
        event_types=(BucketEventType.MODELO_FILED,),
    )[-1]
    assert filed_event.event_type is BucketEventType.MODELO_FILED
    assert filed_event.object_id == filing.filing_record_id
    assert {key: filed_event.payload[key] for key in expected_event_proof} == expected_event_proof
    assert "iban" not in filed_event.model_dump_json().casefold()


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
            workflow_profile=_typed_profile_with_charge_account(taxpayer_nif=_taxpayer_nif, charge_iban=None),
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
            workflow_profile=_typed_profile_with_charge_account(
                taxpayer_nif=_taxpayer_nif,
                charge_iban="ES7921000813610123456789",
            ),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
        )

    assert not output_path.exists()


def test_public_ingreso_export_omits_did_page(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """A public positive ingreso export omits DID rather than emitting an empty account page."""
    taxpayer_nif, _bucket_id, verified, work_repo, calc_repo, event_repo = _build_verified_modelo_303_revision(
        positive_result=True,
    )
    output_path = tmp_path / "modelo-303-ingreso.txt"

    result = export_modelo_revision(
        ModeloExportCommand(
            calculation_revision_id=verified.calculation_revision_id,
            output_path=output_path,
            actor="operator",
        ),
        workflow_profile=TaxpayerProfile(
            tax_id=taxpayer_nif,
            iva_regime=IVARegime.GENERAL,
        ),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        bucket_event_repository=event_repo,
        clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
    )

    assert result.resolved_result_disposition is ResultDisposition.INGRESO
    assert "<T303DID00>" not in output_path.read_text(encoding="utf-8")


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
    assert not any(p.suffix == ".tmp" for p in iter_directory(tmp_path, recursive=True)), (
        "no .tmp orphan anywhere under output root"
    )


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
    assert not any(p.suffix == ".tmp" for p in iter_directory(tmp_path, recursive=True))


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
