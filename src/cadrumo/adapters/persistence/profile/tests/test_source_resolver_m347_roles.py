"""Modelo 347 classification and filer-role tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext
from cadrumo.core.aggregation import ThirdPartyDeclarationRole, TravelAgencyMediationType
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.calculations.registry.tests.registry_tree import bundled_registry_tree
from cadrumo.domain.invoices.models import Invoice
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from .source_resolver_test_support import (
    _BUCKET_ID,
    _domestic_invoice,
    _invoice,
    _m347_2026_context,
    _modelo_revision,
    _public_administration_profile_facts,
    _public_resolution,
    _resolver,
    _statutory_information_duty_profile_facts,
    _unsettled_reading_refs,
)
from .source_resolver_test_support import _generation_pinned_authority as _generation_pinned_authority
from .source_resolver_test_support import secure_profile as secure_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


# ---------------------------------------------------------------------------


def _capability_bucket_invoices(bucket_id: str) -> tuple[Invoice, ...]:
    """Invoices covering every capability that reaches M347 or M349."""
    return (
        # Domestic, over the M347 declaration floor, carrying a recargo and a
        # retencion: both must ride through without disturbing the declared
        # figures, since neither is an M347 concept.
        _invoice(
            bucket_id=bucket_id,
            kind=InvoiceKind.ISSUED,
            invoice_number="CAP-ES-001",
            issued_at=date(2026, 2, 3),
            counterparty_tax_id="B12345674",
            counterparty_name="Cliente Domestico SL",
            counterparty_country="ES",
            base_total=Decimal("4000.00"),
            iva_category=IvaCategory("domestic_zero"),
        ),
        # Intra-community supply of goods -> M349 clave E.
        _invoice(
            bucket_id=bucket_id,
            kind=InvoiceKind.ISSUED,
            invoice_number="CAP-DE-001",
            issued_at=date(2026, 2, 10),
            counterparty_tax_id="DE345678901",
            counterparty_name="Kunde GmbH",
            counterparty_country="DE",
            base_total=Decimal("1500.00"),
            iva_category=IvaCategory("intra_community_supply"),
        ),
        # Intra-community acquisition of SERVICES -> M349 clave I. This is the
        # class the resolver docstring once claimed no IVA category could
        # express, so its presence here is deliberate.
        _invoice(
            bucket_id=bucket_id,
            kind=InvoiceKind.RECEIVED,
            invoice_number="CAP-IT-001",
            issued_at=date(2026, 3, 5),
            counterparty_tax_id="IT12345678901",
            counterparty_name="Servizi SRL",
            counterparty_country="IT",
            base_total=Decimal("800.00"),
            iva_category=IvaCategory("intra_community_service_acquisition_reverse_charge"),
        ),
    )


def test_capability_parity_m349_declares_every_intracommunity_capability(
    secure_profile: TestRuntimeProfile,
) -> None:
    """Both M349 directions and both claves survive the canonical path together.

    Run as one bucket rather than as separate single-invoice cases: the
    declarante summaries aggregate across records, so an error that only shows
    up when a supply and an acquisition are counted together -- a mis-signed
    fold, a direction collapsed onto one clave -- is invisible to per-invoice
    tests and is exactly what a parity proof exists to catch.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    repository.save(build_invoice_catalogue(_capability_bucket_invoices(_BUCKET_ID)))
    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))

    resolution = _resolver(repository).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="349",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=snapshot.revision,
        ),
    )

    from cadrumo.domain.modelos.row_models import Modelo349OperadorRow

    rows = [row for row in resolution.detail_rows if isinstance(row, Modelo349OperadorRow)]
    by_clave = {row.clave_operacion: row for row in rows}
    assert set(by_clave) == {"E", "I"}, by_clave
    assert by_clave["E"].nif_comunitario == "DE345678901"
    assert by_clave["E"].codigo_pais == "DE"
    assert by_clave["E"].importe == Decimal("1500.00")
    assert by_clave["I"].nif_comunitario == "IT12345678901"
    assert by_clave["I"].codigo_pais == "IT"
    assert by_clave["I"].importe == Decimal("800.00")
    # The domestic invoice is not an intra-community operation and must not
    # appear, so the proof also pins that the bucket is not over-declared.
    assert len(rows) == 2


