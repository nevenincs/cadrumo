"""What one profile's own records already say, to offer while a person types.

Every call reads the stored records under the operation's exact profile. Nothing
is kept between calls and no index holds these values, so a read costs what the
named sources cost to decrypt: ask only for the kinds a field needs.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from typing import Final, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.ledger_known_values import LedgerKnownValueKind
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.text_fold import fold_diacritics
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.invoices.catalogue import StoredInvoiceCatalogue
from ...domain.transactions.enums import TransactionLifecycleState
from ...domain.transactions.models import Transaction
from ..actividad_asset.history import ActivityAssetHistory
from ..actividad_asset.ports import ActivityAssetHistoryRepository
from ..invoices.inspection_read_ports import InvoiceInspectionReadPortsFactory
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_profile_operation_identity
from ..operations.read_capture import capture_read_result
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .read_access import resolve_ledger_request_read_access
from .read_ports import LedgerReadPortsFactory

LEDGER_KNOWN_VALUES_OPERATION_DEFINITION_ID = "ledger.known-values"

KNOWN_VALUES_PER_KIND: Final = 512
"""The most recent values one kind returns: enough to type against, well inside one relay reply."""

KNOWN_VALUE_MAX_LENGTH: Final = 512
"""The longest text returned. A longer one is said as truncated: nobody picks it from a list."""


_MOVEMENT_KINDS: Final = frozenset(
    {
        LedgerKnownValueKind.COUNTERPARTY,
        LedgerKnownValueKind.DESCRIPTION,
        LedgerKnownValueKind.GROUP_LABEL,
        LedgerKnownValueKind.M210_PAYER,
        LedgerKnownValueKind.M210_ASSET,
    }
)


class LedgerKnownValuesRequest(CredentialFreeOperationRequest):
    """Which kinds to read. It names no record, so the journal can retain it."""

    profile_id: UUID
    kinds: tuple[LedgerKnownValueKind, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _each_kind_once(self) -> Self:
        if len(set(self.kinds)) != len(self.kinds):
            raise ValueError("known values repeat a kind")
        return self


class KnownCounterparty(BaseModel):
    """One party as the records name it, most recently used spelling first."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    name: str
    tax_id: str | None
    """From an invoice; a movement states none, and only joins a name that maps to exactly one."""
    country: str | None
    identification_state: str | None
    uses: NonNegativeInt
    last_used: date


class KnownText(BaseModel):
    """One free text as the records use it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    text: str
    uses: NonNegativeInt
    last_used: date
    counterparty: str | None
    """The party of its most recent use with one, where the source names parties."""


class LedgerKnownValuesProjection(BaseModel):
    """The values of each requested kind, most recent first, and which kinds were cut short."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    counterparties: tuple[KnownCounterparty, ...] = ()
    descriptions: tuple[KnownText, ...] = ()
    group_labels: tuple[KnownText, ...] = ()
    m210_payers: tuple[KnownText, ...] = ()
    m210_assets: tuple[KnownText, ...] = ()
    asset_references: tuple[KnownText, ...] = ()
    truncated: tuple[LedgerKnownValueKind, ...] = ()

    @model_validator(mode="after")
    def _inside_the_cap(self) -> Self:
        for rows in (
            self.counterparties,
            self.descriptions,
            self.group_labels,
            self.m210_payers,
            self.m210_assets,
            self.asset_references,
        ):
            if len(rows) > KNOWN_VALUES_PER_KIND:
                raise ValueError("known values exceed the cap of one kind")
        return self


@dataclass(frozen=True, slots=True)
class LedgerKnownValuesPorts:
    """The three stored sources, each bound to the admitted profile when read."""

    ledger: LedgerReadPortsFactory
    invoices: InvoiceInspectionReadPortsFactory
    asset_history: Callable[[str], ActivityAssetHistoryRepository]


def _folded(text: str) -> str:
    return " ".join(fold_diacritics(text).casefold().split())


