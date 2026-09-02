"""Typed per-modelo support-matrix registry.

:class:`~domain.calculations.registry.ModeloEntry` is the first-class typed
roll-up of "what does modelo X actually support", derived entirely from the loaded
:class:`~domain.calculations.registry.ModeloDefinition` /
:class:`~domain.calculations.registry.ModeloRevision` records — never
hand-maintained. It composes existing registry primitives rather than
re-implementing them:

* calc-grade / manifest / export-format / extractor detection reads the latest
  revision's declared closure, completeness manifest, export layouts, and
  extraction profiles. This module is the SOLE authority for those predicates:
  a contributor-facing copy of them shipped in the developer tooling for a
  while, recomputing every field this row already carries from the same
  primitives, and was retired rather than delegated once the fork was measured;
* rename tracking reads the revision's already-declared
  :class:`~domain.calculations.registry.CasillaContinuidadEvolutionDefinition`
  entries (the ``casilla_continuidad_evolutions`` field);
* portal-compatibility tracking reads the revision's declared
  :class:`~domain.calculations.registry.LiveCrossReferenceDecision` entries
  (surface kind and evidence tier).

Coverage honesty (``no-silent-under-declaration``): a modelo missing a
capability, rename record, or portal cross-reference reports an explicit
empty/False value, never a fabricated positive.

See Also:
    :func:`~domain.calculations.registry.build_support_matrix`
        Pure builder that folds the
        :class:`~domain.calculations.registry.ValidatedRegistryAuthority` into
        typed rows.
    :class:`~domain.calculations.registry._query_reports.ModeloSupportMatrixReport`
        Query-service envelope returned by
        :meth:`~domain.calculations.registry.RegistryQueryService.support_matrix`.
    :func:`~application.modelo.registry_discovery.registry_support_matrix`
        Application query used by CLI discovery without re-reading registry
        authority directly.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, NonNegativeInt

from ....core.export_layout_format import ExportLayoutFormat
from ....core.models import STRICT_FROZEN_CONFIG
from .authority import ValidatedRegistryAuthority
from .ids import ModeloId, RevisionId
from .record_design_coverage import calculation_closure_casilla_ids
from .schema import ModeloDefinition, ModeloRevision
from .schema_base import CalculationClass, EvidenceTierField
from .schema_surfaces import CasillaContinuidadEvolutionDefinition

__all__ = [
    "ModeloEntry",
    "ModeloPortalCompatibilityRef",
    "ModeloRenameRecord",
    "RevisionCapabilityProbe",
    "build_support_matrix",
    "revision_capability_probe",
]


def _latest_revision(modelo: ModeloDefinition) -> ModeloRevision:
    """Return the revision with the most recent ``valid_from`` for ``modelo``.

    A modelo always declares at least one revision
    (:meth:`~domain.calculations.registry.ModeloDefinition._validate_revisions`
    enforces this at load time), so the max is always well-defined.
    """
    return max(modelo.revisions.values(), key=lambda revision: revision.valid_from)


def _calculation_closure_casilla_ids(revision: ModeloRevision, modelo_id: str):
    return calculation_closure_casilla_ids(revision, modelo_id)


class RevisionCapabilityProbe(BaseModel):
    """The capability predicates ONE modelo revision declares.

    The support matrix folds these over a modelo's latest revision; the
    application-layer conformance composer folds them over whichever revision
    its row names. Both need the identical predicate set, so it is defined
    once here — the support authority owns what "calc grade" and "has a
    fixed-width export" mean, and a consumer that recomputed the expressions
    locally would silently drift from the canonical support row the first time
    a primitive or a scope changed.

    Attributes:
        calc_grade: Whether the revision's calculation closure is non-empty.
        has_completeness_manifest: Whether the revision declares a
            calculation-completeness manifest.
        has_fixed_width_export: Whether it registers a fichero-BOE layout.
        has_xml_dictionary_export: Whether it registers an XML-dictionary layout.
        has_extractor: Whether it declares any extraction profile.
        extraction_profile_count: Extraction profiles declared on the revision.
    """

    model_config = STRICT_FROZEN_CONFIG

    calc_grade: bool
    has_completeness_manifest: bool
    has_fixed_width_export: bool
    has_xml_dictionary_export: bool
    has_extractor: bool
    extraction_profile_count: NonNegativeInt


def revision_capability_probe(revision: ModeloRevision, *, modelo_id: str) -> RevisionCapabilityProbe:
    """Fold the capability predicates ``revision`` declares.

    Args:
        revision: The :class:`ModeloRevision` whose export layouts,
            completeness manifest, and extraction profiles are probed.
        modelo_id: Scopes the calculation-closure traversal that decides
            ``calc_grade``. This is the owning modelo's identifier, not a
            revision id.
    """
    export_formats = {layout.format for layout in revision.export_layouts}
    return RevisionCapabilityProbe(
        calc_grade=bool(_calculation_closure_casilla_ids(revision, modelo_id)),
        has_completeness_manifest=revision.completeness_manifest is not None,
        has_fixed_width_export=ExportLayoutFormat.FIXED_WIDTH in export_formats,
        has_xml_dictionary_export=ExportLayoutFormat.XML_DICTIONARY in export_formats,
        has_extractor=bool(revision.extraction_profiles),
        extraction_profile_count=len(revision.extraction_profiles),
    )


class ModeloRenameRecord(BaseModel):
    """One declared per-ejercicio casilla continuity evolution.

    Projects a :class:`~domain.calculations.registry.CasillaContinuidadEvolutionDefinition`
    already declared on the revision — this record never invents rename
    history; it surfaces what the registry already tracks per continuity
    chain (``continuidad_id``).

    Attributes:
        continuidad_id: The stable continuity chain identifier a casilla's
            number/label is tracked under across revisions.
        from_revision: Revision id the evolution starts from.
        to_revision: Revision id the evolution lands on.
        evolution_kind: The declared nature of the change (e.g.
            ``"label_evolved"``, ``"repurposed"``, ``"retired"``).
    """

    model_config = STRICT_FROZEN_CONFIG

    continuidad_id: str
    from_revision: RevisionId
    to_revision: RevisionId
    evolution_kind: str


class ModeloPortalCompatibilityRef(BaseModel):
    """One declared AEAT-portal cross-reference for a modelo revision.

    Projects a :class:`~domain.calculations.registry.LiveCrossReferenceDecision`
    already declared on the revision — the registry's own record of which live
    AEAT surface the modelo has been cross-checked against and under what
    evidence tier.

    Attributes:
        id: Stable registry identifier for the cross-reference decision.
        surface: The live AEAT surface kind cross-checked (e.g.
            ``"public_read_surface"``, ``"integration_test_service"``).
        evidence_tier: The declared evidence tier backing the cross-reference.
    """

    model_config = STRICT_FROZEN_CONFIG

    id: str
    surface: str
    evidence_tier: EvidenceTierField


class ModeloEntry(BaseModel):
    """First-class typed support-matrix record for one modelo.

    Derived entirely from the loaded registry authority — every field is a
    direct read or fold over the modelo's latest revision, never a
    hand-maintained value. See
    :func:`~domain.calculations.registry.build_support_matrix`.

    Attributes:
        modelo_id: The AEAT modelo identifier (e.g. ``"303"``).
        title: Human-readable display name from the registry.
        calculation_class: The modelo's declared calculation role
            (``"filing"``, ``"informative"``, or ``"summary"``).
        revision_count: Number of registry revisions declared for this modelo.
        latest_revision_id: The id of the revision this entry's capabilities
            are probed against (the revision with the most recent
            ``valid_from``).
        latest_revision_valid_from: That revision's applicability start date.
        supported_revision_ids: Every declared revision id, oldest
            ``valid_from`` first.
        calc_grade: Whether the latest revision's calculation closure is
            non-empty (has at least one formula/binding/verification wiring
            the engine traverses).
        has_completeness_manifest: Whether the latest revision declares a
            calculation-completeness manifest.
        has_fixed_width_export: Whether the latest revision registers a
            ``fixed_width`` (fichero-BOE) export layout.
        has_xml_dictionary_export: Whether the latest revision registers an
            ``xml_dictionary`` export layout.
        has_extractor: Whether the latest revision registers at least one
            extraction profile.
        extraction_profile_count: Count of extraction profiles on the latest
            revision.
        renames: Declared per-ejercicio casilla continuity evolutions on the
            latest revision.
        portal_compatibility_refs: Declared AEAT-portal cross-references on
            the latest revision.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo_id: ModeloId
    title: str
    calculation_class: CalculationClass
    revision_count: int
    latest_revision_id: RevisionId
    latest_revision_valid_from: date
    supported_revision_ids: tuple[RevisionId, ...]
    calc_grade: bool
    has_completeness_manifest: bool
    has_fixed_width_export: bool
    has_xml_dictionary_export: bool
    has_extractor: bool
    extraction_profile_count: int
    renames: tuple[ModeloRenameRecord, ...]
    portal_compatibility_refs: tuple[ModeloPortalCompatibilityRef, ...]


