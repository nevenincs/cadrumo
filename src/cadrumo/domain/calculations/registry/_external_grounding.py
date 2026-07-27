"""Registry-wide external-oracle grounding fold.

Enrollment — every computed casilla named in a ``verification_expectation`` —
is a ceiling. Verification POWER is the narrower count of casillas whose engine
value is reconciled against an AEAT-authoritative expected value that the
application did not itself compute. Two such corpora ship today, enumerated by
:class:`~cadrumo.core.ExternalOracleCorpus`: the Renta WEB Open replay capture
and the AEAT Manual practico worked-example oracles.

This module folds those corpora against the registry tree and emits both
directions of the grounding honesty relation as typed findings:

* an oracle figure exists for a casilla that is not ``input_kind=computed``, or
  is computed but not enrolled in a verification contract — the evidence is
  bundled but stranded, never consumed by the verify gate; and
* a revision DECLARES ``externally_grounded_casilla_ids`` for a casilla that no
  bundled oracle backs for an applicable filing year — a grounding claim with
  no independent AEAT authority behind it.

Both directions were previously computed inside a single pytest module and were
reachable from nowhere else. They are library facts: the same fold answers "how
much of this registry is independently checked" for contributor-facing
governance tooling, and the gate that guards the relation becomes a thin
consumer.

Coverage, not correctness
-------------------------

:attr:`RevisionExternalGroundingRow.independent_check_coverage` and its
registry-wide counterpart measure COVERAGE OF INDEPENDENT CHECKING. A low value
means most of a revision's reconciliation is engine-only — the application
agreeing with itself — not that the revision is wrong; a high value means more
of it is cross-checked against AEAT's own figures, not that it is correct. The
numerator mirrors the per-verdict computation in
:class:`~cadrumo.application.verification.VerificationVerdict` exactly
(declared grounding intersected with the reconciled set), so the registry-wide
signal and the per-filing signal are the same quantity at different scopes.

Reading the registry
--------------------

The fold consumes COMPILED :class:`ModeloDefinition` objects, never a listing
of fragment subdirectories: a subdirectory-blind read of this registry has
twice produced wrong "parse-only" verdicts, which is why revision content is
read from the loaded tree. :func:`audit_bundled_external_grounding` loads that
tree through the non-validating loader and stamps the result
``registry_validated=False``, because a governance read must survive a
concurrently-edited registry that the validating authority would refuse to load
outright. Callers holding a validated authority inject their own definitions
through :func:`build_external_grounding_audit` and stamp the result accordingly;
a row must never be mistaken for validated authority when it was not.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, Field

from ....core import STRICT_FROZEN_CONFIG, CasillaId, ExternalOracleCorpus, validated_casilla_id
from ....core.resources import bundled_path
from ._errors import RegistryValidationError
from ._ids import ModeloId, RevisionId
from ._loader import load_registry_tree
from ._schema import ModeloDefinition, ModeloRevision
from ._schema_input_kind import InputKind

#: Bundled data subtree holding each corpus, relative to the packaged data root.
_ORACLE_CORPUS_DIRECTORIES: Final[Mapping[ExternalOracleCorpus, tuple[str, ...]]] = {
    ExternalOracleCorpus.RENTA_WEB_OPEN_REPLAY: ("corpus", "parity_replays", "renta_web_open"),
    ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE: ("corpus", "manual_oracles"),
}

#: Payload key carrying the per-casilla AEAT-authoritative expected values.
_EXPECTED_BY_CASILLA_ID: Final[str] = "expected_by_casilla_id"

OracleAttributionGap = Literal[
    "payload_name_lacks_modelo_and_filing_year",
    "no_registry_revision_covers_filing_year",
]
"""Why a bundled oracle payload's evidence could not be attributed to a revision."""

ExternalGroundingFindingKind = Literal[
    "oracle_casilla_not_computed",
    "oracle_casilla_not_enrolled",
    "declared_grounding_without_oracle_evidence",
]
"""The grounding honesty relation's failure modes, in both directions."""


class ExternalGroundingModel(BaseModel):
    """Strict frozen base for external-grounding facts."""

    model_config = STRICT_FROZEN_CONFIG


class ExternalOracleEvidence(ExternalGroundingModel):
    """One bundled oracle payload's expected-value inventory, attributed to a filing year.

    Casilla ids renumber across filing years and are scoped per modelo, so a
    captured figure is only a valid grounding claim against its own modelo's
    revision covering its own year. Both axes therefore travel with the
    evidence rather than being inferred at the point of use.
    """

    corpus: ExternalOracleCorpus
    payload_name: str = Field(min_length=1, max_length=255)
    modelo: ModeloId
    filing_year: int = Field(ge=1979, le=2999)
    casilla_ids: tuple[CasillaId, ...]


