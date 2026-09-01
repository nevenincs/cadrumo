"""Standing gate: every cross-modelo carry names the mechanism row that owns it.

A calculation value channel has exactly one canonical mechanism, and a carry that
reads ANOTHER modelo's filed output is a cross-modelo channel whose canonical
mechanism is a relation. Two rows own a cross-modelo channel as a
``previous_filing`` binding instead, and both owe their exemption to the same
cause -- the relation entity cannot express the shape:

* **Cross-member fan-in.** ``grouping = "per_grupo_member"`` aggregates across
  FILERS in one period (every grupo member's own filing), and the relation
  schema carries no grouping axis at all.
* **Direct cross-modelo carry.** The relation entity's plural axis is PERIODS
  (``source_periods`` against one ``source_casilla_id``); a carry whose plural
  axis is SOURCE CASILLAS has no one-relation form. Every instance is
  enumerated in :data:`_DIRECT_CROSS_MODELO_CARRIES` with the constraint that
  keeps it off the relation mechanism and the condition that would end the
  exemption.

Anything else reaching into another modelo belongs on a relation. This gate
refuses a ``previous_filing`` binding that reaches across modelos without
landing in one of the two rows, which is how a second mechanism for one channel
would otherwise enter unobserved -- the failure this repository has already paid
for once, when one fold-in was declared as a relation and as a binding at the
same time and the two resolvers disagreed about who owned it.

The registry's own build-time validators own the adjacent halves and are
asserted here rather than assumed: a ``previous_filing`` binding must satisfy the
direct-selector predicate, and no binding may be both relation-targeted and
``previous_filing``-sourced.

See Also:
    :mod:`cadrumo.domain.calculations.registry._validate_relation_sources`
        The build-time slot-source hygiene gates this module asserts against
        the bundled corpus.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

import pytest

from .....core.aggregation import BindingSourceKind
from ..authority import bundled_authority
from ..binding_selector_utils import selector_as_dict
from ..bindings_previous_filing import is_direct_previous_filing_binding
from ..schema import DataBindingDefinition, ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Row names, used as the classifier's verdict so a violation reads as an
#: unowned channel rather than as a boolean.
_CROSS_MEMBER_FAN_IN = "cross_member_fan_in"
_DIRECT_CROSS_MODELO_CARRY = "direct_cross_modelo_carry"
_UNOWNED = "unowned"


@dataclass(frozen=True, slots=True)
class _DirectCrossModeloCarry:
    """One carry that reads another modelo directly, and why it cannot be a relation.

    Keyed by ``(modelo_id, revision_id, binding_id)`` -- the full coordinate,
    never a line number, so a registry reflow cannot detach an entry from the
    carry it was written for. Every field is required: an entry states its own
    argument, so a later reader judges the exemption instead of inheriting it.

    ``revisit_trigger`` is the condition that ends the exemption. It is a field
    rather than prose because an exemption with no stated end is how a
    documented exception becomes a permanent second mechanism.
    """

    modelo_id: str
    revision_id: str
    binding_id: str
    source_modelo: str
    reason: str
    revisit_trigger: str

    @property
    def key(self) -> tuple[str, str, str]:
        """Return the coordinate this entry is matched by."""
        return (self.modelo_id, self.revision_id, self.binding_id)


_DIRECT_CROSS_MODELO_CARRIES: tuple[_DirectCrossModeloCarry, ...] = (
    _DirectCrossModeloCarry(
        modelo_id="130",
        revision_id="2019-y-siguientes",
        binding_id="irpf.previous_year_economic_activity_net_income",
        source_modelo="100",
        reason=(
            "The minoración of RIRPF art. 110.3.c brackets the PRIOR year's net income from "
            "economic activities, and the Modelo 130 instructions define that antecedent as the "
            "sum of four Modelo 100 boxes (0224 estimación directa, 1479 and 1553 estimación "
            "objetiva, 1577 atribuida). Modelo 100 publishes no total over the four, so the "
            "carry's plural axis is SOURCE CASILLAS -- the one axis a relation lacks, its own "
            "plural axis being periods against a single source_casilla_id. Expressing it as "
            "relations takes four of them, four materialisation slots and an intermediate "
            "casilla to say what one selector says today, and it collapses the operator's "
            "single-value override channel into four per-box overrides that a taxpayer holding "
            "only the total cannot answer. Summing the four inside Modelo 100 instead is worse: "
            "an intermediate casilla is exempt from the official record, so it never appears in "
            "a filed declaration and the relation could not resolve from pulled AEAT history at "
            "all -- the very channel this carry exists to consume."
        ),
        revisit_trigger=(
            "Fold this carry onto a relation when either the relation schema gains a plural "
            "source-casilla axis, or Modelo 100 publishes a single box totalling the "
            "rendimiento neto of economic activities."
        ),
    ),
)


class _ScanResult(TypedDict):
    modelos_scanned: set[str]
    revisions_scanned: int
    previous_filing_bindings_scanned: int
    cross_modelo_keys: set[tuple[str, str, str]]
    cross_modelo_sources: dict[tuple[str, str, str], str]
    unowned: list[str]
    non_direct_selectors: list[str]
    also_relation_targets: list[str]


def _cross_modelo_source(binding: DataBindingDefinition, *, owning_modelo: str) -> str | None:
    """Return the source modelo when the binding reaches across modelos, else ``None``.

    A ``previous_filing`` selector that names no source modelo, or names the
    owning one, is a same-modelo carry and is owned by its own taxonomy row.
    """
    if binding.source is not BindingSourceKind.PREVIOUS_FILING:
        return None
    source_modelo = selector_as_dict(binding).get("source_modelo")
    if not isinstance(source_modelo, str) or not source_modelo or source_modelo == owning_modelo:
        return None
    return source_modelo


def _classify(
    binding: DataBindingDefinition,
    *,
    owning_modelo: str,
    revision_id: str,
) -> str:
    """Return the taxonomy row owning this cross-modelo carry, or ``_UNOWNED``."""
    if selector_as_dict(binding).get("grouping") == "per_grupo_member":
        return _CROSS_MEMBER_FAN_IN
    key = (owning_modelo, revision_id, str(binding.id))
    if any(entry.key == key for entry in _DIRECT_CROSS_MODELO_CARRIES):
        return _DIRECT_CROSS_MODELO_CARRY
    return _UNOWNED


def _relation_targets(revision: ModeloRevision) -> frozenset[str]:
    return frozenset(str(relation.target_binding) for relation in revision.relations)


def _scan() -> _ScanResult:
    """Walk every modelo × revision and collect the cross-modelo carry facts."""
    authority = bundled_authority()

    modelos_scanned: set[str] = set()
    revisions_scanned = 0
    previous_filing_bindings_scanned = 0
    cross_modelo_keys: set[tuple[str, str, str]] = set()
    cross_modelo_sources: dict[tuple[str, str, str], str] = {}
    unowned: list[str] = []
    non_direct_selectors: list[str] = []
    also_relation_targets: list[str] = []

    for modelo in authority.modelos:
        owning_modelo = str(modelo.id)
        modelos_scanned.add(owning_modelo)
        for revision_id, revision in modelo.revisions.items():
            revisions_scanned += 1
            targets = _relation_targets(revision)
            for binding in revision.bindings:
                if binding.source is BindingSourceKind.PREVIOUS_FILING:
                    previous_filing_bindings_scanned += 1
                source_modelo = _cross_modelo_source(binding, owning_modelo=owning_modelo)
                if source_modelo is None:
                    continue
                locator = f"{owning_modelo}/{revision_id}/{binding.id} -> {source_modelo}"
                cross_modelo_keys.add((owning_modelo, str(revision_id), str(binding.id)))
                cross_modelo_sources[(owning_modelo, str(revision_id), str(binding.id))] = source_modelo
                if _classify(binding, owning_modelo=owning_modelo, revision_id=str(revision_id)) == _UNOWNED:
                    unowned.append(locator)
                if not is_direct_previous_filing_binding(binding):
                    non_direct_selectors.append(locator)
                if str(binding.id) in targets:
                    also_relation_targets.append(locator)

    return {
        "modelos_scanned": modelos_scanned,
        "revisions_scanned": revisions_scanned,
        "previous_filing_bindings_scanned": previous_filing_bindings_scanned,
        "cross_modelo_keys": cross_modelo_keys,
        "cross_modelo_sources": cross_modelo_sources,
        "unowned": unowned,
        "non_direct_selectors": non_direct_selectors,
        "also_relation_targets": also_relation_targets,
    }


@pytest.fixture(scope="module")
def scan() -> _ScanResult:
    return _scan()


def test_every_cross_modelo_carry_lands_in_exactly_one_taxonomy_row(scan: _ScanResult) -> None:
    """A `previous_filing` binding reaching another modelo is fan-in or enumerated."""
    assert scan["unowned"] == [], (
        "cross-modelo previous_filing carries owned by no taxonomy row -- a cross-modelo "
        "channel belongs on a relation unless it is a per_grupo_member fan-in or carries "
        f"an enumerated exemption: {scan['unowned']}"
    )


def test_every_cross_modelo_carry_satisfies_the_direct_selector_predicate(scan: _ScanResult) -> None:
    """A non-direct selector is a mis-stamped relation slot, not a carry."""
    assert scan["non_direct_selectors"] == [], (
        "cross-modelo previous_filing carries whose selector is not direct; these are "
        f"relation materialisation slots and must declare relation_prefill: {scan['non_direct_selectors']}"
    )


def test_no_cross_modelo_carry_is_also_a_relation_target(scan: _ScanResult) -> None:
    """One channel, one mechanism: never a relation and a direct carry at once."""
    assert scan["also_relation_targets"] == [], (
        "cross-modelo carries declared as BOTH a relation target and a previous_filing "
        f"source -- one fold-in modelled two ways: {scan['also_relation_targets']}"
    )


def test_no_enumerated_carry_is_stale(scan: _ScanResult) -> None:
    """An entry whose carry no longer exists must be removed, not left standing."""
    stale = sorted(
        f"{entry.modelo_id}/{entry.revision_id}/{entry.binding_id}"
        for entry in _DIRECT_CROSS_MODELO_CARRIES
        if entry.key not in scan["cross_modelo_keys"]
    )
    assert stale == [], (
        "enumerated direct cross-modelo carries that no longer exist in the corpus; remove "
        f"the entry in the same change that removed or narrowed the carry: {stale}"
    )


def test_every_enumerated_carry_states_its_source_modelo_truthfully(scan: _ScanResult) -> None:
    """The entry's declared source modelo matches the selector it exempts."""
    mismatches = sorted(
        f"{entry.binding_id}: entry says {entry.source_modelo!r}, selector says {declared!r}"
        for entry in _DIRECT_CROSS_MODELO_CARRIES
        if (declared := scan["cross_modelo_sources"].get(entry.key)) is not None and declared != entry.source_modelo
    )
    assert mismatches == [], f"enumerated carries describing a source they do not read: {mismatches}"


