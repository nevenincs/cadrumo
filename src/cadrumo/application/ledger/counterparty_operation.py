"""Guarded counterparty confirmation, withdrawal, and ladder lookup."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.country_code import CountryCodeAlpha2
from ...core.external_constants import OutputLanguage
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.clock import today_madrid
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.eu_member_state_catalogue import require_eu_member_state
from ...domain.calculations.registry.ine_provincia_catalogue import ine_provincia_names
from ...domain.filing.declared_party_name import DeclaredPartyFilingName
from ...domain.iva.classification import require_iva_territorial_scope
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.error_detail import MAX_OPERATION_ERROR_WORDS_LENGTH, served_words_language
from ..operations.execution_actor import OperationExecutionCallerReader, execution_actor_label
from ..operations.fenced_result import publish_fenced_result
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .counterparty_establishment import (
    ConfirmedCounterpartyFacts,
    ConfirmedCounterpartyResolution,
    CounterpartyEstablishmentConflictError,
    confirm_counterparty_establishment,
    confirmed_counterparty_facts_key,
    declared_filing_name_from_parts,
    forget_confirmed_counterparty_facts,
    record_counterparty_filing_name,
    record_counterparty_provincia,
    resolve_confirmed_counterparty_facts,
    stated_counterparty_filing_name,
    stated_counterparty_provincia,
    withdraw_counterparty_filing_name,
)
from .counterparty_establishment_ports import (
    CounterpartyEstablishmentRepositoryFactory,
    CounterpartyEstablishmentRepositoryProtocol,
)
from .counterparty_filing_name_kind_findings import CounterpartyFilingNameFinding, filing_name_kind_findings
from .counterparty_filing_name_slots import (
    CounterpartyFilingNamePartLimit,
    CounterpartyFilingNameSlot,
    counterparty_filing_name_slots,
)
from .counterparty_filing_name_words import CounterpartyPartyKindChoice, kind_words, party_kind_choices
from .read_access import resolve_ledger_request_access

LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID = "ledger.counterparty"
LEDGER_COUNTERPARTY_TAX_ID_MAX = 256
"""The longest tax identifier a counterparty confirmation takes."""
LEDGER_COUNTERPARTY_NOTE_MAX = 4096
"""The longest note a counterparty confirmation takes."""
LEDGER_COUNTERPARTY_ASSERTED_BY_MAX = 256
"""The longest attribution label a counterparty confirmation takes."""
LEDGER_COUNTERPARTY_PROVINCIA_LENGTH = 2
"""An INE provincia code is two digits; which codes exist is the registry catalogue's."""
LEDGER_COUNTERPARTY_FILING_NAME_PART_MAX = 256
"""The longest stated name part a filing-name statement takes; the field width is the layout's."""
LEDGER_COUNTERPARTY_FILING_NAME_KIND_MAX = 32
"""The longest party-kind token a filing-name statement takes; which kinds exist is the domain's."""
LEDGER_COUNTERPARTY_FILING_NAME_RENDERINGS_MAX = 16
"""The most width-scoped renderings one filing-name statement carries."""


def _require_confirmation_action_fields(
    *,
    territorial_scope: str | None,
    identification_state: str | None,
    asserted_by: str | None,
    evidenced_scope: str | None,
) -> None:
    """Require an actor and at least one directly confirmed identity axis."""
    if territorial_scope is None and identification_state is None:
        raise ValueError("confirmation must answer at least one axis")
    if asserted_by is None or not asserted_by.strip() or evidenced_scope is not None:
        raise ValueError("confirmation requires its actor and no document evidence")


def _require_provincia_action_fields(
    *,
    provincia_code: str | None,
    territorial_scope: str | None,
    identification_state: str | None,
    asserted_by: str | None,
    evidenced_scope: str | None,
) -> None:
    """Require the stated provincia and its actor, and nothing about establishment."""
    if provincia_code is None:
        raise ValueError("a provincia statement must carry the provincia")
    if territorial_scope is not None or identification_state is not None or evidenced_scope is not None:
        raise ValueError("a provincia statement answers no establishment question")
    if asserted_by is None or not asserted_by.strip():
        raise ValueError("a provincia statement requires its actor")