def _rename_record(evolution: CasillaContinuidadEvolutionDefinition) -> ModeloRenameRecord:
    return ModeloRenameRecord(
        continuidad_id=str(evolution.continuidad_id),
        from_revision=evolution.from_revision,
        to_revision=evolution.to_revision,
        evolution_kind=evolution.evolution_kind,
    )


def _entry_for_modelo(modelo: ModeloDefinition) -> ModeloEntry:
    revision = _latest_revision(modelo)
    capabilities = revision_capability_probe(revision, modelo_id=modelo.id)
    supported_revision_ids = tuple(
        item.id for item in sorted(modelo.revisions.values(), key=lambda item: (item.valid_from, str(item.id)))
    )
    renames = tuple(_rename_record(evolution) for evolution in revision.casilla_continuidad_evolutions)
    portal_refs = tuple(
        ModeloPortalCompatibilityRef(
            id=str(decision.id),
            surface=decision.surface,
            evidence_tier=decision.evidence_tier,
        )
        for decision in revision.live_cross_references
    )
    return ModeloEntry(
        modelo_id=modelo.id,
        title=modelo.title,
        calculation_class=modelo.calculation_class,
        revision_count=len(modelo.revisions),
        latest_revision_id=revision.id,
        latest_revision_valid_from=revision.valid_from,
        supported_revision_ids=supported_revision_ids,
        calc_grade=capabilities.calc_grade,
        has_completeness_manifest=capabilities.has_completeness_manifest,
        has_fixed_width_export=capabilities.has_fixed_width_export,
        has_xml_dictionary_export=capabilities.has_xml_dictionary_export,
        has_extractor=capabilities.has_extractor,
        extraction_profile_count=capabilities.extraction_profile_count,
        renames=renames,
        portal_compatibility_refs=portal_refs,
    )


def build_support_matrix(authority: ValidatedRegistryAuthority) -> tuple[ModeloEntry, ...]:
    """Probe every modelo in ``authority`` and return its typed support row.

    Args:
        authority: The
            :class:`~domain.calculations.registry.ValidatedRegistryAuthority`
            to probe.

    Returns:
        Every modelo's :class:`~domain.calculations.registry.ModeloEntry`,
        sorted by ``modelo_id``.
    """
    entries = (_entry_for_modelo(modelo) for modelo in authority.modelos)
    return tuple(sorted(entries, key=lambda entry: entry.modelo_id))
