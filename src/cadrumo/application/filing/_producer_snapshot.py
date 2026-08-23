"""Typed, immutable filing producer inputs.

This module owns the filing-instance facts that export consumers need before
they translate them into a revision-specific registry vocabulary.  It does not
own export keys, layout offsets, or rendered record fragments.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar, Final, Literal

from pydantic import BaseModel, StringConstraints, model_validator

from ...core import (
    STRICT_FROZEN_CONFIG,
    Modelo,
    PaymentElection,
    Period,
    PriorDomiciliationElection,
    RefundElection,
    ResultDisposition,
    StandardPeriodCode,
    result_disposition_is_refund,
)
from ...core.identity import SubjectTaxId
from ...domain.bienes_inversion import (
    BienesInversionIvaRegister,
    RegistroRegularizacionResult,
    compute_registro_regularizacion,
)
from ...domain.deadlines import ChargeAccount, ModeloIVAProfile, RefundAccount, TaxpayerProfile
from ...domain.modelos import (
    CalculationRevisionAmendmentKind,
    FilingInstanceEvidence,
    M303Exonerado390FilingEvidence,
    M303InsolvencyFilingFact,
    M303InsolvencyFilingSubtype,
    M303RectificativaMotive,
    M303RegimenSimplificadoCalculationResult,
    M303RegimenSimplificadoFilingEvidence,
    m303_rectificativa_motive_is_applicable,
)
from ...domain.prorrata_register import ProrrataRegister
from ..aggregation import (
    IvaDifferentiatedDeductionContribution,
    M303ProrrataTransitionArrival,
    M303SupplierRegimeArrival,
)

_NonBlankName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
_AeatReceiptNumber = Annotated[str, StringConstraints(pattern=r"^\d{13}$")]
_CnaeCode = Annotated[str, StringConstraints(pattern=r"^\d{4}$")]
_M303_OFFICIAL_FILING_PERIODS: Final[frozenset[StandardPeriodCode]] = frozenset(
    {
        StandardPeriodCode.Q1,
        StandardPeriodCode.Q2,
        StandardPeriodCode.Q3,
        StandardPeriodCode.Q4,
        StandardPeriodCode.JAN,
        StandardPeriodCode.FEB,
        StandardPeriodCode.MAR,
        StandardPeriodCode.APR,
        StandardPeriodCode.MAY,
        StandardPeriodCode.JUN,
        StandardPeriodCode.JUL,
        StandardPeriodCode.AUG,
        StandardPeriodCode.SEP,
        StandardPeriodCode.OCT,
        StandardPeriodCode.NOV,
        StandardPeriodCode.DEC,
    },
)


class FilingProducerSnapshotError(ValueError):
    """Raised when filing facts cannot form a complete producer snapshot."""

    __bare_base_rationale__: ClassVar[str] = "internal-filing-producer-snapshot-validation-carrier"


def assert_m303_regularisation_result_matches_bienes_register(
    *,
    bienes_register: BienesInversionIvaRegister,
    regularisation_result: RegistroRegularizacionResult,
) -> None:
    """Refuse a result that is not the register's exact annual projection.

    The result rows carry the definitive prorrata facts used to produce them,
    so replay the canonical domain projection from those facts and compare the
    complete immutable result.  This admits no result-row omission, foreign
    register, substituted contribution, or invented pending state.
    """
    canonical = compute_registro_regularizacion(
        bienes_register,
        regularizacion_year=regularisation_result.regularizacion_year,
        prorrata_definitiva_by_identifier={
            row.identifier: row.prorrata_anio_pct
            for row in regularisation_result.rows
            if row.prorrata_anio_pct is not None
        },
    )
    if regularisation_result != canonical:
        raise ValueError("M303 regularisation result must be the canonical projection of the supplied Bienes register")


def _require_m303_official_filing_period(period: Period) -> None:
    """Refuse non-303 periods before they can reach DP30301's producer fields."""
    if period.standard_code not in _M303_OFFICIAL_FILING_PERIODS:
        raise ValueError(
            "Modelo 303 filing facts require an official quarterly or monthly period "
            f"(1T-4T or 01-12), got {period.registry_token!r}",
        )


