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

from ._errors import IvaValidationError
from ._schema import (
    CUOTA_LESS_M303_IVA_CATEGORIES,
    IvaCategory,
    IvaStrictFrozen,
    _RegistryLegalRef,  # reason: intra-package reuse of the package's own constrained legal-ref alias
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

    Attributes:
        category: The IVA situation this row describes.
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
        label = f"IvaCategoryComponents[{self.category.value}]"
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


# --------------------------------------------------------------------------- #
# Legal-reference shorthands. Every id below is present in the bundled legal
# catalogue under registry/aeat/legal/ unless it appears in _PENDING_*.
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
_LIVA_SUJETO_PASIVO: Final[str] = "ley-37-1992:art-84"
_LIVA_TIPO_GENERAL: Final[str] = "ley-37-1992:art-90"
_LIVA_TIPOS_REDUCIDOS: Final[str] = "ley-37-1992:art-91"
_LIVA_SIMPLIFICADO_AMBITO: Final[str] = "ley-37-1992:art-122"
_LIVA_SIMPLIFICADO_CUOTA: Final[str] = "ley-37-1992:art-123"
_LIVA_RECARGO_AMBITO: Final[str] = "ley-37-1992:art-154"
_LIVA_RECARGO_SUJETOS: Final[str] = "ley-37-1992:art-158"
_LIVA_RECARGO_TIPOS: Final[str] = "ley-37-1992:art-161"
_LIRPF_PAGOS_A_CUENTA: Final[str] = "ley-35-2006:art-99"
_RIRPF_RETENCION_ACTIVIDADES: Final[str] = "rd-439-2007:art-95"

#: RIRPF art. 76 (obligados a retener o ingresar a cuenta) was verified against
#: live BOE consolidated text on 2026-08-05 — apartado 1.c obliges non-residents
#: operating through a permanent establishment, and apartado 1.d limits the
#: obligation for non-residents *without* a PE to rendimientos del trabajo and
#: to rendimientos that are a deducible gasto for IRNR art. 24.2 rentas. The
#: provision is not yet bundled, so rows relying on it declare it here.
_RIRPF_OBLIGADOS_A_RETENER_PENDING: Final[str] = "rd-439-2007:art-76"

_NON_RESIDENT_PAYER_NOTE: Final[str] = (
    "Reasoned from a live-BOE reading of RIRPF art. 76.1 (2026-08-05), not from bundled text: "
    "the payer is non-resident by construction for this category, and a non-resident payer "
    "without a Spanish permanent establishment falls outside the withholding obligation except "
    "for rendimientos del trabajo and rendimientos that are a deducible gasto for IRNR art. 24.2 "
    "rentas (art. 76.1.d). A payer WITH a Spanish permanent establishment IS obliged (art. 76.1.c), "
    "so this expectation is a default and not a prohibition. Promote to bundled grounding once "
    "rd-439-2007:art-76 is in the legal catalogue."
)

_NON_RESIDENT_SUPPLIER_NOTE: Final[str] = (
    "Reasoned from a live-BOE reading of RIRPF art. 76.1 (2026-08-05), not from bundled text: "
    "this is an acquisition category, so the counterparty is a non-resident supplier whose income "
    "is not an IRPF rendimiento; no IRPF retención arises for the Spanish acquirer. Any IRNR "
    "withholding obligation is a separate tax and is out of this table's scope."
)

_PROFESSIONAL_SERVICE_NOTE: Final[str] = (
    "Possible rather than expected because whether a retención arises depends on facts the IVA "
    "category does not carry: the rendimiento must be the contraprestación of an actividad "
    "profesional (RIRPF art. 95.1) and the payer must be an obliged retenedor (LIRPF art. 99)."
)


def _row(
    category: IvaCategory,
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
) -> tuple[IvaCategory, IvaCategoryComponents]:
    """Build one table entry keyed by its category."""
    return category, IvaCategoryComponents(
        category=category,
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


def _domestic_rated(
    category: IvaCategory,
    tipo_ref: str,
) -> tuple[IvaCategory, IvaCategoryComponents]:
    """Build a domestic rated row (base + repercutida cuota + optional recargo)."""
    return _row(
        category,
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
) -> tuple[IvaCategory, IvaCategoryComponents]:
    """Build a domestic zero-cuota row that still carries a real taxable base."""
    return _row(
        category,
        base=IvaComponentPresence.REQUIRED,
        cuota=IvaComponentPresence.ZERO_BY_LAW,
        cuota_settlement=IvaCuotaSettlement.NONE,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        recargo=IvaComponentPresence.ZERO_BY_LAW,
        # The recargo tipos in LIVA art. 161 are keyed to the art. 90/91 tipos;
        # an operation bearing none of those tipos bears no recargo. Inferred
        # from the tipo ladder rather than stated by a bundled provision.
        recargo_grounding=IvaGroundingConfidence.REASONED,
        # The ADR's anchor case: an IVA-exempt professional service carries no
        # cuota and still bears a retención. Cuota-less is not substrate-less.
        retencion=IvaRetencionExpectation.POSSIBLE,
        retencion_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion_note=_PROFESSIONAL_SERVICE_NOTE,
        legal_refs=(exencion_ref, _LIRPF_PAGOS_A_CUENTA, _RIRPF_RETENCION_ACTIVIDADES),
    )


def _zero_cuota_non_resident_payer(
    category: IvaCategory,
    exencion_ref: str,
) -> tuple[IvaCategory, IvaCategoryComponents]:
    """Build a zero-cuota export / entrega-intracomunitaria row.

    The base is real and feeds base-only casillas (Modelo 303 casillas 59/60);
    only the cuota is zero.
    """
    return _row(
        category,
        base=IvaComponentPresence.REQUIRED,
        cuota=IvaComponentPresence.ZERO_BY_LAW,
        cuota_settlement=IvaCuotaSettlement.NONE,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        recargo=IvaComponentPresence.ZERO_BY_LAW,
        recargo_grounding=IvaGroundingConfidence.REASONED,
        retencion=IvaRetencionExpectation.NOT_EXPECTED,
        retencion_grounding=IvaGroundingConfidence.LIVE_SOURCE_ONLY,
        retencion_note=_NON_RESIDENT_PAYER_NOTE,
        legal_refs=(exencion_ref,),
        pending_legal_refs=(_RIRPF_OBLIGADOS_A_RETENER_PENDING,),
    )


_COMPONENT_ROWS: Final[tuple[tuple[IvaCategory, IvaCategoryComponents], ...]] = (
    _domestic_rated(IvaCategory.DOMESTIC_GENERAL_21, _LIVA_TIPO_GENERAL),
    _domestic_rated(IvaCategory.DOMESTIC_REDUCED_10, _LIVA_TIPOS_REDUCIDOS),
    _domestic_rated(IvaCategory.DOMESTIC_SUPER_REDUCED_4, _LIVA_TIPOS_REDUCIDOS),
    _zero_cuota_domestic(IvaCategory.DOMESTIC_ZERO, _LIVA_TIPOS_REDUCIDOS),
    _zero_cuota_domestic(IvaCategory.DOMESTIC_EXEMPT, _LIVA_EXENCIONES_INTERIORES),
    _zero_cuota_domestic(IvaCategory.DOMESTIC_NOT_SUBJECT, _LIVA_NO_SUJECION),
    _zero_cuota_domestic(IvaCategory.OPERACION_NO_SUJETA, _LIVA_NO_SUJECION),
    _zero_cuota_non_resident_payer(IvaCategory.INTRA_COMMUNITY_SUPPLY, _LIVA_ENTREGA_INTRACOM_EXENTA),
    _zero_cuota_non_resident_payer(IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED, _LIVA_EXPORTACION),
    _zero_cuota_non_resident_payer(IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED, _LIVA_EXPORTACION_ASIMILADA),
    _zero_cuota_non_resident_payer(IvaCategory.INTRA_COMMUNITY_TRIANGULATION, _LIVA_EXENCION_ADQ_INTRACOM),
    _row(
        IvaCategory.DOMESTIC_REVERSE_CHARGE,
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
    _row(
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        base=IvaComponentPresence.REQUIRED,
        cuota=IvaComponentPresence.REQUIRED,
        cuota_settlement=IvaCuotaSettlement.INVERSION_SUJETO_PASIVO,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        recargo=IvaComponentPresence.OPTIONAL,
        recargo_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion=IvaRetencionExpectation.NOT_EXPECTED,
        retencion_grounding=IvaGroundingConfidence.LIVE_SOURCE_ONLY,
        retencion_note=_NON_RESIDENT_SUPPLIER_NOTE,
        legal_refs=(
            _LIVA_ADQ_INTRACOM,
            _LIVA_ADQ_INTRACOM_CONCEPTO,
            _LIVA_SUJETO_PASIVO,
            _LIVA_RECARGO_SUJETOS,
        ),
        pending_legal_refs=(_RIRPF_OBLIGADOS_A_RETENER_PENDING,),
    ),
    _row(
        IvaCategory.IMPORT_THIRD_COUNTRY,
        base=IvaComponentPresence.REQUIRED,
        # The cuota is settled at the aduana on the DUA, not repercutida by the
        # supplier, which is why it routes to different casillas entirely.
        cuota=IvaComponentPresence.REQUIRED,
        cuota_settlement=IvaCuotaSettlement.ADUANA,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        recargo=IvaComponentPresence.OPTIONAL,
        recargo_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        retencion=IvaRetencionExpectation.NOT_EXPECTED,
        retencion_grounding=IvaGroundingConfidence.LIVE_SOURCE_ONLY,
        retencion_note=_NON_RESIDENT_SUPPLIER_NOTE,
        legal_refs=(_LIVA_IMPORTACION, _LIVA_RECARGO_SUJETOS),
        pending_legal_refs=(_RIRPF_OBLIGADOS_A_RETENER_PENDING,),
    ),
    _row(
        IvaCategory.RECARGO_EQUIVALENCIA,
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
        base=IvaComponentPresence.REQUIRED,
        # A cuota exists but it is settled through the régimen simplificado
        # módulo path, not the general Modelo 303 cuota bindings.
        cuota=IvaComponentPresence.REQUIRED,
        cuota_settlement=IvaCuotaSettlement.REGIMEN_ESPECIAL,
        cuota_grounding=IvaGroundingConfidence.BUNDLED_CORPUS,
        recargo=IvaComponentPresence.ZERO_BY_LAW,
        recargo_grounding=IvaGroundingConfidence.REASONED,
        retencion=IvaRetencionExpectation.POSSIBLE,
        retencion_grounding=IvaGroundingConfidence.REASONED,
        retencion_note=(
            "Reasoned, not measured: activities in estimación objetiva can bear a retención under "
            "RIRPF art. 95, but the applicable apartado and its rate are not covered by the "
            "bundled art. 95 excerpt (which carries apartado 1 only). Treat the rate as ungrounded "
            "until the full article is bundled."
        ),
        legal_refs=(_LIVA_SIMPLIFICADO_AMBITO, _LIVA_SIMPLIFICADO_CUOTA),
    ),
    _row(
        IvaCategory.ERRONEOUS_INVOICE,
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

IVA_CATEGORY_COMPONENTS: Final[Mapping[IvaCategory, IvaCategoryComponents]] = MappingProxyType(
    dict(_COMPONENT_ROWS),
)
"""Axis-A component-expectation table, one row per :class:`~domain.iva.IvaCategory`.

Completeness is enforced by :mod:`domain.iva.tests.test_component_expectations`,
so a new category cannot ship without declaring its components.
"""


def iva_category_components(category: IvaCategory) -> IvaCategoryComponents:
    """Return the Axis-A component expectations for ``category``.

    Args:
        category: The declared IVA situation of the row being decomposed.

    Returns:
        The :class:`IvaCategoryComponents` row for ``category``.

    Raises:
        IvaValidationError: If the table has no row for ``category``. The
            completeness gate makes this unreachable for a shipped enum member;
            it fires only while a newly added member is still undeclared.
    """
    try:
        return IVA_CATEGORY_COMPONENTS[category]
    except KeyError as exc:  # pragma: no cover - guarded by the completeness gate
        raise IvaValidationError(
            f"no Axis-A component expectations declared for IVA category {category.value!r}",
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

    Returns:
        The categories that legitimately match no Modelo 303 cuota binding.
    """
    return frozenset(
        category
        for category, row in IVA_CATEGORY_COMPONENTS.items()
        if row.cuota is IvaComponentPresence.ZERO_BY_LAW or row.cuota_settlement is IvaCuotaSettlement.REGIMEN_ESPECIAL
    )


def category_bears_taxable_base(category: IvaCategory) -> bool:
    """Return ``True`` when a declared taxable base is legally required.

    Cuota-less is not substrate-less: an entrega intracomunitaria exenta and an
    IVA-exempt professional service both return ``True`` here even though they
    carry no cuota, which is why a base-less row in either category is
    ungrounded rather than legitimately empty.

    Args:
        category: The declared IVA situation.

    Returns:
        ``True`` when the category requires a taxable base.
    """
    return iva_category_components(category).base is IvaComponentPresence.REQUIRED


def category_cuota_is_zero_by_law(category: IvaCategory) -> bool:
    """Return ``True`` when the category's IVA cuota is structurally zero.

    Consumed by the retención-inference precondition: a declared-exempt invoice
    has a *determinable* cuota (zero), so it can qualify for bounded inference
    even though no explicit ``iva_amount`` was recorded.

    Args:
        category: The declared IVA situation.

    Returns:
        ``True`` when the cuota is zero by law for this category.
    """
    return iva_category_components(category).cuota is IvaComponentPresence.ZERO_BY_LAW


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
    "IvaRetencionExpectation",
    "category_bears_taxable_base",
    "category_cuota_is_zero_by_law",
    "cuota_less_m303_categories_from_table",
    "iva_category_components",
]
