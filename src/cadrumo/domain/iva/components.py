"""Typed IVA component models and the registry projection boundary.

Concrete category/component rows are canonical registry data. This module
retains only opaque registry tokens, validation models, generic component
calculations, and the explicit boundary that accepts a registry-projected
catalogue.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from functools import lru_cache
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field, ValidationInfo, model_validator

from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.iva_category_catalogue import (
    IvaCategoryCatalogue,
    resolve_iva_category_catalogue,
)
from ..calculations.registry.schema_base import DateAxis
from .classification import InvoiceKind
from .errors import IvaValidationError
from .schema import (
    IvaCategory,
    IvaStrictFrozen,
    _RegistryLegalRef,  # pyright: ignore[reportPrivateUsage] -- intra-package reuse of this package's own constrained legal-ref alias
)

if TYPE_CHECKING:
    from ..calculations.registry.authority import ValidatedRegistryAuthority


class _IvaRegistryToken(str):
    """Opaque token base for component vocabularies authored in fact 0084."""

    __slots__ = ()

    @classmethod
    def _token_label(cls) -> str:
        return "IVA component registry token"

    def __new__(cls, value: str, *, _registry_validated: bool = False):
        if not _registry_validated:
            raise TypeError(f"{cls._token_label()} must be projected from the facts registry")
        if not isinstance(value, str) or not value:
            raise ValueError(f"{cls._token_label()} must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def _from_registry(cls, value: str):
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object):
        if isinstance(value, cls):
            return value
        raise IvaValidationError(f"{cls._token_label()} must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: object, _handler: object) -> object:
        from pydantic_core import core_schema

        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def value(self) -> str:
        return str(self)

    @property
    def name(self) -> str:
        return str(self)


class IvaComponentPresence(_IvaRegistryToken):
    """Registry-projected component-presence token."""

    @classmethod
    def _token_label(cls) -> str:
        return "IVA component-presence token"


class IvaRetencionExpectation(_IvaRegistryToken):
    """Registry-projected retención-expectation token."""

    @classmethod
    def _token_label(cls) -> str:
        return "IVA retención-expectation token"


class IvaRetencionRole(_IvaRegistryToken):
    """Registry-projected retención-role token."""

    @classmethod
    def _token_label(cls) -> str:
        return "IVA retención-role token"


class IvaKindApplicability(_IvaRegistryToken):
    """Registry-projected category/kind applicability token."""

    @classmethod
    def _token_label(cls) -> str:
        return "IVA kind-applicability token"


class IvaCuotaSettlement(str):
    """Opaque registry-projected IVA cuota-settlement token.

    Membership and legal semantics are selected from fact 0084.  This type
    carries only the token shape; production rows are accepted through the
    typed 0084 projection below.
    """

    __slots__ = ()

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: object, _handler: object) -> object:
        """Expose the opaque token as a non-empty string to Pydantic."""
        from pydantic_core import core_schema

        return core_schema.no_info_after_validator_function(cls, core_schema.str_schema(min_length=1))

    @property
    def value(self) -> str:
        """Return the opaque token for string-oriented serialization."""
        return str(self)


@dataclass(frozen=True, slots=True)
class IvaCuotaSettlementDefinition:
    """One registry-declared cuota-settlement token and its semantics."""

    token: IvaCuotaSettlement
    description: str
    legal_ref: str


@dataclass(frozen=True, slots=True)
class IvaCuotaSettlementCatalogue:
    """Typed projection of the dated 0084 cuota-settlement vocabulary."""

    definitions: tuple[IvaCuotaSettlementDefinition, ...]
    no_settlement_token: IvaCuotaSettlement

    @property
    def all_settlements(self) -> frozenset[IvaCuotaSettlement]:
        """Return every settlement token declared by the selected authority."""
        return frozenset(definition.token for definition in self.definitions)

    def require(self, value: object) -> IvaCuotaSettlement:
        """Validate one opaque settlement token against the selected authority."""
        if isinstance(value, IvaCuotaSettlement):
            token = value
        elif isinstance(value, str):
            token = IvaCuotaSettlement(value.strip())
        else:
            raise IvaValidationError("IVA cuota settlement must be a string token")
        if not str(token):
            raise IvaValidationError("IVA cuota settlement token must not be blank")
        if token not in self.all_settlements:
            raise IvaValidationError(
                f"IVA cuota settlement {str(token)!r} is not declared by the facts registry",
            )
        return token


@dataclass(frozen=True, slots=True)
class IvaComponentVocabulary:
    """Typed membership projection for the four component axes in fact 0084."""

    component_presence: frozenset[IvaComponentPresence]
    retencion_expectation: frozenset[IvaRetencionExpectation]
    retencion_role: frozenset[IvaRetencionRole]
    kind_applicability: frozenset[IvaKindApplicability]

    @staticmethod
    def _require(
        value: object,
        token_type: type[_IvaRegistryToken],
        declared: frozenset[_IvaRegistryToken],
        label: str,
    ) -> _IvaRegistryToken:
        if isinstance(value, token_type):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise IvaValidationError(f"{label} must be a non-empty string")
            try:
                token = token_type._from_registry(raw)
            except (TypeError, ValueError) as exc:
                raise IvaValidationError(f"{label} must be a non-empty string") from exc
        else:
            raise IvaValidationError(f"{label} must be a string token")
        if token not in declared:
            raise IvaValidationError(f"{label} {str(token)!r} is not declared by fact 0084")
        return token

    def require_component_presence(self, value: object) -> IvaComponentPresence:
        return self._require(
            value,
            IvaComponentPresence,
            self.component_presence,
            "IVA component-presence token",
        )  # type: ignore[return-value]

    def require_retencion_expectation(self, value: object) -> IvaRetencionExpectation:
        return self._require(
            value,
            IvaRetencionExpectation,
            self.retencion_expectation,
            "IVA retención-expectation token",
        )  # type: ignore[return-value]

    def require_retencion_role(self, value: object) -> IvaRetencionRole:
        return self._require(
            value,
            IvaRetencionRole,
            self.retencion_role,
            "IVA retención-role token",
        )  # type: ignore[return-value]

    def require_kind_applicability(self, value: object) -> IvaKindApplicability:
        return self._require(
            value,
            IvaKindApplicability,
            self.kind_applicability,
            "IVA kind-applicability token",
        )  # type: ignore[return-value]


class IvaGroundingConfidence(StrEnum):
    """How well a declared component expectation is grounded in legal text.

    This is the honesty marker. An expectation the author could not bottom out
    must be declared ``UNGROUNDED`` rather than stated as if verified: an
    unmarked guess in a legal table is worse than a gap, because the next
    reader treats it as confirmed.
    """

    BUNDLED_CORPUS = "bundled_corpus"
    """Verified against a provision present in the bundled legal catalogue and
    named in :attr:`IvaCategoryComponents.legal_refs`."""

    LIVE_SOURCE_ONLY = "live_source_only"
    """Verified against live BOE/AEAT consolidated text, but the binding
    provision is not yet bundled. The provision is named in
    :attr:`IvaCategoryComponents.pending_legal_refs`."""

    REASONED = "reasoned"
    """Inferred from bundled provisions; no bundled provision states it
    directly. Not a measured claim."""

    UNGROUNDED = "ungrounded"
    """No legal basis established — a declared gap, not an assertion."""


class IvaCategoryComponents(IvaStrictFrozen):
    """One Axis-A row: which components an operation in ``category`` has.

    A row is keyed by the PAIR (``category``, ``kind``). Category alone cannot
    express the retención role, which inverts with direction — the same
    withheld euro is the taxpayer's credit on an invoice they issued and their
    liability to AEAT on one they received — and cannot express that several
    categories are one-directional by law.

    Attributes:
        category: The IVA situation this row describes.
        kind: Which side of the operation the taxpayer is on. Half the key.
        applicability: Whether this (category, kind) pair describes an
            operation that can occur at all.
        retencion_role: Whose money a retención here is. Validated against
            ``kind`` and ``retencion`` rather than trusted, so a row cannot
            declare a credit on a received invoice.
        base: Whether a taxable base (contraprestación) exists.
        cuota: Whether an IVA cuota exists.
        cuota_settlement: Who settles the cuota, and where.
        cuota_grounding: Grounding confidence for the cuota columns.
        recargo: Whether a recargo de equivalencia may exist.
        recargo_grounding: Grounding confidence for the recargo column.
        retencion: Whether an IRPF retención is expected.
        retencion_grounding: Grounding confidence for the retención column.
        retencion_note: Carve-outs and caveats behind the retención
            expectation. Required whenever the retención grounding is anything
            other than :attr:`IvaGroundingConfidence.BUNDLED_CORPUS`, so a
            weakly-grounded expectation can never travel without its caveat.
        legal_refs: Registry legal-reference ids backing the row. Every id
            resolves in the bundled legal catalogue.
        pending_legal_refs: Registry legal-reference ids for provisions
            verified against live BOE/AEAT but not yet bundled. Every id here
            is expected *not* to resolve; bundling one reds the gate so the
            author promotes it into :attr:`legal_refs`.
    """

    category: IvaCategory
    kind: InvoiceKind
    applicability: IvaKindApplicability
    retencion_role: IvaRetencionRole
    base: IvaComponentPresence
    cuota: IvaComponentPresence
    cuota_settlement: IvaCuotaSettlement
    cuota_grounding: IvaGroundingConfidence
    recargo: IvaComponentPresence
    recargo_grounding: IvaGroundingConfidence
    retencion: IvaRetencionExpectation
    retencion_grounding: IvaGroundingConfidence
    retencion_note: str = Field(default="")
    legal_refs: tuple[_RegistryLegalRef, ...] = Field(default=())
    pending_legal_refs: tuple[_RegistryLegalRef, ...] = Field(default=())

    @model_validator(mode="after")
    def _validate_row(self, info: ValidationInfo) -> IvaCategoryComponents:
        """Enforce the internal coherence the table's readers rely on."""
        label = f"IvaCategoryComponents[{self.category.value}/{self.kind.value}]"
        component_vocabulary: IvaComponentVocabulary | None = None
        if isinstance(info.context, Mapping):
            context_vocabulary = info.context.get("component_vocabulary")
            if isinstance(context_vocabulary, IvaComponentVocabulary):
                component_vocabulary = context_vocabulary
        if component_vocabulary is None:
            raise IvaValidationError(
                f"{label}: component vocabulary must be projected from fact 0084 before row validation",
            )
        self._validate_retencion_role(label, component_vocabulary)
        self._validate_applicability(label, component_vocabulary)
        self._validate_reference_integrity(label)
        no_settlement_token: IvaCuotaSettlement | None = None
        if isinstance(info.context, Mapping):
            context_token = info.context.get("cuota_settlement_no_token")
            if isinstance(context_token, IvaCuotaSettlement):
                no_settlement_token = context_token
            elif isinstance(context_token, str):
                no_settlement_token = IvaCuotaSettlement(context_token)
        self._validate_cuota_settlement(
            label,
            component_vocabulary=component_vocabulary,
            no_settlement_token=no_settlement_token,
        )
        self._validate_retencion_notes(label, component_vocabulary)
        self._validate_grounding_references(label)
        return self

    def _validate_reference_integrity(self, label: str) -> None:
        """Refuse duplicate or cross-state legal-reference declarations."""
        if len(set(self.legal_refs)) != len(self.legal_refs):
            raise IvaValidationError(f"{label}: legal_refs must be unique")
        if len(set(self.pending_legal_refs)) != len(self.pending_legal_refs):
            raise IvaValidationError(f"{label}: pending_legal_refs must be unique")
        if set(self.legal_refs) & set(self.pending_legal_refs):
            raise IvaValidationError(
                f"{label}: a legal ref cannot be both bundled and pending",
            )

    def _validate_cuota_settlement(
        self,
        label: str,
        *,
        component_vocabulary: IvaComponentVocabulary,
        no_settlement_token: IvaCuotaSettlement | None = None,
    ) -> None:
        """Refuse a cuota whose declared settlement disagrees with its presence."""
        no_settlement = (
            no_settlement_token
            if no_settlement_token is not None
            else registry_cuota_settlement_catalogue().no_settlement_token
        )
        zero_by_law = component_vocabulary.require_component_presence("zero_by_law")
        cuota = component_vocabulary.require_component_presence(self.cuota)
        if (cuota == zero_by_law) != (self.cuota_settlement == no_settlement):
            raise IvaValidationError(
                f"{label}: a zero-by-law cuota must declare the registry's no-settlement token, and vice versa",
            )

    def _validate_retencion_notes(self, label: str, component_vocabulary: IvaComponentVocabulary) -> None:
        """Require caveats for weakly grounded or default retención expectations."""
        if self.retencion_grounding is not IvaGroundingConfidence.BUNDLED_CORPUS and not self.retencion_note.strip():
            raise IvaValidationError(
                f"{label}: retención grounding {self.retencion_grounding.value!r} "
                "requires a retencion_note stating the caveat",
            )
        # A NOT_EXPECTED expectation needs its note no matter how well grounded,
        # because grounding it does not make it unconditional. RIRPF art. 76.1
        # carries two carve-outs that restore the obligation (letra c, a payer
        # with a Spanish permanent establishment; letra d, rendimientos del
        # trabajo and the TRLIRNR art. 24.2 deducible-gasto rendimientos), so an
        # undisclosed "no retención" reads as a prohibition when it is only a
        # default. Keying this on the EXPECTATION rather than on the grounding
        # is deliberate: bundling the provision must not be able to switch the
        # disclosure off, which is exactly what happened when these rows were
        # promoted from live-source-only to bundled-corpus.
        not_expected = component_vocabulary.require_retencion_expectation("not_expected")
        retencion = component_vocabulary.require_retencion_expectation(self.retencion)
        if retencion == not_expected and not self.retencion_note.strip():
            raise IvaValidationError(
                f"{label}: a not-expected retención requires a retencion_note stating the "
                "carve-outs under which the obligation nevertheless arises",
            )

    def _validate_grounding_references(self, label: str) -> None:
        """Require every grounding claim to carry the reference set it names."""
        for name, grounding in (
            ("cuota", self.cuota_grounding),
            ("recargo", self.recargo_grounding),
            ("retencion", self.retencion_grounding),
        ):
            if grounding is IvaGroundingConfidence.LIVE_SOURCE_ONLY and not self.pending_legal_refs:
                raise IvaValidationError(
                    f"{label}: {name} grounding is live-source-only but no pending_legal_refs "
                    "names the unbundled provision",
                )
            if grounding is IvaGroundingConfidence.BUNDLED_CORPUS and not self.legal_refs:
                raise IvaValidationError(
                    f"{label}: {name} grounding claims bundled corpus but the row cites no legal_refs",
                )

    def _validate_retencion_role(self, label: str, component_vocabulary: IvaComponentVocabulary) -> None:
        """Refuse a retención role that contradicts the row's kind or expectation.

        The role is a function of the kind whenever a retención can arise at
        all: an ISSUED invoice is withheld FROM the taxpayer (credit), a
        RECEIVED one is withheld BY them (liability). Declaring it explicitly
        keeps the table readable; checking it here means the declaration cannot
        be wrong, so a consumer may trust the column without re-deriving it.
        """
        expected_by_kind = {
            InvoiceKind.ISSUED: component_vocabulary.require_retencion_role("taxpayer_credit"),
            InvoiceKind.RECEIVED: component_vocabulary.require_retencion_role("taxpayer_liability"),
        }[self.kind]
        expectation = component_vocabulary.require_retencion_expectation(self.retencion)
        required = {
            component_vocabulary.require_retencion_expectation("expected"): expected_by_kind,
            component_vocabulary.require_retencion_expectation("possible"): expected_by_kind,
            component_vocabulary.require_retencion_expectation(
                "not_expected"
            ): component_vocabulary.require_retencion_role("none"),
            component_vocabulary.require_retencion_expectation("unknown"): component_vocabulary.require_retencion_role(
                "unknown"
            ),
        }[expectation]
        role = component_vocabulary.require_retencion_role(self.retencion_role)
        if role != required:
            raise IvaValidationError(
                f"{label}: retención expectation {str(expectation)!r} on a "
                f"{self.kind.value!r} invoice requires role {required.value!r}, "
                f"got {role.value!r}",
            )

    def _validate_applicability(self, label: str, component_vocabulary: IvaComponentVocabulary) -> None:
        """Refuse a non-arising row that still asserts component expectations.

        A pair that cannot occur has nothing to describe, so asserting a
        required base or a settled cuota on it would be a claim about an
        operation that does not exist. The note is mandatory because the only
        useful thing such a row carries is which category IS this kind's
        counterpart.
        """
        does_not_arise = component_vocabulary.require_kind_applicability("does_not_arise")
        applicability = component_vocabulary.require_kind_applicability(self.applicability)
        if applicability != does_not_arise:
            return
        unknown_presence = component_vocabulary.require_component_presence("unknown")
        asserted = [
            name
            for name, value in (
                ("base", self.base),
                ("cuota", self.cuota),
                ("recargo", self.recargo),
            )
            if component_vocabulary.require_component_presence(value) != unknown_presence
        ]
        if asserted:
            raise IvaValidationError(
                f"{label}: pair does not arise, so it cannot assert {sorted(asserted)!r}; "
                "declare every component UNKNOWN",
            )
        if component_vocabulary.require_retencion_expectation(self.retencion) != (
            component_vocabulary.require_retencion_expectation("unknown")
        ):
            raise IvaValidationError(
                f"{label}: pair does not arise, so its retención expectation must be UNKNOWN",
            )
        if not self.retencion_note.strip():
            raise IvaValidationError(
                f"{label}: a non-arising pair must name the category that is this kind's counterpart",
            )


