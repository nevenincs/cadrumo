"""Focused command-surface tests for generated export-tree publication."""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.toml import parse_toml
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ...compiler.authority import compiled_bundled_authority
from ...compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from ...tests.authored_edition_support import source_first_exercise, source_with_sha256
from .. import cli as cli_module
from .._export_tree import render_complete_export_tree
from .._tree_validation import GeneratedExportTreeValidationContext
from ..bootstrap_construct_retarget import retarget_bootstrap_construct_export_layout
from ..bootstrap_targets import _bootstrap_target_from_row
from ..cli import (
    GeneratedTreeInvocation,
    PreparedGeneratedTreeInvocation,
    TargetCurrentnessFact,
    TargetCurrentnessState,
    app,
    check_prepared_invocation,
    prepare_generated_tree_invocation,
    publish_prepared_invocation,
    require_republication_eligibility,
    reviewed_bootstrap_target,
)
from ..edition_candidate_staging import stage_continuity_metadata
from ..export_fragment_provenance import ExportFragmentTarget
from ..generated_tree_dispositions import GeneratedTreeRecordDriftDisposition, record_drift_dispositions
from ..render_check import (
    GeneratedExportBootstrapTransport,
    RenderComparison,
    RevisionRenderInputs,
    revision_render_inputs,
)
from ..tree_publication_contracts import GeneratedExportTreePublicationContext, GeneratedExportTreeTargetStateReceipt
from ..tree_publication_paths import require_expected_target_state
from ._generated_tree_test_support import (
    ISOLATED_TREE,
    isolated_authorities,
    write_isolated_generated_authority_tree,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_pipeline_cli_registers_the_separate_check_and_publish_verbs() -> None:
    """The developer-only lifecycle surface exposes both authority modes."""
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    assert "check" in result.output
    assert "publish" in result.output
    assert "republish" in result.output


def _republish_invocation(expected_manifest_sha256: str) -> GeneratedTreeInvocation:
    return GeneratedTreeInvocation("190", "2024", "aeat-dr-190-2024", 2024, "0A", expected_manifest_sha256)


def test_row_binding_republication_routes_to_the_explicit_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def capture(invocation, **kwargs):
        calls.append((invocation, kwargs))

    monkeypatch.setattr(cli_module, "_run", capture)
    result = CliRunner().invoke(
        app,
        [
            "republish-target",
            "156",
            "2003-y-siguientes",
            "enrolled-modelo-156-layout",
            "2025",
            "0A",
            "a" * 64,
            "--reconcile-row-bindings",
        ],
    )
    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    invocation, options = calls[0]
    assert invocation.expected_manifest_sha256 == "a" * 64
    assert options == {
        "action": "republish",
        "reconcile_authored_form": False,
        "reconcile_casilla_splits": False,
        "reconcile_row_bindings": True,
    }


def _republish_comparison(*, differing: tuple[str, ...]) -> RenderComparison:
    return RenderComparison(
        modelo="190",
        revision="2024",
        layout_id="generated-modelo-190-2024-fichero",
        files_compared=3,
        differing=differing,
        only_committed=(),
        only_rendered=(),
    )


def test_republish_requires_the_exact_reviewed_target_manifest_digest() -> None:
    """A stale observation cannot authorize replacement of a different target."""
    actual = "a" * 64
    state = GeneratedExportTreeTargetStateReceipt(manifest_sha256=actual, output_files=())

    with pytest.raises(ValueError, match="exact lowercase 64-character"):
        require_republication_eligibility(
            _republish_invocation("not-a-digest"),
            state,
            _republish_comparison(differing=(EXPORT_FRAGMENT_PROVENANCE_FILENAME,)),
        )
    with pytest.raises(ValueError, match="differs from the explicitly reviewed digest"):
        require_republication_eligibility(
            _republish_invocation("b" * 64),
            state,
            _republish_comparison(differing=(EXPORT_FRAGMENT_PROVENANCE_FILENAME,)),
        )


def test_republish_admits_only_provenance_only_drift() -> None:
    """An explicit digest never turns UNEXPLAINED record drift into a publishable target.

    The digest proves someone looked at the artefact. It does not say why the
    records differ, so on its own it still admits nothing beyond attestation
    drift; a record change additionally needs a disposition row stating the
    reason. The subject is asserted to carry no such row, so both record-drift
    cases below are refused.
    """
    assert "190/2024" not in {row.subject for row in record_drift_dispositions()}
    digest = "a" * 64
    state = GeneratedExportTreeTargetStateReceipt(manifest_sha256=digest, output_files=())

    require_republication_eligibility(
        _republish_invocation(digest),
        state,
        _republish_comparison(differing=(EXPORT_FRAGMENT_PROVENANCE_FILENAME,)),
    )
    require_republication_eligibility(
        _republish_invocation(digest),
        state,
        RenderComparison(
            modelo="190",
            revision="2024",
            layout_id="generated-modelo-190-2024-fichero",
            files_compared=3,
            differing=(EXPORT_FRAGMENT_PROVENANCE_FILENAME, "0002-record-m190-perceptor.toml"),
            only_committed=(),
            only_rendered=(),
            serialization_only=("0002-record-m190-perceptor.toml",),
        ),
    )
    with pytest.raises(ValueError, match="refuses an unexplained record change"):
        require_republication_eligibility(
            _republish_invocation(digest),
            state,
            _republish_comparison(
                differing=(EXPORT_FRAGMENT_PROVENANCE_FILENAME, "0002-record-m190-perceptor.toml"),
            ),
        )
    with pytest.raises(ValueError, match="refuses an unexplained record change"):
        require_republication_eligibility(
            _republish_invocation(digest),
            state,
            RenderComparison(
                modelo="190",
                revision="2024",
                layout_id="generated-modelo-190-2024-fichero",
                files_compared=3,
                differing=(EXPORT_FRAGMENT_PROVENANCE_FILENAME,),
                only_committed=(),
                only_rendered=("0003-unexpected-record.toml",),
            ),
        )


def test_pipeline_cli_refuses_a_bootstrap_source_absent_from_the_catalogue() -> None:
    """An isolated absent target reaches the bootstrap guard regardless of completed publications."""
    filing_year = max(compiled_bundled_authority().supported_filing_years().years)
    result = CliRunner().invoke(
        app,
        ["check", "999", "unpublished-fixture", "not-a-declared-source", str(filing_year), "0A"],
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "no source 'not-a-declared-source' exists for bootstrap target selection" in result.stderr


def test_pipeline_cli_refuses_a_catalogued_source_undeclared_as_this_revisions_record_design() -> None:
    """A source that exists but is not a record-design source is refused by name.

    Modelo 200's 2025-y-siguientes revision already has a published export
    tree, so ``prepare_generated_tree_invocation`` skips the bootstrap branch entirely and calls
    ``revision_render_inputs`` directly. ``aeat-modelo-200-manual-2025`` is a
    real catalogued source (``kind = "manual_pdf"``) and is one of this
    revision's declared ``source_refs``, but it is not a record-design source,
    so it can never satisfy this revision's record-design selector. This
    reaches the ``render_check.py`` guard the bootstrap case above cannot.
    """
    result = CliRunner().invoke(
        app,
        ["check", "200", "2025-y-siguientes", "aeat-modelo-200-manual-2025", "2025", "0A"],
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "200/2025-y-siguientes does not declare record-design source 'aeat-modelo-200-manual-2025'" in result.stderr


def test_bootstrap_target_refuses_unenrolled_source_digest() -> None:
    """A generic revision/source convention cannot become a bootstrap permission."""
    with pytest.raises(ValueError, match="no reviewed generated-export bootstrap target"):
        reviewed_bootstrap_target(
            GeneratedTreeInvocation("200", "2025-y-siguientes", "aeat-dr-200-2025", 2025, "0A"),
            source_sha256="0" * 64,
        )


def test_bootstrap_supersession_accepts_an_explicit_zero_construct_reference_pin() -> None:
    """A reviewed manual layout may be replaced when no construct points to it."""
    target = _bootstrap_target_from_row(
        {
            "modelo": "360",
            "revision": "2023-y-siguientes",
            "source_ref": "aeat-dr-360",
            "source_sha256": "a" * 64,
            "layout_id": "generated-modelo-360",
            "line_ending": "crlf",
            "supersedes_layout_id": "modelo-360-fichero-boe",
            "superseded_construct_references": 0,
        },
    )

    assert target.supersedes_layout_id == "modelo-360-fichero-boe"
    assert target.superseded_construct_references == 0


#: The reviewed Modelo 200 design whose export publication retires its bootstrap authorization.
_M200_BOOTSTRAP_DESIGN_SHA256 = "ed4df89a451abc2184bc60a1d13ff53a3d38e9a6201698fb635cf0b8ee455218"
_M200_BOOTSTRAP_DESIGN = source_with_sha256(_M200_BOOTSTRAP_DESIGN_SHA256)
_M200_BOOTSTRAP_DESIGN_EXERCISE = source_first_exercise(_M200_BOOTSTRAP_DESIGN)


def test_a_published_modelo_200_design_has_no_bootstrap_authorization() -> None:
    """The published tree retains its own layout and cannot be bootstrapped again."""
    source_ref = _M200_BOOTSTRAP_DESIGN.id
    revision = (
        compiled_bundled_authority()
        .snapshot(
            "200", filing_year=_M200_BOOTSTRAP_DESIGN_EXERCISE, period="0A", grade=RegistryAuthorityGrade.CALCULATION
        )
        .revision
    )
    assert {str(layout.id) for layout in revision.export_layouts} == {
        f"generated-modelo-200-{_M200_BOOTSTRAP_DESIGN_EXERCISE}-fichero"
    }
    with pytest.raises(ValueError, match="no reviewed generated-export bootstrap target"):
        reviewed_bootstrap_target(
            GeneratedTreeInvocation("200", str(revision.id), source_ref, _M200_BOOTSTRAP_DESIGN_EXERCISE, "0A"),
            source_sha256=_M200_BOOTSTRAP_DESIGN_SHA256,
        )


@pytest.mark.parametrize(
    ("layout_ids", "expected_references", "found_references"),
    (
        ([], 1, 0),
        (["manual-layout"], 2, 1),
        (["manual-layout", "manual-layout"], 1, 2),
    ),
    ids=("missing", "stale-pin", "widened"),
)
def test_bootstrap_construct_retarget_refuses_reference_count_drift_without_mutation(
    tmp_path: Path,
    layout_ids: list[str],
    expected_references: int,
    found_references: int,
) -> None:
    """Missing, stale, or widened superseded membership invalidates its explicit pin."""
    path = tmp_path / "revisions" / "2022" / "constructs" / "0001-constructs.toml"
    path.parent.mkdir(parents=True)
    original = (
        (f'[[revisions."2022".constructs]]\nid = "annual"\nexport_layouts = {layout_ids!r}\n')
        .replace("'", '"')
        .encode()
    )
    path.write_bytes(original)

    with pytest.raises(
        ValueError,
        match=rf"expected {expected_references} construct reference\(s\), found {found_references}",
    ):
        retarget_bootstrap_construct_export_layout(
            tmp_path,
            revision="2022",
            superseded_layout_id="manual-layout",
            generated_layout_id="generated-layout",
            expected_references=expected_references,
        )

    assert path.read_bytes() == original


def test_bootstrap_construct_retarget_changes_only_the_pinned_reference(tmp_path: Path) -> None:
    """A positive reviewed reference count retargets its member and preserves unrelated layout ids."""
    path = tmp_path / "revisions" / "2022" / "constructs" / "0001-constructs.toml"
    path.parent.mkdir(parents=True)
    path.write_text(
        '[[revisions."2022".constructs]]\nid = "annual"\nexport_layouts = ["manual-layout", "unrelated-layout"]\n',
        encoding="utf-8",
    )

    retarget_bootstrap_construct_export_layout(
        tmp_path,
        revision="2022",
        superseded_layout_id="manual-layout",
        generated_layout_id="generated-layout",
        expected_references=1,
    )

    payload = parse_toml(path.read_text("utf-8"))
    construct = payload["revisions"]["2022"]["constructs"][0]
    assert construct["export_layouts"] == ["generated-layout", "unrelated-layout"]


def test_every_bootstrap_target_still_names_a_tree_awaiting_publication() -> None:
    """A reviewed bootstrap authorization must not outlive the bootstrap it authorized.

    ``prepare_generated_tree_invocation`` in ``cli.py`` only ever consults this file while
    ``target_export_root`` is absent; once a revision's tree is published,
    ``reviewed_bootstrap_target`` can never match that row again. A row surviving its
    own bootstrap is dead weight nothing else refuses, mirroring the sibling
    disposition ledger's own stated policy in this package
    (``generated_tree_dispositions.toml``: "a row whose tree has been repaired
    fails too, so an explanation cannot outlive its cause"). This asserts the
    same discipline for the bootstrap-target roster: prune a row once its tree
    is committed, rather than leaving it to silently accumulate.
    """
    path = Path(__file__).resolve().parents[2] / "pipeline" / "generated_export_bootstrap_targets.toml"
    payload = parse_toml(path.read_text("utf-8"))
    targets = payload["targets"]
    assert isinstance(targets, list), "the bootstrap-target roster must declare its targets explicitly"

    registry_root = bundled_path("registry", "aeat")
    already_bootstrapped = [
        (row["modelo"], row["revision"])
        for row in targets
        if (registry_root / "modelos" / row["modelo"] / "revisions" / row["revision"] / "export").is_dir()
    ]
    assert not already_bootstrapped, (
        f"bootstrap target(s) name a tree already published, so the row can never fire again: "
        f"{already_bootstrapped}; prune it once its tree is committed"
    )


def test_m390_continuity_witness_carries_every_sibling_revision(tmp_path: Path) -> None:
    """A 2025 target's witness holds every other revision, predecessor chain included.

    The strict-continuity chain back from 2025 is 2024, 2023 and 2022. The
    witness carries those and 2021 besides, because checks that reason across a
    modelo's revisions -- the semantic-role singleton check among them -- need
    every sibling, not only the ones continuity names. The target itself stays
    out, so the witness cannot validate a stale copy of the candidate.
    """
    modelo_root = bundled_path("registry", "aeat", "modelos", "390")
    metadata_root = stage_continuity_metadata(modelo_root, tmp_path, revision="2025")

    assert metadata_root is not None
    staged = {path.name for path in (metadata_root / "revisions").iterdir()}
    siblings = {path.name for path in (modelo_root / "revisions").iterdir() if path.name != "2025"}
    assert {"2022", "2023", "2024"} <= staged
    assert staged == siblings
    assert "2025" not in staged


def test_a_single_revision_modelo_stages_no_witness(tmp_path: Path) -> None:
    """With no sibling to supply, there is nothing to stage, and a singleton is real."""
    registry_root = bundled_path("registry", "aeat", "modelos")
    single = next(
        root
        for root in sorted(registry_root.iterdir())
        if (root / "revisions").is_dir() and len([child for child in (root / "revisions").iterdir()]) == 1
    )
    (only_revision,) = [child.name for child in (single / "revisions").iterdir()]

    assert stage_continuity_metadata(single, tmp_path, revision=only_revision) is None


def _publication_context_for_target(
    target: Path,
    receipt: GeneratedExportTreeTargetStateReceipt,
) -> GeneratedExportTreePublicationContext:
    """Build a context only for the lock-state detector's private guard."""
    return GeneratedExportTreePublicationContext(
        # The lock-state guard under test never reads `.validation`; a real,
        # minimally-populated context stands in rather than a suppressed None.
        validation=GeneratedExportTreeValidationContext(
            registry_root=target.parent / "unused-registry-root",
            source_root=target.parent / "unused-source-root",
            target=ExportFragmentTarget(modelo="200", revision_id="2025", design_epoch="2025"),
            filing_year=2025,
            period="anual",
        ),
        temporary_root=target.parent / "temporary",
        target_root=target.parent,
        target_export_root=target,
        expected_target_state=receipt,
    )


def test_target_appearing_after_an_absent_receipt_is_refused_without_mutation(tmp_path: Path) -> None:
    """A check-time ABSENT observation cannot race a new target into publication."""
    target = tmp_path / "export"
    receipt = GeneratedExportTreeTargetStateReceipt.observe(target)
    target.mkdir()

    with pytest.raises(RegistryValidationError, match="appeared after check"):
        require_expected_target_state(
            _publication_context_for_target(target, receipt),
            target,
        )

    assert target.is_dir()


def test_non_manifest_member_mutation_after_existing_receipt_is_refused_without_mutation(tmp_path: Path) -> None:
    """Manifest stability alone cannot hide an output-member change before cutover."""
    target = tmp_path / "export"
    target.mkdir()
    (target / EXPORT_FRAGMENT_PROVENANCE_FILENAME).write_text("{}", encoding="utf-8")
    member = target / "0001-records.toml"
    member.write_text("id = 'first'\n", encoding="utf-8")
    receipt = GeneratedExportTreeTargetStateReceipt.observe(target)
    member.write_text("id = 'mutated'\n", encoding="utf-8")

    with pytest.raises(RegistryValidationError, match="changed after check"):
        require_expected_target_state(
            _publication_context_for_target(target, receipt),
            target,
        )

    assert member.read_text(encoding="utf-8") == "id = 'mutated'\n"


def _prepared_absent_target(candidate_base: Path, target_root: Path) -> PreparedGeneratedTreeInvocation:
    """Build a real isolated candidate for the bootstrap-path detector test."""
    validation, joined, semantic_map, rendered, candidate_export_root = write_isolated_generated_authority_tree(
        candidate_base,
    )
    shutil.rmtree(candidate_export_root)
    _joined, _semantic_map, transport, render_profile, evidence = isolated_authorities(ISOLATED_TREE)
    inputs = RevisionRenderInputs(
        revision_id=validation.target.revision_id,
        layout_id=str(rendered.layout.id),
        joined=joined,
        semantic_map=semantic_map,
        render_profile=render_profile,
        render_profile_source_evidence=evidence,
        transport_profile=transport,
    )
    return PreparedGeneratedTreeInvocation(
        invocation=GeneratedTreeInvocation(
            ISOLATED_TREE.modelo,
            ISOLATED_TREE.revision,
            ISOLATED_TREE.source_ref,
            ISOLATED_TREE.filing_year,
            ISOLATED_TREE.period,
        ),
        inputs=inputs,
        validation=validation,
        candidate_root=validation.registry_root,
        target_root=target_root,
        target_export_root=target_root
        / "modelos"
        / ISOLATED_TREE.modelo
        / "revisions"
        / ISOLATED_TREE.revision
        / "export",
        published_modelo_root=None,
    )


def test_absent_tree_is_validated_then_published_through_the_canonical_authorities(tmp_path: Path) -> None:
    """An owed tree is bootstrap-publishable only after its fresh candidate validates."""
    first = _prepared_absent_target(tmp_path / "check", tmp_path / "target" / "registry" / "aeat")
    # Final publication validates the complete authority, including the
    # predecessor editions that own this child's seeded continuity.
    shutil.copytree(bundled_path("registry", "aeat"), first.target_root)
    assert first.target_export_root.resolve().is_relative_to(tmp_path.resolve())
    shutil.rmtree(first.target_export_root)

    result, _rendered, _target_state = check_prepared_invocation(first)
    assert result == "publishable_absence"
    assert first.candidate_root.joinpath(
        "modelos",
        ISOLATED_TREE.modelo,
        "revisions",
        ISOLATED_TREE.revision,
        "export",
    ).is_dir()
    assert not first.target_export_root.exists()

    publication = _prepared_absent_target(tmp_path / "publish", first.target_root)
    _publication_result, publication_rendered, publication_target_state = check_prepared_invocation(publication)
    publish_prepared_invocation(publication, publication_rendered, publication_target_state)

    assert first.target_export_root.is_dir()


def test_final_live_validator_does_not_recover_while_it_checks_the_cutover_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The final currency callback's supplied authority takes the read-only prepare path."""
    invocation = GeneratedTreeInvocation(
        ISOLATED_TREE.modelo,
        ISOLATED_TREE.revision,
        ISOLATED_TREE.source_ref,
        ISOLATED_TREE.filing_year,
        ISOLATED_TREE.period,
    )
    target_root = tmp_path / "live-registry" / "aeat"
    (target_root / "modelos" / invocation.modelo / "revisions" / invocation.revision / "export").mkdir(
        parents=True,
    )
    authority = compiled_bundled_authority()
    monkeypatch.setattr(cli_module, "bundled_path", lambda *_parts: target_root)
    monkeypatch.setattr(cli_module, "compile_validated_authority", lambda *_args, **_kwargs: authority)

    def reject_recovery(**_kwargs: object) -> bool:
        raise AssertionError("final live validation re-entered transaction recovery")

    monkeypatch.setattr(cli_module, "recover_interrupted_supersession_bundle", reject_recovery)
    monkeypatch.setattr(cli_module, "supporting_modelos", lambda _modelo: frozenset())
    monkeypatch.setattr(
        cli_module,
        "revision_render_inputs",
        lambda *_args, **_kwargs: SimpleNamespace(
            revision_id=invocation.revision,
            layout_id="fixture-layout",
            joined=object(),
            semantic_map=object(),
            transport_profile=SimpleNamespace(design_epoch="2025"),
            render_profile=object(),
            render_profile_source_evidence=object(),
        ),
    )
    monkeypatch.setattr(cli_module, "stage_generated_export_candidate", lambda *_args, **_kwargs: target_root)
    monkeypatch.setattr(cli_module, "stage_published_modelo", lambda *_args, **_kwargs: None)
    real_prepare = cli_module.prepare_generated_tree_invocation
    prepared_authorities: list[object] = []

    def inspect_read_only_prepare(
        selected: GeneratedTreeInvocation,
        root: Path,
        *,
        authority: object | None = None,
    ) -> PreparedGeneratedTreeInvocation:
        assert authority is not None
        prepared_authorities.append(authority)
        return real_prepare(selected, root, authority=cast(ValidatedRegistryAuthority, authority))

    def currentness_with_real_prepare(
        modelo: str,
        revision: str,
        source_ref: str,
        filing_year: int,
        period: str,
        *,
        authority: object,
    ) -> TargetCurrentnessFact:
        inspect_read_only_prepare(
            GeneratedTreeInvocation(modelo, revision, source_ref, filing_year, period),
            tmp_path / "currentness",
            authority=authority,
        )
        return TargetCurrentnessFact(modelo, revision, TargetCurrentnessState.CURRENT)

    monkeypatch.setattr(cli_module, "target_currentness", currentness_with_real_prepare)

    prepared = cast(
        PreparedGeneratedTreeInvocation, cast(Any, SimpleNamespace(invocation=invocation, target_root=target_root))
    )
    cli_module._validate_final_live_target(prepared)

    assert prepared_authorities == [authority]


def test_modelo_200_calculation_grade_does_not_widen_its_runtime_filing_authority() -> None:
    """Bootstrap publication can validate static output without promoting Modelo 200."""
    authority = compiled_bundled_authority()

    calculation = authority.snapshot(
        "200",
        filing_year=2024,
        period="0A",
        revision_id="2024",
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    with pytest.raises(RegistryValidationError, match="cannot satisfy the requested 'filing' snapshot authority"):
        authority.snapshot(
            "200",
            filing_year=2024,
            period="0A",
            revision_id="2024",
            grade=RegistryAuthorityGrade.FILING,
        )

    assert str(calculation.revision.id) == "2024"


def test_modelo_200_bootstrap_assembly_reaches_the_real_join_and_renderer(tmp_path: Path) -> None:
    """An unpublished revision is assembled from its selected official design, not a missing layout."""
    authority = compiled_bundled_authority()
    source = next(item for ref, item in authority.catalogues.sources.items() if str(ref) == "aeat-dr-200-2025")
    inputs = revision_render_inputs(
        authority,
        modelo="200",
        revision="2025-y-siguientes",
        source_ref="aeat-dr-200-2025",
        bootstrap_transport=GeneratedExportBootstrapTransport(
            layout_id="generated-modelo-200-2025-y-siguientes-fichero",
            line_ending="crlf",
            source_ref="aeat-dr-200-2025",
            source_sha256=source.sha256,
        ),
    )

    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=inputs.revision_id,
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
    )

    assert inputs.layout_id == "generated-modelo-200-2025-y-siguientes-fichero"
    assert rendered.output_files


# A full candidate compile of modelo 390 and its supporting modelos runs about
# 245s serially, so the lane's 300s ceiling leaves no margin under parallel load.
@pytest.mark.timeout(900)
def test_modelo_390_cli_assembly_uses_the_pipeline_source_defect_catalogue(tmp_path: Path) -> None:
    """The operator path validates M390 without consulting either prior export tree."""
    prepared = prepare_generated_tree_invocation(
        GeneratedTreeInvocation("390", "2022", "aeat-dr-390-2022", 2022, "0A"),
        tmp_path,
    )

    staged_revision = prepared.candidate_root / "modelos" / "390" / "revisions" / "2022"
    assert not (staged_revision / "export").exists()
    assert not (staged_revision / "export_layouts").exists()

    result, rendered, _target_state = check_prepared_invocation(prepared)
    close = next(
        field
        for record in rendered.layout.records
        for field in record.fields
        if str(field.id) == "modelo-390-page-07-close"
    )

    assert result == "matched"
    assert close.literal == "</T39007000>"


def test_republish_admits_record_drift_a_disposition_explains() -> None:
    """A corrected tree is publishable where a source-pinned row says why.

    Without this the generator could be made right and the corpus could never be
    made to match it: the check compares the shipped manifest against a fresh
    render and refuses the difference, which IS the correction being landed.

    The bar is higher here than for attestation drift, not lower. That path needs
    one proof, the reviewed digest. This needs two - the digest AND a row
    carrying a reason, a source pin and a retirement condition, which the
    ledger's own gate fails once its cause is gone.
    """
    digest = "a" * 64
    # The row is STATED, not looked up. A disposition retires the moment its
    # cause is repaired, so a proof that asked the live ledger for "some row
    # whose remedy is republish" held only while a correction was outstanding
    # and broke the day the last one landed - which is the ledger working.
    # What must not change is the admission rule, and that is what this states.
    explained = GeneratedTreeRecordDriftDisposition(
        kind="record_drift",
        modelo="390",
        revision="2024",
        source_ref="aeat-dr-390-2024",
        source_sha256="b" * 64,
        remedy="republish",
        differing_records=1,
        reason="The generator reads the official type column and the shipped tree predates it.",
        reconsideration_condition="Retire once the shipped tree is regenerated from the current inputs.",
    )
    state = GeneratedExportTreeTargetStateReceipt(manifest_sha256=digest, output_files=())

    invocation = GeneratedTreeInvocation(explained.modelo, explained.revision, explained.source_ref, 2024, "0A", digest)
    comparison = RenderComparison(
        modelo=explained.modelo,
        revision=explained.revision,
        layout_id=f"generated-modelo-{explained.modelo}-{explained.revision}-fichero",
        files_compared=3,
        differing=(EXPORT_FRAGMENT_PROVENANCE_FILENAME, "0001-record.toml"),
        only_committed=(),
        only_rendered=(),
        serialization_only=(),
    )
    require_republication_eligibility(invocation, state, comparison, source_sha256="b" * 64, dispositions=(explained,))
    with pytest.raises(ValueError, match="source ref/SHA"):
        require_republication_eligibility(
            invocation, state, comparison, source_sha256="c" * 64, dispositions=(explained,)
        )
    with pytest.raises(ValueError, match="source ref/SHA"):
        require_republication_eligibility(
            invocation,
            state,
            comparison,
            source_sha256="b" * 64,
            dispositions=(explained.model_copy(update={"source_ref": "aeat-dr-other"}),),
        )
    with pytest.raises(ValueError, match="explains 2 differing record"):
        require_republication_eligibility(
            invocation,
            state,
            comparison,
            source_sha256="b" * 64,
            dispositions=(explained.model_copy(update={"differing_records": 2}),),
        )
    with pytest.raises(ValueError, match="added or removed"):
        require_republication_eligibility(
            invocation,
            state,
            replace(comparison, only_rendered=("0002-unreviewed.toml",)),
            source_sha256="b" * 64,
            dispositions=(explained,),
        )
