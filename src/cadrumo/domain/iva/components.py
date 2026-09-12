"""Typed IVA component models and the registry projection boundary.

Concrete category/component rows are canonical registry data.  This module
retains only the enum and validation models, generic component calculations,
and the explicit boundary that accepts a registry-projected catalogue.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from functools import lru_cache
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from pydantic import Field, model_validator

from ..calculations.registry.authority import bundled_authority
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
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


class IvaComponentPresence(StrEnum):
    """Whether an invoice component exists for a given :class:`~domain.iva.IvaCategory`.

    The values grade *legal expectation*, not data availability: ``REQUIRED``
    means the law produces the component for this category, so a row missing it
    is ungrounded rather than merely sparse.
    """

    REQUIRED = "required"
    """The component exists by law; a row without it is not calculation-grounded."""

    OPTIONAL = "optional"
    """The component may legitimately be present or absent on this category."""

    ZERO_BY_LAW = "zero_by_law"
    """The component is structurally zero; a non-zero value is a defect."""

    UNKNOWN = "unknown"
    """Not determinable from the category alone — the category declares nothing."""


class IvaRetencionExpectation(StrEnum):
    """Whether an IRPF retención is expected on an operation in this category.

    Retención is an IRPF settlement-side deduction, not an IVA price component,
    so it gets its own graded axis rather than reusing
    :class:`IvaComponentPresence`: the IVA category never *requires* a
    retención, it only makes one more or less likely by fixing the payer's
    residency and the operation's nature.
    """

    EXPECTED = "expected"
    """The withholding obligation normally applies to this category."""

    POSSIBLE = "possible"
    """Applies only when further, non-category facts hold (the rendimiento is
    profesional and the payer is an obliged retenedor)."""

    NOT_EXPECTED = "not_expected"
    """The obligation normally does not apply. A default, not a prohibition —
    see the row's ``retencion_note`` for the carve-outs."""

    UNKNOWN = "unknown"
    """Not determinable from the category alone."""


class IvaRetencionRole(StrEnum):
    """Whose money a retención on this invoice is, and which way it flows.

    The retención amount is the same arithmetic on both kinds of invoice and
    means opposite things. On an ISSUED invoice the payer withholds from what
    they owe the taxpayer and remits it to AEAT on the taxpayer's account: the
    taxpayer is the *retenido* and the amount is a CREDIT, deducted from the
    pago fraccionado (RIRPF art. 110.3.a) and from the annual cuota. On a
    RECEIVED invoice from a resident professional the taxpayer is the obligated
    *retenedor*: they pay the supplier net, and the withheld amount is a
    LIABILITY they owe AEAT through the retenciones modelos.

    Reading the amount without the role inverts a credit into a debt. The role
    is therefore declared per row and validated against the row's kind, so it
    can be read directly but cannot be authored wrong.
    """

    TAXPAYER_CREDIT = "taxpayer_credit"
    """Withheld from the taxpayer by the payer; deductible against their own tax."""

    TAXPAYER_LIABILITY = "taxpayer_liability"
    """Withheld by the taxpayer from a supplier; owed onward to AEAT."""

    NONE = "none"
    """No retención is expected on this (category, kind), so no role arises."""

    UNKNOWN = "unknown"
    """Not determinable — the row's retención expectation is itself unknown."""


class IvaKindApplicability(StrEnum):
    """Whether a (category, kind) pair describes an operation that can occur.

    Several categories are directional by law: an entrega intracomunitaria
    exenta (LIVA art. 25) is something the taxpayer *supplies*, and its
    received-side counterpart is a different category entirely
    (:attr:`~domain.iva.IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE`).

    A pair that cannot occur is declared here rather than omitted from the
    table. Omission would make the completeness gate satisfiable by narrowing
    what counts as a valid pair — the gameable form — and would leave a caller
    holding such an invoice with a lookup failure instead of an answer stating
    that the combination is not a real operation.
    """

    ARISES = "arises"
    """The pair describes an operation that occurs; the component columns apply."""

    DOES_NOT_ARISE = "does_not_arise"
    """The category is directional and this kind is not its side. Components are
    declared UNKNOWN because there is no operation to describe, and the row's
    note names the category that *is* this kind's counterpart."""


