"""The engine reproduces AEAT's own worked example on where a supply is located.

The place-of-supply grounding says which article places an operation. This proves
the claim against an independent authority: a worked example published in the
Manual práctico IVA, whose outcome AEAT states in its own words, reproduced by
the classifier without being told the answer.

**Why the expected values are not figures.** The existing manual oracles are
Modelo 100 payloads keyed by casilla id, because what they check is arithmetic.
What a place-of-supply rule produces is not a number -- it is *where* the
operation is located and therefore which treatment applies. The oracle is
categorical for that reason, and forcing it into a numeric shape would have meant
inventing figures the manual does not state.

**Why this is not tautological.** The expected category comes from the manual's
own reasoning -- the transport starts in the Península, so art. 68 locates the
supply here, and the goods leave for another Member State, so art. 25 may relieve
it -- and not from running the classifier and recording what it said. The oracle
also carries the verbatim Spanish, extracted from the bundled PDF rather than
retyped, so a reader can check the expectation against the source without
trusting this file.

See Also:
    :class:`~domain.iva.IvaCategory`
        The treatment the worked example resolves to.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from ....core.resources.bundled_data import bundled_path
from ..classification import (
    IvaInvoiceClassificationCriteria,
    resolve_iva_classification_catalogue,
)
from ..place_of_supply import place_of_supply_rule
from ..schema import IvaCategory
from ..supply_nature import SupplyNature
from .classification_authority_support import classify_with_registry_rules

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    """Lease the bundled generation, which carries the IVA runtime catalogues."""
    with _indexed_authority_for_test().operation() as pinned:
        yield pinned


_ORACLE_PATH = bundled_path() / "corpus/manual_oracles/iva-2025-lugar-realizacion-entrega-intracomunitaria.json"


def _oracle() -> dict[str, Any]:
    return json.loads(_ORACLE_PATH.read_text(encoding="utf-8"))


def _oracle_criteria(
    oracle: dict[str, Any], *, operation: PinnedAuthorityOperation
) -> IvaInvoiceClassificationCriteria:
    """Project the recorded operation through the criteria model's own registry fields."""
    operation_case = oracle["operation"]
    on = date(oracle["source"]["year"], 6, 15)
    vocabulary = resolve_iva_classification_catalogue(on, operation=operation)
    return IvaInvoiceClassificationCriteria.model_validate(
        {
            "transaction_date": on,
            "issuer_residency": vocabulary.require_territorial_scope(operation_case["issuer_residency"]),
            "customer_residency": vocabulary.require_territorial_scope(operation_case["customer_residency"]),
            "customer_identification_state": operation_case["customer_member_state"],
            "customer_tax_status": vocabulary.require_customer_tax_status(operation_case["customer_tax_status"]),
            "kind": operation_case["transaction_kind"],
            "direction": operation_case["direction"],
        },
    )


def test_the_oracle_quotes_the_bundled_manual_that_it_names() -> None:
    """The provenance stamp must attach to the artefact the figures came from.

    A manual oracle names a source PDF, a page and a digest. If the digest does
    not match the bundled file, the stamp attests something other than what
    shipped -- which is the failure mode that lets an AEAT-branded name sit on
    text nobody can re-derive.
    """
    oracle = _oracle()
    source = oracle["source"]

    pdf = bundled_path() / source["relative_pdf_path"]
    assert pdf.is_file(), "the oracle names a manual PDF that is not bundled"

    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert digest == source["source_pdf_sha256"], (
        "the bundled manual is not the artefact this oracle was taken from; "
        "the quoted text cannot be trusted against it"
    )

    quoted = oracle["raw_evidence"]["quoted_text"]
    assert "sujetas al IVA español" in quoted
    assert "otro Estado miembro de la Unión Europea" in quoted


def test_the_classifier_reproduces_the_manual_outcome(*, operation: PinnedAuthorityOperation) -> None:
    """The parity itself: AEAT states the treatment, the engine derives it.

    The criteria are read from the oracle rather than typed here, so the case
    cannot drift into asserting something the recorded operation does not
    describe.
    """
    oracle = _oracle()
    criteria = _oracle_criteria(oracle, operation=operation)

    result = classify_with_registry_rules(criteria, operation=operation)

    assert result.category == IvaCategory(oracle["expected"]["iva_category"])


def test_the_grounding_row_reads_the_two_articles_the_manual_reasons_through() -> None:
    """The manual's reasoning is a two-step, and the row must encode the same one.

    AEAT locates the supply by where the transport began (art. 68) and only then
    reaches the exemption for goods destined to another Member State (art. 25).
    A row that cited only one of the two would still classify correctly while
    losing the half of the reasoning that explains why.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        oracle = _oracle()
        expected = oracle["expected"]

        result = classify_with_registry_rules(
            _oracle_criteria(oracle, operation=_authority_operation_for_test), operation=_authority_operation_for_test
        )
        rule = place_of_supply_rule(
            result.matched_rule_id,
            on=date(oracle["source"]["year"], 6, 15),
            operation=_authority_operation_for_test,
            projected_year=date(oracle["source"]["year"], 6, 15).year,
        )

        assert expected["located_by"] in rule.legal_references
        assert rule.establishing_reference == expected["treatment_established_by"]
        assert rule.supply_nature == SupplyNature(expected["supply_nature"])
