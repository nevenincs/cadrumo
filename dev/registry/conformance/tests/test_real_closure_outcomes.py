"""Real-authority outcome proofs for the registry closure loader.

These tests deliberately avoid constructing closure rows or limbs.  Every
assertion starts with a loaded ``ValidatedRegistryAuthority`` and reaches the
report through ``load_registry_closure_report``.  The positive filing limb uses
the canonical generated Modelo 151 export tree and executes ``export_draft``;
the canonical census remains authoritative and therefore keeps that row
unmeasured rather than letting a test fixture invent registry completeness.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.application.filing.producer_snapshot import (
    FilingElectionFacts,
    GeneralFilingProfileFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
)
from cadrumo.application.registry.filing_export_coverage import compose_filing_export_coverage
from cadrumo.application.registry.source_connectivity import load_source_connectivity_census
from cadrumo.application.registry.source_connectivity_coverage import compose_source_connectivity_coverage
from cadrumo.application.registry.temporal_coverage import compose_temporal_coverage
from cadrumo.core.modelo import Modelo
from cadrumo.core.payment_election import PaymentElection
from cadrumo.core.period import Period
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.product_identity import AeatProductSoftwareEvidence, AeatProductSoftwareIdentity
from cadrumo.core.refund_election import RefundElection
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.core.source_connectivity import SourceConnectivityDisposition
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.deadlines.models import RefundAccount
from cadrumo.domain.filing.schema import ModeloDraft, ModeloValue, ModeloValueKind
from cadrumo.domain.submission._protocols import ModeloDraftStatus

from ...filing_export_proof import (
    FilingExportLiveProofEntry,
    FilingExportOfficialOffsetProbe,
    LiveFilingExportProofAuthority,
)
from ..closure import build_registry_closure_report, load_registry_closure_report

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_AS_OF = date(2026, 8, 24)
_REPO_ROOT = Path(__file__).parents[4]
_M151_REVISION = "2025-y-siguientes"
_M151_PAYLOAD_SHA256 = "6bc099105e319c1fac9ddebfd09e2bb319c9cafd0d72cdaaf19919ae7d5900f2"
_M151_PAYLOAD_BYTES = 11_618


@cache
def _canonical_report():
    """Load the shipped report once without inventing either proof authority."""
    return load_registry_closure_report(as_of=_AS_OF, registry_authority=bundled_authority())


def test_real_live_filing_success_cannot_invent_a_complete_source_limb() -> None:
    """Real emitted bytes satisfy filing, while absent census scope keeps release refused."""
    authority = bundled_authority()
    report = load_registry_closure_report(
        as_of=_AS_OF,
        registry_authority=authority,
        filing_proof_authority=_m151_live_filing_authority(authority),
    )
    row = next(item for item in report.rows if (item.modelo, item.revision) == (Modelo.M151, _M151_REVISION))

    assert row.temporal_coverage.status == "validated"
    assert row.filing_export is not None
    assert row.filing_export.outcome == "satisfied"
    assert row.source_connectivity is not None
    assert (row.source_connectivity.outcome, row.source_connectivity.refusal.reason) == (
        "unmeasured",
        "unmeasured",
    )
    assert row.predicate_outcome == "refused"
    assert report.satisfied_revision_count >= 1
    assert not report.release_eligible


def test_real_below_grade_row_is_complete_from_canonical_manual_source_evidence() -> None:
    """M036's real manual source evidence completes its non-filing closure row."""
    report = _canonical_report()
    row = next(item for item in report.rows if (item.modelo, item.revision) == (Modelo.M036, "2025-02-03-y-siguientes"))

    assert row.temporal_coverage.status == "validated"
    assert row.filing_export is not None
    assert (row.filing_export.outcome, row.filing_export.evidence, row.filing_export.refusal) == (
        "not_applicable",
        (),
        None,
    )
    assert row.source_connectivity is not None
    assert row.source_connectivity.outcome == "satisfied"
    assert row.source_connectivity.refusal is None
    assert {evidence.authority for evidence in row.source_connectivity.evidence} == {
        "source-domain-to-casilla-connectivity:censo.modelo-036-profile-status",
    }
    assert row.predicate_outcome == "satisfied"
    assert row.refusals == ()
    assert report.satisfied_revision_count >= 1
    assert not report.release_eligible


def test_real_complete_below_grade_row_refuses_mutated_manual_source_evidence() -> None:
    """Removing M036's terminal evidence makes the real composed row refused again."""
    authority = bundled_authority()
    census = load_source_connectivity_census()
    m036 = next(entry for entry in census.entries if entry.candidate_id == "censo.modelo-036-profile-status")
    mutated_census = _validated_census(
        census,
        entries=tuple(entry for entry in census.entries if entry.candidate_id != m036.candidate_id),
    )
    report = _compose_report(authority=authority, census=mutated_census)
    row = next(item for item in report.rows if (item.modelo, item.revision) == (Modelo.M036, "2025-02-03-y-siguientes"))

    assert row.temporal_coverage.status == "validated"
    assert row.source_connectivity is not None
    assert (row.source_connectivity.outcome, row.source_connectivity.refusal.reason) == (
        "unmeasured",
        "unmeasured",
    )
    assert row.filing_export is not None
    assert row.filing_export.outcome == "not_applicable"
    assert row.predicate_outcome == "refused"


