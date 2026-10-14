"""Modelo 349 resolver classification tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from cadrumo.adapters.outbound.fx.ecb_provider import ECB_RATE_SOURCE_ID
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext
from cadrumo.application.invoices.source_resolver import M349_CLAVE_INFERRED_REASON
from cadrumo.core.aggregation import IntracomOperationType
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.calculations.registry.tests.registry_tree import bundled_registry_tree
from cadrumo.domain.invoices.models import Invoice
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.domain.modelos.row_models import Modelo349OperadorRow

from .source_resolver_test_support import (
    _BUCKET_ID,
    _clave_probe_invoice,
    _invoice,
    _public_m349_claves,
    _public_resolution,
    _resolver,
)
from .source_resolver_test_support import _generation_pinned_authority as _generation_pinned_authority
from .source_resolver_test_support import secure_profile as secure_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_converted_foreign_invoice_projects_its_euro_value_not_its_face_value(
    secure_profile: TestRuntimeProfile,
) -> None:
    """A GBP invoice contributes euro, so the declared importe is the converted amount.

    ECB EXR.D.GBP.EUR.SP00.A on 2026-01-15 is stubbed here as the stored
    GBP->EUR multiplier; 1000.00 GBP at that rate is 1187.89 EUR. Declaring the
    face value 1000.00 would over- or under-state the modelo by the FX spread.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    gbp_rate = Decimal("1") / Decimal("0.84183")
    converted = _invoice(
        bucket_id=_BUCKET_ID,
        invoice_number="F-2026-010",
        issued_at=date(2026, 1, 15),
        counterparty_tax_id="DE123456789",
        base_total=Decimal("1000.00"),
        iva_category=IvaCategory("intra_community_supply"),
        currency="GBP",
        fx_rate=gbp_rate,
        fx_rate_date=date(2026, 1, 15),
        fx_rate_source=ECB_RATE_SOURCE_ID,
    )
    repository.save(build_invoice_catalogue((converted,)))
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

    expected_eur = (Decimal("1000.00") * gbp_rate).quantize(Decimal("0.01"))
    assert expected_eur == Decimal("1187.89")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == expected_eur
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] != Decimal("1000.00")


