"""Registered operation that declares, lists and removes Modelo 360 solicitudes.

A solicitud is the operator-declared header, parties and refund account of one
Modelo 360 filing year. The facts and an embedded representante account arrive
only in the secure request; the published result shows each solicitud by its
year, destination, holder and a masked account, never an IBAN, a BIC, a name
or an address.

A solicitante account is a reference to one of the taxpayer's own accounts and
is admitted only when the own-account register holds it, open, with a SWIFT-BIC
(DR360 campo 116 is obligatorio); the export resolves its IBAN from the register.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Final, Literal, Protocol
from uuid import UUID

import pydantic
from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.errors.hierarchy import InternalInvariantError
from ...core.filing_year import FilingYear
from ...core.iban import mask_iban
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import Period
from ...domain.deadlines.models import RefundAccount
from ...domain.modelos.errors import ModeloError
from ...domain.transactions.own_accounts import OwnAccountId, OwnAccountRegister
from ..filing.producer_snapshot_m360 import (
    M360CausaPresentacion,
    M360TitularEnCalidadDe,
    Modelo360AccountChoice,
    Modelo360OwnAccountChoice,
    Modelo360ProfileFacts,
    Modelo360RepresentanteAccountChoice,
    Modelo360SolicitudEntry,
    Modelo360SolicitudRegister,
)
from ..ledger.own_account_ports import OwnAccountRepositoryFactory
from ..ledger.read_access import resolve_ledger_commit_access, resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.fenced_result import publish_fenced_result
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import ALL_OPERATION_FRONTENDS, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError

MODELO_360_SOLICITUD_OPERATION_DEFINITION_ID = "modelo.m360_solicitud"
#: The Modelo 360 revision addresses one solicitud per filing year through its single period.
MODELO_360_SOLICITUD_PERIOD_CODE: Final = "AD-HOC"

Modelo360SolicitudAction = Literal["declare", "list", "remove"]

_READ_ACTIONS: Final = frozenset({"list"})


class Modelo360SolicitudRefusedError(ModeloError):
    """Raised when a solicitud cannot be declared or removed as asked."""


class Modelo360SolicitudRepositoryProtocol(Protocol):
    """Required bucket-bound operations on the Modelo 360 solicitud register singleton."""

    def load(self) -> Modelo360SolicitudRegister:
        """Load the register, or an empty one when none was ever written."""
        ...

    def declare(self, entry: Modelo360SolicitudEntry) -> Modelo360SolicitudRegister:
        """Declare ``entry``, replacing any entry for its period, under the revision guard."""
        ...

    def remove(self, period: Period) -> Modelo360SolicitudRegister:
        """Remove the entry for ``period`` under the revision guard."""
        ...


class Modelo360SolicitudRepositoryFactory(Protocol):
    """Construct the solicitud register capability for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> Modelo360SolicitudRepositoryProtocol:
        """Return the capability bound to ``bucket_id``."""
        ...


class Modelo360RepresentanteAccountInput(BaseModel):
    """The representante's account as entered; it is validated into a ``RefundAccount`` in the worker."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    iban: str = Field(min_length=1, max_length=64)
    swift_bic: str = Field(min_length=1, max_length=16)
    bank_name: str = Field(default="", max_length=70)
    bank_address: str = Field(default="", max_length=35)
    bank_city: str = Field(default="", max_length=30)
    bank_country_code: str = Field(default="", max_length=2)


class Modelo360SolicitudRequest(BaseModel):
    """One exact-profile solicitud action; the facts and any representante account are private input.

    ``declare`` takes the filing year, the facts and exactly one account: a
    solicitante ``own_account_id`` or a ``representante_account``. ``remove`` takes
    the filing year; ``list`` takes neither.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    action: Modelo360SolicitudAction
    filing_year: FilingYear | None = None
    facts: Modelo360ProfileFacts | None = None
    own_account_id: OwnAccountId | None = None
    representante_account: Modelo360RepresentanteAccountInput | None = None

    @model_validator(mode="after")
    def _action_fields(self) -> Modelo360SolicitudRequest:
        if (self.action == "list") != (self.filing_year is None):
            raise ValueError("a filing year is given exactly when declaring or removing a modelo 360 solicitud")
        declaring = self.action == "declare"
        accounts = (self.own_account_id is not None) + (self.representante_account is not None)
        if declaring != (self.facts is not None) or accounts != (1 if declaring else 0):
            raise ValueError("facts and exactly one account are given exactly when declaring a modelo 360 solicitud")
        return self


