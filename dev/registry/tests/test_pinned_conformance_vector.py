"""Detector teeth for the pinned public conformance-vector contract.

The pinning design exists to make a regenerated export tree fail closed rather
than be silently absorbed: the vector's evidence is committed data, so a tree
whose generation manifest no longer matches the pin must be refused. These
tests prove that refusal actually fires, and that a corrupt pin surfaces as a
typed registry refusal rather than an unhandled crash with no owner.
"""

from __future__ import annotations

import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryError, RegistryFailureCondition, RegistryValidationError
from cadrumo.domain.calculations.registry.export_parse import parse_export_payload
from cadrumo.domain.calculations.registry.governed_fact_scope import (
    governed_facts_in_scope,
    validating_governed_facts,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    newest_authored_editions,
    open_ended_revision,
    revision_covering,
)

from ..filing_export_conformance import FilingExportConformanceRequest
from ..filing_export_conformance_vectors import (
    FilingExportConformanceVector,
    build_pinned_conformance_evidence,
    canonical_filing_export_conformance_vectors,
    load_pinned_conformance_document,
    load_pinned_conformance_inputs,
)
from ..filing_export_proof_authority import (
    CanonicalTwoChannelFilingExportProofAuthority,
)
from ..filing_export_proof_contracts import FilingExportConformanceRenderInputs
from ..filing_export_writer import export

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PINNED_DIR = Path(__file__).resolve().parents[1] / "conformance_vectors"
_PINNED = _PINNED_DIR / "modelo_200_2025_y_siguientes.toml"
_REGISTRY_ROOT = bundled_path("registry", "aeat")
#: The pin covers the open-ended edition of Modelo 200.
_PINNED_M200_REVISION = str(open_ended_revision("200").id)
#: The pin that exercises the success path whatever Modelo 200's grade is: Modelo 165 is held at filing grade.
_PINNED_FILING_GRADE_MODELO = "165"
_PINNED_FILING_GRADE_REVISION = str(open_ended_revision(_PINNED_FILING_GRADE_MODELO).id)


#: Every Modelo 200 revision a committed pin declares, read from the pins themselves.
_PINNED_M200_REVISIONS = tuple(
    sorted(
        {
            document.coordinate.revision
            for document in map(load_pinned_conformance_document, sorted(_PINNED_DIR.glob("*.toml")))
            if document.coordinate.modelo == "200"
        }
    )
)


#: Hand-derived cuota integra (DP200014:00562) for each pinned scenario, keyed by the scenario's
#: resultado contable (00501), INCN of the preceding periodo impositivo and pending BIN. The
#: general case: INCN at or above one million euros, so LIS art. 29.1 gives 25 % x 100000.00.
#: The reduced case: INCN 28500.00, below one million, so the 23 % rate LIS art. 29.1 takes
#: from Ley 31/2022 art. 39 applies to the base 25400.00 - 16300.00 = 9100.00, giving 2093.00.
#: The worked-example case states no preceding-period INCN, because its edition precedes that
#: rate and reads none: the Sociedades manual's "Ejemplo 1" of the cuota liquida minima prints a
#: base imponible of 2.000.000 at the tipo general of 25 % and a cuota integra [00562] of 500.000.
_CUOTA_INTEGRA_BY_SCENARIO = {
    (Decimal("100000"), Decimal("12000000"), Decimal("0")): Decimal("25000"),
    (Decimal("25400.00"), Decimal("28500.00"), Decimal("16300.00")): Decimal("2093.00"),
    (Decimal("2000000.00"), None, Decimal("0")): Decimal("500000.00"),
}


_PRIOR_INCN_BINDING = "modelo-200-incn-periodo-impositivo-anterior"


