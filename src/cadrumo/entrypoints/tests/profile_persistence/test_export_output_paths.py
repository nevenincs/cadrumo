"""Modelo export output-path and fichero emission tests."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from cadrumo.adapters.inbound.pdf.source_provenance import source_pdf_reference_path
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
from cadrumo.adapters.persistence.profile.tests.modelo_export_support import isolated_backend
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test
from cadrumo.domain.calculations.registry.tests.registry_observations import (
    registry_grounded_observations,
    revision_id_for_observation,
)

__all__ = ["isolated_backend"]

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.own_accounts import OwnAccountRepository
from cadrumo.adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.profile.tests.filing_report_support import seed_filing_gate_report
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.application.calculations.observations_repository import ObservationSourceKind, ResultDispositionProjection
from cadrumo.application.modelo.action_errors import (
    ModeloChargeAccountMissingError,
    ModeloPaymentElectionCapabilityRefusedError,
    ModeloPaymentElectionIncompatibleError,
    ModeloRefundAccountMissingError,
)
from cadrumo.application.modelo.export import (
    ModeloExportAccountReference,
    ModeloExportCommand,
    ModeloExportResult,
    export_modelo_revision,
)
from cadrumo.application.modelo.export_sink import ModeloExportOutputPathError
from cadrumo.application.modelo.revision_persistence import persist_filed_revision
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.directory_scan import (
    iter_directory,
)
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.observed_header_fact import ObservedHeaderFact
from cadrumo.core.payment_election import PaymentElection
from cadrumo.core.period import Period
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.deadlines.models import (
    IVARegime,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloIVAProfile,
    TaxpayerProfile,
)
from cadrumo.domain.filing.software_identity import (
    AeatProductSoftwareEvidence,
    AeatProductSoftwareIdentity,
    AeatSoftwareIdentityGrade,
)
from cadrumo.domain.justificante.schema import Justificante
from cadrumo.domain.modelos.calculation_repository import upsert_calculation_revision
from cadrumo.domain.modelos.calculation_revision import (
    derive_calculation_revision_id_from_revision,
)
from cadrumo.domain.modelos.calculation_revision_aggregate import CalculationRevisionAggregateContext
from cadrumo.domain.modelos.calculation_revision_amendment import (
    CalculationRevisionAmendmentIdentity,
    CalculationRevisionAmendmentKind,
    M303RectificativaMotive,
)
from cadrumo.domain.modelos.errors import (
    ModeloExportPriorDomiciliationElectionRequiredError,
)
from cadrumo.domain.modelos.filing_record import (
    AeatConfirmationState,
    ExternalEvidence,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from cadrumo.domain.modelos.filing_repository import upsert_filing_record
from cadrumo.domain.transactions.own_accounts import (
    OwnAccountDesignation,
    OwnAccountHolding,
    OwnAccountRegister,
    OwnAccountRole,
    OwnBankAccountDetails,
)
from cadrumo.entrypoints.tests.profile_persistence.modelo_303_export_support import build_verified_modelo_303_revision
from cadrumo.tests.aeat_literal_fixtures import justificante_cotejo_url

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _product_software_identity() -> AeatProductSoftwareIdentity:
    return AeatProductSoftwareIdentity(
        program_identifier="C303",
        developer_tax_id="Y0000001S",
        evidence=(
            AeatProductSoftwareEvidence(
                reference="aeat-software-registration:export-output-paths",
                digest="a" * 64,
            ),
        ),
    )


def test_export_modelo_303_wallet_only_revision_writes_fichero_with_redacted_wallet_provenance(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            operation=_authority_operation_for_test,
        )

        output_path = tmp_path / "modelo-303-wallet-only.txt"
        result = export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=verified.calculation_revision_id,
                output_path=output_path,
                actor="operator",
                prior_domiciliation_election=PriorDomiciliationElection.KEEP,
            ),
            workflow_profile=_typed_profile_with_charge_account(taxpayer_nif=taxpayer_nif, charge_iban=None),
            export_ports=modelo_export_ports_for_test(
                product_software_identity=_product_software_identity(),
                bucket_id=bucket_id,
                taxpayer_tax_id=taxpayer_nif,
                work_unit=work_repo,
                calculation=calc_repo,
                bucket_event=event_repo,
            ),
            clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
            operation=_authority_operation_for_test,
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


def test_export_modelo_303_stamps_the_development_identity_into_the_developer_header_fields(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """Without a registered developer identity the DP30300 header carries the all-zero mock, graded as such.

    The official Modelo 303 record design reserves positions 93-96 for the
    program version and 101-109 for the developer NIF; neither may be taken
    from the taxpayer, so the mock fills exactly those bytes and the result
    reports it as the development identity.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            operation=_authority_operation_for_test,
        )
        output_path = tmp_path / "modelo-303-development-identity.txt"

        result = export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=verified.calculation_revision_id,
                output_path=output_path,
                actor="operator",
                prior_domiciliation_election=PriorDomiciliationElection.KEEP,
            ),
            workflow_profile=_typed_profile_with_charge_account(taxpayer_nif=taxpayer_nif, charge_iban=None),
            export_ports=modelo_export_ports_for_test(
                bucket_id=bucket_id,
                taxpayer_tax_id=taxpayer_nif,
                work_unit=work_repo,
                calculation=calc_repo,
                bucket_event=event_repo,
            ),
            clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
            operation=_authority_operation_for_test,
        )

        written = output_path.read_bytes()
        prefix_start = written.index(b"<T3030")
        # The all-zero values the development mock identity fact declares.
        assert written[prefix_start + 92 : prefix_start + 96] == b"0000"
        assert written[prefix_start + 100 : prefix_start + 109] == b"X0000000T"
        assert taxpayer_nif.encode("ascii") not in written[prefix_start + 100 : prefix_start + 109]
        assert result.software_identity_grade is AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK
        assert event_repo.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,))


