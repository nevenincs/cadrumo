"""Test-owned external-grounding conformance audit."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Annotated, Literal

from dev.registry.maintenance_support import ExternalOracleInventory, UnattributedOraclePayload

from ..core.casilla_id import CasillaId
from ..core.prose_elision import ElidedProse
from ..domain.calculations.registry.external_grounding import ExternalGroundingModel, ExternalOracleCorpus
from ..domain.calculations.registry.ids import ModeloId, RevisionId
from ..domain.calculations.registry.period_selector_match import selector_token_for_request
from ..domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from ..domain.calculations.registry.schema_input_kind import InputKind

_GroundingDetail = Annotated[str, ElidedProse(512)]

ExternalGroundingFindingKind = Literal[
    "oracle_casilla_not_computed", "oracle_casilla_not_enrolled", "declared_grounding_without_oracle_evidence"
]


class ExternalGroundingFinding(ExternalGroundingModel):
    """One breach of the grounding honesty relation, in either direction."""

    kind: ExternalGroundingFindingKind
    modelo: ModeloId
    revision: RevisionId
    casilla_id: CasillaId
    detail: _GroundingDetail


class RevisionExternalGroundingRow(ExternalGroundingModel):
    """External-grounding facts for one modelo revision.

    Emitted for EVERY revision in the tree, including those with no
    verification contract and no bundled oracle at all, so an ungrounded
    revision is a visible zero rather than an absent row.
    """

    modelo: ModeloId
    revision: RevisionId
    reconciled_casilla_ids: tuple[CasillaId, ...]
    declared_grounded_casilla_ids: tuple[CasillaId, ...]
    oracle_evidence_casilla_ids: tuple[CasillaId, ...]
    evidence_corpora: tuple[ExternalOracleCorpus, ...]
    findings: tuple[ExternalGroundingFinding, ...]

    @property
    def independently_checked_casilla_ids(self) -> tuple[CasillaId, ...]:
        """Reconciled casillas this revision declares externally grounded.

        The registry schema already constrains each expectation's declaration to
        its own reconciled set, so the intersection is defensive rather than
        narrowing in a well-formed tree.
        """
        return tuple(sorted(set(self.declared_grounded_casilla_ids) & set(self.reconciled_casilla_ids)))

    @property
    def independent_check_coverage(self) -> float:
        """Fraction of this revision's reconciled casillas that are independently checked.

        Coverage of independent checking, never a correctness score: a low
        value means most reconciliation here is the engine agreeing with
        itself, not that the revision computes the wrong answer. Zero when the
        revision reconciles nothing, because no claim is being made at all.
        """
        if not self.reconciled_casilla_ids:
            return 0.0
        return len(self.independently_checked_casilla_ids) / len(self.reconciled_casilla_ids)


class RegistryExternalGroundingAudit(ExternalGroundingModel):
    """Registry-wide external-grounding audit across every modelo revision."""

    rows: tuple[RevisionExternalGroundingRow, ...]
    inventory: ExternalOracleInventory
    unmatched_evidence: tuple[UnattributedOraclePayload, ...]
    registry_validated: bool

    @property
    def findings(self) -> tuple[ExternalGroundingFinding, ...]:
        """Every finding across every row, in row order."""
        return tuple(finding for row in self.rows for finding in row.findings)

    def findings_of_kind(self, kind: ExternalGroundingFindingKind) -> tuple[ExternalGroundingFinding, ...]:
        """Return every finding of ``kind``."""
        return tuple(finding for finding in self.findings if finding.kind == kind)

    @property
    def ok(self) -> bool:
        """Whether the grounding honesty relation holds in both directions."""
        return not self.findings

    @property
    def checked_revision_count(self) -> int:
        """Revisions carrying bundled oracle evidence attributed to them.

        The anti-vacuity floor for the oracle-to-registry direction: a fold
        that attributed nothing would report no findings while checking
        nothing.
        """
        return sum(1 for row in self.rows if row.oracle_evidence_casilla_ids)

    @property
    def declared_grounding_count(self) -> int:
        """Casilla-level grounding claims declared across the registry.

        The anti-vacuity floor for the registry-to-oracle direction.
        """
        return sum(len(row.declared_grounded_casilla_ids) for row in self.rows)

    @property
    def independent_check_coverage(self) -> float:
        """Registry-wide fraction of reconciled casillas that are independently checked.

        Coverage of independent checking, never a correctness score, and never
        a quality ranking between modelos: a revision reconciling two casillas
        against an oracle scores higher than one reconciling two hundred
        against the engine alone, which is the intended reading — the metric
        counts how much is checked by an outside authority, nothing more.
        Counted per ``(revision, casilla)`` pair, since casilla ids repeat
        across modelos and revisions.
        """
        reconciled = sum(len(row.reconciled_casilla_ids) for row in self.rows)
        if not reconciled:
            return 0.0
        checked = sum(len(row.independently_checked_casilla_ids) for row in self.rows)
        return checked / reconciled


def _select_revision_for_filing_year(
    revisions: Sequence[ModeloRevision],
    filing_year: int,
    *,
    period: str | None = None,
) -> ModeloRevision | None:
    """Attribute bundled oracle evidence of a filing coordinate to one revision.

    Tries a direct revision-id match first (the Modelo 100 convention, where
    the revision id IS the filing-year string), then falls back to declared
    ``period_selector`` coverage (the ``<start-year>-y-siguientes`` convention).

    Args:
        revisions: The candidate :class:`ModeloRevision` records of one modelo.
        filing_year: AEAT filing year the bundled oracle evidence was captured
            for.
        period: Optional filing-period code used to disambiguate split-year
            revisions.

    This is deliberately separate from the law-determined
    :func:`select_revision`, which resolves a ``(filing_year, period)`` pair
    and raises when none or several match. A payload without a period remains
    year-only and is left unattributed when split revisions claim that year;
    a payload with an explicit period can be attributed to the one revision
    whose selector covers that period.

    **Module-private, and it must stay that way.** This resolver answers an
    evidence-attribution question ("which revision does this captured oracle
    payload belong to"), never the legal question ("which revision governs
    this filing"). Standing on the registry package facade beside
    :func:`select_revision` it would be one autocomplete away from a
    calculation path that holds only a filing year: that path would silently
    drop the period axis and, on an unresolvable year, receive ``None`` and
    abstain exactly where the law-determined resolver refuses. Abstention is
    the right answer for a governance fold reading captured evidence and the
    wrong answer for anything that computes, verifies, files, or exports. If a
    consumer outside this fold ever genuinely needs it, expose it under a name
    that reads as evidence attribution rather than law — never under this one.

    Returns:
        The single applicable revision, or ``None`` when no revision matches
        or more than one ambiguously claims the year — a registry authoring
        defect this function reports by abstaining rather than adjudicates.
    """
    if period is None:
        year_str = str(filing_year)
        by_id = {revision.id: revision for revision in revisions}
        if year_str in by_id:
            return by_id[year_str]
    matches = [
        revision
        for revision in revisions
        if revision.period_selector.includes_year(filing_year)
        and (period is None or selector_token_for_request(revision.period_selector.periods, period) is not None)
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _build_row(
    *,
    modelo_id: str,
    revision: ModeloRevision,
    inventory: ExternalOracleInventory,
    filing_coordinates: tuple[tuple[int, str | None], ...],
    corpora_for: Mapping[tuple[str, int, str | None], tuple[ExternalOracleCorpus, ...]],
) -> RevisionExternalGroundingRow:
    """Build one revision's grounding row and both directions of its findings."""
    computed = {casilla.id for casilla in revision.casillas if casilla.input_kind is InputKind.COMPUTED}
    reconciled: set[CasillaId] = set()
    declared: set[CasillaId] = set()
    for expectation in revision.verification_expectations:
        reconciled |= set(expectation.computed_casilla_ids)
        reconciled |= set(expectation.reconcile_when_present_casilla_ids)
        declared |= set(expectation.externally_grounded_casilla_ids)

    evidence: set[CasillaId] = set()
    corpora: set[ExternalOracleCorpus] = set()
    for filing_year, period in filing_coordinates:
        evidence |= inventory.casilla_ids_for(modelo_id, filing_year, period)
        corpora.update(corpora_for.get((modelo_id, filing_year, period), ()))

    findings: list[ExternalGroundingFinding] = []
    for casilla_id in sorted(evidence):
        if casilla_id not in computed:
            findings.append(
                ExternalGroundingFinding(
                    kind="oracle_casilla_not_computed",
                    modelo=modelo_id,
                    revision=revision.id,
                    casilla_id=casilla_id,
                    detail=(
                        f"modelo {modelo_id} revision {revision.id}: oracle-grounded casilla {casilla_id} "
                        "is not input_kind=computed"
                    ),
                ),
            )
        elif casilla_id not in reconciled:
            findings.append(
                ExternalGroundingFinding(
                    kind="oracle_casilla_not_enrolled",
                    modelo=modelo_id,
                    revision=revision.id,
                    casilla_id=casilla_id,
                    detail=(
                        f"modelo {modelo_id} revision {revision.id}: oracle-grounded casilla {casilla_id} "
                        "is not enrolled in a verification contract"
                    ),
                ),
            )
    for casilla_id in sorted(declared - evidence):
        findings.append(
            ExternalGroundingFinding(
                kind="declared_grounding_without_oracle_evidence",
                modelo=modelo_id,
                revision=revision.id,
                casilla_id=casilla_id,
                detail=(
                    f"modelo {modelo_id} revision {revision.id}: casilla {casilla_id} is declared "
                    "externally_grounded but no bundled external oracle for an applicable filing year "
                    "carries it in expected_by_casilla_id"
                ),
            ),
        )

    return RevisionExternalGroundingRow(
        modelo=modelo_id,
        revision=revision.id,
        reconciled_casilla_ids=tuple(sorted(reconciled)),
        declared_grounded_casilla_ids=tuple(sorted(declared)),
        oracle_evidence_casilla_ids=tuple(sorted(evidence)),
        evidence_corpora=tuple(sorted(corpora)),
        findings=tuple(findings),
    )


def build_external_grounding_audit(
    modelos: Iterable[ModeloDefinition],
    *,
    inventory: ExternalOracleInventory,
    registry_validated: bool,
) -> RegistryExternalGroundingAudit:
    """Fold ``inventory`` against ``modelos`` into a registry-wide grounding audit.

    Args:
        modelos: Compiled :class:`ModeloDefinition` records to audit, each
            carrying the :class:`ModeloRevision` entries the fold reads. Taken
            from the loaded tree, never from a fragment-directory listing.
        inventory: The bundled oracle evidence to reconcile the registry
            against.
        registry_validated: Whether ``modelos`` came from the validating
            authority. Stamped onto the audit so a degraded read is never
            mistaken for validated authority.
    """
    modelo_tuple = tuple(sorted(modelos, key=lambda item: item.id))
    rows: list[RevisionExternalGroundingRow] = []
    matched_evidence_keys: set[tuple[str, int, str | None]] = set()
    corpora_for = inventory.corpora_for
    attributed_coordinates = inventory.attributed_coordinates

    for modelo in modelo_tuple:
        revisions = tuple(sorted(modelo.revisions.values(), key=lambda item: item.id))
        # Resolved once per modelo rather than once per (revision, filing
        # coordinate): the resolution answers "which revision owns this
        # evidence", so it does not depend on the revision being built.
        resolved_years: dict[str, list[tuple[int, str | None]]] = {}
        for candidate_modelo, filing_year, period in attributed_coordinates:
            if candidate_modelo != modelo.id:
                continue
            owner = _select_revision_for_filing_year(revisions, filing_year, period=period)
            if owner is not None:
                resolved_years.setdefault(owner.id, []).append((filing_year, period))
        for revision in revisions:
            filing_coordinates = tuple(resolved_years.get(revision.id, ()))
            matched_evidence_keys.update((modelo.id, filing_year, period) for filing_year, period in filing_coordinates)
            rows.append(
                _build_row(
                    modelo_id=modelo.id,
                    revision=revision,
                    inventory=inventory,
                    filing_coordinates=filing_coordinates,
                    corpora_for=corpora_for,
                ),
            )

    unmatched = tuple(
        UnattributedOraclePayload(
            corpus=item.corpus,
            payload_name=item.payload_name,
            gap="no_registry_revision_covers_filing_year",
            detail=(
                f"oracle evidence for modelo {item.modelo} filing year {item.filing_year} resolves to no single "
                "registry revision, so its expected values are outside the grounding relation"
            ),
        )
        for item in inventory.evidence
        if (item.modelo, item.filing_year, item.period) not in matched_evidence_keys
    )

    return RegistryExternalGroundingAudit(
        rows=tuple(rows),
        inventory=inventory,
        unmatched_evidence=unmatched,
        registry_validated=registry_validated,
    )