class Modelo360SolicitudProjection(BaseModel):
    """Masked operator view of one declared solicitud."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    filing_year: FilingYear
    pais_destino: str = Field(min_length=2, max_length=2)
    causa_presentacion: M360CausaPresentacion
    titular_en_calidad_de: M360TitularEnCalidadDe
    has_representante: bool
    account_kind: Literal["own_account", "representante"] | None = None
    own_account_id: OwnAccountId | None = None
    masked_iban: str | None = None

    @classmethod
    def from_entry(cls, entry: Modelo360SolicitudEntry) -> Modelo360SolicitudProjection:
        """Project a solicitud onto its masked, material-free view."""
        account = entry.account
        masked: str | None = None
        own_account_id: str | None = None
        if isinstance(account, Modelo360OwnAccountChoice):
            own_account_id = account.own_account_id
        elif account is not None and account.account.iban is not None:
            masked = mask_iban(account.account.iban)
        return cls(
            filing_year=entry.period.filing_year,
            pais_destino=entry.facts.solicitud.pais_destino,
            causa_presentacion=entry.facts.solicitud.causa_presentacion,
            titular_en_calidad_de=entry.facts.cuenta.titular_en_calidad_de,
            has_representante=entry.facts.representante is not None,
            account_kind=None if account is None else account.kind,
            own_account_id=own_account_id,
            masked_iban=masked,
        )


class Modelo360SolicitudResult(BaseModel):
    """Encrypted operation result: the masked solicitudes and whether anything changed."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    action: Modelo360SolicitudAction
    filing_year: int | None = None
    solicitudes: tuple[Modelo360SolicitudProjection, ...] = ()
    changed: bool = False


def solicitud_period(filing_year: int) -> Period:
    """The single period through which the Modelo 360 revision addresses a filing year's solicitud."""
    return Period.from_year_and_code(filing_year, MODELO_360_SOLICITUD_PERIOD_CODE)


def _require_admissible_own_account(account: Modelo360AccountChoice, register: OwnAccountRegister) -> None:
    """A solicitante account must be a registered, open own account that carries its SWIFT-BIC."""
    if not isinstance(account, Modelo360OwnAccountChoice):
        return
    held = next((item for item in register.accounts if item.own_account_id == account.own_account_id), None)
    if held is None:
        raise Modelo360SolicitudRefusedError(
            translated_message="errors.refused.refused_modelo_360_solicitud_account_unknown",
            context={"own_account_id": account.own_account_id},
        )
    if held.closed_on is not None:
        raise Modelo360SolicitudRefusedError(
            translated_message="errors.refused.refused_modelo_360_solicitud_account_closed",
            context={"own_account_id": account.own_account_id},
        )
    if not held.swift_bic:
        raise Modelo360SolicitudRefusedError(
            translated_message="errors.refused.refused_modelo_360_solicitud_account_bic_missing",
            context={"own_account_id": account.own_account_id},
        )


def _account_choice(payload: Modelo360SolicitudRequest) -> Modelo360AccountChoice:
    """Build the declared account choice; a representante account must validate as a refund account."""
    if payload.own_account_id is not None:
        return Modelo360OwnAccountChoice(own_account_id=payload.own_account_id)
    entered = _required(payload.representante_account, "representante_account")
    try:
        return Modelo360RepresentanteAccountChoice(account=RefundAccount.model_validate(entered.model_dump()))
    except pydantic.ValidationError:
        # Input is hidden from these messages, so they never carry account material.
        raise Modelo360SolicitudRefusedError(
            translated_message="errors.refused.refused_modelo_360_solicitud_account_invalid",
        ) from None


def _required[T](value: T | None, name: str) -> T:
    # The request validator already demanded the field for this action.
    if value is None:
        raise InternalInvariantError(f"modelo 360 solicitud request reached its action without {name}")
    return value


def _result(
    payload: Modelo360SolicitudRequest,
    register: Modelo360SolicitudRegister,
    *,
    changed: bool,
) -> Modelo360SolicitudResult:
    return Modelo360SolicitudResult(
        profile_id=payload.profile_id,
        action=payload.action,
        filing_year=payload.filing_year,
        solicitudes=tuple(Modelo360SolicitudProjection.from_entry(entry) for entry in register.entries),
        changed=changed,
    )


