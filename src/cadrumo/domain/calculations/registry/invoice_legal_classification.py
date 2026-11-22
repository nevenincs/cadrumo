"""Typed projection of the invoice legal-classification vocabulary (0141)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Final

from ....core.registry_token import StrictRegistryToken
from ...invoices.enums import (
    InvoiceClass,
    InvoiceOperationDateRole,
    RectificationCause,
    RectificationDirection,
    RectificationMethod,
)
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
    from .governed_fact_scope import GovernedFactSource


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
_RECTIFICATION_METHOD_ORDER_KEY = "rectification_method.order"
_RECTIFICATION_METHOD_PREFIX = "rectification_method."
_RECTIFICATION_METHOD_DIFERENCIA_KEY = "rectification_method.diferencia_token"
_RECTIFICATION_METHOD_SUSTITUCION_KEY = "rectification_method.sustitucion_token"
_RECTIFICATION_DIRECTION_ORDER_KEY = "rectification_direction.order"
_RECTIFICATION_DIRECTION_PREFIX = "rectification_direction."
_RECTIFICATION_DIRECTION_MINORACION_KEY = "rectification_direction.minoracion_token"
_RECTIFICATION_DIRECTION_AUMENTO_KEY = "rectification_direction.aumento_token"
_RECTIFICATION_CAUSE_ORDER_KEY = "rectification_cause.order"
_RECTIFICATION_CAUSE_PREFIX = "rectification_cause."
_RECTIFICATION_CAUSE_ART_80_TRES_KEY = "rectification_cause.art_80_tres_token"
_RECTIFICATION_CAUSE_ERROR_FUNDADO_KEY = "rectification_cause.error_fundado_de_derecho_token"
_RECTIFICATION_CAUSE_OTRA_KEY = "rectification_cause.otra_modificacion_token"


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
class RectificationMethodDefinition:
    """One registry-declared RD 1619/2012 art. 15.5 way of stating a rectification."""

    token: RectificationMethod
    description: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RectificationDirectionDefinition:
    """One registry-declared economic sense a rectification carries."""

    token: RectificationDirection
    description: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RectificationCauseDefinition:
    """One registry-declared ground on which a rectificativa modifies base and cuota."""

    token: RectificationCause
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
    rectification_methods: tuple[RectificationMethodDefinition, ...]
    rectification_directions: tuple[RectificationDirectionDefinition, ...]
    rectification_causes: tuple[RectificationCauseDefinition, ...]
    diferencia_token: RectificationMethod
    sustitucion_token: RectificationMethod
    minoracion_token: RectificationDirection
    aumento_token: RectificationDirection
    art_80_tres_cause_token: RectificationCause
    error_fundado_de_derecho_cause_token: RectificationCause
    otra_modificacion_cause_token: RectificationCause

    @property
    def rectification_method_choices(self) -> tuple[RectificationMethod, ...]:
        """Return rectification methods in the registry-authored order."""
        return tuple(item.token for item in self.rectification_methods)

    @property
    def rectification_direction_choices(self) -> tuple[RectificationDirection, ...]:
        """Return rectification directions in the registry-authored order."""
        return tuple(item.token for item in self.rectification_directions)

    @property
    def rectification_cause_choices(self) -> tuple[RectificationCause, ...]:
        """Return rectification causes in the registry-authored order."""
        return tuple(item.token for item in self.rectification_causes)

    def require_rectification_method(self, value: object) -> RectificationMethod:
        """Project a rectification method only when the selected fact declares it."""
        return _require_declared(
            value,
            choices=self.rectification_method_choices,
            factory=RectificationMethod.from_registry,
            subject="rectification method",
        )

    def require_rectification_direction(self, value: object) -> RectificationDirection:
        """Project a rectification direction only when the selected fact declares it."""
        return _require_declared(
            value,
            choices=self.rectification_direction_choices,
            factory=RectificationDirection.from_registry,
            subject="rectification direction",
        )

    def require_rectification_cause(self, value: object) -> RectificationCause:
        """Project a rectification cause only when the selected fact declares it."""
        return _require_declared(
            value,
            choices=self.rectification_cause_choices,
            factory=RectificationCause.from_registry,
            subject="rectification cause",
        )

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


def _require_declared[TokenT: StrictRegistryToken](
    value: object,
    *,
    choices: tuple[TokenT, ...],
    factory: Callable[[str], TokenT],
    subject: str,
) -> TokenT:
    """Project one token of a rectification vocabulary, refusing anything fact 0141 omits.

    Shared by the three rectification families because the refusal they owe a
    caller is the same: the accepted tokens are whatever the selected variant
    declares, so every refusal names them rather than a hard-coded list.
    """
    accepted = ", ".join(str(choice) for choice in choices)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise RegistryValidationError(f"{subject} must be a non-empty string token; accepted values: {accepted}")
        try:
            token = factory(raw)
        except (TypeError, ValueError) as exc:
            raise RegistryValidationError(
                f"{subject} must be a registry token; accepted values: {accepted}",
            ) from exc
    else:
        raise RegistryValidationError(f"{subject} must be a string token; accepted values: {accepted}")
    if token not in choices:
        raise RegistryValidationError(
            f"{subject} {str(token)!r} is not declared by fact {_FACT_ID!r}; accepted values: {accepted}",
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

    methods = tuple(
        RectificationMethodDefinition(token=token, description=description, legal_refs=legal_refs)
        for token, description, legal_refs in _vocabulary_members(
            entries,
            order_key=_RECTIFICATION_METHOD_ORDER_KEY,
            prefix=_RECTIFICATION_METHOD_PREFIX,
            factory=RectificationMethod.from_registry,
            label="rectification method",
        )
    )
    directions = tuple(
        RectificationDirectionDefinition(token=token, description=description, legal_refs=legal_refs)
        for token, description, legal_refs in _vocabulary_members(
            entries,
            order_key=_RECTIFICATION_DIRECTION_ORDER_KEY,
            prefix=_RECTIFICATION_DIRECTION_PREFIX,
            factory=RectificationDirection.from_registry,
            label="rectification direction",
        )
    )
    causes = tuple(
        RectificationCauseDefinition(token=token, description=description, legal_refs=legal_refs)
        for token, description, legal_refs in _vocabulary_members(
            entries,
            order_key=_RECTIFICATION_CAUSE_ORDER_KEY,
            prefix=_RECTIFICATION_CAUSE_PREFIX,
            factory=RectificationCause.from_registry,
            label="rectification cause",
        )
    )
    method_choices = tuple(item.token.value for item in methods)
    direction_choices = tuple(item.token.value for item in directions)
    cause_choices = tuple(item.token.value for item in causes)
    diferencia = _pointer(entries, _RECTIFICATION_METHOD_DIFERENCIA_KEY, method_choices, label="rectification-method")
    sustitucion = _pointer(entries, _RECTIFICATION_METHOD_SUSTITUCION_KEY, method_choices, label="rectification-method")
    minoracion = _pointer(
        entries,
        _RECTIFICATION_DIRECTION_MINORACION_KEY,
        direction_choices,
        label="rectification-direction",
    )
    aumento = _pointer(
        entries,
        _RECTIFICATION_DIRECTION_AUMENTO_KEY,
        direction_choices,
        label="rectification-direction",
    )
    art_80_tres = _pointer(entries, _RECTIFICATION_CAUSE_ART_80_TRES_KEY, cause_choices, label="rectification-cause")
    error_fundado = _pointer(
        entries,
        _RECTIFICATION_CAUSE_ERROR_FUNDADO_KEY,
        cause_choices,
        label="rectification-cause",
    )
    otra = _pointer(entries, _RECTIFICATION_CAUSE_OTRA_KEY, cause_choices, label="rectification-cause")
    _require_distinct_pointers((diferencia, sustitucion), label="rectification-method")
    _require_distinct_pointers((minoracion, aumento), label="rectification-direction")
    _require_distinct_pointers((art_80_tres, error_fundado, otra), label="rectification-cause")

    return InvoiceLegalClassificationCatalogue(
        declarations=entries,
        invoice_classes=tuple(invoice_classes),
        operation_date_roles=tuple(operation_date_roles),
        ordinaria_token=InvoiceClass.from_registry(ordinaria),
        simplificada_token=InvoiceClass.from_registry(simplificada),
        rectificativa_token=InvoiceClass.from_registry(rectificativa),
        operation_performed_token=InvoiceOperationDateRole.from_registry(operation_performed),
        advance_payment_received_token=InvoiceOperationDateRole.from_registry(advance_payment_received),
        rectification_methods=methods,
        rectification_directions=directions,
        rectification_causes=causes,
        diferencia_token=RectificationMethod.from_registry(diferencia),
        sustitucion_token=RectificationMethod.from_registry(sustitucion),
        minoracion_token=RectificationDirection.from_registry(minoracion),
        aumento_token=RectificationDirection.from_registry(aumento),
        art_80_tres_cause_token=RectificationCause.from_registry(art_80_tres),
        error_fundado_de_derecho_cause_token=RectificationCause.from_registry(error_fundado),
        otra_modificacion_cause_token=RectificationCause.from_registry(otra),
    )


def _require_distinct_pointers(pointers: tuple[str, ...], *, label: str) -> None:
    if len(set(pointers)) != len(pointers):
        raise RegistryValidationError(f"invoice legal-classification {label} pointers must be distinct")


def _vocabulary_members[TokenT: StrictRegistryToken](
    entries: Mapping[str, str],
    *,
    order_key: str,
    prefix: str,
    factory: Callable[[str], TokenT],
    label: str,
) -> tuple[tuple[TokenT, str, tuple[str, ...]], ...]:
    """Read one ordered token family of fact 0141 into its token, words and provenance.

    Each member restates its own token under ``.value`` as the invoice-class
    family does, so a reordered or mistyped ``order`` entry is caught here
    rather than producing a definition whose token and body disagree.
    """
    members: list[tuple[TokenT, str, tuple[str, ...]]] = []
    for raw_token in unique_mapping_tokens(entries, order_key, subject=_ENTRY_SUBJECT):
        member_prefix = f"{prefix}{raw_token}."
        if required_mapping_entry(entries, f"{member_prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"{label} {raw_token!r} declares a mismatched value")
        members.append(
            (
                factory(raw_token),
                required_mapping_entry(entries, f"{member_prefix}description", subject=_ENTRY_SUBJECT),
                unique_mapping_legal_refs(entries, f"{member_prefix}legal_refs", subject=_ENTRY_SUBJECT),
            ),
        )
    if len({token for token, _, _ in members}) != len(members):
        raise RegistryValidationError(f"invoice legal-classification catalogue contains duplicate {label}s")
    return tuple(members)


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
    pointers = (ordinaria, simplificada, rectificativa)
    if len(set(pointers)) != len(pointers):
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
    authority: GovernedFactSource | None = None,
) -> InvoiceLegalClassificationCatalogue:
    """Resolve the dated invoice class and operation-date vocabulary.

    ``authority`` is any governed-fact source, which is what the fact read
    below requires: a caller inside a pinned operation hands that operation in,
    so the vocabulary comes from the generation the operation leased rather
    than from whatever authority is in scope.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.governed_fact_scope.GovernedFactSource`.
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


def require_rectification_method(
    value: object,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> RectificationMethod:
    """Return an RD 1619/2012 art. 15.5 method token only when fact 0141 declares it.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return resolve_invoice_legal_classification_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require_rectification_method(value)


def require_rectification_direction(
    value: object,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> RectificationDirection:
    """Return a rectification direction token only when fact 0141 declares it.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return resolve_invoice_legal_classification_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require_rectification_direction(value)


def require_rectification_cause(
    value: object,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> RectificationCause:
    """Return a rectification cause token only when fact 0141 declares it.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return resolve_invoice_legal_classification_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require_rectification_cause(value)


__all__ = [
    "InvoiceClassDefinition",
    "InvoiceLegalClassificationCatalogue",
    "InvoiceOperationDateRoleDefinition",
    "RectificationCauseDefinition",
    "RectificationDirectionDefinition",
    "RectificationMethodDefinition",
    "advance_payment_received_role",
    "invoice_class_ordinaria",
    "invoice_class_rectificativa",
    "invoice_class_simplificada",
    "operation_performed_role",
    "require_invoice_class",
    "require_invoice_operation_date_role",
    "require_rectification_cause",
    "require_rectification_direction",
    "require_rectification_method",
    "resolve_invoice_legal_classification_catalogue",
]
