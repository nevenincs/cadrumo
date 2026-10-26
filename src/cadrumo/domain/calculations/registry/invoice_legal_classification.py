"""Typed projection of the invoice legal-classification vocabulary (0141)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Final

from ...invoices.enums import InvoiceClass, InvoiceOperationDateRole
from .errors import RegistryValidationError
from .facts.resolution import required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
    unique_mapping_legal_refs,
)
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "invoice legal-classification catalogue"

if TYPE_CHECKING:
    from .authority import ValidatedRegistryAuthority


_FACT_ID = "invoice-legal-classification-catalogue"
_INVOICE_CLASS_ORDER_KEY = "invoice_class.order"
_INVOICE_CLASS_PREFIX = "invoice_class."
_INVOICE_CLASS_ORDINARIA_KEY = "invoice_class.ordinaria_token"
_INVOICE_CLASS_SIMPLIFICADA_KEY = "invoice_class.simplificada_token"
_INVOICE_CLASS_RECTIFICATIVA_KEY = "invoice_class.rectificativa_token"
_OPERATION_DATE_ROLE_ORDER_KEY = "invoice_operation_date_role.order"
_OPERATION_DATE_ROLE_PREFIX = "invoice_operation_date_role."
_OPERATION_DATE_ROLE_PERFORMED_KEY = "invoice_operation_date_role.operation_performed_token"
_OPERATION_DATE_ROLE_ADVANCE_KEY = "invoice_operation_date_role.advance_payment_received_token"


@dataclass(frozen=True, slots=True)
class InvoiceClassDefinition:
    """One registry-declared invoice class and its legal semantics."""

    token: InvoiceClass
    description: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InvoiceOperationDateRoleDefinition:
    """One registry-declared operation-date role and its legal semantics."""

    token: InvoiceOperationDateRole
    description: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InvoiceLegalClassificationCatalogue:
    """Complete dated projection of fact 0141."""

    declarations: Mapping[str, str]
    invoice_classes: tuple[InvoiceClassDefinition, ...]
    operation_date_roles: tuple[InvoiceOperationDateRoleDefinition, ...]
    ordinaria_token: InvoiceClass
    simplificada_token: InvoiceClass
    rectificativa_token: InvoiceClass
    operation_performed_token: InvoiceOperationDateRole
    advance_payment_received_token: InvoiceOperationDateRole

    @property
    def invoice_class_choices(self) -> tuple[InvoiceClass, ...]:
        """Return invoice classes in the registry-authored order."""
        return tuple(item.token for item in self.invoice_classes)

    @property
    def operation_date_role_choices(self) -> tuple[InvoiceOperationDateRole, ...]:
        """Return operation-date roles in the registry-authored order."""
        return tuple(item.token for item in self.operation_date_roles)

    def require_invoice_class(self, value: object) -> InvoiceClass:
        """Project an invoice class only when the selected fact declares it."""
        accepted = ", ".join(str(choice) for choice in self.invoice_class_choices)
        if isinstance(value, InvoiceClass):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError(
                    f"invoice class must be a non-empty string token; accepted values: {accepted}",
                )
            try:
                token = InvoiceClass.from_registry(raw)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError(
                    f"invoice class must be a registry token; accepted values: {accepted}",
                ) from exc
        else:
            raise RegistryValidationError(f"invoice class must be a string token; accepted values: {accepted}")
        if token not in self.invoice_class_choices:
            raise RegistryValidationError(
                f"invoice class {str(token)!r} is not declared by fact {_FACT_ID!r}; accepted values: {accepted}",
            )
        return token

    def require_operation_date_role(self, value: object) -> InvoiceOperationDateRole:
        """Project an operation-date role only when the selected fact declares it."""
        if isinstance(value, InvoiceOperationDateRole):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("invoice operation-date role must be a non-empty string token")
            try:
                token = InvoiceOperationDateRole.from_registry(raw)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError(
                    "invoice operation-date role must be a non-empty string token",
                ) from exc
        else:
            raise RegistryValidationError("invoice operation-date role must be a string token")
        if token not in self.operation_date_role_choices:
            raise RegistryValidationError(
                f"invoice operation-date role {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY)


def _pointer(
    entries: Mapping[str, str],
    key: str,
    choices: tuple[str, ...],
    *,
    label: str,
) -> str:
    value = required_mapping_entry(entries, key, subject=_ENTRY_SUBJECT)
    if value not in choices:
        raise RegistryValidationError(f"invoice legal-classification {label} pointer {key!r} is undeclared")
    return value


def _catalogue(entries: Mapping[str, str]) -> InvoiceLegalClassificationCatalogue:
    invoice_classes = _invoice_class_definitions(entries)
    operation_date_roles = _operation_date_role_definitions(entries)
    ordinaria, simplificada, rectificativa = _invoice_class_semantic_tokens(entries, invoice_classes)
    operation_performed, advance_payment_received = _operation_date_role_semantic_tokens(entries, operation_date_roles)

    return InvoiceLegalClassificationCatalogue(
        declarations=entries,
        invoice_classes=tuple(invoice_classes),
        operation_date_roles=tuple(operation_date_roles),
        ordinaria_token=InvoiceClass.from_registry(ordinaria),
        simplificada_token=InvoiceClass.from_registry(simplificada),
        rectificativa_token=InvoiceClass.from_registry(rectificativa),
        operation_performed_token=InvoiceOperationDateRole.from_registry(operation_performed),
        advance_payment_received_token=InvoiceOperationDateRole.from_registry(advance_payment_received),
    )


def _invoice_class_definitions(entries: Mapping[str, str]) -> list[InvoiceClassDefinition]:
    definitions: list[InvoiceClassDefinition] = []
    invoice_class_order = unique_mapping_tokens(entries, _INVOICE_CLASS_ORDER_KEY, subject=_ENTRY_SUBJECT)
    for raw_token in invoice_class_order:
        token = InvoiceClass.from_registry(raw_token)
        prefix = f"{_INVOICE_CLASS_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"invoice class {raw_token!r} declares a mismatched value")
        definitions.append(
            InvoiceClassDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}description", subject=_ENTRY_SUBJECT),
                legal_refs=unique_mapping_legal_refs(entries, f"{prefix}legal_refs", subject=_ENTRY_SUBJECT),
            ),
        )
    if len({item.token for item in definitions}) != len(definitions):
        raise RegistryValidationError("invoice legal-classification catalogue contains duplicate invoice classes")
    return definitions


def _operation_date_role_definitions(entries: Mapping[str, str]) -> list[InvoiceOperationDateRoleDefinition]:
    definitions: list[InvoiceOperationDateRoleDefinition] = []
    role_order = unique_mapping_tokens(entries, _OPERATION_DATE_ROLE_ORDER_KEY, subject=_ENTRY_SUBJECT)
    for raw_token in role_order:
        token = InvoiceOperationDateRole.from_registry(raw_token)
        prefix = f"{_OPERATION_DATE_ROLE_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"invoice operation-date role {raw_token!r} declares a mismatched value")
        definitions.append(
            InvoiceOperationDateRoleDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}description", subject=_ENTRY_SUBJECT),
                legal_refs=unique_mapping_legal_refs(entries, f"{prefix}legal_refs", subject=_ENTRY_SUBJECT),
            ),
        )
    if len({item.token for item in definitions}) != len(definitions):
        raise RegistryValidationError(
            "invoice legal-classification catalogue contains duplicate operation-date roles",
        )
    return definitions


def _invoice_class_semantic_tokens(
    entries: Mapping[str, str],
    invoice_classes: list[InvoiceClassDefinition],
) -> tuple[str, str, str]:
    choices = tuple(item.token.value for item in invoice_classes)
    ordinaria = _pointer(entries, _INVOICE_CLASS_ORDINARIA_KEY, choices, label="invoice-class")
    simplificada = _pointer(entries, _INVOICE_CLASS_SIMPLIFICADA_KEY, choices, label="invoice-class")
    rectificativa = _pointer(entries, _INVOICE_CLASS_RECTIFICATIVA_KEY, choices, label="invoice-class")
    if len({ordinaria, simplificada, rectificativa}) != 3:
        raise RegistryValidationError("invoice legal-classification class pointers must be distinct")
    return ordinaria, simplificada, rectificativa


def _operation_date_role_semantic_tokens(
    entries: Mapping[str, str],
    operation_date_roles: list[InvoiceOperationDateRoleDefinition],
) -> tuple[str, str]:
    choices = tuple(item.token.value for item in operation_date_roles)
    performed = _pointer(entries, _OPERATION_DATE_ROLE_PERFORMED_KEY, choices, label="operation-date-role")
    advance = _pointer(entries, _OPERATION_DATE_ROLE_ADVANCE_KEY, choices, label="operation-date-role")
    if performed == advance:
        raise RegistryValidationError("invoice legal-classification role pointers must be distinct")
    return performed, advance


def resolve_invoice_legal_classification_catalogue(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> InvoiceLegalClassificationCatalogue:
    """Resolve the dated invoice class and operation-date vocabulary.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return _catalogue(_ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority))


