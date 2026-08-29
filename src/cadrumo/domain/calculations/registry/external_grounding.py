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
numerator is the declared grounding intersected with the reconciled set, so the
registry-wide signal is computed directly from canonical registry facts.

Reading the corpora
-------------------

Every bundled payload is parsed through its corpus's own strict frozen model
(:class:`ManualWorkedExamplePayload`, :class:`RentaWebOpenReplayPayload`), never
as an untyped mapping. That is what makes the ``source_kind`` token
load-bearing: the manual corpus declares it, it hydrates to an
:class:`~cadrumo.core.ExternalOracleCorpus` member, and it is cross-checked
against the directory the file was found in. A payload declaring a corpus other
than its directory's is refused by name rather than reclassified to whichever
corpus owns the directory — a silent reclassification would put a provenance on
``evidence_corpora`` that the figures do not have.

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
from typing import Annotated, Final, Literal

from pydantic import BaseModel, BeforeValidator, Field, ValidationError, model_validator

from ....core import (
    STRICT_FROZEN_CONFIG,
    CasillaId,
    ElidedProse,
    ExternalOracleCorpus,
    RegistrySelectorPeriodCode,
)
from ....core.directory_scan import (
    scan_directory,
)
from ....core.external_constants import UTF_8_ENCODING
from ....core.filing_year import FilingYear
from ....core.resources import bundled_path
from .errors import RegistryValidationError
from .ids import ModeloId, RevisionId
from .loader import load_registry_tree
from .period_selector_match import selector_token_for_request
from .schema import ModeloDefinition, ModeloRevision
from .schema_input_kind import InputKind

#: Bundled data subtree holding each corpus, relative to the packaged data root.
_ORACLE_CORPUS_DIRECTORIES: Final[Mapping[ExternalOracleCorpus, tuple[str, ...]]] = {
    ExternalOracleCorpus.RENTA_WEB_OPEN_REPLAY: ("corpus", "parity_replays", "renta_web_open"),
    ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE: ("corpus", "manual_oracles"),
}


def _coerce_external_oracle_corpus(value: object) -> object:
    """Coerce a stored ``source_kind`` token to its canonical corpus member.

    The bundled payloads are JSON, so the corpus arrives as a plain string
    while the schema is strict. This is the boundary hydration that makes the
    stored token load-bearing: an unrecognised token is refused here, with the
    accepted set enumerated, rather than reaching the fold as free text.
    """
    if isinstance(value, ExternalOracleCorpus):
        return value
    if isinstance(value, str):
        try:
            return ExternalOracleCorpus(value)
        except ValueError:
            raise RegistryValidationError(
                f"source_kind {value!r} is not a recognised ExternalOracleCorpus member; "
                f"expected one of {[member.value for member in ExternalOracleCorpus]}",
            ) from None
    raise RegistryValidationError(f"source_kind must be a string, got {type(value).__name__!r}")


ExternalOracleCorpusValue = Annotated[ExternalOracleCorpus, BeforeValidator(_coerce_external_oracle_corpus)]
"""Annotated :class:`ExternalOracleCorpus` that hydrates a stored JSON token."""

OracleAttributionGap = Literal[
    "payload_name_lacks_modelo_and_filing_year",
    "no_registry_revision_covers_filing_year",
]
"""Why a bundled oracle payload's evidence could not be attributed to a revision.

``payload_name_lacks_modelo_and_filing_year`` is reached only when BOTH readings
are silent: the payload declares no modelo and filing year of its own AND its
name does not encode them. A payload declaring either axis is attributed from
what it declares, so the name is a cross-check rather than the sole key.
"""

ExternalGroundingFindingKind = Literal[
    "oracle_casilla_not_computed",
    "oracle_casilla_not_enrolled",
    "declared_grounding_without_oracle_evidence",
]
"""The grounding honesty relation's failure modes, in both directions."""


class ExternalGroundingModel(BaseModel):
    """Strict frozen base for external-grounding facts."""

    model_config = STRICT_FROZEN_CONFIG


