"""The fichero-BOE export exemption must be declared, never left to absence.

The completeness gate demands a value on disk for every manifest casilla that is
a calculation RESULT or is schema-required, intersected with the casillas the
official record addresses. A casilla outside that intersection is exempt — and
that exemption used to be expressed by ABSENCE alone, which reads identically
whether the casilla genuinely files no slot or was simply never annotated. The
second case is a silent under-declaration.

These tests pin the closure of that hole. They run against the BUNDLED registry
rather than a hand-built fixture, because the property under test is about the
shipped corpus: a synthetic revision could satisfy every assertion here while the
real tree carried an undeclared exemption.

Every assertion is paired with a mutation that must red it. A gate whose test
still passes with the mechanism removed asserts nothing, and this gate's whole
subject is a defect that hides by looking like nothing.
"""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from .....core import ExportExemptionReason, ExportLayoutFormat, RegistryAuthorityGrade
from .._snapshot_internals import _check_snapshot_filing_capability
from .._validate_export_exemption import (
    modelo_publishes_a_record_design,
    validate_export_exemption_declarations,
)
from ..authority import ValidatedRegistryAuthority
from ..schema import ModeloRevision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _gate(
    revision: ModeloRevision,
    modelo_id: str = "303",
    *,
    publishes_record_design: bool = True,
) -> list[str]:
    """Run the export-exemption gate over one revision and return its failures.

    ``publishes_record_design`` defaults to ``True`` because every revision these
    tests exercise belongs to a modelo AEAT publishes a design for; that is the
    population the per-casilla exemption rules govern.
    """
    return validate_export_exemption_declarations(
        prefix="modelo T revision R",
        modelo_id=modelo_id,
        revision=revision,
        publishes_record_design=publishes_record_design,
    )


def _fixed_width_revisions(
    authority: ValidatedRegistryAuthority,
) -> list[tuple[str, str, ModeloRevision]]:
    """Return every bundled revision declaring a fixed-width export layout."""
    found: list[tuple[str, str, ModeloRevision]] = []
    for modelo in authority.modelos:
        for revision_id, revision in modelo.revisions.items():
            if any(layout.format is ExportLayoutFormat.FIXED_WIDTH for layout in revision.export_layouts):
                found.append((modelo.id, revision_id, revision))
    return found


def _replace_casilla(revision: ModeloRevision, casilla_id: str, **updates: object) -> ModeloRevision:
    """Return ``revision`` with one casilla's fields overridden.

    Uses ``model_copy`` on the real loaded objects rather than a stub, so the
    mutation exercises the production validator against production data.
    """
    casillas = tuple(
        casilla.model_copy(update=updates) if casilla.id == casilla_id else casilla for casilla in revision.casillas
    )
    return revision.model_copy(update={"casillas": casillas})