def test_export_modelo_303_without_a_prior_domiciliation_election_keeps_it(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """KEEP is the neutral default: an ordinary 303 with no election exports with a blank page-3 marker."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            operation=_authority_operation_for_test,
        )
        output_path = tmp_path / "modelo-303-without-election.txt"

        result = export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=verified.calculation_revision_id,
                output_path=output_path,
                actor="operator",
            ),
            workflow_profile=_typed_profile(taxpayer_nif=taxpayer_nif),
            export_ports=modelo_export_ports_for_test(
                bucket_id=bucket_id,
                taxpayer_tax_id=taxpayer_nif,
                work_unit=work_repo,
                calculation=calc_repo,
                bucket_event=event_repo,
            ),
            clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
            operation=_authority_operation_for_test,
        )

        assert result.prior_domiciliation_election.election is PriorDomiciliationElection.KEEP
        event = event_repo.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,))[-1]
        assert event.payload["prior_domiciliation_election"] == PriorDomiciliationElection.KEEP.value
        assert output_path.exists()


def test_export_modelo_303_rectificativa_stating_casilla_111_requires_the_election(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """Only a rectificativa with casilla 111 must choose: KEEP puts the Nota 3 refund account on DID, X does not."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            negative_result=True,
            casilla_111=Decimal("0"),
            operation=_authority_operation_for_test,
        )
        rectificativa = _persist_rectificativa_with_nota_three(
            verified,
            taxpayer_nif=taxpayer_nif,
            work_repo=work_repo,
            calc_repo=calc_repo,
            operation=_authority_operation_for_test,
        )
        output_path = tmp_path / "modelo-303-n3-without-election.txt"

        with pytest.raises(ModeloExportPriorDomiciliationElectionRequiredError) as refused:
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=rectificativa.calculation_revision_id,
                    output_path=output_path,
                    actor="operator",
                ),
                workflow_profile=_nota_three_profile(
                    taxpayer_nif=taxpayer_nif, bucket_id=bucket_id, refund_account=None
                ),
                export_ports=modelo_export_ports_for_test(
                    product_software_identity=_product_software_identity(),
                    taxpayer_tax_id=taxpayer_nif,
                    work_unit=work_repo,
                    calculation=CalculationRevisionCatalogueRepository(m303_rectificativa_taxpayer_tax_id=taxpayer_nif),
                    bucket_event=event_repo,
                ),
                clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
                operation=_authority_operation_for_test,
            )

        assert get_registered_error_code(refused.value).code == (
            "REFUSED_MODELO_EXPORT_PRIOR_DOMICILIATION_ELECTION_REQUIRED"
        )
        assert refused.value.context == {
            "calculation_revision_id": rectificativa.calculation_revision_id,
            "modelo": "303",
        }
        assert not output_path.exists()
        assert not event_repo.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,))


def _typed_profile(*, taxpayer_nif: str) -> TaxpayerProfile:
    """Build the typed IVA profile; it holds no account, which the ledger register owns."""
    return TaxpayerProfile(
        tax_id=taxpayer_nif,
        iva_regime=IVARegime("GENERAL"),
        iva=ModeloIVAProfile(
            tax_territory=M303TaxTerritory.from_registry("common_regime"),
            regime_composition=M303RegimeComposition.from_registry("general"),
            redeme_enrolled=False,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=False,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
        ),
    )


def _own_account(label: str, iban: str, **bank_block: str) -> OwnBankAccountDetails:
    return OwnBankAccountDetails(label=label, holding=OwnAccountHolding.TITULAR, iban=iban, **bank_block)


def _register_own_account(
    bucket_id: str,
    details: OwnBankAccountDetails,
    *,
    designate: tuple[OwnAccountRole, ...] = (),
) -> str:
    """Add an own account to the bucket's encrypted register, designated for ``designate``."""

    def change(register: OwnAccountRegister) -> OwnAccountRegister:
        account_id = register.next_account_id()
        added = register.with_new_account(details)
        for role in designate:
            added = added.with_designation(OwnAccountDesignation(role=role, own_account_id=account_id))
        return added

    return OwnAccountRepository(bucket_id=bucket_id).mutate(change).accounts[-1].own_account_id


def _typed_profile_with_charge_account(
    *, taxpayer_nif: str, charge_iban: str | None, bucket_id: str | None = None
) -> TaxpayerProfile:
    """Build the typed profile, designating ``charge_iban`` as the bucket's charge own account."""
    if charge_iban is not None:
        assert bucket_id is not None
        _register_own_account(bucket_id, _own_account("Cargo", charge_iban), designate=(OwnAccountRole.CHARGE,))
    return _typed_profile(taxpayer_nif=taxpayer_nif)


