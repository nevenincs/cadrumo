"""Producer snapshot filing facts for Modelo 303: marker evidence, foral notes, periods, amendments and bienes de inversion regularisation."""

import json
from collections.abc import Callable, Iterator
from datetime import date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.core.prorrata_register import ProrrataEspecialTransitionKind, ProrrataRegisterRegime
from cadrumo.domain.bienes_inversion.vocabulary import BienInversionKind
from cadrumo.domain.deadlines.models import IVARegime, M303RegimeComposition, M303TaxTerritory

from ....core.filing_producer_key import FilingProducerKey
from ....core.modelo import Modelo
from ....core.period import Period, PeriodError
from ....core.resources.bundled_data import bundled_path
from ....core.result_disposition import ResultDisposition
from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ....domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
    BienInversionIvaRecord,
    RegistroRegularizacionResult,
    compute_registro_regularizacion,
)
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.deadlines.models import (
    ModeloIVAProfile,
    TaxpayerProfile,
)
from ....domain.modelos.calculation_revision_m303_evidence import (
    M303InsolvencyFilingFact,
    M303InsolvencyFilingSubtype,
)
from ....domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence, M303FilingInstanceEvidence
from ....domain.prorrata_register.register import (
    ProrrataEspecialTransitionEvidence,
    ProrrataRegister,
    ProrrataRegisterEntry,
)
from ...aggregation.m303_arrivals import (
    M303ProrrataTransitionArrival,
    M303SupplierRegimeArrival,
    resolve_m303_prorrata_transition_arrival,
)
from ..export_producer import filing_producer_values, m303_filing_lexicals, m303_profile_lexicals
from ..producer_snapshot import (
    FilingProducerSnapshot,
    FilingProducerSnapshotError,
    GeneralFilingProfileFacts,
    M303FilingFacts,
    Modelo111ProfileFacts,
    Modelo202ProducerProfile,
    build_filing_producer_snapshot,
    resolve_m303_filing_facts,
)
from .producer_snapshot_support import (
    _TAXPAYER_TAX_ID,
    _elections,
    _empty_m303_export_arrivals,
    _m303_filing_facts,
    _m303_instance_evidence,
    _m303_profile,
    _presenter,
    _taxpayer_identity,
    m303_bienes_inversion_parameters,
    m303_exonerado_390_evidence,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_M303_2026_IR_SHA256 = "0be8b156da2250c6b11f6253e0165221ed2e549ec4c65a562021bec6b9b8489b"


@pytest.fixture(autouse=True)
def _generation_pinned_authority() -> Iterator[None]:
    """Run every test inside one generation-pinned authority operation."""
    with bundled_indexed_authority().operation():
        yield


def _bien_inversion(identifier: str) -> BienInversionIvaRecord:
    return BienInversionIvaRecord(
        identifier=identifier,
        description=f"Bien de inversión {identifier}",
        acquisition_year=2024,
        cuota_soportada=Decimal("5000.00"),
        prorrata_inicial_pct=Decimal("70"),
        kind=BienInversionKind.from_registry("mueble"),
        acquisition_ledger_id=f"ledger:{identifier}",
    )


def _m303_filing_facts_payload(
    *,
    bienes_register: BienesInversionIvaRegister,
    regularisation_result: RegistroRegularizacionResult,
) -> dict[str, object]:
    payload = STR_KEYED_MAPPING_ADAPTER.validate_python(_m303_filing_facts().model_dump())
    payload["bienes_register"] = bienes_register.model_dump()
    payload["regularisation_result"] = regularisation_result.model_dump()
    return payload


def _m303_prorrata_transition_arrival(
    transition: ProrrataEspecialTransitionKind,
) -> tuple[M303ProrrataTransitionArrival, ProrrataRegister]:
    period = Period.from_year_and_code(2026, "4T")
    entry = ProrrataRegisterEntry(
        ejercicio=period.filing_year,
        regime=(
            ProrrataRegisterRegime.from_registry("especial")
            if transition == ProrrataEspecialTransitionKind.from_registry("opcion")
            else ProrrataRegisterRegime.from_registry("general")
        ),
        especial_transition=ProrrataEspecialTransitionEvidence(
            kind=transition,
            evidence_reference=f"modelo-303-2026-prorrata-{transition.value}",
        ),
        source_registry_snapshot_refs=(),
    )
    prior_entries = (
        (
            ProrrataRegisterEntry(
                ejercicio=2025,
                regime=ProrrataRegisterRegime.from_registry("especial"),
                especial_transition=None,
                source_registry_snapshot_refs=(),
            ),
        )
        if transition == ProrrataEspecialTransitionKind.from_registry("revocacion")
        else ()
    )
    register = ProrrataRegister(entries=(*prior_entries, entry))
    arrival = resolve_m303_prorrata_transition_arrival(period=period, prorrata_register=register)
    return arrival, register


def _m303_foral_snapshot(
    *,
    prorrata_transition: M303ProrrataTransitionArrival,
    prorrata_register: ProrrataRegister | None = None,
) -> FilingProducerSnapshot:
    period = prorrata_transition.period
    default_register, bienes_register, regularisation = _empty_m303_export_arrivals(period.filing_year)
    register = default_register if prorrata_register is None else prorrata_register
    evidence = _m303_instance_evidence(period)
    facts = M303FilingFacts(
        joint_return_elected=True,
        annual_volume_nonzero=False,
        insolvency=M303InsolvencyFilingFact(
            judicial_order_date=date(2026, 8, 11),
            subtype=M303InsolvencyFilingSubtype.POST_ORDER,
        ),
        exonerado_390=m303_exonerado_390_evidence(applicable=True),
        regimen_simplificado=evidence.regimen_simplificado,
        regimen_simplificado_result=evidence.regimen_simplificado.calculation_result,
        period=period,
        supplier_regime=M303SupplierRegimeArrival(
            period=period,
            recipient_of_cash_accounting_operations=True,
            source_ledger_ids=("foral-supplier-regime-ledger",),
        ),
        prorrata_transition=prorrata_transition,
        prorrata_register=register,
        differentiated_contributions=(),
        bienes_register=bienes_register,
        regularisation_result=regularisation,
        bienes_parameters=m303_bienes_inversion_parameters(period.filing_year),
    )
    profile = _m303_profile().model_copy(
        update={
            "tax_territory": M303TaxTerritory.from_registry("foral_unsupported"),
            "regime_composition": M303RegimeComposition.from_registry("mixed"),
            "redeme_enrolled": True,
            "cash_accounting_regime_enrolled": True,
            "voluntary_sii_enrolled": True,
            "hydrocarbon_deposit_advance_payment_deduction_entitled": True,
        },
    )
    return build_filing_producer_snapshot(
        modelo=Modelo("303"),
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=profile,
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=facts,
    )


def test_modelo_303_uses_the_canonical_iva_profile_type() -> None:
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo("303"),
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=_m303_profile(),
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=_m303_filing_facts(),
    )
    assert type(snapshot.model_profile) is ModeloIVAProfile
    values = filing_producer_values(snapshot)
    assert values[FilingProducerKey.M303_EXCLUSIVELY_FORAL] == "2"
    assert values[FilingProducerKey.M303_REDEME_ENROLLED] == "2"
    assert values[FilingProducerKey.M303_ANNUAL_VOLUME_NONZERO] == "0"
    assert values[FilingProducerKey.M303_JOINT_RETURN_ELECTED] == "2"
    assert values[FilingProducerKey.M303_CASH_ACCOUNTING_REGIME_ENROLLED] == "2"
    assert values[FilingProducerKey.M303_RECIPIENT_OF_CASH_ACCOUNTING_OPERATIONS] == "2"
    assert values[FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION] == "2"
    assert values[FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION] == "2"
    assert values[FilingProducerKey.M303_INSOLVENCY_DECLARED] == "2"
    assert values[FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE] is None
    assert values[FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE] is None
    assert values[FilingProducerKey.M303_VOLUNTARY_SII_ENROLLED] == "2"
    assert values[FilingProducerKey.M303_EXONERADO_390_APPLICABLE] == "2"
    assert values[FilingProducerKey.M303_HYDROCARBON_DEPOSIT_ADVANCE_PAYMENT_DEDUCTION_ENTITLED] == "0"


