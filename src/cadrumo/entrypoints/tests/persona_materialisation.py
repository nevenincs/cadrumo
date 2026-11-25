"""Replay a canonical persona into a registered profile through production operations only.

A persona (``dev/fixtures/personas``, read by :mod:`cadrumo.tests.personas`)
reaches its profile the way an operator's input does: the registered wizard
patch, field and repeatable-row mutations, the household replacements, the
own bank accounts and their designations, the suffered-withholding record, the statement import, single classification,
invoice recording and linking, evidence intake and attachment, and, in the
history scope, the local observations of returns the taxpayer holds, the
withholding capture of every rent payment on leased premises, the filed
capture of every return filed with the AEAT, and the work create, calculate,
verify and local file of every return the persona has already filed (create
and calculate only for a calculated return), each submitted to the production
registry's supervisor and settled. The filed capture reads a recorded AEAT
register in place of the AEAT Sede; nothing after that read is replaced.
Nothing is
written to storage by any other route. A persona block that no operation can
record is returned in :attr:`MaterialisedPersona.not_loaded` with its reason,
never written another way.

Every operation runs at the persona's scenario instant, including the
registration of the profile it runs against.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from ...adapters.persistence.profile.tests.sealed_profile_world import (
    SealedProfileWorld,
    copied_profile_world,
    derived_profile_world,
)
from ...adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from ...adapters.persistence.storage.tests.profile_session_setup import reset_test_profile_session
from ...application.user_profile.profile_operation_contracts import (
    PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID,
    ProfileCompleteSetupOperationRequest,
)
from ...application.user_profile.validation import reject_invalid_profile_facts
from ...core.config import load_settings
from ...core.time.clock import frozen_clock
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext
from ...domain.user_profile.errors import ProfileSchemaValidationError
from ...domain.user_profile.values import ProfileSetupState
from ...tests.persona_types import Persona, YearEnvelope
from ...tests.personas import persona_inputs_digest, read_persona
from .persona_history_replay import (
    _replay_attested_returns,
    _replay_history,
    _replay_records,
    attested_returns_to_replay,
)
from .persona_operations import settle_operation
from .persona_own_accounts import replay_own_accounts
from .persona_prior_values import PriorValueAttestationError, check_prior_value_bindings
from .persona_rental_replay import replay_rentals
from .persona_replay_profile import (
    _imported_transactions,
    _replay_documents,
    _replay_household,
    _replay_inventory,
    _replay_ledger,
    _replay_profile,
    _replay_withholding,
)
from .persona_replay_requests import _state_filing_names, load_profile_record
from .persona_work_inputs import WorkInputError, check_work_inputs
from .persona_world import (
    PERSONA_ACTOR,
    MaterialisedPersona,
    NotLoaded,
    PersonaMaterialisationError,
    PersonaWorld,
    ReplayScope,
    _operations_over,
    _registered_world,
    _scenario,
    persona_world,
    scenario_instant,
    year_envelope,
)


def _complete_setup(world: PersonaWorld) -> bool:
    """Declare the replayed profile's setup complete through the production operation; whether it now is.

    The setup flow ends with that declaration, which modelo work waits on. The
    operation refuses a profile its complete-profile judgement rejects, so that
    same judgement decides first whether to ask it.
    """
    record = load_profile_record(world)
    if record.setup_state is ProfileSetupState.COMPLETE:
        return True
    try:
        reject_invalid_profile_facts(
            str(world.profile_id),
            record.facts,
            require_complete=True,
            schema=world.operation.profile_decode_context().schema,
        )
    except ProfileSchemaValidationError:
        return False
    settle_operation(
        world,
        PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID,
        ProfileCompleteSetupOperationRequest(
            profile_id=world.profile_id,
            expected_revision=record.record_revision,
            expected_content_digest=record.content_digest,
        ),
    )
    return load_profile_record(world).setup_state is ProfileSetupState.COMPLETE


def _not_loaded(
    persona: Persona, scope: ReplayScope, envelope: YearEnvelope, *, setup_complete: bool | None
) -> tuple[NotLoaded, ...]:
    """The persona facts no production operation recorded within ``scope``, and why.

    A block outside the scope was never attempted, so it is absent from the
    scope's result rather than reported as one no operation can record. A
    return-history record a lowered horizon put below the floor is reported
    within the records scope: the application refuses its year.
    """
    found = [
        NotLoaded(block=block, reason="no production operation records this block")
        for block in persona.declared_blocks()
    ]
    if scope.includes(ReplayScope.RECORDS):
        found.extend(
            NotLoaded(block=record.block, reason=record.reason(envelope))
            for record in persona.below_floor
            if record.history
        )
    if setup_complete is False:
        found.append(
            NotLoaded(
                block="setup",
                reason="the persona leaves a profile answer a complete profile requires missing, so its setup cannot be completed",
            )
        )
    if not scope.includes(ReplayScope.FULL):
        return tuple(found)
    if any(item.origin == "payer_certificate" for item in persona.withholding_certificates):
        found.append(
            NotLoaded(
                block="withholding_certificates",
                reason=(
                    "the retención-soportada record operation takes a payer certificate's bytes for origin "
                    "payer_certificate and the persona references no certificate document"
                ),
            )
        )
    if any(item.cotizaciones_seguridad_social is not None for item in persona.withholding_certificates):
        found.append(
            NotLoaded(
                block="withholding_certificates.cotizaciones_seguridad_social",
                reason=(
                    "no operation records an employee's Seguridad Social contributions and no Modelo 100 binding "
                    "sources the work-income deductible expense they enter"
                ),
            )
        )
    return tuple(found)


def materialise_persona(
    persona: Persona, world: PersonaWorld, scope: ReplayScope = ReplayScope.FULL, *, complete_setup: bool = True
) -> MaterialisedPersona:
    """Replay ``persona`` into ``world``'s profile through production operations, as far as ``scope`` reaches.

    With ``complete_setup`` the replay ends as the setup flow does, declaring
    the setup complete; without it the profile stays in setup, the state the
    onboarding review opens.
    """
    try:
        check_work_inputs(persona, world.envelope, world.operation)
    except WorkInputError as error:
        raise PersonaMaterialisationError(str(error)) from error
    try:
        check_prior_value_bindings(persona.attested_prior_values, world.envelope, world.operation)
    except PriorValueAttestationError as error:
        raise PersonaMaterialisationError(f"{persona.id}: {error}") from error
    transactions: dict[str, str] = {}
    invoices: dict[str, str] = {}
    evidence: dict[str, str] = {}
    filings: dict[str, str] = {}
    calculations: dict[str, str] = {}
    with frozen_clock(world.as_of):
        _replay_profile(persona, world)
        if scope.includes(ReplayScope.HOUSEHOLD):
            _replay_household(persona, world)
        if scope.includes(ReplayScope.FULL):
            replay_own_accounts(persona, world.profile_id, partial(settle_operation, world))
            _replay_withholding(persona, world)
            transactions = _imported_transactions(persona, world)
            invoices = _replay_ledger(persona, world, transactions)
            replay_rentals(
                persona,
                world.profile_id,
                world.envelope,
                transactions,
                actor=PERSONA_ACTOR,
                settle=partial(settle_operation, world),
                load_record=partial(load_profile_record, world),
            )
            _state_filing_names(persona, world)
            evidence = _replay_documents(persona, world, transactions)
            _replay_inventory(persona, world, transactions)
        setup_complete = _complete_setup(world) if complete_setup else None
        if scope.includes(ReplayScope.RECORDS) and (
            persona.filed_returns
            or persona.calculated_returns
            or persona.local_observations
            or persona.aeat_filings
            or (scope.includes(ReplayScope.HISTORY) and attested_returns_to_replay(persona, world.envelope))
        ):
            if setup_complete is not True:
                raise PersonaMaterialisationError(f"{persona.id}: replaying its returns needs a completed setup")
            _replay_records(persona, world, transactions=transactions, invoices=invoices)
            if scope.includes(ReplayScope.HISTORY):
                filings, calculations = _replay_history(persona, world)
                calculations |= _replay_attested_returns(persona, world)
    return MaterialisedPersona(
        persona=persona,
        world=world,
        scope=scope,
        transactions=transactions,
        invoices=invoices,
        evidence=evidence,
        not_loaded=_not_loaded(persona, scope, world.envelope, setup_complete=setup_complete),
        filings=filings,
        calculations=calculations,
    )


_REPLAYED_IDS = "persona-materialisation.json"
"""Beside the storage root of a sealed replay: the ids the replay minted, which a copy reads back."""


def _sealed_replay(
    persona: Persona,
    scope: ReplayScope,
    as_of: datetime,
    base: SealedProfileWorld,
    decode_context: ProfileDecodeContext,
    *,
    complete_setup: bool,
    envelope: YearEnvelope,
) -> SealedProfileWorld:
    """This run's world holding ``persona`` replayed to ``scope`` into ``base``, replayed on first use anywhere in the run."""

    def replay(profile_id: UUID) -> None:
        root = load_settings().cadrumo_storage_root
        if root is None:
            raise PersonaMaterialisationError("a sealed replay runs inside an isolated storage root")
        with (
            TemporaryDirectory(prefix="persona-inputs-") as inputs,
            _operations_over(
                root,
                profile_id,
                workdir=Path(inputs),
                as_of=as_of,
                envelope=envelope,
                attested_prior_values=persona.attested_prior_values,
                work_inputs=persona.work_inputs,
                work_income_none_statements=persona.work_income_none_statements,
            ) as world,
        ):
            replayed = materialise_persona(persona, world, scope, complete_setup=complete_setup)
        ids = {
            "transactions": replayed.transactions,
            "invoices": replayed.invoices,
            "evidence": replayed.evidence,
            "filings": replayed.filings,
            "calculations": replayed.calculations,
            "setup_complete": (all(item.block != "setup" for item in replayed.not_loaded) if complete_setup else None),
        }
        (root.parent / _REPLAYED_IDS).write_text(json.dumps(ids, sort_keys=True), encoding="utf-8")

    key = (
        "persona replay",
        persona.id,
        scope.value,
        persona_inputs_digest(persona),
        as_of.isoformat(),
        f"envelope {envelope.floor}..{envelope.horizon}",
        "setup completed" if complete_setup else "setup open",
    )
    return derived_profile_world(base, key, replay, profile_decode_context=decode_context)


