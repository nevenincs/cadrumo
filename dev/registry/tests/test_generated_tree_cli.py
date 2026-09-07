"""Focused command-surface tests for generated export-tree publication."""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..pipeline._export_tree import render_complete_export_tree
from ..pipeline._provenance_manifest import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from ..pipeline._tree_publication import (
    GeneratedExportTreePublicationContext,
    GeneratedExportTreeTargetStateReceipt,
    _require_expected_target_state,
)
from ..pipeline.candidate_staging import (
    retarget_bootstrap_construct_export_layout,
    stage_continuity_metadata,
)
from ..pipeline.cli import (
    _bootstrap_target,
    _check,
    _Invocation,
    _prepare,
    _PreparedInvocation,
    _publish,
    _require_republication_eligibility,
    app,
)
from ..pipeline.render_check import (
    GeneratedExportBootstrapTransport,
    RenderComparison,
    RevisionRenderInputs,
    revision_render_inputs,
)
from .test_generated_export_tree_validation import (
    _ISOLATED_TREE,
    _real_authorities,
    _write_isolated_generated_authority_tree,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_pipeline_cli_registers_the_separate_check_and_publish_verbs() -> None:
    """The developer-only lifecycle surface exposes both authority modes."""
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    assert "check" in result.output
    assert "publish" in result.output
    assert "republish" in result.output


def _republish_invocation(expected_manifest_sha256: str) -> _Invocation:
    return _Invocation("296", "2024-y-siguientes", "aeat-dr-296-2024", 2024, "0A", expected_manifest_sha256)


def _republish_comparison(*, differing: tuple[str, ...]) -> RenderComparison:
    return RenderComparison(
        modelo="296",
        revision="2024-y-siguientes",
        layout_id="generated-modelo-296-2024-y-siguientes-fichero",
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
        _require_republication_eligibility(
            _republish_invocation("not-a-digest"),
            state,
            _republish_comparison(differing=(EXPORT_FRAGMENT_PROVENANCE_FILENAME,)),
        )
    with pytest.raises(ValueError, match="differs from the explicitly reviewed digest"):
        _require_republication_eligibility(
            _republish_invocation("b" * 64),
            state,
            _republish_comparison(differing=(EXPORT_FRAGMENT_PROVENANCE_FILENAME,)),
        )


def test_republish_admits_only_provenance_only_drift() -> None:
    """An explicit digest never turns record drift into a publishable target."""
    digest = "a" * 64
    state = GeneratedExportTreeTargetStateReceipt(manifest_sha256=digest, output_files=())

    _require_republication_eligibility(
        _republish_invocation(digest),
        state,
        _republish_comparison(differing=(EXPORT_FRAGMENT_PROVENANCE_FILENAME,)),
    )
    _require_republication_eligibility(
        _republish_invocation(digest),
        state,
        RenderComparison(
            modelo="296",
            revision="2024-y-siguientes",
            layout_id="generated-modelo-296-2024-y-siguientes-fichero",
            files_compared=3,
            differing=(EXPORT_FRAGMENT_PROVENANCE_FILENAME, "0002-record-m296-declarado.toml"),
            only_committed=(),
            only_rendered=(),
            serialization_only=("0002-record-m296-declarado.toml",),
        ),
    )
    with pytest.raises(ValueError, match="restricted to semantically reproduced attestation drift"):
        _require_republication_eligibility(
            _republish_invocation(digest),
            state,
            _republish_comparison(
                differing=(EXPORT_FRAGMENT_PROVENANCE_FILENAME, "0002-record-m296-declarado.toml"),
            ),
        )
    with pytest.raises(ValueError, match="restricted to semantically reproduced attestation drift"):
        _require_republication_eligibility(
            _republish_invocation(digest),
            state,
            RenderComparison(
                modelo="296",
                revision="2024-y-siguientes",
                layout_id="generated-modelo-296-2024-y-siguientes-fichero",
                files_compared=3,
                differing=(EXPORT_FRAGMENT_PROVENANCE_FILENAME,),
                only_committed=(),
                only_rendered=("0003-unexpected-record.toml",),
            ),
        )


def test_pipeline_cli_refuses_a_bootstrap_source_absent_from_the_catalogue() -> None:
    """An absent tree's bootstrap selector must resolve to a real catalogued source.

    Modelo 200/2024 has no published export tree yet, so ``_prepare`` takes the
    bootstrap branch before ``revision_render_inputs`` is ever reached. The
    given ``source_ref`` is not any catalogued source at all, so this proves
    the bootstrap guard in ``cli.py`` rather than the record-design guard in
    ``render_check.py``.
    """
    result = CliRunner().invoke(
        app,
        ["check", "200", "2024", "not-a-declared-source", "2024", "0A"],
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "no source 'not-a-declared-source' exists for bootstrap target selection" in result.stderr


def test_pipeline_cli_refuses_a_catalogued_source_undeclared_as_this_revisions_record_design() -> None:
    """A source that exists but is not a record-design source is refused by name.

    Modelo 200's 2025-y-siguientes revision already has a published export
    tree, so ``_prepare`` skips the bootstrap branch entirely and calls
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
        _bootstrap_target(
            _Invocation("200", "2025-y-siguientes", "aeat-dr-200-2025", 2025, "0A"),
            source_sha256="0" * 64,
        )


def test_bootstrap_target_enrolls_only_the_pinned_modelo_200_2024_design() -> None:
    """The absent 2024 tree may bootstrap only from its own reviewed source."""
    target = _bootstrap_target(
        _Invocation("200", "2024", "aeat-dr-200-2024", 2024, "0A"),
        source_sha256="ed4df89a451abc2184bc60a1d13ff53a3d38e9a6201698fb635cf0b8ee455218",
    )

    assert target.layout_id == "generated-modelo-200-2024-fichero"
    assert target.line_ending == "crlf"
    assert target.source_ref == "aeat-dr-200-2024"
    assert target.supersedes_layout_id is None
    assert target.superseded_construct_references == 0


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


def test_every_bootstrap_target_still_names_a_tree_awaiting_publication() -> None:
    """A reviewed bootstrap authorization must not outlive the bootstrap it authorized.

    ``_prepare`` in ``cli.py`` only ever consults this file while
    ``target_export_root`` is absent; once a revision's tree is published,
    ``_bootstrap_target`` can never match that row again. A row surviving its
    own bootstrap is dead weight nothing else refuses, mirroring the sibling
    disposition ledger's own stated policy in this package
    (``generated_tree_dispositions.toml``: "a row whose tree has been repaired
    fails too, so an explanation cannot outlive its cause"). This asserts the
    same discipline for the bootstrap-target roster: prune a row once its tree
    is committed, rather than leaving it to silently accumulate.
    """
    path = Path(__file__).resolve().parents[1] / "pipeline" / "generated_export_bootstrap_targets.toml"
    payload = tomllib.loads(path.read_text("utf-8"))
    targets = payload["targets"]
    assert targets, "the bootstrap-target roster must not be silently emptied"

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


def test_m390_continuity_witness_closes_the_full_predecessor_chain(tmp_path: Path) -> None:
    """A 2025 target carries 2024, 2023, and 2022 continuity facts."""
    metadata_root = stage_continuity_metadata(
        bundled_path("registry", "aeat", "modelos", "390"),
        tmp_path,
        revision="2025",
    )

    assert metadata_root is not None
    assert {path.name for path in (metadata_root / "revisions").iterdir()} == {"2022", "2023", "2024"}


def _publication_context_for_target(
    target: Path,
    receipt: GeneratedExportTreeTargetStateReceipt,
) -> GeneratedExportTreePublicationContext:
    """Build a context only for the lock-state detector's private guard."""
    return GeneratedExportTreePublicationContext(
        validation=None,  # type: ignore[arg-type]
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
        _require_expected_target_state(
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
        _require_expected_target_state(
            _publication_context_for_target(target, receipt),
            target,
        )

    assert member.read_text(encoding="utf-8") == "id = 'mutated'\n"


def _prepared_absent_target(candidate_base: Path, target_root: Path) -> _PreparedInvocation:
    """Build a real isolated candidate for the bootstrap-path detector test."""
    validation, joined, semantic_map, rendered, candidate_export_root = _write_isolated_generated_authority_tree(
        candidate_base,
    )
    shutil.rmtree(candidate_export_root)
    _joined, _semantic_map, transport, render_profile, evidence = _real_authorities(_ISOLATED_TREE)
    inputs = RevisionRenderInputs(
        revision_id=validation.target.revision_id,
        layout_id=str(rendered.layout.id),
        joined=joined,
        semantic_map=semantic_map,
        render_profile=render_profile,
        render_profile_source_evidence=evidence,
        transport_profile=transport,
    )
    return _PreparedInvocation(
        invocation=_Invocation(
            _ISOLATED_TREE.modelo,
            _ISOLATED_TREE.revision,
            _ISOLATED_TREE.source_ref,
            _ISOLATED_TREE.filing_year,
            _ISOLATED_TREE.period,
        ),
        inputs=inputs,
        validation=validation,
        candidate_root=validation.registry_root,
        target_root=target_root,
        target_export_root=target_root
        / "modelos"
        / _ISOLATED_TREE.modelo
        / "revisions"
        / _ISOLATED_TREE.revision
        / "export",
        published_modelo_root=None,
    )


def _remove_candidate_export_refs(prepared: _PreparedInvocation) -> None:
    """Inject the missing-derived-ref defect bootstrap must repair before validation."""
    for path in (
        prepared.candidate_root / "modelos" / _ISOLATED_TREE.modelo / "revisions" / _ISOLATED_TREE.revision / "casillas"
    ).glob("*.toml"):
        path.write_text(
            "".join(
                line
                for line in path.read_text(encoding="utf-8").splitlines(keepends=True)
                if not line.startswith("export_refs = ")
            ),
            encoding="utf-8",
        )


def test_absent_tree_is_validated_then_published_through_the_canonical_authorities(tmp_path: Path) -> None:
    """An owed tree is bootstrap-publishable only after its fresh candidate validates."""
    first = _prepared_absent_target(tmp_path / "check", tmp_path / "target" / "registry" / "aeat")
    shutil.copytree(first.candidate_root, first.target_root)
    _remove_candidate_export_refs(first)

    result, _rendered, _target_state = _check(first)
    assert result == "publishable_absence"
    assert any(
        "export_refs = [" in path.read_text(encoding="utf-8")
        for path in (
            first.candidate_root
            / "modelos"
            / _ISOLATED_TREE.modelo
            / "revisions"
            / _ISOLATED_TREE.revision
            / "casillas"
        ).glob("*.toml")
    )
    assert first.candidate_root.joinpath(
        "modelos",
        _ISOLATED_TREE.modelo,
        "revisions",
        _ISOLATED_TREE.revision,
        "export",
    ).is_dir()
    assert not first.target_export_root.exists()

    publication = _prepared_absent_target(tmp_path / "publish", first.target_root)
    _publication_result, publication_rendered, publication_target_state = _check(publication)
    _publish(publication, publication_rendered, publication_target_state)

    assert first.target_export_root.is_dir()


def test_modelo_200_calculation_grade_does_not_widen_its_runtime_filing_authority() -> None:
    """Bootstrap publication can validate static output without promoting Modelo 200."""
    authority = bundled_authority()

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
    authority = bundled_authority()
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


def test_modelo_390_cli_assembly_uses_the_pipeline_source_defect_catalogue(tmp_path: Path) -> None:
    """The operator path validates M390 without consulting either prior export tree."""
    prepared = _prepare(
        _Invocation("390", "2022", "aeat-dr-390-2022", 2022, "0A"),
        tmp_path,
    )

    staged_revision = prepared.candidate_root / "modelos" / "390" / "revisions" / "2022"
    assert not (staged_revision / "export").exists()
    assert not (staged_revision / "export_layouts").exists()

    result, rendered, _target_state = _check(prepared)
    close = next(
        field
        for record in rendered.layout.records
        for field in record.fields
        if str(field.id) == "modelo-390-page-07-close"
    )

    assert result == "matched"
    assert close.literal == "</T39007000>"
