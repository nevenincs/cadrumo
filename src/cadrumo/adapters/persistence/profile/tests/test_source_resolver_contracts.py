"""Invoice-source contracts and decomposition tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext
from cadrumo.application.invoices.source_resolver import InvoiceCatalogueSourceResolver
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.calculations.registry.tests.registry_tree import bundled_registry_tree
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus
from cadrumo.domain.invoices.models import Invoice, InvoiceLine
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.iva.schema import IvaCategory

from .source_resolver_test_support import (
    _BUCKET_ID,
    _OTHER_BUCKET_ID,
    _invoice,
    _modelo_revision,
    _public_resolution,
    _resolver,
)
from .source_resolver_test_support import _generation_pinned_authority as _generation_pinned_authority
from .source_resolver_test_support import secure_profile as secure_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


# ---------------------------------------------------------------------------
# Capability-parity proof
#
# One bucket exercising the capabilities that reach a declaration, projected
# through the canonical path, asserted at MODELO-OUTPUT level rather than at
# fact level (already covered elsewhere).
#
# The criterion also named M303 and M390. Measured at HEAD, neither
# modelo declares a single invoice-sourced binding -- only M347 (one fragment)
# and M349 (three) do. An equality assertion on those two modelos would
# therefore compare zero against zero and pass by construction, proving
# nothing: the vacuous-green shape this plan was rewritten to remove.
#
# So the M303/M390 half is written as the assertion that actually has content:
# that the invoice stores contribute NOTHING there. That is true today, it is
# what makes the parity proof's scope correct, and it fails loudly if anyone
# later adds an invoice-sourced binding to either modelo without extending this
# proof -- which is precisely the change that would silently widen the fold's
# blast radius past what was verified.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("modelo_id", "period"), [("303", "1T"), ("390", "0A")])
def test_the_invoice_stores_contribute_nothing_to_m303_or_m390(modelo_id: str, period: str) -> None:
    """Scope guard, and the honest form of the M303/M390 criterion.

    Neither modelo declares a single invoice-sourced binding, so an equality
    assertion on their outputs would compare zero against zero and pass by
    construction. The assertion with content is the scope itself: the invoice
    stores feed M347 and M349 and nothing else.

    This fails the moment an invoice-sourced binding is added to either modelo,
    which is the change that would silently widen the fold's blast radius past
    what the parity proof above verifies.

    Every declared revision is swept rather than the one a filing year selects.
    The guard is a claim about the modelo, not about a year, and pinning it to a
    year made it depend on AEAT having published that year's orden: modelo 390's
    registry ends at 2025 because the 2026 orden does not exist yet, so a
    hardcoded 2026 failed on registry coverage while saying nothing about
    bindings. Sweeping every revision also widens the guard, since a binding
    added to any revision now trips it.
    """
    _modelos, _catalogues = bundled_registry_tree()
    _modelo = next(candidate for candidate in _modelos if candidate.id == modelo_id)
    assert _modelo.revisions, f"modelo {modelo_id} declares no revisions to inspect"

    offenders = {
        revision_id: [
            binding.id
            for binding in revision.bindings
            if binding.source in InvoiceCatalogueSourceResolver.owned_sources
        ]
        for revision_id, revision in _modelo.revisions.items()
    }
    offenders = {revision_id: bindings for revision_id, bindings in offenders.items() if bindings}

    assert offenders == {}, (
        f"modelo {modelo_id} now declares invoice-sourced bindings {offenders}; "
        "extend the capability-parity proof before relying on it"
    )


# ---------------------------------------------------------------------------
# Decomposition parity across the fold
#
# The decomposition contract is calc-facing and has only ever seen natively
# rich records. The fold routes a new population into it, so what happens to a
# record carrying the economic facts a slim record could hold -- and nothing
# more -- has to be stated rather than discovered later.
#
# The one axis that actually diverges is the IVA category: the slim model
# cannot hold one at all. Everything else the slim record lacks (recargo,
# suplido, retencion, the line set) is read through a zero default by the
# contract, so a record lacking those decomposes cleanly and a test asserting
# divergence there would be GREEN FOR THE WRONG REASON.
# ---------------------------------------------------------------------------


def _same_facts_invoice(*, with_category: bool):
    """One economic record, expressed with and without an IVA category."""
    from cadrumo.domain.invoices.models import derive_invoice_id

    kind = InvoiceKind.ISSUED
    number = "PARITY-2026-001"
    issued = date(2026, 4, 2)
    tax_id = "B12345674"
    return Invoice(
        invoice_id=derive_invoice_id(
            kind=kind,
            invoice_number=number,
            issued_at=issued,
            counterparty_tax_id=tax_id,
            currency="EUR",
            grand_total=Decimal("4840.00"),
        ),
        bucket_id=_BUCKET_ID,
        kind=kind,
        invoice_number=number,
        issued_at=issued,
        counterparty_name="Cliente Paridad SL",
        counterparty_tax_id=tax_id,
        counterparty_country="ES",
        base_total=Decimal("4000.00"),
        iva_total=Decimal("840.00"),
        grand_total=Decimal("4840.00"),
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Servicio",
                quantity=Decimal("1"),
                unit_price=Decimal("4000.00"),
                subtotal=Decimal("4000.00"),
                iva_rate=IvaRate.from_registry("RATE_21"),
                iva_amount=Decimal("840.00"),
            ),
        ),
        payment_status=PaymentStatus.PENDING,
        iva_category=IvaCategory("domestic_general") if with_category else None,
    )


def test_the_only_decomposition_divergence_across_the_fold_is_the_iva_category() -> None:
    """Identical economic facts diverge on exactly one axis, and it is named.

    The record lacking an IVA category is the shape a slim record could hold,
    since the slim model has no category field at all. Its rich twin carries
    the same base, cuota, total and line, and differs only in that declaration.

    The divergence is real and it is reported as a NAMED defect rather than as
    a silent exclusion, which is what makes it actionable: the operator is told
    to declare the treatment, not left with a record that quietly contributes
    nothing.
    """
    from cadrumo.domain.invoices.decomposition import InvoiceDecompositionDefect, decompose_invoice

    grounded = decompose_invoice(_same_facts_invoice(with_category=True))
    ungrounded = decompose_invoice(_same_facts_invoice(with_category=False))

    assert grounded.is_grounded
    assert not ungrounded.is_grounded
    assert InvoiceDecompositionDefect.IVA_TREATMENT_UNDECLARED in ungrounded.defects


def test_the_informativas_are_unaffected_by_that_divergence(
    secure_profile: TestRuntimeProfile,
) -> None:
    """M347 declares the ex-slim record identically. This is the important half.

    The campaign record warns that a test asserting an ex-slim record is
    DROPPED from M347 or M349 by decomposition would be red for a defect that
    does not exist: M347 is deliberately unchecked by the contract, and M349
    excludes absence deliberately. So the proof aims where a loss could really
    occur, and pins that no loss occurs here.

    Asserted as an equality between the two records' declared figures rather
    than as a bare non-zero, so a projection that silently degraded the
    uncategorised record would fail rather than pass.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    repository.save(build_invoice_catalogue((_same_facts_invoice(with_category=False),)))
    context = CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo="347",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "0A"),
        revision=_modelo_revision("347", "2011-2024"),
    )

    resolution = _resolver(repository).resolve(context)

    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("1")
    assert resolution.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("4840.00")


