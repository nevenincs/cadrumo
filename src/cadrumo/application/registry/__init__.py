"""Application services for read-only registry workflows.

Registry query and corpus validation services consume a
:class:`domain.calculations.registry.ValidatedRegistryAuthority` as
the single entry point for
:class:`domain.calculations.registry.ModeloDefinition` instances,
:class:`domain.calculations.registry.RegistrySnapshot` values, and
deadline windows.

This package root is inert for real contracts: it re-exports 87 names
resolved lazily from sibling modules, and owns no type or function
definitions of its own. The three local read surfaces each live in their
own module and are imported directly:
:mod:`application.registry.tree` (registry-tree inspection and
verification over the bundled ``registry/aeat`` tree),
:mod:`application.registry.corpus` (corpus/manual projection over
:class:`~application.registry.corpus.RegistryTopicProjection` and related
report records), and :mod:`application.registry.filed_state` (filed-state
comparison that loads captured AEAT observations before recomputing a
registry snapshot locally).

The observation-persistence path reads captured filed state through the
active-bucket encrypted observation store.

THIS NAMESPACE IS NOT INERT TO IMPORT: the root still eagerly runs
``import_module("cadrumo.domain.renta")`` at module scope to register the
first-slice routing cross-domain snapshot check required by Modelo 100
snapshots. That import alone costs roughly 613 modules and ~1.3s wall
time (measured against a clean interpreter) -- retiring the lazy-export
map and moving the tree/filed-state definitions out did NOT make touching
this package cheap. Any future consumer measuring this package's cost
must account for that eager renta import, not just the (now-retired) lazy
map.

See Also:
    :class:`domain.calculations.registry.ValidatedRegistryAuthority`
        Domain authority used to load, validate, and snapshot modelo registry
        definitions.
    :class:`~application.registry.tree.RegistryTreeReport`
        Application report returned by registry-tree inspection and verification.
    :class:`RegistryCitationsListReport`
        Citation projection over reviewed registry legal references and topics.
    :class:`RegistryManualVerificationReport`
        Manual/casilla verification report for bundled manual corpus checks.
    :mod:`domain.manuals`
        Strict manual schema and loader surface that owns extracted manual
        records and :class:`domain.manuals.ManualCasillaReference` values.
    :mod:`core.resources`
        Bundled-data boundary used to locate packaged registry and corpus
        material without repository-relative path reads.
    :class:`~application.registry.filed_state.FiledStateVerificationReport`
        Filed-state comparison report built from encrypted captured AEAT
        observations and local registry recalculation.
    :class:`adapters.outbound.aeat.sede.FiledDeclaracionObservationStore`
        Active-bucket observation store that persists captured filed state for
        local registry comparison.
    :mod:`application.modelo.registry_discovery`
        Modelo work-unit discovery queries consumed by operator surfaces.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING

from .errors import (
    RegistryApplicationError,
    RegistryApplicationInputError,
)

if TYPE_CHECKING:
    from .conformance import (
        AnnualCasillaPopulationComparison,
        CoverageAuthorityScope,
        LatestRevisionSupportProbe,
        RegistryConformanceProfile,
        RevisionCapabilityFacts,
        RevisionCasillaProducerTrace,
        RevisionConformanceRow,
        RevisionConstructEvidence,
        RevisionGovernanceStamp,
        RevisionModelLawCoverage,
        audit_bundled_registry_conformance,
        build_registry_conformance_profile,
        compare_annual_casilla_population,
        compare_annual_casilla_population_for_revision,
    )
    from .corpus import (
        RegistryCitationArticleProjection,
        RegistryCitationReferenceProjection,
        RegistryCitationShowCommand,
        RegistryCitationShowReport,
        RegistryCitationsListCommand,
        RegistryCitationsListReport,
        RegistryCitationsVerificationReport,
        RegistryCorpusIssueProjection,
        RegistryManualId,
        RegistryManualPartProjection,
        RegistryManualRuleProjection,
        RegistryManualRulesCommand,
        RegistryManualRulesReport,
        RegistryManualSectionProjection,
        RegistryManualShowCommand,
        RegistryManualShowReport,
        RegistryManualsListCommand,
        RegistryManualsListReport,
        RegistryManualVerificationReport,
        RegistryManualVerifyCommand,
        RegistryTopicProjection,
        list_registry_citations,
        list_registry_manual_rules,
        list_registry_manuals,
        registry_manual_id,
        show_registry_citation,
        show_registry_manual,
        verify_registry_citations,
        verify_registry_manual,
    )
    from .diff import (
        BindingDiff,
        CasillaDiff,
        FormulaDiff,
        ParameterDiff,
        RegistryRevisionDiffReport,
        RenumberedCasilla,
        diff_registry_revisions,
    )
    from .filing_export_authority import (
        FilingExportEmissionProof,
        FilingExportGenerationProof,
        FilingExportProof,
        FilingExportProofConflictError,
        GeneratedExportFileDigest,
    )
    from .filing_export_coverage import (
        FilingExportCoverageReport,
        compose_filing_export_coverage,
    )
    from .source_connectivity import (
        ManualCasillaRequirement,
        RegistryBindingRecord,
        RegistryDestinationCandidate,
        RegistryDestinationRecord,
        RegistryFormulaRecord,
        RegistryRelationRecord,
        RegistrySourceDispositionRecord,
        SourceConnectivityCensusEntry,
        SourceConnectivityCensusManifest,
        derive_registry_binding_records,
        derive_registry_destination_records,
        derive_registry_formula_records,
        derive_registry_relation_records,
        derive_registry_source_disposition_records,
        load_source_connectivity_census,
        validate_census_destination_candidates,
    )
    from .source_connectivity_authority import (
        CalculationRouteManualSourceOwnership,
        CalculationRouteResolverSourceOwnership,
        CalculationRouteSourceOwnershipCatalogue,
        LiveSourceConnectivityProofAuthority,
        LiveSourceConnectivityProofExpectation,
        RepositoryEvidenceDigestVerifier,
        RepositoryRootEvidenceDigestVerifier,
        build_calculation_route_source_ownership_catalogue,
    )
    from .source_connectivity_coverage import (
        SourceConnectivityCoverageReport,
        compose_source_connectivity_coverage,
    )
    from .temporal_coverage import (
        TemporalCoverageReport,
        TemporalRevisionCoverage,
        TemporalRevisionCoverageSummary,
        compose_temporal_coverage,
    )

_LAZY_EXPORTS: dict[str, str] = {
    "AnnualCasillaPopulationComparison": "._conformance",
    "BindingDiff": "._diff",
    "CalculationRouteManualSourceOwnership": "._source_connectivity_authority",
    "CalculationRouteResolverSourceOwnership": "._source_connectivity_authority",
    "CalculationRouteSourceOwnershipCatalogue": "._source_connectivity_authority",
    "CasillaDiff": "._diff",
    "CoverageAuthorityScope": "._conformance",
    "FilingExportCoverageReport": "._filing_export_coverage",
    "FilingExportEmissionProof": "._filing_export_authority",
    "FilingExportGenerationProof": "._filing_export_authority",
    "FilingExportProof": "._filing_export_authority",
    "FilingExportProofConflictError": "._filing_export_authority",
    "FormulaDiff": "._diff",
    "GeneratedExportFileDigest": "._filing_export_authority",
    "LatestRevisionSupportProbe": "._conformance",
    "LiveSourceConnectivityProofAuthority": "._source_connectivity_authority",
    "LiveSourceConnectivityProofExpectation": "._source_connectivity_authority",
    "ManualCasillaRequirement": ".source_connectivity",
    "ParameterDiff": "._diff",
    "RegistryBindingRecord": ".source_connectivity",
    "RegistryCitationArticleProjection": "._corpus",
    "RegistryCitationReferenceProjection": "._corpus",
    "RegistryCitationShowCommand": "._corpus",
    "RegistryCitationShowReport": "._corpus",
    "RegistryCitationsListCommand": "._corpus",
    "RegistryCitationsListReport": "._corpus",
    "RegistryCitationsVerificationReport": "._corpus",
    "RegistryConformanceProfile": "._conformance",
    "RegistryCorpusIssueProjection": "._corpus",
    "RegistryDestinationCandidate": ".source_connectivity",
    "RegistryDestinationRecord": ".source_connectivity",
    "RegistryFormulaRecord": ".source_connectivity",
    "RegistryManualId": "._corpus",
    "RegistryManualPartProjection": "._corpus",
    "RegistryManualRuleProjection": "._corpus",
    "RegistryManualRulesCommand": "._corpus",
    "RegistryManualRulesReport": "._corpus",
    "RegistryManualSectionProjection": "._corpus",
    "RegistryManualShowCommand": "._corpus",
    "RegistryManualShowReport": "._corpus",
    "RegistryManualVerificationReport": "._corpus",
    "RegistryManualVerifyCommand": "._corpus",
    "RegistryManualsListCommand": "._corpus",
    "RegistryManualsListReport": "._corpus",
    "RegistryRelationRecord": ".source_connectivity",
    "RegistryRevisionDiffReport": "._diff",
    "RegistrySourceDispositionRecord": ".source_connectivity",
    "RegistryTopicProjection": "._corpus",
    "RenumberedCasilla": "._diff",
    "RepositoryEvidenceDigestVerifier": "._source_connectivity_authority",
    "RepositoryRootEvidenceDigestVerifier": "._source_connectivity_authority",
    "RevisionCapabilityFacts": "._conformance",
    "RevisionCasillaProducerTrace": "._conformance",
    "RevisionConformanceRow": "._conformance",
    "RevisionConstructEvidence": "._conformance",
    "RevisionGovernanceStamp": "._conformance",
    "RevisionModelLawCoverage": "._conformance",
    "SourceConnectivityCensusEntry": ".source_connectivity",
    "SourceConnectivityCensusManifest": ".source_connectivity",
    "SourceConnectivityCoverageReport": "._source_connectivity_coverage",
    "TemporalCoverageReport": "._temporal_coverage",
    "TemporalRevisionCoverage": "._temporal_coverage",
    "TemporalRevisionCoverageSummary": "._temporal_coverage",
    "audit_bundled_registry_conformance": "._conformance",
    "build_calculation_route_source_ownership_catalogue": "._source_connectivity_authority",
    "build_registry_conformance_profile": "._conformance",
    "compare_annual_casilla_population": "._conformance",
    "compare_annual_casilla_population_for_revision": "._conformance",
    "compose_filing_export_coverage": "._filing_export_coverage",
    "compose_source_connectivity_coverage": "._source_connectivity_coverage",
    "compose_temporal_coverage": "._temporal_coverage",
    "derive_registry_binding_records": ".source_connectivity",
    "derive_registry_destination_records": ".source_connectivity",
    "derive_registry_formula_records": ".source_connectivity",
    "derive_registry_relation_records": ".source_connectivity",
    "derive_registry_source_disposition_records": ".source_connectivity",
    "diff_registry_revisions": "._diff",
    "list_registry_citations": "._corpus",
    "list_registry_manual_rules": "._corpus",
    "list_registry_manuals": "._corpus",
    "load_source_connectivity_census": ".source_connectivity",
    "registry_manual_id": "._corpus",
    "show_registry_citation": "._corpus",
    "show_registry_manual": "._corpus",
    "validate_census_destination_candidates": ".source_connectivity",
    "verify_registry_citations": "._corpus",
    "verify_registry_manual": "._corpus",
}
"""Names this package re-exports, resolved on first access.