def test_public_domiciliacion_export_selects_typed_charge_account_for_did_only(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """Public export reaches DID only through the typed selected-account snapshot."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            positive_result=True,
            operation=_authority_operation_for_test,
        )
        charge_iban = "ES7921000813610123456789"
        output_path = tmp_path / "modelo-303-direct-debit.txt"

        result = export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=verified.calculation_revision_id,
                output_path=output_path,
                actor="operator",
                prior_domiciliation_election=PriorDomiciliationElection.KEEP,
                payment_election=PaymentElection.DOMICILIACION,
            ),
            workflow_profile=_typed_profile_with_charge_account(
                taxpayer_nif=taxpayer_nif, charge_iban=charge_iban, bucket_id=bucket_id
            ),
            export_ports=modelo_export_ports_for_test(
                product_software_identity=_product_software_identity(),
                bucket_id=bucket_id,
                taxpayer_tax_id=taxpayer_nif,
                work_unit=work_repo,
                calculation=calc_repo,
                bucket_event=event_repo,
            ),
            clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
            operation=_authority_operation_for_test,
        )

        exported = output_path.read_bytes().decode("latin-1")
        # DR303 page 01000 position 13: Tipo Declaración.
        assert exported[exported.index("<T30301000>") + 12] == "U"
        did_start = exported.index("<T303DID00>")
        did = exported[did_start : did_start + 823]
        assert did[22:56].rstrip() == charge_iban
        # Position 194 is "Devolución - Marca SEPA": a charge account leaves it "0" (Vacía).
        assert did[193] == "0"
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
        # The 2026 1T window declares no payment cutoff: the U export advises, never refuses.
        assert result.domiciliation_cutoff_unverified is True
        assert result.selected_account == ModeloExportAccountReference(
            role=OwnAccountRole.CHARGE, own_account_id="acc-01"
        )
        event = event_repo.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,))[-1]
        assert event.payload["resolved_result_disposition"] == ResultDisposition.DOMICILIACION.value
        assert event.payload["payment_election"] == PaymentElection.DOMICILIACION.value
        assert event.payload["selected_account_role"] == "charge"
        assert event.payload["selected_own_account_id"] == "acc-01"
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


def _baseline_justificante(csv: str, *, work_unit, taxpayer_nif: str, presented_at: datetime) -> Justificante:
    """The persisted receipt an AEAT-accepted baseline filing resolves to."""
    pdf_sha256 = hashlib.sha256(f"justificante {csv}".encode()).hexdigest()
    return Justificante(
        csv=csv,
        modelo="303",
        period=work_unit.period,
        ejercicio=str(work_unit.filing_year),
        presentation_id="3030000000001",
        presented_at=presented_at,
        tax_id=taxpayer_nif,
        total_a_ingresar=None,
        total_a_devolver=None,
        verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
        source_pdf_path=source_pdf_reference_path(pdf_sha256),
        source_pdf_sha256=pdf_sha256,
        parsed_at=presented_at,
    )


def _persist_rectificativa_with_nota_three(
    verified,
    *,
    taxpayer_nif: str,
    work_repo,
    calc_repo,
    operation,
):
    """Persist a C rectificativa over a real AEAT-accepted original.

    A rectificativa validates against its whole evidence chain: the filed
    original it amends, that filing's justificante carrying the original
    receipt number, a persisted motive, and the selected registry snapshot.
    """
    csv = "CSV3032026N3ORIGINAL"
    filed_at = datetime(2026, 5, 20, 9, 0, tzinfo=UTC)
    work_unit = work_repo.load().get(verified.work_unit_id)
    original = ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=verified.work_unit_id,
            calculation_revision_id=verified.calculation_revision_id,
            filed_by="aeat-import",
        ),
        work_unit_id=verified.work_unit_id,
        calculation_revision_id=verified.calculation_revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=filed_at,
        filed_by="aeat-import",
        origin=FilingOrigin.AEAT,
        confirmation=AeatConfirmationState.CONFIRMADA,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id=csv,
            imported_at=filed_at,
        ),
    )
    filing_repo = ModeloRecordCatalogueRepository()
    filing_repo.save(upsert_filing_record(filing_repo.load(), original))
    justificante = _baseline_justificante(csv, work_unit=work_unit, taxpayer_nif=taxpayer_nif, presented_at=filed_at)
    JustificanteRepository().save(justificante)
    amended = verified.model_copy(
        update={
            "amendment_identity": CalculationRevisionAmendmentIdentity(
                kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
                amends_filing_record_id=original.filing_record_id,
                m303_rectificativa_motive=M303RectificativaMotive.RECTIFICACIONES,
            ),
            "amendment_reason": "correct bank-transfer credit declared in casilla 111",
        }
    )
    rectificativa = _with_rederived_id(amended)
    context = CalculationRevisionAggregateContext(
        work_units=work_repo.load(),
        filing_records=filing_repo.load(),
        justificantes=(justificante,),
        registry_snapshots={
            work_unit.work_unit_id: operation.snapshot(
                "303", filing_year=work_unit.filing_year, period=work_unit.period.registry_token
            )
        },
        expected_taxpayer_tax_id=taxpayer_nif,
    )
    calc_repo.save(upsert_calculation_revision(calc_repo.load(), rectificativa, aggregate_context=context))
    return rectificativa


def _nota_three_profile(
    *, taxpayer_nif: str, bucket_id: str, refund_account: OwnBankAccountDetails | None
) -> TaxpayerProfile:
    """Designate a charge account always, and the refund account when given: Nota 3 must pick the refund one."""
    _register_own_account(
        bucket_id, _own_account("Cargo", "ES7921000813610123456789"), designate=(OwnAccountRole.CHARGE,)
    )
    if refund_account is not None:
        _register_own_account(bucket_id, refund_account, designate=(OwnAccountRole.REFUND,))
    return _typed_profile(taxpayer_nif=taxpayer_nif)


def test_public_rectificativa_nota_three_keep_exports_full_refund_account_not_charge_account(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """A C rectificativa with stated c111 writes a refund destination under Nota 3."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            negative_result=True,
            casilla_111=Decimal("0"),
            operation=_authority_operation_for_test,
        )
        assert verified.casilla_values["111"] == Decimal("0")
        rectificativa = _persist_rectificativa_with_nota_three(
            verified,
            taxpayer_nif=taxpayer_nif,
            work_repo=work_repo,
            calc_repo=calc_repo,
            operation=_authority_operation_for_test,
        )
        # An account outside the SEPA zone, so the DID page carries its whole
        # foreign-bank block beside the IBAN (Marca SEPA 3).
        refund_account = _own_account(
            "Nota Three Refund",
            "BR1800360305000010009795493C1",
            swift_bic="BOCBBRSPXXX",
            bank_name="Nota Three Refund Bank",
            bank_address="1 Refund Plaza",
            bank_city="Sao Paulo",
            bank_country_code="BR",
        )
        output_path = tmp_path / "modelo-303-n3-keep.txt"

        result = export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=rectificativa.calculation_revision_id,
                output_path=output_path,
                actor="operator",
                prior_domiciliation_election=PriorDomiciliationElection.KEEP,
            ),
            workflow_profile=_nota_three_profile(
                taxpayer_nif=taxpayer_nif, bucket_id=bucket_id, refund_account=refund_account
            ),
            export_ports=modelo_export_ports_for_test(
                product_software_identity=_product_software_identity(),
                taxpayer_tax_id=taxpayer_nif,
                work_unit=work_repo,
                calculation=CalculationRevisionCatalogueRepository(m303_rectificativa_taxpayer_tax_id=taxpayer_nif),
                bucket_event=event_repo,
            ),
            clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
            operation=_authority_operation_for_test,
        )

        exported = output_path.read_text(encoding="iso-8859-1")
        assert exported[exported.index("<T30301000>") + 12] == "C"
        did_start = exported.index("<T303DID00>")
        did = exported[did_start : did_start + 823]
        assert did[11:22].rstrip() == refund_account.swift_bic
        assert did[22:56].rstrip() == refund_account.iban
        assert did[56:126].rstrip() == refund_account.bank_name
        assert did[126:161].rstrip() == refund_account.bank_address
        assert did[161:191].rstrip() == refund_account.bank_city
        assert did[191:193].rstrip() == refund_account.bank_country_code
        assert did[193:194] == "3"
        assert "ES7921000813610123456789" not in exported
        assert result.resolved_result_disposition is ResultDisposition.COMPENSACION
        assert result.prior_domiciliation_election.election is PriorDomiciliationElection.KEEP
        assert result.selected_account == ModeloExportAccountReference(
            role=OwnAccountRole.REFUND, own_account_id="acc-02"
        )
        assert refund_account.iban not in result.model_dump_json()


