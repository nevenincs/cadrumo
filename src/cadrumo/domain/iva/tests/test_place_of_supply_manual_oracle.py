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
from datetime import date
from typing import Any

import pytest

from ....core.resources.bundled_data import bundled_path
from ..classification import (
    CustomerTaxStatus,
    InvoiceKind,
    IvaInvoiceClassificationCriteria,
    IvaTerritorialScope,
    TransactionKind,
    classify_iva,
)
from ..place_of_supply import place_of_supply_rule
from ..schema import EUMemberState, IvaCategory
from ..supply_nature import SupplyNature

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ORACLE_PATH = bundled_path() / "corpus/manual_oracles/iva-2025-lugar-realizacion-entrega-intracomunitaria.json"


def _oracle() -> dict[str, Any]:
    return json.loads(_ORACLE_PATH.read_text(encoding="utf-8"))


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


def test_the_classifier_reproduces_the_manual_outcome() -> None:
    """The parity itself: AEAT states the treatment, the engine derives it.

    The criteria are read from the oracle rather than typed here, so the case
    cannot drift into asserting something the recorded operation does not
    describe.
    """
    oracle = _oracle()
    operation = oracle["operation"]

    criteria = IvaInvoiceClassificationCriteria(
        transaction_date=date(oracle["source"]["year"], 6, 15),
        issuer_residency=IvaTerritorialScope(operation["issuer_residency"]),
        customer_residency=IvaTerritorialScope(operation["customer_residency"]),
        customer_identification_state=EUMemberState(operation["customer_member_state"]),
        customer_tax_status=CustomerTaxStatus(operation["customer_tax_status"]),
        kind=TransactionKind(operation["transaction_kind"]),
        direction=InvoiceKind(operation["direction"]),
    )

    result = classify_iva(criteria)

    assert result.category is IvaCategory(oracle["expected"]["iva_category"])


def test_the_grounding_row_reads_the_two_articles_the_manual_reasons_through() -> None:
    """The manual's reasoning is a two-step, and the row must encode the same one.

    AEAT locates the supply by where the transport began (art. 68) and only then
    reaches the exemption for goods destined to another Member State (art. 25).
    A row that cited only one of the two would still classify correctly while
    losing the half of the reasoning that explains why.
    """
    oracle = _oracle()
    expected = oracle["expected"]

    result = classify_iva(
        IvaInvoiceClassificationCriteria(
            transaction_date=date(oracle["source"]["year"], 6, 15),
            issuer_residency=IvaTerritorialScope(oracle["operation"]["issuer_residency"]),
            customer_residency=IvaTerritorialScope(oracle["operation"]["customer_residency"]),
            customer_identification_state=EUMemberState(oracle["operation"]["customer_member_state"]),
            customer_tax_status=CustomerTaxStatus(oracle["operation"]["customer_tax_status"]),
            kind=TransactionKind(oracle["operation"]["transaction_kind"]),
            direction=InvoiceKind(oracle["operation"]["direction"]),
        ),
    )
    rule = place_of_supply_rule(result.matched_rule_id, on=date(oracle["source"]["year"], 6, 15))

    assert expected["located_by"] in rule.legal_references
    assert rule.establishing_reference == expected["treatment_established_by"]
    assert rule.supply_nature is SupplyNature(expected["supply_nature"])
