"""Operator check, publication, and digest-bound republication for one generated tree.

This privileged development CLI intentionally has no product-CLI registration.
It assembles one explicitly selected revision from the validated registry, then
delegates all rendering, validation, comparison, and transactional cutover to
the generator pipeline's canonical authorities. ``publish-authority`` validates
the whole registry candidate and republishes the runtime authority artifact.
"""

from __future__ import annotations

import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

import typer

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.locks_errors import LockAcquisitionError
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryError, RegistryValidationError
from dev._paths import prepare_temp_root

from ..compiler.authority import compile_validated_authority, compiled_bundled_authority
from ._export_tree import render_complete_export_tree
from ._form_layout_companion import prepare_generated_form_layout_companion
from ._tree_check import CheckedGeneratedExportTree, GeneratedExportTreeCheckContext, check_generated_export_tree
from ._tree_publication import publish_validated_generated_export_tree
from ._tree_validation import GeneratedExportTreeValidationContext, validate_generated_export_tree
from .authored_form_bridge import AuthoredFormBridge, prepare_authored_form_bridge
from .authority_cli import publish_authority
from .bootstrap_supersession import (
    bootstrap_layout_supersession_fingerprint,
    bootstrap_manual_source_revision_root,
    validate_bootstrap_manual_export_layout_supersession,
)
from .bootstrap_targets import GeneratedExportBootstrapTarget, generated_export_bootstrap_target
from .candidate_source_chain import requires_source_chain
from .candidate_staging import stage_generated_export_candidate
from .export_fragment_provenance import SHA256_PATTERN, ExportFragmentTarget
from .export_tree_models import RenderedExportTree
from .generated_export_inheritance import (
    generated_export_source_chain_fingerprint,
    select_generated_export_inheritance,
)
from .generated_export_inheritance_model import GeneratedExportInheritanceContext
from .generated_form_bridge import (
    GeneratedFormBridge,
    generated_form_companion_changed,
    prepare_generated_form_bridge,
)
from .generated_tree_dispositions import GeneratedTreeRecordDriftDisposition, record_drift_dispositions
from .historical_static_repair import validated_historical_repair_source
from .legacy_publication_recovery import retire_completed_legacy_publication
from .published_edition_staging import stage_published_modelo, supporting_modelos
from .render_check import (
    GeneratedExportBootstrapTransport,
    RenderComparison,
    RevisionRenderInputs,
    compare_export_tree_roots,
    revision_render_inputs,
    select_revision_record_design_source,
)
from .source_defects import source_defects_for
from .tree_publication_contracts import (
    GeneratedExportSupersession,
    GeneratedExportTreePublicationContext,
    GeneratedExportTreeTargetStateReceipt,
)
from .tree_publication_supersession_recovery import recover_interrupted_supersession_bundle

app = typer.Typer(
    name="pipeline",
    help=(
        "Check, publish, or digest-bound republish one generated AEAT registry export tree, "
        "or republish the runtime authority artifact."
    ),
    no_args_is_help=True,
)


app.command("publish-authority")(publish_authority)


@dataclass(frozen=True, slots=True)
class GeneratedTreeInvocation:
    """One explicit generated-tree lifecycle request: target, source, filing context and reviewed digest."""

    modelo: str
    revision: str
    source_ref: str
    filing_year: int
    period: str
    expected_manifest_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class PreparedGeneratedTreeInvocation:
    """A request with its staged candidate registry, derived render inputs and live target roots."""

    invocation: GeneratedTreeInvocation
    inputs: RevisionRenderInputs
    validation: GeneratedExportTreeValidationContext
    candidate_root: Path
    target_root: Path
    target_export_root: Path
    published_modelo_root: Path | None
    supersession: GeneratedExportSupersession | None = None
    inheritance: GeneratedExportInheritanceContext | None = None


def reviewed_bootstrap_target(
    invocation: GeneratedTreeInvocation, *, source_sha256: str
) -> GeneratedExportBootstrapTarget:
    """Load the reviewed bootstrap authority for one explicitly owed tree."""
    target = generated_export_bootstrap_target(
        modelo=invocation.modelo,
        revision=invocation.revision,
        source_ref=invocation.source_ref,
        source_sha256=source_sha256,
    )
    if target is None:
        raise ValueError(
            "no reviewed generated-export bootstrap target matches "
            f"{invocation.modelo}/{invocation.revision}/{invocation.source_ref}; publication is refused",
        )
    return target


def _bootstrap_selection(
    invocation: GeneratedTreeInvocation,
    authority: ValidatedRegistryAuthority,
    target_root: Path,
    target_export_root: Path,
    inheritance: GeneratedExportInheritanceContext | None,
) -> tuple[
    GeneratedExportBootstrapTransport | None, GeneratedExportBootstrapTarget | None, GeneratedExportSupersession | None
]:
    source = next(
        (item for ref, item in authority.catalogues.sources.items() if str(ref) == invocation.source_ref),
        None,
    )
    bootstrap = None
    bootstrap_target: GeneratedExportBootstrapTarget | None = None
    supersession: GeneratedExportSupersession | None = None
    if not target_export_root.exists() and inheritance is None:
        if source is None:
            raise ValueError(f"no source {invocation.source_ref!r} exists for bootstrap target selection")
        bootstrap_target = reviewed_bootstrap_target(invocation, source_sha256=source.sha256)
        if bootstrap_target.supersedes_layout_id is not None:
            source_modelo_root = target_root / "modelos" / invocation.modelo
            source_state_sha256 = validate_bootstrap_manual_export_layout_supersession(
                source_modelo_root,
                revision=invocation.revision,
                superseded_layout_id=bootstrap_target.supersedes_layout_id,
                expected_references=bootstrap_target.superseded_construct_references,
                generated_layout_id=bootstrap_target.layout_id,
                source_ref=bootstrap_target.source_ref,
                source_sha256=bootstrap_target.source_sha256,
                manual_origin_revision=bootstrap_target.manual_origin_revision,
            )
            manual_source_root, _ = bootstrap_manual_source_revision_root(
                source_modelo_root,
                authority.modelo(invocation.modelo),
                revision=invocation.revision,
                expected_origin_revision=bootstrap_target.manual_origin_revision,
            )
            supersession = GeneratedExportSupersession(
                superseded_layout_id=bootstrap_target.supersedes_layout_id,
                generated_layout_id=bootstrap_target.layout_id,
                expected_construct_references=bootstrap_target.superseded_construct_references,
                source_state_sha256=source_state_sha256,
                source_ref=bootstrap_target.source_ref,
                source_sha256=bootstrap_target.source_sha256,
                manual_source_sha256=bootstrap_layout_supersession_fingerprint(manual_source_root),
                manual_origin_revision=bootstrap_target.manual_origin_revision,
            )
        bootstrap = GeneratedExportBootstrapTransport(
            layout_id=bootstrap_target.layout_id,
            line_ending=bootstrap_target.line_ending,
            source_ref=bootstrap_target.source_ref,
            source_sha256=bootstrap_target.source_sha256,
            supersedes_layout_id=bootstrap_target.supersedes_layout_id,
        )
    return bootstrap, bootstrap_target, supersession