class IvaCuotaSettlement(StrEnum):
    """Who settles the IVA cuota, and where.

    Two categories can both carry a cuota and still route to entirely different
    casillas depending on who is liable, so settlement is a separate column
    from presence.
    """

    NONE = "none"
    """No cuota arises."""

    REPERCUTIDA = "repercutida"
    """The counterparty charges the cuota on the invoice (LIVA art. 88)."""

    INVERSION_SUJETO_PASIVO = "inversion_sujeto_pasivo"
    """The recipient self-assesses the cuota (LIVA art. 84.uno.2), declaring it
    as devengada and, where deducible, as soportada."""

    ADUANA = "aduana"
    """The cuota is settled at customs on importación (LIVA art. 17)."""

    REGIMEN_ESPECIAL = "regimen_especial"
    """The cuota is settled through a special regime rather than the general
    Modelo 303 cuota bindings."""

    UNKNOWN = "unknown"
    """Not determinable from the category alone."""


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
    def _validate_row(self) -> IvaCategoryComponents:
        """Enforce the internal coherence the table's readers rely on."""
        label = f"IvaCategoryComponents[{self.category.value}/{self.kind.value}]"
        self._validate_retencion_role(label)
        self._validate_applicability(label)
        self._validate_reference_integrity(label)
        self._validate_cuota_settlement(label)
        self._validate_retencion_notes(label)
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

    def _validate_cuota_settlement(self, label: str) -> None:
        """Refuse a cuota whose declared settlement disagrees with its presence."""
        if (self.cuota is IvaComponentPresence.ZERO_BY_LAW) != (self.cuota_settlement is IvaCuotaSettlement.NONE):
            raise IvaValidationError(
                f"{label}: a zero-by-law cuota must declare settlement NONE, and vice versa",
            )

    def _validate_retencion_notes(self, label: str) -> None:
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
        if self.retencion is IvaRetencionExpectation.NOT_EXPECTED and not self.retencion_note.strip():
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

    def _validate_retencion_role(self, label: str) -> None:
        """Refuse a retención role that contradicts the row's kind or expectation.

        The role is a function of the kind whenever a retención can arise at
        all: an ISSUED invoice is withheld FROM the taxpayer (credit), a
        RECEIVED one is withheld BY them (liability). Declaring it explicitly
        keeps the table readable; checking it here means the declaration cannot
        be wrong, so a consumer may trust the column without re-deriving it.
        """
        expected_by_kind = {
            InvoiceKind.ISSUED: IvaRetencionRole.TAXPAYER_CREDIT,
            InvoiceKind.RECEIVED: IvaRetencionRole.TAXPAYER_LIABILITY,
        }[self.kind]
        required = {
            IvaRetencionExpectation.EXPECTED: expected_by_kind,
            IvaRetencionExpectation.POSSIBLE: expected_by_kind,
            IvaRetencionExpectation.NOT_EXPECTED: IvaRetencionRole.NONE,
            IvaRetencionExpectation.UNKNOWN: IvaRetencionRole.UNKNOWN,
        }[self.retencion]
        if self.retencion_role is not required:
            raise IvaValidationError(
                f"{label}: retención expectation {self.retencion.value!r} on a "
                f"{self.kind.value!r} invoice requires role {required.value!r}, "
                f"got {self.retencion_role.value!r}",
            )

    def _validate_applicability(self, label: str) -> None:
        """Refuse a non-arising row that still asserts component expectations.

        A pair that cannot occur has nothing to describe, so asserting a
        required base or a settled cuota on it would be a claim about an
        operation that does not exist. The note is mandatory because the only
        useful thing such a row carries is which category IS this kind's
        counterpart.
        """
        if self.applicability is not IvaKindApplicability.DOES_NOT_ARISE:
            return
        asserted = [
            name
            for name, value in (
                ("base", self.base),
                ("cuota", self.cuota),
                ("recargo", self.recargo),
            )
            if value is not IvaComponentPresence.UNKNOWN
        ]
        if asserted:
            raise IvaValidationError(
                f"{label}: pair does not arise, so it cannot assert {sorted(asserted)!r}; "
                "declare every component UNKNOWN",
            )
        if self.retencion is not IvaRetencionExpectation.UNKNOWN:
            raise IvaValidationError(
                f"{label}: pair does not arise, so its retención expectation must be UNKNOWN",
            )
        if not self.retencion_note.strip():
            raise IvaValidationError(
                f"{label}: a non-arising pair must name the category that is this kind's counterpart",
            )