def test_bundled_registry_declares_every_load_bearing_export_exemption(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """No bundled fixed-width revision leaves a load-bearing exemption undeclared.

    This is the shipped-corpus invariant. It is not a tautology over the gate: a
    casilla whose reason is missing produces a failure here, which is exactly what
    the pre-annotation tree did for eighteen casillas across eight revisions.
    """
    offenders: list[str] = []
    for modelo_id, _revision_id, revision in _fixed_width_revisions(registry_authority):
        offenders.extend(_gate(revision, modelo_id))
    assert offenders == []


def test_removing_a_declared_reason_reds_the_gate(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """MUTATION: strip a real declared reason and the gate must refuse.

    Proves the clean result above is produced BY the annotations rather than by a
    gate that never fires. Runs over every bundled casilla that actually carries a
    reason, so the proof covers the whole annotated set, not one specimen.
    """
    checked = 0
    for modelo_id, _revision_id, revision in _fixed_width_revisions(registry_authority):
        for casilla in revision.casillas:
            if casilla.export_exemption_reason is None:
                continue
            stripped = _replace_casilla(revision, casilla.id, export_exemption_reason=None)
            if any(repr(casilla.id) in failure for failure in _gate(stripped, modelo_id)):
                checked += 1
                continue
            # The gate does not govern every casilla that carries a reason: it
            # skips one already addressed by a record, one marked internal_only,
            # and one that is neither formula-bearing nor required, and it only
            # ever walks completeness-manifest entries. Nine bundled casillas sit
            # outside it -- modelo 184's `decl.persona-relacion`, absent from its
            # manifest, and eight modelo 353 bound casillas that are in the
            # manifest but neither required nor computed. Their reason is
            # documentation rather than an exemption the gate relies on.
            #
            # Rather than re-deriving that predicate here, where it would drift
            # from the gate, each such casilla proves its own case: the gate must
            # be silent about it WITH the reason too. A casilla the gate really
            # governs cannot satisfy this, because the gate would name it.
            assert not any(repr(casilla.id) in failure for failure in _gate(revision, modelo_id)), (
                f"stripping the reason from {casilla.id!r} did not red the gate, yet the gate does "
                f"name it when the reason is present -- so the reason IS load-bearing and the "
                f"mutation should have been detected"
            )
    assert checked > 0, "no bundled casilla declares a reason the gate relies on; the mutation proved nothing"


def test_a_forgotten_annotation_is_detected(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """POSITIVE CONTROL: plant a genuinely forgotten annotation and find it.

    The adjudication behind this feature concluded that the bundled tree contains
    zero forgotten annotations. A clean negative is worth nothing without a
    demonstration that the method WOULD find one, so this plants the real defect
    shape: a formula-bearing manifest casilla the record no longer addresses,
    carrying no reason — precisely what a casilla that should reach a box but was
    never given an export field looks like.

    The control covers scope rather than a single specimen: it plants the defect
    independently in every bundled fixed-width revision that has a candidate.
    """
    planted = 0
    for modelo_id, _revision_id, revision in _fixed_width_revisions(registry_authority):
        manifest = revision.completeness_manifest
        if manifest is None:
            continue
        manifest_ids = {entry.casilla_id for entry in manifest.casillas}
        candidate = next(
            (
                casilla
                for casilla in revision.casillas
                if casilla.id in manifest_ids
                and casilla.formula is not None
                and casilla.export_refs
                and not casilla.internal_only
            ),
            None,
        )
        if candidate is None:
            continue
        # Drop every export field addressing the candidate: the layout stops
        # carrying it while nothing declares why. Baseline first, so a revision
        # that was already red cannot masquerade as a detection.
        assert _gate(revision, modelo_id) == []
        layouts = tuple(
            layout.model_copy(
                update={
                    "records": tuple(
                        record.model_copy(
                            update={
                                "fields": tuple(field for field in record.fields if field.casilla_id != candidate.id),
                                "row_field_casilla_ids": {
                                    row_field: casilla_id
                                    for row_field, casilla_id in record.row_field_casilla_ids.items()
                                    if casilla_id != candidate.id
                                },
                            },
                        )
                        for record in layout.records
                    ),
                },
            )
            for layout in revision.export_layouts
        )
        wounded = revision.model_copy(update={"export_layouts": layouts})
        failures = _gate(wounded, modelo_id)
        assert any(repr(candidate.id) in failure for failure in failures), (
            f"planted forgotten annotation on {candidate.id!r} went undetected"
        )
        planted += 1
    assert planted > 0, "no revision offered a plantable candidate; the control proved nothing"


def test_feeds_addressed_casilla_claim_is_verified_not_trusted(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """MUTATION: the one reason asserting the figure IS filed must be checked."""
    relabelled = 0
    for modelo_id, _revision_id, revision in _fixed_width_revisions(registry_authority):
        for casilla in revision.casillas:
            if casilla.export_exemption_reason is not ExportExemptionReason.NOT_IN_RECORD_DESIGN:
                continue
            mutated = _replace_casilla(
                revision,
                casilla.id,
                export_exemption_reason=ExportExemptionReason.FEEDS_ADDRESSED_CASILLA,
            )
            failures = _gate(mutated, modelo_id)
            if any(repr(casilla.id) in failure and "Either wire the chain" in failure for failure in failures):
                relabelled += 1
                continue
            # Same population boundary as the stripping mutation above: a casilla
            # the gate does not govern cannot be caught lying about feeding an
            # addressed casilla, because the gate never examines its claim. Each
            # one proves that for itself rather than trusting a re-derived
            # predicate -- the gate must be silent about it unmutated too.
            assert not any(repr(casilla.id) in failure for failure in _gate(revision, modelo_id)), (
                f"{casilla.id!r} claims to feed an addressed casilla and the gate believed it, "
                f"yet the gate does examine this casilla when unmutated"
            )
    assert relabelled > 0, (
        "no governed NOT_IN_RECORD_DESIGN casilla was available to re-label; the mutation proved nothing"
    )


def test_feeds_addressed_casilla_is_wired_into_compiled_authority(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The retained member hydrates real M303 declarations; it is not dormant."""
    users = {
        (modelo.id, revision_id, casilla.id)
        for modelo in registry_authority.modelos
        for revision_id, revision in modelo.revisions.items()
        for casilla in revision.casillas
        if casilla.export_exemption_reason is ExportExemptionReason.FEEDS_ADDRESSED_CASILLA
    }

    assert len(users) == 17
    assert {modelo_id for modelo_id, _revision_id, _casilla_id in users} == {"303"}
    assert {revision_id for _modelo_id, revision_id, _casilla_id in users} == {
        "2022",
        "2023",
        "2024-desde-09-y-3t",
        "2024-hasta-08-y-2t",
        "2025",
        "2026-y-siguientes",
    }


def _revalidate(casilla: object, **updates: object) -> object:
    """Re-run strict schema validation over a real casilla with fields overridden.

    ``model_copy`` deliberately skips validation, so a contradiction test must
    round-trip through ``model_validate`` to exercise the model validator.
    """
    from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

    payload = dict(casilla.__dict__)
    payload.update(updates)
    return CasillaDefinition.model_validate(payload)


def test_a_casilla_the_record_addresses_may_not_declare_an_exemption(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """A reason contradicting an export_refs declaration is refused at schema level.

    Built from a REAL bundled casilla so the contradiction is the only thing under
    test; a hand-rolled fixture could fail validation for an unrelated reason and
    read as a pass.
    """
    exported = next(
        casilla
        for _modelo_id, _revision_id, revision in _fixed_width_revisions(registry_authority)
        for casilla in revision.casillas
        if casilla.export_refs and not casilla.internal_only
    )
    # Control: the untouched casilla revalidates cleanly, so the refusal below is
    # caused by the contradiction and not by the round-trip itself.
    _revalidate(exported)
    # pydantic wraps the model validator's RegistryValidationError.
    with pytest.raises(ValidationError, match="not exempt"):
        _revalidate(exported, export_exemption_reason=ExportExemptionReason.NOT_IN_RECORD_DESIGN)


def test_an_internal_only_casilla_may_not_also_declare_a_reason(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """``internal_only`` already asserts its exemption, so a second one is refused.

    Two mechanisms saying the same thing is how a divergence starts: a later
    author could set them inconsistently and neither would be authoritative.
    """
    internal = next(
        casilla
        for modelo in registry_authority.modelos
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
        if casilla.internal_only
    )
    _revalidate(internal)
    with pytest.raises(ValidationError, match="already asserts"):
        _revalidate(internal, export_exemption_reason=ExportExemptionReason.INTERNAL_INTERMEDIATE)


def test_an_unknown_reason_token_is_refused_at_the_loader_boundary() -> None:
    """An unrecognised TOML token refuses at hydration, naming the accepted set."""
    from .._schema_export_exemption import _coerce_export_exemption_reason
    from ..errors import RegistryValidationError

    assert _coerce_export_exemption_reason("not_in_record_design") is ExportExemptionReason.NOT_IN_RECORD_DESIGN
    with pytest.raises(RegistryValidationError, match="not a recognised ExportExemptionReason"):
        _coerce_export_exemption_reason("probably_fine")


def test_pre_populated_by_aeat_is_documented_dormant_not_silently_unused(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """``PRE_POPULATED_BY_AEAT`` has no bundled user, and this pins WHY.

    The member exists for the Modelo 100 casilla 0599 case, where AEAT fills the
    box from third-party Modelo 190 data the application does not hold. It has no
    user because this gate binds the fixed-width transport only, and Modelo 100
    exports ``xml_dictionary`` — an absent element there is legitimately absent,
    so there is no blank-slot hazard to be exempt from.

    Pinning the reason keeps the member honestly dormant rather than silently so:
    the day Modelo 100 gains a fixed-width layout, this test reds and forces the
    question to be answered rather than rediscovered.
    """
    users = [
        casilla.id
        for modelo in registry_authority.modelos
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
        if casilla.export_exemption_reason is ExportExemptionReason.PRE_POPULATED_BY_AEAT
    ]
    assert users == []
    modelo_100 = registry_authority.modelo("100")
    formats = {layout.format for revision in modelo_100.revisions.values() for layout in revision.export_layouts}
    assert ExportLayoutFormat.FIXED_WIDTH not in formats


def test_the_no_layout_refusal_fires_when_a_design_exists_to_author_from() -> None:
    """A layout-less revision of a modelo AEAT publishes a design for is refused."""
    modelo, _ = _committed_modelo("180")
    revision = modelo.revisions["2023-y-siguientes"]
    stripped = revision.model_copy(update={"export_layouts": ()})

    failures = _gate(stripped, modelo_id="180", publishes_record_design=True)

    assert any("declares no export layout" in failure for failure in failures)


def test_the_no_layout_refusal_is_silent_when_aeat_publishes_no_design() -> None:
    """The same layout-less revision passes once no design exists to author from.

    Paired with the test above on the SAME revision object, so the only thing
    that differs is the predicate. That is what makes this a discrimination
    proof rather than two independent assertions.
    """
    modelo, _ = _committed_modelo("180")
    revision = modelo.revisions["2023-y-siguientes"]
    stripped = revision.model_copy(update={"export_layouts": ()})

    failures = _gate(stripped, modelo_id="180", publishes_record_design=False)

    assert not any("declares no export layout" in failure for failure in failures)


@pytest.mark.parametrize("modelo_id", ["180", "303", "131"])
def test_a_modelo_with_a_bundled_design_reads_as_publishing_one(modelo_id: str) -> None:
    """The predicate resolves True against the real bundled source catalogue."""
    modelo, catalogues = _committed_modelo(modelo_id)

    assert modelo_publishes_a_record_design(modelo, catalogues.sources)


@pytest.mark.parametrize("modelo_id", ["136", "721"])
def test_a_modelo_aeat_publishes_no_design_for_reads_as_publishing_none(modelo_id: str) -> None:
    """Modelo 136 and 721 cite no ``record_design``, only procedure and form_spec sources.

    Both are absent from every AEAT Diseño de Registro index page, current and
    historical, and both are kept in the registry because they carry real
    calculation machinery. They are the entire population this predicate
    separates.
    """
    modelo, catalogues = _committed_modelo(modelo_id)

    assert not modelo_publishes_a_record_design(modelo, catalogues.sources)


def test_a_form_spec_citation_is_not_a_record_design() -> None:
    """Mutation proof: the predicate keys on ``record_design``, not on tier or name.

    Modelo 721 cites its approving orden's anexo at ``layout_authority`` tier
    under an id ending ``-layout``. If the predicate keyed on either signal it
    would read True here, the refusal would return for 721, and the distinction
    this gate rests on would be fictional.

    Read over the modelo AND its revisions, exactly as the predicate does. The
    citation lives at whichever level the registry happens to declare it -- the
    721 revision split moved it from the modelo down to each revision -- so a
    modelo-only read proves nothing about the predicate it mirrors.
    """
    modelo, catalogues = _committed_modelo("721")
    refs = set(modelo.source_refs)
    for revision in modelo.revisions.values():
        refs |= set(revision.source_refs)
    cited = {ref: catalogues.sources[ref] for ref in refs if ref in catalogues.sources}

    assert cited, "fixture drift: modelo 721 should cite resolvable sources"
    assert any(source.evidence_tier == "layout_authority" for source in cited.values())
    assert not any(source.kind == "record_design" for source in cited.values())


def test_an_acquisition_gap_is_not_excused_by_the_design_predicate() -> None:
    """A revision citing no design, in a modelo that HAS one, is still refused.

    Modelo 185 is the worked case: its 2026 design is bundled while the
    ``2003-2025`` revision cites none. Scoping the design predicate per revision
    instead of per modelo excused that gap -- an ACQUISITION gap, the exact shape
    the refusal exists to surface.

    Asserted at FILING grade deliberately. Modelo 185 declares only applicability
    on the real tree, so the grade scoping excuses it there and would make this
    pass for the wrong reason; re-declaring the grade isolates the design
    predicate, which is what this test is about.
    """
    modelo, catalogues = _committed_modelo("185")
    revision = _at_grade(modelo.revisions["2003-2025"], RegistryAuthorityGrade.FILING)

    assert not any(
        catalogues.sources[ref].kind == "record_design" for ref in revision.source_refs if ref in catalogues.sources
    )
    assert modelo_publishes_a_record_design(modelo, catalogues.sources)
    assert any("declares no export layout" in failure for failure in _gate(revision, modelo_id="185"))


def _at_grade(revision: ModeloRevision, grade: RegistryAuthorityGrade) -> ModeloRevision:
    """Return ``revision`` re-declared at ``grade``, on the real loaded object."""
    return revision.model_copy(update={"authority_grade": grade})


def test_the_no_layout_refusal_fires_on_a_revision_claiming_filing_grade() -> None:
    """A filing-grade revision with a design and no layout is refused."""
    modelo, _ = _committed_modelo("180")
    stripped = _at_grade(
        modelo.revisions["2023-y-siguientes"].model_copy(update={"export_layouts": ()}),
        RegistryAuthorityGrade.FILING,
    )

    assert any("declares no export layout" in failure for failure in _gate(stripped, modelo_id="180"))


def test_the_no_layout_refusal_is_silent_on_a_revision_claiming_only_applicability() -> None:
    """The same layout-less revision passes once it claims scheduling reach only.

    Paired with the test above on the SAME revision, so the only thing that
    differs is the declared grade. An applicability-grade revision asserts it can
    say when the modelo is due and to whom it applies -- it makes no export claim,
    so there is no export claim to refuse.
    """
    modelo, _ = _committed_modelo("180")
    stripped = _at_grade(
        modelo.revisions["2023-y-siguientes"].model_copy(update={"export_layouts": ()}),
        RegistryAuthorityGrade.APPLICABILITY,
    )

    assert not any("declares no export layout" in failure for failure in _gate(stripped, modelo_id="180"))


def test_modelo_182_is_applicability_grade_and_is_not_asked_for_a_layout() -> None:
    """Modelo 182 is the worked case for scoping on grade, read off the real tree.

    Its revision records that the donativos declaration is filed by the entity
    RECEIVING the donation, so this application's taxpayer is the declaration's
    subject rather than its filer. A bundled record design exists, so the design
    predicate alone would still demand a layout; the grade is what correctly
    excuses it.
    """
    modelo, catalogues = _committed_modelo("182")
    revision = modelo.revisions["2025"]

    assert revision.effective_authority_grade is RegistryAuthorityGrade.APPLICABILITY
    assert modelo_publishes_a_record_design(modelo, catalogues.sources)
    assert not revision.export_layouts
    assert not any("declares no export layout" in failure for failure in _gate(revision, modelo_id="182"))


def test_the_runtime_filing_gate_is_not_scoped_by_grade() -> None:
    """The build-time scoping cannot become a mute button, and this is why.

    ``_check_snapshot_filing_capability`` refuses a filing-grade snapshot from any
    revision declaring no export layout, and it consults no authority grade of its
    own. Whatever a revision declares at build time, the capability still cannot be
    exercised. If this ever stops holding, the build-time scoping above becomes a
    real hole and must be reconsidered.
    """
    source = inspect.getsource(_check_snapshot_filing_capability)

    assert "RegistryAuthorityGrade" not in source
    assert "authority_grade" not in source