def _source_chain_receipts(
    invocation: GeneratedTreeInvocation,
    authority: ValidatedRegistryAuthority,
    target_root: Path,
    inheritance: GeneratedExportInheritanceContext | None,
) -> tuple[bool, str | None, str | None]:
    source_modelo = authority.modelo(invocation.modelo)
    inherited_revisions = () if inheritance is None else tuple(item[0] for item in inheritance.pinned_ancestors)
    retain_source_chain = requires_source_chain(source_modelo.revisions[invocation.revision]) or (
        inheritance is not None
        and any(
            source_modelo.revisions[revision_id].casilla_continuidad_evolutions
            for revision_id in (*inherited_revisions, invocation.revision)
        )
    )
    source_chain_sha256 = None
    source_chain_non_export_sha256 = None
    if retain_source_chain and inheritance is not None:
        source_chain_sha256 = generated_export_source_chain_fingerprint(
            target_root, modelo=invocation.modelo, revision=invocation.revision
        )
        source_chain_non_export_sha256 = generated_export_source_chain_fingerprint(
            target_root, modelo=invocation.modelo, revision=invocation.revision, omit_target_export=True
        )
    return retain_source_chain, source_chain_sha256, source_chain_non_export_sha256


def prepare_generated_tree_invocation(
    invocation: GeneratedTreeInvocation,
    root: Path,
    *,
    authority: ValidatedRegistryAuthority | None = None,
) -> PreparedGeneratedTreeInvocation:
    """Stage one narrow candidate and derive its render inputs from authority."""
    target_root = bundled_path("registry", "aeat")
    if authority is None:
        recover_interrupted_supersession_bundle(
            target_root=target_root,
            modelo=invocation.modelo,
            revision=invocation.revision,
        )
        try:
            authority = compiled_bundled_authority()
        except RegistryValidationError:
            # The exact reviewed historical target may itself be the one stale
            # export preventing whole-source compilation. Its structural render
            # is admitted only after a one-target whole-registry overlay passes
            # complete validation; every other compile refusal remains closed.
            authority = validated_historical_repair_source(
                modelo=invocation.modelo,
                revision=invocation.revision,
                source_ref=invocation.source_ref,
                filing_year=invocation.filing_year,
                period=invocation.period,
                expected_manifest_sha256=invocation.expected_manifest_sha256,
            )
    target_export_root = target_root / "modelos" / invocation.modelo / "revisions" / invocation.revision / "export"
    inheritance = select_generated_export_inheritance(
        authority,
        target_root,
        modelo=invocation.modelo,
        revision=invocation.revision,
        retain_source_chain=True,
    )
    bootstrap, bootstrap_target, supersession = _bootstrap_selection(
        invocation, authority, target_root, target_export_root, inheritance
    )
    try:
        inputs = revision_render_inputs(
            authority,
            modelo=invocation.modelo,
            revision=invocation.revision,
            source_ref=invocation.source_ref,
            bootstrap_transport=bootstrap,
            filing_year=invocation.filing_year,
            period=invocation.period,
        )
    except (RegistryError, ValueError) as error:
        raise ValueError(str(error)) from error

    candidate_root = root / "candidate" / "registry" / "aeat"
    source_modelo = authority.modelo(invocation.modelo)
    retain_source_chain, source_chain_sha256, source_chain_non_export_sha256 = _source_chain_receipts(
        invocation, authority, target_root, inheritance
    )
    stage_generated_export_candidate(
        target_root,
        candidate_root,
        modelo=invocation.modelo,
        revision=invocation.revision,
        supporting_modelos=supporting_modelos(invocation.modelo),
        bootstrap_target=bootstrap_target,
        inheritance=inheritance,
        retain_source_chain=retain_source_chain,
    )
    validation = GeneratedExportTreeValidationContext(
        registry_root=candidate_root,
        source_root=bundled_path(),
        target=ExportFragmentTarget(
            modelo=invocation.modelo,
            revision_id=invocation.revision,
            design_epoch=inputs.transport_profile.design_epoch,
        ),
        filing_year=invocation.filing_year,
        period=invocation.period,
        required_grade=authority.modelo(invocation.modelo).revisions[invocation.revision].effective_authority_grade,
        scope_authority=authority,
        source_chain_revisions=tuple(source_modelo.revisions) if retain_source_chain else (),
        source_chain_registry_root=(target_root.resolve() if retain_source_chain and inheritance is not None else None),
        source_chain_sha256=source_chain_sha256,
        source_chain_non_export_sha256=source_chain_non_export_sha256,
        supporting_modelos=supporting_modelos(invocation.modelo),
        # The complete validated source above already supplies continuity scope.
        # A second, detached sibling witness is unused by that validation path
        # and cannot represent edge-specific references without losing them.
        inheritance=inheritance,
        historical_static_source_ref=(
            inputs.transport_profile.source_ref
            if invocation.filing_year < authority.catalogues.require_supported_filing_years().floor
            else None
        ),
    )
    return PreparedGeneratedTreeInvocation(
        invocation=invocation,
        inputs=inputs,
        validation=validation,
        candidate_root=candidate_root,
        target_root=target_root,
        target_export_root=target_export_root,
        published_modelo_root=stage_published_modelo(
            root,
            modelo=invocation.modelo,
            revision=invocation.revision,
            inheritance=inheritance,
            retain_source_chain=retain_source_chain,
        ),
        supersession=supersession,
        inheritance=inheritance,
    )