def test_public_rectificativa_nota_three_keep_refuses_without_refund_account_before_bytes_or_event(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """Nota 3 cannot emit an empty DID account block on a C rectificativa."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            negative_result=True,
            casilla_111=Decimal("0"),
            operation=_authority_operation_for_test,
        )
        rectificativa = _persist_rectificativa_with_nota_three(
            verified,
            taxpayer_nif=taxpayer_nif,
            work_repo=work_repo,
            calc_repo=calc_repo,
            operation=_authority_operation_for_test,
        )
        output_path = tmp_path / "modelo-303-n3-missing-refund.txt"

        with pytest.raises(ModeloRefundAccountMissingError):
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=rectificativa.calculation_revision_id,
                    output_path=output_path,
                    actor="operator",
                    prior_domiciliation_election=PriorDomiciliationElection.KEEP,
                ),
                workflow_profile=_nota_three_profile(
                    taxpayer_nif=taxpayer_nif, bucket_id=bucket_id, refund_account=None
                ),
                export_ports=modelo_export_ports_for_test(
                    product_software_identity=_product_software_identity(),
                    taxpayer_tax_id=taxpayer_nif,
                    work_unit=work_repo,
                    calculation=CalculationRevisionCatalogueRepository(m303_rectificativa_taxpayer_tax_id=taxpayer_nif),
                    bucket_event=event_repo,
                ),
                clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
                operation=_authority_operation_for_test,
            )

        assert not output_path.exists()
        assert not event_repo.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,))


def test_public_rectificativa_nota_three_remains_incompatible_with_current_domiciliacion(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """The pre-existing result-sign gate refuses c111 plus a current U election."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            negative_result=True,
            casilla_111=Decimal("0"),
            operation=_authority_operation_for_test,
        )
        rectificativa = _persist_rectificativa_with_nota_three(
            verified,
            taxpayer_nif=taxpayer_nif,
            work_repo=work_repo,
            calc_repo=calc_repo,
            operation=_authority_operation_for_test,
        )
        output_path = tmp_path / "modelo-303-n3-current-u.txt"

        with pytest.raises(ModeloPaymentElectionIncompatibleError):
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=rectificativa.calculation_revision_id,
                    output_path=output_path,
                    actor="operator",
                    prior_domiciliation_election=PriorDomiciliationElection.KEEP,
                    payment_election=PaymentElection.DOMICILIACION,
                ),
                workflow_profile=_nota_three_profile(
                    taxpayer_nif=taxpayer_nif, bucket_id=bucket_id, refund_account=None
                ),
                export_ports=modelo_export_ports_for_test(
                    product_software_identity=_product_software_identity(),
                    taxpayer_tax_id=taxpayer_nif,
                    work_unit=work_repo,
                    calculation=CalculationRevisionCatalogueRepository(m303_rectificativa_taxpayer_tax_id=taxpayer_nif),
                    bucket_event=event_repo,
                ),
                clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
                operation=_authority_operation_for_test,
            )

        assert not output_path.exists()


