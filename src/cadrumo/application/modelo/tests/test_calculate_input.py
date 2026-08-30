"""Modelo work calculation input guards."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period, RegistryAuthorityGrade
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.contribuyente.descendant import DescendantInfo
from ....domain.contribuyente.descendant_facts import descendant_facts_from_list
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from .._calculate_input import (
    ModeloCalculateCasillaInputError,
    ModeloCalculateDecimalInputError,
    ModeloCalculateTextInputError,
    WorkCalculateInputBundle,
    build_work_calculate_input_bundle,
)
from ..work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M200_AMBIGUOUS_PRINTED_NUMBER: CasillaId = validated_casilla_id(
    "00562",
    surface="_M200_AMBIGUOUS_PRINTED_NUMBER",
)
_M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA: CasillaId = validated_casilla_id(
    "DP200010:00562",
    surface="_M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA",
)
_M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00562",
    surface="_M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA",
)
_PROFILE_ID = "20000000-0000-4000-8000-000000000562"
_DECIMAL_GRAMMAR_PROFILE_ID = "20000000-0000-4000-8000-000000000001"
_M200_MANUAL_DECIMAL_CASILLA: CasillaId = validated_casilla_id(
    "00001",
    surface="_M200_MANUAL_DECIMAL_CASILLA",
)


def test_work_calculate_input_bundle_rejects_ambiguous_reused_printed_number(tmp_path: Path) -> None:
    """A raw ``--casilla`` token must be the canonical ``casilla.id``."""
    period = Period.from_year_and_code(2025, "0A")
    snapshot = bundled_authority().snapshot(
        "200",
        filing_year=2025,
        period=period.registry_token,
        # These exercise the CALCULATE path, so they need the rung that
        # computes amounts. The accessor defaults to the strictest rung,
        # and modelo 200's revision honestly declares calculation.
        grade=RegistryAuthorityGrade.CALCULATION,
    )

    bucket_id = _PROFILE_ID
    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(bucket_id):
        # Seeded through a detached WorkflowState, never a repository read:
        # the capsule publishes by an atomic no-replace rename onto
        # ``buckets/<profile-id>``, which a workflow-state repository
        # construction would otherwise materialise first and collide with.
        register_minimal_profile(
            profile_id=bucket_id,
            overrides={
                "identity.tax_id": "B66012345",
                "identity.legal_name": "Calculate Input SL",
                "taxpayer_type.entity_type": "legal_entity",
                "taxpayer_type.legal_entity_form": "sl",
            },
        )
        work_unit = create_work_unit(
            bucket_id=bucket_id,
            modelo="200",
            filing_year=2025,
            period=period,
            revision_id=snapshot.revision.id,
            clock=datetime(2026, 6, 26, 12, 0, tzinfo=UTC),
        )

        with pytest.raises(ModeloCalculateCasillaInputError) as exc_info:
            build_work_calculate_input_bundle(
                work_unit_id=work_unit.work_unit_id,
                casilla_overrides={_M200_AMBIGUOUS_PRINTED_NUMBER: "100.00"},
                binding_overrides={},
                relation_overrides={},
                detail_rows=(),
                borrador_snapshot_id=None,
            )

    # The competing casilla ids travel as facts; the refusal itself renders from
    # its registered key, so neither id can be asserted through str(exc).
    context = exc_info.value.context or {}
    accepted = str(context.get("accepted", ""))
    assert _M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA in accepted
    assert _M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA in accepted


# Forms a bare ``Decimal(raw_value)`` silently accepted before the canonical
# grammar was applied to this boundary. Each would have become a real casilla
# value feeding a tax calculation: ``1e3`` becomes 1000, ``+140000`` becomes
# 140000, ``.5`` becomes 0.5, and ``NaN``/``Infinity`` poison every downstream
# sum. The grammar refuses each with the boundary's own typed error.
_NON_CANONICAL_CASILLA_VALUES = (
    "1e3",
    "1E3",
    "1e-3",
    "+140000",
    "+1.50",
    "NaN",
    "Infinity",
    "-Infinity",
    "1_000",
    ".5",
    "1.",
)

# Canonical forms that MUST keep working, including sub-cent precision: the AEAT
# fixed-width encoder rounds such a value to cents with ROUND_HALF_UP, so the
# input boundary must not refuse it.
#
# Precision is NOT what the boundary caps -- a Spanish thousands lookalike is.
# So a sub-cent value passes at any number of fractional digits provided its
# lead group cannot open a grouping run, which a leading zero never does.
# `2.345` used to sit in this tuple and no longer can: `2` IS a valid lead
# group, so on a money field that text is undecidable between two euros
# thirty-four and two thousand three hundred forty-five, and the boundary
# refuses rather than guessing at a thousandfold error.
_CANONICAL_CASILLA_VALUES = ("140000", "140000.00", "-140000.55", "0", "0.335", "0.075")


def _m200_bundle_with_casilla_value(raw_value: str, *, tmp_path: Path) -> WorkCalculateInputBundle:
    """Drive the real calculate-input boundary with one manual ``--casilla`` value."""
    period = Period.from_year_and_code(2025, "0A")
    snapshot = bundled_authority().snapshot(
        "200",
        filing_year=2025,
        period=period.registry_token,
        # These exercise the CALCULATE path, so they need the rung that
        # computes amounts. The accessor defaults to the strictest rung,
        # and modelo 200's revision honestly declares calculation.
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    bucket_id = _DECIMAL_GRAMMAR_PROFILE_ID
    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(bucket_id):
        # Seeded through a detached WorkflowState, never a repository read:
        # the capsule publishes by an atomic no-replace rename onto
        # ``buckets/<profile-id>``, which a workflow-state repository
        # construction would otherwise materialise first and collide with.
        register_minimal_profile(
            profile_id=bucket_id,
            overrides={
                "identity.tax_id": "B66012345",
                "identity.legal_name": "Calculate Input SL",
                "taxpayer_type.entity_type": "legal_entity",
                "taxpayer_type.legal_entity_form": "sl",
            },
        )
        work_unit = create_work_unit(
            bucket_id=bucket_id,
            modelo="200",
            filing_year=2025,
            period=period,
            revision_id=snapshot.revision.id,
            clock=datetime(2026, 6, 26, 12, 0, tzinfo=UTC),
        )
        return build_work_calculate_input_bundle(
            work_unit_id=work_unit.work_unit_id,
            casilla_overrides={_M200_MANUAL_DECIMAL_CASILLA: raw_value},
            binding_overrides={},
            relation_overrides={},
            detail_rows=(),
            borrador_snapshot_id=None,
        )


@pytest.mark.parametrize("raw_value", _NON_CANONICAL_CASILLA_VALUES)
def test_casilla_override_refuses_non_canonical_decimal(raw_value: str, tmp_path: Path) -> None:
    """A non-canonical ``--casilla`` value refuses instead of being coerced."""
    with pytest.raises(ModeloCalculateDecimalInputError):
        _m200_bundle_with_casilla_value(raw_value, tmp_path=tmp_path)


@pytest.mark.parametrize("raw_value", _CANONICAL_CASILLA_VALUES)
def test_casilla_override_accepts_canonical_decimal(raw_value: str, tmp_path: Path) -> None:
    """The tightening refuses only non-canonical text; real amounts still parse.

    Sub-cent precision is included deliberately: capping the fractional part at
    two digits here would refuse a value the AEAT encoder is built to round.
    """
    bundle = _m200_bundle_with_casilla_value(raw_value, tmp_path=tmp_path)
    assert bundle.casilla_inputs[_M200_MANUAL_DECIMAL_CASILLA] == Decimal(raw_value)


# Modelo 303's informational period casilla is declared
# ``data_type = "period_code"``, a member of the registry's string scalar
# family but NOT the literal ``"text"``. While this boundary keyed its
# text-channel membership on ``data_type == "text"``, every non-``text``
# string family fell through to the Decimal parser: a perfectly valid
# ``--casilla decl.periodo=1T`` was refused as "not a decimal", and any
# string family whose values happen to parse as numbers would have been
# silently corrupted into a Decimal instead. Membership now derives from the
# type family, so these two tests fail if the literal is ever restored.
_M303_PERIOD_CASILLA: CasillaId = validated_casilla_id("decl.periodo", surface="_M303_PERIOD_CASILLA")
_M303_PROFILE_ID = "20000000-0000-4000-8000-000000000303"


def _m303_bundle_with_period_override(raw_value: str, *, tmp_path: Path) -> WorkCalculateInputBundle:
    """Drive the real calculate-input boundary with one ``period_code`` ``--casilla`` value."""
    period = Period.from_year_and_code(2025, "1T")
    snapshot = bundled_authority().snapshot("303", filing_year=2025, period=period.registry_token)
    bucket_id = _M303_PROFILE_ID
    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(bucket_id):
        # Seeded through a detached WorkflowState, never a repository read:
        # the capsule publishes by an atomic no-replace rename onto
        # ``buckets/<profile-id>``, which a workflow-state repository
        # construction would otherwise materialise first and collide with.
        register_minimal_profile(
            profile_id=bucket_id,
            overrides={
                "identity.tax_id": "B66012345",
                "identity.legal_name": "Calculate Input SL",
                "taxpayer_type.entity_type": "legal_entity",
                "taxpayer_type.legal_entity_form": "sl",
            },
        )
        work_unit = create_work_unit(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2025,
            period=period,
            revision_id=snapshot.revision.id,
            clock=datetime(2026, 6, 26, 12, 0, tzinfo=UTC),
        )
        return build_work_calculate_input_bundle(
            work_unit_id=work_unit.work_unit_id,
            casilla_overrides={_M303_PERIOD_CASILLA: raw_value},
            binding_overrides={},
            relation_overrides={},
            detail_rows=(),
            borrador_snapshot_id=None,
        )


def test_period_code_casilla_override_routes_to_the_text_channel(tmp_path: Path) -> None:
    """A ``period_code`` override lands on the string channel, never the Decimal one."""
    bundle = _m303_bundle_with_period_override("1T", tmp_path=tmp_path)

    assert bundle.text_casilla_inputs[_M303_PERIOD_CASILLA] == "1T"
    assert _M303_PERIOD_CASILLA not in bundle.casilla_inputs


def test_period_code_casilla_override_refuses_a_malformed_token(tmp_path: Path) -> None:
    """The declared family validator runs at the boundary, naming the data_type."""
    with pytest.raises(ModeloCalculateTextInputError) as exc_info:
        _m303_bundle_with_period_override("9Q", tmp_path=tmp_path)

    context = exc_info.value.context or {}
    assert context.get("data_type") == "period_code"
    assert context.get("value") == "9Q"


# ---------------------------------------------------------------------------
# The pre-2023 cotizaciones ceiling withholds the deduccion outright, so the
# ambiguous-relacion advisory -- which only ever names a descendant that
# CONTRIBUTES months -- has nothing to name. This locks the INTERACTION rather
# than re-proving either half: `resolve_maternidad_meses` already proves
# `pairs == ()` for a ceilinged year regardless of relacion
# (`test_maternidad_cotizaciones_ceiling.py`), and the ambiguous-relacion check
# reads its candidate set from exactly that field.
# ---------------------------------------------------------------------------

_MATERNIDAD_BUCKET_ID = "20000000-0000-4000-8000-000000000611"
_MATERNIDAD_CEILINGED_FILING_YEAR = 2022
_MATERNIDAD_CASILLA_ID: CasillaId = validated_casilla_id("0611", surface="_MATERNIDAD_CASILLA_ID")


def test_ambiguous_relacion_is_moot_while_the_cotizaciones_ceiling_withholds_everything(
    tmp_path: Path,
) -> None:
    """A default-relacion descendant contributing declared months to a pre-2023 filing.

    The descendant's relacion is the unstated default -- exactly the state the
    ambiguous-relacion advisory exists to disclose -- but the filing year predates
    2023, when Art. 81.1 was still capped at a cotizaciones figure this application
    cannot express. The deduccion is withheld entirely for that reason, so there is
    nothing left for the relacion ambiguity to threaten: only the cotizaciones
    advisory fires, never the ambiguous-relacion one.
    """
    period = Period.from_year_and_code(_MATERNIDAD_CEILINGED_FILING_YEAR, "0A")
    snapshot = bundled_authority().snapshot(
        "100",
        filing_year=_MATERNIDAD_CEILINGED_FILING_YEAR,
        period=period.registry_token,
    )
    child = DescendantInfo(
        birth_date=date(_MATERNIDAD_CEILINGED_FILING_YEAR - 1, 6, 1),
        meses_madre_trabajo=tuple(range(1, 13)),
    )
    descendant_overrides = dict(descendant_facts_from_list((child,)))

    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(_MATERNIDAD_BUCKET_ID):
        # Seeded through a detached WorkflowState, never a repository read:
        # the capsule publishes by an atomic no-replace rename onto
        # ``buckets/<profile-id>``, which a workflow-state repository
        # construction would otherwise materialise first and collide with.
        register_minimal_profile(
            profile_id=_MATERNIDAD_BUCKET_ID,
            overrides=descendant_overrides,
        )
        work_unit = create_work_unit(
            bucket_id=_MATERNIDAD_BUCKET_ID,
            modelo="100",
            filing_year=_MATERNIDAD_CEILINGED_FILING_YEAR,
            period=period,
            revision_id=snapshot.revision.id,
            clock=datetime(2026, 8, 5, 12, 0, tzinfo=UTC),
        )
        bundle = build_work_calculate_input_bundle(
            work_unit_id=work_unit.work_unit_id,
            casilla_overrides={},
            binding_overrides={},
            relation_overrides={},
            detail_rows=(),
            borrador_snapshot_id=None,
        )

    assert _MATERNIDAD_CASILLA_ID not in bundle.casilla_inputs
    source_kinds = {diagnostic.source_kind for diagnostic in bundle.shortcut_diagnostics}
    assert "maternidad_cotizaciones_ceiling_inexpressible" in source_kinds
    assert "maternidad_ambiguous_relacion" not in source_kinds


class TestMaternidadAdvisoryLengthIsBoundedByHouseholdSize:
    """Both maternidad advisories interpolate one entry per descendant.

    That makes their length DYNAMIC, which is what distinguishes this from the
    cotizaciones-ceiling crash: that message was a fixed string measured once
    and trimmed. These grow, so measuring one is measuring nothing. Past a
    household size the message overruns the diagnostic cap, the model refuses,
    and `calculate` exits with a raw validation error reaching the operator --
    a NON-blocking advisory stopping the filing outright, at exactly the moment
    it had something to say.

    Every case here is constructed ABOVE the count at which the unbounded form
    crossed the cap, never at one index, because a single-index construction is
    what let both of these ship.
    """

    #: The pydantic cap on ``CalculationSourceDiagnostic.message``.
    CAP = 512

    #: Comfortably past both observed crossings (13 withheld, 25 ambiguous),
    #: so a later message edit that lengthens the fixed prose is still covered.
    MANY = 60

    @staticmethod
    def _ids(count: int) -> tuple[str, ...]:
        return tuple(str(index) for index in range(count))

    def test_withheld_advisory_stays_within_the_cap_at_many_descendants(self) -> None:
        from .._calculate_input import _maternidad_meses_withheld_advisory

        advisory = _maternidad_meses_withheld_advisory(self._ids(self.MANY), validated_casilla_id("0611"))

        assert advisory is not None
        assert len(advisory.message) <= self.CAP

    def test_ambiguous_relacion_advisory_stays_within_the_cap_at_many_descendants(self) -> None:
        from .._calculate_input import _maternidad_ambiguous_relacion_advisory

        advisory = _maternidad_ambiguous_relacion_advisory(
            frozenset(self._ids(self.MANY)),
            validated_casilla_id("0611"),
        )

        assert advisory is not None
        assert len(advisory.message) <= self.CAP

    def test_both_advisories_hold_at_the_observed_crossing_points(self) -> None:
        """Pinned at the counts the review measured: 13 withheld, 25 ambiguous.

        Kept alongside the larger case so a regression that merely RAISES the
        threshold rather than removing it is still caught here.
        """
        from .._calculate_input import (
            _maternidad_ambiguous_relacion_advisory,
            _maternidad_meses_withheld_advisory,
        )

        casilla = validated_casilla_id("0611")
        for count in (13, 25, 26):
            withheld = _maternidad_meses_withheld_advisory(self._ids(count), casilla)
            ambiguous = _maternidad_ambiguous_relacion_advisory(frozenset(self._ids(count)), casilla)
            assert withheld is not None
            assert ambiguous is not None
            assert len(withheld.message) <= self.CAP, f"withheld overran at {count}"
            assert len(ambiguous.message) <= self.CAP, f"ambiguous overran at {count}"

    def test_the_unbounded_form_would_have_overrun(self) -> None:
        """Positive control: the bound is doing work, not decorating a short message.

        Reconstructs what an unbounded join of the same ids costs and asserts it
        exceeds the cap. Without this, every assertion above would pass equally
        well against a message that never approached the limit, and the tests
        would prove nothing about the defence.
        """
        from .._calculate_input import _bounded_descendant_ids, _maternidad_meses_withheld_advisory

        ids = self._ids(self.MANY)
        advisory = _maternidad_meses_withheld_advisory(ids, validated_casilla_id("0611"))
        assert advisory is not None

        bounded_term = _bounded_descendant_ids(ids)
        unbounded_term = ", ".join(ids)
        would_be = len(advisory.message) - len(bounded_term) + len(unbounded_term)

        assert would_be > self.CAP, "the control does not reach the cap, so the bound proves nothing"

    def test_the_bound_still_names_descendants_and_counts_the_rest(self) -> None:
        """Bounding must keep the advisory ACTIONABLE, not reduce it to a count.

        An operator needs at least one index to act on, and needs to know the
        list was truncated rather than complete -- otherwise a household of
        sixty reads as a household of three.
        """
        from .._calculate_input import _bounded_descendant_ids

        rendered = _bounded_descendant_ids(self._ids(self.MANY))

        assert rendered.startswith("0, 1, 2")
        assert rendered.endswith(f"and {self.MANY - 3} more")

    def test_a_small_household_is_named_in_full_with_no_remainder_clause(self) -> None:
        """The bound must not degrade the ordinary case it was added to protect."""
        from .._calculate_input import _bounded_descendant_ids

        assert _bounded_descendant_ids(("0", "1")) == "0, 1"
