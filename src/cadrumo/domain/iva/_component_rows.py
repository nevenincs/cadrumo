"""Private legal-reference shorthands and row builders for IVA components.

The canonical public mapping and query API remain in :mod:`.components`; this
internal sibling owns the data-driven regulatory rows they expose.
"""

from __future__ import annotations

from typing import Final

from .classification import InvoiceKind
from .components import (
    IvaCategoryComponents,
    IvaComponentPresence,
    IvaCuotaSettlement,
    IvaGroundingConfidence,
    IvaKindApplicability,
    IvaRetencionExpectation,
    IvaRetencionRole,
)
from .schema import IvaCategory

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

COMPONENT_ROWS: Final[tuple[_RowEntry, ...]] = (
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