def _render_candidate(prepared: PreparedGeneratedTreeInvocation) -> RenderedExportTree:
    """Render one candidate export tree into the staged revision."""
    candidate_export_root = (
        prepared.candidate_root
        / "modelos"
        / prepared.invocation.modelo
        / "revisions"
        / prepared.invocation.revision
        / "export"
    )
    rendered = render_complete_export_tree(
        candidate_export_root,
        revision_id=prepared.inputs.revision_id,
        joined=prepared.inputs.joined,
        semantic_map=prepared.inputs.semantic_map,
        transport_profile=prepared.inputs.transport_profile,
        render_profile=prepared.inputs.render_profile,
        render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
        source_defects=source_defects_for(prepared.invocation.source_ref),
        inheritance=prepared.inheritance,
    )
    prepare_generated_form_layout_companion(prepared.validation, temporary_root=prepared.candidate_root.parents[2])
    return rendered


def check_prepared_invocation(
    prepared: PreparedGeneratedTreeInvocation,
) -> tuple[Literal["matched", "publishable_absence"], RenderedExportTree, GeneratedExportTreeTargetStateReceipt]:
    """Drive the canonical checker, or validate a fresh candidate for an owed tree.

    An absent tree has no bytes to compare and therefore cannot be called a
    match.  It is nevertheless publishable when the real generator can render
    it and the real validator accepts that candidate.  This narrow bootstrap
    case keeps an owed tree from deadlocking the publisher while preserving the
    same pre-cutover validation boundary publication uses.
    """
    target_state = GeneratedExportTreeTargetStateReceipt.observe(
        prepared.target_export_root,
        supersession_source_sha256=(
            None if prepared.supersession is None else prepared.supersession.source_state_sha256
        ),
    )
    if not prepared.target_export_root.exists():
        rendered = _render_candidate(prepared)
        validate_generated_export_tree(
            context=prepared.validation,
            joined=prepared.inputs.joined,
            semantic_map=prepared.inputs.semantic_map,
            rendered=rendered,
            render_profile=prepared.inputs.render_profile,
            render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
        )
        return "publishable_absence", rendered, target_state
    checked: CheckedGeneratedExportTree = check_generated_export_tree(
        context=GeneratedExportTreeCheckContext(
            validation=prepared.validation,
            temporary_root=prepared.candidate_root.parents[2],
            target_registry_root=prepared.target_root,
            target_export_root=prepared.target_export_root,
            published_modelo_root=prepared.published_modelo_root,
        ),
        joined=prepared.inputs.joined,
        semantic_map=prepared.inputs.semantic_map,
        transport_profile=prepared.inputs.transport_profile,
        render_profile=prepared.inputs.render_profile,
        render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
        source_defects=source_defects_for(prepared.invocation.source_ref),
    )
    return "matched", checked.rendered, target_state


def publish_prepared_invocation(
    prepared: PreparedGeneratedTreeInvocation,
    rendered: RenderedExportTree,
    target_state: GeneratedExportTreeTargetStateReceipt,
    *,
    generated_form_bridge: GeneratedFormBridge | AuthoredFormBridge | None = None,
) -> None:
    """Publish the exact prepared candidate the read-only check just validated."""
    publish_validated_generated_export_tree(
        context=GeneratedExportTreePublicationContext(
            validation=prepared.validation,
            temporary_root=prepared.candidate_root.parents[2],
            target_root=prepared.target_root,
            target_export_root=prepared.target_export_root,
            expected_target_state=target_state,
            supersession=prepared.supersession,
            final_live_validator=(
                (lambda: generated_form_bridge.require_export_cutover(prepared.target_root))
                if generated_form_bridge is not None
                else (lambda: _validate_final_live_target(prepared))
            ),
        ),
        joined=prepared.inputs.joined,
        semantic_map=prepared.inputs.semantic_map,
        rendered=rendered,
        render_profile=prepared.inputs.render_profile,
        render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
    )


def _validate_final_live_target(prepared: PreparedGeneratedTreeInvocation) -> None:
    """Compile the complete live registry with the installed export before commit.

    The publisher has already proved the live export is byte-identical to the
    validated candidate, and the retained-source check proves every render
    input is unchanged, so re-rendering the target here would only repeat the
    candidate's own render and validation. Content-keyed verdicts let only the
    changed modelo validate again; this records no compiler closure, so it
    does not need the complete validation an authority publication does.
    """
    _require_retained_source_after_cutover(prepared)
    compile_validated_authority(prepared.target_root, bundled_path(), verify_evidence_bytes=True)
    _require_retained_source_after_cutover(prepared)


