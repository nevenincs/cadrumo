"""Reclassifying a row must not erase its prorrata declarations.

``_command_from_patch`` rebuilds a full command from the stored row plus a
patch, and it carried twenty-odd fields across while omitting three:
``art_104_tres_exclusion`` (LIVA art. 104.Tres), ``input_classification``
(art. 106 prorrata especial) and ``prorrata_sector_id`` (arts. 9.1.c / 101
differentiated sectors). The rebuilt command therefore carried ``None`` for all
three and the write erased them — an operator correcting a category or a note
lost three legal declarations and was told the write succeeded.

The no-op guard could not stop it either: ``mutation_signature`` compares these
fields, so set-to-``None`` read as a genuine change and was let through.

``ManualLedgerTransactionPatch`` does not declare them (they are declared at add
time), so carrying the stored value is the only answer available — which is
precisely why the omission was invisible.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.prorrata_exclusions import Art104TresExclusion
from ....domain.iva.prorrata import InputClassification
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..actions_manual import _command_from_patch
from ..models import ManualLedgerTransactionPatch

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "b" * 36
_SECTOR = "sector-a"


def _declared_row() -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="p",
        booked_date=date(2026, 3, 1),
        value_date=None,
        amount=Decimal("100.00"),
        currency="EUR",
        counterparty="Proveedor SL",
        description="compra",
        provenance=RawProvenance(
            source_path=Path("x"),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 3, 1, tzinfo=UTC),
            provider_name="t",
        ),
        raw_fields={},
    )
    transaction = Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "group_label": None,
            "created_at": datetime(2026, 3, 1, tzinfo=UTC),
            "modified_at": datetime(2026, 3, 1, tzinfo=UTC),
        },
    )
    return transaction.model_copy(
        update={
            "art_104_tres_exclusion": Art104TresExclusion.DIRECT_IVA_CUOTAS,
            "input_classification": InputClassification.COMMON,
            "prorrata_sector_id": _SECTOR,
        },
    )


def _rebuild(patch: ManualLedgerTransactionPatch):
    return _command_from_patch(
        bucket_id=_BUCKET,
        current=_declared_row(),
        patch=patch,
        actor="operator",
        source_command="aeat app ledger classify",
    )


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("art_104_tres_exclusion", Art104TresExclusion.DIRECT_IVA_CUOTAS),
        ("input_classification", InputClassification.COMMON),
        ("prorrata_sector_id", _SECTOR),
    ],
)
def test_an_unrelated_edit_keeps_each_prorrata_declaration(field: str, expected: object) -> None:
    """Each of the three is checked separately.

    One case would pass while the other two were still being erased, which is
    how three fields went missing together in the first place.
    """
    assert getattr(_rebuild(ManualLedgerTransactionPatch(notes="corrected note")), field) == expected


def test_a_reclassification_keeps_them_too() -> None:
    """The reclassify path is the one an operator actually runs."""
    rebuilt = _rebuild(ManualLedgerTransactionPatch(category_id="office-supplies"))

    assert rebuilt.art_104_tres_exclusion is Art104TresExclusion.DIRECT_IVA_CUOTAS
    assert rebuilt.input_classification is InputClassification.COMMON
    assert rebuilt.prorrata_sector_id == _SECTOR


def test_a_row_that_declared_none_gains_none() -> None:
    """Carrying forward must not invent a declaration the row never made."""
    plain = _declared_row().model_copy(
        update={"art_104_tres_exclusion": None, "input_classification": None, "prorrata_sector_id": None},
    )

    rebuilt = _command_from_patch(
        bucket_id=_BUCKET,
        current=plain,
        patch=ManualLedgerTransactionPatch(notes="n"),
        actor="operator",
        source_command="aeat app ledger classify",
    )

    assert rebuilt.art_104_tres_exclusion is None
    assert rebuilt.input_classification is None
    assert rebuilt.prorrata_sector_id is None