@pytest.mark.parametrize(
    ("period_code", "entitled", "expected"),
    (
        ("1T", False, "0"),
        ("1T", True, "0"),
        ("02", False, "2"),
        ("02", True, "1"),
    ),
)
def test_modelo_303_hydrocarbon_entitlement_uses_the_official_period_and_yes_no_codes(
    period_code: str,
    entitled: bool,
    expected: str,
) -> None:
    """DP30301 Nota 8/9 reserves ``0`` and maps the applicable decision to 1/2.

    The 2026 official design writes ``0`` for quarterly/01 filings and admits
    the typed entitlement only from period 02.  This test mutates the boolean
    itself so true and false cannot silently collapse into a numeric default.
    """
    profile = _m303_profile().model_copy(
        update={"hydrocarbon_deposit_advance_payment_deduction_entitled": entitled},
    )

    # This lexical branch reads only the typed filing period.  A partial typed
    # instance keeps the proof at the producer boundary instead of requiring a
    # whole bundled-registry load unrelated to this source-stated wire rule.
    facts = M303FilingFacts.model_construct(period=Period.from_year_and_code(2026, period_code))
    lexical = m303_profile_lexicals(profile, facts)

    assert lexical.hydrocarbon_deposit_advance_payment_deduction_entitled == expected