def _require_filing_name_action_fields(
    *,
    party_kind: str | None,
    territorial_scope: str | None,
    identification_state: str | None,
    asserted_by: str | None,
    evidenced_scope: str | None,
    note: str,
) -> None:
    """Require the stated party kind and its actor, and nothing about establishment."""
    if party_kind is None:
        raise ValueError("a filing-name statement must carry the party kind")
    if territorial_scope is not None or identification_state is not None or evidenced_scope is not None or note:
        raise ValueError("a filing-name statement answers no establishment question")
    if asserted_by is None or not asserted_by.strip():
        raise ValueError("a filing-name statement requires its actor")


def _require_non_confirmation_action_fields(
    *,
    action: Literal["withdraw", "withdraw_filing_name", "view"],
    territorial_scope: str | None,
    identification_state: str | None,
    note: str,
    asserted_by: str | None,
    evidenced_scope: str | None,
) -> None:
    """Keep confirmation-only input out of withdraw and view requests."""
    if (
        territorial_scope is not None
        or identification_state is not None
        or note
        or asserted_by is not None
        or (action != "view" and evidenced_scope is not None)
    ):
        raise ValueError("counterparty action contains fields outside its declared purpose")


class CounterpartyFilingNameRendering(BaseModel):
    """A shorter rendering the person states for a field of one width."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    width: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=LEDGER_COUNTERPARTY_FILING_NAME_PART_MAX)


class LedgerCounterpartyRequest(BaseModel):
    """One exact-profile action with private counterparty input.

    ``asserted_by`` is recorded as sent for a person's session. An automation's
    session is recorded under its own session label, whatever the request
    carries; a confirmation must still supply it.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    action: Literal["confirm", "withdraw", "withdraw_filing_name", "view", "provincia", "filing_name"]
    tax_identifier: str = Field(min_length=1, max_length=LEDGER_COUNTERPARTY_TAX_ID_MAX)
    country_code: CountryCodeAlpha2 | None = None
    territorial_scope: str | None = Field(default=None, min_length=1, max_length=64)
    identification_state: CountryCodeAlpha2 | None = None
    evidenced_scope: str | None = Field(default=None, min_length=1, max_length=64)
    note: str = Field(default="", max_length=LEDGER_COUNTERPARTY_NOTE_MAX)
    asserted_by: str | None = Field(default=None, max_length=LEDGER_COUNTERPARTY_ASSERTED_BY_MAX)
    provincia_code: str | None = Field(
        default=None, min_length=LEDGER_COUNTERPARTY_PROVINCIA_LENGTH, max_length=LEDGER_COUNTERPARTY_PROVINCIA_LENGTH
    )
    party_kind: str | None = Field(default=None, min_length=1, max_length=LEDGER_COUNTERPARTY_FILING_NAME_KIND_MAX)
    primer_apellido: str | None = Field(default=None, min_length=1, max_length=LEDGER_COUNTERPARTY_FILING_NAME_PART_MAX)
    segundo_apellido: str | None = Field(
        default=None, min_length=1, max_length=LEDGER_COUNTERPARTY_FILING_NAME_PART_MAX
    )
    no_second_surname: bool = False
    nombre: str | None = Field(default=None, min_length=1, max_length=LEDGER_COUNTERPARTY_FILING_NAME_PART_MAX)
    razon_social: str | None = Field(default=None, min_length=1, max_length=LEDGER_COUNTERPARTY_FILING_NAME_PART_MAX)
    renderings: tuple[CounterpartyFilingNameRendering, ...] = Field(
        default=(), max_length=LEDGER_COUNTERPARTY_FILING_NAME_RENDERINGS_MAX
    )

    def _carries_filing_name_parts(self) -> bool:
        parts = (self.party_kind, self.primer_apellido, self.segundo_apellido, self.nombre, self.razon_social)
        return any(part is not None for part in parts) or self.no_second_surname or bool(self.renderings)

    @model_validator(mode="after")
    def _action_fields(self) -> LedgerCounterpartyRequest:
        if self.action != "provincia" and self.provincia_code is not None:
            raise ValueError("only a provincia statement carries a provincia")
        if self.action != "filing_name" and self._carries_filing_name_parts():
            raise ValueError("only a filing-name statement carries name parts")
        if self.action == "filing_name":
            _require_filing_name_action_fields(
                party_kind=self.party_kind,
                territorial_scope=self.territorial_scope,
                identification_state=self.identification_state,
                asserted_by=self.asserted_by,
                evidenced_scope=self.evidenced_scope,
                note=self.note,
            )
        elif self.action == "provincia":
            _require_provincia_action_fields(
                provincia_code=self.provincia_code,
                territorial_scope=self.territorial_scope,
                identification_state=self.identification_state,
                asserted_by=self.asserted_by,
                evidenced_scope=self.evidenced_scope,
            )
        elif self.action == "confirm":
            _require_confirmation_action_fields(
                territorial_scope=self.territorial_scope,
                identification_state=self.identification_state,
                asserted_by=self.asserted_by,
                evidenced_scope=self.evidenced_scope,
            )
        else:
            _require_non_confirmation_action_fields(
                action=self.action,
                territorial_scope=self.territorial_scope,
                identification_state=self.identification_state,
                note=self.note,
                asserted_by=self.asserted_by,
                evidenced_scope=self.evidenced_scope,
            )
        return self