@contextmanager
def _reused_persona_world(
    persona: Persona,
    scope: ReplayScope,
    tmp_path: Path,
    *,
    as_of: datetime,
    complete_setup: bool,
    envelope: YearEnvelope,
) -> Generator[MaterialisedPersona]:
    """Open this consumer's own copy of the run's replay of ``persona``, replaying it only when the run has none."""
    with bundled_indexed_authority().operation(), _scenario(as_of):
        _create_context, decode_context = profile_authority_contexts()
        sealed = _sealed_replay(
            persona,
            scope,
            as_of,
            _registered_world(persona, as_of),
            decode_context,
            complete_setup=complete_setup,
            envelope=envelope,
        )
        with copied_profile_world(sealed, tmp_path / "runtime", profile_decode_context=decode_context) as (
            root,
            profile_id,
        ):
            ids = json.loads((root.parent / _REPLAYED_IDS).read_text(encoding="utf-8"))
            try:
                with _operations_over(
                    root,
                    profile_id,
                    workdir=tmp_path / "inputs",
                    as_of=as_of,
                    envelope=envelope,
                    attested_prior_values=persona.attested_prior_values,
                    work_inputs=persona.work_inputs,
                    work_income_none_statements=persona.work_income_none_statements,
                ) as world:
                    yield MaterialisedPersona(
                        persona=persona,
                        world=world,
                        scope=scope,
                        transactions=ids["transactions"],
                        invoices=ids["invoices"],
                        evidence=ids["evidence"],
                        not_loaded=_not_loaded(persona, scope, envelope, setup_complete=ids["setup_complete"]),
                        filings=ids["filings"],
                        calculations=ids["calculations"],
                    )
            finally:
                reset_test_profile_session()


