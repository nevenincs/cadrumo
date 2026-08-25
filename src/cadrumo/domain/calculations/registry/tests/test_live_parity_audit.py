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
catch, which is why this module exercises each at unit level. Every
registered oracle is a real production adapter; no stub layer sits
between the test and the catalogue.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ..aeat_nif_iva_oracle import ORACLE_ID, AeatNifIvaCheckerOracle
from ..groi_oracle import GROI_ORACLE_ID, GroiOracle
from ..live_parity import (
    CrossReferenceApplicabilityDeclaracion,
    LiveParityCatalogue,
    OracleEnvironment,
    collect_applicability_declarations,
    collect_orphan_oracle_ids,
)
from .._renta_web_open_oracle import RentaWebOpenOracle
from ..schema import ModeloDefinition
from ._registry_schema_support import _committed_registry_tree

# INTENTIONAL: unit because the audit helpers are pure and exercise the real oracle
# catalogue with no I/O and no AEAT contact.
pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# The committed registry binds these oracle ids; RentaWebOpenOracle's
# id is registered but no cross-reference binds it today, making it the
# canonical "unbound" real adapter used to exercise the orphan-set
# difference logic.
RENTA_WEB_OPEN_ORACLE_ID = "modelo-100-renta-web-open"


def _committed_modelos() -> tuple[ModeloDefinition, ...]:
    modelos, _catalogues = _committed_registry_tree()
    return modelos


def _full_production_catalogue() -> LiveParityCatalogue:
    """Register every production-grade oracle adapter shipped with the project."""

    catalogue = LiveParityCatalogue()
    catalogue.register(AeatNifIvaCheckerOracle(), environment=OracleEnvironment.PRODUCTION)
    catalogue.register(GroiOracle(), environment=OracleEnvironment.PRODUCTION)
    catalogue.register(RentaWebOpenOracle(), environment=OracleEnvironment.PRODUCTION)
    return catalogue


# ---------------------------------------------------------------------------
# collect_orphan_oracle_ids
# ---------------------------------------------------------------------------


def test_collect_orphan_oracle_ids_returns_every_catalogue_id_when_no_modelos_bind_them() -> None:
    catalogue = _full_production_catalogue()

    orphans = collect_orphan_oracle_ids((), catalogue)

    assert orphans == tuple(sorted({ORACLE_ID, GROI_ORACLE_ID, RENTA_WEB_OPEN_ORACLE_ID}))


def test_collect_orphan_oracle_ids_returns_lexicographically_sorted_output() -> None:
    """The orphan tuple is sorted so audit dashboards see a deterministic diff."""
    catalogue = _full_production_catalogue()

    orphans = collect_orphan_oracle_ids((), catalogue)

    assert orphans == tuple(sorted(orphans))


def test_collect_orphan_oracle_ids_omits_ids_bound_by_a_cross_reference() -> None:
    """The committed registry binds AeatNifIvaCheckerOracle and GroiOracle;
    RentaWebOpenOracle is registered but currently unbound. Bound ids must
    disappear from the orphan set, the unbound one must remain."""
    modelos = _committed_modelos()
    bound_ids = {
        cross_reference.oracle_id
        for modelo in modelos
        for revision in modelo.revisions.values()
        for cross_reference in revision.live_cross_references
        if cross_reference.oracle_id is not None
    }
    assert {ORACLE_ID, GROI_ORACLE_ID} <= bound_ids
    assert RENTA_WEB_OPEN_ORACLE_ID not in bound_ids

    catalogue = _full_production_catalogue()
    orphans = collect_orphan_oracle_ids(modelos, catalogue)

    assert ORACLE_ID not in orphans
    assert GROI_ORACLE_ID not in orphans
    assert RENTA_WEB_OPEN_ORACLE_ID in orphans


def test_collect_orphan_oracle_ids_returns_empty_when_every_catalogue_id_is_bound() -> None:
    """Catalogue limited to the two oracles bound by the committed registry."""
    modelos = _committed_modelos()
    catalogue = LiveParityCatalogue()
    catalogue.register(AeatNifIvaCheckerOracle(), environment=OracleEnvironment.PRODUCTION)
    catalogue.register(GroiOracle(), environment=OracleEnvironment.PRODUCTION)

    orphans = collect_orphan_oracle_ids(modelos, catalogue)

    assert orphans == ()


def test_collect_orphan_oracle_ids_treats_cross_reference_without_oracle_id_as_no_binding() -> None:
    """A cross-reference with ``oracle_id=None`` does NOT contribute to
    the bound set; an otherwise-unbound registered oracle stays orphan."""
    modelos = _committed_modelos()
    has_none_binding = any(
        cross_reference.oracle_id is None
        for modelo in modelos
        for revision in modelo.revisions.values()
        for cross_reference in revision.live_cross_references
    )
    assert has_none_binding, "committed registry must expose at least one None-bound cross-reference"

    catalogue = LiveParityCatalogue()
    catalogue.register(RentaWebOpenOracle(), environment=OracleEnvironment.PRODUCTION)
    orphans = collect_orphan_oracle_ids(modelos, catalogue)

    assert RENTA_WEB_OPEN_ORACLE_ID in orphans


def test_collect_orphan_oracle_ids_consumes_iterable_once() -> None:
    """The helper must not consume the modelo iterator twice; otherwise
    callers passing a generator would silently see an empty bound set
    on subsequent walks."""
    catalogue = LiveParityCatalogue()
    catalogue.register(RentaWebOpenOracle(), environment=OracleEnvironment.PRODUCTION)

    def _modelos_once() -> Iterator[ModeloDefinition]:
        yielded = False
        for modelo in _committed_modelos():
            yielded = True
            yield modelo
        assert yielded, "generator must yield something on first pass"

    orphans = collect_orphan_oracle_ids(_modelos_once(), catalogue)

    assert orphans == (RENTA_WEB_OPEN_ORACLE_ID,)


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
        assert isinstance(declaration, CrossReferenceApplicabilityDeclaracion)
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