def test_modelo_303_annual_volume_marker_requires_explicit_evidence() -> None:
    """The art. 121 marker is not silently inferred from rows or the profile."""
    facts = _m303_filing_facts(annual_volume_nonzero=True)
    payload = facts.model_dump(mode="python")
    del payload["annual_volume_nonzero"]
    with pytest.raises(ValidationError, match="annual_volume_nonzero"):
        M303FilingFacts.model_validate(payload)

    snapshot = build_filing_producer_snapshot(
        modelo=Modelo("303"),
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=_m303_profile(),
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=facts,
    )
    # Not exempt from Modelo 390, so the affirmative answer is not printed (DP30301 Nota 3).
    assert filing_producer_values(snapshot)[FilingProducerKey.M303_ANNUAL_VOLUME_NONZERO] == "0"


@pytest.mark.parametrize(
    ("period_code", "exonerado_390", "answer", "expected"),
    (
        ("4T", True, True, "1"),
        ("4T", True, False, "2"),
        ("12", True, True, "1"),
        ("12", True, False, "2"),
        ("4T", False, True, "0"),
        ("12", False, True, "0"),
        ("3T", True, True, "0"),
        ("11", True, True, "0"),
    ),
)
def test_modelo_303_annual_volume_marker_prints_only_for_a_390_exempt_filer_in_the_last_period(
    period_code: str,
    exonerado_390: bool,
    answer: bool,
    expected: str,
) -> None:
    """DP30301 Nota 3: "0" in every period but 12 and 4T, and there too for a filer not exempt from Modelo 390."""
    facts = _m303_filing_facts(annual_volume_nonzero=answer).model_copy(
        update={
            "period": Period.from_year_and_code(2026, period_code),
            "exonerado_390": m303_exonerado_390_evidence(applicable=exonerado_390),
        }
    )

    assert m303_filing_lexicals(facts).annual_volume_nonzero == expected


def test_modelo_303_foral_territory_projects_true_without_a_constant_fallback() -> None:
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo("303"),
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=_m303_profile().model_copy(
            update={"tax_territory": M303TaxTerritory.from_registry("foral_unsupported")}
        ),
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=_m303_filing_facts(),
    )

    assert filing_producer_values(snapshot)[FilingProducerKey.M303_EXCLUSIVELY_FORAL] == "1"