class PresenterIdentity(BaseModel):
    """Identity of the presenter for this filing instance.

    Presenter identity is deliberately separate from taxpayer identity.  A
    caller must supply it; no taxpayer-to-presenter fallback exists here.
    """

    model_config = STRICT_FROZEN_CONFIG

    tax_id: SubjectTaxId
    full_name: _NonBlankName


class TaxpayerIdentityFacts(BaseModel):
    """Explicit taxpayer name facts for one filing instance.

    The four fields model distinct official producer meanings.  They are not
    interchangeable aliases: a revision requiring one of them must receive
    that exact fact, and an absent fact remains absent.
    """

    model_config = STRICT_FROZEN_CONFIG

    legal_name: _NonBlankName | None
    given_name: _NonBlankName | None
    surnames: _NonBlankName | None
    full_name: _NonBlankName | None


class DeclarationContactFacts(BaseModel):
    """The "persona con quien relacionarse" AEAT asks for on an informativa.

    Distinct from both :class:`TaxpayerIdentityFacts` and
    :class:`PresenterIdentity`: AEAT reserves this pair for whoever it should
    contact ABOUT the declaration, which under a gestor is routinely neither
    the taxpayer nor the transmitting presenter. Filling it from either would
    name the wrong person on a live filing, which is why it is its own fact.

    Both halves are optional and absent stays absent -- AEAT's global rule for
    the informativa header is that an alphanumeric field with no content is
    written to blancos, so an unsupplied contact is a legal filing rather than
    a defect.
    """

    model_config = STRICT_FROZEN_CONFIG

    phone: _NonBlankName | None = None
    full_name: _NonBlankName | None = None
    #: AEAT reserves a second telephone and an e-mail beside the pair above on the
    #: informativa header -- modelo 210 cites both. They were absent here, so the layout's
    #: fields resolved to nothing and rendered blank.
    secondary_phone: _NonBlankName | None = None
    email: _NonBlankName | None = None


class Modelo111ProfileFacts(BaseModel):
    """Stable Modelo 111 profile facts consumed by a filing producer."""

    model_config = STRICT_FROZEN_CONFIG

    colegio_concertado: bool | None


_GrupoNumber = Annotated[str, StringConstraints(min_length=1, max_length=7)]
_ForalTerritory = Annotated[str, StringConstraints(min_length=1, max_length=2)]


class Modelo222ProfileFacts(BaseModel):
    """Fiscal-group identity and régimen facts a Modelo 222 filing declares.

    Modelo 222 is the pago fraccionado of a *grupo fiscal*, so the group's own identity is
    not optional context -- it is what the return is about. AEAT's design prescribes a
    format for the número de grupo (``Nota 8``: ``----/--`` estatal, ``---/--A`` foral),
    which is a rule about content, not about an empty field.

    Before this type existed the twenty-three ``m222.*`` producer keys were declared in the
    vocabulary and resolved by nothing, so every one of them rendered blank on a
    non-required field and the return emitted with its group number and its entidad
    dominante empty.

    Every field below is optional EXCEPT the group identity, because AEAT's own design
    leaves the régimen marks blank when they do not apply, and a mark that does not apply
    is genuinely absent rather than unknown. The group number and the dominante are not in
    that category.
    """

    model_config = STRICT_FROZEN_CONFIG

    numero_grupo: _GrupoNumber
    entidad_dominante_identificacion: str
    entidad_dominante_razon_social: str
    #: "1" representante (entidad no dominante), "2" dominante incluida en el grupo fiscal.
    representante_o_dominante: str | None = None
    normativa_territorio_foral: str | None = None
    entidad_dominante_pais_territorio_foral: _ForalTerritory | None = None
    fecha_inicio_periodo_impositivo: str | None = None
    cnae_actividad_principal: _CnaeCode | None = None
    regimen_entidades_navieras_tonelaje: str | None = None
    regimen_reducida_dimension: str | None = None
    cifra_negocios_grupo_doce_meses: str | None = None
    cooperativa_fiscalmente_protegida: str | None = None
    regimen_entidades_capital_riesgo: str | None = None
    circunstancia_concurrente: str | None = None
    cifra_negocios_periodo_anterior_tramo: str | None = None
    multiples_tipos_impositivos: str | None = None
    tipo_gravamen_impuesto_sociedades: str | None = None
    importe_neto_cifra_negocios_tramo: str | None = None
    modalidad_liquidacion: str | None = None
    comunicacion_datos_adicionales: str | None = None
    numero_referencia_sociedades: str | None = None
    comunicacion_variacion_composicion_grupo: str | None = None
    numero_referencia_sociedades_variacion: str | None = None