def test_real_complete_below_grade_row_refuses_pending_source_disposition_mutation() -> None:
    """M036 cannot keep completeness after its terminal manual disposition becomes pending."""
    authority = bundled_authority()
    census = load_source_connectivity_census()
    m036 = next(entry for entry in census.entries if entry.candidate_id == "censo.modelo-036-profile-status")
    follow_up = next(entry.bounded_follow_up for entry in census.entries if entry.bounded_follow_up is not None)
    pending_m036 = m036.model_copy(
        update={
            "disposition": SourceConnectivityDisposition.CONNECT_CANDIDATE,
            "bounded_follow_up": follow_up,
        },
    )
    mutated_census = _validated_census(
        census,
        entries=tuple(pending_m036 if entry.candidate_id == m036.candidate_id else entry for entry in census.entries),
    )
    report = _compose_report(authority=authority, census=mutated_census)
    row = next(item for item in report.rows if (item.modelo, item.revision) == (Modelo.M036, "2025-02-03-y-siguientes"))

    assert row.source_connectivity is not None
    assert (row.source_connectivity.outcome, row.source_connectivity.refusal.reason) == (
        "refused",
        "unreviewed_evidence",
    )
    assert row.source_connectivity.refusal.disposition.work_item == follow_up.action_id
    assert row.predicate_outcome == "refused"


def test_real_grade_scope_row_guards_bite_both_participation_mutations() -> None:
    """Real composed rows reject filing participation that contradicts temporal grade."""
    report = _canonical_report()
    below_grade = next(
        item for item in report.rows if (item.modelo, item.revision) == (Modelo.M036, "2025-02-03-y-siguientes")
    )
    filing_grade = next(item for item in report.rows if (item.modelo, item.revision) == (Modelo.M100, "2025"))
    assert below_grade.filing_export is not None
    assert filing_grade.filing_export is not None

    below_grade_payload = below_grade.model_dump(mode="python", exclude={"refusals", "predicate_outcome"})
    below_grade_payload["filing_export"] = filing_grade.filing_export.model_dump(mode="python")
    below_grade_payload["filing_export"].update(
        modelo=below_grade.modelo,
        revision=below_grade.revision,
    )
    with pytest.raises(ValidationError, match="below-filing temporal coverage requires"):
        below_grade.__class__.model_validate(below_grade_payload)

    filing_grade_payload = filing_grade.model_dump(mode="python", exclude={"refusals", "predicate_outcome"})
    filing_grade_payload["filing_export"] = below_grade.filing_export.model_dump(mode="python")
    filing_grade_payload["filing_export"].update(
        modelo=filing_grade.modelo,
        revision=filing_grade.revision,
    )
    with pytest.raises(ValidationError, match="filing-grade temporal coverage requires"):
        filing_grade.__class__.model_validate(filing_grade_payload)


def test_real_loader_reports_stale_layout_bytes_from_a_live_catalogue_mutation() -> None:
    """A changed official source digest remains visible after all three limbs compose."""
    authority = bundled_authority()
    modelo = authority.modelo(Modelo.M100)
    revision = modelo.revisions["2025"]
    source_id = next(
        source_ref
        for layout in revision.export_layouts
        for source_ref in layout.source_refs
        if authority.catalogues.sources[source_ref].evidence_tier == "layout_authority"
    )
    source = authority.catalogues.sources[source_id]
    catalogues = authority.catalogues.model_copy(
        update={
            "sources": {
                **authority.catalogues.sources,
                source_id: source.model_copy(update={"sha256": "0" * 64}),
            },
        },
    )
    mutated = replace(authority, catalogues=catalogues, _snapshots={})

    report = load_registry_closure_report(as_of=_AS_OF, registry_authority=mutated)
    row = next(item for item in report.rows if (item.modelo, item.revision) == (Modelo.M100, "2025"))

    assert row.filing_export is not None
    assert (row.filing_export.outcome, row.filing_export.refusal.reason) == (
        "refused",
        "stale_evidence",
    )
    assert row.predicate_outcome == "refused"


def test_real_loader_reports_cross_limb_disagreement_from_divergent_authority_cache() -> None:
    """A stale authority lookup cache cannot cross-satisfy another loaded revision."""
    authority = bundled_authority()
    modelo = authority.modelo(Modelo.M303)
    selected = modelo.revisions["2025"]
    selector = selected.period_selector.model_copy(
        update={"years": (2026,), "year_from": None, "year_to": None},
    )
    divergent_revision = selected.model_copy(update={"period_selector": selector})
    divergent_modelo = modelo.model_copy(
        update={"revisions": {divergent_revision.id: divergent_revision}},
    )
    mutated = replace(
        authority,
        _modelos_by_id={**authority._modelos_by_id, divergent_modelo.id: divergent_modelo},
        _snapshots={},
    )

    report = load_registry_closure_report(as_of=_AS_OF, registry_authority=mutated)
    row = next(item for item in report.rows if (item.modelo, item.revision) == (Modelo.M303, "2026-y-siguientes"))

    assert row.temporal_coverage.failure_code == "selected_revision_mismatch"
    assert row.filing_export is not None
    assert (row.filing_export.outcome, row.filing_export.refusal.reason) == (
        "refused",
        "cross_limb_disagreement",
    )
    assert row.predicate_outcome == "refused"


