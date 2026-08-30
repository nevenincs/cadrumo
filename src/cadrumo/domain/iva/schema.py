"""Strict pydantic v2 schema for the :mod:`cadrumo.domain.iva` subpackage.

Every record the subpackage exposes — enumerations, per-rate values,
citations, regulations, catalogues, verification reports — is defined here.
The schema is frozen and strict wherever the loader idiom permits it,
matching the current registry-backed legal grounding conventions.

Closed catalogues (:class:`IvaCategory`, :class:`EUMemberState`,
:class:`IvaRateKind`) are :class:`enum.StrEnum` subclasses. Every prose field
is stored inline and Spanish-authoritative: a citation's ``quoted_text`` is
verbatim BOE text, which is evidence rather than a label, and so has no
locale-resolved form.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Protocol, override

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_serializer,
    field_validator,
    model_validator,
)

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.citation_grounding import CitationGrounding
from ...core.errors.severity import BaseSeverity
from ...core.parsing import parse_iso8601_date
from ...core.validity_window import ValidityWindow
from .errors import IvaValidationError


class _ModuloOrdenAnualLike(Protocol):
    order: int
    coefficient: Decimal
    identity: str


def validate_orden_module_identities(modulos: tuple[_ModuloOrdenAnualLike, ...]) -> None:
    """Refuse an Orden activity whose modules are missing, misordered or non-positive."""
    if not 1 <= len(modulos) <= 7:
        raise IvaValidationError("an Orden activity must declare one through seven modules")
    if tuple(module.order for module in modulos) != tuple(range(1, len(modulos) + 1)):
        raise IvaValidationError("an Orden activity module identities must be complete and ordered")
    if any(module.coefficient <= 0 for module in modulos):
        raise IvaValidationError("an Orden activity module must have a positive coefficient")
    identities = tuple(module.identity for module in modulos)
    if len(set(identities)) != len(identities):
        raise IvaValidationError("an Orden activity contains duplicate module identities")


class IvaCategory(StrEnum):
    """Closed catalogue of Spanish IVA situations.

    The member names and string values are the authoritative identifiers used
    by the downstream classifier layers (financial providers, the spending
    category taxonomy, and the transaction-data-pipeline engine) to tag a
    transaction. Registry binding selectors match these values as STRINGS, so a
    member's value is a stored token, not a label.

    A member names its TIER and never that tier's percentage. The three
    domestic rate members once appended the rate to the name, which was safe
    only while a tier had exactly one rate for all time. RD-ley 4/2024 ended
    that: it put certain foodstuffs at 2 % and 7,5 % while the rest of the
    super-reducido and reducido tiers stayed at 4 % and 10 %, so a 2 % line was
    classified under a member whose name ended in ``_4`` -- asserting a rate the
    line did not carry, and read verbatim by the operator in the CLI's own
    choice list, which renders these values as its accepted set.

    The number is not lost, it is relocated to where it can be correct: the tier
    is this enum's job, the rate the line actually carried rides on the
    observation's ``applied_rate``, and the registry dates it. Do not
    reintroduce a percentage into a member name -- the next statute that steps a
    tier makes it false again.
    """

    DOMESTIC_GENERAL = "domestic_general"
    DOMESTIC_REDUCED = "domestic_reduced"
    DOMESTIC_SUPER_REDUCED = "domestic_super_reduced"
    DOMESTIC_ZERO = "domestic_zero"
    DOMESTIC_EXEMPT = "domestic_exempt"
    DOMESTIC_NOT_SUBJECT = "domestic_not_subject"
    DOMESTIC_REVERSE_CHARGE = "domestic_reverse_charge"
    INTRA_COMMUNITY_SUPPLY = "intra_community_supply"
    INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE = "intra_community_acquisition_reverse_charge"
    INTRA_COMMUNITY_TRIANGULATION = "intra_community_triangulation"
    INTRA_COMMUNITY_SERVICE_SUPPLY = "intra_community_service_supply"
    """A service supplied to a business established in another Member State.

    Kept distinct from :attr:`INTRA_COMMUNITY_SUPPLY` because the two carry no
    Spanish cuota for different reasons, and the reason is what a filing cites.
    An entrega intracomunitaria de bienes is EXEMPT under LIVA art. 25 -- the
    operation is located in Spain and the law relieves it. A B2B service is not
    located in Spain at all: art. 69.Uno.1.o places it where the recipient is
    established, so it is NO SUJETA here. Reusing the goods category would put
    art. 25 on a figure art. 25 does not govern.
    """

    INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE = "intra_community_service_acquisition_reverse_charge"
    """A service received from a supplier established in another Member State.

    The mirror of :attr:`INTRA_COMMUNITY_SERVICE_SUPPLY`: art. 69.Uno.1.o
    locates the service in Spain because the recipient is established here, and
    art. 84.Uno.2.o makes that recipient the sujeto pasivo, so the cuota is
    self-assessed. Distinct from
    :attr:`INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE`, which is the goods
    counterpart resting on arts. 13/15.
    """
    EXPORT_THIRD_COUNTRY_ZERO_RATED = "export_third_country_zero_rated"
    EXPORT_ASSIMILATED_ZERO_RATED = "export_assimilated_zero_rated"
    IMPORT_THIRD_COUNTRY = "import_third_country"
    RECARGO_EQUIVALENCIA = "recargo_equivalencia"
    REGIMEN_SIMPLIFICADO = "regimen_simplificado"
    REAGP_COMPENSATION = "reagp_compensation"
    OPERACION_NO_SUJETA = "operacion_no_sujeta"
    ERRONEOUS_INVOICE = "erroneous_invoice"
    UNKNOWN = "unknown"


class IvaCashAccountingTreatment(StrEnum):
    """Independent cash-accounting treatment axis for IVA observations.

    Cash accounting is a settlement-timing and informational-reporting regime,
    not an operation category. The values here deliberately do not overlap with
    :class:`IvaCategory`: a row keeps its domestic/export/intracom/etc.
    category and separately declares whether cash-accounting timing applies.
    """

    NONE = "none"
    TAXPAYER_REGIME = "taxpayer_regime"
    SUPPLIER_REGIME = "supplier_regime"


class IvaLedgerObservationRole(StrEnum):
    """The reporting role of an IVA ledger observation.

    This is deliberately independent from
    :class:`IvaCashAccountingTreatment`.  A cash-accounting operation creates
    an informational art. 75 projection at its operation date and monetary
    settlement projections at each payment (or the statutory fallback) date.
    Both carry the same treatment affiliation, while their role tells registry
    bindings which projection they are permitted to consume.

    Ordinary IVA observations are monetary projections too, so they use
    :attr:`SETTLEMENT`.  That keeps normal IVA bindings on one role while
    reserving :attr:`OPERATION_INFORMATIONAL` for Modelo 303 boxes 62, 63, 74,
    and 75.
    """

    OPERATION_INFORMATIONAL = "operation_informational"
    SETTLEMENT = "settlement"


class IvaCashAccountingPaymentEvidence(BaseModel):
    """Collection/payment evidence for an operation affected by criterio de caja.

    The amounts are the IVA substrate settled by the collection/payment event,
    not a gross bank amount that downstream code must reinterpret. Partial
    evidence therefore remains explicit and auditable.
    """

    model_config = STRICT_FROZEN_CONFIG

    payment_date: date
    taxable_base: Decimal = Field(..., ge=Decimal("0"))
    iva_amount: Decimal = Field(..., ge=Decimal("0"))
    recargo_amount: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))

    @field_validator("payment_date", mode="before")
    @classmethod
    def _parse_payment_date(cls, value: object) -> object:
        if isinstance(value, str):
            return parse_iso8601_date(value)
        return value

    @field_validator("taxable_base", "iva_amount", "recargo_amount", mode="before")
    @classmethod
    def _coerce_decimal_field(cls, value: object) -> object:
        """Accept a JSON-decoded ``Decimal`` string alongside a real ``Decimal``.

        Without this, a ``Transaction`` carrying a populated
        ``cash_accounting_payment_evidence`` tuple cannot round-trip through
        ``Envelope[Transaction].model_validate_json`` at all: pydantic-core
        strict mode rejects the JSON-decoded string for these fields even
        though ``payment_date`` was already coerced above.
        """
        if isinstance(value, str):
            return Decimal(value)
        return value

    @model_validator(mode="after")
    def _require_settlement_amount(self) -> IvaCashAccountingPaymentEvidence:
        if (
            self.taxable_base == Decimal("0")
            and self.iva_amount == Decimal("0")
            and self.recargo_amount == Decimal("0")
        ):
            raise IvaValidationError(
                "cash-accounting payment evidence must carry a non-zero base, IVA, or recargo amount",
            )
        return self

    @field_serializer("taxable_base", "iva_amount", "recargo_amount", when_used="json")
    def _serialize_decimal(self, value: Decimal) -> str:
        return str(value)


# IVA categories that legitimately bear no Modelo 303 cuota by law, so a
# ledger observation in one of these categories correctly matches no
# ``ledger_iva_aggregation`` cuota binding and MUST NOT be treated as a
# modelling gap. They are exempt, zero-rated, not-subject, exempt
# intra-community supplies/exports, or filed under a separate regime:
#
# - DOMESTIC_ZERO / DOMESTIC_EXEMPT / DOMESTIC_NOT_SUBJECT: no cuota
#   devengada arises (Ley 37/1992 arts. 7, 20, 26 exemptions / tipo cero).
# - OPERACION_NO_SUJETA: operación no sujeta — outside the IVA hecho
#   imponible (Ley 37/1992 art. 7).
# - INTRA_COMMUNITY_SUPPLY: entrega intracomunitaria exenta — zero cuota,
#   declared as base only (Ley 37/1992 art. 25, casilla 59).
# - EXPORT_THIRD_COUNTRY_ZERO_RATED / EXPORT_ASSIMILATED_ZERO_RATED:
#   exportación u operación asimilada exenta — zero cuota, base only
#   (Ley 37/1992 arts. 21-22, casilla 60).
# - INTRA_COMMUNITY_SERVICE_SUPPLY: a B2B service supplied to a business in
#   another Member State — no Spanish cuota because art. 69.Uno.1.o locates
#   the operation where the recipient is established, so it is NO SUJETA here
#   rather than exempt. Its received-side counterpart is deliberately ABSENT
#   from this set: art. 84.Uno.2.o makes the Spanish recipient the sujeto
#   pasivo, so that side bears a real self-assessed cuota and must keep firing
#   the unconsumed-declarable advisory until a binding routes it.
# - INTRA_COMMUNITY_TRIANGULATION: operación triangular informativa — no
#   cuota for the Spanish intermediary.
# - REGIMEN_SIMPLIFICADO: settled under the régimen simplificado modulo
#   path (Modelo 131), not the general 303 cuota bindings.
#
# This set is the cuota-less companion to the non-declarable sentinel set
# (recargo de equivalencia / unknown / erroneous) consumed at the
# application boundary. It exists so the #64 unconsumed-declarable advisory
# fires only on categories that genuinely SHOULD produce a 303 cuota but
# currently have no binding (reverse-charge / acquisitions / imports),
# never on these by-law cuota-less categories.
CUOTA_LESS_M303_IVA_CATEGORIES: frozenset[IvaCategory] = frozenset(
    {
        IvaCategory.DOMESTIC_ZERO,
        IvaCategory.DOMESTIC_EXEMPT,
        IvaCategory.DOMESTIC_NOT_SUBJECT,
        IvaCategory.OPERACION_NO_SUJETA,
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
        IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY,
        IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED,
        IvaCategory.INTRA_COMMUNITY_TRIANGULATION,
        IvaCategory.REGIMEN_SIMPLIFICADO,
        # REAGP_COMPENSATION: a farmer under the régimen especial does not
        # repercutir IVA at all — art. 130.Dos gives them a compensación a tanto
        # alzado instead, and art. 134.Uno lets the acquirer deduct its amount.
        # So no general-303 devengada cuota arises on either face, and the
        # advisory would only ever be noise here. The DEDUCTION side is not
        # suppressed by this membership: the evidence advisory reads this set on
        # its output limb only, and the art. 134.Tres self-issued document is
        # enforced by the deduction-fact authority instead.
        IvaCategory.REAGP_COMPENSATION,
    },
)

# Per-modelo (M303) categories genuinely out of scope for the structural
# unrouted-BASE screen (``structurally_unroutable_iva_base_categories``).
#
# This is NOT a re-export of CUOTA_LESS_M303_IVA_CATEGORIES, and reusing that
# set here would be wrong rather than merely redundant. CUOTA_LESS answers
# "does this category produce a cuota?" -- the new screen asks a different
# question, "does this category's BASE reach some casilla?", and several
# by-law cuota-less categories DO carry a real base by law (DOMESTIC_ZERO is
# the clearest instance: zero cuota by definition, but the taxable operation
# still has a real base). Suppressing every CUOTA_LESS member here would
# silence exactly the population the screen exists to surface.
#
# Only four members are genuinely out of scope for a LEDGER-driven base
# screen, because for these the concept of "an independent ledger base this
# mechanism should route" does not apply at all:
#
# - RECARGO_EQUIVALENCIA: the recargo surcharge is levied on the SAME base
#   already reported under the transaction's ordinary general/reduced/
#   super-reducido tier (Ley 37/1992 art. 161); it is not a second,
#   independent taxable amount this screen could find undeclared.
# - REGIMEN_SIMPLIFICADO: settled from módulos, never from ledger rows at
#   all -- a ledger-routing screen has nothing to say about a mechanism the
#   ledger never feeds.
# - ERRONEOUS_INVOICE / UNKNOWN: data-quality sentinels for a row the
#   classifier could not place, not declared economic operations carrying a
#   taxable base of their own.
M303_BASE_OUT_OF_SCOPE_IVA_CATEGORIES: frozenset[IvaCategory] = frozenset(
    {
        IvaCategory.RECARGO_EQUIVALENCIA,
        IvaCategory.REGIMEN_SIMPLIFICADO,
        IvaCategory.ERRONEOUS_INVOICE,
        IvaCategory.UNKNOWN,
    },
)

# IVA categories that never bear a deductible (input) or devengada (output)
# cuota a binding would route, so a missing-evidence advisory on them would be
# noise. Extends the by-law cuota-less set with the non-declarable sentinels
# (recargo de equivalencia is filed under a separate regime; unknown /
# erroneous carry no settled cuota). The single canonical home for this
# derived set — evidence-presence gates and advisories both consume it rather
# than each re-deriving the same extension of CUOTA_LESS_M303_IVA_CATEGORIES.
EVIDENCE_EXEMPT_IVA_CATEGORIES: frozenset[IvaCategory] = CUOTA_LESS_M303_IVA_CATEGORIES | frozenset(
    {
        IvaCategory.RECARGO_EQUIVALENCIA,
        IvaCategory.ERRONEOUS_INVOICE,
        IvaCategory.UNKNOWN,
    },
)

# IVA categories under which the INVOICE ITSELF is printed with no repercutido
# rate and no repercutido cuota on its face.
#
# This answers a different question from CUOTA_LESS_M303_IVA_CATEGORIES, and the
# difference is load-bearing rather than incidental. That set answers "does this
# category produce a cuota on the 303?"; this one answers "does the paper carry a
# tax line?". The two agree everywhere except the reverse-charge family, and they
# disagree there in opposite directions: under inversión del sujeto pasivo the
# recipient self-assesses a real 303 cuota (art. 84.Uno.2.o), which is exactly why
# the received side is deliberately EXCLUDED from the cuota-less set above — while
# the supplier's invoice repercutes nothing and RD 1619/2012 art. 6.1.m requires it
# to say so instead. Reading the 303 set as an answer to the printed question
# therefore omits precisely the highest-frequency no-IVA invoice a Spanish
# autónomo receives, and a reader told such an invoice cannot exist is a reader
# pushed toward supplying the rate it expected to find.
#
# Derived from the closed enum rather than hand-listed, so a category the law
# moves in or out of the printed-tax-bearing set moves here with it.
NO_PRINTED_TAX_IVA_CATEGORIES: frozenset[IvaCategory] = CUOTA_LESS_M303_IVA_CATEGORIES | frozenset(
    {
        IvaCategory.DOMESTIC_REVERSE_CHARGE,
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
    },
)


class IvaExemptionArticle(StrEnum):
    """Closed catalogue of Ley 37/1992 Art. 20 sub-articles.

    The optional discriminator carries a known sub-article alongside the
    generic :attr:`IvaCategory.DOMESTIC_EXEMPT` classification. ``None``
    means no further Art. 20 distinction is available. A stamped value adds
    legal context but does not create a Modelo 303 binding or override the
    generic exempt-operation route.

    The discriminator's legal grounding follows Ley 37/1992
    (BOE-A-1992-28740). Each retained member identifies the matching
    article as classification evidence; it is not an official-form binding.
    """

    ART_20_UNO_8 = "art_20_uno_8"
    """Enseñanza — exenta sin derecho a deducción (Ley 37/1992 Art. 20.Uno.8)."""

    ART_20_UNO_14 = "art_20_uno_14"
    """Sanitarios — exenta sin derecho a deducción (Ley 37/1992 Art. 20.Uno.14)."""

    ART_20_OTHER = "art_20_other"
    """Other Art. 20 sub-articles that do not yet warrant a dedicated
    classification slot."""


class IvaArt69DosService(StrEnum):
    """The twelve services Ley 37/1992 art. 69.Dos excepts from the B2C rule.

    Art. 69.Uno.2.º places a service supplied to someone who is not an
    *empresario o profesional* where the SUPPLIER is established, so a mainland
    issuer's B2C service is realizada en el TAI. Art. 69.Dos excepts these twelve
    from that paragraph when the recipient is established outside the Comunidad
    — and states its own limit in the same sentence: *"salvo en el caso de que
    dicho destinatario esté establecido o tenga su domicilio o residencia
    habitual en las Islas Canarias, Ceuta o Melilla"*.

    **The operator states the item; nothing reads it off the invoice.** The list
    is a closed legal vocabulary fixed by statute, which is what makes it
    readable at all. Deciding from an invoice's own prose which lettered item it
    falls under — "asesoría" implies letter d) — would be a model wearing a
    lookup table: confident on the population it was written against and
    silently wrong everywhere else. ``None`` means no item was stated, which is
    not evidence that none applies; the supply then stays taxed here.

    Two members carry an exclusion the statute writes into the letter itself
    rather than alongside it, and both are load-bearing: letter d) excludes the
    services art. 70.Uno.1.º reaches, and letter j) excludes any means of
    transport and containers.

    See Also:
        :class:`~domain.iva.IvaCategory`
            The catalogue whose not-subject member a declared item reaches.
    """

    ART_69_DOS_A = "art_69_dos_a"
    """Cesiones y concesiones de derechos de autor, patentes, licencias, marcas
    de fábrica o comerciales y demás derechos de propiedad intelectual o
    industrial, así como cualesquiera otros derechos similares."""

    ART_69_DOS_B = "art_69_dos_b"
    """Cesión o concesión de fondos de comercio, de exclusivas de compra o venta
    o del derecho a ejercer una actividad profesional."""

    ART_69_DOS_C = "art_69_dos_c"
    """Los de publicidad."""

    ART_69_DOS_D = "art_69_dos_d"
    """Los de asesoramiento, auditoría, ingeniería, gabinete de estudios,
    abogacía, consultores, expertos contables o fiscales y otros similares, **con
    excepción de los comprendidos en el número 1.º del apartado Uno del artículo
    70** — the land-related services, which that article places where the
    property is."""

    ART_69_DOS_E = "art_69_dos_e"
    """Los de tratamiento de datos y el suministro de informaciones, incluidos
    los procedimientos y experiencias de carácter comercial."""

    ART_69_DOS_F = "art_69_dos_f"
    """Los de traducción, corrección o composición de textos, así como los
    prestados por intérpretes."""

    ART_69_DOS_G = "art_69_dos_g"
    """Los de seguro, reaseguro y capitalización, así como los servicios
    financieros citados por el art. 20.Uno.16.º y 18.º, incluidos los que no
    estén exentos, **con excepción del alquiler de cajas de seguridad**."""

    ART_69_DOS_H = "art_69_dos_h"
    """Los de cesión de personal."""

    ART_69_DOS_I = "art_69_dos_i"
    """El doblaje de películas."""

    ART_69_DOS_J = "art_69_dos_j"
    """Los arrendamientos de bienes muebles corporales, **con excepción de los
    que tengan por objeto cualquier medio de transporte y los contenedores**."""

    ART_69_DOS_K = "art_69_dos_k"
    """La provisión de acceso a las redes de gas natural situadas en el
    territorio de la Comunidad o a cualquier red conectada a dichas redes, a la
    red de electricidad, de calefacción o de refrigeración, y el transporte o
    distribución a través de dichas redes, así como otros servicios directamente
    relacionados con los de esta letra."""

    ART_69_DOS_L = "art_69_dos_l"
    """Las obligaciones de no prestar, total o parcialmente, cualquiera de los
    servicios enunciados en este apartado."""


class EUMemberState(StrEnum):
    """Current EU IVA country prefixes accepted at IVA-facing boundaries.

    The canonical 27 EU member states use ISO 3166-1 alpha-2 codes. ``XI`` is
    the post-Brexit Northern Ireland IVA prefix accepted for goods movements in
    Modelo 349 / intra-community IVA contexts; predicates that need strict
    member-state membership must exclude it explicitly.
    """

    AT = "at"
    BE = "be"
    BG = "bg"
    CY = "cy"
    CZ = "cz"
    DE = "de"
    DK = "dk"
    EE = "ee"
    ES = "es"
    FI = "fi"
    FR = "fr"
    GR = "gr"
    HR = "hr"
    HU = "hu"
    IE = "ie"
    IT = "it"
    LT = "lt"
    LU = "lu"
    LV = "lv"
    MT = "mt"
    NL = "nl"
    PL = "pl"
    PT = "pt"
    RO = "ro"
    SE = "se"
    SI = "si"
    SK = "sk"
    XI = "xi"


class IvaRateKind(StrEnum):
    """Closed catalogue of rate tiers referenced by :class:`IvaRateRecord`."""

    GENERAL = "general"
    REDUCED = "reduced"
    SUPER_REDUCED = "super_reduced"
    ZERO = "zero"
    EXEMPT = "exempt"


_RegistryLegalRef = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=160,
        pattern=r"^[a-z0-9][a-z0-9._:-]*[a-z0-9]$|^[a-z0-9]$",
    ),
]
"""Registry legal-reference identifier; catalogue verification resolves it."""


_RegistrySourceRef = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=160,
        pattern=r"^[a-z0-9][a-z0-9._:-]*[a-z0-9]$|^[a-z0-9]$",
    ),
]
"""Registry source-reference identifier; catalogue verification resolves it."""


_ManualRef = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]
"""Free-form reference to a Manual práctico IVA rule id or section reference."""


class _IvaStrictFrozen(BaseModel):
    """Shared base config: strict validation, immutable, extras forbidden."""

    model_config = STRICT_FROZEN_CONFIG


IvaStrictFrozen = _IvaStrictFrozen


class _IvaStrictMutable(BaseModel):
    """Strict validation mixin with mutable config for incrementally populated catalogues."""

    model_config = ConfigDict(
        strict=True,
        frozen=False,
        extra="forbid",
    )


def _require_grounded_rate_refs(record: IvaRateRecord) -> None:
    """Refuse duplicate, absent, or jurisdiction-inappropriate registry grounding.

    A Spanish rate is established by binding domestic law, so it must cite
    ``legal_refs``; a foreign member-state rate is observed rather than enacted
    here, so it must cite ``source_refs`` instead.
    """
    label = f"IvaRateRecord[{record.member_state.value}/{record.kind.value}]"
    if len(set(record.legal_refs)) != len(record.legal_refs):
        raise IvaValidationError(f"{label}: legal_refs must be unique")
    if len(set(record.source_refs)) != len(record.source_refs):
        raise IvaValidationError(f"{label}: source_refs must be unique")
    if not record.legal_refs and not record.source_refs:
        raise IvaValidationError(f"{label}: missing registry legal_refs/source_refs")
    if record.member_state is EUMemberState.ES and not record.legal_refs:
        raise IvaValidationError(f"{label}: Spanish rates require binding registry legal_refs")
    if record.member_state is not EUMemberState.ES and not record.source_refs:
        raise IvaValidationError(f"{label}: foreign rates require registry source_refs")


class IvaRateRecord(_IvaStrictFrozen):
    """A single IVA rate line item keyed by member state and rate kind.

    Attributes:
        member_state: Issuing member state.
        kind: Rate tier (general / reduced / ...).
        pct: Rate percentage as a :class:`~decimal.Decimal` in ``[0, 100]``.
        effective_from: First date the rate applies.
        effective_until: Last date the rate applies, or ``None`` for
            open-ended.
        legal_refs: Binding registry legal-reference identities backing the
            numerical rate where provision-level authority is bundled.
        source_refs: Registry source-reference identities backing the
            numerical foreign-rate evidence.
    """

    member_state: EUMemberState = Field(description="Issuing member state.")
    kind: IvaRateKind = Field(description="Rate tier (general / reduced / ...).")
    pct: Decimal = Field(
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Rate percentage as a decimal in [0, 100].",
    )
    effective_from: date = Field(description="First date the rate applies.")
    effective_until: date | None = Field(
        default=None,
        description="Last date the rate applies, or ``None`` for open-ended.",
    )
    legal_refs: tuple[_RegistryLegalRef, ...] = Field(
        default=(),
        description="Binding registry legal-reference identities backing this numerical rate.",
    )
    source_refs: tuple[_RegistrySourceRef, ...] = Field(
        default=(),
        description="Registry source-reference identities backing this rate.",
    )
    supersedes_tier_default: bool = Field(
        default=False,
        description="A rate that applies ALONGSIDE its tier's ordinary rate, not instead of it.",
    )
    """Whether this rate coexists with its tier's ordinary rate rather than replacing it.

    ``False`` -- the ordinary case -- means the record IS the tier's rate for its
    window, so :func:`lookup_rate` can answer "what does this tier mean on this
    date" with one record and the no-overlap rule guarantees that answer is
    unambiguous.

    ``True`` marks a rate that a statute applied to PART of a tier's supplies
    while the rest stayed on the ordinary rate. Spain's 2024 anti-inflation
    measures are the worked case: certain foodstuffs moved to 2 % while every
    other super-reducido supply stayed at 4 %, so both were simultaneously
    correct and neither replaced the other (RDL 4/2024 art. 1). Such a record is
    excluded from the no-overlap rule and from :func:`lookup_rate`, because
    including it would make the tier's rate ambiguous for the far larger set of
    supplies that never moved.

    The distinction is which QUESTION each record can answer. A coexisting rate
    cannot answer "what is this tier's rate" -- only the statute's goods scope
    decides that, and no bundled AEAT surface carries a goods axis. It can
    answer "is this declared rate a legitimate one for this tier on this date",
    which is what classification needs and what
    :func:`rate_kinds_for_declared_rate` serves.
    """

    @model_validator(mode="after")
    def _validate_window(self) -> IvaRateRecord:
        """Ensure :attr:`effective_from` precedes :attr:`effective_until`."""
        if self.effective_until is not None and self.effective_from > self.effective_until:
            raise IvaValidationError(
                f"IvaRateRecord[{self.member_state.value}/{self.kind.value}]: "
                f"effective_from {self.effective_from} is after effective_until {self.effective_until}",
            )
        _require_grounded_rate_refs(self)
        return self


class IvaCitation(_IvaStrictFrozen):
    """A legal or regulatory citation backing a :class:`IvaRegulation`.

    :attr:`quoted_text` holds the authoritative Spanish INLINE, not a
    translation key. Verifying a quotation against the bundled corpus requires
    the literal text at the citation site; indirecting it means the record no
    longer carries its own evidence, whatever the key resolves to.

    Attributes:
        legal_reference: Article-qualified registry legal-reference id.
        quoted_text: Verbatim Spanish from the bundled corpus. Empty only when
            :attr:`grounding` is ``UNRESOLVED``.
        grounding: Whether the text was verified or the citation refused.
        unresolved_reason: Why the citation could not be grounded. Required
            when, and only when, :attr:`grounding` is ``UNRESOLVED``.
        valid_from: First date this citation is asserted to support the rule.
        valid_to: Last date, inclusive.

    Both window bounds are required and closed. The span is a grounding claim,
    not bookkeeping: it says the cited provision supports this rule across those
    years, and a gate holds it inside the provision's own effective span in the
    registry legal catalogue. A defaulted or open end would assert grounding
    nobody typed and nothing could check.
    """

    legal_reference: _RegistryLegalRef = Field(
        description="Article-qualified id resolved through the registry legal catalogue.",
    )
    quoted_text: str = Field(
        default="",
        description="Verbatim Spanish from the bundled corpus; empty only when grounding is unresolved.",
    )
    grounding: CitationGrounding = Field(
        default=CitationGrounding.VERIFIED,
        description="Whether the quotation was verified against the corpus, or examined and refused.",
    )
    unresolved_reason: str = Field(
        default="",
        description="Why the citation could not be grounded; required when grounding is unresolved.",
    )
    valid_from: date = Field(
        description="First date this citation is asserted to support the rule.",
    )
    valid_to: date = Field(
        description="Last date, inclusive, this citation is asserted to support the rule.",
    )

    @property
    def window(self) -> ValidityWindow:
        """Return the closed span this citation is asserted over.

        Returns:
            The :class:`~core.validity_window.ValidityWindow` the declared
            bounds describe.
        """
        return ValidityWindow(valid_from=self.valid_from, valid_to=self.valid_to)

    @model_validator(mode="after")
    def _validate(self) -> IvaCitation:
        """Hold each grounding state to the evidence it claims.

        Unlike the validator this replaced, both branches can fail. The old
        one asserted a translatable was non-empty AFTER the loader had already
        resolved it through a fallback that never yields an empty string, so
        it inspected ``"Quoted text"``, found it non-empty, and passed for
        every citation in the catalogue.
        """
        where = f"IvaCitation[{self.legal_reference}]"
        # Constructing the window is the validation: an inverted span covers no
        # year at all, and must refuse where it was written rather than make the
        # citation silently vanish from every filing year downstream.
        _ = self.window
        if self.grounding is CitationGrounding.VERIFIED:
            if not self.quoted_text.strip():
                raise IvaValidationError(f"{where}: a verified citation must carry its verbatim quotation")
            if self.unresolved_reason.strip():
                raise IvaValidationError(f"{where}: a verified citation must not carry an unresolved reason")
        else:
            if not self.unresolved_reason.strip():
                raise IvaValidationError(
                    f"{where}: an unresolved citation must record WHY it could not be grounded, "
                    "so that it reads as examined and refused rather than merely unchecked",
                )
            if self.quoted_text.strip():
                # verify_catalogue deliberately skips the empty-quotation check
                # for this state, so text parked here would never be read
                # against the corpus while the record says it could not be.
                raise IvaValidationError(
                    f"{where}: an unresolved citation must not carry a quotation; "
                    "text that survived the corpus read belongs under verified grounding",
                )
        return self


class IvaRegulation(_IvaStrictFrozen):
    """A single codified IVA rule for a :class:`IvaCategory`.

    Every regulation carries at least one :class:`IvaCitation`. The
    substrate-level invariant enforced by
    :func:`cadrumo.domain.iva.verify_catalogue` additionally requires every
    shipped regulation to cite real legal articles so downstream tools
    can surface the legal backing of any classification.

    Attributes:
        category: The IVA situation codified by this rule.
        requires_reverse_charge: Whether the rule triggers
            *inversión del sujeto pasivo*.
        requires_supplier_iva_id: Whether a supplier NIF-IVA is mandatory.
        manual_references: Optional Manual práctico IVA rule ids or section
            references.
        citations: At least one :class:`IvaCitation` is required, unless
            :attr:`legal_basis_exempt` is set.
        notes: Free-form reviewer notes.
        legal_basis_exempt: True only for a category that codifies no tax
            treatment at all (an application-level classifier sentinel), so
            citing law for it would manufacture the appearance of a legal
            basis a construct without one by design. Citing an unrelated or
            over-broad article is not this: that is a wrong citation on a
            category that DOES need grounding, and must be fixed, not
            exempted.
    """

    category: IvaCategory = Field(description="The IVA situation codified by this rule.")
    requires_reverse_charge: bool = Field(
        description="Whether the rule triggers inversión del sujeto pasivo.",
    )
    requires_supplier_iva_id: bool = Field(
        description="Whether a supplier NIF-IVA is mandatory for this rule.",
    )
    manual_references: tuple[_ManualRef, ...] = Field(
        description="Optional Manual práctico IVA rule ids or section refs.",
    )
    citations: tuple[IvaCitation, ...] = Field(
        description="At least one IvaCitation is required, unless legal_basis_exempt is set.",
    )
    notes: str = Field(
        default="",
        description="Free-form reviewer notes.",
    )
    legal_basis_exempt: bool = Field(
        default=False,
        description="True only for a classifier sentinel that codifies no tax treatment.",
    )

    @model_validator(mode="after")
    def _validate(self) -> IvaRegulation:
        """Enforce the at-least-one-citation invariant and its sole carve-out."""
        if self.legal_basis_exempt:
            if self.citations:
                raise IvaValidationError(
                    f"IvaRegulation[{self.category.value}]: legal_basis_exempt must carry no citations",
                )
            if not self.notes.strip():
                raise IvaValidationError(
                    f"IvaRegulation[{self.category.value}]: legal_basis_exempt requires notes explaining why",
                )
        elif not self.citations:
            raise IvaValidationError(f"IvaRegulation[{self.category.value}]: at least one IvaCitation is required")
        return self


class IvaCatalogue(_IvaStrictMutable):
    """Aggregate view over a collection of :class:`IvaRegulation` records.

    The aggregate is mutable to keep the loader idiom simple — the loader
    populates the mapping incrementally. Individual :class:`IvaRegulation`
    records remain frozen.

    Attributes:
        regulations: Regulations keyed by their
            :class:`IvaCategory`.
    """

    regulations: dict[IvaCategory, IvaRegulation] = Field(
        default_factory=dict,
        description="Regulations keyed by their IvaCategory.",
    )

    @model_validator(mode="after")
    def _check_key_alignment(self) -> IvaCatalogue:
        """Ensure every mapping key matches its record's :attr:`IvaRegulation.category`."""
        for key, regulation in self.regulations.items():
            if key != regulation.category:
                raise IvaValidationError(
                    f"IvaCatalogue: key {key!r} does not match regulation.category {regulation.category!r}",
                )
        return self

    @override
    def __iter__(self) -> Iterator[IvaRegulation]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional Pydantic catalogue iteration adapter; the established public API yields IvaRegulation records, not BaseModel field-value tuples
        """Iterate over every loaded :class:`IvaRegulation`."""
        return iter(self.regulations.values())

    def __len__(self) -> int:
        """Return the number of loaded :class:`IvaRegulation` records."""
        return len(self.regulations)

    def __contains__(self, key: object) -> bool:
        """Return ``True`` when ``key`` names a loaded :class:`IvaCategory`."""
        return key in self.regulations

    def get(self, category: IvaCategory) -> IvaRegulation | None:
        """Return the :class:`IvaRegulation` for ``category`` or ``None`` if absent."""
        return self.regulations.get(category)