class UnattributedOraclePayload(ExternalGroundingModel):
    """A bundled oracle payload whose evidence reaches no registry revision.

    Recorded rather than skipped. A payload the fold silently dropped would be
    indistinguishable from one it checked and found clean, and the figures it
    carries would sit outside the honesty relation with nothing reporting their
    absence.
    """

    corpus: ExternalOracleCorpus
    payload_name: str = Field(min_length=1, max_length=255)
    gap: OracleAttributionGap
    detail: str = Field(min_length=1, max_length=512)


class ExternalOracleInventory(ExternalGroundingModel):
    """Every bundled oracle payload, split into attributed evidence and attribution gaps."""

    evidence: tuple[ExternalOracleEvidence, ...]
    unattributed_payloads: tuple[UnattributedOraclePayload, ...]

    def casilla_ids_for(self, modelo: str, filing_year: int) -> frozenset[CasillaId]:
        """Return every oracle-grounded casilla id bundled for ``modelo`` and ``filing_year``.

        Unions across corpora: a manual worked-example figure is an equally
        real, independent AEAT authority alongside a simulator replay capture.
        """
        return frozenset(
            casilla_id
            for item in self.evidence
            if item.modelo == modelo and item.filing_year == filing_year
            for casilla_id in item.casilla_ids
        )

    @property
    def corpora_for(self) -> Mapping[tuple[str, int], tuple[ExternalOracleCorpus, ...]]:
        """Map each attributed ``(modelo, filing_year)`` to the corpora backing it."""
        grouped: dict[tuple[str, int], set[ExternalOracleCorpus]] = {}
        for item in self.evidence:
            grouped.setdefault((item.modelo, item.filing_year), set()).add(item.corpus)
        return {key: tuple(sorted(value)) for key, value in grouped.items()}

    @property
    def attributed_filing_years(self) -> tuple[tuple[str, int], ...]:
        """Every ``(modelo, filing_year)`` key carrying bundled oracle evidence."""
        return tuple(sorted({(item.modelo, item.filing_year) for item in self.evidence}))


class ExternalGroundingFinding(ExternalGroundingModel):
    """One breach of the grounding honesty relation, in either direction."""

    kind: ExternalGroundingFindingKind
    modelo: ModeloId
    revision: RevisionId
    casilla_id: CasillaId
    detail: str = Field(min_length=1, max_length=512)


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

        Mirrors the per-verdict intersection in
        :class:`~cadrumo.application.verification.VerificationVerdict`; the
        registry schema already constrains each expectation's declaration to
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