def _compose_report(*, authority, census):
    """Join real temporal, source, and export composers with only census evidence varied."""
    return build_registry_closure_report(
        temporal_coverage=compose_temporal_coverage(authority=authority),
        source_connectivity=compose_source_connectivity_coverage(
            authority=authority,
            census=census,
            as_of=_AS_OF,
        ),
        filing_export=compose_filing_export_coverage(authority=authority),
        as_of=_AS_OF,
    )


def _validated_census(census, *, entries):
    """Revalidate an in-memory mutation through the canonical census contract."""
    return census.__class__.model_validate(
        {
            **census.model_dump(mode="python"),
            "entries": entries,
        },
    )


def _m151_live_filing_authority(authority) -> LiveFilingExportProofAuthority:
    return LiveFilingExportProofAuthority(
        workspace_root=_REPO_ROOT,
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        authority=authority,
        entries=(_m151_live_proof_entry(authority),),
    )


def _m151_live_proof_entry(authority) -> FilingExportLiveProofEntry:
    period = Period.from_year_and_code(2023, "0A")
    return FilingExportLiveProofEntry(
        modelo=Modelo.M151,
        revision=_M151_REVISION,
        design_epoch="2023",
        filing_year=2023,
        period=period,
        draft=_m151_draft(authority, period=period),
        producer_snapshot=_m151_producer_snapshot(),
        expected_payload_sha256=_M151_PAYLOAD_SHA256,
        expected_emitted_bytes=_M151_PAYLOAD_BYTES,
        official_offset_probes=(
            FilingExportOfficialOffsetProbe(
                record_id="m151-page-01",
                field_id="m151-2023.pagina01.f001",
            ),
        ),
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity=AeatProductSoftwareIdentity(
            program_identifier="C151",
            developer_tax_id="Y0000001S",
            evidence=(
                AeatProductSoftwareEvidence(
                    reference="test:registry-closure:m151-live-emission",
                    digest="a" * 64,
                ),
            ),
        ),
    )


def _m151_draft(authority, *, period: Period) -> ModeloDraft:
    snapshot = authority.snapshot(Modelo.M151, filing_year=2023, period="0A")
    fields = {
        str(field.casilla_id): field
        for layout in snapshot.revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.casilla_id is not None
    }
    values = tuple(
        ModeloValue(
            casilla_id=casilla.id,
            value=value,
            kind=ModeloValueKind.LITERAL,
            source="bundled canonical M151 live-emission integration proof",
        )
        for casilla in snapshot.revision.casillas
        if (value := _m151_non_positive_value(casilla, fields.get(str(casilla.id)))) is not None
    )
    timestamp = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
    return ModeloDraft(
        draft_id="registry-closure-m151-live-emission",
        modelo=Modelo.M151,
        period=period,
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=RegistrySnapshotRef(
            modelo=Modelo.M151,
            revision_id=snapshot.revision.id,
            modelo_year=2023,
            period="0A",
        ),
        status=ModeloDraftStatus.APROBADO,
        values=values,
        created_at=timestamp,
        updated_at=timestamp,
        schema_version=f"registry:151:{snapshot.revision.id}",
    )


def _m151_non_positive_value(casilla, field):
    """Supply only wire-required, identity, and non-positive numeric values."""
    if field is not None and field.value_policy is ExportValuePolicy.YYYYMMDD:
        return "20230101"
    if field is not None and field.allowed_values:
        return field.allowed_values[0]
    if casilla.data_type == "money":
        return Decimal("0")
    if casilla.data_type == "year":
        return 2023
    if casilla.data_type == "period_code":
        return "0A"
    if casilla.data_type == "nif":
        return "12345678Z"
    if field is not None and field.value_policy is ExportValuePolicy.DIGIT_STRING:
        return "0" * field.length
    return None


def _m151_producer_snapshot():
    refund_account = RefundAccount(
        iban="GB82WEST12345698765432",
        swift_bic="DEUTDEFF",
        bank_name="Refund Bank",
        bank_address="Refund Street 1",
        bank_city="Berlin",
        bank_country_code="DE",
        sepa_marca="S",
    )
    return build_filing_producer_snapshot(
        modelo=Modelo.M151,
        taxpayer_tax_id="12345678Z",
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name=None,
            given_name="Ana",
            surnames="Prueba",
            full_name="Ana Prueba",
        ),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoria Prueba"),
        model_profile=GeneralFilingProfileFacts(),
        elections=FilingElectionFacts(
            result_disposition=ResultDisposition.DEVOLUCION,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.DEVOLVER,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=None,
        m303_filing_facts=None,
        refund_account=refund_account,
        charge_account=None,
    )
