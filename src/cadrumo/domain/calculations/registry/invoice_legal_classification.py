"""Typed projection of the invoice legal-classification vocabulary (0141)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING

from ...invoices.enums import InvoiceClass, InvoiceOperationDateRole
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, cache_governed_projection, governed_facts_in_scope
from .schema_base import DateAxis

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
        if isinstance(value, InvoiceClass):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("invoice class must be a non-empty string token")
            try:
                token = InvoiceClass._from_registry(raw)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError("invoice class must be a non-empty string token") from exc
        else:
            raise RegistryValidationError("invoice class must be a string token")
        if token not in self.invoice_class_choices:
            raise RegistryValidationError(
                f"invoice class {str(token)!r} is not declared by fact {_FACT_ID!r}",
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
                token = InvoiceOperationDateRole._from_registry(raw)
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

    def invoice_class_definition(self, value: object) -> InvoiceClassDefinition:
        """Return the full legal definition for one invoice class."""
        token = self.require_invoice_class(value)
        for definition in self.invoice_classes:
            if definition.token == token:
                return definition
        raise RegistryValidationError(f"invoice class {str(token)!r} has no registry definition")

    def operation_date_role_definition(self, value: object) -> InvoiceOperationDateRoleDefinition:
        """Return the full legal definition for one operation-date role."""
        token = self.require_operation_date_role(value)
        for definition in self.operation_date_roles:
            if definition.token == token:
                return definition
        raise RegistryValidationError(f"invoice operation-date role {str(token)!r} has no registry definition")


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"invoice legal-classification catalogue is missing {key!r}")
    return value.strip()


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"invoice legal-classification catalogue {key!r} must contain unique tokens")
    return values


def _legal_refs(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(
            f"invoice legal-classification catalogue {key!r} must contain unique legal references",
        )
    return values


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError(
                "invoice legal-classification catalogue entries must be string-to-string",
            )
        if entry.key in entries:
            raise RegistryValidationError(
                f"duplicate invoice legal-classification catalogue key {entry.key!r}",
            )
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _resolve_entries(*, effective_date: date, authority: GovernedFactSource) -> Mapping[str, str]:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("invoice legal-classification catalogue must resolve as a mapping fact")
    return _mapping_entries(resolved)


@cache_governed_projection(maxsize=64)
def _bundled_mapping_entries(effective_date: date) -> Mapping[str, str]:
    from .authority import bundled_authority

    return _resolve_entries(effective_date=effective_date, authority=(governed_facts_in_scope() or bundled_authority()))


def _selected_mapping_entries(
    *,
    effective_date: date,
    authority: GovernedFactSource | None,
) -> Mapping[str, str]:
    selected = authority or governed_facts_in_scope()
    if selected is None:
        return _bundled_mapping_entries(effective_date)
    return _resolve_entries(effective_date=effective_date, authority=selected)


def _pointer(
    entries: Mapping[str, str],
    key: str,
    choices: tuple[str, ...],
    *,
    label: str,
) -> str:
    value = _required(entries, key)
    if value not in choices:
        raise RegistryValidationError(f"invoice legal-classification {label} pointer {key!r} is undeclared")
    return value


def _catalogue(entries: Mapping[str, str]) -> InvoiceLegalClassificationCatalogue:
    invoice_classes: list[InvoiceClassDefinition] = []
    invoice_class_order = _csv(entries, _INVOICE_CLASS_ORDER_KEY)
    for raw_token in invoice_class_order:
        token = InvoiceClass._from_registry(raw_token)
        prefix = f"{_INVOICE_CLASS_PREFIX}{raw_token}."
        if _required(entries, f"{prefix}value") != raw_token:
            raise RegistryValidationError(f"invoice class {raw_token!r} declares a mismatched value")
        invoice_classes.append(
            InvoiceClassDefinition(
                token=token,
                description=_required(entries, f"{prefix}description"),
                legal_refs=_legal_refs(entries, f"{prefix}legal_refs"),
            ),
        )
    if len({item.token for item in invoice_classes}) != len(invoice_classes):
        raise RegistryValidationError("invoice legal-classification catalogue contains duplicate invoice classes")

    operation_date_roles: list[InvoiceOperationDateRoleDefinition] = []
    operation_date_role_order = _csv(entries, _OPERATION_DATE_ROLE_ORDER_KEY)
    for raw_token in operation_date_role_order:
        token = InvoiceOperationDateRole._from_registry(raw_token)
        prefix = f"{_OPERATION_DATE_ROLE_PREFIX}{raw_token}."
        if _required(entries, f"{prefix}value") != raw_token:
            raise RegistryValidationError(f"invoice operation-date role {raw_token!r} declares a mismatched value")
        operation_date_roles.append(
            InvoiceOperationDateRoleDefinition(
                token=token,
                description=_required(entries, f"{prefix}description"),
                legal_refs=_legal_refs(entries, f"{prefix}legal_refs"),
            ),
        )
    if len({item.token for item in operation_date_roles}) != len(operation_date_roles):
        raise RegistryValidationError(
            "invoice legal-classification catalogue contains duplicate operation-date roles",
        )

    invoice_class_choices = tuple(item.token.value for item in invoice_classes)
    operation_date_role_choices = tuple(item.token.value for item in operation_date_roles)
    ordinaria = _pointer(
        entries,
        _INVOICE_CLASS_ORDINARIA_KEY,
        invoice_class_choices,
        label="invoice-class",
    )
    simplificada = _pointer(
        entries,
        _INVOICE_CLASS_SIMPLIFICADA_KEY,
        invoice_class_choices,
        label="invoice-class",
    )
    rectificativa = _pointer(
        entries,
        _INVOICE_CLASS_RECTIFICATIVA_KEY,
        invoice_class_choices,
        label="invoice-class",
    )
    if len({ordinaria, simplificada, rectificativa}) != 3:
        raise RegistryValidationError("invoice legal-classification class pointers must be distinct")
    operation_performed = _pointer(
        entries,
        _OPERATION_DATE_ROLE_PERFORMED_KEY,
        operation_date_role_choices,
        label="operation-date-role",
    )
    advance_payment_received = _pointer(
        entries,
        _OPERATION_DATE_ROLE_ADVANCE_KEY,
        operation_date_role_choices,
        label="operation-date-role",
    )
    if operation_performed == advance_payment_received:
        raise RegistryValidationError("invoice legal-classification role pointers must be distinct")

    return InvoiceLegalClassificationCatalogue(
        declarations=entries,
        invoice_classes=tuple(invoice_classes),
        operation_date_roles=tuple(operation_date_roles),
        ordinaria_token=InvoiceClass._from_registry(ordinaria),
        simplificada_token=InvoiceClass._from_registry(simplificada),
        rectificativa_token=InvoiceClass._from_registry(rectificativa),
        operation_performed_token=InvoiceOperationDateRole._from_registry(operation_performed),
        advance_payment_received_token=InvoiceOperationDateRole._from_registry(advance_payment_received),
    )


@cache_governed_projection(maxsize=64)
def _bundled_catalogue(effective_date: date) -> InvoiceLegalClassificationCatalogue:
    return _catalogue(_bundled_mapping_entries(effective_date))


def resolve_invoice_legal_classification_catalogue(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> InvoiceLegalClassificationCatalogue:
    """Resolve the dated invoice class and operation-date vocabulary."""
    coordinate = effective_date or date.today()
    if authority is None and governed_facts_in_scope() is None:
        return _bundled_catalogue(coordinate)
    return _catalogue(_selected_mapping_entries(effective_date=coordinate, authority=authority))


def require_invoice_class(
    value: object,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> InvoiceClass:
    """Return an invoice-class token only when fact 0141 declares it."""
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
    """Return an operation-date role only when fact 0141 declares it."""
    return resolve_invoice_legal_classification_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require_operation_date_role(value)


def invoice_class_ordinaria(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> InvoiceClass:
    """Return the registry-declared ordinary invoice-class token."""
    return resolve_invoice_legal_classification_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).ordinaria_token


def invoice_class_simplificada(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> InvoiceClass:
    """Return the registry-declared simplified invoice-class token."""
    return resolve_invoice_legal_classification_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).simplificada_token


def invoice_class_rectificativa(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> InvoiceClass:
    """Return the registry-declared corrective invoice-class token."""
    return resolve_invoice_legal_classification_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).rectificativa_token


def operation_performed_role(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> InvoiceOperationDateRole:
    """Return the registry-declared performed-operation date role."""
    return resolve_invoice_legal_classification_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).operation_performed_token


def advance_payment_received_role(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> InvoiceOperationDateRole:
    """Return the registry-declared advance-payment date role."""
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
