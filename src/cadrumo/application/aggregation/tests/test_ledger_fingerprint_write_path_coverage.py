"""Every IVA fact an operator can write is watched by the current fingerprint field set.

The filing-snapshot fingerprint is the only thing the BORRADOR verify drift gate
compares, so a transaction field that the manual ledger write path can change,
and that the IVA resolvers read, but that the current field set does not hash,
is an edit verify cannot see: the draft is sealed on values computed under the
old fact. That is how ``investment_asset_id`` and
``counterparty_identification_state`` slipped past field-set version 2.

The writable set is read from the real write path rather than copied here, so a
new operator-settable field reaches this check without anyone remembering to
list it: the attributes :func:`~application.ledger.actions_common.mutation_signature`
folds (the fields whose change makes an edit a change at all) and the literal
payload keys :func:`~application.ledger.actions_manual.transaction_from_command`
builds a row from. The IVA-read set is the ``Transaction`` and ``RawTransaction``
fields accessed by name in the IVA aggregation modules. Matching by attribute
name over-approximates what is read, which errs toward demanding a decision.
"""

from __future__ import annotations

import ast
import inspect
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

import pytest

from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawTransaction
from ...ledger.actions_common import mutation_signature
from ...ledger.actions_manual import transaction_from_command
from ..ledger_filing_snapshot import (
    CURRENT_FINGERPRINT_FIELD_SET_VERSION,
    FINGERPRINT_FIELDS_V2,
    FINGERPRINT_FIELDS_V3,
    FINGERPRINT_FIELDS_V5,
    FINGERPRINT_FIELDS_V7,
    fingerprint_fields,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_AGGREGATION_ROOT = Path(__file__).resolve().parents[1]
#: Modules whose reads decide an IVA casilla or an IVA admission outcome.
_IVA_AGGREGATION_MODULES: tuple[Path, ...] = (
    *sorted(_AGGREGATION_ROOT.glob("*iva*.py")),
    _AGGREGATION_ROOT / "prorrata_volume.py",
    _AGGREGATION_ROOT / "m303_arrivals.py",
)

#: Writable, IVA-read fields deliberately left out of the fingerprint, each with
#: the reason. Adding an entry here is a reviewed decision, not a way to pass.
INTENTIONALLY_EXCLUDED: dict[str, str] = {
    "attachment_ids": (
        "presence of a stored copy only drives the non-blocking missing-source-document warnings, which "
        "verification recomputes from the live catalogue on every run and never reads from a sealed "
        "fingerprint; no casilla amount or admission outcome depends on it"
    ),
}

_RAW_PREFIX = "raw."


def _signature_fields(source: str) -> frozenset[str]:
    """Return the ``transaction.X`` / ``raw.X`` attributes a signature's source folds."""
    tree = ast.parse(source)
    fields: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "transaction" and node.attr != "raw":
                fields.add(node.attr)
            elif node.value.id == "raw":
                fields.add(f"{_RAW_PREFIX}{node.attr}")
    return frozenset(fields)


def _payload_keys(function: Callable[..., object]) -> frozenset[str]:
    """Return the literal keys of the ``payload`` dict a row builder validates.

    ``raw`` itself is a container whose operator-settable parts the signature
    already names one by one, so it is not a field of its own here.
    """
    tree = ast.parse(inspect.getsource(function))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "payload"
            and isinstance(node.value, ast.Dict)
        ):
            keys.update(
                key.value for key in node.value.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)
            )
    keys.discard("raw")
    return frozenset(keys)


def writable_transaction_fields() -> frozenset[str]:
    """Fields the manual ledger write path can set, read from its real code."""
    fields = _signature_fields(inspect.getsource(mutation_signature)) | _payload_keys(transaction_from_command)
    known = set(Transaction.model_fields) | {f"{_RAW_PREFIX}{name}" for name in RawTransaction.model_fields}
    unknown = fields - known
    assert not unknown, f"write-path derivation produced non-fields: {sorted(unknown)}"
    return frozenset(fields)


def iva_read_fields(modules: Iterable[Path]) -> frozenset[str]:
    """Transaction/raw fields accessed by attribute name in the given modules."""
    attributes: set[str] = set()
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        attributes.update(node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute))
    transaction = set(Transaction.model_fields) & attributes
    raw = {f"{_RAW_PREFIX}{name}" for name in set(RawTransaction.model_fields) & attributes}
    return frozenset(transaction | raw)


def unwatched_writable_iva_fields(
    *,
    writable: Iterable[str],
    iva_read: Iterable[str],
    field_set: Iterable[tuple[str, str]],
    excluded: Mapping[str, str],
) -> tuple[str, ...]:
    """Return writable, IVA-read fields neither hashed by ``field_set`` nor excluded.

    A field is hashed when an accessor path is the field itself or descends
    into it (``m210_income_classification.payer_id`` watches
    ``m210_income_classification``).
    """
    paths = tuple(path for _label, path in field_set)

    def hashed(field: str) -> bool:
        return any(path == field or path.startswith(f"{field}.") for path in paths)

    return tuple(
        sorted(field for field in set(writable) & set(iva_read) if not hashed(field) and field not in excluded)
    )