@pytest.mark.parametrize(
    "transition",
    (
        ProrrataEspecialTransitionKind.from_registry("opcion"),
        ProrrataEspecialTransitionKind.from_registry("revocacion"),
    ),
)
def test_modelo_303_foral_note_5_overrides_each_a16_to_a30_lexical_branch(
    transition: ProrrataEspecialTransitionKind,
) -> None:
    """DP30301 Nota 5 supersedes the contradictory typed input values."""
    arrival, register = _m303_prorrata_transition_arrival(transition)
    snapshot = _m303_foral_snapshot(prorrata_transition=arrival, prorrata_register=register)

    values = filing_producer_values(snapshot)

    assert {
        FilingProducerKey.M303_REDEME_ENROLLED: values[FilingProducerKey.M303_REDEME_ENROLLED],
        FilingProducerKey.M303_EXCLUSIVELY_FORAL: values[FilingProducerKey.M303_EXCLUSIVELY_FORAL],
        FilingProducerKey.M303_REGIME_COMPOSITION_CODE: values[FilingProducerKey.M303_REGIME_COMPOSITION_CODE],
        FilingProducerKey.M303_JOINT_RETURN_ELECTED: values[FilingProducerKey.M303_JOINT_RETURN_ELECTED],
        FilingProducerKey.M303_CASH_ACCOUNTING_REGIME_ENROLLED: values[
            FilingProducerKey.M303_CASH_ACCOUNTING_REGIME_ENROLLED
        ],
        FilingProducerKey.M303_RECIPIENT_OF_CASH_ACCOUNTING_OPERATIONS: values[
            FilingProducerKey.M303_RECIPIENT_OF_CASH_ACCOUNTING_OPERATIONS
        ],
        FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION: values[FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION],
        FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION: values[FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION],
        FilingProducerKey.M303_INSOLVENCY_DECLARED: values[FilingProducerKey.M303_INSOLVENCY_DECLARED],
        FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE: values[
            FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE
        ],
        FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE: values[FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE],
        FilingProducerKey.M303_VOLUNTARY_SII_ENROLLED: values[FilingProducerKey.M303_VOLUNTARY_SII_ENROLLED],
        FilingProducerKey.M303_EXONERADO_390_APPLICABLE: values[FilingProducerKey.M303_EXONERADO_390_APPLICABLE],
        FilingProducerKey.M303_ANNUAL_VOLUME_NONZERO: values[FilingProducerKey.M303_ANNUAL_VOLUME_NONZERO],
        FilingProducerKey.M303_HYDROCARBON_DEPOSIT_ADVANCE_PAYMENT_DEDUCTION_ENTITLED: values[
            FilingProducerKey.M303_HYDROCARBON_DEPOSIT_ADVANCE_PAYMENT_DEDUCTION_ENTITLED
        ],
    } == {
        FilingProducerKey.M303_REDEME_ENROLLED: "2",
        FilingProducerKey.M303_EXCLUSIVELY_FORAL: "1",
        FilingProducerKey.M303_REGIME_COMPOSITION_CODE: "3",
        FilingProducerKey.M303_JOINT_RETURN_ELECTED: "2",
        FilingProducerKey.M303_CASH_ACCOUNTING_REGIME_ENROLLED: "2",
        FilingProducerKey.M303_RECIPIENT_OF_CASH_ACCOUNTING_OPERATIONS: "2",
        FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION: "2",
        FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION: "2",
        FilingProducerKey.M303_INSOLVENCY_DECLARED: None,
        FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE: None,
        FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE: None,
        FilingProducerKey.M303_VOLUNTARY_SII_ENROLLED: "2",
        FilingProducerKey.M303_EXONERADO_390_APPLICABLE: "2",
        FilingProducerKey.M303_ANNUAL_VOLUME_NONZERO: "2",
        FilingProducerKey.M303_HYDROCARBON_DEPOSIT_ADVANCE_PAYMENT_DEDUCTION_ENTITLED: "2",
    }