#: Bounds on a bundled oracle payload's ``raw_evidence_locator``, declared once.
#:
#: The generic :class:`~domain.calculations.registry._live_parity.ReplayPayload`
#: that every
#: checker-style driver decodes through is deliberately looser — it makes the
#: locator optional and caps it at 512 — because not every replay surface
#: carries bundled-corpus evidence. The Renta WEB Open corpus is read by BOTH
#: contracts, so these bounds are exported and re-applied at the Renta driver
#: rather than restated there: a capture that satisfies grounding must not fail
#: live replay, and one that skips the evidence locator entirely must not pass
#: the driver while grounding would refuse it.
BUNDLED_ORACLE_EVIDENCE_LOCATOR_MIN_LENGTH = 1
BUNDLED_ORACLE_EVIDENCE_LOCATOR_MAX_LENGTH = 1024


def require_bundled_oracle_evidence_locator(
    raw_evidence_locator: str | None,
    *,
    surface_label: str,
) -> str:
    """Hold a decoded replay document to the bundled-oracle evidence contract.

    Applies the same locator bounds :class:`BundledOraclePayload` enforces on
    the grounding side, and makes the locator required, so a capture cannot
    ground as bundled evidence while reaching a replay driver with no
    provenance at all.

    The expected-value map is deliberately NOT required here: a replay driver
    reads the OBSERVED figures and receives the expected ones as a separate
    argument, so a hand-written non-corpus capture legitimately omits it. Only
    the evidence axis is shared between the two contracts.

    Returns:
        The validated ``raw_evidence_locator``.

    Raises:
        RegistryValidationError: When the locator is absent or out of bounds.
    """
    if raw_evidence_locator is None:
        raise RegistryValidationError(
            f"{surface_label} payload must declare raw_evidence_locator",
        )
    locator_length = len(raw_evidence_locator)
    if not (BUNDLED_ORACLE_EVIDENCE_LOCATOR_MIN_LENGTH <= locator_length <= BUNDLED_ORACLE_EVIDENCE_LOCATOR_MAX_LENGTH):
        raise RegistryValidationError(
            f"{surface_label} raw_evidence_locator must be between "
            f"{BUNDLED_ORACLE_EVIDENCE_LOCATOR_MIN_LENGTH} and "
            f"{BUNDLED_ORACLE_EVIDENCE_LOCATOR_MAX_LENGTH} characters, got {locator_length}",
        )
    return raw_evidence_locator


class BundledOraclePayload(ExternalGroundingModel):
    """What every bundled oracle payload carries, whichever corpus holds it.

    The corpus files are read through a model rather than as an untyped
    mapping, so every axis the fold consumes is validated once at the boundary
    and an undeclared key is refused rather than ignored.

    Only the genuine intersection lives here — where the evidence came from,
    and the figures themselves. The attribution axes are corpus-dependent and
    are declared by each corpus's own model, never narrowed from an optional
    base field: the manual worked-example payloads state their modelo, filing
    year, and corpus token outright, while the Renta WEB Open replays state
    none of the three.
    """

    raw_evidence_locator: str = Field(
        min_length=BUNDLED_ORACLE_EVIDENCE_LOCATOR_MIN_LENGTH,
        max_length=BUNDLED_ORACLE_EVIDENCE_LOCATOR_MAX_LENGTH,
    )
    expected_by_casilla_id: Mapping[CasillaId, str]
    period: RegistrySelectorPeriodCode | None = None
    """Optional period coordinate when a filing year has multiple revisions."""