def test_unconverted_foreign_invoice_is_withheld_from_projection(
    secure_profile: TestRuntimeProfile,
) -> None:
    """A foreign invoice with no resolved rate must not reach the modelo at all.

    Its euro value is unknown, so the only safe outcomes are exclusion or
    refusal -- never declaring the foreign face value as euro. This mirrors the
    ledger's ``is_non_eur_without_conversion`` gate.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    unconverted = _invoice(
        bucket_id=_BUCKET_ID,
        invoice_number="F-2026-011",
        issued_at=date(2026, 1, 15),
        counterparty_tax_id="DE123456789",
        base_total=Decimal("1000.00"),
        iva_category=IvaCategory("intra_community_supply"),
        currency="GBP",
    )
    repository.save(build_invoice_catalogue((unconverted,)))
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

    # No operator counted, and no importe declared from the foreign face value.
    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("0")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] != Decimal("1000.00")


def test_a_service_category_alone_resolves_its_m349_clave() -> None:
    """A record carrying the service category but NO operation_type still files.

    The operation-type branch short-circuits ahead of the category branches, so
    an invoice created through the CLI reaches its clave via ``operation_type``
    and never exercises these lines. A record carrying only the IVA category --
    which the creation service permits, the two fields being independent --
    would otherwise resolve to no clave at all and drop out of the
    recapitulativa silently.

    Asserted on both directions and against the goods claves, because filing a
    service as E or A would report it as an entrega/adquisición de bienes.
    """
    issued = _clave_probe_invoice(InvoiceKind.ISSUED, IvaCategory("intra_community_service_supply"))
    received = _clave_probe_invoice(
        InvoiceKind.RECEIVED,
        IvaCategory("intra_community_service_acquisition_reverse_charge"),
    )

    assert issued.operation_type is None
    assert received.operation_type is None
    assert set(_public_m349_claves((issued, received))) == {"S", "I"}


def test_a_service_category_on_its_impossible_side_resolves_no_clave() -> None:
    """The directional half of the same branch.

    A supply category on a received invoice, or an acquisition category on an
    issued one, describes an operation that does not arise. Resolving a clave
    for it would file a fabricated row, so the branch must decline.
    """
    wrong_way_supply = _clave_probe_invoice(
        InvoiceKind.RECEIVED,
        IvaCategory("intra_community_service_supply"),
    )
    wrong_way_acquisition = _clave_probe_invoice(
        InvoiceKind.ISSUED,
        IvaCategory("intra_community_service_acquisition_reverse_charge"),
    )

    assert _public_m349_claves((wrong_way_supply, wrong_way_acquisition)) == ()


def test_an_explicit_operation_type_resolves_a_clave_without_any_iva_category() -> None:
    """The measured ground for M349 absence being non-disqualifying.

    This is the executable form of the justification in
    ``_m349_incoherent_verdict``. An absent IVA category does not mean the
    operation was inexpressible; it usually means the clave came from the
    explicitly declared operation type, which is consulted first and returns
    without ever reading the category.

    Treating absence as disqualifying would therefore drop exactly the records
    whose clave the operator stated most directly. If this ever fails, that
    justification is void and the guard must be re-decided rather than
    re-explained.
    """
    invoice = _invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        invoice_number="EXPLICIT-CLAVE-001",
        issued_at=date(2026, 2, 1),
        counterparty_tax_id="DE345678901",
        counterparty_country="DE",
        base_total=Decimal("100.00"),
        iva_category=IvaCategory("intra_community_supply"),
    ).model_copy(update={"iva_category": None, "operation_type": IntracomOperationType.E})

    assert invoice.iva_category is None
    assert _public_m349_claves((invoice,)) == ("E",)


def test_the_intra_community_service_categories_exist_and_map_to_their_claves() -> None:
    """Pins the premise that refuted the previous justification.

    The retired reasoning asserted that intra-community services mapped to no
    IVA category member at all. Both members exist and both resolve to their
    own clave -- kept distinct from the goods claves, because a service
    declared as an entrega would be filed as an entrega de bienes.
    """
    supply = _invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        invoice_number="SERV-S-001",
        issued_at=date(2026, 2, 1),
        counterparty_tax_id="DE345678901",
        counterparty_country="DE",
        base_total=Decimal("100.00"),
        iva_category=IvaCategory("intra_community_service_supply"),
    )
    acquisition = _invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        invoice_number="SERV-I-001",
        issued_at=date(2026, 2, 1),
        counterparty_tax_id="DE345678901",
        counterparty_country="DE",
        base_total=Decimal("100.00"),
        iva_category=IvaCategory("intra_community_service_acquisition_reverse_charge"),
    )

    assert set(_public_m349_claves((supply, acquisition))) == {"S", "I"}


def _m349_resolution(repository: InvoiceCatalogueRepository):
    """Resolve the committed Modelo 349 revision against a saved catalogue."""
    _modelos, _catalogues = bundled_registry_tree()
    _modelo_349 = next(candidate for candidate in _modelos if candidate.id == "349")
    snapshot = SimpleNamespace(revision=select_revision(_modelo_349, filing_year=2026, period="1T"))
    return _resolver(repository).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="349",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision=snapshot.revision,
        ),
    )


def _ic_supply_without_operation_type() -> Invoice:
    """An ordinary exempt intra-community supply, clave unstated.

    The ambiguous record: the resolver must pick a clave, and nothing on the
    invoice says whether the goods were previously imported.
    """
    return _invoice(
        bucket_id=_BUCKET_ID,
        invoice_number="IC-SUPPLY-001",
        issued_at=date(2026, 1, 15),
        counterparty_tax_id="DE123456789",
        base_total=Decimal("1000.00"),
        iva_category=IvaCategory("intra_community_supply"),
    )


def _third_country_import() -> Invoice:
    """An importation in the same bucket -- the fact that makes M/H possible."""
    return _invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        invoice_number="IMPORT-001",
        issued_at=date(2026, 1, 10),
        counterparty_tax_id="US99887766",
        counterparty_country="US",
        base_total=Decimal("800.00"),
        iva_category=IvaCategory("import_third_country"),
        linked_transaction_ids=("2" * 64,),
    )


def _inferred_clave_reasons(resolution) -> list[str]:
    return [d.reason for d in resolution.diagnostics if d.reason == M349_CLAVE_INFERRED_REASON]


def test_an_inferred_entrega_clave_is_disclosed_when_the_bucket_also_holds_an_importation(
    secure_profile: TestRuntimeProfile,
) -> None:
    """The one case the advisory exists for: E was a guess and M/H was possible.

    Clave M (or H) applies only to an intra-community supply following an EXEMPT
    IMPORTATION by the same taxpayer, per LIVA art. 27.12 -- the diseño defines E
    as excluding exactly those. Nothing on the supply records the prior
    importation, so the resolver's E is a guess. Here the bucket holds an
    importation, so the guess could be wrong and the operator is told.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    repository.save(build_invoice_catalogue((_ic_supply_without_operation_type(), _third_country_import())))

    resolution = _m349_resolution(repository)

    assert _inferred_clave_reasons(resolution) == [M349_CLAVE_INFERRED_REASON]
    advisory = next(d for d in resolution.diagnostics if d.reason == M349_CLAVE_INFERRED_REASON)
    # Names the record and both alternatives, so the operator can act without
    # already knowing that clave M exists.
    assert "IC-SUPPLY-001" in advisory.message
    assert "'M'" in advisory.message
    # Advisory-asserted: this resolver holds no revision, snapshot or casilla
    # definition anywhere, so the two LIVA provisions the message states
    # (the ordinary art. 25 exemption and the art. 27.12 carve-out) are
    # declared rather than read off a registry object.
    assert advisory.asserted_legal_refs == ("ley-37-1992:art-25", "ley-37-1992:art-27")
    assert "'H'" in advisory.message


