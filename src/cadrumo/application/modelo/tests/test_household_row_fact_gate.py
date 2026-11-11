"""An ascendant stored without a NIF, or a descendant or ascendant without a name, refuses checking, filing and export with a typed refusal that names the fact.

The profile door admits the ascendant as a draft; the Modelo 100 design requires
its NIF on every ascendant row. The profile record goes through the production
profile resolver, its diagnostics persist as the revision's notes the way a
calculation persists them, and the application's own gate decides each action.
The refusal carries the profile door where the NIF is stated, and the NIF is
never replaced by a stand-in. The design also requires the surnames and name of every
descendant and ascendant, so a row that omits them is refused with the door for its
member kind. A household with those facts stated, with no ascendants, or with only a
child without a NIF is not refused.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from cadrumo.domain.user_profile.values import create_user_profile_record

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.errors.error_codes import get_registered_error_code
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ...operator_actions.catalogue import lookup_action
from ..bucket_unrouted_source_issues import unrouted_source_issues
from ..calculation_note_gate import (
    ModeloCalculationBlockedError,
    blocking_calculation_issues,
    require_work_unit_calculation_unblocked,
)
from ..calculation_screen import calculation_screen_stamp
from ..household_row_fact_gate import ModeloHouseholdRowFactUnstatedError
from ..printed_boxes import snapshot_printed_boxes
from ..profile_binding import resolve_profile_sourced_bindings
from .work_form_fixture import form_snapshot

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET = "0de41ce4-0000-4000-8000-000000000810"
_CLOCK = datetime(1980, 5, 21, 10, 0, tzinfo=UTC)
_NIF = "00000001R"
_ACTIONS = {"verify": "modelo.work.verify", "file": "modelo.work.file", "export": "modelo.export"}


def _filing_years(operation: PinnedAuthorityOperation) -> tuple[int, ...]:
    """The supported years whose own Modelo 100 edition lets a filing-grade check run."""
    return tuple(
        year
        for year in operation.supported_filing_years().years
        if operation.reachable_authority_grade("100", filing_year=year, period="0A") is RegistryAuthorityGrade.FILING
    )


def _record(operation: PinnedAuthorityOperation, *facts: UserProfileFact) -> UserProfileRecord:
    return create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET,
        facts=facts,
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=operation.profile_create_context(),
    )


def _ascendant(year: int, *, nif: str | None) -> tuple[UserProfileFact, ...]:
    parent = "renta_family.ascendiente.0"
    return (
        UserProfileFact(path="renta_family.ascendientes_count", value="1"),
        UserProfileFact(path=f"{parent}.birth_date", value=date(year - 78, 1, 8).isoformat()),
        UserProfileFact(path=f"{parent}.apellidos_nombre", value="Navarro Gil Carmen"),
        *(() if nif is None else (UserProfileFact(path=f"{parent}.nif", value=nif),)),
    )


def _work_unit(operation: PinnedAuthorityOperation, year: int) -> WorkUnit:
    snapshot = form_snapshot(operation, "100", year, "0A")
    period = Period.from_year_and_code(year, "0A")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET, modelo="100", filing_year=year, period=period, revision_id=snapshot.revision.id
        ),
        bucket_id=_BUCKET,
        modelo="100",
        filing_year=year,
        period=period,
        revision_id=snapshot.revision.id,
        name="household-fact",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _revision(operation: PinnedAuthorityOperation, year: int, record: UserProfileRecord) -> CalculationRevision:
    """The revision a calculation persists from what the profile resolver reports."""
    snapshot = form_snapshot(operation, "100", year, "0A")
    work_unit = _work_unit(operation, year)
    resolution = resolve_profile_sourced_bindings(
        snapshot, bucket_id=_BUCKET, profile_record=record, operation=operation
    )
    # The bare profile leaves other facts unanswered; those notes belong to other gates, so only the household's persist.
    issues = tuple(
        issue
        for issue in unrouted_source_issues(resolution.diagnostics, snapshot_printed_boxes(operation, snapshot))
        if issue.reason.startswith("household_")
    )
    stamp = calculation_screen_stamp(snapshot, operation=operation)
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            source_issues=issues,
            filing_instance_evidence=None,
            source_provenance=(),
            screen_stamp=stamp,
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        casilla_values={},
        observations=(),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        filing_instance_evidence=None,
        source_provenance=(),
        source_issues=issues,
        screen_stamp=stamp,
    )


def _context(error: ModeloHouseholdRowFactUnstatedError) -> dict[str, object]:
    """The operator-facing facts the refusal names: the missing fact and how many rows omit it."""
    assert error.context is not None
    return {name: error.context[name] for name in ("field", "count")}


def _household_reasons(revision: CalculationRevision) -> list[str]:
    """The household notes a revision persists."""
    return [issue.reason for issue in revision.source_issues]


def _gate(operation: PinnedAuthorityOperation, year: int, revision: CalculationRevision, action: str) -> None:
    require_work_unit_calculation_unblocked(
        work_unit=_work_unit(operation, year), revision=revision, action=action, operation=operation
    )


def test_an_ascendant_without_a_nif_refuses_every_action_with_the_profile_door(
    operation: PinnedAuthorityOperation,
) -> None:
    years = _filing_years(operation)
    assert years
    for year in years:
        revision = _revision(operation, year, _record(operation, *_ascendant(year, nif=None)))

        assert [issue.reason for issue in blocking_calculation_issues(revision)] == ["household_row_fact_unstated"], (
            year
        )
        for action, leaf in _ACTIONS.items():
            with pytest.raises(ModeloHouseholdRowFactUnstatedError) as refused:
                _gate(operation, year, revision, action)

            error = refused.value
            assert get_registered_error_code(error).code == "REFUSED_MODELO_HOUSEHOLD_ROW_FACT_UNSTATED"
            assert _context(error) == {"field": "renta_family.ascendiente.nif", "count": "1"}
            failure = error.precondition_failure
            assert failure is not None
            assert failure.subject_leaf_key == leaf
            assert failure.verdict.action is not None
            assert failure.verdict.action.action_id == "operator.profile.ascendiente"
            assert not isinstance(error, ModeloCalculationBlockedError)


def test_the_door_the_refusal_names_is_the_ascendant_list_command() -> None:
    assert lookup_action("operator.profile.ascendiente").target_command_key == "config.profile.ascendiente.list"


def test_an_ascendant_with_its_nif_is_not_refused(operation: PinnedAuthorityOperation) -> None:
    for year in _filing_years(operation):
        revision = _revision(operation, year, _record(operation, *_ascendant(year, nif=_NIF)))

        assert _household_reasons(revision) == [], year
        for action in _ACTIONS:
            _gate(operation, year, revision, action)


def test_a_household_without_ascendants_is_not_refused(operation: PinnedAuthorityOperation) -> None:
    for year in _filing_years(operation):
        unanswered = _revision(operation, year, _record(operation))
        declared_none = _revision(
            operation, year, _record(operation, UserProfileFact(path="renta_family.ascendientes_count", value="0"))
        )

        for revision in (unanswered, declared_none):
            assert _household_reasons(revision) == [], year
            for action in _ACTIONS:
                _gate(operation, year, revision, action)


def test_a_child_without_a_nif_is_not_refused_because_the_design_does_not_require_it(
    operation: PinnedAuthorityOperation,
) -> None:
    for year in _filing_years(operation):
        child = (
            UserProfileFact(path="renta_family.descendientes_count", value="1"),
            UserProfileFact(path="renta_family.descendiente.0.birth_date", value=date(year - 9, 3, 14).isoformat()),
            UserProfileFact(path="renta_family.descendiente.0.apellidos_nombre", value="Ortega Navarro Pablo"),
        )
        revision = _revision(operation, year, _record(operation, *child))

        assert _household_reasons(revision) == [], year
        _gate(operation, year, revision, "export")


def _descendant(year: int, *, name: str | None) -> tuple[UserProfileFact, ...]:
    child = "renta_family.descendiente.0"
    return (
        UserProfileFact(path="renta_family.descendientes_count", value="1"),
        UserProfileFact(path=f"{child}.birth_date", value=date(year - 9, 3, 14).isoformat()),
        *(() if name is None else (UserProfileFact(path=f"{child}.apellidos_nombre", value=name),)),
    )


def test_a_descendant_without_a_name_refuses_every_action_with_the_descendant_door(
    operation: PinnedAuthorityOperation,
) -> None:
    years = _filing_years(operation)
    assert years
    for year in years:
        revision = _revision(operation, year, _record(operation, *_descendant(year, name=None)))

        assert [issue.reason for issue in blocking_calculation_issues(revision)] == ["household_row_fact_unstated"], (
            year
        )
        for action, leaf in _ACTIONS.items():
            with pytest.raises(ModeloHouseholdRowFactUnstatedError) as refused:
                _gate(operation, year, revision, action)

            error = refused.value
            assert get_registered_error_code(error).code == "REFUSED_MODELO_HOUSEHOLD_ROW_FACT_UNSTATED"
            assert _context(error) == {"field": "renta_family.descendiente.apellidos_nombre", "count": "1"}
            failure = error.precondition_failure
            assert failure is not None
            assert failure.subject_leaf_key == leaf
            assert failure.verdict.action is not None
            assert failure.verdict.action.action_id == "operator.profile.descendiente"


def test_a_descendant_with_its_name_is_not_refused(operation: PinnedAuthorityOperation) -> None:
    for year in _filing_years(operation):
        revision = _revision(operation, year, _record(operation, *_descendant(year, name="Ortega Navarro Pablo")))

        assert _household_reasons(revision) == [], year
        for action in _ACTIONS:
            _gate(operation, year, revision, action)


def test_an_ascendant_without_a_name_is_refused_with_the_ascendant_door(operation: PinnedAuthorityOperation) -> None:
    for year in _filing_years(operation):
        facts = tuple(fact for fact in _ascendant(year, nif=_NIF) if not fact.path.endswith("apellidos_nombre"))
        revision = _revision(operation, year, _record(operation, *facts))

        with pytest.raises(ModeloHouseholdRowFactUnstatedError) as refused:
            _gate(operation, year, revision, "export")

        assert _context(refused.value) == {"field": "renta_family.ascendiente.apellidos_nombre", "count": "1"}
        failure = refused.value.precondition_failure
        assert failure is not None
        assert failure.verdict.action is not None
        assert failure.verdict.action.action_id == "operator.profile.ascendiente"


def test_the_descendant_door_is_the_descendant_list_command() -> None:
    assert lookup_action("operator.profile.descendiente").target_command_key == "config.profile.descendiente.list"


def test_only_the_ascendant_rows_that_omit_the_nif_are_counted(operation: PinnedAuthorityOperation) -> None:
    year = _filing_years(operation)[-1]
    first = "renta_family.ascendiente.0"
    second = "renta_family.ascendiente.1"
    facts = (
        UserProfileFact(path="renta_family.ascendientes_count", value="2"),
        UserProfileFact(path=f"{first}.birth_date", value=date(year - 78, 1, 8).isoformat()),
        UserProfileFact(path=f"{first}.nif", value=_NIF),
        UserProfileFact(path=f"{first}.apellidos_nombre", value="Navarro Gil Carmen"),
        UserProfileFact(path=f"{second}.apellidos_nombre", value="Navarro Gil Pedro"),
        UserProfileFact(path=f"{second}.birth_date", value=date(year - 80, 2, 9).isoformat()),
    )
    revision = _revision(operation, year, _record(operation, *facts))

    with pytest.raises(ModeloHouseholdRowFactUnstatedError) as refused:
        _gate(operation, year, revision, "file")

    assert _context(refused.value)["count"] == "1"
