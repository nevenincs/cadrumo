"""Typed, immutable filing producer inputs.

This module owns the filing-instance facts that export consumers need before
they translate them into a revision-specific registry vocabulary.  It does not
own export keys, layout offsets, or rendered record fragments.

Core types:
:class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import AfterValidator, BaseModel, StringConstraints, ValidationError, model_validator

from cadrumo.domain.calculations.registry.tax_id_format import SubjectTaxId

from ...core.errors.hierarchy import CadrumoError, pydantic_validation_boundary
from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.payment_election import PaymentElection
from ...core.period import Period, StandardPeriodCode
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.refund_election import RefundElection
from ...core.result_disposition import ResultDisposition, result_disposition_is_refund
from ...domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
    RegistroRegularizacionResult,
    compute_registro_regularizacion,
)
from ...domain.bienes_inversion.regularizacion_parameters import (
    BienesInversionRegularizacionParameters,
)
from ...domain.calculations.registry.form_codes import form_width_validator
from ...domain.deadlines.models import ChargeAccount, ModeloIVAProfile, RefundAccount, TaxpayerProfile
from ...domain.iva.refund_eligibility import is_last_filing_period_of_year
from ...domain.modelos.calculation_revision_amendment import (
    CalculationRevisionAmendmentKind,
    M303RectificativaMotive,
    m303_rectificativa_motive_is_applicable,
)
from ...domain.modelos.calculation_revision_m303_evidence import (
    M303Exonerado390FilingEvidence,
    M303InsolvencyFilingFact,
    M303InsolvencyFilingSubtype,
    M303RegimenSimplificadoCalculationResult,
)
from ...domain.modelos.calculation_revision_m303_handoff import (
    FilingInstanceEvidence,
    M303RegimenSimplificadoFilingEvidence,
)
from ...domain.prorrata_register.register import ProrrataRegister
from ..aggregation.iva_ledger import (
    IvaDifferentiatedDeductionContribution,
)
from ..aggregation.m303_arrivals import (
    M303ProrrataTransitionArrival,
    M303SupplierRegimeArrival,
)
from ._producer_snapshot_m390 import M390FilingFacts as _M390FilingFacts
from .producer_snapshot_m200 import Modelo200ProfileFacts
from .producer_snapshot_m210 import Modelo210ProfileFacts
from .producer_snapshot_m296 import Modelo296ProfileFacts
from .producer_snapshot_m360 import Modelo360ProfileFacts

_NonBlankName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
_AeatReceiptNumber = Annotated[
    str,
    StringConstraints(pattern=r"^\d+$", max_length=16),
    AfterValidator(form_width_validator("aeat.receipt_digits")),
]
_CnaeCode = Annotated[
    str,
    StringConstraints(pattern=r"^\d+$", max_length=16),
    AfterValidator(form_width_validator("cnae.digits")),
]
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


class FilingProducerSnapshotError(CadrumoError):
    """Raised when filing facts cannot form a complete producer snapshot."""


def assert_m303_regularisation_result_matches_bienes_register(
    *,
    bienes_register: BienesInversionIvaRegister,
    regularisation_result: RegistroRegularizacionResult,
    parameters: BienesInversionRegularizacionParameters,
) -> None:
    """Refuse a result that is not the register's exact annual projection.

    The result rows carry the definitive prorrata facts used to produce them,
    so replay the canonical domain projection from those facts and compare the
    complete immutable result.  This admits no result-row omission, foreign
    register, substituted contribution, or invented pending state.

    The result also carries the registry declaration its figures came from, and
    that is checked against ``parameters`` FIRST and by identity rather than by
    replay.  A result produced under a different revision would otherwise be
    silently re-derived under this one and compared against itself, so the
    provenance check is what stops the replay from confirming the wrong law.
    """
    if regularisation_result.parameters_provenance != parameters.provenance:
        raise ValueError(
            "M303 regularisation result was produced from registry declaration "
            f"{regularisation_result.parameters_provenance.modelo_id}/"
            f"{regularisation_result.parameters_provenance.revision_id}"
            f"@{regularisation_result.parameters_provenance.resolved_on.isoformat()}, "
            "not from the supplied "
            f"{parameters.provenance.modelo_id}/{parameters.provenance.revision_id}"
            f"@{parameters.provenance.resolved_on.isoformat()}",
        )
    canonical = compute_registro_regularizacion(
        bienes_register,
        regularizacion_year=regularisation_result.regularizacion_year,
        prorrata_definitiva_by_identifier={
            row.identifier: row.prorrata_anio_pct
            for row in regularisation_result.rows
            if row.prorrata_anio_pct is not None
        },
        parameters=parameters,
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

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _refuse_entity_and_person_names_together(self) -> TaxpayerIdentityFacts:
        """An entity carries a legal name; a natural person carries given name and surnames.

        The two are exclusive by meaning, and the export reads the taxpayer's
        legal form from which of them is present. Holding both would let a
        requirement stated for natural persons be judged against an entity.
        """
        if self.legal_name is not None and (self.given_name is not None or self.surnames is not None):
            raise ValueError("taxpayer identity cannot carry both an entity legal name and personal names")
        return self


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
    #: The 2023-2024 diseño's single enumerated slot covering both the cooperativa
    #: fiscalmente protegida and the "dos tipos impositivos" question: "0" no consta,
    #: "1" grupo de cooperativas, "2" otros grupos fiscales. The 2025 diseño asks the
    #: two questions separately through the fields above and below.
    cooperativa_o_multiples_tipos: str | None = None
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

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

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

    result_disposition: ResultDisposition | None
    payment: PaymentElection
    refund: RefundElection
    prior_domiciliation: PriorDomiciliationElection


class M303FilingFacts(BaseModel):
    """DP30301 facts owned by one immutable Modelo 303 filing instance."""

    model_config = STRICT_FROZEN_CONFIG

    joint_return_elected: bool
    annual_volume_nonzero: bool | None
    insolvency: M303InsolvencyFilingFact | None
    exonerado_390: M303Exonerado390FilingEvidence | None
    regimen_simplificado: M303RegimenSimplificadoFilingEvidence
    regimen_simplificado_result: M303RegimenSimplificadoCalculationResult
    period: Period
    supplier_regime: M303SupplierRegimeArrival
    prorrata_transition: M303ProrrataTransitionArrival
    prorrata_register: ProrrataRegister
    differentiated_contributions: tuple[IvaDifferentiatedDeductionContribution, ...]
    bienes_register: BienesInversionIvaRegister
    regularisation_result: RegistroRegularizacionResult
    #: The registry-resolved figures the regularisation result was produced
    #: under. Carried on the facts rather than resolved here because this
    #: model holds no revision, and because the oracle's independence depends
    #: on comparing the result's own provenance against a bundle supplied
    #: from outside it.
    bienes_parameters: BienesInversionRegularizacionParameters

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _arrivals_share_one_filing_period(self) -> M303FilingFacts:
        _validate_m303_filing_periods(self)
        _validate_m303_calculation_results(self)
        _validate_m303_register_evidence(self)
        return self


def _validate_m303_filing_periods(facts: M303FilingFacts) -> None:
    _require_m303_official_filing_period(facts.period)
    if facts.exonerado_390 is None and is_last_filing_period_of_year(facts.period):
        raise ValueError("M303 last-period filing facts require the Modelo 390 exemption evidence")
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
        parameters=facts.bienes_parameters,
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
    bienes_parameters: BienesInversionRegularizacionParameters,
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
        bienes_parameters=bienes_parameters,
    )


class AmendmentEvidence(BaseModel):
    """Typed evidence for an amendment of an AEAT-accepted filing."""

    model_config = STRICT_FROZEN_CONFIG

    kind: CalculationRevisionAmendmentKind
    m303_rectificativa_motive: M303RectificativaMotive | None
    original_aeat_receipt: _AeatReceiptNumber

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _motive_belongs_only_to_rectificativa(self) -> AmendmentEvidence:
        if (
            self.m303_rectificativa_motive is not None
            and self.kind is not CalculationRevisionAmendmentKind.RECTIFICATIVA
        ):
            raise ValueError("M303 rectificativa motive is valid only for rectificativa evidence")
        return self

    @property
    def is_complementaria(self) -> bool:
        """True when this evidence records a complementaria amendment."""
        return self.kind is CalculationRevisionAmendmentKind.COMPLEMENTARIA

    @property
    def is_sustitutiva(self) -> bool:
        """True when this evidence records a sustitutiva amendment."""
        return self.kind is CalculationRevisionAmendmentKind.SUSTITUTIVA

    @property
    def is_rectificativa(self) -> bool:
        """True when this evidence records a rectificativa amendment."""
        return self.kind is CalculationRevisionAmendmentKind.RECTIFICATIVA


class RefundAccountSelection(BaseModel):
    """Secure account selected for a refund disposition."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    role: Literal["refund"]
    account: RefundAccount


