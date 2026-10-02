"""The calculation summary PDF over a real calculation and a real encrypted store.

The revision is calculated and verified through the same application services an
operator drives, the summary is signed with the profile's own key in encrypted
custody and published through the one export sink, and verification rebuilds the
report from the store. Every expected page figure is written out by hand from the
calculation's inputs rather than read back from the formatter.

Store-layer reasons are produced two ways. Where the store can be changed the way
a later operation would change it -- the revision filed, a filing record or a
verification report dropped, a revision removed, the filer's identity edited --
the store is changed. Where the store's own integrity forbids the change -- a
stored revision's identity covers its work unit, registry snapshot and source
traces, and one authority generation is published -- the document is changed
instead and re-signed with THIS profile's key, so the document layer passes and
only the store can object.
"""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pikepdf
import pypdfium2
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

from cadrumo.adapters.outbound.calculation_summary_pdf.summary_container import write_calculation_summary_pdf
from cadrumo.adapters.outbound.calculation_summary_pdf.summary_reading import read_calculation_summary_pdf
from cadrumo.adapters.persistence.profile.review_package_signing import (
    build_review_package_signing_keypair_capability,
    build_review_package_signing_keypair_reader,
)
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.tests.modelo_export_support import isolated_backend
from cadrumo.adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import upsert_test_profile_facts
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision
from cadrumo.application.modelo.calculation_report import (
    ModeloCalculationReport,
    ModeloCalculationReportSourceProvenance,
)
from cadrumo.application.modelo.calculation_report_certification import calculation_report_signature_is_valid
from cadrumo.application.modelo.calculation_report_document import (
    CalculationSummaryPdfRendering,
    serialize_calculation_report,
    serialize_calculation_report_csv,
)
from cadrumo.application.modelo.calculation_report_export import (
    ModeloCalculationReportCommand,
    ModeloCalculationReportResult,
    build_modelo_calculation_report_for_revision,
    export_modelo_calculation_report,
)
from cadrumo.application.modelo.calculation_report_verification import (
    CalculationSummaryStoreContext,
    CalculationSummaryVerification,
    CalculationSummaryVerificationOutcome,
    CalculationSummaryVerificationReason,
    verify_calculation_summary,
)
from cadrumo.application.modelo.calculation_summary_pdf_ports import (
    CSV_ATTACHMENT_NAME,
    REPORT_ATTACHMENT_NAME,
    SIGNATURE_ATTACHMENT_NAME,
    STATEMENT_ATTACHMENT_NAME,
)
from cadrumo.application.modelo.export_ports import ModeloExportPorts
from cadrumo.application.modelo.export_sink import ModeloExportOutputPathError
from cadrumo.application.modelo.review_package_signing import (
    ReviewPackageSigningKeypair,
    ensure_review_package_signing_keypair,
)
from cadrumo.core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from cadrumo.core.calculation_report_format import CalculationReportDocumentFormat
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.modelos.filing_record import ModeloRecordCatalogue
from cadrumo.domain.modelos.verification_report import VerificationReportCatalogue
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.domain.user_profile.values import UserProfileFact
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import (
    DEFAULT_130_BASELINE_INPUTS,
    DEFAULT_130_BINDING_VALUES,
    M130_INCOME_CASILLA,
    T1,
    T2,
    Repos,
    calculation_ports_for_test,
    file_revision,
    seed_work_unit,
    verify_revision,
)

__all__ = ["isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

Reason = CalculationSummaryVerificationReason
Outcome = CalculationSummaryVerificationOutcome

_EXPORTED_AT = T1

#: What the Spanish summary of the Modelo 130 baseline must show: income 10 000,
#: expenses 3 000, their difference 7 000 and the 20 per cent instalment on it,
#: each grouped with a point and carrying no decimal comma it was not given.
_EXPECTED_SPANISH_FIGURES = ("10.000", "3.000", "7.000", "1.400")


def _verified_130(repos: Repos) -> tuple[WorkUnit, CalculationRevision]:
    work_repo, calculation_repo, filing_repo, verification_repo, event_repo = repos
    work_unit = seed_work_unit(work_repo)
    with calculation_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        bucket_event_repository=event_repo,
    ) as ports:
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator-A",
            casilla_inputs=dict(DEFAULT_130_BASELINE_INPUTS),
            binding_values=dict(DEFAULT_130_BINDING_VALUES),
            ports=ports,
            clock=T1,
        )
    report = verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        bucket_event_repository=event_repo,
        filing_repository=filing_repo,
        clock=T1,
    )
    assert report.granted_verificado_completo is True
    return work_unit, calculation_repo.load().revisions[revision.calculation_revision_id]