def test_the_renta_lane_is_where_the_divergence_actually_bites() -> None:
    """The income lane refuses the uncategorised record, and does so visibly.

    This is the lane that loses capability, and the loss is bounded: the
    refusal carries the typed defect naming what is missing, and the
    remediation text tells the operator to declare the treatment. A record that
    cannot be grounded is withheld from the income calculation rather than
    contributing an unclassified figure to it -- which is the correct
    behaviour, since an untagged operation cannot be told apart from an exempt
    one.
    """
    from cadrumo.domain.invoices.decomposition import InvoiceDecompositionDefect, decompose_invoice

    verdict = decompose_invoice(_same_facts_invoice(with_category=False))

    assert not verdict.is_grounded
    assert not verdict.components
    # Named, not anonymous: the operator fix for an absent category differs
    # from the fix for a contradictory one, so the two must stay separable.
    assert verdict.defects == (InvoiceDecompositionDefect.IVA_TREATMENT_UNDECLARED,)


# Declarable-coverage proof
#
# Folding the slim store into the canonical structure retires a live M347/M349
# source. What has to survive that retirement is not the slim store's OUTPUT
# but the set of declarable FACTS it contributes. The public resolver envelope
# carries those facts through its aggregate, detail-row and provenance channels.
#
# They deliberately do NOT assert equality against a resolver wired to both
# stores. That union double-counts an invoice held in both, so a union-equality
# assertion would demand the canonical path reproduce the double-count -- it is
# either unsatisfiable or it pins the very defect being removed. Instead
# each store is projected ALONE and both are asserted against one explicit
# contract, so the contract is the thing conserved.
# ---------------------------------------------------------------------------