class ChargeAccountSelection(BaseModel):
    """Secure account selected for a direct-debit disposition."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    role: Literal["charge"]
    account: ChargeAccount


type SelectedFilingAccount = RefundAccountSelection | ChargeAccountSelection
type FilingModelProfileFacts = (
    GeneralFilingProfileFacts
    | Modelo111ProfileFacts
    | Modelo202ProducerProfile
    | Modelo200ProfileFacts
    | Modelo210ProfileFacts
    | Modelo222ProfileFacts
    | Modelo296ProfileFacts
    | Modelo353ProfileFacts
    | Modelo360ProfileFacts
    | ModeloIVAProfile
)


class FilingProducerSnapshot(BaseModel):
    """Complete immutable filing facts before registry-specific translation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

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
    m390_filing_facts: _M390FilingFacts | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_model_profile(self) -> FilingProducerSnapshot:
        _validate_snapshot_model_profile(self)
        _validate_snapshot_account_selection(self)
        return self


def _validate_snapshot_model_profile(snapshot: FilingProducerSnapshot) -> None:
    _validate_snapshot_cross_model_facts(snapshot)
    _validate_snapshot_modelo_profile(snapshot)


def _validate_snapshot_cross_model_facts(snapshot: FilingProducerSnapshot) -> None:
    if snapshot.modelo != Modelo("303") and snapshot.m303_filing_facts is not None:
        raise ValueError("M303FilingFacts are valid only for modelo 303")
    if snapshot.modelo != Modelo("390") and snapshot.m390_filing_facts is not None:
        raise ValueError("M390FilingFacts are valid only for modelo 390")
    if (
        snapshot.modelo != Modelo("303")
        and snapshot.amendment_evidence is not None
        and snapshot.amendment_evidence.m303_rectificativa_motive is not None
    ):
        raise ValueError("M303 rectificativa motive is valid only for modelo 303")


