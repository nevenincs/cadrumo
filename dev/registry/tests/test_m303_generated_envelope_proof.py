"""End-to-end publication and filing-boundary proof for the committed M303 tree.

This deliberately uses the real 2026 generated target and the generator's
ordinary target-only isolation.  It does not make a test layout or a copied
export tree into a positive authority.
"""

from __future__ import annotations

import shutil
from datetime import date as _prov_date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from pydantic import ValidationError

from cadrumo.application.aggregation import IvaDifferentiatedDeductionContribution
from cadrumo.application.calculations.m303_regimen_simplificado import calculate_m303_regimen_simplificado_result
from cadrumo.application.filing.export import render_filing_envelope
from cadrumo.application.filing.export_envelope import FilingEnvelopeRenderRequest, FilingEnvelopeRenderResult
from cadrumo.application.filing.projection import _project_record
from cadrumo.application.filing.tests import test_m303_did_account_wire_isolated_authority as m303_did
from cadrumo.application.filing.tests.test_producer_snapshot import _m303_exonerado_evidence
from cadrumo.core.filing_projection_ref import (
    M303DifferentiatedDeductionProjectionRef,
    M303Exonerado390ActivityProjectionRef,
    M303ProrrataActivityProjectionRef,
    M303RegimenSimplificadoFact,
)
from cadrumo.core.iva_deduction_fact import IvaDeductionFactKind
from cadrumo.core.period import Period
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.prorrata_register import (
    ProrrataActivityRowType,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.bienes_inversion.regularizacion_parameters import BienesInversionParameterProvenance
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry._supplementary_orden import compile_supplementary_ordenes
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.loader import load_modelo_directory, load_registry_tree
from cadrumo.domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from cadrumo.domain.filing.errors import FilingExportValidationError
from cadrumo.domain.filing_evidence import FilingEvidenceReference
from cadrumo.domain.iva.regimen_simplificado_rows import (
    ActividadNoAgricolaSimplificado,
    EntradaModuloSimplificado,
    HechoActividadSimplificado,
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from cadrumo.domain.modelos.calculation_revision_m303_handoff import M303RegimenSimplificadoFilingEvidence
from cadrumo.domain.prorrata_register.register import (
    ProrrataActivityRow,
    ProrrataRegister,
    ProrrataRegisterEntry,
    SectorDefinition,
)
from cadrumo.tests.registry_snapshot import build_snapshot

from ..pipeline._export_tree import render_complete_export_tree
from ..pipeline._provenance_manifest import (
    EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    ExportFragmentTarget,
    collect_export_fragment_output_digests,
    load_export_fragment_provenance_manifest,
    normalised_loader_semantics,
)
from ..pipeline._tree_check import GeneratedExportTreeCheckContext, check_generated_export_tree
from ..pipeline._tree_validation import GeneratedExportTreeValidationContext
from ..pipeline.render_check import parsed_tree_file
from .test_generated_export_trees import (
    _GENERATED_TREES,
    _authorities,
    _isolated_authority,
    _stage_continuity_metadata,
    _supporting_modelos,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


#: Provenance stamped onto directly-constructed projections in this module. A
#: result must name the registry declaration its figures came from; these tests
#: build results by hand rather than by projection, so they state it explicitly.
_PROVENANCE = BienesInversionParameterProvenance(
    modelo_id="303",
    revision_id="2025",
    parameter_ids=("m303-bien-inversion-ventana-anos-mueble",),
    resolved_on=_prov_date(2025, 6, 1),
)


def _m303_2026_tree():
    return next(
        tree
        for tree in _GENERATED_TREES
        if tree.modelo == "303"
        and tree.source_ref == "aeat-dr-303-2026"
        and tree.epoch == "2026"
        and tree.filing_year == 2026
        and tree.period == "4T"
    )


def _tree_bytes(export_root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(export_root).as_posix(): path.read_bytes()
        for path in sorted(export_root.rglob("*"))
        if path.is_file()
    }


def _render_isolated_tree(tree, root: Path):
    assert root.drive == tree.committed.drive == bundled_path().drive
    assert not root.exists()
    semantic_map, render_profile, joined, evidence, transport = _authorities(tree)
    registry_root = _isolated_authority(tree, root)
    continuity_metadata_modelo_root = _stage_continuity_metadata(tree, root)
    export_root = registry_root / "modelos" / tree.modelo / "revisions" / tree.revision / "export"
    render_complete_export_tree(
        export_root,
        revision_id=tree.revision,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=transport,
        render_profile=render_profile,
        render_profile_source_evidence=evidence,
    )
    return (
        registry_root,
        continuity_metadata_modelo_root,
        export_root,
        semantic_map,
        render_profile,
        joined,
        evidence,
        transport,
    )


def _committed_tree_hashes(tree) -> tuple[tuple[str, str], ...]:
    return tuple((item.relative_path, item.sha256) for item in collect_export_fragment_output_digests(tree.committed))


def _m303_2026_prorrata_and_differentiated_producer(*, snapshot, catalogues):
    """Return one source-owned live DP30305 value arrival, without a test layout."""
    filing_year = snapshot.filing_year
    register = ProrrataRegister(
        sector_definitions=(
            SectorDefinition(sector_id="a", letra=SectorDiferenciadoLetra.A, member_activity_codes=("4711",)),
            SectorDefinition(sector_id="b", letra=SectorDiferenciadoLetra.B, member_activity_codes=("6820",)),
        ),
        entries=tuple(
            ProrrataRegisterEntry(
                ejercicio=filing_year,
                sector_id=sector_id,
                regime=ProrrataRegisterRegime.GENERAL,
                especial_transition=None,
                provisional_percentage=Decimal("50"),
                provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
            )
            for sector_id in (None, "a", "b")
        ),
        activity_rows=tuple(
            ProrrataActivityRow(
                ejercicio=filing_year,
                activity_id=f"m303-proof-prorrata-{slot}",
                slot=slot,
                cnae_code=f"47{slot}",
                operaciones_total=Decimal("100"),
                operaciones_con_derecho=Decimal("50"),
                prorrata_type=ProrrataActivityRowType.GENERAL,
                percentage=Decimal("50"),
                evidence_reference=f"test:m303-proof:prorrata:{slot}",
            )
            for slot in range(1, 6)
        ),
    )
    contribution_kinds = tuple(
        kind for kind in IvaDeductionFactKind if kind is not IvaDeductionFactKind.INVESTMENT_GOODS_REGULARISATION
    )
    contributions = tuple(
        IvaDifferentiatedDeductionContribution(
            sector_id=sector_id,
            deduction_fact_kind=kind,
            source_ledger_ids=(f"test:m303-proof:{sector_id}:{index}",),
            base_amount=Decimal("100"),
            deducible_iva_amount=Decimal("20"),
        )
        for sector_id in ("a", "b")
        for index, kind in enumerate(contribution_kinds, start=1)
    )
    regimen_evidence = _m303_2026_6919_regimen_evidence(snapshot, catalogues=catalogues)
    period = Period.from_year_and_code(filing_year, "1T")
    facts = m303_did.M303FilingFactSet(
        joint_return_elected=False,
        annual_volume_nonzero=False,
        insolvency=None,
        exonerado_390=_m303_exonerado_evidence(applicable=True),
        regimen_simplificado=regimen_evidence,
        regimen_simplificado_result=regimen_evidence.calculation_result,
        period=period,
        supplier_regime=m303_did.M303SupplierRegimeArrival(
            period=period,
            recipient_of_cash_accounting_operations=False,
            source_ledger_ids=(),
        ),
        prorrata_transition=m303_did.M303ProrrataTransitionArrival(
            period=period,
            transition=None,
            register_evidence=(),
        ),
        prorrata_register=register,
        differentiated_contributions=contributions,
        bienes_register=m303_did.BienesInversionIvaRegister(),
        regularisation_result=m303_did.RegistroRegularizacionResult(
            regularizacion_year=filing_year,
            rows=(),
            proposed_casilla_43=Decimal("0"),
            computed_count=0,
            pending_percentage_count=0,
            sector_contributions=(),
            parameters_provenance=_PROVENANCE,
        ),
    )
    taxpayer = m303_did._taxpayer_profile()
    assert taxpayer.iva is not None
    producer = m303_did.build_filing_producer_snapshot(
        modelo=m303_did.Modelo.M303,
        taxpayer_tax_id=taxpayer.tax_id,
        taxpayer_identity=m303_did.TaxpayerIdentityFactSet(
            legal_name=None,
            given_name="María",
            surnames="García López",
            full_name="María García López",
        ),
        presenter=m303_did.PresenterIdentity(tax_id="00000000T", full_name="Gestoría Ejemplo"),
        model_profile=taxpayer.iva,
        elections=m303_did._elections(ResultDisposition.DEVOLUCION),
        amendment_evidence=None,
        refund_account=taxpayer.iva.refund_account,
        charge_account=taxpayer.iva.charge_account,
        m303_filing_facts=facts,
    )
    return snapshot, producer


def _m303_2026_6919_regimen_evidence(snapshot, *, catalogues):
    """Build two official 691.9 rows so the real f022 field carries their wire identity."""
    period = Period.from_year_and_code(snapshot.filing_year, "1T")
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED,
    )
    regimen_snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=snapshot,
        scope_decision=scope,
    )
    annual_activities = tuple(
        activity for activity in regimen_snapshot.orden.activities if activity.iae_epigrafe == "691.9"
    )
    assert tuple(activity.auxiliary_activity_indicator for activity in annual_activities) == ("1", "2")
    evidence = FilingEvidenceReference(reference="test:s16:m303-2026:691.9")
    rows = RegimenSimplificadoFilingRows(
        ejercicio=period.filing_year,
        activities=tuple(
            ActividadNoAgricolaSimplificado(
                orden_id=activity.orden_id,
                ejercicio=period.filing_year,
                activity_id=activity.orden_id,
                iae_epigrafe="691.9",
                auxiliary_activity_indicator=activity.auxiliary_activity_indicator,
                modulos=tuple(
                    EntradaModuloSimplificado(
                        module_identity=module.identity,
                        declared_quantity=Decimal("1"),
                        evidence_reference=evidence,
                    )
                    for module in activity.modulos
                ),
                facts=tuple(
                    HechoActividadSimplificado(
                        fact=M303RegimenSimplificadoFact.CUOTA_DEVENGADA_OPERACIONES_CORRIENTES,
                        value=Decimal("1"),
                        evidence_reference=evidence,
                    )
                    for _identity in activity.applicable_fact_identities
                ),
                evidence_reference=evidence,
            )
            for activity in annual_activities
        ),
    )
    calculation_result = calculate_m303_regimen_simplificado_result(
        period=period,
        scope_decision=scope,
        rows=rows,
        regimen_snapshot=regimen_snapshot,
        dana_2024_eligibility=None,
        catalogues=catalogues,
    )
    return M303RegimenSimplificadoFilingEvidence(
        scope_decision=scope,
        rows=rows,
        regimen_snapshot=regimen_snapshot,
        dana_2024_eligibility=None,
        calculation_result=calculation_result,
    )


def _m303_2026_committed_snapshot(tmp_path: Path):
    """Build a filing snapshot from the committed M303 target, not the mutable whole tree."""
    tree = _m303_2026_tree()
    registry_root = _isolated_authority(tree, tmp_path / "m303-authority")
    isolated_modelo = load_modelo_directory(registry_root / "modelos" / tree.modelo)
    (isolated_modelo_revision,) = isolated_modelo.revisions.values()
    committed_modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", tree.modelo))
    committed_revision = committed_modelo.revisions[tree.revision]
    assert isolated_modelo_revision.id == committed_revision.id == tree.revision
    assert isolated_modelo_revision.source_refs == committed_revision.source_refs
    modelos, catalogues = load_registry_tree(registry_root)
    assert catalogues.supported_filing_years is not None
    supplementary_ordenes = compile_supplementary_ordenes(
        registry_root,
        source_root=bundled_path(),
        modelos=modelos,
        sources=catalogues.sources,
        supported_filing_years=catalogues.supported_filing_years.years,
    )
    catalogues = catalogues.model_copy(
        update={
            "legal": {**catalogues.legal, **supplementary_ordenes.legal},
            "supplementary_ordenes": supplementary_ordenes.authorities,
        },
    )
    snapshot = build_snapshot(
        committed_modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=tree.filing_year,
        period="1T",
    )
    assert snapshot.revision.id == tree.revision
    assert snapshot.revision.export_layouts == committed_revision.export_layouts
    return snapshot, catalogues


@pytest.fixture(scope="module")
def _m303_2026_real_envelope():
    """Render one isolated, source-owned M303 filing instance for envelope assertions."""
    with TemporaryDirectory(prefix="s16-m303-envelope-", dir=Path.cwd()) as temporary:
        snapshot, catalogues = _m303_2026_committed_snapshot(Path(temporary))
        snapshot, producer = _m303_2026_prorrata_and_differentiated_producer(
            snapshot=snapshot,
            catalogues=catalogues,
        )
        (layout,) = snapshot.revision.export_layouts
        request = FilingEnvelopeRenderRequest(
            registry_snapshot=snapshot,
            layout=layout,
            draft=m303_did._draft(),
            producer_snapshot=producer,
            prior_domiciliation_election=PriorDomiciliationElection.KEEP,
            product_software_identity=m303_did._product_software_identity(),
        )
        yield request, render_filing_envelope(request)


def _request_model_payload(request: FilingEnvelopeRenderRequest) -> dict[str, object]:
    """Keep the selected layout's identity while exercising public request validation."""
    return {
        "registry_snapshot": request.registry_snapshot,
        "layout": request.layout,
        "draft": request.draft,
        "producer_snapshot": request.producer_snapshot,
        "prior_domiciliation_election": request.prior_domiciliation_election,
        "product_software_identity": request.product_software_identity,
    }


def _result_payload_with_occurrences(
    rendered: FilingEnvelopeRenderResult,
    occurrences: tuple[dict[str, object], ...],
) -> dict[str, object]:
    """Re-derive result evidence so occurrence-order validation remains the failing boundary."""
    payload = rendered.model_dump(mode="python")
    payload["occurrences"] = occurrences
    emitted = rendered.prefix + b"".join(item["payload"] for item in occurrences) + rendered.closer
    payload["payload"] = emitted
    payload["payload_sha256"] = sha256(emitted).hexdigest()
    payload["total_length"] = len(emitted)
    return payload


def test_m303_2026_publication_is_twice_reproducible_and_check_mode_is_non_mutating() -> None:
    """The real target is reproducible in two disjoint Y: roots and check-mode only observes it."""
    tree = _m303_2026_tree()
    with TemporaryDirectory(prefix="s16-m303-", dir=Path.cwd()) as temporary:
        temp_path = Path(temporary)
        assert temp_path.drive == tree.committed.drive == bundled_path().drive
        first = _render_isolated_tree(tree, temp_path / "first")
        second = _render_isolated_tree(tree, temp_path / "second")
        first_registry_root, _first_metadata_root, first_export_root, *_first_authorities = first
        second_registry_root, _second_metadata_root, second_export_root, *_second_authorities = second

        # Two claims live here and only one of them is about bytes. Rendering twice
        # must be byte-identical, because that is the determinism this test is named
        # for and a serializer cannot excuse a difference between two runs of itself.
        # Matching the SHIPPED tree is a claim about meaning: a closed-vocabulary
        # conversion changed how one field is quoted across every generated tree
        # without changing any value, so that half is compared parsed.
        first_bytes = _tree_bytes(first_export_root)
        assert first_bytes == _tree_bytes(second_export_root)

        committed_bytes = _tree_bytes(tree.committed)
        assert set(first_bytes) == set(committed_bytes)
        semantically_differing = [
            name
            for name, raw in sorted(first_bytes.items())
            if (parsed := parsed_tree_file(name, committed_bytes[name])) is None
            or parsed != parsed_tree_file(name, raw)
        ]
        assert semantically_differing == [], (
            f"records whose meaning differs from the shipped tree: {semantically_differing}"
        )
        assert collect_export_fragment_output_digests(first_export_root) == collect_export_fragment_output_digests(
            second_export_root
        )
        assert load_export_fragment_provenance_manifest(
            (first_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME).read_bytes()
        ) == load_export_fragment_provenance_manifest(
            (second_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME).read_bytes()
        )

        first_layout = (
            load_modelo_directory(first_registry_root / "modelos" / tree.modelo)
            .revisions[tree.revision]
            .export_layouts[0]
        )
        second_layout = (
            load_modelo_directory(second_registry_root / "modelos" / tree.modelo)
            .revisions[tree.revision]
            .export_layouts[0]
        )
        assert normalised_loader_semantics(first_layout) == normalised_loader_semantics(second_layout)

        check_root = temp_path / "check"
        check_registry_root = _isolated_authority(tree, check_root)
        metadata_root = _stage_continuity_metadata(tree, check_root)
        published_modelo_root = check_root / "published-registry" / "aeat" / "modelos" / tree.modelo
        shutil.copytree(bundled_path("registry", "aeat", "modelos", tree.modelo), published_modelo_root)
        for sibling in (published_modelo_root / "revisions").iterdir():
            if sibling.name != tree.revision:
                shutil.rmtree(sibling)
        semantic_map, render_profile, joined, evidence, transport = _authorities(tree)
        before = _committed_tree_hashes(tree)
        checked = check_generated_export_tree(
            context=GeneratedExportTreeCheckContext(
                validation=GeneratedExportTreeValidationContext(
                    registry_root=check_registry_root,
                    source_root=bundled_path(),
                    target=ExportFragmentTarget(modelo=tree.modelo, revision_id=tree.revision, design_epoch=tree.epoch),
                    filing_year=tree.filing_year,
                    period=tree.period,
                    supporting_modelos=_supporting_modelos(tree),
                    continuity_metadata_modelo_root=metadata_root,
                ),
                temporary_root=check_root,
                target_registry_root=bundled_path("registry", "aeat"),
                target_export_root=tree.committed,
                published_modelo_root=published_modelo_root,
            ),
            joined=joined,
            semantic_map=semantic_map,
            transport_profile=transport,
            render_profile=render_profile,
            render_profile_source_evidence=evidence,
        )
        assert _committed_tree_hashes(tree) == before
        assert checked.published_manifest == checked.candidate.provenance_manifest
        assert normalised_loader_semantics(checked.published_layout) == normalised_loader_semantics(
            checked.candidate.layout
        )
        assert checked.candidate.layout.format == "fixed_width"
        assert transport.encoding is ExportEncoding.ISO_8859_1


def test_m303_dp30305_composes_its_two_declared_projection_families_once(tmp_path: Path) -> None:
    """The committed mixed-family record is composed by its two canonical projectors.

    DP30305 interleaves prorrata activity slots and differentiated deduction
    facts.  The layout, rather than this proof, owns the complete reference
    order.  A third real M303 family remains closed out at the dispatcher.
    """
    snapshot, catalogues = _m303_2026_committed_snapshot(tmp_path)
    snapshot, producer = _m303_2026_prorrata_and_differentiated_producer(snapshot=snapshot, catalogues=catalogues)
    (layout,) = snapshot.revision.export_layouts
    record = next(item for item in layout.records if item.id == "m303-prorrata-deducciones")
    refs = tuple(field.projection_ref for field in record.fields if field.projection_ref is not None)
    assert {type(ref) for ref in refs} == {
        M303ProrrataActivityProjectionRef,
        M303DifferentiatedDeductionProjectionRef,
    }

    contexts, values = _project_record(
        registry_snapshot=snapshot,
        layout=layout,
        record=record,
        refs=refs,
        producer_snapshot=producer,
    )

    assert tuple((context.record.id, context.occurrence) for context in contexts) == ((record.id, 1),)
    assert tuple(value.projection_ref for value in values) == refs
    assert {type(value.projection_ref) for value in values} == {
        M303ProrrataActivityProjectionRef,
        M303DifferentiatedDeductionProjectionRef,
    }

    exonerado_record = next(item for item in layout.records if item.id == "m303-exonerado-390")
    unsupported_ref = next(
        field.projection_ref for field in exonerado_record.fields if field.projection_ref is not None
    )
    assert isinstance(unsupported_ref, M303Exonerado390ActivityProjectionRef)
    with pytest.raises(FilingExportValidationError, match="mixes or uses an unsupported"):
        _project_record(
            registry_snapshot=snapshot,
            layout=layout,
            record=record,
            refs=(*refs, unsupported_ref),
            producer_snapshot=producer,
        )


def test_m303_2026_untouched_generated_layout_renders_official_6919_f022(
    _m303_2026_real_envelope,
) -> None:
    """The committed layout emits every reviewed kind through one coherent envelope."""
    request, rendered = _m303_2026_real_envelope
    layout = request.layout
    regimen_record = next(record for record in layout.records if record.id == "m303-regimen-simplificado")
    f022 = next(field for field in regimen_record.fields if field.id.endswith(".f022"))
    regimen_occurrences = tuple(item for item in rendered.occurrences if item.record_id == regimen_record.id)

    assert tuple((item.record_id, item.occurrence) for item in rendered.occurrences) == (
        ("m303-declaration", 1),
        ("m303-regimen-simplificado", 1),
        ("m303-resultados", 1),
        ("m303-exonerado-390", 1),
        ("m303-prorrata-deducciones", 1),
        ("m303-domiciliacion", 1),
    )
    assert rendered.prefix == (
        b"<T303020261T0000><AUX>" + (b" " * 70) + b"C303" + (b" " * 4) + b"Y0000001S" + (b" " * 213) + b"</AUX>"
    )
    assert rendered.closer == b"</T303020261T0000>"
    assert len(rendered.prefix) == layout.filing_envelope.prefix_extent
    assert tuple(item.occurrence for item in regimen_occurrences) == (1,)
    assert all(item.payload[f022.offset - 1 : f022.offset - 1 + f022.length] == b"6919" for item in regimen_occurrences)
    emitted_slices: dict[CasillaFieldKind, list[bytes]] = {}
    records = {record.id: record for record in layout.records}
    for occurrence in rendered.occurrences:
        for field in records[occurrence.record_id].fields:
            emitted_slices.setdefault(field.kind, []).append(
                occurrence.payload[field.offset - 1 : field.offset - 1 + field.length],
            )
    admitted_kinds = {field.kind for record in layout.records for field in record.fields}
    assert set(emitted_slices) == admitted_kinds
    assert all(emitted_slices[kind] for kind in admitted_kinds)
    assert any(slice_ == b"6919" for slice_ in emitted_slices[CasillaFieldKind.PROJECTION])
    assert all(slice_ == (b" " * len(slice_)) for slice_ in emitted_slices[CasillaFieldKind.FILLER])
    assert all(item.payload_sha256 == sha256(item.payload).hexdigest() for item in rendered.occurrences)
    assert (
        rendered.payload == rendered.prefix + b"".join(item.payload for item in rendered.occurrences) + rendered.closer
    )
    assert rendered.payload_sha256 == sha256(rendered.payload).hexdigest()
    assert rendered.total_length == len(rendered.payload)


@pytest.mark.parametrize(
    ("_case", "mutation", "refusal"),
    (
        (
            "cross-snapshot",
            lambda request: {"registry_snapshot": request.registry_snapshot.model_copy(deep=True)},
            "filing-envelope layout must be owned by the selected registry snapshot",
        ),
        (
            "cross-period",
            lambda request: {
                "draft": request.draft.model_copy(update={"period": Period.from_year_and_code(2026, "2T")}),
            },
            "draft period token '2T' does not match its snapshot_ref period '1T'",
        ),
        ("opaque-bytes", lambda _request: {"opaque_bytes": b"not-an-envelope"}, "Extra inputs are not permitted"),
        ("open-map", lambda _request: {"open_map": {}}, "Extra inputs are not permitted"),
        ("injected-plan", lambda _request: {"injected_plan": {}}, "Extra inputs are not permitted"),
        ("casilla-only", lambda _request: {"casilla_only": {}}, "Extra inputs are not permitted"),
        ("default", lambda _request: {"default_values": {}}, "Extra inputs are not permitted"),
        ("fake", lambda _request: {"fake_input": {}}, "Extra inputs are not permitted"),
        ("legacy", lambda _request: {"legacy_input": {}}, "Extra inputs are not permitted"),
    ),
)
def test_m303_2026_envelope_request_rejects_cross_authority_and_forbidden_spellings(
    _m303_2026_real_envelope,
    _case: str,
    mutation,
    refusal: str,
) -> None:
    """The closed public request carries one selected authority, never caller-owned export material."""
    request, _rendered = _m303_2026_real_envelope
    payload = _request_model_payload(request)
    payload.update(mutation(request))

    with pytest.raises(ValidationError, match=refusal):
        FilingEnvelopeRenderRequest.model_validate(payload)


def _reordered_occurrences(rendered: FilingEnvelopeRenderResult) -> dict[str, object]:
    occurrences = rendered.model_dump(mode="python")["occurrences"]
    return _result_payload_with_occurrences(rendered, (occurrences[1], occurrences[0], *occurrences[2:]))


def _dropped_occurrence(rendered: FilingEnvelopeRenderResult) -> dict[str, object]:
    payload = rendered.model_dump(mode="python")
    payload["occurrences"] = payload["occurrences"][1:]
    return payload


def _duplicated_occurrence(rendered: FilingEnvelopeRenderResult) -> dict[str, object]:
    occurrences = rendered.model_dump(mode="python")["occurrences"]
    return _result_payload_with_occurrences(rendered, (occurrences[0], occurrences[0], *occurrences[1:]))


def _extra_occurrence(rendered: FilingEnvelopeRenderResult) -> dict[str, object]:
    occurrences = rendered.model_dump(mode="python")["occurrences"]
    payload = b"unreviewed"
    extra = {
        "record_id": "m303-unreviewed-extra",
        "occurrence": 1,
        "payload": payload,
        "payload_sha256": sha256(payload).hexdigest(),
    }
    return _result_payload_with_occurrences(rendered, (*occurrences, extra))


@pytest.mark.parametrize(
    ("_case", "mutation", "refusal"),
    (
        ("reorder", _reordered_occurrences, "filing-envelope occurrences must retain reviewed record-family order"),
        (
            "drop",
            _dropped_occurrence,
            "filing-envelope payload must be the exact prefix, occurrences, and closer bytes",
        ),
        (
            "duplicate",
            _duplicated_occurrence,
            "must be positive, contiguous, and uncollapsed",
        ),
        ("extra", _extra_occurrence, "filing envelope emitted an undeclared record family"),
    ),
)
def test_m303_2026_envelope_result_rejects_tampered_occurrence_evidence(
    _m303_2026_real_envelope,
    _case: str,
    mutation,
    refusal: str,
) -> None:
    """Result evidence cannot lose, reorder, duplicate, or add an emitted record occurrence."""
    _request, rendered = _m303_2026_real_envelope

    with pytest.raises(ValidationError, match=refusal):
        FilingEnvelopeRenderResult.model_validate(mutation(rendered))