def apply_solicitud_request(
    payload: Modelo360SolicitudRequest,
    *,
    repository: Modelo360SolicitudRepositoryProtocol,
    own_accounts: Callable[[], OwnAccountRegister],
) -> Modelo360SolicitudResult:
    """Read, declare or remove a solicitud and project the masked register."""
    before = repository.load()
    if payload.action in _READ_ACTIONS:
        return _result(payload, before, changed=False)
    period = solicitud_period(_required(payload.filing_year, "filing_year"))
    if payload.action == "remove":
        if before.entry_for(period) is None:
            raise Modelo360SolicitudRefusedError(
                translated_message="errors.refused.refused_modelo_360_solicitud_undeclared",
                context={"filing_year": period.filing_year},
            )
        after = repository.remove(period)
        return _result(payload, after, changed=after != before)
    account = _account_choice(payload)
    _require_admissible_own_account(account, own_accounts())
    try:
        entry = Modelo360SolicitudEntry(period=period, facts=_required(payload.facts, "facts"), account=account)
    except pydantic.ValidationError:
        raise Modelo360SolicitudRefusedError(
            translated_message="errors.refused.refused_modelo_360_solicitud_holder_mismatch",
        ) from None
    after = repository.declare(entry)
    return _result(payload, after, changed=after != before)


async def _publish_solicitud_action(
    context: OperationExecutorContext,
    *,
    payload: Modelo360SolicitudRequest,
    bucket_id: str,
    repository_factory: Modelo360SolicitudRepositoryFactory,
    own_account_repository_factory: OwnAccountRepositoryFactory,
) -> str:
    """Publish reads without effect and settle mutations through the irreversible fence."""

    async def run_action() -> Modelo360SolicitudResult:
        return await asyncio.to_thread(
            apply_solicitud_request,
            payload,
            repository=repository_factory(bucket_id=bucket_id),
            own_accounts=lambda: own_account_repository_factory(bucket_id=bucket_id).load(),
        )

    return await publish_fenced_result(
        context,
        run_action=run_action,
        is_read=payload.action in _READ_ACTIONS,
        result_changed=lambda result: result.changed,
    )


class Modelo360SolicitudExecutor:
    """Apply solicitud actions inside the profile worker's access fence."""

    def __init__(
        self,
        repository_factory: Modelo360SolicitudRepositoryFactory,
        own_account_repository_factory: OwnAccountRepositoryFactory,
    ) -> None:
        """Keep the profile-bound register factories in the worker."""
        self._repository_factory = repository_factory
        self._own_account_repository_factory = own_account_repository_factory

    async def execute(
        self,
        request: OperationRequest[Modelo360SolicitudRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Apply the selected action and publish its encrypted, masked result."""
        payload = request.payload
        if request.definition_id != MODELO_360_SOLICITUD_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(MODELO_360_SOLICITUD_OPERATION_DEFINITION_ID)
        return await await_cancellation_complete(
            _publish_solicitud_action(
                context,
                payload=payload,
                bucket_id=str(payload.profile_id),
                repository_factory=self._repository_factory,
                own_account_repository_factory=self._own_account_repository_factory,
            ),
            task_name="modelo-360-solicitud",
        )


def build_modelo_360_solicitud_definition(
    repository_factory: Modelo360SolicitudRepositoryFactory,
    own_account_repository_factory: OwnAccountRepositoryFactory,
) -> OperationDefinition:
    """Declare private input, a recorded result and honest mutation effects."""
    return build_single_phase_definition(
        definition_id=MODELO_360_SOLICITUD_OPERATION_DEFINITION_ID,
        request_type=Modelo360SolicitudRequest,
        result_type=Modelo360SolicitudResult,
        executor_type=Modelo360SolicitudExecutor,
        build=lambda: Modelo360SolicitudExecutor(repository_factory, own_account_repository_factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def resolve_modelo_360_solicitud_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Require whole-profile scope, and COMMIT for a declaration or removal."""
    if request.definition_id != MODELO_360_SOLICITUD_OPERATION_DEFINITION_ID or not isinstance(
        request.payload,
        Modelo360SolicitudRequest,
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolve = resolve_ledger_read_access if request.payload.action in _READ_ACTIONS else resolve_ledger_commit_access
    return resolve(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_modelo_360_solicitud_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact request and encrypted result schemas."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=Modelo360SolicitudResult,
        access_resolver=resolve_modelo_360_solicitud_access,
    )


__all__ = [
    "MODELO_360_SOLICITUD_OPERATION_DEFINITION_ID",
    "MODELO_360_SOLICITUD_PERIOD_CODE",
    "Modelo360RepresentanteAccountInput",
    "Modelo360SolicitudAction",
    "Modelo360SolicitudExecutor",
    "Modelo360SolicitudProjection",
    "Modelo360SolicitudRefusedError",
    "Modelo360SolicitudRepositoryFactory",
    "Modelo360SolicitudRepositoryProtocol",
    "Modelo360SolicitudRequest",
    "Modelo360SolicitudResult",
    "apply_solicitud_request",
    "build_modelo_360_solicitud_definition",
    "build_modelo_360_solicitud_registration",
    "resolve_modelo_360_solicitud_access",
    "solicitud_period",
]