_M353GrupoNumber = Annotated[str, StringConstraints(min_length=1, max_length=10)]
_SiNoMark = Annotated[str, StringConstraints(pattern=r"^[12]$")]
_XOrBlankMark = Annotated[str, StringConstraints(pattern=r"^X$")]


class Modelo353ProfileFacts(BaseModel):
    """Grupo de entidades IVA identity and régimen marks a Modelo 353 filing declares.

    Modelo 353 is the *autoliquidación agregada* of the régimen especial del grupo de
    entidades (LIVA art. 163 sexies), so the group's number is what the return is about
    rather than optional colour.

    Before this type existed the five ``m353.*`` producer keys were declared in the
    vocabulary and resolved by nothing, so the número de grupo and the two marks rendered
    from whatever the field's ``required`` flag allowed.

    ``numero_grupo`` is required here. The two régimen marks are required too, and that is
    a departure from the Modelo 222 shape for a grounded reason: AEAT's design gives them
    ``1 -Sí, 2 -No`` and the published layout marks both ``required = true``, so there is
    no blank state to represent -- a filer who is not inscrito declares ``"2"``, not
    nothing. ``sin_actividad`` and ``grupo_normativa_foral`` are the genuinely optional
    ones: the design reads ``X o blanco``.
    """

    model_config = STRICT_FROZEN_CONFIG

    #: Identificación. Nº Grupo -- design offset 109, length 10.
    numero_grupo: _M353GrupoNumber
    #: Tipo régimen especial aplicable, art. 163 sexies.cinco: "1" sí, "2" no.
    regimen_especial_avanzado_elected: _SiNoMark
    #: Inscrito en el Registro de devolución mensual (art. 30 RIVA): "1" sí, "2" no.
    regimen_especial_inscrito_redeme: _SiNoMark
    #: "X o blanco" in the design; absent means the group had activity.
    sin_actividad: _XOrBlankMark | None = None
    #: "X o blanco" in the design; absent means the group is not sometido a normativa foral.
    grupo_normativa_foral: _XOrBlankMark | None = None


class GeneralFilingProfileFacts(BaseModel):
    """Explicit absence of modelo-specific producer facts for a layout."""

    model_config = STRICT_FROZEN_CONFIG


class Modelo202ActivityFacts(BaseModel):
    """One repeatable M202 activity fact, without claiming primacy."""

    model_config = STRICT_FROZEN_CONFIG

    cnae: _CnaeCode


class M202UnsupportedProducerId(StrEnum):
    """M202 producer facts that are not yet admitted to the typed substrate."""

    PRINCIPAL_CNAE = "m202.principal_cnae"
    OFFICIAL_OFFSET_122 = "m202.official_offset_122"
    OFFICIAL_OFFSET_123 = "m202.official_offset_123"
    OFFICIAL_OFFSET_124 = "m202.official_offset_124"
    OFFICIAL_OFFSET_125 = "m202.official_offset_125"
    OFFICIAL_OFFSET_126 = "m202.official_offset_126"
    OFFICIAL_OFFSET_127 = "m202.official_offset_127"
    OFFICIAL_OFFSET_128 = "m202.official_offset_128"
    OFFICIAL_OFFSET_129 = "m202.official_offset_129"
    OFFICIAL_OFFSET_130 = "m202.official_offset_130"
    OFFICIAL_OFFSET_131 = "m202.official_offset_131"
    OFFICIAL_OFFSET_132 = "m202.official_offset_132"
    OFFICIAL_OFFSET_147 = "m202.official_offset_147"


