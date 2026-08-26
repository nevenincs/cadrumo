"""Coherence of the filed / informative / non-filing partition, and the dead-axis census.

Whether a modelo is a self-assessment the taxpayer settles, an informative
declaration carrying no liquidación, or something the registry deliberately does
not model at all, is decided today in four places that do not have to agree:

* :attr:`ModeloDefinition.calculation_class` — an ENFORCEMENT posture. Declaring
  ``informative`` binds the modelo to
  :func:`~cadrumo.domain.calculations.registry.validate_revision_rules.validate_informative_class_invariant`,
  which refuses formulas, cross-model relations, and any casilla outside
  ``{informational, manual}``. It is therefore not a free label: a modelo that is
  informative in the AEAT sense but computes bound totals cannot carry the value
  without failing registry build.
* :attr:`ModeloDefinition.tax_domain` — a TAXONOMY label.
  :attr:`~cadrumo.core.TaxDomain.INFORMATIVE` groups a modelo into the
  informative family and carries no invariant whatsoever.
* The core modelo constants (:data:`~cadrumo.core.NON_REGISTRY_MODELOS` and the
  obligation-scope mappings behind it) — which codes intentionally have no
  registry definition at all.
* :class:`~cadrumo.domain.calculations.registry.DependencyClassificationDefinition`'s
  ``taxpayer_files_source`` and ``conditional_on_economic_activity`` — per
  cross-period dependency, who files the source and under what condition.

Because one axis carries an enforced invariant and another carries none, a
divergence between them is a SIGNAL, not automatically a defect. This module
therefore reports and never canonicalizes: it emits the disagreement together
with the answer to "would the enforcement invariant even permit the other
value?", so a reader can tell an unexplained drift from a divergence the
registry forces. Nothing here raises on a disagreement, and nothing here
rewrites one — adjudicating which axis is right for a given modelo is a
domain-authority question about Spanish tax law, not a fact about the tree.

Declared-but-dead axes
----------------------

A conformance report must show a schema surface that no TOML exercises as
UNUSED, never as passing: a vocabulary member with zero declarations produces
zero failures, which is indistinguishable from a member that is declared
everywhere and always correct. :attr:`RegistryClassificationAudit.axis_usage`
carries one row per tracked axis, always — exercised or not — each with the
population of candidate declaration sites behind it, because "0 of 43 extraction
profiles" and "0 of 0" are very different claims about the same zero.

Fixture-sidecar provenance (``real_corpus`` versus ``synthetic_generated``) is a
sibling dead-axis question but is deliberately OUT of this module's scope: those
sidecars are test fixtures with no registry schema model, validated by a gate
rather than compiled into the tree, and shipped registry code must not reach
into test corpora to census them.

Reading the registry
--------------------

The fold consumes COMPILED :class:`ModeloDefinition` objects, never a listing of
fragment subdirectories: a subdirectory-blind read of this registry has twice
produced wrong "parse-only" verdicts.
:func:`audit_bundled_classification_coherence` loads the tree through the
non-validating loader and stamps the result ``registry_validated=False``,
because a governance read must survive a concurrently-edited registry that the
validating authority would refuse to load outright. Callers holding a validated
authority inject their own definitions through
:func:`build_classification_coherence_audit` and stamp the result accordingly.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final, Literal

from pydantic import BaseModel, Field

from ....core import (
    NON_REGISTRY_MODELOS,
    PROSE_ELISION_MARKER,
    STRICT_FROZEN_CONFIG,
    Modelo,
    TaxDomain,
    elide_to_cap,
)
from ....core.resources import bundled_path
from ._validate_revision_rules import validate_informative_class_invariant
from .ids import ModeloId
from .loader import load_registry_tree
from .schema import ModeloDefinition
from .schema_base import CalculationClass

#: The ``calculation_class`` value naming the informative enforcement posture.
_INFORMATIVE_CLASS: Final[CalculationClass] = "informative"

#: Appended to a clamped ``detail`` so a truncated sentence reads as truncated.
#: The elision marker, taken from the one home the whole tree shares.
#:
#: This module grew its own marker before a canonical one existed. Keeping a
#: second spelling meant an operator met "…" here and " [...]" on every
#: diagnostic, for the same act of shortening.
_TRUNCATION_SUFFIX: Final[str] = PROSE_ELISION_MARKER

#: Blockers rendered verbatim into a finding's prose before the rest is counted.
#: A modelo can carry one blocker per casilla, so the full list belongs on
#: :attr:`ModeloClassificationRow.informative_class_blockers` and only a sample
#: reaches the sentence.
_RENDERED_BLOCKER_SAMPLE: Final[int] = 1

ClassificationFindingKind = Literal[
    "informative_axis_divergence",
    "non_registry_modelo_defined_in_tree",
    "registry_modelo_absent_from_modelo_enum",
    "dependency_conditional_activity_without_filing",
]
"""How the four classification homes can contradict one another."""

DeclaredAxis = Literal[
    "calculation_class.summary",
    "extraction_profile.confidence.review_required",
    "extraction_profile.verification_source.real_aeat_corpus_pdf",
    "completeness_manifest.manual_extraction",
]
"""Registry schema surfaces whose exercise by the tree is censused, not assumed."""

DeclaredAxisStatus = Literal["exercised", "unused"]
"""Whether any TOML in the tree declares an axis, or the surface is dead."""


def _field_max_length(model: type[BaseModel], field_name: str) -> int | None:
    """Return the ``max_length`` constraint declared on ``model``'s ``field_name``.

    Read from the field's own constraint metadata rather than copied as a second
    literal, so a clamp that exists to satisfy a bound cannot outlive a change to
    it: lowering the field bound lowers the clamp in the same edit.

    Returns:
        The declared upper bound, or :data:`None` when the field declares none —
        in which case there is nothing to clamp against.
    """
    for constraint in model.model_fields[field_name].metadata:
        declared = getattr(constraint, "max_length", None)
        if declared is not None:
            return int(declared)
    return None


class ClassificationModel(BaseModel):
    """Strict frozen base for classification-coherence facts."""

    model_config = STRICT_FROZEN_CONFIG


class ClassificationCoherenceFinding(ClassificationModel):
    """One disagreement between two of the four classification homes.

    Reported, never acted on. ``subject`` names the narrower thing the finding
    is about when the modelo id alone is too coarse — a revision id, or a
    dependency-classification id — and repeats the modelo id otherwise, so a
    renderer can always print a stable second column.

    ``registry_validated`` mirrors the audit-level flag down onto each finding so
    the label is not lost when findings are extracted through the container's
    :attr:`RegistryClassificationAudit.findings` property: a consumer that
    flattens findings across rows still knows whether each one came from a
    validated authority read or a degraded non-validating one.
    """

    kind: ClassificationFindingKind
    modelo: ModeloId
    subject: str = Field(min_length=1, max_length=160)
    detail: str = Field(min_length=1, max_length=512)
    registry_validated: bool


#: Upper bound on a finding's ``detail``, READ FROM the field constraint above
#: rather than duplicated as a second literal beside it. :data:`None` would mean
#: the field declares no bound and nothing needs clamping.
_MAX_DETAIL_LENGTH: Final[int | None] = _field_max_length(ClassificationCoherenceFinding, "detail")


class DeclaredAxisUsage(ClassificationModel):
    """Whether the tree exercises one declared schema axis, and out of how many sites.

    ``population`` is the count of candidate declaration sites the axis could
    have been declared on — revisions, extraction profiles, completeness
    manifests — so an unused axis is reported against a real denominator. Zero
    declarations out of a large population is a dead vocabulary member; zero out
    of zero says only that nothing could have declared it either way.
    """

    axis: DeclaredAxis
    declaration_count: int = Field(ge=0)
    population: int = Field(ge=0)

    @property
    def status(self) -> DeclaredAxisStatus:
        """Whether any site in the tree declares this axis."""
        return "exercised" if self.declaration_count else "unused"


class ModeloClassificationRow(ClassificationModel):
    """Classification facts for one modelo, across every home that classifies it.

    Emitted for EVERY modelo in the tree, including fully coherent ones, so a
    modelo with nothing to report is a visible clean row rather than an absent
    one.

    ``registry_validated`` mirrors the audit-level flag so a consumer that
    iterates rows directly, rather than reading the enclosing audit, can still
    tell whether the row came from a validated authority read or a degraded one.
    """

    modelo: ModeloId
    calculation_class: CalculationClass
    tax_domain: TaxDomain
    informative_by_calculation_class: bool
    informative_by_tax_domain: bool
    informative_class_blockers: tuple[str, ...]
    declared_non_registry: bool
    known_modelo_code: bool
    findings: tuple[ClassificationCoherenceFinding, ...]
    registry_validated: bool

    @property
    def informative_axes_agree(self) -> bool:
        """Whether the enforcement posture and the taxonomy label say the same thing."""
        return self.informative_by_calculation_class == self.informative_by_tax_domain

    @property
    def informative_class_available(self) -> bool:
        """Whether ``calculation_class = "informative"`` would survive registry build.

        :data:`False` when the modelo declares filing-grade computation
        artefacts the informative-class invariant forbids. A divergence on a
        modelo where this is :data:`False` is FORCED by the enforcement rule,
        not authoring drift — the distinction this row exists to preserve.
        """
        return not self.informative_class_blockers


class RegistryClassificationAudit(ClassificationModel):
    """Registry-wide classification coherence and declared-axis census."""

    rows: tuple[ModeloClassificationRow, ...]
    axis_usage: tuple[DeclaredAxisUsage, ...]
    registry_validated: bool

    @property
    def findings(self) -> tuple[ClassificationCoherenceFinding, ...]:
        """Every finding across every row, in row order."""
        return tuple(finding for row in self.rows for finding in row.findings)

    def findings_of_kind(self, kind: ClassificationFindingKind) -> tuple[ClassificationCoherenceFinding, ...]:
        """Return every finding of ``kind``."""
        return tuple(finding for finding in self.findings if finding.kind == kind)

    @property
    def ok(self) -> bool:
        """Whether the four classification homes agree everywhere.

        Scoped to coherence only. The declared-axis census is deliberately
        excluded: unused axes exist in the tree today by design, so folding them
        in would pin this to :data:`False` permanently and destroy its value as
        a signal.
        """
        return not self.findings

    @property
    def unused_axes(self) -> tuple[DeclaredAxis, ...]:
        """Every tracked schema axis no TOML in the tree declares."""
        return tuple(item.axis for item in self.axis_usage if item.status == "unused")

    @property
    def checked_modelo_count(self) -> int:
        """Modelos the fold classified.

        The anti-vacuity floor: a fold that read an empty tree would report no
        findings while checking nothing.
        """
        return len(self.rows)


def build_classification_coherence_audit(
    modelos: Iterable[ModeloDefinition],
    *,
    non_registry_modelo_codes: frozenset[str],
    known_modelo_codes: frozenset[str],
    registry_validated: bool,
) -> RegistryClassificationAudit:
    """Fold ``modelos`` into a registry-wide classification-coherence audit.

    Args:
        modelos: Compiled :class:`ModeloDefinition` records to classify, taken
            from the loaded tree, never from a fragment-directory listing.
        non_registry_modelo_codes: Modelo codes declared to have no registry
            definition. A code here that nonetheless appears in ``modelos``
            contradicts the declaration.
        known_modelo_codes: Every modelo code the core identifier enum knows. A
            tree modelo absent from this set is unreachable through the typed
            identifier surface.
        registry_validated: Whether ``modelos`` came from the validating
            authority. Stamped onto the audit so a degraded read is never
            mistaken for validated authority.

    Returns:
        A :class:`RegistryClassificationAudit`. Never raises on a disagreement;
        a contradiction between two homes is returned as a finding.
    """
    modelo_tuple = tuple(sorted(modelos, key=lambda item: item.id))
    rows = tuple(
        _build_row(
            modelo,
            non_registry_modelo_codes=non_registry_modelo_codes,
            known_modelo_codes=known_modelo_codes,
            registry_validated=registry_validated,
        )
        for modelo in modelo_tuple
    )
    return RegistryClassificationAudit(
        rows=rows,
        axis_usage=_census_declared_axes(modelo_tuple),
        registry_validated=registry_validated,
    )


def audit_bundled_classification_coherence() -> RegistryClassificationAudit:
    """Audit classification coherence across the bundled registry tree.

    Uses the non-validating loader, so a governance read survives a
    concurrently-edited registry that the validating authority would refuse
    outright. The returned audit is stamped ``registry_validated=False``
    accordingly.
    """
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return build_classification_coherence_audit(
        modelos,
        non_registry_modelo_codes=frozenset(item.value for item in NON_REGISTRY_MODELOS),
        known_modelo_codes=frozenset(item.value for item in Modelo),
        registry_validated=False,
    )


def _build_row(
    modelo: ModeloDefinition,
    *,
    non_registry_modelo_codes: frozenset[str],
    known_modelo_codes: frozenset[str],
    registry_validated: bool,
) -> ModeloClassificationRow:
    """Build one modelo's classification row and every finding it carries."""
    by_class = modelo.calculation_class == _INFORMATIVE_CLASS
    by_domain = modelo.tax_domain is TaxDomain.INFORMATIVE
    blockers = _informative_class_blockers(modelo)
    declared_non_registry = modelo.id in non_registry_modelo_codes
    known_code = modelo.id in known_modelo_codes

    findings: list[ClassificationCoherenceFinding] = []
    if by_class != by_domain:
        findings.append(
            _informative_divergence_finding(
                modelo, by_class=by_class, blockers=blockers, registry_validated=registry_validated
            )
        )
    if declared_non_registry:
        findings.append(
            ClassificationCoherenceFinding(
                kind="non_registry_modelo_defined_in_tree",
                modelo=modelo.id,
                subject=modelo.id,
                detail=_bounded_detail(
                    f"modelo {modelo.id} is declared to have no registry definition, yet the loaded tree "
                    "compiles one for it",
                ),
                registry_validated=registry_validated,
            ),
        )
    if not known_code:
        findings.append(
            ClassificationCoherenceFinding(
                kind="registry_modelo_absent_from_modelo_enum",
                modelo=modelo.id,
                subject=modelo.id,
                detail=_bounded_detail(
                    f"modelo {modelo.id} is defined in the registry tree but no core modelo identifier names "
                    "it, so it is unreachable through the typed identifier surface",
                ),
                registry_validated=registry_validated,
            ),
        )
    findings.extend(_dependency_findings(modelo, registry_validated=registry_validated))

    return ModeloClassificationRow(
        modelo=modelo.id,
        calculation_class=modelo.calculation_class,
        tax_domain=modelo.tax_domain,
        informative_by_calculation_class=by_class,
        informative_by_tax_domain=by_domain,
        informative_class_blockers=blockers,
        declared_non_registry=declared_non_registry,
        known_modelo_code=known_code,
        findings=tuple(findings),
        registry_validated=registry_validated,
    )


