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

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import (
    CasillaObservation,
    RegistryCalculationResult,
    RegistrySnapshot,
)
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .._actions import (
    CasillaProvenanceMissingError,
    _amendment_observations,
    _build_typed_observations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = 2025
_PERIOD = "0A"


def _modelo_100_snapshot() -> RegistrySnapshot:
    return resources().modelos.authority.snapshot("100", filing_year=_YEAR, period=_PERIOD)


def _engine_result(snapshot: RegistrySnapshot) -> RegistryCalculationResult:
    """Assemble a structurally faithful result from the real revision.

    Every casilla on the revision lands as one
    :class:`CasillaObservation`. Formula-computed casillas carry the
    formula id, op label, and the formula's registry-authored
    legal / source refs; non-computed casillas pull legal / source
    refs from the casilla definition so the derived ``values`` and
    ``entries`` views remain faithful to a real engine run.
    """
    revision = snapshot.revision
    formulas_by_target = {formula.target: formula for formula in revision.formulas}
    observations: list[CasillaObservation] = []
    for casilla in revision.casillas:
        casilla_id = str(casilla.id)
        formula = formulas_by_target.get(casilla_id)
        if formula is not None:
            observations.append(
                CasillaObservation(
                    casilla_id=casilla_id,
                    value=Decimal("0"),
                    formula_id=str(formula.id),
                    op="literal",
                    legal_refs=formula.legal_refs,
                    source_refs=formula.source_refs,
                ),
            )
        else:
            observations.append(
                CasillaObservation(
                    casilla_id=casilla_id,
                    value=Decimal("0"),
                    legal_refs=casilla.legal_refs,
                    source_refs=casilla.source_refs,
                ),
            )
    return RegistryCalculationResult(
        modelo=str(revision.id).split(":")[0] if ":" in str(revision.id) else "100",
        revision=str(revision.id),
        observations=tuple(observations),
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

    polluted_observations = (
        *engine_result.observations,
        CasillaObservation(casilla_id=orphan_casilla, value=Decimal("123")),
    )
    polluted_result = engine_result.model_copy(update={"observations": polluted_observations})

    with pytest.raises(CasillaProvenanceMissingError, match=orphan_casilla):
        _build_typed_observations(engine_result=polluted_result, snapshot=snapshot)


def _baseline_revision(casilla_values: dict[str, Decimal]) -> CalculationRevision:
    """A minimal baseline CalculationRevision with no observations.

    An externally-imported baseline carries no typed observations, so
    a non-overridden casilla absent from the registry snapshot has no
    provenance source at all — exactly the orphan path under test.
    """
    work_unit_id = "a" * 64
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot={},
        binding_overrides={},
        casilla_values=casilla_values,
    )
    moment = datetime(2026, 1, 1, tzinfo=UTC)
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        casilla_values=casilla_values,
        created_at=moment,
        updated_at=moment,
    )


def test_amendment_orphan_casilla_raises_instead_of_emitting_empty_provenance() -> None:
    """``_amendment_observations`` hard-fails on an orphan casilla.

    A non-overridden casilla that is absent from BOTH the baseline
    revision's observations AND the registry snapshot revision has no
    provenance source. Projecting it would emit empty legal_refs /
    source_refs and silently erase legal grounding from the persisted
    amendment. The guard must raise instead.
    """
    snapshot = _modelo_100_snapshot()
    casilla_ids = {casilla.id for casilla in snapshot.revision.casillas}
    orphan_casilla = "9999999"
    assert orphan_casilla not in casilla_ids

    # The orphan appears in corrected_values but NOT in overrides, and
    # the baseline revision carries no observations to inherit from.
    corrected_values = {orphan_casilla: Decimal("123")}
    baseline = _baseline_revision(corrected_values)
    assert baseline.observations == ()

    with pytest.raises(CasillaProvenanceMissingError, match=orphan_casilla):
        _amendment_observations(
            corrected_values=corrected_values,
            overrides={},
            baseline_revision=baseline,
            snapshot=snapshot,
        )
