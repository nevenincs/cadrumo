"""The population scope must silence an empty bucket without silencing a populated one.

Reconciling a pulled AEAT filing against a freshly onboarded profile is the case
these tests pin: the local calculation holds nothing, so every reconciled casilla
would diverge and the operator would learn only that the bucket is empty. The
scope resolved here is what stops that, and the risk of any such narrowing is
that it silences the real disagreements too — so both directions are asserted,
over a real bundled registry revision rather than a hand-built one.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind

from ....core import BindingSourceKind, CasillaId
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .._reconcile_casilla import (
    CasillaDivergenceKind,
    detect_casilla_divergences,
)
from .._reconcile_population import resolve_casilla_population_scope

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WORK_UNIT_ID = "b" * 64

#: Distinct and fixed rather than "now". The model documents updated_at as equal
#: to created_at on a fresh draft, so a differing pair is the non-default state a
#: save-drops-field / load-re-defaults regression would collapse; and a frozen
#: instant keeps the fixture deterministic.
_CREATED_AT = datetime(2026, 3, 4, 9, 15, 30, tzinfo=UTC)
_UPDATED_AT = datetime(2026, 5, 6, 17, 45, 5, tzinfo=UTC)


def _m130_revision() -> ModeloRevision:
    """Return the real bundled Modelo 130 revision used as the subject."""
    modelo = next(definition for definition in bundled_authority().modelos if definition.id == "130")
    return modelo.revisions["2019-y-siguientes"]


def _calculation(
    *,
    inputs: Mapping[CasillaId, str] | None = None,
    binding_overrides: Mapping[BindingId, str] | None = None,
) -> CalculationRevision:
    """Build one persisted-shaped revision; every test varies only what it supplies."""
    supplied_inputs = dict(inputs or {})
    supplied_overrides = dict(binding_overrides or {})
    return CalculationRevision(
        # The id is content addressed over what the revision carries, so a
        # fixed constant only matches a fixture that never varies. These tests
        # vary the inputs, so the id is derived from the same values.
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=_WORK_UNIT_ID,
            input_values_by_casilla_id=supplied_inputs,
            binding_overrides=supplied_overrides,
            casilla_values={},
            source_provenance=(),
            filing_instance_evidence=None,
        ),
        work_unit_id=_WORK_UNIT_ID,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=supplied_inputs,
        binding_overrides=supplied_overrides,
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def test_an_untouched_calculation_is_comparable_at_no_casilla() -> None:
    """A bucket that supplied nothing must reconcile to nothing, not to everything."""
    revision = _m130_revision()
    scope = resolve_casilla_population_scope(registry_revision=revision, calculation=_calculation())

    assert scope.comparable_casilla_ids == ()
    assert scope.is_empty
    # The complement is carried rather than dropped, so a caller can report what
    # was withheld instead of silently narrowing.
    assert scope.unpopulated_casilla_ids != ()


def test_an_untouched_calculation_raises_no_divergence_against_a_full_filed_side() -> None:
    """The scope must survive the case it exists for: empty local, complete filed."""
    revision = _m130_revision()
    scope = resolve_casilla_population_scope(registry_revision=revision, calculation=_calculation())
    filed = {casilla.id: Decimal("1234.56") for casilla in revision.casillas}

    divergences = detect_casilla_divergences(computed={}, filed=filed, scope=scope.divergence_scope)

    assert divergences == ()
    # Without the scope the same comparison is pure noise; that contrast is the
    # whole justification for the narrowing and is asserted, not assumed.
    assert len(detect_casilla_divergences(computed={}, filed=filed)) == len(filed)


def test_one_supplied_input_opens_its_own_casillas_and_not_the_rest() -> None:
    """Population is per casilla: one supplied figure must not unlock the whole revision."""
    revision = _m130_revision()
    manual_ids = sorted(casilla.id for casilla in revision.casillas if casilla.input_kind is InputKind.MANUAL)
    assert manual_ids, "subject revision declares no manual casilla; the test would be vacuous"
    supplied = manual_ids[0]

    scope = resolve_casilla_population_scope(
        registry_revision=revision,
        calculation=_calculation(inputs={supplied: "500.00"}),
    )

    candidates = {casilla.id for casilla in revision.casillas if casilla.input_kind is not InputKind.INFORMATIONAL}
    comparable = set(scope.comparable_casilla_ids)
    assert supplied in comparable
    assert comparable < candidates, "a single supplied input must not make every casilla comparable"


def test_a_populated_casilla_still_surfaces_a_real_disagreement() -> None:
    """The narrowing must not silence the disagreement it was built to preserve."""
    revision = _m130_revision()
    manual_ids = sorted(casilla.id for casilla in revision.casillas if casilla.input_kind is InputKind.MANUAL)
    assert manual_ids, "subject revision declares no manual casilla; the test would be vacuous"
    supplied = manual_ids[0]

    scope = resolve_casilla_population_scope(
        registry_revision=revision,
        calculation=_calculation(inputs={supplied: "500.00"}),
    )
    assert scope.comparable_casilla_ids, "the supplied input opened no casilla"

    divergences = detect_casilla_divergences(
        computed={supplied: Decimal("500.00")},
        filed={supplied: Decimal("900.00")},
        scope=scope.divergence_scope,
    )

    assert [row.casilla_id for row in divergences] == [supplied]
    assert divergences[0].kind is CasillaDivergenceKind.VALUE_MISMATCH
    assert divergences[0].delta == Decimal("400.00")


def test_a_carry_binding_is_never_population_evidence() -> None:
    """A value read back from the filed store cannot license comparing against that store."""
    revision = _m130_revision()
    carry_binding_ids = sorted(
        binding.id
        for binding in revision.bindings
        if binding.source in {BindingSourceKind.PREVIOUS_FILING, BindingSourceKind.RELATION_PREFILL}
    )
    assert carry_binding_ids, "subject revision declares no carry binding; the test would be vacuous"

    scope = resolve_casilla_population_scope(
        registry_revision=revision,
        calculation=_calculation(binding_overrides={carry_binding_ids[0]: "750.00"}),
    )

    assert scope.comparable_casilla_ids == ()
    assert scope.is_empty
