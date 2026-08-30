"""A fourth IVA screen axis: could this category's base EVER be routed, independent of any row.

The two existing IVA quantity screens are both OBSERVATION-DEPENDENT:
``unsupported_ledger_iva_observations`` asks whether a ROW is selected by some
binding, and ``unrouted_ledger_iva_quantities`` asks whether a consumed row's
FACT is drawn -- and its own docstring states it must not fire on a zero
total, so a by-law cuota-less category (whose cuota IS zero) is filtered
before any exclusion set could matter. Neither can answer a question that
holds true or false from the registry alone, before a single ledger row
exists: "could this revision's bindings EVER draw this category's base?"

``structurally_unroutable_iva_base_categories`` answers exactly that, and
this module proves it end to end: the pure registry-level function, its live
wiring into ``LedgerIvaAggregationSourceResolver`` (scoped to this taxpayer's
actually-present categories on Modelo 303), and a mutation proof that the
detector has teeth.

Real-behaviour: the committed Modelo 303 registry revision and real
:class:`Transaction` fixtures driven through the production classification
path, never a hand-built ``IvaLedgerObservation`` standing in for the
projection. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

import shutil
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core import Period
from ....core.resources import bundled_path
from ....domain.bienes_inversion import BienesInversionIvaRegister
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.ledger_bindings import structurally_unroutable_iva_base_categories
from ....domain.calculations.registry.loader import load_registry_tree
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.iva import CUOTA_LESS_M303_IVA_CATEGORIES, IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import isolated_runtime_profile
from .._modelo_bindings import LedgerIvaAggregationSourceResolver
from .._source_mesh import CalculationSourceContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2025, 2, 10, 12, 0, tzinfo=UTC)
_Q1_2025 = Period.from_year_and_code(2025, "1T")
_BUCKET_ID = "38383838-3838-4838-8838-383838383838"


def _m303_revision() -> ModeloRevision:
    return bundled_authority().snapshot("303", filing_year=_Q1_2025.filing_year, period="1T").revision


def _domestic_zero_sale() -> Transaction:
    """A zero-rated domestic sale: zero cuota by law, a real base by law.

    ``IvaCategory.DOMESTIC_ZERO`` is the canonical proof this screen exists
    for: cuota-less BY LAW (so Screen 1/2's cuota-side reasoning never fires
    on it), while the base is a real declared amount M303 currently has no
    ``base_amount_sum`` binding for at all.
    """
    raw = RawTransaction(
        provider_transaction_id="zero-rated-1",
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=Decimal("500.00"),
        currency="EUR",
        counterparty="Comprador Nacional SL",
        description="venta tipo cero",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"row": "zero-rated-1"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("500.00"),
            "iva_rate": Decimal("0.00"),
            "iva_amount": Decimal("0.00"),
            "iva_category": IvaCategory.DOMESTIC_ZERO,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def _domestic_general_sale() -> Transaction:
    """A fully-covered domestic sale, the negative control."""
    raw = RawTransaction(
        provider_transaction_id="general-1",
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=Decimal("1210.00"),
        currency="EUR",
        counterparty="Comprador Nacional SL",
        description="venta tipo general",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="f" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"row": "general-1"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("210.00"),
            "iva_category": IvaCategory.DOMESTIC_GENERAL,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def test_domestic_zero_is_structurally_unroutable_on_m303() -> None:
    """Positive control: the registry-only question, no observation needed.

    Per Ruling B, this is the proof the screen exists at all: cuota-less by
    law, base-bearing by law, and reused from
    :data:`CUOTA_LESS_M303_IVA_CATEGORIES` would wrongly suppress it.
    """
    unroutable = structurally_unroutable_iva_base_categories(_m303_revision())

    assert IvaCategory.DOMESTIC_ZERO in unroutable, (
        "refutation, not a tuning target: if this ever fails, M303 has gained a base_amount_sum "
        "binding for domestic_zero and the fixture/finding is stale, not the screen"
    )


def test_a_fully_covered_category_is_not_reported() -> None:
    """Negative control: the domestic general tier IS routed on the committed revision."""
    unroutable = structurally_unroutable_iva_base_categories(_m303_revision())

    assert IvaCategory.DOMESTIC_GENERAL not in unroutable


def test_the_out_of_scope_declaration_is_not_a_re_export_of_cuota_less() -> None:
    """Ruling B, checked rather than asserted: the two suppression sets differ.

    ``CUOTA_LESS_M303_IVA_CATEGORIES`` answers "does this produce a cuota?" and
    would wrongly suppress DOMESTIC_ZERO here (base-bearing despite being
    cuota-less). The out-of-scope set for THIS screen is a real, smaller,
    independently-justified set -- proved by two cuota-less members landing on
    opposite sides of this screen's membership test: DOMESTIC_ZERO (base-
    bearing by law) IS reported, while REGIMEN_SIMPLIFICADO (settled from
    módulos, not the ledger at all) is NOT. If reusing CUOTA_LESS as the
    suppressor here, both would be silenced together.
    """
    unroutable = set(structurally_unroutable_iva_base_categories(_m303_revision()))

    assert IvaCategory.DOMESTIC_ZERO in CUOTA_LESS_M303_IVA_CATEGORIES
    assert IvaCategory.REGIMEN_SIMPLIFICADO in CUOTA_LESS_M303_IVA_CATEGORIES
    assert IvaCategory.DOMESTIC_ZERO in unroutable
    assert IvaCategory.REGIMEN_SIMPLIFICADO not in unroutable


def test_the_advisory_fires_live_for_a_present_unroutable_category(tmp_path: Path) -> None:
    """Positive control end to end: live wiring, scoped to this ledger's own categories."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(TransactionCatalogue.from_transactions((_domestic_zero_sale(),)))
        resolution = LedgerIvaAggregationSourceResolver(
            transaction_repository=repository,
            prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID),
            investment_asset_register=BienesInversionIvaRegister(),
            investment_asset_profile_id=_BUCKET_ID,
        ).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=2025,
                period=_Q1_2025,
                revision=_m303_revision(),
            ),
        )

    advisories = [
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "structurally_unroutable_base_category"
    ]
    assert len(advisories) == 1, "the live domestic_zero residue must surface exactly one advisory"
    message = advisories[0].message
    assert "domestic_zero" in message
    assert "no tax is lost" in message


