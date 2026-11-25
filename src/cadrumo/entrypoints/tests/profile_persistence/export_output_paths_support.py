"""Profiles, filing fixtures and clock shared by the export output path tests."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from cadrumo.adapters.inbound.pdf.source_provenance import source_pdf_reference_path
from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.own_accounts import OwnAccountRepository
from cadrumo.application.modelo.export_contracts import (
    ModeloExportCommand,
)
from cadrumo.core.payment_election import PaymentElection
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.time.clock import frozen_clock
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
)
from cadrumo.domain.justificante.schema import Justificante
from cadrumo.domain.modelos.calculation_repository import upsert_calculation_revision
from cadrumo.domain.modelos.calculation_revision import (
    derive_calculation_revision_id_from_revision,
)
from cadrumo.domain.modelos.calculation_revision_aggregate import CalculationRevisionAggregateContext
from cadrumo.domain.modelos.calculation_revision_amendment import (
    CalculationRevisionAmendmentIdentity,
    M303RectificativaMotive,
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
from cadrumo.tests.aeat_literal_fixtures import justificante_cotejo_url


def product_software_identity() -> AeatProductSoftwareIdentity:
    return AeatProductSoftwareIdentity(
        program_identifier="C303",
        developer_tax_id="Y0001006P",
        evidence=(
            AeatProductSoftwareEvidence(
                reference="aeat-software-registration:export-output-paths",
                digest="a" * 64,
            ),
        ),
    )


def typed_profile(*, taxpayer_nif: str) -> TaxpayerProfile:
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


def own_account(label: str, iban: str, **bank_block: str) -> OwnBankAccountDetails:
    return OwnBankAccountDetails(label=label, holding=OwnAccountHolding.TITULAR, iban=iban, **bank_block)


def register_own_account(
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


def typed_profile_with_charge_account(
    *, taxpayer_nif: str, charge_iban: str | None, bucket_id: str | None = None
) -> TaxpayerProfile:
    """Build the typed profile, designating ``charge_iban`` as the bucket's charge own account."""
    if charge_iban is not None:
        assert bucket_id is not None
        register_own_account(bucket_id, own_account("Cargo", charge_iban), designate=(OwnAccountRole.CHARGE,))
    return typed_profile(taxpayer_nif=taxpayer_nif)


def with_rederived_id(revision):
    """Re-stamp a copied revision with the id its new content derives to.

    `model_copy` changes content without touching calculation_revision_id, and
    the id is content addressed over the amendment identity, so a copy that adds
    one carries an id the catalogue rejects as not matching its own content.
    """
    return revision.model_copy(
        update={"calculation_revision_id": derive_calculation_revision_id_from_revision(revision)},
    )


def export_output_paths_baseline_justificante(
    csv: str, *, work_unit, taxpayer_nif: str, presented_at: datetime
) -> Justificante:
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


def persist_rectificativa_with_nota_three(
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
    justificante = export_output_paths_baseline_justificante(
        csv, work_unit=work_unit, taxpayer_nif=taxpayer_nif, presented_at=filed_at
    )
    JustificanteRepository().save(justificante)
    amended = verified.model_copy(
        update={
            "amendment_identity": CalculationRevisionAmendmentIdentity(
                kind=FilingDeclarationKind.RECTIFICATIVA,
                amends_filing_record_id=original.filing_record_id,
                m303_rectificativa_motive=M303RectificativaMotive.RECTIFICACIONES,
            ),
            "amendment_reason": "correct bank-transfer credit declared in casilla 111",
        }
    )
    rectificativa = with_rederived_id(amended)
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


def nota_three_profile(
    *, taxpayer_nif: str, bucket_id: str, refund_account: OwnBankAccountDetails | None
) -> TaxpayerProfile:
    """Designate a charge account always, and the refund account when given: Nota 3 must pick the refund one."""
    register_own_account(
        bucket_id, own_account("Cargo", "ES7921000813610123456789"), designate=(OwnAccountRole.CHARGE,)
    )
    if refund_account is not None:
        register_own_account(bucket_id, refund_account, designate=(OwnAccountRole.REFUND,))
    return typed_profile(taxpayer_nif=taxpayer_nif)


def u_command(verified, output_path: Path, *, charge_account_id: str | None = None) -> ModeloExportCommand:
    return ModeloExportCommand(
        calculation_revision_id=verified.calculation_revision_id,
        output_path=output_path,
        actor="operator",
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        payment_election=PaymentElection.DOMICILIACION,
        charge_account_id=charge_account_id,
    )


def redeme_profile(*, taxpayer_nif: str) -> TaxpayerProfile:
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
@pytest.fixture(autouse=True)
def authored_export_clock() -> Iterator[None]:
    """Keep captured wallet freshness on the authored scenario's timeline."""
    with frozen_clock(datetime(2026, 6, 4, 12, 0, tzinfo=UTC)):
        yield