@contextmanager
def materialised_persona(
    persona_id: str,
    tmp_path: Path,
    scope: ReplayScope = ReplayScope.FULL,
    *,
    reuse: bool = False,
    complete_setup: bool = True,
    read_on: datetime | None = None,
    horizon: int | None = None,
) -> Generator[MaterialisedPersona]:
    """Read one persona, open its world at its scenario instant and replay it there as far as ``scope`` reaches.

    With ``read_on`` the world is opened, and the persona signs in, on that
    later day instead, for a scenario read when the persona's own instant has
    passed: a session opened at that instant would have ended by then.

    A replay of the full ledger takes tens of seconds. With ``reuse`` the run
    replays a persona at a scope once into a sealed world keyed by the
    persona's input files, the scope, the scenario instant and the authority
    generation, and every consumer receives its own filesystem copy of it: a
    write to one copy reaches no other and never the sealed world. A consumer
    that mutates the profile may reuse; one that needs the replay to run
    afresh does not. ``complete_setup`` is as :func:`materialise_persona` takes it.

    With ``horizon`` the persona is read as if the registry's horizon were that
    earlier supported year: its year tokens and its scenario clock move down
    with it, so a scenario written against ``horizon-1`` is replayed for an
    earlier supported year. The floor stays the registry's own, so a return
    history record or expectation that moves below it is left out of the
    replay and listed in :attr:`Persona.below_floor`, its history records
    also in :attr:`MaterialisedPersona.not_loaded`; a return that depends on
    one meets the application's own refusal.
    """
    with bundled_indexed_authority().operation() as operation:
        envelope = year_envelope(operation)
    lowered = horizon is not None and horizon != envelope.horizon
    if horizon is not None:
        if not envelope.floor <= horizon <= envelope.horizon:
            raise PersonaMaterialisationError(f"horizon {horizon} lies outside {envelope.floor}..{envelope.horizon}")
        envelope = dataclasses.replace(envelope, horizon=horizon)
    persona = read_persona(persona_id, envelope=envelope, omit_below_floor=lowered)
    as_of = scenario_instant(persona, envelope) if read_on is None else read_on
    if reuse:
        with _reused_persona_world(
            persona, scope, tmp_path, as_of=as_of, complete_setup=complete_setup, envelope=envelope
        ) as reused:
            yield reused
        return
    with persona_world(tmp_path, persona, as_of=as_of, envelope=envelope) as world:
        yield materialise_persona(persona, world, scope, complete_setup=complete_setup)


__all__ = [
    "materialise_persona",
    "materialised_persona",
]