def test_modelo_303_foral_note_5_retains_blank_prorrata_slots_before_final_period() -> None:
    period = Period.from_year_and_code(2026, "1T")
    snapshot = _m303_foral_snapshot(
        prorrata_transition=M303ProrrataTransitionArrival(period=period, transition=None, register_evidence=())
    )

    values = filing_producer_values(snapshot)

    assert values[FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION] is None
    assert values[FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION] is None


@pytest.mark.parametrize(
    ("composition", "expected"),
    (
        (M303RegimeComposition.from_registry("simplified"), "1"),
        (M303RegimeComposition.from_registry("mixed"), "2"),
        (M303RegimeComposition.from_registry("general"), "3"),
    ),
)
def test_m303_regime_composition_projects_only_the_exclusively_simplified_arm(
    composition: M303RegimeComposition,
    expected: str,
) -> None:
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo("303"),
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=_m303_profile().model_copy(update={"regime_composition": composition}),
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=_m303_filing_facts(),
    )
    assert filing_producer_values(snapshot)[FilingProducerKey.M303_REGIME_COMPOSITION_CODE] == expected


@pytest.mark.parametrize(
    ("subtype", "expected"),
    (
        (M303InsolvencyFilingSubtype.PRE_ORDER, "1"),
        (M303InsolvencyFilingSubtype.POST_ORDER, "2"),
    ),
)
def test_m303_insolvency_fact_projects_coupled_date_and_official_subtype_code(
    subtype: M303InsolvencyFilingSubtype,
    expected: str,
) -> None:
    facts = _m303_filing_facts().model_copy(
        update={
            "insolvency": M303InsolvencyFilingFact(
                judicial_order_date=date(2026, 8, 11),
                subtype=subtype,
            ),
        },
    )
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo("303"),
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=_m303_profile(),
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=facts,
    )
    values = filing_producer_values(snapshot)
    assert values[FilingProducerKey.M303_INSOLVENCY_DECLARED] == "1"
    assert values[FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE] == "11082026"
    assert values[FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE] == expected


_NON_OFFICIAL_PERIOD_REFUSAL = (
    r"official quarterly or monthly period"
    r"|modelo 303: no revision for year=2026 period='0A'"
    r"|has no calendar date span"
)


@pytest.mark.parametrize("period_code", ("0A", "1P", "EXT-1T"))
def test_m303_filing_facts_refuse_annual_and_non_official_filing_periods(period_code: str) -> None:
    period = Period.from_year_and_code(2026, period_code)

    # Refused wherever the period first meets a component that needs an official
    # quarterly or monthly period: its evidence, its arrivals, or the facts.
    with pytest.raises((ValidationError, PeriodError), match=_NON_OFFICIAL_PERIOD_REFUSAL):
        register, bienes_register, regularisation = _empty_m303_export_arrivals(period.filing_year)
        evidence = _m303_instance_evidence(period)
        M303FilingFacts(
            joint_return_elected=False,
            annual_volume_nonzero=False,
            insolvency=None,
            exonerado_390=m303_exonerado_390_evidence(applicable=False),
            regimen_simplificado=evidence.regimen_simplificado,
            regimen_simplificado_result=evidence.regimen_simplificado.calculation_result,
            period=period,
            supplier_regime=M303SupplierRegimeArrival(
                period=period,
                recipient_of_cash_accounting_operations=False,
                source_ledger_ids=(),
            ),
            prorrata_transition=M303ProrrataTransitionArrival(period=period, transition=None, register_evidence=()),
            prorrata_register=register,
            differentiated_contributions=(),
            bienes_register=bienes_register,
            regularisation_result=regularisation,
            bienes_parameters=m303_bienes_inversion_parameters(period.filing_year),
        )