def _export_ports(repos: Repos, work_unit: WorkUnit) -> ModeloExportPorts:
    work_repo, calculation_repo, filing_repo, verification_repo, event_repo = repos
    return modelo_export_ports_for_test(
        bucket_id=work_unit.bucket_id,
        work_unit=work_repo,
        calculation=calculation_repo,
        filing=filing_repo,
        verification=verification_repo,
        bucket_event=event_repo,
    )


def _profile_keypair(work_unit: WorkUnit) -> ReviewPackageSigningKeypair:
    return ensure_review_package_signing_keypair(
        bucket_id=work_unit.bucket_id,
        signing_keypair=build_review_package_signing_keypair_capability(bucket_id=work_unit.bucket_id),
    )


def _publish(
    repos: Repos,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    output: Path,
    *,
    document_format: CalculationReportDocumentFormat = CalculationReportDocumentFormat.PDF,
    replace_existing: bool = False,
) -> ModeloCalculationReportResult:
    return export_modelo_calculation_report(
        ModeloCalculationReportCommand(
            calculation_revision_id=revision.calculation_revision_id,
            document_format=document_format,
            report_language=OutputLanguage.ES,
            output_path=output,
            replace_existing=replace_existing,
        ),
        export_ports=_export_ports(repos, work_unit),
        signing_keypair=build_review_package_signing_keypair_capability(bucket_id=work_unit.bucket_id),
        operation=published_authority_operation(),
        clock=_EXPORTED_AT,
        pdf_writer=write_calculation_summary_pdf,
    )


def _store(repos: Repos, work_unit: WorkUnit) -> CalculationSummaryStoreContext:
    return CalculationSummaryStoreContext(
        active_bucket_id=work_unit.bucket_id,
        export_ports=_export_ports(repos, work_unit),
        signing_keypair=build_review_package_signing_keypair_reader(bucket_id=work_unit.bucket_id),
        operation=published_authority_operation(),
    )


def _verify(payload: bytes, repos: Repos, work_unit: WorkUnit) -> CalculationSummaryVerification:
    return verify_calculation_summary(payload, reader=read_calculation_summary_pdf, store=_store(repos, work_unit))


def _embedded(payload: bytes, name: str) -> bytes:
    with pikepdf.open(io.BytesIO(payload)) as pdf:
        return pdf.attachments[name].get_file().read_bytes()


def _embedded_report(payload: bytes) -> ModeloCalculationReport:
    decoded = json.loads(_embedded(payload, REPORT_ATTACHMENT_NAME))
    return ModeloCalculationReport.model_validate_json(
        json.dumps({"header": decoded["header"], "rows": decoded["rows"]})
    )


def _page_text(payload: bytes) -> str:
    document = pypdfium2.PdfDocument(payload)
    try:
        text = "\n".join(document[index].get_textpage().get_text_range() for index in range(len(document)))
    finally:
        document.close()
    return " ".join(text.split())


def _resigned(
    payload: bytes,
    keypair: ReviewPackageSigningKeypair,
    *,
    header: dict[str, object] | None = None,
    change_rows: Callable[[ModeloCalculationReport], ModeloCalculationReport] | None = None,
) -> bytes:
    """Rewrite the embedded report and render it again as a complete, consistently signed summary."""
    report = _embedded_report(payload)
    if header:
        report = report.model_copy(update={"header": report.header.model_copy(update=header)})
    if change_rows is not None:
        report = change_rows(report)
    return serialize_calculation_report(
        report,
        document_format=CalculationReportDocumentFormat.PDF,
        pdf_rendering=CalculationSummaryPdfRendering(writer=write_calculation_summary_pdf, keypair=keypair),
    ).payload


