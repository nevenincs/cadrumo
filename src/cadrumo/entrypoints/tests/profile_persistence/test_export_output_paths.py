"""Modelo export output-path and fichero emission tests."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.tests.modelo_export_support import isolated_backend
from cadrumo.application.filing.export_verification import FilingExportValidatedPayload
from cadrumo.application.modelo.action_errors import (
    ModeloPaymentElectionIncompatibleError,
    ModeloRefundAccountMissingError,
)
from cadrumo.application.modelo.export import export_modelo_revision
from cadrumo.application.modelo.export_contracts import (
    ModeloExportAccountReference,
    ModeloExportCommand,
)
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.payment_election import PaymentElection
from cadrumo.core.period import Period
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.filing.software_identity import (
    AeatSoftwareIdentityGrade,
    development_mock_software_identity,
)
from cadrumo.domain.modelos.errors import (
    ModeloExportPriorDomiciliationElectionRequiredError,
)
from cadrumo.domain.transactions.own_accounts import (
    OwnAccountRole,
)
from cadrumo.entrypoints.tests.profile_persistence.modelo_303_export_support import build_verified_modelo_303_revision

from .export_output_paths_support import (
    authored_export_clock,
    nota_three_profile,
    own_account,
    persist_rectificativa_with_nota_three,
    product_software_identity,
    typed_profile,
    typed_profile_with_charge_account,
)

__all__ = ["authored_export_clock", "isolated_backend"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _assert_matched_wallet_result(result, output_path: Path) -> None:
    assert output_path.exists()
    assert result.modelo == "303"
    assert result.byte_size == output_path.stat().st_size
    assert result.file_sha256
    assert result.resolved_result_disposition is ResultDisposition.NEGATIVA
    assert result.payment_election is None
    assert result.refund_election is None
    assert result.casilla_provenance


def _assert_matched_wallet_provenance(result) -> None:
    provenance = result.iva_wallet_decision_provenance
    assert provenance is not None
    assert provenance.selected_authority == "aeat_wallet"
    assert provenance.divergence == "match"
    assert provenance.target_year == 2026
    assert provenance.target_period == Period.from_year_and_code(2026, "2T")
    assert provenance.decision_ref.startswith("sha256:")
    assert provenance.authority_source_kinds == ("aeat_wallet", "local_recurrence", "filed_history_observation")
    assert provenance.authority_source_refs[0].startswith("sha256:")


def _assert_matched_wallet_event(event) -> None:
    assert event.payload["period"] == "2T"
    assert event.payload["resolved_result_disposition"] == ResultDisposition.NEGATIVA.value
    assert "refund_election" not in event.payload
    assert "payment_election" not in event.payload
    assert event.payload["iva_wallet_selected_authority"] == "aeat_wallet"
    assert event.payload["iva_wallet_divergence"] == "match"
    assert event.payload["iva_wallet_target_period"] == "2T"


def _assert_matched_wallet_export_is_redacted(result, event, output_path: Path, taxpayer_nif: str) -> None:
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


def test_export_modelo_303_matched_wallet_revision_writes_fichero_with_redacted_wallet_provenance(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            operation=_authority_operation_for_test,
        )

        output_path = tmp_path / "modelo-303-matched-wallet.txt"
        result = export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=verified.calculation_revision_id,
                output_path=output_path,
                actor="operator",
                prior_domiciliation_election=PriorDomiciliationElection.KEEP,
            ),
            workflow_profile=typed_profile_with_charge_account(taxpayer_nif=taxpayer_nif, charge_iban=None),
            export_ports=modelo_export_ports_for_test(
                product_software_identity=product_software_identity(),
                bucket_id=bucket_id,
                taxpayer_tax_id=taxpayer_nif,
                work_unit=work_repo,
                calculation=calc_repo,
                bucket_event=event_repo,
            ),
            clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
            operation=_authority_operation_for_test,
        )

        _assert_matched_wallet_result(result, output_path)
        _assert_matched_wallet_provenance(result)
        event = event_repo.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,))[-1]
        _assert_matched_wallet_event(event)
        _assert_matched_wallet_export_is_redacted(result, event, output_path, taxpayer_nif)


class _CollectingPayloadConsumer:
    def __init__(self) -> None:
        self.payloads: list[FilingExportValidatedPayload] = []

    def consume_validated_payload(self, payload: FilingExportValidatedPayload) -> None:
        self.payloads.append(payload)


def test_export_modelo_303_to_a_payload_consumer_writes_no_file_and_records_the_event(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            operation=_authority_operation_for_test,
        )
        package_path = tmp_path / "review-package.zip"
        consumer = _CollectingPayloadConsumer()
        files_before = sorted(path for path in tmp_path.rglob("*") if path.is_file())

        result = export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=verified.calculation_revision_id,
                output_path=package_path,
                actor="operator",
                prior_domiciliation_election=PriorDomiciliationElection.KEEP,
            ),
            workflow_profile=typed_profile_with_charge_account(taxpayer_nif=taxpayer_nif, charge_iban=None),
            export_ports=modelo_export_ports_for_test(
                product_software_identity=product_software_identity(),
                bucket_id=bucket_id,
                taxpayer_tax_id=taxpayer_nif,
                work_unit=work_repo,
                calculation=calc_repo,
                bucket_event=event_repo,
            ),
            clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
            operation=_authority_operation_for_test,
            payload_consumer=consumer,
        )

        assert not package_path.exists()
        new_files = sorted(path for path in tmp_path.rglob("*") if path.is_file() and path not in files_before)
        delivered_digest = hashlib.sha256(consumer.payloads[0].payload).hexdigest()
        assert not [path for path in new_files if hashlib.sha256(path.read_bytes()).hexdigest() == delivered_digest]
        (delivered,) = consumer.payloads
        assert taxpayer_nif in delivered.payload.decode("utf-8")
        assert result.output_path == package_path
        assert result.byte_size == len(delivered.payload)
        assert result.file_sha256 == hashlib.sha256(delivered.payload).hexdigest()
        event = event_repo.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,))[-1]
        assert event.event_id == result.bucket_event_id
        assert event.payload["output_path"] == str(package_path)
        assert event.payload["file_sha256"] == result.file_sha256


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
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
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
            workflow_profile=typed_profile_with_charge_account(taxpayer_nif=taxpayer_nif, charge_iban=None),
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
        mock = development_mock_software_identity()
        assert written[prefix_start + 92 : prefix_start + 96] == b"0000"
        assert written[prefix_start + 100 : prefix_start + 109] == mock.developer_tax_id.encode("ascii")
        assert taxpayer_nif.encode("ascii") not in written[prefix_start + 100 : prefix_start + 109]
        assert result.software_identity_grade is AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK
        assert event_repo.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,))


def test_export_modelo_303_without_a_prior_domiciliation_election_keeps_it(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """KEEP is the neutral default: an ordinary 303 with no election exports with a blank page-3 marker."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
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
            workflow_profile=typed_profile(taxpayer_nif=taxpayer_nif),
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
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            negative_result=True,
            casilla_111=Decimal("0"),
            operation=_authority_operation_for_test,
        )
        rectificativa = persist_rectificativa_with_nota_three(
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
                workflow_profile=nota_three_profile(
                    taxpayer_nif=taxpayer_nif, bucket_id=bucket_id, refund_account=None
                ),
                export_ports=modelo_export_ports_for_test(
                    product_software_identity=product_software_identity(),
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


def test_public_domiciliacion_export_selects_typed_charge_account_for_did_only(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """Public export reaches DID only through the typed selected-account snapshot."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
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
            workflow_profile=typed_profile_with_charge_account(
                taxpayer_nif=taxpayer_nif, charge_iban=charge_iban, bucket_id=bucket_id
            ),
            export_ports=modelo_export_ports_for_test(
                product_software_identity=product_software_identity(),
                bucket_id=bucket_id,
                taxpayer_tax_id=taxpayer_nif,
                work_unit=work_repo,
                calculation=calc_repo,
                bucket_event=event_repo,
            ),
            clock=datetime(2026, 4, 15, 10, 3, tzinfo=UTC),
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
        # The 2026 1T window authors no payment cutoff; the governed rule derives
        # 15 April 2026, the export's Madrid date, so the U export is checked and admitted.
        assert result.domiciliation_cutoff_unverified is False
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


def test_public_rectificativa_nota_three_keep_exports_full_refund_account_not_charge_account(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """A C rectificativa with stated c111 writes a refund destination under Nota 3."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            negative_result=True,
            casilla_111=Decimal("0"),
            operation=_authority_operation_for_test,
        )
        assert verified.casilla_values["111"] == Decimal("0")
        rectificativa = persist_rectificativa_with_nota_three(
            verified,
            taxpayer_nif=taxpayer_nif,
            work_repo=work_repo,
            calc_repo=calc_repo,
            operation=_authority_operation_for_test,
        )
        # An account outside the SEPA zone, so the DID page carries its whole
        # foreign-bank block beside the IBAN (Marca SEPA 3).
        refund_account = own_account(
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
            workflow_profile=nota_three_profile(
                taxpayer_nif=taxpayer_nif, bucket_id=bucket_id, refund_account=refund_account
            ),
            export_ports=modelo_export_ports_for_test(
                product_software_identity=product_software_identity(),
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
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            negative_result=True,
            casilla_111=Decimal("0"),
            operation=_authority_operation_for_test,
        )
        rectificativa = persist_rectificativa_with_nota_three(
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
                workflow_profile=nota_three_profile(
                    taxpayer_nif=taxpayer_nif, bucket_id=bucket_id, refund_account=None
                ),
                export_ports=modelo_export_ports_for_test(
                    product_software_identity=product_software_identity(),
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
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo = build_verified_modelo_303_revision(
            negative_result=True,
            casilla_111=Decimal("0"),
            operation=_authority_operation_for_test,
        )
        rectificativa = persist_rectificativa_with_nota_three(
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
                workflow_profile=nota_three_profile(
                    taxpayer_nif=taxpayer_nif, bucket_id=bucket_id, refund_account=None
                ),
                export_ports=modelo_export_ports_for_test(
                    product_software_identity=product_software_identity(),
                    taxpayer_tax_id=taxpayer_nif,
                    work_unit=work_repo,
                    calculation=CalculationRevisionCatalogueRepository(m303_rectificativa_taxpayer_tax_id=taxpayer_nif),
                    bucket_event=event_repo,
                ),
                clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
                operation=_authority_operation_for_test,
            )

        assert not output_path.exists()