@pytest.mark.parametrize("period_code", ("0A", "EXT-1T"))
def test_m303_filing_facts_resolver_refuses_non_official_period_before_producer_output(period_code: str) -> None:
    period = Period.from_year_and_code(2026, period_code)

    with pytest.raises((ValueError, PeriodError), match=_NON_OFFICIAL_PERIOD_REFUSAL):
        register, bienes_register, regularisation = _empty_m303_export_arrivals(period.filing_year)
        evidence = FilingInstanceEvidence(
            m303=_m303_instance_evidence(period),
        )
        resolve_m303_filing_facts(
            evidence=evidence,
            supplier_regime=M303SupplierRegimeArrival(
                period=period,
                recipient_of_cash_accounting_operations=False,
                source_ledger_ids=(),
            ),
            prorrata_transition=M303ProrrataTransitionArrival(period=period, transition=None, register_evidence=()),
            prorrata_register=register,
            differentiated_contributions=(),
            bienes_register=bienes_register,
            regularisation_result=regularisation,
            bienes_parameters=m303_bienes_inversion_parameters(period.filing_year),
        )


def test_real_open_ended_design_dp30301_source_pins_a16_a30_lexical_domains() -> None:
    """The official open-ended design pins the A16-A30 lexical domains verbatim.

    This case once also asserted that A29, the non-zero annual volume marker,
    had NO producer key. That pin was written while the box was unmodelled and
    was never revisited when the marker was implemented three days later as a
    deliberate, evidence-gated producer grounded in art. 121 -- see
    ``test_modelo_303_annual_volume_marker_requires_explicit_evidence``, which
    proves the value cannot be inferred from rows or the profile. Two claims
    about the same box disagreed, and the newer one is the one with the
    grounding, so the stale assertion is gone rather than the producer.
    """
    # The open-ended Modelo 303 revision's endpoint design, found by its pinned bytes.
    with bundled_indexed_authority().operation() as operation:
        directory = operation.modelo_directory("303")
        open_ended = next(revision for revision in directory.revisions if revision.valid_to is None)
        (design,) = (
            source
            for source in (operation.source_reference(ref) for ref in directory.endpoint_source_ids(open_ended.id))
            if source.sha256 == _M303_2026_IR_SHA256
        )
    source = bundled_path(*design.corpus_path.split("/"))
    extracted = Path(f"{source}.extracted.json")
    assert sha256(source.read_bytes()).hexdigest() == _M303_2026_IR_SHA256
    payload = json.loads(extracted.read_text(encoding="utf-8"))
    page = next(unit["text"] for unit in payload["units"] if unit["section"] == "DP30301")

    exact_source_domains = (
        '"1" SI, "2" NO',
        '"1" SI (sólo RS)',
        '"2" NO (RG + RS)',
        '"3" NO (sólo RG)',
        "DDMMYYYY",
        '"1" SI Preconcursal',
        '"2" SI Postconcursal',
        "0 | Para todos los periodos distintos del último (12 y 4T)",
        "0 | Para los periodos 1T, 2T, 3T, 4T y 01",
        "Sólo para periodo 02 y siguientes",
    )
    assert all(domain in page for domain in exact_source_domains)
    exact_nota_5 = (
        "Nota 5 - Tributación exclusivamente a una Administración Foral",
        'se cumplimentarán con el valor "2" NO',
        'IVA a la importación liquidado por la Aduana pendiente de ingreso >> "1" SI',
        'Tributa exclusivamente en Régimen Simplificado (RS) >> "3" NO (sólo RG).',
        "Auto de declaración de concurso dictado en el período >> blanco NO",
        'Opción por la aplicación de la prorrata especial (art. 103.Dos.1º LIVA) >> "2" blanco',
        'Revocación de la opción por la aplicación de la prorrata especial >> "2" blanco',
    )
    assert all(note in page for note in exact_nota_5)
    assert "Sujeto pasivo con volumen anual de operaciones distinto de cero" in page


type _NonM303ProducerProfile = Modelo111ProfileFacts | Modelo202ProducerProfile | GeneralFilingProfileFacts


def _m111_producer_profile() -> Modelo111ProfileFacts:
    return Modelo111ProfileFacts(colegio_concertado=False)


def _m202_producer_profile() -> Modelo202ProducerProfile:
    return Modelo202ProducerProfile(
        taxpayer_profile=TaxpayerProfile(tax_id=_TAXPAYER_TAX_ID, iva_regime=IVARegime("GENERAL")),
        activities=(),
    )


