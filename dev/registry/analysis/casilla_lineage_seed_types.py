"""Typed lineage plans, refusal states, and evidence bounds."""

from __future__ import annotations

import collections
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition


class LineageRefusalCategory(StrEnum):
    """Why the seeder declined to write a lineage disposition for a successor row.

    The closed vocabulary of every reason a row is refused, named once so the
    seeder, the ledger it writes and the tests reading either share one
    spelling per reason rather than repeating the token inline.
    """

    NOT_EXAMINED = "not_examined"
    ABSENCE_UNCLASSIFIED = "absence_unclassified"
    ABSENCE_UNLOCALISED = "absence_unlocalised"
    RULING_REFUSES_BARE = "ruling_refuses_bare"
    POSITIONAL_HOLD = "positional_hold"
    PARTIAL_STAMP = "partial_stamp"
    CHAIN_CONTRACT = "chain_contract"
    PRINTED_BOX_FORK = "printed_box_fork"
    GROUNDED_UNLOCALISED = "grounded_unlocalised"
    GROUNDED_BLOCKED = "grounded_blocked"
    HELD = "held"
    WITHHELD = "withheld"
    MERGED = "merged"
    ROLE_ABSENT = "role_absent"
    CONTRADICTED = "contradicted"


@dataclass(frozen=True, slots=True)
class ExcludedModelo:
    """A modelo this seeder never writes, and how its unresolved rows are recorded.

    ``residual_category`` is the ledger category every unresolved successor row
    of the modelo is refused under, unless an adjudicated ruling names the row
    more precisely. ``None`` means the modelo can have no unresolved successor
    row at all, so finding one is an error rather than a refusal.
    """

    reason: str
    residual_category: LineageRefusalCategory | None
    residual_reason: str


_M100_REASON = (
    "no in-registry oracle: no export surface, byte span or form_number, and semantic_role labels a grid "
    "column; box reassignment under stable identifiers is proven at scale, so nothing is seeded mechanically"
)

EXCLUDED_MODELOS: Mapping[str, ExcludedModelo] = {
    "100": ExcludedModelo(
        reason=_M100_REASON,
        residual_category=LineageRefusalCategory.NOT_EXAMINED,
        residual_reason=f"not examined; its lineage is its own campaign: {_M100_REASON}",
    ),
    "309": ExcludedModelo(
        reason=(
            "its lineage is grounded by adjudication against the official record designs, including a printed box "
            "number that moved from the record-design metadata into form_number, rather than seeded"
        ),
        residual_category=LineageRefusalCategory.ABSENCE_UNCLASSIFIED,
        residual_reason=(
            "residual after adjudication against the official record designs: no ruling chains this row or names "
            "which kind of absence it is"
        ),
    ),
    "369": ExcludedModelo(
        reason="the editions are parallel schemes sharing one validity window, not a temporal sequence",
        residual_category=None,
        residual_reason="every edition declares that it has no predecessor edition",
    ),
}

_EVIDENCE_ADVISORY = 512


def _schema_evidence_limit() -> int:
    """The maximum length the casilla row model accepts for ``continuidad_evidence``.

    Read off the model rather than restated here, so the seeder's bound is the
    one that will actually refuse the value and cannot drift from it.
    """
    for constraint in CasillaDefinition.model_fields["continuidad_evidence"].metadata:
        limit = getattr(constraint, "max_length", None)
        if limit is not None:
            return int(limit)
    raise ValueError("CasillaDefinition.continuidad_evidence declares no maximum length")


SCHEMA_EVIDENCE_LIMIT = _schema_evidence_limit()


@dataclass(frozen=True, slots=True)
class Refusal:
    """One row the seeder declined to write, with the reason it stops."""

    modelo: str
    revision: str
    casilla_id: str
    category: LineageRefusalCategory
    reason: str
    predecessor: str | None = None


@dataclass(frozen=True, slots=True)
class LongEvidence:
    """One row whose evidence runs past the advisory length but stays within the schema's cap.

    Written, not refused: the schema is the bound, and cutting a checkable
    citation to a house style loses the one thing the evidence is for. Reported
    so an unusually long citation is visible without opening the ledger.
    """

    modelo: str
    revision: str
    casilla: str
    length: int


@dataclass(slots=True)
class LineagePlan:
    """Every disposition for one modelo, plus the key edits that realise them."""

    modelo: str
    edits: dict[tuple[str, str], dict[str, str]] = field(default_factory=dict)
    counts: collections.Counter[str] = field(default_factory=collections.Counter)
    refusals: list[Refusal] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    long_evidence: list[LongEvidence] = field(default_factory=list)

    def record_evidence(self, revision: str, casilla_id: str, evidence: str) -> str:
        """Bound one evidence string by the schema's cap, recording it when it is unusually long."""
        text = _bounded(evidence)
        if len(text) > _EVIDENCE_ADVISORY:
            self.long_evidence.append(LongEvidence(self.modelo, revision, casilla_id, len(text)))
        return text

    def refuse(
        self,
        revision: str,
        casilla_id: str,
        category: LineageRefusalCategory,
        reason: str,
        predecessor: str | None = None,
    ) -> None:
        """Record a refusal and count it."""
        self.refusals.append(Refusal(self.modelo, revision, casilla_id, category, reason, predecessor))
        self.counts[f"refused:{category}"] += 1

    def set_keys(self, revision: str, casilla_id: str, **keys: str) -> None:
        """Stage key edits for one row, refusing to plan two values for one key."""
        staged = self.edits.setdefault((revision, casilla_id), {})
        for key, value in keys.items():
            if staged.get(key, value) != value:
                raise ValueError(f"modelo {self.modelo} {revision}/{casilla_id}: two values planned for {key}")
            staged[key] = value