The package root is a HYBRID: it defines real contracts of its own AND
re-exports 89 names from siblings. A lazy map still works, because
``__getattr__`` runs only for names absent from module globals -- the module's
own definitions are untouched and stay eager.

Eager re-exports made this root expensive to touch at all. CommandSpec
parameter annotations resolve through here, so BUILDING the Typer signature for
an unrelated registry command imported the filing package, the sede adapter and
the persistence family behind them. Four `app/registry/manuals/*` nodes paid
that on resolution.
"""

_LAZY_MODULE_LOADERS: dict[str, Callable[[], ModuleType]] = {
    module_path: partial(import_module, module_path, __name__) for module_path in frozenset(_LAZY_EXPORTS.values())
}


def __getattr__(name: str) -> object:
    """Resolve one re-exported name by importing only the sibling that owns it."""
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(_LAZY_MODULE_LOADERS[module_name](), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Report the full public surface, including names not yet resolved."""
    return sorted(set(__all__) | set(globals()))


import_module("cadrumo.domain.renta")


__all__ = [
    "AnnualCasillaPopulationComparison",
    "BindingDiff",
    "CalculationRouteManualSourceOwnership",
    "CalculationRouteResolverSourceOwnership",
    "CalculationRouteSourceOwnershipCatalogue",
    "CasillaDiff",
    "CoverageAuthorityScope",
    "FilingExportCoverageReport",
    "FilingExportEmissionProof",
    "FilingExportGenerationProof",
    "FilingExportProof",
    "FilingExportProofConflictError",
    "FormulaDiff",
    "GeneratedExportFileDigest",
    "LatestRevisionSupportProbe",
    "LiveSourceConnectivityProofAuthority",
    "LiveSourceConnectivityProofExpectation",
    "ManualCasillaRequirement",
    "ParameterDiff",
    "RegistryApplicationError",
    "RegistryApplicationInputError",
    "RegistryBindingRecord",
    "RegistryCitationArticleProjection",
    "RegistryCitationReferenceProjection",
    "RegistryCitationShowCommand",
    "RegistryCitationShowReport",
    "RegistryCitationsListCommand",
    "RegistryCitationsListReport",
    "RegistryCitationsVerificationReport",
    "RegistryConformanceProfile",
    "RegistryCorpusIssueProjection",
    "RegistryDestinationCandidate",
    "RegistryDestinationRecord",
    "RegistryFormulaRecord",
    "RegistryManualId",
    "RegistryManualPartProjection",
    "RegistryManualRuleProjection",
    "RegistryManualRulesCommand",
    "RegistryManualRulesReport",
    "RegistryManualSectionProjection",
    "RegistryManualShowCommand",
    "RegistryManualShowReport",
    "RegistryManualVerificationReport",
    "RegistryManualVerifyCommand",
    "RegistryManualsListCommand",
    "RegistryManualsListReport",
    "RegistryRelationRecord",
    "RegistryRevisionDiffReport",
    "RegistrySourceDispositionRecord",
    "RegistryTopicProjection",
    "RenumberedCasilla",
    "RepositoryEvidenceDigestVerifier",
    "RepositoryRootEvidenceDigestVerifier",
    "RevisionCapabilityFacts",
    "RevisionCasillaProducerTrace",
    "RevisionConformanceRow",
    "RevisionConstructEvidence",
    "RevisionGovernanceStamp",
    "RevisionModelLawCoverage",
    "SourceConnectivityCensusEntry",
    "SourceConnectivityCensusManifest",
    "SourceConnectivityCoverageReport",
    "TemporalCoverageReport",
    "TemporalRevisionCoverage",
    "TemporalRevisionCoverageSummary",
    "audit_bundled_registry_conformance",
    "build_calculation_route_source_ownership_catalogue",
    "build_registry_conformance_profile",
    "compare_annual_casilla_population",
    "compare_annual_casilla_population_for_revision",
    "compose_filing_export_coverage",
    "compose_source_connectivity_coverage",
    "compose_temporal_coverage",
    "derive_registry_binding_records",
    "derive_registry_destination_records",
    "derive_registry_formula_records",
    "derive_registry_relation_records",
    "derive_registry_source_disposition_records",
    "diff_registry_revisions",
    "list_registry_citations",
    "list_registry_manual_rules",
    "list_registry_manuals",
    "load_source_connectivity_census",
    "registry_manual_id",
    "show_registry_citation",
    "show_registry_manual",
    "validate_census_destination_candidates",
    "verify_registry_citations",
    "verify_registry_manual",
]
