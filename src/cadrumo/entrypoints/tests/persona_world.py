"""The registered world a persona replays into, the settled scenario clock and the typed outcome of a replay."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import cast
from uuid import UUID

from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.operations.typed_financial_operand_custody import (
    OperationTypedFinancialOperandCustodyFilesystemRepository,
)
from ...adapters.persistence.profile.tests.sealed_profile_world import (
    SealedProfileWorld,
    copied_profile_world,
    sealed_profile_world,
)
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from ...adapters.persistence.storage.tests.profile_session_setup import reset_test_profile_session
from ...application.operations.composition import OperationComposedServices, compose_operation_services
from ...application.operations.registry import OperationRegistry
from ...application.user_profile.custody_ports import profile_custody_secure_object_repository
from ...application.user_profile.registration import create_registered_profile
from ...core.auth_provider import AuthProviderKind
from ...core.config import override_settings
from ...core.time.clock import frozen_clock, now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...tests.persona_types import (
    AttestedPriorValue,
    Persona,
    ProvisionPeriods,
    WorkIncomeNoneStatement,
    WorkInput,
    YearEnvelope,
)
from ...tests.personas import governed_provisions
from ..operation_composition import build_production_operation_registry
from .persona_aeat_filings import PERSONA_FILED_REGISTER

PERSONA_ACTOR = "operator:persona"
"""The actor every replayed operation is submitted under."""


SCENARIO_TIME = time(9, 0, tzinfo=UTC)
"""The time of day of every persona's scenario instant; the date is the persona's ``[clock].as_of``."""


PERSONA_PROFILE_CREDENTIAL = "persona-materialisation-passphrase"
"""The synthetic passphrase of every persona profile; a harness that signs in to a persona's profile reads it here."""


class PersonaMaterialisationError(RuntimeError):
    """A production operation refused a persona fact; the catalogue or the operation must change."""


class ReplayScope(StrEnum):
    """How much of a persona a replay records; each scope holds everything the narrower ones do."""

    PROFILE = "profile"
    """The wizard patch, its elections, the field mutations and the activity rows."""
    HOUSEHOLD = "household"
    """The profile scope and the descendant and ascendant replacements."""
    FULL = "full"
    """The household scope, the own bank accounts, the declared withholding, the statement import, invoices, evidence and inventory books."""
    RECORDS = "records"
    """The full scope, then the records the persona's returns read, without the returns.

    The local observations, the Modelo 303 compensation carried in, the rent
    and professional withholding and the returns filed with the AEAT are
    recorded; no return is created. A consumer that takes the persona's
    returns through their own operations, in order, replays this scope.
    """
    HISTORY = "history"
    """The full scope, then the persona's return history.

    The local observations are recorded and every rent payment on leased
    premises is captured as withholding; then every filed return is created,
    calculated, verified and filed locally, and every calculated return is
    created and calculated. Then every return the persona attests a prior value
    on that neither the history nor a stated value calculates is created and
    attested, which calculates it. Opt-in: a consumer that walks those periods
    itself replays the full scope.
    """

    def includes(self, other: ReplayScope) -> bool:
        """Whether replaying ``self`` records everything ``other`` does."""
        order = tuple(ReplayScope)
        return order.index(self) >= order.index(other)


@dataclass(frozen=True, slots=True)
class NotLoaded:
    """A persona block no production operation recorded, and why."""

    block: str
    reason: str


@dataclass(frozen=True, slots=True)
class PersonaWorld:
    """One registered, empty profile and the supervisor that runs operations against it."""

    profile_id: UUID
    storage_root: Path
    workdir: Path
    as_of: datetime
    envelope: YearEnvelope
    services: OperationComposedServices
    registry: OperationRegistry
    operation: PinnedAuthorityOperation
    attested_prior_values: tuple[AttestedPriorValue, ...] = ()
    """The persona's stated figures for earlier returns; :func:`run_operation` submits them after a calculation."""
    work_inputs: tuple[WorkInput, ...] = ()
    """The values the persona's operator enters on a return; :func:`run_operation` enters them before its first calculation."""
    work_income_none_statements: tuple[WorkIncomeNoneStatement, ...] = ()
    """The ejercicios whose unevidenced work income the persona states is none; submitted after a calculation."""


@dataclass(frozen=True, slots=True)
class MaterialisedPersona:
    """What replaying a persona left in its profile."""

    persona: Persona
    world: PersonaWorld
    scope: ReplayScope
    transactions: Mapping[str, str]
    """Ledger ``ref`` to the imported transaction id."""
    invoices: Mapping[str, str]
    """Ledger ``ref`` to the recorded and linked invoice id."""
    evidence: Mapping[str, str]
    """Document id to the stored evidence id."""
    not_loaded: tuple[NotLoaded, ...]
    """What no operation recorded, and ``setup`` when completing the setup was asked and the persona's answers refuse it."""
    filings: Mapping[str, str]
    """:func:`filing_key` of each return the history scope filed locally, to its filed calculation revision id."""
    calculations: Mapping[str, str]
    """:func:`filing_key` of each return the history scope calculated without filing, to its revision id."""


