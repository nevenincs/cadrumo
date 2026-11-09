"""Registered read of the closed vocabularies a ledger entry form offers.

Each list comes from its owner, so a frontend holds no list of its own. A code
with no ``label_key`` is named by whoever shows it; a country or currency code
is an international standard's token, and the backend holds no name for it.

The country and currency lists are what is known, not what is allowed: a ledger
record checks those codes by shape, so a real jurisdiction outside these lists
stays recordable. The other lists are closed by the writers that read them.

A catalogue the registry dates is read on ``on_date``, and on the registry's own
default day when none is given; the undated lists ignore it.

The filing periods a window selects among are served beside them, from the one
period model, so a window does no period arithmetic: the periods of a year with
their days, neighbours and names in ``output_language``, the periods holding
``on_date`` (today in Spain when none is given), the period holding a span, and
the periods holding each day asked.

The statement formats this installation parses are served with them, so a
window offers no format whose parser is not installed.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import date
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.bucket_pointer import require_active_bucket_id
from ...core.external_constants import DEFAULT_CURRENCY, DEFAULT_OUTPUT_LANGUAGE, OutputLanguage
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.bienes_inversion_catalogue import resolve_bienes_inversion_catalogue
from ...domain.calculations.registry.invoice_legal_classification import resolve_invoice_legal_classification_catalogue
from ...domain.calculations.registry.irnr_tipo_renta import resolve_tipo_renta_irnr_catalogue
from ...domain.calculations.registry.iva_category_catalogue import resolve_iva_category_catalogue
from ...domain.calculations.registry.iva_deduction_catalogue import iva_deduction_fact_kinds
from ...domain.calculations.registry.prorrata_register_catalogue import resolve_prorrata_register_catalogue
from ...domain.categories.spending_category_catalogue import resolve_spending_category_catalogue
from ...domain.invoices.business_premises import SituacionInmueble
from ...domain.invoices.enums import default_invoice_class, invoice_class_rectificativa, invoice_class_simplificada
from ...domain.iva.establishment import catalogued_country_codes
from ...domain.transactions.classification_effects import keeps_category, takes_usage_ratio
from ...domain.transactions.enums import (
    BusinessClassification,
    carries_business_figures,
    rule_names_category,
    split_part_requires_category,
    takes_business_share,
)
from ...domain.transactions.irpf_categories import ledger_irpf_category_catalogue
from ...domain.transactions.m210_income_classification import m210_payer_modes
from ...domain.usage_ratios.model import eligible_usage_ratio_categories
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.models import (
    OperationRequest,
    OperationTerminalReceipt,
    require_succeeded_terminal_receipt,
)
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .actions_import import installed_ledger_providers
from .entry_limits import LedgerEntryLimitsProjection, ledger_entry_limits
from .invoice_label_vocabulary import CURRENCY_CODES
from .period_options import LedgerPeriodsProjection, LedgerPeriodsQuery, PeriodDay, ledger_periods
from .read_access import resolve_ledger_request_read_access

LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID: Final = "ledger.entry-options"

ENTRY_OPTION_LABEL_PREFIX: Final = "application.ledger.entry_options."
"""Where the words of the served tokens live, one family under it per kind of word."""

type EntryOptionFamily = Literal[
    "country",
    "currency",
    "deduction_fact_kind",
    "m210_payer_mode",
    "m210_tipo_renta",
    "iva_category",
    "irpf_category",
    "spending_category",
    "usage_ratio_category",
    "invoice_class",
    "premises_situation",
    "prorrata_provenance",
    "prorrata_sector_letter",
    "capital_good_kind",
    "capital_good_disposal",
    "import_format",
]


class LedgerEntryOptionsRequest(BaseModel):
    """Ask for the vocabularies; they vary by the day a dated one is read on, not by ledger row.

    ``output_language`` is the language the period names are said in; the worker
    renders them for this invocation rather than in its own startup language.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    on_date: PeriodDay | None = None
    output_language: OutputLanguage = DEFAULT_OUTPUT_LANGUAGE
    periods: LedgerPeriodsQuery = LedgerPeriodsQuery()


class LedgerEntryOptionProjection(BaseModel):
    """One offered value, the key of its word where the backend words it, and the group it is filed under."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    value: str
    label_key: str | None = None
    group: str | None = None


class LedgerEntryOptionFamilyProjection(BaseModel):
    """One vocabulary."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    family: EntryOptionFamily
    options: tuple[LedgerEntryOptionProjection, ...]


class LedgerEntryClassificationProjection(BaseModel):
    """What one classification takes, each answer from the predicate the writers enforce it with."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    classification: BusinessClassification
    takes_business_share: bool
    takes_usage_ratio: bool
    carries_business_figures: bool
    keeps_category: bool
    rule_may_name_category: bool
    split_part_requires_category: bool


class LedgerEntryOptionsProjection(BaseModel):
    """The vocabularies a ledger entry form offers, what each classification takes, and its text limits.

    ``default_currency`` is the ledger's functional currency, one of the served ``currency``
    codes: the currency a new movement is offered when the profile's own accounts name none.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    default_currency: str
    families: tuple[LedgerEntryOptionFamilyProjection, ...]
    classifications: tuple[LedgerEntryClassificationProjection, ...]
    limits: LedgerEntryLimitsProjection
    periods: LedgerPeriodsProjection