class CounterpartyFactProjection(BaseModel):
    """Scalar copy of the confirmed fact for the encrypted public result."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    counterparty_key: Hex64Str
    canonical_tax_identifier: str = Field(min_length=1, max_length=LEDGER_COUNTERPARTY_TAX_ID_MAX)
    territorial_scope: str | None = Field(default=None, min_length=1, max_length=64)
    identification_state: CountryCodeAlpha2 | None = None
    asserted_by: str = Field(min_length=1, max_length=256)
    asserted_at: datetime
    note: str = Field(default="", max_length=LEDGER_COUNTERPARTY_NOTE_MAX)
    provincia_code: str | None = Field(
        default=None, min_length=LEDGER_COUNTERPARTY_PROVINCIA_LENGTH, max_length=LEDGER_COUNTERPARTY_PROVINCIA_LENGTH
    )

    @classmethod
    def from_fact(cls, fact: ConfirmedCounterpartyFacts) -> CounterpartyFactProjection:
        """Copy domain tokens into stable string fields at the worker boundary."""
        return cls(
            counterparty_key=fact.counterparty_key,
            canonical_tax_identifier=fact.canonical_tax_identifier,
            territorial_scope=fact.territorial_scope.value if fact.territorial_scope is not None else None,
            identification_state=fact.identification_state.value if fact.identification_state is not None else None,
            asserted_by=fact.asserted_by,
            asserted_at=fact.asserted_at,
            note=fact.note,
            provincia_code=fact.provincia_code,
        )


class CounterpartyFilingNameProjection(BaseModel):
    """Scalar copy of the stated filing name and who stated it, for the encrypted public result."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    party_kind: str = Field(min_length=1, max_length=LEDGER_COUNTERPARTY_FILING_NAME_KIND_MAX)
    primer_apellido: str | None = Field(default=None, min_length=1, max_length=LEDGER_COUNTERPARTY_FILING_NAME_PART_MAX)
    segundo_apellido: str | None = Field(
        default=None, min_length=1, max_length=LEDGER_COUNTERPARTY_FILING_NAME_PART_MAX
    )
    no_second_surname: bool = False
    nombre: str | None = Field(default=None, min_length=1, max_length=LEDGER_COUNTERPARTY_FILING_NAME_PART_MAX)
    razon_social: str | None = Field(default=None, min_length=1, max_length=LEDGER_COUNTERPARTY_FILING_NAME_PART_MAX)
    renderings: tuple[CounterpartyFilingNameRendering, ...] = ()
    asserted_by: str = Field(min_length=1, max_length=LEDGER_COUNTERPARTY_ASSERTED_BY_MAX)
    asserted_at: datetime
    party_kind_words: str = Field(min_length=1, max_length=MAX_OPERATION_ERROR_WORDS_LENGTH)
    party_kind_words_language: OutputLanguage

    @classmethod
    def from_fact(cls, fact: ConfirmedCounterpartyFacts) -> CounterpartyFilingNameProjection | None:
        """Copy the stated name into stable scalar fields, or ``None`` when no name is stated."""
        name = fact.declared_filing_name
        if name is None or fact.filing_name_asserted_by is None or fact.filing_name_asserted_at is None:
            return None
        language = served_words_language()
        return cls(
            party_kind=name.kind.value,
            primer_apellido=name.primer_apellido,
            segundo_apellido=name.segundo_apellido,
            no_second_surname=name.no_second_surname,
            nombre=name.nombre,
            razon_social=name.razon_social,
            renderings=tuple(
                CounterpartyFilingNameRendering(width=rendering.width, text=rendering.text)
                for rendering in name.renderings
            ),
            asserted_by=fact.filing_name_asserted_by,
            asserted_at=fact.filing_name_asserted_at,
            party_kind_words=kind_words(name.kind.value, language),
            party_kind_words_language=language,
        )