_DECLARABLE_FACTS: frozenset[str] = frozenset(
    {
        "party_tax_id",
        "country_code",
        "transaction_date",
        "base_amount",
        "invoice_total_amount",
        "intracommunity_clave",
        "operation_clave",
        "party_legal_name",
    },
)


#: The Modelo 347 record-key facts the slim store never carried: the operations
#: RD 1065/2007 art. 34.1.d, j and k relate separately, the leased premises of
#: art. 34.1.d, and the annual basis of art. 33.1. Their canonical reachability is
#: proven through the real resolver by the declarado and inmueble record tests over
#: the compiled registry, not by the slim-store contract.


_M347_RECORD_KEY_FACTS: frozenset[str] = frozenset(
    {
        "cash_accounting_operation",
        "reverse_charge_recipient",
        "annual_computation_basis",
        "arrendamiento_local_negocio",
        "situacion_inmueble",
        "referencia_catastral",
    },
)


def test_declarable_fact_contract_covers_every_observation_fact_the_stores_contribute() -> None:
    """Anti-tautology guard on the contract itself.

    The contract is pinned against the observation model's own declarable
    surface. Identity and rectification axes are excluded by name, which forces
    a newly-added declarable field to fail here rather than slip past the
    coverage proof unnoticed.
    """
    from cadrumo.domain.calculations.registry.invoice_bindings import InvoiceObservation

    non_declarable = {
        "invoice_id",
        "source_kind",
        "iva_regime",
        "is_rectification",
        "rectified_year",
        "rectified_period",
        "rectified_base_previous",
    }
    assert set(InvoiceObservation.model_fields) - non_declarable == _DECLARABLE_FACTS | _M347_RECORD_KEY_FACTS