def load_bundled_external_oracle_inventory() -> ExternalOracleInventory:
    """Inventory every bundled external-oracle payload across both corpora.

    Returns:
        An :class:`ExternalOracleInventory` carrying the attributed evidence
        and every payload whose evidence could not be attributed.
    """
    evidence: list[ExternalOracleEvidence] = []
    unattributed: list[UnattributedOraclePayload] = []
    for corpus, parts in _ORACLE_CORPUS_DIRECTORIES.items():
        directory = Path(bundled_path(*parts))
        for payload_path in sorted(directory.glob("modelo-*.json")):
            record = _read_oracle_payload(corpus, payload_path)
            if isinstance(record, UnattributedOraclePayload):
                unattributed.append(record)
            else:
                evidence.append(record)
    return ExternalOracleInventory(
        evidence=tuple(evidence),
        unattributed_payloads=tuple(unattributed),
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
    matched_evidence_keys: set[tuple[str, int]] = set()
    corpora_for = inventory.corpora_for

    for modelo in modelo_tuple:
        revisions = tuple(sorted(modelo.revisions.values(), key=lambda item: item.id))
        for revision in revisions:
            filing_years = tuple(
                filing_year
                for candidate_modelo, filing_year in inventory.attributed_filing_years
                if candidate_modelo == modelo.id and select_revision_for_filing_year(revisions, filing_year) is revision
            )
            matched_evidence_keys.update((modelo.id, filing_year) for filing_year in filing_years)
            rows.append(
                _build_row(
                    modelo_id=modelo.id,
                    revision=revision,
                    inventory=inventory,
                    filing_years=filing_years,
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
        if (item.modelo, item.filing_year) not in matched_evidence_keys
    )

    return RegistryExternalGroundingAudit(
        rows=tuple(rows),
        inventory=inventory,
        unmatched_evidence=unmatched,
        registry_validated=registry_validated,
    )


def audit_bundled_external_grounding() -> RegistryExternalGroundingAudit:
    """Audit external grounding across the bundled registry tree.

    Uses the non-validating loader, so a governance read survives a
    concurrently-edited registry that the validating authority would refuse
    outright. The returned audit is stamped ``registry_validated=False``
    accordingly.
    """
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return build_external_grounding_audit(
        modelos,
        inventory=load_bundled_external_oracle_inventory(),
        registry_validated=False,
    )


def select_revision_for_filing_year(
    revisions: Sequence[ModeloRevision],
    filing_year: int,
) -> ModeloRevision | None:
    """Resolve the single :class:`ModeloRevision` applicable to ``filing_year``.

    Tries a direct revision-id match first (the Modelo 100 convention, where
    the revision id IS the filing-year string), then falls back to declared
    ``period_selector`` coverage (the ``<start-year>-y-siguientes`` convention).

    Args:
        revisions: The candidate :class:`ModeloRevision` records of one modelo.
        filing_year: AEAT filing year the bundled oracle evidence was captured
            for.

    Deliberately period-agnostic and total, unlike the law-determined
    :func:`select_revision`, which resolves a ``(filing_year, period)`` pair
    and raises when none or several match. Oracle evidence is captured per
    filing year with no period axis, and a governance fold must report an
    unresolvable year rather than abort the whole registry read on it.

    Returns:
        The single applicable revision, or ``None`` when no revision matches
        or more than one ambiguously claims the year — a registry authoring
        defect this function reports by abstaining rather than adjudicates.
    """
    year_str = str(filing_year)
    by_id = {revision.id: revision for revision in revisions}
    if year_str in by_id:
        return by_id[year_str]
    matches = [revision for revision in revisions if revision.period_selector.includes_year(filing_year)]
    if len(matches) == 1:
        return matches[0]
    return None


def _build_row(
    *,
    modelo_id: str,
    revision: ModeloRevision,
    inventory: ExternalOracleInventory,
    filing_years: tuple[int, ...],
    corpora_for: Mapping[tuple[str, int], tuple[ExternalOracleCorpus, ...]],
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
    for filing_year in filing_years:
        evidence |= inventory.casilla_ids_for(modelo_id, filing_year)
        corpora.update(corpora_for.get((modelo_id, filing_year), ()))

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


def _read_oracle_payload(
    corpus: ExternalOracleCorpus,
    payload_path: Path,
) -> ExternalOracleEvidence | UnattributedOraclePayload:
    """Read one ``modelo-<id>-<year>-<scenario>.json`` payload into typed evidence.

    The payload's own ``modelo`` and ``filing_year`` fields are authoritative
    when present and are cross-checked against the filename-derived values, so
    a misnamed file cannot silently misattribute its evidence. The Renta WEB
    Open replays declare neither field, hence the filename fallback.
    """
    parts = payload_path.stem.split("-")
    if len(parts) < 3 or parts[0] != "modelo" or not parts[1] or not parts[2].isdigit():
        return UnattributedOraclePayload(
            corpus=corpus,
            payload_name=payload_path.name,
            gap="payload_name_lacks_modelo_and_filing_year",
            detail=(
                f"{payload_path.name}: name does not encode modelo-<id>-<filing-year>, so its expected values "
                "cannot be attributed to a modelo revision"
            ),
        )
    filename_modelo_id = parts[1]
    filename_year = int(parts[2])
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    declared_modelo_id = str(payload.get("modelo", filename_modelo_id)).strip() or filename_modelo_id
    declared_year_value = payload.get("filing_year", filename_year)
    declared_year = int(declared_year_value) if declared_year_value is not None else filename_year
    if declared_modelo_id != filename_modelo_id:
        raise RegistryValidationError(
            f"{payload_path.name}: payload modelo {declared_modelo_id!r} does not match filename modelo "
            f"{filename_modelo_id!r}",
        )
    if declared_year != filename_year:
        raise RegistryValidationError(
            f"{payload_path.name}: payload filing_year {declared_year!r} does not match filename year "
            f"{filename_year!r}",
        )
    expected = payload.get(_EXPECTED_BY_CASILLA_ID, {})
    casilla_ids = tuple(
        sorted(validated_casilla_id(key, surface=f"{payload_path.name}.{_EXPECTED_BY_CASILLA_ID}") for key in expected),
    )
    return ExternalOracleEvidence(
        corpus=corpus,
        payload_name=payload_path.name,
        modelo=declared_modelo_id,
        filing_year=declared_year,
        casilla_ids=casilla_ids,
    )