ComponentCatalogue = Mapping[tuple[IvaCategory, InvoiceKind], IvaCategoryComponents]

CategoryProjectionName = Literal[
    "cuota_less_m303",
    "m303_base_out_of_scope",
    "evidence_exempt",
    "no_printed_tax",
]

_CATEGORY_PROJECTION_NAMES = frozenset(
    {
        "cuota_less_m303",
        "m303_base_out_of_scope",
        "evidence_exempt",
        "no_printed_tax",
    },
)

_CUOTA_SETTLEMENT_ORDER_KEY = "cuota_settlement.order"
_CUOTA_SETTLEMENT_NO_TOKEN_KEY = "cuota_settlement.no_settlement"
_CUOTA_SETTLEMENT_PREFIX = "cuota_settlement."
_COMPONENT_PRESENCE_ORDER_KEY = "component_presence.order"
_RETENCION_EXPECTATION_ORDER_KEY = "retencion_expectation.order"
_RETENCION_ROLE_ORDER_KEY = "retencion_role.order"
_KIND_APPLICABILITY_ORDER_KEY = "kind_applicability.order"


def _resolve_component_catalogue_entries(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority,
) -> dict[str, str]:
    """Resolve and type-check the raw 0084 mapping entries once."""
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="iva-category-component-catalogue",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise IvaValidationError("IVA component catalogue must resolve as a mapping fact")

    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise IvaValidationError("IVA component mapping entries must be string-to-string")
        if entry.key in entries:
            raise IvaValidationError(f"duplicate IVA component mapping key {entry.key!r}")
        entries[entry.key] = entry.value
    return entries