def _pinned_scenario_cuota_integra(authority: ValidatedRegistryAuthority, revision_id: str) -> Decimal:
    """Return the hand-derived cuota integra of the scenario the Modelo 200 pin for ``revision_id`` declares.

    A revision that declares the preceding-period INCN binding reads it for the rate, so its
    pin must state it; only a revision without that binding may leave it out.
    """
    (document,) = (
        document
        for document in map(load_pinned_conformance_document, sorted(_PINNED_DIR.glob("*.toml")))
        if document.coordinate.modelo == "200" and document.coordinate.revision == revision_id
    )
    (revision,) = (
        revision for revision in authority.modelo("200").revisions.values() if str(revision.id) == revision_id
    )
    decimals = document.inputs["decimal"]
    if any(binding.id == _PRIOR_INCN_BINDING for binding in revision.bindings):
        assert _PRIOR_INCN_BINDING in decimals, (
            f"the Modelo 200 pin for {revision_id} omits {_PRIOR_INCN_BINDING}, which that revision declares"
        )
        prior_incn: Decimal | None = Decimal(decimals[_PRIOR_INCN_BINDING])
    else:
        assert _PRIOR_INCN_BINDING not in decimals, (
            f"the Modelo 200 pin for {revision_id} states {_PRIOR_INCN_BINDING}, which that revision does not declare"
        )
        prior_incn = None
    scenario = (
        Decimal(decimals["DP200012:00501"]),
        prior_incn,
        Decimal(decimals["modelo-200-bin-pendiente-ejercicios-anteriores"]),
    )
    assert scenario in _CUOTA_INTEGRA_BY_SCENARIO, f"no hand-derived cuota for the pinned scenario {scenario}"
    return _CUOTA_INTEGRA_BY_SCENARIO[scenario]


def _pinned_revision_is_filing_grade(authority: ValidatedRegistryAuthority, revision_id: str) -> bool:
    (revision,) = (
        revision for revision in authority.modelo("200").revisions.values() if str(revision.id) == revision_id
    )
    return revision.authority_grade is RegistryAuthorityGrade.FILING


def _filing_grade_m200_revisions(authority: ValidatedRegistryAuthority) -> set[str]:
    return {
        str(revision.id)
        for revision in authority.modelo("200").revisions.values()
        if revision.authority_grade is RegistryAuthorityGrade.FILING
    }