class DeclaredScenarioInputs(ExternalGroundingModel):
    """The taxpayer facts a worked example is built FROM, declared beside its figures.

    A worked-example payload used to pin only the OUTPUT — the locator and
    ``expected_by_casilla_id``. The facts that make the example *that* example
    lived solely in hand-written test fixtures, so a fixture could reach the
    manual's printed number from a scenario the manual never states, and pass
    while looking AEAT-grounded. Three tests did exactly that: a proration that
    bound on the wrong term, an oracle built on a child two years younger than
    the manual's, and a death-in-period suite whose birth dates made the case it
    named unreachable. Each passed before and after the defect it guarded.

    What declaring inputs BUYS, precisely:

    * The facts become ONE reviewable declaration sitting beside a corpus
      locator, instead of scattered across a fixture nobody diffs against the
      manual.
    * The fixture-matches-declaration link becomes MECHANICAL: a consuming test
      builds its inputs from this block, so the two cannot drift apart.

    What it does NOT buy, and must not be read as: **this does not prove the
    declared inputs are the manual's inputs.** A wrong transcription declared
    here is still a wrong transcription, and it will now be wrong in one place
    rather than two. The locators exist so a reviewer can check that claim
    against the printed page; nothing mechanical checks it for them.

    ``corpus_locator`` addresses where the case's INPUTS are printed, which is
    not the same question as :attr:`BundledOraclePayload.raw_evidence_locator`
    — that one addresses the FIGURE. ``locator_by_casilla_id`` refines it per
    input, because a reviewer verifying one box against the manual needs the
    line that box came from, and an input assembled from several printed line
    items (two income rows folded into one registry box) has no single line the
    block locator could imply.

    Attributes:
        corpus_locator: Where the worked example states the facts below.
        by_casilla_id: The input value per casilla, as printed.
        locator_by_casilla_id: The line reference each input was read from.
            Must cover exactly the same casillas as ``by_casilla_id`` — an
            input with no locator is unreviewable, and a locator with no input
            names a fact the scenario does not use.
    """

    corpus_locator: str = Field(
        min_length=BUNDLED_ORACLE_EVIDENCE_LOCATOR_MIN_LENGTH,
        max_length=BUNDLED_ORACLE_EVIDENCE_LOCATOR_MAX_LENGTH,
    )
    by_casilla_id: Mapping[CasillaId, str] = Field(min_length=1)
    locator_by_casilla_id: Mapping[CasillaId, str] = Field(min_length=1)

    @model_validator(mode="after")
    def _every_declared_input_carries_its_own_locator(self) -> DeclaredScenarioInputs:
        """Refuse a declaration a reviewer could not check against the page."""
        inputs = set(self.by_casilla_id)
        locators = set(self.locator_by_casilla_id)
        if inputs != locators:
            missing = sorted(inputs - locators)
            orphaned = sorted(locators - inputs)
            raise ValueError(
                "declared_inputs: by_casilla_id and locator_by_casilla_id must cover the "
                f"same casillas (inputs without a locator: {missing}; "
                f"locators without an input: {orphaned})",
            )
        return self


class ManualWorkedExamplePayload(BundledOraclePayload):
    """An AEAT Manual practico worked-example oracle payload.

    Every attribution axis is declared by this corpus, including the
    ``source_kind`` token whose value is byte-identical to its
    :class:`~cadrumo.core.ExternalOracleCorpus` member, so an unknown token
    fails enum hydration and a known-but-wrong token fails the directory
    cross-check in :func:`_parse_oracle_payload`.

    ``declared_inputs`` is optional at the MODEL boundary and not optional in
    practice: a payload that omits it must be enrolled, with a stated reason, in
    the un-migrated registry that
    :mod:`~domain.calculations.registry.tests.test_manual_oracle_declared_inputs`
    reads. Optional-and-unenumerated would be the worse outcome — the contract
    would appear to cover inputs while most payloads quietly did not, which is
    harder to see than today's uniform absence.
    """

    modelo: ModeloId
    filing_year: FilingYear
    source_kind: ExternalOracleCorpusValue
    scenario_id: str = Field(min_length=1, max_length=255)
    notes: str = Field(min_length=1, max_length=16384)
    declared_inputs: DeclaredScenarioInputs | None = None


class RentaWebOpenReplayPayload(BundledOraclePayload):
    """A Renta WEB Open open-simulator replay capture.

    Carries the simulator's own rendered labels alongside the casilla-keyed
    projection, and the AS-OBSERVED figures beside the expected ones, so the
    capture stays auditable against the live surface it was taken from.

    This corpus declares no ``source_kind``, modelo, or filing year: the corpus
    directory and the payload filename carry those axes. They are modelled as
    optional rather than absent so the corpus cross-check still binds a replay
    that ever grows a token — an optional field is where a check quietly stops
    applying. They are NOT given a value-bearing default, which would answer
    the cross-check with the very token it verifies.
    """

    modelo: ModeloId | None = None
    filing_year: FilingYear | None = None
    source_kind: ExternalOracleCorpusValue | None = None
    scenario_id: str | None = Field(default=None, min_length=1, max_length=255)
    expected: Mapping[str, str]
    observed: Mapping[str, str]
    observed_by_casilla_id: Mapping[CasillaId, str]
    profile_overrides: Mapping[str, str] | None = None