M202_UNSUPPORTED_PRODUCER_IDS: tuple[M202UnsupportedProducerId, ...] = tuple(M202UnsupportedProducerId)


class Modelo202ProducerProfile(BaseModel):
    """M202 producer view referencing the canonical taxpayer profile owner.

    The régimen marks and the principal CNAE below are what modelo 202's export layout
    cites as header producers. Before they existed the eighteen ``m202.*`` keys were
    declared in the vocabulary and resolved by nothing, so each one rendered blank on a
    filed pago fraccionado.

    ``principal_cnae`` is DECLARED, never inferred from ``activities``:
    :class:`Modelo202ActivityFacts` is documented as "one repeatable M202 activity fact,
    without claiming primacy", so picking the first or the largest would invent a primacy
    the substrate deliberately does not carry. AEAT asks which activity is principal, so
    the operator answers it.

    Every mark is optional and absent stays absent -- AEAT leaves a régimen mark blank when
    the régimen does not apply, and a mark that does not apply is genuinely absent rather
    than unknown.
    """

    model_config = STRICT_FROZEN_CONFIG

    taxpayer_profile: TaxpayerProfile
    activities: tuple[Modelo202ActivityFacts, ...]
    principal_cnae: _CnaeCode | None = None
    regimen_ley_49_2002_sin_fines_lucrativos: str | None = None
    regimen_ley_11_2009_socimi: str | None = None
    regimen_entidades_navieras_tonelaje: str | None = None
    regimen_articulo_101_lis_reducida_dimension: str | None = None
    regimen_entidad_capital_riesgo: str | None = None
    cifra_negocios_doce_meses_umbral: str | None = None
    cifra_negocios_periodo_anterior_bajo_umbral: str | None = None
    cooperativa_o_multiples_tipos: str | None = None
    cooperativa_fiscalmente_protegida: str | None = None
    multiples_tipos_impositivos: str | None = None
    tipo_gravamen_impuesto_sociedades: str | None = None
    importe_neto_cifra_negocios_tramo: str | None = None
    marca_instrumental: str | None = None
    discriminante_declaracion_negativa: str | None = None
    normativa_territorio_foral: str | None = None
    comunicacion_datos_adicionales: str | None = None
    numero_referencia_sociedades: str | None = None

    @property
    def unsupported_producer_ids(self) -> tuple[M202UnsupportedProducerId, ...]:
        """Return the exact immutable M202 producer-gap inventory."""
        return M202_UNSUPPORTED_PRODUCER_IDS


class FilingElectionFacts(BaseModel):
    """Immutable operator elections and their resolved result disposition."""

    model_config = STRICT_FROZEN_CONFIG

    result_disposition: ResultDisposition
    payment: PaymentElection
    refund: RefundElection
    prior_domiciliation: PriorDomiciliationElection


class M303FilingFacts(BaseModel):
    """DP30301 facts owned by one immutable Modelo 303 filing instance."""

    model_config = STRICT_FROZEN_CONFIG

    joint_return_elected: bool
    annual_volume_nonzero: bool
    insolvency: M303InsolvencyFilingFact | None
    exonerado_390: M303Exonerado390FilingEvidence
    regimen_simplificado: M303RegimenSimplificadoFilingEvidence
    regimen_simplificado_result: M303RegimenSimplificadoCalculationResult
    period: Period
    supplier_regime: M303SupplierRegimeArrival
    prorrata_transition: M303ProrrataTransitionArrival
    prorrata_register: ProrrataRegister
    differentiated_contributions: tuple[IvaDifferentiatedDeductionContribution, ...]
    bienes_register: BienesInversionIvaRegister
    regularisation_result: RegistroRegularizacionResult

    @model_validator(mode="after")
    def _arrivals_share_one_filing_period(self) -> M303FilingFacts:
        _validate_m303_filing_periods(self)
        _validate_m303_calculation_results(self)
        _validate_m303_register_evidence(self)
        return self