def testprior_domiciliation_export_and_filing_events_keep_the_safe_baseline_u_proof(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """Actual export and filing event ledgers retain proof coordinates, never accounts."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            negative_result=True,
            casilla_111=Decimal("0"),
            operation=_authority_operation_for_test,
        )
    work_unit = work_repo.load().get(verified.work_unit_id)
    assert work_unit is not None
    filing_repository = ModeloRecordCatalogueRepository()
    baseline_evidence_reference = "CSV3032026ST2S21"
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
        origin=FilingOrigin.AEAT,
        confirmation=AeatConfirmationState.CONFIRMADA,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
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
                # A domiciliation settles a positive result; the carry ingress
                # proves the disposition against this sign.
                observations=registry_grounded_observations(
                    modelo="303",
                    filing_year=work_unit.filing_year,
                    period=work_unit.period.registry_token,
                    casilla_values={validated_casilla_id("iva.resultado", surface="test"): Decimal("125.00")},
                ),
            ),
            source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            captured_at=datetime(2026, 5, 21, 11, 59, tzinfo=UTC),
            source_metadata={"aeat_justificante_csv": baseline_evidence_reference},
            source_headers=(
                ObservedHeaderFact(
                    header_key="filing.result_disposition",
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
            stamped_revision_id=revision_id_for_observation(
                RegistryModeloObservation(
                    modelo="303",
                    filing_year=work_unit.filing_year,
                    period=work_unit.period.registry_token,
                )
            ),
        )
    )
    _amended = verified.model_copy(
        update={
            "amendment_identity": CalculationRevisionAmendmentIdentity(
                kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
                amends_filing_record_id=baseline.filing_record_id,
                m303_rectificativa_motive=M303RectificativaMotive.RECTIFICACIONES,
            ),
            "amendment_reason": "correct prior direct-debit election",
        },
    )
    rectificativa = _with_rederived_id(_amended)
    baseline_justificante = _baseline_justificante(
        baseline_evidence_reference,
        work_unit=work_unit,
        taxpayer_nif=taxpayer_nif,
        presented_at=baseline.filed_at,
    )
    JustificanteRepository().save(baseline_justificante)
    calc_repo = CalculationRevisionCatalogueRepository(m303_rectificativa_taxpayer_tax_id=taxpayer_nif)
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        calc_repo.save(
            upsert_calculation_revision(
                calc_repo.load(),
                rectificativa,
                aggregate_context=CalculationRevisionAggregateContext(
                    work_units=work_repo.load(),
                    filing_records=filing_repository.load(),
                    justificantes=(baseline_justificante,),
                    registry_snapshots={
                        work_unit.work_unit_id: _authority_operation_for_test.snapshot(
                            "303", filing_year=work_unit.filing_year, period=work_unit.period.registry_token
                        )
                    },
                    expected_taxpayer_tax_id=taxpayer_nif,
                ),
            )
        )

    output_path = tmp_path / "modelo-303-prior-domiciliation.txt"
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        result = export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=rectificativa.calculation_revision_id,
                output_path=output_path,
                actor="operator",
                prior_domiciliation_election=PriorDomiciliationElection.CANCEL_OR_MODIFY,
            ),
            workflow_profile=_typed_profile_with_charge_account(taxpayer_nif=taxpayer_nif, charge_iban=None),
            export_ports=modelo_export_ports_for_test(
                product_software_identity=_product_software_identity(),
                taxpayer_tax_id=taxpayer_nif,
                work_unit=work_repo,
                calculation=calc_repo,
                filing=filing_repository,
                bucket_event=event_repo,
            ),
            clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
            operation=_authority_operation_for_test,
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
    assert "<T303DID00>" not in output_path.read_text(encoding="iso-8859-1")
    assert "iban" not in export_event.model_dump_json().casefold()

    verification_repository = VerificationReportCatalogueRepository(
        bucket_id=bucket_id,
        m303_rectificativa_taxpayer_tax_id=taxpayer_nif,
    )
    report_id = seed_filing_gate_report(
        rectificativa,
        verification_repository,
    )
    _, filing_baseline_revision_id = filing_repository.load_revisioned()
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        filing = persist_filed_revision(
            target=rectificativa,
            approved_verification_report_id=report_id,
            filing_baseline_revision_id=filing_baseline_revision_id,
            work_unit=work_unit,
            work_units=work_repo.load(),
            notes=None,
            actor="operator",
            now=datetime(2026, 5, 21, 12, 4, tzinfo=UTC),
            calculation_repository=calc_repo,
            filing_repository=filing_repository,
            verification_repository=verification_repository,
            work_unit_repository=work_repo,
            bucket_event_repository=event_repo,
            result_disposition=result.resolved_result_disposition,
            prior_domiciliation_election=result.prior_domiciliation_election,
            taxpayer_nif=taxpayer_nif,
            calculation_observation_repository=CalculationObservationRepository(),
            iva_compensation_history_repository=IvaCompensationHistoryRepository(),
            participation_index_repository=TransactionParticipationIndexRepository(bucket_id=bucket_id),
            prorrata_register_repository=ProrrataRegisterRepository(bucket_id=bucket_id),
            justificante_repository=JustificanteRepository(),
            operation=_authority_operation_for_test,
        )
    filed_event = event_repo.load().for_bucket(
        bucket_id,
        event_types=(BucketEventType.MODELO_FILED,),
    )[-1]
    assert filed_event.event_type is BucketEventType.MODELO_FILED
    assert filed_event.object_id == filing.filing_record_id
    assert {key: filed_event.payload[key] for key in expected_event_proof} == expected_event_proof
    assert "iban" not in filed_event.model_dump_json().casefold()


def _u_command(verified, output_path: Path, *, charge_account_id: str | None = None) -> ModeloExportCommand:
    return ModeloExportCommand(
        calculation_revision_id=verified.calculation_revision_id,
        output_path=output_path,
        actor="operator",
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        payment_election=PaymentElection.DOMICILIACION,
        charge_account_id=charge_account_id,
    )


def test_public_domiciliacion_per_filing_choice_overrides_the_charge_designation(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """An explicit charge account wins over the designated one, and only its id is recorded."""
    with _indexed_authority_for_test().operation() as operation:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            positive_result=True,
            operation=operation,
        )
        designated = "ES7921000813610123456789"
        chosen = "ES9121000418450200051332"
        _register_own_account(bucket_id, _own_account("Designada", designated), designate=(OwnAccountRole.CHARGE,))
        chosen_id = _register_own_account(bucket_id, _own_account("Elegida", chosen))
        output_path = tmp_path / "modelo-303-chosen-charge.txt"

        result = export_modelo_revision(
            _u_command(verified, output_path, charge_account_id=chosen_id),
            workflow_profile=_typed_profile(taxpayer_nif=taxpayer_nif),
            export_ports=modelo_export_ports_for_test(
                product_software_identity=_product_software_identity(),
                bucket_id=bucket_id,
                taxpayer_tax_id=taxpayer_nif,
                work_unit=work_repo,
                calculation=calc_repo,
                bucket_event=event_repo,
            ),
            clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
            operation=operation,
        )

        exported = output_path.read_bytes().decode("latin-1")
        did_start = exported.index("<T303DID00>")
        # DR303 DID IBAN: positions 23-56.
        assert exported[did_start + 22 : did_start + 56].rstrip() == chosen
        assert designated not in exported
        assert chosen_id == "acc-02"
        assert result.selected_account == ModeloExportAccountReference(
            role=OwnAccountRole.CHARGE, own_account_id="acc-02"
        )
        event = event_repo.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,))[-1]
        assert event.payload["selected_own_account_id"] == "acc-02"
        for text in (result.model_dump_json(), event.model_dump_json()):
            assert chosen not in text
            assert designated not in text
            assert chosen[-4:] + '"' not in text


@pytest.mark.parametrize(
    ("charge_account_id", "closed_on", "reason"),
    [
        pytest.param("acc-07", None, "own_account_unregistered", id="unregistered-choice"),
        pytest.param("acc-01", "2026-05-20", "own_account_closed", id="closed-choice"),
        pytest.param(None, "2026-05-20", "own_account_closed", id="closed-designation"),
    ],
)
def test_public_domiciliacion_refuses_an_unusable_charge_account_before_any_byte(
    isolated_backend: None,
    tmp_path: Path,
    charge_account_id: str | None,
    closed_on: str | None,
    reason: str,
) -> None:
    """An unknown or closed own account is the missing-account refusal, named by its opaque id."""
    with _indexed_authority_for_test().operation() as operation:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            positive_result=True,
            operation=operation,
        )
        details = _own_account("Cargo", "ES9121000418450200051332")
        if closed_on is not None:
            details = details.model_copy(update={"closed_on": date.fromisoformat(closed_on)})
        _register_own_account(bucket_id, details, designate=(OwnAccountRole.CHARGE,))
        output_path = tmp_path / "modelo-303-unusable-charge.txt"

        with pytest.raises(ModeloChargeAccountMissingError) as refused:
            export_modelo_revision(
                _u_command(verified, output_path, charge_account_id=charge_account_id),
                workflow_profile=_typed_profile(taxpayer_nif=taxpayer_nif),
                export_ports=modelo_export_ports_for_test(
                    product_software_identity=_product_software_identity(),
                    bucket_id=bucket_id,
                    taxpayer_tax_id=taxpayer_nif,
                    work_unit=work_repo,
                    calculation=calc_repo,
                    bucket_event=event_repo,
                ),
                clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
                operation=operation,
            )

        assert get_registered_error_code(refused.value).code == "REFUSED_MODELO_CHARGE_ACCOUNT_MISSING"
        assert refused.value.context == {
            "calculation_revision_id": verified.calculation_revision_id,
            "reason": reason,
            "own_account_id": charge_account_id or "acc-01",
        }
        assert not output_path.exists()
        assert not event_repo.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,))


def test_public_ingreso_ignores_a_closed_charge_designation(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """A closed designated account blocks only the export that needs its role."""
    with _indexed_authority_for_test().operation() as operation:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            positive_result=True,
            operation=operation,
        )
        closed = _own_account("Cargo", "ES9121000418450200051332").model_copy(update={"closed_on": date(2026, 1, 31)})
        _register_own_account(bucket_id, closed, designate=(OwnAccountRole.CHARGE,))
        output_path = tmp_path / "modelo-303-ingreso-closed-designation.txt"

        result = export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=verified.calculation_revision_id,
                output_path=output_path,
                actor="operator",
                prior_domiciliation_election=PriorDomiciliationElection.KEEP,
            ),
            workflow_profile=_typed_profile(taxpayer_nif=taxpayer_nif),
            export_ports=modelo_export_ports_for_test(
                product_software_identity=_product_software_identity(),
                bucket_id=bucket_id,
                taxpayer_tax_id=taxpayer_nif,
                work_unit=work_repo,
                calculation=calc_repo,
                bucket_event=event_repo,
            ),
            clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
            operation=operation,
        )

        assert result.resolved_result_disposition is ResultDisposition.INGRESO
        assert result.selected_account is None
        assert result.domiciliation_cutoff_unverified is False
        assert "<T303DID00>" not in output_path.read_bytes().decode("latin-1")


def _redeme_profile(*, taxpayer_nif: str) -> TaxpayerProfile:
    """A REDEME-inscribed profile: every negative period resolves to a devolución."""
    return TaxpayerProfile(
        tax_id=taxpayer_nif,
        iva_regime=IVARegime("GENERAL"),
        iva=ModeloIVAProfile(
            tax_territory=M303TaxTerritory.from_registry("common_regime"),
            regime_composition=M303RegimeComposition.from_registry("general"),
            redeme_enrolled=True,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=False,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
        ),
    )


# DR303 2026 offsets, 1-based in the design, 0-based slices here: page 01000
# "Tipo Declaración" at position 13; DID SWIFT-BIC 12-22, IBAN 23-56, bank
# block 57-193, Marca SEPA 194 (Nota 2: 1 Cuenta España, 2 Unión Europea SEPA).
@pytest.mark.parametrize(
    ("refund_iban", "tipo", "marca"),
    [
        pytest.param("ES9121000418450200051332", "D", "1", id="spanish-account-devolucion"),
        pytest.param("DE89370400440532013000", "X", "2", id="foreign-account-transferencia-al-extranjero"),
    ],
)
def test_public_refund_tipo_follows_the_refund_account_country(
    isolated_backend: None,
    tmp_path: Path,
    refund_iban: str,
    tipo: str,
    marca: str,
) -> None:
    """A devolución into a Spanish account is D; into a foreign one, X, with the DID page to match."""
    with _indexed_authority_for_test().operation() as operation:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            negative_result=True,
            operation=operation,
        )
        account_id = _register_own_account(
            bucket_id, _own_account("Devolución", refund_iban), designate=(OwnAccountRole.REFUND,)
        )
        output_path = tmp_path / f"modelo-303-refund-{tipo}.txt"

        result = export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=verified.calculation_revision_id,
                output_path=output_path,
                actor="operator",
                prior_domiciliation_election=PriorDomiciliationElection.KEEP,
            ),
            workflow_profile=_redeme_profile(taxpayer_nif=taxpayer_nif),
            export_ports=modelo_export_ports_for_test(
                product_software_identity=_product_software_identity(),
                bucket_id=bucket_id,
                taxpayer_tax_id=taxpayer_nif,
                work_unit=work_repo,
                calculation=calc_repo,
                bucket_event=event_repo,
            ),
            clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
            operation=operation,
        )

        exported = output_path.read_bytes().decode("latin-1")
        page_one = exported[exported.index("<T30301000>") :]
        assert page_one[12] == tipo
        did = exported[exported.index("<T303DID00>") :][:823]
        assert did[11:22].strip() == ""
        assert did[22:56].rstrip() == refund_iban
        assert did[56:193].strip() == ""
        assert did[193] == marca
        assert did.endswith("</T303DID00>")

        assert result.resolved_result_disposition is ResultDisposition(tipo)
        assert result.selected_account == ModeloExportAccountReference(
            role=OwnAccountRole.REFUND, own_account_id=account_id
        )
        event = event_repo.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,))[-1]
        assert event.payload["resolved_result_disposition"] == tipo
        assert event.payload["selected_account_role"] == "refund"
        assert refund_iban not in event.model_dump_json()
        assert refund_iban not in result.model_dump_json()


def test_public_domiciliacion_without_persisted_charge_account_refuses(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """A persisted refund account never becomes a public U debit fallback."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        _taxpayer_nif, _bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            positive_result=True,
            operation=_authority_operation_for_test,
        )
        output_path = tmp_path / "missing-charge-account.txt"

        with pytest.raises(ModeloChargeAccountMissingError):
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=verified.calculation_revision_id,
                    output_path=output_path,
                    actor="operator",
                    prior_domiciliation_election=PriorDomiciliationElection.KEEP,
                    payment_election=PaymentElection.DOMICILIACION,
                ),
                workflow_profile=_typed_profile_with_charge_account(taxpayer_nif=_taxpayer_nif, charge_iban=None),
                export_ports=modelo_export_ports_for_test(
                    product_software_identity=_product_software_identity(),
                    taxpayer_tax_id=_taxpayer_nif,
                    work_unit=work_repo,
                    calculation=calc_repo,
                    bucket_event=event_repo,
                ),
                clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
                operation=_authority_operation_for_test,
            )

        assert not output_path.exists()