@pytest.mark.parametrize(
    ("modelo", "model_profile_factory"),
    (
        (Modelo("111"), _m111_producer_profile),
        (Modelo("202"), _m202_producer_profile),
        (Modelo("131"), GeneralFilingProfileFacts),
    ),
)
def test_m303_filing_facts_are_refused_for_every_non_m303_modelo(
    modelo: Modelo,
    model_profile_factory: Callable[[], _NonM303ProducerProfile],
) -> None:
    """Modelo-specific filing facts never cross into M111, M202, or generic producers."""
    with bundled_indexed_authority().operation():
        model_profile = model_profile_factory()
        with pytest.raises(FilingProducerSnapshotError, match="M303FilingFacts are valid only for modelo 303"):
            build_filing_producer_snapshot(
                modelo=modelo,
                taxpayer_tax_id=_TAXPAYER_TAX_ID,
                taxpayer_identity=_taxpayer_identity(),
                presenter=_presenter(),
                model_profile=model_profile,
                elections=_elections(ResultDisposition.NEGATIVA),
                amendment_evidence=None,
                refund_account=None,
                charge_account=None,
                m303_filing_facts=_m303_filing_facts(),
            )


def test_m303_filing_facts_refuse_a_regularisation_result_for_another_year() -> None:
    payload = _m303_filing_facts().model_dump()
    payload["regularisation_result"]["regularizacion_year"] = 2025

    with pytest.raises(ValidationError, match="regularisation result must use the filing year"):
        M303FilingFacts.model_validate(payload)


def test_m303_filing_facts_accept_the_canonical_bienes_regularisation_result() -> None:
    register = BienesInversionIvaRegister(records=(_bien_inversion("canonical-bien"),))
    regularisation = compute_registro_regularizacion(
        register,
        regularizacion_year=2026,
        prorrata_definitiva_by_identifier={"canonical-bien": Decimal("80")},
        parameters=m303_bienes_inversion_parameters(2026),
    )

    facts = M303FilingFacts.model_validate(
        _m303_filing_facts_payload(
            bienes_register=register,
            regularisation_result=regularisation,
        )
    )

    assert facts.bienes_register == register
    assert facts.regularisation_result == regularisation


def test_m303_filing_facts_refuse_an_empty_regularisation_for_a_register_bien() -> None:
    register = BienesInversionIvaRegister(records=(_bien_inversion("unrepresented-bien"),))
    empty = RegistroRegularizacionResult(
        regularizacion_year=2026,
        rows=(),
        proposed_casilla_43=Decimal("0"),
        computed_count=0,
        pending_percentage_count=0,
        sector_contributions=(),
        parameters_provenance=m303_bienes_inversion_parameters(2026).provenance,
    )

    with pytest.raises(ValidationError, match="canonical projection of the supplied Bienes register"):
        M303FilingFacts.model_validate(
            _m303_filing_facts_payload(
                bienes_register=register,
                regularisation_result=empty,
            )
        )


def test_m303_filing_facts_refuse_a_regularisation_from_another_bienes_register() -> None:
    canonical_register = BienesInversionIvaRegister(records=(_bien_inversion("canonical-bien"),))
    foreign_register = BienesInversionIvaRegister(records=(_bien_inversion("foreign-bien"),))
    foreign_regularisation = compute_registro_regularizacion(
        foreign_register,
        regularizacion_year=2026,
        prorrata_definitiva_by_identifier={"foreign-bien": Decimal("80")},
        parameters=m303_bienes_inversion_parameters(2026),
    )

    with pytest.raises(ValidationError, match="canonical projection of the supplied Bienes register"):
        M303FilingFacts.model_validate(
            _m303_filing_facts_payload(
                bienes_register=canonical_register,
                regularisation_result=foreign_regularisation,
            )
        )