def _validate_m303_filing_periods(facts: M303FilingFacts) -> None:
    _require_m303_official_filing_period(facts.period)
    if facts.period != facts.supplier_regime.period or facts.period != facts.prorrata_transition.period:
        raise ValueError("M303 filing facts and arrivals must share one filing period")
    if facts.regularisation_result.regularizacion_year != facts.period.filing_year:
        raise ValueError("M303 regularisation result must use the filing year")


def _validate_m303_calculation_results(facts: M303FilingFacts) -> None:
    if facts.regimen_simplificado_result != facts.regimen_simplificado.calculation_result:
        raise ValueError("M303 filing facts must retain the exact simplified-regime calculation result")
    if facts.regimen_simplificado_result.period != facts.period:
        raise ValueError("M303 filing facts and simplified-regime result must share one filing period")


def _validate_m303_register_evidence(facts: M303FilingFacts) -> None:
    assert_m303_regularisation_result_matches_bienes_register(
        bienes_register=facts.bienes_register,
        regularisation_result=facts.regularisation_result,
    )
    if facts.prorrata_transition.is_applicable and not facts.prorrata_register.has_complete_current_entry_coverage(
        facts.period.filing_year
    ):
        raise ValueError("M303 final-period filing facts require complete current-year prorrata register coverage")
    for entry in facts.prorrata_transition.register_evidence:
        if facts.prorrata_register.entry_for(entry.ejercicio, sector_id=entry.sector_id) != entry:
            raise ValueError("M303 prorrata transition arrival evidence must belong to the supplied register")


def resolve_m303_filing_facts(
    *,
    evidence: FilingInstanceEvidence,
    supplier_regime: M303SupplierRegimeArrival,
    prorrata_transition: M303ProrrataTransitionArrival,
    prorrata_register: ProrrataRegister,
    differentiated_contributions: tuple[IvaDifferentiatedDeductionContribution, ...],
    bienes_register: BienesInversionIvaRegister,
    regularisation_result: RegistroRegularizacionResult,
) -> M303FilingFacts:
    """Project persisted M303 evidence together with canonical arrival facts."""
    m303 = evidence.m303
    _require_m303_official_filing_period(m303.period)
    return M303FilingFacts(
        joint_return_elected=m303.joint_return_elected,
        annual_volume_nonzero=m303.annual_volume_nonzero,
        insolvency=m303.insolvency,
        exonerado_390=m303.exonerado_390,
        regimen_simplificado=m303.regimen_simplificado,
        regimen_simplificado_result=m303.regimen_simplificado.calculation_result,
        period=m303.period,
        supplier_regime=supplier_regime,
        prorrata_transition=prorrata_transition,
        prorrata_register=prorrata_register,
        differentiated_contributions=differentiated_contributions,
        bienes_register=bienes_register,
        regularisation_result=regularisation_result,
    )


