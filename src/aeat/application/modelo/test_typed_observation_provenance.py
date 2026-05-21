"""Provenance-erasure guard for the typed-observation build.

`_build_typed_observations` projects every casilla in a
:class:`RegistryCalculationResult` into a :class:`CasillaObservation`.
A casilla present in ``engine_result.values`` but absent from the
registry snapshot revision is a referential-integrity violation:
projecting it would emit empty ``legal_refs`` / ``source_refs`` and
silently erase legal provenance. This module proves the build
hard-fails on such a casilla instead of yielding a stripped row.

The :class:`RegistryCalculationResult` fed to the build is assembled
directly from the real Modelo 100 registry snapshot — every casilla
id, formula target, legal_ref and source_ref is registry-authored.
No values are invented: ``_build_typed_observations`` only consumes
``values`` keys, ``entries`` targets, and the snapshot's casilla
definitions, so a structurally faithful result exercises the exact
referential-integrity contract under test.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from aeat.application.modelo._actions import (
    CasillaProvenanceMissingError,
    _build_typed_observations,
)
from aeat.core.resources import resources
from aeat.domain.calculations.registry import (
    RegistryCalculationEntry,
    RegistryCalculationResult,
    RegistrySnapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_YEAR = 2025
_PERIOD = "0A"


def _modelo_100_snapshot() -> RegistrySnapshot:
    return resources().modelos.authority.snapshot("100", filing_year=_YEAR, period=_PERIOD)


def _engine_result(snapshot: RegistrySnapshot) -> RegistryCalculationResult:
    """Assemble a structurally faithful result from the real revision.

    Every casilla on the revision appears in ``values``; every
    formula-computed casilla also appears in ``entries`` carrying the
    formula id and its registry-authored legal / source refs.
    """
    revision = snapshot.revision
    formulas_by_target = {formula.target: formula for formula in revision.formulas}
    values = {str(casilla.id): Decimal("0") for casilla in revision.casillas}
    entries = tuple(
        RegistryCalculationEntry(
            formula_id=str(formula.id),
            target=str(formula.target),
            op="literal",
            operand_refs=(),
            operand_values=(),
            value=Decimal("0"),
            legal_refs=formula.legal_refs,
            source_refs=formula.source_refs,
        )
        for formula in formulas_by_target.values()
    )
    return RegistryCalculationResult(
        modelo=str(revision.id).split(":")[0] if ":" in str(revision.id) else "100",
        revision=str(revision.id),
        values=values,
        entries=entries,
    )


def test_typed_observations_built_for_real_snapshot_carry_provenance() -> None:
    snapshot = _modelo_100_snapshot()
    engine_result = _engine_result(snapshot)

    observations = _build_typed_observations(engine_result=engine_result, snapshot=snapshot)

    assert len(observations) == len(engine_result.values)
    casilla_ids = {casilla.id for casilla in snapshot.revision.casillas}
    for observation in observations:
        assert observation.casilla_id in casilla_ids

    non_computed = [obs for obs in observations if obs.formula_id is None]
    assert non_computed, "expected at least one input / bound casilla observation"
    casillas_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    for observation in non_computed:
        registry_casilla = casillas_by_id[observation.casilla_id]
        assert observation.legal_refs == registry_casilla.legal_refs
        assert observation.source_refs == registry_casilla.source_refs


def test_unknown_casilla_raises_instead_of_emitting_empty_provenance() -> None:
    snapshot = _modelo_100_snapshot()
    engine_result = _engine_result(snapshot)

    casilla_ids = {casilla.id for casilla in snapshot.revision.casillas}
    orphan_casilla = "9999999"
    assert orphan_casilla not in casilla_ids

    polluted_values = dict(engine_result.values)
    polluted_values[orphan_casilla] = Decimal("123")
    polluted_result = engine_result.model_copy(update={"values": polluted_values})

    with pytest.raises(CasillaProvenanceMissingError, match=orphan_casilla):
        _build_typed_observations(engine_result=polluted_result, snapshot=snapshot)
