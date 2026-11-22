"""A calendar whose IVA block leaves a yes/no question unanswered loads, and holds only what that question decides.

A profile that claims the Modelo IVA block owes four yes/no answers: REDEME,
the cash accounting regime, voluntary SII and the hydrocarbon deposit advance
payment deduction. With any of them unanswered the installed overview read
used to settle FAILED on ``ERROR_DEADLINES_PROFILE`` and the window showed a
loading error. The read now succeeds: every deadline the answered facts decide
stays a row, each Modelo 303 window the REDEME answer decides is held as an
undecided obligation with the door to the question, each unanswered question
arrives as a named warning, and answering them through the profile field edit
turns the 303 windows back into deadlines.

Every read and edit is a registered operation in a replayed persona world. No doubles.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ...adapters.persistence.storage.tests.profile_capsule_runtime import replace_test_profile_record
from ...application.overview.coverage import CoverageAdviceReason
from ...application.overview.read_payload import OverviewCalendarRead
from ...application.overview.read_request import OVERVIEW_READ_DEFINITION_IDS, OverviewReadKind, OverviewReadRequest
from ...application.overview.read_result import OverviewReadProjection
from ...application.user_profile.profile_operation_contracts import (
    PROFILE_PATCH_OPERATION_DEFINITION_ID,
    ProfilePatchOperationRequest,
    ProfilePatchValue,
)
from ...core.external_constants import OutputLanguage
from ...domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.iva_regime_vocabulary import (
    default_iva_regime,
    iva_regime_no_aplica_token,
    iva_regime_recargo_equivalencia_token,
    iva_regime_simplificado_token,
)
from ...domain.deadlines.profiles import MODELO_IVA_BLOCK_REQUIRED_PATHS
from ...domain.user_profile.values import create_user_profile_record
from .persona_materialisation import materialised_persona
from .persona_operations import run_operation, settle_operation
from .persona_replay_requests import load_profile_record
from .persona_world import PersonaWorld, ReplayScope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PERSONA = "autonomo-fontanero"
_YES_NO_PATHS = (
    "iva.redeme_enrolled",
    "iva.cash_accounting_regime_enrolled",
    "iva.voluntary_sii_enrolled",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
)
_REGIMES = {
    "general": default_iva_regime,
    "simplificado": iva_regime_simplificado_token,
    "recargo_equivalencia": iva_regime_recargo_equivalencia_token,
    "no_aplica": iva_regime_no_aplica_token,
}


def _answer(world: PersonaWorld, answers: dict[str, str]) -> None:
    """Answer profile questions through the profile edit, an explicit blank leaving one unanswered."""
    record = load_profile_record(world)
    settle_operation(
        world,
        PROFILE_PATCH_OPERATION_DEFINITION_ID,
        ProfilePatchOperationRequest(
            profile_id=world.profile_id,
            expected_revision=record.record_revision,
            expected_content_digest=record.content_digest,
            values=tuple(
                ProfilePatchValue(question_id=path.replace(".", "-").replace("_", "-"), value=value)
                for path, value in answers.items()
            ),
        ),
    )


def _read(world: PersonaWorld, kind: OverviewReadKind, year: int) -> OverviewReadProjection:
    query: dict[OverviewReadKind, dict[str, object]] = {
        OverviewReadKind.STATUS: {},
        OverviewReadKind.CALENDAR: {
            "from_date": date(year, 1, 1),
            "to_date": date(year, 12, 31),
            "show_suppressed": True,
        },
        OverviewReadKind.AGENDA: {"as_of": date(year, 1, 1)},
        OverviewReadKind.BACKLOG: {"from_date": date(year, 1, 1), "to_date": date(year, 12, 31)},
        OverviewReadKind.EXPLAIN: {
            "modelo": str(form_for_role("iva.periodic", authority=world.operation)),
            "year": year,
        },
    }
    request = OverviewReadRequest.model_validate(
        {"profile_id": world.profile_id, "kind": kind, "output_language": OutputLanguage.ES, **query[kind]},
    )
    return run_operation(world, OVERVIEW_READ_DEFINITION_IDS[kind], request, OverviewReadProjection)


def _unanswer_yes_no_facts(world: PersonaWorld, *, iva_regime: str | None = None) -> None:
    """Store the profile as one saved before the four questions were asked, optionally under another IVA regime.

    The profile edit refuses to blank a required question, so this state is
    reachable only from a record stored earlier, as the operator's was.
    """
    record = load_profile_record(world)
    facts = tuple(fact for fact in record.facts if fact.path not in _YES_NO_PATHS)
    if iva_regime is not None:
        facts = tuple(
            fact.model_copy(update={"value": iva_regime}) if fact.path == "iva.regime" else fact for fact in facts
        )
    replace_test_profile_record(
        create_user_profile_record(
            setup_state=record.setup_state,
            profile_id=record.profile_id,
            facts=facts,
            created_at=record.created_at,
            updated_at=record.updated_at,
            context=world.operation.profile_create_context(),
        ),
        root=world.storage_root,
    )
    stored = {fact.path for fact in load_profile_record(world).facts}
    assert not stored & set(_YES_NO_PATHS), stored & set(_YES_NO_PATHS)


def test_the_unanswered_iva_questions_hold_only_the_windows_they_decide(tmp_path: Path) -> None:
    assert set(_YES_NO_PATHS) <= set(MODELO_IVA_BLOCK_REQUIRED_PATHS)
    with materialised_persona(_PERSONA, tmp_path, ReplayScope.PROFILE, reuse=True) as replayed:
        world = replayed.world
        year = replayed.persona.fiscal_year.resolve(world.envelope)
        periodic = str(form_for_role("iva.periodic", authority=world.operation))
        answered = _read(world, OverviewReadKind.CALENDAR, year).payload
        _unanswer_yes_no_facts(world)
        unanswered = _read(world, OverviewReadKind.CALENDAR, year).payload
        _answer(world, dict.fromkeys(_YES_NO_PATHS, "false"))
        reanswered = _read(world, OverviewReadKind.CALENDAR, year).payload

    for payload in (answered, unanswered, reanswered):
        assert isinstance(payload, OverviewCalendarRead)
        assert payload.calendar is not None
    assert isinstance(answered, OverviewCalendarRead) and answered.calendar is not None
    assert isinstance(unanswered, OverviewCalendarRead) and unanswered.calendar is not None
    assert isinstance(reanswered, OverviewCalendarRead) and reanswered.calendar is not None
    before = answered.calendar.to_calendar()
    held = unanswered.calendar.to_calendar()
    after = reanswered.calendar.to_calendar()

    # ANTI-VACUITY: with every question answered the 303 quarters are deadlines.
    assert periodic in {entry.modelo for entry in before.entries}
    # Unanswered: the read loads, every row the answered facts decide stays, and each
    # modelo that leaves the schedule is held as undetermined, never dropped as not owed.
    assert held.taxpayer_model_declared
    kept = {entry.modelo for entry in held.entries}
    lost = {entry.modelo for entry in before.entries} - kept
    assert kept, kept
    assert kept <= {entry.modelo for entry in before.entries}, kept
    assert periodic in lost
    held_off = {entry.modelo for entry in held.suppressed_entries if entry.verdict is ApplicabilityVerdict.INCOMPLETE}
    advised = {item.modelo: item.reason for item in held.coverage.advised}
    undetermined = held_off | {m for m, r in advised.items() if r is CoverageAdviceReason.APPLICABILITY_UNDETERMINED}
    assert lost <= undetermined, (sorted(lost), sorted(undetermined))
    undecided = [entry for entry in held.suppressed_entries if entry.modelo == periodic]
    assert undecided
    assert all(entry.verdict is ApplicabilityVerdict.INCOMPLETE for entry in undecided)
    assert all(entry.actions for entry in undecided)
    assert all("REDEME" in entry.reason for entry in undecided)
    assert advised.get(periodic) is CoverageAdviceReason.APPLICABILITY_UNDETERMINED
    named = {warning.code: warning for warning in held.warnings}
    for path in _YES_NO_PATHS:
        assert path in named, path
        assert named[path].affected_modelos, path
    # Answered again through the profile edit: the same deadlines as before, no question left.
    assert [(e.modelo, e.period) for e in after.entries] == [(e.modelo, e.period) for e in before.entries]
    assert not {warning.code for warning in after.warnings} & set(_YES_NO_PATHS)


@pytest.mark.parametrize("regime", sorted(_REGIMES))
def test_every_iva_regime_loads_its_overview_reads_with_the_questions_unanswered(tmp_path: Path, regime: str) -> None:
    with materialised_persona(_PERSONA, tmp_path, ReplayScope.PROFILE, reuse=True) as replayed:
        world = replayed.world
        year = replayed.persona.fiscal_year.resolve(world.envelope)
        periodic = str(form_for_role("iva.periodic", authority=world.operation))
        _unanswer_yes_no_facts(world, iva_regime=str(_REGIMES[regime](authority=world.operation)))
        # Every read that projects the taxpayer shares the calendar's projection.
        reads = {
            kind: _read(world, kind, year).payload for kind in OverviewReadKind if kind is not OverviewReadKind.PREPARE
        }

    calendar = reads[OverviewReadKind.CALENDAR]
    assert isinstance(calendar, OverviewCalendarRead)
    assert calendar.calendar is not None
    held = calendar.calendar.to_calendar()
    # A missing answer is never read as "no": no 303 window becomes a deadline on it.
    assert periodic not in {entry.modelo for entry in held.entries}
    named = {warning.code for warning in held.warnings}
    assert set(_YES_NO_PATHS) <= named, set(_YES_NO_PATHS) - named
    assert all(payload is not None for payload in reads.values())