def _validate_snapshot_modelo_profile(snapshot: FilingProducerSnapshot) -> None:
    if snapshot.modelo == Modelo("111"):
        _validate_modelo_111_snapshot(snapshot)
        return
    if snapshot.modelo == Modelo("200"):
        _validate_modelo_200_snapshot(snapshot)
        return
    if snapshot.modelo == Modelo("202"):
        _validate_modelo_202_snapshot(snapshot)
        return
    if snapshot.modelo == Modelo("222"):
        _validate_modelo_222_snapshot(snapshot)
        return
    if snapshot.modelo == Modelo("303"):
        _validate_modelo_303_snapshot(snapshot)
        return
    if snapshot.modelo == Modelo("296"):
        _validate_modelo_296_snapshot(snapshot)
        return
    if snapshot.modelo == Modelo("353"):
        _validate_modelo_353_snapshot(snapshot)
        return
    if snapshot.modelo == Modelo("360"):
        _validate_modelo_360_snapshot(snapshot)
        return
    _validate_general_modelo_snapshot(snapshot)


def _validate_modelo_200_snapshot(snapshot: FilingProducerSnapshot) -> None:
    """Modelo 200 carries repeated party, holding and establishment pages of its own.

    Six records of the return are made entirely of projection fields -- the
    administradores, the participaciones, the establecimientos permanentes, the
    INCN communication, the operaciones de reestructuración and the
    transparencia fiscal internacional -- and their rows exist nowhere but this
    profile.  A general profile resolves none of them, so the return would
    render with every one of those pages absent.
    """
    if not isinstance(snapshot.model_profile, Modelo200ProfileFacts):
        raise ValueError("modelo 200 requires Modelo200ProfileFacts")