def test_public_domiciliacion_with_a_foreign_charge_account_refuses_before_any_byte(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """A non-ES charge account is capability-refused until art. 5 bis is grounded."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            positive_result=True,
            operation=_authority_operation_for_test,
        )
        output_path = tmp_path / "foreign-charge-account.txt"

        with pytest.raises(ModeloPaymentElectionCapabilityRefusedError) as refused:
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=verified.calculation_revision_id,
                    output_path=output_path,
                    actor="operator",
                    prior_domiciliation_election=PriorDomiciliationElection.KEEP,
                    payment_election=PaymentElection.DOMICILIACION,
                ),
                workflow_profile=_typed_profile_with_charge_account(
                    taxpayer_nif=taxpayer_nif,
                    charge_iban="DE89370400440532013000",
                    bucket_id=bucket_id,
                ),
                export_ports=modelo_export_ports_for_test(
                    product_software_identity=_product_software_identity(),
                    bucket_id=bucket_id,
                    taxpayer_tax_id=taxpayer_nif,
                    work_unit=work_repo,
                    calculation=calc_repo,
                    bucket_event=event_repo,
                ),
                clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
                operation=_authority_operation_for_test,
            )

        assert get_registered_error_code(refused.value).code == "REFUSED_MODELO_PAYMENT_ELECTION_CAPABILITY"
        assert refused.value.context == {
            "modelo": "303",
            "payment_election": "domiciliacion",
            "charge_account_country": "DE",
        }
        assert not output_path.exists()
        assert not event_repo.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,))


def test_public_cuenta_corriente_payment_election_is_capability_refused(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """G remains a typed but unavailable capability and never reads a charge account."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        _taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            positive_result=True,
            operation=_authority_operation_for_test,
        )
        output_path = tmp_path / "cuenta-corriente.txt"

        with pytest.raises(ModeloPaymentElectionCapabilityRefusedError):
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=verified.calculation_revision_id,
                    output_path=output_path,
                    actor="operator",
                    prior_domiciliation_election=PriorDomiciliationElection.KEEP,
                    payment_election=PaymentElection.CUENTA_CORRIENTE,
                ),
                workflow_profile=_typed_profile_with_charge_account(
                    taxpayer_nif=_taxpayer_nif,
                    charge_iban="ES7921000813610123456789",
                    bucket_id=bucket_id,
                ),
                export_ports=modelo_export_ports_for_test(
                    product_software_identity=_product_software_identity(),
                    taxpayer_tax_id=_taxpayer_nif,
                    work_unit=work_repo,
                    calculation=calc_repo,
                    bucket_event=event_repo,
                ),
                clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
                operation=_authority_operation_for_test,
            )

        assert not output_path.exists()


