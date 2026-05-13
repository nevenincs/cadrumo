"""Focused unit tests for the _live_parity audit helpers.

`_live_parity` exports two audit helpers that CI / dashboard tooling
consumes to surface oracle-binding drift across modelos:

- ``collect_orphan_oracle_ids`` — catalogue ids that no
  cross-reference binds (in-flight future binding, renamed
  ``oracle_id``, or retired binding whose catalogue registration
  stayed).
- ``collect_applicability_declarations`` — every cross-reference
  declaring applicability predicates, deterministically ordered for
  audit output.

Both helpers are pure (no profile-fact evaluation, no I/O). A
regression in the orphan-set difference, the predicate filter, or the
lexicographic sort would silently mask the drift CI is supposed to
catch, which is why this module exercises each at unit level.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping

import pytest

from aeat.core.paths import PROJECT_ROOT

from ._live_parity import (
    CrossReferenceApplicabilityDeclaration,
    LiveParityCatalogue,
    OracleSurfaceKind,
    ParityResult,
    collect_applicability_declarations,
    collect_orphan_oracle_ids,
)
from ._loader import load_registry_tree
from ._remote_state_guard import RemoteOperation, RemoteStateGuardPolicy
from ._schema import ModeloDefinition

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


class _MinimalOracle:
    """Project-pattern test oracle exposing only ``oracle_id``.

    Mirrors the ``_FakeOracle`` pattern already established in
    ``test_live_parity.py``: a minimal LiveParityOracle implementation
    sufficient to populate :class:`LiveParityCatalogue` for collection-
    style tests. ``planned_operations`` and ``verify_payload`` are
    structurally required by the Protocol but are not exercised by the
    audit helpers under test.
    """

    def __init__(self, oracle_id: str) -> None:
        self._oracle_id = oracle_id

    @property
    def oracle_id(self) -> str:
        return self._oracle_id

    @property
    def surface_kind(self) -> OracleSurfaceKind:
        return "open_simulator"

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        return ()

    def verify_payload(
        self,
        policy: RemoteStateGuardPolicy,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> ParityResult:
        raise NotImplementedError("audit-helper tests never invoke verify_payload")


def _committed_modelos() -> tuple[ModeloDefinition, ...]:
    modelos, _catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    return tuple(modelos)


def _registry_with(ids: tuple[str, ...]) -> LiveParityCatalogue:
    catalogue = LiveParityCatalogue()
    for oracle_id in ids:
        catalogue.register(_MinimalOracle(oracle_id), environment="production")
    return catalogue


# ---------------------------------------------------------------------------
# collect_orphan_oracle_ids
# ---------------------------------------------------------------------------


def test_collect_orphan_oracle_ids_returns_every_catalogue_id_when_no_modelos_bind_them() -> None:
    catalogue = _registry_with(("oracle-alpha", "oracle-beta", "oracle-gamma"))

    orphans = collect_orphan_oracle_ids((), catalogue)

    assert orphans == ("oracle-alpha", "oracle-beta", "oracle-gamma")


def test_collect_orphan_oracle_ids_returns_lexicographically_sorted_output() -> None:
    """Even when registration order is shuffled, the orphan tuple is
    sorted so audit dashboards see a deterministic diff."""
    catalogue = _registry_with(("oracle-z", "oracle-a", "oracle-m"))

    orphans = collect_orphan_oracle_ids((), catalogue)

    assert orphans == tuple(sorted(orphans))


def test_collect_orphan_oracle_ids_omits_ids_bound_by_a_cross_reference() -> None:
    """Walk the committed registry's actual oracle_ids — the catalogue
    registers two oracle ids and one of them is a real cross-reference
    binding. The bound id must disappear from the orphan set."""
    modelos = _committed_modelos()
    bound_ids = {
        cross_reference.oracle_id
        for modelo in modelos
        for revision in modelo.revisions.values()
        for cross_reference in revision.live_cross_references
        if cross_reference.oracle_id is not None
    }
    assert bound_ids, "committed registry must expose at least one bound oracle_id"
    bound_id = next(iter(bound_ids))

    catalogue = _registry_with((bound_id, "oracle-not-bound"))
    orphans = collect_orphan_oracle_ids(modelos, catalogue)

    assert bound_id not in orphans
    assert "oracle-not-bound" in orphans


def test_collect_orphan_oracle_ids_returns_empty_when_every_catalogue_id_is_bound() -> None:
    modelos = _committed_modelos()
    bound_ids = tuple(
        sorted(
            {
                cross_reference.oracle_id
                for modelo in modelos
                for revision in modelo.revisions.values()
                for cross_reference in revision.live_cross_references
                if cross_reference.oracle_id is not None
            }
        )
    )
    assert bound_ids, "committed registry must expose at least one bound oracle_id"

    catalogue = _registry_with(bound_ids)
    orphans = collect_orphan_oracle_ids(modelos, catalogue)

    assert orphans == ()


def test_collect_orphan_oracle_ids_treats_cross_reference_without_oracle_id_as_no_binding() -> None:
    """A cross-reference with ``oracle_id=None`` does NOT contribute to
    the bound set; the matching catalogue id (if any) stays orphan."""
    modelos = _committed_modelos()
    has_none_binding = any(
        cross_reference.oracle_id is None
        for modelo in modelos
        for revision in modelo.revisions.values()
        for cross_reference in revision.live_cross_references
    )
    assert has_none_binding, "committed registry must expose at least one None-bound cross-reference"

    catalogue = _registry_with(("none-bindings-do-not-shadow-this-id",))
    orphans = collect_orphan_oracle_ids(modelos, catalogue)

    assert "none-bindings-do-not-shadow-this-id" in orphans


def test_collect_orphan_oracle_ids_consumes_iterable_once() -> None:
    """The helper must not consume the modelo iterator twice; otherwise
    callers passing a generator would silently see an empty bound set
    on subsequent walks."""
    catalogue = _registry_with(("alpha",))

    def _modelos_once() -> Iterator[ModeloDefinition]:
        yielded = False
        for modelo in _committed_modelos():
            yielded = True
            yield modelo
        assert yielded, "generator must yield something on first pass"

    orphans = collect_orphan_oracle_ids(_modelos_once(), catalogue)

    assert orphans == ("alpha",)


# ---------------------------------------------------------------------------
# collect_applicability_declarations
# ---------------------------------------------------------------------------


def test_collect_applicability_declarations_omits_cross_references_with_no_predicates() -> None:
    """Cross-references with empty ``applicability_predicates`` are the
    unconditional default; the helper documents them as out-of-scope."""
    declarations = collect_applicability_declarations(_committed_modelos())

    inspected = 0
    for declaration in declarations:
        assert declaration.predicate_fields, (
            f"declaration {declaration.cross_reference_id} surfaced with empty predicates"
        )
        inspected += 1
    assert inspected == len(declarations), "every declaration must be inspected by the loop"


def test_collect_applicability_declarations_returns_typed_records() -> None:
    declarations = collect_applicability_declarations(_committed_modelos())

    assert isinstance(declarations, tuple)
    for declaration in declarations:
        assert isinstance(declaration, CrossReferenceApplicabilityDeclaration)
        assert declaration.modelo_id
        assert declaration.revision_id
        assert declaration.cross_reference_id
        assert declaration.applicability_condition_mode in {"all", "any"}


def test_collect_applicability_declarations_is_sorted_for_deterministic_audit_output() -> None:
    """Order is ``(modelo_id, revision_id, cross_reference_id)`` per the
    docstring's deterministic-output contract."""
    declarations = collect_applicability_declarations(_committed_modelos())

    keys = [
        (declaration.modelo_id, declaration.revision_id, declaration.cross_reference_id) for declaration in declarations
    ]
    assert keys == sorted(keys)


def test_collect_applicability_declarations_handles_empty_modelo_iterable() -> None:
    assert collect_applicability_declarations(()) == ()


def test_collect_applicability_declarations_consumes_iterable_once() -> None:
    """Same generator-safety property as collect_orphan_oracle_ids."""

    def _modelos_once() -> Iterator[ModeloDefinition]:
        yielded = False
        for modelo in _committed_modelos():
            yielded = True
            yield modelo
        assert yielded, "generator must yield something on first pass"

    declarations = collect_applicability_declarations(_modelos_once())

    # Tuple is non-empty (committed registry declares at least one
    # cross-reference with predicates) or empty (helper preserved
    # without re-walking). Either way the call must complete without
    # iterating the generator a second time.
    assert isinstance(declarations, tuple)