def test_the_same_supply_is_silent_when_the_taxpayer_never_imports(
    secure_profile: TestRuntimeProfile,
) -> None:
    """The negative control, and the reason this is a disclosure not an alarm.

    Byte-identical supply, importation removed. A taxpayer who imports nothing
    cannot have made a post-importation supply, so E is not merely the likely
    clave -- it is the only one available, and an advisory here would fire on
    every Modelo 349 an ordinary EU-trading taxpayer ever files.

    Without this control the positive test above would pass just as well against
    an unconditional advisory, which is the design that was measured and
    rejected.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    repository.save(build_invoice_catalogue((_ic_supply_without_operation_type(),)))

    assert _inferred_clave_reasons(_m349_resolution(repository)) == []


def test_a_stated_operation_type_is_never_disclosed_as_inferred(
    secure_profile: TestRuntimeProfile,
) -> None:
    """A clave the record STATES is not a guess, even with an importation present.

    Separates the two conditions the advisory ANDs together. With the importation
    still in the bucket, the only changed fact is that the supply now declares its
    operation type -- so a screen keying on the importation alone would still fire
    here, and must not.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    stated = _ic_supply_without_operation_type().model_copy(
        update={"operation_type": IntracomOperationType.E},
    )
    repository.save(build_invoice_catalogue((stated, _third_country_import())))

    assert _inferred_clave_reasons(_m349_resolution(repository)) == []