@dataclass(frozen=True, slots=True)
class Ruling:
    """An adjudicated boundary, applied verbatim."""

    predecessor: str
    successor: str
    refuse_bare: bool
    rationale: str
    grounded: tuple[tuple[str, str], ...]
    new_on_form: frozenset[str]
    new_on_form_stems: frozenset[str]
    not_on_form: frozenset[str]
    held: tuple[tuple[str, str], ...]
    held_stems: frozenset[str]
    held_reason: str
    withheld: tuple[tuple[str, str], ...]
    withheld_reason: str
    merged: tuple[tuple[str, str], ...]
    merged_reason: str
    discontinued: frozenset[str]


def _bounded(evidence: str) -> str:
    """Normalise evidence whitespace, refusing only what the casilla row model itself would refuse.

    The bound is the schema's, read from the model. A shorter house style is
    not a reason to lose a checkable citation: evidence longer than
    ``_EVIDENCE_ADVISORY`` but within the schema cap is written and reported,
    and only evidence the schema would reject stops the run.
    """
    text = " ".join(evidence.split())
    if len(text) > SCHEMA_EVIDENCE_LIMIT:
        raise ValueError(f"evidence exceeds the schema's {SCHEMA_EVIDENCE_LIMIT}-character cap: {text[:120]!r}")
    return text


@dataclass(frozen=True, slots=True)
class ModeloLoadFailure:
    """A modelo that could not be compiled at all, and the first message its loader raised.

    Recorded at modelo level because a modelo that does not load has no rows to
    record: its editions are never materialised, so its casillas cannot be
    enumerated and none of them can be named. The record is therefore not a
    per-row refusal, and :func:`render_ledger` keeps it out of the ``[[refusal]]``
    array the lineage totality gate reads.
    """

    modelo: str
    reason: str


@dataclass(frozen=True, slots=True)
class PartialStamping:
    """An identifier the corpus stamps on some editions of a modelo and not on others.

    Recorded at modelo level for the same reason a load failure is: the modelo
    is skipped whole, so none of its rows is dispositioned and none can be
    named. :func:`render_ledger` keeps it out of the ``[[refusal]]`` array the
    lineage totality gate reads.

    The state is a half-finished stamping pass, whoever is or is not conducting
    it: the stamped editions carry ``chain``, and each edition in ``unstamped``
    carries neither it nor a recorded absence excusing its start. The registry
    refuses that identifier, so this seeder writes nothing into the modelo until
    the pass finishes.
    """

    modelo: str
    casilla: str
    chain: str
    stamped: tuple[str, ...]
    unstamped: tuple[str, ...]

    def describe(self) -> str:
        """One line naming the chain and the editions, for the ledger and the run's output."""
        chain = self.chain or "(no chain id)"
        return (
            f"chain {chain} on {self.casilla}: stamped in {', '.join(self.stamped)}; "
            f"unstamped in {', '.join(self.unstamped)}"
        )


def _partial_stamping_error(modelo_id: str, records: tuple[PartialStamping, ...]) -> RegistryError:
    """Build the registered registry refusal carrying the structured records."""
    return RegistryError(
        f"modelo {modelo_id}: identifiers stay partly stamped: {[record.casilla for record in records][:5]}",
        context={"modelo_id": modelo_id, "partial_stamping_records": records},
    )


@dataclass(frozen=True, slots=True)
class CarriedRefusal:
    """A previous run's refusal, carried forward because its modelo could not be rejudged.

    Carried verbatim: the row it names and the category and reason it stopped
    are the previous run's words, not a fresh judgement. ``carried_reason`` says
    why this run could not rejudge it. ``last_judged`` is the identifier of the
    run that did judge it, propagated unchanged across repeated carries, and
    ``carried_runs`` counts the consecutive runs that have carried it since.
    Those two are what make staleness visible rather than implied: an entry
    judged in this morning's run and one carried twenty times since a run weeks
    ago read differently in the ledger.
    """

    modelo: str
    revision: str
    casilla: str
    category: str
    reason: str
    predecessor: str | None
    carried_reason: str
    last_judged: str
    carried_runs: int

    @property
    def key(self) -> tuple[str, str, str]:
        """The row this entry names, in the ledger's own key order."""
        return (self.modelo, self.revision, self.casilla)


@dataclass(frozen=True, slots=True)
class PreviousLedger:
    """The ledger as the previous run left it: when it judged, and what it refused per modelo."""

    judged_at: str
    refusals: Mapping[str, tuple[Mapping[str, object], ...]]
