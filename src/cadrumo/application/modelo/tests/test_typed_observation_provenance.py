"""Provenance-erasure guard for the typed-observation build.

`build_typed_observations` projects every casilla in a
:class:`RegistryCalculationResult` into a :class:`CasillaObservation`.
A casilla present in ``engine_result.values`` but absent from the
registry snapshot revision is a referential-integrity violation:
projecting it would emit empty ``legal_refs`` / ``source_refs`` and
silently erase legal provenance. This module proves the build
hard-fails on such a casilla instead of yielding a stripped row.

The :class:`RegistryCalculationResult` fed to the build is assembled
directly from the real Modelo 100 registry snapshot — every casilla
id, formula target, legal_ref and source_ref is registry-authored.
No values are invented: ``build_typed_observations`` only consumes
``values`` keys, ``entries`` targets, and the snapshot's casilla
definitions, so a structurally faithful result exercises the exact
referential-integrity contract under test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core import CasillaId, validated_casilla_id
from ....core.resources import resources
from ....domain.calculations.registry import (
    CasillaObservation,
    RegistryCalculationResult,
    RegistrySnapshot,
    expression_casilla_refs,
)
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .. import CasillaProvenanceMissingError
from .._calculation_helpers import (
    amendment_observations as _amendment_observations,
)
from .._calculation_helpers import (
    build_typed_observations as _build_typed_observations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_ORPHAN_CASILLA: CasillaId = validated_casilla_id("9999999", surface="_ORPHAN_CASILLA")

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
    formulas_by_target = {formula.target_casilla_id: formula for formula in revision.formulas}
    observations: list[CasillaObservation] = []
    for casilla in revision.casillas:
        casilla_id: CasillaId = casilla.id
        formula = formulas_by_target.get(casilla_id)
        if formula is not None:
            operand_casilla_refs = expression_casilla_refs(formula.expression)
            observations.append(
                CasillaObservation(
                    casilla_id=casilla_id,
                    value=Decimal("0"),
                    formula_id=formula.id,
                    op="literal",
                    operand_refs=operand_casilla_refs,
                    operand_casilla_refs=operand_casilla_refs,
                    operand_values=tuple(Decimal("0") for _ in operand_casilla_refs),
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
    orphan_casilla = _ORPHAN_CASILLA
    assert orphan_casilla not in casilla_ids

    template_observation = next(obs for obs in engine_result.observations if obs.formula_id is None)
    polluted_observations = (
        *engine_result.observations,
        template_observation.model_copy(update={"casilla_id": orphan_casilla, "value": Decimal("123")}),
    )
    polluted_result = engine_result.model_copy(update={"observations": polluted_observations})

    with pytest.raises(CasillaProvenanceMissingError) as raised_1:
        _build_typed_observations(engine_result=polluted_result, snapshot=snapshot)

    # The orphan casilla is a machine fact now, not part of a sentence.
    assert raised_1.value.context is not None
    assert raised_1.value.context["casilla_id"] == orphan_casilla


def _baseline_revision(
    casilla_values: dict[CasillaId, Decimal],
    observations: tuple[CasillaObservation, ...],
) -> CalculationRevision:
    """A minimal complete baseline CalculationRevision for amendment tests."""
    work_unit_id = "a" * 64
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    moment = datetime(2026, 1, 1, tzinfo=UTC)
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        casilla_values=casilla_values,
        observations=observations,
        created_at=moment,
        updated_at=moment,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def test_amendment_override_orphan_casilla_raises_instead_of_emitting_empty_provenance() -> None:
    """``amendment_observations`` hard-fails on an orphan casilla.

    An overridden casilla that is absent from the registry snapshot revision
    has no provenance source. Projecting it would emit empty legal_refs /
    source_refs and silently erase legal grounding from the persisted amendment.
    The guard must raise instead.
    """
    snapshot = _modelo_100_snapshot()
    casilla_ids = {casilla.id for casilla in snapshot.revision.casillas}
    orphan_casilla = _ORPHAN_CASILLA
    assert orphan_casilla not in casilla_ids

    registry_casilla = snapshot.revision.casillas[0]
    baseline_value = Decimal("0")
    baseline = _baseline_revision(
        {registry_casilla.id: baseline_value},
        (
            CasillaObservation(
                casilla_id=registry_casilla.id,
                value=baseline_value,
                legal_refs=registry_casilla.legal_refs,
                source_refs=registry_casilla.source_refs,
            ),
        ),
    )
    corrected_values = {registry_casilla.id: baseline_value, orphan_casilla: Decimal("123")}

    with pytest.raises(CasillaProvenanceMissingError) as raised_2:
        _amendment_observations(
            corrected_values=corrected_values,
            overrides={orphan_casilla: Decimal("123")},
            baseline_revision=baseline,
            snapshot=snapshot,
        )

    # The orphan casilla is a machine fact now, not part of a sentence.
    assert raised_2.value.context is not None
    assert raised_2.value.context["casilla_id"] == orphan_casilla