def _require_retained_source_after_cutover(prepared: PreparedGeneratedTreeInvocation) -> None:
    """Keep every captured source byte except the separately validated target export."""
    expected = prepared.validation.source_chain_non_export_sha256
    if expected is None:
        return
    if prepared.validation.source_chain_registry_root != prepared.target_root.resolve():
        raise RegistryValidationError("generated source-chain origin differs from the publication root")
    current = generated_export_source_chain_fingerprint(
        prepared.target_root,
        modelo=prepared.invocation.modelo,
        revision=prepared.invocation.revision,
        omit_target_export=True,
    )
    if current != expected:
        raise RegistryValidationError("generated source-chain facts changed during export cutover")


def require_republication_eligibility(
    invocation: GeneratedTreeInvocation,
    target_state: GeneratedExportTreeTargetStateReceipt,
    comparison: RenderComparison,
    *,
    source_sha256: str | None = None,
    dispositions: tuple[GeneratedTreeRecordDriftDisposition, ...] | None = None,
) -> None:
    """Admit one explicitly digest-bound manifest repair and nothing broader.

    ``dispositions`` defaults to the pipeline's own ledger, which is what every
    caller uses. It is a parameter so the admission rules can be proven against
    a stated row: a row retires as soon as its cause is repaired, so a proof
    that reaches into the live ledger for "some row with this remedy" passes or
    fails on whichever corrections happen to be outstanding.
    """
    _require_republication_target_binding(invocation, target_state, comparison)
    if comparison.disposition_class == "provenance_only":
        return
    _require_republication_record_disposition(invocation, comparison, dispositions, source_sha256=source_sha256)


def _require_republication_target_binding(
    invocation: GeneratedTreeInvocation,
    target_state: GeneratedExportTreeTargetStateReceipt,
    comparison: RenderComparison,
) -> None:
    expected = invocation.expected_manifest_sha256
    if expected is None or re.fullmatch(SHA256_PATTERN, expected) is None:
        raise ValueError("republish requires an exact lowercase 64-character target manifest sha256")
    if target_state.manifest_sha256 is None:
        raise ValueError("republish requires an existing generated export tree")
    if target_state.manifest_sha256 != expected:
        raise ValueError(
            "republish target manifest sha256 differs from the explicitly reviewed digest: "
            f"expected {expected}, found {target_state.manifest_sha256}",
        )
    if comparison.modelo != invocation.modelo or comparison.revision != invocation.revision:
        raise ValueError("republish comparison identity differs from the explicitly selected target")


def _require_republication_record_disposition(
    invocation: GeneratedTreeInvocation,
    comparison: RenderComparison,
    dispositions: tuple[GeneratedTreeRecordDriftDisposition, ...] | None,
    *,
    source_sha256: str | None,
) -> None:
    if comparison.disposition_class != "record_drift":
        raise ValueError(
            "republish admits attestation drift, or record drift a disposition explains; "
            f"differing={list(comparison.differing)!r} "
            f"only_committed={list(comparison.only_committed)!r} "
            f"only_rendered={list(comparison.only_rendered)!r}",
        )
    # A tree whose RECORDS changed can be replaced only where a disposition row
    # states why. Without this, a correction could never be published at all: the
    # check compares the shipped manifest against a fresh render and refuses the
    # difference, which is precisely the difference being landed. The generator
    # could be made right and the corpus could not be made to match it.
    #
    # The bar is HIGHER here than for attestation drift, not lower. That path
    # needs one proof - the reviewed digest. This needs two: the digest, and a
    # source-pinned row carrying a reason and a retirement condition, which the
    # ledger's own gate fails when its cause is gone. An unexplained record
    # change is refused exactly as before.
    subject = f"{invocation.modelo}/{invocation.revision}"
    rows = {row.subject: row for row in (record_drift_dispositions() if dispositions is None else dispositions)}
    disposition = rows.get(subject)
    if disposition is None:
        raise ValueError(
            f"republish refuses an unexplained record change for {subject}: "
            "declare a disposition row stating why the shipped records differ from what the "
            "current inputs produce, with its source pin and reconsideration condition",
        )
    _validate_record_disposition(invocation, comparison, disposition, subject, source_sha256)


def _validate_record_disposition(
    invocation: GeneratedTreeInvocation,
    comparison: RenderComparison,
    disposition: GeneratedTreeRecordDriftDisposition,
    subject: str,
    source_sha256: str | None,
) -> None:
    if disposition.remedy != "republish":
        # A row saying the SHIPPED bytes are right must never be read as
        # permission to overwrite them. Both directions produce identical record
        # drift, so without this the informative modelo whose type-2 record must
        # repeat per declarado would be republished into a return naming one
        # counterparty and dropping the rest.
        raise ValueError(
            f"republish refuses {subject}: its disposition declares the shipped records correct "
            f"and the inputs wrong (remedy={disposition.remedy!r}). Regenerating would ship the "
            "defect. Repair the inputs and retire the row instead",
        )
    if disposition.source_ref != invocation.source_ref or disposition.source_sha256 != source_sha256:
        raise ValueError("republish disposition source ref/SHA differs from the exact selected design")
    if comparison.only_committed or comparison.only_rendered:
        raise ValueError("republish disposition does not admit added or removed target files")
    if disposition.differing_records != len(comparison.record_differing):
        raise ValueError(
            f"republish disposition explains {disposition.differing_records} differing record(s), "
            f"but the exact comparison has {len(comparison.record_differing)}"
        )