ComponentCatalogue = Mapping[tuple[IvaCategory, InvoiceKind], IvaCategoryComponents]


def _project_component_catalogue(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority,
) -> ComponentCatalogue:
    """Project the selected registry mapping fact into typed component rows."""
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

    order_text = entries.get("catalogue_order")
    if order_text is None or not order_text.strip():
        raise IvaValidationError("IVA component mapping is missing 'catalogue_order'")
    ordered_keys = tuple(token.strip() for token in order_text.split(",") if token.strip())
    if len(set(ordered_keys)) != len(ordered_keys):
        raise IvaValidationError("IVA component catalogue order contains duplicate rows")

    # Keep the conversion helper as the narrow mechanical boundary. The helper
    # is imported lazily because it imports this module for the row model.
    from ._component_rows import component_row_from_registry

    projected: dict[tuple[IvaCategory, InvoiceKind], IvaCategoryComponents] = {}
    for row_key in ordered_keys:
        category_text, separator, kind_text = row_key.partition("|")
        if not separator or not category_text or not kind_text:
            raise IvaValidationError(f"invalid IVA component catalogue row key {row_key!r}")
        try:
            category = IvaCategory(category_text)
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
        row = component_row_from_registry(decoded)
        if row.category is not category or row.kind is not kind:
            raise IvaValidationError(
                f"IVA component row {row_key!r} disagrees with its catalogue key",
            )
        projected[(category, kind)] = row
    return MappingProxyType(projected)


@lru_cache(maxsize=16)
def _bundled_component_catalogue(effective_date: date) -> ComponentCatalogue:
    """Cache the immutable bundled projection by its legal effective date."""
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
        :attr:`IvaKindApplicability.DOES_NOT_ARISE` is a real answer — the
        combination is not an operation — not a lookup failure.

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
    """Derive the cuota-less category set from a registry component catalogue.

    A category bears no Modelo 303 general cuota when either its cuota is zero
    by law or its cuota is settled through a special regime rather than the
    general 303 bindings.

    A category is cuota-less when NO arising kind of it produces a general-303
    cuota. The quantifier is load-bearing: ``DOMESTIC_REVERSE_CHARGE`` carries
    no cuota on the issued side (the recipient self-assesses) but a real
    self-assessed one on the received side, so an "any kind" reading would
    wrongly declare the whole category cuota-less and silence the advisory on
    the side that does bear one. Non-arising pairs are skipped: they describe
    no operation, so they cannot witness the absence of a cuota.

    Returns:
        The categories that legitimately match no Modelo 303 cuota binding.
    """
    if component_catalogue is None:
        component_catalogue = registry_component_catalogue()
    arising: dict[IvaCategory, list[IvaCategoryComponents]] = {}
    for (category, _kind), row in component_catalogue.items():
        if row.applicability is IvaKindApplicability.ARISES:
            arising.setdefault(category, []).append(row)
    return frozenset(
        category
        for category, rows in arising.items()
        if all(
            row.cuota is IvaComponentPresence.ZERO_BY_LAW or row.cuota_settlement is IvaCuotaSettlement.REGIMEN_ESPECIAL
            for row in rows
        )
    )


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
    return (
        category_components(
            category,
            kind,
            component_catalogue=component_catalogue,
        ).base
        is IvaComponentPresence.REQUIRED
    )


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
    return (
        category_components(
            category,
            kind,
            component_catalogue=component_catalogue,
        ).cuota
        is IvaComponentPresence.ZERO_BY_LAW
    )


__all__ = [
    "ComponentCatalogue",
    "IvaCategoryComponents",
    "IvaComponentPresence",
    "IvaCuotaSettlement",
    "IvaGroundingConfidence",
    "IvaKindApplicability",
    "IvaRetencionExpectation",
    "IvaRetencionRole",
    "category_bears_taxable_base",
    "category_components",
    "category_cuota_is_zero_by_law",
    "cuota_less_m303_categories_from_table",
    "registry_component_catalogue",
]
