"""The establishment ladder is reached BY THE CONFIRM PATH, not merely by a test.

Every rung of the ladder, the identification and establishment split, the
printed-country vocabulary, the alpha-3 correspondence and the Spanish postal
derivation were built and gated, and nothing in production called any of them:
the routing function and the direction selector both landed with zero callers
outside their own module. A suite over the ladder proves the ladder works. It
proves nothing about whether a document a person confirms ever reaches it, and
that is the property this module exists to hold.

**So every case here drives the real confirm.** Bytes are written through the
real encrypted evidence service, read back by the real extraction the CLI
invokes, and handed to
:func:`~application.ledger.confirm_invoice_draft_from_evidence` --- the function
the ``aeat app ledger evidence confirm`` verb calls. Nothing constructs a draft,
calls the ladder, or assembles criteria directly. A case that did would be
green in exactly the state this module was written to detect.

**The territory asserted is one no default could produce.** The counterparty's
address states a Las Palmas postal code, so the answer is ``ES_CANARIAS``: a
rung returning a constant, a resolver defaulting to the majority population, or
a confirm path never reaching the ladder at all each yield the mainland or
nothing, and all three fail here. Asserting a mainland territory would have been
satisfied by every one of those failures.

**The exhaustion direction is asserted too**, because it is the one that
produces no red when it breaks. A document whose paper settles nothing must
surface a resolvable review item naming the counterparty, and must carry NO
scope --- silently resolving to the peninsula is the failure the whole ladder
exists to prevent, and it is invisible from the outside.

See Also:
    :func:`~application.ledger.resolve_confirmed_establishment`
        The confirm-path resolution these cases reach through the verb.
    :class:`~application.ledger.CounterpartyEstablishment`
        What the ladder settles, carried onto the confirmation result.
    :class:`~domain.iva.IvaTerritorialScope`
        The closed territory axis every rung resolves into.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....domain.iva import InvoiceKind, IvaTerritorialScope
from .._establishment_ladder import EstablishmentRung
from .._evidence_draft import confirm_invoice_draft_from_evidence
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import seeded_filer_profile as seeded_filer_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects", "seeded_filer_profile"]

_CORPUS = Path(__file__).parent / "_evidence_corpus"

# The bundled Facturae specimen. Its SellerParty block already carries the
# CountryCode and PostCode elements the ladder's two address rungs read, so the
# only edit any case makes is to the postal VALUE -- the document shape, the
# parse path and the element locations are the corpus's, not the test's.
_FACTURAE = "facturae_32_series_and_parties_invoice.xml"
_SELLER_MAINLAND_CODE = "08009"  # Barcelona, as the specimen ships
_SELLER_CANARIAS_CODE = "35001"  # Las Palmas de Gran Canaria

# The specimen's own parties. The seller is the counterparty on a RECEIVED
# document, which is the direction every case here confirms under.
_SELLER_TAX_ID = "45821337R"
_SELLER_NAME = "Marta"


def _corpus(name: str) -> str:
    return (_CORPUS / name).read_text(encoding="utf-8")


def _stored(
    xml: str,
    *,
    settings: Settings,
    objects: SecureObjectRepository,
    tmp_path: Path,
    name: str,
) -> str:
    staged = tmp_path / name
    staged.write_text(xml, encoding="utf-8")
    return _make_svc(settings, objects).add(bucket_id=_BUCKET_ID, source_path=staged).record.evidence_id


def _facturae_with_seller_in(postal_code: str) -> str:
    """Return the specimen with the SELLER's postal code replaced.

    Only the seller's block is edited, and the edit is asserted to have landed:
    a fixture whose markup drifted must fail as a broken fixture rather than as
    a ladder that resolved nothing.
    """
    xml = _corpus(_FACTURAE)
    assert xml.count(f"<PostCode>{_SELLER_MAINLAND_CODE}</PostCode>") == 1
    edited = xml.replace(
        f"<PostCode>{_SELLER_MAINLAND_CODE}</PostCode>",
        f"<PostCode>{postal_code}</PostCode>",
        1,
    )
    assert f"<PostCode>{postal_code}</PostCode>" in edited
    return edited


def _facturae_without_addresses() -> str:
    """Return the specimen with every address block's country and postcode gone.

    The exhaustion fixture. Both address rungs lose their source and the
    concordance rung has no foreign registration to corroborate, so the ladder
    walks its whole length and settles nothing -- which is the state a bare
    domestic invoice presents and the one a silent default would hide.
    """
    xml = _corpus(_FACTURAE)
    for element in ("PostCode", "CountryCode"):
        while f"<{element}>" in xml:
            head, _, rest = xml.partition(f"<{element}>")
            _, _, tail = rest.partition(f"</{element}>")
            xml = head + tail
    assert "<PostCode>" not in xml
    assert "<CountryCode>" not in xml
    return xml


def _confirmed(
    xml: str,
    *,
    settings: Settings,
    objects: SecureObjectRepository,
    tmp_path: Path,
    name: str,
):
    evidence_id = _stored(xml, settings=settings, objects=objects, tmp_path=tmp_path, name=name)
    return confirm_invoice_draft_from_evidence(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        counterparty_country="ES",
        evidence_id=evidence_id,
        counterparty_name=_SELLER_NAME,
        settings=settings,
        invoice_repository=InvoiceCatalogueRepository(objects=objects),
    )


def test_a_confirmed_canarian_counterparty_resolves_its_territory_through_the_verb(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The headline: a real document, a real confirm, a resolved territory.

    ``ES_CANARIAS`` is reachable here only if the confirm path routed the
    counterparty into the ladder, the country rung matched the specimen's
    alpha-3 ``ESP`` through the correspondence, and the postal rung it gates
    read the Las Palmas code. Any link missing yields ``None`` or the mainland.
    """
    confirmation = _confirmed(
        _facturae_with_seller_in(_SELLER_CANARIAS_CODE),
        settings=isolated_settings,
        objects=secure_objects,
        tmp_path=tmp_path,
        name="facturae_canarias.xml",
    )

    establishment = confirmation.establishment
    assert establishment is not None
    assert establishment.counterparty.scope is IvaTerritorialScope.ES_CANARIAS
    assert establishment.counterparty.rung is EstablishmentRung.SPANISH_POSTAL_CODE