def year_envelope(operation: PinnedAuthorityOperation) -> YearEnvelope:
    """The registry's supported filing-year envelope, as the persona reader takes it.

    It carries the governed periods of every provision a persona's stated value is limited
    to, read from the legal register: absent a declared reach, the governed span is the
    provision's own in-force span.
    """
    support = operation.supported_filing_years()
    provisions: list[tuple[str, ProvisionPeriods]] = []
    for provision in sorted(governed_provisions()):
        reference = operation.legal_reference(provision)
        if reference.governs_periods_from is not None:
            periods = ProvisionPeriods(first=reference.governs_periods_from, last=reference.governs_periods_to)
        else:
            periods = ProvisionPeriods(first=reference.effective_from, last=reference.effective_to)
        provisions.append((provision, periods))
    return YearEnvelope(floor=support.floor, horizon=support.horizon, provisions=tuple(provisions))


def scenario_instant(persona: Persona, envelope: YearEnvelope) -> datetime:
    """The instant a persona's operations run at."""
    return datetime.combine(persona.as_of.resolve(envelope), SCENARIO_TIME)


@cache
def _registry() -> OperationRegistry:
    return build_production_operation_registry(filed_register=PERSONA_FILED_REGISTER)


def persona_profile_id(persona_id: str) -> UUID:
    """The profile identity every materialisation of the persona ``persona_id`` registers, on every run.

    A profile identity is a UUIDv4, so it is the version 4 UUID spelled by the digest of the persona id.
    """
    return UUID(bytes=hashlib.sha256(f"persona profile:{persona_id}".encode()).digest()[:16], version=4)


def _registered_world(persona: Persona, as_of: datetime) -> SealedProfileWorld:
    create_context, decode_context = profile_authority_contexts()
    profile_id = persona_profile_id(persona.id)

    def register() -> str:
        return create_registered_profile(
            profile_id=profile_id,
            label="persona",
            passphrase=PERSONA_PROFILE_CREDENTIAL,
            profile_create_context=create_context,
            profile_decode_context=decode_context,
        ).profile_id

    key = ("persona world", str(profile_id), str(create_context.generation), as_of.isoformat())
    return sealed_profile_world(key, register)


@contextmanager
def _scenario(as_of: datetime) -> Generator[None]:
    """The clock and the sign-in provider every persona operation runs under."""
    with (
        frozen_clock(as_of),
        override_settings(cadrumo_auth_provider=AuthProviderKind.CERTIFICATE, cadrumo_certificate_path=None),
    ):
        yield


@contextmanager
def _operations_over(
    root: Path,
    profile_id: UUID,
    *,
    workdir: Path,
    as_of: datetime,
    envelope: YearEnvelope | None = None,
    attested_prior_values: tuple[AttestedPriorValue, ...] = (),
    work_inputs: tuple[WorkInput, ...] = (),
    work_income_none_statements: tuple[WorkIncomeNoneStatement, ...] = (),
) -> Generator[PersonaWorld]:
    """Compose a production supervisor over the profile already resumed in the isolated ``root``.

    ``envelope`` is the year envelope the persona was read under; the registry's own when omitted.
    ``attested_prior_values`` are the persona's stated figures for earlier returns,
    ``work_inputs`` the values its operator enters on a return, and
    ``work_income_none_statements`` the ejercicios whose unevidenced work income it states is none.
    """
    with (
        profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as objects,
        bundled_indexed_authority().operation() as operation,
    ):
        registry = _registry()
        journal = OperationJournalRepository(storage_root=root / "operations")
        operands = operation_secure_reference_repository(objects=cast(SecureObjectRepository, objects))
        services = compose_operation_services(
            registry=registry,
            authority_operation=operation,
            journal=journal,
            reader=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=root / "operations"),
            operands=operands,
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=now,
            lease_duration=timedelta(minutes=10),
            execution_timeout=timedelta(hours=1),
            cleanup_timeout=timedelta(minutes=2),
            typed_financial_operand_custody=OperationTypedFinancialOperandCustodyFilesystemRepository(
                root=root / "operations" / "typed_financial_operand_custody",
            ),
        )
        workdir.mkdir(parents=True, exist_ok=True)
        try:
            yield PersonaWorld(
                profile_id=profile_id,
                storage_root=root,
                workdir=workdir,
                as_of=as_of,
                envelope=year_envelope(operation) if envelope is None else envelope,
                services=services,
                registry=registry,
                operation=operation,
                attested_prior_values=attested_prior_values,
                work_inputs=work_inputs,
                work_income_none_statements=work_income_none_statements,
            )
        finally:
            asyncio.run(services.shutdown())


@contextmanager
def persona_world(
    tmp_path: Path, persona: Persona, *, as_of: datetime, envelope: YearEnvelope | None = None
) -> Generator[PersonaWorld]:
    """Open ``persona``'s registered empty profile and a production supervisor over it, frozen at ``as_of``."""
    with bundled_indexed_authority().operation(), _scenario(as_of):
        _create_context, decode_context = profile_authority_contexts()
        world = _registered_world(persona, as_of)
        with copied_profile_world(world, tmp_path / "runtime", profile_decode_context=decode_context) as (
            root,
            profile_id,
        ):
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
                ) as opened:
                    yield opened
            finally:
                reset_test_profile_session()


__all__ = [
    "PERSONA_ACTOR",
    "PERSONA_PROFILE_CREDENTIAL",
    "SCENARIO_TIME",
    "MaterialisedPersona",
    "NotLoaded",
    "PersonaMaterialisationError",
    "PersonaWorld",
    "ReplayScope",
    "persona_profile_id",
    "persona_world",
    "scenario_instant",
    "year_envelope",
]