class CounterpartyResolutionProjection(BaseModel):
    """Scalar copy of the ladder's answer, including withheld contradictions."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    territorial_scope: str | None = Field(default=None, min_length=1, max_length=64)
    territorial_source: str | None = Field(default=None, min_length=1, max_length=64)
    identification_state: CountryCodeAlpha2 | None = None
    identification_source: str | None = Field(default=None, min_length=1, max_length=64)
    confirmed_scope: str | None = Field(default=None, min_length=1, max_length=64)
    evidenced_scope: str | None = Field(default=None, min_length=1, max_length=64)
    contradiction_detail: str | None = Field(default=None, min_length=1, max_length=2048)

    @classmethod
    def from_resolution(cls, resolution: ConfirmedCounterpartyResolution) -> CounterpartyResolutionProjection:
        """Retain exactly what the canonical resolver settled or withheld."""
        fact = resolution.fact
        identification = resolution.identification
        contradiction = resolution.contradiction
        return cls(
            territorial_scope=fact.value.value if fact is not None else None,
            territorial_source=fact.source.value if fact is not None else None,
            identification_state=identification.value.value if identification is not None else None,
            identification_source=identification.source.value if identification is not None else None,
            confirmed_scope=contradiction.confirmed_scope.value if contradiction is not None else None,
            evidenced_scope=contradiction.evidenced_scope.value if contradiction is not None else None,
            contradiction_detail=contradiction.detail if contradiction is not None else None,
        )


class CounterpartyProvinciaChoice(BaseModel):
    """One province or autonomous city a counterparty's domicilio fiscal can be in, by its INE code."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    code: str = Field(pattern=r"^[0-9]{2}$")
    name: str = Field(min_length=1, max_length=64)


def _provincia_choices(operation: PinnedAuthorityOperation) -> tuple[CounterpartyProvinciaChoice, ...]:
    """The INE catalogue's provinces in code order, named as INE prints them in every language."""
    return tuple(
        CounterpartyProvinciaChoice(code=code, name=name)
        for code, name in ine_provincia_names(authority=operation).items()
    )