def _cuota_settlement_catalogue_from_entries(
    entries: Mapping[str, str],
) -> IvaCuotaSettlementCatalogue:
    """Project the explicit cuota-settlement membership in fact 0084."""
    order_text = entries.get(_CUOTA_SETTLEMENT_ORDER_KEY)
    if order_text is None or not order_text.strip():
        raise IvaValidationError(
            f"IVA component mapping is missing {_CUOTA_SETTLEMENT_ORDER_KEY!r}",
        )
    raw_tokens = tuple(token.strip() for token in order_text.split(",") if token.strip())
    if not raw_tokens or len(set(raw_tokens)) != len(raw_tokens):
        raise IvaValidationError("IVA cuota-settlement membership must contain unique non-empty tokens")

    no_settlement_value = entries.get(_CUOTA_SETTLEMENT_NO_TOKEN_KEY)
    if no_settlement_value is None or not no_settlement_value.strip():
        raise IvaValidationError(
            f"IVA component mapping is missing {_CUOTA_SETTLEMENT_NO_TOKEN_KEY!r}",
        )
    no_settlement_token = IvaCuotaSettlement(no_settlement_value.strip())

    definitions: list[IvaCuotaSettlementDefinition] = []
    for raw_token in raw_tokens:
        token = IvaCuotaSettlement(raw_token)
        prefix = f"{_CUOTA_SETTLEMENT_PREFIX}{raw_token}"
        declared_value = entries.get(f"{prefix}.value")
        if declared_value is None or not declared_value.strip():
            raise IvaValidationError(f"IVA component mapping is missing {prefix + '.value'!r}")
        if declared_value.strip() != raw_token:
            raise IvaValidationError(
                f"IVA cuota-settlement token {raw_token!r} declares mismatched value {declared_value!r}",
            )
        description = entries.get(f"{prefix}.description")
        legal_ref = entries.get(f"{prefix}.legal_ref")
        if description is None or not description.strip() or legal_ref is None or not legal_ref.strip():
            raise IvaValidationError(f"IVA component mapping is missing semantics for {raw_token!r}")
        definitions.append(
            IvaCuotaSettlementDefinition(
                token=token,
                description=description.strip(),
                legal_ref=legal_ref.strip(),
            ),
        )

    catalogue = IvaCuotaSettlementCatalogue(
        definitions=tuple(definitions),
        no_settlement_token=no_settlement_token,
    )
    if no_settlement_token not in catalogue.all_settlements:
        raise IvaValidationError(
            "IVA component mapping no-settlement token is not declared in cuota-settlement order",
        )
    return catalogue