def test_the_advisory_stays_silent_when_the_category_never_appears(tmp_path: Path) -> None:
    """Negative control: an unroutable category not present in this ledger must not fire.

    Scoping the live advisory to present categories is deliberate (a taxpayer
    with no domestic_zero row should not see a blanket registry dump), and
    this is the assertion that would catch a regression to "fire on every
    unroutable category regardless of relevance."
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(TransactionCatalogue.from_transactions((_domestic_general_sale(),)))
        resolution = LedgerIvaAggregationSourceResolver(
            transaction_repository=repository,
            prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID),
            investment_asset_register=BienesInversionIvaRegister(),
            investment_asset_profile_id=_BUCKET_ID,
        ).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=2025,
                period=_Q1_2025,
                revision=_m303_revision(),
            ),
        )

    assert not [
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "structurally_unroutable_base_category"
    ]


def test_mutation_stripping_the_intra_community_supply_binding_reds_the_negative_control(tmp_path: Path) -> None:
    """Mutation proof, from an isolated scratch copy (never the tracked tree).

    ``INTRA_COMMUNITY_SUPPLY`` is drawn by exactly ONE ``base_amount_sum``
    binding on this revision (unlike ``DOMESTIC_GENERAL``, which several
    bindings cover redundantly), so retargeting its sole binding's category
    genuinely strips all coverage rather than leaving a second binding to
    mask the mutation. Confirms the screen then reports
    ``INTRA_COMMUNITY_SUPPLY`` as unroutable -- proving the detector actually
    reads the bindings rather than returning a fixed answer.
    """
    bundled_root = bundled_path("registry", "aeat")
    scratch_root = tmp_path / "registry-mutant" / "aeat"
    (scratch_root / "modelos").mkdir(parents=True)
    shutil.copytree(bundled_root / "modelos" / "303", scratch_root / "modelos" / "303")
    for catalogue_dir in (
        "apoderamientos",
        "authorization.d",
        "calendars",
        "categories",
        "iva",
        "legal",
        "topics",
        "treaties",
    ):
        source = bundled_root / catalogue_dir
        if source.is_dir():
            shutil.copytree(source, scratch_root / catalogue_dir)
        elif source.exists():
            shutil.copy2(source, scratch_root / catalogue_dir)

    # Located by its NAME, not its ordinal. Fragment files carry a sequence
    # prefix that registry sweeps renumber -- this one moved from 0003 to 0004
    # and the pinned path stopped existing, so the mutation never ran and the
    # negative control proved nothing about the assertion it guards.
    bindings_dir = scratch_root / "modelos" / "303" / "revisions" / _m303_revision().id / "bindings"
    candidates = sorted(bindings_dir.glob("*intracom-export-base*.toml"))
    assert len(candidates) == 1, f"expected exactly one intracom-export-base fragment, found {candidates}"
    bindings_path = candidates[0]
    original = bindings_path.read_text(encoding="utf-8")
    mutated = original.replace('categories = ["intra_community_supply"]', 'categories = ["domestic_general"]', 1)
    assert mutated != original, "the mutation target string was not found -- test is stale"
    bindings_path.write_text(mutated, encoding="utf-8")

    modelos, _catalogues = load_registry_tree(scratch_root)
    mutated_revision = next(m for m in modelos if m.id == "303").revisions[_m303_revision().id]

    unroutable = structurally_unroutable_iva_base_categories(mutated_revision)
    assert IvaCategory.INTRA_COMMUNITY_SUPPLY in unroutable, (
        "stripping the only binding drawing intra_community_supply's base must red the negative control"
    )