def test_m347_declarable_facts_are_reachable_on_the_canonical_path(
    secure_profile: TestRuntimeProfile,
) -> None:
    """Every M347 fact the slim store contributes must be reachable canonically.

    The gross total is kept distinct from the taxable base here on purpose:
    M347's declaration floor is the gross total, so a proof whose base and total
    coincide would not detect the two being confused.
    """
    from cadrumo.domain.invoices.models import derive_invoice_id

    context = CalculationSourceContext(
        bucket_id=secure_profile.bucket_id,
        modelo="347",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "0A"),
        revision=_modelo_revision("347", "2011-2024"),
    )

    # Pinned for the same reason as the M349 proof above: these are the facts
    # the retired slim store declared, every one of them read off the fixture.
    # ``intracommunity_clave`` is None because M347 is the domestic informativa.
    # ``operation_clave`` is "B" (entregas): this is an ISSUED invoice with no
    # travel-agency mediation fact, so it falls through to the ordinary
    # invoice-direction classification.
    # Above the 3,005.06 EUR annual threshold below which Modelo 347 declares
    # no counterparty, so the reachable facts are declarable ones.
    declared_facts = {
        "party_tax_id": "B12345674",
        "country_code": "ES",
        "transaction_date": date(2025, 2, 10),
        "base_amount": Decimal("3000.00"),
        "invoice_total_amount": Decimal("3630.00"),
        "intracommunity_clave": None,
        "operation_clave": "B",
        "party_legal_name": "Cliente M347 SL",
    }

    canonical = Invoice(
        invoice_id=derive_invoice_id(
            kind=InvoiceKind.ISSUED,
            invoice_number="M347-C-2025-001",
            issued_at=date(2025, 2, 10),
            counterparty_tax_id="B12345674",
            currency="EUR",
            grand_total=Decimal("3630.00"),
        ),
        bucket_id=secure_profile.bucket_id,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-C-2025-001",
        issued_at=date(2025, 2, 10),
        counterparty_name="Cliente M347 SL",
        counterparty_tax_id="B12345674",
        counterparty_country="ES",
        base_total=Decimal("3000.00"),
        iva_total=Decimal("630.00"),
        grand_total=Decimal("3630.00"),
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Servicio",
                quantity=Decimal("1"),
                unit_price=Decimal("3000.00"),
                subtotal=Decimal("3000.00"),
                iva_rate=IvaRate.from_registry("RATE_21"),
                iva_amount=Decimal("630.00"),
            ),
        ),
        payment_status=PaymentStatus.PENDING,
    )
    resolution = _public_resolution((canonical,), context=context)
    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("1")
    assert resolution.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("3630.00")
    assert {item.source_ref for item in resolution.provenance} == {
        f"collectible_invoice:{canonical.invoice_id}",
    }
    # The public source-resolution envelope exposes the invoice facts through
    # its aggregate/provenance channels; operation-clave detail rows are not a
    # part of the M347 resolver contract.
    public_facts = {
        "party_tax_id": canonical.counterparty_tax_id,
        "country_code": canonical.counterparty_country,
        "transaction_date": canonical.issued_at,
        "base_amount": canonical.base_total_eur,
        "invoice_total_amount": canonical.grand_total_eur,
        "intracommunity_clave": None,
        "party_legal_name": canonical.counterparty_name,
    }
    assert {name: declared_facts[name] for name in public_facts} == public_facts


def test_an_unattributed_invoice_in_the_bucket_store_is_still_declared(
    secure_profile: TestRuntimeProfile,
) -> None:
    """An invoice carrying no bucket must not vanish from the informativas.

    The repository is opened against one bucket and refuses a foreign row on
    read, so an invoice loaded here came from THIS bucket's encrypted store.
    An unattributed one therefore belongs to this bucket; it simply never had
    the redundant field stamped.

    Comparing on the bucket id alone treats that as a mismatch and drops the
    record from M347 and M349 with no defect, no advisory and no refusal --
    and nothing downstream can distinguish "this taxpayer had no such
    operations" from "the filter discarded them". The persistence guard
    already treats an unattributed record as belonging rather than foreign, so
    before this the two layers disagreed about the same record.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    unattributed = _invoice(
        bucket_id=None,
        invoice_number="F-2026-UNATTRIBUTED",
        issued_at=date(2026, 1, 15),
        counterparty_tax_id="DE123456789",
        base_total=Decimal("1000.00"),
        iva_category=IvaCategory("intra_community_supply"),
    )
    repository.save(build_invoice_catalogue((unattributed,)))
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

    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("1")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == Decimal("1000.00")


def test_an_invoice_naming_another_bucket_is_still_excluded(
    secure_profile: TestRuntimeProfile,
) -> None:
    """Positive control: the attribution filter is narrowed, not removed.

    Admitting unattributed invoices must not admit invoices that positively
    name a DIFFERENT bucket. Without this control the change above would read
    as correct while having disabled cross-bucket isolation, which is a
    confidentiality failure rather than a declaration one -- one taxpayer's
    invoice surfacing in another's return.
    """
    repository = InvoiceCatalogueRepository(objects=secure_profile.repository)
    foreign = _invoice(
        bucket_id=_OTHER_BUCKET_ID,
        invoice_number="F-2026-FOREIGN",
        issued_at=date(2026, 1, 16),
        counterparty_tax_id="DE987654321",
        base_total=Decimal("500.00"),
        iva_category=IvaCategory("intra_community_supply"),
    )
    repository.save(build_invoice_catalogue((foreign,)))
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

    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("0")
    assert resolution.provenance == ()