def _informative_divergence_finding(
    modelo: ModeloDefinition,
    *,
    by_class: bool,
    blockers: tuple[str, ...],
    registry_validated: bool,
) -> ClassificationCoherenceFinding:
    """Describe an informative-axis divergence together with what forces it, if anything."""
    if by_class:
        held, absent = "calculation_class = 'informative'", f"tax_domain = '{modelo.tax_domain.value}'"
        forcing = "the taxonomy label is a free choice carrying no invariant"
    else:
        held, absent = "tax_domain = 'informative'", f"calculation_class = '{modelo.calculation_class}'"
        forcing = (
            f"the informative-class invariant forbids the value here ({_render_blockers(blockers)})"
            if blockers
            else "the informative-class invariant would permit the value, so nothing in the tree forces the divergence"
        )
    return ClassificationCoherenceFinding(
        kind="informative_axis_divergence",
        modelo=modelo.id,
        subject=modelo.id,
        detail=_bounded_detail(f"modelo {modelo.id} declares {held} but {absent}; {forcing}"),
        registry_validated=registry_validated,
    )


def _render_blockers(blockers: tuple[str, ...]) -> str:
    """Render a sample of ``blockers`` plus a count of the rest.

    A modelo can produce one blocker per casilla, so joining them all would
    overflow the finding's ``detail`` bound and make constructing the finding
    raise — on precisely the disagreement this fold exists to report. The
    complete list stays on the row.
    """
    sample = "; ".join(blockers[:_RENDERED_BLOCKER_SAMPLE])
    remainder = len(blockers) - _RENDERED_BLOCKER_SAMPLE
    if remainder <= 0:
        return sample
    return f"{sample}; and {remainder} further blocker{'s' if remainder > 1 else ''}"