#: Every corpus's payload model, as one union the reader can attribute from.
type OraclePayload = ManualWorkedExamplePayload | RentaWebOpenReplayPayload

#: The strict model each corpus's payloads are parsed through.
_ORACLE_PAYLOAD_MODELS: Final[Mapping[ExternalOracleCorpus, type[OraclePayload]]] = {
    ExternalOracleCorpus.RENTA_WEB_OPEN_REPLAY: RentaWebOpenReplayPayload,
    ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE: ManualWorkedExamplePayload,
}


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
    filing_year: FilingYear
    period: RegistrySelectorPeriodCode | None = None
    casilla_ids: tuple[CasillaId, ...]


#: The grounding ``detail`` annotation: elides rather than refusing.
#:
#: Both carriers interpolate registry ids — modelo, revision, casilla, payload
#: name — whose combined length is a property of the registry rather than of
#: the sentence. Refusing one would abort the honesty audit at the point it had
#: a breach to report, which is the one moment it must not fail.
_GroundingDetail = Annotated[str, ElidedProse(512)]


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
    detail: _GroundingDetail


class ExternalOracleInventory(ExternalGroundingModel):
    """Every bundled oracle payload, split into attributed evidence and attribution gaps."""

    evidence: tuple[ExternalOracleEvidence, ...]
    unattributed_payloads: tuple[UnattributedOraclePayload, ...]

    def casilla_ids_for(
        self,
        modelo: str,
        filing_year: int,
        period: str | None = None,
    ) -> frozenset[CasillaId]:
        """Return every oracle-grounded casilla id bundled for ``modelo`` and ``filing_year``.

        Unions across corpora: a manual worked-example figure is an equally
        real, independent AEAT authority alongside a simulator replay capture.
        """
        return frozenset(
            casilla_id
            for item in self.evidence
            if item.modelo == modelo and item.filing_year == filing_year and item.period == period
            for casilla_id in item.casilla_ids
        )

    @property
    def corpora_for(self) -> Mapping[tuple[str, int, str | None], tuple[ExternalOracleCorpus, ...]]:
        """Map each attributed ``(modelo, filing_year, period)`` to its corpora."""
        grouped: dict[tuple[str, int, str | None], set[ExternalOracleCorpus]] = {}
        for item in self.evidence:
            grouped.setdefault((item.modelo, item.filing_year, item.period), set()).add(item.corpus)
        return {key: tuple(sorted(value)) for key, value in grouped.items()}

    @property
    def attributed_coordinates(self) -> tuple[tuple[str, int, str | None], ...]:
        """Every ``(modelo, filing_year, period)`` carrying bundled evidence."""
        return tuple(sorted({(item.modelo, item.filing_year, item.period) for item in self.evidence}))

    @property
    def attributed_filing_years(self) -> tuple[tuple[str, int], ...]:
        """Every ``(modelo, filing_year)`` carrying bundled oracle evidence."""
        return tuple(sorted({(modelo, year) for modelo, year, _period in self.attributed_coordinates}))


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
        for payload_path in scan_directory(directory, pattern="modelo-*.json"):
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


def _parse_oracle_payload(
    corpus: ExternalOracleCorpus,
    payload_path: Path,
) -> OraclePayload:
    """Parse one bundled payload through its corpus's strict model.

    Two refusals live here, both loud and neither tolerant of a shape nothing
    ships today. The model itself refuses a payload missing a field its corpus
    declares, carrying an undeclared key, or naming a ``source_kind`` outside
    :class:`~cadrumo.core.ExternalOracleCorpus`. The cross-check then refuses a
    payload whose declared corpus token contradicts the directory it was found
    in — the case a directory-keyed read would silently reclassify, reporting a
    provenance the figures do not have.

    Args:
        corpus: The corpus the containing directory belongs to, per
            :data:`_ORACLE_CORPUS_DIRECTORIES`.
        payload_path: The payload file to read.

    Raises:
        RegistryValidationError: When the payload violates its corpus's model,
            or declares a corpus token other than ``corpus``.
    """
    model = _ORACLE_PAYLOAD_MODELS[corpus]
    try:
        payload = model.model_validate(json.loads(payload_path.read_text(encoding=UTF_8_ENCODING)))
    except ValidationError as exc:
        raise RegistryValidationError(
            f"{payload_path.name}: bundled oracle payload does not satisfy {model.__name__}: {exc}",
        ) from exc
    if payload.source_kind is not None and payload.source_kind is not corpus:
        raise RegistryValidationError(
            f"{payload_path.name}: declared source_kind {payload.source_kind.value!r} contradicts the corpus "
            f"directory {payload_path.parent.name!r}, which holds the {corpus.value!r} corpus",
        )
    return payload


