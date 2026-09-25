"""Test access to the published registry authority through the runtime reader.

Tests that need real registry material read the generation selected by the
installed authority descriptor, exactly as product runtime does.  Each helper
leases one operation, answers from that pinned generation, and releases the
lease; the returned values are immutable, so they remain valid afterwards.

Authored-source compilation is not reachable from here.  A test that must
observe unpublished source edits validates the authoring boundary and belongs
with the registry development tooling instead.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from .....core.authority_grade import RegistryAuthorityGrade
from ....user_profile.schema import ProfileSchemaDefinition
from ..authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..authority_artifact import ProfileCreateContext
from ..facts.resolution import GovernedFactQuery, ResolvedGovernedFact
from ..governed_fact_scope import governed_facts_in_scope
from ..ids import RevisionId
from ..schema import ModeloDefinition, ModeloRevision, RegistrySnapshot, SupportedFilingYearsCatalogue
from ..schema_references import LegalReference, SourceReference
from ..static_inspection import RegistryRevisionInspection


@dataclass(frozen=True, slots=True)
class PublishedGovernedFactSource:
    """Resolve each governed-fact query inside its own published operation lease.

    Consumers that hold a fact source beyond one call, such as module-level
    resolution contexts, cannot keep an operation lease open; this source
    leases per query instead.
    """

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        """Resolve one typed governed-fact query from the published generation."""
        with bundled_indexed_authority().operation() as operation:
            return operation.resolve_governed_fact(query)

    def supported_filing_years(self) -> SupportedFilingYearsCatalogue:
        """Return the support envelope of the published generation."""
        with bundled_indexed_authority().operation() as operation:
            return operation.supported_filing_years()


def published_snapshot(
    modelo_id: str,
    *,
    filing_year: int,
    period: str,
    on: date | None = None,
    revision_id: RevisionId | None = None,
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
) -> RegistrySnapshot:
    """Build one admitted snapshot from the published generation."""
    with bundled_indexed_authority().operation() as operation:
        return operation.snapshot(
            modelo_id,
            filing_year=filing_year,
            period=period,
            on=on,
            revision_id=revision_id,
            grade=grade,
        )


def published_inspection(
    modelo_id: str,
    *,
    filing_year: int,
    period: str,
) -> RegistryRevisionInspection:
    """Project one static inspection from the published generation.

    Taken through the same law-selected capture product runtime uses, so the
    inspection a test reads is the one a workspace read would be admitted
    through rather than a separately assembled equivalent.
    """
    with bundled_indexed_authority().operation() as operation:
        capture = operation.capture_law_selected_projection(
            modelo_id,
            filing_year=filing_year,
            period=period,
            grade=None,
        )
    projection = capture.projection
    if not isinstance(projection, RegistryRevisionInspection):
        raise TypeError("a gradeless law-selected capture must return a static inspection")
    return projection


def published_authored_revision(modelo_id: str, *, year: int) -> ModeloRevision:
    """Load the authored revision whose validity covers ``year``.

    Filing selection refuses years outside the support envelope; authored
    historical revisions stay readable for tests that inspect their declarations.
    """
    with bundled_indexed_authority().operation() as operation:
        covering = [
            revision
            for revision in operation.modelo_directory(modelo_id).revisions
            if revision.valid_from.year <= year and (revision.valid_to is None or year <= revision.valid_to.year)
        ]
        if len(covering) != 1:
            raise LookupError(
                f"modelo {modelo_id}: expected one authored revision covering {year}, got {len(covering)}"
            )
        return operation.revision(modelo_id, str(covering[0].id))


def published_modelo_ids() -> tuple[str, ...]:
    """Return every modelo identity in the published generation."""
    with bundled_indexed_authority().operation() as operation:
        return operation.modelo_ids()


def published_revision(modelo_id: str, revision_id: str) -> ModeloRevision:
    """Return one published revision together with its export layouts."""
    with bundled_indexed_authority().operation() as operation:
        return operation.revision_with_export_layouts(modelo_id, revision_id)


def published_revision_definitions() -> tuple[ModeloDefinition, ...]:
    """Return one single-revision modelo view per published revision.

    Each view is materialized by its modelo directory, so revision-identity
    references resolve against every revision the directory declares.  A
    modelo with several revisions therefore appears once per revision.
    """
    with bundled_indexed_authority().operation() as operation:
        definitions: list[ModeloDefinition] = []
        for modelo_id in operation.modelo_ids():
            directory = operation.modelo_directory(modelo_id)
            definitions.extend(
                directory.materialize(operation.revision_with_export_layouts(modelo_id, str(metadata.id)))
                for metadata in directory.revisions
            )
        return tuple(definitions)


def published_selected_revision_id(modelo_id: str, *, filing_year: int, period: str) -> str:
    """Return the revision the canonical temporal selector admits for one filing coordinate."""
    with bundled_indexed_authority().operation() as operation:
        return str(operation.revision_for_context(modelo_id, filing_year=filing_year, period=period).id)


def published_legal_reference(reference_id: str) -> LegalReference:
    """Return one published legal declaration by canonical identity."""
    with bundled_indexed_authority().operation() as operation:
        return operation.legal_reference(reference_id)


def published_legal_references(reference_ids: Iterable[str]) -> dict[str, LegalReference]:
    """Return the published legal declarations among ``reference_ids``, omitting ids it does not carry."""
    references: dict[str, LegalReference] = {}
    with bundled_indexed_authority().operation() as operation:
        for reference_id in dict.fromkeys(reference_ids):
            try:
                references[reference_id] = operation.legal_reference(reference_id)
            except LookupError:
                continue
    return references


def published_legal_quotation_is_grounded(reference_id: str, quotation: str) -> bool:
    """Judge one quotation against the published evidence through the canonical projection."""
    with bundled_indexed_authority().operation() as operation:
        return operation.legal_quotation_is_grounded(reference_id, quotation)


def published_legal_evidence_text(reference_id: str) -> str:
    """Return the publisher-anchored text for one legal citation."""
    with bundled_indexed_authority().operation() as operation:
        return operation.legal_evidence(reference_id).anchored_text


def published_source_reference(reference_id: str) -> SourceReference:
    """Return one published public-source declaration by canonical identity."""
    with bundled_indexed_authority().operation() as operation:
        return operation.source_reference(reference_id)


def published_supported_filing_years() -> SupportedFilingYearsCatalogue | None:
    """Return the filing-year envelope the published modelo directories carry."""
    with bundled_indexed_authority().operation() as operation:
        return operation.modelo_directory(operation.modelo_ids()[0]).supported_filing_years


def published_profile_schema() -> ProfileSchemaDefinition:
    """Return the user-profile schema carried by the published generation."""
    with bundled_indexed_authority().operation() as operation:
        return operation.profile_schema()


def leased_profile_create_context() -> ProfileCreateContext:
    """Return the creation context of the authority operation leased for the running test.

    The code under test reads that same operation through the governed-fact
    scope, so a record built with this context carries the generation pin the
    code under test compares against. A test module obtains the lease with
    ``pytest.mark.usefixtures("authority_operation")``; outside a lease this
    refuses instead of opening a lease of its own.
    """
    operation = governed_facts_in_scope()
    if not isinstance(operation, PinnedAuthorityOperation):
        raise LookupError("a profile creation context requires a leased authority operation in scope")
    return operation.profile_create_context()