def test_the_resolved_scope_reaches_the_criteria_as_a_declared_fact(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The scope arrives at the assembly through the declared-facts channel.

    Asserted on the ISSUER slot because the document is RECEIVED: the
    counterparty issued it, so its territory is the issuer's. A wiring that
    filled the customer slot would place the filer's counterparty on the filer's
    own side, and the scope would be carried while meaning the opposite.
    """
    confirmation = _confirmed(
        _facturae_with_seller_in(_SELLER_CANARIAS_CODE),
        settings=isolated_settings,
        objects=secure_objects,
        tmp_path=tmp_path,
        name="facturae_declared.xml",
    )

    establishment = confirmation.establishment
    assert establishment is not None
    declared_issuer = establishment.declared.issuer_scope
    assert declared_issuer is not None
    assert declared_issuer.value is IvaTerritorialScope.ES_CANARIAS
    # The counterparty slot must NOT have been filled from the same answer: one
    # resolution belongs to one party, and a wiring that wrote both would place
    # every operation inside a single territory.
    assert establishment.declared.customer_scope is None


def test_a_document_whose_paper_settles_nothing_reaches_the_review_gate(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """Exhaustion surfaces a resolvable item and invents no territory.

    The direction that produces no red when it breaks: a confirm path that
    quietly resolved the peninsula here would pass every other case in this
    module and mis-territory the whole Canarian and Ceutan population.
    """
    confirmation = _confirmed(
        _facturae_without_addresses(),
        settings=isolated_settings,
        objects=secure_objects,
        tmp_path=tmp_path,
        name="facturae_exhausted.xml",
    )

    establishment = confirmation.establishment
    assert establishment is not None
    assert establishment.counterparty.scope is None
    assert establishment.counterparty.rung is None
    assert establishment.declared.issuer_scope is None

    reasons = {item.reason for item in establishment.review_items}
    assert reasons, "an exhausted ladder must surface a resolvable review item"
    assert any("establishment" in item.reason.value for item in establishment.review_items)
    # The counterparty must be nameable from the item: an operator cannot answer
    # a question that does not say which entity it is about.
    assert any(_SELLER_TAX_ID in item.detail for item in establishment.review_items)