class LedgerCounterpartyResult(BaseModel):
    """Encrypted operation result containing only the selected action's facts.

    ``provincia_code`` is the provincia stated for the counterparty, served by a
    view; ``provincia_choices`` are the provinces it can be stated as, served by
    a view and a provincia statement so a surface offers no list of its own.
    ``filing_name`` is the name stated for the counterparty, served by a view
    and a filing-name statement. ``filing_name_slots`` are the export fields the
    pinned authority's layouts file a party name into, each with its width and
    whether the stated name fills it, and ``filing_name_part_limits`` the longest
    each stated part can be for the full name to fit a slot; a view serves both.
    ``party_kinds`` are the kinds a name can be stated for, each with its label,
    served by a view and a filing-name statement. A filing-name withdrawal
    reports in ``withdrawn`` whether a name was held and removed, and in
    ``facts`` the record that remains, ``None`` when the name was its only answer.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    action: Literal["confirm", "withdraw", "withdraw_filing_name", "view", "provincia", "filing_name"]
    tax_identifier: str
    country_code: str | None = None
    evidenced_scope: str | None = Field(default=None, min_length=1, max_length=64)
    facts: CounterpartyFactProjection | None = None
    resolution: CounterpartyResolutionProjection | None = None
    recorded: bool | None = None
    withdrawn: bool | None = None
    changed: bool = False
    conflict_context: tuple[tuple[str, str], ...] | None = None
    provincia_code: str | None = Field(default=None, pattern=r"^[0-9]{2}$")
    provincia_choices: tuple[CounterpartyProvinciaChoice, ...] = ()
    filing_name: CounterpartyFilingNameProjection | None = None
    findings: tuple[CounterpartyFilingNameFinding, ...] = ()
    filing_name_slots: tuple[CounterpartyFilingNameSlot, ...] = ()
    filing_name_part_limits: tuple[CounterpartyFilingNamePartLimit, ...] = ()
    party_kinds: tuple[CounterpartyPartyKindChoice, ...] = ()


class _TrackedCounterpartyRepository:
    """Observe canonical service writes without inventing a second writer."""

    def __init__(self, repository: CounterpartyEstablishmentRepositoryProtocol) -> None:
        """Wrap only the repository supplied by the profile worker."""
        self._repository = repository
        self.changed = False

    def load(self, identifier: str) -> ConfirmedCounterpartyFacts | None:
        """Read the existing fact without changing the write marker."""
        return self._repository.load(identifier)

    def save(self, payload: ConfirmedCounterpartyFacts) -> None:
        """Delegate persistence and mark a completed write."""
        self._repository.save(payload)
        self.changed = True

    def delete(self, identifier: str) -> bool:
        """Delegate deletion and mark a completed removal."""
        deleted = self._repository.delete(identifier)
        self.changed = deleted
        return deleted


def _confirm_counterparty_action(
    payload: LedgerCounterpartyRequest,
    *,
    bucket_id: str,
    context: OperationExecutorContext,
    repository: _TrackedCounterpartyRepository,
) -> LedgerCounterpartyResult:
    """Confirm selected identity axes, preserving domain conflict facts."""
    try:
        outcome = confirm_counterparty_establishment(
            bucket_id=bucket_id,
            tax_identifier=payload.tax_identifier,
            asserted_by=payload.asserted_by or "",
            territorial_scope=(
                require_iva_territorial_scope(
                    payload.territorial_scope, effective_date=today_madrid(), operation=context.authority_operation
                )
                if payload.territorial_scope is not None
                else None
            ),
            identification_state=(
                require_eu_member_state(payload.identification_state, authority=context.authority_operation)
                if payload.identification_state is not None
                else None
            ),
            country_code=payload.country_code,
            note=payload.note,
            repository=repository,
        )
    except CounterpartyEstablishmentConflictError as error:
        return LedgerCounterpartyResult(
            profile_id=payload.profile_id,
            action=payload.action,
            tax_identifier=payload.tax_identifier,
            country_code=payload.country_code,
            conflict_context=tuple(sorted((key, str(value)) for key, value in (error.context or {}).items())),
        )
    return LedgerCounterpartyResult(
        profile_id=payload.profile_id,
        action=payload.action,
        tax_identifier=payload.tax_identifier,
        country_code=payload.country_code,
        facts=CounterpartyFactProjection.from_fact(outcome.facts),
        recorded=outcome.recorded,
        changed=repository.changed,
    )


def _withdraw_counterparty_action(
    payload: LedgerCounterpartyRequest,
    *,
    bucket_id: str,
    repository: _TrackedCounterpartyRepository,
) -> LedgerCounterpartyResult:
    """Withdraw only a verifiable exact-key fact and report the actual delete."""
    if confirmed_counterparty_facts_key(payload.tax_identifier, country_code=payload.country_code) is None:
        raise ValueError("counterparty identifier is unverifiable")
    withdrawn = forget_confirmed_counterparty_facts(
        bucket_id=bucket_id,
        tax_identifier=payload.tax_identifier,
        country_code=payload.country_code,
        repository=repository,
    )
    return LedgerCounterpartyResult(
        profile_id=payload.profile_id,
        action=payload.action,
        tax_identifier=payload.tax_identifier,
        country_code=payload.country_code,
        withdrawn=withdrawn,
        changed=repository.changed,
    )


def _withdraw_filing_name_counterparty_action(
    payload: LedgerCounterpartyRequest,
    *,
    bucket_id: str,
    repository: _TrackedCounterpartyRepository,
) -> LedgerCounterpartyResult:
    """Withdraw only the stated filing name, keeping every other answer, and report the actual write."""
    if confirmed_counterparty_facts_key(payload.tax_identifier, country_code=payload.country_code) is None:
        raise ValueError("counterparty identifier is unverifiable")
    withdrawn, remaining = withdraw_counterparty_filing_name(
        bucket_id=bucket_id,
        tax_identifier=payload.tax_identifier,
        country_code=payload.country_code,
        repository=repository,
    )
    return LedgerCounterpartyResult(
        profile_id=payload.profile_id,
        action=payload.action,
        tax_identifier=payload.tax_identifier,
        country_code=payload.country_code,
        facts=None if remaining is None else CounterpartyFactProjection.from_fact(remaining),
        withdrawn=withdrawn,
        changed=repository.changed,
    )


def _provincia_counterparty_action(
    payload: LedgerCounterpartyRequest,
    *,
    bucket_id: str,
    context: OperationExecutorContext,
    repository: _TrackedCounterpartyRepository,
) -> LedgerCounterpartyResult:
    """State the counterparty's provincia, keeping its other answers."""
    facts = record_counterparty_provincia(
        bucket_id=bucket_id,
        tax_identifier=payload.tax_identifier,
        provincia_code=payload.provincia_code or "",
        asserted_by=payload.asserted_by or "",
        country_code=payload.country_code,
        repository=repository,
    )
    return LedgerCounterpartyResult(
        profile_id=payload.profile_id,
        action=payload.action,
        tax_identifier=payload.tax_identifier,
        country_code=payload.country_code,
        facts=CounterpartyFactProjection.from_fact(facts),
        recorded=True,
        changed=repository.changed,
        provincia_code=facts.provincia_code,
        provincia_choices=_provincia_choices(context.authority_operation),
    )