class IvaVerificationIssue(_IvaStrictFrozen):
    """A single finding produced by :func:`cadrumo.domain.iva.verify_catalogue`.

    Attributes:
        level: Severity, shared with every other diagnostic and validation
            issue in the project via :class:`~cadrumo.core.errors.BaseSeverity`.
        code: Short stable issue code.
        message: Human-readable detail.
        category_id: Affected IVA category value, if any.
    """

    level: BaseSeverity
    code: str = Field(description="Short, stable issue code.")
    message: str = Field(description="Human-readable detail.")
    category_id: str | None = Field(
        default=None,
        description="Affected IVA category value, if any.",
    )


class IvaVerificationReport(_IvaStrictFrozen):
    """Aggregate verification report for a :class:`IvaCatalogue`.

    Attributes:
        issues: All findings produced by
            :func:`cadrumo.domain.iva.verify_catalogue`.
    """

    issues: tuple[IvaVerificationIssue, ...] = Field(default_factory=tuple)

    @property
    def errors(self) -> tuple[IvaVerificationIssue, ...]:
        """Return the subset of issues at :attr:`~cadrumo.core.errors.BaseSeverity.ERROR`.

        Returns:
            Tuple of :class:`IvaVerificationIssue` objects with error-level severity.
        """
        return tuple(issue for issue in self.issues if issue.level is BaseSeverity.ERROR)

    @property
    def warnings(self) -> tuple[IvaVerificationIssue, ...]:
        """Return the subset of issues at :attr:`~cadrumo.core.errors.BaseSeverity.WARNING`.

        Returns:
            Tuple of :class:`IvaVerificationIssue` objects with warning-level severity.
        """
        return tuple(issue for issue in self.issues if issue.level is BaseSeverity.WARNING)

    @property
    def ok(self) -> bool:
        """Return ``True`` when no error-level issues were found."""
        return not self.errors