def _republish(prepared: PreparedGeneratedTreeInvocation, target_state: GeneratedExportTreeTargetStateReceipt) -> None:
    """Replace one stale manifest only after an exact target-bound safety proof."""
    rendered = _render_candidate(prepared)
    candidate_export_root = (
        prepared.candidate_root
        / "modelos"
        / prepared.invocation.modelo
        / "revisions"
        / prepared.invocation.revision
        / "export"
    )
    comparison = compare_export_tree_roots(
        modelo=prepared.invocation.modelo,
        revision=prepared.invocation.revision,
        layout_id=prepared.inputs.layout_id,
        committed_root=prepared.target_export_root,
        rendered_root=candidate_export_root,
    )
    # The publisher validates this candidate under its transaction lock before
    # any cutover; the eligibility proof below needs only the byte comparison.
    generated_form_bridge = None
    if prepared.inheritance is not None and comparison.disposition_class == "record_drift":
        _require_storage_equivalent_republication(prepared, rendered, target_state, comparison)
    else:
        require_republication_eligibility(
            prepared.invocation,
            target_state,
            comparison,
            source_sha256=str(prepared.inputs.transport_profile.source_sha256),
        )
    if (prepared.invocation.modelo, prepared.invocation.revision) in {
        ("232", "2016-2017"),
        ("232", "2018-y-siguientes"),
        ("190", "2025-y-siguientes"),
        ("347", "2011-2024"),
        ("347", "2025-y-siguientes"),
        ("720", "2013-y-siguientes"),
    } and generated_form_companion_changed(
        prepared.target_root,
        prepared.candidate_root,
        prepared.invocation.modelo,
        prepared.invocation.revision,
    ):
        generated_form_bridge = prepare_generated_form_bridge(
            registry_root=prepared.target_root,
            candidate_root=prepared.candidate_root,
            modelo=prepared.invocation.modelo,
            revision=prepared.invocation.revision,
            source_ref=prepared.invocation.source_ref,
            source_sha256=str(prepared.inputs.transport_profile.source_sha256),
            expected_manifest_sha256=prepared.invocation.expected_manifest_sha256,
        )
    publish_prepared_invocation(prepared, rendered, target_state, generated_form_bridge=generated_form_bridge)
    if generated_form_bridge is not None:
        _finish_form_republication(
            prepared.target_root,
            generated_form_bridge,
            final_live_validator=lambda: _validate_final_live_target(prepared),
        )


def _finish_form_republication(
    registry_root: Path,
    bridge: GeneratedFormBridge | AuthoredFormBridge,
    *,
    final_live_validator: Callable[[], None],
) -> None:
    """Report the separate-owner interval as incomplete until full live proof."""
    try:
        bridge.finish_with_form_owner(registry_root, bundled_path())
        final_live_validator()
    except (OSError, RegistryError, ValueError) as error:
        raise RegistryValidationError(
            "Generated export source was installed but companion/currentness closure is incomplete; "
            f"repair through the canonical form owner: {error}"
        ) from error


def _require_storage_equivalent_republication(
    prepared: PreparedGeneratedTreeInvocation,
    rendered: RenderedExportTree,
    target_state: GeneratedExportTreeTargetStateReceipt,
    comparison: RenderComparison,
) -> None:
    """Admit only an exact old full tree becoming an equal, attested keyed delta."""
    _require_republication_target_binding(prepared.invocation, target_state, comparison)
    if (
        prepared.inheritance is None
        or rendered.output_files != ("0000-export-layout.toml",)
        or rendered.provenance_manifest.generated_export_inheritance != prepared.inheritance.attestation
        or comparison.disposition_class != "record_drift"
        or comparison.only_rendered
    ):
        raise ValueError("storage-equivalent republish requires an exact attested child delta and old full tree")
    full_root = prepared.candidate_root.parents[2] / "full-storage-witness" / "export"
    full_rendered = render_complete_export_tree(
        full_root,
        revision_id=prepared.inputs.revision_id,
        joined=prepared.inputs.joined,
        semantic_map=prepared.inputs.semantic_map,
        transport_profile=prepared.inputs.transport_profile,
        render_profile=prepared.inputs.render_profile,
        render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
        source_defects=source_defects_for(prepared.invocation.source_ref),
    )
    if full_rendered.layout != rendered.layout or full_rendered.field_derivations != rendered.field_derivations:
        raise ValueError("storage-equivalent republish changed fresh child layout or derivations")
    old_full_comparison = compare_export_tree_roots(
        modelo=prepared.invocation.modelo,
        revision=prepared.invocation.revision,
        layout_id=prepared.inputs.layout_id,
        committed_root=prepared.target_export_root,
        rendered_root=full_root,
    )
    if not old_full_comparison.reproduced:
        raise ValueError(
            "storage-equivalent republish refuses an old target that does not reproduce the current full source render"
        )


def _validate_reconciliation(
    prepared: PreparedGeneratedTreeInvocation,
    action: Literal["check", "publish", "republish"],
    reconcile_authored_form: bool,
    reconcile_casilla_splits: bool,
    reconcile_row_bindings: bool,
    reconcile_scalar_sources: bool,
) -> bool:
    if (
        sum(
            (
                reconcile_authored_form,
                reconcile_casilla_splits,
                reconcile_row_bindings,
                reconcile_scalar_sources,
            )
        )
        > 1
    ):
        raise ValueError("choose one authored form reconciliation mode")
    if (reconcile_casilla_splits or reconcile_row_bindings or reconcile_scalar_sources) and action != "republish":
        raise ValueError("field reconciliation requires exclusive republication")
    return _validate_reconciliation_target(prepared, action)


def _validate_reconciliation_target(
    prepared: PreparedGeneratedTreeInvocation, action: Literal["check", "publish", "republish"]
) -> bool:
    correcting_producers = action == "republish"
    if not correcting_producers and (
        action != "publish" or prepared.target_export_root.exists() or prepared.supersession is not None
    ):
        raise ValueError("authored form reconciliation requires a first export publication")
    if correcting_producers and (prepared.inheritance is not None or prepared.supersession is not None):
        raise ValueError("authored producer reconciliation refuses inherited or superseded export targets")
    return correcting_producers