def _stated_filing_name_parts(payload: LedgerCounterpartyRequest) -> DeclaredPartyFilingName | None:
    """Form the stated filing name from a statement's parts, or ``None`` for any other action.

    Run before the write fence opens, so parts that form no name are refused
    with nothing written and no effect in doubt.
    """
    if payload.action != "filing_name":
        return None
    return declared_filing_name_from_parts(
        kind=payload.party_kind or "",
        primer_apellido=payload.primer_apellido,
        segundo_apellido=payload.segundo_apellido,
        no_second_surname=payload.no_second_surname,
        nombre=payload.nombre,
        razon_social=payload.razon_social,
        renderings=tuple((rendering.width, rendering.text) for rendering in payload.renderings),
    )


def _filing_name_counterparty_action(
    payload: LedgerCounterpartyRequest,
    *,
    filing_name: DeclaredPartyFilingName,
    bucket_id: str,
    context: OperationExecutorContext,
    repository: _TrackedCounterpartyRepository,
) -> LedgerCounterpartyResult:
    """State the counterparty's filing name, keeping its other answers."""
    facts = record_counterparty_filing_name(
        bucket_id=bucket_id,
        tax_identifier=payload.tax_identifier,
        filing_name=filing_name,
        asserted_by=payload.asserted_by or "",
        country_code=payload.country_code,
        repository=repository,
    )
    return LedgerCounterpartyResult(
        profile_id=payload.profile_id,
        action=payload.action,
        tax_identifier=payload.tax_identifier,
        country_code=payload.country_code,
        facts=CounterpartyFactProjection.from_fact(facts),
        recorded=repository.changed,
        changed=repository.changed,
        filing_name=CounterpartyFilingNameProjection.from_fact(facts),
        findings=filing_name_kind_findings(
            tax_identifier=payload.tax_identifier,
            country_code=payload.country_code,
            declared_kind=filing_name.kind.value,
            operation=context.authority_operation,
        ),
        party_kinds=party_kind_choices(),
    )


def _view_counterparty_action(
    payload: LedgerCounterpartyRequest,
    *,
    bucket_id: str,
    context: OperationExecutorContext,
    repository: _TrackedCounterpartyRepository,
) -> LedgerCounterpartyResult:
    """Resolve canonical facts and optional document evidence under one authority."""
    resolution = resolve_confirmed_counterparty_facts(
        bucket_id=bucket_id,
        tax_identifier=payload.tax_identifier,
        country_code=payload.country_code,
        evidenced_scope=(
            require_iva_territorial_scope(
                payload.evidenced_scope, effective_date=today_madrid(), operation=context.authority_operation
            )
            if payload.evidenced_scope is not None
            else None
        ),
        repository=repository,
    )
    stated = stated_counterparty_filing_name(
        payload.tax_identifier, country_code=payload.country_code, repository=repository
    )
    stated_name = None if stated is None else CounterpartyFilingNameProjection.from_fact(stated)
    slots, part_limits = counterparty_filing_name_slots(
        context.authority_operation, None if stated is None else stated.declared_filing_name
    )
    return LedgerCounterpartyResult(
        profile_id=payload.profile_id,
        action=payload.action,
        tax_identifier=payload.tax_identifier,
        country_code=payload.country_code,
        evidenced_scope=payload.evidenced_scope,
        resolution=CounterpartyResolutionProjection.from_resolution(resolution),
        provincia_code=stated_counterparty_provincia(
            payload.tax_identifier, country_code=payload.country_code, repository=repository
        ),
        provincia_choices=_provincia_choices(context.authority_operation),
        filing_name=stated_name,
        findings=(
            ()
            if stated_name is None
            else filing_name_kind_findings(
                tax_identifier=payload.tax_identifier,
                country_code=payload.country_code,
                declared_kind=stated_name.party_kind,
                operation=context.authority_operation,
            )
        ),
        filing_name_slots=slots,
        filing_name_part_limits=part_limits,
        party_kinds=party_kind_choices(),
    )