@dataclass(slots=True)
class _HeldText:
    text: str
    uses: int
    last_used: date
    counterparty: str | None
    counterparty_used: date | None


def _known_texts(uses: Iterable[tuple[str | None, date, str | None]]) -> tuple[tuple[KnownText, ...], bool]:
    """Distinct by folded spelling, newest first; the flag says something was left out."""
    held: dict[str, _HeldText] = {}
    overlong = False
    for raw, used_on, party in uses:
        text = (raw or "").strip()
        if not text:
            continue
        if len(text) > KNOWN_VALUE_MAX_LENGTH:
            overlong = True
            continue
        _record_text_use(held, text, used_on, party)
    ordered = sorted(held.items(), key=lambda item: (-item[1].last_used.toordinal(), item[0]))
    return (
        tuple(
            KnownText(text=row.text, uses=row.uses, last_used=row.last_used, counterparty=row.counterparty)
            for _, row in ordered[:KNOWN_VALUES_PER_KIND]
        ),
        overlong or len(ordered) > KNOWN_VALUES_PER_KIND,
    )


def _record_text_use(held: dict[str, _HeldText], text: str, used_on: date, party: str | None) -> None:
    """Update one folded text and its latest independently stated counterparty."""
    party = (party or "").strip() or None
    key = _folded(text)
    row = held.get(key)
    if row is None:
        held[key] = _HeldText(text, 1, used_on, party, used_on if party is not None else None)
        return
    row.uses += 1
    if used_on >= row.last_used:
        row.text, row.last_used = text, used_on
    if party is not None and (row.counterparty_used is None or used_on >= row.counterparty_used):
        row.counterparty, row.counterparty_used = party, used_on


@dataclass(slots=True)
class _HeldParty:
    name: str
    tax_id: str | None
    uses: int = 0
    last_used: date = date.min
    country: str | None = None
    country_used: date = date.min
    state: str | None = None
    state_used: date = date.min

    def see(self, name: str, used_on: date, country: str | None, state: str | None) -> None:
        self.uses += 1
        if used_on >= self.last_used:
            self.name, self.last_used = name, used_on
        if country is not None and country != "" and used_on >= self.country_used:
            self.country, self.country_used = country, used_on
        if state is not None and state != "" and used_on >= self.state_used:
            self.state, self.state_used = state, used_on


def _known_counterparties(
    transactions: Iterable[Transaction],
    invoices: StoredInvoiceCatalogue,
) -> tuple[tuple[KnownCounterparty, ...], bool]:
    """One row per invoice tax id and one per name no tax id can be joined to.

    A name under two tax ids stays two parties, and the movements with that name
    join neither: an offered tax id must be the only one the name can mean.
    """
    by_tax_id, tax_ids_of, untaxed = _invoice_counterparties(invoices)
    untaxed.extend(_movement_counterparties(transactions))
    by_name: dict[str, _HeldParty] = {}
    for name, used_on, country, state in untaxed:
        key = _folded(name)
        joined = tax_ids_of.get(key, set())
        party = by_tax_id[next(iter(joined))] if len(joined) == 1 else by_name.setdefault(key, _HeldParty(name, None))
        party.see(name, used_on, country, state)
    parties = (*by_tax_id.values(), *by_name.values())
    overlong = any(len(party.name) > KNOWN_VALUE_MAX_LENGTH for party in parties)
    fitting = sorted(
        (party for party in parties if len(party.name) <= KNOWN_VALUE_MAX_LENGTH),
        key=lambda party: (-party.last_used.toordinal(), _folded(party.name), party.tax_id or ""),
    )
    return (
        tuple(
            KnownCounterparty(
                name=party.name,
                tax_id=party.tax_id,
                country=party.country,
                identification_state=party.state,
                uses=party.uses,
                last_used=party.last_used,
            )
            for party in fitting[:KNOWN_VALUES_PER_KIND]
        ),
        overlong or len(fitting) > KNOWN_VALUES_PER_KIND,
    )


