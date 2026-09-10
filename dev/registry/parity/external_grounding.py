"""Registry-wide external-oracle grounding fold.

Development tooling. This fold is a quality signal over the registry tree,
not a product capability, and it does not ship with the package.

Enrollment -- every computed casilla named in a ``verification_expectation`` --
is a ceiling. Verification POWER is the narrower count of casillas whose engine
value is reconciled against an AEAT-authoritative expected value that the
application did not itself compute. Two such corpora exist today, enumerated
by :class:`ExternalOracleCorpus`: the Renta WEB Open replay captures, which
are repository-only development artefacts covering 2025 Modelo 100 alone,
and the AEAT Manual practico worked-example oracles, which are packaged data.

This module folds those corpora against the registry tree and emits both
directions of the grounding honesty relation as typed findings:

* an oracle figure exists for a casilla that is not ``input_kind=computed``, or
  is computed but not enrolled in a verification contract -- the evidence is
  present but stranded, never consumed by the verify gate; and
* a revision DECLARES ``externally_grounded_casilla_ids`` for a casilla that no
  oracle payload backs for an applicable filing year -- a grounding claim with
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
means most of a revision's reconciliation is engine-only -- the application
agreeing with itself -- not that the revision is wrong; a high value means more
of it is cross-checked against AEAT's own figures, not that it is correct. The
numerator is the declared grounding intersected with the reconciled set, so the
registry-wide signal is computed directly from canonical registry facts.

Reading the corpora
-------------------

Every payload is parsed through its corpus's own strict frozen model
(:class:`ManualWorkedExamplePayload`, :class:`RentaWebOpenReplayPayload`), never
as an untyped mapping. That is what makes the ``source_kind`` token
load-bearing: the manual corpus declares it, it hydrates to an
:class:`ExternalOracleCorpus` member, and it is cross-checked
against the directory the file was found in. A payload declaring a corpus other
than its directory's is refused by name rather than reclassified to whichever
corpus owns the directory -- a silent reclassification would put a provenance on
``evidence_corpora`` that the figures do not have.

Reading the registry
--------------------

The fold consumes COMPILED :class:`ModeloDefinition` objects, never a listing
of fragment subdirectories: a subdirectory-blind read of this registry has
twice produced wrong "parse-only" verdicts, which is why revision content is
read from the loaded tree. The development audit loads that
tree through the non-validating loader and stamps the result
``registry_validated=False``, because a governance read must survive a
concurrently-edited registry that the validating authority would refuse to load
outright. Callers holding a validated authority inject their own definitions
through :func:`build_external_grounding_audit` and stamp the result accordingly;
a row must never be mistaken for validated authority when it was not.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, model_validator

from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.filing_year import FilingYear
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.core.period import RegistrySelectorPeriodCode
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import ModeloId

from .external_oracle_corpus import ExternalOracleCorpus


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

"""Why a bundled oracle payload's evidence could not be attributed to a revision.

``payload_name_lacks_modelo_and_filing_year`` is reached only when BOTH readings
are silent: the payload declares no modelo and filing year of its own AND its
name does not encode them. A payload declaring either axis is attributed from
what it declares, so the name is a cross-check rather than the sole key.
"""

"""The grounding honesty relation's failure modes, in both directions."""


class ExternalGroundingModel(BaseModel):
    """Strict frozen base for external-grounding facts."""

    model_config = STRICT_FROZEN_CONFIG


#: Bounds on a bundled oracle payload's ``raw_evidence_locator``, declared once.
#:
#: The generic :class:`~dev.registry.parity.live_parity.ReplayPayload` that
#: every
#: checker-style driver decodes through is deliberately looser -- it makes the
#: locator optional and caps it at 512 -- because not every replay surface
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

    Only the genuine intersection lives here -- where the evidence came from,
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

    A worked-example payload used to pin only the OUTPUT -- the locator and
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
    -- that one addresses the FIGURE. ``locator_by_casilla_id`` refines it per
    input, because a reviewer verifying one box against the manual needs the
    line that box came from, and an input assembled from several printed line
    items (two income rows folded into one registry box) has no single line the
    block locator could imply.

    Attributes:
        corpus_locator: Where the worked example states the facts below.
        by_casilla_id: The input value per casilla, as printed.
        locator_by_casilla_id: The line reference each input was read from.
            Must cover exactly the same casillas as ``by_casilla_id`` -- an
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
    reads. Optional-and-unenumerated would be the worse outcome -- the contract
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
    that ever grows a token -- an optional field is where a check quietly stops
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


#: The grounding ``detail`` annotation: elides rather than refusing.
#:
#: Both carriers interpolate registry ids -- modelo, revision, casilla, payload
#: name -- whose combined length is a property of the registry rather than of
#: the sentence. Refusing one would abort the honesty audit at the point it had
#: a breach to report, which is the one moment it must not fail.