def test_m303_filing_facts_refuse_a_regularisation_that_omits_an_in_window_bien() -> None:
    register = BienesInversionIvaRegister(records=(_bien_inversion("first-bien"), _bien_inversion("second-bien")))
    canonical = compute_registro_regularizacion(
        register,
        regularizacion_year=2026,
        prorrata_definitiva_by_identifier={},
        parameters=m303_bienes_inversion_parameters(2026),
    )
    omitted = RegistroRegularizacionResult(
        regularizacion_year=2026,
        rows=(canonical.rows[0],),
        proposed_casilla_43=Decimal("0"),
        computed_count=0,
        pending_percentage_count=1,
        sector_contributions=(),
        parameters_provenance=m303_bienes_inversion_parameters(2026).provenance,
    )

    with pytest.raises(ValidationError, match="canonical projection of the supplied Bienes register"):
        M303FilingFacts.model_validate(
            _m303_filing_facts_payload(
                bienes_register=register,
                regularisation_result=omitted,
            )
        )


def test_m303_filing_facts_refuse_final_period_register_coverage_gaps() -> None:
    payload = _m303_filing_facts().model_dump()
    payload["prorrata_register"] = ProrrataRegister()

    with pytest.raises(ValidationError, match="complete current-year prorrata register coverage"):
        M303FilingFacts.model_validate(payload)


def test_m303_filing_facts_refuse_transition_arrival_evidence_from_another_register() -> None:
    period = Period.from_year_and_code(2026, "4T")
    canonical_entry = ProrrataRegisterEntry(
        ejercicio=period.filing_year,
        regime=ProrrataRegisterRegime.from_registry("especial"),
        especial_transition=ProrrataEspecialTransitionEvidence(
            kind=ProrrataEspecialTransitionKind.from_registry("opcion"),
            evidence_reference="operator-evidence:canonical-option",
        ),
        source_registry_snapshot_refs=(),
    )
    foreign_entry = canonical_entry.model_copy(
        update={
            "especial_transition": ProrrataEspecialTransitionEvidence(
                kind=ProrrataEspecialTransitionKind.from_registry("opcion"),
                evidence_reference="operator-evidence:foreign-option",
            )
        }
    )
    payload = _m303_filing_facts().model_dump()
    payload["prorrata_transition"] = M303ProrrataTransitionArrival(
        period=period,
        transition=ProrrataEspecialTransitionKind.from_registry("opcion"),
        register_evidence=(foreign_entry,),
    )
    payload["prorrata_register"] = ProrrataRegister(entries=(canonical_entry,))

    with pytest.raises(ValidationError, match="transition arrival evidence must belong to the supplied register"):
        M303FilingFacts.model_validate(payload)


@pytest.mark.parametrize(("period_code", "required"), [("1T", False), ("3T", False), ("4T", True)])
def test_m303_evidence_requires_the_modelo_390_exemption_only_in_the_last_period(
    period_code: str, required: bool
) -> None:
    """DP30301 Nota 4 asks for the exemption in 12 and 4T only; any other period may omit it."""
    payload = _m303_instance_evidence(Period.from_year_and_code(2026, period_code)).model_dump(mode="python")
    payload["exonerado_390"] = None
    payload["annual_volume_nonzero"] = None

    if required:
        with pytest.raises(ValidationError, match="Modelo 390 exemption"):
            M303FilingInstanceEvidence.model_validate(payload)
    else:
        assert M303FilingInstanceEvidence.model_validate(payload).exonerado_390 is None


def test_m303_filing_facts_without_the_exemption_question_print_zero_for_both_marks() -> None:
    """Outside the last period both DP30301 fields 23 and 24 carry "0", whether or not evidence was stored."""
    facts = _m303_filing_facts(period_code="2T").model_copy(
        update={"exonerado_390": None, "annual_volume_nonzero": None}
    )

    lexicals = m303_filing_lexicals(facts)

    assert (lexicals.exonerado_390_applicable, lexicals.annual_volume_nonzero) == ("0", "0")


def test_m303_last_period_filing_facts_refuse_a_missing_exemption_question() -> None:
    payload = _m303_filing_facts(period_code="4T").model_dump(mode="python")
    payload["exonerado_390"] = None

    with pytest.raises(ValidationError, match="Modelo 390 exemption"):
        M303FilingFacts.model_validate(payload)