def test_capability_parity_m347_excludes_the_intracommunity_operations(
    secure_profile: TestRuntimeProfile,
) -> None:
    """M347 excludes the intra-community operations, by CLASSIFICATION not country.

    The same bucket as the M349 proof, asserted from the other modelo, because
    the two projections share one resolver and a filter error would move a
    record between them rather than losing it -- a shape that a single-modelo
    proof reads as correct. The DE/IT invoices this fixture excludes from
    M347 carry a genuine intra-community `IvaCategory`
    (RD 1065/2007 art. 33.2.i), not merely a non-ES country; see
    `test_m347_declares_an_ordinary_operation_with_a_nonresident_counterparty`
    for the discrimination this test alone cannot prove -- a non-resident
    counterparty under an ORDINARY operation still reaches the declaration.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    repository.save(build_invoice_catalogue(_capability_bucket_invoices(_BUCKET_ID)))

    resolution = _resolver(repository).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="347",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "0A"),
            revision=_modelo_revision("347", "2011-2024"),
        ),
    )

    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("1")
    assert resolution.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("4000.00")


def test_m347_declares_an_ordinary_operation_with_a_nonresident_counterparty(
    secure_profile: TestRuntimeProfile,
) -> None:
    """A non-resident counterparty under an ordinary SERVICE operation REACHES M347.

    RD 1065/2007 art. 33.2 is a closed exclusion list whose
    residency-adjacent items are the filer's own foreign permanent
    establishment, operations reported through a coincident informativa and,
    in letter g, the imports and exports of GOODS -- none covers a service
    rendered to a genuinely non-resident, non-recapitulativa counterparty. A
    US customer of a service not subject to Spanish IVA is exactly that case:
    it must count toward the M347 declarante summary, not vanish silently.
    """
    service_sale = _invoice(
        bucket_id=secure_profile.bucket_id,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-US-2026-001",
        issued_at=date(2026, 4, 1),
        counterparty_tax_id="US000000001",
        counterparty_name="Acme Imports Inc",
        counterparty_country="US",
        base_total=Decimal("4000.00"),
        iva_category=IvaCategory("operacion_no_sujeta"),
    )
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    repository.save(build_invoice_catalogue((service_sale,)))

    resolution = _resolver(repository).resolve(
        CalculationSourceContext(
            bucket_id=secure_profile.bucket_id,
            modelo="347",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "0A"),
            revision=_modelo_revision("347", "2011-2024"),
        ),
    )

    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("1")
    assert resolution.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("4000.00")


@pytest.mark.parametrize(
    ("kind", "category"),
    [
        pytest.param(InvoiceKind.ISSUED, "export_third_country_zero_rated", id="goods-export"),
        pytest.param(InvoiceKind.RECEIVED, "import_third_country", id="goods-import"),
    ],
)
def test_m347_excludes_the_imports_and_exports_of_goods(
    secure_profile: TestRuntimeProfile,
    kind: InvoiceKind,
    category: str,
) -> None:
    """Art. 33.2.g: "Las importaciones y exportaciones de mercancías" are not declared.

    The same US counterparty and amount that a service declares above: only the
    goods category differs, so the exclusion reads the operation, never the
    residence.
    """
    goods = _invoice(
        bucket_id=None,
        kind=kind,
        invoice_number=f"M347-GOODS-{kind.value.upper()}-2026-001",
        issued_at=date(2026, 4, 1),
        counterparty_tax_id="US000000001",
        counterparty_name="Acme Imports Inc",
        counterparty_country="US",
        base_total=Decimal("4000.00"),
        iva_category=IvaCategory(category),
    )

    resolution = _public_resolution((goods,), context=_m347_2026_context(secure_profile.bucket_id))

    assert resolution.provenance == ()
    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("0")
    assert resolution.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("0")
    assert _unsettled_reading_refs(resolution) == []


def test_m347_declares_an_operation_assimilated_to_an_export_and_discloses_the_open_exclusion(
    secure_profile: TestRuntimeProfile,
) -> None:
    """An operation assimilated to an export may be goods or services; it stays declared with an advisory."""
    assimilated = _invoice(
        bucket_id=None,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-ASIMILADA-2026-001",
        issued_at=date(2026, 4, 1),
        counterparty_tax_id="US000000001",
        counterparty_name="Acme Shipping Inc",
        counterparty_country="US",
        base_total=Decimal("4000.00"),
        iva_category=IvaCategory("export_assimilated_zero_rated"),
    )

    resolution = _public_resolution((assimilated,), context=_m347_2026_context(secure_profile.bucket_id))

    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("1")
    assert _unsettled_reading_refs(resolution) == ["m347-exclusion:iva-category"]
    advisory = next(item for item in resolution.diagnostics if item.reason == "unsettled_legal_reading")
    assert "M347-ASIMILADA-2026-001" in advisory.message
    assert advisory.asserted_legal_refs == ("rd-1065-2007:art-33.2.g",)


def _withheld_invoice(bucket_id: str, *, kind: InvoiceKind, invoice_number: str) -> Invoice:
    return _domestic_invoice(
        bucket_id=bucket_id,
        kind=kind,
        invoice_number=invoice_number,
        issued_at=date(2026, 3, 10),
        counterparty_tax_id="B12345674",
        counterparty_name="Profesional Retenido SL",
        base_total=Decimal("3500.00"),
        iva_total=Decimal("735.00"),
    ).model_copy(update={"retention_rate": Decimal("0.15"), "retention_amount": Decimal("525.00")})


def test_m347_excludes_a_received_invoice_whose_withholding_the_filer_declares_annually(
    secure_profile: TestRuntimeProfile,
) -> None:
    """Art. 33.2.i with RIRPF art. 108.2: the payer reports the operation in its withholding summary.

    The same received invoice without the withholding is declared, so what
    excludes it is the withholding alone.
    """
    withheld = _withheld_invoice(
        secure_profile.bucket_id, kind=InvoiceKind.RECEIVED, invoice_number="M347-RETENIDA-REC-2026-001"
    )
    unwithheld = withheld.model_copy(update={"retention_rate": None, "retention_amount": None})
    context = _m347_2026_context(secure_profile.bucket_id)

    excluded = _public_resolution((withheld,), context=context)
    declared = _public_resolution((unwithheld,), context=context)

    assert excluded.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("0")
    assert _unsettled_reading_refs(excluded) == []
    assert declared.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("1")
    assert declared.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("4235.00")


def test_m347_declares_an_issued_invoice_withheld_by_the_customer_and_discloses_it(
    secure_profile: TestRuntimeProfile,
) -> None:
    """The withheld party has no withholding summary of its own, so its side stays declared and disclosed.

    The advisory must not tell a landlord of business premises that the lease may
    drop out: art. 34.1.d has the landlord relate it. This invoice records no
    lease, so the advisory names it and points at the lease fact that would
    take it out of the unsettled set.
    """
    withheld = _withheld_invoice(
        secure_profile.bucket_id, kind=InvoiceKind.ISSUED, invoice_number="M347-RETENIDA-EMI-2026-001"
    )

    resolution = _public_resolution((withheld,), context=_m347_2026_context(secure_profile.bucket_id))

    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("1")
    assert _unsettled_reading_refs(resolution) == ["m347-exclusion:withheld-issued-invoice"]
    advisory = next(item for item in resolution.diagnostics if item.reason == "unsettled_legal_reading")
    assert advisory.asserted_legal_refs == (
        "rd-1065-2007:art-33.2.i",
        "rd-1065-2007:art-34.1.d",
        "rd-439-2007:art-108",
    )
    assert "None of them records a business-premises lease" in advisory.message
    assert advisory.remedy is not None
    assert "lease of a local de negocio" in advisory.remedy


def test_m347_clave_f_declares_a_mediated_sale_ordinary_sale_of_the_same_amount_does_not(
    secure_profile: TestRuntimeProfile,
) -> None:
    """The discrimination this test exists to prove, not just the classification.

    A travel agency's ISSUED invoice under RD 1619/2012 disposición adicional
    cuarta declares clave F. An ORDINARY issued invoice of the identical
    amount, direction and counterparty -- carrying no mediation fact -- must
    NOT declare F: it falls through to the ordinary clave B. Varying only the
    mediation fact, nothing else, is what proves the classifier reads the
    fact rather than the amount or direction.
    """
    context = CalculationSourceContext(
        bucket_id=secure_profile.bucket_id,
        modelo="347",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "0A"),
        revision=_modelo_revision("347", "2025-y-siguientes"),
    )
    mediated_sale = _invoice(
        bucket_id=None,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-AGENCY-2026-001",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="B12345674",
        counterparty_name="Cliente Agencia SL",
        counterparty_country="ES",
        base_total=Decimal("3500.00"),
        iva_category=IvaCategory("domestic_general"),
    )
    mediated_sale = mediated_sale.model_copy(
        update={"travel_agency_mediation": TravelAgencyMediationType.from_registry("mediated_service")},
    )
    ordinary_sale = _invoice(
        bucket_id=None,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-ORDINARY-2026-001",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="B12345674",
        counterparty_name="Cliente Agencia SL",
        counterparty_country="ES",
        base_total=Decimal("3500.00"),
        iva_category=IvaCategory("domestic_general"),
    )
    assert ordinary_sale.travel_agency_mediation is None

    resolution = _public_resolution((mediated_sale, ordinary_sale), context=context)

    assert {item.source_ref for item in resolution.provenance} == {
        f"collectible_invoice:{mediated_sale.invoice_id}",
        f"collectible_invoice:{ordinary_sale.invoice_id}",
    }
    assert resolution.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("7000.00")


def test_m347_clave_g_declares_only_air_transport_purchases_not_other_mediated_purchases(
    secure_profile: TestRuntimeProfile,
) -> None:
    """Clave G is narrower than F: only air passenger transport, RECEIVED direction.

    A RECEIVED invoice for a mediated but NON-air service (e.g. hostelería)
    is neither F nor G by the diseño's own text, and must fall through to the
    ordinary clave A rather than being fabricated into G.
    """
    context = CalculationSourceContext(
        bucket_id=secure_profile.bucket_id,
        modelo="347",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "0A"),
        revision=_modelo_revision("347", "2025-y-siguientes"),
    )
    air_transport_purchase = _invoice(
        bucket_id=None,
        kind=InvoiceKind.RECEIVED,
        invoice_number="M347-AIR-2026-001",
        issued_at=date(2026, 5, 2),
        counterparty_tax_id="B11223344",
        counterparty_name="Agencia de Viajes SA",
        counterparty_country="ES",
        base_total=Decimal("1200.00"),
        iva_category=IvaCategory("domestic_general"),
    )
    air_transport_purchase = air_transport_purchase.model_copy(
        update={"travel_agency_mediation": TravelAgencyMediationType.from_registry("air_passenger_transport")},
    )
    non_air_mediated_purchase = _invoice(
        bucket_id=None,
        kind=InvoiceKind.RECEIVED,
        invoice_number="M347-HOTEL-2026-001",
        issued_at=date(2026, 5, 2),
        counterparty_tax_id="B11223344",
        counterparty_name="Agencia de Viajes SA",
        counterparty_country="ES",
        base_total=Decimal("1200.00"),
        iva_category=IvaCategory("domestic_general"),
    )
    non_air_mediated_purchase = non_air_mediated_purchase.model_copy(
        update={"travel_agency_mediation": TravelAgencyMediationType.from_registry("mediated_service")},
    )

    resolution = _public_resolution((air_transport_purchase, non_air_mediated_purchase), context=context)

    assert {item.source_ref for item in resolution.provenance} == {
        f"payable_invoice:{air_transport_purchase.invoice_id}",
        f"payable_invoice:{non_air_mediated_purchase.invoice_id}",
    }
    assert resolution.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("0")


def test_m347_filer_declaration_roles_fails_closed_to_empty_for_a_profile_absent_bucket(
    secure_profile: TestRuntimeProfile,
) -> None:
    """No `UserProfileRecord` was ever seeded for this bucket -- a real absent profile.

    Exercises the real repository's `ProfileNotFoundError` path, not a mock:
    the loader must fail closed to an empty role set rather than raising, so
    an M347 filer whose profile is otherwise incomplete or unset still
    reaches claves A, B, F and G, and simply carries no C/D/E eligibility.
    """
    purchase = _invoice(
        bucket_id=None,
        kind=InvoiceKind.RECEIVED,
        invoice_number="M347-ABSENT-ROLE-2026-001",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="C3333333G",
        counterparty_name="Proveedor SL",
        counterparty_country="ES",
        base_total=Decimal("3500.00"),
        iva_category=IvaCategory("domestic_general"),
    )
    resolution = _public_resolution(
        (purchase,),
        context=CalculationSourceContext(
            bucket_id=secure_profile.bucket_id,
            modelo="347",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "0A"),
            revision=_modelo_revision("347", "2025-y-siguientes"),
        ),
    )
    # The one advisory left is the record gap every Spanish declarado carries
    # (its provincia is not held as structured data), never a role advisory.
    assert [item.source_ref for item in resolution.diagnostics] == ["m347-record:provincia-not-recorded"]
    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("1")


def test_m347_filer_declaration_roles_reaches_a_role_set_by_the_real_operator_path(
    secure_profile: TestRuntimeProfile,
) -> None:
    """The role set must be reachable from a REAL persisted profile, not only a test object.

    The role axis arrived with a fail-closed loader but left `declaration_roles`
    with no operator-input path -- `taxpayer_profile_from_mapping` never read
    or wrote it, so no real persisted profile could ever carry a non-empty
    value. This seeds a real `UserProfileRecord` (the wizard-facts shape) and
    proves the SAME loader the M347 resolver calls resolves a non-empty role
    set through the real projection, not a directly-constructed
    `TaxpayerProfile`.
    """
    facts = (
        UserProfileFact(path="identity.tax_id", value="B12345674"),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="iva.regime", value="GENERAL"),
        UserProfileFact(path="iva.m303_regime_composition", value="general"),
        UserProfileFact(path="iva.redeme_enrolled", value=False),
        UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
        UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
        UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        UserProfileFact(
            path="taxpayer_type.declaration_roles",
            value=ThirdPartyDeclarationRole.from_registry("third_party_fee_collector").value,
        ),
    )
    seed_test_profile_record(
        _create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=secure_profile.bucket_id,
            facts=facts,
            context=_profile_creation_context_for_test(),
        ),
    )

    collection = _invoice(
        bucket_id=None,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-ROLE-COLLECTION-2026-001",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="C3333333G",
        counterparty_name="Cliente Pagador SL",
        counterparty_country="ES",
        base_total=Decimal("3500.00"),
        iva_category=IvaCategory("domestic_general"),
    ).model_copy(
        update={
            "collected_on_behalf_of_tax_id": "A87654321",
            "collected_on_behalf_of_name": "Colegiado Beneficiario SL",
        },
    )
    ordinary = _invoice(
        bucket_id=None,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-ROLE-ORDINARY-2026-001",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="C3333333G",
        counterparty_name="Cliente Pagador SL",
        counterparty_country="ES",
        base_total=Decimal("3500.00"),
        iva_category=IvaCategory("domestic_general"),
    )
    resolution = _public_resolution(
        (collection, ordinary),
        context=CalculationSourceContext(
            bucket_id=secure_profile.bucket_id,
            modelo="347",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "0A"),
            revision=_modelo_revision("347", "2025-y-siguientes"),
        ),
    )
    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("2")
    assert resolution.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("7000.00")


def _third_party_fee_collector_profile_facts() -> tuple[UserProfileFact, ...]:
    return (
        UserProfileFact(path="identity.tax_id", value="B12345674"),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="iva.regime", value="GENERAL"),
        UserProfileFact(path="iva.m303_regime_composition", value="general"),
        UserProfileFact(path="iva.redeme_enrolled", value=False),
        UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
        UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
        UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        UserProfileFact(
            path="taxpayer_type.declaration_roles",
            value=ThirdPartyDeclarationRole.from_registry("third_party_fee_collector").value,
        ),
    )


def test_m347_clave_c_declares_the_beneficiary_not_the_payer_through_the_real_resolver(
    secure_profile: TestRuntimeProfile,
) -> None:
    """Clave C production reachability: a real filer, a real profile, the real resolver.

    A colegio profesional that collects fees on behalf of its colegiados
    (RD 1065/2007 art. 31.3) receives a payment from a CLIENT, but the M347
    row it declares must name the COLEGIADO on whose behalf the fee was
    collected (art. 34.g), not the client who paid. An ORDINARY invoice from
    the SAME collecting-entity filer, carrying no beneficiary fact, must NOT
    become clave C -- the role alone is not sufficient, proving the
    classifier reads both facts together, not either one.
    """
    seed_test_profile_record(
        _create_profile_record_for_test(
            context=_profile_creation_context_for_test(),
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=secure_profile.bucket_id,
            facts=_third_party_fee_collector_profile_facts(),
        ),
    )
    context = CalculationSourceContext(
        bucket_id=secure_profile.bucket_id,
        modelo="347",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "0A"),
        revision=_modelo_revision("347", "2025-y-siguientes"),
    )

    collection_invoice = _invoice(
        bucket_id=None,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-COBRO-2026-001",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="C3333333G",
        counterparty_name="Cliente Pagador SL",
        counterparty_country="ES",
        base_total=Decimal("3500.00"),
        iva_category=IvaCategory("domestic_general"),
    )
    collection_invoice = collection_invoice.model_copy(
        update={
            "collected_on_behalf_of_tax_id": "A87654321",
            "collected_on_behalf_of_name": "Colegiado Beneficiario SL",
        },
    )
    ordinary_invoice = _invoice(
        bucket_id=None,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-ORDINARIA-2026-001",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="C3333333G",
        counterparty_name="Cliente Pagador SL",
        counterparty_country="ES",
        base_total=Decimal("3500.00"),
        iva_category=IvaCategory("domestic_general"),
    )
    assert ordinary_invoice.collected_on_behalf_of_tax_id is None

    resolution = _public_resolution((collection_invoice, ordinary_invoice), context=context)

    assert {item.source_ref for item in resolution.provenance} == {
        f"collectible_invoice:{collection_invoice.invoice_id}",
        f"collectible_invoice:{ordinary_invoice.invoice_id}",
    }
    # The public summary sees two parties only when the persisted collector role
    # causes the collected amount to be attributed to its beneficiary.
    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("2")
    assert resolution.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("7000.00")


def test_m347_clave_c_requires_the_filer_role_a_beneficiary_fact_alone_is_not_enough(
    secure_profile: TestRuntimeProfile,
) -> None:
    """The other half of the AND: a beneficiary fact without the filer's own role does not declare C.

    Guards against a fact injected on an invoice from reclassifying a row
    for a filer who never declared the collecting-entity role -- the role
    must be attested on the PROFILE, not merely implied by the invoice.
    """
    context = CalculationSourceContext(
        bucket_id=secure_profile.bucket_id,
        modelo="347",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "0A"),
        revision=_modelo_revision("347", "2025-y-siguientes"),
    )
    collection_shaped_invoice = _invoice(
        bucket_id=None,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-COBRO-2026-002",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="C3333333G",
        counterparty_name="Cliente Pagador SL",
        counterparty_country="ES",
        base_total=Decimal("3500.00"),
        iva_category=IvaCategory("domestic_general"),
    )
    collection_shaped_invoice = collection_shaped_invoice.model_copy(
        update={
            "collected_on_behalf_of_tax_id": "A87654321",
            "collected_on_behalf_of_name": "Colegiado Beneficiario SL",
        },
    )

    ordinary_invoice = _invoice(
        bucket_id=None,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-COBRO-2026-003",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="C3333333G",
        counterparty_name="Cliente Pagador SL",
        counterparty_country="ES",
        base_total=Decimal("3500.00"),
        iva_category=IvaCategory("domestic_general"),
    )
    resolution = _public_resolution((collection_shaped_invoice, ordinary_invoice), context=context)

    assert {item.source_ref for item in resolution.provenance} == {
        f"collectible_invoice:{collection_shaped_invoice.invoice_id}",
        f"collectible_invoice:{ordinary_invoice.invoice_id}",
    }
    # Without the filer's persisted role, both records remain the same payer.
    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("1")
    assert resolution.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("7000.00")


def test_m347_clave_e_declares_a_subvencion_from_a_public_administration_ordinary_payment_does_not(
    secure_profile: TestRuntimeProfile,
) -> None:
    """Clave E production reachability, proven in both directions.

    A PUBLIC_ADMINISTRATION_ENTITY filer's subvención/ayuda declares clave E
    (RD 1065/2007 art. 31.2's second paragraph). An ORDINARY payment from the
    SAME filer of the identical amount, carrying no subvención fact, must
    NOT become clave E -- it falls through to the ordinary clave A/B
    classification, proving the role alone is not sufficient.
    """
    seed_test_profile_record(
        _create_profile_record_for_test(
            context=_profile_creation_context_for_test(),
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=secure_profile.bucket_id,
            facts=_public_administration_profile_facts(),
        ),
    )
    context = CalculationSourceContext(
        bucket_id=secure_profile.bucket_id,
        modelo="347",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "0A"),
        revision=_modelo_revision("347", "2025-y-siguientes"),
    )

    subvencion_invoice = _invoice(
        bucket_id=None,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-SUBVENCION-2026-001",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="C3333333G",
        counterparty_name="Beneficiario Subvencion SL",
        counterparty_country="ES",
        base_total=Decimal("3500.00"),
        iva_category=IvaCategory("domestic_general"),
    )
    subvencion_invoice = subvencion_invoice.model_copy(update={"is_subvencion_ayuda": True})
    ordinary_invoice = _invoice(
        bucket_id=None,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-PAGO-ORDINARIO-2026-001",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="C3333333G",
        counterparty_name="Beneficiario Subvencion SL",
        counterparty_country="ES",
        base_total=Decimal("3500.00"),
        iva_category=IvaCategory("domestic_general"),
    )
    ordinary_invoice = ordinary_invoice.model_copy(update={"is_subvencion_ayuda": False})
    assert ordinary_invoice.is_subvencion_ayuda is False

    resolution = _public_resolution((subvencion_invoice, ordinary_invoice), context=context)

    assert {item.source_ref for item in resolution.provenance} == {
        f"collectible_invoice:{subvencion_invoice.invoice_id}",
        f"collectible_invoice:{ordinary_invoice.invoice_id}",
    }
    # The same counterparty under two claves is two declarado records, and the type 1
    # count is the number of records (designs 2011 and 2025, positions 136-144).
    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("2")
    assert resolution.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("7000.00")


def test_m347_clave_e_requires_the_public_administration_role_a_subvencion_fact_alone_is_not_enough(
    secure_profile: TestRuntimeProfile,
) -> None:
    """The other half of the AND: a subvención fact without the public-administration role does not declare E."""
    context = CalculationSourceContext(
        bucket_id=secure_profile.bucket_id,
        modelo="347",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "0A"),
        revision=_modelo_revision("347", "2025-y-siguientes"),
    )
    subvencion_shaped_invoice = _invoice(
        bucket_id=None,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-SUBVENCION-2026-002",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="C3333333G",
        counterparty_name="Beneficiario Subvencion SL",
        counterparty_country="ES",
        base_total=Decimal("3500.00"),
        iva_category=IvaCategory("domestic_general"),
    )
    subvencion_shaped_invoice = subvencion_shaped_invoice.model_copy(update={"is_subvencion_ayuda": True})

    resolution = _public_resolution((subvencion_shaped_invoice,), context=context)

    assert {item.source_ref for item in resolution.provenance} == {
        f"collectible_invoice:{subvencion_shaped_invoice.invoice_id}",
    }
    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("1")


def test_m347_clave_d_declares_an_acquisition_outside_activity_the_same_activity_purchase_does_not(
    secure_profile: TestRuntimeProfile,
) -> None:
    """Clave D production reachability: a mixed-activity filer, proven in both directions.

    A statutory-information-duty filer (e.g. a public body running a genuine
    side business) makes two acquisitions of the SAME amount: one al margen
    de su actividad empresarial (clave D), one WITHIN it (ordinary clave A).
    Only the transaction-level fact distinguishes them -- the role alone
    would misclassify the second as D too.
    """
    seed_test_profile_record(
        _create_profile_record_for_test(
            context=_profile_creation_context_for_test(),
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=secure_profile.bucket_id,
            facts=_statutory_information_duty_profile_facts(),
        ),
    )
    context = CalculationSourceContext(
        bucket_id=secure_profile.bucket_id,
        modelo="347",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "0A"),
        revision=_modelo_revision("347", "2025-y-siguientes"),
    )

    outside_activity_purchase = _invoice(
        bucket_id=None,
        kind=InvoiceKind.RECEIVED,
        invoice_number="M347-AL-MARGEN-2026-001",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="C3333333G",
        counterparty_name="Proveedor Al Margen SL",
        counterparty_country="ES",
        base_total=Decimal("3500.00"),
        iva_category=IvaCategory("domestic_general"),
    )
    outside_activity_purchase = outside_activity_purchase.model_copy(update={"outside_economic_activity": True})
    within_activity_purchase = _invoice(
        bucket_id=None,
        kind=InvoiceKind.RECEIVED,
        invoice_number="M347-DENTRO-ACTIVIDAD-2026-001",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="C3333333G",
        counterparty_name="Proveedor Al Margen SL",
        counterparty_country="ES",
        base_total=Decimal("3500.00"),
        iva_category=IvaCategory("domestic_general"),
    )
    within_activity_purchase = within_activity_purchase.model_copy(update={"outside_economic_activity": False})

    resolution = _public_resolution((outside_activity_purchase, within_activity_purchase), context=context)

    assert {item.source_ref for item in resolution.provenance} == {
        f"payable_invoice:{outside_activity_purchase.invoice_id}",
        f"payable_invoice:{within_activity_purchase.invoice_id}",
    }
    # The same counterparty under two claves is two declarado records, and the type 1
    # count is the number of records (designs 2011 and 2025, positions 136-144).
    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("2")
    assert resolution.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("7000.00")


def test_m347_clave_d_requires_the_filer_role_the_fact_alone_is_not_enough(
    secure_profile: TestRuntimeProfile,
) -> None:
    """The other half of the AND: the al-margen fact without any of D's four roles does not declare D."""
    context = CalculationSourceContext(
        bucket_id=secure_profile.bucket_id,
        modelo="347",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "0A"),
        revision=_modelo_revision("347", "2025-y-siguientes"),
    )
    outside_activity_shaped_purchase = _invoice(
        bucket_id=None,
        kind=InvoiceKind.RECEIVED,
        invoice_number="M347-AL-MARGEN-2026-002",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="C3333333G",
        counterparty_name="Proveedor Al Margen SL",
        counterparty_country="ES",
        base_total=Decimal("3500.00"),
        iva_category=IvaCategory("domestic_general"),
    )
    outside_activity_shaped_purchase = outside_activity_shaped_purchase.model_copy(
        update={"outside_economic_activity": True},
    )

    resolution = _public_resolution((outside_activity_shaped_purchase,), context=context)

    assert {item.source_ref for item in resolution.provenance} == {
        f"payable_invoice:{outside_activity_shaped_purchase.invoice_id}",
    }
    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("1")