def test_the_scan_reaches_the_corpus(scan: _ScanResult) -> None:
    """Anti-vacuity: the walk saw the corpus, so an empty violation list means something."""
    assert len(scan["modelos_scanned"]) > 1
    assert scan["revisions_scanned"] > 1
    assert scan["previous_filing_bindings_scanned"] > 1
    assert scan["cross_modelo_keys"], "the corpus carries no cross-modelo previous_filing binding at all"


def test_an_unenumerated_cross_modelo_carry_is_refused() -> None:
    """Positive control: the classifier flags a carry that lands in neither row."""
    binding = DataBindingDefinition(
        id="probe.unenumerated-cross-modelo-carry",
        source=BindingSourceKind.PREVIOUS_FILING,
        selector={"source_modelo": "100", "filing_year_delta": -1, "period": "0A", "source_casilla_ids": ("0224",)},
        legal_refs=("rd-439-2007:art-110",),
        source_refs=("aeat-modelo-130-instructions",),
    )

    assert _cross_modelo_source(binding, owning_modelo="130") == "100"
    assert _classify(binding, owning_modelo="130", revision_id="2019-y-siguientes") == _UNOWNED


def test_the_fan_in_row_is_recognised_by_its_grouping_axis() -> None:
    """Positive control: the fan-in row is claimed by the grouping axis, not by a list."""
    binding = DataBindingDefinition(
        id="probe.cross-member-fan-in",
        source=BindingSourceKind.PREVIOUS_FILING,
        selector={
            "source_modelo": "322",
            "filing_year_delta": 0,
            "source_period_offset_from_target": 0,
            "grouping": "per_grupo_member",
            "source_casilla_ids": ("iva.cuota-deducible-total",),
        },
        legal_refs=("ley-37-1992:art-92",),
        source_refs=("aeat-modelo-353-instructions",),
    )

    assert _classify(binding, owning_modelo="353", revision_id="2008-2025") == _CROSS_MEMBER_FAN_IN