def require_invoice_class(
    value: object,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> InvoiceClass:
    """Return an invoice-class token only when fact 0141 declares it.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return resolve_invoice_legal_classification_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require_invoice_class(value)


def require_invoice_operation_date_role(
    value: object,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> InvoiceOperationDateRole:
    """Return an operation-date role only when fact 0141 declares it.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return resolve_invoice_legal_classification_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require_operation_date_role(value)


def invoice_class_ordinaria(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> InvoiceClass:
    """Return the registry-declared ordinary invoice-class token.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return resolve_invoice_legal_classification_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).ordinaria_token


def invoice_class_simplificada(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> InvoiceClass:
    """Return the registry-declared simplified invoice-class token.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return resolve_invoice_legal_classification_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).simplificada_token


def invoice_class_rectificativa(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> InvoiceClass:
    """Return the registry-declared corrective invoice-class token.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return resolve_invoice_legal_classification_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).rectificativa_token


def operation_performed_role(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> InvoiceOperationDateRole:
    """Return the registry-declared performed-operation date role.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return resolve_invoice_legal_classification_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).operation_performed_token


def advance_payment_received_role(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> InvoiceOperationDateRole:
    """Return the registry-declared advance-payment date role.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return resolve_invoice_legal_classification_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).advance_payment_received_token


__all__ = [
    "InvoiceClassDefinition",
    "InvoiceLegalClassificationCatalogue",
    "InvoiceOperationDateRoleDefinition",
    "advance_payment_received_role",
    "invoice_class_ordinaria",
    "invoice_class_rectificativa",
    "invoice_class_simplificada",
    "operation_performed_role",
    "require_invoice_class",
    "require_invoice_operation_date_role",
    "resolve_invoice_legal_classification_catalogue",
]