class AmendmentEvidence(BaseModel):
    """Typed evidence for an amendment of an AEAT-accepted filing."""

    model_config = STRICT_FROZEN_CONFIG

    kind: CalculationRevisionAmendmentKind
    m303_rectificativa_motive: M303RectificativaMotive | None
    original_aeat_receipt: _AeatReceiptNumber

    @model_validator(mode="after")
    def _motive_belongs_only_to_rectificativa(self) -> AmendmentEvidence:
        if (
            self.m303_rectificativa_motive is not None
            and self.kind is not CalculationRevisionAmendmentKind.RECTIFICATIVA
        ):
            raise ValueError("M303 rectificativa motive is valid only for rectificativa evidence")
        return self

    @property
    def is_complementaria(self) -> bool:
        return self.kind is CalculationRevisionAmendmentKind.COMPLEMENTARIA

    @property
    def is_sustitutiva(self) -> bool:
        return self.kind is CalculationRevisionAmendmentKind.SUSTITUTIVA

    @property
    def is_rectificativa(self) -> bool:
        return self.kind is CalculationRevisionAmendmentKind.RECTIFICATIVA


class RefundAccountSelection(BaseModel):
    """Secure account selected for a refund disposition."""

    model_config = STRICT_FROZEN_CONFIG

    role: Literal["refund"]
    account: RefundAccount


class ChargeAccountSelection(BaseModel):
    """Secure account selected for a direct-debit disposition."""

    model_config = STRICT_FROZEN_CONFIG

    role: Literal["charge"]
    account: ChargeAccount


type SelectedFilingAccount = RefundAccountSelection | ChargeAccountSelection
type FilingModelProfileFacts = (
    GeneralFilingProfileFacts
    | Modelo111ProfileFacts
    | Modelo202ProducerProfile
    | Modelo222ProfileFacts
    | Modelo353ProfileFacts
    | ModeloIVAProfile
)