def _bounded_detail(detail: str, *, max_length: int | None = _MAX_DETAIL_LENGTH) -> str:
    """Clamp ``detail`` to the finding field's own declared bound.

    Defensive rather than cosmetic, and the LAST of two layers: the blocker
    sampler keeps the sentence short in the cases the fold can foresee, and this
    keeps a sentence that outgrew the bound anyway from raising a validation
    error and aborting the whole governance read. Registry-authored ids flow into
    these sentences, so their combined worst case moves whenever an id bound or a
    sentence template does.

    ``max_length`` defaults to the bound derived from the field and is injectable
    so a test can prove the clamp TRACKS the bound rather than restating a
    number. :data:`None` disables clamping, which is the correct behaviour for an
    unbounded field.
    """
    if max_length is None:
        return detail
    return elide_to_cap(detail, cap=max_length)


def _informative_class_blockers(modelo: ModeloDefinition) -> tuple[str, ...]:
    """Return why ``calculation_class = "informative"`` would be refused for ``modelo``.

    Asks the real invariant rather than mirroring it: the modelo is copied with
    the informative class applied and handed to
    :func:`validate_informative_class_invariant`, so this answer cannot drift
    from the rule the registry build actually enforces. Empty when the value
    would be accepted.
    """
    candidate = modelo.model_copy(update={"calculation_class": _INFORMATIVE_CLASS})
    return tuple(validate_informative_class_invariant(candidate))