def test_m347_role_fact_advisories_fires_only_for_a_role_carrying_filer_with_the_fact_unset(
    secure_profile: TestRuntimeProfile,
) -> None:
    """The advisory is proportionate: it never fires for a filer with no clave D/E role."""
    context = CalculationSourceContext(
        bucket_id=secure_profile.bucket_id,
        modelo="347",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "0A"),
        revision=_modelo_revision("347", "2025-y-siguientes"),
    )
    unrelated_purchase = _invoice(
        bucket_id=None,
        kind=InvoiceKind.RECEIVED,
        invoice_number="M347-SIN-ROL-2026-001",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="C3333333G",
        counterparty_name="Proveedor SL",
        counterparty_country="ES",
        base_total=Decimal("3500.00"),
        iva_category=IvaCategory("domestic_general"),
    )

    diagnostics = _public_resolution((unrelated_purchase,), context=context).diagnostics

    # No role advisory; the one diagnostic is the provincia gap every Spanish declarado carries.
    assert [item.source_ref for item in diagnostics] == ["m347-record:provincia-not-recorded"]


def test_m347_role_fact_advisories_fires_for_an_unset_clave_d_fact_and_not_once_declared(
    secure_profile: TestRuntimeProfile,
) -> None:
    """A D-role filer's RECEIVED invoice with the fact undeclared surfaces an advisory; declaring it clears it."""
    seed_test_profile_record(
        _create_profile_record_for_test(
            context=_profile_creation_context_for_test(),
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=secure_profile.bucket_id,
            facts=_statutory_information_duty_profile_facts(),
        ),
    )
    context = CalculationSourceContext(
        bucket_id=secure_profile.bucket_id,
        modelo="347",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "0A"),
        revision=_modelo_revision("347", "2025-y-siguientes"),
    )
    undeclared_purchase = _invoice(
        bucket_id=None,
        kind=InvoiceKind.RECEIVED,
        invoice_number="M347-SIN-DECLARAR-2026-001",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="C3333333G",
        counterparty_name="Proveedor SL",
        counterparty_country="ES",
        base_total=Decimal("3500.00"),
        iva_category=IvaCategory("domestic_general"),
    )
    declared_purchase = undeclared_purchase.model_copy(update={"outside_economic_activity": False})

    # Both resolutions also carry the provincia gap every Spanish declarado has;
    # it is asserted exactly so that nothing else can hide beside the role advisory.
    provincia_gap = "m347-record:provincia-not-recorded"
    undeclared_all = _public_resolution((undeclared_purchase,), context=context).diagnostics
    declared_all = _public_resolution((declared_purchase,), context=context).diagnostics
    undeclared_diagnostics = tuple(item for item in undeclared_all if item.source_ref != provincia_gap)
    declared_diagnostics = tuple(item for item in declared_all if item.source_ref != provincia_gap)

    assert [item.source_ref for item in undeclared_all].count(provincia_gap) == 1
    assert [item.source_ref for item in declared_all] == [provincia_gap]
    assert len(undeclared_diagnostics) == 1
    assert undeclared_diagnostics[0].reason == "unclassified_declarant_role_fact"
    assert undeclared_diagnostics[0].source_ref == f"invoice:{undeclared_purchase.invoice_id}"
    assert undeclared_diagnostics[0].remedy
    assert declared_diagnostics == ()