def test_every_writable_iva_field_is_in_the_current_field_set_or_excluded_with_a_reason() -> None:
    missing = unwatched_writable_iva_fields(
        writable=writable_transaction_fields(),
        iva_read=iva_read_fields(_IVA_AGGREGATION_MODULES),
        field_set=fingerprint_fields(CURRENT_FINGERPRINT_FIELD_SET_VERSION),
        excluded=INTENTIONALLY_EXCLUDED,
    )
    assert missing == (), (
        f"writable IVA facts the current fingerprint cannot see: {list(missing)}; "
        "add them under a new field-set version, or exclude each with a reason"
    )


def test_the_derivation_sees_the_fields_this_guard_exists_for() -> None:
    """The guard is only as good as its inputs; prove they reach the real fields."""
    writable = writable_transaction_fields()
    iva_read = iva_read_fields(_IVA_AGGREGATION_MODULES)
    for field in ("investment_asset_id", "counterparty_identification_state", "input_classification"):
        assert field in writable
        assert field in iva_read
    assert "raw.booked_date" in writable
    assert {"deduction_provenance", "operation_date"} <= writable & iva_read
    assert all(reason.strip() for reason in INTENTIONALLY_EXCLUDED.values())
    assert set(INTENTIONALLY_EXCLUDED) <= writable & iva_read


def test_the_accrual_date_is_writable_and_no_iva_module_reads_it() -> None:
    """The Renta accrual date moves no IVA period, so the IVA readers must not touch it."""
    assert "accrual_date" in writable_transaction_fields()
    assert "accrual_date" not in iva_read_fields(_IVA_AGGREGATION_MODULES)


def test_the_guard_would_have_caught_the_v2_gap() -> None:
    """Against the V2 field set, the check names the V3 facts and the later V5, V6 and V8 ones."""
    missing = unwatched_writable_iva_fields(
        writable=writable_transaction_fields(),
        iva_read=iva_read_fields(_IVA_AGGREGATION_MODULES),
        field_set=FINGERPRINT_FIELDS_V2,
        excluded=INTENTIONALLY_EXCLUDED,
    )
    assert missing == (
        "counterparty_identification_state",
        "deduction_provenance",
        "exemption_article",
        "investment_asset_id",
        "iva_vehicle_use",
        "operation_date",
        "purchase_invoice_evidence_id",
    )


def test_the_guard_would_have_caught_the_v3_gap() -> None:
    """Detached evidence, the operation date and the factura evidence the art. 97 gate reads escaped V3."""
    missing = unwatched_writable_iva_fields(
        writable=writable_transaction_fields(),
        iva_read=iva_read_fields(_IVA_AGGREGATION_MODULES),
        field_set=FINGERPRINT_FIELDS_V3,
        excluded=INTENTIONALLY_EXCLUDED,
    )
    assert missing == (
        "deduction_provenance",
        "exemption_article",
        "iva_vehicle_use",
        "operation_date",
        "purchase_invoice_evidence_id",
    )


def test_the_guard_would_have_caught_the_v5_gap() -> None:
    """The stated vehicle use was the one writable fact V5 could not see, before the exemption article became one."""
    missing = unwatched_writable_iva_fields(
        writable=writable_transaction_fields(),
        iva_read=iva_read_fields(_IVA_AGGREGATION_MODULES),
        field_set=FINGERPRINT_FIELDS_V5,
        excluded=INTENTIONALLY_EXCLUDED,
    )
    assert missing == ("exemption_article", "iva_vehicle_use")


def test_the_guard_would_have_caught_the_v7_gap() -> None:
    """The stated art. 20.Uno exemption article is the one writable fact V7 cannot see."""
    missing = unwatched_writable_iva_fields(
        writable=writable_transaction_fields(),
        iva_read=iva_read_fields(_IVA_AGGREGATION_MODULES),
        field_set=FINGERPRINT_FIELDS_V7,
        excluded=INTENTIONALLY_EXCLUDED,
    )
    assert missing == ("exemption_article",)


#: An isolated write path shaped like the real signature, with one extra writable field.
_FIXTURE_SIGNATURE_SOURCE = (
    "def fixture_signature(transaction):\n"
    "    raw = transaction.raw\n"
    "    return (raw.booked_date, transaction.iva_rate, transaction.operation_date)\n"
)


def test_a_writable_field_dropped_from_the_field_set_fails_the_guard(tmp_path: Path) -> None:
    """Isolated fixture: a write path that sets a field the field set does not hash."""
    fixture_writable = _signature_fields(_FIXTURE_SIGNATURE_SOURCE)
    assert fixture_writable == {"raw.booked_date", "iva_rate", "operation_date"}
    iva_reader = tmp_path / "fixture_iva_reader.py"
    iva_reader.write_text(
        "def read(row):\n    return row.raw.booked_date, row.iva_rate, row.operation_date\n",
        encoding="utf-8",
    )
    field_set = (("booked_date", "raw.booked_date"), ("iva_rate", "iva_rate"))

    missing = unwatched_writable_iva_fields(
        writable=fixture_writable,
        iva_read=iva_read_fields((iva_reader,)),
        field_set=field_set,
        excluded={},
    )
    assert missing == ("operation_date",)

    assert (
        unwatched_writable_iva_fields(
            writable=fixture_writable,
            iva_read=iva_read_fields((iva_reader,)),
            field_set=(*field_set, ("operation_date", "operation_date")),
            excluded={},
        )
        == ()
    )
    assert (
        unwatched_writable_iva_fields(
            writable=fixture_writable,
            iva_read=iva_read_fields((iva_reader,)),
            field_set=field_set,
            excluded={"operation_date": "fixture reason"},
        )
        == ()
    )
