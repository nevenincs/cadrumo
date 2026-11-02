"""The 2025 Modelo 100 form serves descendants and ascendants as row groups read from the stored household.

Each case runs the real path: a real profile record goes through the production
profile resolver, its row values and source traces are persisted onto a
calculation the way the calculation persists them, and the generated form
projects that calculation. A household the filer has not answered stays
unknown; one declared empty (a stated zero count) is known-empty; stored rows
are rows, up to the design's limit of 15 children.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context as _profile_creation_context_for_test,
)
from ....domain.contribuyente.descendant import DescendantInfo
from ....domain.contribuyente.descendant_facts import descendant_facts_from_list
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ..calculation_bucket_actions import _source_provenance_refs
from ..calculation_resolution import build_calculation_replay_payloads
from ..profile_binding import resolve_profile_sourced_bindings
from ..work_form_models import ModeloFormRepeatingBlock
from .work_form_fixture import built_form, form_snapshot

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET = "0de41ce4-0000-4000-8000-000000000702"
_T0 = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)
_CHILD_LIMIT = 15
_ASCENDANT_LIMIT = 4


def _record(*facts: UserProfileFact) -> UserProfileRecord:
    return _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET,
        facts=facts,
        created_at=_T0,
        updated_at=_T0,
        context=_profile_creation_context_for_test(),
    )


def _descendant_facts(
    operation: PinnedAuthorityOperation, descendants: tuple[DescendantInfo, ...]
) -> tuple[UserProfileFact, ...]:
    pairs = descendant_facts_from_list(descendants, authority=operation)
    return tuple(UserProfileFact(path=path, value=value) for path, value in pairs)


def _calculated(operation: PinnedAuthorityOperation, record: UserProfileRecord) -> CalculationRevision:
    snapshot = form_snapshot(operation, "100", 2025, "0A")
    resolution = resolve_profile_sourced_bindings(
        snapshot, bucket_id=_BUCKET, profile_record=record, operation=operation
    )
    payloads = build_calculation_replay_payloads(
        resolved_inputs={},
        resolved_bindings={},
        resolved_enum_bindings={},
        resolved_date_bindings={},
        resolved_relations={},
        resolved_row_bindings=resolution.row_binding_values,
    )
    work_id = "e" * 64
    base = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            source_transaction_ids=(),
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=work_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        created_at=_T0,
        updated_at=_T0,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return base.model_copy(
        update={
            "row_binding_values": payloads.row_binding_values,
            "source_provenance": _source_provenance_refs(resolution),
        }
    )


def _group(
    operation: PinnedAuthorityOperation, revision: CalculationRevision, group_id: str
) -> ModeloFormRepeatingBlock:
    form = built_form(operation, "100", 2025, "0A", revision=revision)
    return next(
        block
        for page in form.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, ModeloFormRepeatingBlock) and block.id == group_id
    )


def _cells(block: ModeloFormRepeatingBlock) -> list[dict[str | None, object]]:
    return [dict(zip(block.column_casilla_ids, row.values, strict=True)) for row in block.rows]


def test_the_groups_are_bounded_by_the_official_repeat_limits(operation: PinnedAuthorityOperation) -> None:
    revision = _calculated(operation, _record())

    children = _group(operation, revision, "hijo-rows")
    ascendants = _group(operation, revision, "ascendiente-rows")

    assert children.max_rows == _CHILD_LIMIT
    assert ascendants.max_rows == _ASCENDANT_LIMIT
    assert set(children.column_casilla_ids) == {"NIFDLG", "APENOMDLG", "FNACDLG", "MINUSDLG", "FALLDLG"}
    assert set(ascendants.column_casilla_ids) == {
        "DNIASDLG",
        "APENOMDLG_ASC",
        "ANOASDLG",
        "PCTMINASDLG",
        "CONVASDLG",
        "FALLASDLG",
    }


def test_an_unanswered_household_is_unknown_not_empty(operation: PinnedAuthorityOperation) -> None:
    revision = _calculated(operation, _record())

    children = _group(operation, revision, "hijo-rows")
    ascendants = _group(operation, revision, "ascendiente-rows")

    assert (children.rows_known, children.rows) == (False, ())
    assert (ascendants.rows_known, ascendants.rows) == (False, ())


def test_a_stated_zero_count_proves_the_group_empty(operation: PinnedAuthorityOperation) -> None:
    record = _record(
        UserProfileFact(path="renta_family.descendientes_count", value="0"),
        UserProfileFact(path="renta_family.ascendientes_count", value="0"),
    )

    revision = _calculated(operation, record)

    for group_id in ("hijo-rows", "ascendiente-rows"):
        group = _group(operation, revision, group_id)
        assert (group.rows_known, group.rows) == (True, ())


@pytest.mark.parametrize("count", ["1", "2", "15"])
def test_a_stated_non_zero_count_without_rows_stays_unknown(operation: PinnedAuthorityOperation, count: str) -> None:
    record = _record(
        UserProfileFact(path="renta_family.descendientes_count", value=count),
        UserProfileFact(path="renta_family.ascendientes_count", value=count),
    )

    revision = _calculated(operation, record)

    for group_id in ("hijo-rows", "ascendiente-rows"):
        group = _group(operation, revision, group_id)
        assert (group.rows_known, group.rows) == (False, ())


def test_a_zero_count_that_is_not_plain_text_zero_still_proves_the_group_empty(
    operation: PinnedAuthorityOperation,
) -> None:
    record = _record(UserProfileFact(path="renta_family.descendientes_count", value="0.00"))

    revision = _calculated(operation, record)

    assert (_group(operation, revision, "hijo-rows").rows_known, _group(operation, revision, "hijo-rows").rows) == (
        True,
        (),
    )
    assert _group(operation, revision, "ascendiente-rows").rows_known is False


def test_a_count_larger_than_the_stored_rows_serves_the_stored_rows(operation: PinnedAuthorityOperation) -> None:
    child = DescendantInfo(birth_date=date(2019, 3, 14), convive_con_contribuyente=True, nif="12345678Z")
    facts = (
        *_descendant_facts(operation, (child,)),
        UserProfileFact(path="renta_family.descendientes_count", value="3"),
    )

    revision = _calculated(operation, _record(*facts))

    group = _group(operation, revision, "hijo-rows")
    assert group.rows_known is True
    assert [row.index for row in group.rows] == [1]


def test_one_descendant_is_one_row_with_its_stored_facts_and_unknown_cells_elsewhere(
    operation: PinnedAuthorityOperation,
) -> None:
    child = DescendantInfo(birth_date=date(2019, 3, 14), convive_con_contribuyente=True, nif="12345678Z")
    revision = _calculated(operation, _record(*_descendant_facts(operation, (child,))))

    group = _group(operation, revision, "hijo-rows")

    assert group.rows_known is True
    assert [row.index for row in group.rows] == [1]
    (cells,) = _cells(group)
    assert cells["NIFDLG"] == "12345678Z"
    assert cells["FNACDLG"] == "2019-03-14"
    # No stored leaf states the name or the official disability clave, so those cells stay unknown.
    assert cells["APENOMDLG"] is None
    assert cells["MINUSDLG"] is None
    assert cells["FALLDLG"] is None
    assert _group(operation, revision, "ascendiente-rows").rows_known is False


def test_the_design_maximum_of_descendants_is_served_in_stored_order(operation: PinnedAuthorityOperation) -> None:
    children = tuple(
        DescendantInfo(birth_date=date(2000 + index, 1, 1), convive_con_contribuyente=True)
        for index in range(_CHILD_LIMIT)
    )
    revision = _calculated(operation, _record(*_descendant_facts(operation, children)))

    group = _group(operation, revision, "hijo-rows")

    assert group.rows_known is True
    assert [row.index for row in group.rows] == list(range(1, _CHILD_LIMIT + 1))
    assert [cells["FNACDLG"] for cells in _cells(group)] == [f"{2000 + index}-01-01" for index in range(_CHILD_LIMIT)]
    assert len(group.rows) == group.max_rows