def _reconcile_authored_form(
    invocation: GeneratedTreeInvocation,
    prepared: PreparedGeneratedTreeInvocation,
    root: Path,
    action: Literal["check", "publish", "republish"],
    reconcile_authored_form: bool,
    reconcile_casilla_splits: bool,
    reconcile_row_bindings: bool,
    reconcile_scalar_sources: bool,
) -> None:
    correcting_producers = _validate_reconciliation(
        prepared,
        action,
        reconcile_authored_form,
        reconcile_casilla_splits,
        reconcile_row_bindings,
        reconcile_scalar_sources,
    )
    target_state = GeneratedExportTreeTargetStateReceipt.observe(prepared.target_export_root)
    rendered = _render_candidate(prepared)
    if correcting_producers:
        comparison = compare_export_tree_roots(
            modelo=invocation.modelo,
            revision=invocation.revision,
            layout_id=prepared.inputs.layout_id,
            committed_root=prepared.target_export_root,
            rendered_root=prepared.candidate_root
            / "modelos"
            / invocation.modelo
            / "revisions"
            / invocation.revision
            / "export",
        )
        require_republication_eligibility(
            invocation,
            target_state,
            comparison,
            source_sha256=str(prepared.inputs.transport_profile.source_sha256),
        )
    bridge = prepare_authored_form_bridge(
        registry_root=prepared.target_root,
        candidate_root=prepared.candidate_root,
        source_root=prepared.validation.source_root,
        temporary_root=root,
        modelo=invocation.modelo,
        revision=invocation.revision,
        unreferenced_producers=correcting_producers
        and not (reconcile_casilla_splits or reconcile_row_bindings or reconcile_scalar_sources),
        casilla_splits=reconcile_casilla_splits,
        row_bindings=reconcile_row_bindings,
        scalar_sources=reconcile_scalar_sources,
    )
    publish_prepared_invocation(prepared, rendered, target_state, generated_form_bridge=bridge)
    _finish_form_republication(
        prepared.target_root, bridge, final_live_validator=lambda: _validate_final_live_target(prepared)
    )


def _run(
    invocation: GeneratedTreeInvocation,
    *,
    action: Literal["check", "publish", "republish"],
    reconcile_authored_form: bool = False,
    reconcile_casilla_splits: bool = False,
    reconcile_row_bindings: bool = False,
    reconcile_scalar_sources: bool = False,
    temporary_directory: Callable[..., tempfile.TemporaryDirectory[str]] = tempfile.TemporaryDirectory,
) -> None:
    """Run one explicit lifecycle action without retaining a staging tree."""
    try:
        with temporary_directory(prefix="cadrumo-generated-export-") as temporary_name:
            root = Path(temporary_name)
            prepared = prepare_generated_tree_invocation(invocation, root)
            if any(
                (reconcile_authored_form, reconcile_casilla_splits, reconcile_row_bindings, reconcile_scalar_sources)
            ):
                _reconcile_authored_form(
                    invocation,
                    prepared,
                    root,
                    action,
                    reconcile_authored_form,
                    reconcile_casilla_splits,
                    reconcile_row_bindings,
                    reconcile_scalar_sources,
                )
            elif action == "check":
                result, _rendered, _target_state = check_prepared_invocation(prepared)
                typer.echo(
                    "checked "
                    f"modelo={invocation.modelo} revision={invocation.revision} source={invocation.source_ref} "
                    f"result={result}",
                )
            elif action == "publish":
                # Publishing is never the first question: a candidate must first
                # pass the independent read-only proof against its live target.
                _result, rendered, target_state = check_prepared_invocation(prepared)
                publish_prepared_invocation(prepared, rendered, target_state)
            else:
                target_state = GeneratedExportTreeTargetStateReceipt.observe(prepared.target_export_root)
                _republish(prepared, target_state)
    except (RegistryError, ValueError) as error:
        typer.echo(f"refused: {error}", err=True)
        raise typer.Exit(code=1) from error


class TargetCurrentnessState(StrEnum):
    """Read-only state of one named generated export target."""

    CURRENT = "current"
    STALE = "stale"
    DRIFTED = "drifted"
    NEVER_COMMITTED = "never-committed"


@dataclass(frozen=True, slots=True)
class TargetCurrentnessFact:
    """Canonical generated-tree currentness fact and its comparison evidence."""

    modelo: str
    revision: str
    state: TargetCurrentnessState
    differing: tuple[str, ...] = ()
    only_committed: tuple[str, ...] = ()
    only_rendered: tuple[str, ...] = ()
    serialization_only: tuple[str, ...] = ()
    provenance_fields: tuple[str, ...] = ()
    detail: str = ""


def at_edition_grade(
    prepared: PreparedGeneratedTreeInvocation,
    grade: RegistryAuthorityGrade,
) -> PreparedGeneratedTreeInvocation:
    """Validate a prepared target at the authority grade its edition declares.

    Currentness asks whether the committed tree still reproduces and still
    loads, not whether the edition can back a filing. A calculation-grade
    edition never selects at filing grade, so proving its tree at the filing
    default reports drift for a tree that is exactly current.
    """
    return replace(prepared, validation=replace(prepared.validation, required_grade=grade))


def target_currentness(
    modelo: str,
    revision: str,
    source_ref: str | None,
    filing_year: int | None,
    period: str | None = None,
    *,
    authority: ValidatedRegistryAuthority | None = None,
) -> TargetCurrentnessFact:
    """Prove one generated target currentness without publishing or repairing it.

    The canonical generated-tree checker owns the fresh render, isolated
    authority validation, published-layout load, and byte comparison. The
    comparison below is used only to classify a refused check as stale
    attestation or substantive drift for the read-only fact.
    """
    effective_authority = compiled_bundled_authority() if authority is None else authority
    selected = effective_authority.modelo(modelo).revisions.get(revision)
    if selected is None:
        raise ValueError(f"modelo {modelo} declares no revision {revision!r}")
    effective_filing_year = selected.valid_from.year if filing_year is None else filing_year
    effective_period = period or str(selected.period_selector.periods_for_year(effective_filing_year)[0])
    selected_source_ref, _epoch = select_revision_record_design_source(
        effective_authority,
        modelo=modelo,
        revision=revision,
        filing_year=effective_filing_year,
        period=effective_period,
        source_ref=source_ref,
    )
    invocation = GeneratedTreeInvocation(
        modelo,
        revision,
        str(selected_source_ref),
        effective_filing_year,
        effective_period,
    )
    with tempfile.TemporaryDirectory(
        prefix="cadrumo-generated-export-currentness-", dir=prepare_temp_root()
    ) as temporary_name:
        prepared = at_edition_grade(
            prepare_generated_tree_invocation(invocation, Path(temporary_name), authority=effective_authority),
            selected.effective_authority_grade,
        )
        return _target_currentness_for_prepared(modelo, revision, prepared)


