"""End-to-end publication and filing-boundary proof for the committed M303 tree.

This deliberately uses the real 2026 generated target and the generator's
ordinary target-only isolation.  It does not make a test layout or a copied
export tree into a positive authority.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from cadrumo.application.aggregation import IvaDifferentiatedDeductionContribution
from cadrumo.application.filing._projection import _project_record
from cadrumo.application.filing.tests import test_m303_did_account_wire_isolated_authority as m303_did
from cadrumo.application.filing.tests.test_producer_snapshot import _m303_exonerado_evidence
from cadrumo.core import (
    IvaDeductionFactKind,
    M303DifferentiatedDeductionProjectionRef,
    M303Exonerado390ActivityProjectionRef,
    M303ProrrataActivityProjectionRef,
    Period,
    ProrrataActivityRowType,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    ResultDisposition,
    SectorDiferenciadoLetra,
)
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import ExportEncoding, load_modelo_directory
from cadrumo.domain.filing import FilingExportValidationError
from cadrumo.domain.prorrata_register import ProrrataActivityRow, ProrrataRegister, ProrrataRegisterEntry, SectorDefinition

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
from .test_generated_export_trees import (
    _GENERATED_TREES,
    _authorities,
    _isolated_authority,
    _stage_continuity_metadata,
    _supporting_modelos,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.hex_application]


def _m303_2026_tree():
    return next(tree for tree in _GENERATED_TREES if tree.modelo == "303" and tree.revision == "2026-y-siguientes")


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


def _m303_2026_prorrata_and_differentiated_producer():
    """Return one source-owned live DP30305 value arrival, without a test layout."""
    from decimal import Decimal

    snapshot = m303_did._m303_2026_snapshot()
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
    facts = m303_did._m303_filing_facts(
        Period.from_year_and_code(filing_year, "1T"),
        registry_snapshot=snapshot,
        non_agricultural_activity_count=1,
    ).model_copy(
        update={
            "exonerado_390": _m303_exonerado_evidence(applicable=True),
            "prorrata_register": register,
            "differentiated_contributions": contributions,
        }
    )
    producer = m303_did._m303_did_producer_snapshot(
        ResultDisposition.DEVOLUCION,
        registry_snapshot=snapshot,
        non_agricultural_activity_count=1,
    ).model_copy(update={"m303_filing_facts": facts})
    return snapshot, producer


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

        assert _tree_bytes(first_export_root) == _tree_bytes(second_export_root) == _tree_bytes(tree.committed)
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
        assert transport.encoding is ExportEncoding.LATIN_1


def test_m303_dp30305_composes_its_two_declared_projection_families_once() -> None:
    """The committed mixed-family record is composed by its two canonical projectors.

    DP30305 interleaves prorrata activity slots and differentiated deduction
    facts.  The layout, rather than this proof, owns the complete reference
    order.  A third real M303 family remains closed out at the dispatcher.
    """
    snapshot, producer = _m303_2026_prorrata_and_differentiated_producer()
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
