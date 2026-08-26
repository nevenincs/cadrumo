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
    :mod:`domain.iva._schema`
        Owns :class:`~domain.iva.IvaCategory` and the canonical
        :data:`~domain.iva.CUOTA_LESS_M303_IVA_CATEGORIES` /
        :data:`~domain.iva.EVIDENCE_EXEMPT_IVA_CATEGORIES` frozensets this
        table is cross-checked against.
    :mod:`domain.iva._recargo_equivalencia`
        Registry-backed LIVA art. 161 recargo rates; this table declares
        *whether* a recargo may exist, that module declares *how much*.
"""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from pydantic import Field, model_validator

from ._classification import InvoiceKind
from ._schema import (
    CUOTA_LESS_M303_IVA_CATEGORIES,
    IvaCategory,
    IvaStrictFrozen,
    _RegistryLegalRef,  # pyright: ignore[reportPrivateUsage] -- intra-package reuse of this package's own constrained legal-ref alias
)
from .errors import IvaValidationError

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


# --------------------------------------------------------------------------- #
# Legal-reference shorthands. Every id below is present in the bundled legal
# catalogue under registry/aeat/legal/. An id read from live authoritative text
# but not yet bundled belongs on a row's pending_legal_refs, never here.
# --------------------------------------------------------------------------- #
_LIVA_NO_SUJECION: Final[str] = "ley-37-1992:art-7"
_LIVA_ADQ_INTRACOM: Final[str] = "ley-37-1992:art-13"
_LIVA_ADQ_INTRACOM_CONCEPTO: Final[str] = "ley-37-1992:art-15"
_LIVA_IMPORTACION: Final[str] = "ley-37-1992:art-17"
_LIVA_EXENCIONES_INTERIORES: Final[str] = "ley-37-1992:art-20"
_LIVA_EXPORTACION: Final[str] = "ley-37-1992:art-21"
_LIVA_EXPORTACION_ASIMILADA: Final[str] = "ley-37-1992:art-22"
_LIVA_ENTREGA_INTRACOM_EXENTA: Final[str] = "ley-37-1992:art-25"
_LIVA_EXENCION_ADQ_INTRACOM: Final[str] = "ley-37-1992:art-26"
_LIVA_LUGAR_SERVICIOS_GENERAL: Final[str] = "ley-37-1992:art-69"
_LIVA_LUGAR_SERVICIOS_ESPECIAL: Final[str] = "ley-37-1992:art-70"
_LIVA_SUJETO_PASIVO: Final[str] = "ley-37-1992:art-84"
_LIVA_TIPO_GENERAL: Final[str] = "ley-37-1992:art-90"
_LIVA_TIPOS_REDUCIDOS: Final[str] = "ley-37-1992:art-91"
_LIVA_SIMPLIFICADO_AMBITO: Final[str] = "ley-37-1992:art-122"
_LIVA_SIMPLIFICADO_CUOTA: Final[str] = "ley-37-1992:art-123"
_LIVA_REAGP_COMPENSACION: Final[str] = "ley-37-1992:art-130"
_LIVA_REAGP_REINTEGRO: Final[str] = "ley-37-1992:art-131"
_LIVA_REAGP_DEDUCCION: Final[str] = "ley-37-1992:art-134"
_LIVA_RECARGO_AMBITO: Final[str] = "ley-37-1992:art-154"
_LIVA_RECARGO_SUJETOS: Final[str] = "ley-37-1992:art-158"
_LIVA_RECARGO_TIPOS: Final[str] = "ley-37-1992:art-161"
_LIRPF_PAGOS_A_CUENTA: Final[str] = "ley-35-2006:art-99"
_RIRPF_RETENCION_ACTIVIDADES: Final[str] = "rd-439-2007:art-95"

#: RIRPF art. 76 (obligados a retener o ingresar a cuenta) fixes WHO bears the
#: withholding obligation: apartado 1.c obliges non-residents operating through
#: a permanent establishment, and apartado 1.d limits the obligation for
#: non-residents *without* a PE to rendimientos del trabajo and to rendimientos
#: that are a deducible gasto for IRNR art. 24.2 rentas.
_RIRPF_OBLIGADOS_A_RETENER: Final[str] = "rd-439-2007:art-76"

_NON_RESIDENT_PAYER_NOTE: Final[str] = (
    "The payer is non-resident by construction for this category, and RIRPF art. 76.1 places a "
    "non-resident payer without a Spanish permanent establishment outside the withholding "
    "obligation except for rendimientos del trabajo and rendimientos that are a deducible gasto "
    "for IRNR art. 24.2 rentas (art. 76.1.d). A payer WITH a Spanish permanent establishment IS "
    "obliged (art. 76.1.c), so this expectation is a default and not a prohibition: a counterparty "
    "falling in either carve-out bears a real retención and the row is wrong for that counterparty."
)

_NON_RESIDENT_SUPPLIER_NOTE: Final[str] = (
    "This is an acquisition category, so the counterparty is a non-resident supplier whose income "
    "is not an IRPF rendimiento; no IRPF retención arises for the Spanish acquirer, and RIRPF "
    "art. 76.1 names no obligation running the other way. Any IRNR withholding obligation is a "
    "separate tax and is out of this table's scope."
)

_AGRICULTURAL_ACTIVITY_NOTE: Final[str] = (
    "Possible rather than expected, and grounded on both sides. RIRPF art. 95.4 sets the "
    "retención on the contraprestación of an actividad agrícola o ganadera at 1 % for engorde de "
    "porcino y avicultura and 2 % otherwise, over the ingresos íntegros satisfechos, and scopes "
    "itself to activities obtaining productos naturales directly from the explotación without "
    "transformation -- the same population LIVA art. 130.Tres describes. It stays POSSIBLE because "
    "the payer must also be an obliged retenedor (LIRPF art. 99), which the IVA category does not "
    "carry, and because a REAGP operation may instead be a servicio accesorio the apartado does "
    "not reach."
)

_ESTIMACION_OBJETIVA_NOTE: Final[str] = (
    "Possible rather than expected, and the gap is in the SCOPE rather than in the rate. RIRPF "
    "art. 95.6.1.º sets the retención on a rendimiento whose actividad económica determines its "
    "rendimiento neto by estimación objetiva at 1 % of the ingresos íntegros satisfechos, and the "
    "bundled excerpt carries it. What the excerpt truncates is art. 95.6.2.º, the list of "
    "activities the apartado reaches, so whether a given taxpayer's activity is one of them cannot "
    "be settled from the bundled text. Two further reasons keep this POSSIBLE rather than "
    "expected: the IVA régimen simplificado and the IRPF estimación objetiva are regimes of "
    "different taxes whose populations merely tend to coincide, so this category does not "
    "establish the IRPF method at all; and an agrícola, ganadera or forestal activity is reached "
    "by apartados 4 and 5 at their own rates instead."
)

_PROFESSIONAL_SERVICE_NOTE: Final[str] = (
    "Possible rather than expected because whether a retención arises depends on facts the IVA "
    "category does not carry: the rendimiento must be the contraprestación of an actividad "
    "profesional (RIRPF art. 95.1) and the payer must be an obliged retenedor (LIRPF art. 99)."
)


def _role_for(kind: InvoiceKind, retencion: IvaRetencionExpectation) -> IvaRetencionRole:
    """Derive the retención role the row must declare.

    Kept as a derivation rather than a per-row literal so the table's ~30 rows
    cannot each get it subtly wrong; the model validator then re-checks the
    result, so the derivation and the declaration are two independent
    statements of the same rule rather than one trusted one.
    """
    if retencion is IvaRetencionExpectation.UNKNOWN:
        return IvaRetencionRole.UNKNOWN
    if retencion is IvaRetencionExpectation.NOT_EXPECTED:
        return IvaRetencionRole.NONE
    return IvaRetencionRole.TAXPAYER_CREDIT if kind is InvoiceKind.ISSUED else IvaRetencionRole.TAXPAYER_LIABILITY


type _RowEntry = tuple[tuple[IvaCategory, InvoiceKind], IvaCategoryComponents]


def _row(
    category: IvaCategory,
    kind: InvoiceKind,
    *,
    base: IvaComponentPresence,
    cuota: IvaComponentPresence,
    cuota_settlement: IvaCuotaSettlement,
    cuota_grounding: IvaGroundingConfidence,
    recargo: IvaComponentPresence,
    recargo_grounding: IvaGroundingConfidence,
    retencion: IvaRetencionExpectation,
    retencion_grounding: IvaGroundingConfidence,
    retencion_note: str = "",
    legal_refs: tuple[str, ...] = (),
    pending_legal_refs: tuple[str, ...] = (),
    applicability: IvaKindApplicability = IvaKindApplicability.ARISES,
) -> _RowEntry:
    """Build one table entry keyed by its (category, kind) pair."""
    return (category, kind), IvaCategoryComponents(
        category=category,
        kind=kind,
        applicability=applicability,
        retencion_role=_role_for(kind, retencion),
        base=base,
        cuota=cuota,
        cuota_settlement=cuota_settlement,
        cuota_grounding=cuota_grounding,
        recargo=recargo,
        recargo_grounding=recargo_grounding,
        retencion=retencion,
        retencion_grounding=retencion_grounding,
        retencion_note=retencion_note,
        legal_refs=legal_refs,
        pending_legal_refs=pending_legal_refs,
    )


def _one_sided(category: IvaCategory, kind: InvoiceKind, counterpart_note: str) -> _RowEntry:
    """Build the non-arising side of a directional category."""
    return _row(
        category,
        kind,
        applicability=IvaKindApplicability.DOES_NOT_ARISE,
        base=IvaComponentPresence.UNKNOWN,
        cuota=IvaComponentPresence.UNKNOWN,
        cuota_settlement=IvaCuotaSettlement.UNKNOWN,
        cuota_grounding=IvaGroundingConfidence.UNGROUNDED,
        recargo=IvaComponentPresence.UNKNOWN,
        recargo_grounding=IvaGroundingConfidence.UNGROUNDED,
        retencion=IvaRetencionExpectation.UNKNOWN,
        retencion_grounding=IvaGroundingConfidence.UNGROUNDED,
        retencion_note=counterpart_note,
    )


def _domestic_rated(
    category: IvaCategory,
    tipo_ref: str,
    kind: InvoiceKind,
) -> _RowEntry:
    """Build a domestic rated row (base + repercutida cuota + optional recargo).

    Symmetric in components across both kinds — the taxpayer charges the cuota
    on what they issue and bears it on what they receive — and asymmetric only
    in the retención role, which the shared derivation supplies.
    """
    return _row(
        category,
        kind,
        base=IvaComponentPresence.REQUIRED,
        cuota=IvaComponentPresence.REQUIRED,
        cuota_settlement=IvaCuotaSettlement.REPERCUTIDA,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        # A supplier charges recargo only when the customer is a comerciante
        # minorista under the régimen especial (LIVA arts. 154/158.1/161), which
        # is a counterparty fact, not a category fact.
        recargo=IvaComponentPresence.OPTIONAL,
        recargo_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion=IvaRetencionExpectation.POSSIBLE,
        retencion_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion_note=_PROFESSIONAL_SERVICE_NOTE,
        legal_refs=(
            tipo_ref,
            _LIVA_RECARGO_SUJETOS,
            _LIVA_RECARGO_TIPOS,
            _LIRPF_PAGOS_A_CUENTA,
            _RIRPF_RETENCION_ACTIVIDADES,
        ),
    )


def _zero_cuota_domestic(
    category: IvaCategory,
    exencion_ref: str,
    kind: InvoiceKind,
) -> _RowEntry:
    """Build a domestic zero-cuota row that still carries a real taxable base."""
    return _row(
        category,
        kind,
        base=IvaComponentPresence.REQUIRED,
        cuota=IvaComponentPresence.ZERO_BY_LAW,
        cuota_settlement=IvaCuotaSettlement.NONE,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        recargo=IvaComponentPresence.ZERO_BY_LAW,
        # The recargo tipos in LIVA art. 161 are keyed to the art. 90/91 tipos;
        # an operation bearing none of those tipos bears no recargo. Inferred
        # from the tipo ladder rather than stated by a bundled provision.
        recargo_grounding=IvaGroundingConfidence.REASONED,
        # The anchor case: an IVA-exempt professional service carries no
        # cuota and still bears a retención. Cuota-less is not substrate-less.
        retencion=IvaRetencionExpectation.POSSIBLE,
        retencion_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion_note=_PROFESSIONAL_SERVICE_NOTE,
        legal_refs=(exencion_ref, _LIRPF_PAGOS_A_CUENTA, _RIRPF_RETENCION_ACTIVIDADES),
    )


def _zero_cuota_non_resident_payer(
    category: IvaCategory,
    exencion_ref: str,
    kind: InvoiceKind = InvoiceKind.ISSUED,
) -> _RowEntry:
    """Build a zero-cuota export / entrega-intracomunitaria row.

    The base is real and feeds base-only casillas (Modelo 303 casillas 59/60);
    only the cuota is zero. Issued by default: these are operations the
    taxpayer supplies, so the counterparty is a non-resident PAYER.
    """
    return _row(
        category,
        kind,
        base=IvaComponentPresence.REQUIRED,
        cuota=IvaComponentPresence.ZERO_BY_LAW,
        cuota_settlement=IvaCuotaSettlement.NONE,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        recargo=IvaComponentPresence.ZERO_BY_LAW,
        recargo_grounding=IvaGroundingConfidence.REASONED,
        retencion=IvaRetencionExpectation.NOT_EXPECTED,
        retencion_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion_note=_NON_RESIDENT_PAYER_NOTE,
        legal_refs=(exencion_ref, _LIRPF_PAGOS_A_CUENTA, _RIRPF_OBLIGADOS_A_RETENER),
    )


_ISSUED: Final = InvoiceKind.ISSUED
_RECEIVED: Final = InvoiceKind.RECEIVED

_COMPONENT_ROWS: Final[tuple[_RowEntry, ...]] = (
    # Domestic categories occur on both sides: the taxpayer both issues and
    # receives them. Components are symmetric, the retención role is not.
    _domestic_rated(IvaCategory.DOMESTIC_GENERAL, _LIVA_TIPO_GENERAL, _ISSUED),
    _domestic_rated(IvaCategory.DOMESTIC_GENERAL, _LIVA_TIPO_GENERAL, _RECEIVED),
    _domestic_rated(IvaCategory.DOMESTIC_REDUCED, _LIVA_TIPOS_REDUCIDOS, _ISSUED),
    _domestic_rated(IvaCategory.DOMESTIC_REDUCED, _LIVA_TIPOS_REDUCIDOS, _RECEIVED),
    _domestic_rated(IvaCategory.DOMESTIC_SUPER_REDUCED, _LIVA_TIPOS_REDUCIDOS, _ISSUED),
    _domestic_rated(IvaCategory.DOMESTIC_SUPER_REDUCED, _LIVA_TIPOS_REDUCIDOS, _RECEIVED),
    _zero_cuota_domestic(IvaCategory.DOMESTIC_ZERO, _LIVA_TIPOS_REDUCIDOS, _ISSUED),
    _zero_cuota_domestic(IvaCategory.DOMESTIC_ZERO, _LIVA_TIPOS_REDUCIDOS, _RECEIVED),
    _zero_cuota_domestic(IvaCategory.DOMESTIC_EXEMPT, _LIVA_EXENCIONES_INTERIORES, _ISSUED),
    _zero_cuota_domestic(IvaCategory.DOMESTIC_EXEMPT, _LIVA_EXENCIONES_INTERIORES, _RECEIVED),
    _zero_cuota_domestic(IvaCategory.DOMESTIC_NOT_SUBJECT, _LIVA_NO_SUJECION, _ISSUED),
    _zero_cuota_domestic(IvaCategory.DOMESTIC_NOT_SUBJECT, _LIVA_NO_SUJECION, _RECEIVED),
    _zero_cuota_domestic(IvaCategory.OPERACION_NO_SUJETA, _LIVA_NO_SUJECION, _ISSUED),
    _zero_cuota_domestic(IvaCategory.OPERACION_NO_SUJETA, _LIVA_NO_SUJECION, _RECEIVED),
    # Directional by law: an entrega/exportación is something the taxpayer
    # SUPPLIES. Each names the category that is the received-side counterpart.
    _zero_cuota_non_resident_payer(IvaCategory.INTRA_COMMUNITY_SUPPLY, _LIVA_ENTREGA_INTRACOM_EXENTA),
    _one_sided(
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
        _RECEIVED,
        "LIVA art. 25 exempts an entrega intracomunitaria — a supply the taxpayer makes. The "
        "received-side counterpart of an intra-community movement is "
        "'intra_community_acquisition_reverse_charge', which carries its own row.",
    ),
    _zero_cuota_non_resident_payer(IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED, _LIVA_EXPORTACION),
    _one_sided(
        IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        _RECEIVED,
        "LIVA art. 21 exempts an exportación — goods the taxpayer sends out of the Community. The "
        "received-side counterpart is 'import_third_country', which carries its own row.",
    ),
    _zero_cuota_non_resident_payer(IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED, _LIVA_EXPORTACION_ASIMILADA),
    _one_sided(
        IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED,
        _RECEIVED,
        "LIVA art. 22 exempts operaciones asimiladas a las exportaciones — supplies the taxpayer "
        "makes. The received-side counterpart is 'import_third_country'.",
    ),
    # Triangulation is declared on BOTH sides deliberately. The taxpayer can be
    # the intermediate operator, and LIVA art. 26.3 exempts that intermediary's
    # ADQUISICIÓN — a received-side fact — while the onward leg is a supply. A
    # DOES_NOT_ARISE here would refuse a real operation, so both sides are
    # declared with the counterparty note each side's residency implies.
    _zero_cuota_non_resident_payer(IvaCategory.INTRA_COMMUNITY_TRIANGULATION, _LIVA_EXENCION_ADQ_INTRACOM),
    _row(
        IvaCategory.INTRA_COMMUNITY_TRIANGULATION,
        _RECEIVED,
        base=IvaComponentPresence.REQUIRED,
        cuota=IvaComponentPresence.ZERO_BY_LAW,
        cuota_settlement=IvaCuotaSettlement.NONE,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        recargo=IvaComponentPresence.ZERO_BY_LAW,
        recargo_grounding=IvaGroundingConfidence.REASONED,
        retencion=IvaRetencionExpectation.NOT_EXPECTED,
        retencion_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion_note=_NON_RESIDENT_SUPPLIER_NOTE,
        legal_refs=(_LIVA_EXENCION_ADQ_INTRACOM, _LIRPF_PAGOS_A_CUENTA, _RIRPF_OBLIGADOS_A_RETENER),
    ),
    _row(
        IvaCategory.DOMESTIC_REVERSE_CHARGE,
        _RECEIVED,
        base=IvaComponentPresence.REQUIRED,
        # Inversión del sujeto pasivo: the recipient declares the cuota as
        # devengada and, where deducible, as soportada. Two entries, one cuota.
        cuota=IvaComponentPresence.REQUIRED,
        cuota_settlement=IvaCuotaSettlement.INVERSION_SUJETO_PASIVO,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        # LIVA art. 158.2 obliges a minorista under the régimen especial to pay
        # recargo on art. 84.uno.2 (inversión) supuestos as well.
        recargo=IvaComponentPresence.OPTIONAL,
        recargo_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion=IvaRetencionExpectation.POSSIBLE,
        retencion_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion_note=_PROFESSIONAL_SERVICE_NOTE,
        legal_refs=(
            _LIVA_SUJETO_PASIVO,
            _LIVA_RECARGO_SUJETOS,
            _LIRPF_PAGOS_A_CUENTA,
            _RIRPF_RETENCION_ACTIVIDADES,
        ),
    ),
    # The issued side of inversión del sujeto pasivo: the taxpayer SUPPLIES
    # under LIVA art. 84.Uno.2.º, so the invoice carries base only and the
    # RECIPIENT self-assesses the cuota. Zero cuota here is the correct face of
    # the operation, not a missing one.
    _row(
        IvaCategory.DOMESTIC_REVERSE_CHARGE,
        _ISSUED,
        base=IvaComponentPresence.REQUIRED,
        cuota=IvaComponentPresence.ZERO_BY_LAW,
        cuota_settlement=IvaCuotaSettlement.NONE,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        recargo=IvaComponentPresence.ZERO_BY_LAW,
        recargo_grounding=IvaGroundingConfidence.REASONED,
        retencion=IvaRetencionExpectation.POSSIBLE,
        retencion_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion_note=_PROFESSIONAL_SERVICE_NOTE,
        legal_refs=(
            _LIVA_SUJETO_PASIVO,
            _LIRPF_PAGOS_A_CUENTA,
            _RIRPF_RETENCION_ACTIVIDADES,
        ),
    ),
    # Intra-community SERVICES. Deliberately NOT folded into the goods rows
    # above: both carry no Spanish cuota on the issued face, but for a
    # different reason, and the reason is what the filing cites. An entrega de
    # bienes is located in Spain and EXEMPTED by art. 25; a B2B service is not
    # located in Spain at all, because art. 69.Uno.1.o places it where the
    # recipient is established. No sujeta is not exenta, and citing art. 25 on
    # a service would ground the figure in a provision that does not reach it.
    # Art. 70 rides alongside art. 69 on both rows because its reglas
    # especiales OVERRIDE the general rule for several service kinds, so the
    # localisation a row asserts is only sound once art. 70 has been read.
    _row(
        IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY,
        _ISSUED,
        # The base is real and belongs on the base-only casillas: the operation
        # is declarable in Spain even though no Spanish cuota arises from it.
        base=IvaComponentPresence.REQUIRED,
        cuota=IvaComponentPresence.ZERO_BY_LAW,
        cuota_settlement=IvaCuotaSettlement.NONE,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        # Every recargo tipo in art. 161 names an ENTREGA DE BIENES, so a
        # prestacion de servicios bears none. Inferred from the tipo ladder
        # rather than stated by a bundled provision, exactly as the domestic
        # zero-cuota rows infer it.
        recargo=IvaComponentPresence.ZERO_BY_LAW,
        recargo_grounding=IvaGroundingConfidence.REASONED,
        retencion=IvaRetencionExpectation.NOT_EXPECTED,
        retencion_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion_note=_NON_RESIDENT_PAYER_NOTE,
        legal_refs=(
            _LIVA_LUGAR_SERVICIOS_GENERAL,
            _LIVA_LUGAR_SERVICIOS_ESPECIAL,
            _LIRPF_PAGOS_A_CUENTA,
            _RIRPF_OBLIGADOS_A_RETENER,
        ),
    ),
    _one_sided(
        IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY,
        _RECEIVED,
        "LIVA art. 69.Uno.1.o locates a B2B service where the RECIPIENT is established, so this "
        "category describes a service the taxpayer SUPPLIES to a business in another Member "
        "State. The received-side counterpart is "
        "'intra_community_service_acquisition_reverse_charge', which carries its own row.",
    ),
    _row(
        IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
        _RECEIVED,
        base=IvaComponentPresence.REQUIRED,
        # Art. 69.Uno.1.o locates the service HERE because the recipient is
        # established here, and art. 84.Uno.2.o makes that recipient the sujeto
        # pasivo: the cuota is real and self-assessed, not absent.
        cuota=IvaComponentPresence.REQUIRED,
        cuota_settlement=IvaCuotaSettlement.INVERSION_SUJETO_PASIVO,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        # Diverges from the goods acquisition row, which carries OPTIONAL
        # recargo: the recargo de equivalencia attaches to entregas de bienes
        # to a comerciante minorista, and no art. 161 tipo reaches a service.
        recargo=IvaComponentPresence.ZERO_BY_LAW,
        recargo_grounding=IvaGroundingConfidence.REASONED,
        retencion=IvaRetencionExpectation.NOT_EXPECTED,
        retencion_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion_note=_NON_RESIDENT_SUPPLIER_NOTE,
        legal_refs=(
            _LIVA_LUGAR_SERVICIOS_GENERAL,
            _LIVA_LUGAR_SERVICIOS_ESPECIAL,
            _LIVA_SUJETO_PASIVO,
            _LIRPF_PAGOS_A_CUENTA,
            _RIRPF_OBLIGADOS_A_RETENER,
        ),
    ),
    _one_sided(
        IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
        _ISSUED,
        "This category describes a service the taxpayer RECEIVES from a supplier in another "
        "Member State, self-assessing the cuota under LIVA art. 84.Uno.2.o. The issued-side "
        "counterpart is 'intra_community_service_supply', which carries its own row.",
    ),
    _one_sided(
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        _ISSUED,
        "LIVA arts. 13/15 define an adquisición intracomunitaria — something the taxpayer "
        "RECEIVES. The issued-side counterpart of an intra-community movement is "
        "'intra_community_supply', which carries its own row.",
    ),
    _row(
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        _RECEIVED,
        base=IvaComponentPresence.REQUIRED,
        cuota=IvaComponentPresence.REQUIRED,
        cuota_settlement=IvaCuotaSettlement.INVERSION_SUJETO_PASIVO,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        recargo=IvaComponentPresence.OPTIONAL,
        recargo_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion=IvaRetencionExpectation.NOT_EXPECTED,
        retencion_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion_note=_NON_RESIDENT_SUPPLIER_NOTE,
        legal_refs=(
            _LIVA_ADQ_INTRACOM,
            _LIVA_ADQ_INTRACOM_CONCEPTO,
            _LIVA_SUJETO_PASIVO,
            _LIVA_RECARGO_SUJETOS,
            _LIRPF_PAGOS_A_CUENTA,
            _RIRPF_OBLIGADOS_A_RETENER,
        ),
    ),
    _one_sided(
        IvaCategory.IMPORT_THIRD_COUNTRY,
        _ISSUED,
        "LIVA art. 17 defines an importación — goods entering the Community, which the taxpayer "
        "RECEIVES. The issued-side counterparts are 'export_third_country_zero_rated' and "
        "'export_assimilated_zero_rated', which carry their own rows.",
    ),
    _row(
        IvaCategory.IMPORT_THIRD_COUNTRY,
        _RECEIVED,
        base=IvaComponentPresence.REQUIRED,
        # The cuota is settled at the aduana on the DUA, not repercutida by the
        # supplier, which is why it routes to different casillas entirely.
        cuota=IvaComponentPresence.REQUIRED,
        cuota_settlement=IvaCuotaSettlement.ADUANA,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        recargo=IvaComponentPresence.OPTIONAL,
        recargo_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion=IvaRetencionExpectation.NOT_EXPECTED,
        retencion_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion_note=_NON_RESIDENT_SUPPLIER_NOTE,
        legal_refs=(
            _LIVA_IMPORTACION,
            _LIVA_RECARGO_SUJETOS,
            _LIRPF_PAGOS_A_CUENTA,
            _RIRPF_OBLIGADOS_A_RETENER,
        ),
    ),
    # The recargo de equivalencia category is the retailer's PURCHASE-side
    # surcharge: the supplier charges IVA + RE to a comerciante minorista, and
    # the total is non-deductible acquisition cost. The ledger preflight already
    # refuses it on the issued side ("not the supplier-side recargo sales
    # channel"), so declaring the issued pair non-arising restates a decision
    # this codebase has already made rather than adding a new one.
    _one_sided(
        IvaCategory.RECARGO_EQUIVALENCIA,
        _ISSUED,
        "LIVA art. 154 applies the régimen del recargo de equivalencia to entregas made TO a "
        "comerciante minorista, so this category describes what the taxpayer receives. Supplier-side "
        "recargo charged on a taxable output sale is recorded through the invoice's recargo amount, "
        "not by tagging the sale with this category.",
    ),
    _row(
        IvaCategory.RECARGO_EQUIVALENCIA,
        _RECEIVED,
        base=IvaComponentPresence.REQUIRED,
        cuota=IvaComponentPresence.REQUIRED,
        cuota_settlement=IvaCuotaSettlement.REPERCUTIDA,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        recargo=IvaComponentPresence.REQUIRED,
        recargo_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion=IvaRetencionExpectation.NOT_EXPECTED,
        retencion_grounding=IvaGroundingConfidence.REASONED,
        retencion_note=(
            "Reasoned, not measured: the régimen del recargo de equivalencia applies to entregas "
            "de bienes to comerciantes minoristas (LIVA art. 154), while RIRPF art. 95.1 scopes "
            "retención to the contraprestación of an actividad profesional. The inference that a "
            "goods purchase under this regime bears no retención follows from those two scopes; "
            "no bundled provision states it directly."
        ),
        legal_refs=(_LIVA_RECARGO_AMBITO, _LIVA_RECARGO_SUJETOS, _LIVA_RECARGO_TIPOS),
    ),
    _row(
        IvaCategory.REGIMEN_SIMPLIFICADO,
        _ISSUED,
        base=IvaComponentPresence.REQUIRED,
        # A cuota exists but it is settled through the régimen simplificado
        # módulo path, not the general Modelo 303 cuota bindings.
        cuota=IvaComponentPresence.REQUIRED,
        cuota_settlement=IvaCuotaSettlement.REGIMEN_ESPECIAL,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        recargo=IvaComponentPresence.ZERO_BY_LAW,
        recargo_grounding=IvaGroundingConfidence.REASONED,
        retencion=IvaRetencionExpectation.POSSIBLE,
        retencion_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion_note=_ESTIMACION_OBJETIVA_NOTE,
        legal_refs=(
            _LIVA_SIMPLIFICADO_AMBITO,
            _LIVA_SIMPLIFICADO_CUOTA,
            _LIRPF_PAGOS_A_CUENTA,
            _RIRPF_RETENCION_ACTIVIDADES,
        ),
    ),
    # The received side is declared ARISES rather than non-arising: the régimen
    # simplificado computes a cuota from módulos in which the taxpayer's own
    # purchases participate, so an invoice tagged this way on the received side
    # is not obviously impossible. Declaring it non-arising would refuse a real
    # operation on a reasoned guess, which is the more damaging error of the
    # two; the weak grounding is stated rather than hidden.
    _row(
        IvaCategory.REGIMEN_SIMPLIFICADO,
        _RECEIVED,
        base=IvaComponentPresence.REQUIRED,
        cuota=IvaComponentPresence.REQUIRED,
        cuota_settlement=IvaCuotaSettlement.REGIMEN_ESPECIAL,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        recargo=IvaComponentPresence.ZERO_BY_LAW,
        recargo_grounding=IvaGroundingConfidence.REASONED,
        retencion=IvaRetencionExpectation.POSSIBLE,
        retencion_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion_note=(
            "Whether a RECEIVED invoice legitimately carries this category is itself unsettled -- "
            "the régimen simplificado (LIVA arts. 122/123) describes the taxpayer's own OUTPUT "
            "regime -- and the pair is declared to arise because refusing a real operation is "
            "worse than carrying an unused row. That uncertainty is about the row, not about the "
            "retención: where one arises the taxpayer is the retenedor, and it is grounded exactly "
            "as on the issued side. " + _ESTIMACION_OBJETIVA_NOTE
        ),
        legal_refs=(
            _LIVA_SIMPLIFICADO_AMBITO,
            _LIVA_SIMPLIFICADO_CUOTA,
            _LIRPF_PAGOS_A_CUENTA,
            _RIRPF_RETENCION_ACTIVIDADES,
        ),
    ),
    # REAGP, the régimen especial de la agricultura, ganadería y pesca. Both
    # sides arise and they are different operations rather than mirror images:
    # LIVA art. 131.2.º makes the ACQUIRER pay the compensación on an ordinary
    # domestic supply, so the issued side is the taxpayer farming and being
    # compensated, and the received side is the taxpayer buying and paying it.
    #
    # No cuota on either face, and that is the regime's whole point: a REAGP
    # farmer does not repercutir IVA, and art. 130.Dos gives them a compensación
    # a tanto alzado instead -- 12 % of the sale price for agrícolas y
    # forestales, 10,5 % for ganaderas y pesqueras (art. 130.Cinco). What the
    # acquirer pays is therefore not a cuota, though art. 134.Uno lets them
    # deduct its amount as if it were one, against the self-issued document
    # art. 134.Tres requires.
    _row(
        IvaCategory.REAGP_COMPENSATION,
        _ISSUED,
        base=IvaComponentPresence.REQUIRED,
        # NONE rather than REGIMEN_ESPECIAL, and the difference is the point:
        # the régimen simplificado settles a real cuota through its own path,
        # while here no cuota arises at all. What flows is a compensación, which
        # art. 130 names as such precisely because it is not tax charged.
        cuota=IvaComponentPresence.ZERO_BY_LAW,
        cuota_settlement=IvaCuotaSettlement.NONE,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        # Art. 161's tipos all name an entrega to a comerciante minorista under
        # the recargo regime; none reaches a compensación. Inferred from that
        # ladder rather than stated, exactly as the other zero-cuota rows infer
        # it.
        recargo=IvaComponentPresence.ZERO_BY_LAW,
        recargo_grounding=IvaGroundingConfidence.REASONED,
        retencion=IvaRetencionExpectation.POSSIBLE,
        retencion_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion_note=_AGRICULTURAL_ACTIVITY_NOTE,
        legal_refs=(
            _LIVA_REAGP_COMPENSACION,
            _LIVA_REAGP_REINTEGRO,
            _LIRPF_PAGOS_A_CUENTA,
            _RIRPF_RETENCION_ACTIVIDADES,
        ),
    ),
    _row(
        IvaCategory.REAGP_COMPENSATION,
        _RECEIVED,
        base=IvaComponentPresence.REQUIRED,
        cuota=IvaComponentPresence.ZERO_BY_LAW,
        cuota_settlement=IvaCuotaSettlement.NONE,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        recargo=IvaComponentPresence.ZERO_BY_LAW,
        recargo_grounding=IvaGroundingConfidence.REASONED,
        retencion=IvaRetencionExpectation.POSSIBLE,
        retencion_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion_note=_AGRICULTURAL_ACTIVITY_NOTE,
        legal_refs=(
            _LIVA_REAGP_COMPENSACION,
            _LIVA_REAGP_REINTEGRO,
            _LIVA_REAGP_DEDUCCION,
            _LIRPF_PAGOS_A_CUENTA,
            _RIRPF_RETENCION_ACTIVIDADES,
        ),
    ),
    _row(
        IvaCategory.ERRONEOUS_INVOICE,
        _ISSUED,
        base=IvaComponentPresence.UNKNOWN,
        cuota=IvaComponentPresence.UNKNOWN,
        cuota_settlement=IvaCuotaSettlement.UNKNOWN,
        cuota_grounding=IvaGroundingConfidence.UNGROUNDED,
        recargo=IvaComponentPresence.UNKNOWN,
        recargo_grounding=IvaGroundingConfidence.UNGROUNDED,
        retencion=IvaRetencionExpectation.UNKNOWN,
        retencion_grounding=IvaGroundingConfidence.UNGROUNDED,
        retencion_note=(
            "Sentinel category: the operator has flagged the invoice as erroneous, so no component "
            "expectation can be asserted. Declared unknown rather than guessed."
        ),
    ),
    # Both sentinels arise on both kinds: an operator can flag an invoice
    # erroneous, or leave it untagged, whichever way it was going.
    _row(
        IvaCategory.ERRONEOUS_INVOICE,
        _RECEIVED,
        base=IvaComponentPresence.UNKNOWN,
        cuota=IvaComponentPresence.UNKNOWN,
        cuota_settlement=IvaCuotaSettlement.UNKNOWN,
        cuota_grounding=IvaGroundingConfidence.UNGROUNDED,
        recargo=IvaComponentPresence.UNKNOWN,
        recargo_grounding=IvaGroundingConfidence.UNGROUNDED,
        retencion=IvaRetencionExpectation.UNKNOWN,
        retencion_grounding=IvaGroundingConfidence.UNGROUNDED,
        retencion_note=(
            "Sentinel category: the operator has flagged the invoice as erroneous, so no component "
            "expectation can be asserted. Declared unknown rather than guessed."
        ),
    ),
    _row(
        IvaCategory.UNKNOWN,
        _ISSUED,
        base=IvaComponentPresence.UNKNOWN,
        cuota=IvaComponentPresence.UNKNOWN,
        cuota_settlement=IvaCuotaSettlement.UNKNOWN,
        cuota_grounding=IvaGroundingConfidence.UNGROUNDED,
        recargo=IvaComponentPresence.UNKNOWN,
        recargo_grounding=IvaGroundingConfidence.UNGROUNDED,
        retencion=IvaRetencionExpectation.UNKNOWN,
        retencion_grounding=IvaGroundingConfidence.UNGROUNDED,
        retencion_note=(
            "Sentinel category: no IVA treatment declared, so untagged and exempt are "
            "indistinguishable from the amounts alone. This is exactly the ambiguity that makes a "
            "row ungrounded rather than exempt."
        ),
    ),
    _row(
        IvaCategory.UNKNOWN,
        _RECEIVED,
        base=IvaComponentPresence.UNKNOWN,
        cuota=IvaComponentPresence.UNKNOWN,
        cuota_settlement=IvaCuotaSettlement.UNKNOWN,
        cuota_grounding=IvaGroundingConfidence.UNGROUNDED,
        recargo=IvaComponentPresence.UNKNOWN,
        recargo_grounding=IvaGroundingConfidence.UNGROUNDED,
        retencion=IvaRetencionExpectation.UNKNOWN,
        retencion_grounding=IvaGroundingConfidence.UNGROUNDED,
        retencion_note=(
            "Sentinel category: no IVA treatment declared, so untagged and exempt are "
            "indistinguishable from the amounts alone. This is exactly the ambiguity that makes a "
            "row ungrounded rather than exempt."
        ),
    ),
)

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