def _target_currentness_for_prepared(
    modelo: str,
    revision: str,
    prepared: PreparedGeneratedTreeInvocation,
) -> TargetCurrentnessFact:
    if not prepared.target_export_root.exists():
        check_prepared_invocation(prepared)
        return TargetCurrentnessFact(
            modelo=modelo,
            revision=revision,
            state=TargetCurrentnessState.NEVER_COMMITTED,
            detail="the target rendered successfully but has no committed export tree",
        )
    try:
        check_prepared_invocation(prepared)
    except (OSError, RegistryError, ValueError) as error:
        return _classify_target_currentness_failure(prepared, error)
    return TargetCurrentnessFact(
        modelo=modelo,
        revision=revision,
        state=TargetCurrentnessState.CURRENT,
        detail="fresh canonical output matches the committed target",
    )


def _classify_target_currentness_failure(
    prepared: PreparedGeneratedTreeInvocation,
    error: OSError | RegistryError | ValueError,
) -> TargetCurrentnessFact:
    modelo = prepared.invocation.modelo
    revision = prepared.invocation.revision
    candidate_export_root = prepared.candidate_root / "modelos" / modelo / "revisions" / revision / "export"
    comparison: RenderComparison | None = None
    try:
        if not candidate_export_root.exists():
            _render_candidate(prepared)
        comparison = compare_export_tree_roots(
            modelo=modelo,
            revision=revision,
            layout_id=prepared.inputs.layout_id,
            committed_root=prepared.target_export_root,
            rendered_root=candidate_export_root,
        )
    except (OSError, RegistryError, ValueError):
        pass
    if comparison is None:
        return TargetCurrentnessFact(
            modelo=modelo,
            revision=revision,
            state=TargetCurrentnessState.DRIFTED,
            detail=str(error),
        )
    return _target_currentness_comparison_fact(modelo, revision, comparison, error)


def _target_currentness_comparison_fact(
    modelo: str,
    revision: str,
    comparison: RenderComparison,
    error: OSError | RegistryError | ValueError,
) -> TargetCurrentnessFact:
    state = TargetCurrentnessState.STALE if comparison.provenance_only else TargetCurrentnessState.DRIFTED
    # A stale manifest's refusal names the digest that failed; the members that
    # differ from a fresh render say which input moved.
    detail = str(error)
    if comparison.provenance_fields:
        detail = f"{detail}; manifest members differing from a fresh render: " + ", ".join(comparison.provenance_fields)
    return TargetCurrentnessFact(
        modelo=modelo,
        revision=revision,
        state=state,
        differing=comparison.differing,
        only_committed=comparison.only_committed,
        only_rendered=comparison.only_rendered,
        serialization_only=comparison.serialization_only,
        provenance_fields=comparison.provenance_fields,
        detail=detail,
    )


_MODELO = Annotated[str, typer.Argument(help="Three-digit AEAT modelo identifier.")]
_REVISION = Annotated[str, typer.Argument(help="Exact declared revision identifier.")]
_SOURCE = Annotated[str, typer.Argument(help="Exact declared record-design source reference.")]
_FILING_YEAR = Annotated[int, typer.Argument(help="Filing year used to select the stated source.")]
_PERIOD = Annotated[str, typer.Argument(help="Non-empty declared filing period, for example 0A.")]


@app.command("target-current")
def target_current_command(
    modelo: _MODELO,
    revision: _REVISION,
    source_ref: _SOURCE,
    filing_year: _FILING_YEAR,
    period: _PERIOD,
) -> None:
    """Prove one named generated target is current without changing it."""
    try:
        fact = target_currentness(modelo, revision, source_ref, filing_year, period)
    except (OSError, RegistryError, ValueError) as error:
        typer.echo(f"refused: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(
        "target-current"
        f"\tmodelo={fact.modelo}"
        f"\trevision={fact.revision}"
        f"\tstate={fact.state.value}"
        f"\tdetail={fact.detail}",
    )
    if fact.state is not TargetCurrentnessState.CURRENT:
        raise typer.Exit(code=1)


@app.command("publish-target")
def publish_target_command(
    modelo: _MODELO,
    revision: _REVISION,
    source_ref: _SOURCE,
    filing_year: _FILING_YEAR,
    period: _PERIOD,
    reconcile_authored_form: Annotated[
        bool,
        typer.Option("--reconcile-authored-form", help="Preserve an authored draft while installing its first export."),
    ] = False,
) -> None:
    """Check, then transactionally publish one named static target tree."""
    _run(
        GeneratedTreeInvocation(modelo, revision, source_ref, filing_year, period),
        action="publish",
        reconcile_authored_form=reconcile_authored_form,
    )
    typer.echo(f"publish-target\tmodelo={modelo}\trevision={revision}\tsource={source_ref}")
    typer.echo(
        "next\tcurrentness=check-registry-target-current\tpublication=registry-publish-authority-if-authority-stale"
    )