def test_the_shipped_pin_admits_the_current_generated_tree_and_enrolls_by_grade(
    canonical_filing_export_proof: CanonicalTwoChannelFilingExportProofAuthority,
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The committed pins admit the tree as generated today, and enroll only while their revision is filing grade.

    Loading the vectors checks the live generation manifest against the pinned
    digest, so a pin admits the tree whatever the grade. Every filing-grade
    Modelo 200 revision must carry its own pin, so an unpinned edition fails
    here rather than being tolerated. The open-ended pin is kept whatever its
    grade; held below filing grade it is refused with its own residue rather
    than dropped.
    """
    filing_grade_m200 = _filing_grade_m200_revisions(registry_authority)
    vectors = canonical_filing_export_conformance_vectors(
        registry_root=_REGISTRY_ROOT,
        source_root=bundled_path(),
    )
    assert {
        (str(vector.evidence.coordinate.modelo), str(vector.evidence.coordinate.revision)) for vector in vectors
    } == {
        *(("200", revision) for revision in filing_grade_m200 | {_PINNED_M200_REVISION}),
        (_PINNED_FILING_GRADE_MODELO, _PINNED_FILING_GRADE_REVISION),
    }

    # The canonical proof derives its enrollment from exactly these vectors and
    # the validated bundled authority.
    enrollment = canonical_filing_export_proof.conformance_enrollment
    materialized = {
        (str(vector.evidence.coordinate.modelo), str(vector.evidence.coordinate.revision))
        for vector in enrollment.materializable_vectors
    }
    assert (_PINNED_FILING_GRADE_MODELO, _PINNED_FILING_GRADE_REVISION) in materialized
    m200_residues = [
        (residue.revision, residue.reason, residue.owner, residue.detail)
        for residue in enrollment.residues
        if str(residue.modelo) == "200"
    ]
    assert {("200", revision) for revision in filing_grade_m200} <= materialized, m200_residues
    if _pinned_revision_is_filing_grade(registry_authority, _PINNED_M200_REVISION):
        assert not m200_residues
    else:
        assert ("200", _PINNED_M200_REVISION) not in materialized
        assert [(str(revision), reason) for revision, reason, _, _ in m200_residues] == [
            (_PINNED_M200_REVISION, "filing_revision_unselected")
        ]
    candidates = {
        (str(candidate.evidence.coordinate.modelo), str(candidate.evidence.coordinate.revision))
        for candidate in enrollment.provenance_candidates
    }
    assert {
        ("165", str(open_ended_revision("165").id)),
        *(("189", str(revision_covering("189", year).id)) for year in newest_authored_editions("189", 2)),
        ("369", "esquema-exterior"),
        ("369", "esquema-importacion"),
        ("369", "esquema-union"),
    } <= candidates


def _pinned_vector(
    vectors: tuple[FilingExportConformanceVector, ...],
    modelo: str,
    revision: str,
) -> FilingExportConformanceVector:
    (vector,) = (
        vector
        for vector in vectors
        if str(vector.evidence.coordinate.modelo) == modelo and str(vector.evidence.coordinate.revision) == revision
    )
    return vector


def _assert_payload_parses_back(
    tmp_path: Path,
    *,
    proof: CanonicalTwoChannelFilingExportProofAuthority,
    authority: ValidatedRegistryAuthority,
    render: FilingExportConformanceRenderInputs,
    vector: FilingExportConformanceVector,
) -> None:
    """The writer's bytes read back through the registry codec in layout order with the draft's typed values."""
    evidence = vector.evidence
    output_path = tmp_path / "parse-back" / "payload"
    output_path.parent.mkdir(parents=True)
    with validating_governed_facts(authority):
        provider = proof.schema_provider_for_conformance(evidence)
        (layout,) = authority.snapshot(
            evidence.coordinate.modelo,
            filing_year=evidence.filing_year,
            period=evidence.period.registry_token,
            grade=RegistryAuthorityGrade.FILING,
        ).revision.export_layouts
        export(render, output_path=output_path, schema_provider=provider)
        parsed = parse_export_payload(
            layout,
            output_path.read_bytes(),
            sources=provider.sources,
            source_payloads=provider.source_payloads,
        )
    record_order = {record.id: record.order for record in layout.records}
    parsed_orders = [record_order[value.record_id] for value in parsed.fields]
    assert parsed_orders == sorted(parsed_orders)
    assert {value.record_id for value in parsed.fields} >= {record.id for record in layout.records if record.required}
    parsed_by_casilla = {value.casilla_id: value.value for value in parsed.casillas if value.casilla_id is not None}
    stated = {value.casilla_id: value.value for value in render.draft.values if isinstance(value.value, Decimal)}
    for casilla_id in stated.keys() & parsed_by_casilla.keys():
        assert parsed_by_casilla[casilla_id] == stated[casilla_id], casilla_id


def _corrupt_candidate_output_is_refused(
    tmp_path: Path,
    *,
    proof: CanonicalTwoChannelFilingExportProofAuthority,
    authority: ValidatedRegistryAuthority,
    vector: FilingExportConformanceVector,
    request: FilingExportConformanceRequest,
) -> None:
    """The healthy active tree must not mask a corrupt explicitly selected candidate."""
    modelo = str(vector.evidence.coordinate.modelo)
    revision = str(vector.evidence.coordinate.revision)
    candidate_root = tmp_path / "registry"
    # The whole modelo is copied because an edition's generated export can inherit
    # its predecessor's package, which the writer reads from the same candidate root.
    shutil.copytree(_REGISTRY_ROOT / f"modelos/{modelo}", candidate_root / f"modelos/{modelo}")
    candidate_export = candidate_root / f"modelos/{modelo}/revisions/{revision}/export"
    selected_output = candidate_export / vector.evidence.provenance.generated_outputs[0].relative_path
    selected_output.write_bytes(selected_output.read_bytes() + b"\n# changed candidate\n")
    candidate_proof = CanonicalTwoChannelFilingExportProofAuthority(
        workspace_root=Path.cwd(),
        registry_root=candidate_root,
        source_root=bundled_path(),
        authority=authority,
        vectors=(vector,),
        conformance_enrollment=proof.conformance_enrollment,
        secure_replay_source=None,
        secure_replay_custody=None,
    )
    with pytest.raises(RegistryValidationError, match="output-file digests"):
        candidate_proof.prove_conformance(request)


def _prove_through_the_real_writer(
    tmp_path: Path,
    *,
    proof: CanonicalTwoChannelFilingExportProofAuthority,
    authority: ValidatedRegistryAuthority,
    vector: FilingExportConformanceVector,
) -> FilingExportConformanceRenderInputs:
    """Build the vector's inputs, prove it through the production writer and refuse a corrupt candidate."""
    before = governed_facts_in_scope()
    render = vector.builder.build(vector.evidence)
    assert governed_facts_in_scope() is before
    assert render.draft.profile_tax_id == render.producer_snapshot.taxpayer_tax_id
    request = FilingExportConformanceRequest(coordinate=vector.evidence.coordinate)
    receipt = proof.prove_conformance(request)
    assert receipt.checked_official_offsets == len(vector.evidence.provenance.probes)
    assert receipt.emitted_bytes > 0
    assert receipt.taxpayer_truth_claimed is False
    assert receipt.source_owned_replay_claimed is False
    assert governed_facts_in_scope() is before
    _assert_payload_parses_back(tmp_path, proof=proof, authority=authority, render=render, vector=vector)
    assert governed_facts_in_scope() is before
    _corrupt_candidate_output_is_refused(tmp_path, proof=proof, authority=authority, vector=vector, request=request)
    assert governed_facts_in_scope() is before
    return render


def test_a_filing_grade_pin_proves_through_the_real_writer(
    tmp_path: Path,
    canonical_filing_export_proof: CanonicalTwoChannelFilingExportProofAuthority,
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """Every materializable pin runs the proof's success path, and its emitted bytes parse back.

    The Modelo 165 pin is held at filing grade, so the success path runs
    whatever Modelo 200's grade is; every filing-grade Modelo 200 edition runs
    through the same writer under its own pin.
    """
    proved = set()
    for vector in canonical_filing_export_proof.conformance_enrollment.materializable_vectors:
        modelo = str(vector.evidence.coordinate.modelo)
        revision = str(vector.evidence.coordinate.revision)
        _prove_through_the_real_writer(
            tmp_path / f"{modelo}-{revision}",
            proof=canonical_filing_export_proof,
            authority=registry_authority,
            vector=vector,
        )
        proved.add((modelo, revision))
    assert (_PINNED_FILING_GRADE_MODELO, _PINNED_FILING_GRADE_REVISION) in proved
    assert {("200", revision) for revision in _filing_grade_m200_revisions(registry_authority)} <= proved


@pytest.mark.parametrize("pinned_revision", _PINNED_M200_REVISIONS)
def test_the_modelo_200_pin_follows_the_declared_grade(
    pinned_revision: str,
    tmp_path: Path,
    canonical_filing_export_proof: CanonicalTwoChannelFilingExportProofAuthority,
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """Required rows, typed rate inputs and official probes reach the production writer once the grade allows it.

    The production writer admits a filing-grade revision only. While the pinned
    revision is held below it, the canonical builder is refused with the typed
    grade failure, the proof refuses the unenrolled coordinate, and both leave
    the candidate fact scope as they found it. The expectation is derived from
    the registry's declared grade, so it becomes the success expectation when
    the grade returns.
    """
    authority = registry_authority
    proof = canonical_filing_export_proof
    before = governed_facts_in_scope()
    if not _pinned_revision_is_filing_grade(authority, pinned_revision):
        pinned = _pinned_vector(
            canonical_filing_export_conformance_vectors(registry_root=_REGISTRY_ROOT, source_root=bundled_path()),
            "200",
            pinned_revision,
        )
        with pytest.raises(RegistryError) as refused:
            pinned.builder.build(pinned.evidence)
        failure = refused.value.registry_failure
        assert failure is not None
        assert failure.condition is RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT
        assert governed_facts_in_scope() is before
        with pytest.raises(ValueError, match="no mechanism vector"):
            proof.prove_conformance(FilingExportConformanceRequest(coordinate=pinned.evidence.coordinate))
        assert governed_facts_in_scope() is before
        return
    vector = _pinned_vector(proof.conformance_enrollment.materializable_vectors, "200", pinned_revision)
    render = _prove_through_the_real_writer(tmp_path, proof=proof, authority=authority, vector=vector)
    values = {value.casilla_id: value.value for value in render.draft.values}
    assert values["DP200014:00562"] == _pinned_scenario_cuota_integra(authority, pinned_revision)
    assert render.product_software_identity is not None


def test_a_manifest_digest_that_drifts_from_the_pin_is_refused(tmp_path: Path) -> None:
    """A regenerated tree must fail closed, never be silently absorbed."""
    drifted = tmp_path / "drifted.toml"
    text = _PINNED.read_text(encoding="utf-8")
    document = load_pinned_conformance_document(_PINNED)
    drifted.write_text(
        text.replace(document.generation_manifest_sha256, "0" * 64),
        encoding="utf-8",
    )
    manifest_path = (
        _REGISTRY_ROOT
        / "modelos"
        / "200"
        / "revisions"
        / _PINNED_M200_REVISION
        / "export"
        / "_generation.provenance.json"
    )
    manifest_raw = manifest_path.read_bytes()

    from ..pipeline.export_fragment_provenance import load_export_fragment_provenance_manifest

    with pytest.raises(RegistryValidationError, match="does not match the pinned conformance vector"):
        build_pinned_conformance_evidence(
            load_pinned_conformance_document(drifted),
            manifest_raw=manifest_raw,
            manifest=load_export_fragment_provenance_manifest(manifest_raw),
        )


def test_a_corrupt_pin_refuses_as_a_typed_registry_error(tmp_path: Path) -> None:
    """A truncated or malformed pin must not escape as an unowned crash."""
    truncated = tmp_path / "truncated.toml"
    shutil.copy(_PINNED, truncated)
    truncated.write_text('authority_id = "only-this"\n', encoding="utf-8")
    with pytest.raises(RegistryValidationError, match="pinned-vector contract"):
        load_pinned_conformance_document(truncated)

    unparseable = tmp_path / "unparseable.toml"
    unparseable.write_text("this is = = not toml\n", encoding="utf-8")
    with pytest.raises(RegistryValidationError, match="unreadable"):
        load_pinned_conformance_document(unparseable)

    absent = tmp_path / "absent.toml"
    with pytest.raises(RegistryValidationError, match="unreadable"):
        load_pinned_conformance_document(absent)


def test_one_id_declared_on_both_input_channels_is_refused(tmp_path: Path) -> None:
    """An ambiguous declaration is refused rather than resolved by ordering."""
    colliding = tmp_path / "colliding.toml"
    text = _PINNED.read_text(encoding="utf-8")
    decimal_id = next(iter(load_pinned_conformance_document(_PINNED).inputs["decimal"]))
    colliding.write_text(
        text.replace(
            "[inputs.enum]",
            f'[inputs.enum]\n"{decimal_id}" = "sl"',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(RegistryValidationError, match="multiple typed channels"):
        load_pinned_conformance_inputs(load_pinned_conformance_document(colliding))


def test_public_boolean_input_is_typed_and_cannot_shadow_another_channel(tmp_path: Path) -> None:
    """Profile predicates arrive as bools, never numeric substitutes or overwritten ids."""
    document = load_pinned_conformance_document(_PINNED)
    values = load_pinned_conformance_inputs(document)
    assert values["modelo-200-profile-new-entity-flag"] is False
    colliding = tmp_path / "boolean-collision.toml"
    colliding.write_text(
        _PINNED.read_text(encoding="utf-8").replace(
            '"modelo-200-profile-new-entity-flag" = false', '"DP200012:00501" = false'
        ),
        encoding="utf-8",
    )
    with pytest.raises(RegistryValidationError, match="multiple typed channels"):
        load_pinned_conformance_inputs(load_pinned_conformance_document(colliding))
    mistyped = tmp_path / "numeric-predicate.toml"
    mistyped.write_text(
        _PINNED.read_text(encoding="utf-8").replace(
            '"modelo-200-profile-new-entity-flag" = false', '"modelo-200-profile-new-entity-flag" = 0'
        ),
        encoding="utf-8",
    )
    with pytest.raises(RegistryValidationError, match="pinned-vector contract"):
        load_pinned_conformance_document(mistyped)