def _perform_counterparty_action(
    payload: LedgerCounterpartyRequest,
    *,
    bucket_id: str,
    context: OperationExecutorContext,
    repository_factory: CounterpartyEstablishmentRepositoryFactory,
    filing_name: DeclaredPartyFilingName | None,
) -> LedgerCounterpartyResult:
    """Create one tracked repository and dispatch the declared action."""
    repository = _TrackedCounterpartyRepository(repository_factory(bucket_id=bucket_id))
    if payload.action == "confirm":
        return _confirm_counterparty_action(payload, bucket_id=bucket_id, context=context, repository=repository)
    if payload.action == "withdraw":
        return _withdraw_counterparty_action(payload, bucket_id=bucket_id, repository=repository)
    if payload.action == "withdraw_filing_name":
        return _withdraw_filing_name_counterparty_action(payload, bucket_id=bucket_id, repository=repository)
    if payload.action == "provincia":
        return _provincia_counterparty_action(payload, bucket_id=bucket_id, context=context, repository=repository)
    if filing_name is not None:
        return _filing_name_counterparty_action(
            payload, filing_name=filing_name, bucket_id=bucket_id, context=context, repository=repository
        )
    return _view_counterparty_action(payload, bucket_id=bucket_id, context=context, repository=repository)


async def _publish_counterparty_action(
    context: OperationExecutorContext,
    *,
    payload: LedgerCounterpartyRequest,
    bucket_id: str,
    repository_factory: CounterpartyEstablishmentRepositoryFactory,
    filing_name: DeclaredPartyFilingName | None,
) -> str:
    """Publish views as reads and settle mutations through the irreversible fence."""

    async def run_action() -> LedgerCounterpartyResult:
        return await asyncio.to_thread(
            _perform_counterparty_action,
            payload,
            bucket_id=bucket_id,
            context=context,
            repository_factory=repository_factory,
            filing_name=filing_name,
        )

    return await publish_fenced_result(
        context,
        run_action=run_action,
        is_read=payload.action == "view",
        result_changed=lambda result: result.changed,
    )


class LedgerCounterpartyExecutor:
    """Invoke canonical services inside the profile worker's access fence."""

    def __init__(
        self,
        repository_factory: CounterpartyEstablishmentRepositoryFactory,
        *,
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Keep the profile-bound repository factory in the worker."""
        self._repository_factory = repository_factory
        self._execution_caller_reader = execution_caller_reader

    async def execute(
        self, request: OperationRequest[LedgerCounterpartyRequest], context: OperationExecutorContext
    ) -> str:
        """Apply the selected action and publish its encrypted result."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID)
        if payload.action in {"confirm", "provincia", "filing_name"}:
            asserted_by = execution_actor_label(
                self._execution_caller_reader, context, supplied=payload.asserted_by or ""
            )
            payload = payload.model_copy(update={"asserted_by": asserted_by})
        filing_name = _stated_filing_name_parts(payload)
        return await await_cancellation_complete(
            _publish_counterparty_action(
                context,
                payload=payload,
                bucket_id=bucket_id,
                repository_factory=self._repository_factory,
                filing_name=filing_name,
            ),
            task_name="ledger-counterparty",
        )


def build_ledger_counterparty_definition(
    repository_factory: CounterpartyEstablishmentRepositoryFactory,
    *,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Declare private input, a recorded result and honest mutation effects."""
    return build_single_phase_definition(
        definition_id=LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
        request_type=LedgerCounterpartyRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerCounterpartyResult,
        executor_type=LedgerCounterpartyExecutor,
        build=lambda: LedgerCounterpartyExecutor(repository_factory, execution_caller_reader=execution_caller_reader),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
    )


def resolve_ledger_counterparty_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile scope, and COMMIT for mutations."""
    return resolve_ledger_request_access(
        request,
        context,
        definition_id=LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
        request_type=LedgerCounterpartyRequest,
        commits=lambda payload: payload.action != "view",
    )


def build_ledger_counterparty_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact request and encrypted result schemas."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerCounterpartyResult,
        access_resolver=resolve_ledger_counterparty_access,
    )