@pytest.fixture
def published(repos: Repos, tmp_path: Path) -> tuple[WorkUnit, CalculationRevision, bytes]:
    work_unit, revision = _verified_130(repos)
    output = tmp_path / "modelo-130-summary.pdf"
    _publish(repos, work_unit, revision, output)
    return work_unit, revision, output.read_bytes()


def test_a_real_calculation_publishes_a_summary_embedding_its_report_and_csv(repos: Repos, tmp_path: Path) -> None:
    work_unit, revision = _verified_130(repos)
    pdf_path = tmp_path / "modelo-130-summary.pdf"
    csv_path = tmp_path / "modelo-130-report.csv"

    result = _publish(repos, work_unit, revision, pdf_path)
    _publish(repos, work_unit, revision, csv_path, document_format=CalculationReportDocumentFormat.CSV)

    landed = pdf_path.read_bytes()
    report = build_modelo_calculation_report_for_revision(
        revision.calculation_revision_id,
        active_bucket_id=work_unit.bucket_id,
        export_ports=_export_ports(repos, work_unit),
        signing_keypair=build_review_package_signing_keypair_capability(bucket_id=work_unit.bucket_id),
        operation=published_authority_operation(),
        report_language=OutputLanguage.ES,
        exported_at=_EXPORTED_AT,
    )
    embedded_report = _embedded(landed, REPORT_ATTACHMENT_NAME)
    embedded_csv = _embedded(landed, CSV_ATTACHMENT_NAME)
    statement = json.loads(_embedded(landed, STATEMENT_ATTACHMENT_NAME))

    assert landed.startswith(b"%PDF-1.7")
    assert result.document_format is CalculationReportDocumentFormat.PDF
    assert result.file_sha256 == hashlib.sha256(landed).hexdigest()
    assert embedded_report == report.canonical_bytes()
    assert hashlib.sha256(embedded_report).hexdigest() == result.report_sha256 == statement["report_sha256"]
    assert embedded_csv == csv_path.read_bytes() == serialize_calculation_report_csv(report)
    assert hashlib.sha256(embedded_csv).hexdigest() == statement["csv_sha256"]


def test_the_signature_verifies_with_the_profile_key_and_one_tampered_byte_fails(
    published: tuple[WorkUnit, CalculationRevision, bytes],
) -> None:
    work_unit, _revision, payload = published
    profile_key = _profile_keypair(work_unit).public_key_hex
    statement = _embedded(payload, STATEMENT_ATTACHMENT_NAME)
    signature = _embedded(payload, SIGNATURE_ATTACHMENT_NAME)
    tampered = bytearray(statement)
    tampered[10] ^= 0x01

    assert json.loads(statement)["signing_key"]["public_key_hex"] == profile_key
    assert calculation_report_signature_is_valid(statement, signature, public_key_hex=profile_key)
    assert not calculation_report_signature_is_valid(bytes(tampered), signature, public_key_hex=profile_key)


def test_the_page_shows_the_figures_and_the_taxpayer_and_the_metadata_shows_neither(
    published: tuple[WorkUnit, CalculationRevision, bytes],
) -> None:
    _work_unit, _revision, payload = published
    header = _embedded_report(payload).header
    text = _page_text(payload)

    for figure in _EXPECTED_SPANISH_FIGURES:
        assert figure in text, f"{figure} is not on the page"
    assert header.taxpayer_tax_id in text
    assert header.taxpayer_name in text
    with pikepdf.open(io.BytesIO(payload)) as pdf:
        packet = pdf.Root.Metadata.read_bytes().decode("utf-8")
        assert "/Info" not in pdf.trailer
    assert header.taxpayer_tax_id not in packet
    assert header.taxpayer_name not in packet


def test_two_publications_of_one_revision_are_byte_identical(repos: Repos, tmp_path: Path) -> None:
    work_unit, revision = _verified_130(repos)
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"

    _publish(repos, work_unit, revision, first)
    _publish(repos, work_unit, revision, second)

    assert first.read_bytes() == second.read_bytes()