def _invoice_counterparties(
    invoices: StoredInvoiceCatalogue,
) -> tuple[dict[str, _HeldParty], dict[str, set[str]], list[tuple[str, date, str | None, str | None]]]:
    """Collect invoice identities and the names that can unambiguously resolve to them."""
    by_tax_id: dict[str, _HeldParty] = {}
    tax_ids_of: dict[str, set[str]] = {}
    untaxed: list[tuple[str, date, str | None, str | None]] = []
    for invoice in invoices.values():
        name = invoice.counterparty_name.strip()
        tax_id = (invoice.counterparty_tax_id or "").strip().upper()
        if not name or not tax_id:
            if name:
                untaxed.append((name, invoice.issued_at, invoice.counterparty_country or None, None))
            continue
        tax_ids_of.setdefault(_folded(name), set()).add(tax_id)
        by_tax_id.setdefault(tax_id, _HeldParty(name, tax_id)).see(
            name, invoice.issued_at, invoice.counterparty_country or None, None
        )
    return by_tax_id, tax_ids_of, untaxed


def _movement_counterparties(
    transactions: Iterable[Transaction],
) -> Iterable[tuple[str, date, str | None, str | None]]:
    """Read stated counterparties without inventing tax identities for movements."""
    for transaction in transactions:
        name = transaction.raw.display_counterparty.strip()
        if name:
            state = transaction.counterparty_identification_state
            yield (
                name,
                transaction.raw.value_date or transaction.raw.booked_date,
                transaction.counterparty_country,
                state.value if state is not None else None,
            )


def _asset_reference_uses(history: ActivityAssetHistory) -> Iterable[tuple[str | None, date, str | None]]:
    for revision in history.revisions:
        for reference in revision.stated_references():
            yield reference, revision.in_service_date, None


def _dated(transaction: Transaction) -> date:
    return transaction.raw.value_date or transaction.raw.booked_date


