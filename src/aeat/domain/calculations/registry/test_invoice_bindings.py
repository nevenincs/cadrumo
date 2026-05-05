"""Modelo-agnostic tests for invoice-source binding resolution.

Invoice-source bindings let any IVA-relevant modelo (303, 349, 369, 390 and
follow-ups) aggregate facts from the user's invoice ledger without owning the
ledger schema. The InvoiceObservation model is the wire-format every modelo
shares; the resolver evaluates a revision's invoice bindings against a stream
of observations.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ._bindings import (
    InvoiceObservation,
    invoice_binding_requirements,
    resolve_invoice_binding_values,
)
from ._errors import RegistryValidationError
from ._schema import (
    DataBindingDefinition,
    LegalReference,
    ModeloRevision,
    PeriodSelector,
    SourceReference,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


_LEGAL_REF = "test-iva-base"
_SOURCE_REF = "test-iva-source"


def _legal() -> LegalReference:
    return LegalReference(
        id=_LEGAL_REF,
        evidence_tier="legal_authority",
        authority="boe",
        kind="ley",
        corpus_ref="corpus/normatives/test.json",
        document_id="BOE-A-1992-28740",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740",
        effective_from=date(1992, 1, 1),
        review_status="reviewed",
    )


def _source() -> SourceReference:
    return SourceReference(
        id=_SOURCE_REF,
        evidence_tier="official_source_guidance",
        authority="aeat",
        kind="instructions",
        corpus_path="corpus/aeat_official/test.html",
        sha256="0" * 64,
        bytes=1,
        retrieved_at=date(2026, 1, 1),
        source_url="https://sede.agenciatributaria.gob.es/",
        review_status="reviewed",
    )


def _binding(
    *,
    binding_id: str,
    fact: str,
    op: str,
    claves: tuple[str, ...] = (),
    rectification_scope: str = "any",
) -> DataBindingDefinition:
    selector: dict[str, str | int | Decimal | bool | tuple[str, ...]] = {"fact": fact}
    if claves:
        selector["claves"] = claves
    if rectification_scope != "any":
        selector["rectification_scope"] = rectification_scope
    return DataBindingDefinition(
        id=binding_id,
        source="invoice",
        selector=selector,
        aggregation={"op": op},
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )


def _revision(*bindings: DataBindingDefinition) -> ModeloRevision:
    return ModeloRevision(
        id="test-revision",
        valid_from=date(2020, 1, 1),
        period_selector=PeriodSelector(year_from=2020, periods=("0A",)),
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
        bindings=bindings,
    )


def _observation(
    *,
    party: str,
    country: str,
    base: str,
    clave: str | None,
    is_rectification: bool = False,
    previous: str | None = None,
    period: str | None = None,
    year: int | None = None,
) -> InvoiceObservation:
    return InvoiceObservation(
        invoice_id=f"inv-{party}-{base}",
        party_tax_id=party,
        country_code=country,
        transaction_date=date(2026, 3, 15),
        base_amount=Decimal(base),
        intracommunity_clave=clave,
        is_rectification=is_rectification,
        rectified_base_previous=Decimal(previous) if previous is not None else None,
        rectified_period=period,
        rectified_year=year,
    )


def test_invoice_observation_validates_country_and_clave_enums() -> None:
    with pytest.raises(ValidationError):
        InvoiceObservation(
            invoice_id="inv-1",
            party_tax_id="DE123",
            country_code="de",
            transaction_date=date(2026, 1, 1),
            base_amount=Decimal("1"),
        )
    with pytest.raises(ValidationError):
        InvoiceObservation(
            invoice_id="inv-1",
            party_tax_id="DE123",
            country_code="DE",
            transaction_date=date(2026, 1, 1),
            base_amount=Decimal("1"),
            intracommunity_clave="X",
        )


def test_invoice_observation_rejects_inconsistent_rectification_metadata() -> None:
    with pytest.raises(ValidationError):
        InvoiceObservation(
            invoice_id="inv-1",
            party_tax_id="DE1",
            country_code="DE",
            transaction_date=date(2026, 1, 1),
            base_amount=Decimal("1"),
            is_rectification=True,
        )
    with pytest.raises(ValidationError):
        InvoiceObservation(
            invoice_id="inv-1",
            party_tax_id="DE1",
            country_code="DE",
            transaction_date=date(2026, 1, 1),
            base_amount=Decimal("1"),
            rectified_base_previous=Decimal("2"),
        )


def test_resolve_invoice_binding_values_aggregates_operator_count_distinct_per_clave_set() -> None:
    revision = _revision(
        _binding(
            binding_id="iva-operadores-count",
            fact="operator_count",
            op="count_distinct",
            claves=("E", "M"),
            rectification_scope="exclude_rectifications",
        ),
    )
    observations = (
        _observation(party="DE1", country="DE", base="100", clave="E"),
        _observation(party="DE1", country="DE", base="200", clave="E"),  # same operator deduped
        _observation(party="FR1", country="FR", base="50", clave="M"),
        _observation(party="IT1", country="IT", base="75", clave="A"),  # outside selected claves
    )

    resolved = resolve_invoice_binding_values(revision, observations)

    assert resolved == {"iva-operadores-count": Decimal("2")}


def test_resolve_invoice_binding_values_sums_base_amounts_within_selector_scope() -> None:
    revision = _revision(
        _binding(
            binding_id="iva-base-total",
            fact="base_sum",
            op="sum",
            claves=("E", "M", "T"),
            rectification_scope="exclude_rectifications",
        ),
    )
    observations = (
        _observation(party="DE1", country="DE", base="1000.50", clave="E"),
        _observation(party="FR1", country="FR", base="500.25", clave="T"),
        _observation(party="IT1", country="IT", base="999.99", clave="A"),  # filtered out
        _observation(
            party="ES1",
            country="ES",
            base="200",
            clave="E",
            is_rectification=True,
            previous="180",
            period="1T",
            year=2025,
        ),  # rectification, excluded by scope
    )

    resolved = resolve_invoice_binding_values(revision, observations)

    assert resolved == {"iva-base-total": Decimal("1500.75")}


def test_resolve_invoice_binding_values_computes_rectification_delta_sum() -> None:
    revision = _revision(
        _binding(
            binding_id="iva-rect-delta",
            fact="rectified_base_delta_sum",
            op="sum",
            claves=("E",),
            rectification_scope="only_rectifications",
        ),
    )
    observations = (
        _observation(
            party="DE1",
            country="DE",
            base="1100",
            clave="E",
            is_rectification=True,
            previous="1000",
            period="1T",
            year=2025,
        ),
        _observation(
            party="FR1",
            country="FR",
            base="450",
            clave="E",
            is_rectification=True,
            previous="500",
            period="2T",
            year=2025,
        ),
        _observation(party="IT1", country="IT", base="200", clave="E"),  # not a rectification
    )

    resolved = resolve_invoice_binding_values(revision, observations)

    assert resolved == {"iva-rect-delta": Decimal("50")}


def test_resolve_invoice_binding_values_rejects_unsupported_fact() -> None:
    revision = _revision(_binding(binding_id="iva-bad", fact="not_a_fact", op="sum"))
    with pytest.raises(RegistryValidationError):
        resolve_invoice_binding_values(revision, ())


def test_resolve_invoice_binding_values_rejects_op_mismatch_for_fact() -> None:
    revision = _revision(_binding(binding_id="iva-op", fact="operator_count", op="sum"))
    with pytest.raises(RegistryValidationError):
        resolve_invoice_binding_values(revision, ())


def test_invoice_binding_requirements_groups_bindings_by_clave_and_scope() -> None:
    revision = _revision(
        _binding(
            binding_id="b-ops",
            fact="operator_count",
            op="count_distinct",
            claves=("E", "M"),
            rectification_scope="exclude_rectifications",
        ),
        _binding(
            binding_id="b-base",
            fact="base_sum",
            op="sum",
            claves=("E", "M"),
            rectification_scope="exclude_rectifications",
        ),
        _binding(
            binding_id="b-rect-base",
            fact="rectified_base_delta_sum",
            op="sum",
            claves=("E",),
            rectification_scope="only_rectifications",
        ),
    )

    requirements = invoice_binding_requirements(revision)

    assert len(requirements) == 2
    by_scope = {req.rectification_scope: req for req in requirements}
    assert by_scope["exclude_rectifications"].binding_ids == ("b-base", "b-ops")
    assert by_scope["exclude_rectifications"].claves == ("E", "M")
    assert by_scope["only_rectifications"].binding_ids == ("b-rect-base",)
    assert by_scope["only_rectifications"].claves == ("E",)


def test_resolve_invoice_binding_values_ignores_non_invoice_bindings() -> None:
    invoice_binding = _binding(
        binding_id="iva-base",
        fact="base_sum",
        op="sum",
        claves=("E",),
    )
    other_binding = DataBindingDefinition(
        id="other",
        source="manual_input",
        selector={"field": "noop"},
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )
    revision = _revision(invoice_binding, other_binding)

    resolved = resolve_invoice_binding_values(
        revision,
        (_observation(party="DE1", country="DE", base="100", clave="E"),),
    )

    assert resolved == {"iva-base": Decimal("100")}
