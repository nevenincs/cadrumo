"""Axis-A component-expectation table: which components an IVA category has.

The engine previously carried no declared answer to "which components does an
operation in this IVA category even *have*?", so every decomposition site
re-derived it inline. This module is that declared answer: one row per
:class:`~domain.iva.IvaCategory` stating whether a taxable base, an IVA cuota,
a recargo de equivalencia, and an IRPF retención are required, optional, zero
by law, or undeterminable from the category alone — each row carrying its
binding ``legal_refs``.

The table is the *component* axis only. It deliberately says nothing about
which modelo family a row feeds or under which regime it is filed: that is the
per-family (Axis-B) scope axis owned by the ledger binding families, and
collapsing the two would re-couple regulatory-distinct bindings.

**The table is not a third inline category set.** The cuota-less predicate is
*derived* from the ``cuota``/``cuota_settlement`` columns and asserted equal to
the canonical :data:`~domain.iva.CUOTA_LESS_M303_IVA_CATEGORIES` frozenset by
:mod:`domain.iva.tests.test_component_expectations`, so the two cannot drift.
Read the frozenset through :func:`cuota_less_m303_categories_from_table` when
you want to see that derivation explicitly.

Cuota-less is **not** substrate-less: an entrega intracomunitaria exenta or an
exportación carries a real taxable base that feeds base-only casillas, and an
IVA-exempt professional service still bears an IRPF retención. Both are
declared here as ``base = REQUIRED`` with a zero cuota, which is precisely the
distinction a bare cash amount cannot make.

Grounding honesty
-----------------
Every row declares, per component, how well its expectation is grounded
(:class:`IvaGroundingConfidence`). Rows whose expectation was verified against
live BOE text but whose provision is **not yet in the bundled legal catalogue**
are marked :attr:`IvaGroundingConfidence.LIVE_SOURCE_ONLY` and name that
provision in :attr:`IvaCategoryComponents.pending_legal_refs` rather than in
:attr:`IvaCategoryComponents.legal_refs`. The gate in the test module asserts
that every ``legal_refs`` id resolves in the bundled catalogue and every
``pending_legal_refs`` id does *not*, so bundling a pending provision turns the
gate red until the author promotes the row — the marker retires itself instead
of rotting.

See Also:
    :mod:`domain.iva.schema`
        Owns :class:`~domain.iva.IvaCategory` and the canonical
        :data:`~domain.iva.CUOTA_LESS_M303_IVA_CATEGORIES` /
        :data:`~domain.iva.EVIDENCE_EXEMPT_IVA_CATEGORIES` frozensets this
        table is cross-checked against.
    :mod:`domain.iva.recargo_equivalencia`
        Registry-backed LIVA art. 161 recargo rates; this table declares
        *whether* a recargo may exist, that module declares *how much*.
"""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from pydantic import Field, model_validator

from .classification import InvoiceKind
from .errors import IvaValidationError
from .schema import (
    CUOTA_LESS_M303_IVA_CATEGORIES,
    IvaCategory,
    IvaStrictFrozen,
    _RegistryLegalRef,  # pyright: ignore[reportPrivateUsage] -- intra-package reuse of this package's own constrained legal-ref alias
)

if TYPE_CHECKING:
    from collections.abc import Mapping


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
        if len(set(self.legal_refs)) != len(self.legal_refs):
            raise IvaValidationError(f"{label}: legal_refs must be unique")
        if len(set(self.pending_legal_refs)) != len(self.pending_legal_refs):
            raise IvaValidationError(f"{label}: pending_legal_refs must be unique")
        if set(self.legal_refs) & set(self.pending_legal_refs):
            raise IvaValidationError(
                f"{label}: a legal ref cannot be both bundled and pending",
            )
        if (self.cuota is IvaComponentPresence.ZERO_BY_LAW) != (self.cuota_settlement is IvaCuotaSettlement.NONE):
            raise IvaValidationError(
                f"{label}: a zero-by-law cuota must declare settlement NONE, and vice versa",
            )
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
        return self

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


from ._component_rows import _COMPONENT_ROWS  # noqa: E402

IVA_CATEGORY_COMPONENTS: Final[Mapping[tuple[IvaCategory, InvoiceKind], IvaCategoryComponents]] = MappingProxyType(
    dict(_COMPONENT_ROWS),
)
"""Axis-A component-expectation table, one row per (category, kind) PAIR.

Keyed on the pair because the retención role inverts with direction and
several categories are one-directional by law; category alone cannot express
either. Completeness is enforced by
:mod:`domain.iva.tests.test_component_expectations`, which requires every
category AND every pair to be declared, so neither a new category nor a new
invoice kind can ship undeclared.
"""


def category_components(category: IvaCategory, kind: InvoiceKind) -> IvaCategoryComponents:
    """Return the Axis-A component expectations for ``category`` on ``kind``.

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
        IvaValidationError: If the table has no row for the pair. The
            completeness gate makes this unreachable for shipped enum members;
            it fires only while a newly added member is still undeclared.
    """
    try:
        return IVA_CATEGORY_COMPONENTS[(category, kind)]
    except KeyError as exc:  # pragma: no cover - guarded by the completeness gate
        raise IvaValidationError(
            f"no Axis-A component expectations declared for IVA category "
            f"{category.value!r} on a {kind.value!r} invoice",
        ) from exc


def cuota_less_m303_categories_from_table() -> frozenset[IvaCategory]:
    """Derive the cuota-less category set from the component table.

    A category bears no Modelo 303 general cuota when either its cuota is zero
    by law or its cuota is settled through a special regime rather than the
    general 303 bindings.

    This is the derivation that keeps the table and
    :data:`~domain.iva.CUOTA_LESS_M303_IVA_CATEGORIES` from drifting: the two
    are asserted equal by the test module, so the table is a second *view* of
    one fact rather than a second declaration of it.

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
    arising: dict[IvaCategory, list[IvaCategoryComponents]] = {}
    for (category, _kind), row in IVA_CATEGORY_COMPONENTS.items():
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


def category_bears_taxable_base(category: IvaCategory, kind: InvoiceKind) -> bool:
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
    return category_components(category, kind).base is IvaComponentPresence.REQUIRED


def category_cuota_is_zero_by_law(category: IvaCategory, kind: InvoiceKind) -> bool:
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
    return category_components(category, kind).cuota is IvaComponentPresence.ZERO_BY_LAW


# Import-time coherence check. The table and the canonical frozenset describe
# one fact; a divergence here is a defect that must never reach a caller, and
# the test module reports it with a readable diff.
if cuota_less_m303_categories_from_table() != CUOTA_LESS_M303_IVA_CATEGORIES:  # pragma: no cover
    raise IvaValidationError(
        "Axis-A component table diverges from CUOTA_LESS_M303_IVA_CATEGORIES; "
        "the cuota-less set has two disagreeing declarations",
    )


__all__ = [
    "IVA_CATEGORY_COMPONENTS",
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
]
