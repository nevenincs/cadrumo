"""Apply one ordered edition boundary at a time to a modelo's lineage state."""

from __future__ import annotations

from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from .casilla_lineage_seed_chain_state import ChainState
from .casilla_lineage_seed_design import DesignOracle
from .casilla_lineage_seed_pair_walk import walk_pair
from .casilla_lineage_seed_rules import (
    judged_pairs,
    role_derived,
    slug,
)
from .casilla_lineage_seed_stamp_settlement import (
    partial_stamp_records,
    settle_partial_stamps,
)
from .casilla_lineage_seed_types import (
    LineagePlan,
    PartialStamping,
    Ruling,
)


class ModeloPlanner:
    """A planner that walks each judged revision pair of a modelo to build its casilla lineage."""

    def __init__(
        self,
        modelo_id: str,
        modelo: ModeloDefinition,
        oracle: DesignOracle,
        rulings: list[Ruling],
        forbidden: frozenset[str],
    ) -> None:
        """Bind the modelo, its design oracle, rulings and forbidden identifiers."""
        self.forbidden = forbidden
        self.modelo_id = modelo_id
        self.modelo = modelo
        self.oracle = oracle
        self.rulings = {(ruling.predecessor, ruling.successor): ruling for ruling in rulings}
        self.plan = LineagePlan(modelo_id)
        self.state = ChainState.of(modelo)

    # -- chain writing

    def _new_chain_id(self, previous: CasillaDefinition, successor: CasillaDefinition, pair: tuple[str, str]) -> str:
        role = previous.semantic_role
        if (
            role is not None
            and role == successor.semantic_role
            and all(self.state.role_counts[revision][role] == 1 for revision in pair)
        ):
            return role_derived(role)
        if role is not None and not bool(self.state.members.get(role_derived(role))):
            return role_derived(role)
        return slug(previous.id)

    def _write_absence(
        self, revision: str, casilla: CasillaDefinition, origin: CasillaLineageOrigin, evidence: str
    ) -> None:
        self.plan.set_keys(
            revision,
            casilla.id,
            continuidad_origin=origin.value,
            continuidad_evidence=self.plan.record_evidence(revision, casilla.id, evidence),
        )
        self.plan.counts[origin.value] += 1

    def _already_disposed(self, casilla: CasillaDefinition) -> bool:
        """Count a row whose continuation or kind of none the corpus already declares, and stop judging it.

        A declared ``continuidad_origin`` is the disposition the lineage
        totality rule reads to call the row resolved. Re-judging it here can
        only disagree with that rule, and a refusal it produced would put an
        entry in the ledger for a row the gate resolves -- a stale exception,
        not an unresolved row. Counted under the origin it declares, so the
        run's report still accounts for every successor row exactly once.
        """
        if casilla.continuidad_origin is None:
            return False
        self.plan.counts[casilla.continuidad_origin.value] += 1
        return True

    # -- identifier-wide stamping

    def settle_partial_stamps(self) -> frozenset[str]:
        """Settle which partially stamped casillas of the modelo remain unsettled."""
        return settle_partial_stamps(self)

    def partial_stamp_records(self, unsettled: frozenset[str]) -> tuple[PartialStamping, ...]:
        """Return the partial-stamping records for the given unsettled casillas."""
        return partial_stamp_records(self, unsettled)

    # -- pair walk

    def run(self) -> LineagePlan:
        """Walk every judged revision pair and return the lineage plan, refusing orphan rulings."""
        pairs = judged_pairs(self.modelo, ordered_revisions(self.modelo))
        for previous, successor in pairs:
            walk_pair(self, previous, successor)
        missing = set(self.rulings) - {(p.id, s.id) for p, s in pairs}
        if missing:
            raise ValueError(f"modelo {self.modelo_id}: rulings name boundaries that do not exist: {sorted(missing)}")
        return self.plan
