"""A confirmation record says which checks ran when it was minted.

A record predating the structured-path fix attests only the checks that ran at
its own minting, and nothing on disk distinguished it from one minted under the
full set. A later audit reading such a record as evidence the arithmetic and
regime checks passed would be reading a claim the record never made.

**The trap this module exists to hold shut.** "Which checks ran" is easy to
record as a hand-written list of names -- and that list is a second declaration
of the check set, which drifts from the one the readers execute the moment a
check is added. That is the same two-lists defect that let the structured reader
run no checks at all, returning one layer up in the record. So the stamp is
DERIVED from :data:`~application.ledger.deterministic_findings.DETERMINISTIC_CHECKS`, and the case
below adds a check to that declaration and asserts the stamp moves on its own.

**Three states, not two.** ``None`` means the record makes no claim; an empty
tuple means the set was recorded and was empty. A record minted before this
field existed is the first, and reading it as either extreme is a lie -- toward
alarm if read as "no check ran", toward assurance if read as "every current
check ran".

See Also:
    :data:`~application.ledger.deterministic_findings.DETERMINISTIC_CHECKS`
        The one declaration the stamp is derived from.
    :class:`~application.ledger.confirmation_record.InvoiceConfirmationRecord`
        The record that carries it.
"""

from __future__ import annotations

import pytest

# Imported absolutely, not as `from .. import <module>`: the test needs the
# MODULE object to scope an attribute, and the package-facade gate reads any
# `from .. import` edge as reaching through the inert namespace.
import cadrumo.application.ledger.deterministic_findings as deterministic_findings_module

from ....tests.attribute_scope import scoped_attribute
from ..deterministic_findings import (
    DETERMINISTIC_CHECKS,
    DeterministicCheck,
    deterministic_check_names,
    deterministic_findings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_INVOICE_ID_1 = "c" * 64
_INVOICE_ID_2 = "d" * 64


def test_the_stamp_names_every_declared_check() -> None:
    """The stamp and the executed set are the same declaration, read two ways."""
    assert deterministic_check_names() == tuple(check.name for check in DETERMINISTIC_CHECKS)
    assert deterministic_check_names() == (
        "closure_identities",
        "regime_contradiction",
        "postal_code_shape",
    )


def test_a_check_added_to_the_declaration_moves_the_stamp_by_itself() -> None:
    """The anti-drift proof, and the reason the stamp is derived rather than written.

    A hand-written name list passes every other case in this module while
    silently describing a stale set. This one fails against that implementation:
    it adds a check to the declaration and asserts the stamp follows with no
    second place updated.
    """
    before = deterministic_check_names()

    added = DeterministicCheck("a_check_that_did_not_exist", lambda draft: ())
    with scoped_attribute(deterministic_findings_module, "DETERMINISTIC_CHECKS", (*DETERMINISTIC_CHECKS, added)):
        after = deterministic_check_names()

    assert after == (*before, "a_check_that_did_not_exist")
    assert len(after) == len(before) + 1


def test_a_check_added_to_the_declaration_also_runs() -> None:
    """The other half: the declaration is what executes, not merely what is named.

    Without this, the stamp could be derived from a list nothing runs -- a record
    truthfully naming checks that never executed, which is worse than the gap it
    replaced because it reads as evidence.
    """
    from ....core.draft_discrepancy import DraftDiscrepancyKind
    from ..evidence_draft import DraftDiscrepancyFinding, InvoiceDraft

    sentinel = DraftDiscrepancyFinding(kind=DraftDiscrepancyKind.ROLE_UNRESOLVED, detail="sentinel")
    with scoped_attribute(
        deterministic_findings_module,
        "DETERMINISTIC_CHECKS",
        (*DETERMINISTIC_CHECKS, DeterministicCheck("sentinel_check", lambda draft: (sentinel,))),
    ):
        findings = deterministic_findings(InvoiceDraft())

    assert sentinel in findings


def test_the_names_are_the_checks_own_not_their_findings() -> None:
    """The closure check raises three discrepancy kinds, so it is not named after one.

    Naming a check after one of its findings describes a fraction of what it
    does, and a later reader auditing "did the breakdown check run" would find no
    such name and conclude it did not.
    """
    assert "closure_identities" in deterministic_check_names()
    assert "arithmetic_closure" not in deterministic_check_names()


def test_a_minted_record_carries_the_stamp() -> None:
    """The deliverable: a record actually says which checks ran when it was minted.

    Everything above proves the stamp is derived correctly. This proves it
    reaches the record, which is the only place a later audit will look.
    """
    from decimal import Decimal

    from ..confirmation_record import build_confirmation_record
    from ..evidence_draft import InvoiceDraft

    record = build_confirmation_record(
        bucket_id="bucket-checks-run",
        invoice_id=_INVOICE_ID_1,
        evidence_reference="ev-structured-001",
        evidence_sha256="a" * 64,
        draft=InvoiceDraft(taxable_base=Decimal("100.00")),
        extractor="exact_structured",
        confirmed_by="gestor@example.test",
        overrides={},
    )

    assert record.checks_run == deterministic_check_names()
    # Not None: a record minted now makes a claim. The None state is reserved for
    # records that predate the field, and conflating the two would erase exactly
    # the distinction this stamp exists to draw.
    assert record.checks_run is not None


def test_the_stamp_is_not_folded_into_the_derived_identity() -> None:
    """Adding a check must not re-address an existing confirmation.

    The id folds the OUTCOME -- who confirmed what against which evidence -- so a
    retry matches and the idempotency guard holds. Folding the check set in would
    change every id the moment the product grew a check, so two records of the
    same confirmation would stop matching for a reason having nothing to do with
    the confirmation.
    """
    from decimal import Decimal

    from ..confirmation_record import InvoiceConfirmationRecord, build_confirmation_record
    from ..evidence_draft import InvoiceDraft

    def _mint() -> InvoiceConfirmationRecord:
        return build_confirmation_record(
            bucket_id="bucket-checks-run",
            invoice_id=_INVOICE_ID_2,
            evidence_reference="ev-structured-002",
            evidence_sha256="b" * 64,
            draft=InvoiceDraft(taxable_base=Decimal("100.00")),
            extractor="exact_structured",
            confirmed_by="gestor@example.test",
            overrides={},
        )

    before = _mint()
    with scoped_attribute(
        deterministic_findings_module,
        "DETERMINISTIC_CHECKS",
        (*DETERMINISTIC_CHECKS, DeterministicCheck("late_arrival", lambda draft: ())),
    ):
        after = _mint()

    assert after.checks_run != before.checks_run
    assert after.confirmation_id == before.confirmation_id
