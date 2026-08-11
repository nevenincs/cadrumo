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
from ...domain.bienes_inversion import BienesInversionIvaRegister, RegistroRegularizacionResult
from ...domain.deadlines import ChargeAccount, ModeloIVAProfile, RefundAccount, TaxpayerProfile
from ...domain.modelos import (
    CalculationRevisionAmendmentKind,
    FilingInstanceEvidence,
    M303Exonerado390FilingEvidence,
    M303InsolvencyFilingFact,
    M303InsolvencyFilingSubtype,
    M303RegimenSimplificadoFilingEvidence,
)
from ...domain.prorrata_register import ProrrataRegister
from ..aggregation import (
    IvaDifferentiatedDeductionContribution,
    M303ProrrataTransitionArrival,
    M303SupplierRegimeArrival,
)

_NonBlankName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
_AmendmentMotive = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
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


class Modelo111ProfileFacts(BaseModel):
    """Stable Modelo 111 profile facts consumed by a filing producer."""

    model_config = STRICT_FROZEN_CONFIG

    colegio_concertado: bool | None


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
    """M202 producer view referencing the canonical taxpayer profile owner."""

    model_config = STRICT_FROZEN_CONFIG

    taxpayer_profile: TaxpayerProfile
    activities: tuple[Modelo202ActivityFacts, ...]

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
    insolvency: M303InsolvencyFilingFact | None
    exonerado_390: M303Exonerado390FilingEvidence
    regimen_simplificado: M303RegimenSimplificadoFilingEvidence
    period: Period
    supplier_regime: M303SupplierRegimeArrival
    prorrata_transition: M303ProrrataTransitionArrival
    prorrata_register: ProrrataRegister
    differentiated_contributions: tuple[IvaDifferentiatedDeductionContribution, ...]
    bienes_register: BienesInversionIvaRegister
    regularisation_result: RegistroRegularizacionResult

    @model_validator(mode="after")
    def _arrivals_share_one_filing_period(self) -> M303FilingFacts:
        _require_m303_official_filing_period(self.period)
        if self.period != self.supplier_regime.period or self.period != self.prorrata_transition.period:
            raise ValueError("M303 filing facts and arrivals must share one filing period")
        return self


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
        insolvency=m303.insolvency,
        exonerado_390=m303.exonerado_390,
        regimen_simplificado=m303.regimen_simplificado,
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
    motive: _AmendmentMotive
    original_aeat_receipt: _AeatReceiptNumber

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
    GeneralFilingProfileFacts | Modelo111ProfileFacts | Modelo202ProducerProfile | ModeloIVAProfile
)


class FilingProducerSnapshot(BaseModel):
    """Complete immutable filing facts before registry-specific translation."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: Modelo
    taxpayer_tax_id: SubjectTaxId
    taxpayer_identity: TaxpayerIdentityFacts
    presenter: PresenterIdentity
    model_profile: FilingModelProfileFacts
    elections: FilingElectionFacts
    amendment_evidence: AmendmentEvidence | None
    selected_account: SelectedFilingAccount | None
    m303_filing_facts: M303FilingFacts | None = None

    @model_validator(mode="after")
    def _validate_model_profile(self) -> FilingProducerSnapshot:
        if self.modelo is Modelo.M111:
            if not isinstance(self.model_profile, Modelo111ProfileFacts):
                raise ValueError("modelo 111 requires Modelo111ProfileFacts")
            if self.model_profile.colegio_concertado is None:
                raise ValueError("Modelo 111 colegio_concertado must be explicitly declared")
        elif self.modelo is Modelo.M202:
            if not isinstance(self.model_profile, Modelo202ProducerProfile):
                raise ValueError("modelo 202 requires Modelo202ProducerProfile")
            unsupported = ", ".join(item.value for item in self.model_profile.unsupported_producer_ids)
            raise ValueError(f"Modelo 202 producer snapshot is incomplete: {unsupported}")
        elif self.modelo is Modelo.M303:
            if not isinstance(self.model_profile, ModeloIVAProfile):
                raise ValueError("modelo 303 requires the canonical ModeloIVAProfile")
            if self.m303_filing_facts is None:
                raise ValueError("modelo 303 requires complete M303FilingFacts")
        elif not isinstance(self.model_profile, GeneralFilingProfileFacts):
            raise ValueError(f"modelo {self.modelo.value} requires GeneralFilingProfileFacts")
        elif self.m303_filing_facts is not None:
            raise ValueError("M303FilingFacts are valid only for modelo 303")
        disposition = self.elections.result_disposition
        if disposition is ResultDisposition.DOMICILIACION:
            if self.elections.payment is not PaymentElection.DOMICILIACION:
                raise ValueError("domiciliacion disposition requires the matching payment election")
            if not isinstance(self.selected_account, ChargeAccountSelection):
                raise ValueError("domiciliacion disposition requires a selected charge account")
        elif self.elections.payment is PaymentElection.DOMICILIACION:
            raise ValueError("domiciliacion payment election requires the matching result disposition")
        elif result_disposition_is_refund(disposition):
            if not isinstance(self.selected_account, RefundAccountSelection):
                raise ValueError("refund disposition requires a selected refund account")
        elif self.selected_account is not None:
            raise ValueError("a result disposition without an account must not retain one")
        profile_iva = (
            self.model_profile
            if isinstance(self.model_profile, ModeloIVAProfile)
            else self.model_profile.taxpayer_profile.iva
            if isinstance(self.model_profile, Modelo202ProducerProfile)
            else None
        )
        if profile_iva is not None and (
            profile_iva.refund_account is not None or profile_iva.charge_account is not None
        ):
            raise ValueError("model profile must not retain accounts outside selected_account")
        return self


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
    m303_filing_facts: M303FilingFacts | None = None,
) -> FilingProducerSnapshot:
    """Build a snapshot retaining only the account selected by disposition."""
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
    "build_filing_producer_snapshot",
    "resolve_m303_filing_facts",
]