@lru_cache(maxsize=64)
def _bundled_cuota_settlement_catalogue(effective_date: date) -> IvaCuotaSettlementCatalogue:
    """Cache the immutable 0084 cuota-settlement projection."""
    from ..calculations.registry.authority import bundled_authority

    entries = _resolve_component_catalogue_entries(
        effective_date=effective_date,
        authority=bundled_authority(),
    )
    return _cuota_settlement_catalogue_from_entries(entries)


def registry_cuota_settlement_catalogue(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> IvaCuotaSettlementCatalogue:
    """Resolve the explicit cuota-settlement vocabulary from published 0084."""
    selected_date = date.today() if effective_date is None else effective_date
    if authority is None:
        return _bundled_cuota_settlement_catalogue(selected_date)
    entries = _resolve_component_catalogue_entries(
        effective_date=selected_date,
        authority=authority,
    )
    return _cuota_settlement_catalogue_from_entries(entries)


def _ordered_component_rows(entries: Mapping[str, str]) -> tuple[str, ...]:
    """Return the validated row-key order declared by fact 0084."""
    order_text = entries.get("catalogue_order")
    if order_text is None or not order_text.strip():
        raise IvaValidationError("IVA component mapping is missing 'catalogue_order'")
    ordered_keys = tuple(token.strip() for token in order_text.split(",") if token.strip())
    if len(set(ordered_keys)) != len(ordered_keys):
        raise IvaValidationError("IVA component catalogue order contains duplicate rows")
    return ordered_keys


def _component_axis_membership(
    entries: Mapping[str, str],
    *,
    key: str,
    token_type: type[_IvaRegistryToken],
    observed: set[str],
    label: str,
) -> frozenset[_IvaRegistryToken]:
    order_text = entries.get(key)
    if order_text is None or not order_text.strip():
        raise IvaValidationError(f"IVA component mapping is missing {key!r}")
    raw_tokens = tuple(token.strip() for token in order_text.split(",") if token.strip())
    if not raw_tokens or len(raw_tokens) != len(set(raw_tokens)):
        raise IvaValidationError(f"{label} membership must contain unique non-empty tokens")
    if not observed.issubset(set(raw_tokens)):
        missing = sorted(observed - set(raw_tokens))
        raise IvaValidationError(f"{label} rows use undeclared tokens {missing!r}")
    return frozenset(token_type._from_registry(raw_token) for raw_token in raw_tokens)


def _component_vocabulary_from_entries(entries: Mapping[str, str]) -> IvaComponentVocabulary:
    """Project the four explicit component-axis memberships from fact 0084."""
    observed: dict[str, set[str]] = {
        "applicability": set(),
        "retencion_role": set(),
        "base": set(),
        "cuota": set(),
        "recargo": set(),
        "retencion": set(),
    }
    for row_key in _ordered_component_rows(entries):
        raw_row = entries.get(f"row.{row_key}")
        if raw_row is None:
            raise IvaValidationError(f"IVA component mapping is missing row {row_key!r}")
        try:
            decoded = json.loads(raw_row)
        except json.JSONDecodeError as exc:
            raise IvaValidationError(f"IVA component row {row_key!r} is not valid JSON") from exc
        if not isinstance(decoded, Mapping):
            raise IvaValidationError(f"IVA component row {row_key!r} must decode as an object")
        for field in observed:
            value = decoded.get(field)
            if not isinstance(value, str) or not value.strip():
                raise IvaValidationError(f"IVA component row {row_key!r} is missing {field!r}")
            observed[field].add(value.strip())
    return IvaComponentVocabulary(
        component_presence=frozenset(
            _component_axis_membership(
                entries,
                key=_COMPONENT_PRESENCE_ORDER_KEY,
                token_type=IvaComponentPresence,
                observed=observed["base"] | observed["cuota"] | observed["recargo"],
                label="IVA component-presence",
            ),
        ),
        retencion_expectation=frozenset(
            _component_axis_membership(
                entries,
                key=_RETENCION_EXPECTATION_ORDER_KEY,
                token_type=IvaRetencionExpectation,
                observed=observed["retencion"],
                label="IVA retención-expectation",
            ),
        ),
        retencion_role=frozenset(
            _component_axis_membership(
                entries,
                key=_RETENCION_ROLE_ORDER_KEY,
                token_type=IvaRetencionRole,
                observed=observed["retencion_role"],
                label="IVA retención-role",
            ),
        ),
        kind_applicability=frozenset(
            _component_axis_membership(
                entries,
                key=_KIND_APPLICABILITY_ORDER_KEY,
                token_type=IvaKindApplicability,
                observed=observed["applicability"],
                label="IVA kind-applicability",
            ),
        ),
    )


@lru_cache(maxsize=64)
def _bundled_component_vocabulary(effective_date: date) -> IvaComponentVocabulary:
    """Cache the immutable 0084 component-axis vocabulary."""
    from ..calculations.registry.authority import bundled_authority

    entries = _resolve_component_catalogue_entries(
        effective_date=effective_date,
        authority=bundled_authority(),
    )
    return _component_vocabulary_from_entries(entries)


def registry_component_vocabulary(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> IvaComponentVocabulary:
    """Resolve the four typed component-axis memberships from fact 0084."""
    selected_date = date.today() if effective_date is None else effective_date
    if authority is None:
        return _bundled_component_vocabulary(selected_date)
    entries = _resolve_component_catalogue_entries(
        effective_date=selected_date,
        authority=authority,
    )
    return _component_vocabulary_from_entries(entries)


def registry_component_presence_token(
    value: str,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> IvaComponentPresence:
    return registry_component_vocabulary(
        effective_date=effective_date,
        authority=authority,
    ).require_component_presence(value)


def registry_retencion_expectation_token(
    value: str,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> IvaRetencionExpectation:
    return registry_component_vocabulary(
        effective_date=effective_date,
        authority=authority,
    ).require_retencion_expectation(value)


def registry_retencion_role_token(
    value: str,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> IvaRetencionRole:
    return registry_component_vocabulary(
        effective_date=effective_date,
        authority=authority,
    ).require_retencion_role(value)


def registry_kind_applicability_token(
    value: str,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> IvaKindApplicability:
    return registry_component_vocabulary(
        effective_date=effective_date,
        authority=authority,
    ).require_kind_applicability(value)


def _category_projection_from_entries(
    entries: Mapping[str, str],
    projection: CategoryProjectionName,
    category_catalogue: IvaCategoryCatalogue,
) -> frozenset[IvaCategory]:
    """Project one explicit category membership mapping from fact 0084."""
    if projection not in _CATEGORY_PROJECTION_NAMES:
        raise IvaValidationError(f"unknown IVA category projection {projection!r}")
    raw_members = entries.get(f"category_projection.{projection}")
    if raw_members is None or not raw_members.strip():
        raise IvaValidationError(
            f"IVA component catalogue is missing category projection {projection!r}",
        )
    member_values = tuple(token.strip() for token in raw_members.split(","))
    if any(not token for token in member_values):
        raise IvaValidationError(f"IVA category projection {projection!r} contains an empty member")
    if len(set(member_values)) != len(member_values):
        raise IvaValidationError(f"IVA category projection {projection!r} contains duplicate members")
    try:
        members = frozenset(category_catalogue.require(token) for token in member_values)
    except ValueError as exc:
        raise IvaValidationError(
            f"IVA category projection {projection!r} contains an unknown category",
        ) from exc

    declared_categories: set[str] = set()
    for row_key in _ordered_component_rows(entries):
        category_text, separator, kind_text = row_key.partition("|")
        if not separator or not category_text or not kind_text:
            raise IvaValidationError(f"invalid IVA component catalogue row key {row_key!r}")
        declared_categories.add(category_text)
    undeclared = sorted(member.value for member in members if member.value not in declared_categories)
    if undeclared:
        raise IvaValidationError(
            f"IVA category projection {projection!r} names categories without component rows: {undeclared!r}",
        )
    return members


@lru_cache(maxsize=64)
def _bundled_category_projection(
    effective_date: date,
    projection: CategoryProjectionName,
) -> frozenset[IvaCategory]:
    """Cache one immutable category projection from the bundled authority."""
    from ..calculations.registry.authority import bundled_authority

    entries = _resolve_component_catalogue_entries(
        effective_date=effective_date,
        authority=bundled_authority(),
    )
    return _category_projection_from_entries(
        entries,
        projection,
        resolve_iva_category_catalogue(effective_date=effective_date, authority=bundled_authority()),
    )


def registry_category_projection(
    projection: CategoryProjectionName,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> frozenset[IvaCategory]:
    """Resolve an explicit category membership projection from published 0084.

    There is intentionally no derived or Python-owned fallback. Missing,
    malformed, duplicate, or stale projection entries fail through
    :class:`IvaValidationError`.
    """
    selected_date = date.today() if effective_date is None else effective_date
    if authority is None:
        return _bundled_category_projection(selected_date, projection)
    entries = _resolve_component_catalogue_entries(
        effective_date=selected_date,
        authority=authority,
    )
    return _category_projection_from_entries(
        entries,
        projection,
        resolve_iva_category_catalogue(effective_date=selected_date, authority=authority),
    )


def _project_component_catalogue(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority,
) -> ComponentCatalogue:
    """Project the selected registry mapping fact into typed component rows."""
    entries = _resolve_component_catalogue_entries(effective_date=effective_date, authority=authority)
    category_catalogue = resolve_iva_category_catalogue(effective_date=effective_date, authority=authority)
    ordered_keys = _ordered_component_rows(entries)
    component_vocabulary = _component_vocabulary_from_entries(entries)
    cuota_settlement_catalogue = _cuota_settlement_catalogue_from_entries(entries)

    # Keep the conversion helper as the narrow mechanical boundary. The helper
    # is imported lazily because it imports this module for the row model.
    from ._component_rows import component_row_from_registry

    projected: dict[tuple[IvaCategory, InvoiceKind], IvaCategoryComponents] = {}
    for row_key in ordered_keys:
        category_text, separator, kind_text = row_key.partition("|")
        if not separator or not category_text or not kind_text:
            raise IvaValidationError(f"invalid IVA component catalogue row key {row_key!r}")
        try:
            category = category_catalogue.require(category_text)
            kind = InvoiceKind(kind_text)
        except ValueError as exc:
            raise IvaValidationError(f"unknown IVA component catalogue row key {row_key!r}") from exc
        raw_row = entries.get(f"row.{row_key}")
        if raw_row is None:
            raise IvaValidationError(f"IVA component mapping is missing row {row_key!r}")
        try:
            decoded: Any = json.loads(raw_row)
        except json.JSONDecodeError as exc:
            raise IvaValidationError(f"IVA component row {row_key!r} is not valid JSON") from exc
        if not isinstance(decoded, Mapping):
            raise IvaValidationError(f"IVA component row {row_key!r} must decode as an object")
        if "cuota_settlement" not in decoded:
            raise IvaValidationError(f"IVA component row {row_key!r} is missing cuota settlement")
        decoded = dict(decoded)
        decoded.pop("label", None)
        decoded.pop("fact_ids", None)
        decoded["category"] = category
        decoded["kind"] = kind
        for grounding_field in ("cuota_grounding", "recargo_grounding", "retencion_grounding"):
            raw_grounding = decoded.get(grounding_field)
            try:
                decoded[grounding_field] = IvaGroundingConfidence(raw_grounding)
            except (TypeError, ValueError) as exc:
                raise IvaValidationError(
                    f"IVA component row {row_key!r} has invalid {grounding_field}",
                ) from exc
        for reference_field in ("legal_refs", "pending_legal_refs"):
            raw_references = decoded.get(reference_field, ())
            if not isinstance(raw_references, list) or any(not isinstance(item, str) for item in raw_references):
                raise IvaValidationError(
                    f"IVA component row {row_key!r} has invalid {reference_field}",
                )
            decoded[reference_field] = tuple(raw_references)
        decoded["applicability"] = component_vocabulary.require_kind_applicability(decoded["applicability"])
        decoded["retencion_role"] = component_vocabulary.require_retencion_role(decoded["retencion_role"])
        decoded["base"] = component_vocabulary.require_component_presence(decoded["base"])
        decoded["cuota"] = component_vocabulary.require_component_presence(decoded["cuota"])
        decoded["recargo"] = component_vocabulary.require_component_presence(decoded["recargo"])
        decoded["retencion"] = component_vocabulary.require_retencion_expectation(decoded["retencion"])
        decoded["cuota_settlement"] = cuota_settlement_catalogue.require(decoded["cuota_settlement"])
        row = component_row_from_registry(
            decoded,
            cuota_settlement_no_token=cuota_settlement_catalogue.no_settlement_token,
            component_vocabulary=component_vocabulary,
        )
        if row.category != category or row.kind is not kind:
            raise IvaValidationError(
                f"IVA component row {row_key!r} disagrees with its catalogue key",
            )
        projected[(category, kind)] = row
    return MappingProxyType(projected)


@lru_cache(maxsize=16)
def _bundled_component_catalogue(effective_date: date) -> ComponentCatalogue:
    """Cache the immutable bundled projection by its legal effective date."""
    from ..calculations.registry.authority import bundled_authority

    return _project_component_catalogue(effective_date=effective_date, authority=bundled_authority())


def registry_component_catalogue(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> ComponentCatalogue:
    """Return the Axis-A catalogue projected by the validated registry authority.

    Production callers may omit both arguments and receive the current bundled
    filing-period projection. Tests and review tooling can pass an explicit
    effective date or an isolated validated authority to inspect another
    governed projection without introducing a second source of row data.
    """
    selected_date = date.today() if effective_date is None else effective_date
    if authority is None:
        return _bundled_component_catalogue(selected_date)
    return _project_component_catalogue(effective_date=selected_date, authority=authority)


def category_components(
    category: IvaCategory,
    kind: InvoiceKind,
    *,
    component_catalogue: ComponentCatalogue | None = None,
) -> IvaCategoryComponents:
    """Return a registry-projected Axis-A row for ``category`` on ``kind``.

    ``kind`` is required, deliberately. A category-only accessor over a
    pair-keyed table would have to pick one of the two rows for any category
    whose sides differ, and would return the wrong one silently on a filing
    path — worse than the gap this key closes. Callers hold an invoice, so
    they hold its kind.

    Args:
        category: The declared IVA situation of the row being decomposed.
        kind: Whether the taxpayer issued or received the invoice.

    Returns:
        The :class:`IvaCategoryComponents` row for the pair. A row whose
        ``applicability`` is
        the registry's ``does_not_arise`` applicability token is a real answer
        — the combination is not an operation — not a lookup failure.

    Raises:
        IvaValidationError: If no registry catalogue was supplied or it has
            no row for the pair.
    """
    if component_catalogue is None:
        component_catalogue = registry_component_catalogue()
    try:
        return component_catalogue[(category, kind)]
    except KeyError as exc:  # pragma: no cover - guarded by the completeness gate
        raise IvaValidationError(
            f"no Axis-A component expectations declared for IVA category "
            f"{category.value!r} on a {kind.value!r} invoice",
        ) from exc


def cuota_less_m303_categories_from_table(
    component_catalogue: ComponentCatalogue | None = None,
) -> frozenset[IvaCategory]:
    """Return the explicit cuota-less projection declared by fact 0084.

    ``component_catalogue`` remains an accepted argument for callers that
    already hold a projected catalogue, but the membership itself is never
    inferred from row semantics: the canonical ``category_projection`` entry
    is resolved from the published authority and missing data fails closed.
    """
    del component_catalogue
    return registry_category_projection("cuota_less_m303")


def category_bears_taxable_base(
    category: IvaCategory,
    kind: InvoiceKind,
    *,
    component_catalogue: ComponentCatalogue | None = None,
) -> bool:
    """Return ``True`` when a declared taxable base is legally required.

    Cuota-less is not substrate-less: an entrega intracomunitaria exenta and an
    IVA-exempt professional service both return ``True`` here even though they
    carry no cuota, which is why a base-less row in either category is
    ungrounded rather than legitimately empty.

    A non-arising pair returns ``False``: there is no operation to require a
    base of, and reporting a missing base on an impossible combination would
    be a second, misleading defect on top of the real one.

    Args:
        category: The declared IVA situation.
        kind: Whether the taxpayer issued or received the invoice.

    Returns:
        ``True`` when the pair requires a taxable base.
    """
    row = category_components(
        category,
        kind,
        component_catalogue=component_catalogue,
    )
    return row.base == registry_component_presence_token("required")


def category_cuota_is_zero_by_law(
    category: IvaCategory,
    kind: InvoiceKind,
    *,
    component_catalogue: ComponentCatalogue | None = None,
) -> bool:
    """Return ``True`` when the pair's IVA cuota is structurally zero.

    Consumed by the retención-inference precondition: a declared-exempt invoice
    has a *determinable* cuota (zero), so it can qualify for bounded inference
    even though no explicit ``iva_amount`` was recorded.

    The kind matters here rather than being incidental. A domestic
    reverse-charge invoice the taxpayer ISSUED carries no cuota (the recipient
    self-assesses), while one they RECEIVED carries a self-assessed cuota that
    is emphatically not zero.

    Args:
        category: The declared IVA situation.
        kind: Whether the taxpayer issued or received the invoice.

    Returns:
        ``True`` when the cuota is zero by law for this pair.
    """
    row = category_components(
        category,
        kind,
        component_catalogue=component_catalogue,
    )
    return row.cuota == registry_component_presence_token("zero_by_law")


__all__ = [
    "CategoryProjectionName",
    "ComponentCatalogue",
    "IvaCategoryComponents",
    "IvaComponentPresence",
    "IvaComponentVocabulary",
    "IvaCuotaSettlement",
    "IvaCuotaSettlementCatalogue",
    "IvaCuotaSettlementDefinition",
    "IvaGroundingConfidence",
    "IvaKindApplicability",
    "IvaRetencionExpectation",
    "IvaRetencionRole",
    "category_bears_taxable_base",
    "category_components",
    "category_cuota_is_zero_by_law",
    "cuota_less_m303_categories_from_table",
    "registry_category_projection",
    "registry_component_catalogue",
    "registry_component_presence_token",
    "registry_component_vocabulary",
    "registry_cuota_settlement_catalogue",
    "registry_kind_applicability_token",
    "registry_retencion_expectation_token",
    "registry_retencion_role_token",
]