def _dependency_findings(modelo: ModeloDefinition, *, registry_validated: bool) -> list[ClassificationCoherenceFinding]:
    """Report dependency classifications whose two filing flags cannot both hold.

    ``conditional_on_economic_activity`` narrows WHEN the taxpayer files the
    source, so it is meaningful only where the taxpayer files it at all. Paired
    with ``taxpayer_files_source = false`` it states a condition on a filing
    that never happens.
    """
    findings: list[ClassificationCoherenceFinding] = []
    for revision in sorted(modelo.revisions.values(), key=lambda item: item.id):
        for dependency in revision.dependency_classifications:
            if dependency.conditional_on_economic_activity and not dependency.taxpayer_files_source:
                findings.append(
                    ClassificationCoherenceFinding(
                        kind="dependency_conditional_activity_without_filing",
                        modelo=modelo.id,
                        subject=str(dependency.id),
                        detail=_bounded_detail(
                            f"modelo {modelo.id} revision {revision.id}: dependency {dependency.id} is "
                            "conditional_on_economic_activity while taxpayer_files_source is false, so it "
                            "conditions a filing the taxpayer never makes",
                        ),
                        registry_validated=registry_validated,
                    ),
                )
    return findings


def _census_declared_axes(modelos: tuple[ModeloDefinition, ...]) -> tuple[DeclaredAxisUsage, ...]:
    """Count declarations of every tracked schema axis against its candidate population."""
    revisions = tuple(revision for modelo in modelos for revision in modelo.revisions.values())
    profiles = tuple(profile for revision in revisions for profile in revision.extraction_profiles)
    manifests = tuple(revision.completeness_manifest for revision in revisions if revision.completeness_manifest)

    return (
        DeclaredAxisUsage(
            axis="calculation_class.summary",
            declaration_count=sum(1 for modelo in modelos if modelo.calculation_class == "summary"),
            population=len(modelos),
        ),
        DeclaredAxisUsage(
            axis="extraction_profile.confidence.review_required",
            declaration_count=sum(1 for profile in profiles if profile.confidence == "review_required"),
            population=len(profiles),
        ),
        DeclaredAxisUsage(
            axis="extraction_profile.verification_source.real_aeat_corpus_pdf",
            declaration_count=sum(1 for profile in profiles if profile.verification_source == "real_aeat_corpus_pdf"),
            population=len(profiles),
        ),
        DeclaredAxisUsage(
            axis="completeness_manifest.manual_extraction",
            declaration_count=sum(1 for manifest in manifests if manifest.manual_extraction),
            population=len(manifests),
        ),
    )