def test_the_sink_refuses_to_overwrite_a_summary_unless_asked(repos: Repos, tmp_path: Path) -> None:
    work_unit, revision = _verified_130(repos)
    output = tmp_path / "summary.pdf"
    output.write_bytes(b"an earlier file")

    with pytest.raises(ModeloExportOutputPathError):
        _publish(repos, work_unit, revision, output)
    assert output.read_bytes() == b"an earlier file"

    _publish(repos, work_unit, revision, output, replace_existing=True)
    assert output.read_bytes().startswith(b"%PDF")


def test_a_pristine_summary_is_verified_against_the_store(
    repos: Repos,
    published: tuple[WorkUnit, CalculationRevision, bytes],
) -> None:
    work_unit, _revision, payload = published

    verification = _verify(payload, repos, work_unit)

    assert verification.outcome is Outcome.VERIFIED
    assert verification.store_checked is True
    assert verification.reasons == ()


def test_filing_after_export_is_reported_without_refusing_the_summary(
    repos: Repos,
    published: tuple[WorkUnit, CalculationRevision, bytes],
) -> None:
    work_unit, revision, payload = published
    work_repo, calculation_repo, filing_repo, _verification_repo, event_repo = repos
    file_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        filing_repository=filing_repo,
        bucket_event_repository=event_repo,
        clock=T2,
    )

    verification = _verify(payload, repos, work_unit)

    assert verification.outcome is Outcome.VERIFIED_WITH_LATER_CHANGES
    assert set(verification.reasons) == {Reason.REVISION_STATE_CHANGED, Reason.FILED_SINCE_EXPORT}


def test_a_filing_record_the_store_no_longer_holds_is_refused(repos: Repos, tmp_path: Path) -> None:
    work_unit, revision = _verified_130(repos)
    work_repo, calculation_repo, filing_repo, _verification_repo, event_repo = repos
    file_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        filing_repository=filing_repo,
        bucket_event_repository=event_repo,
        clock=T2,
    )
    output = tmp_path / "filed-summary.pdf"
    _publish(repos, work_unit, calculation_repo.load().revisions[revision.calculation_revision_id], output)
    assert _verify(output.read_bytes(), repos, work_unit).outcome is Outcome.VERIFIED
    filing_repo.save(ModeloRecordCatalogue())

    verification = _verify(output.read_bytes(), repos, work_unit)

    assert verification.outcome is Outcome.REFUSED
    assert verification.reasons == (Reason.FILING_RECORD_MISMATCH,)


def test_a_removed_verification_report_is_refused(
    repos: Repos,
    published: tuple[WorkUnit, CalculationRevision, bytes],
) -> None:
    work_unit, _revision, payload = published
    repos[3].save(VerificationReportCatalogue())

    verification = _verify(payload, repos, work_unit)

    assert verification.outcome is Outcome.REFUSED
    assert Reason.VERIFICATION_REPORT_MISMATCH in verification.reasons


def test_a_taxpayer_identity_edited_after_export_fails_the_rebuild(
    repos: Repos,
    published: tuple[WorkUnit, CalculationRevision, bytes],
) -> None:
    """The report names the filer, so an identity the profile no longer holds is not reproduced."""
    work_unit, _revision, payload = published
    upsert_test_profile_facts(work_unit.bucket_id, (UserProfileFact(path="identity.surnames", value="Renamed"),))

    verification = _verify(payload, repos, work_unit)

    assert verification.outcome is Outcome.REFUSED
    assert verification.reasons == (Reason.REPORT_REBUILD_MISMATCH,)