def _validate_modelo_296_snapshot(snapshot: FilingProducerSnapshot) -> None:
    """Modelo 296 identifies a declarante and an ejercicio; it cannot be filed without them."""
    if not isinstance(snapshot.model_profile, Modelo296ProfileFacts):
        raise ValueError("modelo 296 requires Modelo296ProfileFacts")


def _validate_modelo_353_snapshot(snapshot: FilingProducerSnapshot) -> None:
    """Modelo 353 is the grupo de entidades aggregate; it cannot be filed without it."""
    if not isinstance(snapshot.model_profile, Modelo353ProfileFacts):
        raise ValueError("modelo 353 requires Modelo353ProfileFacts")


def _validate_modelo_360_snapshot(snapshot: FilingProducerSnapshot) -> None:
    """Modelo 360 is a solicitud de devolución; DR360 makes its datos bancarios obligatorio.

    Campos 115 and 116 -- the IBAN and the banco-BIC -- are both required, so a solicitud
    without a selected refund account, or with one that carries no BIC, has nowhere to be
    paid and is refused here rather than at the first blank position.
    """
    if not isinstance(snapshot.model_profile, Modelo360ProfileFacts):
        raise ValueError("modelo 360 requires Modelo360ProfileFacts")
    selected = snapshot.selected_account
    if not isinstance(selected, RefundAccountSelection) or selected.account.iban is None:
        raise ValueError("modelo 360 requires a selected refund account")
    if not selected.account.swift_bic.strip():
        raise ValueError("modelo 360 requires the refund account's banco-BIC")


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
    missing_ids = tuple(item.value for item in snapshot.model_profile.unsupported_producer_ids)
    raise FilingProducerSnapshotError(
        f"Modelo 202 producer snapshot is incomplete: {', '.join(missing_ids)}",
        context={"missing_fact_ids": missing_ids, "reason": "m202_producer_facts_unsupported"},
    )


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
        _validate_domiciliacion_selection(snapshot)
    elif snapshot.elections.payment is PaymentElection.DOMICILIACION:
        raise ValueError("domiciliacion payment election requires the matching result disposition")
    elif disposition is not None and result_disposition_is_refund(disposition):
        if not isinstance(snapshot.selected_account, RefundAccountSelection):
            raise ValueError("refund disposition requires a selected refund account")
    elif snapshot.selected_account is not None and not (
        _account_page_carries_refund_account(snapshot) and isinstance(snapshot.selected_account, RefundAccountSelection)
    ):
        raise ValueError("a result disposition without an account must not retain one")


def _validate_domiciliacion_selection(snapshot: FilingProducerSnapshot) -> None:
    if snapshot.elections.payment is not PaymentElection.DOMICILIACION:
        raise ValueError("domiciliacion disposition requires the matching payment election")
    if not isinstance(snapshot.selected_account, ChargeAccountSelection):
        raise ValueError("domiciliacion disposition requires a selected charge account")