class LedgerKnownValuesExecutor:
    """Read the named sources under the operation's profile and keep nothing."""

    def __init__(self, ports: LedgerKnownValuesPorts) -> None:
        """Retain the exact-profile port factories."""
        self._ports = ports

    def _movements(self, bucket_id: str, context: OperationExecutorContext) -> tuple[Transaction, ...]:
        operation = context.authority_operation
        ports = self._ports.ledger(bucket_id=bucket_id, operation=operation)
        if ports.transaction_repository.bucket_id != bucket_id or ports.operation is not operation:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        return tuple(
            row
            for row in ports.transaction_repository.load().values()
            # A split parent's text lives on in its children.
            if row.lifecycle_state is not TransactionLifecycleState.SPLIT
        )

    def _counterparties(
        self, bucket_id: str, context: OperationExecutorContext, movements: tuple[Transaction, ...]
    ) -> tuple[tuple[KnownCounterparty, ...], bool]:
        operation = context.authority_operation
        ports = self._ports.invoices(bucket_id=bucket_id, operation=operation)
        if ports.bucket_id != bucket_id or ports.invoices.bucket_id != bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        with validating_governed_facts(operation):
            catalogue = ports.invoices.load_authenticated()
            if any(attributed != bucket_id for attributed in catalogue.attributed_bucket_ids()):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            return _known_counterparties(movements, catalogue)

    def _read(
        self, payload: LedgerKnownValuesRequest, context: OperationExecutorContext
    ) -> LedgerKnownValuesProjection:
        kinds = frozenset(payload.kinds)
        bucket_id = str(payload.profile_id)
        movements = self._movements(bucket_id, context) if kinds & _MOVEMENT_KINDS else ()
        found: dict[str, object] = {}
        cut: list[LedgerKnownValueKind] = []

        def keep(kind: LedgerKnownValueKind, field: str, section: tuple[tuple[BaseModel, ...], bool]) -> None:
            found[field] = section[0]
            if section[1]:
                cut.append(kind)

        if LedgerKnownValueKind.COUNTERPARTY in kinds:
            keep(
                LedgerKnownValueKind.COUNTERPARTY,
                "counterparties",
                self._counterparties(bucket_id, context, movements),
            )
        self._keep_movement_texts(kinds, movements, keep)
        if LedgerKnownValueKind.ASSET_REFERENCE in kinds:
            keep(
                LedgerKnownValueKind.ASSET_REFERENCE,
                "asset_references",
                _known_texts(_asset_reference_uses(self._ports.asset_history(bucket_id).load())),
            )
        return LedgerKnownValuesProjection.model_validate(
            {"profile_id": payload.profile_id, **found, "truncated": tuple(cut)}
        )

    @staticmethod
    def _keep_movement_texts(
        kinds: frozenset[LedgerKnownValueKind],
        movements: tuple[Transaction, ...],
        keep: Callable[[LedgerKnownValueKind, str, tuple[tuple[BaseModel, ...], bool]], None],
    ) -> None:
        """Project requested free-text fields from the already authenticated movements."""
        if LedgerKnownValueKind.DESCRIPTION in kinds:
            keep(
                LedgerKnownValueKind.DESCRIPTION,
                "descriptions",
                _known_texts((row.raw.description, _dated(row), row.raw.display_counterparty) for row in movements),
            )
        if LedgerKnownValueKind.GROUP_LABEL in kinds:
            keep(
                LedgerKnownValueKind.GROUP_LABEL,
                "group_labels",
                _known_texts((row.group_label, _dated(row), None) for row in movements),
            )
        LedgerKnownValuesExecutor._keep_m210_texts(kinds, movements, keep)

    @staticmethod
    def _keep_m210_texts(
        kinds: frozenset[LedgerKnownValueKind],
        movements: tuple[Transaction, ...],
        keep: Callable[[LedgerKnownValueKind, str, tuple[tuple[BaseModel, ...], bool]], None],
    ) -> None:
        """Project the payer and asset identities stated in M210 classifications."""
        m210 = tuple(
            (classification, _dated(row))
            for row in movements
            if (classification := row.m210_income_classification) is not None
        )
        if LedgerKnownValueKind.M210_PAYER in kinds:
            keep(
                LedgerKnownValueKind.M210_PAYER,
                "m210_payers",
                _known_texts((row.payer_id, used_on, None) for row, used_on in m210),
            )
        if LedgerKnownValueKind.M210_ASSET in kinds:
            keep(
                LedgerKnownValueKind.M210_ASSET,
                "m210_assets",
                _known_texts((row.asset_or_right_id, used_on, None) for row, used_on in m210),
            )

    async def execute(
        self, request: OperationRequest[LedgerKnownValuesRequest], context: OperationExecutorContext
    ) -> str:
        """Publish the values as an encrypted no-effect result."""
        payload = request.payload
        if request.definition_id != LEDGER_KNOWN_VALUES_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, payload.profile_id)
        await context.events.phase(LEDGER_KNOWN_VALUES_OPERATION_DEFINITION_ID)
        return await capture_read_result(context, lambda: self._read(payload, context), task_name="ledger-known-values")


def build_ledger_known_values_definition(ports: LedgerKnownValuesPorts) -> OperationDefinition:
    """Register a whole-profile read without commit or provider authority."""
    return build_single_phase_definition(
        definition_id=LEDGER_KNOWN_VALUES_OPERATION_DEFINITION_ID,
        request_type=LedgerKnownValuesRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerKnownValuesProjection,
        executor_type=LedgerKnownValuesExecutor,
        build=lambda: LedgerKnownValuesExecutor(ports),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
    )


def resolve_ledger_known_values_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require the exact profile and every period: the values span the whole history."""
    return resolve_ledger_request_read_access(
        request,
        context,
        definition_id=LEDGER_KNOWN_VALUES_OPERATION_DEFINITION_ID,
        request_type=LedgerKnownValuesRequest,
    )


def build_ledger_known_values_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the values schema to whole-profile scope evaluation."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerKnownValuesProjection,
        access_resolver=resolve_ledger_known_values_access,
    )
