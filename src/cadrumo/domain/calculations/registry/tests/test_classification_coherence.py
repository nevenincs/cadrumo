"""Structure and wiring of the classification-coherence fold.

The fold reports disagreements between the four homes that classify a modelo as
filed, informative, or non-filing, and censuses the schema axes no TOML
exercises. These tests hold its BEHAVIOUR, deliberately not the tree's current
census: pinning today's disagreement count would turn every legitimate registry
edit into a red gate, and the count is a fact about authoring rather than about
the checker.

Two kinds of assertion carry the weight:

* Against the LIVE registry tree, invariants that hold whatever the tree says —
  every loaded modelo produces a row, a row's findings track its own axis
  disagreement exactly, and the census denominators match an independent
  traversal of the same loaded definitions.
* Against INJECTED definitions, detection power in both directions. A checker
  that reported findings for everything and one that reported them for nothing
  would each pass a one-sided test, so every finding kind is proven on a case
  built to carry it AND on a coherent case built to carry none.

The live-tree reads go through the same non-validating loader the fold uses, so
they survive a concurrently-edited registry that the validating authority would
refuse to load outright.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import BaseModel, Field, ValidationError

from .....core import TaxDomain
from .....tests.registry_tree import bundled_registry_tree
from ..classification_coherence import (
    _MAX_DETAIL_LENGTH,
    _TRUNCATION_SUFFIX,
    ClassificationCoherenceFinding,
    DeclaredAxis,
    RegistryClassificationAudit,
    _bounded_detail,
    _field_max_length,
    audit_bundled_classification_coherence,
    build_classification_coherence_audit,
)
from ..schema import (
    CasillaDefinition,
    DependencyClassificationDefinition,
    ModeloDefinition,
    ModeloRevision,
)
from ..schema_base import CalculationClass
from ..schema_input_kind import InputKind
from ..schema_references import PeriodSelector

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REFS = ("lex:art-1",)
_SOURCE_REFS = ("src-1",)

#: Injected core-constant inputs that assert nothing, so a fixture exercising one
#: contradiction never trips another by accident.
_NO_NON_REGISTRY_CODES = frozenset[str]()


def _revision(
    revision_id: str = "rev-a",
    *,
    casillas: tuple[CasillaDefinition, ...] = (),
    dependencies: tuple[DependencyClassificationDefinition, ...] = (),
) -> ModeloRevision:
    """Build the smallest revision the schema accepts, optionally carrying content."""
    return ModeloRevision(
        id=revision_id,
        localization_key=f"test.schema.revision.{revision_id}.label",
        valid_from=date(2020, 1, 1),
        period_selector=PeriodSelector(year_from=2020, periods=("0A",)),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
        casillas=casillas,
        dependency_classifications=dependencies,
    )


def _modelo(
    modelo_id: str = "130",
    *,
    calculation_class: CalculationClass = "filing",
    tax_domain: TaxDomain = TaxDomain.IRPF,
    revision: ModeloRevision | None = None,
) -> ModeloDefinition:
    """Build the smallest modelo the schema accepts, with both classification axes explicit."""
    built = revision if revision is not None else _revision()
    return ModeloDefinition(
        id=modelo_id,
        title_localization_key="test.schema.modelo.title",
        official_name_localization_key="test.schema.modelo.official_name",
        tax_domain=tax_domain,
        cadence="annual",
        jurisdiction="ES-AEAT",
        calculation_class=calculation_class,
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
        revisions={built.id: built},
    )


def _bound_casilla() -> CasillaDefinition:
    """A casilla whose input kind the informative-class invariant refuses."""
    return CasillaDefinition(
        id="c1",
        number="01",
        localization_keys=("test.schema.casilla.label",),
        section=("totales",),
        input_kind=InputKind.BOUND,
        binding="b1",
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )


def _audit(*modelos: ModeloDefinition, non_registry: frozenset[str] | None = None) -> RegistryClassificationAudit:
    """Fold injected modelos, defaulting every core-constant input to assert nothing."""
    return build_classification_coherence_audit(
        modelos,
        non_registry_modelo_codes=_NO_NON_REGISTRY_CODES if non_registry is None else non_registry,
        known_modelo_codes=frozenset(modelo.id for modelo in modelos),
        registry_validated=False,
    )


@pytest.fixture(scope="module")
def bundled_modelos() -> tuple[ModeloDefinition, ...]:
    """Every compiled modelo definition in the bundled tree.

    Read through the loader rather than by listing fragment subdirectories: a
    subdirectory-blind read of this registry has twice produced wrong
    "parse-only" verdicts.
    """
    modelos, _catalogues = bundled_registry_tree()
    return tuple(modelos)


@pytest.fixture(scope="module")
def bundled_audit() -> RegistryClassificationAudit:
    """The classification audit over the bundled registry tree."""
    return audit_bundled_classification_coherence()


def test_bundled_audit_classifies_every_loaded_modelo(
    bundled_audit: RegistryClassificationAudit,
    bundled_modelos: tuple[ModeloDefinition, ...],
) -> None:
    """Every loaded modelo gets a row, including the fully coherent ones.

    The anti-vacuity floor for the whole fold: an audit that classified nothing
    would report no findings while checking nothing, which is indistinguishable
    from a clean tree.
    """
    assert bundled_audit.checked_modelo_count > 1, "the fold must classify a real tree, not an empty one"
    assert {row.modelo for row in bundled_audit.rows} == {modelo.id for modelo in bundled_modelos}
    assert len(bundled_audit.rows) == len(bundled_modelos), "each modelo must produce exactly one row"


def test_bundled_audit_stamps_the_read_as_unvalidated(bundled_audit: RegistryClassificationAudit) -> None:
    """The bundled convenience reads through the non-validating loader and says so."""
    assert bundled_audit.registry_validated is False


def test_live_divergence_findings_track_the_axis_disagreement_exactly(
    bundled_audit: RegistryClassificationAudit,
) -> None:
    """A divergence finding exists for a live row if and only if its two axes disagree.

    Holds whether the tree currently carries many disagreements or none, so a
    registry edit that reconciles an axis pair does not red this gate. It fails
    on both a missed disagreement and a fabricated one.
    """
    reported = {finding.modelo for finding in bundled_audit.findings_of_kind("informative_axis_divergence")}
    disagreeing = {row.modelo for row in bundled_audit.rows if not row.informative_axes_agree}
    assert reported == disagreeing


def test_live_informative_modelos_carry_no_class_blockers(bundled_audit: RegistryClassificationAudit) -> None:
    """A modelo already declaring the informative class cannot carry a blocker.

    Ground truth external to this fold: the registry loaded, and registry build
    enforces the informative-class invariant on exactly those modelos. So any
    blocker computed for one is the fold's own error, which is what makes this
    a real cross-check rather than a restatement of the blocker derivation.
    """
    assert any(row.informative_by_calculation_class for row in bundled_audit.rows), (
        "no modelo in the bundled tree declares the informative class, so the loop below "
        "would pass without exercising the invariant at all"
    )
    for row in bundled_audit.rows:
        if row.informative_by_calculation_class:
            assert row.informative_class_blockers == (), (
                f"modelo {row.modelo} declares the informative class, so the invariant must accept it"
            )


def test_axis_census_reports_every_tracked_axis_once_against_a_real_population(
    bundled_audit: RegistryClassificationAudit,
    bundled_modelos: tuple[ModeloDefinition, ...],
) -> None:
    """Every tracked axis is censused exactly once, against an independently derived denominator.

    The denominators are recomputed here by a separate traversal of the same
    loaded definitions, so a census that counted the wrong population — the
    difference between a dead vocabulary member and one nothing could have
    declared — fails rather than passing silently.
    """
    tracked = set(DeclaredAxis.__args__)
    censused = [item.axis for item in bundled_audit.axis_usage]
    assert set(censused) == tracked, "every tracked axis must be censused"
    assert len(censused) == len(tracked), "no axis may be censused twice"

    revisions = tuple(revision for modelo in bundled_modelos for revision in modelo.revisions.values())
    profiles = tuple(profile for revision in revisions for profile in revision.extraction_profiles)
    manifests = tuple(revision for revision in revisions if revision.completeness_manifest)
    expected_population: dict[str, int] = {
        "calculation_class.summary": len(bundled_modelos),
        "extraction_profile.confidence.review_required": len(profiles),
        "extraction_profile.verification_source.real_aeat_corpus_pdf": len(profiles),
        "completeness_manifest.manual_extraction": len(manifests),
    }
    for item in bundled_audit.axis_usage:
        assert item.population == expected_population[item.axis], f"wrong population for {item.axis}"
        assert item.declaration_count <= item.population, f"{item.axis} declares more than its population"
        assert item.status == ("exercised" if item.declaration_count else "unused")


def test_coherent_modelos_report_no_findings() -> None:
    """A tree whose classifications all agree yields nothing.

    Half of the anti-tautology pair: a checker that reported a finding for
    everything would still satisfy every positive-detection test below.
    """
    audit = _audit(
        _modelo("100", calculation_class="filing", tax_domain=TaxDomain.IRPF),
        _modelo("347", calculation_class="informative", tax_domain=TaxDomain.INFORMATIVE),
    )
    assert audit.findings == ()
    assert audit.ok is True
    assert audit.checked_modelo_count == 2
    assert all(row.informative_axes_agree for row in audit.rows)


@pytest.mark.parametrize(
    ("calculation_class", "tax_domain"),
    [
        ("informative", TaxDomain.IRPF),
        ("filing", TaxDomain.INFORMATIVE),
    ],
)
def test_divergent_modelo_reports_exactly_one_divergence_finding(
    calculation_class: CalculationClass,
    tax_domain: TaxDomain,
) -> None:
    """Either one-sided informative declaration is reported, in both directions.

    The other half of the anti-tautology pair: a checker that reported nothing
    would satisfy the coherent-case test above.
    """
    audit = _audit(_modelo("130", calculation_class=calculation_class, tax_domain=tax_domain))
    findings = audit.findings_of_kind("informative_axis_divergence")
    assert len(findings) == 1
    assert findings[0].modelo == "130"
    assert audit.ok is False
    assert audit.rows[0].informative_axes_agree is False


def test_forced_divergence_names_the_invariant_blocker() -> None:
    """A divergence the enforcement invariant forces is distinguished from unexplained drift.

    A modelo declaring the informative tax domain while carrying a bound casilla
    CANNOT take the informative calculation class: registry build would refuse
    it. The finding must still be reported, but annotated as forced, so a reader
    does not mechanically reclassify it and break the tree.
    """
    blocked = _modelo(
        "349",
        calculation_class="filing",
        tax_domain=TaxDomain.INFORMATIVE,
        revision=_revision(casillas=(_bound_casilla(),)),
    )
    unexplained = _modelo("038", calculation_class="filing", tax_domain=TaxDomain.INFORMATIVE)

    blocked_row = _audit(blocked).rows[0]
    assert blocked_row.informative_class_blockers != ()
    assert blocked_row.informative_class_available is False

    unexplained_row = _audit(unexplained).rows[0]
    assert unexplained_row.informative_class_blockers == ()
    assert unexplained_row.informative_class_available is True

    blocked_detail = _audit(blocked).findings_of_kind("informative_axis_divergence")[0].detail
    unexplained_detail = _audit(unexplained).findings_of_kind("informative_axis_divergence")[0].detail
    assert blocked_detail != unexplained_detail, "a forced divergence must not read like an unexplained one"


def test_non_registry_modelo_defined_in_tree_is_reported() -> None:
    """A modelo declared to have no registry definition, yet compiled, is a contradiction."""
    audit = _audit(_modelo("037"), non_registry=frozenset({"037"}))
    findings = audit.findings_of_kind("non_registry_modelo_defined_in_tree")
    assert len(findings) == 1
    assert findings[0].modelo == "037"
    assert audit.rows[0].declared_non_registry is True


def test_registry_modelo_absent_from_the_identifier_enum_is_reported() -> None:
    """A tree modelo no core identifier names is unreachable through the typed surface."""
    audit = build_classification_coherence_audit(
        (_modelo("999"),),
        non_registry_modelo_codes=_NO_NON_REGISTRY_CODES,
        known_modelo_codes=frozenset({"130"}),
        registry_validated=False,
    )
    findings = audit.findings_of_kind("registry_modelo_absent_from_modelo_enum")
    assert len(findings) == 1
    assert findings[0].modelo == "999"
    assert audit.rows[0].known_modelo_code is False


def test_dependency_conditional_on_activity_without_filing_is_reported() -> None:
    """Conditioning on economic activity is meaningless where the taxpayer never files the source."""
    incoherent = DependencyClassificationDefinition(
        id="dep-incoherent",
        source_modelo="111",
        treatment="factual_evidence",
        taxpayer_files_source=False,
        conditional_on_economic_activity=True,
        target_constructs=("k1",),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )
    coherent = DependencyClassificationDefinition(
        id="dep-coherent",
        source_modelo="130",
        treatment="factual_evidence",
        taxpayer_files_source=True,
        conditional_on_economic_activity=True,
        target_constructs=("k1",),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )
    audit = _audit(_modelo("100", revision=_revision(dependencies=(incoherent, coherent))))
    findings = audit.findings_of_kind("dependency_conditional_activity_without_filing")
    assert len(findings) == 1, "only the pair that cannot both hold is reported"
    assert findings[0].subject == "dep-incoherent"


def test_builder_returns_findings_instead_of_raising_on_a_fully_incoherent_modelo() -> None:
    """Every contradiction at once is reported, not raised.

    The fold is a governance read over a tree it does not own: a disagreement
    is the output, so refusing to return one would make the tool unable to
    describe the very state it exists to surface.
    """
    dependency = DependencyClassificationDefinition(
        id="dep-incoherent",
        source_modelo="111",
        treatment="factual_evidence",
        taxpayer_files_source=False,
        conditional_on_economic_activity=True,
        target_constructs=("k1",),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )
    audit = build_classification_coherence_audit(
        (
            _modelo(
                "999",
                calculation_class="informative",
                tax_domain=TaxDomain.IRPF,
                revision=_revision(dependencies=(dependency,)),
            ),
        ),
        non_registry_modelo_codes=frozenset({"999"}),
        known_modelo_codes=frozenset({"130"}),
        registry_validated=False,
    )
    assert {finding.kind for finding in audit.findings} == {
        "informative_axis_divergence",
        "non_registry_modelo_defined_in_tree",
        "registry_modelo_absent_from_modelo_enum",
        "dependency_conditional_activity_without_filing",
    }
    assert audit.ok is False


def test_axis_census_flips_to_exercised_when_the_tree_declares_the_axis() -> None:
    """A censused axis reports what the tree actually says, in both directions.

    Proves the census reads the tree rather than restating a hardcoded verdict:
    the same axis is unused for a tree that omits it and exercised for one that
    declares it. Without this, a census that always answered "unused" would
    match today's registry perfectly and be worthless.
    """
    axis = "calculation_class.summary"

    silent = {item.axis: item for item in _audit(_modelo("130")).axis_usage}[axis]
    assert silent.declaration_count == 0
    assert silent.status == "unused"
    assert axis in _audit(_modelo("130")).unused_axes

    declaring_audit = _audit(_modelo("390", calculation_class="summary", tax_domain=TaxDomain.IVA))
    declaring = {item.axis: item for item in declaring_audit.axis_usage}[axis]
    assert declaring.declaration_count == 1
    assert declaring.status == "exercised"
    assert axis not in declaring_audit.unused_axes


def test_declared_axis_census_is_excluded_from_the_coherence_verdict() -> None:
    """Unused axes never flip ``ok``.

    They exist in the tree today by design, so folding them into the verdict
    would pin it to :data:`False` permanently and destroy its value as a signal.
    """
    audit = _audit(_modelo("130"))
    assert audit.unused_axes != (), "the injected tree exercises no tracked axis"
    assert audit.findings == ()
    assert audit.ok is True


def test_a_modelo_with_many_blockers_is_reported_rather_than_refused() -> None:
    """A heavily blocked divergence must not overflow the finding's own bound.

    The invariant produces one blocker per offending casilla, so rendering them
    all into the finding's prose would exceed its length constraint and raise
    while CONSTRUCTING the report — aborting the whole governance read on
    exactly the disagreement it exists to surface. The complete list stays on
    the row; the sentence carries a sample and a count.
    """
    casillas = tuple(
        CasillaDefinition(
            id=f"c{index}",
            number=f"{index:02d}",
            localization_keys=("test.schema.casilla.label",),
            section=("totales",),
            input_kind=InputKind.BOUND,
            binding=f"b{index}",
            legal_refs=_LEGAL_REFS,
            source_refs=_SOURCE_REFS,
        )
        for index in range(40)
    )
    audit = _audit(
        _modelo(
            "100",
            calculation_class="filing",
            tax_domain=TaxDomain.INFORMATIVE,
            revision=_revision(casillas=casillas),
        ),
    )
    finding = audit.findings_of_kind("informative_axis_divergence")[0]
    assert _MAX_DETAIL_LENGTH is not None
    assert len(finding.detail) <= _MAX_DETAIL_LENGTH
    assert "further blocker" in finding.detail, "the unrendered blockers must still be counted"
    assert len(audit.rows[0].informative_class_blockers) == len(casillas), (
        "the row keeps every blocker even though the sentence samples them"
    )


def test_the_detail_bound_is_read_from_the_field_it_must_satisfy() -> None:
    """The clamp's bound IS the field's constraint, not a copy of its number.

    A hand-copied literal beside the field it mirrors is only correct until
    someone edits one of the two. Reading the constraint makes the pair
    inseparable: lowering the field bound lowers the clamp in the same edit.
    """
    assert _field_max_length(ClassificationCoherenceFinding, "detail") == _MAX_DETAIL_LENGTH
    assert _MAX_DETAIL_LENGTH is not None, "the finding's detail must stay bounded, or the clamp means nothing"

    over_bound = "x" * (_MAX_DETAIL_LENGTH + 1)
    with pytest.raises(ValidationError):
        ClassificationCoherenceFinding(
            kind="informative_axis_divergence",
            modelo="130",
            subject="130",
            detail=over_bound,
            registry_validated=False,
        )


def test_the_bound_reader_reads_the_declared_constraint() -> None:
    """The reader reports what a field declares, in both the bounded and unbounded cases.

    Without this, a reader that always returned the finding's own 512 would
    satisfy the binding assertion above while reading nothing at all.
    """

    class _NarrowlyBounded(BaseModel):
        text: str = Field(min_length=1, max_length=40)

    class _Unbounded(BaseModel):
        text: str

    assert _field_max_length(_NarrowlyBounded, "text") == 40
    assert _field_max_length(_Unbounded, "text") is None


def test_a_detail_over_the_bound_is_truncated_to_exactly_the_bound() -> None:
    """The truncation branch itself, exercised rather than reasoned about.

    The fold's own worst case sits inside the bound (see the headroom test
    below), so nothing else in this module reaches this branch. Driving it
    directly is what turns the clamp from assumed-correct into proven-correct.
    """
    assert _MAX_DETAIL_LENGTH is not None

    at_bound = "y" * _MAX_DETAIL_LENGTH
    assert _bounded_detail(at_bound) == at_bound, "a detail exactly at the bound must pass through untouched"

    over_bound = "y" * (_MAX_DETAIL_LENGTH + 50)
    clamped = _bounded_detail(over_bound)
    assert len(clamped) == _MAX_DETAIL_LENGTH
    assert clamped.endswith(_TRUNCATION_SUFFIX)
    assert clamped.startswith(over_bound[: _MAX_DETAIL_LENGTH - len(_TRUNCATION_SUFFIX)])


def test_lowering_the_bound_moves_the_clamp() -> None:
    """The clamp cuts where the bound says, not where a remembered number said.

    The assertion the hand-copied literal could never fail: with the number
    duplicated, lowering the field constraint left the clamp cutting at the old
    length and nothing anywhere flipped.
    """
    detail = "z" * 200

    assert _bounded_detail(detail, max_length=100) != _bounded_detail(detail, max_length=150)
    assert len(_bounded_detail(detail, max_length=100)) == 100
    assert len(_bounded_detail(detail, max_length=150)) == 150
    assert _bounded_detail(detail, max_length=None) == detail, "an unbounded field needs no clamp"


def test_the_clamp_is_what_keeps_an_oversized_detail_constructible() -> None:
    """Remove the clamp and the finding refuses to construct; keep it and it validates.

    The load-bearing proof. The fold is a governance read over a tree it does not
    own, so a finding that raises while being CONSTRUCTED aborts the whole read
    on exactly the disagreement it exists to surface.
    """
    assert _MAX_DETAIL_LENGTH is not None
    oversized = "modelo 100 declares " + "w" * _MAX_DETAIL_LENGTH

    with pytest.raises(ValidationError):
        ClassificationCoherenceFinding(
            kind="informative_axis_divergence",
            modelo="100",
            subject="100",
            detail=oversized,
            registry_validated=False,
        )

    survived = ClassificationCoherenceFinding(
        kind="informative_axis_divergence",
        modelo="100",
        subject="100",
        detail=_bounded_detail(oversized),
        registry_validated=False,
    )
    assert len(survived.detail) == _MAX_DETAIL_LENGTH
    assert survived.detail.endswith(_TRUNCATION_SUFFIX)


def test_the_worst_case_the_registry_schema_permits_needs_no_truncation() -> None:
    """The sampler leaves real headroom under the bound, and this measures it.

    Built from ids at their schema maxima — a 128-character revision id and a
    64-character casilla id — so it is the longest divergence sentence legal
    registry data can produce. It must not be truncated: a truncated finding has
    silently dropped the prose a reader needs. If a widened id bound or a longer
    sentence template eats the margin, the clamp starts firing on real data and
    this flips, which is the early warning the clamp itself cannot give.
    """
    revision_id = "r" + "x" * 126 + "z"
    casilla_id = "c" + "x" * 62 + "z"
    assert len(revision_id) == 128, "the revision id must sit at its schema maximum"
    assert len(casilla_id) == 64, "the casilla id must sit at its schema maximum"

    widest = CasillaDefinition(
        id=casilla_id,
        number="01",
        localization_keys=("test.schema.casilla.label",),
        section=("totales",),
        input_kind=InputKind.BOUND,
        binding="b1",
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )
    second = widest.model_copy(update={"id": "d" + "x" * 62 + "z", "number": "02", "binding": "b2"})
    audit = _audit(
        _modelo(
            "100",
            calculation_class="filing",
            tax_domain=TaxDomain.INFORMATIVE,
            revision=_revision(revision_id, casillas=(widest, second)),
        ),
    )

    detail = audit.findings_of_kind("informative_axis_divergence")[0].detail
    assert _MAX_DETAIL_LENGTH is not None
    assert not detail.endswith(_TRUNCATION_SUFFIX), (
        f"the widest legal divergence sentence is being truncated at {len(detail)} characters; "
        "the sampler no longer keeps real findings inside the field bound"
    )
    assert len(detail) < _MAX_DETAIL_LENGTH


def test_degraded_read_stamps_every_row_and_finding_unvalidated() -> None:
    """A non-validating read stamps both the row and each finding as unvalidated.

    The label rides every emitted artefact, not only the enclosing audit, so a
    consumer iterating rows or flattening findings can still distinguish a
    degraded read from a validated one.
    """
    audit = _audit(
        _modelo("130", calculation_class="informative", tax_domain=TaxDomain.IRPF),
    )
    assert audit.registry_validated is False
    assert len(audit.rows) == 1
    assert audit.rows[0].registry_validated is False
    assert len(audit.findings) == 1, "the divergent modelo must produce a finding"
    assert all(finding.registry_validated is False for finding in audit.findings)
    assert all(finding.registry_validated is False for finding in audit.rows[0].findings)


def test_validated_read_stamps_every_row_and_finding_validated() -> None:
    """A validated-authority read stamps both the row and each finding as validated.

    The other half of the anti-tautology pair: a stamper that always wrote
    False would satisfy the degraded test above.
    """
    audit = build_classification_coherence_audit(
        (_modelo("130", calculation_class="informative", tax_domain=TaxDomain.IRPF),),
        non_registry_modelo_codes=_NO_NON_REGISTRY_CODES,
        known_modelo_codes=frozenset({"130"}),
        registry_validated=True,
    )
    assert audit.registry_validated is True
    assert audit.rows[0].registry_validated is True
    assert len(audit.findings) == 1, "the divergent modelo must produce a finding"
    assert all(finding.registry_validated is True for finding in audit.findings)


def test_flattened_findings_preserve_the_validated_label() -> None:
    """The label is not lost when findings are extracted through the container's property.

    A degraded audit and a validated audit over the same content produce
    findings that carry different labels; flattening via ``audit.findings``
    must preserve, not erase, the per-finding stamp.
    """
    divergent = _modelo("130", calculation_class="informative", tax_domain=TaxDomain.IRPF)

    degraded = _audit(divergent)
    validated = build_classification_coherence_audit(
        (divergent,),
        non_registry_modelo_codes=_NO_NON_REGISTRY_CODES,
        known_modelo_codes=frozenset({"130"}),
        registry_validated=True,
    )

    degraded_findings = degraded.findings
    validated_findings = validated.findings
    assert len(degraded_findings) == 1
    assert len(validated_findings) == 1
    assert degraded_findings[0].registry_validated is False
    assert validated_findings[0].registry_validated is True
    assert degraded_findings[0].registry_validated is not validated_findings[0].registry_validated, (
        "the two reads over identical content must produce findings with opposite labels"
    )