class FilingProducerSnapshot(BaseModel):
    """Complete immutable filing facts before registry-specific translation."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: Modelo
    taxpayer_tax_id: SubjectTaxId
    taxpayer_identity: TaxpayerIdentityFacts
    presenter: PresenterIdentity
    #: Defaulted rather than required: every existing caller predates this fact
    #: and none of them can supply it, so demanding it would refuse filings that
    #: are legal without it. An absent contact renders as blancos, which is what
    #: AEAT's own header rule prescribes.
    declaration_contact: DeclarationContactFacts = DeclarationContactFacts()
    model_profile: FilingModelProfileFacts
    elections: FilingElectionFacts
    amendment_evidence: AmendmentEvidence | None
    selected_account: SelectedFilingAccount | None
    m303_filing_facts: M303FilingFacts | None

    @model_validator(mode="after")
    def _validate_model_profile(self) -> FilingProducerSnapshot:
        _validate_snapshot_model_profile(self)
        _validate_snapshot_account_selection(self)
        _validate_snapshot_profile_secrecy(self)
        return self


def _validate_snapshot_model_profile(snapshot: FilingProducerSnapshot) -> None:
    if snapshot.modelo is not Modelo.M303 and snapshot.m303_filing_facts is not None:
        raise ValueError("M303FilingFacts are valid only for modelo 303")
    if (
        snapshot.modelo is not Modelo.M303
        and snapshot.amendment_evidence is not None
        and snapshot.amendment_evidence.m303_rectificativa_motive is not None
    ):
        raise ValueError("M303 rectificativa motive is valid only for modelo 303")
    if snapshot.modelo is Modelo.M111:
        _validate_modelo_111_snapshot(snapshot)
        return
    if snapshot.modelo is Modelo.M202:
        _validate_modelo_202_snapshot(snapshot)
        return
    if snapshot.modelo is Modelo.M222:
        _validate_modelo_222_snapshot(snapshot)
        return
    if snapshot.modelo is Modelo.M303:
        _validate_modelo_303_snapshot(snapshot)
        return
    if snapshot.modelo is Modelo.M353:
        _validate_modelo_353_snapshot(snapshot)
        return
    _validate_general_modelo_snapshot(snapshot)


def _validate_modelo_353_snapshot(snapshot: FilingProducerSnapshot) -> None:
    """Modelo 353 is the grupo de entidades aggregate; it cannot be filed without it."""
    if not isinstance(snapshot.model_profile, Modelo353ProfileFacts):
        raise ValueError("modelo 353 requires Modelo353ProfileFacts")


def _validate_modelo_222_snapshot(snapshot: FilingProducerSnapshot) -> None:
    """Modelo 222 is a grupo fiscal return; it cannot be filed without the group."""
    if not isinstance(snapshot.model_profile, Modelo222ProfileFacts):
        raise ValueError("modelo 222 requires Modelo222ProfileFacts")


def _validate_modelo_111_snapshot(snapshot: FilingProducerSnapshot) -> None:
    if not isinstance(snapshot.model_profile, Modelo111ProfileFacts):
        raise ValueError("modelo 111 requires Modelo111ProfileFacts")
    if snapshot.model_profile.colegio_concertado is None:
        raise ValueError("Modelo 111 colegio_concertado must be explicitly declared")


def _validate_modelo_202_snapshot(snapshot: FilingProducerSnapshot) -> None:
    if not isinstance(snapshot.model_profile, Modelo202ProducerProfile):
        raise ValueError("modelo 202 requires Modelo202ProducerProfile")
    unsupported = ", ".join(item.value for item in snapshot.model_profile.unsupported_producer_ids)
    raise ValueError(f"Modelo 202 producer snapshot is incomplete: {unsupported}")


def _validate_modelo_303_snapshot(snapshot: FilingProducerSnapshot) -> None:
    if not isinstance(snapshot.model_profile, ModeloIVAProfile):
        raise ValueError("modelo 303 requires the canonical ModeloIVAProfile")
    if snapshot.m303_filing_facts is None:
        raise ValueError("modelo 303 requires complete M303FilingFacts")
    amendment = snapshot.amendment_evidence
    motive_applicable = m303_rectificativa_motive_is_applicable(
        registry_revision_id=snapshot.m303_filing_facts.regimen_simplificado.regimen_snapshot.orden.registry_revision_id,
        record_design=snapshot.m303_filing_facts.regimen_simplificado.regimen_snapshot.record_design,
    )
    has_rectificativa = amendment is not None and amendment.is_rectificativa
    has_motive = amendment is not None and amendment.m303_rectificativa_motive is not None
    if motive_applicable and has_rectificativa != has_motive:
        raise ValueError("applicable M303 rectificativa evidence requires exactly one canonical motive")
    if not motive_applicable and has_motive:
        raise ValueError("M303 rectificativa motive is prohibited outside the admitted record-design sources")


def _validate_general_modelo_snapshot(snapshot: FilingProducerSnapshot) -> None:
    if not isinstance(snapshot.model_profile, GeneralFilingProfileFacts):
        raise ValueError(f"modelo {snapshot.modelo.value} requires GeneralFilingProfileFacts")


def _validate_snapshot_account_selection(snapshot: FilingProducerSnapshot) -> None:
    disposition = snapshot.elections.result_disposition
    if disposition is ResultDisposition.DOMICILIACION:
        if snapshot.elections.payment is not PaymentElection.DOMICILIACION:
            raise ValueError("domiciliacion disposition requires the matching payment election")
        if not isinstance(snapshot.selected_account, ChargeAccountSelection):
            raise ValueError("domiciliacion disposition requires a selected charge account")
    elif snapshot.elections.payment is PaymentElection.DOMICILIACION:
        raise ValueError("domiciliacion payment election requires the matching result disposition")
    elif result_disposition_is_refund(disposition):
        if not isinstance(snapshot.selected_account, RefundAccountSelection):
            raise ValueError("refund disposition requires a selected refund account")
    elif snapshot.selected_account is not None:
        raise ValueError("a result disposition without an account must not retain one")


def _validate_snapshot_profile_secrecy(snapshot: FilingProducerSnapshot) -> None:
    profile_iva = _profile_iva(snapshot.model_profile)
    if profile_iva is not None and (profile_iva.refund_account is not None or profile_iva.charge_account is not None):
        raise ValueError("model profile must not retain accounts outside selected_account")


def _profile_iva(model_profile: FilingModelProfileFacts) -> ModeloIVAProfile | None:
    if isinstance(model_profile, ModeloIVAProfile):
        return model_profile
    if isinstance(model_profile, Modelo202ProducerProfile):
        return model_profile.taxpayer_profile.iva
    return None


def build_filing_producer_snapshot(
    *,
    modelo: Modelo,
    taxpayer_tax_id: SubjectTaxId,
    taxpayer_identity: TaxpayerIdentityFacts,
    presenter: PresenterIdentity,
    model_profile: FilingModelProfileFacts,
    elections: FilingElectionFacts,
    amendment_evidence: AmendmentEvidence | None,
    refund_account: RefundAccount | None,
    charge_account: ChargeAccount | None,
    m303_filing_facts: M303FilingFacts | None,
    declaration_contact: DeclarationContactFacts | None = None,
) -> FilingProducerSnapshot:
    """Build a snapshot retaining only the account selected by disposition.

    ``declaration_contact`` is optional so every caller that predates the
    informativa contact fact keeps working unchanged; an absent contact renders
    as blancos, which is what AEAT's own header rule prescribes.
    """
    safe_model_profile = _without_embedded_accounts(model_profile)
    selected_account: SelectedFilingAccount | None
    if elections.result_disposition is ResultDisposition.DOMICILIACION:
        if charge_account is None:
            raise FilingProducerSnapshotError("domiciliacion requires a charge account")
        selected_account = ChargeAccountSelection(role="charge", account=charge_account)
    elif result_disposition_is_refund(elections.result_disposition):
        if refund_account is None or refund_account.iban is None:
            raise FilingProducerSnapshotError("refund disposition requires a refund account")
        selected_account = RefundAccountSelection(role="refund", account=refund_account)
    else:
        selected_account = None

    try:
        return FilingProducerSnapshot(
            modelo=modelo,
            taxpayer_tax_id=taxpayer_tax_id,
            taxpayer_identity=taxpayer_identity,
            presenter=presenter,
            model_profile=safe_model_profile,
            elections=elections,
            amendment_evidence=amendment_evidence,
            selected_account=selected_account,
            m303_filing_facts=m303_filing_facts,
            declaration_contact=declaration_contact or DeclarationContactFacts(),
        )
    except ValueError as exc:
        raise FilingProducerSnapshotError(str(exc)) from exc


def _without_embedded_accounts(model_profile: FilingModelProfileFacts) -> FilingModelProfileFacts:
    if isinstance(model_profile, ModeloIVAProfile):
        return model_profile.model_copy(update={"refund_account": None, "charge_account": None})
    if isinstance(model_profile, Modelo202ProducerProfile):
        taxpayer_profile = model_profile.taxpayer_profile
        if taxpayer_profile.iva is None:
            return model_profile
        safe_iva = taxpayer_profile.iva.model_copy(update={"refund_account": None, "charge_account": None})
        safe_taxpayer = taxpayer_profile.model_copy(update={"iva": safe_iva})
        return model_profile.model_copy(update={"taxpayer_profile": safe_taxpayer})
    return model_profile


__all__ = [
    "M202_UNSUPPORTED_PRODUCER_IDS",
    "AmendmentEvidence",
    "ChargeAccountSelection",
    "FilingElectionFacts",
    "FilingModelProfileFacts",
    "FilingProducerSnapshot",
    "FilingProducerSnapshotError",
    "GeneralFilingProfileFacts",
    "M202UnsupportedProducerId",
    "M303FilingFacts",
    "M303InsolvencyFilingFact",
    "M303InsolvencyFilingSubtype",
    "Modelo111ProfileFacts",
    "Modelo202ActivityFacts",
    "Modelo202ProducerProfile",
    "PresenterIdentity",
    "RefundAccountSelection",
    "SelectedFilingAccount",
    "TaxpayerIdentityFacts",
    "assert_m303_regularisation_result_matches_bienes_register",
    "build_filing_producer_snapshot",
    "resolve_m303_filing_facts",
]