def test_public_ingreso_export_omits_did_page(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """A public positive ingreso export omits DID rather than emitting an empty account page."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        taxpayer_nif, _bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            positive_result=True,
            operation=_authority_operation_for_test,
        )
        output_path = tmp_path / "modelo-303-ingreso.txt"

        result = export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=verified.calculation_revision_id,
                output_path=output_path,
                actor="operator",
                prior_domiciliation_election=PriorDomiciliationElection.KEEP,
            ),
            workflow_profile=_typed_profile_with_charge_account(taxpayer_nif=taxpayer_nif, charge_iban=None),
            export_ports=modelo_export_ports_for_test(
                product_software_identity=_product_software_identity(),
                taxpayer_tax_id=taxpayer_nif,
                work_unit=work_repo,
                calculation=calc_repo,
                bucket_event=event_repo,
            ),
            clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
            operation=_authority_operation_for_test,
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
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        taxpayer_nif, _bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            operation=_authority_operation_for_test,
        )

        existing_dir = tmp_path / "already-a-directory"
        existing_dir.mkdir()
        tmp_sibling = existing_dir.with_name(existing_dir.name + ".tmp")

        with pytest.raises(ModeloExportOutputPathError):
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=verified.calculation_revision_id,
                    output_path=existing_dir,
                    actor="operator",
                    prior_domiciliation_election=PriorDomiciliationElection.KEEP,
                ),
                workflow_profile=_typed_profile_with_charge_account(taxpayer_nif=taxpayer_nif, charge_iban=None),
                export_ports=modelo_export_ports_for_test(
                    product_software_identity=_product_software_identity(),
                    taxpayer_tax_id=taxpayer_nif,
                    work_unit=work_repo,
                    calculation=calc_repo,
                    bucket_event=event_repo,
                ),
                clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
                operation=_authority_operation_for_test,
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
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        taxpayer_nif, _bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            operation=_authority_operation_for_test,
        )

        with pytest.raises(ModeloExportOutputPathError):
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=verified.calculation_revision_id,
                    output_path=Path(""),
                    actor="operator",
                    prior_domiciliation_election=PriorDomiciliationElection.KEEP,
                ),
                workflow_profile=_typed_profile_with_charge_account(taxpayer_nif=taxpayer_nif, charge_iban=None),
                export_ports=modelo_export_ports_for_test(
                    product_software_identity=_product_software_identity(),
                    taxpayer_tax_id=taxpayer_nif,
                    work_unit=work_repo,
                    calculation=calc_repo,
                    bucket_event=event_repo,
                ),
                clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
                operation=_authority_operation_for_test,
            )
        assert not any(p.suffix == ".tmp" for p in iter_directory(tmp_path, recursive=True))


def test_export_refuses_an_existing_file_unless_the_operator_chooses_to_replace_it(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """An earlier export is never silently destroyed; an explicit replace rewrites it identically."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            operation=_authority_operation_for_test,
        )
        output_path = tmp_path / "modelo-303.txt"
        profile = _typed_profile_with_charge_account(taxpayer_nif=taxpayer_nif, charge_iban=None)

        def export(*, replace_existing: bool, minute: int) -> ModeloExportResult:
            return export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=verified.calculation_revision_id,
                    output_path=output_path,
                    actor="operator",
                    prior_domiciliation_election=PriorDomiciliationElection.KEEP,
                    replace_existing=replace_existing,
                ),
                workflow_profile=profile,
                export_ports=modelo_export_ports_for_test(
                    product_software_identity=_product_software_identity(),
                    taxpayer_tax_id=taxpayer_nif,
                    work_unit=work_repo,
                    calculation=calc_repo,
                    bucket_event=event_repo,
                ),
                clock=datetime(2026, 5, 21, 12, minute, tzinfo=UTC),
                operation=_authority_operation_for_test,
            )

        first = export(replace_existing=False, minute=3)
        earlier_bytes = output_path.read_bytes()
        exported_events = len(event_repo.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,)))

        with pytest.raises(ModeloExportOutputPathError) as refused:
            export(replace_existing=False, minute=4)
        assert refused.value.context is not None
        assert refused.value.context["reason"] == "path is an existing file"
        assert output_path.read_bytes() == earlier_bytes
        assert (
            len(event_repo.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,)))
            == exported_events
        )

        replaced = export(replace_existing=True, minute=5)
        assert replaced.file_sha256 == first.file_sha256
        assert not (output_path.with_name(output_path.name + ".tmp")).exists()