def test_an_unconverted_foreign_invoice_is_excluded_but_reported(
    secure_profile: TestRuntimeProfile,
) -> None:
    """Excluding the amount is right; excluding it in silence is not.

    A foreign-currency invoice with no resolved euro rate must never be declared
    at its face value -- that part is settled, and the sibling test above pins
    it. But the OPERATION is still real and still declarable: a GBP
    intracommunity supply to a German customer belongs on the recapitulativa
    whatever the euro figure turns out to be.

    Dropping it silently leaves the operator filing a Modelo 349 that omits an
    operation, with nothing on any surface saying so. The resolver's own
    incoherence advisory states the principle it must follow here: a missing
    intracomunitaria is an under-declaration whether it was dropped by a
    contradiction or by silence.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    unconverted = _invoice(
        bucket_id=_BUCKET_ID,
        invoice_number="F-2026-012",
        issued_at=date(2026, 1, 15),
        counterparty_tax_id="DE123456789",
        base_total=Decimal("1000.00"),
        iva_category=IvaCategory("intra_community_supply"),
        currency="GBP",
    )
    repository.save(build_invoice_catalogue((unconverted,)))
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

    assert resolution.diagnostics, (
        "the invoice was withheld from Modelo 349 with no advisory: the operator "
        "files a recapitulativa missing a real operation and is never told"
    )
    reported = [
        d
        for d in resolution.diagnostics
        if (d.source_ref is not None and d.source_ref) and unconverted.invoice_id in d.source_ref
    ]
    assert reported, f"no advisory names the withheld invoice: {[d.source_ref for d in resolution.diagnostics]}"
    # The advisory has to say what to DO about it. An operator who cannot act on
    # the message is no better off than one who never saw it.
    assert reported[0].remedy is not None and reported[0].remedy, "the advisory names the problem but not the remedy"


def test_m349_declarable_facts_are_reachable_on_the_canonical_path(
    secure_profile: TestRuntimeProfile,
) -> None:
    """Every M349 fact the slim store contributes must be reachable canonically.

    The counterparty carries BOTH a domestic-format NIF and an EU IVA ID, which
    is the case that separates the two paths. The slim record has no coupling
    between its tax id and its country, so it needs a second identity field and
    a prefix-derivation fallback to decide who is being declared. The canonical
    record reaches the same declared party by a stronger route: a non-ES country
    forces the tax id to BE that country's NIF-IVA, so there is only ever one
    party identity on the aggregate. Same facts, fewer authorities.
    """
    context = CalculationSourceContext(
        bucket_id=secure_profile.bucket_id,
        modelo="349",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision=select_revision(
            next(candidate for candidate in bundled_registry_tree()[0] if candidate.id == "349"),
            filing_year=2026,
            period="1T",
        ),
    )

    # The contract the retired slim store contributed, pinned as literals so
    # the proof outlives the store it conserves. Every value is read straight
    # off the fixture below except ``intracommunity_clave``, which the M349
    # clave table fixes for an ADQUISICION_SERVICIOS operation ("I", servicios
    # adquiridos).
    declared_facts = {
        "party_tax_id": "DE345678901",
        "country_code": "DE",
        "transaction_date": date(2026, 3, 10),
        "base_amount": Decimal("3000.00"),
        "invoice_total_amount": Decimal("3000.00"),
        "intracommunity_clave": "I",
        "operation_clave": None,
        "party_legal_name": "Servizi SRL",
    }

    canonical = _invoice(
        bucket_id=secure_profile.bucket_id,
        kind=InvoiceKind.RECEIVED,
        invoice_number="IT-SERV-2026-001",
        issued_at=date(2026, 3, 10),
        counterparty_tax_id="DE345678901",
        counterparty_name="Servizi SRL",
        counterparty_country="DE",
        base_total=Decimal("3000.00"),
        iva_category=IvaCategory("intra_community_service_acquisition_reverse_charge"),
    )
    resolution = _public_resolution((canonical,), context=context)
    rows = [row for row in resolution.detail_rows if isinstance(row, Modelo349OperadorRow)]
    assert len(rows) == 1
    row = rows[0]
    canonical_facts = {
        "party_tax_id": row.nif_comunitario,
        "country_code": row.codigo_pais,
        "transaction_date": canonical.issued_at,
        "base_amount": row.importe,
        "invoice_total_amount": canonical.grand_total_eur,
        "intracommunity_clave": row.clave_operacion,
        "operation_clave": None,
        "party_legal_name": row.razon_social,
    }

    assert canonical_facts == declared_facts


def test_canonical_invoice_refuses_the_tax_id_country_mismatch_slim_permits(
    secure_profile: TestRuntimeProfile,
) -> None:
    """The mechanism by which canonical conserves M349 party identity.

    This is the other half of the proof above, and it is why the canonical
    aggregate needs no second EU-IVA-ID field. The slim record accepts a
    Spanish-format NIF alongside a German country because nothing couples the
    two, which is exactly what forces it to carry a separate identity field and
    prefer it at projection time. The canonical record refuses that shape: a
    non-ES country validates the tax id against that country's published
    NIF-IVA pattern, so the only representable party identity is already the
    one M349 must declare.

    Adding an EU-IVA-ID field to the canonical aggregate would therefore
    install a SECOND party-identity authority on the record -- two fields that
    can disagree about who was invoiced -- on the axis where a disagreement is
    a mis-declared intra-community operator.
    """
    from pydantic import ValidationError

    # Matched on the message, not merely on the exception type: the point is
    # that the COUNTRY/TAX-ID coupling fired, not that some validator did.
    with pytest.raises(ValidationError, match="DE"):
        _invoice(
            bucket_id=secure_profile.bucket_id,
            kind=InvoiceKind.RECEIVED,
            invoice_number="IT-SERV-2026-002",
            issued_at=date(2026, 3, 11),
            counterparty_tax_id="B12345674",
            counterparty_name="Servizi SRL",
            counterparty_country="DE",
            base_total=Decimal("3000.00"),
            iva_category=IvaCategory("intra_community_service_acquisition_reverse_charge"),
        )