class LedgerEntryOptionsExecutionResult(BaseModel):
    """Private result kept in the worker's encrypted operation record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: LedgerEntryOptionsProjection


def _codes(values: frozenset[str]) -> tuple[LedgerEntryOptionProjection, ...]:
    return tuple(LedgerEntryOptionProjection(value=value) for value in sorted(values))


def _worded(word_family: str, tokens: tuple[str, ...]) -> tuple[LedgerEntryOptionProjection, ...]:
    return tuple(
        LedgerEntryOptionProjection(value=token, label_key=f"{ENTRY_OPTION_LABEL_PREFIX}{word_family}.{token}")
        for token in tokens
    )


def _classification_rules() -> tuple[LedgerEntryClassificationProjection, ...]:
    """Answer, for each classification in the enum's order, what the writers ask of it.

    A rule deciding a classification names a category only where
    ``rule_names_category`` allows it, and a share belongs only where
    ``takes_business_share`` says so; each flag is that predicate's verdict, so
    what is served and what is enforced cannot differ.
    """
    return tuple(
        LedgerEntryClassificationProjection(
            classification=classification,
            takes_business_share=takes_business_share(classification),
            takes_usage_ratio=takes_usage_ratio(classification),
            carries_business_figures=carries_business_figures(classification),
            keeps_category=keeps_category(classification),
            rule_may_name_category=rule_names_category(classification),
            split_part_requires_category=split_part_requires_category(classification),
        )
        for classification in BusinessClassification
    )


def _tipo_renta_options(operation: PinnedAuthorityOperation) -> tuple[LedgerEntryOptionProjection, ...]:
    """Offer the official codes a calculation can project, each worded by its income concept.

    A fetch-gated code has no projected concept and the calculation refuses it,
    so it is not offered; a row that already stores one keeps it.
    """
    catalogue = resolve_tipo_renta_irnr_catalogue(authority=operation)
    return tuple(
        LedgerEntryOptionProjection(
            value=definition.code,
            label_key=f"{ENTRY_OPTION_LABEL_PREFIX}m210_income_concept.{definition.concept.value}",
        )
        for definition in catalogue.code_definitions
        if definition.concept is not None and not definition.fetch_gated
    )


def _plain(tokens: Iterable[object]) -> tuple[LedgerEntryOptionProjection, ...]:
    return tuple(LedgerEntryOptionProjection(value=str(token)) for token in tokens)


def _spending_options(
    on_date: date | None, operation: PinnedAuthorityOperation
) -> tuple[LedgerEntryOptionProjection, ...]:
    """Offer each spending category under the family the registry files it in."""
    catalogue = resolve_spending_category_catalogue(effective_date=on_date, authority=operation)
    return tuple(
        LedgerEntryOptionProjection(value=str(category), group=family.value)
        for family, members in catalogue.family_members.items()
        for category in members
    )


def _invoice_class_options(on_date: date | None) -> tuple[LedgerEntryOptionProjection, ...]:
    """Offer each invoice class, filed under what it means to whoever fills a form in.

    A form starts on the ``default`` class, a ``corrective`` one names the invoice it
    rectifies and a ``simplified`` one may leave the counterparty's tax id out; the
    tokens stay the registry's.
    """
    groups = {
        default_invoice_class(effective_date=on_date): "default",
        invoice_class_simplificada(effective_date=on_date): "simplified",
        invoice_class_rectificativa(effective_date=on_date): "corrective",
    }
    return tuple(
        LedgerEntryOptionProjection(value=str(token), group=groups.get(token))
        for token in resolve_invoice_legal_classification_catalogue(effective_date=on_date).invoice_class_choices
    )


def _usage_ratio_options(
    on_date: date | None, operation: PinnedAuthorityOperation
) -> tuple[LedgerEntryOptionProjection, ...]:
    """Offer the categories a usage ratio applies to, in the spending catalogue's order.

    Which categories take a ratio is the registry's proportionality kind, which does not vary by day.
    """
    eligible = eligible_usage_ratio_categories()
    catalogue = resolve_spending_category_catalogue(effective_date=on_date, authority=operation)
    return _plain(category for category in catalogue.categories if category in eligible)


def ledger_entry_options(
    profile_id: UUID,
    *,
    operation: PinnedAuthorityOperation,
    on_date: date | None = None,
    periods: LedgerPeriodsQuery | None = None,
    language: OutputLanguage = DEFAULT_OUTPUT_LANGUAGE,
) -> LedgerEntryOptionsProjection:
    """Read every vocabulary from its owner, under one pinned authority generation."""
    prorrata = resolve_prorrata_register_catalogue(effective_date=on_date, authority=operation)
    # These two owners take the scope's pinned generation, which the operation runs inside.
    capital = resolve_bienes_inversion_catalogue(effective_date=on_date)
    families: tuple[tuple[EntryOptionFamily, tuple[LedgerEntryOptionProjection, ...]], ...] = (
        ("country", _codes(catalogued_country_codes(operation=operation))),
        ("currency", _codes(CURRENCY_CODES)),
        (
            "deduction_fact_kind",
            _worded("deduction_fact_kind", tuple(kind.value for kind in iva_deduction_fact_kinds(authority=operation))),
        ),
        (
            "m210_payer_mode",
            _worded("m210_payer_mode", tuple(mode.value for mode in m210_payer_modes(operation=operation))),
        ),
        ("m210_tipo_renta", _tipo_renta_options(operation)),
        (
            "iva_category",
            _plain(resolve_iva_category_catalogue(effective_date=on_date, authority=operation).all_categories),
        ),
        ("irpf_category", _plain(item.id for item in ledger_irpf_category_catalogue(authority=operation))),
        ("spending_category", _spending_options(on_date, operation)),
        ("usage_ratio_category", _usage_ratio_options(on_date, operation)),
        (
            "invoice_class",
            _invoice_class_options(on_date),
        ),
        (
            "premises_situation",
            _plain(SituacionInmueble.form_codes(effective_date=on_date, authority=operation).values()),
        ),
        ("prorrata_provenance", _plain(item.token for item in prorrata.provenances)),
        ("prorrata_sector_letter", _plain(item.token for item in prorrata.sector_letters)),
        ("capital_good_kind", _plain(capital.kind_choices)),
        ("capital_good_disposal", _plain(capital.disposal_regime_choices)),
        ("import_format", _plain(installed_ledger_providers())),
    )
    return LedgerEntryOptionsProjection(
        profile_id=profile_id,
        default_currency=DEFAULT_CURRENCY,
        families=tuple(
            LedgerEntryOptionFamilyProjection(family=family, options=options) for family, options in families
        ),
        classifications=_classification_rules(),
        limits=ledger_entry_limits(),
        periods=ledger_periods(periods or LedgerPeriodsQuery(), reference_day=on_date, language=language),
    )


class LedgerEntryOptionsExecutor:
    """Answer the vocabularies inside the exact profile's worker."""

    async def execute(
        self,
        request: OperationRequest[LedgerEntryOptionsRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Check the exact profile, then answer from the pinned authority; nothing is written."""
        bucket_id = str(request.payload.profile_id)
        subject = profile_operation_subject(bucket_id)
        if (
            request.definition_id != LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID
            or context.identity.definition_id != LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.subject_ref != subject
            or require_active_bucket_id() != bucket_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID)
        options = await asyncio.to_thread(
            ledger_entry_options,
            request.payload.profile_id,
            operation=context.authority_operation,
            on_date=request.payload.on_date,
            periods=request.payload.periods,
            language=request.payload.output_language,
        )
        return await context.operands.put(LedgerEntryOptionsExecutionResult(result=options), written_at=now())


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerEntryOptionsExecutionResult:
        raise ValueError("invalid ledger entry options result")
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(result.result.profile_id)),
        effect=OperationEffect.NONE,
        message="ledger entry options has an incompatible terminal receipt",
    )
    return result.result


def build_ledger_entry_options_definition() -> OperationDefinition:
    """Declare the exact-profile read of the ledger entry vocabularies."""
    return build_single_phase_definition(
        definition_id=LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID,
        request_type=LedgerEntryOptionsRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerEntryOptionsExecutionResult,
        executor_type=LedgerEntryOptionsExecutor,
        build=LedgerEntryOptionsExecutor,
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    )


def resolve_ledger_entry_options_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind the read to the exact profile, as every ledger read is."""
    return resolve_ledger_request_read_access(
        request,
        context,
        definition_id=LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID,
        request_type=LedgerEntryOptionsRequest,
    )


def build_ledger_entry_options_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind bounded schemas, exact-profile access and receipt projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerEntryOptionsProjection,
        result_projector=_project_result,
        access_resolver=resolve_ledger_entry_options_access,
    )


__all__ = [
    "ENTRY_OPTION_LABEL_PREFIX",
    "LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID",
    "EntryOptionFamily",
    "LedgerEntryClassificationProjection",
    "LedgerEntryOptionFamilyProjection",
    "LedgerEntryOptionProjection",
    "LedgerEntryOptionsExecutionResult",
    "LedgerEntryOptionsExecutor",
    "LedgerEntryOptionsProjection",
    "LedgerEntryOptionsRequest",
    "build_ledger_entry_options_definition",
    "build_ledger_entry_options_registration",
    "ledger_entry_options",
    "resolve_ledger_entry_options_access",
]