@app.command("recover-completed-legacy-target")
def recover_completed_legacy_target_command(
    modelo: _MODELO,
    revision: _REVISION,
    source_ref: _SOURCE,
    filing_year: _FILING_YEAR,
    period: _PERIOD,
    expected_manifest_sha256: Annotated[str, typer.Option("--expected-manifest-sha256")],
) -> None:
    """Retire a completed legacy journal after digest-bound current record equivalence."""
    invocation = GeneratedTreeInvocation(modelo, revision, source_ref, filing_year, period, expected_manifest_sha256)
    try:
        if re.fullmatch(SHA256_PATTERN, expected_manifest_sha256) is None:
            raise ValueError("legacy recovery requires an exact lowercase target manifest sha256")
        authority = compiled_bundled_authority()
        with tempfile.TemporaryDirectory(
            prefix="cadrumo-legacy-export-recovery-", dir=prepare_temp_root()
        ) as directory:
            prepared = prepare_generated_tree_invocation(invocation, Path(directory), authority=authority)
            rendered = _render_candidate(prepared)
            receipt = GeneratedExportTreeTargetStateReceipt.observe(prepared.target_export_root)
            if receipt.manifest_sha256 != expected_manifest_sha256:
                raise ValueError("legacy recovery target manifest differs from the explicitly reviewed digest")
            retire_completed_legacy_publication(
                context=GeneratedExportTreePublicationContext(
                    validation=prepared.validation,
                    temporary_root=prepared.candidate_root.parents[2],
                    target_root=prepared.target_root,
                    target_export_root=prepared.target_export_root,
                    expected_target_state=receipt,
                ),
                joined=prepared.inputs.joined,
                semantic_map=prepared.inputs.semantic_map,
                rendered=rendered,
                render_profile=prepared.inputs.render_profile,
                render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
            )
    except (RegistryError, LockAcquisitionError, OSError, ValueError) as error:
        typer.echo(f"refused: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(f"recovered-completed-legacy-target\tmodelo={modelo}\trevision={revision}")


@app.command("republish-target")
def republish_target_command(
    modelo: _MODELO,
    revision: _REVISION,
    source_ref: _SOURCE,
    filing_year: _FILING_YEAR,
    period: _PERIOD,
    expected_manifest_sha256: Annotated[
        str,
        typer.Argument(help="Exact current manifest sha256 reviewed for replacement."),
    ],
    reconcile_unreferenced_producers: Annotated[
        bool,
        typer.Option(
            "--reconcile-unreferenced-producers",
            help="Reconcile unseen headers or computed markers replaced by displayed manual X-or-blank casillas.",
        ),
    ] = False,
    reconcile_casilla_splits: Annotated[
        bool,
        typer.Option(
            "--reconcile-casilla-splits", help="Preserve an authored draft through reviewed text-field subdivision."
        ),
    ] = False,
    reconcile_row_bindings: Annotated[
        bool,
        typer.Option(
            "--reconcile-row-bindings", help="Preserve official positions while connecting repeated row sources."
        ),
    ] = False,
    reconcile_scalar_sources: Annotated[
        bool,
        typer.Option(
            "--reconcile-scalar-sources",
            help="Preserve an authored draft through reviewed manual-input or rate-box scalar source corrections.",
        ),
    ] = False,
) -> None:
    """Digest-bound republish of one named target after its exact state was reviewed."""
    _run(
        GeneratedTreeInvocation(modelo, revision, source_ref, filing_year, period, expected_manifest_sha256),
        action="republish",
        reconcile_authored_form=reconcile_unreferenced_producers,
        reconcile_casilla_splits=reconcile_casilla_splits,
        reconcile_row_bindings=reconcile_row_bindings,
        reconcile_scalar_sources=reconcile_scalar_sources,
    )
    typer.echo(f"republish-target\tmodelo={modelo}\trevision={revision}\tsource={source_ref}")
    typer.echo(
        "next\tcurrentness=check-registry-target-current\tpublication=registry-publish-authority-if-authority-stale"
    )


@app.command("check")
def check_command(
    modelo: _MODELO,
    revision: _REVISION,
    source_ref: _SOURCE,
    filing_year: _FILING_YEAR,
    period: _PERIOD,
    expected_manifest_sha256: Annotated[
        str | None,
        typer.Option("--expected-manifest-sha256", help="Reviewed current manifest for an exact stale-target repair."),
    ] = None,
) -> None:
    """Regenerate and validate one target without changing the published registry."""
    _run(
        GeneratedTreeInvocation(modelo, revision, source_ref, filing_year, period, expected_manifest_sha256),
        action="check",
    )


@app.command("publish")
def publish_command(
    modelo: _MODELO,
    revision: _REVISION,
    source_ref: _SOURCE,
    filing_year: _FILING_YEAR,
    period: _PERIOD,
) -> None:
    """Check, then transactionally publish one target through the canonical authority."""
    _run(GeneratedTreeInvocation(modelo, revision, source_ref, filing_year, period), action="publish")
    typer.echo(f"published modelo={modelo} revision={revision} source={source_ref}")


@app.command("republish")
def republish_command(
    modelo: _MODELO,
    revision: _REVISION,
    source_ref: _SOURCE,
    filing_year: _FILING_YEAR,
    period: _PERIOD,
    expected_manifest_sha256: Annotated[
        str,
        typer.Argument(help="Exact current manifest sha256 reviewed for provenance-only replacement."),
    ],
) -> None:
    """Replace one digest-pinned tree only when its records reproduce semantically."""
    _run(
        GeneratedTreeInvocation(modelo, revision, source_ref, filing_year, period, expected_manifest_sha256),
        action="republish",
    )
    typer.echo(f"republished modelo={modelo} revision={revision} source={source_ref}")


__all__ = [
    "TargetCurrentnessFact",
    "TargetCurrentnessState",
    "app",
    "at_edition_grade",
    "target_currentness",
]