def test_a_source_trace_the_store_never_recorded_is_named_as_a_provenance_mismatch(
    repos: Repos,
    published: tuple[WorkUnit, CalculationRevision, bytes],
) -> None:
    """A stored revision's traces are part of its identity, so the document is what changes here."""
    work_unit, _revision, payload = published
    trace = ModeloCalculationReportSourceProvenance(
        resolver_id="ledger_renta_income_aggregation",
        resolved_binding_source=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        contributor_source_kind=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION.value,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref_digest="collectible_invoice:hmac-sha256:" + "e" * 64,
        source_content_digest="sha256:" + "f" * 64,
    )

    def add_trace(report: ModeloCalculationReport) -> ModeloCalculationReport:
        rows = tuple(
            row.model_copy(update={"source_provenance": (trace,)}) if row.casilla_id == M130_INCOME_CASILLA else row
            for row in report.rows
        )
        return report.model_copy(update={"rows": rows})

    resigned = _resigned(payload, _profile_keypair(work_unit), change_rows=add_trace)
    verification = _verify(resigned, repos, work_unit)

    assert verification.outcome is Outcome.REFUSED
    assert set(verification.reasons) == {Reason.SOURCE_PROVENANCE_MISMATCH, Reason.REPORT_REBUILD_MISMATCH}


def test_a_revision_the_store_no_longer_holds_is_refused(
    repos: Repos,
    published: tuple[WorkUnit, CalculationRevision, bytes],
) -> None:
    work_unit, revision, payload = published
    calculation_repo = repos[1]
    catalogue = calculation_repo.load()
    remaining = {key: value for key, value in catalogue.revisions.items() if key != revision.calculation_revision_id}
    calculation_repo.save(catalogue.model_copy(update={"revisions": remaining}))

    verification = _verify(payload, repos, work_unit)

    assert verification.reasons == (Reason.CALCULATION_REVISION_NOT_FOUND,)


@pytest.mark.parametrize(
    ("header", "reason"),
    (
        ({"work_unit_id": "9" * 64}, Reason.WORK_UNIT_MISMATCH),
        (
            {
                "registry_snapshot_ref": RegistrySnapshotRef(
                    modelo="130",
                    revision_id="another-revision",
                    modelo_year=2026,
                    period="1T",
                ),
            },
            Reason.REGISTRY_SNAPSHOT_MISMATCH,
        ),
        ({"authority_logical_generation": "7" * 64}, Reason.AUTHORITY_GENERATION_UNAVAILABLE),
    ),
)
def test_a_document_this_profile_signed_that_the_store_does_not_describe_is_refused(
    repos: Repos,
    published: tuple[WorkUnit, CalculationRevision, bytes],
    header: dict[str, object],
    reason: CalculationSummaryVerificationReason,
) -> None:
    work_unit, _revision, payload = published
    resigned = _resigned(payload, _profile_keypair(work_unit), header=header)
    assert verify_calculation_summary(resigned, reader=read_calculation_summary_pdf).outcome is Outcome.VALID_UNPINNED

    verification = _verify(resigned, repos, work_unit)

    assert verification.outcome is Outcome.REFUSED
    assert reason in verification.reasons
    if reason is Reason.AUTHORITY_GENERATION_UNAVAILABLE:
        assert Reason.REPORT_REBUILD_MISMATCH not in verification.reasons, "an unprovable rebuild is not attempted"


def test_a_forgery_under_another_key_is_refused_by_key_and_by_rebuild(
    repos: Repos,
    published: tuple[WorkUnit, CalculationRevision, bytes],
) -> None:
    work_unit, _revision, payload = published
    forger_key = Ed25519PrivateKey.from_private_bytes(hashlib.sha256(b"a forger's own key").digest())
    forger = ReviewPackageSigningKeypair(
        bucket_id=work_unit.bucket_id,
        private_key_hex=forger_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex(),
        public_key_hex=forger_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
        created_at=_EXPORTED_AT,
    )

    def raise_income(report: ModeloCalculationReport) -> ModeloCalculationReport:
        rows = tuple(
            row.model_copy(update={"value": Decimal("1.00")}) if row.casilla_id == M130_INCOME_CASILLA else row
            for row in report.rows
        )
        return report.model_copy(update={"rows": rows})

    forged = _resigned(payload, forger, change_rows=raise_income)

    assert verify_calculation_summary(forged, reader=read_calculation_summary_pdf).outcome is Outcome.VALID_UNPINNED
    verification = _verify(forged, repos, work_unit)
    assert verification.outcome is Outcome.REFUSED
    assert {Reason.SIGNING_KEY_NOT_THIS_PROFILE, Reason.REPORT_REBUILD_MISMATCH} <= set(verification.reasons)