def _attribution_from_payload_name(payload_path: Path) -> tuple[ModeloId | None, int | None]:
    """Read the ``modelo-<id>-<year>-<scenario>.json`` naming convention off a payload.

    Returns ``(None, None)`` when the name does not follow the convention. The
    two axes are read together because the convention encodes them together: a
    name that fails the shape carries neither, so there is no partial reading to
    salvage.
    """
    parts = payload_path.stem.split("-")
    if len(parts) < 3 or parts[0] != "modelo" or not parts[1] or not parts[2].isdigit():
        return (None, None)
    return (parts[1], int(parts[2]))


def _read_oracle_payload(
    corpus: ExternalOracleCorpus,
    payload_path: Path,
) -> ExternalOracleEvidence | UnattributedOraclePayload:
    """Read one bundled payload into typed evidence, attributed to a modelo and year.

    Every payload is parsed through its corpus's strict model first, including
    one that cannot be attributed at all: a file the fold cannot place is still
    a file whose contents must be well-formed, and validating only the
    attributable ones would leave the boundary open exactly where the least is
    known about the payload.

    Attribution reads the DECLARED axes first and falls back to the
    ``modelo-<id>-<year>-<scenario>.json`` naming convention, rather than
    keying on the name alone. Both are real statements of the same fact, and a
    payload declaring its modelo and filing year has said where its figures
    belong whatever it is called; keying solely on the name made a naming slip
    silently demote a fully self-describing payload to an attribution gap, where
    its AEAT figures sit outside both directions of the honesty relation. The
    Renta WEB Open replays declare neither axis, so the name remains the only
    reading for that corpus.

    Where both sources speak, they must agree. A disagreement is refused by
    name, quoting both readings, rather than resolved by preferring one side:
    the two disagree only when one of them is wrong, and which one is wrong is
    not something this function can know. Silently taking the declared value
    would attribute figures to a revision the file's own name denies.
    """
    payload = _parse_oracle_payload(corpus, payload_path)
    name_modelo_id, name_filing_year = _attribution_from_payload_name(payload_path)
    if payload.modelo is not None and name_modelo_id is not None and payload.modelo != name_modelo_id:
        raise RegistryValidationError(
            f"{payload_path.name}: payload modelo {payload.modelo!r} does not match filename modelo {name_modelo_id!r}",
        )
    if payload.filing_year is not None and name_filing_year is not None and payload.filing_year != name_filing_year:
        raise RegistryValidationError(
            f"{payload_path.name}: payload filing_year {payload.filing_year!r} does not match filename year "
            f"{name_filing_year!r}",
        )
    modelo_id = payload.modelo if payload.modelo is not None else name_modelo_id
    filing_year = payload.filing_year if payload.filing_year is not None else name_filing_year
    if modelo_id is None or filing_year is None:
        return UnattributedOraclePayload(
            corpus=corpus,
            payload_name=payload_path.name,
            gap="payload_name_lacks_modelo_and_filing_year",
            detail=(
                f"{payload_path.name}: the payload declares no modelo and filing year and its name does not "
                "encode modelo-<id>-<filing-year>, so its expected values cannot be attributed to a modelo "
                "revision"
            ),
        )
    return ExternalOracleEvidence(
        corpus=corpus,
        payload_name=payload_path.name,
        modelo=modelo_id,
        filing_year=filing_year,
        period=payload.period,
        casilla_ids=tuple(sorted(payload.expected_by_casilla_id)),
    )