def _account_page_carries_refund_account(snapshot: FilingProducerSnapshot) -> bool:
    """Whether the record design carries the refund account whatever the disposition says.

    Modelo 303 Nota 3 does so for a rectificativa keeping its prior domiciliation, and
    modelo 360 always does: a solicitud de devolución has no result casilla to derive a
    refund disposition from, yet DR360 campos 113-117 are its obligatorio datos bancarios.
    """
    return _m303_nota_three_shape(snapshot) or snapshot.modelo == Modelo("360")


def _m303_nota_three_shape(snapshot: FilingProducerSnapshot) -> bool:
    """Whether Modelo 303 Nota 3 may carry the refund account on the account page."""
    amendment = snapshot.amendment_evidence
    return (
        snapshot.modelo == Modelo("303")
        and amendment is not None
        and amendment.is_rectificativa
        and snapshot.elections.prior_domiciliation is PriorDomiciliationElection.KEEP
    )


def _registered_snapshot_refusal(error: ValueError) -> FilingProducerSnapshotError | None:
    """Return the typed refusal a snapshot validator raised, if it raised one.

    The validation boundary re-raises a registered refusal as the builtin
    ``ValueError`` Pydantic requires, keeping the refusal as its cause, and
    Pydantic keeps that ``ValueError`` in the error context. Recovering it
    keeps the refusal's structured context rather than only its message.
    """
    if not isinstance(error, ValidationError):
        return None
    for detail in error.errors(include_url=False):
        context = detail.get("ctx")
        nested = context.get("error") if isinstance(context, dict) else None
        cause = nested.__cause__ if isinstance(nested, BaseException) else None
        if isinstance(cause, FilingProducerSnapshotError):
            return cause
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
    account_page_refund_account: bool = False,
) -> FilingProducerSnapshot:
    """Build a snapshot retaining only the account selected by disposition.

    ``declaration_contact`` is optional so every caller that predates the
    informativa contact fact keeps working unchanged; an absent contact renders
    as blancos, which is what AEAT's own header rule prescribes.

    ``account_page_refund_account`` selects the refund account although the
    disposition is not a refund: Modelo 303 Nota 3, and every modelo 360 solicitud.
    """
    selected_account = _select_filing_account(
        elections,
        refund_account=refund_account,
        charge_account=charge_account,
        account_page_refund_account=account_page_refund_account,
    )
    try:
        return FilingProducerSnapshot(
            modelo=modelo,
            taxpayer_tax_id=taxpayer_tax_id,
            taxpayer_identity=taxpayer_identity,
            presenter=presenter,
            model_profile=model_profile,
            elections=elections,
            amendment_evidence=amendment_evidence,
            selected_account=selected_account,
            m303_filing_facts=m303_filing_facts,
            m390_filing_facts=None,
            declaration_contact=declaration_contact or DeclarationContactFacts(),
        )
    except ValueError as exc:
        raise _registered_snapshot_refusal(exc) or FilingProducerSnapshotError(str(exc)) from exc


def _select_filing_account(
    elections: FilingElectionFacts,
    *,
    refund_account: RefundAccount | None,
    charge_account: ChargeAccount | None,
    account_page_refund_account: bool,
) -> SelectedFilingAccount | None:
    if elections.result_disposition is ResultDisposition.DOMICILIACION:
        if charge_account is None:
            raise FilingProducerSnapshotError("domiciliacion requires a charge account")
        return ChargeAccountSelection(role="charge", account=charge_account)
    if elections.result_disposition is not None and result_disposition_is_refund(elections.result_disposition):
        if refund_account is None or refund_account.iban is None:
            raise FilingProducerSnapshotError("refund disposition requires a refund account")
        return RefundAccountSelection(role="refund", account=refund_account)
    if account_page_refund_account:
        # Modelo 303 Nota 3 and modelo 360: the account page carries the refund
        # account even though the disposition itself is not a refund.
        if refund_account is None or refund_account.iban is None:
            raise FilingProducerSnapshotError("the account page requires a refund account")
        return RefundAccountSelection(role="refund", account=refund_account)
    return None


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
