"""The setup flow writes the RIRPF art. 7 criterion for one ejercicio at a time.

The imputation resolver reads only facts dated into the ejercicio, and the
election binds three years, so a write for one ejercicio must keep what earlier
ejercicios state. These tests drive the real wizard patch and full-flow writers
against an encrypted profile and read the result back through the resolver.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.aggregation.renta_imputation import (
    ActivityImputationCriterion,
    declared_imputation_criteria,
)
from cadrumo.application.user_profile.capsule_record import ProfileRecordConflictError
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.application.wizard.catalogue import build_setup_flow
from cadrumo.application.wizard.commands import persist_full_flow_answers, run_wizard_persistence_path
from cadrumo.application.wizard.errors import WizardMissingFlagError, WizardValidationError
from cadrumo.application.wizard.imputation_election import (
    ACCOUNTING_PROFILE_PATH,
    ACCOUNTING_QUESTION_ID,
    CRITERION_PROFILE_PATH,
    CRITERION_QUESTION_ID,
    YEAR_QUESTION_ID,
    election_changes,
)
from cadrumo.application.wizard.patch_edit import apply_profile_patch
from cadrumo.application.wizard.persistence import project_answers
from cadrumo.core.config import override_settings
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.user_profile.values import UserProfileRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REGIME_QUESTION_ID = "irpf-estimation-regime"
_REGIME_PATH = "irpf.estimation_regime"
_FIRST = 2000
_SECOND = 2001
_THIRD = 2002


class _World:
    """One registered, authenticated profile and the wizard flow pinned to its authority."""

    def __init__(self, profile_id: str, operation: PinnedAuthorityOperation) -> None:
        self.profile_id = profile_id
        self.operation = operation
        self.flow = build_setup_flow(operation)

    def record(self) -> UserProfileRecord:
        return ProfileRecordRepository.for_current_session(
            self.profile_id, profile_decode_context=self.operation.profile_decode_context()
        ).load(self.profile_id)

    def patch(self, supplied: dict[str, str]) -> UserProfileRecord:
        current = self.record()
        return apply_profile_patch(
            flow=self.flow,
            profile_id=self.profile_id,
            expected_revision=current.record_revision,
            expected_content_digest=current.content_digest,
            supplied=supplied,
            colegio_concertado=None,
            operation=self.operation,
        )

    def criteria(self):
        return declared_imputation_criteria(self.record())


@pytest.fixture
def world(tmp_path: Path) -> Iterator[_World]:
    secret = f"imputation-election-{tmp_path.name}"
    with (
        override_settings(cadrumo_output_language="", cadrumo_secret_passphrase=secret),
        isolated_profile_storage_root(tmp_path=tmp_path),
        bundled_indexed_authority().operation() as operation,
    ):
        outcome = register_profile_with_credentials(
            label="Imputation election",
            passphrase=secret,
            profile_create_context=operation.profile_create_context(),
            profile_decode_context=operation.profile_decode_context(),
        )
        authenticate_profile_for_invocation(
            name=outcome.label,
            passphrase_callback=secret.__str__,
            profile_decode_context=operation.profile_decode_context(),
        )
        register_minimal_profile(profile_id=outcome.profile_id)
        yield _World(outcome.profile_id, operation)


def _election(world: _World, year: int, criterion: str, *, accounting: str | None = None) -> dict[str, str]:
    supplied = {CRITERION_QUESTION_ID: criterion, YEAR_QUESTION_ID: str(year)}
    if accounting is not None:
        supplied[ACCOUNTING_QUESTION_ID] = accounting
    return supplied


def _facts_at(record: UserProfileRecord, path: str) -> list[tuple[date | None, date | None, object]]:
    return sorted(
        ((fact.valid_from, fact.valid_to, fact.value) for fact in record.facts if fact.path == path),
        key=lambda item: item[0] or date.min,
    )


def test_a_non_interactive_run_leaves_the_election_absent(world: _World) -> None:
    before = world.record()
    values, _changed = run_wizard_persistence_path(
        world.flow,
        "edit",
        {},
        {},
        scalar_profile_values={},
        quiet=False,
        accept_defaults=True,
        profile_name="Imputation election",
        profile_id=world.profile_id,
        operation=world.operation,
    )
    after = world.record()
    assert CRITERION_PROFILE_PATH not in values
    assert ACCOUNTING_PROFILE_PATH not in values
    assert _facts_at(after, CRITERION_PROFILE_PATH) == []
    assert _facts_at(after, ACCOUNTING_PROFILE_PATH) == []
    assert after.content_digest == before.content_digest
    assert world.criteria().declared(_FIRST) is None


def test_the_quiet_edit_route_writes_the_flags_it_was_given_as_dated_facts(world: _World) -> None:
    explicit = _election(world, _FIRST, "cobros_y_pagos", accounting="false")

    values, changed = run_wizard_persistence_path(
        world.flow,
        "edit",
        dict(explicit),
        explicit,
        scalar_profile_values={},
        quiet=True,
        accept_defaults=False,
        profile_name="Imputation election",
        profile_id=world.profile_id,
        operation=world.operation,
    )

    assert changed
    assert values[CRITERION_PROFILE_PATH] == "cobros_y_pagos"
    assert _facts_at(world.record(), CRITERION_PROFILE_PATH) == [
        (date(_FIRST, 1, 1), date(_FIRST, 12, 31), "cobros_y_pagos")
    ]
    assert world.criteria().declared(_FIRST) is ActivityImputationCriterion.COBROS_Y_PAGOS


def test_an_answer_is_dated_to_its_ejercicio_and_the_resolver_reads_it_there_only(world: _World) -> None:
    world.patch(_election(world, _FIRST, "devengo"))

    assert _facts_at(world.record(), CRITERION_PROFILE_PATH) == [(date(_FIRST, 1, 1), date(_FIRST, 12, 31), "devengo")]
    criteria = world.criteria()
    assert criteria.declared(_FIRST) is ActivityImputationCriterion.DEVENGO
    assert criteria.declared(_SECOND) is None
    assert criteria.declared(_FIRST - 1) is None


def test_answers_for_different_ejercicios_both_survive(world: _World) -> None:
    world.patch(_election(world, _FIRST, "cobros_y_pagos", accounting="false"))
    world.patch(_election(world, _SECOND, "devengo"))

    criteria = world.criteria()
    assert criteria.declared(_FIRST) is ActivityImputationCriterion.COBROS_Y_PAGOS
    assert criteria.declared(_SECOND) is ActivityImputationCriterion.DEVENGO
    assert [year for year, _end, _value in _facts_at(world.record(), CRITERION_PROFILE_PATH)] == [
        date(_FIRST, 1, 1),
        date(_SECOND, 1, 1),
    ]
    assert _facts_at(world.record(), ACCOUNTING_PROFILE_PATH) == [(date(_FIRST, 1, 1), date(_FIRST, 12, 31), False)]


def test_re_answering_an_ejercicio_replaces_only_that_ejercicio(world: _World) -> None:
    world.patch(_election(world, _FIRST, "devengo"))
    world.patch(_election(world, _SECOND, "devengo"))

    # The earlier ejercicio is not the effective one at the path, so the writer
    # must still see this as a change.
    revision = world.record().record_revision
    world.patch(_election(world, _FIRST, "cobros_y_pagos"))

    criteria = world.criteria()
    assert world.record().record_revision == revision + 1
    assert criteria.declared(_FIRST) is ActivityImputationCriterion.COBROS_Y_PAGOS
    assert criteria.declared(_SECOND) is ActivityImputationCriterion.DEVENGO
    assert len(_facts_at(world.record(), CRITERION_PROFILE_PATH)) == 2


def test_stating_the_same_answer_again_publishes_nothing(world: _World) -> None:
    world.patch(_election(world, _FIRST, "devengo"))
    before = world.record()

    world.patch(_election(world, _FIRST, "devengo"))

    assert world.record().record_revision == before.record_revision
    assert world.record().content_digest == before.content_digest


def test_clearing_an_ejercicio_clears_that_ejercicio_only(world: _World) -> None:
    world.patch(_election(world, _FIRST, "devengo", accounting="false"))
    world.patch(_election(world, _SECOND, "cobros_y_pagos", accounting="false"))

    world.patch({CRITERION_QUESTION_ID: "", ACCOUNTING_QUESTION_ID: "", YEAR_QUESTION_ID: str(_FIRST)})

    criteria = world.criteria()
    assert criteria.declared(_FIRST) is None
    assert criteria.declared(_SECOND) is ActivityImputationCriterion.COBROS_Y_PAGOS
    assert _facts_at(world.record(), CRITERION_PROFILE_PATH) == [
        (date(_SECOND, 1, 1), date(_SECOND, 12, 31), "cobros_y_pagos")
    ]
    assert _facts_at(world.record(), ACCOUNTING_PROFILE_PATH) == [(date(_SECOND, 1, 1), date(_SECOND, 12, 31), False)]

    world.patch({CRITERION_QUESTION_ID: "", YEAR_QUESTION_ID: str(_SECOND)})
    assert _facts_at(world.record(), CRITERION_PROFILE_PATH) == []
    assert world.criteria().declared(_SECOND) is None


def test_cash_with_no_accounting_and_a_regime_is_usable_for_that_ejercicio(world: _World) -> None:
    world.patch({_REGIME_QUESTION_ID: "directa_simplificada"})
    world.patch(_election(world, _FIRST, "cobros_y_pagos", accounting="false"))

    criteria = world.criteria()
    assert criteria.usable(_FIRST) is ActivityImputationCriterion.COBROS_Y_PAGOS
    assert criteria.usable(_SECOND) is None


def test_cash_is_not_usable_with_accounting_or_without_stating_it(world: _World) -> None:
    world.patch({_REGIME_QUESTION_ID: "directa_simplificada"})
    world.patch(_election(world, _FIRST, "cobros_y_pagos", accounting="true"))
    world.patch(_election(world, _SECOND, "cobros_y_pagos"))

    criteria = world.criteria()
    assert criteria.declared(_FIRST) is ActivityImputationCriterion.COBROS_Y_PAGOS
    assert criteria.usable(_FIRST) is None
    assert criteria.usable(_SECOND) is None


def test_the_accounting_answer_alone_is_dated_and_leaves_the_criterion_alone(world: _World) -> None:
    world.patch(_election(world, _FIRST, "devengo"))
    world.patch({ACCOUNTING_QUESTION_ID: "true", YEAR_QUESTION_ID: str(_SECOND)})

    assert _facts_at(world.record(), ACCOUNTING_PROFILE_PATH) == [(date(_SECOND, 1, 1), date(_SECOND, 12, 31), True)]
    assert world.criteria().declared(_FIRST) is ActivityImputationCriterion.DEVENGO


def test_answers_that_are_not_supplied_are_preserved_by_the_patch_path(world: _World) -> None:
    world.patch(_election(world, _FIRST, "cobros_y_pagos", accounting="false"))
    world.patch(_election(world, _SECOND, "devengo"))
    before = {path: _facts_at(world.record(), path) for path in (CRITERION_PROFILE_PATH, ACCOUNTING_PROFILE_PATH)}

    world.patch({_REGIME_QUESTION_ID: "objetiva"})
    world.patch({YEAR_QUESTION_ID: str(_THIRD)})

    after = {path: _facts_at(world.record(), path) for path in (CRITERION_PROFILE_PATH, ACCOUNTING_PROFILE_PATH)}
    assert after == before


def test_a_full_flow_run_dates_the_answer_and_preserves_what_it_did_not_state(world: _World) -> None:
    world.patch(_election(world, _FIRST, "cobros_y_pagos", accounting="false"))
    answers = _answers_without_election(world)

    # A run that states nothing about the election keeps every ejercicio.
    persist_full_flow_answers(world.flow, answers, profile_id=world.profile_id, operation=world.operation)
    assert world.criteria().declared(_FIRST) is ActivityImputationCriterion.COBROS_Y_PAGOS

    stated = answers.model_copy(
        update={
            "irpf_activity_income_imputation_criterion": "devengo",
            "irpf_activity_income_imputation_year": str(_SECOND),
            "irpf_codigo_comercio_accounting": "",
        }
    )
    values = persist_full_flow_answers(world.flow, stated, profile_id=world.profile_id, operation=world.operation)

    criteria = world.criteria()
    assert criteria.declared(_FIRST) is ActivityImputationCriterion.COBROS_Y_PAGOS
    assert criteria.declared(_SECOND) is ActivityImputationCriterion.DEVENGO
    assert values[CRITERION_PROFILE_PATH] == "devengo"
    assert all(fact.valid_from is not None for fact in world.record().facts if fact.path == CRITERION_PROFILE_PATH)


def test_a_full_flow_answer_without_its_ejercicio_is_refused_and_writes_nothing(world: _World) -> None:
    answers = _answers_without_election(world)
    stated = answers.model_copy(update={"irpf_activity_income_imputation_criterion": "devengo"})
    before = world.record()

    with pytest.raises(WizardMissingFlagError):
        persist_full_flow_answers(world.flow, stated, profile_id=world.profile_id, operation=world.operation)

    assert world.record().content_digest == before.content_digest


def test_a_stale_revision_is_refused_and_writes_nothing(world: _World) -> None:
    stale = world.record()
    world.patch({_REGIME_QUESTION_ID: "objetiva"})
    current = world.record()

    with pytest.raises(ProfileRecordConflictError):
        apply_profile_patch(
            flow=world.flow,
            profile_id=world.profile_id,
            expected_revision=stale.record_revision,
            expected_content_digest=stale.content_digest,
            supplied=_election(world, _FIRST, "devengo"),
            colegio_concertado=None,
            operation=world.operation,
        )

    assert world.record().content_digest == current.content_digest
    assert _facts_at(world.record(), CRITERION_PROFILE_PATH) == []


@pytest.mark.parametrize("stated", [CRITERION_QUESTION_ID, ACCOUNTING_QUESTION_ID])
def test_an_answer_without_an_ejercicio_is_refused(world: _World, stated: str) -> None:
    before = world.record()
    value = "devengo" if stated == CRITERION_QUESTION_ID else "false"

    with pytest.raises(WizardMissingFlagError):
        world.patch({stated: value})

    assert world.record().content_digest == before.content_digest


def test_an_ejercicio_alone_writes_nothing(world: _World) -> None:
    before = world.record()

    world.patch({YEAR_QUESTION_ID: str(_FIRST)})

    assert world.record().content_digest == before.content_digest


def test_an_unknown_criterion_is_refused_at_the_boundary(world: _World) -> None:
    with pytest.raises(WizardValidationError):
        election_changes(world.flow, _election(world, _FIRST, "caja"))


def _answers_without_election(world: _World) -> BaseModel:
    """Return the answers a run states when it was not asked about the election.

    A run's answers carry the election only when the person supplied it; the
    stored values at those paths are one fact per ejercicio, not one answer.
    """
    values = record_to_path_values(world.record())
    values.pop(CRITERION_PROFILE_PATH, None)
    values.pop(ACCOUNTING_PROFILE_PATH, None)
    return project_answers(world.flow, values)
